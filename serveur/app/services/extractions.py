"""Lecture des documents d'un candidat : extraction, persistance chiffrée, revue humaine.

Règles tenues ici :
- règle 4 : un champ non lu n'a pas de ligne ; une valeur douteuse reste `a_verifier` (jamais
  appliquée sans validation humaine) ; une valeur non ancrée dans le document est `rejete` ;
- règle 5 : valeurs, valeurs alternatives et extraits sont chiffrés en base ; l'audit et les
  messages d'erreur ne contiennent que des identifiants et des codes ;
- garde D3 : la lecture ne modifie JAMAIS le `type_piece` d'un document ; la classification par
  contenu n'est qu'une proposition et un type de confiance basse impose une confirmation humaine ;
- une décision humaine (valider, rejeter, corriger) ou une valeur déjà appliquée à la fiche n'est
  jamais écrasée par une relecture.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.chiffrement import chiffrer_champ, dechiffrer_champ
from app.core.config import Parametres
from app.core.erreurs import DonneesInvalides, NonTrouve, ServiceIndisponible
from app.db.base import maintenant_utc
from app.db.tenant import tenant_courant
from app.modeles.document import DocumentCandidat
from app.modeles.extraction_document import ExtractionDocument, StatutExtraction
from app.modeles.journal_audit import ResultatAudit
from app.schemas.extraction import (
    AlerteSortie,
    ClassificationSortie,
    ErreurDocumentSortie,
    ExtractionSortie,
    ResultatExtractionDocumentSortie,
    ResultatLotSortie,
)
from app.services import audit
from app.services.candidats import obtenir_candidat, obtenir_candidat_orm
from app.services.classification_pieces import ClassificationPiece, deviner_type_piece
from app.services.documents import lire_document_dechiffre, lister_documents_orm
from app.services.extraction_champs import (
    ChampLu,
    extraire_champs,
    famille_pour_type_piece,
    normaliser_valeur,
    valeur_valide,
)
from app.services.fusion_extractions import (
    AlerteControle,
    ChampFusionne,
    ValeurExtraite,
    controles_croises,
    fusionner_lectures,
)
from app.services.lecture_documents import LecteurDocument, ResultatLecture
from app.services.lecture_vision import LecteurVision
from app.services.pieces_requises import obtenir_demarche, verifier_completude_dossier

MOTIF_DISCORDANCE_INTER_PIECES = "discordance_inter_pieces"
_CODES_DISCORDANCE = frozenset({"nom_discordant", "prenom_discordant", "date_naissance_discordante"})
_AAD_VALEUR, _AAD_ALTERNATIVE, _AAD_EXTRAIT = "extraction_valeur", "extraction_valeur_alternative", "extraction_extrait"


def _exiger_tenant(db: Session) -> uuid.UUID:
    tid = tenant_courant(db)
    if tid is None:
        raise RuntimeError("Contexte bureau (tenant) manquant sur la session.")
    return tid


def vers_sortie(e: ExtractionDocument, cle_maitresse: bytes) -> ExtractionSortie:
    tid = e.tenant_id
    return ExtractionSortie(
        id=e.id,
        document_id=e.document_id,
        candidat_id=e.candidat_id,
        champ=e.champ,
        valeur=dechiffrer_champ(cle_maitresse, tid, _AAD_VALEUR, e.valeur_chiffree) or "",
        valeur_alternative=dechiffrer_champ(cle_maitresse, tid, _AAD_ALTERNATIVE, e.valeur_alternative_chiffree),
        page=e.page,
        extrait=dechiffrer_champ(cle_maitresse, tid, _AAD_EXTRAIT, e.extrait_chiffre) or "",
        source=e.source,
        confiance=e.confiance,
        statut=e.statut,
        motif=e.motif,
        decide_par_id=e.decide_par_id,
        decide_le=e.decide_le,
        applique_le=e.applique_le,
        cree_le=e.cree_le,
        modifie_le=e.modifie_le,
    )


def _est_verrouillee(e: ExtractionDocument) -> bool:
    """Décision humaine ou valeur déjà appliquée à la fiche : une relecture n'y touche pas."""
    return e.decide_par_id is not None or e.applique_le is not None


