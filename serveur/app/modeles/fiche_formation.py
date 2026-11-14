"""Modèle ORM `FicheFormation` (`fiches_formations`) : cache de fiches de formation par bureau.

Une fiche = ce qui a été LU sur une source officielle (établissement, intitulé, niveau d'entrée, langue
exigée, moyenne, date limite, pièces, URL officielle) avec sa date de relevé. Toute exigence non lue reste
NULL et la fiche est au statut « à vérifier » (règle 4 : jamais de valeur inventée).

Sécurité : isolé par bureau (`MixinTenant`) ; aucune donnée personnelle (règle 5).
"""

from __future__ import annotations

import enum
from datetime import date

from sqlalchemy import JSON, Boolean, CheckConstraint, Date, Enum, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MixinHorodatage, MixinIdentifiant, MixinTenant


class StatutFiche(str, enum.Enum):
    VERIFIE = "verifie"
    A_VERIFIER = "a_verifier"


def _valeurs(enum_cls: type[enum.Enum]) -> list[str]:
    return [m.value for m in enum_cls]


class FicheFormation(MixinIdentifiant, MixinTenant, MixinHorodatage, Base):
    __tablename__ = "fiches_formations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "cle", name="uq_fiches_formations_tenant_cle"),
        CheckConstraint(
            "moyenne_min IS NULL OR (moyenne_min >= 0 AND moyenne_min <= 20)",
            name="moyenne_min_sur_20",
        ),
        CheckConstraint(
            "niveau_entree_bac_plus IS NULL OR (niveau_entree_bac_plus >= 1 AND niveau_entree_bac_plus <= 8)",
            name="niveau_entree_plage",
        ),
    )

    cle: Mapped[str] = mapped_column(String(520), nullable=False)
    etablissement: Mapped[str] = mapped_column(String(200), nullable=False)
    intitule: Mapped[str] = mapped_column(String(250), nullable=False)
    niveau_entree_bac_plus: Mapped[int | None] = mapped_column(Integer, nullable=True)
    niveau_entree_libelle: Mapped[str | None] = mapped_column(String(60), nullable=True)
    francais_min: Mapped[str | None] = mapped_column(String(2), nullable=True)
    anglais_min: Mapped[str | None] = mapped_column(String(2), nullable=True)
    priorite_c1: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    langue_texte: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    langue_ambigue: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    moyenne_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    moyenne_reference: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pieces: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    date_limite: Mapped[date | None] = mapped_column(Date, nullable=True)
    ferme: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    domaines: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    url_officielle: Mapped[str | None] = mapped_column(String(500), nullable=True)
    date_releve: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    aucune_exigence_confirmee: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    exigences_a_verifier: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    statut: Mapped[StatutFiche] = mapped_column(
        Enum(
            StatutFiche,
            native_enum=False,
            length=12,
            values_callable=_valeurs,
            create_constraint=True,
            name="statut_fiche",
        ),
        default=StatutFiche.A_VERIFIER,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<FicheFormation id={self.id} statut={self.statut.value}>"
