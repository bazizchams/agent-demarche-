"""Échanges temporaires du coffre (consentement de connexion, dépôt à enregistrer) et portail visé par une tâche.

Revision ID: 0019_echanges_coffre
Revises: 0018_passeport_unique
Create Date: 2026-11-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.base import HorodatageUTC

revision: str = "0019_echanges_coffre"
down_revision: str | Sequence[str] | None = "0018_passeport_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

T = "echanges_coffre"


def upgrade() -> None:
    with op.batch_alter_table("taches_dossiers") as lot:
        lot.add_column(sa.Column("portail", sa.String(length=40), nullable=True))
    op.create_table(
        T,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("tache_id", sa.Uuid(), nullable=False),
        sa.Column("candidat_id", sa.Uuid(), nullable=False),
        sa.Column("portail", sa.String(length=40), nullable=False),
        sa.Column("nature", sa.String(length=30), nullable=False),
        sa.Column("accorde_par_id", sa.Uuid(), nullable=True),
        sa.Column("agent_local_id", sa.Uuid(), nullable=True),
        sa.Column("expire_le", HorodatageUTC(), nullable=False),
        sa.Column("utilise_le", HorodatageUTC(), nullable=True),
        sa.Column("identifiant_chiffre", sa.Text(), nullable=True),
        sa.Column("mot_de_passe_chiffre", sa.Text(), nullable=True),
        sa.Column("cree_le", HorodatageUTC(), nullable=False),
        sa.Column("modifie_le", HorodatageUTC(), nullable=False),
        sa.CheckConstraint(
            "nature IN ('autorisation_lecture','depot_a_enregistrer')",
            name=op.f("ck_echanges_coffre_nature_valide"),
        ),
        sa.ForeignKeyConstraint(
            ["tache_id"], ["taches_dossiers.id"],
            name=op.f("fk_echanges_coffre_tache_id_taches_dossiers"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["candidat_id"], ["candidats.id"],
            name=op.f("fk_echanges_coffre_candidat_id_candidats"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["accorde_par_id"], ["utilisateurs.id"],
            name=op.f("fk_echanges_coffre_accorde_par_id_utilisateurs"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["agent_local_id"], ["agents_locaux.id"],
            name=op.f("fk_echanges_coffre_agent_local_id_agents_locaux"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["bureaux.id"],
            name=op.f("fk_echanges_coffre_tenant_id_bureaux"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_echanges_coffre")),
    )
    op.create_index(op.f(f"ix_{T}_tenant_id"), T, ["tenant_id"], unique=False)
    op.create_index(op.f(f"ix_{T}_tache_id"), T, ["tache_id"], unique=False)
    op.create_index(op.f(f"ix_{T}_candidat_id"), T, ["candidat_id"], unique=False)
    op.create_index("ix_echanges_coffre_tache_nature", T, ["tenant_id", "tache_id", "nature"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_echanges_coffre_tache_nature", table_name=T)
    op.drop_index(op.f(f"ix_{T}_candidat_id"), table_name=T)
    op.drop_index(op.f(f"ix_{T}_tache_id"), table_name=T)
    op.drop_index(op.f(f"ix_{T}_tenant_id"), table_name=T)
    op.drop_table(T)
    with op.batch_alter_table("taches_dossiers") as lot:
        lot.drop_column("portail")
