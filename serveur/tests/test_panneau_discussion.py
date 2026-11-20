"""Panneau de discussion injecté dans un VRAI Chromium (headless) sur une page de démonstration locale.

Vérifie : messages typés affichés, saisie remontée à Python, Pause / Reprendre / Arrêter, surlignage non intrusif,
champs sensibles jamais lus, survie aux navigations, accessibilité, mouvement réduit, aucun innerHTML/eval.
Aucun portail réel : pages servies par `page.route`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Route, sync_playwright

from app.agent_local.journal_agent import ArretDemandeParHumain, JournalAgent
from app.agent_local.panneau_discussion import JS_PANNEAU_DISCUSSION, pont_pour

ORIGINE = "http://portail.test"
MARQUEUR_VALEUR = "VALEUR-SAISIE-SECRETE-77"
PAGE_DEMO = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Démo</title></head><body>
<h1>Portail de démonstration</h1>
<form onsubmit="return false">
  <input id="recherche" name="recherche" type="text" aria-label="Recherche">
  <input id="mdp" name="motdepasse" type="password" aria-label="Mot de passe">
  <input id="passeport" name="passeport_numero" type="text" aria-label="Passeport">
  <button id="btn" type="button">Ajouter au panier</button>
  <button id="droite" type="button" style="float:right">Bouton à droite</button>
</form><a id="suite" href="/page2">Page suivante</a></body></html>"""
PAGE_2 = "<!doctype html><html lang='fr'><body><h1>Deuxième page</h1><button id='b2'>Ok</button></body></html>"
RACINE = "document.getElementById('agent-panneau-hote').shadowRoot"


class _Reponse:
    def __init__(self, statut: int, corps: dict[str, Any]) -> None:
        self.status_code = statut
        self._corps = corps

    def json(self) -> dict[str, Any]:
        return self._corps


class FauxClient:
    """Remplace le client HTTP du démon : enregistre les événements, sert des consignes préparées."""

    def __init__(self) -> None:
        self.postes: list[dict[str, Any]] = []
        self.reponse_attente: dict[str, Any] = {"messages": [], "commandes": [], "etat": "en_cours"}
        self.file_attente: list[dict[str, Any]] = []  # réponses successives (la dernière reste)

    def post(self, url: str, **kwargs: Any) -> Any:
        self.postes.append({"url": url, **kwargs.get("json", {})})
        return _Reponse(201, {})

    def get(self, url: str, **_: Any) -> Any:
        if self.file_attente:
            self.reponse_attente = self.file_attente.pop(0)
        return _Reponse(200, self.reponse_attente)


@pytest.fixture(scope="module")
def navigateur() -> Iterator[Browser]:
    with sync_playwright() as p:
        nav = p.chromium.launch(headless=True)
        yield nav
        nav.close()


def _servir(contexte: BrowserContext) -> None:
    def gerer(route: Route) -> None:
        corps = PAGE_2 if route.request.url.endswith("/page2") else PAGE_DEMO
        route.fulfill(status=200, body=corps, content_type="text/html; charset=utf-8")

    contexte.route(f"{ORIGINE}/**", gerer)


@pytest.fixture()
def banc(navigateur: Browser) -> Iterator[Callable[..., tuple[Page, JournalAgent, FauxClient]]]:
    contextes: list[BrowserContext] = []

    def fabriquer(**options_contexte: Any) -> tuple[Page, JournalAgent, FauxClient]:
        contexte = navigateur.new_context(**{k: v for k, v in options_contexte.items() if k != "_ouvert"})
        contextes.append(contexte)
        _servir(contexte)
        page = contexte.new_page()
        page.goto(ORIGINE + "/")
        if options_contexte.get("_ouvert", True):
            page.evaluate("() => { window.__AGENT_PANNEAU_OUVERT__ = true; }")  # racine ouverte : inspection des tests
            contexte.add_init_script("window.__AGENT_PANNEAU_OUVERT__ = true;")
        client = FauxClient()
        pont = pont_pour(page)
        pont.installer()
        journal = JournalAgent(
            tache_id="11111111-1111-1111-1111-111111111111", client_api=client, pont=pont, intervalle_serveur_s=0
        )
        journal._definir_etat("travaille")  # comme `JournalAgent.depuis_contexte`
        return page, journal, client

    yield fabriquer
    for c in contextes:
        c.close()


