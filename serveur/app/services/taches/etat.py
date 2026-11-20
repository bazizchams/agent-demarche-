"""État partagé des tâches : machine à états stricte et gardes communes."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.erreurs import AccesRefuse, Conflit, NonTrouve
from app.db.tenant import tenant_courant
from app.modeles.tache import (
    ACTIONS_OUVERTURE_PC,
    EtapeTache,
    StatutEtapeTache,
    StatutTache,
    TacheDossier,
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


def _exiger_action_avec_pieces(tache: TacheDossier) -> None:
    """Minimisation des données : une action « Ouvrir sur mon PC » (ajout de vœux) n'a besoin ni de la fiche
    complète ni des pièces du candidat ; ni l'agent ni personne ne les reçoit par ces routes."""
    if tache.action in ACTIONS_OUVERTURE_PC:
        raise AccesRefuse("Cette action n'a pas besoin du dossier ni des pièces du candidat : accès refusé.")


def _prochaine_etape(etapes: list[EtapeTache]) -> str | None:
    for etape in sorted(etapes, key=lambda e: e.ordre):
        if etape.statut != StatutEtapeTache.TERMINEE:
            return etape.code_etape
    return None


def _detenteur_verrou(
    agent_local_id: uuid.UUID | None, acteur_id: uuid.UUID | None
) -> str:
    return f"agent:{agent_local_id}" if agent_local_id else f"utilisateur:{acteur_id}"


def _texte_agent(agent_local_id: uuid.UUID | None) -> str | None:
    return str(agent_local_id) if agent_local_id else None
