"""Routes du Centre de validation humaine (Règle 1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependances import ContexteAuth, obtenir_cle_maitresse, obtenir_contexte_auth
from app.schemas.tache import SyntheseCentreValidationSortie
from app.services import taches as service_taches

routeur = APIRouter(prefix="/validations", tags=["centre de validation humaine"])


@routeur.get("/en-attente", response_model=SyntheseCentreValidationSortie)
def lister_en_attente(
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> SyntheseCentreValidationSortie:
    return service_taches.obtenir_synthese_centre_validation(
        ctx.db, cle_maitresse=cle_maitresse
    )
