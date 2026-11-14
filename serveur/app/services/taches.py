"""Service de gestion des tâches longues, de la machine à états, des verrous exclusifs
par dossier et du Centre de validation humaine (Phase 3).

Règles non négociables appliquées par construction :
- Règle 1 (Option A) : aucune tâche ne peut atteindre l'état `terminee` sans passer par
  `a_valider` puis recevoir une décision humaine explicite (`confirmation_humaine_explicite=True`)
  d'un utilisateur authentifié du bureau. Un jeton d'agent local ne peut jamais valider une tâche.
- Règle 4 : si des champs candidats ou des pièces obligatoires manquent ou sont expirés,
  la tâche passe automatiquement à l'état `suspendue` avec la liste exacte des manques
  (aucune valeur par défaut n'est jamais inventée).
- Règle 5 : aucune donnée personnelle dans les journaux applicatifs ni dans `journal_audit`.
  Le récapitulatif de pré-remplissage, les détails d'étape, la capture de contrôle et les
  commentaires de validation sont chiffrés au repos en AES-256-GCM avec la clé du bureau.
- Règle 7 : les étapes de chaque démarche proviennent des fichiers YAML `config/demarches/*.yaml`.
"""

from __future__ import annotations

import json
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.chiffrement import (
    chiffrer_champ,
    chiffrer_octets,
    dechiffrer_champ,
    dechiffrer_octets,
)
from app.core.config import Parametres
from app.core.erreurs import AccesRefuse, Conflit, DonneesInvalides, NonTrouve
from app.db.base import maintenant_utc
from app.db.tenant import tenant_courant
from app.modeles.journal_audit import ResultatAudit
from app.modeles.tache import (
    ACTION_PREREMPLISSAGE,
    ACTIONS_OUVERTURE_PC,
    DecisionValidationHumaine,
    EtapeTache,
    MotifSuspensionTache,
    StatutEtapeTache,
    StatutTache,
    TacheDossier,
    TypeDecisionValidation,
    VerrouDossier,
)
from app.schemas.tache import (
    ContexteDossierExecutionSortie,
    DecisionValidationSortie,
    DemarrerTacheEntree,
    EtapeTacheSortie,
    RejetValidationEntree,
    SignalerErreurTacheEntree,
    SoumissionValidationEntree,
    SuspendreTacheEntree,
    SyntheseCentreValidationSortie,
    TacheCreation,
    TacheSortie,
    TerminerEtapeEntree,
    ValidationHumaineEntree,
    VerrouDossierSortie,
)
from app.services import audit
from app.services.candidats import obtenir_candidat
from app.services.documents import (
    _detecter_type_mime_par_signature,
    _resoudre_chemin_stockage,
    lire_document_dechiffre,
    lister_documents_candidat,
    lister_documents_orm,
)
from app.services.pieces_requises import (
    obtenir_demarche,
    verifier_completude_dossier,
)

# Machine à états stricte : toute transition non listée ici est rejetée (HTTP 409).
TRANSITIONS_AUTORISEES: dict[StatutTache, set[StatutTache]] = {
    StatutTache.EN_ATTENTE: {
        StatutTache.EN_COURS,
        StatutTache.SUSPENDUE,
        StatutTache.ANNULEE,
    },
    StatutTache.EN_COURS: {
        StatutTache.SUSPENDUE,
        StatutTache.A_VALIDER,
        StatutTache.EN_ERREUR,
        StatutTache.ANNULEE,
    },
    StatutTache.SUSPENDUE: {
        StatutTache.EN_ATTENTE,
        StatutTache.ANNULEE,
    },
    StatutTache.A_VALIDER: {
        StatutTache.TERMINEE,
        StatutTache.SUSPENDUE,
        StatutTache.ANNULEE,
    },
    StatutTache.EN_ERREUR: {
        StatutTache.EN_ATTENTE,
        StatutTache.ANNULEE,
    },
    StatutTache.TERMINEE: set(),
    StatutTache.ANNULEE: set(),
}

STATUTS_TACHE_OUVERTE = {
    StatutTache.EN_ATTENTE,
    StatutTache.EN_COURS,
    StatutTache.SUSPENDUE,
    StatutTache.A_VALIDER,
}


def _exiger_tenant(db: Session) -> uuid.UUID:
    tid = tenant_courant(db)
    if tid is None:
        raise RuntimeError("Contexte bureau (tenant) manquant sur la session.")
    return tid


def _verifier_transition(actuel: StatutTache, cible: StatutTache) -> None:
    autorisees = TRANSITIONS_AUTORISEES.get(actuel, set())
    if cible not in autorisees:
        raise Conflit(
            f"Transition d'état interdite : impossible de passer de '{actuel.value}' à '{cible.value}'."
        )


def _obtenir_tache_orm(db: Session, tache_id: uuid.UUID) -> TacheDossier:
    tache = db.scalar(select(TacheDossier).where(TacheDossier.id == tache_id))
    if tache is None:
        raise NonTrouve("Tâche introuvable.")
    return tache


def _exiger_detenteur_agent(tache: TacheDossier, agent_local_id: uuid.UUID | None) -> None:
    """Tâche « Ouvrir sur mon PC » : seul l'agent qui l'a réservée peut agir dessus (jamais un autre
    agent du même bureau). Un humain authentifié (`agent_local_id` nul) reste libre d'agir."""
    if (
        tache.action in ACTIONS_OUVERTURE_PC
        and agent_local_id is not None
        and tache.agent_local_id != agent_local_id
    ):
        raise AccesRefuse("Cette tâche est réservée par un autre agent local.")


def _obtenir_verrou_actif(
    db: Session, candidat_id: uuid.UUID
) -> VerrouDossier | None:
    maintenant = maintenant_utc()
    verrou = db.scalar(
        select(VerrouDossier).where(VerrouDossier.candidat_id == candidat_id)
    )
    if verrou is None:
        return None
    if verrou.expire_le <= maintenant:
        db.delete(verrou)
        db.flush()
        return None
    return verrou


