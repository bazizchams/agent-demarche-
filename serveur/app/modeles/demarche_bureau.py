"""Modèle ORM `DemarcheBureau` (`demarches_bureaux`) : démarches définies par un bureau.

Une démarche stockée ici complète ou remplace, pour CE bureau uniquement, la démarche
de même code fournie par les fichiers YAML de base (`config/demarches/*.yaml`).
Le contenu (`definition`) est validé par `ConfigDemarche` avant chaque écriture, ce qui
permet à un bureau d'ajouter ou de modifier une procédure sans redéploiement.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MixinHorodatage, MixinIdentifiant, MixinTenant


class DemarcheBureau(MixinIdentifiant, MixinTenant, MixinHorodatage, Base):
    __tablename__ = "demarches_bureaux"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_demarches_bureaux_tenant_code"),
    )

    code: Mapped[str] = mapped_column(String(60), nullable=False)
    # Compteur incrémenté à chaque modification (traçabilité simple des changements).
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Faux = la démarche est masquée pour ce bureau (même si elle existe en YAML de base).
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
