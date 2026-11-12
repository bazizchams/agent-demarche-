"""Jetons à usage unique par courriel et adresse e-mail vérifiée.

Revision ID: 0010_jetons_courriel
Revises: 0009_validation_recapitulatif
Create Date: 2026-11-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.base import HorodatageUTC

revision: str = "0010_jetons_courriel"
down_revision: str | None = "0009_validation_recapitulatif"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("utilisateurs", sa.Column("email_verifie_le", HorodatageUTC(), nullable=True))
    op.create_table(
        "jetons_courriel",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("utilisateur_id", sa.Uuid(), nullable=False),
        sa.Column(
            "objet",
            sa.Enum(
                "verification_adresse",
                "reinitialisation_mot_de_passe",
                name="objet_jeton_courriel",
                native_enum=False,
                length=40,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("empreinte", sa.String(length=64), nullable=False),
        sa.Column("cree_le", HorodatageUTC(), nullable=False),
        sa.Column("expire_le", HorodatageUTC(), nullable=False),
        sa.Column("utilise_le", HorodatageUTC(), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["bureaux.id"],
            name=op.f("fk_jetons_courriel_tenant_id_bureaux"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["utilisateur_id"], ["utilisateurs.id"],
            name=op.f("fk_jetons_courriel_utilisateur_id_utilisateurs"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jetons_courriel")),
        sa.UniqueConstraint("empreinte", name=op.f("uq_jetons_courriel_empreinte")),
    )
    op.create_index(op.f("ix_jetons_courriel_tenant_id"), "jetons_courriel", ["tenant_id"])
    op.create_index(
        op.f("ix_jetons_courriel_utilisateur_id"), "jetons_courriel", ["utilisateur_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_jetons_courriel_utilisateur_id"), table_name="jetons_courriel")
    op.drop_index(op.f("ix_jetons_courriel_tenant_id"), table_name="jetons_courriel")
    op.drop_table("jetons_courriel")
    with op.batch_alter_table("utilisateurs") as lot:
        lot.drop_column("email_verifie_le")
