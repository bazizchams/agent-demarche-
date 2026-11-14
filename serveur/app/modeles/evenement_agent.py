"""Événements de la discussion de l'agent (panneau Co-Pilote en direct) pour une tâche.

Principes :
- texte court CHIFFRÉ (AES-256-GCM, clé du bureau) ; aucune donnée personnelle ni valeur de formulaire
  sensible : le texte est masqué avant stockage (`services/evenements_agent.py`) ;
- `seq` : numéro croissant par tâche, sert de curseur (`depuis`) pour l'interrogation et le flux SSE ;
- `code` : code technique court (jamais une donnée personnelle) : commande `pause|reprise|arret|premier_plan`
  ou drapeau `refusee` sur une consigne contraire aux règles 1/2/3/6 ;
- `traite_le` : instant où l'agent a pris connaissance d'une consigne ou d'une commande de l'humain ;
- purge automatique après 7 jours.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MixinHorodatage, MixinIdentifiant, MixinTenant


class TypeEvenementAgent(str, enum.Enum):
    AGENT = "agent"
    ACTION = "action"
    ALERTE = "alerte"
    DEMANDE_HUMAINE = "demande_humaine"
    UTILISATEUR = "utilisateur"
    COMMANDE = "commande"


class AuteurEvenement(str, enum.Enum):
    AGENT = "agent"
    HUMAIN = "humain"


CODES_COMMANDE = ("pause", "reprise", "arret", "premier_plan")
CODE_CONSIGNE_REFUSEE = "refusee"
LONGUEUR_MAX_TEXTE = 500


class EvenementAgent(MixinIdentifiant, MixinTenant, MixinHorodatage, Base):
    __tablename__ = "evenements_agent"
    __table_args__ = (
        UniqueConstraint("tenant_id", "tache_id", "seq", name="uq_evenements_agent_seq"),
        CheckConstraint(
            "type IN ('agent','action','alerte','demande_humaine','utilisateur','commande')",
            name="type_valide",
        ),
        CheckConstraint("auteur IN ('agent','humain')", name="auteur_valide"),
        Index("ix_evenements_agent_tache_seq", "tenant_id", "tache_id", "seq"),
        Index("ix_evenements_agent_cree_le", "cree_le"),
    )

    tache_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taches_dossiers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    auteur: Mapped[str] = mapped_column(String(10), nullable=False)
    code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    texte_chiffre: Mapped[str] = mapped_column(Text, nullable=False)
    traite_le: Mapped[datetime | None] = mapped_column(nullable=True)
