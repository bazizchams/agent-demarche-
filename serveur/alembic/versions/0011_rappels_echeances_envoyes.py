"""Rappels d'échéance déjà envoyés (idempotence de l'envoi par courriel).

Revision ID: 0011_rappels_echeances_envoyes
Revises: 0010_jetons_courriel
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.base import HorodatageUTC

revision: str = "0011_rappels_echeances_envoyes"
down_revision: str | None = "0010_jetons_courriel"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rappels_echeances_envoyes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("code_demarche", sa.String(length=60), nullable=False),
        sa.Column("code_echeance", sa.String(length=60), nullable=False),
        sa.Column("seuil_jours", sa.Integer(), nullable=False),
        sa.Column("date_echeance", sa.Date(), nullable=False),
        sa.Column("envoye_le", HorodatageUTC(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["bureaux.id"],
            name=op.f("fk_rappels_echeances_envoyes_tenant_id_bureaux"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rappels_echeances_envoyes")),
        sa.UniqueConstraint(
            "tenant_id", "code_demarche", "code_echeance", "seuil_jours", "date_echeance",
            name=op.f("uq_rappels_echeances_envoyes_rappel"),
        ),
    )
    op.create_index(
        op.f("ix_rappels_echeances_envoyes_tenant_id"), "rappels_echeances_envoyes", ["tenant_id"]
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_rappels_echeances_envoyes_tenant_id"), table_name="rappels_echeances_envoyes"
    )
    op.drop_table("rappels_echeances_envoyes")
