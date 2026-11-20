"""Parcours « Créer la fiche depuis le passeport » de l'écran Dossier automatique (Chromium, API simulée)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from playwright.sync_api import Page, Route, sync_playwright

from app.interface.routeur_interface import HTML_INTERFACE_FR

ORIGINE = "http://ui.test"
PASSEPORT = {"name": "passeport.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.4"}
CHAMPS = [
    ("nom", "BENALI", "NOM<<BENALI"), ("prenom", "Sara", "PRENOM<<SARA"), ("date_naissance", "2001-04-12", "010412"),
    ("sexe", "F", "F"), ("nationalite", "DZA", "DZA"), ("numero_passeport", "P1234567", "P1234567"),
    ("date_expiration_passeport", "2031-01-05", "310105"),
]
NOUVEAU = {"id": "c9", "nom": "BENALI", "prenom": "Sara"}


def _depot(statut: str = "propose", existant: str | None = None) -> dict[str, Any]:
    propositions = [] if statut == "saisie_manuelle" else [
        {"champ": c, "valeur": v, "extrait": e, "page": 1, "confiance": 0.9, "statut": "a_confirmer"} for c, v, e in CHAMPS
    ]
    return {
        "id": "d1", "statut": statut, "propositions": propositions, "saisie_manuelle_requise": statut == "saisie_manuelle",
        "avertissements": [], "candidat_existant_id": existant, "expire_le": "2026-12-01T00:00:00Z", "cree_le": "2026-11-20T00:00:00Z",
    }


class Api:
    def __init__(self) -> None:
        self.appels: list[tuple[str, str]] = []
        self.corps: list[dict[str, Any]] = []
        self.depot = _depot()
        self.creation = (201, {"candidat": NOUVEAU, "document_id": "x", "extractions_validees": 7, "avertissements": []})
        self.cree = False

    def servir(self, route: Route) -> None:
        req = route.request
        chemin = req.url.replace(ORIGINE, "")
        self.appels.append((req.method, chemin))

        def rep(code: int, corps: Any = None) -> None:
            route.fulfill(status=code, body="" if corps is None else json.dumps(corps), content_type="application/json")

        if chemin.startswith("/api/v1/auth/connexion"):
            return rep(200, {"jeton_csrf": "t", "utilisateur": {"role": "employe", "nom_affiche": "Test", "email_verifie": True}})
        if chemin == "/api/v1/depots-passeport" and req.method == "POST":
            return rep(201, self.depot)
        if chemin == "/api/v1/depots-passeport/d1/creer-fiche":
            self.corps.append(json.loads(req.post_data or "{}"))
            self.cree = self.creation[0] == 201
            return rep(*self.creation)
        if chemin == "/api/v1/depots-passeport/d1" and req.method == "DELETE":
            return rep(204)
        if chemin.endswith("/dossier-automatique/etat"):
            return rep(200, {"candidat_id": "c9", "progression": 0, "etapes": [], "pieces_manquantes": []})
        if chemin.startswith("/api/v1/candidats"):
            return rep(200, {"total": 1, "elements": [NOUVEAU] if self.cree else []})
        return rep(200, [])

    def creations(self) -> int:
        return sum(1 for m, c in self.appels if m == "POST" and c.endswith("/creer-fiche"))


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
            if "/api/v1/" in route.request.url:
                api.servir(route)
            else:
                route.fulfill(status=200, body=HTML_INTERFACE_FR, content_type="text/html; charset=utf-8")

        page.route(f"{ORIGINE}/**", servir)
        page.goto(ORIGINE + "/")
        page.wait_for_function("document.querySelector('#btn-se-deconnecter') && !document.querySelector('#btn-se-deconnecter').classList.contains('cache')")
        page.evaluate("allerVersVue('vue-flux-dossier')")
        page.click("#fd-passeport summary")
        yield page
        assert erreurs == []
        nav.close()


def _deposer(page: Page) -> None:
    page.set_input_files("#fd-pp-fichier", [PASSEPORT])
    page.wait_for_selector("#fd-pp-confirmer")


def test_statique_pas_d_innerhtml_et_ids_uniques() -> None:
    assert HTML_INTERFACE_FR.count('id="fd-passeport"') == 1 and "Créer la fiche depuis le passeport" in HTML_INTERFACE_FR
    assert HTML_INTERFACE_FR.count('id="fd-pp-statut"') == 1 and 'id="fd-pp-statut" class="fd-pp-statut" role="status" aria-live="polite"' in HTML_INTERFACE_FR
    from app.interface.design.js_flux_dossier import JS_FLUX_DOSSIER as js
    assert ".innerHTML" not in js and "console." not in js and chr(92) not in js


def test_proposition_modification_puis_confirmation(page_ui: Page, api: Api) -> None:
    _deposer(page_ui)
    assert api.creations() == 0
    assert page_ui.locator("#fd-pp-zone .badge", has_text="À confirmer").count() == 7
    assert "NOM<<BENALI" in page_ui.locator("#fd-pp-champ-nom-aide").inner_text()
    assert page_ui.input_value("#fd-pp-champ-nom") == "BENALI"
    assert page_ui.input_value("#fd-pp-champ-sexe") == "F"
    page_ui.fill("#fd-pp-champ-prenom", "Sarah")
    page_ui.fill("#fd-pp-champ-nationalite", "")
    assert api.creations() == 0  # rien n'est envoyé avant le clic de confirmation
    page_ui.click("#fd-pp-confirmer")
    page_ui.wait_for_selector("#fd-contenu:not(.cache)")
    assert api.corps == [{
        "confirme": True, "nom": "BENALI", "prenom": "Sarah", "date_naissance": "2001-04-12", "sexe": "F",
        "numero_passeport": "P1234567", "date_expiration_passeport": "2031-01-05",
    }]
    assert page_ui.input_value("#fd-etudiant") == "c9"
    assert "Fiche créée pour BENALI Sara" in page_ui.locator("#fd-pp-statut").inner_text()


def test_nom_obligatoire_aucun_envoi(page_ui: Page, api: Api) -> None:
    _deposer(page_ui)
    page_ui.fill("#fd-pp-champ-nom", "")
    page_ui.click("#fd-pp-confirmer")
    assert page_ui.get_attribute("#fd-pp-champ-nom", "aria-invalid") == "true"
    assert "obligatoires" in page_ui.locator("#fd-pp-statut").inner_text()
    assert api.creations() == 0


def test_saisie_manuelle_champs_vides(page_ui: Page, api: Api) -> None:
    api.depot = _depot("saisie_manuelle")
    _deposer(page_ui)
    assert "remplissez les champs vous-même" in page_ui.locator("#fd-pp-statut").inner_text()
    assert page_ui.locator("#fd-pp-zone .badge").count() == 0
    assert page_ui.input_value("#fd-pp-champ-nom") == "" and page_ui.input_value("#fd-pp-champ-numero_passeport") == ""
    page_ui.fill("#fd-pp-champ-nom", "OUALI")
    page_ui.fill("#fd-pp-champ-prenom", "Amine")
    page_ui.click("#fd-pp-confirmer")
    page_ui.wait_for_selector("#fd-contenu:not(.cache)")
    assert api.corps == [{"confirme": True, "nom": "OUALI", "prenom": "Amine"}]


def test_candidat_existant_avertissement_et_doublon_409(page_ui: Page, api: Api) -> None:
    api.depot = _depot(existant="c5")
    api.creation = (409, {"code": "passeport_deja_utilise", "detail": "x", "candidat_id": "c5", "lien": "/api/v1/candidats/c5"})
    _deposer(page_ui)
    statut = page_ui.locator("#fd-pp-statut")
    assert "déjà ce numéro de passeport" in statut.inner_text()
    assert statut.get_by_role("button", name="Voir la fiche existante").count() == 1
    page_ui.click("#fd-pp-confirmer")
    page_ui.wait_for_function("document.getElementById('fd-pp-statut').textContent.includes('déjà utilisé')")
    assert statut.get_by_role("button", name="Voir la fiche existante").count() == 1
    assert page_ui.locator("#fd-pp-confirmer").is_enabled()


def test_annulation_supprime_le_depot(page_ui: Page, api: Api) -> None:
    _deposer(page_ui)
    page_ui.click("#fd-pp-annuler")
    page_ui.wait_for_function("document.getElementById('fd-pp-statut').textContent.includes('annulé')")
    assert ("DELETE", "/api/v1/depots-passeport/d1") in api.appels
    assert page_ui.locator("#fd-pp-zone form").count() == 0 and api.creations() == 0


def test_mobile_375_sans_debordement(page_ui: Page, api: Api) -> None:
    page_ui.set_viewport_size({"width": 375, "height": 800})
    _deposer(page_ui)
    assert page_ui.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