def _textes(page: Page) -> list[str]:
    return page.evaluate(f"() => Array.from({RACINE}.querySelectorAll('.msg .texte')).map(n => n.textContent)")


def test_le_script_n_utilise_ni_innerhtml_ni_eval() -> None:
    for interdit in ("innerHTML", "outerHTML", "insertAdjacentHTML", "eval(", "new Function", "document.write", "console.log"):
        assert interdit not in JS_PANNEAU_DISCUSSION, interdit


def test_messages_types_affiches_dans_un_shadow_dom_accessible(banc: Callable[..., Any]) -> None:
    page, journal, _ = banc()
    journal.dire("Je commence")
    journal.agir("Je clique sur Ajouter")
    journal.alerter("Un problème")
    journal.demander_humain("Connectez-vous vous-même")
    assert _textes(page) == ["Je commence", "Je clique sur Ajouter", "Un problème", "Connectez-vous vous-même"]
    classes = page.evaluate(f"() => Array.from({RACINE}.querySelectorAll('.msg')).map(n => n.className)")
    assert [c.split()[1] for c in classes] == ["t-agent", "t-action", "t-alerte", "t-demande_humaine"]
    attrs = page.evaluate(
        f"""() => {{ const r = {RACINE};
          const log = r.querySelector('[role=log]');
          return {{ aria: log.getAttribute('aria-live'), alertes: r.querySelectorAll('.msg[role=alert]').length,
                   region: r.querySelector('section').getAttribute('aria-label'), etat: r.querySelector('[role=status]').textContent }}; }}"""
    )
    assert attrs["aria"] == "polite" and attrs["alertes"] == 2 and "agent" in attrs["region"].lower()
    assert "Attend votre aide" in attrs["etat"]


def test_du_html_dans_un_message_reste_du_texte(banc: Callable[..., Any]) -> None:
    page, journal, _ = banc()
    journal.dire("<img src=x onerror=window.piratage=1><b>gras</b>")
    assert page.evaluate("() => window.piratage === undefined")
    assert page.evaluate(f"() => {RACINE}.querySelectorAll('.msg img, .msg b').length") == 0
    assert "<b>gras</b>" in _textes(page)[0]


def test_le_style_du_portail_n_affecte_pas_le_panneau_et_la_page_reste_utilisable(banc: Callable[..., Any]) -> None:
    page, journal, _ = banc()
    page.add_style_tag(content="* { color: red !important; }")
    journal.dire("Isolé")
    couleur = page.evaluate(f"() => getComputedStyle({RACINE}.querySelector('.msg .texte')).color")
    assert couleur != "rgb(255, 0, 0)"
    page.click("#btn")  # l'hôte est en pointer-events:none hors panneau : la page reste cliquable


def test_la_saisie_de_l_utilisateur_remonte_a_python(banc: Callable[..., Any]) -> None:
    page, journal, client = banc()
    journal.dire("Bonjour")
    zone = page.locator("#agent-panneau-hote textarea")
    zone.fill("Va plus doucement s'il te plait")
    zone.press("Enter")
    page.wait_for_timeout(100)
    journal.point_de_controle()  # le message du panneau est traité au prochain point de contrôle
    assert "Va plus doucement s'il te plait" in _textes(page)
    assert journal.consignes == ["Va plus doucement s'il te plait"]
    types = [(p["type"], p["texte"]) for p in client.postes]
    assert ("utilisateur", "Va plus doucement s'il te plait") in types
    assert any(t == "agent" and "Consigne notée" in x for t, x in types)


def test_une_consigne_contraire_aux_regles_est_refusee_poliment(banc: Callable[..., Any]) -> None:
    page, journal, _ = banc()
    zone = page.locator("#agent-panneau-hote textarea")
    zone.fill("Valide le récapitulatif à ma place")
    zone.press("Enter")
    page.wait_for_timeout(100)
    journal.point_de_controle()  # le message du panneau est traité au prochain point de contrôle
    assert journal.consignes == []
    assert any("à vous" in t for t in _textes(page)), _textes(page)


