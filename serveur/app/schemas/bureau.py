"""Schémas du bureau et du journal d'audit."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.modeles.journal_audit import ResultatAudit
from app.schemas.commun import SchemaEntree, SchemaSortie


class BureauSortie(SchemaSortie):
    id: uuid.UUID
    nom: str
    slug: str
    actif: bool
    cree_le: datetime


class BureauModification(SchemaEntree):
    nom: str = Field(min_length=2, max_length=200)


class EntreeAuditSortie(SchemaSortie):
    id: uuid.UUID
    horodatage: datetime
    acteur_id: uuid.UUID | None
    action: str
    resultat: ResultatAudit
    ressource_type: str | None
    ressource_id: uuid.UUID | None
    details: dict[str, Any] | None