def _renseigner(e: ExtractionDocument, f: ChampFusionne, tid: uuid.UUID, cle: bytes) -> None:
    e.valeur_chiffree = chiffrer_champ(cle, tid, _AAD_VALEUR, f.valeur) or ""
    e.valeur_alternative_chiffree = chiffrer_champ(cle, tid, _AAD_ALTERNATIVE, f.valeur_alternative)
    e.extrait_chiffre = chiffrer_champ(cle, tid, _AAD_EXTRAIT, f.extrait) or ""
    e.page = f.page
    e.source = f.source
    e.confiance = max(0.0, min(1.0, f.confiance))
    e.statut = f.statut
    e.motif = f.motif


def _persister(
    db: Session, doc: DocumentCandidat, fusionnes: list[ChampFusionne], tid: uuid.UUID, cle: bytes
) -> None:
    existantes = {
        e.champ: e for e in db.scalars(select(ExtractionDocument).where(ExtractionDocument.document_id == doc.id))
    }
    produits: set[str] = set()
    for f in fusionnes:
        produits.add(f.champ)
        courante = existantes.get(f.champ)
        if courante is not None and _est_verrouillee(courante):
            continue
        if courante is None:
            courante = ExtractionDocument(
                id=uuid.uuid4(), tenant_id=tid, document_id=doc.id, candidat_id=doc.candidat_id, champ=f.champ
            )
            _renseigner(courante, f, tid, cle)
            db.add(courante)
        else:
            _renseigner(courante, f, tid, cle)
    for champ, e in existantes.items():
        if champ not in produits and not _est_verrouillee(e):
            db.delete(e)  # valeur périmée : le document relu ne la porte plus
    db.flush()


def _recalculer_controles(
    db: Session, candidat_id: uuid.UUID, cle: bytes, date_reference: date
) -> list[AlerteControle]:
    """Contrôles croisés sur tout le dossier ; une discordance dégrade les valeurs `auto`
    concernées en `a_verifier` (sauf décision humaine ou valeur déjà appliquée)."""
    lignes = list(
        db.scalars(
            select(ExtractionDocument).where(
                ExtractionDocument.candidat_id == candidat_id,
                ExtractionDocument.statut != StatutExtraction.REJETE,
            )
        )
    )
    types = dict(db.execute(select(DocumentCandidat.id, DocumentCandidat.type_piece)).all())
    valeurs = [
        ValeurExtraite(
            extraction_id=e.id,
            document_id=str(e.document_id),
            type_piece=types.get(e.document_id, ""),
            champ=e.champ,
            valeur=dechiffrer_champ(cle, e.tenant_id, _AAD_VALEUR, e.valeur_chiffree) or "",
        )
        for e in lignes
    ]
    alertes = controles_croises(valeurs, date_reference=date_reference)
    par_id = {e.id: e for e in lignes}
    for alerte in alertes:
        if alerte.code not in _CODES_DISCORDANCE:
            continue
        for eid in alerte.extraction_ids:
            e = par_id.get(eid)  # type: ignore[arg-type]
            if e is None or _est_verrouillee(e):
                continue
            if e.statut is StatutExtraction.AUTO:
                e.statut = StatutExtraction.A_VERIFIER
            e.motif = MOTIF_DISCORDANCE_INTER_PIECES
    db.flush()
    return alertes


def _alerte_sortie(a: AlerteControle) -> AlerteSortie:
    return AlerteSortie(
        code=a.code,
        champ=a.champ,
        document_ids=list(a.document_ids),
        extraction_ids=[str(i) for i in a.extraction_ids],
        message=a.message,
    )


def _choisir_famille(
    type_piece: str, classification: ClassificationPiece, avertissements: list[str]
) -> str | None:
    declaree = famille_pour_type_piece(type_piece)
    fiable = classification.famille is not None and not classification.confirmation_humaine_requise
    if declaree is not None:
        if fiable and classification.famille != declaree:
            avertissements.append(
                "Le type de pièce déclaré semble incohérent avec le contenu lu : à vérifier "
                "(le type du document n'a pas été modifié)."
            )
        return declaree
    if fiable:
        avertissements.append(
            "Type de pièce déclaré non géré ; lecture faite selon le contenu reconnu "
            "(le type du document n'a pas été modifié)."
        )
        return classification.famille
    avertissements.append(
        "Type de pièce non reconnu avec une confiance suffisante : confirmation humaine requise "
        "avant toute lecture structurée."
    )
    return None


