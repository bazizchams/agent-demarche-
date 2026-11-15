"""Routeur servant l'interface web complète en français de la plateforme.

La page est une chaîne unique assemblée à l'import :

- `design/` : système de design (tokens clairs et sombres, composants), coquille (navigation
  groupée par tâche, thème), tableau de bord d'accueil, gabarits des écrans et JavaScript ;
- `ecrans_coffre_validation` : coffre d'identifiants portail et récapitulatifs à valider ;
- `ecran_navigateur_serveur` : vue et prise en main du navigateur de l'agent.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.interface.design.page import construire_page_base
from app.interface.design.ecran_discussion_agent import assembler_discussion_agent
from app.interface.design.ecran_flux_dossier import assembler_flux_dossier
from app.interface.design.ecran_projet import assembler_projet
from app.interface.ecran_navigateur_serveur import assembler_navigateur_serveur
from app.interface.ecran_revue_extractions import assembler_revue_extractions
from app.interface.ecrans_coffre_validation import assembler_interface

routeur_interface = APIRouter(tags=["interface web en français"])

_HTML_INTERFACE_BASE = construire_page_base()

# Ajoute le coffre d'identifiants (Règle 3), les récapitulatifs à valider (Règle 1) et le
# navigateur de l'agent.
HTML_INTERFACE_FR = assembler_discussion_agent(
    assembler_flux_dossier(
        assembler_projet(
            assembler_revue_extractions(assembler_navigateur_serveur(assembler_interface(_HTML_INTERFACE_BASE)))
        )
    )
)


@routeur_interface.get("/", response_class=HTMLResponse)
@routeur_interface.get("/interface", response_class=HTMLResponse)
def afficher_interface_francaise() -> HTMLResponse:
    return HTMLResponse(content=HTML_INTERFACE_FR)
