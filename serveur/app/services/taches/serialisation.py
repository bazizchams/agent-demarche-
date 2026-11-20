"""Sérialisation d'une tâche vers son schéma de sortie (déchiffrement des champs sensibles)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.chiffrement import dechiffrer_champ
from app.modeles.tache import DecisionValidationHumaine, EtapeTache, TacheDossier
from app.schemas.tache import (
    DecisionValidationSortie,
    EtapeTacheSortie,
    TacheSortie,
    VerrouDossierSortie,
)
from app.services.taches.etat import _prochaine_etape
from app.services.taches.verrous import _obtenir_verrou_actif


def _liste_json(valeur: str | None) -> list[str]:
    return json.loads(valeur) if valeur else []


def _recapitulatif(tache: TacheDossier, cle_maitresse: bytes) -> dict[str, Any] | None:
    if not tache.recapitulatif_remplissage_chiffre:
        return None
    recap_str = dechiffrer_champ(
        cle_maitresse,
        tache.tenant_id,
        "recapitulatif_remplissage",
        tache.recapitulatif_remplissage_chiffre,
    )
    return json.loads(recap_str) if recap_str else None


def _etape_sortie(
    e: EtapeTache, tid: uuid.UUID, cle_maitresse: bytes
) -> EtapeTacheSortie:
    return EtapeTacheSortie(
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


def _decision_sortie(
    d: DecisionValidationHumaine, tid: uuid.UUID, cle_maitresse: bytes
) -> DecisionValidationSortie:
    return DecisionValidationSortie(
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


def _verrou_sortie(db: Session, tache: TacheDossier) -> VerrouDossierSortie | None:
    verrou_actif = _obtenir_verrou_actif(db, tache.candidat_id)
    if verrou_actif is not None and verrou_actif.tache_id == tache.id:
        return VerrouDossierSortie.model_validate(verrou_actif)
    return None


def _serialiser_tache(
    db: Session, tache: TacheDossier, cle_maitresse: bytes
) -> TacheSortie:
    tid = tache.tenant_id
    champs_manquants = _liste_json(tache.champs_manquants_json)
    pieces_manquantes = _liste_json(tache.pieces_manquantes_json)
    recap = _recapitulatif(tache, cle_maitresse)

    etapes_sortie = [
        _etape_sortie(e, tid, cle_maitresse)
        for e in sorted(tache.etapes, key=lambda x: x.ordre)
    ]
    decisions_sortie = [
        _decision_sortie(d, tid, cle_maitresse)
        for d in sorted(tache.decisions_validation, key=lambda x: x.cree_le)
    ]
    verrou_sortie = _verrou_sortie(db, tache)

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
