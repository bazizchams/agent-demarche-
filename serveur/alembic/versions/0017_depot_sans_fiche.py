"""Dépôt de passeport sans fiche : fichier et propositions chiffrés, purge à 24 h.

Revision ID: 0017_depot_sans_fiche
Revises: 0016_evenements_agent
Create Date: 2026-11-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.base import HorodatageUTC

revision: str = "0017_depot_sans_fiche"
down_revision: str | Sequence[str] | None = "0016_evenements_agent"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

T = "depots_passeport"


def upgrade() -> None:
    op.create_table(
        T,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("depose_par_id", sa.Uuid(), nullable=True),
        sa.Column("nom_fichier_chiffre", sa.Text(), nullable=False),
        sa.Column("type_mime", sa.String(length=100), nullable=False),
        sa.Column("taille_octets", sa.Integer(), nullable=False),
        sa.Column("empreinte_contenu", sa.String(length=64), nullable=False),
        sa.Column("chemin_stockage_relatif", sa.String(length=255), nullable=False),
        sa.Column("statut", sa.String(length=20), nullable=False),
        sa.Column("propositions_chiffrees", sa.Text(), nullable=True),
        sa.Column("cree_le", HorodatageUTC(), nullable=False),
        sa.Column("modifie_le", HorodatageUTC(), nullable=False),
        sa.CheckConstraint(
            "statut IN ('propose','saisie_manuelle')", name=op.f("ck_depots_passeport_statut_valide")
        ),
        sa.CheckConstraint("taille_octets > 0", name=op.f("ck_depots_passeport_taille_positive")),
        sa.ForeignKeyConstraint(
            ["depose_par_id"], ["utilisateurs.id"],
            name=op.f("fk_depots_passeport_depose_par_id_utilisateurs"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["bureaux.id"],
            name=op.f("fk_depots_passeport_tenant_id_bureaux"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_depots_passeport")),
    )
    op.create_index(op.f(f"ix_{T}_tenant_id"), T, ["tenant_id"], unique=False)
    op.create_index("ix_depots_passeport_cree_le", T, ["cree_le"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_depots_passeport_cree_le", table_name=T)
    op.drop_index(op.f(f"ix_{T}_tenant_id"), table_name=T)
    op.drop_table(T)