def _acquerir_ou_rafraichir_verrou(
    db: Session,
    *,
    tid: uuid.UUID,
    candidat_id: uuid.UUID,
    tache_id: uuid.UUID,
    detenteur: str,
    duree_secondes: int,
) -> VerrouDossier:
    maintenant = maintenant_utc()
    expiration = maintenant + timedelta(seconds=duree_secondes)
    verrou_existant = _obtenir_verrou_actif(db, candidat_id)

    if verrou_existant is not None:
        if verrou_existant.tache_id != tache_id:
            raise Conflit(
                "Ce dossier candidat est déjà verrouillé par une autre tâche en cours d'exécution."
            )
        verrou_existant.detenteur = detenteur
        verrou_existant.expire_le = expiration
        db.flush()
        return verrou_existant

    nouveau_verrou = VerrouDossier(
        id=uuid.uuid4(),
        tenant_id=tid,
        candidat_id=candidat_id,
        tache_id=tache_id,
        detenteur=detenteur,
        acquis_le=maintenant,
        expire_le=expiration,
    )
    db.add(nouveau_verrou)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise Conflit(
            "Ce dossier candidat est déjà verrouillé par une autre tâche en cours d'exécution."
        ) from exc
    return nouveau_verrou


def _liberer_verrou_dossier(db: Session, *, tache_id: uuid.UUID) -> None:
    verrou = db.scalar(
        select(VerrouDossier).where(VerrouDossier.tache_id == tache_id)
    )
    if verrou is not None:
        db.delete(verrou)
        db.flush()


def _prochaine_etape(etapes: list[EtapeTache]) -> str | None:
    for etape in sorted(etapes, key=lambda e: e.ordre):
        if etape.statut != StatutEtapeTache.TERMINEE:
            return etape.code_etape
    return None


def _serialiser_tache(
    db: Session, tache: TacheDossier, cle_maitresse: bytes
) -> TacheSortie:
    tid = tache.tenant_id
    champs_manquants: list[str] = (
        json.loads(tache.champs_manquants_json)
        if tache.champs_manquants_json
        else []
    )
    pieces_manquantes: list[str] = (
        json.loads(tache.pieces_manquantes_json)
        if tache.pieces_manquantes_json
        else []
    )

    recap: dict[str, Any] | None = None
    if tache.recapitulatif_remplissage_chiffre:
        recap_str = dechiffrer_champ(
            cle_maitresse,
            tid,
            "recapitulatif_remplissage",
            tache.recapitulatif_remplissage_chiffre,
        )
        if recap_str:
            recap = json.loads(recap_str)

    etapes_sortie = [
        EtapeTacheSortie(
            id=e.id,
            ordre=e.ordre,
            code_etape=e.code_etape,
            libelle=e.libelle,
            statut=e.statut,
            cle_idempotence=e.cle_idempotence,
            detail_execution=dechiffrer_champ(
                cle_maitresse, tid, "detail_etape", e.detail_execution_chiffre
            ),
            message_erreur=e.message_erreur,
            nb_tentatives=e.nb_tentatives,
            commencee_le=e.commencee_le,
            terminee_le=e.terminee_le,
        )
        for e in sorted(tache.etapes, key=lambda x: x.ordre)
    ]

    decisions_sortie = [
        DecisionValidationSortie(
            id=d.id,
            tache_id=d.tache_id,
            candidat_id=d.candidat_id,
            decideur_id=d.decideur_id,
            decision=d.decision,
            confirmation_explicite=d.confirmation_explicite,
            commentaire=dechiffrer_champ(
                cle_maitresse, tid, "commentaire_validation", d.commentaire_chiffre
            ),
            reinitialiser_depuis_etape=d.reinitialiser_depuis_etape,
            cree_le=d.cree_le,
        )
        for d in sorted(tache.decisions_validation, key=lambda x: x.cree_le)
    ]

    verrou_actif = _obtenir_verrou_actif(db, tache.candidat_id)
    verrou_sortie = (
        VerrouDossierSortie.model_validate(verrou_actif)
        if verrou_actif is not None and verrou_actif.tache_id == tache.id
        else None
    )

    return TacheSortie(
        id=tache.id,
        candidat_id=tache.candidat_id,
        code_demarche=tache.code_demarche,
        action=tache.action,
        statut=tache.statut,
        motif_suspension=tache.motif_suspension,
        message_alerte=tache.message_alerte,
        champs_manquants=champs_manquants,
        pieces_manquantes=pieces_manquantes,
        recapitulatif_remplissage=recap,
        capture_controle_disponible=bool(tache.chemin_capture_controle_relatif),
        type_mime_capture_controle=tache.type_mime_capture_controle,
        prochaine_etape_a_executer=_prochaine_etape(tache.etapes),
        verrou_actif=verrou_sortie,
        creee_par_id=tache.creee_par_id,
        agent_local_id=tache.agent_local_id,
        demarree_le=tache.demarree_le,
        suspendue_le=tache.suspendue_le,
        soumise_validation_le=tache.soumise_validation_le,
        terminee_le=tache.terminee_le,
        cree_le=tache.cree_le,
        modifie_le=tache.modifie_le,
        etapes=etapes_sortie,
        decisions_validation=decisions_sortie,
    )


