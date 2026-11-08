"""Routes d'information et de paramétrage du bureau courant."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependances import ContexteAuth, exiger_roles, obtenir_contexte_auth
from app.modeles.utilisateur import Role
from app.schemas.bureau import BureauModification, BureauSortie
from app.services import bureaux as service_bureaux

routeur = APIRouter(prefix="/bureau", tags=["bureau"])


@routeur.get("", response_model=BureauSortie)
def obtenir(
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
) -> BureauSortie:
    bureau = service_bureaux.obtenir_bureau_courant(ctx.db)
    return BureauSortie.model_validate(bureau)


@routeur.patch("", response_model=BureauSortie)
def renommer(
    donnees: BureauModification,
    ctx: ContexteAuth = Depends(exiger_roles(Role.ADMINISTRATEUR)),
) -> BureauSortie:
    bureau = service_bureaux.renommer_bureau_courant(
        ctx.db, nouveau_nom=donnees.nom, acteur_id=ctx.utilisateur.id
    )
    return BureauSortie.model_validate(bureau)
