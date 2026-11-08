"""Modèles ORM de la Phase 6 :
- `AbonnementBureau` (`abonnements_bureaux`) : forfait SaaS mensuel, quota de dossiers,
  identifiants Stripe (`stripe_customer_id`, `stripe_subscription_id`), acceptation des
  Conditions Générales d'Utilisation (CGU) et politique de durée de conservation des données.
- `PreuveConsentementCandidat` (`preuves_consentement_candidats`) : traçabilité probante
  du recueil et du retrait du consentement des candidats (conformité Loi algérienne 18-07).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import (
    Base,
    MixinHorodatage,
    MixinIdentifiant,
    MixinTenant,
    maintenant_utc,
)


class ForfaitAbonnement(str, enum.Enum):
    STARTER = "starter"
    PROFESSIONNEL = "professionnel"
    ENTREPRISE = "entreprise"


class AbonnementBureau(MixinIdentifiant, MixinTenant, MixinHorodatage, Base):
    __tablename__ = "abonnements_bureaux"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_abonnements_bureaux_tenant"),
    )

    forfait: Mapped[ForfaitAbonnement] = mapped_column(
        Enum(
            ForfaitAbonnement,
            native_enum=False,
            length=30,
            values_callable=lambda e: [m.value for m in e],
            create_constraint=True,
            name="forfait_abonnement",
        ),
        default=ForfaitAbonnement.STARTER,
        nullable=False,
    )
    quota_dossiers_mensuels: Mapped[int] = mapped_column(
        Integer, default=30, nullable=False
    )
    prix_mensuel_eur: Mapped[int] = mapped_column(
        Integer, default=49, nullable=False
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(120), nullable=True, index=True
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(120), nullable=True, index=True
    )
    statut_stripe: Mapped[str] = mapped_column(
        String(40), default="trialing", nullable=False
    )
    periode_courante_fin: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Acceptation des Conditions Générales d'Utilisation (CGU) par le bureau
    cgu_version_acceptee: Mapped[str | None] = mapped_column(
        String(40), nullable=True
    )
    cgu_acceptees_le: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cgu_acceptees_par_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )

    # Politique de conservation des dossiers archivés avant purge définitive (Loi 18-07)
    duree_conservation_jours: Mapped[int] = mapped_column(
        Integer, default=365, nullable=False
    )


class PreuveConsentementCandidat(MixinIdentifiant, MixinTenant, Base):
    __tablename__ = "preuves_consentement_candidats"

    candidat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_texte_consentement: Mapped[str] = mapped_column(
        String(40), nullable=False
    )
    mode_recueil: Mapped[str] = mapped_column(
        String(60), nullable=False
    )
    empreinte_texte_sha256: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    recueilli_par_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    recueilli_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=maintenant_utc, nullable=False
    )
    revoque_le: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