def creer_tache(
    db: Session,
    *,
    donnees: TacheCreation,
    acteur_id: uuid.UUID,
    parametres: Parametres,
    cle_maitresse: bytes,
) -> TacheSortie:
    """Crée une tâche longue pour un candidat et une démarche.
    Applique immédiatement la Règle 4 : si des champs candidats ou des pièces justificatives
    obligatoires manquent ou sont invalides, la tâche naît à l'état `suspendue` avec l'alerte
    détaillée (aucune valeur par défaut n'est inventée)."""
    tid = _exiger_tenant(db)

    candidat = obtenir_candidat(
        db, candidat_id=donnees.candidat_id, cle_maitresse=cle_maitresse
    )
    docs_orm = lister_documents_orm(db, candidat_id=candidat.id)
    demarche = obtenir_demarche(
        parametres.dossier_demarches, donnees.code_demarche, db
    )

    tache_ouverte = db.scalar(
        select(TacheDossier.id).where(
            TacheDossier.candidat_id == candidat.id,
            TacheDossier.code_demarche == demarche.code,
            TacheDossier.action == ACTION_PREREMPLISSAGE,
            TacheDossier.statut.in_(STATUTS_TACHE_OUVERTE),
        )
    )
    if tache_ouverte is not None:
        raise Conflit(
            "Une tâche est déjà active ou en attente de validation pour ce candidat et cette démarche."
        )

    completude = verifier_completude_dossier(
        candidat=candidat,
        documents=docs_orm,
        demarche=demarche,
    )

    maintenant = maintenant_utc()
    tache_id = uuid.uuid4()

    if not completude.pret_pour_prerequis:
        motif = (
            MotifSuspensionTache.DONNEE_MANQUANTE
            if completude.champs_candidat_manquants
            else MotifSuspensionTache.PIECE_MANQUANTE_OU_INVALIDE
        )
        alerte = (
            "Dossier incomplet (Règle 4 : aucune valeur par défaut inventée). "
            "Complétez les données ou pièces signalées avant de reprendre la tâche."
        )
        tache = TacheDossier(
            id=tache_id,
            tenant_id=tid,
            candidat_id=candidat.id,
            code_demarche=demarche.code,
            statut=StatutTache.SUSPENDUE,
            motif_suspension=motif,
            message_alerte=alerte,
            champs_manquants_json=json.dumps(completude.champs_candidat_manquants),
            pieces_manquantes_json=json.dumps(
                completude.pieces_manquantes_ou_invalides
            ),
            creee_par_id=acteur_id,
            suspendue_le=maintenant,
        )
    else:
        tache = TacheDossier(
            id=tache_id,
            tenant_id=tid,
            candidat_id=candidat.id,
            code_demarche=demarche.code,
            statut=StatutTache.EN_ATTENTE,
            creee_par_id=acteur_id,
        )

    db.add(tache)
    db.flush()

    for idx, cfg_etape in enumerate(demarche.etapes_tache, start=1):
        est_premiere = idx == 1
        if est_premiere and completude.pret_pour_prerequis:
            statut_etape = StatutEtapeTache.TERMINEE
            cle_idem = "prerequis-initiaux-ok"
            commencee = maintenant
            terminee = maintenant
        elif est_premiere and not completude.pret_pour_prerequis:
            statut_etape = StatutEtapeTache.SUSPENDUE
            cle_idem = None
            commencee = maintenant
            terminee = None
        else:
            statut_etape = StatutEtapeTache.A_FAIRE
            cle_idem = None
            commencee = None
            terminee = None

        etape = EtapeTache(
            id=uuid.uuid4(),
            tenant_id=tid,
            tache_id=tache.id,
            ordre=idx,
            code_etape=cfg_etape.code,
            libelle=cfg_etape.libelle,
            statut=statut_etape,
            cle_idempotence=cle_idem,
            nb_tentatives=1 if est_premiere else 0,
            commencee_le=commencee,
            terminee_le=terminee,
        )
        db.add(etape)

    db.flush()
    db.refresh(tache)

    audit.journaliser(
        db,
        "tache.creation"
        if completude.pret_pour_prerequis
        else "tache.creation_suspendue_prerequis",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="tache",
        ressource_id=tache.id,
        details={
            "code_demarche": demarche.code,
            "statut_initial": tache.statut.value,
            "nb_champs_manquants": len(completude.champs_candidat_manquants),
            "nb_pieces_invalides": len(completude.pieces_manquantes_ou_invalides),
        },
    )
    db.commit()
    return _serialiser_tache(db, tache, cle_maitresse)


def obtenir_tache(
    db: Session, *, tache_id: uuid.UUID, cle_maitresse: bytes
) -> TacheSortie:
    tache = _obtenir_tache_orm(db, tache_id)
    return _serialiser_tache(db, tache, cle_maitresse)


def lister_taches(
    db: Session,
    *,
    cle_maitresse: bytes,
    page: int = 1,
    taille: int = 20,
    statut: StatutTache | None = None,
    candidat_id: uuid.UUID | None = None,
    code_demarche: str | None = None,
) -> tuple[list[TacheSortie], int]:
    _exiger_tenant(db)
    conditions = []
    if statut is not None:
        conditions.append(TacheDossier.statut == statut)
    if candidat_id is not None:
        conditions.append(TacheDossier.candidat_id == candidat_id)
    if code_demarche is not None:
        conditions.append(TacheDossier.code_demarche == code_demarche)

    total = db.scalar(select(func.count(TacheDossier.id)).where(*conditions)) or 0
    lignes = db.scalars(
        select(TacheDossier)
        .where(*conditions)
        .order_by(TacheDossier.cree_le.desc(), TacheDossier.id)
        .offset((page - 1) * taille)
        .limit(taille)
    ).all()
    return [_serialiser_tache(db, t, cle_maitresse) for t in lignes], total


