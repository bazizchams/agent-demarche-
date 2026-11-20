"""Validation humaine (Règle 1) : soumission, approbation, rejet et synthèse du Centre de validation."""

from __future__ import annotations

import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.chiffrement import chiffrer_champ
from app.core.erreurs import Conflit, DonneesInvalides
from app.db.base import maintenant_utc
from app.modeles.journal_audit import ResultatAudit
from app.modeles.tache import (
    DecisionValidationHumaine,
    EtapeTache,
    MotifSuspensionTache,
    StatutEtapeTache,
    StatutTache,
    TacheDossier,
    TypeDecisionValidation,
)
from app.schemas.tache import (
    RejetValidationEntree,
    SoumissionValidationEntree,
    SyntheseCentreValidationSortie,
    TacheSortie,
    ValidationHumaineEntree,
)
from app.services import audit
from app.services.taches.etat import (
    _exiger_detenteur_agent,
    _exiger_tenant,
    _obtenir_tache_orm,
    _texte_agent,
    _verifier_transition,
)
from app.services.taches.serialisation import _serialiser_tache
from app.services.taches.verrous import _liberer_verrou_dossier


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

    tache.statut = StatutTache.A_VALIDER
    tache.soumise_validation_le = maintenant_utc()
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
            "agent_local_id": _texte_agent(agent_local_id),
            "capture_presente": bool(tache.chemin_capture_controle_relatif),
        },
    )
    db.commit()
    return _serialiser_tache(db, tache, cle_maitresse)


def _refuser_sans_confirmation(
    db: Session, tache_id: uuid.UUID, decideur_id: uuid.UUID
) -> None:
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
        _refuser_sans_confirmation(db, tache_id, decideur_id)

    tache = _obtenir_tache_orm(db, tache_id)
    _verifier_transition(tache.statut, StatutTache.TERMINEE)

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
    tache.terminee_le = maintenant_utc()
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


def _reinitialiser_etapes_depuis(
    etapes_triees: list[EtapeTache], code_cible: str
) -> None:
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
    _reinitialiser_etapes_depuis(etapes_triees, code_cible)

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
    tache.suspendue_le = maintenant_utc()
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
