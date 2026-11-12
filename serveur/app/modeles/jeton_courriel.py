"""Jetons à usage unique envoyés par courriel (vérification d'adresse, mot de passe oublié).

Sécurité : seule l'empreinte SHA-256 du jeton est stockée (une fuite de la base ne permet
pas de rejouer un lien) ; le jeton clair n'existe que dans le courriel. Aucune adresse e-mail
n'est copiée dans cette table : le lien se fait par `utilisateur_id`.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MixinIdentifiant, MixinTenant, maintenant_utc


class ObjetJetonCourriel(str, enum.Enum):
    VERIFICATION_ADRESSE = "verification_adresse"
    REINITIALISATION_MOT_DE_PASSE = "reinitialisation_mot_de_passe"


class JetonCourriel(MixinIdentifiant, MixinTenant, Base):
    __tablename__ = "jetons_courriel"

    utilisateur_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    objet: Mapped[ObjetJetonCourriel] = mapped_column(
        Enum(
            ObjetJetonCourriel,
            native_enum=False,
            length=40,
            values_callable=lambda e: [m.value for m in e],
            create_constraint=True,
            name="objet_jeton_courriel",
        ),
        nullable=False,
    )
    empreinte: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    cree_le: Mapped[datetime] = mapped_column(default=maintenant_utc, nullable=False)
    expire_le: Mapped[datetime] = mapped_column(nullable=False)
    utilise_le: Mapped[datetime | None] = mapped_column(nullable=True)

    def __repr__(self) -> str:  # jamais l'empreinte ni l'adresse (règle 5)
        return f"<JetonCourriel id={self.id} objet={self.objet}>"
