"""Bureau d'études = tenant. Seule table métier SANS tenant_id (elle EST le tenant)."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MixinHorodatage, MixinIdentifiant


class Bureau(MixinIdentifiant, MixinHorodatage, Base):
    __tablename__ = "bureaux"

    nom: Mapped[str] = mapped_column(String(200), nullable=False)
    # Identifiant court et stable (ex. « bureau-alger-centre »), unique sur la plateforme.
    slug: Mapped[str] = mapped_column(String(63), nullable=False, unique=True)
    # Faux = abonnement suspendu : plus aucune session n'est acceptée pour ce bureau.
    actif: Mapped[bool] = mapped_column(default=True, nullable=False)
