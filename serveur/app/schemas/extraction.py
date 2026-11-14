"""Schémas Pydantic v2 de la lecture des documents (extractions, revue, application à la fiche).

Aucun schéma ne reprend une valeur lue dans un message d'erreur ou un rapport d'application :
seules les routes `ExtractionSortie` renvoient les valeurs, à un utilisateur authentifié du bureau.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.modeles.extraction_document import StatutExtraction
from app.schemas.commun import SchemaEntree, SchemaSortie
from app.schemas.document import EtatCompletudeDemarcheSortie


class ExtractionSortie(SchemaSortie):
    id: uuid.UUID
    document_id: uuid.UUID
    candidat_id: uuid.UUID
    champ: str
    valeur: str
    valeur_alternative: str | None
    page: int | None
    extrait: str
    source: str
    confiance: float
    statut: StatutExtraction
    motif: str | None
    decide_par_id: uuid.UUID | None
    decide_le: datetime | None
    applique_le: datetime | None
    cree_le: datetime
    modifie_le: datetime


class ClassificationSortie(SchemaSortie):
    famille: str | None
    type_piece_propose: str | None
    confiance: float
    indices: list[str]
    confirmation_humaine_requise: bool


class AlerteSortie(SchemaSortie):
    code: str
    champ: str | None
    document_ids: list[str]
    extraction_ids: list[str]
    message: str


class ResultatExtractionDocumentSortie(SchemaSortie):
    document_id: uuid.UUID
    type_piece: str
    classification: ClassificationSortie
    lecteur_b_utilise: bool
    extractions: list[ExtractionSortie]
    alertes: list[AlerteSortie]
    avertissements: list[str]


class ErreurDocumentSortie(SchemaSortie):
    document_id: uuid.UUID
    detail: str


class ResultatLotSortie(SchemaSortie):
    completude: EtatCompletudeDemarcheSortie | None
    dossier_complet: bool | None
    documents: list[ResultatExtractionDocumentSortie]
    erreurs: list[ErreurDocumentSortie]
    alertes: list[AlerteSortie]


class CorrectionEntree(SchemaEntree):
    valeur: str = Field(min_length=1, max_length=200)


class ChampAppliqueSortie(SchemaSortie):
    champ: str
    extraction_id: uuid.UUID


class ConflitApplicationSortie(SchemaSortie):
    champ: str
    extraction_id: uuid.UUID
    raison: str  # code : fiche_deja_renseignee, passeport_deja_utilise, valeurs_multiples


class RapportApplicationSortie(SchemaSortie):
    appliques: list[ChampAppliqueSortie]
    conflits: list[ConflitApplicationSortie]
    deja_identiques: list[str]
    hors_fiche: list[str]
    a_verifier_restants: int
