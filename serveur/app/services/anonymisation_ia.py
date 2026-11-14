"""Anonymisation du texte avant envoi à un fournisseur d'IA qui n'est pas local (règle 5).

Filet de sécurité « au mieux » : retire les e-mails, téléphones, numéros de passeport
reconnaissables, les valeurs étiquetées « nom : … » / « prénom : … » et les termes connus
fournis par l'appelant (nom, prénom du candidat). Elle ne peut PAS reconnaître un nom cité
au milieu d'une phrase : les appelants doivent continuer à construire des contextes sans
donnée personnelle. Les dates ne sont volontairement pas masquées (échéances des procédures).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Iterable

from app.core.erreurs import ServiceIndisponible

if TYPE_CHECKING:  # évite l'import circulaire avec app.services.llm
    from app.services.llm import ClientLLM, ImageEntree, ReponseLLM

_MOTIFS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), "[email]"),
    (re.compile(r"(?<![\w-])(?:\+|00)\d[\d \-.]{7,}\d(?![\w-])"), "[telephone]"),
    (re.compile(r"(?<![\w-])0[5-7]\d(?:[ .\-]?\d{2}){3}(?![\w-])"), "[telephone]"),
    # Passeport algérien (ex. 12AB34567) puis formats génériques lettres + chiffres.
    (re.compile(r"(?<![\w-])\d{2}[A-Za-z]{2}\d{5}(?![\w-])"), "[passeport]"),
    (re.compile(r"(?<![\w-])[A-Za-z]{1,2}\d{6,9}(?![\w-])"), "[passeport]"),
    # Valeur suivant le mot « passeport » (ex. « passeport n° 123456789 »).
    (
        re.compile(r"(?i)(passeport\s*(?:n°|no|num[ée]ro|#)?\s*[:=]?\s*)[A-Za-z0-9]{6,12}"),
        r"\1[passeport]",
    ),
    (re.compile(r"(?<![\w-])\d{8,12}(?![\w-])"), "[numero]"),
    # Valeurs étiquetées : « Nom : Dupont », « Prénom = Amine ».
    (
        re.compile(
            r"(?i)\b((?:nom(?: de famille)?|pr[ée]nom)\s*[:=]\s*)[^\n,;:]{1,60}"
        ),
        r"\1[nom]",
    ),
]


def anonymiser(texte: str, termes: Iterable[str] = ()) -> str:
    """Renvoie `texte` sans e-mail, téléphone, n° de passeport ni nom étiqueté/connu."""
    for motif, remplacement in _MOTIFS:
        texte = motif.sub(remplacement, texte)
    for terme in sorted({t.strip() for t in termes if t and len(t.strip()) >= 2}, key=len, reverse=True):
        texte = re.sub(rf"(?<!\w){re.escape(terme)}(?!\w)", "[nom]", texte, flags=re.IGNORECASE)
    return texte


class ClientAnonymisant:
    """Enveloppe un `ClientLLM` : le texte envoyé est anonymisé, la réponse reste inchangée."""

    def __init__(self, client: ClientLLM, termes: Iterable[str] = ()) -> None:
        self._client = client
        self._termes = tuple(termes)

    def generer(
        self,
        *,
        systeme: str,
        message: str,
        outil: dict[str, Any] | None = None,
        max_tokens: int = 4096,
        images: "Sequence[ImageEntree] | None" = None,
    ) -> ReponseLLM:
        if images:  # l'anonymisation ne sait traiter que du texte : une image ne part jamais
            raise ServiceIndisponible(
                "Envoi d'image refusé : une image ne peut pas être anonymisée et contient des "
                "données personnelles."
            )
        return self._client.generer(
            systeme=anonymiser(systeme, self._termes),
            message=anonymiser(message, self._termes),
            outil=outil,
            max_tokens=max_tokens,
        )
