"""Écran « Navigateur de l'agent » (vue et prise en main de l'opérateur).

Tests statiques sur le HTML servi, puis tests headless (Playwright, ignorés si Chromium est
indisponible) avec une API simulée : conversion de coordonnées, texte vidé après envoi,
lecture seule désactivée, absence de polling quand l'onglet est caché.
"""

from __future__ import annotations

import base64
import json
import re
import struct
import zlib
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.interface import ecran_navigateur_serveur as ecran
from app.interface.routeur_interface import HTML_INTERFACE_FR

SECRET_TEXTE = "CODE-SECRET-482913"
URL_AVEC_PARAMETRES = "https://etudes.exemple.fr/portail/connexion?jeton=SECRET-URL-77&x=1#frag"


def _png_vide(largeur: int, hauteur: int) -> bytes:
    def bloc(type_: bytes, donnees: bytes) -> bytes:
        crc = zlib.crc32(type_ + donnees) & 0xFFFFFFFF
        return struct.pack(">I", len(donnees)) + type_ + donnees + struct.pack(">I", crc)

    ligne = b"\x00" + b"\xcc" * largeur
    brut = zlib.compress(ligne * hauteur)
    return (
        b"\x89PNG\r\n\x1a\n"
        + bloc(b"IHDR", struct.pack(">IIBBBBB", largeur, hauteur, 8, 0, 0, 0, 0))
        + bloc(b"IDAT", brut)
        + bloc(b"IEND", b"")
    )


IMAGE_CAPTURE = _png_vide(ecran.LARGEUR_VIEWPORT, ecran.HAUTEUR_VIEWPORT)


# --------------------------------------------------------------------------- statique


def test_page_servie_avec_ecran_et_bannieres(application: FastAPI) -> None:
    rep = TestClient(application).get("/")
    assert rep.status_code == 200
    for fragment in (
        'data-vue="vue-navigateur-serveur"',
        'id="vue-navigateur-serveur"',
        "À utiliser pour un CAPTCHA ou un code de sécurité : l'agent ne les contourne jamais",
        "Ce que vous tapez n'est ni enregistré ni affiché dans l'historique",
        "Prendre la main",
        "Rendre la main à l'agent",
        "Fermer le navigateur",
    ):
        assert fragment in rep.text, fragment
    # Les écrans précédents sont toujours là.
    assert 'data-vue="vue-recaps-valider"' in rep.text


def test_identifiants_uniques_et_cibles_presentes() -> None:
    ids = re.findall(r"""\bid="([^"]+)\"""", HTML_INTERFACE_FR)
    assert len(ids) == len(set(ids)), "identifiants HTML dupliqués"
    cibles = set(re.findall(r"""getElementById\("([^"]+)"\)""", ecran.JS_NAVIGATEUR))
    assert cibles
    for cible in cibles:
        assert cible in ids, cible


def test_js_sans_api_dangereuse_ni_stockage_ni_journal() -> None:
    js = ecran.JS_NAVIGATEUR
    for interdit in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(",
                     "new Function", "localStorage", "sessionStorage", "indexedDB", "document.cookie",
                     "console.", "alert(", "fetch("):
        assert interdit not in js, interdit
    for fragment in (ecran.JS_NAVIGATEUR, ecran.HTML_VUE_NAVIGATEUR, ecran.HTML_NAV):
        assert chr(92) not in fragment
    assert "appelApi(" in js, "tout appel doit passer par appelApi (en-tête CSRF)"
    assert "innerHTML" not in ecran.HTML_VUE_NAVIGATEUR


def test_champ_texte_masque_sans_valeur_ni_autocompletion() -> None:
    champ = re.search(r"""<input id="ns-texte"[^>]*>""", HTML_INTERFACE_FR)
    assert champ is not None
    assert 'type="password"' in champ.group(0)
    assert 'autocomplete="off"' in champ.group(0)
    assert "value=" not in champ.group(0)


def test_lien_direct_depuis_le_centre_de_validation_pour_captcha() -> None:
    assert 't.motif_suspension === "action_utilisateur_portail"' in HTML_INTERFACE_FR
    assert "allerVersVue('vue-navigateur-serveur')" in HTML_INTERFACE_FR


def test_assemblage_echoue_si_marqueur_absent() -> None:
    with pytest.raises(RuntimeError):
        ecran.assembler_navigateur_serveur("<html></html>")


# --------------------------------------------------------------------------- headless

Reponse = tuple[int, str, bytes]


def _json(statut: int, corps: Any) -> Reponse:
    return statut, "application/json", json.dumps(corps).encode()


