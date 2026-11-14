"""Action d'une tâche (pré-remplissage ou « Ouvrir sur mon PC »).

Revision ID: 0012_action_tache
Revises: 0011_rappels_echeances_envoyes
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_action_tache"
down_revision: str | None = "0011_rappels_echeances_envoyes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "taches_dossiers",
        sa.Column(
            "action",
            sa.String(length=40),
            nullable=False,
            server_default="preremplissage",
        ),
    )


def downgrade() -> None:
    with op.batch_alter_table("taches_dossiers") as lot:
        lot.drop_column("action")
