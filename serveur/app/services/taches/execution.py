"""Exécution d'une tâche par l'agent : démarrage, battement de cœur, étapes, annulation."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.chiffrement import chiffrer_champ
from app.core.config import Parametres
from app.core.erreurs import Conflit, NonTrouve
from app.db.base import maintenant_utc
from app.modeles.journal_audit import ResultatAudit
from app.modeles.tache import (
    ACTIONS_OUVERTURE_PC,
    EtapeTache,
    MotifSuspensionTache,
    StatutEtapeTache,
    StatutTache,
    TacheDossier,
)
from app.schemas.tache import DemarrerTacheEntree, TacheSortie, TerminerEtapeEntree
from app.services import audit
from app.services.taches.etat import (
    _detenteur_verrou,
    _exiger_detenteur_agent,
    _exiger_tenant,
    _obtenir_tache_orm,
    _prochaine_etape,
    _texte_agent,
    _verifier_transition,
)
from app.services.taches.prerequis import _evaluer_completude_tache
from app.services.taches.serialisation import _serialiser_tache
from app.services.taches.verrous import (
    _acquerir_ou_rafraichir_verrou,
    _liberer_verrou_dossier,
)


def _suspendre_pour_prerequis(
    db: Session,
    tache: TacheDossier,
    completude: Any,
    acteur_id: uuid.UUID | None,
    maintenant: datetime,
) -> None:
    """Suspension automatique (Règle 4) au démarrage : persiste puis lève un conflit."""
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


def _activer_etape_courante(tache: TacheDossier, maintenant: datetime) -> None:
    for etape in sorted(tache.etapes, key=lambda e: e.ordre):
        if etape.statut != StatutEtapeTache.TERMINEE:
            etape.statut = StatutEtapeTache.EN_COURS
            etape.commencee_le = etape.commencee_le or maintenant
            etape.nb_tentatives += 1
            break


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
    completude = _evaluer_completude_tache(db, tache, parametres, cle_maitresse)
    maintenant = maintenant_utc()
    if not completude.pret_pour_prerequis:
        _suspendre_pour_prerequis(db, tache, completude, acteur_id, maintenant)

    detenteur = donnees.detenteur or _detenteur_verrou(agent_local_id, acteur_id)
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
    _activer_etape_courante(tache, maintenant)

    audit.journaliser(
        db,
        "tache.demarrage",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="tache",
        ressource_id=tache.id,
        details={
            "agent_local_id": _texte_agent(agent_local_id),
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

    _acquerir_ou_rafraichir_verrou(
        db,
        tid=tid,
        candidat_id=tache.candidat_id,
        tache_id=tache.id,
        detenteur=_detenteur_verrou(agent_local_id, acteur_id),
        duree_secondes=parametres.duree_verrou_dossier_secondes,
    )
    db.commit()
    return _serialiser_tache(db, tache, cle_maitresse)


def _trouver_etape(etapes_triees: list[EtapeTache], code_etape: str) -> EtapeTache:
    for e in etapes_triees:
        if e.code_etape == code_etape:
            return e
    raise NonTrouve("Étape inconnue pour cette démarche.")


def _exiger_etapes_precedentes_terminees(
    etapes_triees: list[EtapeTache], cible: EtapeTache
) -> None:
    for precedente in etapes_triees:
        if precedente.ordre < cible.ordre and precedente.statut != StatutEtapeTache.TERMINEE:
            raise Conflit(
                f"Ordre des étapes non respecté : l'étape précédente '{precedente.code_etape}' n'est pas terminée."
            )


def _marquer_etape_terminee(
    cible: EtapeTache,
    donnees: TerminerEtapeEntree,
    *,
    tid: uuid.UUID,
    cle_maitresse: bytes,
    maintenant: datetime,
) -> None:
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


def _activer_etape_suivante(
    etapes_triees: list[EtapeTache], cible: EtapeTache, maintenant: datetime
) -> None:
    for suivante in etapes_triees:
        if suivante.ordre > cible.ordre and suivante.statut != StatutEtapeTache.TERMINEE:
            suivante.statut = StatutEtapeTache.EN_COURS
            suivante.commencee_le = suivante.commencee_le or maintenant
            suivante.nb_tentatives += 1
            break


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
    cible = _trouver_etape(etapes_triees, code_etape)

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
    _exiger_etapes_precedentes_terminees(etapes_triees, cible)

    maintenant = maintenant_utc()
    _marquer_etape_terminee(
        cible, donnees, tid=tid, cle_maitresse=cle_maitresse, maintenant=maintenant
    )
    _activer_etape_suivante(etapes_triees, cible, maintenant)

    # Prolonge le verrou du dossier
    _acquerir_ou_rafraichir_verrou(
        db,
        tid=tid,
        candidat_id=tache.candidat_id,
        tache_id=tache.id,
        detenteur=_detenteur_verrou(agent_local_id, acteur_id),
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