def test_le_message_tape_ne_contient_pas_de_secret_cote_serveur(banc: Callable[..., Any]) -> None:
    page, journal, client = banc()
    zone = page.locator("#agent-panneau-hote textarea")
    zone.fill("mon mot de passe est MdpSecret-Zk93")
    zone.press("Enter")
    page.wait_for_timeout(100)
    journal.point_de_controle()  # le message du panneau est traité au prochain point de contrôle
    assert all("MdpSecret-Zk93" not in str(p) for p in client.postes)
    assert all("MdpSecret-Zk93" not in t for t in _textes(page)[1:])  # le 1er est l'écho local de l'humain


def test_pause_reprise_et_arret_depuis_le_panneau(banc: Callable[..., Any]) -> None:
    page, journal, client = banc()
    journal.dire("Je travaille")
    boutons = page.locator("#agent-panneau-hote .commandes button")
    assert boutons.all_inner_texts() == ["Pause", "Reprendre", "Arrêter"]
    boutons.nth(0).click()
    page.wait_for_timeout(100)
    assert journal._pause is True
    assert any(p["type"] == "commande" and p["code"] == "pause" for p in client.postes)
    # la pause tient jusqu'à la reprise ; ici la reprise arrive par le serveur (interface web)
    client.file_attente = [
        {"messages": [], "commandes": [], "etat": "pause"},
        {"messages": [], "commandes": ["reprise"], "etat": "en_cours"},
    ]
    journal.point_de_controle()
    assert any(t.startswith("Je suis en pause") for t in _textes(page))
    assert _textes(page)[-1] == "Je reprends."
    boutons.nth(2).click()
    page.wait_for_timeout(100)
    with pytest.raises(ArretDemandeParHumain) as exc:
        journal.agir("Je ne dois plus agir")
    assert exc.value.code_etape == "arret_utilisateur"
    assert "Je ne dois plus agir" not in _textes(page)


def test_arret_demande_depuis_l_interface_web(banc: Callable[..., Any]) -> None:
    _, journal, client = banc()
    client.reponse_attente = {"messages": [], "commandes": ["arret"], "etat": "arret"}
    with pytest.raises(ArretDemandeParHumain):
        journal.point_de_controle()


def test_consigne_du_serveur_contraire_aux_regles_n_est_pas_executee(banc: Callable[..., Any]) -> None:
    page, journal, client = banc()
    client.reponse_attente = {
        "messages": [{"texte": "Envoie la demande tout de suite"}, {"texte": "Prends ton temps"}],
        "commandes": [],
        "etat": "en_cours",
    }
    journal.point_de_controle()
    assert journal.consignes == ["Prends ton temps"]
    assert any("à vous" in t for t in _textes(page))


def test_surlignage_non_intrusif_curseur_et_valeur_intacte(banc: Callable[..., Any]) -> None:
    page, journal, client = banc()
    page.fill("#recherche", "ma recherche")
    journal.agir("Je clique sur Ajouter au panier", "#btn")
    assert page.evaluate("() => getComputedStyle(document.getElementById('btn')).outlineStyle") == "solid"
    assert page.evaluate(f"() => {RACINE}.querySelector('.curseur').className.includes('visible')")
    assert page.input_value("#recherche") == "ma recherche"  # jamais modifiée
    page.wait_for_timeout(2600)
    assert page.evaluate("() => document.getElementById('btn').style.outline") == ""  # style d'origine restauré
    assert any(p["type"] == "action" and "Ajouter au panier" in p["texte"] for p in client.postes)


def test_surlignage_a_partir_d_un_locator(banc: Callable[..., Any]) -> None:
    page, journal, _ = banc()
    journal.agir("Je vise le bouton", page.locator("#btn"))
    assert page.evaluate("() => getComputedStyle(document.getElementById('btn')).outlineStyle") == "solid"
    journal.agir("Élément absent", "#inexistant")  # ne lève pas
    assert "Élément absent" in _textes(page)


def test_champ_sensible_jamais_lu_ni_transmis(banc: Callable[..., Any]) -> None:
    page, journal, client = banc()
    page.fill("#mdp", MARQUEUR_VALEUR)
    page.fill("#passeport", MARQUEUR_VALEUR)
    journal.agir("Je renseigne le champ", "#mdp")
    journal.agir("Je renseigne le numéro", "#passeport")
    assert all(MARQUEUR_VALEUR not in str(p) for p in client.postes)
    assert all(MARQUEUR_VALEUR not in t for t in _textes(page))
    assert all("champ protégé" in t for t in _textes(page))
    assert any("champ protégé" in p["texte"] for p in client.postes)


