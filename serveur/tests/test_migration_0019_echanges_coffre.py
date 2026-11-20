"""Migration 0019 : colonne `taches_dossiers.portail` et table `echanges_coffre` (up/down SQLite reel)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app.core.config import RACINE_SERVEUR
from app.db.session import creer_moteur

REVISION = "0019_echanges_coffre"
PRECEDENTE = "0018_passeport_unique"


def _cfg(url: str) -> Config:
    cfg = Config(str(RACINE_SERVEUR / "alembic.ini"))
    cfg.set_main_option("script_location", str(RACINE_SERVEUR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def _etat(url: str) -> tuple[set[str], set[str]]:
    moteur = creer_moteur(url)
    try:
        insp = inspect(moteur)
        return set(insp.get_table_names()), {c["name"] for c in insp.get_columns("taches_dossiers")}
    finally:
        moteur.dispose()


def test_chaine_et_cycle_up_down(tmp_path: Path) -> None:
    cfg = _cfg(f"sqlite:///{(tmp_path / 'm.db').as_posix()}")
    script = ScriptDirectory.from_config(cfg)
    assert script.get_revision(REVISION).down_revision == PRECEDENTE
    assert script.get_current_head() == REVISION

    url = cfg.get_main_option("sqlalchemy.url")
    command.upgrade(cfg, PRECEDENTE)
    tables, colonnes = _etat(url)
    assert "echanges_coffre" not in tables and "portail" not in colonnes
    command.upgrade(cfg, "head")
    tables, colonnes = _etat(url)
    assert "echanges_coffre" in tables and "portail" in colonnes
    command.downgrade(cfg, PRECEDENTE)
    tables, colonnes = _etat(url)
    assert "echanges_coffre" not in tables and "portail" not in colonnes
    command.upgrade(cfg, "head")
