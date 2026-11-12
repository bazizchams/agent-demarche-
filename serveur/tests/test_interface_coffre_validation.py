"""Écrans web du coffre d'identifiants portail et des récapitulatifs à valider.

Tests statiques sur le HTML servi, puis tests headless (Playwright, ignorés si Chromium est
indisponible) avec une API simulée : rôle lecture seule, échappement d'un contenu piégé,
absence de secret dans la page et dans le stockage navigateur.
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

from app.interface import ecrans_coffre_validation as ecrans
from app.interface.routeur_interface import HTML_INTERFACE_FR

SECRET_ID = "IDENT-SECRET-QX93"
SECRET_MDP = "MotDePasse-SECRET-ZK41!"
CANDIDAT_ID = "11111111-1111-4111-8111-111111111111"
VALIDATION_ID = "22222222-2222-4222-8222-222222222222"
PIEGE = "<script>window.__pwned = 1</script><img src=x onerror=\"window.__pwned = 2\">"


# --------------------------------------------------------------------------- statique


def _ids_html() -> list[str]:
    return re.findall(r"""\bid="([^"]+)\"""", HTML_INTERFACE_FR)


def test_page_servie_avec_les_nouveaux_blocs(application: FastAPI) -> None:
    rep = TestClient(application).get("/")
    assert rep.status_code == 200
    for fragment in (
        "Identifiants portail",
        "Récapitulatifs à valider",
        "L'agent enverra exactement ce contenu ; toute modification annule la validation.",
        "consentement écrit",
        'data-vue="vue-recaps-valider"',
        'id="compteur-recaps-centre"',
    ):
        assert fragment in rep.text, fragment


def test_identifiants_uniques_et_cibles_presentes() -> None:
    ids = _ids_html()
    assert len(ids) == len(set(ids)), "identifiants HTML dupliqués"
    for code, _ in ecrans.PORTAILS_COFFRE:
        for prefixe in ("coffre-id-", "coffre-mdp-", "coffre-consent-", "coffre-statut-",
                        "coffre-enregistrer-", "coffre-supprimer-"):
            assert prefixe + code in ids
    cibles = set(re.findall(r"""getElementById\("([^"]+)"\)""", ecrans.JS_COFFRE_VALIDATION))
    for cible in cibles:
        assert cible in ids or cible.endswith("-"), cible


def test_champs_mot_de_passe_sans_valeur_ni_autocompletion() -> None:
    for code, _ in ecrans.PORTAILS_COFFRE:
        mdp = re.search(rf"""<input id="coffre-mdp-{code}"[^>]*>""", HTML_INTERFACE_FR)
        ident = re.search(rf"""<input id="coffre-id-{code}"[^>]*>""", HTML_INTERFACE_FR)
        assert mdp and 'type="password"' in mdp.group(0)
        for champ in (mdp, ident):
            assert champ is not None
            assert 'autocomplete="off"' in champ.group(0)
            assert "value=" not in champ.group(0)
        assert re.search(rf"""<input id="coffre-consent-{code}" type="checkbox"[^>]*/>""", HTML_INTERFACE_FR)


def test_aucun_secret_dans_html_ni_journal_ni_stockage() -> None:
    assert SECRET_ID not in HTML_INTERFACE_FR and SECRET_MDP not in HTML_INTERFACE_FR
    js = ecrans.JS_COFFRE_VALIDATION
    for interdit in ("console.", "localStorage", "sessionStorage", "indexedDB", "document.cookie",
                     "innerHTML", "outerHTML", "insertAdjacentHTML", "eval(", "alert("):
        assert interdit not in js, interdit
    assert chr(92) not in js and chr(92) not in ecrans.HTML_VUE_RECAPS
    # Le corps de la requête ne sert qu'à l'envoi : les champs sont vidés avant l'appel réseau.
    assert js.index("viderChampsCoffre(code); //") < js.index('{ method: "PUT", body: corps }')


def test_ecritures_via_appel_api_csrf_et_routes_attendues() -> None:
    js = ecrans.JS_COFFRE_VALIDATION
    assert "fetch(" not in js, "tout appel doit passer par appelApi (en-tête CSRF)"
    for route in ('"/coffre/"', "/api/v1/validations-recapitulatif?statut=en_attente",
                  '"/api/v1/validations-recapitulatif/"', 'method: "PUT"', 'method: "DELETE"'):
        assert route in js, route


# --------------------------------------------------------------------------- headless


Moquettes = dict[tuple[str, str], tuple[int, Any]]


