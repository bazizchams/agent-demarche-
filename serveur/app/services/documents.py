"""Service de gestion des documents des candidats :
stockage chiffré AES-256-GCM par bureau et par candidat, contrôle des signatures binaires,
détection des doublons par empreinte HMAC-SHA256 et suppression sécurisée.
"""

from __future__ import annotations

import unicodedata
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.chiffrement import (
    calculer_empreinte_document,
    chiffrer_champ,
    chiffrer_octets,
    dechiffrer_champ,
    dechiffrer_octets,
)
from app.core.config import Parametres
from app.core.erreurs import Conflit, DonneesInvalides, NonTrouve
from app.db.tenant import tenant_courant
from app.modeles.document import DocumentCandidat
from app.modeles.journal_audit import ResultatAudit
from app.schemas.document import DocumentSortie
from app.services import audit
from app.services.candidats import obtenir_candidat_orm
from app.services.pieces_requises import verifier_type_piece_autorise


def _detecter_type_mime_par_signature(contenu: bytes) -> str:
    """Vérifie l'en-tête binaire (magic bytes) du fichier : seuls PDF, JPEG et PNG sont acceptés."""
    if contenu.startswith(b"%PDF-"):
        return "application/pdf"
    if contenu.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if contenu.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    raise DonneesInvalides(
        "Format de fichier non autorisé (seuls les fichiers PDF, PNG et JPEG authentiques sont acceptés)."
    )


def _normaliser_nom_fichier(nom_brut: str) -> str:
    base = Path(nom_brut.replace("\\", "/")).name.strip()
    normalise = unicodedata.normalize("NFC", base)
    if not normalise or normalise in {".", ".."}:
        return "document"
    return normalise[:200]


def _resoudre_chemin_stockage(
    dossier_racine: Path, chemin_relatif: str
) -> Path:
    racine = dossier_racine.resolve()
    cible = (racine / chemin_relatif).resolve()
    if not cible.is_relative_to(racine):
        raise ValueError("Chemin de stockage hors du dossier autorisé.")
    return cible


def dechiffrer_document_meta(
    doc: DocumentCandidat, cle_maitresse: bytes
) -> DocumentSortie:
    nom_origine = (
        dechiffrer_champ(
            cle_maitresse,
            doc.tenant_id,
            "nom_fichier_origine",
            doc.nom_fichier_origine_chiffre,
        )
        or "document"
    )
    return DocumentSortie(
        id=doc.id,
        candidat_id=doc.candidat_id,
        type_piece=doc.type_piece,
        nom_fichier_origine=nom_origine,
        type_mime=doc.type_mime,
        taille_octets=doc.taille_octets,
        empreinte_contenu=doc.empreinte_contenu,
        date_expiration=doc.date_expiration,
        ajoute_par_id=doc.ajoute_par_id,
        cree_le=doc.cree_le,
    )


def deposer_document(
    db: Session,
    *,
    candidat_id: uuid.UUID,
    type_piece: str,
    nom_fichier_origine: str,
    contenu_clair: bytes,
    date_expiration: date | None,
    acteur_id: uuid.UUID | None,
    parametres: Parametres,
    cle_maitresse: bytes,
) -> DocumentSortie:
    tid = tenant_courant(db)
    if tid is None:
        raise RuntimeError("Contexte bureau (tenant) manquant sur la session.")

    # Vérifie que le candidat existe et appartient bien au bureau courant (filtré par l'ORM).
    candidat = obtenir_candidat_orm(db, candidat_id)

    type_propre = verifier_type_piece_autorise(parametres.dossier_demarches, type_piece)

    if not contenu_clair:
        raise DonneesInvalides("Le fichier déposé est vide.")
    if len(contenu_clair) > parametres.taille_max_document_octets:
        raise DonneesInvalides(
            f"Le fichier dépasse la taille maximale autorisée ({parametres.taille_max_document_octets} octets)."
        )

    type_mime = _detecter_type_mime_par_signature(contenu_clair)
    nom_propre = _normaliser_nom_fichier(nom_fichier_origine)
    empreinte = calculer_empreinte_document(cle_maitresse, tid, contenu_clair)

    doublon = db.scalar(
        select(DocumentCandidat.id).where(
            DocumentCandidat.candidat_id == candidat.id,
            DocumentCandidat.empreinte_contenu == empreinte,
        )
    )
    if doublon is not None:
        raise Conflit(
            "Ce fichier est déjà présent dans le dossier de ce candidat (doublon détecté par empreinte)."
        )

    doc_id = uuid.uuid4()
    chemin_relatif = f"{tid}/{candidat.id}/{doc_id}.bin"
    chemin_disque = _resoudre_chemin_stockage(
        parametres.dossier_stockage, chemin_relatif
    )

    octets_chiffres = chiffrer_octets(
        cle_maitresse,
        tenant_id=tid,
        candidat_id=candidat.id,
        document_id=doc_id,
        contenu_clair=contenu_clair,
    )

    doc = DocumentCandidat(
        id=doc_id,
        tenant_id=tid,
        candidat_id=candidat.id,
        type_piece=type_propre,
        nom_fichier_origine_chiffre=chiffrer_champ(
            cle_maitresse, tid, "nom_fichier_origine", nom_propre
        )
        or "",
        type_mime=type_mime,
        taille_octets=len(contenu_clair),
        empreinte_contenu=empreinte,
        chemin_stockage_relatif=chemin_relatif,
        date_expiration=date_expiration,
        ajoute_par_id=acteur_id,
    )
    db.add(doc)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise Conflit(
            "Ce fichier est déjà présent dans le dossier de ce candidat (doublon détecté par empreinte)."
        ) from exc

    chemin_disque.parent.mkdir(parents=True, exist_ok=True)
    chemin_disque.write_bytes(octets_chiffres)

    audit.journaliser(
        db,
        "document.depot",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="document",
        ressource_id=doc.id,
        details={
            "candidat_id": str(candidat.id),
            "type_piece": type_propre,
            "taille_octets": len(contenu_clair),
        },
    )
    db.commit()
    return dechiffrer_document_meta(doc, cle_maitresse)