def demarrer_tache(
    db: Session,
    *,
    tache_id: uuid.UUID,
    donnees: DemarrerTacheEntree,
    acteur_id: uuid.UUID | None,
    agent_local_id: uuid.UUID | None,
    parametres: Parametres,
    cle_maitresse: bytes,
) -> TacheSortie:
    """Passe la tâche de `en_attente` à `en_cours` après avoir acquis le verrou exclusif
    du dossier candidat et vérifié les prérequis (Règle 4)."""
    tid = _exiger_tenant(db)
    tache = _obtenir_tache_orm(db, tache_id)
    if tache.action in ACTIONS_OUVERTURE_PC:
        raise Conflit(
            "Cette tâche « Ouvrir sur mon PC » n'est prise en charge que par l'Agent Local "
            "(réservation atomique) : elle ne se démarre pas à la main."
        )
    _verifier_transition(tache.statut, StatutTache.EN_COURS)

    # Contrôle de sécurité Règle 4 juste avant le démarrage effectif
    candidat = obtenir_candidat(
        db, candidat_id=tache.candidat_id, cle_maitresse=cle_maitresse
    )
    docs_orm = lister_documents_orm(db, candidat_id=tache.candidat_id)
    demarche = obtenir_demarche(
        parametres.dossier_demarches, tache.code_demarche, db
    )
    completude = verifier_completude_dossier(
        candidat=candidat, documents=docs_orm, demarche=demarche
    )

    maintenant = maintenant_utc()
    if not completude.pret_pour_prerequis:
        tache.statut = StatutTache.SUSPENDUE
        tache.motif_suspension = (
            MotifSuspensionTache.DONNEE_MANQUANTE
            if completude.champs_candidat_manquants
            else MotifSuspensionTache.PIECE_MANQUANTE_OU_INVALIDE
        )
        tache.message_alerte = (
            "Suspension automatique (Règle 4) : données ou pièces obligatoires manquantes."
        )
        tache.champs_manquants_json = json.dumps(completude.champs_candidat_manquants)
        tache.pieces_manquantes_json = json.dumps(
            completude.pieces_manquantes_ou_invalides
        )
        tache.suspendue_le = maintenant
        audit.journaliser(
            db,
            "tache.suspension_automatique_prerequis",
            ResultatAudit.REFUS,
            acteur_id=acteur_id,
            ressource_type="tache",
            ressource_id=tache.id,
        )
        db.commit()
        raise Conflit(
            "Le dossier ne respecte plus les prérequis obligatoires : la tâche a été suspendue (règle 4)."
        )

    detenteur = (
        donnees.detenteur
        or (f"agent:{agent_local_id}" if agent_local_id else f"utilisateur:{acteur_id}")
    )
    _acquerir_ou_rafraichir_verrou(
        db,
        tid=tid,
        candidat_id=tache.candidat_id,
        tache_id=tache.id,
        detenteur=detenteur,
        duree_secondes=parametres.duree_verrou_dossier_secondes,
    )

    tache.statut = StatutTache.EN_COURS
    tache.demarree_le = tache.demarree_le or maintenant
    if agent_local_id is not None:
        tache.agent_local_id = agent_local_id

    for etape in sorted(tache.etapes, key=lambda e: e.ordre):
        if etape.statut != StatutEtapeTache.TERMINEE:
            etape.statut = StatutEtapeTache.EN_COURS
            etape.commencee_le = etape.commencee_le or maintenant
            etape.nb_tentatives += 1
            break

    audit.journaliser(
        db,
        "tache.demarrage",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="tache",
        ressource_id=tache.id,
        details={
            "agent_local_id": str(agent_local_id) if agent_local_id else None,
            "prochaine_etape": _prochaine_etape(tache.etapes),
        },
    )
    db.commit()
    return _serialiser_tache(db, tache, cle_maitresse)


def renouveler_verrou_tache(
    db: Session,
    *,
    tache_id: uuid.UUID,
    acteur_id: uuid.UUID | None,
    agent_local_id: uuid.UUID | None,
    parametres: Parametres,
    cle_maitresse: bytes,
) -> TacheSortie:
    """Battement de cœur (heartbeat) prolongeant le verrou exclusif d'une tâche `en_cours`."""
    tid = _exiger_tenant(db)
    tache = _obtenir_tache_orm(db, tache_id)
    _exiger_detenteur_agent(tache, agent_local_id)
    if tache.statut != StatutTache.EN_COURS:
        raise Conflit("Seule une tâche en cours peut renouveler son verrou.")

    detenteur = (
        f"agent:{agent_local_id}" if agent_local_id else f"utilisateur:{acteur_id}"
    )
    _acquerir_ou_rafraichir_verrou(
        db,
        tid=tid,
        candidat_id=tache.candidat_id,
        tache_id=tache.id,
        detenteur=detenteur,
        duree_secondes=parametres.duree_verrou_dossier_secondes,
    )
    db.commit()
    return _serialiser_tache(db, tache, cle_maitresse)


def terminer_etape_tache(
    db: Session,
    *,
    tache_id: uuid.UUID,
    code_etape: str,
    donnees: TerminerEtapeEntree,
    acteur_id: uuid.UUID | None,
    agent_local_id: uuid.UUID | None,
    parametres: Parametres,
    cle_maitresse: bytes,
) -> TacheSortie:
    """Marque une étape comme `terminee` de façon idempotente :
    - Si l'étape est déjà `terminee`, ne la rejoue pas et retourne immédiatement l'état courant.
    - Sinon, exige que la tâche soit `en_cours` et que toutes les étapes précédentes soient `terminee`."""
    tid = _exiger_tenant(db)
    tache = _obtenir_tache_orm(db, tache_id)

    etapes_triees = sorted(tache.etapes, key=lambda e: e.ordre)
    cible: EtapeTache | None = None
    for e in etapes_triees:
        if e.code_etape == code_etape:
            cible = e
            break
    if cible is None:
        raise NonTrouve("Étape inconnue pour cette démarche.")

    # Idempotence : une étape déjà terminée n'est jamais rejouée ni réécrite
    if cible.statut == StatutEtapeTache.TERMINEE:
        audit.journaliser(
            db,
            "tache.etape_idempotente_ignoree",
            ResultatAudit.SUCCES,
            acteur_id=acteur_id,
            ressource_type="tache",
            ressource_id=tache.id,
            details={"code_etape": code_etape, "deja_terminee": True},
        )
        db.commit()
        return _serialiser_tache(db, tache, cle_maitresse)

    if tache.statut != StatutTache.EN_COURS:
        raise Conflit("La tâche doit être à l'état 'en_cours' pour valider une étape.")

    for precedente in etapes_triees:
        if precedente.ordre < cible.ordre and precedente.statut != StatutEtapeTache.TERMINEE:
            raise Conflit(
                f"Ordre des étapes non respecté : l'étape précédente '{precedente.code_etape}' n'est pas terminée."
            )

    maintenant = maintenant_utc()
    cible.statut = StatutEtapeTache.TERMINEE
    cible.cle_idempotence = donnees.cle_idempotence
    cible.detail_execution_chiffre = chiffrer_champ(
        cle_maitresse, tid, "detail_etape", donnees.detail_execution
    )
    cible.message_erreur = None
    cible.commencee_le = cible.commencee_le or maintenant
    cible.terminee_le = maintenant
    if cible.nb_tentatives == 0:
        cible.nb_tentatives = 1

    # Active l'étape suivante si elle existe
    for suivante in etapes_triees:
        if suivante.ordre > cible.ordre and suivante.statut != StatutEtapeTache.TERMINEE:
            suivante.statut = StatutEtapeTache.EN_COURS
            suivante.commencee_le = suivante.commencee_le or maintenant
            suivante.nb_tentatives += 1
            break

    # Prolonge le verrou du dossier
    detenteur = (
        f"agent:{agent_local_id}" if agent_local_id else f"utilisateur:{acteur_id}"
    )
    _acquerir_ou_rafraichir_verrou(
        db,
        tid=tid,
        candidat_id=tache.candidat_id,
        tache_id=tache.id,
        detenteur=detenteur,
        duree_secondes=parametres.duree_verrou_dossier_secondes,
    )

    audit.journaliser(
        db,
        "tache.etape_terminee",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="tache",
        ressource_id=tache.id,
        details={
            "code_etape": code_etape,
            "prochaine_etape": _prochaine_etape(tache.etapes),
        },
    )
    db.commit()
    return _serialiser_tache(db, tache, cle_maitresse)


