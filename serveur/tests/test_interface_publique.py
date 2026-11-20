"""Vitrine publique (/bienvenue, /inscription) : tests statiques puis Playwright
(mouvement réduit, sans JavaScript, mobile 375 px). Les tests Playwright sont ignorés si
Chromium est indisponible."""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.interface import vitrine_css, vitrine_html, vitrine_js
from app.services.abonnements import CATALOGUE_FORFAITS

HOTE = "http://interface.local"


def _texte_visible(html: str) -> str:
    html = re.sub(r"<(script|style)\b.*?</\1>", "", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", html)


# --------------------------------------------------------------------------- statique


@pytest.mark.parametrize("chemin", ["/bienvenue", "/inscription"])
def test_structure_et_accessibilite(application: FastAPI, chemin: str) -> None:
    html = TestClient(application).get(chemin).text
    assert '<html lang="fr">' in html
    assert len(re.findall(r"<h1[ >]", html)) == 1
    for balise in ("<header", "<main", "<footer", "<nav"):
        assert balise in html
    assert 'class="sr-focus" href="#contenu"' in html
    assert "<title>" in html and 'name="description"' in html


def test_forfaits_lus_dans_le_catalogue(application: FastAPI) -> None:
    html = TestClient(application).get("/bienvenue").text
    for libelle, prix, quota in CATALOGUE_FORFAITS.values():
        assert libelle in html and f"{prix}&nbsp;&euro;" in html and f"Jusqu'à {quota} dossiers" in html
    assert 49 in [p for _, p, _ in CATALOGUE_FORFAITS.values()]


def test_sections_attendues(application: FastAPI) -> None:
    html = TestClient(application).get("/bienvenue").text
    for ancre in ('id="comment"', 'id="securite"', 'id="tarifs"', 'id="faq"', "data-flux", "data-scene"):
        assert ancre in html
    assert html.count("<details") >= 5


def test_copy_sans_fausse_promesse(application: FastAPI) -> None:
    texte = _texte_visible(TestClient(application).get("/bienvenue").text).lower()
    for interdit in ("100 %", "100%", "satim", "garanti ", "automatiquement soumis", "sans intervention"):
        assert interdit not in texte
    assert "validation" in texte and "captcha" in texte
    assert "paiement en ligne n'est pas disponible" in texte


def test_invariants_de_code() -> None:
    sources = vitrine_css.STYLE_PUBLIC + vitrine_js.SCRIPT_VITRINE + vitrine_js.SCRIPT_SCENE
    sources += vitrine_js.SCRIPT_INSCRIPTION + vitrine_html.corps_bienvenue()
    for interdit in ("innerHTML", "eval(", "console.log", "document.write", chr(92)):
        assert interdit not in sources
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", vitrine_css.STYLE_PUBLIC)  # tokens uniquement
    assert "rgba(" not in vitrine_css.STYLE_PUBLIC


def test_mouvement_conditionnel_et_pause() -> None:
    css = vitrine_css.STYLE_PUBLIC
    bloc = css.split("@media (prefers-reduced-motion: no-preference)", 1)[1]
    assert "@keyframes fx-doc" in bloc and "@keyframes fx-doc" not in css.split("no-preference", 1)[0]
    assert "hors-ecran" in css and "anim-pause" in css
    for propriete in ("width:", "height:", "top:", "left:", "margin"):  # animations : transform/opacité
        for kf in re.findall(r"@keyframes [\w-]+ \{(.*?)\}\s*\n", bloc):
            assert propriete not in kf


def test_three_epingle_charge_paresseusement() -> None:
    js = vitrine_js.SCRIPT_SCENE
    assert re.search(r"cdnjs\.cloudflare\.com/ajax/libs/three\.js/r\d+/three\.min\.js", js)
    assert "sha384-" in js and "crossOrigin" in js
    assert "prefers-reduced-motion" in js and "hover: hover" in js and "requestIdleCallback" in js
    assert js.count("<script") == 1 and "<script src" not in js  # pas de balise bloquante


def test_inscription_garde_ses_messages_et_preselection(application: FastAPI) -> None:
    html = TestClient(application).get("/inscription").text
    assert "form.elements[fautif]" in html and "URLSearchParams" in html
    assert 'data-quota="30"' in html


# --------------------------------------------------------------------------- Playwright


@contextmanager
def _page(application: FastAPI, **contexte: Any) -> Iterator[tuple[Any, list[str]]]:
    sync_api = pytest.importorskip("playwright.sync_api")
    client = TestClient(application)
    erreurs: list[str] = []
    with sync_api.sync_playwright() as p:
        try:
            navigateur = p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"Chromium indisponible : {exc}")
        try:
            ctx = navigateur.new_context(**contexte)
            page = ctx.new_page()
            page.on("pageerror", lambda e: erreurs.append(str(e)))

            def servir(route: Any) -> None:
                url = route.request.url
                if not url.startswith(HOTE):
                    route.abort()
                    return
                rep = client.get(url[len(HOTE):] or "/")
                route.fulfill(status=rep.status_code, body=rep.content,
                              headers={"content-type": rep.headers.get("content-type", "text/html")})

            page.route("**/*", servir)
            yield page, erreurs
        finally:
            navigateur.close()


