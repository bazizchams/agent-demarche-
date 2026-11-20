"""Routes du dépôt de passeport SANS fiche : lecture de la MRZ, propositions, création de la fiche confirmée.

Sécurité : session et CSRF sur toute écriture, rôle administrateur ou employé ; lecture limitée par
utilisateur (comme l'extraction). Aucune fiche n'est créée sans `confirme=true` et sans les valeurs
confirmées par l'humain.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile, status
from fastapi.responses import JSONResponse

from app.api.dependances import ContexteAuth, exiger_roles, obtenir_cle_maitresse, obtenir_contexte_auth
from app.api.v1.extractions import _limiter_extractions, obtenir_lecteur_document
from app.core.config import Parametres, obtenir_parametres
from app.modeles.utilisateur import Role
from app.schemas.depot_passeport import CreationFicheEntree, DepotPasseportSortie, FicheCreeeSortie
from app.services import depots_passeport as service
from app.services.lecture_documents import LecteurDocument

routeur = APIRouter(prefix="/depots-passeport", tags=["dépôt de passeport sans fiche"])

ExigerEcriture = Depends(exiger_roles(Role.ADMINISTRATEUR, Role.EMPLOYE))


@routeur.post("", response_model=DepotPasseportSortie, status_code=status.HTTP_201_CREATED)
async def deposer(
    requete: Request,
    fichier: UploadFile = File(...),
    ctx: ContexteAuth = ExigerEcriture,
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
    lecteur: LecteurDocument = Depends(obtenir_lecteur_document),
) -> DepotPasseportSortie:
    _limiter_extractions(requete, ctx, parametres, lot=False)
    contenu = await fichier.read(parametres.taille_max_document_octets + 1)
    return service.deposer_passeport(
        ctx.db,
        nom_fichier_origine=fichier.filename or "passeport",
        contenu_clair=contenu,
        acteur_id=ctx.utilisateur.id,
        parametres=parametres,
        cle_maitresse=cle_maitresse,
        lecteur_document=lecteur,
    )


@routeur.get("/{depot_id}", response_model=DepotPasseportSortie)
def obtenir(
    depot_id: uuid.UUID,
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> DepotPasseportSortie:
    return service.obtenir_depot(ctx.db, depot_id=depot_id, parametres=parametres, cle_maitresse=cle_maitresse)


@routeur.delete("/{depot_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer(
    depot_id: uuid.UUID,
    ctx: ContexteAuth = ExigerEcriture,
    parametres: Parametres = Depends(obtenir_parametres),
) -> Response:
    service.supprimer_depot(ctx.db, depot_id=depot_id, acteur_id=ctx.utilisateur.id, parametres=parametres)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@routeur.post("/{depot_id}/creer-fiche", response_model=FicheCreeeSortie, status_code=status.HTTP_201_CREATED)
def creer_fiche(
    depot_id: uuid.UUID,
    donnees: CreationFicheEntree,
    ctx: ContexteAuth = ExigerEcriture,
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
    lecteur: LecteurDocument = Depends(obtenir_lecteur_document),
):
    try:
        return service.creer_fiche_depuis_depot(
            ctx.db,
            depot_id=depot_id,
            donnees=donnees,
            acteur_id=ctx.utilisateur.id,
            parametres=parametres,
            cle_maitresse=cle_maitresse,
            lecteur_document=lecteur,
        )
    except service.PasseportDejaUtilise as exc:
        return JSONResponse(
            status_code=exc.statut_http,
            content={
                "code": exc.code,
                "detail": exc.message,
                "candidat_id": str(exc.candidat_id),
                "lien": f"/api/v1/candidats/{exc.candidat_id}",
            },
        )