def suspendre_tache(
    db: Session,
    *,
    tache_id: uuid.UUID,
    donnees: SuspendreTacheEntree,
    acteur_id: uuid.UUID | None,
    agent_local_id: uuid.UUID | None,
    cle_maitresse: bytes,
) -> TacheSortie:
    """Suspend une tâche (CAPTCHA/2FA à résoudre par l'humain, donnée manquante, sélecteur
    introuvable), libère le verrou du dossier et conserve intactes les étapes déjà terminées."""
    _exiger_tenant(db)
    tache = _obtenir_tache_orm(db, tache_id)
    _exiger_detenteur_agent(tache, agent_local_id)
    _verifier_transition(tache.statut, StatutTache.SUSPENDUE)

    maintenant = maintenant_utc()
    tache.statut = StatutTache.SUSPENDUE
    tache.motif_suspension = donnees.motif
    tache.message_alerte = donnees.message_alerte
    tache.suspendue_le = maintenant
    tache.champs_manquants_json = (
        json.dumps(donnees.champs_manquants) if donnees.champs_manquants else None
    )
    tache.pieces_manquantes_json = (
        json.dumps(donnees.pieces_manquantes) if donnees.pieces_manquantes else None
    )

    for etape in sorted(tache.etapes, key=lambda e: e.ordre):
        if donnees.code_etape and etape.code_etape == donnees.code_etape:
            if etape.statut != StatutEtapeTache.TERMINEE:
                etape.statut = StatutEtapeTache.SUSPENDUE
                etape.message_erreur = donnees.message_alerte
            break
        if not donnees.code_etape and etape.statut == StatutEtapeTache.EN_COURS:
            etape.statut = StatutEtapeTache.SUSPENDUE
            etape.message_erreur = donnees.message_alerte
            break

    _liberer_verrou_dossier(db, tache_id=tache.id)

    audit.journaliser(
        db,
        "tache.suspension",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="tache",
        ressource_id=tache.id,
        details={
            "motif": donnees.motif.value,
            "code_etape": donnees.code_etape,
            "agent_local_id": str(agent_local_id) if agent_local_id else None,
        },
    )
    db.commit()
    return _serialiser_tache(db, tache, cle_maitresse)


def signaler_erreur_tache(
    db: Session,
    *,
    tache_id: uuid.UUID,
    donnees: SignalerErreurTacheEntree,
    acteur_id: uuid.UUID | None,
    agent_local_id: uuid.UUID | None,
    cle_maitresse: bytes,
) -> TacheSortie:
    """Passe la tâche à l'état `en_erreur`, libère le verrou du dossier et conserve
    les étapes déjà validées pour diagnostic et reprise."""
    _exiger_tenant(db)
    tache = _obtenir_tache_orm(db, tache_id)
    _exiger_detenteur_agent(tache, agent_local_id)
    _verifier_transition(tache.statut, StatutTache.EN_ERREUR)

    tache.statut = StatutTache.EN_ERREUR
    tache.message_alerte = donnees.message_erreur

    for etape in sorted(tache.etapes, key=lambda e: e.ordre):
        if donnees.code_etape and etape.code_etape == donnees.code_etape:
            if etape.statut != StatutEtapeTache.TERMINEE:
                etape.statut = StatutEtapeTache.EN_ERREUR
                etape.message_erreur = donnees.message_erreur
            break
        if not donnees.code_etape and etape.statut == StatutEtapeTache.EN_COURS:
            etape.statut = StatutEtapeTache.EN_ERREUR
            etape.message_erreur = donnees.message_erreur
            break

    _liberer_verrou_dossier(db, tache_id=tache.id)

    audit.journaliser(
        db,
        "tache.erreur",
        ResultatAudit.ECHEC,
        acteur_id=acteur_id,
        ressource_type="tache",
        ressource_id=tache.id,
        details={
            "code_etape": donnees.code_etape,
            "agent_local_id": str(agent_local_id) if agent_local_id else None,
        },
    )
    db.commit()
    return _serialiser_tache(db, tache, cle_maitresse)


