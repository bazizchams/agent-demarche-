"""Niveaux de langue du candidat (niveau_francais, niveau_anglais), colonnes nullables.

Revision ID: 0007_niveaux_langue_candidat
Revises: 0006_voeux_formations
Create Date: 2026-11-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_niveaux_langue_candidat"
down_revision: str | None = "0006_voeux_formations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("candidats") as batch:
        batch.add_column(sa.Column("niveau_francais", sa.String(length=2), nullable=True))
        batch.add_column(sa.Column("niveau_anglais", sa.String(length=2), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("candidats") as batch:
        batch.drop_column("niveau_anglais")
        batch.drop_column("niveau_francais")
