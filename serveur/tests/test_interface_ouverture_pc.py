"""Carte « Ouvrir sur mon PC » : intégration dans la page, règles du guide de design, comportement du JavaScript.

Le comportement est vérifié dans un vrai Chromium (headless) avec une API simulée : on y charge la vraie carte
HTML et le vrai JavaScript, avec `appelApi` remplacé par des réponses préparées.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any

import pytest
from playwright.sync_api import Page, Route, sync_playwright

from app.interface.design.js_ouverture_pc import JS_OUVERTURE_PC
from app.interface.design.page import construire_page_base
from app.interface.design.shell import rendre_icones
from app.interface.design.vues_ouverture_pc import HTML_OUVERTURE_PC

ORIGINE = "http://ui.test"
IDS_CARTE = (
    "carte-ouverture-pc",
    "ouverture-pc-badge",
    "ouverture-pc-etat",
    "ouverture-pc-marche",
    "btn-ouvrir-sur-pc",
    "btn-reprendre-ouverture-pc",
    "btn-ouverture-vers-validation",
)

SOCLE_SIMULE = """
let candidatActifId = "cand-1";
const notificationsVues = [];
const appelsApi = [];
const reponsesApi = { agents: [], taches: [], tache: null, creation: null, reprise: null };
function notifier(message, ok) { notificationsVues.push([message, ok]); }
function dosNoeud(balise, classe, texte) {
  const n = document.createElement(balise);
  if (classe) n.className = classe;
  if (texte !== undefined && texte !== null) n.textContent = texte;
  return n;
}
function reponse(statut, corps) {
  return { ok: statut >= 200 && statut < 300, status: statut, json: async () => corps };
}
async function appelApi(url, options) {
  const methode = (options && options.method) || "GET";
  const corps = options && options.body ? JSON.parse(options.body) : null;
  appelsApi.push({ url, methode, corps });
  if (url.startsWith("/api/v1/agents-locaux")) return reponse(200, reponsesApi.agents);
  if (url.startsWith("/api/v1/taches?")) return reponse(200, { elements: reponsesApi.taches });
  if (url.endsWith("/reprendre")) return reponse(reponsesApi.reprise.statut, reponsesApi.reprise.corps);
  if (methode === "POST" && url === "/api/v1/taches") return reponse(reponsesApi.creation.statut, reponsesApi.creation.corps);
  if (url.startsWith("/api/v1/taches/")) return reponse(200, reponsesApi.tache);
  return reponse(404, {});
}
"""


@pytest.fixture()
def page_ui() -> Iterator[Page]:
    with sync_playwright() as p:
        navigateur = p.chromium.launch(headless=True)
        page = navigateur.new_page()

        def servir(route: Route) -> None:
            corps = "<!doctype html><html><body>" + rendre_icones(HTML_OUVERTURE_PC) + "</body></html>"
            route.fulfill(status=200, body=corps, content_type="text/html; charset=utf-8")

        page.route(f"{ORIGINE}/**", servir)
        page.goto(ORIGINE + "/")
        page.add_script_tag(content=SOCLE_SIMULE)
        page.add_script_tag(content=JS_OUVERTURE_PC)
        yield page
        navigateur.close()


def _agent(*, actif: bool = True, en_ligne: bool = False, vu: str | None = None) -> dict[str, Any]:
    return {"id": "a1", "nom_machine": "PC-1", "actif": actif, "en_ligne": en_ligne, "derniere_activite_le": vu}


def _tache(statut: str, message: str | None = None) -> dict[str, Any]:
    return {"id": "t1", "action": "ajouter_voeux_panier", "statut": statut, "message_alerte": message}


def _charger(page: Page, **reponses: Any) -> None:
    page.evaluate("(r) => Object.assign(reponsesApi, r)", reponses)
    page.evaluate("ouvSurChangementCandidat({ id: 'cand-1' })")


def _texte(page: Page, id_: str) -> str:
    return page.evaluate("(i) => document.getElementById(i).textContent", id_)


def _cache(page: Page, id_: str) -> bool:
    return page.evaluate("(i) => document.getElementById(i).classList.contains('cache')", id_)


# ---------------------------------------------------------------------------
# Intégration et règles du guide de design
# ---------------------------------------------------------------------------


def test_la_carte_est_dans_l_ecran_etudiants_et_le_js_dans_la_page() -> None:
    html = construire_page_base()
    for identifiant in IDS_CARTE:
        assert html.count(f'id="{identifiant}"') == 1, identifiant
    assert "Ouvrir sur mon PC" in html
    assert html.index('id="carte-ouverture-pc"') < html.index('id="carte-nouvel-etudiant"')
    assert "function ouvSurChangementCandidat" in html


def test_regles_du_guide_de_design_et_de_securite_du_js() -> None:
    assert "innerHTML" not in JS_OUVERTURE_PC and "console.log" not in JS_OUVERTURE_PC
    assert chr(92) not in JS_OUVERTURE_PC  # aucun antislash (leur nombre est verrouillé ailleurs)
    # Pas de couleur littérale : uniquement des tokens var(--…)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgb\(|hsl\(", HTML_OUVERTURE_PC)
    assert "var(--" in HTML_OUVERTURE_PC
    # Aucun champ de mot de passe : la connexion se fait dans la fenêtre du PC (R3)
    assert "password" not in HTML_OUVERTURE_PC.lower() and "mot_de_passe" not in JS_OUVERTURE_PC


# ---------------------------------------------------------------------------
# Comportement
# ---------------------------------------------------------------------------


def test_aucun_agent_enrole_affiche_la_marche_a_suivre_sans_inventer(page_ui: Page) -> None:
    _charger(page_ui, agents=[], taches=[])
    page_ui.wait_for_function("!document.getElementById('ouverture-pc-marche').classList.contains('cache')")
    marche = _texte(page_ui, "ouverture-pc-marche")
    assert "Aucun poste agent n'est enrôlé" in marche
    assert "Enrôler un poste agent local" in marche
    assert "installer_agent.bat" in marche and "lancer_agent.bat" in marche
    assert ORIGINE in marche  # l'adresse du serveur à saisir est la vraie adresse de cette page
    assert page_ui.evaluate("document.getElementById('btn-ouvrir-sur-pc').disabled") is True
    assert "Aucune ouverture sur le PC" in _texte(page_ui, "ouverture-pc-etat")


def test_agent_enrole_mais_hors_ligne_marche_a_suivre_et_bouton_actif(page_ui: Page) -> None:
    _charger(page_ui, agents=[_agent(en_ligne=False, vu="2026-11-13T08:00:00Z")], taches=[])
    page_ui.wait_for_function("!document.getElementById('ouverture-pc-marche').classList.contains('cache')")
    marche = _texte(page_ui, "ouverture-pc-marche")
    assert "Aucun agent n'est en ligne" in marche and "Dernier signe de vie" in marche
    assert "lancer_agent.bat" in marche and "installer_agent.bat" not in marche
    assert page_ui.evaluate("document.getElementById('btn-ouvrir-sur-pc').disabled") is False


def test_agent_en_ligne_pas_de_marche_a_suivre(page_ui: Page) -> None:
    _charger(page_ui, agents=[_agent(en_ligne=True)], taches=[])
    page_ui.wait_for_function("document.getElementById('btn-ouvrir-sur-pc').disabled === false")
    assert _cache(page_ui, "ouverture-pc-marche") is True


def test_clic_cree_la_tache_puis_affiche_en_attente_puis_l_etat(page_ui: Page) -> None:
    _charger(page_ui, agents=[_agent(en_ligne=True)], taches=[])
    page_ui.evaluate(
        "(t) => { reponsesApi.creation = { statut: 201, corps: t }; reponsesApi.tache = t; }", _tache("en_attente")
    )
    page_ui.click("#btn-ouvrir-sur-pc")
    page_ui.wait_for_function("document.getElementById('ouverture-pc-badge').textContent === 'en attente'")
    assert "En attente de l'agent" in _texte(page_ui, "ouverture-pc-etat")
    creation = next(a for a in page_ui.evaluate("appelsApi") if a["methode"] == "POST")
    assert creation["url"] == "/api/v1/taches"
    assert creation["corps"] == {
        "candidat_id": "cand-1",
        "code_demarche": "campus_france",
        "action": "ajouter_voeux_panier",
    }

    # L'agent a pris la tâche, puis s'est arrêté avant l'envoi : l'écran suit l'état réel.
    page_ui.evaluate("(t) => { reponsesApi.tache = t; }", _tache("en_cours"))
    page_ui.evaluate("ouvActualiser()")
    assert "L'agent travaille dans la fenêtre ouverte sur votre PC" in _texte(page_ui, "ouverture-pc-etat")
    page_ui.evaluate("(t) => { reponsesApi.tache = t; }", _tache("a_valider"))
    page_ui.evaluate("ouvActualiser()")
    assert "validez dans le Centre de validation" in _texte(page_ui, "ouverture-pc-etat")
    assert _cache(page_ui, "btn-ouverture-vers-validation") is False
    assert page_ui.evaluate("ouvMinuteur") is None  # le suivi s'arrête à l'état final


def test_pause_captcha_affiche_le_message_et_permet_de_reprendre(page_ui: Page) -> None:
    message = "CAPTCHA détecté : à résoudre dans la fenêtre ouverte sur votre PC."
    _charger(page_ui, agents=[_agent(en_ligne=True)], taches=[_tache("suspendue", message)])
    page_ui.wait_for_function("document.getElementById('ouverture-pc-badge').textContent === 'suspendue'")
    assert message in _texte(page_ui, "ouverture-pc-etat")
    assert _cache(page_ui, "btn-reprendre-ouverture-pc") is False

    page_ui.evaluate(
        "(t) => { reponsesApi.reprise = { statut: 200, corps: t }; reponsesApi.tache = t; }", _tache("en_attente")
    )
    page_ui.click("#btn-reprendre-ouverture-pc")
    page_ui.wait_for_function("document.getElementById('ouverture-pc-badge').textContent === 'en attente'")
    assert any(a["url"] == "/api/v1/taches/t1/reprendre" for a in page_ui.evaluate("appelsApi"))
    assert _cache(page_ui, "btn-reprendre-ouverture-pc") is True
    page_ui.evaluate("ouvArreterSuivi()")


def test_refus_du_serveur_sans_voeu_valide_affiche_le_message(page_ui: Page) -> None:
    _charger(page_ui, agents=[_agent(en_ligne=True)], taches=[])
    detail = "Aucun vœu validé pour ce candidat : rédigez puis validez au moins un vœu."
    page_ui.evaluate("(d) => { reponsesApi.creation = { statut: 422, corps: { detail: d } }; }", detail)
    page_ui.click("#btn-ouvrir-sur-pc")
    page_ui.wait_for_function("document.getElementById('ouverture-pc-etat').textContent.includes('Aucun vœu validé')")
    assert page_ui.evaluate("notificationsVues")[-1] == [detail, False]
    assert page_ui.evaluate("ouvMinuteur") is None  # rien à suivre : aucune tâche créée


def test_le_texte_du_serveur_n_est_jamais_interprete_comme_du_html(page_ui: Page) -> None:
    piege = "<img src=x onerror=window.__pwned=1>"
    _charger(page_ui, agents=[_agent(en_ligne=True)], taches=[_tache("en_erreur", piege)])
    page_ui.wait_for_function("document.getElementById('ouverture-pc-badge').textContent === 'en erreur'")
    assert page_ui.evaluate("window.__pwned") is None
    assert page_ui.evaluate("document.querySelectorAll('#ouverture-pc-etat img').length") == 0
    assert piege in _texte(page_ui, "ouverture-pc-etat")
    assert json.loads(json.dumps(piege)) == piege