def reprendre_tache(
    db: Session,
    *,
    tache_id: uuid.UUID,
    acteur_id: uuid.UUID,
    parametres: Parametres,
    cle_maitresse: bytes,
) -> TacheSortie:
    """Reprend une tâche `suspendue` ou `en_erreur` sans rejouer les étapes déjà `terminee` :
    - Vérifie d'abord que toutes les données et pièces obligatoires sont désormais présentes (Règle 4).
    - Remet la tâche à `en_attente` et conserve toutes les étapes déjà `terminee`."""
    _exiger_tenant(db)
    tache = _obtenir_tache_orm(db, tache_id)
    if tache.action in ACTIONS_OUVERTURE_PC:
        # Action « Ouvrir sur mon PC » : pas d'étapes YAML ni de prérequis de démarche.
        from app.services.taches_ouverture_pc import reprendre_tache_ouverture_pc

        return reprendre_tache_ouverture_pc(
            db, tache=tache, acteur_id=acteur_id, cle_maitresse=cle_maitresse
        )
    _verifier_transition(tache.statut, StatutTache.EN_ATTENTE)

    candidat = obtenir_candidat(
        db, candidat_id=tache.candidat_id, cle_maitresse=cle_maitresse
    )
    docs_orm = lister_documents_orm(db, candidat_id=tache.candidat_id)
    demarche = obtenir_demarche(
        parametres.dossier_demarches, tache.code_demarche, db
    )
    completude = verifier_completude_dossier(
        candidat=candidat, documents=docs_orm, demarche=demarche
    )

    if not completude.pret_pour_prerequis:
        tache.champs_manquants_json = json.dumps(completude.champs_candidat_manquants)
        tache.pieces_manquantes_json = json.dumps(
            completude.pieces_manquantes_ou_invalides
        )
        db.commit()
        raise Conflit(
            "Impossible de reprendre la tâche : des données ou pièces obligatoires sont toujours manquantes (règle 4)."
        )

    maintenant = maintenant_utc()
    for etape in sorted(tache.etapes, key=lambda e: e.ordre):
        if (
            etape.ordre == 1
            and etape.code_etape == "verification_prerequis_dossier"
            and etape.statut != StatutEtapeTache.TERMINEE
        ):
            etape.statut = StatutEtapeTache.TERMINEE
            etape.cle_idempotence = "prerequis-repris-ok"
            etape.commencee_le = etape.commencee_le or maintenant
            etape.terminee_le = maintenant
            etape.message_erreur = None
        elif etape.statut in {StatutEtapeTache.SUSPENDUE, StatutEtapeTache.EN_ERREUR}:
            etape.statut = StatutEtapeTache.A_FAIRE
            etape.message_erreur = None

    tache.statut = StatutTache.EN_ATTENTE
    tache.motif_suspension = None
    tache.message_alerte = None
    tache.champs_manquants_json = None
    tache.pieces_manquantes_json = None

    audit.journaliser(
        db,
        "tache.reprise",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="tache",
        ressource_id=tache.id,
        details={"prochaine_etape": _prochaine_etape(tache.etapes)},
    )
    db.commit()
    return _serialiser_tache(db, tache, cle_maitresse)


def deposer_capture_controle(
    db: Session,
    *,
    tache_id: uuid.UUID,
    contenu_clair: bytes,
    acteur_id: uuid.UUID | None,
    agent_local_id: uuid.UUID | None,
    parametres: Parametres,
    cle_maitresse: bytes,
) -> TacheSortie:
    """Enregistre de façon chiffrée (AES-256-GCM) la capture d'écran de contrôle
    prise par l'agent local juste avant le bouton d'envoi final."""
    tid = _exiger_tenant(db)
    tache = _obtenir_tache_orm(db, tache_id)
    _exiger_detenteur_agent(tache, agent_local_id)
    if tache.statut not in {StatutTache.EN_COURS, StatutTache.A_VALIDER}:
        raise Conflit(
            "La capture de contrôle ne peut être déposée que sur une tâche en cours ou en attente de validation."
        )

    if not contenu_clair:
        raise DonneesInvalides("Le fichier de capture est vide.")
    if len(contenu_clair) > parametres.taille_max_document_octets:
        raise DonneesInvalides("La capture dépasse la taille maximale autorisée.")

    type_mime = _detecter_type_mime_par_signature(contenu_clair)
    chemin_relatif = f"{tid}/captures/{tache.id}.bin"
    chemin_disque: Path = _resoudre_chemin_stockage(
        parametres.dossier_stockage, chemin_relatif
    )

    octets_chiffres = chiffrer_octets(
        cle_maitresse,
        tenant_id=tid,
        candidat_id=tache.candidat_id,
        document_id=tache.id,
        contenu_clair=contenu_clair,
    )
    chemin_disque.parent.mkdir(parents=True, exist_ok=True)
    chemin_disque.write_bytes(octets_chiffres)

    tache.chemin_capture_controle_relatif = chemin_relatif
    tache.type_mime_capture_controle = type_mime

    audit.journaliser(
        db,
        "tache.depot_capture_controle",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="tache",
        ressource_id=tache.id,
        details={
            "taille_octets": len(contenu_clair),
            "type_mime": type_mime,
            "agent_local_id": str(agent_local_id) if agent_local_id else None,
        },
    )
    db.commit()
    return _serialiser_tache(db, tache, cle_maitresse)


def lire_capture_controle(
    db: Session,
    *,
    tache_id: uuid.UUID,
    parametres: Parametres,
    cle_maitresse: bytes,
) -> tuple[str, bytes]:
    tache = _obtenir_tache_orm(db, tache_id)
    if not tache.chemin_capture_controle_relatif:
        raise NonTrouve("Aucune capture de contrôle n'est associée à cette tâche.")

    chemin_disque = _resoudre_chemin_stockage(
        parametres.dossier_stockage, tache.chemin_capture_controle_relatif
    )
    if not chemin_disque.exists():
        raise NonTrouve("Fichier de capture introuvable sur le stockage.")

    clair = dechiffrer_octets(
        cle_maitresse,
        tenant_id=tache.tenant_id,
        candidat_id=tache.candidat_id,
        document_id=tache.id,
        contenu_chiffre=chemin_disque.read_bytes(),
    )
    return tache.type_mime_capture_controle or "image/png", clair