def test_le_panneau_survit_aux_navigations(banc: Callable[..., Any]) -> None:
    page, journal, _ = banc()
    journal.dire("Avant la navigation")
    page.click("#suite")
    page.wait_for_url("**/page2")
    page.wait_for_function("() => !!document.getElementById('agent-panneau-hote')")
    journal.dire("Après la navigation")
    assert _textes(page) == ["Avant la navigation", "Après la navigation"]


def test_replier_et_deplier(banc: Callable[..., Any]) -> None:
    page, journal, _ = banc()
    journal.dire("Un")
    page.locator("#agent-panneau-hote button", has_text="Replier").click()
    assert page.locator("#agent-panneau-hote .panneau").evaluate("n => n.classList.contains('replie')")
    journal.dire("Message pendant que c'est replié")
    assert page.locator("#agent-panneau-hote .badge").inner_text() == "1"
    journal.demander_humain("Il me faut votre aide")  # une demande déplie le panneau
    assert not page.locator("#agent-panneau-hote .panneau").evaluate("n => n.classList.contains('replie')")
    page.locator("#agent-panneau-hote textarea").press("Escape")
    assert page.locator("#agent-panneau-hote .panneau").evaluate("n => n.classList.contains('replie')")


def test_mouvement_reduit_respecte(banc: Callable[..., Any]) -> None:
    page, journal, _ = banc(reduced_motion="reduce")
    journal.agir("Je vise", "#btn")
    duree = page.evaluate(f"() => getComputedStyle({RACINE}.querySelector('.curseur')).transitionDuration")
    assert float(duree.split(",")[0].strip().rstrip("s")) <= 0.001


def test_le_panneau_n_est_jamais_monte_dans_un_iframe(banc: Callable[..., Any]) -> None:
    page, _, _ = banc()
    page.evaluate(
        "() => { const f = document.createElement('iframe'); f.id = 'cadre'; f.srcdoc = '<p>x</p>'; document.body.appendChild(f); }"
    )
    page.frame_locator("#cadre").locator("p").wait_for()
    assert page.frames[1].evaluate("() => !document.getElementById('agent-panneau-hote')")


def test_une_panne_du_panneau_ne_fait_pas_echouer_la_tache() -> None:
    class PageCassee:
        @property
        def context(self) -> Any:
            raise RuntimeError("contexte indisponible")

        def on(self, *_: Any) -> None:
            raise RuntimeError("page indisponible")

    class CtxFactice:
        tache_id = "22222222-2222-2222-2222-222222222222"
        page = PageCassee()
        client_api = FauxClient()
        amener_au_premier_plan = staticmethod(lambda: None)

    journal = JournalAgent.depuis_contexte(CtxFactice())
    journal.dire("Toujours là")  # serveur seul
    assert CtxFactice.client_api.postes[-1]["texte"] == "Toujours là"


def test_racine_fermee_par_defaut_les_selecteurs_de_l_agent_ne_voient_pas_le_panneau(banc: Callable[..., Any]) -> None:
    """Régression : un `locator("textarea")` ou `get_by_role("button")` de l'agent ne doit jamais tomber sur le
    panneau (le champ de motivation du portail est un textarea)."""
    page, journal, _ = banc(_ouvert=False)
    journal.dire("Je suis là")
    assert page.evaluate("() => document.getElementById('agent-panneau-hote').shadowRoot") is None
    assert page.locator("textarea").count() == 0
    assert page.get_by_role("button", name="Envoyer").count() == 0
    assert page.get_by_text("Je suis là").count() == 0
    assert page.locator("button").count() == 2  # uniquement les 2 boutons du portail


def test_le_panneau_deplie_ne_masque_ni_ne_bloque_la_page(banc: Callable[..., Any]) -> None:
    """Régression : le panneau superposé interceptait les clics sur le bord droit du portail (voeux en erreur)."""
    page, journal, _ = banc()
    journal.dire("Bonjour")
    boite = page.locator("#droite").bounding_box()
    assert boite is not None and boite["x"] + boite["width"] <= 1280 - 360 + 1
    page.click("#droite", timeout=2000)  # Playwright échoue si un autre élément intercepte le clic
    page.locator("#agent-panneau-hote button", has_text="Replier").click()
    assert page.evaluate("() => document.documentElement.style.marginRight") == ""  # marge d'origine rétablie


