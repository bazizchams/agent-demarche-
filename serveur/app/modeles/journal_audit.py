"""Journal d'audit : qui a fait quoi, quand, sur quelle ressource, avec quel résultat.

- Ajout seul : aucune modification ni suppression via l'ORM (voir garde-fou ci-dessous).
- Aucune donnée personnelle : identifiants opaques et codes d'action uniquement.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Enum, ForeignKey, String, event
from sqlalchemy.orm import Mapped, ORMExecuteState, Session, mapped_column

from app.db.base import Base, MixinIdentifiant, MixinTenant, maintenant_utc
from app.db.tenant import CLE_CONTOURNEMENT


class ResultatAudit(str, enum.Enum):
    SUCCES = "succes"
    ECHEC = "echec"
    REFUS = "refus"


class EntreeAudit(MixinIdentifiant, MixinTenant, Base):
    __tablename__ = "journal_audit"

    horodatage: Mapped[datetime] = mapped_column(default=maintenant_utc, nullable=False, index=True)
    acteur_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    resultat: Mapped[ResultatAudit] = mapped_column(
        Enum(ResultatAudit, native_enum=False, length=10,
             values_callable=lambda e: [m.value for m in e],
             create_constraint=True, name="resultat_audit"),
        nullable=False,
    )
    ressource_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    ressource_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class JournalAuditImmuable(RuntimeError):
    pass


@event.listens_for(Session, "before_flush")
def _interdire_modification_audit(session: Session, flush_context, instances) -> None:
    for objet in list(session.dirty) + list(session.deleted):
        if isinstance(objet, EntreeAudit) and not session.info.get(CLE_CONTOURNEMENT):
            raise JournalAuditImmuable("Le journal d'audit ne peut être ni modifié ni supprimé.")


@event.listens_for(Session, "do_orm_execute")
def _interdire_dml_audit(etat: ORMExecuteState) -> None:
    if (etat.is_update or etat.is_delete) and not etat.session.info.get(CLE_CONTOURNEMENT):
        if any(m.class_ is EntreeAudit for m in etat.all_mappers):
            raise JournalAuditImmuable("Le journal d'audit ne peut être ni modifié ni supprimé.")
