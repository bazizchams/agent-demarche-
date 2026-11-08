"""Phase 2 : tables candidats (chiffrés + index aveugles) et documents_candidats.

Revision ID: 0002_candidats_documents
Revises: 0001_fondations
Create Date: 2026-10-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.base import HorodatageUTC

revision: str = "0002_candidats_documents"
down_revision: str | None = "0001_fondations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidats",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("nom_chiffre", sa.Text(), nullable=False),
        sa.Column("prenom_chiffre", sa.Text(), nullable=False),
        sa.Column("date_naissance_chiffree", sa.Text(), nullable=True),
        sa.Column("lieu_naissance_chiffre", sa.Text(), nullable=True),
        sa.Column("email_chiffre", sa.Text(), nullable=True),
        sa.Column("telephone_chiffre", sa.Text(), nullable=True),
        sa.Column("numero_passeport_chiffre", sa.Text(), nullable=True),
        sa.Column("adresse_chiffree", sa.Text(), nullable=True),
        sa.Column("notes_internes_chiffrees", sa.Text(), nullable=True),
        sa.Column("idx_nom", sa.String(length=64), nullable=False),
        sa.Column("idx_prenom", sa.String(length=64), nullable=False),
        sa.Column("idx_email", sa.String(length=64), nullable=True),
        sa.Column("idx_passeport", sa.String(length=64), nullable=True),
        sa.Column(
            "sexe",
            sa.Enum(
                "M",
                "F",
                name="sexe_candidat",
                native_enum=False,
                length=4,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column("nationalite", sa.String(length=100), nullable=True),
        sa.Column("pays_residence", sa.String(length=100), nullable=True),
        sa.Column("date_expiration_passeport", sa.Date(), nullable=True),
        sa.Column("niveau_actuel", sa.String(length=160), nullable=True),
        sa.Column("programme_vise", sa.String(length=200), nullable=True),
        sa.Column("etablissement_vise", sa.String(length=200), nullable=True),
        sa.Column("fonds_disponibles_eur", sa.Integer(), nullable=True),
        sa.Column("consentement_signe", sa.Boolean(), nullable=False),
        sa.Column("date_consentement", HorodatageUTC(), nullable=True),
        sa.Column(
            "statut",
            sa.Enum(
                "actif",
                "archive",
                name="statut_candidat",
                native_enum=False,
                length=16,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("archive_le", HorodatageUTC(), nullable=True),
        sa.Column("cree_le", HorodatageUTC(), nullable=False),
        sa.Column("modifie_le", HorodatageUTC(), nullable=False),
        sa.CheckConstraint(
            "fonds_disponibles_eur IS NULL OR fonds_disponibles_eur >= 0",
            name=op.f("ck_candidats_fonds_positifs"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["bureaux.id"],
            name=op.f("fk_candidats_tenant_id_bureaux"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidats")),
    )
    op.create_index(op.f("ix_candidats_tenant_id"), "candidats", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_candidats_statut"), "candidats", ["statut"], unique=False)
    op.create_index(
        "ix_candidats_tenant_idx_nom", "candidats", ["tenant_id", "idx_nom"], unique=False
    )
    op.create_index(
        "ix_candidats_tenant_idx_prenom", "candidats", ["tenant_id", "idx_prenom"], unique=False
    )
    op.create_index(
        "ix_candidats_tenant_idx_email", "candidats", ["tenant_id", "idx_email"], unique=False
    )
    op.create_index(
        "ix_candidats_tenant_idx_passeport",
        "candidats",
        ["tenant_id", "idx_passeport"],
        unique=False,
    )

    op.create_table(
        "documents_candidats",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("candidat_id", sa.Uuid(), nullable=False),
        sa.Column("type_piece", sa.String(length=80), nullable=False),
        sa.Column("nom_fichier_origine_chiffre", sa.Text(), nullable=False),
        sa.Column("type_mime", sa.String(length=100), nullable=False),
        sa.Column("taille_octets", sa.Integer(), nullable=False),
        sa.Column("empreinte_contenu", sa.String(length=64), nullable=False),
        sa.Column("chemin_stockage_relatif", sa.String(length=255), nullable=False),
        sa.Column("date_expiration", sa.Date(), nullable=True),
        sa.Column("ajoute_par_id", sa.Uuid(), nullable=True),
        sa.Column("cree_le", HorodatageUTC(), nullable=False),
        sa.Column("modifie_le", HorodatageUTC(), nullable=False),
        sa.CheckConstraint(
            "taille_octets > 0",
            name=op.f("ck_documents_candidats_taille_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["ajoute_par_id"],
            ["utilisateurs.id"],
            name=op.f("fk_documents_candidats_ajoute_par_id_utilisateurs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["candidat_id"],
            ["candidats.id"],
            name=op.f("fk_documents_candidats_candidat_id_candidats"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["bureaux.id"],
            name=op.f("fk_documents_candidats_tenant_id_bureaux"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents_candidats")),
        sa.UniqueConstraint(
            "tenant_id",
            "candidat_id",
            "empreinte_contenu",
            name="uq_documents_candidats_doublon",
        ),
    )
    op.create_index(
        op.f("ix_documents_candidats_tenant_id"),
        "documents_candidats",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_documents_candidats_candidat_id"),
        "documents_candidats",
        ["candidat_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_documents_candidats_type_piece"),
        "documents_candidats",
        ["type_piece"],
        unique=False,
    )
    op.create_index(
        op.f("ix_documents_candidats_empreinte_contenu"),
        "documents_candidats",
        ["empreinte_contenu"],
        unique=False,
    )

    op.create_table(
        "messages_discussion_dossier",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("candidat_id", sa.Uuid(), nullable=False),
        sa.Column("code_demarche", sa.String(length=60), nullable=False),
        sa.Column(
            "auteur",
            sa.Enum(
                "utilisateur",
                "assistant",
                name="auteur_message_dossier",
                native_enum=False,
                length=16,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("utilisateur_id", sa.Uuid(), nullable=True),
        sa.Column("contenu_chiffre", sa.Text(), nullable=False),
        sa.Column("score_solidite_pourcent", sa.Integer(), nullable=True),
        sa.Column("cree_le", HorodatageUTC(), nullable=False),
        sa.Column("modifie_le", HorodatageUTC(), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidat_id"],
            ["candidats.id"],
            name=op.f("fk_messages_discussion_dossier_candidat_id_candidats"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["bureaux.id"],
            name=op.f("fk_messages_discussion_dossier_tenant_id_bureaux"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["utilisateur_id"],
            ["utilisateurs.id"],
            name=op.f("fk_messages_discussion_dossier_utilisateur_id_utilisateurs"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages_discussion_dossier")),
    )
    op.create_index(
        op.f("ix_messages_discussion_dossier_tenant_id"),
        "messages_discussion_dossier",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_messages_discussion_dossier_candidat_id"),
        "messages_discussion_dossier",
        ["candidat_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_messages_discussion_dossier_code_demarche"),
        "messages_discussion_dossier",
        ["code_demarche"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_messages_discussion_dossier_code_demarche"),
        table_name="messages_discussion_dossier",
    )
    op.drop_index(
        op.f("ix_messages_discussion_dossier_candidat_id"),
        table_name="messages_discussion_dossier",
    )
    op.drop_index(
        op.f("ix_messages_discussion_dossier_tenant_id"),
        table_name="messages_discussion_dossier",
    )
    op.drop_table("messages_discussion_dossier")
    op.drop_index(
        op.f("ix_documents_candidats_empreinte_contenu"),
        table_name="documents_candidats",
    )
    op.drop_index(
        op.f("ix_documents_candidats_type_piece"),
        table_name="documents_candidats",
    )
    op.drop_index(
        op.f("ix_documents_candidats_candidat_id"),
        table_name="documents_candidats",
    )
    op.drop_index(
        op.f("ix_documents_candidats_tenant_id"),
        table_name="documents_candidats",
    )
    op.drop_table("documents_candidats")

    op.drop_index("ix_candidats_tenant_idx_passeport", table_name="candidats")
    op.drop_index("ix_candidats_tenant_idx_email", table_name="candidats")
    op.drop_index("ix_candidats_tenant_idx_prenom", table_name="candidats")
    op.drop_index("ix_candidats_tenant_idx_nom", table_name="candidats")
    op.drop_index(op.f("ix_candidats_statut"), table_name="candidats")
    op.drop_index(op.f("ix_candidats_tenant_id"), table_name="candidats")
    op.drop_table("candidats")
