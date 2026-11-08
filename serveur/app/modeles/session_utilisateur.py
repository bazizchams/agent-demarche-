"""Sessions de connexion côté serveur (révocables immédiatement)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, MixinIdentifiant, MixinTenant, maintenant_utc
from app.modeles.utilisateur import Utilisateur


class SessionUtilisateur(MixinIdentifiant, MixinTenant, Base):
    __tablename__ = "sessions_utilisateurs"

    utilisateur_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Empreinte SHA-256 du jeton : le jeton lui-même n'est jamais stocké.
    empreinte_jeton: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    jeton_csrf: Mapped[str] = mapped_column(String(64), nullable=False)
    cree_le: Mapped[datetime] = mapped_column(default=maintenant_utc, nullable=False)
    expire_le: Mapped[datetime] = mapped_column(nullable=False)
    derniere_activite_le: Mapped[datetime] = mapped_column(default=maintenant_utc, nullable=False)
    revoquee_le: Mapped[datetime | None] = mapped_column(nullable=True)

    utilisateur: Mapped[Utilisateur] = relationship(lazy="joined")
