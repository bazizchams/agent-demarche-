"""Migration 0014 (points forts et projet professionnel) : up/down SQLite réel, SQL PostgreSQL hors ligne."""

from __future__ import annotations

import io
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app.core.config import RACINE_SERVEUR
from app.db.session import creer_moteur

REVISION = "0014_points_forts_projet"
PRECEDENTE = "0013_catalogue_formations"


def _cfg(url: str) -> Config:
    cfg = Config(str(RACINE_SERVEUR / "alembic.ini"))
    cfg.set_main_option("script_location", str(RACINE_SERVEUR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_revision_courte_une_seule_tete_et_parent() -> None:
    assert len(REVISION) <= 32
    script = ScriptDirectory.from_config(_cfg("sqlite://"))
    assert REVISION in {r.revision for r in script.walk_revisions()}  # la tête peut avancer (0016…)
    assert script.get_revision(REVISION).down_revision == PRECEDENTE


def test_up_down_sqlite(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'm14.db').as_posix()}"
    cfg = _cfg(url)
    command.upgrade(cfg, REVISION)
    moteur = creer_moteur(url)
    try:
        insp = inspect(moteur)
        assert {"points_forts_candidats", "projets_professionnels"} <= set(insp.get_table_names())
        assert {"tenant_id", "document_id", "extrait_chiffre", "texte_chiffre", "statut", "cle"} <= {
            c["name"] for c in insp.get_columns("points_forts_candidats")
        }
        assert {"tenant_id", "candidat_id", "texte_chiffre", "version", "statut"} <= {
            c["name"] for c in insp.get_columns("projets_professionnels")
        }
        assert ("tenant_id", "candidat_id", "cle") in {
            tuple(u["column_names"]) for u in insp.get_unique_constraints("points_forts_candidats")
        }
    finally:
        moteur.dispose()

    command.downgrade(cfg, PRECEDENTE)
    moteur = creer_moteur(url)
    try:
        tables = set(inspect(moteur).get_table_names())
        assert "points_forts_candidats" not in tables and "projets_professionnels" not in tables
        assert "fiches_formations" in tables
    finally:
        moteur.dispose()
    command.upgrade(cfg, REVISION)


def test_sql_postgresql_genere_hors_ligne_up_et_down() -> None:
    cfg = _cfg("postgresql+psycopg://utilisateur@localhost/base_fictive")
    cfg.output_buffer = io.StringIO()
    command.upgrade(cfg, f"{PRECEDENTE}:{REVISION}", sql=True)
    montee = cfg.output_buffer.getvalue()
    assert "CREATE TABLE points_forts_candidats" in montee and "CREATE TABLE projets_professionnels" in montee
    assert "REFERENCES bureaux (id) ON DELETE RESTRICT" in montee
    assert "UNIQUE (tenant_id, candidat_id)" in montee

    cfg.output_buffer = io.StringIO()
    command.downgrade(cfg, f"{REVISION}:{PRECEDENTE}", sql=True)
    descente = cfg.output_buffer.getvalue()
    assert "DROP TABLE points_forts_candidats" in descente and "DROP TABLE projets_professionnels" in descente
