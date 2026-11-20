"""Régressions de performance de l'interface : compression, cache par ETag, appels réseau."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.interface.design.js_dossiers import JS_DOSSIERS
from app.interface.design.page import JS_DEMARRAGE
from app.interface.design.styles import LIEN_POLICES
from app.main import creer_application


def _client() -> TestClient:
    return TestClient(creer_application())


def test_page_interface_est_compressee_en_gzip() -> None:
    rep = _client().get("/", headers={"Accept-Encoding": "gzip"})
    assert rep.status_code == 200
    assert rep.headers["content-encoding"] == "gzip"
    assert int(rep.headers["content-length"]) < 250_000


def test_page_interface_revalidee_par_etag_sans_corps() -> None:
    client = _client()
    premiere = client.get("/")
    etag = premiere.headers["etag"]
    assert premiere.headers["cache-control"] == "no-cache"
    seconde = client.get("/", headers={"If-None-Match": etag})
    assert seconde.status_code == 304
    assert seconde.content == b""


def test_polices_non_bloquantes_pour_le_rendu() -> None:
    assert "display=swap" in LIEN_POLICES
    assert 'rel="preconnect"' in LIEN_POLICES
    assert 'media="print"' in LIEN_POLICES


def test_demarrage_charge_en_parallele_et_sans_doublon() -> None:
    assert "Promise.all([chargerCandidats(), rafraichirTableauDeBord()])" in JS_DEMARRAGE
    # les GET identiques simultanés sont partagés
    assert "appelsEnVol" in JS_DOSSIERS


def test_interrogations_suspendues_onglet_cache() -> None:
    from app.interface.design.ecran_discussion_agent import assembler_discussion_agent  # noqa: F401
    import app.interface.design.ecran_discussion_agent as da
    import app.interface.design.js_ouverture_pc as ouv

    assert "if (document.hidden) return;" in open(da.__file__, encoding="utf-8").read()
    assert "if (document.hidden) return;" in open(ouv.__file__, encoding="utf-8").read()
