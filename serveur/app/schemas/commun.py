"""Schémas communs."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class SchemaEntree(BaseModel):
    """Toute entrée refuse les champs inconnus : impossible, par exemple, d'injecter
    un `tenant_id` ou un `role` non prévu dans le corps d'une requête."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SchemaSortie(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    elements: list[T]
    total: int
    page: int
    taille: int


class Erreur(BaseModel):
    code: str
    detail: str
    reference: str | None = None
