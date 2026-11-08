"""Routes de gestion des utilisateurs du bureau (réservées aux administrateurs)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.dependances import ContexteAuth, exiger_roles
from app.core.config import Parametres, obtenir_parametres
from app.modeles.utilisateur import Role
from app.schemas.auth import (
    ReinitialisationMotDePasseEntree,
    UtilisateurCreation,
    UtilisateurModification,
    UtilisateurSortie,
)
from app.schemas.commun import Page
from app.services import utilisateurs as service_utilisateurs

routeur = APIRouter(prefix="/utilisateurs", tags=["utilisateurs"])

ExigerAdmin = Depends(exiger_roles(Role.ADMINISTRATEUR))


@routeur.get("", response_model=Page[UtilisateurSortie])
def lister(
    page: int = Query(default=1, ge=1),
    taille: int = Query(default=20, ge=1, le=100),
    ctx: ContexteAuth = ExigerAdmin,
) -> Page[UtilisateurSortie]:
    elements, total = service_utilisateurs.lister_utilisateurs(
        ctx.db, page=page, taille=taille
    )
    return Page(
        elements=[UtilisateurSortie.model_validate(u) for u in elements],
        total=total,
        page=page,
        taille=taille,
    )


@routeur.get("/{utilisateur_id}", response_model=UtilisateurSortie)
def obtenir(
    utilisateur_id: uuid.UUID,
    ctx: ContexteAuth = ExigerAdmin,
) -> UtilisateurSortie:
    u = service_utilisateurs.obtenir_utilisateur(ctx.db, utilisateur_id)
    return UtilisateurSortie.model_validate(u)


@routeur.post("", response_model=UtilisateurSortie, status_code=status.HTTP_201_CREATED)
def creer(
    donnees: UtilisateurCreation,
    ctx: ContexteAuth = ExigerAdmin,
    parametres: Parametres = Depends(obtenir_parametres),
) -> UtilisateurSortie:
    u = service_utilisateurs.creer_utilisateur(
        ctx.db,
        donnees=donnees,
        acteur_id=ctx.utilisateur.id,
        parametres=parametres,
    )
    return UtilisateurSortie.model_validate(u)


@routeur.patch("/{utilisateur_id}", response_model=UtilisateurSortie)
def modifier(
    utilisateur_id: uuid.UUID,
    donnees: UtilisateurModification,
    ctx: ContexteAuth = ExigerAdmin,
) -> UtilisateurSortie:
    u = service_utilisateurs.modifier_utilisateur(
        ctx.db,
        utilisateur_id=utilisateur_id,
        donnees=donnees,
        acteur_id=ctx.utilisateur.id,
    )
    return UtilisateurSortie.model_validate(u)


@routeur.post(
    "/{utilisateur_id}/reinitialiser-mot-de-passe",
    response_model=UtilisateurSortie,
)
def reinitialiser_mot_de_passe(
    utilisateur_id: uuid.UUID,
    donnees: ReinitialisationMotDePasseEntree,
    ctx: ContexteAuth = ExigerAdmin,
    parametres: Parametres = Depends(obtenir_parametres),
) -> UtilisateurSortie:
    u = service_utilisateurs.reinitialiser_mot_de_passe(
        ctx.db,
        utilisateur_id=utilisateur_id,
        mot_de_passe_temporaire=donnees.mot_de_passe_temporaire,
        acteur_id=ctx.utilisateur.id,
        parametres=parametres,
    )
    return UtilisateurSortie.model_validate(u)
