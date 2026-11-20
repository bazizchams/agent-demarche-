"""Interruptions d'une tâche (suspension, erreur) et reprise sans rejouer les étapes terminées."""

from __future__ import annotations

import json
import uuid

from sqlalchemy.orm import Session

from app.core.config import Parametres
from app.core.erreurs import Conflit
from app.db.base import maintenant_utc
from app.modeles.journal_audit import ResultatAudit
from app.modeles.tache import (
    ACTIONS_OUVERTURE_PC,
    StatutEtapeTache,
    StatutTache,
    TacheDossier,
)
from app.schemas.tache import (
    SignalerErreurTacheEntree,
    SuspendreTacheEntree,
    TacheSortie,
)
from app.services import audit
from app.services.taches.etat import (
    _exiger_detenteur_agent,
    _exiger_tenant,
    _obtenir_tache_orm,
    _prochaine_etape,
    _texte_agent,
    _verifier_transition,
)
from app.services.taches.prerequis import _evaluer_completude_tache
from app.services.taches.serialisation import _serialiser_tache
from app.services.taches.verrous import _liberer_verrou_dossier


def _marquer_etape_interrompue(
    tache: TacheDossier,
    code_etape: str | None,
    statut: StatutEtapeTache,
    message: str,
) -> None:
    """Marque l'étape ciblée (ou, à défaut, l'étape en cours) sans toucher aux étapes terminées."""
    for etape in sorted(tache.etapes, key=lambda e: e.ordre):
        if code_etape and etape.code_etape == code_etape:
            if etape.statut != StatutEtapeTache.TERMINEE:
                etape.statut = statut
                etape.message_erreur = message
            break
        if not code_etape and etape.statut == StatutEtapeTache.EN_COURS:
            etape.statut = statut
            etape.message_erreur = message
            break


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

    tache.statut = StatutTache.SUSPENDUE
    tache.motif_suspension = donnees.motif
    tache.message_alerte = donnees.message_alerte
    tache.suspendue_le = maintenant_utc()
    tache.champs_manquants_json = (
        json.dumps(donnees.champs_manquants) if donnees.champs_manquants else None
    )
    tache.pieces_manquantes_json = (
        json.dumps(donnees.pieces_manquantes) if donnees.pieces_manquantes else None
    )
    _marquer_etape_interrompue(
        tache, donnees.code_etape, StatutEtapeTache.SUSPENDUE, donnees.message_alerte
    )
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
            "agent_local_id": _texte_agent(agent_local_id),
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
    _marquer_etape_interrompue(
        tache, donnees.code_etape, StatutEtapeTache.EN_ERREUR, donnees.message_erreur
    )
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
            "agent_local_id": _texte_agent(agent_local_id),
        },
    )
    db.commit()
    return _serialiser_tache(db, tache, cle_maitresse)


def _rouvrir_etapes_pour_reprise(tache: TacheDossier) -> None:
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

    completude = _evaluer_completude_tache(db, tache, parametres, cle_maitresse)
    if not completude.pret_pour_prerequis:
        tache.champs_manquants_json = json.dumps(completude.champs_candidat_manquants)
        tache.pieces_manquantes_json = json.dumps(
            completude.pieces_manquantes_ou_invalides
        )
        db.commit()
        raise Conflit(
            "Impossible de reprendre la tâche : des données ou pièces obligatoires sont toujours manquantes (règle 4)."
        )

    _rouvrir_etapes_pour_reprise(tache)
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
