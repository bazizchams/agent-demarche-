"""Routes de l'assistant IA (Claude). Désactivées (503) tant qu'aucune clé API n'est configurée."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependances import ContexteAuth, exiger_roles, obtenir_cle_maitresse
from app.core.config import Parametres, obtenir_parametres
from app.modeles.utilisateur import Role
from app.services import assistant_ia as service_ia
from app.services import llm
from app.services.llm import ClientLLM, obtenir_client_llm
from app.services.pieces_requises import ConfigDemarche

routeur = APIRouter(prefix="/ia", tags=["assistant IA"])


class GenerationProcedureEntree(BaseModel):
    model_config = ConfigDict(extra="forbid")

    texte: str = Field(min_length=1, max_length=service_ia.TAILLE_MAX_TEXTE_SOURCE + 1000)


class GenerationProcedureSortie(BaseModel):
    brouillon: ConfigDemarche
    avertissements: list[str]


class QuestionAssistantEntree(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code_demarche: str = Field(min_length=1, max_length=60)
    question: str = Field(min_length=1, max_length=2000)


class ReponseAssistantSortie(BaseModel):
    reponse: str
    mention: str


class StatutIASortie(BaseModel):
    active: bool
    appels_ce_mois: int
    plafond_mensuel: int


@routeur.get("/statut", response_model=StatutIASortie)
def statut(
    ctx: ContexteAuth = Depends(exiger_roles(Role.ADMINISTRATEUR, Role.EMPLOYE, Role.LECTURE_SEULE)),
    parametres: Parametres = Depends(obtenir_parametres),
) -> StatutIASortie:
    return StatutIASortie(
        active=bool(parametres.cle_api_anthropic),
        appels_ce_mois=llm.appels_ia_ce_mois(ctx.db),
        plafond_mensuel=llm.plafond_ia(ctx.db),
    )


@routeur.post("/procedures/generer", response_model=GenerationProcedureSortie)
def generer_procedure(
    donnees: GenerationProcedureEntree,
    ctx: ContexteAuth = Depends(exiger_roles(Role.ADMINISTRATEUR)),
    client: ClientLLM = Depends(obtenir_client_llm),
) -> GenerationProcedureSortie:
    brouillon, avertissements = service_ia.generer_procedure(
        ctx.db, client, texte=donnees.texte, acteur_id=ctx.utilisateur.id
    )
    return GenerationProcedureSortie(brouillon=brouillon, avertissements=avertissements)


@routeur.post("/dossiers/{candidat_id}/assistant", response_model=ReponseAssistantSortie)
def assistant_dossier(
    candidat_id: uuid.UUID,
    donnees: QuestionAssistantEntree,
    ctx: ContexteAuth = Depends(exiger_roles(Role.ADMINISTRATEUR, Role.EMPLOYE)),
    client: ClientLLM = Depends(obtenir_client_llm),
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> ReponseAssistantSortie:
    texte = service_ia.conseiller_dossier_ia(
        ctx.db,
        client,
        candidat_id=candidat_id,
        code_demarche=donnees.code_demarche,
        question=donnees.question,
        acteur_id=ctx.utilisateur.id,
        parametres=parametres,
        cle_maitresse=cle_maitresse,
    )
    return ReponseAssistantSortie(
        reponse=texte,
        mention=(
            "Réponse générée par IA à partir de la procédure et de l'état du dossier, "
            "sans aucune donnée personnelle du candidat. À vérifier avant toute décision."
        ),
    )
