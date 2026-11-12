"""Routes des voeux de formation d'un candidat (panier Campus France, 7 voeux maximum)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependances import (
    ContexteAuth,
    exiger_roles,
    obtenir_cle_maitresse,
    obtenir_contexte_auth,
)
from app.modeles.utilisateur import Role
from app.modeles.voeu_formation import (
    MAX_CARACTERES_MOTIVATION,
    MAX_VOEUX,
    StatutVoeu,
    VoieVoeu,
)
from app.services import lettres_voeux as service_lettres
from app.services import voeux as service_voeux
from app.services.lettres_motivation import FaitsParcours
from app.services.llm import ClientLLM, obtenir_client_llm_optionnel

routeur = APIRouter(prefix="/candidats/{candidat_id}/voeux", tags=["voeux de formation"])

ExigerEcriture = Depends(exiger_roles(Role.ADMINISTRATEUR, Role.EMPLOYE))


class VoeuCreation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intitule: str = Field(min_length=1, max_length=250)
    etablissement: str = Field(min_length=1, max_length=200)
    niveau: str = Field(min_length=1, max_length=40)
    voie: VoieVoeu = VoieVoeu.HORS_DAP
    url_source: str | None = Field(default=None, max_length=500)
    justification: str | None = Field(default=None, max_length=500)
    motivation: str | None = Field(default=None, max_length=MAX_CARACTERES_MOTIVATION)


class VoeuModification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intitule: str | None = Field(default=None, min_length=1, max_length=250)
    etablissement: str | None = Field(default=None, min_length=1, max_length=200)
    niveau: str | None = Field(default=None, min_length=1, max_length=40)
    voie: VoieVoeu | None = None
    url_source: str | None = Field(default=None, max_length=500)
    justification: str | None = Field(default=None, max_length=500)
    motivation: str | None = Field(default=None, max_length=MAX_CARACTERES_MOTIVATION)
    rang: int | None = Field(default=None, ge=1, le=MAX_VOEUX)


class VoeuSortie(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    candidat_id: uuid.UUID
    rang: int
    intitule: str
    etablissement: str
    niveau: str
    voie: VoieVoeu
    url_source: str | None
    justification: str | None
    motivation: str | None
    nb_caracteres_motivation: int
    statut: StatutVoeu
    cree_le: datetime
    modifie_le: datetime


@routeur.get("", response_model=list[VoeuSortie])
def lister(
    candidat_id: uuid.UUID,
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> list[dict]:
    return service_voeux.lister_voeux(ctx.db, candidat_id, cle_maitresse)


@routeur.post("", response_model=VoeuSortie, status_code=status.HTTP_201_CREATED)
def creer(
    candidat_id: uuid.UUID,
    donnees: VoeuCreation,
    ctx: ContexteAuth = ExigerEcriture,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> dict:
    return service_voeux.creer_voeu(
        ctx.db,
        candidat_id=candidat_id,
        donnees=donnees.model_dump(),
        acteur_id=ctx.utilisateur.id,
        cle_maitresse=cle_maitresse,
    )


TexteCourt = Annotated[str, Field(min_length=1, max_length=300)]


class FaitsParcoursEntree(BaseModel):
    """Faits fournis par l'agent (jamais d'identité : ni nom, ni date de naissance, ni passeport)."""

    model_config = ConfigDict(extra="forbid")

    parcours: list[TexteCourt] = Field(default_factory=list, max_length=20)
    points_forts: list[TexteCourt] = Field(default_factory=list, max_length=20)
    langues: list[TexteCourt] = Field(default_factory=list, max_length=10)
    projet: str | None = Field(default=None, max_length=800)
    remarques: str | None = Field(default=None, max_length=800)


class LettreSortie(BaseModel):
    voeu: VoeuSortie
    elements_a_verifier: list[str]
    origine: str  # "ia" (modèle Claude) ou "modele" (lettre type à compléter)


@routeur.post("/{voeu_id}/lettre/generer", response_model=LettreSortie)
def generer_lettre(
    candidat_id: uuid.UUID,
    voeu_id: uuid.UUID,
    faits: FaitsParcoursEntree,
    ctx: ContexteAuth = ExigerEcriture,
    client: ClientLLM | None = Depends(obtenir_client_llm_optionnel),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> dict:
    """Rédige la lettre du vœu et l'enregistre EN BROUILLON (à relire puis valider)."""
    return service_lettres.generer_lettre_pour_voeu(
        ctx.db,
        client,
        candidat_id=candidat_id,
        voeu_id=voeu_id,
        faits=FaitsParcours(**faits.model_dump()),
        acteur_id=ctx.utilisateur.id,
        cle_maitresse=cle_maitresse,
    )


@routeur.patch("/{voeu_id}", response_model=VoeuSortie)
def modifier(
    candidat_id: uuid.UUID,
    voeu_id: uuid.UUID,
    donnees: VoeuModification,
    ctx: ContexteAuth = ExigerEcriture,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> dict:
    return service_voeux.modifier_voeu(
        ctx.db,
        candidat_id=candidat_id,
        voeu_id=voeu_id,
        donnees=donnees.model_dump(exclude_unset=True),
        acteur_id=ctx.utilisateur.id,
        cle_maitresse=cle_maitresse,
    )


@routeur.post("/{voeu_id}/valider", response_model=VoeuSortie)
def valider(
    candidat_id: uuid.UUID,
    voeu_id: uuid.UUID,
    ctx: ContexteAuth = ExigerEcriture,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> dict:
    return service_voeux.valider_voeu(
        ctx.db,
        candidat_id=candidat_id,
        voeu_id=voeu_id,
        acteur_id=ctx.utilisateur.id,
        cle_maitresse=cle_maitresse,
    )


@routeur.post("/{voeu_id}/marquer-ajoute", response_model=VoeuSortie)
def marquer_ajoute(
    candidat_id: uuid.UUID,
    voeu_id: uuid.UUID,
    ctx: ContexteAuth = ExigerEcriture,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> dict:
    return service_voeux.marquer_ajoute_au_panier(
        ctx.db,
        candidat_id=candidat_id,
        voeu_id=voeu_id,
        acteur_id=ctx.utilisateur.id,
        cle_maitresse=cle_maitresse,
    )


@routeur.delete("/{voeu_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer(
    candidat_id: uuid.UUID,
    voeu_id: uuid.UUID,
    ctx: ContexteAuth = ExigerEcriture,
) -> Response:
    service_voeux.supprimer_voeu(
        ctx.db, candidat_id=candidat_id, voeu_id=voeu_id, acteur_id=ctx.utilisateur.id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
