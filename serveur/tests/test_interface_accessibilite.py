"""Accessibilité de l'interface : tests statiques (HTML/CSS/JS servis) et clavier (Playwright).

Couvre le tiroir mobile (inert, piège de focus, Échap), le focus et le titre au changement d'écran,
les régions de notification persistantes, les tableaux, le contraste des champs, le lien
d'évitement, les zones aria-live et les cibles tactiles.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.interface.design import styles
from app.interface.routeur_interface import HTML_INTERFACE_FR

# --------------------------------------------------------------------------- aides


def _balise(identifiant: str) -> str:
    m = re.search(r"""<[a-z0-9]+\b[^>]*\bid="%s"[^>]*>""" % re.escape(identifiant), HTML_INTERFACE_FR)
    assert m is not None, identifiant
    return m.group(0)


def _fonction_js(nom: str) -> str:
    debut = HTML_INTERFACE_FR.index("function %s(" % nom)
    return HTML_INTERFACE_FR[debut: debut + 2500]


def _jeton(css: str, nom: str) -> str:
    m = re.search(r"%s:\s*(#[0-9a-fA-F]{6})" % re.escape(nom), css)
    assert m is not None, nom
    return m.group(1)


def _luminance(hexa: str) -> float:
    canaux = [int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canaux]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contraste(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# --------------------------------------------------------------------------- 1. tiroir mobile


def test_bouton_menu_a_un_nom_fixe_et_seulement_aria_expanded() -> None:
    balise = _balise("btn-menu")
    assert 'aria-label="Menu"' in balise
    assert 'aria-expanded="false"' in balise
    assert "Ouvrir le menu" not in HTML_INTERFACE_FR
    # Le JS ne modifie plus le nom accessible du bouton du menu.
    assert 'bouton.setAttribute("aria-label"' not in HTML_INTERFACE_FR.split("function fermerMenuMobile")[1][:2500]


def test_tiroir_inert_piege_de_focus_et_echap_dans_le_js() -> None:
    js = HTML_INTERFACE_FR
    assert ".inert" in js
    assert 'e.key !== "Tab"' in js
    assert 'e.key === "Escape"' in js
    assert "barre-haute" in js.split("function majInertTiroir")[1][:600]


# --------------------------------------------------------------------------- 2. changement d'écran


def test_changement_d_ecran_donne_le_focus_au_titre_et_met_a_jour_le_titre_du_document() -> None:
    corps = _fonction_js("allerVersVue")
    assert 'setAttribute("tabindex", "-1")' in corps
    assert ".focus(" in corps
    assert "document.title" in corps
    assert ":focus { outline: none; }" in styles.CSS_DESIGN.replace("  ", " ") or "h2[tabindex=\"-1\"]" in styles.CSS_DESIGN


# --------------------------------------------------------------------------- 3. notifications


def test_regions_de_notification_persistantes() -> None:
    statut = _balise("notif-statut")
    alerte = _balise("notif-alerte")
    assert 'role="status"' in statut and 'aria-live="polite"' in statut
    assert 'role="alert"' in alerte
    assert 'role="status"' in _balise("annonce-statut")
    assert 'id="zone-notification"' in HTML_INTERFACE_FR


def test_notifier_ne_change_plus_de_role_et_propose_fermer() -> None:
    corps = _fonction_js("notifier")
    assert 'setAttribute("role"' not in corps
    assert "Fermer" in corps
    assert "textContent" in corps
    assert "innerHTML" not in corps


# --------------------------------------------------------------------------- 4. tableaux


def test_tableaux_dans_une_region_focalisable_avec_legende_et_scope() -> None:
    enveloppes = re.findall(r'<div class="table-wrap"[^>]*>', HTML_INTERFACE_FR)
    assert len(enveloppes) >= 4
    for balise in enveloppes:
        assert 'tabindex="0"' in balise, balise
        assert 'role="region"' in balise, balise
        assert re.search(r'aria-label="[^"]{8,}"', balise), balise
    etiquettes = [re.search(r'aria-label="([^"]+)"', b).group(1) for b in enveloppes]  # type: ignore[union-attr]
    assert len(set(etiquettes)) == len(etiquettes), "chaque tableau a son propre nom"
    nb_tables = len(re.findall(r"<table\b", HTML_INTERFACE_FR))
    assert len(re.findall(r'<caption class="sr-only">[^<]+</caption>', HTML_INTERFACE_FR)) == nb_tables
    assert re.search(r"<th(?![a-z])(?![^>]*scope=)", HTML_INTERFACE_FR) is None


# --------------------------------------------------------------------------- 5. champs et focus


def test_bordure_de_champ_contrastee_en_clair_et_en_sombre() -> None:
    clair, sombre = styles.TOKENS_CLAIR, styles.TOKENS_SOMBRE
    assert _contraste(_jeton(clair, "--bord-champ"), _jeton(clair, "--surface")) >= 3.0
    assert _contraste(_jeton(clair, "--bord-champ"), _jeton(clair, "--fond")) >= 3.0
    assert _contraste(_jeton(sombre, "--bord-champ"), _jeton(sombre, "--surface")) >= 3.0
    assert _contraste(_jeton(sombre, "--bord-champ"), _jeton(sombre, "--fond")) >= 3.0
    regle = re.search(r"\n    input, select, textarea \{[^}]*\}", styles.CSS_DESIGN)
    assert regle is not None and "var(--bord-champ)" in regle.group(0)


def test_focus_des_champs_en_outline_et_classes_sr() -> None:
    css = styles.CSS_DESIGN
    assert "input:focus-visible, select:focus-visible, textarea:focus-visible { outline: none; }" not in css
    assert re.search(r"input:focus-visible[^{]*\{[^}]*outline: 2px solid", css)
    assert ".sr-only {" in css and ".sr-focus" in css


# --------------------------------------------------------------------------- 6. repères


def test_lien_d_evitement_main_focalisable_et_h1() -> None:
    assert re.search(r'<a class="sr-focus" href="#contenu">Aller au contenu</a>', HTML_INTERFACE_FR)
    assert HTML_INTERFACE_FR.index("Aller au contenu") < HTML_INTERFACE_FR.index('id="btn-menu"')
    assert 'id="contenu" tabindex="-1"' in HTML_INTERFACE_FR
    assert len(re.findall(r"<h1\b", HTML_INTERFACE_FR)) == 1
    assert '<h1 class="sr-only">' in HTML_INTERFACE_FR


# --------------------------------------------------------------------------- 7. divers


@pytest.mark.parametrize(
    "identifiant",
    ["zone-completude", "zone-score-acceptation", "liste-voeux", "zone-retour-cf", "zone-retour-ircc",
     "zone-retour-generation-ia", "zone-retour-procedure"],
)
def test_pas_d_aria_live_sur_les_grandes_zones(identifiant: str) -> None:
    assert "aria-live" not in _balise(identifiant)


@pytest.mark.parametrize("identifiant", ["fil-discussion", "fil-copilote-cf", "fil-copilote-ircc"])
def test_fils_en_role_log(identifiant: str) -> None:
    balise = _balise(identifiant)
    assert 'role="log"' in balise
    assert "aria-live" not in balise


def test_compteur_validation_et_iframes_et_alt() -> None:
    assert 'aria-label="' in _balise("nav-compteur-validation")
    assert "setAttribute(\"aria-label\"" in _fonction_js("accueilMajCompteurNav")
    for balise in re.findall(r"<iframe\b[^>]*>", HTML_INTERFACE_FR):
        assert re.search(r'title="[^"]{6,}"', balise), balise
    assert 'img.alt = "Image du document source"' not in HTML_INTERFACE_FR
    assert "img.alt = " in HTML_INTERFACE_FR


def test_cibles_tactiles_44_px_en_pointeur_grossier() -> None:
    m = re.search(r"@media \(pointer: coarse\) \{(.*?)\n    \}", styles.CSS_DESIGN, re.S)
    assert m is not None
    assert "44px" in m.group(1)


def test_js_sans_api_dangereuse_dans_la_coquille() -> None:
    for fragment in (_fonction_js("notifier"), _fonction_js("allerVersVue"), _fonction_js("fermerMenuMobile")):
        for interdit in ("innerHTML", "eval(", "console."):
            assert interdit not in fragment
    assert chr(92) not in styles.CSS_DESIGN


# --------------------------------------------------------------------------- clavier (Playwright)


@contextmanager
def _page(application: FastAPI, largeur: int, hauteur: int) -> Iterator[tuple[Any, list[str]]]:
    sync_api = pytest.importorskip("playwright.sync_api")
    client = TestClient(application)
    erreurs: list[str] = []

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
            page = navigateur.new_page(viewport={"width": largeur, "height": hauteur})
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
            page.wait_for_function("document.getElementById('etat-utilisateur').textContent.includes('Testeur')")
            yield page, erreurs
        finally:
            navigateur.close()


_DANS_LE_TIROIR = "!!document.activeElement.closest('#navigation-principale')"


def test_tiroir_mobile_inert_piege_de_focus_echap_et_retour_au_bouton(application: FastAPI) -> None:
    with _page(application, 375, 800) as (page, erreurs):
        page.click("#btn-menu")
        assert page.evaluate("document.body.classList.contains('nav-ouverte')")
        assert page.evaluate("document.querySelector('main').inert") is True
        assert page.evaluate("document.querySelector('.barre-haute').inert") is True
        assert page.get_attribute("#btn-menu", "aria-expanded") == "true"
        assert page.get_attribute("#btn-menu", "aria-label") == "Menu"
        assert page.evaluate(_DANS_LE_TIROIR)
        for _ in range(40):
            page.keyboard.press("Tab")
            assert page.evaluate(_DANS_LE_TIROIR), "Tab ne doit pas quitter le tiroir"
        for _ in range(40):
            page.keyboard.press("Shift+Tab")
            assert page.evaluate(_DANS_LE_TIROIR), "Maj+Tab ne doit pas quitter le tiroir"
        page.keyboard.press("Escape")
        assert not page.evaluate("document.body.classList.contains('nav-ouverte')")
        assert page.evaluate("document.querySelector('main').inert") is False
        assert page.evaluate("document.querySelector('.barre-haute').inert") is False
        assert page.evaluate("document.activeElement.id") == "btn-menu"
        assert page.get_attribute("#btn-menu", "aria-expanded") == "false"
        assert page.get_attribute("#btn-menu", "aria-label") == "Menu"
    assert erreurs == []


def test_changement_d_ecran_focus_sur_le_titre_et_titre_du_document(application: FastAPI) -> None:
    with _page(application, 1280, 900) as (page, erreurs):
        page.click('aside button.nav-btn[data-vue="vue-etudiants"]')
        info = page.evaluate(
            "({ balise: document.activeElement.tagName, texte: document.activeElement.textContent.trim(),"
            " tabindex: document.activeElement.getAttribute('tabindex'), titre: document.title,"
            " dansVue: !!document.activeElement.closest('#vue-etudiants') })")
        assert info["balise"] == "H2" and info["tabindex"] == "-1" and info["dansVue"]
        assert info["texte"] in info["titre"]
        ancien = info["titre"]
        page.click('aside button.nav-btn[data-vue="vue-documents"]')
        assert page.evaluate("document.title") != ancien
        assert page.evaluate("document.activeElement.tagName") == "H2"
    assert erreurs == []


def test_notifications_regions_persistantes_et_bouton_fermer(application: FastAPI) -> None:
    with _page(application, 1280, 900) as (page, erreurs):
        roles_avant = page.evaluate(
            "[document.getElementById('notif-statut').getAttribute('role'),"
            " document.getElementById('notif-alerte').getAttribute('role')]")
        page.evaluate("notifier('Enregistré', true)")
        assert "Enregistré" in page.inner_text("#notif-statut")
        assert page.locator("#notif-alerte button").count() == 0
        page.evaluate("notifier('Échec de la sauvegarde', false)")
        assert "Échec de la sauvegarde" in page.inner_text("#notif-alerte")
        bouton = page.locator("#notif-alerte button", has_text="Fermer")
        assert bouton.count() == 1
        bouton.click()
        assert page.locator("#notif-alerte .toast").count() == 0
        roles_apres = page.evaluate(
            "[document.getElementById('notif-statut').getAttribute('role'),"
            " document.getElementById('notif-alerte').getAttribute('role')]")
        assert roles_avant == roles_apres == ["status", "alert"]
    assert erreurs == []


def test_lien_d_evitement_amene_le_focus_sur_le_contenu(application: FastAPI) -> None:
    with _page(application, 1280, 900) as (page, erreurs):
        page.evaluate("document.activeElement && document.activeElement.blur()")
        page.keyboard.press("Tab")
        assert page.evaluate("document.activeElement.textContent.trim()") == "Aller au contenu"
        assert page.evaluate("getComputedStyle(document.activeElement).position") == "fixed"
        page.keyboard.press("Enter")
        assert page.evaluate("document.activeElement.id") == "contenu"
        assert page.locator("h1.sr-only").count() == 1
    assert erreurs == []


def test_regions_de_tableau_atteignables_au_clavier(application: FastAPI) -> None:
    with _page(application, 1280, 900) as (page, erreurs):
        page.click('aside button.nav-btn[data-vue="vue-etudiants"]')
        region = page.locator('#vue-etudiants .table-wrap[role="region"]').first
        region.focus()
        assert page.evaluate("document.activeElement.classList.contains('table-wrap')")
    assert erreurs == []
