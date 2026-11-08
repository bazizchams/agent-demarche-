"""Utilisateurs de la plateforme (personnel d'un bureau) et rôles."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MixinHorodatage, MixinIdentifiant, MixinTenant


class Role(str, enum.Enum):
    ADMINISTRATEUR = "administrateur"
    EMPLOYE = "employe"
    LECTURE_SEULE = "lecture_seule"


def _valeurs(enum_cls: type[enum.Enum]) -> list[str]:
    return [m.value for m in enum_cls]


class Utilisateur(MixinIdentifiant, MixinTenant, MixinHorodatage, Base):
    __tablename__ = "utilisateurs"
    __table_args__ = (
        CheckConstraint("echecs_connexion >= 0", name="echecs_positifs"),
    )

    # Unique sur toute la plateforme : l'e-mail sert d'identifiant de connexion.
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    nom_affiche: Mapped[str] = mapped_column(String(120), nullable=False)
    empreinte_mot_de_passe: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(
        Enum(Role, native_enum=False, length=20, values_callable=_valeurs,
             create_constraint=True, name="role"),
        nullable=False,
    )
    actif: Mapped[bool] = mapped_column(default=True, nullable=False)
    # Vrai après création par un administrateur ou réinitialisation : l'utilisateur
    # doit choisir son propre mot de passe avant toute autre action.
    doit_changer_mot_de_passe: Mapped[bool] = mapped_column(default=True, nullable=False)
    echecs_connexion: Mapped[int] = mapped_column(default=0, nullable=False)
    verrouille_jusqua: Mapped[datetime | None] = mapped_column(nullable=True)
    derniere_connexion_le: Mapped[datetime | None] = mapped_column(nullable=True)

    def __repr__(self) -> str:  # jamais l'e-mail ni le nom (règle 5)
        return f"<Utilisateur id={self.id} role={self.role.value if self.role else None}>"

