"""Migration 0013 (catalogue de formations) : up/down sur SQLite réel, SQL PostgreSQL généré hors ligne."""

from __future__ import annotations

import io
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app.core.config import RACINE_SERVEUR
from app.db.session import creer_moteur

REVISION = "0013_catalogue_formations"


def _cfg(url: str) -> Config:
    cfg = Config(str(RACINE_SERVEUR / "alembic.ini"))
    cfg.set_main_option("script_location", str(RACINE_SERVEUR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_revision_courte_et_une_seule_tete() -> None:
    assert len(REVISION) <= 32
    assert len(ScriptDirectory.from_config(_cfg("sqlite://")).get_heads()) == 1


def test_up_down_sqlite(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'm13.db').as_posix()}"
    cfg = _cfg(url)
    command.upgrade(cfg, REVISION)
    moteur = creer_moteur(url)
    try:
        insp = inspect(moteur)
        assert "fiches_formations" in insp.get_table_names()
        colonnes = {c["name"] for c in insp.get_columns("fiches_formations")}
        assert {"tenant_id", "cle", "etablissement", "intitule", "francais_min", "date_releve",
                "exigences_a_verifier", "statut", "aucune_exigence_confirmee"} <= colonnes
        uniques = {tuple(u["column_names"]) for u in insp.get_unique_constraints("fiches_formations")}
        assert ("tenant_id", "cle") in uniques
    finally:
        moteur.dispose()

    command.downgrade(cfg, "0012_extractions")  # annule 0013 (et la branche action_tache, non ancêtre de la cible)
    moteur = creer_moteur(url)
    try:
        assert "fiches_formations" not in inspect(moteur).get_table_names()
    finally:
        moteur.dispose()
    command.upgrade(cfg, REVISION)


def test_sql_postgresql_genere_hors_ligne_up_et_down() -> None:
    cfg = _cfg("postgresql+psycopg://utilisateur@localhost/base_fictive")
    precedente = "0012_extractions"  # parent de la fusion : suffit pour borner la plage hors ligne

    cfg.output_buffer = io.StringIO()
    command.upgrade(cfg, f"{precedente}:{REVISION}", sql=True)
    montee = cfg.output_buffer.getvalue()
    assert "CREATE TABLE fiches_formations" in montee
    assert "REFERENCES bureaux (id) ON DELETE RESTRICT" in montee
    assert "UNIQUE (tenant_id, cle)" in montee
    assert "DEFAULT false" in montee

    cfg.output_buffer = io.StringIO()
    command.downgrade(cfg, f"{REVISION}:{precedente}", sql=True)
    descente = cfg.output_buffer.getvalue()
    assert "DROP TABLE fiches_formations" in descente
