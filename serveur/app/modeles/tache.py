"""Modèles ORM de la Phase 3 :
- `TacheDossier` : machine à états persistée (`en_attente -> en_cours -> suspendue -> a_valider -> terminee / annulee / en_erreur`)
- `EtapeTache` : journal des étapes d'une tâche pour reprise idempotente sans rejouer les étapes déjà faites
- `VerrouDossier` : bail exclusif (`lease lock`) empêchant deux tâches de modifier simultanément le même dossier candidat
- `DecisionValidationHumaine` : trace immuable de chaque validation ou rejet humain dans le Centre de validation humaine (Règle 1)

Toutes ces tables portent `MixinTenant` (`tenant_id` non nul et indexé) pour l'isolation stricte multi-bureaux.
Aucune donnée personnelle n'est stockée en clair : le récapitulatif de pré-remplissage, les détails d'étape
et les commentaires de validation sont chiffrés en AES-256-GCM avec la clé du bureau.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, MixinHorodatage, MixinIdentifiant, MixinTenant


class StatutTache(str, enum.Enum):
    EN_ATTENTE = "en_attente"
    EN_COURS = "en_cours"
    SUSPENDUE = "suspendue"
    A_VALIDER = "a_valider"
    TERMINEE = "terminee"
    ANNULEE = "annulee"
    EN_ERREUR = "en_erreur"


class MotifSuspensionTache(str, enum.Enum):
    DONNEE_MANQUANTE = "donnee_manquante"
    PIECE_MANQUANTE_OU_INVALIDE = "piece_manquante_ou_invalide"
    ACTION_UTILISATEUR_PORTAIL = "action_utilisateur_portail"
    SELECTEUR_PORTAIL_INTROUVABLE = "selecteur_portail_introuvable"
    REJET_VALIDATION_HUMAINE = "rejet_validation_humaine"
    AUTRE = "autre"


class StatutEtapeTache(str, enum.Enum):
    A_FAIRE = "a_faire"
    EN_COURS = "en_cours"
    TERMINEE = "terminee"
    SUSPENDUE = "suspendue"
    EN_ERREUR = "en_erreur"


class TypeDecisionValidation(str, enum.Enum):
    APPROUVEE = "approuvee"
    REJETEE = "rejetee"


ACTION_PREREMPLISSAGE = "preremplissage"
ACTION_AJOUTER_VOEUX_PANIER = "ajouter_voeux_panier"
# Actions « Ouvrir sur mon PC » : exécutées dans la fenêtre visible de l'Agent Local (sans étapes YAML).
ACTIONS_OUVERTURE_PC: frozenset[str] = frozenset({ACTION_AJOUTER_VOEUX_PANIER})


def _valeurs(enum_cls: type[enum.Enum]) -> list[str]:
    return [m.value for m in enum_cls]


class TacheDossier(MixinIdentifiant, MixinTenant, MixinHorodatage, Base):
    __tablename__ = "taches_dossiers"
    __table_args__ = (
        Index("ix_taches_dossiers_tenant_statut", "tenant_id", "statut"),
        Index("ix_taches_dossiers_tenant_candidat", "tenant_id", "candidat_id"),
    )

    candidat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code_demarche: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    # `preremplissage` (étapes YAML) ou une action « Ouvrir sur mon PC » (`ACTIONS_OUVERTURE_PC`).
    action: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default=ACTION_PREREMPLISSAGE,
        server_default=ACTION_PREREMPLISSAGE,
    )

    statut: Mapped[StatutTache] = mapped_column(
        Enum(
            StatutTache,
            native_enum=False,
            length=20,
            values_callable=_valeurs,
            create_constraint=True,
            name="statut_tache",
        ),
        default=StatutTache.EN_ATTENTE,
        nullable=False,
        index=True,
    )
    motif_suspension: Mapped[MotifSuspensionTache | None] = mapped_column(
        Enum(
            MotifSuspensionTache,
            native_enum=False,
            length=40,
            values_callable=_valeurs,
            create_constraint=True,
            name="motif_suspension_tache",
        ),
        nullable=True,
    )
    message_alerte: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Listes JSON de noms techniques de champs ou de types de pièces (aucune donnée personnelle)
    champs_manquants_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    pieces_manquantes_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Récapitulatif de pré-remplissage chiffré en AES-256-GCM (pour contrôle au Centre de validation humaine)
    recapitulatif_remplissage_chiffre: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    # Capture d'écran de contrôle chiffrée sur disque avant le bouton d'envoi final (Règles 1 & 6)
    chemin_capture_controle_relatif: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    type_mime_capture_controle: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    creee_par_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    agent_local_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents_locaux.id", ondelete="SET NULL"), nullable=True
    )

    demarree_le: Mapped[datetime | None] = mapped_column(nullable=True)
    suspendue_le: Mapped[datetime | None] = mapped_column(nullable=True)
    soumise_validation_le: Mapped[datetime | None] = mapped_column(nullable=True)
    terminee_le: Mapped[datetime | None] = mapped_column(nullable=True)

    etapes: Mapped[list["EtapeTache"]] = relationship(
        "EtapeTache",
        back_populates="tache",
        order_by="EtapeTache.ordre",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    decisions_validation: Mapped[list["DecisionValidationHumaine"]] = relationship(
        "DecisionValidationHumaine",
        back_populates="tache",
        order_by="DecisionValidationHumaine.cree_le",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return (
            f"<TacheDossier id={self.id} demarche={self.code_demarche} "
            f"statut={self.statut.value if self.statut else None}>"
        )


class EtapeTache(MixinIdentifiant, MixinTenant, MixinHorodatage, Base):
    __tablename__ = "etapes_taches"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "tache_id",
            "code_etape",
            name="uq_etapes_taches_code",
        ),
        UniqueConstraint(
            "tenant_id",
            "tache_id",
            "ordre",
            name="uq_etapes_taches_ordre",
        ),
        CheckConstraint("ordre >= 1", name="ordre_etape_positif"),
        CheckConstraint("nb_tentatives >= 0", name="nb_tentatives_positif"),
    )

    tache_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taches_dossiers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ordre: Mapped[int] = mapped_column(Integer, nullable=False)
    code_etape: Mapped[str] = mapped_column(String(80), nullable=False)
    libelle: Mapped[str] = mapped_column(String(200), nullable=False)

    statut: Mapped[StatutEtapeTache] = mapped_column(
        Enum(
            StatutEtapeTache,
            native_enum=False,
            length=20,
            values_callable=_valeurs,
            create_constraint=True,
            name="statut_etape_tache",
        ),
        default=StatutEtapeTache.A_FAIRE,
        nullable=False,
    )
    cle_idempotence: Mapped[str | None] = mapped_column(String(120), nullable=True)
    detail_execution_chiffre: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_erreur: Mapped[str | None] = mapped_column(String(500), nullable=True)
    nb_tentatives: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    commencee_le: Mapped[datetime | None] = mapped_column(nullable=True)
    terminee_le: Mapped[datetime | None] = mapped_column(nullable=True)

    tache: Mapped[TacheDossier] = relationship("TacheDossier", back_populates="etapes")

    def __repr__(self) -> str:
        return (
            f"<EtapeTache id={self.id} code={self.code_etape} "
            f"statut={self.statut.value if self.statut else None}>"
        )


class VerrouDossier(MixinIdentifiant, MixinTenant, MixinHorodatage, Base):
    __tablename__ = "verrous_dossiers"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "candidat_id",
            name="uq_verrous_dossiers_candidat",
        ),
    )

    candidat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tache_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taches_dossiers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    detenteur: Mapped[str] = mapped_column(String(120), nullable=False)
    acquis_le: Mapped[datetime] = mapped_column(nullable=False)
    expire_le: Mapped[datetime] = mapped_column(nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<VerrouDossier id={self.id} candidat_id={self.candidat_id} tache_id={self.tache_id}>"


class DecisionValidationHumaine(MixinIdentifiant, MixinTenant, MixinHorodatage, Base):
    __tablename__ = "decisions_validation_humaine"

    tache_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taches_dossiers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    decideur_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    decision: Mapped[TypeDecisionValidation] = mapped_column(
        Enum(
            TypeDecisionValidation,
            native_enum=False,
            length=20,
            values_callable=_valeurs,
            create_constraint=True,
            name="type_decision_validation",
        ),
        nullable=False,
    )
    confirmation_explicite: Mapped[bool] = mapped_column(Boolean, nullable=False)
    commentaire_chiffre: Mapped[str | None] = mapped_column(Text, nullable=True)
    reinitialiser_depuis_etape: Mapped[str | None] = mapped_column(
        String(80), nullable=True
    )

    tache: Mapped[TacheDossier] = relationship(
        "TacheDossier", back_populates="decisions_validation"
    )

    def __repr__(self) -> str:
        return (
            f"<DecisionValidationHumaine id={self.id} tache_id={self.tache_id} "
            f"decision={self.decision.value if self.decision else None}>"
        )