def test_mouvement_reduit_aucune_animation_ni_trajectoire(banc: Callable[..., Any]) -> None:
    """prefers-reduced-motion : ni apparition, ni pulsation, ni curseur animé ; le message reste visible."""
    page, journal, _ = banc(reduced_motion="reduce")
    journal.dire("Je commence")
    journal.agir("Je vise", "#btn")
    journal.agir("Je vise ailleurs", "#droite")
    noms = page.evaluate(
        f"""() => Array.from({RACINE}.querySelectorAll('*')).map(n => getComputedStyle(n).animationName)
                .filter(a => a !== 'none')"""
    )
    assert noms == []
    assert page.evaluate(f"() => {RACINE}.querySelector('.curseur').getAnimations().length") == 0
    assert page.evaluate(f"() => getComputedStyle({RACINE}.querySelector('.msg')).opacity") == "1"


def test_le_curseur_suit_une_trajectoire_courte_et_ne_capte_aucun_clic(banc: Callable[..., Any]) -> None:
    page, journal, _ = banc()
    journal.agir("Premier", "#btn")
    journal.agir("Second", "#droite")
    duree = page.evaluate(f"() => {RACINE}.querySelector('.curseur').getAnimations().map(a => a.effect.getTiming().duration)")
    assert all(d <= 500 for d in duree) and duree
    for selecteur in (".curseur", ".halo"):
        assert page.evaluate(f"() => getComputedStyle({RACINE}.querySelector('{selecteur}')).pointerEvents") == "none"
    page.click("#btn", timeout=2000)  # halo et curseur au-dessus du bouton : le clic du portail passe


def test_panneau_replie_n_intercepte_aucun_clic_du_portail(banc: Callable[..., Any]) -> None:
    page, journal, _ = banc()
    journal.dire("Un")
    page.locator("#agent-panneau-hote button", has_text="Replier").click()
    page.wait_for_timeout(350)  # fin de l'animation de repli
    assert page.evaluate(f"() => getComputedStyle({RACINE}.querySelector('.panneau')).visibility") == "hidden"
    point = page.locator("#droite").bounding_box()
    assert point is not None
    page.mouse.click(1275, 40)  # sous l'ancien emplacement du panneau
    assert page.evaluate("() => document.elementFromPoint(1275, 40).tagName") in {"HTML", "BODY", "FORM", "H1"}


def test_defilement_intelligent_ne_vole_pas_la_lecture(banc: Callable[..., Any]) -> None:
    page, journal, _ = banc(viewport={"width": 1280, "height": 500})
    for i in range(30):
        journal.dire(f"Message numéro {i}")
    page.wait_for_timeout(1500)
    fil = f"{RACINE}.querySelector('.fil')"
    assert page.evaluate(f"() => {fil}.scrollHeight - {fil}.scrollTop - {fil}.clientHeight < 60")  # suit le bas
    page.evaluate(f"() => {{ {fil}.scrollTop = 0; }}")
    page.wait_for_timeout(500)
    journal.dire("Nouveau message pendant la lecture")
    page.wait_for_timeout(500)
    assert page.evaluate(f"() => {fil}.scrollTop") < 50  # la lecture n'a pas été déplacée
    assert page.evaluate(f"() => {RACINE}.querySelector('.nouveaux').className.includes('visible')")
    page.evaluate(f"() => {RACINE}.querySelector('.nouveaux').click()")
    page.wait_for_timeout(800)
    assert page.evaluate(f"() => {fil}.scrollHeight - {fil}.scrollTop - {fil}.clientHeight < 60")


def test_l_animation_ne_suggere_jamais_une_validation(banc: Callable[..., Any]) -> None:
    """R1 : aucune coche ni mention de validation/envoi dans le décor du panneau ; la demande humaine reste du texte."""
    assert "✓" not in JS_PANNEAU_DISCUSSION and "✔" not in JS_PANNEAU_DISCUSSION
    page, journal, _ = banc()
    journal.demander_humain("Cliquez vous-même sur Envoyer")
    assert page.evaluate(f"() => {RACINE}.querySelectorAll('.msg.t-demande_humaine').length") == 1
