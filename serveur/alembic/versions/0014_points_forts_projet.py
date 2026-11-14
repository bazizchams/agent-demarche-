"""Points forts vérifiables (P2) et projet professionnel brouillon (P3).

Revision ID: 0014_points_forts_projet
Revises: 0013_catalogue_formations
Create Date: 2026-11-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.base import HorodatageUTC

revision: str = "0014_points_forts_projet"
down_revision: str | Sequence[str] | None = "0013_catalogue_formations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PF = "points_forts_candidats"
PP = "projets_professionnels"


def upgrade() -> None:
    op.create_table(
        PF,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("candidat_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("categorie", sa.String(length=20), nullable=False),
        sa.Column("regle", sa.String(length=40), nullable=False),
        sa.Column("cle", sa.String(length=64), nullable=False),
        sa.Column("texte_chiffre", sa.Text(), nullable=False),
        sa.Column("extrait_chiffre", sa.Text(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column(
            "statut",
            sa.Enum(
                "a_verifier", "confirme", "rejete",
                name="statut_point_fort", native_enum=False, length=16, create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("alerte", sa.String(length=40), nullable=True),
        sa.Column("champ_fiche", sa.String(length=20), nullable=True),
        sa.Column("valeur_fiche", sa.String(length=2), nullable=True),
        sa.Column("decide_par_id", sa.Uuid(), nullable=True),
        sa.Column("decide_le", HorodatageUTC(), nullable=True),
        sa.Column("applique_le", HorodatageUTC(), nullable=True),
        sa.Column("cree_le", HorodatageUTC(), nullable=False),
        sa.Column("modifie_le", HorodatageUTC(), nullable=False),
        sa.CheckConstraint("extrait_chiffre <> ''", name=op.f("ck_points_forts_candidats_preuve_obligatoire")),
        sa.ForeignKeyConstraint(
            ["candidat_id"], ["candidats.id"],
            name=op.f("fk_points_forts_candidats_candidat_id_candidats"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents_candidats.id"],
            name=op.f("fk_points_forts_candidats_document_id_documents_candidats"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["decide_par_id"], ["utilisateurs.id"],
            name=op.f("fk_points_forts_candidats_decide_par_id_utilisateurs"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["bureaux.id"],
            name=op.f("fk_points_forts_candidats_tenant_id_bureaux"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_points_forts_candidats")),
        sa.UniqueConstraint("tenant_id", "candidat_id", "cle", name="uq_points_forts_candidats_cle"),
    )
    for colonne in ("tenant_id", "candidat_id", "document_id", "statut"):
        op.create_index(op.f(f"ix_{PF}_{colonne}"), PF, [colonne], unique=False)

    op.create_table(
        PP,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("candidat_id", sa.Uuid(), nullable=False),
        sa.Column("texte_chiffre", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "statut",
            sa.Enum(
                "brouillon", "valide",
                name="statut_projet", native_enum=False, length=12, create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("origine", sa.String(length=10), nullable=False),
        sa.Column("valide_par_id", sa.Uuid(), nullable=True),
        sa.Column("valide_le", HorodatageUTC(), nullable=True),
        sa.Column("cree_le", HorodatageUTC(), nullable=False),
        sa.Column("modifie_le", HorodatageUTC(), nullable=False),
        sa.CheckConstraint("version >= 1", name=op.f("ck_projets_professionnels_version_positive")),
        sa.ForeignKeyConstraint(
            ["candidat_id"], ["candidats.id"],
            name=op.f("fk_projets_professionnels_candidat_id_candidats"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["valide_par_id"], ["utilisateurs.id"],
            name=op.f("fk_projets_professionnels_valide_par_id_utilisateurs"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["bureaux.id"],
            name=op.f("fk_projets_professionnels_tenant_id_bureaux"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projets_professionnels")),
        sa.UniqueConstraint("tenant_id", "candidat_id", name="uq_projets_professionnels_candidat"),
    )
    for colonne in ("tenant_id", "candidat_id"):
        op.create_index(op.f(f"ix_{PP}_{colonne}"), PP, [colonne], unique=False)


def downgrade() -> None:
    for colonne in ("candidat_id", "tenant_id"):
        op.drop_index(op.f(f"ix_{PP}_{colonne}"), table_name=PP)
    op.drop_table(PP)
    for colonne in ("statut", "document_id", "candidat_id", "tenant_id"):
        op.drop_index(op.f(f"ix_{PF}_{colonne}"), table_name=PF)
    op.drop_table(PF)
