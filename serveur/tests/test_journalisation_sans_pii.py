"""Tests de la règle 5 : aucune donnée personnelle dans les journaux techniques."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.journalisation import FormateurSansPII, masquer_pii
from tests.conftest import DonneesBureauTest


def test_masquage_motifs_pii_dans_formateur() -> None:
    brut = (
        "Contact candidat.fictif@exemple.org né le 15/04/2001 ou 2001-04-15, "
        "tél +213 555 12 34 56 / 0555123456, passeport AB123456789."
    )
    propre = masquer_pii(brut)
    assert "candidat.fictif@exemple.org" not in propre
    assert "15/04/2001" not in propre
    assert "2001-04-15" not in propre
    assert "555 12 34 56" not in propre
    assert "0555123456" not in propre
    assert "AB123456789" not in propre

    formateur = FormateurSansPII("%(asctime)s %(levelname)s %(message)s")
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Erreur sur %s",
        args=("secret.perso@exemple.org",),
        exc_info=None,
    )
    sortie = formateur.format(record)
    assert "secret.perso@exemple.org" not in sortie
    assert "[email]" in sortie


def test_erreur_validation_ne_renvoie_ni_ne_journalise_la_valeur_soumise(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
    caplog,
) -> None:
    client = TestClient(application)
    valeur_sensible = " donnée_personnelle_sensible_12345 "
    with caplog.at_level(logging.INFO):
        rep = client.post(
            "/api/v1/auth/connexion",
            json={"email": valeur_sensible, "mot_de_passe": "SecretSensible!99"},
        )
    assert rep.status_code == 422
    assert "donnée_personnelle_sensible_12345" not in rep.text
    assert "SecretSensible!99" not in rep.text
    for enregistrement in caplog.records:
        assert "donnée_personnelle_sensible_12345" not in enregistrement.getMessage()
        assert "SecretSensible!99" not in enregistrement.getMessage()
