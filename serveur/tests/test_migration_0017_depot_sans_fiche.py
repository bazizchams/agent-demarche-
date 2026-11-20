"""Migration 0017 (dépôt de passeport sans fiche) : up/down SQLite réel, SQL PostgreSQL hors ligne."""

from __future__ import annotations

import io
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app.core.config import RACINE_SERVEUR
from app.db.session import creer_moteur

REVISION = "0017_depot_sans_fiche"
PRECEDENTE = "0016_evenements_agent"
TABLE = "depots_passeport"


def _cfg(url: str) -> Config:
    cfg = Config(str(RACINE_SERVEUR / "alembic.ini"))
    cfg.set_main_option("script_location", str(RACINE_SERVEUR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_revision_courte_et_parent() -> None:
    assert len(REVISION) <= 32
    script = ScriptDirectory.from_config(_cfg("sqlite://"))
    assert script.get_revision(REVISION).down_revision == PRECEDENTE


def test_tete_unique_des_revisions() -> None:
    script = ScriptDirectory.from_config(_cfg("sqlite://"))
    # Une seule tête, et 0017 fait partie de l'historique (les migrations suivantes s'empilent dessus).
    tetes = script.get_heads()
    assert len(tetes) == 1
    assert REVISION in {r.revision for r in script.walk_revisions()}


def test_up_down_sqlite(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'm17.db').as_posix()}"
    cfg = _cfg(url)
    command.upgrade(cfg, REVISION)
    moteur = creer_moteur(url)
    try:
        insp = inspect(moteur)
        assert TABLE in insp.get_table_names()
        colonnes = {c["name"] for c in insp.get_columns(TABLE)}
        assert {
            "tenant_id",
            "depose_par_id",
            "nom_fichier_chiffre",
            "type_mime",
            "taille_octets",
            "empreinte_contenu",
            "chemin_stockage_relatif",
            "statut",
            "propositions_chiffrees",
            "cree_le",
        } <= colonnes
        assert "nom_fichier" not in colonnes  # jamais de nom de fichier en clair
        assert "propositions" not in colonnes  # jamais de propositions en clair
    finally:
        moteur.dispose()
    command.downgrade(cfg, PRECEDENTE)
    moteur = creer_moteur(url)
    try:
        assert TABLE not in set(inspect(moteur).get_table_names())
    finally:
        moteur.dispose()
    command.upgrade(cfg, REVISION)


def test_sql_postgresql_genere_hors_ligne_up_et_down() -> None:
    cfg = _cfg("postgresql+psycopg://utilisateur@localhost/base_fictive")
    cfg.output_buffer = io.StringIO()
    command.upgrade(cfg, f"{PRECEDENTE}:{REVISION}", sql=True)
    montee = cfg.output_buffer.getvalue()
    assert f"CREATE TABLE {TABLE}" in montee
    cfg.output_buffer = io.StringIO()
    command.downgrade(cfg, f"{REVISION}:{PRECEDENTE}", sql=True)
    assert f"DROP TABLE {TABLE}" in cfg.output_buffer.getvalue()
