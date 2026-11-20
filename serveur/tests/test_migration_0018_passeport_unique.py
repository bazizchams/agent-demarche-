"""Migration 0018 (unicité du passeport par bureau) : up/down SQLite réel, doublons refusés, SQL PostgreSQL hors ligne."""

from __future__ import annotations

import io
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.config import RACINE_SERVEUR
from app.db.session import creer_moteur

REVISION = "0018_passeport_unique"
PRECEDENTE = "0017_depot_sans_fiche"
UNIQUE = "uq_candidats_tenant_idx_passeport"
ANCIEN = "ix_candidats_tenant_idx_passeport"


def _cfg(url: str) -> Config:
    cfg = Config(str(RACINE_SERVEUR / "alembic.ini"))
    cfg.set_main_option("script_location", str(RACINE_SERVEUR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def _index(url: str) -> dict[str, dict]:
    moteur = creer_moteur(url)
    try:
        return {i["name"]: i for i in inspect(moteur).get_indexes("candidats")}
    finally:
        moteur.dispose()


def _inserer_candidat(conn, tenant: str, idx_passeport: str | None) -> None:
    conn.execute(
        text(
            "INSERT INTO candidats (id, tenant_id, nom_chiffre, prenom_chiffre, idx_nom, idx_prenom, idx_passeport, "
            "consentement_signe, statut, cree_le, modifie_le) VALUES (:id, :t, 'n', 'p', 'a', 'b', :p, 0, 'actif', "
            "'2026-01-01 00:00:00', '2026-01-01 00:00:00')"
        ),
        {"id": uuid.uuid4().hex, "t": tenant, "p": idx_passeport},
    )


def _preparer_bureaux(conn, *tenants: str) -> None:
    for t in tenants:
        conn.execute(
            text(
                "INSERT INTO bureaux (id, nom, slug, actif, cree_le, modifie_le) "
                "VALUES (:id, :nom, :slug, 1, '2026-01-01 00:00:00', '2026-01-01 00:00:00')"
            ),
            {"id": t, "nom": f"B{t[:4]}", "slug": f"b-{t[:8]}"},
        )


def test_revision_courte_et_parent() -> None:
    assert len(REVISION) <= 32
    assert ScriptDirectory.from_config(_cfg("sqlite://")).get_revision(REVISION).down_revision == PRECEDENTE


def test_up_down_sqlite_index_unique_partiel(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'm18.db').as_posix()}"
    cfg = _cfg(url)
    command.upgrade(cfg, REVISION)
    index = _index(url)
    assert UNIQUE in index and ANCIEN not in index
    assert index[UNIQUE]["unique"] and index[UNIQUE]["column_names"] == ["tenant_id", "idx_passeport"]

    moteur = creer_moteur(url)
    t1, t2 = uuid.uuid4().hex, uuid.uuid4().hex
    try:
        with moteur.begin() as conn:
            _preparer_bureaux(conn, t1, t2)
            _inserer_candidat(conn, t1, "x" * 64)
            _inserer_candidat(conn, t2, "x" * 64)  # même valeur, autre bureau : autorisé
            _inserer_candidat(conn, t1, None)
            _inserer_candidat(conn, t1, None)  # NULL multiples : autorisés (index partiel)
        with pytest.raises(IntegrityError), moteur.begin() as conn:
            _inserer_candidat(conn, t1, "x" * 64)
    finally:
        moteur.dispose()

    command.downgrade(cfg, PRECEDENTE)
    index = _index(url)
    assert UNIQUE not in index and ANCIEN in index and not index[ANCIEN]["unique"]
    command.upgrade(cfg, "head")


def test_doublons_existants_font_echouer_la_migration_sans_rien_supprimer(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'm18_dup.db').as_posix()}"
    cfg = _cfg(url)
    command.upgrade(cfg, PRECEDENTE)
    moteur = creer_moteur(url)
    t = uuid.uuid4().hex
    try:
        with moteur.begin() as conn:
            _preparer_bureaux(conn, t)
            _inserer_candidat(conn, t, "d" * 64)
            _inserer_candidat(conn, t, "d" * 64)
        with pytest.raises(Exception, match="doublon"):
            command.upgrade(cfg, REVISION)
        with moteur.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM candidats")).scalar_one() == 2
    finally:
        moteur.dispose()
    index = _index(url)
    assert ANCIEN in index and UNIQUE not in index


def test_sql_postgresql_genere_hors_ligne_up_et_down() -> None:
    cfg = _cfg("postgresql+psycopg://utilisateur@localhost/base_fictive")
    cfg.output_buffer = io.StringIO()
    command.upgrade(cfg, f"{PRECEDENTE}:{REVISION}", sql=True)
    montee = cfg.output_buffer.getvalue()
    assert f"CREATE UNIQUE INDEX {UNIQUE}" in montee and "WHERE idx_passeport IS NOT NULL" in montee
    cfg.output_buffer = io.StringIO()
    command.downgrade(cfg, f"{REVISION}:{PRECEDENTE}", sql=True)
    assert f"CREATE INDEX {ANCIEN}" in cfg.output_buffer.getvalue()
