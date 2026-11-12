"""Routes du coffre d'identifiants portail (regle 3).

AUCUNE route ne renvoie jamais l'identifiant ni le mot de passe : seul le statut
(existe oui/non + dates) est exposé. Le déchiffrement est réservé à l'agent (service).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.api.dependances import (
    ContexteAuth,
    exiger_roles,
    obtenir_cle_maitresse,
    obtenir_contexte_auth,
)
from app.modeles.utilisateur import Role
from app.services import coffre_identifiants as service

routeur = APIRouter(
    prefix="/candidats/{candidat_id}/coffre/{portail}", tags=["coffre identifiants portail"]
)

ExigerEcriture = Depends(exiger_roles(Role.ADMINISTRATEUR, Role.EMPLOYE))


class IdentifiantsEntree(BaseModel):
    """Saisie unique des identifiants ; SecretStr pour ne jamais apparaître dans un repr."""

    model_config = ConfigDict(extra="forbid")

    identifiant: SecretStr = Field(min_length=1, max_length=service.LONGUEUR_MAX_SECRET)
    mot_de_passe: SecretStr = Field(min_length=1, max_length=service.LONGUEUR_MAX_SECRET)
    consentement: bool = Field(
        description="Le candidat a donné son consentement écrit (obligatoire)."
    )


class StatutCoffreSortie(BaseModel):
    portail: str
    existe: bool
    consentement_recueilli_le: datetime | None
    cree_le: datetime | None
    mis_a_jour_le: datetime | None


@routeur.put("", response_model=StatutCoffreSortie)
def enregistrer(
    candidat_id: uuid.UUID,
    portail: str,
    donnees: IdentifiantsEntree,
    ctx: ContexteAuth = ExigerEcriture,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> dict:
    return service.enregistrer(
        ctx.db,
        candidat_id=candidat_id,
        portail=portail,
        identifiant=donnees.identifiant.get_secret_value(),
        mot_de_passe=donnees.mot_de_passe.get_secret_value(),
        consentement=donnees.consentement,
        acteur_id=ctx.utilisateur.id,
        cle_maitresse=cle_maitresse,
    )


@routeur.get("", response_model=StatutCoffreSortie)
def statut(
    candidat_id: uuid.UUID,
    portail: str,
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
) -> dict:
    return service.statut(ctx.db, candidat_id=candidat_id, portail=portail)


@routeur.delete("", status_code=status.HTTP_204_NO_CONTENT)
def supprimer(
    candidat_id: uuid.UUID,
    portail: str,
    ctx: ContexteAuth = ExigerEcriture,
) -> Response:
    service.supprimer(
        ctx.db, candidat_id=candidat_id, portail=portail, acteur_id=ctx.utilisateur.id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