def _moquettes(role: str, ouvert: bool = True) -> dict[tuple[str, str], Reponse]:
    etat = {
        "navigateur_ouvert": ouvert,
        "url_courante": URL_AVEC_PARAMETRES if ouvert else None,
        "titre_page": "Connexion — Portail" if ouvert else None,
    }
    return {
        ("POST", "/api/v1/auth/connexion"): _json(200, {
            "jeton_csrf": "csrf-test", "utilisateur": {"role": role, "nom_affiche": "Testeur"},
        }),
        ("GET", "/api/v1/candidats"): _json(200, {"total": 0, "elements": []}),
        ("GET", "/api/v1/navigateur/etat"): _json(200, etat),
        ("GET", "/api/v1/navigateur/capture"): (200, "image/jpeg", IMAGE_CAPTURE),
        ("POST", "/api/v1/navigateur/controle"): _json(200, {"ok": True}),
        ("POST", "/api/v1/navigateur/fermer"): _json(200, {"ok": True}),
    }


@contextmanager
def _page_simulee(
    application: FastAPI, moquettes: dict[tuple[str, str], Reponse]
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
            page = navigateur.new_page(viewport={"width": 1500, "height": 1000})
            page.on("pageerror", lambda e: erreurs.append(str(e)))
            page.on("dialog", lambda d: d.accept())

            def servir(route: Any) -> None:
                chemin = route.request.url.split("http://interface.local", 1)[1] or "/"
                sans_requete = chemin.split("?", 1)[0]
                if sans_requete.startswith("/api/"):
                    requetes.append({
                        "methode": route.request.method, "chemin": chemin,
                        "csrf": route.request.headers.get("x-csrf-token"),
                        "corps": route.request.post_data,
                    })
                    statut, type_contenu, corps = moquettes.get(
                        (route.request.method, sans_requete), _json(404, {"detail": "non simulé"}))
                    route.fulfill(status=statut, content_type=type_contenu, body=corps)
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


def _ouvrir_ecran(page: Any) -> None:
    page.click('aside button.nav-btn[data-vue="vue-navigateur-serveur"]')
    page.wait_for_selector("#ns-capture:not(.cache)")
    page.wait_for_function("document.getElementById('ns-capture').naturalWidth === 1280")


def _compter(requetes: list[dict[str, Any]], fragment: str) -> int:
    return sum(1 for r in requetes if fragment in r["chemin"])


def _controles(requetes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [json.loads(r["corps"]) for r in requetes
            if r["methode"] == "POST" and r["chemin"] == "/api/v1/navigateur/controle"]


def test_conversion_coordonnees_ratio_affiche_vers_viewport(application: FastAPI) -> None:
    with _page_simulee(application, _moquettes("employe")) as (page, erreurs, _):
        resultat = page.evaluate(
            """() => {
              const rect = { left: 100, top: 50, width: 640, height: 450 };
              return [
                nsConvertirClic(rect, 100, 50),
                nsConvertirClic(rect, 420, 275),
                nsConvertirClic(rect, 739, 499),
                nsConvertirClic(rect, 5000, 5000),
                nsConvertirClic(rect, -10, -10),
                nsConvertirClic({ left: 0, top: 0, width: 0, height: 0 }, 1, 1),
              ];
            }""")
        assert resultat == [
            {"x": 0, "y": 0},
            {"x": 640, "y": 450},
            {"x": 1278, "y": 898},
            {"x": 1279, "y": 899},
            {"x": 0, "y": 0},
            None,
        ]
        assert page.evaluate(
            "[nsUrlSansParametres('https://a.fr/p/q?jeton=1#f'), nsUrlSansParametres('pas une url'),"
            " nsUrlSansParametres(null)]") == ["https://a.fr/p/q", "—", "—"]
    assert erreurs == []


def test_vue_etat_sans_parametres_et_capture_avec_jeton_anti_cache(application: FastAPI) -> None:
    with _page_simulee(application, _moquettes("employe")) as (page, erreurs, requetes):
        _ouvrir_ecran(page)
        assert page.inner_text("#ns-url") == "https://etudes.exemple.fr/portail/connexion"
        assert page.inner_text("#ns-titre") == "Connexion — Portail"
        assert "SECRET-URL-77" not in page.content()
        assert page.evaluate("document.getElementById('ns-capture').tagName") == "IMG"
        page.wait_for_timeout(2600)
        captures = [r["chemin"] for r in requetes if "/navigateur/capture" in r["chemin"]]
        assert len(captures) >= 2
        assert len(set(captures)) == len(captures), "chaque image doit avoir un horodatage unique (anti-cache)"
        assert all("?t=" in c and "jeton" not in c for c in captures)
        # Cadence d'environ une image par seconde, pas davantage.
        assert len(captures) <= 6
        # Aucune commande n'est envoyée tant que l'opérateur n'a pas pris la main.
        page.click("#ns-capture", position={"x": 10, "y": 10})
        assert _controles(requetes) == []
    assert erreurs == []


def test_prise_en_main_clic_molette_touches_et_csrf(application: FastAPI) -> None:
    with _page_simulee(application, _moquettes("administrateur")) as (page, erreurs, requetes):
        _ouvrir_ecran(page)
        assert page.is_hidden("#ns-controles")
        page.click("#ns-prendre-main")
        assert page.is_visible("#ns-controles")
        assert page.is_visible("#ns-rendre-main")

        boite = page.locator("#ns-capture").bounding_box()
        assert boite is not None
        largeur, hauteur = boite["width"], boite["height"]
        page.locator("#ns-capture").click(position={"x": largeur / 2, "y": hauteur / 4})
        page.wait_for_timeout(400)
        attendu_x = round(largeur / 2 * 1280 / largeur)
        attendu_y = round(hauteur / 4 * 900 / hauteur)
        clic = next(c for c in _controles(requetes) if c["type"] == "clic")
        assert abs(clic["x"] - attendu_x) <= 2 and abs(clic["y"] - attendu_y) <= 2
        envoi = next(r for r in requetes if r["methode"] == "POST" and "controle" in r["chemin"])
        assert envoi["csrf"] == "csrf-test"

        page.locator("#ns-capture").hover(position={"x": 50, "y": 50})
        page.mouse.wheel(0, 240)
        page.wait_for_timeout(400)
        page.wait_for_timeout(500)
        defilement = [c for c in _controles(requetes) if c["type"] == "defilement"]
        assert defilement and defilement[0]["delta_y"] > 0

        for libelle, touche in (("Entrée", "Enter"), ("Tab", "Tab"), ("Retour", "Backspace"),
                                ("Échap", "Escape")):
            page.click(f"#ns-controles .ns-touche:has-text('{libelle}')")
            page.wait_for_timeout(150)
            assert {"type": "touche", "touche": touche} in _controles(requetes)

        page.click("#ns-rendre-main")
        assert page.is_hidden("#ns-controles")
        nombre = len(_controles(requetes))
        page.click("#ns-capture", position={"x": 20, "y": 20})
        assert len(_controles(requetes)) == nombre
    assert erreurs == []


def test_texte_masque_vide_apres_envoi_et_jamais_stocke(application: FastAPI) -> None:
    with _page_simulee(application, _moquettes("employe")) as (page, erreurs, requetes):
        _ouvrir_ecran(page)
        page.click("#ns-prendre-main")
        assert page.get_attribute("#ns-texte", "type") == "password"
        page.check("#ns-afficher")
        assert page.get_attribute("#ns-texte", "type") == "text"
        page.uncheck("#ns-afficher")
        assert page.get_attribute("#ns-texte", "type") == "password"

        page.fill("#ns-texte", SECRET_TEXTE)
        page.click("#ns-envoyer-texte")
        page.wait_for_function("document.getElementById('ns-texte').value === ''")
        envoi = next(r for r in requetes if r["methode"] == "POST" and "controle" in r["chemin"])
        assert json.loads(envoi["corps"]) == {"type": "texte", "texte": SECRET_TEXTE}
        assert envoi["csrf"] == "csrf-test"
        assert page.input_value("#ns-texte") == ""
        assert SECRET_TEXTE not in page.content()
        stockage = page.evaluate(
            "JSON.stringify([Object.entries(localStorage), Object.entries(sessionStorage), document.cookie])")
        assert SECRET_TEXTE not in stockage
        assert not any(SECRET_TEXTE in r["chemin"] for r in requetes)

        # Touche Entrée dans le champ : envoie puis vide.
        page.fill("#ns-texte", "abc")
        page.press("#ns-texte", "Enter")
        page.wait_for_function("document.getElementById('ns-texte').value === ''")
        assert {"type": "texte", "texte": "abc"} in _controles(requetes)

        # Rendre la main vide aussi un champ resté rempli.
        page.fill("#ns-texte", "reste")
        page.click("#ns-rendre-main")
        page.click("#ns-prendre-main")
        assert page.input_value("#ns-texte") == ""
    assert erreurs == []


def test_fermer_le_navigateur_poste_avec_csrf(application: FastAPI) -> None:
    with _page_simulee(application, _moquettes("employe")) as (page, erreurs, requetes):
        _ouvrir_ecran(page)
        page.click("#ns-fermer")
        page.wait_for_function(
            "document.getElementById('zone-notification').textContent.includes('fermé')")
        envoi = next(r for r in requetes if r["chemin"] == "/api/v1/navigateur/fermer")
        assert envoi["methode"] == "POST" and envoi["csrf"] == "csrf-test"
    assert erreurs == []


def test_aucun_navigateur_ouvert_pas_de_capture(application: FastAPI) -> None:
    with _page_simulee(application, _moquettes("employe", ouvert=False)) as (page, erreurs, requetes):
        page.click('aside button.nav-btn[data-vue="vue-navigateur-serveur"]')
        page.wait_for_function(
            "document.getElementById('ns-etat').textContent.includes('Aucun navigateur')")
        assert page.is_hidden("#ns-capture")
        assert _compter(requetes, "/navigateur/capture") == 0
    assert erreurs == []


def test_lecture_seule_desactive_et_sans_appel_serveur(application: FastAPI) -> None:
    with _page_simulee(application, _moquettes("lecture_seule")) as (page, erreurs, requetes):
        page.click('aside button.nav-btn[data-vue="vue-navigateur-serveur"]')
        page.wait_for_selector("#ns-lecture-seule:not(.cache)")
        for identifiant in ("ns-prendre-main", "ns-fermer", "ns-texte", "ns-envoyer-texte"):
            assert page.is_disabled("#" + identifiant), identifiant
        page.wait_for_timeout(1500)
        assert _compter(requetes, "/api/v1/navigateur/") == 0
        page.evaluate("nsMain = true; nsAppliquerMain()")
        assert page.is_hidden("#ns-controles")
        page.evaluate("nsEnvoyerControle({ type: 'clic', x: 1, y: 1 })")
        page.wait_for_timeout(300)
        assert _controles(requetes) == []
    assert erreurs == []


def test_pas_de_polling_onglet_cache_ni_ecran_inactif(application: FastAPI) -> None:
    with _page_simulee(application, _moquettes("employe")) as (page, erreurs, requetes):
        _ouvrir_ecran(page)

        # Onglet caché : plus aucune requête /navigateur/.
        page.evaluate(
            """() => {
              Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });
              document.dispatchEvent(new Event('visibilitychange'));
            }""")
        page.wait_for_timeout(400)  # laisse finir un éventuel cycle déjà engagé
        figes = _compter(requetes, "/api/v1/navigateur/")
        page.wait_for_timeout(2500)
        assert _compter(requetes, "/api/v1/navigateur/") == figes

        # Onglet de nouveau visible : le rafraîchissement reprend.
        page.evaluate(
            """() => {
              Object.defineProperty(document, 'hidden', { configurable: true, get: () => false });
              document.dispatchEvent(new Event('visibilitychange'));
            }""")
        page.wait_for_timeout(400)
        page.wait_for_timeout(1500)
        assert _compter(requetes, "/api/v1/navigateur/") > figes

        # Écran quitté : plus de requêtes, et la prise en main est rendue.
        page.click("#ns-prendre-main")
        page.click('aside button.nav-btn[data-vue="vue-tableau-bord"]')
        page.wait_for_timeout(400)
        figes = _compter(requetes, "/api/v1/navigateur/")
        page.wait_for_timeout(2500)
        assert _compter(requetes, "/api/v1/navigateur/") == figes
        assert page.evaluate("nsMain") is False
    assert erreurs == []


def test_contenu_piege_affiche_comme_texte_inerte(application: FastAPI) -> None:
    piege = "<img src=x onerror=\"window.__pwned = 1\"><script>window.__pwned = 2</script>"
    moq = _moquettes("employe")
    moq[("GET", "/api/v1/navigateur/etat")] = _json(200, {
        "navigateur_ouvert": True, "url_courante": "https://exemple.fr/p", "titre_page": piege})
    with _page_simulee(application, moq) as (page, erreurs, _):
        _ouvrir_ecran(page)
        assert piege in page.inner_text("#ns-titre")
        assert page.locator("#ns-bandeau img, #ns-bandeau script").count() == 0
        assert page.evaluate("window.__pwned") is None
    assert erreurs == []


def test_image_png_de_test_est_bien_formee() -> None:
    assert IMAGE_CAPTURE.startswith(b"\x89PNG")
    assert base64.b64encode(IMAGE_CAPTURE)  # encodable, non vide
