"""Base déclarative SQLAlchemy 2, types et mixins communs.

Compatibilité SQLite (local) / PostgreSQL (en ligne) :
- identifiants UUID via le type générique `Uuid` ;
- horodatages toujours en UTC avec fuseau (`HorodatageUTC`) ;
- énumérations stockées en texte + contrainte CHECK (pas de type ENUM natif) ;
- convention de nommage des contraintes, nécessaire aux migrations Alembic.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, MetaData, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column
from sqlalchemy.types import TypeDecorator

CONVENTION_NOMMAGE = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def maintenant_utc() -> datetime:
    return datetime.now(timezone.utc)


class HorodatageUTC(TypeDecorator[datetime]):
    """Refuse les dates sans fuseau, stocke en UTC, relit toujours en UTC avec fuseau
    (SQLite ne conserve pas le fuseau, PostgreSQL oui : le comportement est identique)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Horodatage sans fuseau horaire refusé (utiliser UTC).")
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENTION_NOMMAGE)
    type_annotation_map = {uuid.UUID: Uuid(), datetime: HorodatageUTC()}


class MixinIdentifiant:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class MixinHorodatage:
    cree_le: Mapped[datetime] = mapped_column(default=maintenant_utc, nullable=False)
    modifie_le: Mapped[datetime] = mapped_column(
        default=maintenant_utc, onupdate=maintenant_utc, nullable=False
    )


class MixinTenant:
    """À hériter par TOUTE table métier : rattache la ligne à un bureau (tenant).
    Le filtrage automatique est assuré par `app.db.tenant`."""

    @declared_attr
    def tenant_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            ForeignKey("bureaux.id", ondelete="RESTRICT"), nullable=False, index=True
        )
