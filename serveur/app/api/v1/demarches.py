"""Routes de consultation des démarches configurées en YAML (règle 7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependances import ContexteAuth, obtenir_contexte_auth
from app.core.config import Parametres, obtenir_parametres
from app.schemas.document import DemarcheResumeSortie
from app.services import pieces_requises as service_pieces

routeur = APIRouter(prefix="/demarches", tags=["démarches"])


@routeur.get("", response_model=list[DemarcheResumeSortie])
def lister(
    _ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    parametres: Parametres = Depends(obtenir_parametres),
) -> list[DemarcheResumeSortie]:
    return service_pieces.lister_demarches(parametres.dossier_demarches)
