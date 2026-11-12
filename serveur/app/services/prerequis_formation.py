"""Analyse du champ « prérequis » d'une formation du catalogue Études en France.

Service pur : aucune base, aucun réseau, aucune écriture.
Extrait le niveau de français et d'anglais exigé (CECRL) et le compare au niveau du candidat.
Règle : aucune valeur inventée ; en cas de doute, None.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

NIVEAUX_CECRL = ("A1", "A2", "B1", "B2", "C1", "C2")

_RE_BALISE = re.compile(r"<[^>]+>")
_RE_ESPACES = re.compile(r"\s+")
_RE_SEPARATEUR_PHRASE = re.compile(r"(?<=[.!?;])\s+|(?<=\))(?=\s*[A-ZÀ-ÖØ-Þ])")
_RE_NIVEAU = re.compile(r"\b(A1|A2|B1|B2|C1|C2)\b", re.IGNORECASE)
_RE_FRANCAIS = re.compile(r"fran[çc]a(?:is|ise)|\bTCF\b|\bDELF\b|\bDALF\b", re.IGNORECASE)
_RE_ANGLAIS = re.compile(r"anglais|english", re.IGNORECASE)
_RE_MARQUEUR_EXIGENCE = re.compile(r"exig|minimum|requis|au moins|niveau", re.IGNORECASE)
_RE_PRIORITE = re.compile(r"priorit[ée]", re.IGNORECASE)
_RE_C1 = re.compile(r"\bC1\b", re.IGNORECASE)

_FENETRE_MARQUEUR = 60
_LONGUEUR_EXTRAIT = 200
_MAX_EXTRAITS = 3


@dataclass(frozen=True)
class ExigenceLangue:
    francais_min: str | None
    anglais_min: str | None
    priorite_c1: bool = False
    extraits: tuple[str, ...] = ()


def _nettoyer(texte: str) -> str:
    """Retire les balises HTML, décode les entités et normalise les espaces."""
    sans_balises = _RE_BALISE.sub(" ", texte)
    decode = html.unescape(sans_balises)
    return _RE_ESPACES.sub(" ", decode).strip()


def _phrases(texte: str) -> list[str]:
    return [p.strip() for p in _RE_SEPARATEUR_PHRASE.split(texte) if p and p.strip()]


def _niveaux_par_langue(phrase: str) -> dict[str, list[tuple[str, bool]]]:
    """Associe chaque niveau cité à la langue (fr/en) la plus proche dans la phrase.

    Retourne, par langue, la liste (niveau, marqué) dans l'ordre du texte ; « marqué »
    signifie qu'un mot d'exigence (exigé, minimum, requis, au moins, niveau) précède le niveau.
    """
    positions_fr = [m.start() for m in _RE_FRANCAIS.finditer(phrase)]
    positions_en = [m.start() for m in _RE_ANGLAIS.finditer(phrase)]
    resultat: dict[str, list[tuple[str, bool]]] = {"fr": [], "en": []}

    for m in _RE_NIVEAU.finditer(phrase):
        pos = m.start()
        niveau = m.group(1).upper()
        marque = bool(_RE_MARQUEUR_EXIGENCE.search(phrase[max(0, pos - _FENETRE_MARQUEUR):pos]))
        dist_fr = min((abs(pos - p) for p in positions_fr), default=None)
        dist_en = min((abs(pos - p) for p in positions_en), default=None)
        if dist_fr is None and dist_en is None:
            continue
        if dist_en is None or (dist_fr is not None and dist_fr <= dist_en):
            resultat["fr"].append((niveau, marque))
        else:
            resultat["en"].append((niveau, marque))
    return resultat


def _choisir_niveau(candidats: list[tuple[str, bool]]) -> str | None:
    """Premier niveau marqué par une exigence ; à défaut le plus bas cité."""
    if not candidats:
        return None
    marques = [niveau for niveau, marque in candidats if marque]
    if marques:
        return marques[0]
    return min((niveau for niveau, _ in candidats), key=NIVEAUX_CECRL.index)


def analyser_prerequis(texte: str | None) -> ExigenceLangue:
    """Extrait les niveaux de français et d'anglais exigés depuis le texte d'un prérequis."""
    if not texte:
        return ExigenceLangue(francais_min=None, anglais_min=None)

    nettoye = _nettoyer(texte)
    if not nettoye:
        return ExigenceLangue(francais_min=None, anglais_min=None)

    candidats_fr: list[tuple[str, bool]] = []
    candidats_en: list[tuple[str, bool]] = []
    extraits: list[str] = []
    phrase_priorite: str | None = None

    for phrase in _phrases(nettoye):
        niveaux = _niveaux_par_langue(phrase)
        if niveaux["fr"] or niveaux["en"]:
            candidats_fr.extend(niveaux["fr"])
            candidats_en.extend(niveaux["en"])
            extraits.append(phrase)
        if (
            phrase_priorite is None
            and _RE_PRIORITE.search(phrase)
            and _RE_C1.search(phrase)
            and not _RE_ANGLAIS.search(phrase)
        ):
            phrase_priorite = phrase

    francais_min = _choisir_niveau(candidats_fr)
    anglais_min = _choisir_niveau(candidats_en)
    priorite_c1 = francais_min is not None and phrase_priorite is not None

    if priorite_c1 and phrase_priorite not in extraits:
        extraits.append(phrase_priorite)

    extraits_tronques = tuple(e[:_LONGUEUR_EXTRAIT] for e in dict.fromkeys(extraits))[:_MAX_EXTRAITS]

    return ExigenceLangue(
        francais_min=francais_min,
        anglais_min=anglais_min,
        priorite_c1=priorite_c1,
        extraits=extraits_tronques,
    )


def _normaliser_niveau(valeur: str | None) -> str | None:
    if valeur is None:
        return None
    niveau = str(valeur).strip().upper()
    return niveau if niveau in NIVEAUX_CECRL else None


def evaluer_adequation(
    exigence: ExigenceLangue,
    *,
    francais_candidat: str | None,
    anglais_candidat: str | None = None,
) -> dict:
    """Compare le niveau du candidat à l'exigence. Renvoie {"statut": ..., "messages": [...]}."""
    if exigence.francais_min is None and exigence.anglais_min is None:
        return {
            "statut": "inconnu",
            "messages": ["Aucune exigence de langue détectée dans le prérequis."],
        }

    messages: list[str] = []
    statuts: list[str] = []
    controles = (
        ("Français", exigence.francais_min, francais_candidat),
        ("Anglais", exigence.anglais_min, anglais_candidat),
    )
    for libelle, requis, candidat in controles:
        if requis is None:
            continue
        niveau_candidat = _normaliser_niveau(candidat)
        if niveau_candidat is None:
            statuts.append("inconnu")
            messages.append(
                f"Niveau de {libelle.lower()} du candidat absent ou non reconnu : "
                "adéquation impossible à vérifier."
            )
            continue
        if NIVEAUX_CECRL.index(niveau_candidat) < NIVEAUX_CECRL.index(requis):
            statuts.append("insuffisant")
            messages.append(f"{libelle} exigé : {requis}, niveau du candidat : {niveau_candidat}")
        else:
            statuts.append("ok")

    niveau_fr_candidat = _normaliser_niveau(francais_candidat)
    if (
        exigence.priorite_c1
        and niveau_fr_candidat is not None
        and NIVEAUX_CECRL.index(niveau_fr_candidat) < NIVEAUX_CECRL.index("C1")
    ):
        messages.append("Priorité aux candidats C1")

    if "insuffisant" in statuts:
        statut = "insuffisant"
    elif "inconnu" in statuts:
        statut = "inconnu"
    else:
        statut = "ok"
    return {"statut": statut, "messages": messages}
