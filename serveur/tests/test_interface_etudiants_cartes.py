"""Tableau des étudiants : cartes sous 640 px, tableau classique au-dessus (Chromium, API simulée)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from playwright.sync_api import Page, Route, sync_playwright

from app.interface.design import js_dossiers, vues_dossiers
from app.interface.routeur_interface import HTML_INTERFACE_FR

ORIGINE = "http://ui.test"
ETUDIANTS = [
    {"id": "c1", "nom": "BENALI", "prenom": "Sara", "email": "sara@exemple.fr", "numero_passeport": "P123456",
     "date_expiration_passeport": "2030-01-01", "programme_vise": "Master informatique", "etablissement_vise": "Université de Lyon",
     "consentement_signe": True},
    {"id": "c2", "nom": "KACI", "prenom": "Yanis", "consentement_signe": False},
    {"id": "c3", "nom": "AIT", "prenom": "Lina", "email": "lina@exemple.fr", "sexe": "F", "consentement_signe": False},
]


def _servir(route: Route) -> None:
    chemin = route.request.url.replace(ORIGINE, "")

    def rep(corps: Any) -> None:
        route.fulfill(status=200, body=json.dumps(corps), content_type="application/json")

    if chemin.startswith("/api/v1/auth/connexion"):
        return rep({"jeton_csrf": "t", "utilisateur": {"role": "employe", "nom_affiche": "Test", "email_verifie": True}})
    if chemin.startswith("/api/v1/candidats"):
        return rep({"total": len(ETUDIANTS), "elements": ETUDIANTS})
    if "/api/v1/" in chemin:
        return rep([])
    route.fulfill(status=200, body=HTML_INTERFACE_FR, content_type="text/html; charset=utf-8")


@pytest.fixture()
def page_etudiants() -> Iterator[Page]:
    with sync_playwright() as p:
        nav = p.chromium.launch(headless=True)
        page = nav.new_page(viewport={"width": 375, "height": 800})
        erreurs: list[str] = []
        page.on("pageerror", lambda e: erreurs.append(str(e)))
        page.route(f"{ORIGINE}/**", _servir)
        page.goto(ORIGINE + "/")
        page.wait_for_function("document.querySelector('#btn-se-deconnecter') && !document.querySelector('#btn-se-deconnecter').classList.contains('cache')")
        page.evaluate("allerVersVue('vue-etudiants')")
        page.wait_for_selector("#table-candidats tbody tr[role=row]")
        yield page
        assert erreurs == []
        nav.close()


def test_statique_pas_d_innerhtml_et_roles_de_tableau() -> None:
    assert "innerHTML" not in js_dossiers.JS_DOSSIERS
    assert "max-width: 640px" in vues_dossiers.CSS_DOSSIERS
    assert 'scope="col"' in vues_dossiers.HTML_ETUDIANTS and "<caption" in vues_dossiers.HTML_ETUDIANTS
    assert "\\" not in vues_dossiers.CSS_DOSSIERS


def test_etiquettes_data_label_et_semantique(page_etudiants: Page) -> None:
    lignes = page_etudiants.locator("#table-candidats tbody tr[role=row]")
    assert lignes.count() == 3
    etiquettes = lignes.first.locator("td").evaluate_all("tds => tds.map(t => t.getAttribute('data-label'))")
    assert etiquettes == [None, "Passeport", "Formation visée", "Fiche", "Consentement", None]
    assert page_etudiants.locator("#table-candidats > caption").count() == 1
    assert page_etudiants.locator("#table-candidats thead th[scope=col]").count() == 6
    assert page_etudiants.locator("#table-candidats tbody td[role=cell]").count() == 18


def test_cartes_a_375_px_sans_debordement(page_etudiants: Page) -> None:
    ligne = page_etudiants.locator("#table-candidats tbody tr[role=row]").first
    assert ligne.evaluate("e => getComputedStyle(e).display") == "flex"
    assert page_etudiants.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert page_etudiants.evaluate("(() => { const w = document.querySelector('.table-wrap:has(#table-candidats)'); return w.scrollWidth <= w.clientWidth; })()")
    # la colonne Fiche ne passe pas à la ligne : libellé et valeur sur la même ligne
    haut = page_etudiants.evaluate(
        "(() => { const e = document.querySelector('.etu-progression .etu-fiche-ligne'); const a = e.firstChild.getBoundingClientRect(), b = e.lastChild.getBoundingClientRect(); return [a.top + a.height / 2, b.top + b.height / 2]; })()")
    assert abs(haut[0] - haut[1]) < 6
    # cibles tactiles >= 44 px
    for h in page_etudiants.locator("#table-candidats .cellule-actions .btn").evaluate_all("bs => bs.map(b => b.getBoundingClientRect().height)"):
        assert h >= 44
    # étiquette visible via ::before
    contenu = page_etudiants.locator("#table-candidats td[data-label=Passeport]").first.evaluate("e => getComputedStyle(e, '::before').content")
    assert "Passeport" in contenu


def test_tableau_classique_a_1280_px(page_etudiants: Page) -> None:
    page_etudiants.set_viewport_size({"width": 1280, "height": 800})
    assert page_etudiants.locator("#table-candidats").evaluate("e => getComputedStyle(e).display") == "table"
    assert page_etudiants.locator("#table-candidats tbody tr").first.evaluate("e => getComputedStyle(e).display") == "table-row"
    assert page_etudiants.locator("#table-candidats thead").evaluate("e => getComputedStyle(e).display") == "table-header-group"
    haut = page_etudiants.evaluate(
        "(() => { const e = document.querySelector('.etu-progression .etu-fiche-ligne'); const a = e.firstChild.getBoundingClientRect(), b = e.lastChild.getBoundingClientRect(); return [a.top + a.height / 2, b.top + b.height / 2]; })()")
    assert abs(haut[0] - haut[1]) < 6


def test_fiche_court_une_teinte_et_pas_de_rognage_a_1280(page_etudiants: Page) -> None:
    page_etudiants.set_viewport_size({"width": 1280, "height": 800})
    textes = page_etudiants.locator("#table-candidats td.etu-progression strong").all_inner_texts()
    assert all("/" in t and " " not in t for t in textes)
    assert page_etudiants.locator("#table-candidats .barre-progression.ok, #table-candidats .barre-progression.alerte").count() == 0
    assert "fiche complète sur 3" in page_etudiants.inner_text("#etudiants-total")
