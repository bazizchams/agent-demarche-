"""Fondations : bureaux (tenants), utilisateurs, sessions, journal d'audit.

Revision ID: 0001_fondations
Revises: None
Create Date: 2026-10-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.base import HorodatageUTC

revision: str = "0001_fondations"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bureaux",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nom", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=63), nullable=False),
        sa.Column("actif", sa.Boolean(), nullable=False),
        sa.Column("cree_le", HorodatageUTC(), nullable=False),
        sa.Column("modifie_le", HorodatageUTC(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bureaux")),
        sa.UniqueConstraint("slug", name=op.f("uq_bureaux_slug")),
    )

    op.create_table(
        "utilisateurs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("nom_affiche", sa.String(length=120), nullable=False),
        sa.Column("empreinte_mot_de_passe", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "administrateur",
                "employe",
                "lecture_seule",
                name="role",
                native_enum=False,
                length=20,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("actif", sa.Boolean(), nullable=False),
        sa.Column("doit_changer_mot_de_passe", sa.Boolean(), nullable=False),
        sa.Column("echecs_connexion", sa.Integer(), nullable=False),
        sa.Column("verrouille_jusqua", HorodatageUTC(), nullable=True),
        sa.Column("derniere_connexion_le", HorodatageUTC(), nullable=True),
        sa.Column("cree_le", HorodatageUTC(), nullable=False),
        sa.Column("modifie_le", HorodatageUTC(), nullable=False),
        sa.CheckConstraint(
            "echecs_connexion >= 0",
            name=op.f("ck_utilisateurs_echecs_positifs"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["bureaux.id"],
            name=op.f("fk_utilisateurs_tenant_id_bureaux"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_utilisateurs")),
        sa.UniqueConstraint("email", name=op.f("uq_utilisateurs_email")),
    )
    op.create_index(
        op.f("ix_utilisateurs_tenant_id"),
        "utilisateurs",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "sessions_utilisateurs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("utilisateur_id", sa.Uuid(), nullable=False),
        sa.Column("empreinte_jeton", sa.String(length=64), nullable=False),
        sa.Column("jeton_csrf", sa.String(length=64), nullable=False),
        sa.Column("cree_le", HorodatageUTC(), nullable=False),
        sa.Column("expire_le", HorodatageUTC(), nullable=False),
        sa.Column("derniere_activite_le", HorodatageUTC(), nullable=False),
        sa.Column("revoquee_le", HorodatageUTC(), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["bureaux.id"],
            name=op.f("fk_sessions_utilisateurs_tenant_id_bureaux"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["utilisateur_id"],
            ["utilisateurs.id"],
            name=op.f("fk_sessions_utilisateurs_utilisateur_id_utilisateurs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions_utilisateurs")),
        sa.UniqueConstraint(
            "empreinte_jeton",
            name=op.f("uq_sessions_utilisateurs_empreinte_jeton"),
        ),
    )
    op.create_index(
        op.f("ix_sessions_utilisateurs_tenant_id"),
        "sessions_utilisateurs",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sessions_utilisateurs_utilisateur_id"),
        "sessions_utilisateurs",
        ["utilisateur_id"],
        unique=False,
    )

    op.create_table(
        "journal_audit",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("horodatage", HorodatageUTC(), nullable=False),
        sa.Column("acteur_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column(
            "resultat",
            sa.Enum(
                "succes",
                "echec",
                "refus",
                name="resultat_audit",
                native_enum=False,
                length=10,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("ressource_type", sa.String(length=60), nullable=True),
        sa.Column("ressource_id", sa.Uuid(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["acteur_id"],
            ["utilisateurs.id"],
            name=op.f("fk_journal_audit_acteur_id_utilisateurs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["bureaux.id"],
            name=op.f("fk_journal_audit_tenant_id_bureaux"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_journal_audit")),
    )
    op.create_index(
        op.f("ix_journal_audit_action"),
        "journal_audit",
        ["action"],
        unique=False,
    )
    op.create_index(
        op.f("ix_journal_audit_acteur_id"),
        "journal_audit",
        ["acteur_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_journal_audit_horodatage"),
        "journal_audit",
        ["horodatage"],
        unique=False,
    )
    op.create_index(
        op.f("ix_journal_audit_tenant_id"),
        "journal_audit",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_journal_audit_tenant_id"), table_name="journal_audit")
    op.drop_index(op.f("ix_journal_audit_horodatage"), table_name="journal_audit")
    op.drop_index(op.f("ix_journal_audit_acteur_id"), table_name="journal_audit")
    op.drop_index(op.f("ix_journal_audit_action"), table_name="journal_audit")
    op.drop_table("journal_audit")

    op.drop_index(
        op.f("ix_sessions_utilisateurs_utilisateur_id"),
        table_name="sessions_utilisateurs",
    )
    op.drop_index(
        op.f("ix_sessions_utilisateurs_tenant_id"),
        table_name="sessions_utilisateurs",
    )
    op.drop_table("sessions_utilisateurs")

    op.drop_index(op.f("ix_utilisateurs_tenant_id"), table_name="utilisateurs")
    op.drop_table("utilisateurs")

    op.drop_table("bureaux")
