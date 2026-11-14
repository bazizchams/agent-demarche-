"""Schémas de la sélection de vœux : profil d'étudiant (entrée) et suggestions (sortie).

Règle 5 : le profil ne contient AUCUNE identité (ni nom, ni prénom, ni date de naissance, ni passeport,
ni texte libre) ; `extra="forbid"` refuse tout champ supplémentaire. Les sorties n'en contiennent pas non plus
et peuvent donc être transmises à une IA.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.commun import SchemaEntree

NiveauCECRL = Literal["A1", "A2", "B1", "B2", "C1", "C2"]
TypeCertificat = Literal["TCF", "DELF", "DALF", "TEF", "TOEFL", "IELTS", "TOEIC", "autre"]
Note20 = Annotated[float, Field(ge=0, le=20)]
Domaine = Annotated[str, Field(min_length=1, max_length=60)]


class CertificatLangue(SchemaEntree):
    type: TypeCertificat | None = None
    date_obtention: date | None = None


class NiveauLangueProfil(SchemaEntree):
    niveau: NiveauCECRL | None = None
    certificat: CertificatLangue | None = None


class MoyennesProfil(SchemaEntree):
    """Moyennes sur 20 (jamais complétées par défaut : absente = inconnue)."""

    bac: Note20 | None = None
    derniere_annee: Note20 | None = None
    cursus: Note20 | None = None


class ProfilEtudiant(SchemaEntree):
    # Dernier diplôme obtenu : nombre d'années validées après le bac (bac = 0, licence = 3, master = 5).
    niveau_diplome_bac_plus: int | None = Field(default=None, ge=0, le=8)
    moyennes: MoyennesProfil = Field(default_factory=MoyennesProfil)
    francais: NiveauLangueProfil = Field(default_factory=NiveauLangueProfil)
    anglais: NiveauLangueProfil = Field(default_factory=NiveauLangueProfil)
    domaines_souhaites: list[Domaine] = Field(default_factory=list, max_length=10)
    date_rentree: date | None = None


class DemandeSuggestions(SchemaEntree):
    profil: ProfilEtudiant
    # Facultatif : complète le niveau de français/anglais manquant d'un candidat DU BUREAU (404 sinon).
    candidat_id: uuid.UUID | None = None
    # Facultatif : calcule le calendrier de la démarche (échéances relatives à la rentrée).
    code_demarche: str | None = Field(default=None, min_length=1, max_length=60)
    max_voeux: int = Field(default=7, ge=1, le=7)


class _Sortie(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CritereSortie(_Sortie):
    critere: str
    resultat: Literal["ok", "ecart", "ko", "inconnu", "non_applicable"]
    exigence_officielle: str
    donnee_profil: str
    detail: str


class ExigencesOfficielles(_Sortie):
    niveau_entree: str | None
    francais_min: str | None
    anglais_min: str | None
    priorite_c1: bool
    moyenne_min: float | None
    moyenne_reference: str | None
    date_limite: date | None
    pieces: list[str]
    url_officielle: str | None
    date_releve: date
    exigences_a_verifier: list[str]


class VoeuSuggere(_Sortie):
    fiche_id: uuid.UUID
    rang: int
    etablissement: str
    intitule: str
    categorie: Literal["sur", "realiste", "ambitieux", "a_verifier"]
    a_verifier: bool
    raisons_a_verifier: list[str]
    justification: str
    ecarts: list[str]
    exigences: ExigencesOfficielles
    criteres: list[CritereSortie]


class VoeuExclu(_Sortie):
    fiche_id: uuid.UUID
    etablissement: str
    intitule: str
    raisons: list[str]


class ReponseSuggestions(_Sortie):
    propositions: list[VoeuSuggere]
    exclus: list[VoeuExclu]
    nb_fiches_examinees: int
    nb_non_retenues_faute_de_place: int
    calendrier_demarche: list[dict[str, Any]] | None = None
    avertissements: list[str]
    avis: str
