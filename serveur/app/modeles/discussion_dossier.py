"""Modèle ORM de l'espace de discussion et d'avis sur le dossier d'un candidat.

Sécurité et confidentialité :
- Isolé par bureau (`MixinTenant`).
- Le contenu des messages est chiffré au repos en AES-256-GCM avec la clé du bureau.
- Aucun nom, passeport ou e-mail n'est transmis à l'extérieur ni écrit dans les logs.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MixinHorodatage, MixinIdentifiant, MixinTenant


class AuteurMessageDossier(str, enum.Enum):
    UTILISATEUR = "utilisateur"
    ASSISTANT = "assistant"


def _valeurs(enum_cls: type[enum.Enum]) -> list[str]:
    return [m.value for m in enum_cls]


class MessageDiscussionDossier(MixinIdentifiant, MixinTenant, MixinHorodatage, Base):
    __tablename__ = "messages_discussion_dossier"

    candidat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code_demarche: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    auteur: Mapped[AuteurMessageDossier] = mapped_column(
        Enum(
            AuteurMessageDossier,
            native_enum=False,
            length=16,
            values_callable=_valeurs,
            create_constraint=True,
            name="auteur_message_dossier",
        ),
        nullable=False,
    )
    utilisateur_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    contenu_chiffre: Mapped[str] = mapped_column(Text, nullable=False)
    score_solidite_pourcent: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"<MessageDiscussionDossier id={self.id} auteur={self.auteur.value}>"
