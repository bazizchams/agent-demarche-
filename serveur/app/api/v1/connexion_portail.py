"""Routes de connexion aux portails et de creation de compte par l'agent local (Regle 3).

Aucune route ne renvoie un identifiant au navigateur de l'humain. Seule `remise` renvoie les identifiants, a l'agent
detenteur de la tache (jeton X-Agent-Token), une fois, dans les 60 s qui suivent le consentement.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from pydantic import ConfigDict, BaseModel, Field, SecretStr

from app.api.dependances import (
    ContexteAgentLocal,
    ContexteAuth,
    exiger_roles,
    obtenir_agent_local_requis,
    obtenir_cle_maitresse,
    obtenir_contexte_auth,
)
from app.modeles.utilisateur import Role
from app.services import echanges_coffre as service

routeur = APIRouter(prefix="/taches", tags=["connexion portail et creation de compte"])

ExigerEcritureHumaine = Depends(exiger_roles(Role.ADMINISTRATEUR, Role.EMPLOYE))


class SecretsEntree(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identifiant: SecretStr = Field(min_length=1, max_length=service.LONGUEUR_MAX_SECRET)
    mot_de_passe: SecretStr = Field(min_length=1, max_length=service.LONGUEUR_MAX_SECRET)


class ConsentementEntree(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consentement: bool


class AutorisationSortie(BaseModel):
    expire_le: datetime
    duree_secondes: int


class DepotEtatSortie(BaseModel):
    present: bool
    portail: str | None
    expire_le: datetime | None


@routeur.post("/{tache_id}/autoriser-connexion", response_model=AutorisationSortie)
def autoriser_connexion(tache_id: uuid.UUID, ctx: ContexteAuth = ExigerEcritureHumaine) -> dict:
    return service.autoriser_connexion(ctx.db, tache_id=tache_id, acteur_id=ctx.utilisateur.id)


@routeur.get("/{tache_id}/coffre-etat")
def coffre_etat(tache_id: uuid.UUID, ctx: ContexteAgentLocal = Depends(obtenir_agent_local_requis)) -> dict:
    return service.etat_coffre_pour_agent(ctx.db, tache_id=tache_id, agent=ctx.agent_local)


@routeur.post("/{tache_id}/identifiants-portail/remise")
def remise(
    tache_id: uuid.UUID,
    ctx: ContexteAgentLocal = Depends(obtenir_agent_local_requis),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> JSONResponse:
    clairs = service.remettre_identifiants(
        ctx.db, tache_id=tache_id, agent=ctx.agent_local, cle_maitresse=cle_maitresse
    )
    return JSONResponse(
        {"identifiant": clairs.identifiant, "mot_de_passe": clairs.mot_de_passe},
        headers={"Cache-Control": "no-store"},
    )


@routeur.post("/{tache_id}/depot-identifiants", status_code=status.HTTP_204_NO_CONTENT)
def deposer(
    tache_id: uuid.UUID,
    donnees: SecretsEntree,
    ctx: ContexteAgentLocal = Depends(obtenir_agent_local_requis),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> Response:
    service.deposer_identifiants_captes(
        ctx.db,
        tache_id=tache_id,
        agent=ctx.agent_local,
        identifiant=donnees.identifiant.get_secret_value(),
        mot_de_passe=donnees.mot_de_passe.get_secret_value(),
        cle_maitresse=cle_maitresse,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@routeur.get("/{tache_id}/depot-identifiants", response_model=DepotEtatSortie)
def etat_depot(tache_id: uuid.UUID, ctx: ContexteAuth = Depends(obtenir_contexte_auth)) -> dict:
    return service.etat_depot(ctx.db, tache_id=tache_id)


@routeur.post("/{tache_id}/depot-identifiants/enregistrer")
def enregistrer_depot(
    tache_id: uuid.UUID,
    donnees: ConsentementEntree,
    ctx: ContexteAuth = ExigerEcritureHumaine,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> dict:
    statut = service.enregistrer_depot(
        ctx.db,
        tache_id=tache_id,
        acteur_id=ctx.utilisateur.id,
        consentement=donnees.consentement,
        cle_maitresse=cle_maitresse,
    )
    return {"portail": statut["portail"], "existe": statut["existe"]}


@routeur.delete("/{tache_id}/depot-identifiants", status_code=status.HTTP_204_NO_CONTENT)
def refuser_depot(tache_id: uuid.UUID, ctx: ContexteAuth = ExigerEcritureHumaine) -> Response:
    service.refuser_depot(ctx.db, tache_id=tache_id, acteur_id=ctx.utilisateur.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@routeur.get("/{tache_id}/champs-compte-eef")
def champs_compte(
    tache_id: uuid.UUID,
    ctx: ContexteAgentLocal = Depends(obtenir_agent_local_requis),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> dict:
    return service.champs_compte_pour_agent(
        ctx.db, tache_id=tache_id, agent=ctx.agent_local, cle_maitresse=cle_maitresse
    )


@routeur.post("/{tache_id}/compte-eef/enregistrer-identifiants")
def enregistrer_compte(
    tache_id: uuid.UUID,
    donnees: SecretsEntree,
    ctx: ContexteAgentLocal = Depends(obtenir_agent_local_requis),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> dict:
    statut = service.enregistrer_compte_cree(
        ctx.db,
        tache_id=tache_id,
        agent=ctx.agent_local,
        identifiant=donnees.identifiant.get_secret_value(),
        mot_de_passe=donnees.mot_de_passe.get_secret_value(),
        cle_maitresse=cle_maitresse,
    )
    return {"portail": statut["portail"], "existe": statut["existe"]}
