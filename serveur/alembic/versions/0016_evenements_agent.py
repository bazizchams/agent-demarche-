"""Événements de la discussion de l'agent (panneau Co-Pilote en direct), texte chiffré, purge à 7 jours.

Revision ID: 0016_evenements_agent
Revises: 0014_points_forts_projet
Create Date: 2026-11-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.base import HorodatageUTC

revision: str = "0016_evenements_agent"
down_revision: str | Sequence[str] | None = "0014_points_forts_projet"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

T = "evenements_agent"


def upgrade() -> None:
    op.create_table(
        T,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("tache_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("auteur", sa.String(length=10), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=True),
        sa.Column("texte_chiffre", sa.Text(), nullable=False),
        sa.Column("traite_le", HorodatageUTC(), nullable=True),
        sa.Column("cree_le", HorodatageUTC(), nullable=False),
        sa.Column("modifie_le", HorodatageUTC(), nullable=False),
        sa.CheckConstraint(
            "type IN ('agent','action','alerte','demande_humaine','utilisateur','commande')",
            name=op.f("ck_evenements_agent_type_valide"),
        ),
        sa.CheckConstraint("auteur IN ('agent','humain')", name=op.f("ck_evenements_agent_auteur_valide")),
        sa.ForeignKeyConstraint(
            ["tache_id"], ["taches_dossiers.id"],
            name=op.f("fk_evenements_agent_tache_id_taches_dossiers"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["bureaux.id"],
            name=op.f("fk_evenements_agent_tenant_id_bureaux"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evenements_agent")),
        sa.UniqueConstraint("tenant_id", "tache_id", "seq", name="uq_evenements_agent_seq"),
    )
    op.create_index(op.f(f"ix_{T}_tenant_id"), T, ["tenant_id"], unique=False)
    op.create_index(op.f(f"ix_{T}_tache_id"), T, ["tache_id"], unique=False)
    op.create_index("ix_evenements_agent_tache_seq", T, ["tenant_id", "tache_id", "seq"], unique=False)
    op.create_index("ix_evenements_agent_cree_le", T, ["cree_le"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_evenements_agent_cree_le", table_name=T)
    op.drop_index("ix_evenements_agent_tache_seq", table_name=T)
    op.drop_index(op.f(f"ix_{T}_tache_id"), table_name=T)
    op.drop_index(op.f(f"ix_{T}_tenant_id"), table_name=T)
    op.drop_table(T)
