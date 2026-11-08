"""Routes d'enrôlement et de gestion des Agents Locaux du bureau."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.api.dependances import ContexteAuth, exiger_roles, obtenir_contexte_auth
from app.modeles.utilisateur import Role
from app.schemas.tache import (
    AgentLocalCreation,
    AgentLocalEnroleSortie,
    AgentLocalSortie,
)
from app.services import agents_locaux as service_agents

routeur = APIRouter(prefix="/agents-locaux", tags=["agents locaux"])

ExigerAdmin = Depends(exiger_roles(Role.ADMINISTRATEUR))


@routeur.get("", response_model=list[AgentLocalSortie])
def lister(
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
) -> list[AgentLocalSortie]:
    return service_agents.lister_agents_locaux(ctx.db)


@routeur.post(
    "",
    response_model=AgentLocalEnroleSortie,
    status_code=status.HTTP_201_CREATED,
)
def enroler(
    donnees: AgentLocalCreation,
    ctx: ContexteAuth = ExigerAdmin,
) -> AgentLocalEnroleSortie:
    return service_agents.enroler_agent_local(
        ctx.db,
        donnees=donnees,
        acteur_id=ctx.utilisateur.id,
    )


@routeur.post("/{agent_id}/revoquer", response_model=AgentLocalSortie)
def revoquer(
    agent_id: uuid.UUID,
    ctx: ContexteAuth = ExigerAdmin,
) -> AgentLocalSortie:
    return service_agents.changer_statut_agent_local(
        ctx.db,
        agent_id=agent_id,
        actif=False,
        acteur_id=ctx.utilisateur.id,
    )


@routeur.post("/{agent_id}/activer", response_model=AgentLocalSortie)
def activer(
    agent_id: uuid.UUID,
    ctx: ContexteAuth = ExigerAdmin,
) -> AgentLocalSortie:
    return service_agents.changer_statut_agent_local(
        ctx.db,
        agent_id=agent_id,
        actif=True,
        acteur_id=ctx.utilisateur.id,
    )
