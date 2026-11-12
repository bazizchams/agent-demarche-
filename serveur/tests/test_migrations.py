"""Test des migrations Alembic (upgrade head -> downgrade base -> upgrade head)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.core.config import RACINE_SERVEUR
from app.db.session import creer_moteur


def test_cycle_complet_migrations_alembic(tmp_path: Path) -> None:
    chemin_db = (tmp_path / "migration_test.db").as_posix()
    url = f"sqlite:///{chemin_db}"

    cfg = Config(str(RACINE_SERVEUR / "alembic.ini"))
    cfg.set_main_option("script_location", str(RACINE_SERVEUR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)

    command.upgrade(cfg, "head")

    moteur = creer_moteur(url)
    try:
        tables = set(inspect(moteur).get_table_names())
        assert {
            "bureaux",
            "utilisateurs",
            "sessions_utilisateurs",
            "journal_audit",
            "candidats",
            "documents_candidats",
            "messages_discussion_dossier",
            "agents_locaux",
            "taches_dossiers",
            "etapes_taches",
            "verrous_dossiers",
            "decisions_validation_humaine",
            "abonnements_bureaux",
            "preuves_consentement_candidats",
            "demarches_bureaux",
            "voeux_formations",
            "alembic_version",
        }.issubset(tables)
    finally:
        moteur.dispose()

    command.downgrade(cfg, "base")

    moteur = creer_moteur(url)
    try:
        tables_apres_down = set(inspect(moteur).get_table_names()) - {"alembic_version"}
        assert tables_apres_down == set()
    finally:
        moteur.dispose()

    command.upgrade(cfg, "head")
