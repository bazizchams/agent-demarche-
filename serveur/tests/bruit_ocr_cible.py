"""Bruit OCR ciblé et déterministe, complémentaire de `corpus_releves_synthetique.bruiter_ocr`.

Altère les jetons numériques comme le ferait un mauvais OCR. Aucune fonction n'ajoute ni ne
retire de ligne ni ne change le nombre de caractères d'une ligne. Bibliothèque standard seule.
"""

from __future__ import annotations

import random
import re
import unicodedata

# Jeton numérique : suite maximale de 0-9 , . / - contenant au moins un chiffre, non collée
# à une lettre, un chiffre, un tiret bas ou un séparateur.
_JETON_NUMERIQUE = re.compile(r"(?<![\w,./-])[0-9,./-]*[0-9][0-9,./-]*(?![\w,./-])")
_VIRGULE_DECIMALE = re.compile(r"(?<=[0-9]),(?=[0-9])")
_CHIFFRES_CONFONDABLES = "01"


def _confondre_jeton(jeton: str, generateur: random.Random) -> str:
    """Remplace au plus un chiffre 0 ou 1 du jeton (0 -> O, 1 -> l ou I) ; sinon le jeton est intact."""
    positions = [i for i, car in enumerate(jeton) if car in _CHIFFRES_CONFONDABLES]
    if not positions:
        return jeton
    i = generateur.choice(positions)
    cible = "O" if jeton[i] == "0" else generateur.choice(("l", "I"))
    return jeton[:i] + cible + jeton[i + 1 :]


def chiffres_confondus(texte: str, *, graine: int = 0) -> str:
    """Confond au plus un chiffre 0/1 par jeton numérique, de façon déterministe selon la graine."""
    generateur = random.Random(graine)
    return _JETON_NUMERIQUE.sub(lambda m: _confondre_jeton(m.group(0), generateur), texte)


def virgule_perdue(texte: str) -> str:
    """Remplace la virgule décimale entre deux chiffres par un point, sans toucher au reste."""
    return _VIRGULE_DECIMALE.sub(".", texte)


def accents_perdus(texte: str) -> str:
    """Supprime les accents par décomposition NFD puis retrait des marques Mn."""
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(car for car in decompose if unicodedata.category(car) != "Mn")


def variantes_ciblees(texte: str) -> dict[str, str]:
    """Renvoie les variantes de bruit ciblé du texte, avec la même structure de lignes."""
    return {
        "chiffres_confondus_0": chiffres_confondus(texte, graine=0),
        "chiffres_confondus_1": chiffres_confondus(texte, graine=1),
        "chiffres_confondus_2": chiffres_confondus(texte, graine=2),
        "virgule_perdue": virgule_perdue(texte),
        "accents_perdus": accents_perdus(texte),
        "tout_combine": accents_perdus(virgule_perdue(chiffres_confondus(texte, graine=3))),
    }
