"""Modèle ORM d'un document justificatif rattaché à un candidat.

Principes :
- Chaque document porte un `type_piece` explicite (attribué à l'import ou au dépôt,
  jamais deviné par sous-chaîne dans le nom de fichier).
- Le nom de fichier d'origine est chiffré en base (il contient souvent le nom du candidat).
- Le fichier binaire est stocké chiffré en AES-256-GCM sous
  `<dossier_stockage>/<tenant_id>/<candidat_id>/<document_id>.bin` (aucune donnée personnelle
  dans le chemin sur disque).
- L'empreinte `empreinte_contenu` (HMAC-SHA256 par bureau) empêche tout doublon
  binaire pour un même candidat (`uq_documents_candidats_doublon`).
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, MixinHorodatage, MixinIdentifiant, MixinTenant
from app.modeles.candidat import Candidat


class DocumentCandidat(MixinIdentifiant, MixinTenant, MixinHorodatage, Base):
    __tablename__ = "documents_candidats"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "candidat_id",
            "empreinte_contenu",
            name="uq_documents_candidats_doublon",
        ),
        CheckConstraint("taille_octets > 0", name="taille_positive"),
    )

    candidat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type_piece: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    nom_fichier_origine_chiffre: Mapped[str] = mapped_column(Text, nullable=False)
    type_mime: Mapped[str] = mapped_column(String(100), nullable=False)
    taille_octets: Mapped[int] = mapped_column(Integer, nullable=False)
    empreinte_contenu: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    chemin_stockage_relatif: Mapped[str] = mapped_column(String(255), nullable=False)
    date_expiration: Mapped[date | None] = mapped_column(Date, nullable=True)
    ajoute_par_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )

    candidat: Mapped[Candidat] = relationship("Candidat", back_populates="documents")

    def __repr__(self) -> str:  # jamais le nom de fichier (règle 5)
        return f"<DocumentCandidat id={self.id} type_piece={self.type_piece}>"