def _moquettes(role: str, validations: list[dict[str, Any]] | None = None) -> Moquettes:
    candidat = {
        "id": CANDIDAT_ID, "nom": PIEGE, "prenom": "Test", "numero_passeport": "X1",
        "email": None, "programme_vise": None, "etablissement_vise": None,
        "consentement_signe": True,
    }
    return {
        ("POST", "/api/v1/auth/connexion"): (200, {
            "jeton_csrf": "csrf-test", "utilisateur": {"role": role, "nom_affiche": "Testeur"},
        }),
        ("GET", "/api/v1/candidats"): (200, {"total": 1, "elements": [candidat]}),
        ("GET", f"/api/v1/candidats/{CANDIDAT_ID}/coffre/ircc"): (200, {
            "portail": "ircc", "existe": True, "consentement_recueilli_le": "2026-11-12T10:00:00",
            "cree_le": "2026-11-12T10:00:00", "mis_a_jour_le": "2026-11-12T10:00:00",
        }),
        ("GET", f"/api/v1/candidats/{CANDIDAT_ID}/coffre/etudes_en_france"): (200, {
            "portail": "etudes_en_france", "existe": False, "consentement_recueilli_le": None,
            "cree_le": None, "mis_a_jour_le": None,
        }),
        ("PUT", f"/api/v1/candidats/{CANDIDAT_ID}/coffre/etudes_en_france"): (200, {
            "portail": "etudes_en_france", "existe": True,
            "consentement_recueilli_le": "2026-11-12T11:00:00",
            "cree_le": "2026-11-12T11:00:00", "mis_a_jour_le": "2026-11-12T11:00:00",
        }),
        ("DELETE", f"/api/v1/candidats/{CANDIDAT_ID}/coffre/ircc"): (204, None),
        ("GET", "/api/v1/validations-recapitulatif"): (200, validations or []),
    }


@contextmanager
def _page_simulee(
    application: FastAPI, moquettes: Moquettes
) -> Iterator[tuple[Any, list[str], list[dict[str, Any]]]]:
    sync_api = pytest.importorskip("playwright.sync_api")
    client = TestClient(application)
    erreurs: list[str] = []
    requetes: list[dict[str, Any]] = []
    with sync_api.sync_playwright() as p:
        try:
            navigateur = p.chromium.launch()
        except Exception as exc:  # navigateur non installé
            pytest.skip(f"Chromium indisponible : {exc}")
        try:
            page = navigateur.new_page()
            page.on("pageerror", lambda e: erreurs.append(str(e)))
            page.on("dialog", lambda d: d.accept())

            def servir(route: Any) -> None:
                url = route.request.url
                chemin = url.split("http://interface.local", 1)[1] or "/"
                chemin_sans_requete = chemin.split("?", 1)[0]
                cle = (route.request.method, chemin_sans_requete)
                if chemin_sans_requete.startswith("/api/"):
                    requetes.append({
                        "methode": route.request.method, "chemin": chemin,
                        "csrf": route.request.headers.get("x-csrf-token"),
                        "corps": route.request.post_data,
                    })
                    statut, corps = moquettes.get(cle, (404, {"detail": "non simulé"}))
                    route.fulfill(status=statut, content_type="application/json",
                                  body="" if corps is None else json.dumps(corps))
                    return
                rep = client.get(chemin)
                route.fulfill(status=rep.status_code,
                              headers={"content-type": rep.headers.get("content-type", "text/html")},
                              body=rep.content)

            page.route("http://interface.local/**", servir)
            page.goto("http://interface.local/", wait_until="domcontentloaded")
            page.wait_for_function("document.getElementById('etat-utilisateur').textContent.includes('Testeur')")
            yield page, erreurs, requetes
        finally:
            navigateur.close()


def test_lecture_seule_bloc_coffre_masque_et_recaps_refuses(application: FastAPI) -> None:
    with _page_simulee(application, _moquettes("lecture_seule")) as (page, erreurs, requetes):
        page.click('aside button.nav-btn[data-vue="vue-documents"]')
        page.wait_for_selector("#coffre-lecture-seule:not(.cache)")
        for code, _ in ecrans.PORTAILS_COFFRE:
            assert page.is_hidden(f"#coffre-saisie-{code}")
            assert page.is_disabled(f"#coffre-mdp-{code}")
            assert page.is_disabled(f"#coffre-enregistrer-{code}")
            assert page.is_hidden(f"#coffre-supprimer-{code}")
        page.wait_for_function(
            "document.getElementById('coffre-statut-ircc').textContent.includes('enregistrés')")
        page.click('aside button.nav-btn[data-vue="vue-recaps-valider"]')
        page.wait_for_function(
            "document.getElementById('liste-recaps').textContent.includes('réservé')")
        assert page.locator("#liste-recaps button").count() == 0
        assert not any(r["chemin"].startswith("/api/v1/validations-recapitulatif") for r in requetes)
        assert not any(r["methode"] in ("PUT", "DELETE") for r in requetes)
    assert erreurs == []


