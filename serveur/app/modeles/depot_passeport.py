"""Dépôt de passeport « en attente de fiche » (table `depots_passeport`).

Un passeport déposé AVANT que la fiche de l'étudiant existe est conservé ici, chiffré, le temps
que l'humain confirme (ou corrige) les valeurs proposées. Principes :
- le fichier est chiffré sur disque (AES-256-GCM, clé du bureau) ; le nom d'origine et les
  propositions (valeurs + extraits MRZ) sont chiffrés en base : rien de personnel en clair (règle 5) ;
- les propositions ne sont JAMAIS une fiche : seule une confirmation humaine crée le candidat (règles 1 et 4) ;
- un dépôt non converti est purgé après 24 h (fichier et ligne).
"""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MixinHorodatage, MixinIdentifiant, MixinTenant

STATUT_PROPOSE = "propose"  # MRZ lue et tous ses chiffres de contrôle sont corrects
STATUT_SAISIE_MANUELLE = "saisie_manuelle"  # MRZ absente, illisible ou invalide : saisie humaine


class DepotPasseport(MixinIdentifiant, MixinTenant, MixinHorodatage, Base):
    __tablename__ = "depots_passeport"
    __table_args__ = (
        CheckConstraint("statut IN ('propose','saisie_manuelle')", name="statut_valide"),
        CheckConstraint("taille_octets > 0", name="taille_positive"),
        Index("ix_depots_passeport_cree_le", "cree_le"),
    )

    depose_par_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    nom_fichier_chiffre: Mapped[str] = mapped_column(Text, nullable=False)
    type_mime: Mapped[str] = mapped_column(String(100), nullable=False)
    taille_octets: Mapped[int] = mapped_column(Integer, nullable=False)
    empreinte_contenu: Mapped[str] = mapped_column(String(64), nullable=False)
    chemin_stockage_relatif: Mapped[str] = mapped_column(String(255), nullable=False)
    statut: Mapped[str] = mapped_column(String(20), nullable=False)
    propositions_chiffrees: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # jamais de donnée personnelle (règle 5)
        return f"<DepotPasseport id={self.id} statut={self.statut}>"
