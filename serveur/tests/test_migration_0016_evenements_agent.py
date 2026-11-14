"""Migration 0016 (événements de la discussion de l'agent) : up/down SQLite réel, SQL PostgreSQL hors ligne."""

from __future__ import annotations

import io
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app.core.config import RACINE_SERVEUR
from app.db.session import creer_moteur

REVISION = "0016_evenements_agent"
PRECEDENTE = "0014_points_forts_projet"


def _cfg(url: str) -> Config:
    cfg = Config(str(RACINE_SERVEUR / "alembic.ini"))
    cfg.set_main_option("script_location", str(RACINE_SERVEUR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_revision_courte_et_parent() -> None:
    assert len(REVISION) <= 32
    script = ScriptDirectory.from_config(_cfg("sqlite://"))
    assert script.get_revision(REVISION).down_revision == PRECEDENTE


def test_up_down_sqlite(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'm16.db').as_posix()}"
    cfg = _cfg(url)
    command.upgrade(cfg, REVISION)
    moteur = creer_moteur(url)
    try:
        insp = inspect(moteur)
        assert "evenements_agent" in insp.get_table_names()
        colonnes = {c["name"] for c in insp.get_columns("evenements_agent")}
        assert {"tenant_id", "tache_id", "seq", "type", "auteur", "code", "texte_chiffre", "traite_le", "cree_le"} <= colonnes
        assert "texte" not in colonnes  # jamais de texte en clair
        assert ("tenant_id", "tache_id", "seq") in {
            tuple(u["column_names"]) for u in insp.get_unique_constraints("evenements_agent")
        }
    finally:
        moteur.dispose()
    command.downgrade(cfg, PRECEDENTE)
    moteur = creer_moteur(url)
    try:
        assert "evenements_agent" not in set(inspect(moteur).get_table_names())
    finally:
        moteur.dispose()
    command.upgrade(cfg, REVISION)


def test_sql_postgresql_genere_hors_ligne_up_et_down() -> None:
    cfg = _cfg("postgresql+psycopg://utilisateur@localhost/base_fictive")
    cfg.output_buffer = io.StringIO()
    command.upgrade(cfg, f"{PRECEDENTE}:{REVISION}", sql=True)
    montee = cfg.output_buffer.getvalue()
    assert "CREATE TABLE evenements_agent" in montee
    assert "REFERENCES taches_dossiers (id) ON DELETE CASCADE" in montee
    assert "UNIQUE (tenant_id, tache_id, seq)" in montee
    cfg.output_buffer = io.StringIO()
    command.downgrade(cfg, f"{REVISION}:{PRECEDENTE}", sql=True)
    assert "DROP TABLE evenements_agent" in cfg.output_buffer.getvalue()
