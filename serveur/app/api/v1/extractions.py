"""Routes de lecture des documents d'un candidat (phase P1) : lancer l'extraction d'un document
ou d'un lot, lister les valeurs lues, les valider / rejeter / corriger (humain), puis appliquer
à la fiche uniquement les champs confirmés.

Sécurité : CSRF et session obligatoires sur toute écriture (dépendance commune), rôle
administrateur ou employé pour lancer, décider et appliquer ; un compte en lecture seule ne peut
que consulter. Un agent local n'a aucun accès ici : la validation d'une valeur est humaine.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request

from app.api.dependances import (
    ContexteAuth,
    exiger_roles,
    obtenir_cle_maitresse,
    obtenir_contexte_auth,
)
from app.core.config import Environnement, Parametres, obtenir_parametres
from app.modeles.extraction_document import StatutExtraction
from app.modeles.utilisateur import Role
from app.schemas.extraction import (
    CorrectionEntree,
    ExtractionSortie,
    RapportApplicationSortie,
    ResultatExtractionDocumentSortie,
    ResultatLotSortie,
)
from app.services import application_extractions as service_application
from app.services import extractions as service_extractions
from app.services.jetons_courriel import LimiteurDemandes
from app.services.lecture_documents import LecteurDocument, LecteurDocumentLocal
from app.services.lecture_vision import LecteurVision, construire_lecteur_vision

routeur = APIRouter(prefix="/candidats/{candidat_id}", tags=["lecture des documents"])

ExigerEcriture = Depends(exiger_roles(Role.ADMINISTRATEUR, Role.EMPLOYE))


def _limiter_extractions(
    requete: Request, ctx: ContexteAuth, parametres: Parametres, *, lot: bool
) -> None:
    """La lecture (OCR) est coûteuse : débit limité par utilisateur et par heure (limiteur en mémoire partagé
    avec la réinitialisation de mot de passe). Inactif en test sauf demande explicite."""
    if parametres.environnement is Environnement.TEST and not parametres.extraction_limite_active_en_test:
        return
    etat = requete.app.state
    if not hasattr(etat, "limiteur_extractions"):
        etat.limiteur_extractions = LimiteurDemandes()
    maximum = (
        parametres.extraction_lot_max_par_heure_par_utilisateur
        if lot
        else parametres.extraction_max_par_heure_par_utilisateur
    )
    etat.limiteur_extractions.verifier_et_compter(f"{'lot' if lot else 'doc'}:{ctx.utilisateur.id}", maximum)


def obtenir_lecteur_document() -> LecteurDocument:
    """Lecteur A local (remplaçable dans les tests)."""
    return LecteurDocumentLocal()


def obtenir_lecteur_vision(
    parametres: Parametres = Depends(obtenir_parametres),
) -> LecteurVision | None:
    """Lecteur B : None par défaut ; refuse tout hôte non local (remplaçable dans les tests)."""
    return construire_lecteur_vision(parametres)


@routeur.post(
    "/documents/{document_id}/extraire", response_model=ResultatExtractionDocumentSortie
)
def extraire_document(
    candidat_id: uuid.UUID,
    document_id: uuid.UUID,
    requete: Request,
    ctx: ContexteAuth = ExigerEcriture,
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
    lecteur: LecteurDocument = Depends(obtenir_lecteur_document),
    vision: LecteurVision | None = Depends(obtenir_lecteur_vision),
) -> ResultatExtractionDocumentSortie:
    _limiter_extractions(requete, ctx, parametres, lot=False)
    return service_extractions.lancer_extraction_document(
        ctx.db,
        candidat_id=candidat_id,
        document_id=document_id,
        acteur_id=ctx.utilisateur.id,
        parametres=parametres,
        cle_maitresse=cle_maitresse,
        lecteur_document=lecteur,
        lecteur_vision=vision,
    )


@routeur.post("/extractions/lot", response_model=ResultatLotSortie)
def extraire_lot(
    candidat_id: uuid.UUID,
    requete: Request,
    code_demarche: str | None = Query(default=None, max_length=60),
    ctx: ContexteAuth = ExigerEcriture,
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
    lecteur: LecteurDocument = Depends(obtenir_lecteur_document),
    vision: LecteurVision | None = Depends(obtenir_lecteur_vision),
) -> ResultatLotSortie:
    _limiter_extractions(requete, ctx, parametres, lot=True)
    return service_extractions.lancer_extraction_lot(
        ctx.db,
        candidat_id=candidat_id,
        code_demarche=code_demarche,
        acteur_id=ctx.utilisateur.id,
        parametres=parametres,
        cle_maitresse=cle_maitresse,
        lecteur_document=lecteur,
        lecteur_vision=vision,
    )


@routeur.get("/extractions", response_model=list[ExtractionSortie])
def lister(
    candidat_id: uuid.UUID,
    document_id: uuid.UUID | None = Query(default=None),
    statut: StatutExtraction | None = Query(default=None),
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> list[ExtractionSortie]:
    return service_extractions.lister_extractions(
        ctx.db, candidat_id=candidat_id, cle_maitresse=cle_maitresse, document_id=document_id, statut=statut
    )


def _decider(
    action: str,
    candidat_id: uuid.UUID,
    extraction_id: uuid.UUID,
    ctx: ContexteAuth,
    cle_maitresse: bytes,
    valeur: str | None = None,
) -> ExtractionSortie:
    return service_extractions.decider_extraction(
        ctx.db,
        candidat_id=candidat_id,
        extraction_id=extraction_id,
        action=action,
        valeur_corrigee=valeur,
        acteur_id=ctx.utilisateur.id,
        cle_maitresse=cle_maitresse,
    )


@routeur.post("/extractions/{extraction_id}/valider", response_model=ExtractionSortie)
def valider(
    candidat_id: uuid.UUID,
    extraction_id: uuid.UUID,
    ctx: ContexteAuth = ExigerEcriture,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> ExtractionSortie:
    return _decider("valider", candidat_id, extraction_id, ctx, cle_maitresse)


@routeur.post("/extractions/{extraction_id}/rejeter", response_model=ExtractionSortie)
def rejeter(
    candidat_id: uuid.UUID,
    extraction_id: uuid.UUID,
    ctx: ContexteAuth = ExigerEcriture,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> ExtractionSortie:
    return _decider("rejeter", candidat_id, extraction_id, ctx, cle_maitresse)


@routeur.post("/extractions/{extraction_id}/corriger", response_model=ExtractionSortie)
def corriger(
    candidat_id: uuid.UUID,
    extraction_id: uuid.UUID,
    donnees: CorrectionEntree,
    ctx: ContexteAuth = ExigerEcriture,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> ExtractionSortie:
    return _decider("corriger", candidat_id, extraction_id, ctx, cle_maitresse, donnees.valeur)


@routeur.post("/extractions/appliquer", response_model=RapportApplicationSortie)
def appliquer(
    candidat_id: uuid.UUID,
    ctx: ContexteAuth = ExigerEcriture,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> RapportApplicationSortie:
    return service_application.appliquer_extractions_a_fiche(
        ctx.db, candidat_id=candidat_id, acteur_id=ctx.utilisateur.id, cle_maitresse=cle_maitresse
    )
