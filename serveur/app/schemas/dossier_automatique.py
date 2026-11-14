"""Schémas du dossier automatique (phase P7) : état d'avancement d'un candidat, étape par étape.

Règle 5 : l'état ne contient QUE des codes, des libellés génériques et des compteurs (jamais un nom, un
numéro de passeport ou une valeur lue). Il peut donc être affiché, journalisé ou transmis sans risque.
"""

from __future__ import annotations

import enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.commun import SchemaEntree

CODES_ETAPES = (
    "pieces",
    "lecture",
    "revue_valeurs",
    "fiche",
    "points_forts",
    "projet_professionnel",
    "voeux",
    "lettres",
    "navigateur",
)


class StatutEtape(str, enum.Enum):
    A_FAIRE = "a_faire"
    EN_COURS = "en_cours"
    TERMINE = "termine"
    A_VERIFIER = "a_verifier"
    BLOQUE = "bloque"


class LancerDossierAutomatiqueEntree(SchemaEntree):
    """Corps facultatif : démarche dont la porte d'entrée vérifie les pièces (défaut : Campus France)."""

    code_demarche: Annotated[str, Field(min_length=1, max_length=60)] | None = None


class EtapeDossierSortie(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    libelle: str
    statut: StatutEtape
    detail: str
    action_humaine: str | None
    lien_ecran: str | None
    compteurs: dict[str, int]


class EtatDossierAutomatiqueSortie(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidat_id: str
    progression: int = Field(ge=0, le=100)
    etapes: list[EtapeDossierSortie]
    pieces_manquantes: list[str]