def test_mouvement_reduit_contenu_complet_et_aucune_animation(application: FastAPI) -> None:
    with _page(application, reduced_motion="reduce", viewport={"width": 1280, "height": 800}) as (page, erreurs):
        page.goto(HOTE + "/bienvenue", wait_until="load")
        page.wait_for_timeout(500)
        assert page.evaluate("document.getAnimations().filter(a => a.playState === 'running').length") == 0
        for sel in (".fx-b-ok", "#etape-4 .il-b-b", ".v-forfaits li:last-child", ".v-faq"):
            assert float(page.evaluate(f"getComputedStyle(document.querySelector('{sel}')).opacity")) == 1.0
        assert page.evaluate("!document.querySelector('[data-scene] canvas')")  # pas de scène 3D
        assert not page.is_visible("[data-pause-anim]")
        assert erreurs == []


def test_sans_javascript_tout_est_lisible(application: FastAPI) -> None:
    with _page(application, java_script_enabled=False, viewport={"width": 1280, "height": 800}) as (page, _):
        page.goto(HOTE + "/bienvenue", wait_until="load")
        for sel in ("h1", "#etape-1 h3", "#etape-4 h3", ".v-forfaits", "#faq summary", ".v-appel"):
            assert page.is_visible(sel), sel
        assert float(page.evaluate("getComputedStyle(document.querySelector('.v-forfaits li')).opacity")) == 1.0
        page.goto(HOTE + "/inscription", wait_until="load")
        assert page.is_visible("form#formulaire")


@pytest.mark.parametrize("chemin", ["/bienvenue", "/inscription"])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_mobile_375_sans_debordement(application: FastAPI, chemin: str, theme: str) -> None:
    with _page(application, viewport={"width": 375, "height": 812}, color_scheme=theme) as (page, erreurs):
        page.goto(HOTE + chemin, wait_until="load")
        page.wait_for_timeout(600)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert page.evaluate("!document.querySelector('[data-scene] canvas')")  # mobile : repli CSS
        assert erreurs == []


def test_pause_manuelle_et_clavier(application: FastAPI) -> None:
    with _page(application, viewport={"width": 1280, "height": 800}) as (page, _):
        page.goto(HOTE + "/bienvenue", wait_until="load")
        page.click("[data-pause-anim]")
        assert page.evaluate("document.documentElement.classList.contains('anim-pause')")
        assert page.get_attribute("[data-pause-anim]", "aria-pressed") == "true"
        page.reload(wait_until="load")
        page.keyboard.press("Tab")
        assert page.evaluate("document.activeElement.className") == "sr-focus"


def test_repli_si_cdn_inaccessible(application: FastAPI) -> None:
    with _page(application, viewport={"width": 1280, "height": 800}) as (page, erreurs):
        page.goto(HOTE + "/bienvenue", wait_until="load")
        page.wait_for_timeout(3500)  # le CDN est refusé par la route : le fond CSS reste en place
        assert page.evaluate("!document.querySelector('[data-scene] canvas')")
        assert page.is_visible("h1") and page.is_visible(".flux")
        assert erreurs == []
