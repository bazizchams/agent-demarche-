"""Classification d'une pièce par son CONTENU : une PROPOSITION, jamais une décision.

Cohérence avec la garde D3 de `import_dossier` : le type d'une pièce n'est jamais deviné puis
appliqué en silence. Ce module ne modifie rien ; tant que la confiance est inférieure à
`SEUIL_CONFIRMATION`, `confirmation_humaine_requise` est vrai et l'appelant ne doit appliquer
aucun type sans confirmation explicite d'un humain.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from app.services.extraction_champs import (
    FAMILLE_CERTIFICAT,
    FAMILLE_PASSEPORT,
    FAMILLE_RELEVE,
    TYPES_CERTIFICAT,
    analyser_mrz,
)

SEUIL_CONFIRMATION = 0.9
_ECART_AMBIGUITE = 20
_PENALITE_AMBIGUITE = 30
_CHAMPS_MRZ_A_CONTROLE = frozenset(
    {"numero_passeport", "date_naissance", "date_expiration_passeport", "sexe"}
)


@dataclass(frozen=True)
class ClassificationPiece:
    famille: str | None
    type_piece_propose: str | None
    confiance: float
    indices: tuple[str, ...]
    confirmation_humaine_requise: bool


def _bas(texte: str) -> str:
    sans = "".join(c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c))
    return sans.lower()


def _score_passeport(texte: str, bas: str) -> tuple[int, list[str]]:
    mrz = analyser_mrz(texte)
    if mrz:
        controles = [c for c in mrz if c.champ in _CHAMPS_MRZ_A_CONTROLE]
        if controles and all(c.valide and c.controle_fort for c in controles):
            return 98, ["mrz_valide"]
        return 70, ["mrz_presente_controle_invalide"]
    if re.search(r"passeport|passport", bas):
        return 55, ["mot_cle_passeport"]
    return 0, []


def _score_releve(bas: str) -> tuple[int, list[str]]:
    if not re.search(r"releve de notes|bulletin", bas):
        return 0, []
    score, indices = 50, ["releve_de_notes"]
    if "moyenne" in bas:
        score += 20
        indices.append("moyenne")
    if re.search(r"baccalaureat|licence|master|semestre", bas):
        score += 20
        indices.append("cursus")
    return score, indices


def _score_certificat(texte: str, bas: str) -> tuple[int, list[str]]:
    if not any(re.search(rf"\b{t}\b", texte, re.IGNORECASE) for t in TYPES_CERTIFICAT):
        return 0, []
    score, indices = 55, ["type_de_test"]
    if re.search(r"attestation|certificat|resultats|test report|score|diplome", bas):
        score += 20
        indices.append("intitule_certificat")
    if re.search(r"niveau|band|cecrl|cefr", bas):
        score += 15
        indices.append("niveau")
    return score, indices


def deviner_type_piece(pages: Sequence[tuple[int, str]]) -> ClassificationPiece:
    """Famille et type de pièce PROPOSÉS d'après le texte lu ; confiance en [0, 1]."""
    texte = "\n".join(t for _, t in pages)
    bas = _bas(texte)
    candidats: dict[str, tuple[int, list[str]]] = {}
    for famille, (score, indices) in (
        (FAMILLE_PASSEPORT, _score_passeport(texte, bas)),
        (FAMILLE_RELEVE, _score_releve(bas)),
        (FAMILLE_CERTIFICAT, _score_certificat(texte, bas)),
    ):
        if score > 0:
            candidats[famille] = (score, indices)
    if not candidats:
        return ClassificationPiece(None, None, 0.0, (), True)
    classes = sorted(candidats.items(), key=lambda kv: kv[1][0], reverse=True)
    famille, (score, indices) = classes[0]
    if len(classes) > 1 and classes[1][1][0] >= score - _ECART_AMBIGUITE:
        score -= _PENALITE_AMBIGUITE
        indices = [*indices, "famille_concurrente"]
    if famille == FAMILLE_PASSEPORT:
        type_piece = "passeport"
    elif famille == FAMILLE_CERTIFICAT:
        type_piece = "resultats_test_langue"
    else:
        type_piece = "releve_notes_bac" if "baccalaureat" in bas else "releves_notes_superieur"
    confiance = score / 100
    return ClassificationPiece(
        famille=famille,
        type_piece_propose=type_piece,
        confiance=confiance,
        indices=tuple(indices),
        confirmation_humaine_requise=confiance < SEUIL_CONFIRMATION,
    )