def test_saisie_coffre_videe_jamais_reaffichee_et_csrf_envoye(application: FastAPI) -> None:
    with _page_simulee(application, _moquettes("employe")) as (page, erreurs, requetes):
        page.click('aside button.nav-btn[data-vue="vue-documents"]')
        page.wait_for_function(
            "document.getElementById('coffre-statut-ircc').textContent.includes('enregistrés')")
        assert page.is_visible("#coffre-supprimer-ircc")
        assert page.is_hidden("#coffre-supprimer-etudes_en_france")

        # Sans consentement : aucun envoi.
        page.fill("#coffre-id-etudes_en_france", SECRET_ID)
        page.fill("#coffre-mdp-etudes_en_france", SECRET_MDP)
        page.click("#coffre-enregistrer-etudes_en_france")
        assert not any(r["methode"] == "PUT" for r in requetes)

        page.check("#coffre-consent-etudes_en_france")
        page.click("#coffre-enregistrer-etudes_en_france")
        page.wait_for_function(
            "document.getElementById('coffre-statut-etudes_en_france').textContent.includes('enregistrés')")
        envoi = next(r for r in requetes if r["methode"] == "PUT")
        assert envoi["csrf"] == "csrf-test"
        assert json.loads(envoi["corps"]) == {
            "identifiant": SECRET_ID, "mot_de_passe": SECRET_MDP, "consentement": True}

        assert page.input_value("#coffre-id-etudes_en_france") == ""
        assert page.input_value("#coffre-mdp-etudes_en_france") == ""
        assert not page.is_checked("#coffre-consent-etudes_en_france")
        contenu = page.content()
        assert SECRET_ID not in contenu and SECRET_MDP not in contenu
        stockage = page.evaluate(
            "JSON.stringify([Object.entries(localStorage), Object.entries(sessionStorage), document.cookie])")
        assert SECRET_ID not in stockage and SECRET_MDP not in stockage

        page.click("#coffre-supprimer-ircc")
        page.wait_for_function(
            "document.getElementById('coffre-statut-ircc').textContent.includes('Aucun')")
        assert any(r["methode"] == "DELETE" and r["csrf"] == "csrf-test" for r in requetes)
    assert erreurs == []


def _validation(contenu: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": VALIDATION_ID, "candidat_id": CANDIDAT_ID, "portail": "etudes_en_france",
        "type_demarche": PIEGE, "empreinte": "ab12cd34ef56" + "0" * 52, "statut": "en_attente",
        "cree_le": "2026-11-12T10:00:00", "validee_par": None, "validee_le": None,
        "envoyee_le": None, "champs_manquants": contenu.get("champs_manquants", []),
        "contenu": contenu,
    }


def test_contenu_piege_est_echappe_et_actions_disponibles(application: FastAPI) -> None:
    contenu = {
        "nom": PIEGE, "voeux": [PIEGE, "Informatique Lyon"],
        "pieces": {"passeport": PIEGE}, "champs_manquants": [],
    }
    moq = _moquettes("administrateur", [_validation(contenu)])
    moq[("POST", f"/api/v1/validations-recapitulatif/{VALIDATION_ID}/valider")] = (
        200, _validation(contenu) | {"statut": "validee"})
    with _page_simulee(application, moq) as (page, erreurs, requetes):
        page.click('aside button.nav-btn[data-vue="vue-recaps-valider"]')
        page.wait_for_selector("#liste-recaps .carte")
        zone = page.locator("#liste-recaps")
        assert page.evaluate("window.__pwned") is None
        assert zone.locator("script, img").count() == 0
        assert "<script>window.__pwned = 1</script>" in zone.inner_text()
        assert "ab12cd34ef56…" in zone.inner_text()
        assert "L'agent enverra exactement ce contenu" in zone.inner_text()
        assert zone.locator("button.btn-valider-recap").is_enabled()
        assert zone.locator("button.btn-refuser-recap").is_enabled()
        assert zone.locator(".recap-manquants").count() == 0

        page.click("#liste-recaps button.btn-valider-recap")
        page.wait_for_function("document.getElementById('zone-notification').textContent.includes('validé')")
        assert any(r["methode"] == "POST" and r["chemin"].endswith("/valider")
                   and r["csrf"] == "csrf-test" for r in requetes)

        page.click('aside button.nav-btn[data-vue="vue-validation-humaine"]')
        page.wait_for_function(
            "document.getElementById('compteur-recaps-centre').textContent.includes('en attente')")
        assert page.evaluate("window.__pwned") is None
    assert erreurs == []


def test_champs_manquants_rendent_le_recapitulatif_non_validable(application: FastAPI) -> None:
    contenu = {"nom": "BELAID", "champs_manquants": ["date_naissance", PIEGE]}
    with _page_simulee(application, _moquettes("employe", [_validation(contenu)])) as (page, erreurs, _):
        page.click('aside button.nav-btn[data-vue="vue-recaps-valider"]')
        page.wait_for_selector("#liste-recaps .recap-manquants")
        alerte = page.locator("#liste-recaps .recap-manquants").inner_text()
        assert "Non validable" in alerte and "Date de naissance" in alerte
        assert "<script>" in alerte and "<img" in alerte  # affichés comme texte inerte
        assert page.locator("#liste-recaps .recap-manquants script, #liste-recaps img").count() == 0
        assert page.locator("#liste-recaps button.btn-valider-recap").is_disabled()
        assert page.locator("#liste-recaps button.btn-refuser-recap").is_enabled()
        assert page.evaluate("window.__pwned") is None
    assert erreurs == []
