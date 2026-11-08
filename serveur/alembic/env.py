"""Environnement Alembic (compatible SQLite local et PostgreSQL en ligne)."""

from __future__ import annotations

from alembic import context
from sqlalchemy import pool

import app.modeles  # noqa: F401  (charge toutes les tables dans Base.metadata)
from app.core.config import obtenir_parametres
from app.db.base import Base
from app.db.session import creer_moteur

config = context.config
target_metadata = Base.metadata


def _url_base() -> str:
    url_cfg = config.get_main_option("sqlalchemy.url")
    if url_cfg:
        return url_cfg
    return obtenir_parametres().url_base_donnees


def run_migrations_offline() -> None:
    url = _url_base()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = config.attributes.get("connection")
    if connectable is not None:
        est_sqlite = connectable.dialect.name == "sqlite"
        context.configure(
            connection=connectable,
            target_metadata=target_metadata,
            render_as_batch=est_sqlite,
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    url = _url_base()
    moteur = creer_moteur(url)
    if url.startswith("sqlite"):
        moteur = moteur.execution_options(isolation_level="AUTOCOMMIT")
    try:
        with moteur.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=url.startswith("sqlite"),
                poolclass=pool.NullPool,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        moteur.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
