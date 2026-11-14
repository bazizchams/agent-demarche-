"""Modèle ORM d'un Agent Local (poste de travail Windows autorisé à exécuter Playwright).

Architecture cible :
- Le serveur ne pilote jamais les portails officiels depuis un datacenter.
- L'agent local sur le PC du bureau s'authentifie auprès du serveur via un jeton
  propre au bureau (stocké uniquement sous forme d'empreinte SHA-256 en base).
- Isolé par bureau (`MixinTenant`).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MixinHorodatage, MixinIdentifiant, MixinTenant, maintenant_utc

# Un agent qui sonde le serveur toutes les quelques secondes est « en ligne » tant que son dernier
# signe de vie date de moins de ce délai.
DELAI_AGENT_EN_LIGNE_SECONDES = 90


class AgentLocal(MixinIdentifiant, MixinTenant, MixinHorodatage, Base):
    __tablename__ = "agents_locaux"

    nom_machine: Mapped[str] = mapped_column(String(120), nullable=False)
    empreinte_jeton: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cree_par_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    derniere_activite_le: Mapped[datetime | None] = mapped_column(nullable=True)

    @property
    def en_ligne(self) -> bool:
        if not self.actif or self.derniere_activite_le is None:
            return False
        ecart = maintenant_utc() - self.derniere_activite_le
        return ecart.total_seconds() <= DELAI_AGENT_EN_LIGNE_SECONDES

    def __repr__(self) -> str:
        return f"<AgentLocal id={self.id} nom_machine={self.nom_machine!r} actif={self.actif}>"
