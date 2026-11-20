"""Échanges temporaires autour du coffre d'identifiants portail (Règle 3), liés à UNE tâche de l'agent local.

Deux natures, une seule table :
- `autorisation_lecture` : consentement explicite donné dans l'interface web pour CETTE tâche (« Autoriser l'agent à se
  connecter »). Valable `DUREE_AUTORISATION_S` secondes, à usage unique (`utilise_le` posé par un compare-and-swap).
  Elle ne contient AUCUN identifiant ;
- `depot_a_enregistrer` : identifiants lus par l'agent dans le formulaire du portail au moment où l'humain l'a
  soumis, en attente de la décision de l'humain dans l'interface web (enregistrer dans le coffre ou refuser).
  Chiffrés (AES-256-GCM, clé du bureau, noms de champ distincts), valables `DUREE_DEPOT_S` secondes puis purgés ;
  supprimés dès l'enregistrement ou le refus. Jamais en clair, jamais renvoyés par une route.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MixinHorodatage, MixinIdentifiant, MixinTenant

DUREE_AUTORISATION_S = 60
DUREE_DEPOT_S = 600

CHAMP_ECHANGE_IDENTIFIANT = "echange_coffre.identifiant"
CHAMP_ECHANGE_MOT_DE_PASSE = "echange_coffre.mot_de_passe"


class NatureEchange(str, enum.Enum):
    AUTORISATION_LECTURE = "autorisation_lecture"
    DEPOT_A_ENREGISTRER = "depot_a_enregistrer"


class EchangeCoffre(MixinIdentifiant, MixinTenant, MixinHorodatage, Base):
    __tablename__ = "echanges_coffre"
    __table_args__ = (
        CheckConstraint(
            "nature IN ('autorisation_lecture','depot_a_enregistrer')", name="nature_valide"
        ),
        Index("ix_echanges_coffre_tache_nature", "tenant_id", "tache_id", "nature"),
    )

    tache_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taches_dossiers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    portail: Mapped[str] = mapped_column(String(40), nullable=False)
    nature: Mapped[str] = mapped_column(String(30), nullable=False)
    # Humain qui a donné le consentement (autorisation) ; agent qui a déposé (dépôt).
    accorde_par_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    agent_local_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents_locaux.id", ondelete="SET NULL"), nullable=True
    )
    expire_le: Mapped[datetime] = mapped_column(nullable=False)
    utilise_le: Mapped[datetime | None] = mapped_column(nullable=True)
    identifiant_chiffre: Mapped[str | None] = mapped_column(Text, nullable=True)
    mot_de_passe_chiffre: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        # Jamais de valeur chiffrée dans la représentation.
        return f"<EchangeCoffre id={self.id} nature={self.nature} portail={self.portail}>"
