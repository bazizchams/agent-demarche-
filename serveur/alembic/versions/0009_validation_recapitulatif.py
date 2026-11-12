"""Validation humaine du récapitulatif avant soumission officielle (Règle 1).

Revision ID: 0009_validation_recapitulatif
Revises: 0008_coffre_identifiants
Create Date: 2026-11-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.base import HorodatageUTC

revision: str = "0009_validation_recapitulatif"
down_revision: str | None = "0008_coffre_identifiants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "validations_recapitulatif",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("candidat_id", sa.Uuid(), nullable=False),
        sa.Column("portail", sa.String(length=40), nullable=False),
        sa.Column("type_demarche", sa.String(length=60), nullable=False),
        sa.Column("contenu_chiffre", sa.Text(), nullable=False),
        sa.Column("empreinte", sa.String(length=64), nullable=False),
        sa.Column(
            "statut",
            sa.Enum(
                "en_attente",
                "validee",
                "refusee",
                "envoyee",
                "invalidee",
                name="statut_validation_recapitulatif",
                native_enum=False,
                length=12,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("cree_le", HorodatageUTC(), nullable=False),
        sa.Column("validee_par", sa.Uuid(), nullable=True),
        sa.Column("validee_le", HorodatageUTC(), nullable=True),
        sa.Column("envoyee_le", HorodatageUTC(), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["bureaux.id"],
            name=op.f("fk_validations_recapitulatif_tenant_id_bureaux"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["candidat_id"], ["candidats.id"],
            name=op.f("fk_validations_recapitulatif_candidat_id_candidats"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["validee_par"], ["utilisateurs.id"],
            name=op.f("fk_validations_recapitulatif_validee_par_utilisateurs"), ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_validations_recapitulatif")),
    )
    op.create_index(
        op.f("ix_validations_recapitulatif_tenant_id"),
        "validations_recapitulatif", ["tenant_id"],
    )
    op.create_index(
        op.f("ix_validations_recapitulatif_candidat_id"),
        "validations_recapitulatif", ["candidat_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_validations_recapitulatif_candidat_id"), table_name="validations_recapitulatif"
    )
    op.drop_index(
        op.f("ix_validations_recapitulatif_tenant_id"), table_name="validations_recapitulatif"
    )
    op.drop_table("validations_recapitulatif")
