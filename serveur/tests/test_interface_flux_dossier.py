"""Écran « Dossier automatique » : intégration statique et comportement dans un vrai Chromium (API simulée)."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any

import pytest
from playwright.sync_api import Page, Route, sync_playwright

from app.interface.routeur_interface import HTML_INTERFACE_FR

ORIGINE = "http://ui.test"
CAND = {"id": "c1", "nom": "BENALI", "prenom": "Sara", "numero_passeport": "P123"}
CODES = ["pieces", "lecture", "revue_valeurs", "fiche", "points_forts", "projet_professionnel", "voeux", "lettres", "navigateur"]


def _etat(statuts: dict[str, str], progression: int = 0, manquantes: list[str] | None = None) -> dict[str, Any]:
    return {
        "candidat_id": "c1",
        "progression": progression,
        "etapes": [
            {
                "code": c, "libelle": "Étape " + c, "statut": statuts.get(c, "a_faire"), "detail": "Détail " + c,
                "action_humaine": "Confirmer les 6 valeurs lues" if c == "revue_valeurs" and statuts.get(c) == "a_verifier" else None,
                "lien_ecran": "vue-revue-extractions" if c == "revue_valeurs" else None,
                "compteurs": {"valeurs_lues": 6} if c == "lecture" else {},
            }
            for c in CODES
        ],
        "pieces_manquantes": manquantes or [],
    }


class Api:
    def __init__(self) -> None:
        self.appels: list[tuple[str, str]] = []
        self.etat = _etat({})
        self.lancer_statut = 200
        self.etat_statut = 200

    def servir(self, route: Route) -> None:
        req = route.request
        chemin = req.url.replace(ORIGINE, "")
        self.appels.append((req.method, chemin))
        def rep(code: int, corps: Any) -> None:
            route.fulfill(status=code, body=json.dumps(corps), content_type="application/json")
        if chemin.startswith("/api/v1/auth/connexion"):
            return rep(200, {"jeton_csrf": "t", "utilisateur": {"role": "employe", "nom_affiche": "Test", "email_verifie": True}})
        if chemin.endswith("/dossier-automatique/lancer"):
            if self.lancer_statut != 200:
                return rep(self.lancer_statut, {"detail": "boom"})
            self.etat = _etat({"pieces": "termine", "lecture": "en_cours"}, 15)
            return rep(200, self.etat)
        if chemin.endswith("/dossier-automatique/etat"):
            return rep(self.etat_statut, self.etat if self.etat_statut == 200 else {"detail": "x"})
        if chemin.endswith("/documents") and req.method == "POST":
            return rep(201, {"id": "d1", "type_piece": "passeport"})
        if chemin.startswith("/api/v1/candidats"):
            return rep(200, {"total": 1, "elements": [CAND]})
        return rep(200, [])


@pytest.fixture()
def api() -> Api:
    return Api()


@pytest.fixture()
def page_ui(api: Api) -> Iterator[Page]:
    with sync_playwright() as p:
        nav = p.chromium.launch(headless=True)
        page = nav.new_page()
        erreurs: list[str] = []
        page.on("pageerror", lambda e: erreurs.append(str(e)))
        def servir(route: Route) -> None:
            if route.request.url.endswith("/api/v1/auth/connexion") or "/api/v1/" in route.request.url:
                api.servir(route)
            else:
                route.fulfill(status=200, body=HTML_INTERFACE_FR, content_type="text/html; charset=utf-8")
        page.route(f"{ORIGINE}/**", servir)
        page.goto(ORIGINE + "/")
        page.wait_for_function("document.querySelector('#btn-se-deconnecter') && !document.querySelector('#btn-se-deconnecter').classList.contains('cache')")
        page.evaluate("allerVersVue('vue-flux-dossier')")
        yield page
        assert erreurs == []
        nav.close()


def test_statique_entree_menu_en_tete_et_regles_js() -> None:
    assert HTML_INTERFACE_FR.count('data-vue="vue-flux-dossier"') == 1
    assert HTML_INTERFACE_FR.index('data-vue="vue-flux-dossier"') < HTML_INTERFACE_FR.index('data-vue="vue-tableau-bord"')
    bloc = HTML_INTERFACE_FR.split('id="vue-flux-dossier"', 1)[1]
    assert "Dossier automatique" in bloc and "Pièces manquantes" in bloc and "Lancer l'analyse" in bloc
    from app.interface.design.js_flux_dossier import JS_FLUX_DOSSIER as js
    assert ".innerHTML" not in js and "eval(" not in js and "console." not in js and chr(92) not in js
    ids = re.findall(r'\bid="([^"]+)"', HTML_INTERFACE_FR)
    for i in set(re.findall(r'fdEl\("([^"]+)"\)', js)):
        assert ids.count(i) == 1, i
    assert 'role="progressbar"' in bloc and 'aria-live="polite"' in bloc


def test_vide_puis_depot_lancement_et_suivi(page_ui: Page, api: Api) -> None:
    page_ui.evaluate("candidatActifId = null; fdChoisirEtudiant(''); fdAfficherSelection()")
    assert page_ui.locator("#fd-vide").is_visible()
    page_ui.select_option("#fd-etudiant", "c1")
    page_ui.wait_for_selector("#fd-contenu:not(.cache)")
    assert page_ui.locator(".fd-etape").count() == 9
    # dépôt : le type est suggéré mais modifiable, aucun type = refus
    page_ui.set_input_files("#fd-fichiers", [
        {"name": "passeport.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.4"},
        {"name": "scan.png", "mimeType": "image/png", "buffer": b"x"},
        {"name": "virus.exe", "mimeType": "application/octet-stream", "buffer": b"x"},
    ])
    assert page_ui.locator(".fd-fichier").count() == 2
    page_ui.click("#fd-btn-envoyer")
    assert "Choisissez le type" in page_ui.locator(".fd-fichier-erreur").inner_text()
    page_ui.locator(".fd-fichier select").nth(1).select_option("cv")
    page_ui.click("#fd-btn-envoyer")
    page_ui.wait_for_function("document.querySelectorAll('.fd-fichier .badge-ok').length === 2")
    assert sum(1 for m, c in api.appels if m == "POST" and c.endswith("/documents")) == 2
    # lancement puis interrogation douce
    page_ui.click("#fd-btn-lancer")
    page_ui.wait_for_selector(".fd-etape-en_cours")
    assert page_ui.locator("#fd-barre").get_attribute("aria-valuenow") == "15"
    api.etat = _etat({"pieces": "termine", "lecture": "termine", "revue_valeurs": "a_verifier"}, 40, ["cv"])
    page_ui.wait_for_selector(".fd-etape-a_verifier", timeout=6000)
    bouton = page_ui.get_by_role("button", name="Confirmer les 6 valeurs lues")
    assert bouton.get_attribute("data-aller-vers") == "vue-revue-extractions"
    assert "À fournir" in page_ui.locator("#fd-manquantes").inner_text() or "1 à fournir" in page_ui.locator("#fd-badge-manquantes").inner_text()


def test_erreurs_en_francais(page_ui: Page, api: Api) -> None:
    page_ui.select_option("#fd-etudiant", "c1")
    page_ui.wait_for_selector(".fd-etape")
    api.lancer_statut = 500
    page_ui.click("#fd-btn-lancer")
    page_ui.wait_for_selector("#fd-erreur:not(.cache)")
    assert "problème" in page_ui.locator("#fd-erreur-texte").inner_text()
    api.etat_statut = 404
    page_ui.click("#fd-btn-actualiser")
    page_ui.wait_for_function("document.getElementById('fd-erreur-texte').textContent.includes('pas disponible')")