def _lecture_b(
    lecteur_document: LecteurDocument,
    lecteur_vision: LecteurVision | None,
    contenu: bytes,
    type_mime: str,
    famille: str | None,
    avertissements: list[str],
) -> list[ChampLu] | None:
    if lecteur_vision is None or famille is None:
        return None
    images = lecteur_document.extraire_images(contenu, type_mime)
    if not images:
        avertissements.append("Lecteur B : aucune image à lire dans ce document (PDF numérique).")
        return None
    try:
        return lecteur_vision.lire_champs(images, famille=famille)
    except ServiceIndisponible:
        avertissements.append("Lecteur B indisponible : lecture A seule, tout reste à vérifier.")
        return None


def lancer_extraction_document(
    db: Session,
    *,
    candidat_id: uuid.UUID,
    document_id: uuid.UUID,
    acteur_id: uuid.UUID,
    parametres: Parametres,
    cle_maitresse: bytes,
    lecteur_document: LecteurDocument,
    lecteur_vision: LecteurVision | None = None,
    date_reference: date | None = None,
) -> ResultatExtractionDocumentSortie:
    tid = _exiger_tenant(db)
    obtenir_candidat_orm(db, candidat_id)
    meta, contenu = lire_document_dechiffre(
        db, candidat_id=candidat_id, document_id=document_id, parametres=parametres, cle_maitresse=cle_maitresse
    )
    doc = db.scalar(select(DocumentCandidat).where(DocumentCandidat.id == document_id))
    if doc is None:
        raise NonTrouve("Document introuvable.")

    lecture: ResultatLecture = lecteur_document.lire_texte(contenu, meta.type_mime)
    pages = [(p.numero, p.texte) for p in lecture.pages]
    textes = dict(pages)
    avertissements = list(lecture.avertissements)
    classification = deviner_type_piece(pages)
    famille = _choisir_famille(meta.type_piece, classification, avertissements)

    lecture_a = extraire_champs(famille, pages) if famille else []
    lecture_b = _lecture_b(lecteur_document, lecteur_vision, contenu, meta.type_mime, famille, avertissements)
    fusionnes = fusionner_lectures(lecture_a, lecture_b, textes)

    _persister(db, doc, fusionnes, tid, cle_maitresse)
    alertes = _recalculer_controles(db, candidat_id, cle_maitresse, date_reference or date.today())
    audit.journaliser(
        db,
        "extraction.lancer",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="document",
        ressource_id=document_id,
        details={
            "candidat_id": str(candidat_id),
            "famille": famille or "inconnue",
            "nb_champs": len(fusionnes),
            "nb_auto": sum(f.statut is StatutExtraction.AUTO for f in fusionnes),
            "nb_a_verifier": sum(f.statut is StatutExtraction.A_VERIFIER for f in fusionnes),
            "nb_rejetes": sum(f.statut is StatutExtraction.REJETE for f in fusionnes),
            "lecteur_b": lecture_b is not None,
        },
    )
    db.commit()

    lignes = db.scalars(
        select(ExtractionDocument).where(ExtractionDocument.document_id == document_id).order_by(ExtractionDocument.champ)
    ).all()
    return ResultatExtractionDocumentSortie(
        document_id=document_id,
        type_piece=meta.type_piece,
        classification=ClassificationSortie(
            famille=classification.famille,
            type_piece_propose=classification.type_piece_propose,
            confiance=classification.confiance,
            indices=list(classification.indices),
            confirmation_humaine_requise=classification.confirmation_humaine_requise,
        ),
        lecteur_b_utilise=lecture_b is not None,
        extractions=[vers_sortie(e, cle_maitresse) for e in lignes],
        alertes=[_alerte_sortie(a) for a in alertes],
        avertissements=avertissements,
    )


