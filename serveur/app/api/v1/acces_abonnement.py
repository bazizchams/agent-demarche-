"""État d'accès du bureau selon son abonnement (essai, actif, lecture seule)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.dependances import ContexteAuth, obtenir_contexte_auth
from app.core.config import Parametres, obtenir_parametres
from app.services import acces_abonnement as service_acces

routeur = APIRouter(prefix="/abonnement", tags=["abonnement"])


class AccesSortie(BaseModel):
    # Faux hors production (sauf réglage explicite) : l'état est alors donné à titre indicatif.
    controle_actif: bool
    acces_complet: bool
    motif: str
    statut: str
    fin: datetime | None
    jours_restants: int | None
    message: str


@routeur.get("/acces", response_model=AccesSortie)
def lire_acces(
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    parametres: Parametres = Depends(obtenir_parametres),
) -> AccesSortie:
    acces = service_acces.evaluer_acces(ctx.db, parametres)
    return AccesSortie(
        controle_actif=parametres.blocage_abonnement_actif,
        acces_complet=acces.acces_complet,
        motif=acces.motif,
        statut=acces.statut,
        fin=acces.fin,
        jours_restants=acces.jours_restants,
        message=acces.message,
    )
