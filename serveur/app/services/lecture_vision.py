"""Lecteur B (optionnel) : un modèle de VISION lit l'image du document et renvoie, par champ,
la valeur et l'extrait littéral qui la porte.

Garde-fous :
- DÉSACTIVÉ par défaut (`BE_VISION_ACTIVE`) ;
- une image contient des données personnelles : tout hôte non local est REFUSÉ à la
  construction du lecteur ET, en seconde barrière, par `ClientOpenAICompatible.generer(images=…)` ;
  les clients Anthropic et anonymisant refusent aussi toute image ;
- la réponse du modèle n'est qu'une proposition : champs hors liste, valeurs vides ou
  réponse illisible sont ignorés (règle 4), et la fusion exige l'ancrage littéral.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx

from app.core.config import Parametres
from app.core.erreurs import ServiceIndisponible
from app.services.extraction_champs import (
    CERTIFICAT_DATE,
    CERTIFICAT_TYPE,
    DATE_EXPIRATION_PASSEPORT,
    DATE_NAISSANCE,
    FAMILLE_CERTIFICAT,
    FAMILLE_PASSEPORT,
    FAMILLE_RELEVE,
    IELTS_BANDE,
    MOYENNE_GENERALE,
    NATIONALITE_CODE,
    NIVEAU_ANGLAIS,
    NIVEAU_FRANCAIS,
    NOM,
    NUMERO_PASSEPORT,
    PRENOM,
    SEXE,
    ChampLu,
    normaliser_valeur,
)
from app.services.lecture_documents import ImagePage
from app.services.llm import ClientLLM, ClientOpenAICompatible, ImageEntree, hote_est_local

CONFIANCE_LECTEUR_B = 0.6
NOM_OUTIL = "transcrire_champs"

CHAMPS_PAR_FAMILLE: dict[str, tuple[str, ...]] = {
    FAMILLE_PASSEPORT: (
        NOM, PRENOM, DATE_NAISSANCE, SEXE, NUMERO_PASSEPORT, DATE_EXPIRATION_PASSEPORT, NATIONALITE_CODE,
    ),
    FAMILLE_RELEVE: (MOYENNE_GENERALE,),
    FAMILLE_CERTIFICAT: (CERTIFICAT_TYPE, CERTIFICAT_DATE, NIVEAU_FRANCAIS, NIVEAU_ANGLAIS, IELTS_BANDE),
}

_SYSTEME = (
    "Tu es un lecteur de documents. Transcris UNIQUEMENT ce qui est écrit sur l'image, sans "
    "rien déduire ni compléter. Pour chaque champ visible, renvoie sa valeur et l'extrait "
    "littéral (la ligne exacte du document qui la contient). Si un champ n'est pas lisible ou "
    "absent, ne le renvoie pas. Dates au format AAAA-MM-JJ."
)


def _outil(champs: Sequence[str]) -> dict[str, Any]:
    return {
        "name": NOM_OUTIL,
        "description": "Champs lus sur le document, avec leur extrait littéral.",
        "input_schema": {
            "type": "object",
            "properties": {
                "champs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "champ": {"type": "string", "enum": list(champs)},
                            "valeur": {"type": "string"},
                            "page": {"type": "integer"},
                            "extrait": {"type": "string"},
                        },
                        "required": ["champ", "valeur", "page", "extrait"],
                    },
                }
            },
            "required": ["champs"],
        },
    }


class LecteurVision:
    def __init__(self, client: ClientLLM) -> None:
        self._client = client

    def lire_champs(self, images: Sequence[ImagePage], *, famille: str) -> list[ChampLu]:
        autorises = CHAMPS_PAR_FAMILLE.get(famille)
        if not autorises or not images:
            return []
        pages = [img.page for img in images]
        message = (
            f"Famille de document : {famille}. Champs possibles : {', '.join(autorises)}. "
            "Images jointes, dans l'ordre : "
            + ", ".join(f"image {i} = page {p}" for i, p in enumerate(pages, start=1))
            + "."
        )
        reponse = self._client.generer(
            systeme=_SYSTEME,
            message=message,
            outil=_outil(autorises),
            max_tokens=1500,
            images=[ImageEntree(octets=img.octets, type_mime=img.type_mime) for img in images],
        )
        brut = (reponse.outil or {}).get("champs") if isinstance(reponse.outil, dict) else None
        if not isinstance(brut, list):
            return []
        lus: list[ChampLu] = []
        for element in brut:
            lu = self._convertir(element, autorises, pages)
            if lu is not None:
                lus.append(lu)
        return lus

    @staticmethod
    def _convertir(element: Any, autorises: Sequence[str], pages: Sequence[int]) -> ChampLu | None:
        if not isinstance(element, dict):
            return None
        champ, valeur, extrait = element.get("champ"), element.get("valeur"), element.get("extrait")
        if champ not in autorises or not isinstance(valeur, str) or not valeur.strip():
            return None
        page = element.get("page")
        if not isinstance(page, int) or page not in pages:
            if len(pages) != 1:
                return None
            page = pages[0]
        return ChampLu(
            champ=champ,
            valeur=normaliser_valeur(champ, valeur),
            extrait=extrait.strip() if isinstance(extrait, str) else "",
            page=page,
            confiance=CONFIANCE_LECTEUR_B,
        )


def construire_lecteur_vision(
    parametres: Parametres, *, transport: httpx.BaseTransport | None = None
) -> LecteurVision | None:
    """None si la vision est désactivée (défaut). Refuse tout hôte non local."""
    if not parametres.vision_active:
        return None
    if not parametres.vision_url_base or not parametres.vision_modele:
        raise ServiceIndisponible(
            "Le lecteur de vision est activé mais BE_VISION_URL_BASE et BE_VISION_MODELE sont requis."
        )
    if not hote_est_local(parametres.vision_url_base):
        raise ServiceIndisponible(
            "Lecteur de vision refusé : l'hôte doit être local (cette machine ou le réseau privé), "
            "car une image de document contient des données personnelles."
        )
    return LecteurVision(
        ClientOpenAICompatible(
            url_base=parametres.vision_url_base,
            modele=parametres.vision_modele,
            cle=parametres.vision_cle,
            delai_secondes=parametres.delai_llm_secondes,
            tentatives=parametres.ia_tentatives,
            transport=transport,
        )
    )
