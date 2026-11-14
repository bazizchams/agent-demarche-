"""Catalogue de fiches de formation par bureau (table fiches_formations).

Revision ID: 0013_catalogue_formations
Revises: 0012_extractions, 0012_action_tache
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.base import HorodatageUTC

revision: str = "0013_catalogue_formations"
# Révision de FUSION : deux migrations 0012 parallèles existent (extractions P1 et action_tache P6, toutes
# deux issues de 0011). Cette migration les rassemble en une seule tête, puis crée `fiches_formations`.
down_revision: str | Sequence[str] | None = ("0012_extractions", "0012_action_tache")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fiches_formations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("cle", sa.String(length=520), nullable=False),
        sa.Column("etablissement", sa.String(length=200), nullable=False),
        sa.Column("intitule", sa.String(length=250), nullable=False),
        sa.Column("niveau_entree_bac_plus", sa.Integer(), nullable=True),
        sa.Column("niveau_entree_libelle", sa.String(length=60), nullable=True),
        sa.Column("francais_min", sa.String(length=2), nullable=True),
        sa.Column("anglais_min", sa.String(length=2), nullable=True),
        sa.Column("priorite_c1", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("langue_texte", sa.String(length=1000), nullable=True),
        sa.Column("langue_ambigue", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("moyenne_min", sa.Float(), nullable=True),
        sa.Column("moyenne_reference", sa.String(length=20), nullable=True),
        sa.Column("pieces", sa.JSON(), nullable=False),
        sa.Column("date_limite", sa.Date(), nullable=True),
        sa.Column("ferme", sa.Boolean(), nullable=True),
        sa.Column("domaines", sa.JSON(), nullable=False),
        sa.Column("url_officielle", sa.String(length=500), nullable=True),
        sa.Column("date_releve", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("aucune_exigence_confirmee", sa.JSON(), nullable=False),
        sa.Column("exigences_a_verifier", sa.JSON(), nullable=False),
        sa.Column(
            "statut",
            sa.Enum(
                "verifie",
                "a_verifier",
                name="statut_fiche",
                native_enum=False,
                length=12,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("cree_le", HorodatageUTC(), nullable=False),
        sa.Column("modifie_le", HorodatageUTC(), nullable=False),
        sa.CheckConstraint(
            "moyenne_min IS NULL OR (moyenne_min >= 0 AND moyenne_min <= 20)",
            name=op.f("ck_fiches_formations_moyenne_min_sur_20"),
        ),
        sa.CheckConstraint(
            "niveau_entree_bac_plus IS NULL OR (niveau_entree_bac_plus >= 1 AND niveau_entree_bac_plus <= 8)",
            name=op.f("ck_fiches_formations_niveau_entree_plage"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["bureaux.id"],
            name=op.f("fk_fiches_formations_tenant_id_bureaux"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fiches_formations")),
        sa.UniqueConstraint("tenant_id", "cle", name="uq_fiches_formations_tenant_cle"),
    )
    op.create_index(
        op.f("ix_fiches_formations_tenant_id"), "fiches_formations", ["tenant_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_fiches_formations_tenant_id"), table_name="fiches_formations")
    op.drop_table("fiches_formations")
