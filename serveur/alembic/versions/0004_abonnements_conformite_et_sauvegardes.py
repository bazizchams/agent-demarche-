"""Phase 6 : tables abonnements_bureaux et preuves_consentement_candidats.

Revision ID: 0004_abonnements_conformite
Revises: 0003_taches_verrous_validations
Create Date: 2026-10-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.base import HorodatageUTC

revision: str = "0004_abonnements_conformite"
down_revision: str | None = "0003_taches_verrous_validations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "abonnements_bureaux",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column(
            "forfait",
            sa.Enum(
                "starter",
                "professionnel",
                "entreprise",
                name="forfait_abonnement",
                native_enum=False,
                length=30,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("quota_dossiers_mensuels", sa.Integer(), nullable=False),
        sa.Column("prix_mensuel_eur", sa.Integer(), nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=120), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(length=120), nullable=True),
        sa.Column("statut_stripe", sa.String(length=40), nullable=False),
        sa.Column("periode_courante_fin", HorodatageUTC(), nullable=True),
        sa.Column("cgu_version_acceptee", sa.String(length=40), nullable=True),
        sa.Column("cgu_acceptees_le", HorodatageUTC(), nullable=True),
        sa.Column("cgu_acceptees_par_id", sa.Uuid(), nullable=True),
        sa.Column("duree_conservation_jours", sa.Integer(), nullable=False),
        sa.Column("cree_le", HorodatageUTC(), nullable=False),
        sa.Column("modifie_le", HorodatageUTC(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["bureaux.id"],
            name="fk_abonnements_bureaux_tenant_id_bureaux",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["cgu_acceptees_par_id"],
            ["utilisateurs.id"],
            name="fk_abonnements_bureaux_cgu_acceptees_par_id_utilisateurs",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_abonnements_bureaux"),
        sa.UniqueConstraint("tenant_id", name="uq_abonnements_bureaux_tenant"),
    )
    op.create_index(
        "ix_abonnements_bureaux_tenant_id",
        "abonnements_bureaux",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_abonnements_bureaux_stripe_customer_id",
        "abonnements_bureaux",
        ["stripe_customer_id"],
        unique=False,
    )
    op.create_index(
        "ix_abonnements_bureaux_stripe_subscription_id",
        "abonnements_bureaux",
        ["stripe_subscription_id"],
        unique=False,
    )

    op.create_table(
        "preuves_consentement_candidats",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("candidat_id", sa.Uuid(), nullable=False),
        sa.Column(
            "version_texte_consentement", sa.String(length=40), nullable=False
        ),
        sa.Column("mode_recueil", sa.String(length=60), nullable=False),
        sa.Column("empreinte_texte_sha256", sa.String(length=64), nullable=False),
        sa.Column("recueilli_par_id", sa.Uuid(), nullable=True),
        sa.Column("recueilli_le", HorodatageUTC(), nullable=False),
        sa.Column("revoque_le", HorodatageUTC(), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["bureaux.id"],
            name="fk_preuves_consentement_tenant_id_bureaux",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["candidat_id"],
            ["candidats.id"],
            name="fk_preuves_consentement_candidat_id_candidats",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recueilli_par_id"],
            ["utilisateurs.id"],
            name="fk_preuves_consentement_recueilli_par_id_utilisateurs",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_preuves_consentement_candidats"),
    )
    op.create_index(
        "ix_preuves_consentement_candidats_tenant_id",
        "preuves_consentement_candidats",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_preuves_consentement_candidats_candidat_id",
        "preuves_consentement_candidats",
        ["candidat_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_preuves_consentement_candidats_candidat_id",
        table_name="preuves_consentement_candidats",
    )
    op.drop_index(
        "ix_preuves_consentement_candidats_tenant_id",
        table_name="preuves_consentement_candidats",
    )
    op.drop_table("preuves_consentement_candidats")

    op.drop_index(
        "ix_abonnements_bureaux_stripe_subscription_id",
        table_name="abonnements_bureaux",
    )
    op.drop_index(
        "ix_abonnements_bureaux_stripe_customer_id",
        table_name="abonnements_bureaux",
    )
    op.drop_index(
        "ix_abonnements_bureaux_tenant_id",
        table_name="abonnements_bureaux",
    )
    op.drop_table("abonnements_bureaux")
