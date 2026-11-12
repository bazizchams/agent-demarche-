"""Modele ORM `VoeuFormation` (`voeux_formations`) : panier de voeux Campus France d'un candidat.

Securite : isole par bureau (`MixinTenant`) ; le texte de motivation est chiffre au repos
(AES-256-GCM, cle du bureau). Aucune motivation n'est jamais generee par defaut (regle 4).
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MixinHorodatage, MixinIdentifiant, MixinTenant

MAX_VOEUX = 7
MAX_CARACTERES_MOTIVATION = 4000


class VoieVoeu(str, enum.Enum):
    DAP_BLANCHE = "dap_blanche"
    DAP_JAUNE = "dap_jaune"
    HORS_DAP = "hors_dap"


class StatutVoeu(str, enum.Enum):
    BROUILLON = "brouillon"
    VALIDE = "valide"
    AJOUTE_AU_PANIER = "ajoute_au_panier"


def _valeurs(enum_cls: type[enum.Enum]) -> list[str]:
    return [m.value for m in enum_cls]


class VoeuFormation(MixinIdentifiant, MixinTenant, MixinHorodatage, Base):
    __tablename__ = "voeux_formations"
    __table_args__ = (
        UniqueConstraint(
            "candidat_id",
            "intitule",
            "etablissement",
            name="uq_voeux_formations_candidat_intitule_etablissement",
        ),
        CheckConstraint("rang >= 1 AND rang <= 7", name="rang_voeu"),
    )

    candidat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rang: Mapped[int] = mapped_column(Integer, nullable=False)
    intitule: Mapped[str] = mapped_column(String(250), nullable=False)
    etablissement: Mapped[str] = mapped_column(String(200), nullable=False)
    niveau: Mapped[str] = mapped_column(String(40), nullable=False)
    voie: Mapped[VoieVoeu] = mapped_column(
        Enum(
            VoieVoeu,
            native_enum=False,
            length=16,
            values_callable=_valeurs,
            create_constraint=True,
            name="voie_voeu",
        ),
        default=VoieVoeu.HORS_DAP,
        nullable=False,
    )
    url_source: Mapped[str | None] = mapped_column(String(500), nullable=True)
    justification: Mapped[str | None] = mapped_column(String(500), nullable=True)
    motivation_chiffree: Mapped[str | None] = mapped_column(Text, nullable=True)
    statut: Mapped[StatutVoeu] = mapped_column(
        Enum(
            StatutVoeu,
            native_enum=False,
            length=20,
            values_callable=_valeurs,
            create_constraint=True,
            name="statut_voeu",
        ),
        default=StatutVoeu.BROUILLON,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<VoeuFormation id={self.id} rang={self.rang} statut={self.statut.value}>"