def soumettre_pour_validation_humaine(
    db: Session,
    *,
    tache_id: uuid.UUID,
    donnees: SoumissionValidationEntree,
    acteur_id: uuid.UUID | None,
    agent_local_id: uuid.UUID | None,
    cle_maitresse: bytes,
) -> TacheSortie:
    """Passe la tâche de `en_cours` à `a_valider` après l'arrêt de sécurité avant envoi final.
    Exige que toutes les étapes de la tâche soient `terminee`."""
    tid = _exiger_tenant(db)
    tache = _obtenir_tache_orm(db, tache_id)
    _exiger_detenteur_agent(tache, agent_local_id)
    _verifier_transition(tache.statut, StatutTache.A_VALIDER)

    etapes_non_terminees = [
        e.code_etape
        for e in sorted(tache.etapes, key=lambda x: x.ordre)
        if e.statut != StatutEtapeTache.TERMINEE
    ]
    if etapes_non_terminees:
        raise Conflit(
            f"Toutes les étapes doivent être terminées avant de demander la validation humaine "
            f"(étapes restantes : {', '.join(etapes_non_terminees)})."
        )

    maintenant = maintenant_utc()
    tache.statut = StatutTache.A_VALIDER
    tache.soumise_validation_le = maintenant
    tache.message_alerte = donnees.message_alerte
    tache.recapitulatif_remplissage_chiffre = chiffrer_champ(
        cle_maitresse,
        tid,
        "recapitulatif_remplissage",
        json.dumps(donnees.recapitulatif_remplissage, ensure_ascii=False),
    )

    _liberer_verrou_dossier(db, tache_id=tache.id)

    audit.journaliser(
        db,
        "tache.soumission_validation_humaine",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="tache",
        ressource_id=tache.id,
        details={
            "agent_local_id": str(agent_local_id) if agent_local_id else None,
            "capture_presente": bool(tache.chemin_capture_controle_relatif),
        },
    )
    db.commit()
    return _serialiser_tache(db, tache, cle_maitresse)


def valider_par_humain(
    db: Session,
    *,
    tache_id: uuid.UUID,
    donnees: ValidationHumaineEntree,
    decideur_id: uuid.UUID,
    cle_maitresse: bytes,
) -> TacheSortie:
    """Valide humainement une tâche à l'état `a_valider` (Règle 1).
    Exige `confirmation_humaine_explicite=True` et un utilisateur humain authentifié."""
    tid = _exiger_tenant(db)
    if not donnees.confirmation_humaine_explicite:
        audit.journaliser(
            db,
            "tache.validation_humaine_refusee_sans_confirmation",
            ResultatAudit.REFUS,
            acteur_id=decideur_id,
            ressource_type="tache",
            ressource_id=tache_id,
        )
        db.commit()
        raise DonneesInvalides(
            "La confirmation humaine explicite (confirmation_humaine_explicite=true) est obligatoire (règle 1)."
        )

    tache = _obtenir_tache_orm(db, tache_id)
    _verifier_transition(tache.statut, StatutTache.TERMINEE)

    maintenant = maintenant_utc()
    decision = DecisionValidationHumaine(
        id=uuid.uuid4(),
        tenant_id=tid,
        tache_id=tache.id,
        candidat_id=tache.candidat_id,
        decideur_id=decideur_id,
        decision=TypeDecisionValidation.APPROUVEE,
        confirmation_explicite=True,
        commentaire_chiffre=chiffrer_champ(
            cle_maitresse, tid, "commentaire_validation", donnees.commentaire
        ),
    )
    db.add(decision)

    tache.statut = StatutTache.TERMINEE
    tache.terminee_le = maintenant
    tache.message_alerte = None
    _liberer_verrou_dossier(db, tache_id=tache.id)

    audit.journaliser(
        db,
        "tache.validation_humaine_approuvee",
        ResultatAudit.SUCCES,
        acteur_id=decideur_id,
        ressource_type="tache",
        ressource_id=tache.id,
        details={"decision_id": str(decision.id)},
    )
    db.commit()
    db.refresh(tache)
    return _serialiser_tache(db, tache, cle_maitresse)


def rejeter_validation_humaine(
    db: Session,
    *,
    tache_id: uuid.UUID,
    donnees: RejetValidationEntree,
    decideur_id: uuid.UUID,
    cle_maitresse: bytes,
) -> TacheSortie:
    """Rejette le pré-remplissage dans le Centre de validation humaine :
    - Passe la tâche à `suspendue` (`motif = rejet_validation_humaine`).
    - Réinitialise uniquement l'étape demandée (et les suivantes) à `a_faire`, en conservant
      les étapes précédentes déjà validées (reprise idempotente)."""
    tid = _exiger_tenant(db)
    tache = _obtenir_tache_orm(db, tache_id)
    _verifier_transition(tache.statut, StatutTache.SUSPENDUE)

    etapes_triees = sorted(tache.etapes, key=lambda e: e.ordre)
    code_cible = donnees.reinitialiser_depuis_etape or etapes_triees[-1].code_etape
    ordre_cible: int | None = None
    for e in etapes_triees:
        if e.code_etape == code_cible:
            ordre_cible = e.ordre
            break
    if ordre_cible is None:
        raise DonneesInvalides(
            f"Étape '{code_cible}' inconnue pour réinitialiser la tâche."
        )

    for e in etapes_triees:
        if e.ordre >= ordre_cible:
            e.statut = StatutEtapeTache.A_FAIRE
            e.cle_idempotence = None
            e.terminee_le = None

    maintenant = maintenant_utc()
    decision = DecisionValidationHumaine(
        id=uuid.uuid4(),
        tenant_id=tid,
        tache_id=tache.id,
        candidat_id=tache.candidat_id,
        decideur_id=decideur_id,
        decision=TypeDecisionValidation.REJETEE,
        confirmation_explicite=True,
        commentaire_chiffre=chiffrer_champ(
            cle_maitresse, tid, "commentaire_validation", donnees.commentaire
        ),
        reinitialiser_depuis_etape=code_cible,
    )
    db.add(decision)

    tache.statut = StatutTache.SUSPENDUE
    tache.motif_suspension = MotifSuspensionTache.REJET_VALIDATION_HUMAINE
    tache.suspendue_le = maintenant
    tache.message_alerte = (
        f"Validation humaine rejetée : reprise requise à partir de l'étape '{code_cible}'."
    )
    _liberer_verrou_dossier(db, tache_id=tache.id)

    audit.journaliser(
        db,
        "tache.validation_humaine_rejetee",
        ResultatAudit.SUCCES,
        acteur_id=decideur_id,
        ressource_type="tache",
        ressource_id=tache.id,
        details={
            "decision_id": str(decision.id),
            "reinitialiser_depuis_etape": code_cible,
        },
    )
    db.commit()
    db.refresh(tache)
    return _serialiser_tache(db, tache, cle_maitresse)


