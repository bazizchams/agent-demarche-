"""Modèle ORM d'un candidat (étudiant accompagné par le bureau).

Sécurité et conformité :
- Aucun champ n'a de valeur métier par défaut inventée (règle 4) : si une donnée
  (date de naissance, lieu de naissance, sexe, pays, passeport…) n'est pas fournie,
  elle reste `None` (`NULL` en base).
- Les données personnelles identifiantes sont chiffrées au repos en AES-256-GCM
  avec une clé propre au bureau et un contexte AAD lié au `tenant_id` et au nom de colonne.
- Les recherches par nom, prénom, e-mail ou numéro de passeport utilisent des
  index aveugles HMAC-SHA256 (`idx_*`) calculés avec la clé d'index du bureau.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, Enum, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, MixinHorodatage, MixinIdentifiant, MixinTenant


class SexeCandidat(str, enum.Enum):
    MASCULIN = "M"
    FEMININ = "F"


class StatutCandidat(str, enum.Enum):
    ACTIF = "actif"
    ARCHIVE = "archive"


def _valeurs(enum_cls: type[enum.Enum]) -> list[str]:
    return [m.value for m in enum_cls]


class Candidat(MixinIdentifiant, MixinTenant, MixinHorodatage, Base):
    __tablename__ = "candidats"
    __table_args__ = (
        CheckConstraint(
            "fonds_disponibles_eur IS NULL OR fonds_disponibles_eur >= 0",
            name="fonds_positifs",
        ),
        Index("ix_candidats_tenant_idx_nom", "tenant_id", "idx_nom"),
        Index("ix_candidats_tenant_idx_prenom", "tenant_id", "idx_prenom"),
        Index("ix_candidats_tenant_idx_email", "tenant_id", "idx_email"),
        Index("ix_candidats_tenant_idx_passeport", "tenant_id", "idx_passeport"),
    )

    # Champs personnels chiffrés (AES-256-GCM)
    nom_chiffre: Mapped[str] = mapped_column(Text, nullable=False)
    prenom_chiffre: Mapped[str] = mapped_column(Text, nullable=False)
    date_naissance_chiffree: Mapped[str | None] = mapped_column(Text, nullable=True)
    lieu_naissance_chiffre: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_chiffre: Mapped[str | None] = mapped_column(Text, nullable=True)
    telephone_chiffre: Mapped[str | None] = mapped_column(Text, nullable=True)
    numero_passeport_chiffre: Mapped[str | None] = mapped_column(Text, nullable=True)
    adresse_chiffree: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes_internes_chiffrees: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Index aveugles HMAC-SHA256 par bureau (recherche sans déchiffrement intégral)
    idx_nom: Mapped[str] = mapped_column(String(64), nullable=False)
    idx_prenom: Mapped[str] = mapped_column(String(64), nullable=False)
    idx_email: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idx_passeport: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Données structurées de dossier (jamais de valeur par défaut inventée — règle 4)
    sexe: Mapped[SexeCandidat | None] = mapped_column(
        Enum(
            SexeCandidat,
            native_enum=False,
            length=4,
            values_callable=_valeurs,
            create_constraint=True,
            name="sexe_candidat",
        ),
        nullable=True,
    )
    nationalite: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pays_residence: Mapped[str | None] = mapped_column(String(100), nullable=True)
    date_expiration_passeport: Mapped[date | None] = mapped_column(Date, nullable=True)
    niveau_actuel: Mapped[str | None] = mapped_column(String(160), nullable=True)
    programme_vise: Mapped[str | None] = mapped_column(String(200), nullable=True)
    etablissement_vise: Mapped[str | None] = mapped_column(String(200), nullable=True)
    fonds_disponibles_eur: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Consentement au traitement des données (loi 18-07 / bonnes pratiques)
    consentement_signe: Mapped[bool] = mapped_column(default=False, nullable=False)
    date_consentement: Mapped[datetime | None] = mapped_column(nullable=True)

    # Cycle de vie et archivage
    statut: Mapped[StatutCandidat] = mapped_column(
        Enum(
            StatutCandidat,
            native_enum=False,
            length=16,
            values_callable=_valeurs,
            create_constraint=True,
            name="statut_candidat",
        ),
        default=StatutCandidat.ACTIF,
        nullable=False,
        index=True,
    )
    archive_le: Mapped[datetime | None] = mapped_column(nullable=True)

    documents = relationship(
        "DocumentCandidat",
        back_populates="candidat",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # jamais de donnée personnelle (règle 5)
        return f"<Candidat id={self.id} statut={self.statut.value if self.statut else None}>"


__all__ = ["Candidat", "SexeCandidat", "StatutCandidat", "uuid"]
