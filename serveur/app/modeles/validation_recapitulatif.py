"""Modèle `ValidationRecapitulatif` (`validations_recapitulatif`) : validation humaine d'un
récapitulatif avant soumission officielle (Règle 1).

Sécurité : isolé par bureau (`MixinTenant`) ; le récapitulatif exact est chiffré au repos
(AES-256-GCM, clé du bureau) ; seule son empreinte SHA-256 est lisible en base.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MixinIdentifiant, MixinTenant, maintenant_utc


class StatutValidationRecapitulatif(str, enum.Enum):
    EN_ATTENTE = "en_attente"
    VALIDEE = "validee"
    REFUSEE = "refusee"
    ENVOYEE = "envoyee"
    INVALIDEE = "invalidee"


class ValidationRecapitulatif(MixinIdentifiant, MixinTenant, Base):
    __tablename__ = "validations_recapitulatif"

    candidat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    portail: Mapped[str] = mapped_column(String(40), nullable=False)
    type_demarche: Mapped[str] = mapped_column(String(60), nullable=False)
    contenu_chiffre: Mapped[str] = mapped_column(Text, nullable=False)
    empreinte: Mapped[str] = mapped_column(String(64), nullable=False)
    statut: Mapped[StatutValidationRecapitulatif] = mapped_column(
        Enum(
            StatutValidationRecapitulatif,
            native_enum=False,
            length=12,
            values_callable=lambda e: [m.value for m in e],
            create_constraint=True,
            name="statut_validation_recapitulatif",
        ),
        nullable=False,
        default=StatutValidationRecapitulatif.EN_ATTENTE,
    )
    cree_le: Mapped[datetime] = mapped_column(default=maintenant_utc, nullable=False)
    validee_par: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    validee_le: Mapped[datetime | None] = mapped_column(nullable=True)
    envoyee_le: Mapped[datetime | None] = mapped_column(nullable=True)

    def __repr__(self) -> str:  # jamais le contenu (règle 5)
        return f"<ValidationRecapitulatif id={self.id} statut={self.statut}>"
