"""Voeux de formation des candidats (table voeux_formations).

Revision ID: 0006_voeux_formations
Revises: 0005_demarches_par_bureau
Create Date: 2026-11-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.base import HorodatageUTC

revision: str = "0006_voeux_formations"
down_revision: str | None = "0005_demarches_par_bureau"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "voeux_formations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("candidat_id", sa.Uuid(), nullable=False),
        sa.Column("rang", sa.Integer(), nullable=False),
        sa.Column("intitule", sa.String(length=250), nullable=False),
        sa.Column("etablissement", sa.String(length=200), nullable=False),
        sa.Column("niveau", sa.String(length=40), nullable=False),
        sa.Column(
            "voie",
            sa.Enum(
                "dap_blanche",
                "dap_jaune",
                "hors_dap",
                name="voie_voeu",
                native_enum=False,
                length=16,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("url_source", sa.String(length=500), nullable=True),
        sa.Column("justification", sa.String(length=500), nullable=True),
        sa.Column("motivation_chiffree", sa.Text(), nullable=True),
        sa.Column(
            "statut",
            sa.Enum(
                "brouillon",
                "valide",
                "ajoute_au_panier",
                name="statut_voeu",
                native_enum=False,
                length=20,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("cree_le", HorodatageUTC(), nullable=False),
        sa.Column("modifie_le", HorodatageUTC(), nullable=False),
        sa.CheckConstraint("rang >= 1 AND rang <= 7", name=op.f("ck_voeux_formations_rang_voeu")),
        sa.ForeignKeyConstraint(
            ["candidat_id"],
            ["candidats.id"],
            name=op.f("fk_voeux_formations_candidat_id_candidats"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["bureaux.id"],
            name=op.f("fk_voeux_formations_tenant_id_bureaux"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_voeux_formations")),
        sa.UniqueConstraint(
            "candidat_id",
            "intitule",
            "etablissement",
            name="uq_voeux_formations_candidat_intitule_etablissement",
        ),
    )
    op.create_index(
        op.f("ix_voeux_formations_tenant_id"), "voeux_formations", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_voeux_formations_candidat_id"), "voeux_formations", ["candidat_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_voeux_formations_candidat_id"), table_name="voeux_formations")
    op.drop_index(op.f("ix_voeux_formations_tenant_id"), table_name="voeux_formations")
    op.drop_table("voeux_formations")
