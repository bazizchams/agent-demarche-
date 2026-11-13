"""Rappels d'échéance déjà envoyés (garantie d'idempotence de l'envoi).

Une ligne = « le rappel (démarche, échéance, seuil en jours) a été envoyé pour la date
d'échéance donnée ». La contrainte d'unicité empêche tout second envoi, même si deux
exécutions du déclencheur se chevauchent. La date d'échéance fait partie de la clé pour qu'une
échéance qui revient l'année suivante (même code) puisse être rappelée de nouveau.

Règle 5 : aucune donnée personnelle ici (ni candidat, ni destinataire, ni adresse) :
uniquement des codes de configuration et des dates.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MixinIdentifiant, MixinTenant, maintenant_utc


class RappelEcheanceEnvoye(MixinIdentifiant, MixinTenant, Base):
    __tablename__ = "rappels_echeances_envoyes"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "code_demarche",
            "code_echeance",
            "seuil_jours",
            "date_echeance",
            name="uq_rappels_echeances_envoyes_rappel",
        ),
    )

    code_demarche: Mapped[str] = mapped_column(String(60), nullable=False)
    code_echeance: Mapped[str] = mapped_column(String(60), nullable=False)
    seuil_jours: Mapped[int] = mapped_column(Integer, nullable=False)
    date_echeance: Mapped[date] = mapped_column(Date, nullable=False)
    envoye_le: Mapped[datetime] = mapped_column(default=maintenant_utc, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<RappelEcheanceEnvoye demarche={self.code_demarche} "
            f"echeance={self.code_echeance} seuil={self.seuil_jours}>"
        )
