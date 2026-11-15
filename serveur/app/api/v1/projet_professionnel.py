"""Routes du projet professionnel (phase P3) : générer un brouillon à partir des points forts
confirmés, le lire, le modifier puis le valider (humain obligatoire : rôle administrateur ou
employé, CSRF, version précise du texte).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.api.dependances import ContexteAuth, exiger_roles, obtenir_cle_maitresse, obtenir_contexte_auth
from app.modeles.utilisateur import Role
from app.schemas.deduction import (
    ProjetGenereEntree,
    ProjetModificationEntree,
    ProjetProfessionnelSortie,
    ProjetValidationEntree,
)
from app.services import projet_professionnel as service
from app.services.llm import ClientLLM, obtenir_client_llm_optionnel

routeur = APIRouter(prefix="/candidats/{candidat_id}/projet-professionnel", tags=["projet professionnel"])

ExigerEcriture = Depends(exiger_roles(Role.ADMINISTRATEUR, Role.EMPLOYE))


@routeur.post("/generer", response_model=ProjetProfessionnelSortie)
def generer(
    candidat_id: uuid.UUID,
    donnees: ProjetGenereEntree | None = None,
    ctx: ContexteAuth = ExigerEcriture,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
    client: ClientLLM | None = Depends(obtenir_client_llm_optionnel),
) -> ProjetProfessionnelSortie:
    return service.generer_projet(
        ctx.db, client, candidat_id=candidat_id, acteur_id=ctx.utilisateur.id, cle_maitresse=cle_maitresse,
        remplacer=bool(donnees and donnees.remplacer),
        remplacer_valide=bool(donnees and donnees.remplacer_valide),
    )


@routeur.get("", response_model=ProjetProfessionnelSortie)
def lire(
    candidat_id: uuid.UUID,
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> ProjetProfessionnelSortie:
    return service.lire_projet(ctx.db, candidat_id=candidat_id, cle_maitresse=cle_maitresse)


@routeur.put("", response_model=ProjetProfessionnelSortie)
def modifier(
    candidat_id: uuid.UUID,
    donnees: ProjetModificationEntree,
    ctx: ContexteAuth = ExigerEcriture,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> ProjetProfessionnelSortie:
    return service.modifier_projet(
        ctx.db, candidat_id=candidat_id, texte=donnees.texte, version=donnees.version,
        acteur_id=ctx.utilisateur.id, cle_maitresse=cle_maitresse,
    )


@routeur.post("/valider", response_model=ProjetProfessionnelSortie)
def valider(
    candidat_id: uuid.UUID,
    donnees: ProjetValidationEntree,
    ctx: ContexteAuth = ExigerEcriture,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> ProjetProfessionnelSortie:
    return service.valider_projet(
        ctx.db, candidat_id=candidat_id, version=donnees.version, acteur_id=ctx.utilisateur.id,
        cle_maitresse=cle_maitresse,
    )