def annuler_tache(
    db: Session,
    *,
    tache_id: uuid.UUID,
    acteur_id: uuid.UUID,
    cle_maitresse: bytes,
) -> TacheSortie:
    _exiger_tenant(db)
    tache = _obtenir_tache_orm(db, tache_id)
    _verifier_transition(tache.statut, StatutTache.ANNULEE)

    tache.statut = StatutTache.ANNULEE
    _liberer_verrou_dossier(db, tache_id=tache.id)

    audit.journaliser(
        db,
        "tache.annulation",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="tache",
        ressource_id=tache.id,
    )
    db.commit()
    return _serialiser_tache(db, tache, cle_maitresse)


def obtenir_synthese_centre_validation(
    db: Session, *, cle_maitresse: bytes
) -> SyntheseCentreValidationSortie:
    """Retourne les tâches du bureau qui requièrent une décision ou une action humaine :
    - `taches_a_valider` : pré-remplissage terminé, arrêtées avant le bouton d'envoi final (Règle 1)
    - `taches_suspendues` : en pause pour donnée manquante (Règle 4), CAPTCHA/2FA (Règle 2) ou session portail (Règle 3)."""
    _exiger_tenant(db)
    a_valider_orm = db.scalars(
        select(TacheDossier)
        .where(TacheDossier.statut == StatutTache.A_VALIDER)
        .order_by(TacheDossier.soumise_validation_le.asc(), TacheDossier.cree_le.asc())
    ).all()
    suspendues_orm = db.scalars(
        select(TacheDossier)
        .where(TacheDossier.statut == StatutTache.SUSPENDUE)
        .order_by(TacheDossier.suspendue_le.desc(), TacheDossier.cree_le.desc())
    ).all()

    a_valider = [_serialiser_tache(db, t, cle_maitresse) for t in a_valider_orm]
    suspendues = [_serialiser_tache(db, t, cle_maitresse) for t in suspendues_orm]
    return SyntheseCentreValidationSortie(
        taches_a_valider=a_valider,
        taches_suspendues=suspendues,
        total_a_valider=len(a_valider),
        total_suspendues=len(suspendues),
    )


def _exiger_action_avec_pieces(tache: TacheDossier) -> None:
    """Minimisation des données : une action « Ouvrir sur mon PC » (ajout de vœux) n'a besoin ni de la fiche
    complète ni des pièces du candidat ; ni l'agent ni personne ne les reçoit par ces routes."""
    if tache.action in ACTIONS_OUVERTURE_PC:
        raise AccesRefuse("Cette action n'a pas besoin du dossier ni des pièces du candidat : accès refusé.")


def obtenir_contexte_dossier_execution(
    db: Session,
    *,
    tache_id: uuid.UUID,
    agent_local_id: uuid.UUID | None,
    cle_maitresse: bytes,
) -> ContexteDossierExecutionSortie:
    """Retourne les données déchiffrées du candidat et la liste de ses documents
    uniquement si la tâche est actuellement `en_cours` et si l'action en a besoin."""
    _exiger_tenant(db)
    tache = _obtenir_tache_orm(db, tache_id)
    _exiger_detenteur_agent(tache, agent_local_id)
    _exiger_action_avec_pieces(tache)
    if tache.statut != StatutTache.EN_COURS:
        raise Conflit(
            "Le contexte d'exécution du dossier n'est accessible que pour une tâche à l'état 'en_cours'."
        )
    candidat = obtenir_candidat(
        db, candidat_id=tache.candidat_id, cle_maitresse=cle_maitresse
    )
    documents = lister_documents_candidat(
        db, candidat_id=tache.candidat_id, cle_maitresse=cle_maitresse
    )
    return ContexteDossierExecutionSortie(
        tache=_serialiser_tache(db, tache, cle_maitresse),
        candidat=candidat,
        documents=documents,
    )


def lire_document_pour_tache_en_cours(
    db: Session,
    *,
    tache_id: uuid.UUID,
    document_id: uuid.UUID,
    agent_local_id: uuid.UUID | None,
    parametres: Parametres,
    cle_maitresse: bytes,
) -> tuple[str, str, bytes]:
    """Permet à l'Agent Local exécutant une tâche `en_cours` de récupérer le binaire déchiffré
    d'une pièce justificative du candidat afin de la téléverser sur le portail."""
    _exiger_tenant(db)
    tache = _obtenir_tache_orm(db, tache_id)
    _exiger_detenteur_agent(tache, agent_local_id)
    _exiger_action_avec_pieces(tache)
    if tache.statut != StatutTache.EN_COURS:
        raise Conflit(
            "Le téléchargement d'une pièce par l'agent n'est autorisé que pour une tâche à l'état 'en_cours'."
        )
    meta, octets = lire_document_dechiffre(
        db,
        candidat_id=tache.candidat_id,
        document_id=document_id,
        parametres=parametres,
        cle_maitresse=cle_maitresse,
    )
    return meta.type_mime, meta.nom_fichier_origine, octets
