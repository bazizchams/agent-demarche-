"""Contrôles statiques de l'interface web (sans navigateur) + un test headless Playwright.

L'interface est une unique chaîne Python non brute : un antislash mal placé y casse le JS
sans aucune erreur Python. Ces tests verrouillent les pièges connus.
"""

from __future__ import annotations

import re
from collections import Counter

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.interface.routeur_interface import HTML_INTERFACE_FR

# Nombre d'antislash du HTML servi avant l'ajout des écrans IA (mesuré au début du travail).
ANTISLASHS_INITIAUX = 4

IDS_NOUVEAUX_ELEMENTS = [
    "ia-statut-procedures",
    "ia-statut-discussion",
    "carte-generation-ia",
    "ia-texte-source",
    "ia-compteur-texte",
    "btn-generer-procedure-ia",
    "zone-retour-generation-ia",
    "bloc-ia-editeur",
    "titre-avertissements-ia",
    "liste-avertissements-ia",
    "encart-champs-avances",
    "liste-champs-avances",
    "carte-assistant-ia",
    "ia-demarche-assistant",
    "ia-question-assistant",
    "btn-demander-assistant-ia",
    "zone-reponse-assistant-ia",
]


def _ids_html() -> Counter[str]:
    return Counter(re.findall(r"""\bid="([^"]+)\"""", HTML_INTERFACE_FR))


def test_page_servie_et_sans_nouvel_antislash(application: FastAPI) -> None:
    rep = TestClient(application).get("/")
    assert rep.status_code == 200
    assert rep.text.count(chr(92)) <= ANTISLASHS_INITIAUX


def test_nouveaux_identifiants_uniques() -> None:
    ids = _ids_html()
    for identifiant in IDS_NOUVEAUX_ELEMENTS:
        assert ids[identifiant] == 1, identifiant


def test_get_element_by_id_vise_un_id_present() -> None:
    ids = _ids_html()
    cibles = set(re.findall(r"""getElementById\("([^"]+)"\)""", HTML_INTERFACE_FR))
    assert cibles, "aucun getElementById trouvé"
    absents = sorted(c for c in cibles if c not in ids)
    assert absents == []


def test_balises_script_equilibrees() -> None:
    ouvrantes = re.findall(r"<script[ >]", HTML_INTERFACE_FR)
    fermantes = re.findall(r"</script>", HTML_INTERFACE_FR)
    assert len(ouvrantes) == len(fermantes) >= 1


def test_aucune_donnee_non_echappee_dans_les_blocs_ia() -> None:
    debut = HTML_INTERFACE_FR.index("// ===== Assistant IA")
    fin = HTML_INTERFACE_FR.index("// ===== Vœux de formation")
    bloc = HTML_INTERFACE_FR[debut:fin]
    assert "innerHTML = data" not in bloc
    assert "textContent = data.reponse" in bloc


def test_chargement_headless_sans_erreur_js_et_onglet_procedures(application: FastAPI) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    client = TestClient(application)
    erreurs: list[str] = []

    with sync_api.sync_playwright() as p:
        try:
            navigateur = p.chromium.launch()
        except Exception as exc:  # navigateur non installé
            pytest.skip(f"Chromium indisponible : {exc}")
        try:
            page = navigateur.new_page()
            page.on("pageerror", lambda e: erreurs.append(str(e)))

            def servir(route: sync_api.Route) -> None:
                url = route.request.url
                chemin = url.split("http://interface.local", 1)[1] or "/"
                rep = client.request(
                    route.request.method,
                    chemin,
                    content=route.request.post_data_buffer,
                )
                route.fulfill(
                    status=rep.status_code,
                    headers={"content-type": rep.headers.get("content-type", "text/html")},
                    body=rep.content,
                )

            page.route("http://interface.local/**", servir)
            page.goto("http://interface.local/", wait_until="domcontentloaded")
            page.click('aside button.nav-btn[data-vue="vue-procedures"]')
            page.wait_for_selector("#vue-procedures:not(.cache)")
            assert page.locator("#ia-statut-procedures").count() == 1
            page.click('aside button.nav-btn[data-vue="vue-conseiller"]')
            page.wait_for_selector("#vue-conseiller:not(.cache)")
            page.wait_for_timeout(300)
        finally:
            navigateur.close()

    assert erreurs == []


def test_bouton_changer_de_dossier_a_un_style_de_bouton_visible() -> None:
    """Recette 375 px : le bouton était en `btn-fantome` (sans bord ni fond) et paraissait sans style."""
    m = re.search(r'<button class="([^"]*)"[^>]*data-aller-vers="vue-etudiants">Changer de dossier', HTML_INTERFACE_FR)
    assert m is not None
    classes = m.group(1).split()
    assert "btn" in classes and "btn-contour" in classes and "btn-fantome" not in classes
