"""Moteur et fabrique de sessions."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

import app.db.tenant  # noqa: F401  (enregistre les garde-fous multi-bureaux)


def creer_moteur(url: str) -> Engine:
    est_sqlite = url.startswith("sqlite")
    moteur = create_engine(
        url,
        # Les valeurs des paramètres SQL n'apparaissent jamais dans les messages d'erreur
        # (elles peuvent contenir des données personnelles).
        hide_parameters=True,
        connect_args={"check_same_thread": False} if est_sqlite else {},
    )
    if est_sqlite:

        @event.listens_for(moteur, "connect")
        def _pragmas_sqlite(connexion_dbapi, _enregistrement) -> None:
            curseur = connexion_dbapi.cursor()
            curseur.execute("PRAGMA foreign_keys=ON")
            curseur.execute("PRAGMA busy_timeout=5000")
            if ":memory:" not in url:
                curseur.execute("PRAGMA journal_mode=WAL")
            curseur.close()

    return moteur


def creer_fabrique_sessions(moteur: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=moteur, expire_on_commit=False, autoflush=True)
