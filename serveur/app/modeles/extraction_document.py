"""Modèle ORM d'une valeur lue dans un document (table `extractions_documents`).

Principes (règles 4 et 5) :
- une ligne = un champ lu dans un document ; aucune valeur par défaut : un champ non lu n'a
  pas de ligne ;
- la valeur, la valeur alternative du second lecteur et l'extrait littéral du document sont
  CHIFFRÉS (AES-256-GCM, clé du bureau) : ils contiennent des données personnelles ;
- le statut décide de ce qui peut atteindre la fiche : seuls `auto` et `valide_humain` sont
  applicables ; `a_verifier` et `rejete` ne le sont jamais ;
- le `motif` est un code technique (jamais une donnée personnelle).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MixinHorodatage, MixinIdentifiant, MixinTenant


class StatutExtraction(str, enum.Enum):
    AUTO = "auto"
    A_VERIFIER = "a_verifier"
    VALIDE_HUMAIN = "valide_humain"
    REJETE = "rejete"


STATUTS_APPLICABLES = frozenset({StatutExtraction.AUTO, StatutExtraction.VALIDE_HUMAIN})


def _valeurs(enum_cls: type[enum.Enum]) -> list[str]:
    return [m.value for m in enum_cls]


class ExtractionDocument(MixinIdentifiant, MixinTenant, MixinHorodatage, Base):
    __tablename__ = "extractions_documents"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "document_id", "champ", name="uq_extractions_documents_champ_par_document"
        ),
        CheckConstraint("source IN ('A', 'B')", name="source_lecteur"),
        CheckConstraint("confiance >= 0 AND confiance <= 1", name="confiance_bornee"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents_candidats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    champ: Mapped[str] = mapped_column(String(60), nullable=False)
    valeur_chiffree: Mapped[str] = mapped_column(Text, nullable=False)
    valeur_alternative_chiffree: Mapped[str | None] = mapped_column(Text, nullable=True)
    extrait_chiffre: Mapped[str] = mapped_column(Text, nullable=False)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(1), nullable=False)
    confiance: Mapped[float] = mapped_column(Float, nullable=False)
    statut: Mapped[StatutExtraction] = mapped_column(
        Enum(
            StatutExtraction,
            native_enum=False,
            length=16,
            values_callable=_valeurs,
            create_constraint=True,
            name="statut_extraction",
        ),
        nullable=False,
        index=True,
    )
    motif: Mapped[str | None] = mapped_column(String(60), nullable=True)
    decide_par_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    decide_le: Mapped[datetime | None] = mapped_column(nullable=True)
    applique_le: Mapped[datetime | None] = mapped_column(nullable=True)

    def __repr__(self) -> str:  # jamais la valeur (règle 5)
        return f"<ExtractionDocument id={self.id} champ={self.champ} statut={self.statut.value}>"
