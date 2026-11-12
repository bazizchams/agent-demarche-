"""Coffre d'identifiants portail (table identifiants_portail, regle 3).

Revision ID: 0008_coffre_identifiants
Revises: 0007_niveaux_langue_candidat
Create Date: 2026-11-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.base import HorodatageUTC

revision: str = "0008_coffre_identifiants"
down_revision: str | None = "0007_niveaux_langue_candidat"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "identifiants_portail",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("candidat_id", sa.Uuid(), nullable=False),
        sa.Column("portail", sa.String(length=40), nullable=False),
        sa.Column("identifiant_chiffre", sa.Text(), nullable=False),
        sa.Column("mot_de_passe_chiffre", sa.Text(), nullable=False),
        sa.Column("consentement_recueilli_le", HorodatageUTC(), nullable=False),
        sa.Column("consentement_par", sa.Uuid(), nullable=False),
        sa.Column("cree_le", HorodatageUTC(), nullable=False),
        sa.Column("mis_a_jour_le", HorodatageUTC(), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidat_id"],
            ["candidats.id"],
            name=op.f("fk_identifiants_portail_candidat_id_candidats"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["consentement_par"],
            ["utilisateurs.id"],
            name=op.f("fk_identifiants_portail_consentement_par_utilisateurs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["bureaux.id"],
            name=op.f("fk_identifiants_portail_tenant_id_bureaux"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_identifiants_portail")),
        sa.UniqueConstraint(
            "tenant_id",
            "candidat_id",
            "portail",
            name="uq_identifiants_portail_tenant_candidat_portail",
        ),
    )
    op.create_index(
        op.f("ix_identifiants_portail_tenant_id"), "identifiants_portail", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_identifiants_portail_candidat_id"),
        "identifiants_portail",
        ["candidat_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_identifiants_portail_candidat_id"), table_name="identifiants_portail")
    op.drop_index(op.f("ix_identifiants_portail_tenant_id"), table_name="identifiants_portail")
    op.drop_table("identifiants_portail")
