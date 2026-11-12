"""Schémas Pydantic v2 des candidats.

Règle 4 : aucun champ facultatif ne reçoit de valeur inventée (« 01/01/2000 », « Alger », « M »).
Tout champ non renseigné reste `None`.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from typing import Annotated

from pydantic import BeforeValidator, Field

from app.modeles.candidat import SexeCandidat, StatutCandidat
from app.schemas.auth import EmailNormalise
from app.schemas.commun import SchemaEntree, SchemaSortie


def _normaliser_niveau(valeur):
    if valeur is None:
        return None
    if not isinstance(valeur, str):
        raise ValueError("niveau CECRL invalide")
    v = valeur.strip().upper()
    if v not in {"A1", "A2", "B1", "B2", "C1", "C2"}:
        raise ValueError("niveau attendu : A1, A2, B1, B2, C1 ou C2")
    return v


NiveauCECRL = Annotated[str | None, BeforeValidator(_normaliser_niveau)]


class CandidatCreation(SchemaEntree):
    nom: str = Field(min_length=1, max_length=120)
    prenom: str = Field(min_length=1, max_length=120)
    sexe: SexeCandidat | None = None
    date_naissance: date | None = None
    lieu_naissance: str | None = Field(default=None, min_length=1, max_length=120)
    nationalite: str | None = Field(default=None, min_length=1, max_length=100)
    pays_residence: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailNormalise | None = None
    telephone: str | None = Field(default=None, min_length=5, max_length=40)
    numero_passeport: str | None = Field(default=None, min_length=4, max_length=40)
    date_expiration_passeport: date | None = None
    adresse: str | None = Field(default=None, min_length=1, max_length=300)
    niveau_actuel: str | None = Field(default=None, min_length=1, max_length=160)
    niveau_francais: NiveauCECRL = None
    niveau_anglais: NiveauCECRL = None
    programme_vise: str | None = Field(default=None, min_length=1, max_length=200)
    etablissement_vise: str | None = Field(default=None, min_length=1, max_length=200)
    fonds_disponibles_eur: int | None = Field(default=None, ge=0)
    notes_internes: str | None = Field(default=None, max_length=2000)
    consentement_signe: bool = False


class CandidatModification(SchemaEntree):
    nom: str | None = Field(default=None, min_length=1, max_length=120)
    prenom: str | None = Field(default=None, min_length=1, max_length=120)
    sexe: SexeCandidat | None = None
    date_naissance: date | None = None
    lieu_naissance: str | None = Field(default=None, min_length=1, max_length=120)
    nationalite: str | None = Field(default=None, min_length=1, max_length=100)
    pays_residence: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailNormalise | None = None
    telephone: str | None = Field(default=None, min_length=5, max_length=40)
    numero_passeport: str | None = Field(default=None, min_length=4, max_length=40)
    date_expiration_passeport: date | None = None
    adresse: str | None = Field(default=None, min_length=1, max_length=300)
    niveau_actuel: str | None = Field(default=None, min_length=1, max_length=160)
    niveau_francais: NiveauCECRL = None
    niveau_anglais: NiveauCECRL = None
    programme_vise: str | None = Field(default=None, min_length=1, max_length=200)
    etablissement_vise: str | None = Field(default=None, min_length=1, max_length=200)
    fonds_disponibles_eur: int | None = Field(default=None, ge=0)
    notes_internes: str | None = Field(default=None, max_length=2000)
    consentement_signe: bool | None = None


class CandidatSortie(SchemaSortie):
    id: uuid.UUID
    nom: str
    prenom: str
    sexe: SexeCandidat | None
    date_naissance: date | None
    lieu_naissance: str | None
    nationalite: str | None
    pays_residence: str | None
    email: str | None
    telephone: str | None
    numero_passeport: str | None
    date_expiration_passeport: date | None
    adresse: str | None
    niveau_actuel: str | None
    niveau_francais: str | None = None
    niveau_anglais: str | None = None
    programme_vise: str | None
    etablissement_vise: str | None
    fonds_disponibles_eur: int | None
    notes_internes: str | None
    consentement_signe: bool
    date_consentement: datetime | None
    statut: StatutCandidat
    archive_le: datetime | None
    cree_le: datetime
    modifie_le: datetime