def lancer_extraction_lot(
    db: Session,
    *,
    candidat_id: uuid.UUID,
    code_demarche: str | None,
    acteur_id: uuid.UUID,
    parametres: Parametres,
    cle_maitresse: bytes,
    lecteur_document: LecteurDocument,
    lecteur_vision: LecteurVision | None = None,
    date_reference: date | None = None,
) -> ResultatLotSortie:
    """Lit tous les documents du dossier. Porte d'entrée : si une démarche est indiquée, la liste
    des pièces manquantes ou invalides est établie AVANT le traitement et renvoyée."""
    fiche = obtenir_candidat(db, candidat_id=candidat_id, cle_maitresse=cle_maitresse)
    documents = lister_documents_orm(db, candidat_id=candidat_id)
    completude = None
    if code_demarche:
        demarche = obtenir_demarche(parametres.dossier_demarches, code_demarche, db)
        completude = verifier_completude_dossier(
            candidat=fiche, documents=documents, demarche=demarche, date_reference=date_reference
        )
    ids = [d.id for d in documents]
    resultats: list[ResultatExtractionDocumentSortie] = []
    erreurs: list[ErreurDocumentSortie] = []
    for document_id in ids:
        try:
            resultats.append(
                lancer_extraction_document(
                    db,
                    candidat_id=candidat_id,
                    document_id=document_id,
                    acteur_id=acteur_id,
                    parametres=parametres,
                    cle_maitresse=cle_maitresse,
                    lecteur_document=lecteur_document,
                    lecteur_vision=lecteur_vision,
                    date_reference=date_reference,
                )
            )
        except DonneesInvalides as exc:  # un fichier illisible n'arrête pas le lot
            erreurs.append(ErreurDocumentSortie(document_id=document_id, detail=exc.message))
    alertes = resultats[-1].alertes if resultats else []
    return ResultatLotSortie(
        completude=completude,
        dossier_complet=completude.pret_pour_prerequis if completude else None,
        documents=resultats,
        erreurs=erreurs,
        alertes=alertes,
    )


def lister_extractions(
    db: Session,
    *,
    candidat_id: uuid.UUID,
    cle_maitresse: bytes,
    document_id: uuid.UUID | None = None,
    statut: StatutExtraction | None = None,
) -> list[ExtractionSortie]:
    obtenir_candidat_orm(db, candidat_id)
    requete = select(ExtractionDocument).where(ExtractionDocument.candidat_id == candidat_id)
    if document_id is not None:
        requete = requete.where(ExtractionDocument.document_id == document_id)
    if statut is not None:
        requete = requete.where(ExtractionDocument.statut == statut)
    lignes = db.scalars(requete.order_by(ExtractionDocument.cree_le, ExtractionDocument.champ)).all()
    return [vers_sortie(e, cle_maitresse) for e in lignes]


# ================================================================== revue humaine


def _obtenir_extraction(db: Session, candidat_id: uuid.UUID, extraction_id: uuid.UUID) -> ExtractionDocument:
    obtenir_candidat_orm(db, candidat_id)
    e = db.scalar(
        select(ExtractionDocument).where(
            ExtractionDocument.id == extraction_id, ExtractionDocument.candidat_id == candidat_id
        )
    )
    if e is None:
        raise NonTrouve("Extraction introuvable.")
    return e


def decider_extraction(
    db: Session,
    *,
    candidat_id: uuid.UUID,
    extraction_id: uuid.UUID,
    action: str,
    valeur_corrigee: str | None,
    acteur_id: uuid.UUID,
    cle_maitresse: bytes,
) -> ExtractionSortie:
    """Décision d'un humain authentifié : `valider`, `rejeter` ou `corriger`."""
    e = _obtenir_extraction(db, candidat_id, extraction_id)
    tid = e.tenant_id
    if action == "valider":
        courante = dechiffrer_champ(cle_maitresse, tid, _AAD_VALEUR, e.valeur_chiffree) or ""
        if not valeur_valide(e.champ, normaliser_valeur(e.champ, courante)):
            raise DonneesInvalides(
                "La valeur lue n'est pas valide pour ce champ : corrigez-la avant de la confirmer."
            )
        e.statut, e.motif = StatutExtraction.VALIDE_HUMAIN, None
    elif action == "rejeter":
        e.statut, e.motif = StatutExtraction.REJETE, "rejete_humain"
    elif action == "corriger":
        nouvelle = normaliser_valeur(e.champ, valeur_corrigee or "")
        if not valeur_valide(e.champ, nouvelle):
            raise DonneesInvalides("La valeur saisie n'est pas valide pour ce champ.")
        e.valeur_chiffree = chiffrer_champ(cle_maitresse, tid, _AAD_VALEUR, nouvelle) or ""
        e.statut, e.motif = StatutExtraction.VALIDE_HUMAIN, "corrige_humain"
        e.applique_le = None
    else:  # pragma: no cover - les routes n'appellent que les trois actions
        raise DonneesInvalides("Action inconnue.")
    e.decide_par_id, e.decide_le = acteur_id, maintenant_utc()
    audit.journaliser(
        db,
        f"extraction.{action}",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="extraction",
        ressource_id=e.id,
        details={"candidat_id": str(candidat_id), "champ": e.champ},
    )
    db.commit()
    return vers_sortie(e, cle_maitresse)
