"""Catalogue de fiches de formation du bureau : consultation, import des écoles, import de fiches relevées.

R6 : une fiche issue de l'exploration du portail (`source = exploration`) doit porter une URL d'un domaine
officiel des YAML de portail. Multi-tenant : toutes les opérations sont limitées au bureau de l'appelant.
"""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, Depends
from pydantic import Field

from app.agent_local.domaines_officiels import politique_depuis_parametres
from app.api.dependances import ContexteAuth, exiger_roles, obtenir_contexte_auth
from app.core.config import Parametres, obtenir_parametres
from app.core.erreurs import DonneesInvalides
from app.modeles.utilisateur import Role
from app.schemas.commun import SchemaEntree
from app.services import catalogue_formations
from app.services.fiche_formation import FicheEntree, exigences_inconnues

routeur = APIRouter(prefix="/catalogue-formations", tags=["catalogue de formations"])

ExigerRoleDossier = Depends(exiger_roles(Role.ADMINISTRATEUR, Role.EMPLOYE))


class ImportFiches(SchemaEntree):
    fiches: list[FicheEntree] = Field(min_length=1, max_length=catalogue_formations.MAX_FICHES_PAR_IMPORT)


def _verifier_domaines_officiels(fiches: list[FicheEntree], parametres: Parametres) -> None:
    domaines = politique_depuis_parametres(parametres).domaines_https
    for fiche in fiches:
        if fiche.source == "yaml":
            raise DonneesInvalides("Source « yaml » refusée : réservée à l'import des écoles du bureau.")
        if fiche.source != "exploration" and not fiche.url_officielle:
            continue
        hote = (urlparse(fiche.url_officielle or "").hostname or "").lower()
        if hote not in domaines:
            raise DonneesInvalides(
                "Fiche refusée (Règle 6) : l'URL d'une fiche doit appartenir à un domaine officiel."
            )


@routeur.get("")
def lister(ctx: ContexteAuth = Depends(obtenir_contexte_auth)) -> list[dict]:
    return [
        {
            "id": str(fiche_id),
            **fiche.model_dump(mode="json"),
            "exigences_a_verifier": exigences_inconnues(fiche),
        }
        for fiche_id, fiche in catalogue_formations.charger_fiches(ctx.db)
    ]


@routeur.post("/import-ecoles")
def importer_ecoles(ctx: ContexteAuth = ExigerRoleDossier) -> dict[str, int]:
    return catalogue_formations.importer_ecoles_yaml(ctx.db, acteur_id=ctx.utilisateur.id)


@routeur.post("/fiches")
def importer_fiches(
    donnees: ImportFiches,
    ctx: ContexteAuth = ExigerRoleDossier,
    parametres: Parametres = Depends(obtenir_parametres),
) -> dict[str, int]:
    _verifier_domaines_officiels(donnees.fiches, parametres)
    return catalogue_formations.enregistrer_fiches(ctx.db, donnees.fiches, acteur_id=ctx.utilisateur.id)
