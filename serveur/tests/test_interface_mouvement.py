"""Système de mouvement : tokens, classes, API `Mouvement`, no-op en mouvement réduit, repli sans JS."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.interface.design import motion, styles
from app.interface.routeur_interface import HTML_INTERFACE_FR

# --------------------------------------------------------------------------- statique


@pytest.mark.parametrize(
    "fragment",
    [
        "--mo-dur-1: 120ms", "--mo-dur-2: 220ms", "--mo-dur-3: 420ms", "--mo-dur-4: 700ms",
        "--mo-ease-out: cubic-bezier(.16, 1, .3, 1)", "--mo-ease-inout: cubic-bezier(.65, 0, .35, 1)",
        "--mo-ease-spring: cubic-bezier(", "--mo-ease-spring: linear(", "@supports (transition-timing-function: linear(0, 1))",
    ],
)
def test_tokens_de_mouvement_presents(fragment: str) -> None:
    assert fragment in motion.CSS_MOUVEMENT
    assert fragment in styles.CSS_DESIGN
    assert fragment in HTML_INTERFACE_FR


@pytest.mark.parametrize("classe", [".mo-reveal", ".mo-stagger", ".mo-press", ".mo-lift", ".mo-skel", ".mo-pulse", ".mo-in"])
def test_classes_du_contrat_presentes(classe: str) -> None:
    assert classe in motion.CSS_MOUVEMENT


def test_masquage_initial_uniquement_sous_mo_actif() -> None:
    css = motion.CSS_MOUVEMENT
    assert "html.mo-actif .mo-reveal:not(.mo-in)" in css
    # Aucune règle ne masque .mo-reveal hors de html.mo-actif (hors forçage visible en mouvement réduit).
    for regle in css.split("}"):
        if "opacity: 0" in regle and ".mo-reveal" in regle and "@keyframes" not in regle:
            assert "html.mo-actif" in regle, regle
    assert "document.documentElement.classList.add(\"mo-actif\")" in motion.SCRIPT_MOUVEMENT_AMORCE
    assert motion.SCRIPT_MOUVEMENT_AMORCE in HTML_INTERFACE_FR
    assert HTML_INTERFACE_FR.index(motion.SCRIPT_MOUVEMENT_AMORCE) < HTML_INTERFACE_FR.index("<style>")


def test_mouvement_reduit_force_l_affichage() -> None:
    bloc = motion.CSS_MOUVEMENT.split("@media (prefers-reduced-motion: reduce)")[1]
    assert ".mo-reveal" in bloc and "opacity: 1 !important" in bloc and "animation: none !important" in bloc


def test_animations_limitees_a_transform_et_opacite() -> None:
    css = motion.CSS_MOUVEMENT
    for interdit in ("width:", "height:", "top:", "left:", "margin:"):
        for regle in css.split("}"):
            if "@keyframes" in regle:
                assert interdit not in regle.split("{", 2)[-1] or "transform" in regle, regle


def test_api_mouvement_et_js_propre() -> None:
    js = motion.JS_MOUVEMENT
    for nom in ("reduit", "reveler", "cascade", "compteur", "transitionVue", "pret"):
        assert nom in js.split("window.Mouvement = ")[1]
    assert HTML_INTERFACE_FR.index("window.Mouvement = ") < HTML_INTERFACE_FR.index("function allerVersVue(")
    for interdit in (".innerHTML", "eval(", "console.", chr(92)):
        assert interdit not in js and interdit not in motion.CSS_MOUVEMENT
    assert "prefers-reduced-motion" in js
    assert "700" in js


def test_coque_utilise_le_mouvement() -> None:
    assert "Mouvement.transitionVue" in HTML_INTERFACE_FR
    assert "Mouvement.basculerTheme" in HTML_INTERFACE_FR
    assert "Mouvement.sortie" in HTML_INTERFACE_FR
    assert 'class="connexion-form mo-stagger"' in HTML_INTERFACE_FR


# --------------------------------------------------------------------------- navigateur (Playwright)


@contextmanager
def _page(application: FastAPI, **options: Any) -> Iterator[Any]:
    sync_api = pytest.importorskip("playwright.sync_api")
    client = TestClient(application)

    def reponse(statut: int, corps: Any) -> tuple[int, str, bytes]:
        return statut, "application/json", json.dumps(corps).encode()

    moquettes = {
        ("POST", "/api/v1/auth/connexion"): reponse(200, {
            "jeton_csrf": "csrf-test", "utilisateur": {"role": "employe", "nom_affiche": "Testeur"}}),
        ("GET", "/api/v1/candidats"): reponse(200, {"total": 0, "elements": []}),
    }
    with sync_api.sync_playwright() as p:
        try:
            navigateur = p.chromium.launch()
        except Exception as exc:  # navigateur non installé
            pytest.skip(f"Chromium indisponible : {exc}")
        try:
            contexte = navigateur.new_context(viewport={"width": 1280, "height": 900}, **options)
            page = contexte.new_page()
            erreurs: list[str] = []
            page.on("pageerror", lambda e: erreurs.append(str(e)))

            def servir(route: Any) -> None:
                chemin = route.request.url.split("http://interface.local", 1)[1] or "/"
                sans_requete = chemin.split("?", 1)[0]
                if sans_requete.startswith("/api/"):
                    statut, type_contenu, corps = moquettes.get(
                        (route.request.method, sans_requete), reponse(404, {"detail": "non simulé"}))
                    route.fulfill(status=statut, content_type=type_contenu, body=corps)
                    return
                rep = client.get(chemin)
                route.fulfill(status=rep.status_code,
                              headers={"content-type": rep.headers.get("content-type", "text/html")},
                              body=rep.content)

            page.route("http://interface.local/**", servir)
            page.goto("http://interface.local/", wait_until="domcontentloaded")
            yield page, erreurs
        finally:
            navigateur.close()


def _injecter_bloc_de_test(page: Any) -> None:
    page.evaluate(
        """() => {
          const c = document.createElement('div');
          c.id = 'banc-mouvement';
          const r = document.createElement('p'); r.className = 'mo-reveal'; r.id = 'banc-reveal'; r.textContent = 'Bloc';
          const s = document.createElement('ul'); s.className = 'mo-stagger'; s.id = 'banc-stagger';
          for (let i = 0; i < 3; i++) { const li = document.createElement('li'); li.textContent = 'ligne ' + i; s.appendChild(li); }
          c.append(r, s);
          document.getElementById('contenu').appendChild(c);
        }""")


def test_mouvement_actif_et_reveal_au_defilement(application: FastAPI) -> None:
    with _page(application) as (page, erreurs):
        page.wait_for_function("window.Mouvement && document.documentElement.classList.contains('mo-actif')")
        assert page.evaluate("window.Mouvement.reduit()") is False
        assert page.evaluate("window.Mouvement.pret instanceof Promise") is True
        _injecter_bloc_de_test(page)
        page.wait_for_function("document.getElementById('banc-reveal').classList.contains('mo-in')", timeout=3000) \
            if page.evaluate("document.getElementById('banc-reveal').getBoundingClientRect().top < innerHeight") else None
        page.evaluate("document.getElementById('banc-reveal').scrollIntoView()")
        page.wait_for_function("document.getElementById('banc-reveal').classList.contains('mo-in')", timeout=3000)
        page.wait_for_function("document.getElementById('banc-stagger').classList.contains('mo-in')", timeout=3000)
        assert page.evaluate("document.getElementById('banc-stagger').children[2].style.getPropertyValue('--i')") == "2"
        page.wait_for_timeout(900)
        assert page.evaluate("getComputedStyle(document.getElementById('banc-reveal')).opacity") == "1"
    assert erreurs == []


def test_mouvement_reduit_no_op_et_tout_visible(application: FastAPI) -> None:
    with _page(application, reduced_motion="reduce") as (page, erreurs):
        page.wait_for_function("window.Mouvement")
        assert page.evaluate("window.Mouvement.reduit()") is True
        assert page.evaluate("document.documentElement.classList.contains('mo-actif')") is False
        _injecter_bloc_de_test(page)
        # Affichés immédiatement, sans défilement ni attente : aucune animation en cours.
        page.wait_for_function("document.getElementById('banc-reveal').classList.contains('mo-in')", timeout=2000)
        assert page.evaluate("getComputedStyle(document.getElementById('banc-reveal')).opacity") == "1"
        assert page.evaluate(
            "getComputedStyle(document.getElementById('banc-stagger').children[1]).opacity") == "1"
        assert page.evaluate("document.getAnimations().filter(a => a.animationName === 'mo-entree').length") == 0
        # compteur : valeur finale immédiate ; transitionVue : rien à jouer ; cascade : aucune classe ajoutée.
        page.evaluate("document.getElementById('banc-reveal').textContent = '0'")
        page.evaluate("window.Mouvement.compteur(document.getElementById('banc-reveal'), 42, 700)")
        assert page.inner_text("#banc-reveal") == "42"
        page.evaluate("window.Mouvement.cascade(document.querySelectorAll('#banc-stagger li'))")
        assert page.evaluate("document.querySelectorAll('.mo-casc').length") == 0
        page.wait_for_function("document.getElementById('etat-utilisateur').textContent.includes('Testeur')")
        page.click('aside button.nav-btn[data-vue="vue-etudiants"]')
        assert page.evaluate("document.getAnimations().filter(a => a.effect && a.effect.target && "
                             "a.effect.target.id === 'vue-etudiants').length") == 0
        assert page.evaluate("document.activeElement.tagName") == "H2"
    assert erreurs == []


def test_compteur_atteint_la_valeur_et_ne_depasse_pas_700_ms(application: FastAPI) -> None:
    with _page(application) as (page, erreurs):
        page.wait_for_function("window.Mouvement")
        _injecter_bloc_de_test(page)
        page.evaluate("document.getElementById('banc-reveal').textContent = '0'")
        page.evaluate("window.Mouvement.compteur(document.getElementById('banc-reveal'), 128, 5000)")
        page.wait_for_function("document.getElementById('banc-reveal').textContent === '128'", timeout=1500)
    assert erreurs == []


def test_transition_de_vue_ne_bloque_pas_le_focus_ni_le_titre(application: FastAPI) -> None:
    with _page(application) as (page, erreurs):
        page.wait_for_function("document.getElementById('etat-utilisateur').textContent.includes('Testeur')")
        page.click('aside button.nav-btn[data-vue="vue-etudiants"]')
        # Immédiatement après le clic : focus sur le h2, titre mis à jour, animation d'entrée lancée.
        assert page.evaluate("document.activeElement.tagName") == "H2"
        assert "Étudiants" in page.evaluate("document.title")
        page.wait_for_timeout(400)
        assert page.evaluate("getComputedStyle(document.getElementById('vue-etudiants')).opacity") == "1"
        pastille = page.evaluate(
            "(() => { const p = document.querySelector('.nav-pastille'); const b = document.querySelector('button.nav-btn.actif');"
            " return Math.abs(p.getBoundingClientRect().top - b.getBoundingClientRect().top) < 2; })()")
        assert pastille is True
    assert erreurs == []


def test_toast_sortie_animee_sans_garder_de_noeud_reel(application: FastAPI) -> None:
    with _page(application) as (page, erreurs):
        page.wait_for_function("window.Mouvement")
        page.evaluate("notifier('Échec', false)")
        page.locator("#notif-alerte button", has_text="Fermer").click()
        assert page.locator("#notif-alerte .toast").count() == 0
        page.wait_for_function("document.querySelectorAll('.mo-sortie').length === 0", timeout=2000)
    assert erreurs == []


def test_bascule_de_theme_douce_puis_stable(application: FastAPI) -> None:
    with _page(application) as (page, erreurs):
        page.wait_for_function("window.Mouvement")
        page.click("#btn-theme") if page.is_visible("#btn-theme") else None
        theme = page.evaluate("document.documentElement.getAttribute('data-theme')")
        assert theme in ("dark", "light")
        page.wait_for_function("!document.documentElement.classList.contains('mo-theme')", timeout=2000)
    assert erreurs == []


def test_contenu_visible_sans_javascript(application: FastAPI) -> None:
    with _page(application, java_script_enabled=False) as (page, _erreurs):
        assert page.locator("html.mo-actif").count() == 0
        for sel in (".connexion-form > *", ".connexion-arguments > li", ".connexion-accroche"):
            n = page.locator(sel).count()
            assert n > 0, sel
            for i in range(n):
                assert page.locator(sel).nth(i).evaluate("e => getComputedStyle(e).opacity") == "1", sel
