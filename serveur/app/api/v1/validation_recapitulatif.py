"""Routes de validation humaine d'un récapitulatif avant soumission officielle (Règle 1).

Aucune route ne permet à l'agent de valider : `valider` et `refuser` exigent une session
humaine (cookie + CSRF) d'un administrateur ou d'un employé ; un jeton agent seul est rejeté.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import Field

from app.api.dependances import (
    ContexteAuth,
    ContexteExecutionTache,
    exiger_roles,
    obtenir_cle_maitresse,
    obtenir_contexte_execution_tache,
)
from app.modeles.utilisateur import Role
from app.modeles.validation_recapitulatif import (
    StatutValidationRecapitulatif,
    ValidationRecapitulatif,
)
from app.schemas.commun import SchemaEntree, SchemaSortie
from app.services import validation_recapitulatif as service

routeur = APIRouter(
    prefix="/validations-recapitulatif", tags=["validation humaine du récapitulatif"]
)

# Lecture et écriture réservées aux humains du bureau (la lecture montre le contenu clair).
HumainValideur = Depends(exiger_roles(Role.ADMINISTRATEUR, Role.EMPLOYE))


class PropositionEntree(SchemaEntree):
    candidat_id: uuid.UUID
    portail: str = Field(min_length=1, max_length=40)
    type_demarche: str = Field(min_length=1, max_length=60)
    contenu: dict[str, Any] = Field(min_length=1)


class ValidationSortie(SchemaSortie):
    id: uuid.UUID
    candidat_id: uuid.UUID
    portail: str
    type_demarche: str
    empreinte: str
    statut: StatutValidationRecapitulatif
    cree_le: datetime
    validee_par: uuid.UUID | None
    validee_le: datetime | None
    envoyee_le: datetime | None
    champs_manquants: list[str] = []
    contenu: dict[str, Any] | None = None


def _sortie(
    ctx_db, v: ValidationRecapitulatif, cle: bytes, *, avec_contenu: bool
) -> ValidationSortie:
    sortie = ValidationSortie.model_validate(v)
    contenu = service.dechiffrer_contenu(ctx_db, v, cle_maitresse=cle)
    sortie.champs_manquants = service.champs_manquants(contenu)
    sortie.contenu = contenu if avec_contenu else None
    return sortie


@routeur.post("", response_model=ValidationSortie, status_code=status.HTTP_201_CREATED)
def proposer(
    corps: PropositionEntree,
    ctx: ContexteExecutionTache = Depends(obtenir_contexte_execution_tache),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> ValidationSortie:
    """Proposition par l'agent local ou par un employé/administrateur (jamais une validation)."""
    v = service.proposer(
        ctx.db, candidat_id=corps.candidat_id, portail=corps.portail,
        type_demarche=corps.type_demarche, contenu=corps.contenu,
        cle_maitresse=cle_maitresse, acteur_id=ctx.acteur_id,
        par_agent=ctx.agent_local is not None,
    )
    # L'agent ne reçoit pas le contenu en retour : il connaît déjà ce qu'il a proposé.
    return _sortie(ctx.db, v, cle_maitresse, avec_contenu=ctx.agent_local is None)


@routeur.get("", response_model=list[ValidationSortie])
def lister(
    candidat_id: uuid.UUID | None = Query(default=None),
    statut: StatutValidationRecapitulatif | None = Query(default=None),
    ctx: ContexteAuth = HumainValideur,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> list[ValidationSortie]:
    return [
        _sortie(ctx.db, v, cle_maitresse, avec_contenu=True)
        for v in service.lister(ctx.db, candidat_id=candidat_id, statut=statut)
    ]


@routeur.get("/{validation_id}", response_model=ValidationSortie)
def detail(
    validation_id: uuid.UUID,
    ctx: ContexteAuth = HumainValideur,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> ValidationSortie:
    v = service.obtenir(ctx.db, validation_id)
    return _sortie(ctx.db, v, cle_maitresse, avec_contenu=True)


@routeur.post("/{validation_id}/valider", response_model=ValidationSortie)
def valider(
    validation_id: uuid.UUID,
    ctx: ContexteAuth = HumainValideur,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> ValidationSortie:
    v = service.valider(
        ctx.db, validation_id, utilisateur=ctx.utilisateur, cle_maitresse=cle_maitresse
    )
    return _sortie(ctx.db, v, cle_maitresse, avec_contenu=True)


@routeur.post("/{validation_id}/refuser", response_model=ValidationSortie)
def refuser(
    validation_id: uuid.UUID,
    ctx: ContexteAuth = HumainValideur,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> ValidationSortie:
    v = service.refuser(ctx.db, validation_id, utilisateur=ctx.utilisateur)
    return _sortie(ctx.db, v, cle_maitresse, avec_contenu=True)
