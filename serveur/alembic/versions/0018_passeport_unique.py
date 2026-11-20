"""Unicité du numéro de passeport par bureau (index unique partiel sur l'index aveugle).

Revision ID: 0018_passeport_unique
Revises: 0017_depot_sans_fiche
Create Date: 2026-11-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "0018_passeport_unique"
down_revision: str | Sequence[str] | None = "0017_depot_sans_fiche"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

T = "candidats"
ANCIEN = "ix_candidats_tenant_idx_passeport"
UNIQUE = "uq_candidats_tenant_idx_passeport"
FILTRE = sa.text("idx_passeport IS NOT NULL")


def _verifier_absence_de_doublons() -> None:
    if context.is_offline_mode():
        return
    nb = op.get_bind().execute(
        sa.text(
            "SELECT COUNT(*) FROM (SELECT 1 FROM candidats WHERE idx_passeport IS NOT NULL "
            "GROUP BY tenant_id, idx_passeport HAVING COUNT(*) > 1) AS doublons"
        )
    ).scalar_one()
    if nb:
        raise RuntimeError(
            f"Migration 0018 interrompue : {nb} numéro(s) de passeport sont déjà en doublon dans un même bureau. "
            "Aucune donnée n'a été modifiée. Fusionnez ou archivez les fiches en double (même tenant_id et "
            "idx_passeport), puis relancez la migration."
        )


def upgrade() -> None:
    _verifier_absence_de_doublons()
    op.drop_index(ANCIEN, table_name=T)
    op.create_index(
        UNIQUE, T, ["tenant_id", "idx_passeport"], unique=True,
        sqlite_where=FILTRE, postgresql_where=FILTRE,
    )


def downgrade() -> None:
    op.drop_index(UNIQUE, table_name=T)
    op.create_index(ANCIEN, T, ["tenant_id", "idx_passeport"], unique=False)
