"""Schémas du dépôt de passeport sans fiche (propositions à confirmer, puis création de la fiche)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import Field

from app.modeles.candidat import SexeCandidat
from app.schemas.candidat import CandidatSortie
from app.schemas.commun import SchemaEntree, SchemaSortie


class PropositionSortie(SchemaSortie):
    champ: str  # nom, prenom, date_naissance, sexe, nationalite, numero_passeport, date_expiration_passeport
    valeur: str
    extrait: str
    page: int | None
    confiance: float
    statut: str  # toujours « a_confirmer » : rien n'est une fiche tant qu'un humain n'a pas confirmé


class DepotPasseportSortie(SchemaSortie):
    id: uuid.UUID
    statut: str  # propose | saisie_manuelle
    propositions: list[PropositionSortie]
    saisie_manuelle_requise: bool
    avertissements: list[str]
    candidat_existant_id: uuid.UUID | None  # un candidat du bureau a déjà ce numéro de passeport
    expire_le: datetime
    cree_le: datetime


class CreationFicheEntree(SchemaEntree):
    """Valeurs CONFIRMÉES (ou corrigées) par l'humain : seules celles-ci entrent dans la fiche."""

    confirme: bool
    nom: str = Field(min_length=1, max_length=120)
    prenom: str = Field(min_length=1, max_length=120)
    date_naissance: date | None = None
    sexe: SexeCandidat | None = None
    nationalite: str | None = Field(default=None, min_length=1, max_length=100)
    numero_passeport: str | None = Field(default=None, min_length=4, max_length=40)
    date_expiration_passeport: date | None = None


class FicheCreeeSortie(SchemaSortie):
    candidat: CandidatSortie
    document_id: uuid.UUID
    extractions_validees: int
    avertissements: list[str]
