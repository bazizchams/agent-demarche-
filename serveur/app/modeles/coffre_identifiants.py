"""Modele ORM `IdentifiantPortail` (`identifiants_portail`) : coffre chiffre des identifiants
de connexion d'un candidat aux portails officiels (Etudes en France, IRCC).

Regle 3 : identifiant et mot de passe ne sont JAMAIS stockes en clair (AES-256-GCM, cle du bureau,
nom de champ distinct par colonne), jamais renvoyes par l'API, jamais journalises. Le
consentement ecrit du candidat est obligatoire et trace (date + utilisateur authentifie).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MixinIdentifiant, MixinTenant, maintenant_utc

CHAMP_IDENTIFIANT = "identifiant_portail.identifiant"
CHAMP_MOT_DE_PASSE = "identifiant_portail.mot_de_passe"


class IdentifiantPortail(MixinIdentifiant, MixinTenant, Base):
    __tablename__ = "identifiants_portail"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "candidat_id", "portail", name="uq_identifiants_portail_tenant_candidat_portail"
        ),
    )

    candidat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    portail: Mapped[str] = mapped_column(String(40), nullable=False)
    identifiant_chiffre: Mapped[str] = mapped_column(Text, nullable=False)
    mot_de_passe_chiffre: Mapped[str] = mapped_column(Text, nullable=False)
    consentement_recueilli_le: Mapped[datetime] = mapped_column(nullable=False)
    consentement_par: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False
    )
    cree_le: Mapped[datetime] = mapped_column(default=maintenant_utc, nullable=False)
    mis_a_jour_le: Mapped[datetime] = mapped_column(
        default=maintenant_utc, onupdate=maintenant_utc, nullable=False
    )

    def __repr__(self) -> str:
        # Jamais de secret ni de valeur chiffree dans la representation.
        return f"<IdentifiantPortail id={self.id} portail={self.portail}>"
