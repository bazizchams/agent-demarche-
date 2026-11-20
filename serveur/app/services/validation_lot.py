"""Validation en lot des valeurs lues FIABLES, puis remplissage de la fiche (un seul clic humain).

Garanties (règles 1, 4 et 5) :
- le lot est une décision humaine : il n'existe que par un appel authentifié (rôle, CSRF) ;
- une valeur est FIABLE seulement si : (a) lecture automatique `auto` (chiffres de contrôle de la zone
  lisible par machine, ou concordance des deux lectures A/B ancrées dans le document), ou (b) la même
  valeur est lue sur au moins deux pièces différentes sans qu'aucune autre pièce ne la contredise ;
  et si la valeur est valide pour son champ. Tout le reste est DOUTEUX : jamais inclus, confirmation
  individuelle obligatoire ;
- aucune valeur n'est jamais écrasée sur la fiche (conflit signalé) ; un champ illisible reste vide et
  est listé « à compléter » ;
- l'audit ne contient que des compteurs (aucune valeur, aucun nom).
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.chiffrement import dechiffrer_champ
from app.db.base import maintenant_utc
from app.modeles.extraction_document import ExtractionDocument, StatutExtraction
from app.modeles.journal_audit import ResultatAudit
from app.schemas.extraction import FiabiliteSortie, ResultatValidationLotSortie, SyntheseRevueSortie
from app.services import audit
from app.services.application_extractions import (
    CHAMPS_FICHE,
    _convertir,
    _identiques,
    _vide,
    appliquer_extractions_a_fiche,
    attribut_fiche,
)
from app.services.candidats import obtenir_candidat, obtenir_candidat_orm
from app.services.extraction_champs import (
    ANNEE_UNIVERSITAIRE,
    CERTIFICAT_DATE,
    DIPLOME_ETABLISSEMENT,
    MENTION,
    MOYENNE_GENERALE,
    NATIONALITE_CODE,
    NOM,
    NUMERO_PASSEPORT,
    PRENOM,
    SEXE,
    normaliser_valeur,
    valeur_valide,
)
from app.services.extractions import _AAD_EXTRAIT, _AAD_VALEUR

MOTIF_LOT = "confirme_en_lot"
RAISON_MRZ = "mrz_valide"
RAISON_DOUBLE_LECTURE = "double_lecture_concordante"
RAISON_DEUX_PIECES = "concordance_deux_pieces"
# Lus dans la zone lisible par machine : fiables quand TOUS ses chiffres de contrôle sont bons (le numéro
# du même passeport est alors `auto` « controle_icao »). Nom et prénom n'ont pas de chiffre propre.
_CHAMPS_MRZ_SANS_CLE = frozenset({NOM, PRENOM, SEXE, NATIONALITE_CODE})
SEUIL_MRZ_COMPLETE = 0.8
_MOTIFS_LECTURE_UNIQUE = frozenset({"double_lecture_absente", "lecteur_b_sans_valeur"})
# Champs utiles que les pièces doivent permettre de lire en plus de la fiche (sinon « à compléter »).
_CHAMPS_PIECES_UTILES = (DIPLOME_ETABLISSEMENT, ANNEE_UNIVERSITAIRE, MOYENNE_GENERALE, MENTION, CERTIFICAT_DATE)
NIVEAU_FIABLE, NIVEAU_DOUTEUSE = "fiable", "douteuse"


@dataclass(frozen=True)
class _Ligne:
    e: ExtractionDocument
    valeur: str  # forme canonique
    extrait: str = ""  # texte littéral lu sur la pièce (zone visuelle pour un passeport)


def _lignes(db: Session, candidat_id: uuid.UUID, cle: bytes) -> list[_Ligne]:
    rows = db.scalars(
        select(ExtractionDocument).where(
            ExtractionDocument.candidat_id == candidat_id, ExtractionDocument.statut != StatutExtraction.REJETE
        )
    )
    return [
        _Ligne(
            e,
            normaliser_valeur(e.champ, dechiffrer_champ(cle, e.tenant_id, _AAD_VALEUR, e.valeur_chiffree) or ""),
            dechiffrer_champ(cle, e.tenant_id, _AAD_EXTRAIT, e.extrait_chiffre) or "",
        )
        for e in rows
    ]


def _sans_accents_majuscules(texte: str) -> str:
    decompose = unicodedata.normalize("NFKD", texte or "")
    return "".join(c for c in decompose if not unicodedata.combining(c)).upper()


def _nom_confirme_par_zone_visuelle(ligne: _Ligne) -> bool:
    """Nom/prénom de la MRZ (sans chiffre de contrôle) : fiable seulement s'il figure tel quel, comme
    mot entier, dans le texte lisible de la pièce. Sinon une erreur d'OCR (BENAII pour BENALI) passerait
    en lot sans que personne ne la voie."""
    if ligne.e.champ not in (NOM, PRENOM):
        return True
    valeur = _sans_accents_majuscules(ligne.valeur).strip()
    if not valeur:
        return False
    # Les lignes de la MRZ elle-même (« P<DZABENALI<<AMINA… ») ne confirment rien : seule compte la zone visuelle.
    zone_visuelle = "\n".join(l for l in (ligne.extrait or "").splitlines() if "<<" not in l)
    mots = re.findall(r"[A-Z]+", _sans_accents_majuscules(zone_visuelle))
    return all(m in mots for m in re.findall(r"[A-Z]+", valeur))


def _en_attente(ligne: _Ligne) -> bool:
    return ligne.e.statut is not StatutExtraction.VALIDE_HUMAIN and ligne.e.applique_le is None


def _evaluer(ligne: _Ligne, toutes: list[_Ligne]) -> tuple[str, str]:
    e = ligne.e
    if not valeur_valide(e.champ, ligne.valeur):
        return NIVEAU_DOUTEUSE, e.motif or "valeur_invalide"
    memes_champ = [x for x in toutes if x.e.champ == e.champ]
    if any(x.valeur != ligne.valeur for x in memes_champ if x.e.document_id != e.document_id):
        return NIVEAU_DOUTEUSE, "valeurs_differentes_entre_pieces"
    if e.statut is StatutExtraction.AUTO:
        return NIVEAU_FIABLE, RAISON_MRZ if e.motif == "controle_icao" else RAISON_DOUBLE_LECTURE
    if (
        e.statut is StatutExtraction.A_VERIFIER
        and e.champ in _CHAMPS_MRZ_SANS_CLE
        and e.confiance >= SEUIL_MRZ_COMPLETE
        and any(
            x.e.document_id == e.document_id and x.e.champ == NUMERO_PASSEPORT and x.e.motif == "controle_icao"
            and x.e.statut is StatutExtraction.AUTO
            for x in toutes
        )
    ):
        if not _nom_confirme_par_zone_visuelle(ligne):
            return NIVEAU_DOUTEUSE, "nom_different_de_la_zone_visuelle"
        return NIVEAU_FIABLE, RAISON_MRZ
    if e.statut is StatutExtraction.A_VERIFIER and (e.motif in _MOTIFS_LECTURE_UNIQUE or e.motif is None):
        autres = {x.e.document_id for x in memes_champ if x.valeur == ligne.valeur and x.e.document_id != e.document_id}
        if autres:
            return NIVEAU_FIABLE, RAISON_DEUX_PIECES
    return NIVEAU_DOUTEUSE, e.motif or "lecture_incertaine"


def _conflit_fiche(fiche, ligne: _Ligne) -> bool:
    if ligne.e.champ not in CHAMPS_FICHE:
        return False
    try:
        proposee = _convertir(ligne.e.champ, ligne.valeur)
    except ValueError:
        return True
    actuelle = getattr(fiche, attribut_fiche(ligne.e.champ))
    return not _vide(actuelle) and not _identiques(ligne.e.champ, actuelle, proposee)


def _a_completer(fiche, toutes: list[_Ligne]) -> list[str]:
    lus = {x.e.champ for x in toutes}
    manquants = [c for c in CHAMPS_FICHE if _vide(getattr(fiche, attribut_fiche(c))) and c not in lus]
    return manquants + [c for c in _CHAMPS_PIECES_UTILES if c not in lus]


def synthese_revue(db: Session, *, candidat_id: uuid.UUID, cle_maitresse: bytes) -> SyntheseRevueSortie:
    obtenir_candidat_orm(db, candidat_id)
    fiche = obtenir_candidat(db, candidat_id=candidat_id, cle_maitresse=cle_maitresse)
    toutes = _lignes(db, candidat_id, cle_maitresse)
    items: list[FiabiliteSortie] = []
    for ligne in toutes:
        if not _en_attente(ligne):
            continue
        niveau, raison = _evaluer(ligne, toutes)
        items.append(
            FiabiliteSortie(
                extraction_id=ligne.e.id, niveau=niveau, raison=raison, conflit_fiche=_conflit_fiche(fiche, ligne)
            )
        )
    return SyntheseRevueSortie(
        nb_fiables=sum(i.niveau == NIVEAU_FIABLE for i in items),
        nb_douteuses=sum(i.niveau == NIVEAU_DOUTEUSE for i in items),
        nb_deja_confirmees=sum(x.e.statut is StatutExtraction.VALIDE_HUMAIN for x in toutes),
        items=items,
        a_completer=_a_completer(fiche, toutes),
    )


def valider_lot_et_remplir_fiche(
    db: Session,
    *,
    candidat_id: uuid.UUID,
    acteur_id: uuid.UUID,
    cle_maitresse: bytes,
    extraction_ids: list[uuid.UUID] | None = None,
) -> ResultatValidationLotSortie:
    obtenir_candidat_orm(db, candidat_id)
    toutes = _lignes(db, candidat_id, cle_maitresse)
    demandes = set(extraction_ids) if extraction_ids is not None else None
    valides = ignores = douteuses = 0
    maintenant = maintenant_utc()
    decisions = [(ligne, _evaluer(ligne, toutes)[0] == NIVEAU_FIABLE) for ligne in toutes if _en_attente(ligne)]
    for ligne, fiable in decisions:  # évaluation complète AVANT toute modification (les lignes sont liées)
        if demandes is not None and ligne.e.id not in demandes:
            douteuses += not fiable
        elif not fiable:
            douteuses += 1
            ignores += demandes is not None
        else:
            ligne.e.statut, ligne.e.motif = StatutExtraction.VALIDE_HUMAIN, MOTIF_LOT
            ligne.e.decide_par_id, ligne.e.decide_le = acteur_id, maintenant
            valides += 1
    if demandes is not None:
        ignores += len(demandes - {x.e.id for x in toutes})
    audit.journaliser(
        db,
        "extraction.valider_lot",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="candidat",
        ressource_id=candidat_id,
        details={"nb_valides": valides, "nb_ignores": ignores, "nb_douteuses_restantes": douteuses},
    )
    db.commit()  # la décision est durable avant le report : un refus d'écriture ne l'annule pas
    rapport = appliquer_extractions_a_fiche(
        db, candidat_id=candidat_id, acteur_id=acteur_id, cle_maitresse=cle_maitresse
    )
    return ResultatValidationLotSortie(
        nb_valides=valides, nb_ignores=ignores, nb_douteuses_restantes=douteuses, rapport=rapport
    )
