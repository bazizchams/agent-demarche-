"""Routes des démarches : consultation, ajout et modification par bureau (règle 7).

Les démarches de base viennent des fichiers YAML ; chaque bureau peut en ajouter ou les
personnaliser sans redéploiement. Seul un administrateur peut écrire.
"""

from __future__ import annotations

import datetime as dt
from datetime import date

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from app.api.dependances import ContexteAuth, exiger_roles, obtenir_contexte_auth
from app.core.config import Parametres, obtenir_parametres
from app.modeles.utilisateur import Role
from app.schemas.document import DemarcheResumeSortie
from app.services import demarches_bureau as service_demarches
from app.services import pieces_requises as service_pieces
from app.services.echeances_demarche import calculer_echeances
from app.services.pieces_requises import ConfigDemarche

routeur = APIRouter(prefix="/demarches", tags=["démarches"])


class DemarcheMetaSortie(BaseModel):
    code: str
    libelle: str
    source: str  # "base" (YAML commun) ou "bureau" (définie ou personnalisée par le bureau)
    version: int
    actif: bool


class EcheanceSortie(BaseModel):
    code: str
    libelle: str
    date: dt.date | None
    jours_restants: int | None
    statut: str
    rappels_dus: list[int]


class DemarcheCompleteSortie(BaseModel):
    source: str
    version: int
    actif: bool
    definition: ConfigDemarche


@routeur.get("", response_model=list[DemarcheResumeSortie])
def lister(
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    parametres: Parametres = Depends(obtenir_parametres),
) -> list[DemarcheResumeSortie]:
    return service_pieces.lister_demarches(parametres.dossier_demarches, ctx.db)


@routeur.get("/gestion", response_model=list[DemarcheMetaSortie])
def lister_gestion(
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    parametres: Parametres = Depends(obtenir_parametres),
) -> list[DemarcheMetaSortie]:
    elements = service_demarches.lister_metadonnees(ctx.db, parametres.dossier_demarches)
    return [DemarcheMetaSortie(**e) for e in elements]


@routeur.get("/{code}/echeances", response_model=list[EcheanceSortie])
def echeances(
    code: str,
    date_rentree: date | None = None,
    date_depot: date | None = None,
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    parametres: Parametres = Depends(obtenir_parametres),
) -> list[EcheanceSortie]:
    definition, _meta = service_demarches.obtenir(
        ctx.db, parametres.dossier_demarches, code
    )
    calculees = calculer_echeances(
        definition,
        aujourd_hui=date.today(),
        date_rentree=date_rentree,
        date_depot=date_depot,
    )
    return [EcheanceSortie(**e) for e in calculees]


@routeur.get("/{code}", response_model=DemarcheCompleteSortie)
def obtenir(
    code: str,
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    parametres: Parametres = Depends(obtenir_parametres),
) -> DemarcheCompleteSortie:
    definition, meta = service_demarches.obtenir(
        ctx.db, parametres.dossier_demarches, code
    )
    return DemarcheCompleteSortie(definition=definition, **meta)


@routeur.post("", response_model=DemarcheCompleteSortie, status_code=status.HTTP_201_CREATED)
def creer(
    definition: ConfigDemarche,
    ctx: ContexteAuth = Depends(exiger_roles(Role.ADMINISTRATEUR)),
    parametres: Parametres = Depends(obtenir_parametres),
) -> DemarcheCompleteSortie:
    ligne = service_demarches.creer(
        ctx.db, parametres.dossier_demarches, definition, ctx.utilisateur.id
    )
    return DemarcheCompleteSortie(
        source="bureau",
        version=ligne.version,
        actif=ligne.actif,
        definition=ConfigDemarche.model_validate(ligne.definition),
    )


@routeur.put("/{code}", response_model=DemarcheCompleteSortie)
def remplacer(
    code: str,
    definition: ConfigDemarche,
    ctx: ContexteAuth = Depends(exiger_roles(Role.ADMINISTRATEUR)),
    parametres: Parametres = Depends(obtenir_parametres),
) -> DemarcheCompleteSortie:
    ligne = service_demarches.remplacer(
        ctx.db, code, definition, ctx.utilisateur.id, parametres.dossier_demarches
    )
    return DemarcheCompleteSortie(
        source="bureau",
        version=ligne.version,
        actif=ligne.actif,
        definition=ConfigDemarche.model_validate(ligne.definition),
    )


@routeur.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT)
def desactiver(
    code: str,
    ctx: ContexteAuth = Depends(exiger_roles(Role.ADMINISTRATEUR)),
    parametres: Parametres = Depends(obtenir_parametres),
) -> Response:
    service_demarches.desactiver(
        ctx.db, code, ctx.utilisateur.id, parametres.dossier_demarches
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
