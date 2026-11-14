"""Fiche de formation du catalogue : format d'échange, exigences inconnues, import du YAML des écoles.

Module PUR (aucune base, aucun réseau) : il est utilisé par le service de catalogue (base de données),
par la sélection de vœux et par l'exploration du portail (Co-Pilote).

Règles :
- R4 : aucune exigence n'est inventée. Une exigence non lue sur la source vaut « inconnue » (jamais « ok »)
  et la fiche est au statut « à vérifier ». Seul un humain peut confirmer « aucune exigence » en ajoutant
  le code à `aucune_exigence_confirmee`.
- R5 : aucune donnée personnelle (une fiche décrit une formation, jamais un candidat).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.prerequis_formation import NIVEAUX_CECRL, analyser_prerequis

CODE_NIVEAU_ENTREE = "niveau_entree"
CODE_LANGUE = "langue"
CODE_MOYENNE = "moyenne"
CODE_DATE_LIMITE = "date_limite"
CODES_EXIGENCES: tuple[str, ...] = (CODE_NIVEAU_ENTREE, CODE_LANGUE, CODE_MOYENNE, CODE_DATE_LIMITE)
# Pièces : toujours à lire sur la page officielle, mais elles ne bloquent pas la sélection
# (aucun critère du profil ne permet de les évaluer).
CODE_PIECES = "pieces"

REFERENCES_MOYENNE = ("bac", "derniere_annee", "cursus")
SOURCES_FICHE = ("yaml", "exploration", "manuel")
TEXTE_A_VERIFIER = "à vérifier"

_RE_NIVEAU_BAC_PLUS = re.compile(r"\bbac\s*\+\s*(\d)\b", re.IGNORECASE)
_RE_ANGLAIS = re.compile(r"anglais|english", re.IGNORECASE)
# Marqueurs d'exigences ALTERNATIVES (selon le parcours / la langue d'enseignement).
_RE_ALTERNATIVE = re.compile(r"\bou\b|track|parcours|selon|programmes?\b", re.IGNORECASE)
_LONGUEUR_TEXTE_LANGUE = 400

TexteCourt = Annotated[str, Field(min_length=1, max_length=200)]


def normaliser(texte: str | None) -> str:
    """Minuscule, sans accents, ponctuation réduite à des espaces."""
    brut = unicodedata.normalize("NFKD", texte or "")
    sans_accents = "".join(c for c in brut if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", sans_accents.lower()).strip()


class FicheEntree(BaseModel):
    """Fiche de formation au format du catalogue (entrée API, import YAML, sortie d'exploration)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    etablissement: str = Field(min_length=1, max_length=200)
    intitule: str = Field(min_length=1, max_length=250)
    niveau_entree_bac_plus: int | None = Field(default=None, ge=1, le=8)
    niveau_entree_libelle: str | None = Field(default=None, max_length=60)
    francais_min: str | None = None
    anglais_min: str | None = None
    priorite_c1: bool = False
    langue_texte: str | None = Field(default=None, max_length=1000)
    langue_ambigue: bool = False
    moyenne_min: float | None = Field(default=None, ge=0, le=20)
    moyenne_reference: Literal["bac", "derniere_annee", "cursus"] | None = None
    pieces: list[TexteCourt] = Field(default_factory=list, max_length=50)
    date_limite: date | None = None
    ferme: bool | None = None
    domaines: list[TexteCourt] = Field(default_factory=list, max_length=20)
    url_officielle: str | None = Field(default=None, max_length=500)
    date_releve: date
    source: Literal["yaml", "exploration", "manuel"]
    aucune_exigence_confirmee: list[Literal["niveau_entree", "langue", "moyenne", "date_limite"]] = (
        Field(default_factory=list, max_length=4)
    )

    @field_validator("francais_min", "anglais_min")
    @classmethod
    def _niveau_cecrl(cls, valeur: str | None) -> str | None:
        if valeur is None:
            return None
        niveau = valeur.strip().upper()
        if niveau not in NIVEAUX_CECRL:
            raise ValueError("Niveau de langue hors CECRL (A1 à C2).")
        return niveau

    @field_validator("url_officielle")
    @classmethod
    def _url_https(cls, valeur: str | None) -> str | None:
        if valeur is None:
            return None
        if not valeur.lower().startswith("https://"):
            raise ValueError("L'URL officielle doit être en HTTPS (Règle 6).")
        return valeur

    @model_validator(mode="after")
    def _coherence(self) -> "FicheEntree":
        if self.langue_ambigue and (self.francais_min or self.anglais_min):
            raise ValueError("Une exigence de langue ambiguë ne porte aucun niveau (à vérifier).")
        return self



def exigences_inconnues(fiche: Any) -> list[str]:
    """Codes des exigences INCONNUES (fiche ORM ou `FicheEntree`). Une valeur absente n'est « sans
    exigence » que si un humain l'a confirmé (`aucune_exigence_confirmee`)."""
    confirmees = set(getattr(fiche, "aucune_exigence_confirmee", None) or [])
    inconnues: list[str] = []
    if fiche.niveau_entree_bac_plus is None and CODE_NIVEAU_ENTREE not in confirmees:
        inconnues.append(CODE_NIVEAU_ENTREE)
    sans_niveau = fiche.francais_min is None and fiche.anglais_min is None
    if fiche.langue_ambigue or (sans_niveau and CODE_LANGUE not in confirmees):
        inconnues.append(CODE_LANGUE)
    if fiche.moyenne_min is None:
        if CODE_MOYENNE not in confirmees:
            inconnues.append(CODE_MOYENNE)
    elif fiche.moyenne_reference is None:
        inconnues.append(CODE_MOYENNE)  # seuil connu mais on ignore sur quelle moyenne il porte
    if fiche.date_limite is None and CODE_DATE_LIMITE not in confirmees:
        inconnues.append(CODE_DATE_LIMITE)
    return inconnues


def cle_fiche(etablissement: str, intitule: str, niveau_entree_bac_plus: int | None) -> str:
    """Clé d'unicité (par bureau) d'une fiche : établissement, intitulé et niveau d'entrée normalisés."""
    niveau = "" if niveau_entree_bac_plus is None else str(niveau_entree_bac_plus)
    return f"{normaliser(etablissement)}|{normaliser(intitule)}|{niveau}"[:520]


def niveau_bac_plus_depuis_libelle(libelle: str | None) -> int | None:
    """« Bac +4 » -> 4. Tout autre libellé -> None (jamais deviné)."""
    if not libelle:
        return None
    trouve = _RE_NIVEAU_BAC_PLUS.search(libelle)
    return int(trouve.group(1)) if trouve else None


def exigences_langue_depuis_textes(textes: list[str]) -> dict[str, Any]:
    """Niveaux de langue exigés d'après un ou plusieurs textes (prérequis, procédure d'inscription).

    Conservateur : si les textes décrivent des exigences ALTERNATIVES (plusieurs parcours ou langues
    d'enseignement) ou se contredisent, aucun niveau n'est retenu et `langue_ambigue` vaut True.
    """
    utiles = [t for t in textes if t and t.strip()]
    analyses = [analyser_prerequis(t) for t in utiles]
    retenue = next((a for a in analyses if a.francais_min or a.anglais_min), None)
    resultat: dict[str, Any] = {
        "francais_min": None,
        "anglais_min": None,
        "priorite_c1": any(a.priorite_c1 for a in analyses),
        "langue_ambigue": False,
        "langue_texte": None,
    }
    if utiles:
        resultat["langue_texte"] = " | ".join(utiles)[:_LONGUEUR_TEXTE_LANGUE]
    if retenue is None:
        return resultat

    niveaux_fr = {a.francais_min for a in analyses if a.francais_min}
    niveaux_en = {a.anglais_min for a in analyses if a.anglais_min}
    alternatives = any(_RE_ANGLAIS.search(t) and _RE_ALTERNATIVE.search(t) for t in utiles)
    if len(niveaux_fr) > 1 or len(niveaux_en) > 1 or alternatives:
        resultat["langue_ambigue"] = True
        return resultat
    resultat["francais_min"] = next(iter(niveaux_fr), None)
    resultat["anglais_min"] = next(iter(niveaux_en), None)
    return resultat


def _date_iso(valeur: Any) -> date | None:
    try:
        return date.fromisoformat(str(valeur)[:10])
    except (TypeError, ValueError):
        return None


_RE_PORTEE = re.compile(r"\(([^)]*\b(?:programme|cursus|formation)s?\b[^)]*)\)", re.IGNORECASE)
_MOTS_NEUTRES = {"programme", "programmes", "cursus", "formation", "formations"}


def _formation_concernee(texte_langue: str, formation: str) -> bool:
    """Vrai si l'exigence de langue vise cette formation. Un texte du type « B2 minimum (programme
    ingénieur) » ne vise que les formations dont l'intitulé reprend le mot de la parenthèse ; sans
    parenthèse de portée, l'exigence est celle de l'école entière."""
    portee = _RE_PORTEE.search(texte_langue)
    if portee is None:
        return True
    mots = [m for m in normaliser(portee.group(1)).split() if m not in _MOTS_NEUTRES and len(m) >= 4]
    cible = normaliser(formation)
    return any(m in cible for m in mots) if mots else True


def fiches_depuis_yaml(contenu: dict[str, Any]) -> list[FicheEntree]:
    """Une fiche par formation citée pour chaque école du YAML `ecoles_privees_france.yaml`.

    Ne sont reprises QUE les informations lues sur la source : le niveau d'entrée, la moyenne et la date
    limite ne figurent pas dans le YAML : ils restent inconnus (« à vérifier »).
    """
    meta = contenu.get("meta") or {}
    releve_global = _date_iso(meta.get("consulte_le"))
    fiches: list[FicheEntree] = []
    for ecole in contenu.get("ecoles") or []:
        nom = str(ecole.get("nom") or "").strip()
        releve = _date_iso(ecole.get("consulte_le")) or releve_global
        if not nom or releve is None:
            continue
        texte = str(ecole.get("langue_requise") or "").strip()
        texte_utile = "" if not texte or texte.lower() == TEXTE_A_VERIFIER else texte
        domaines = [str(d) for d in ecole.get("domaines") or []]
        url = ecole.get("url_admissions")
        for formation in ecole.get("formations") or []:
            concernee = _formation_concernee(texte_utile, str(formation))
            langue = exigences_langue_depuis_textes([texte_utile])
            if not concernee:
                langue.update(francais_min=None, anglais_min=None, priorite_c1=False)
            fiches.append(
                FicheEntree(
                    etablissement=nom,
                    intitule=str(formation),
                    domaines=domaines,
                    url_officielle=str(url) if url else None,
                    date_releve=releve,
                    source="yaml",
                    **langue,
                )
            )
    return fiches
