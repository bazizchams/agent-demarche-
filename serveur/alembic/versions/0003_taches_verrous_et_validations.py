"""Phase 3 : tables agents_locaux, taches_dossiers, etapes_taches, verrous_dossiers et decisions_validation_humaine.

Revision ID: 0003_taches_verrous_validations
Revises: 0002_candidats_documents
Create Date: 2026-10-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.base import HorodatageUTC

revision: str = "0003_taches_verrous_validations"
down_revision: str | None = "0002_candidats_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agents_locaux",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("nom_machine", sa.String(length=120), nullable=False),
        sa.Column("empreinte_jeton", sa.String(length=64), nullable=False),
        sa.Column("actif", sa.Boolean(), nullable=False),
        sa.Column("cree_par_id", sa.Uuid(), nullable=True),
        sa.Column("derniere_activite_le", HorodatageUTC(), nullable=True),
        sa.Column("cree_le", HorodatageUTC(), nullable=False),
        sa.Column("modifie_le", HorodatageUTC(), nullable=False),
        sa.ForeignKeyConstraint(
            ["cree_par_id"],
            ["utilisateurs.id"],
            name=op.f("fk_agents_locaux_cree_par_id_utilisateurs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["bureaux.id"],
            name=op.f("fk_agents_locaux_tenant_id_bureaux"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agents_locaux")),
    )
    op.create_index(
        op.f("ix_agents_locaux_tenant_id"),
        "agents_locaux",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agents_locaux_empreinte_jeton"),
        "agents_locaux",
        ["empreinte_jeton"],
        unique=True,
    )

    op.create_table(
        "taches_dossiers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("candidat_id", sa.Uuid(), nullable=False),
        sa.Column("code_demarche", sa.String(length=60), nullable=False),
        sa.Column(
            "statut",
            sa.Enum(
                "en_attente",
                "en_cours",
                "suspendue",
                "a_valider",
                "terminee",
                "annulee",
                "en_erreur",
                name="statut_tache",
                native_enum=False,
                length=20,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "motif_suspension",
            sa.Enum(
                "donnee_manquante",
                "piece_manquante_ou_invalide",
                "action_utilisateur_portail",
                "selecteur_portail_introuvable",
                "rejet_validation_humaine",
                "autre",
                name="motif_suspension_tache",
                native_enum=False,
                length=40,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column("message_alerte", sa.String(length=500), nullable=True),
        sa.Column("champs_manquants_json", sa.Text(), nullable=True),
        sa.Column("pieces_manquantes_json", sa.Text(), nullable=True),
        sa.Column("recapitulatif_remplissage_chiffre", sa.Text(), nullable=True),
        sa.Column("chemin_capture_controle_relatif", sa.String(length=255), nullable=True),
        sa.Column("type_mime_capture_controle", sa.String(length=100), nullable=True),
        sa.Column("creee_par_id", sa.Uuid(), nullable=True),
        sa.Column("agent_local_id", sa.Uuid(), nullable=True),
        sa.Column("demarree_le", HorodatageUTC(), nullable=True),
        sa.Column("suspendue_le", HorodatageUTC(), nullable=True),
        sa.Column("soumise_validation_le", HorodatageUTC(), nullable=True),
        sa.Column("terminee_le", HorodatageUTC(), nullable=True),
        sa.Column("cree_le", HorodatageUTC(), nullable=False),
        sa.Column("modifie_le", HorodatageUTC(), nullable=False),
        sa.ForeignKeyConstraint(
            ["agent_local_id"],
            ["agents_locaux.id"],
            name=op.f("fk_taches_dossiers_agent_local_id_agents_locaux"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["candidat_id"],
            ["candidats.id"],
            name=op.f("fk_taches_dossiers_candidat_id_candidats"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["creee_par_id"],
            ["utilisateurs.id"],
            name=op.f("fk_taches_dossiers_creee_par_id_utilisateurs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["bureaux.id"],
            name=op.f("fk_taches_dossiers_tenant_id_bureaux"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_taches_dossiers")),
    )
    op.create_index(
        op.f("ix_taches_dossiers_tenant_id"),
        "taches_dossiers",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_taches_dossiers_candidat_id"),
        "taches_dossiers",
        ["candidat_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_taches_dossiers_code_demarche"),
        "taches_dossiers",
        ["code_demarche"],
        unique=False,
    )
    op.create_index(
        op.f("ix_taches_dossiers_statut"),
        "taches_dossiers",
        ["statut"],
        unique=False,
    )
    op.create_index(
        "ix_taches_dossiers_tenant_statut",
        "taches_dossiers",
        ["tenant_id", "statut"],
        unique=False,
    )
    op.create_index(
        "ix_taches_dossiers_tenant_candidat",
        "taches_dossiers",
        ["tenant_id", "candidat_id"],
        unique=False,
    )

    op.create_table(
        "etapes_taches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("tache_id", sa.Uuid(), nullable=False),
        sa.Column("ordre", sa.Integer(), nullable=False),
        sa.Column("code_etape", sa.String(length=80), nullable=False),
        sa.Column("libelle", sa.String(length=200), nullable=False),
        sa.Column(
            "statut",
            sa.Enum(
                "a_faire",
                "en_cours",
                "terminee",
                "suspendue",
                "en_erreur",
                name="statut_etape_tache",
                native_enum=False,
                length=20,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("cle_idempotence", sa.String(length=120), nullable=True),
        sa.Column("detail_execution_chiffre", sa.Text(), nullable=True),
        sa.Column("message_erreur", sa.String(length=500), nullable=True),
        sa.Column("nb_tentatives", sa.Integer(), nullable=False),
        sa.Column("commencee_le", HorodatageUTC(), nullable=True),
        sa.Column("terminee_le", HorodatageUTC(), nullable=True),
        sa.Column("cree_le", HorodatageUTC(), nullable=False),
        sa.Column("modifie_le", HorodatageUTC(), nullable=False),
        sa.CheckConstraint("ordre >= 1", name=op.f("ck_etapes_taches_ordre_etape_positif")),
        sa.CheckConstraint(
            "nb_tentatives >= 0", name=op.f("ck_etapes_taches_nb_tentatives_positif")
        ),
        sa.ForeignKeyConstraint(
            ["tache_id"],
            ["taches_dossiers.id"],
            name=op.f("fk_etapes_taches_tache_id_taches_dossiers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["bureaux.id"],
            name=op.f("fk_etapes_taches_tenant_id_bureaux"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_etapes_taches")),
        sa.UniqueConstraint(
            "tenant_id",
            "tache_id",
            "code_etape",
            name="uq_etapes_taches_code",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "tache_id",
            "ordre",
            name="uq_etapes_taches_ordre",
        ),
    )
    op.create_index(
        op.f("ix_etapes_taches_tenant_id"),
        "etapes_taches",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_etapes_taches_tache_id"),
        "etapes_taches",
        ["tache_id"],
        unique=False,
    )

    op.create_table(
        "verrous_dossiers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("candidat_id", sa.Uuid(), nullable=False),
        sa.Column("tache_id", sa.Uuid(), nullable=False),
        sa.Column("detenteur", sa.String(length=120), nullable=False),
        sa.Column("acquis_le", HorodatageUTC(), nullable=False),
        sa.Column("expire_le", HorodatageUTC(), nullable=False),
        sa.Column("cree_le", HorodatageUTC(), nullable=False),
        sa.Column("modifie_le", HorodatageUTC(), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidat_id"],
            ["candidats.id"],
            name=op.f("fk_verrous_dossiers_candidat_id_candidats"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tache_id"],
            ["taches_dossiers.id"],
            name=op.f("fk_verrous_dossiers_tache_id_taches_dossiers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["bureaux.id"],
            name=op.f("fk_verrous_dossiers_tenant_id_bureaux"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_verrous_dossiers")),
        sa.UniqueConstraint(
            "tenant_id",
            "candidat_id",
            name="uq_verrous_dossiers_candidat",
        ),
    )
    op.create_index(
        op.f("ix_verrous_dossiers_tenant_id"),
        "verrous_dossiers",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_verrous_dossiers_candidat_id"),
        "verrous_dossiers",
        ["candidat_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_verrous_dossiers_tache_id"),
        "verrous_dossiers",
        ["tache_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_verrous_dossiers_expire_le"),
        "verrous_dossiers",
        ["expire_le"],
        unique=False,
    )

    op.create_table(
        "decisions_validation_humaine",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("tache_id", sa.Uuid(), nullable=False),
        sa.Column("candidat_id", sa.Uuid(), nullable=False),
        sa.Column("decideur_id", sa.Uuid(), nullable=False),
        sa.Column(
            "decision",
            sa.Enum(
                "approuvee",
                "rejetee",
                name="type_decision_validation",
                native_enum=False,
                length=20,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("confirmation_explicite", sa.Boolean(), nullable=False),
        sa.Column("commentaire_chiffre", sa.Text(), nullable=True),
        sa.Column("reinitialiser_depuis_etape", sa.String(length=80), nullable=True),
        sa.Column("cree_le", HorodatageUTC(), nullable=False),
        sa.Column("modifie_le", HorodatageUTC(), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidat_id"],
            ["candidats.id"],
            name=op.f("fk_decisions_validation_humaine_candidat_id_candidats"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["decideur_id"],
            ["utilisateurs.id"],
            name=op.f("fk_decisions_validation_humaine_decideur_id_utilisateurs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tache_id"],
            ["taches_dossiers.id"],
            name=op.f("fk_decisions_validation_humaine_tache_id_taches_dossiers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["bureaux.id"],
            name=op.f("fk_decisions_validation_humaine_tenant_id_bureaux"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decisions_validation_humaine")),
    )
    op.create_index(
        op.f("ix_decisions_validation_humaine_tenant_id"),
        "decisions_validation_humaine",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_decisions_validation_humaine_tache_id"),
        "decisions_validation_humaine",
        ["tache_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_decisions_validation_humaine_candidat_id"),
        "decisions_validation_humaine",
        ["candidat_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_decisions_validation_humaine_decideur_id"),
        "decisions_validation_humaine",
        ["decideur_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_decisions_validation_humaine_decideur_id"),
        table_name="decisions_validation_humaine",
    )
    op.drop_index(
        op.f("ix_decisions_validation_humaine_candidat_id"),
        table_name="decisions_validation_humaine",
    )
    op.drop_index(
        op.f("ix_decisions_validation_humaine_tache_id"),
        table_name="decisions_validation_humaine",
    )
    op.drop_index(
        op.f("ix_decisions_validation_humaine_tenant_id"),
        table_name="decisions_validation_humaine",
    )
    op.drop_table("decisions_validation_humaine")

    op.drop_index(op.f("ix_verrous_dossiers_expire_le"), table_name="verrous_dossiers")
    op.drop_index(op.f("ix_verrous_dossiers_tache_id"), table_name="verrous_dossiers")
    op.drop_index(op.f("ix_verrous_dossiers_candidat_id"), table_name="verrous_dossiers")
    op.drop_index(op.f("ix_verrous_dossiers_tenant_id"), table_name="verrous_dossiers")
    op.drop_table("verrous_dossiers")

    op.drop_index(op.f("ix_etapes_taches_tache_id"), table_name="etapes_taches")
    op.drop_index(op.f("ix_etapes_taches_tenant_id"), table_name="etapes_taches")
    op.drop_table("etapes_taches")

    op.drop_index("ix_taches_dossiers_tenant_candidat", table_name="taches_dossiers")
    op.drop_index("ix_taches_dossiers_tenant_statut", table_name="taches_dossiers")
    op.drop_index(op.f("ix_taches_dossiers_statut"), table_name="taches_dossiers")
    op.drop_index(op.f("ix_taches_dossiers_code_demarche"), table_name="taches_dossiers")
    op.drop_index(op.f("ix_taches_dossiers_candidat_id"), table_name="taches_dossiers")
    op.drop_index(op.f("ix_taches_dossiers_tenant_id"), table_name="taches_dossiers")
    op.drop_table("taches_dossiers")

    op.drop_index(op.f("ix_agents_locaux_empreinte_jeton"), table_name="agents_locaux")
    op.drop_index(op.f("ix_agents_locaux_tenant_id"), table_name="agents_locaux")
    op.drop_table("agents_locaux")
