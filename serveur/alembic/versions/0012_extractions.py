"""Extractions de valeurs lues dans les documents (lecture des documents, phase P1).

Revision ID: 0012_extractions
Revises: 0011_rappels_echeances_envoyes
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.base import HorodatageUTC

revision: str = "0012_extractions"
down_revision: str | None = "0011_rappels_echeances_envoyes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "extractions_documents"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("candidat_id", sa.Uuid(), nullable=False),
        sa.Column("champ", sa.String(length=60), nullable=False),
        sa.Column("valeur_chiffree", sa.Text(), nullable=False),
        sa.Column("valeur_alternative_chiffree", sa.Text(), nullable=True),
        sa.Column("extrait_chiffre", sa.Text(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=1), nullable=False),
        sa.Column("confiance", sa.Float(), nullable=False),
        sa.Column(
            "statut",
            sa.Enum(
                "auto",
                "a_verifier",
                "valide_humain",
                "rejete",
                name="statut_extraction",
                native_enum=False,
                length=16,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("motif", sa.String(length=60), nullable=True),
        sa.Column("decide_par_id", sa.Uuid(), nullable=True),
        sa.Column("decide_le", HorodatageUTC(), nullable=True),
        sa.Column("applique_le", HorodatageUTC(), nullable=True),
        sa.Column("cree_le", HorodatageUTC(), nullable=False),
        sa.Column("modifie_le", HorodatageUTC(), nullable=False),
        sa.CheckConstraint("source IN ('A', 'B')", name=op.f("ck_extractions_documents_source_lecteur")),
        sa.CheckConstraint(
            "confiance >= 0 AND confiance <= 1", name=op.f("ck_extractions_documents_confiance_bornee")
        ),
        sa.ForeignKeyConstraint(
            ["candidat_id"], ["candidats.id"],
            name=op.f("fk_extractions_documents_candidat_id_candidats"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["decide_par_id"], ["utilisateurs.id"],
            name=op.f("fk_extractions_documents_decide_par_id_utilisateurs"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents_candidats.id"],
            name=op.f("fk_extractions_documents_document_id_documents_candidats"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["bureaux.id"],
            name=op.f("fk_extractions_documents_tenant_id_bureaux"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_extractions_documents")),
        sa.UniqueConstraint(
            "tenant_id", "document_id", "champ",
            name=op.f("uq_extractions_documents_champ_par_document"),
        ),
    )
    for colonne in ("tenant_id", "document_id", "candidat_id", "statut"):
        op.create_index(op.f(f"ix_{TABLE}_{colonne}"), TABLE, [colonne], unique=False)


def downgrade() -> None:
    for colonne in ("statut", "candidat_id", "document_id", "tenant_id"):
        op.drop_index(op.f(f"ix_{TABLE}_{colonne}"), table_name=TABLE)
    op.drop_table(TABLE)
