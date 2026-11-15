"""Routes de gestion des candidats, de leurs documents chiffrés et des pièces requises."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status

from app.api.dependances import (
    ContexteAuth,
    exiger_roles,
    obtenir_cle_maitresse,
    obtenir_contexte_auth,
)
from app.core.config import Environnement, Parametres, obtenir_parametres
from app.core.erreurs import NonTrouve
from app.modeles.candidat import StatutCandidat
from app.modeles.utilisateur import Role
from app.schemas.candidat import (
    CandidatCreation,
    CandidatModification,
    CandidatSortie,
)
from app.schemas.commun import Page
from app.schemas.document import (
    DocumentSortie,
    EchangeDiscussionSortie,
    EtatCompletudeDemarcheSortie,
    EvaluationDossierSortie,
    MessageDiscussionSortie,
    QuestionDiscussionEntree,
)
from app.services import candidats as service_candidats
from app.services import conseiller_dossier as service_conseiller
from app.services import documents as service_documents
from app.services import pieces_requises as service_pieces

routeur = APIRouter(prefix="/candidats", tags=["candidats et documents"])

ExigerEcriture = Depends(exiger_roles(Role.ADMINISTRATEUR, Role.EMPLOYE))


@routeur.get("", response_model=Page[CandidatSortie])
def lister_ou_rechercher(
    page: int = Query(default=1, ge=1),
    taille: int = Query(default=20, ge=1, le=100),
    statut: StatutCandidat | None = Query(default=StatutCandidat.ACTIF),
    recherche: str | None = Query(default=None, max_length=120),
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> Page[CandidatSortie]:
    elements, total = service_candidats.lister_candidats(
        ctx.db,
        cle_maitresse=cle_maitresse,
        page=page,
        taille=taille,
        statut=statut,
        recherche=recherche,
    )
    return Page(elements=elements, total=total, page=page, taille=taille)


@routeur.post("", response_model=CandidatSortie, status_code=status.HTTP_201_CREATED)
def creer(
    donnees: CandidatCreation,
    ctx: ContexteAuth = ExigerEcriture,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> CandidatSortie:
    return service_candidats.creer_candidat(
        ctx.db,
        donnees=donnees,
        acteur_id=ctx.utilisateur.id,
        cle_maitresse=cle_maitresse,
    )


@routeur.get("/{candidat_id}", response_model=CandidatSortie)
def obtenir(
    candidat_id: uuid.UUID,
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> CandidatSortie:
    return service_candidats.obtenir_candidat(
        ctx.db, candidat_id=candidat_id, cle_maitresse=cle_maitresse
    )


@routeur.patch("/{candidat_id}", response_model=CandidatSortie)
def modifier(
    candidat_id: uuid.UUID,
    donnees: CandidatModification,
    ctx: ContexteAuth = ExigerEcriture,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> CandidatSortie:
    return service_candidats.modifier_candidat(
        ctx.db,
        candidat_id=candidat_id,
        donnees=donnees,
        acteur_id=ctx.utilisateur.id,
        cle_maitresse=cle_maitresse,
    )


@routeur.post("/{candidat_id}/archiver", response_model=CandidatSortie)
def archiver(
    candidat_id: uuid.UUID,
    ctx: ContexteAuth = ExigerEcriture,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> CandidatSortie:
    return service_candidats.changer_statut_archivage(
        ctx.db,
        candidat_id=candidat_id,
        archiver=True,
        acteur_id=ctx.utilisateur.id,
        cle_maitresse=cle_maitresse,
    )


@routeur.post("/{candidat_id}/restaurer", response_model=CandidatSortie)
def restaurer(
    candidat_id: uuid.UUID,
    ctx: ContexteAuth = ExigerEcriture,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> CandidatSortie:
    return service_candidats.changer_statut_archivage(
        ctx.db,
        candidat_id=candidat_id,
        archiver=False,
        acteur_id=ctx.utilisateur.id,
        cle_maitresse=cle_maitresse,
    )


# ---------------------------------------------------------------------------
# Documents du candidat
# ---------------------------------------------------------------------------

@routeur.get("/{candidat_id}/documents", response_model=list[DocumentSortie])
def lister_documents(
    candidat_id: uuid.UUID,
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> list[DocumentSortie]:
    return service_documents.lister_documents_candidat(
        ctx.db, candidat_id=candidat_id, cle_maitresse=cle_maitresse
    )


@routeur.post(
    "/{candidat_id}/documents",
    response_model=DocumentSortie,
    status_code=status.HTTP_201_CREATED,
)
async def deposer_document(
    candidat_id: uuid.UUID,
    type_piece: str = Form(..., min_length=1, max_length=80),
    date_expiration: date | None = Form(default=None),
    date_expiration_piece: date | None = Form(default=None),
    fichier: UploadFile = File(...),
    ctx: ContexteAuth = ExigerEcriture,
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> DocumentSortie:
    # Lecture bornée (+1 octet) pour refuser immédiatement un fichier trop volumineux
    # sans saturer la mémoire.
    contenu = await fichier.read(parametres.taille_max_document_octets + 1)
    return service_documents.deposer_document(
        ctx.db,
        candidat_id=candidat_id,
        type_piece=type_piece,
        nom_fichier_origine=fichier.filename or "document",
        contenu_clair=contenu,
        date_expiration=date_expiration or date_expiration_piece,
        acteur_id=ctx.utilisateur.id,
        parametres=parametres,
        cle_maitresse=cle_maitresse,
    )


@routeur.get("/{candidat_id}/documents/{document_id}/telecharger")
def telecharger_document(
    candidat_id: uuid.UUID,
    document_id: uuid.UUID,
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> Response:
    meta, octets = service_documents.lire_document_dechiffre(
        ctx.db,
        candidat_id=candidat_id,
        document_id=document_id,
        parametres=parametres,
        cle_maitresse=cle_maitresse,
    )
    return Response(
        content=octets,
        media_type=meta.type_mime,
        headers={
            "Content-Disposition": f'attachment; filename="{meta.id}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@routeur.delete(
    "/{candidat_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def supprimer_document(
    candidat_id: uuid.UUID,
    document_id: uuid.UUID,
    ctx: ContexteAuth = ExigerEcriture,
    parametres: Parametres = Depends(obtenir_parametres),
) -> Response:
    service_documents.supprimer_document(
        ctx.db,
        candidat_id=candidat_id,
        document_id=document_id,
        acteur_id=ctx.utilisateur.id,
        parametres=parametres,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@routeur.post(
    "/{candidat_id}/documents/specimens-demo",
    response_model=list[DocumentSortie],
    status_code=status.HTTP_201_CREATED,
)
def generer_specimens_demonstration(
    candidat_id: uuid.UUID,
    code_demarche: str | None = Query(default=None, max_length=60),
    ctx: ContexteAuth = ExigerEcriture,
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> list[DocumentSortie]:
    """Dépose des documents PDF spécimens chiffrés pour les pièces manquantes du candidat
    afin de faciliter le test immédiat des démarches Campus France et IRCC.

    Hors production uniquement : en production la route est introuvable (404), pour ne jamais
    fabriquer de fausses pièces dans un vrai dossier (règle 4)."""
    from datetime import timedelta

    if parametres.environnement is Environnement.PRODUCTION:
        raise NonTrouve("Ressource introuvable.")

    service_candidats.obtenir_candidat(
        ctx.db, candidat_id=candidat_id, cle_maitresse=cle_maitresse
    )
    docs_existants = {
        d.type_piece for d in service_documents.lister_documents_orm(ctx.db, candidat_id=candidat_id)
    }
    codes = [code_demarche] if code_demarche else ["campus_france", "ircc_permis_etudes"]
    types_a_creer: list[str] = []
    for c_dem in codes:
        try:
            dem = service_pieces.obtenir_demarche(
                parametres.dossier_demarches, c_dem, ctx.db
            )
            for p in dem.pieces_requises:
                if p.type_piece not in docs_existants and p.type_piece not in types_a_creer:
                    types_a_creer.append(p.type_piece)
        except Exception:
            continue

    exp_future = date.today() + timedelta(days=730)
    crees: list[DocumentSortie] = []
    for idx, tp in enumerate(types_a_creer):
        octets_pdf = (
            b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
            + f"% Specimen {tp} candidat {candidat_id} idx {idx}\n%%EOF\n".encode("ascii")
        )
        doc_cree = service_documents.deposer_document(
            ctx.db,
            candidat_id=candidat_id,
            type_piece=tp,
            nom_fichier_origine=f"specimen_{tp}.pdf",
            contenu_clair=octets_pdf,
            date_expiration=exp_future,
            acteur_id=ctx.utilisateur.id,
            parametres=parametres,
            cle_maitresse=cle_maitresse,
        )
        crees.append(doc_cree)

    return crees



# ---------------------------------------------------------------------------
# Contrôle de complétude et pièces manquantes par démarche (YAML)
# ---------------------------------------------------------------------------

@routeur.get(
    "/{candidat_id}/completude/{code_demarche}",
    response_model=EtatCompletudeDemarcheSortie,
)
def verifier_completude(
    candidat_id: uuid.UUID,
    code_demarche: str,
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> EtatCompletudeDemarcheSortie:
    candidat = service_candidats.obtenir_candidat(
        ctx.db, candidat_id=candidat_id, cle_maitresse=cle_maitresse
    )
    docs_orm = service_documents.lister_documents_orm(
        ctx.db, candidat_id=candidat_id
    )
    demarche = service_pieces.obtenir_demarche(
        parametres.dossier_demarches, code_demarche, ctx.db
    )
    return service_pieces.verifier_completude_dossier(
        candidat=candidat,
        documents=docs_orm,
        demarche=demarche,
    )


# ---------------------------------------------------------------------------
# Évaluation du pourcentage d'acceptation et espace discussion conseiller
# ---------------------------------------------------------------------------

@routeur.get(
    "/{candidat_id}/evaluation/{code_demarche}",
    response_model=EvaluationDossierSortie,
)
def evaluer_dossier(
    candidat_id: uuid.UUID,
    code_demarche: str,
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> EvaluationDossierSortie:
    candidat = service_candidats.obtenir_candidat(
        ctx.db, candidat_id=candidat_id, cle_maitresse=cle_maitresse
    )
    docs_orm = service_documents.lister_documents_orm(
        ctx.db, candidat_id=candidat_id
    )
    demarche = service_pieces.obtenir_demarche(
        parametres.dossier_demarches, code_demarche, ctx.db
    )
    return service_conseiller.evaluer_dossier(
        candidat=candidat,
        documents=docs_orm,
        demarche=demarche,
    )


@routeur.post(
    "/{candidat_id}/discussion",
    response_model=EchangeDiscussionSortie,
    status_code=status.HTTP_201_CREATED,
)
def poser_question_dossier(
    candidat_id: uuid.UUID,
    donnees: QuestionDiscussionEntree,
    ctx: ContexteAuth = ExigerEcriture,
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> EchangeDiscussionSortie:
    return service_conseiller.poser_question_dossier(
        ctx.db,
        candidat_id=candidat_id,
        code_demarche=donnees.code_demarche,
        message_utilisateur=donnees.message,
        acteur_id=ctx.utilisateur.id,
        parametres=parametres,
        cle_maitresse=cle_maitresse,
    )


@routeur.get(
    "/{candidat_id}/discussion",
    response_model=list[MessageDiscussionSortie],
)
def lister_discussion_dossier(
    candidat_id: uuid.UUID,
    code_demarche: str | None = Query(default=None, max_length=60),
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> list[MessageDiscussionSortie]:
    return service_conseiller.lister_messages_dossier(
        ctx.db,
        candidat_id=candidat_id,
        code_demarche=code_demarche,
        cle_maitresse=cle_maitresse,
    )
