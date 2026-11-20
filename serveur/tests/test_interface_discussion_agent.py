"""Composant « Discussion de l'agent » (interface) : règles du guide de design et comportement dans un vrai Chromium
(headless) avec une API et un flux SSE simulés. Le vrai CSS et le vrai JavaScript du composant sont chargés."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any

import pytest
from playwright.sync_api import Page, Route, sync_playwright

from app.interface.design import ecran_discussion_agent as module_discussion
from app.interface.design.ecran_discussion_agent import (
    CSS_DISCUSSION_AGENT,
    JS_DISCUSSION_AGENT,
    assembler_discussion_agent,
)

ORIGINE = "http://ui.test"
TACHE = "33333333-3333-3333-3333-333333333333"

SOCLE = """
let roleActif = "administrateur";
const notifs = [];
const appels = [];
const etatApi = { elements: [], etat: "en_cours", message: null, commande: null };
function notifier(m, ok) { notifs.push([m, ok]); }
function rep(statut, corps) { return { ok: statut >= 200 && statut < 300, status: statut, json: async () => corps }; }
async function appelApi(url, options) {
  const methode = (options && options.method) || "GET";
  appels.push({ url, methode, corps: options && options.body ? JSON.parse(options.body) : null });
  if (url.includes("/evenements?depuis=")) return rep(200, { elements: etatApi.elements, dernier: 0, etat: etatApi.etat });
  if (url.endsWith("/messages")) return rep(201, etatApi.message);
  if (methode === "POST") return rep(etatApi.commande ? 200 : 409, etatApi.commande || { detail: "Commande sans effet." });
  return rep(404, {});
}
const flux = [];
class EventSource {
  constructor(url) { this.url = url; this.ecouteurs = {}; this.ferme = false; flux.push(this); }
  addEventListener(nom, f) { this.ecouteurs[nom] = f; }
  close() { this.ferme = true; }
  emettre(nom, donnees) { this.ecouteurs[nom]({ data: JSON.stringify(donnees) }); }
}
"""


def _evt(seq: int, type_: str, texte: str, auteur: str = "agent") -> dict[str, Any]:
    return {"id": f"e{seq}", "tache_id": TACHE, "seq": seq, "type": type_, "auteur": auteur, "code": None,
            "texte": texte, "cree_le": "2026-11-14T10:00:00Z", "traite": False}


@pytest.fixture()
def page_ui() -> Iterator[Page]:
    with sync_playwright() as p:
        navigateur = p.chromium.launch(headless=True)
        page = navigateur.new_page()

        def servir(route: Route) -> None:
            corps = "<!doctype html><html><head>" + CSS_DISCUSSION_AGENT + "</head><body><div id='zone'></div></body></html>"
            route.fulfill(status=200, body=corps, content_type="text/html; charset=utf-8")

        page.route(f"{ORIGINE}/**", servir)
        page.goto(ORIGINE + "/")
        page.add_script_tag(content=SOCLE)
        page.add_script_tag(content=JS_DISCUSSION_AGENT)
        yield page
        navigateur.close()


def _monter(page: Page, **reponses: Any) -> None:
    page.evaluate("(r) => Object.assign(etatApi, r)", reponses)
    page.evaluate("(t) => { window.poignee = monterDiscussionAgent(document.getElementById('zone'), t); }", TACHE)
    page.wait_for_function("() => flux.length === 1")


def _textes(page: Page) -> list[str]:
    return page.evaluate("() => Array.from(document.querySelectorAll('.da-msg-texte')).map(n => n.textContent)")


def test_regles_du_guide_de_design_et_securite() -> None:
    for interdit in ("innerHTML", "console.log", "eval(", "outerHTML", "insertAdjacentHTML"):
        assert interdit not in JS_DISCUSSION_AGENT, interdit
    assert chr(92) not in JS_DISCUSSION_AGENT and chr(92) not in CSS_DISCUSSION_AGENT
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgb\(|hsl\(", CSS_DISCUSSION_AGENT)
    assert "var(--" in CSS_DISCUSSION_AGENT
    assert "monterDiscussionAgent(conteneur, tacheId)" in module_discussion.__doc__
    assert "password" not in JS_DISCUSSION_AGENT.lower()


def test_assemblage_dans_une_page() -> None:
    base = "<html>\n  </main>\n\n  <script>\n    // Connexion automatique dès l'ouverture de l'interface\n</script></html>"
    page = assembler_discussion_agent(base)
    assert page.count("function monterDiscussionAgent") == 1 and ".da-fil" in page
    with pytest.raises(ValueError):
        assembler_discussion_agent("<html></html>")


def test_fil_en_direct_par_sse_sans_doublon(page_ui: Page) -> None:
    _monter(page_ui, elements=[_evt(1, "agent", "Bonjour, je commence")])
    assert _textes(page_ui) == ["Bonjour, je commence"]
    page_ui.evaluate("() => { flux[0].emettre('evenement', " + json.dumps(_evt(2, "action", "Je clique")) + "); }")
    page_ui.evaluate("() => { flux[0].emettre('evenement', " + json.dumps(_evt(2, "action", "Je clique")) + "); }")
    page_ui.evaluate("() => { flux[0].emettre('evenement', " + json.dumps(_evt(3, "demande_humaine", "Connectez-vous")) + "); }")
    assert _textes(page_ui) == ["Bonjour, je commence", "Je clique", "Connectez-vous"]
    assert "depuis=2" in page_ui.evaluate("() => flux[0].url") or "depuis=1" in page_ui.evaluate("() => flux[0].url")
    assert page_ui.locator(".da-msg[role=alert]").count() == 1
    assert "Attend votre aide" in page_ui.locator("[role=status]").inner_text()
    log = page_ui.locator("[role=log]")
    assert log.get_attribute("aria-live") == "polite"


def test_du_html_dans_un_message_reste_du_texte(page_ui: Page) -> None:
    _monter(page_ui, elements=[_evt(1, "agent", "<img src=x onerror=window.pirate=1>")])
    assert page_ui.evaluate("() => window.pirate === undefined && document.querySelectorAll('.da-msg img').length === 0")


def test_envoi_d_un_message_et_reponse_de_refus(page_ui: Page) -> None:
    _monter(page_ui)
    message = _evt(1, "utilisateur", "Valide à ma place", "humain")
    reponse = _evt(2, "agent", "Je ne peux pas valider à votre place : c'est à vous de le faire.")
    page_ui.evaluate("(m) => { etatApi.message = m; }", {"message": message, "refuse": True, "reponse": reponse})
    page_ui.fill("textarea", "Valide à ma place")
    page_ui.press("textarea", "Enter")
    page_ui.wait_for_function("() => document.querySelectorAll('.da-msg').length === 2")
    assert _textes(page_ui)[1].startswith("Je ne peux pas valider à votre place")
    assert page_ui.input_value("textarea") == ""
    assert page_ui.evaluate("() => appels.filter(a => a.url.endsWith('/messages'))[0].corps.texte") == "Valide à ma place"


def test_commandes_pause_reprise_arret_et_fenetre(page_ui: Page) -> None:
    _monter(page_ui)
    page_ui.evaluate("(c) => { etatApi.commande = c; }", {"etat": "pause", "evenement": _evt(1, "commande", "Pause demandée.", "humain")})
    page_ui.get_by_role("button", name="Pause").click()
    page_ui.wait_for_function("() => document.querySelector('[role=status]').textContent === 'En pause'")
    assert page_ui.get_by_role("button", name="Reprendre").is_enabled()
    assert page_ui.get_by_role("button", name="Pause").is_disabled()
    page_ui.evaluate("(c) => { etatApi.commande = c; }", {"etat": "arret", "evenement": _evt(2, "commande", "Arrêt demandé.", "humain")})
    page_ui.get_by_role("button", name="Arrêter").click()
    page_ui.wait_for_function("() => document.querySelector('[role=status]').textContent === 'Arrêté'")
    page_ui.get_by_role("button", name="Voir la fenêtre sur mon PC").click()
    urls = page_ui.evaluate("() => appels.filter(a => a.methode === 'POST').map(a => a.url.split('/').pop())")
    assert urls == ["pause", "arret", "premier-plan"]


def test_commande_refusee_affiche_le_motif(page_ui: Page) -> None:
    _monter(page_ui)
    page_ui.get_by_role("button", name="Pause").click()  # etatApi.commande nul -> 409
    page_ui.wait_for_function("() => notifs.length === 1")
    assert page_ui.evaluate("() => notifs[0]") == ["Commande sans effet.", False]


def test_lecture_seule_voit_le_fil_sans_pouvoir_ecrire(page_ui: Page) -> None:
    page_ui.evaluate("() => { roleActif = 'lecture_seule'; }")
    _monter(page_ui, elements=[_evt(1, "agent", "Visible")])
    assert _textes(page_ui) == ["Visible"]
    assert page_ui.locator("textarea").is_disabled()
    for nom in ("Pause", "Reprendre", "Arrêter", "Envoyer"):
        assert page_ui.get_by_role("button", name=nom).is_disabled(), nom


def test_demontage_ferme_le_flux_et_vide_le_conteneur(page_ui: Page) -> None:
    _monter(page_ui)
    page_ui.evaluate("() => window.poignee.demonter()")
    assert page_ui.evaluate("() => flux[0].ferme && document.getElementById('zone').childNodes.length === 0")


def test_repli_par_interrogation_si_le_flux_echoue(page_ui: Page) -> None:
    _monter(page_ui)
    page_ui.evaluate("() => { for (let i = 0; i < 3; i++) flux[0].onerror(); }")
    assert page_ui.evaluate("() => flux[0].ferme")
    page_ui.evaluate("(e) => { etatApi.elements = [e]; }", _evt(5, "agent", "Reçu par interrogation"))
    page_ui.wait_for_function("() => document.querySelectorAll('.da-msg').length === 1", timeout=6000)


def test_mise_en_page_mobile_sans_debordement(page_ui: Page) -> None:
    page_ui.set_viewport_size({"width": 360, "height": 740})
    _monter(page_ui, elements=[_evt(1, "agent", "x" * 400)])
    assert page_ui.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth")


def test_mouvement_reduit_et_pas_de_validation_suggeree() -> None:
    assert "prefers-reduced-motion: reduce" in CSS_DISCUSSION_AGENT
    assert "animation: none !important" in CSS_DISCUSSION_AGENT
    assert "✓" not in JS_DISCUSSION_AGENT and "✔" not in JS_DISCUSSION_AGENT
    assert "transition: width" not in CSS_DISCUSSION_AGENT and "transition: height" not in CSS_DISCUSSION_AGENT


def test_defilement_intelligent_et_indicateur_discret(page_ui: Page) -> None:
    page_ui.set_viewport_size({"width": 900, "height": 700})
    _monter(page_ui, elements=[_evt(i, "agent", f"Message {i}") for i in range(1, 40)])
    page_ui.wait_for_timeout(300)
    # l'agent travaille : indicateur visible, aria-hidden, hors décompte des messages
    assert page_ui.locator(".da-ecrit").get_attribute("aria-hidden") == "true"
    assert page_ui.locator(".da-ecrit").is_visible()
    assert page_ui.locator(".da-msg").count() == 39
    page_ui.evaluate("() => { const f = document.querySelector('.da-fil'); f.dispatchEvent(new WheelEvent('wheel', { deltaY: -50 })); f.scrollTop = 0; }")
    page_ui.wait_for_timeout(200)
    page_ui.evaluate("() => flux[0].emettre('evenement', " + json.dumps(_evt(100, "agent", "Nouveau")) + ")")
    page_ui.wait_for_timeout(400)
    assert page_ui.evaluate("() => document.querySelector('.da-fil').scrollTop") < 50
    assert page_ui.locator(".da-nouveaux").is_visible()
    page_ui.locator(".da-nouveaux").click()
    page_ui.wait_for_function("() => { const f = document.querySelector('.da-fil'); return f.scrollHeight - f.scrollTop - f.clientHeight < 60; }")
    assert not page_ui.locator(".da-nouveaux").is_visible()
