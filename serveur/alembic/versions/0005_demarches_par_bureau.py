"""Démarches définies par bureau (table demarches_bureaux).

Revision ID: 0005_demarches_par_bureau
Revises: 0004_abonnements_conformite
Create Date: 2026-11-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.base import HorodatageUTC

revision: str = "0005_demarches_par_bureau"
down_revision: str | None = "0004_abonnements_conformite"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "demarches_bureaux",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("actif", sa.Boolean(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("cree_le", HorodatageUTC(), nullable=False),
        sa.Column("modifie_le", HorodatageUTC(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["bureaux.id"],
            name="fk_demarches_bureaux_tenant_id_bureaux",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_demarches_bureaux"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_demarches_bureaux_tenant_code"),
    )
    op.create_index(
        "ix_demarches_bureaux_tenant_id",
        "demarches_bureaux",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_demarches_bureaux_tenant_id", table_name="demarches_bureaux")
    op.drop_table("demarches_bureaux")
