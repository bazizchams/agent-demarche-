"""Boutons du co-pilote (Campus France, IRCC) : aucun gestionnaire `onclick` / `onchange` ne doit
appeler une fonction absente du JavaScript servi (analyse statique de la page rendue), et les
actions rapides de la barre du navigateur doivent exister côté serveur.

Un test headless (Playwright, ignoré si Chromium est absent) vérifie aussi le comportement purement
interface : choix du portail -> barre d'adresse, bascule de vue, puce d'exemple -> champ de consigne.
"""

from __future__ import annotations

import inspect
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Attributs d'événement en ligne, valeur entre guillemets doubles.
_RE_GESTIONNAIRE = re.compile(r"""\bon(?:click|change|input|submit|keydown|keyup)="([^"]*)\"""")
# Premier appel de fonction « nu » (pas une méthode `objet.m(`) dans la valeur de l'attribut.
_RE_APPEL = re.compile(r"""(?<![.\w$])([A-Za-z_$][\w$]*)\s*\(""")
_MOTS_JS = {"if", "return", "function", "typeof", "void", "new", "await", "async", "while", "for", "switch"}

FONCTIONS_COPILOTE = (
    "executerActionDomRapide",
    "naviguerUrlDirecte",
    "basculerModeVueDirecte",
    "synchroniserEtatNavigateurDirect",
    "changerCibleNavigateurDirect",
    "envoyerConsigneRapideCopilote",
    "demarrerDicteeVocale",
)


def _page(application: FastAPI) -> str:
    rep = TestClient(application).get("/")
    assert rep.status_code == 200
    return rep.text


def _scripts(html: str) -> str:
    return "\n".join(re.findall(r"<script[^>]*>(.*?)</script>", html, flags=re.S))


def _fonctions_definies(js: str) -> set[str]:
    noms = set(re.findall(r"""\bfunction\s+([A-Za-z_$][\w$]*)\s*\(""", js))
    noms |= set(
        re.findall(
            r"""\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?(?:function\b|\([^)]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>)""",
            js,
        )
    )
    noms |= set(re.findall(r"""\bwindow\.([A-Za-z_$][\w$]*)\s*=""", js))
    return noms


def _fonctions_appelees(html: str) -> dict[str, str]:
    appelees: dict[str, str] = {}
    for valeur in _RE_GESTIONNAIRE.findall(html):
        # Les littéraux entre apostrophes (textes d'exemple) ne contiennent pas d'appels.
        code = re.sub(r"'[^']*'", "''", valeur)
        for nom in _RE_APPEL.findall(code):
            if nom not in _MOTS_JS:
                appelees.setdefault(nom, valeur)
    return appelees


def test_chaque_gestionnaire_en_ligne_appelle_une_fonction_definie(application: FastAPI) -> None:
    html = _page(application)
    definies = _fonctions_definies(_scripts(html))
    appelees = _fonctions_appelees(html)
    assert appelees, "aucun gestionnaire onclick/onchange trouvé : l'analyse ne voit plus rien"
    absentes = {nom: exemple for nom, exemple in appelees.items() if nom not in definies}
    assert absentes == {}, f"fonctions appelées mais jamais définies : {absentes}"


def test_les_boutons_du_copilote_sont_relies(application: FastAPI) -> None:
    html = _page(application)
    definies = _fonctions_definies(_scripts(html))
    appelees = _fonctions_appelees(html)
    for nom in FONCTIONS_COPILOTE:
        assert nom in appelees, f"{nom} n'est plus appelée par la page"
        assert nom in definies, f"{nom} n'est pas définie"


def test_le_bloc_copilote_respecte_les_regles_js() -> None:
    from app.interface.design.js_demarches import JS_DEMARCHES

    debut = JS_DEMARCHES.index("const PREFIXES_DIRECT")
    fin = JS_DEMARCHES.index("// Statut d'une étape de tâche")
    bloc = JS_DEMARCHES[debut:fin]
    for interdit in ("innerHTML", "outerHTML", "insertAdjacentHTML", "eval(", "new Function", "console.", "fetch("):
        assert interdit not in bloc, interdit
    assert chr(92) not in bloc
    # Tout appel serveur passe par appelApi (en-tête X-CSRF-Token).
    assert "appelApi(\"/api/v1/portails/action-dom-directe\"" in bloc
    # Aucun envoi audio : la dictée n'appelle jamais le serveur.
    debut_dictee = bloc.index("function demarrerDicteeVocale")
    fin_dictee = bloc.index("(function dirBrancherCadres")
    assert "appelApi" not in bloc[debut_dictee:fin_dictee]


def test_actions_rapides_existent_cote_serveur(application: FastAPI) -> None:
    pytest.importorskip("playwright.sync_api")
    from app.agent_local.pilote_navigateur import GestionnairePiloteNavigateur

    source = inspect.getsource(GestionnairePiloteNavigateur._executer_action_dom_dans_thread)
    actions = set(re.findall(r"""executerActionDomRapide\('[^']+',\s*'([^']+)'\)""", _page(application)))
    assert actions >= {"retour", "suivant", "actualiser", "scroll_haut", "scroll_bas", "focus_fenetre"}
    for action in actions:
        assert f'"{action}"' in source, f"action « {action} » sans équivalent serveur"


def test_comportement_interface_headless(application: FastAPI) -> None:
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
                chemin = route.request.url.split("http://interface.local", 1)[1] or "/"
                rep = client.request(route.request.method, chemin, content=route.request.post_data_buffer)
                route.fulfill(
                    status=rep.status_code,
                    headers={"content-type": rep.headers.get("content-type", "text/html")},
                    body=rep.content,
                )

            page.route("http://interface.local/**", servir)
            page.goto("http://interface.local/", wait_until="domcontentloaded")

            # Choix du portail -> barre d'adresse
            # (écrans masqués tant que l'onglet n'est pas ouvert : on agit par le DOM)
            page.evaluate(
                "() => { const s = document.getElementById('ircc-cible-navigateur');"
                " s.value = 'ircc_canada_info'; s.dispatchEvent(new Event('change')); }"
            )
            assert page.input_value("#ircc-url-live").startswith("https://www.canada.ca/")

            # Bascule DOM <-> capture (purement interface)
            page.evaluate("basculerModeVueDirecte('campus_france')")
            assert "cache" in (page.get_attribute("#cf-panneau-dom-live", "class") or "")
            assert "cache" not in (page.get_attribute("#cf-vue-capture", "class") or "")
            page.evaluate("basculerModeVueDirecte('campus_france')")
            assert "cache" not in (page.get_attribute("#cf-panneau-dom-live", "class") or "")

            # Navigation vers un domaine non officiel : refusée côté client, aucun appel serveur
            appels: list[str] = []
            page.on("request", lambda r: appels.append(r.url) if "action-dom-directe" in r.url else None)
            page.evaluate("() => { document.getElementById('cf-url-live').value = 'https://exemple-pirate.com/'; }")
            page.evaluate("naviguerUrlDirecte('campus_france')")
            page.wait_for_timeout(300)
            assert "règle 6" in page.text_content("#zone-retour-cf")
            assert appels == []

            # Puce d'exemple : le texte arrive dans le champ de consigne (chemin du bouton « Exécuter »)
            page.evaluate("envoyerConsigneRapideCopilote('ircc_permis_etudes', 'Analyse cette page IRCC')")
            assert page.input_value("#ircc-instruction-agent") == "Analyse cette page IRCC"
        finally:
            navigateur.close()

    assert erreurs == []
