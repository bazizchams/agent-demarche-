"""Modèles ORM des déductions vérifiables (phase P2) et du projet professionnel (phase P3).

Principes (règles 4 et 5) :
- un point fort n'existe QUE s'il cite sa pièce : `document_id` et `extrait_chiffre` sont
  obligatoires (contrainte en base) ; le texte et l'extrait sont CHIFFRÉS (clé du bureau) ;
- le statut décide de l'usage : seuls les points `confirme` (décision humaine) alimentent le
  projet professionnel ; `alerte` est un code technique, jamais une donnée personnelle ;
- le projet professionnel est un brouillon chiffré versionné ; la validation est humaine.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MixinHorodatage, MixinIdentifiant, MixinTenant


class StatutPointFort(str, enum.Enum):
    A_VERIFIER = "a_verifier"
    CONFIRME = "confirme"
    REJETE = "rejete"


class StatutProjet(str, enum.Enum):
    BROUILLON = "brouillon"
    VALIDE = "valide"


def _valeurs(enum_cls: type[enum.Enum]) -> list[str]:
    return [m.value for m in enum_cls]


class PointFort(MixinIdentifiant, MixinTenant, MixinHorodatage, Base):
    __tablename__ = "points_forts_candidats"
    __table_args__ = (
        UniqueConstraint("tenant_id", "candidat_id", "cle", name="uq_points_forts_candidats_cle"),
        CheckConstraint("extrait_chiffre <> ''", name="preuve_obligatoire"),
    )

    candidat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents_candidats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    categorie: Mapped[str] = mapped_column(String(20), nullable=False)
    regle: Mapped[str] = mapped_column(String(40), nullable=False)
    cle: Mapped[str] = mapped_column(String(64), nullable=False)
    texte_chiffre: Mapped[str] = mapped_column(Text, nullable=False)
    extrait_chiffre: Mapped[str] = mapped_column(Text, nullable=False)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    statut: Mapped[StatutPointFort] = mapped_column(
        Enum(
            StatutPointFort,
            native_enum=False,
            length=16,
            values_callable=_valeurs,
            create_constraint=True,
            name="statut_point_fort",
        ),
        nullable=False,
        index=True,
    )
    alerte: Mapped[str | None] = mapped_column(String(40), nullable=True)
    champ_fiche: Mapped[str | None] = mapped_column(String(20), nullable=True)
    valeur_fiche: Mapped[str | None] = mapped_column(String(2), nullable=True)
    decide_par_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    decide_le: Mapped[datetime | None] = mapped_column(nullable=True)
    applique_le: Mapped[datetime | None] = mapped_column(nullable=True)

    def __repr__(self) -> str:  # jamais le texte (règle 5)
        return f"<PointFort id={self.id} regle={self.regle} statut={self.statut.value}>"


class ProjetProfessionnel(MixinIdentifiant, MixinTenant, MixinHorodatage, Base):
    __tablename__ = "projets_professionnels"
    __table_args__ = (
        UniqueConstraint("tenant_id", "candidat_id", name="uq_projets_professionnels_candidat"),
        CheckConstraint("version >= 1", name="version_positive"),
    )

    candidat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    texte_chiffre: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    statut: Mapped[StatutProjet] = mapped_column(
        Enum(
            StatutProjet,
            native_enum=False,
            length=12,
            values_callable=_valeurs,
            create_constraint=True,
            name="statut_projet",
        ),
        nullable=False,
    )
    origine: Mapped[str] = mapped_column(String(10), nullable=False)
    valide_par_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    valide_le: Mapped[datetime | None] = mapped_column(nullable=True)

    def __repr__(self) -> str:  # jamais le texte (règle 5)
        return f"<ProjetProfessionnel id={self.id} v={self.version} statut={self.statut.value}>"
