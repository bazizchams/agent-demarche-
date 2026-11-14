"""Suggestions de vœux selon les prérequis réels du catalogue (LECTURE SEULE).

Cette route ne crée AUCUN vœu : la création reste une action humaine via `/candidats/{id}/voeux`.
Rôle requis (administrateur ou employé), CSRF vérifié (méthode POST), audit sans donnée personnelle.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependances import ContexteAuth, exiger_roles
from app.core.config import Parametres, obtenir_parametres
from app.modeles.utilisateur import Role
from app.schemas.selection_voeux import DemandeSuggestions, ReponseSuggestions
from app.services import selection_voeux

routeur = APIRouter(prefix="/voeux", tags=["suggestions de voeux"])

ExigerRoleDossier = Depends(exiger_roles(Role.ADMINISTRATEUR, Role.EMPLOYE))


@routeur.post("/suggestions", response_model=ReponseSuggestions)
def suggerer(
    demande: DemandeSuggestions,
    ctx: ContexteAuth = ExigerRoleDossier,
    parametres: Parametres = Depends(obtenir_parametres),
) -> ReponseSuggestions:
    return selection_voeux.suggerer_voeux(
        ctx.db,
        profil=demande.profil,
        acteur_id=ctx.utilisateur.id,
        dossier_demarches=parametres.dossier_demarches,
        candidat_id=demande.candidat_id,
        code_demarche=demande.code_demarche,
        max_voeux=demande.max_voeux,
    )