def lister_documents_candidat(
    db: Session, *, candidat_id: uuid.UUID, cle_maitresse: bytes
) -> list[DocumentSortie]:
    obtenir_candidat_orm(db, candidat_id)
    docs = db.scalars(
        select(DocumentCandidat)
        .where(DocumentCandidat.candidat_id == candidat_id)
        .order_by(DocumentCandidat.cree_le.desc(), DocumentCandidat.id)
    ).all()
    return [dechiffrer_document_meta(d, cle_maitresse) for d in docs]


def lister_documents_orm(
    db: Session, *, candidat_id: uuid.UUID
) -> list[DocumentCandidat]:
    obtenir_candidat_orm(db, candidat_id)
    return list(
        db.scalars(
            select(DocumentCandidat)
            .where(DocumentCandidat.candidat_id == candidat_id)
            .order_by(DocumentCandidat.cree_le.asc(), DocumentCandidat.id)
        ).all()
    )


def lire_document_dechiffre(
    db: Session,
    *,
    candidat_id: uuid.UUID,
    document_id: uuid.UUID,
    parametres: Parametres,
    cle_maitresse: bytes,
) -> tuple[DocumentSortie, bytes]:
    doc = db.scalar(
        select(DocumentCandidat).where(
            DocumentCandidat.id == document_id,
            DocumentCandidat.candidat_id == candidat_id,
        )
    )
    if doc is None:
        raise NonTrouve("Document introuvable.")

    chemin_disque = _resoudre_chemin_stockage(
        parametres.dossier_stockage, doc.chemin_stockage_relatif
    )
    if not chemin_disque.exists():
        raise NonTrouve("Fichier chiffré introuvable sur le stockage.")

    clair = dechiffrer_octets(
        cle_maitresse,
        tenant_id=doc.tenant_id,
        candidat_id=doc.candidat_id,
        document_id=doc.id,
        contenu_chiffre=chemin_disque.read_bytes(),
    )
    return dechiffrer_document_meta(doc, cle_maitresse), clair


def supprimer_document(
    db: Session,
    *,
    candidat_id: uuid.UUID,
    document_id: uuid.UUID,
    acteur_id: uuid.UUID,
    parametres: Parametres,
) -> None:
    doc = db.scalar(
        select(DocumentCandidat).where(
            DocumentCandidat.id == document_id,
            DocumentCandidat.candidat_id == candidat_id,
        )
    )
    if doc is None:
        raise NonTrouve("Document introuvable.")

    chemin_disque = _resoudre_chemin_stockage(
        parametres.dossier_stockage, doc.chemin_stockage_relatif
    )
    type_piece = doc.type_piece
    db.delete(doc)
    audit.journaliser(
        db,
        "document.suppression",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="document",
        ressource_id=document_id,
        details={"candidat_id": str(candidat_id), "type_piece": type_piece},
    )
    db.commit()
    if chemin_disque.exists():
        chemin_disque.unlink()
