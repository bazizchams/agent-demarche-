"""Démon d'écoute de l'Agent Local : sondage -> réservation -> exécution sur la page de démonstration.

Le navigateur est un vrai Chromium Playwright. Le serveur n'écoute sur aucun port : la page de démo
`http://testserver/demo/campus-france` est servie au navigateur par interception (`context.route`) depuis
l'application FastAPI de test. Le test « fenêtre VISIBLE » (headless=False) est sauté avec un motif explicite
si l'environnement n'a pas d'écran. Données fictives uniquement.
"""

from __future__ import annotations

import importlib.util
import json
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from playwright.sync_api import Route, sync_playwright

from app.agent_local.action_voeux_demo import executer_ajout_voeux_demo
from app.agent_local.demon_ecoute import (
    ContexteExecution,
    DemonEcoute,
    JetonRefuse,
    ResultatExecution,
)
from app.agent_local.ouverture_visible import (
    ErreurOuvertureNavigateur,
    FenetreVisible,
    ouvrir_contexte_visible,
)
from app.modeles.tache import ACTION_AJOUTER_VOEUX_PANIER
from tests.conftest import DonneesBureauTest, connecter_client
from tests.test_agent_ecoute_serveur import (
    client_agent,
    creer_tache_pc,
    enroler_agent,
)

URL_SERVEUR = "http://testserver"
MOTIVATION_SECRETE = "MOTIVATION-SECRETE-9137 : un projet d'études cohérent avec mon parcours."
VOEUX_DEMO = (
    ("Master 1 Intelligence Artificielle", "Sorbonne Université"),
    ("Master 1 Informatique", "Université Paris-Saclay"),
)
JS_ESPION_CLICS = """() => {
    window.__CLICS_INTERDITS__ = [];
    document.addEventListener('click', (e) => {
        const c = e.target.closest('#case-certif-exactitude, #case-certif-prerequis, #btn-soumission-finale-officielle, #btn-enregistrer-brouillon');
        if (c) window.__CLICS_INTERDITS__.push(c.id);
    }, true);
}"""


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------


class FenetreDeTest(FenetreVisible):
    """Vraie `FenetreVisible`, avec la page de démo servie par l'application de test."""

    def __init__(self, playwright: Any, racine: Path, serveur: TestClient, *, headless: bool = True) -> None:
        super().__init__(playwright, racine, canaux=(None,), headless=headless)
        self.requete_demo = "/demo/campus-france"
        self.statut_force: int | None = None
        self._serveur = serveur
        self._route_sur: Any = None

    def _servir(self, route: Route) -> None:
        if self.statut_force is not None:
            route.fulfill(status=self.statut_force, body="introuvable")
            return
        chemin = route.request.url.removeprefix(URL_SERVEUR)
        if chemin.split("?")[0] == "/demo/campus-france":
            chemin = self.requete_demo
        rep = self._serveur.get(chemin)
        route.fulfill(status=rep.status_code, body=rep.text, content_type="text/html; charset=utf-8")

    def page(self) -> Any:
        page = super().page()
        if self._route_sur is not self._contexte:
            self._contexte.route(f"{URL_SERVEUR}/**", self._servir)
            self._contexte.add_init_script(f"({JS_ESPION_CLICS})()")
            self._route_sur = self._contexte
        return page


@pytest.fixture()
def playwright_sync() -> Iterator[Any]:
    with sync_playwright() as p:
        yield p


class Scenario:
    def __init__(self, application: FastAPI, bureau: DonneesBureauTest, tmp_path: Path, p: Any) -> None:
        self.application = application
        self.admin, _ = connecter_client(application, bureau.admin.email)
        self.serveur_demo = TestClient(application)
        _agent_id, self.jeton = enroler_agent(self.admin)
        self.agent = client_agent(application, self.jeton)
        self.sortie: list[str] = []
        self.fenetre = FenetreDeTest(p, tmp_path / "profils" / "bureau", self.serveur_demo)

    def candidat_avec_voeux(self, nom: str = "Demo", voeux: tuple[tuple[str, str], ...] = VOEUX_DEMO) -> str:
        rep = self.admin.post(
            "/api/v1/candidats",
            json={"nom": nom, "prenom": "Pc", "email": f"{nom.lower()}.pc@exemple-fictif.dz"},
        )
        assert rep.status_code == 201, rep.text
        cid = rep.json()["id"]
        for intitule, etab in voeux:
            r = self.admin.post(
                f"/api/v1/candidats/{cid}/voeux",
                json={"intitule": intitule, "etablissement": etab, "niveau": "Master 1"},
            )
            assert r.status_code == 201, r.text
            vid = r.json()["id"]
            assert self.admin.patch(
                f"/api/v1/candidats/{cid}/voeux/{vid}", json={"motivation": MOTIVATION_SECRETE}
            ).status_code == 200
            assert self.admin.post(f"/api/v1/candidats/{cid}/voeux/{vid}/valider").status_code == 200
        return cid

    def creer_tache(self, candidat_id: str) -> str:
        rep = creer_tache_pc(self.admin, candidat_id)
        assert rep.status_code == 201, rep.text
        return rep.json()["id"]

    def demon(self, **kw: Any) -> DemonEcoute:
        return DemonEcoute(
            client_api=self.agent,
            fenetre=self.fenetre,
            executeurs={ACTION_AJOUTER_VOEUX_PANIER: executer_ajout_voeux_demo},
            url_serveur=URL_SERVEUR,
            intervalle_sondage_s=0.05,
            intervalle_battement_s=3600,
            sortie=self.sortie.append,
            **kw,
        )

    def tache(self, tache_id: str) -> dict[str, Any]:
        rep = self.admin.get(f"/api/v1/taches/{tache_id}")
        assert rep.status_code == 200, rep.text
        return rep.json()

    def dans_page(self, js: str) -> Any:
        return self.fenetre.page().evaluate(js)

    def fermer(self) -> None:
        self.fenetre.fermer()


@pytest.fixture()
def scenario(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
    tmp_path: Path,
    playwright_sync: Any,
) -> Iterator[Scenario]:
    s = Scenario(application, deux_bureaux[0], tmp_path, playwright_sync)
    try:
        yield s
    finally:
        s.fermer()


# ---------------------------------------------------------------------------
# Exécution complète sur la page de démonstration
# ---------------------------------------------------------------------------


def test_sondage_puis_execution_sur_la_page_de_demo_arret_avant_envoi(scenario: Scenario) -> None:
    s = scenario
    assert s.demon().sonder_une_fois() is False  # rien en attente : le sondage ne fait rien
    tache_id = s.creer_tache(s.candidat_avec_voeux())

    assert s.demon().sonder_une_fois() is True
    tache = s.tache(tache_id)

    # R1 : l'agent s'arrête à « à valider », il ne termine ni ne valide jamais lui-même.
    assert tache["statut"] == "a_valider"
    assert tache["verrou_actif"] is None and tache["capture_controle_disponible"] is True
    recap = tache["recapitulatif_remplissage"]
    assert recap["nb_voeux_traites"] == 2 and recap["nb_voeux_ajoutes_ou_deja_presents"] == 2
    assert [v["statut"] for v in recap["voeux"]] == ["ajoute", "ajoute"]
    assert recap["arret_avant_soumission_finale"] is True
    # R5 : ni texte de motivation ni jeton dans la tâche rendue ni dans la sortie du démon.
    assert MOTIVATION_SECRETE not in json.dumps(tache, ensure_ascii=False)
    assert all(MOTIVATION_SECRETE not in ligne and s.jeton not in ligne for ligne in s.sortie)

    # Les vœux sont réellement dans le panier de la page de démonstration, dans la fenêtre restée ouverte.
    assert s.dans_page("document.querySelectorAll('#panier-liste .panier-item').length") == 2
    assert s.dans_page("document.querySelector('#panier-compteur').innerText") == "2 / 7"
    # Aucune certification, aucun bouton de soumission, aucun brouillon global cliqués.
    assert s.dans_page("window.__CLICS_INTERDITS__") == []
    assert s.dans_page("window.__SOUMISSION_FINALE_CLIQUEE__") is False
    assert s.dans_page("window.__BROUILLON_ENREGISTRE__") is False
    # Le statut des vœux en base ne change pas (panier de démonstration, pas le vrai panier).
    assert {v["statut"] for v in s.admin.get(f"/api/v1/candidats/{tache['candidat_id']}/voeux").json()} == {"valide"}


def test_la_fenetre_reste_ouverte_et_est_reutilisee_d_une_tache_a_l_autre(scenario: Scenario) -> None:
    s = scenario
    cid = s.candidat_avec_voeux()
    t1 = s.creer_tache(cid)
    assert s.demon().sonder_une_fois() is True
    page_1 = s.fenetre.page()
    assert s.tache(t1)["statut"] == "a_valider" and not page_1.is_closed()

    # Le bureau valide (humain) puis relance : la même fenêtre sert à nouveau.
    assert s.admin.post(
        f"/api/v1/taches/{t1}/valider", json={"confirmation_humaine_explicite": True}
    ).status_code == 200
    s.creer_tache(cid)
    assert s.demon().sonder_une_fois() is True
    assert s.fenetre.page() is page_1


def test_r2_captcha_suspend_la_tache_puis_reprise_humaine(scenario: Scenario) -> None:
    s = scenario
    tache_id = s.creer_tache(s.candidat_avec_voeux())
    s.fenetre.requete_demo = "/demo/campus-france?captcha=1"

    assert s.demon().sonder_une_fois() is True
    tache = s.tache(tache_id)
    assert tache["statut"] == "suspendue" and tache["motif_suspension"] == "action_utilisateur_portail"
    assert "CAPTCHA" in tache["message_alerte"] and tache["verrou_actif"] is None
    # La fenêtre reste ouverte pour que l'humain résolve ; rien n'a été ajouté ni contourné.
    assert not s.fenetre.page().is_closed()
    assert s.dans_page("document.querySelectorAll('#panier-liste .panier-item').length") == 0
    assert s.dans_page("window.__CLICS_INTERDITS__") == []

    # L'humain a résolu le contrôle dans la fenêtre : il reprend la tâche, l'agent la reprend et termine.
    s.fenetre.requete_demo = "/demo/campus-france"
    assert s.admin.post(f"/api/v1/taches/{tache_id}/reprendre").json()["statut"] == "en_attente"
    assert s.demon().sonder_une_fois() is True
    assert s.tache(tache_id)["statut"] == "a_valider"


def test_r3_session_non_connectee_connexion_manuelle_dans_la_fenetre(scenario: Scenario) -> None:
    s = scenario
    tache_id = s.creer_tache(s.candidat_avec_voeux())
    s.fenetre.requete_demo = "/demo/campus-france?session_ouverte=0"

    assert s.demon().sonder_une_fois() is True
    tache = s.tache(tache_id)
    assert tache["statut"] == "suspendue"
    assert "connectez-vous vous-même" in tache["message_alerte"]
    assert "mot de passe" in tache["message_alerte"]
    # L'agent ne tape aucun mot de passe : la page n'a aucun champ de mot de passe rempli, aucun vœu ajouté.
    assert s.dans_page("Array.from(document.querySelectorAll('input[type=password]')).every(e => e.value === '')") is True
    assert s.dans_page("document.querySelectorAll('#panier-liste .panier-item').length") == 0


def test_voeux_devenus_non_valides_avant_execution_suspension_r4(scenario: Scenario) -> None:
    s = scenario
    cid = s.candidat_avec_voeux()
    tache_id = s.creer_tache(cid)
    for v in s.admin.get(f"/api/v1/candidats/{cid}/voeux").json():
        s.admin.patch(f"/api/v1/candidats/{cid}/voeux/{v['id']}", json={"motivation": "Texte modifié, à revalider."})

    assert s.demon().sonder_une_fois() is True
    tache = s.tache(tache_id)
    assert tache["statut"] == "suspendue" and tache["motif_suspension"] == "donnee_manquante"
    assert "règle 4" in tache["message_alerte"]


def test_page_de_demo_indisponible_en_production_tache_en_erreur(scenario: Scenario) -> None:
    s = scenario
    tache_id = s.creer_tache(s.candidat_avec_voeux())
    s.fenetre.statut_force = 404

    assert s.demon().sonder_une_fois() is True
    tache = s.tache(tache_id)
    assert tache["statut"] == "en_erreur" and tache["verrou_actif"] is None
    assert "RuntimeError" in tache["message_alerte"]  # type d'erreur seulement, jamais de donnée


def test_arret_propre_apres_la_tache_en_cours(scenario: Scenario) -> None:
    s = scenario
    tache_id = s.creer_tache(s.candidat_avec_voeux())
    demon = s.demon()
    # Le démon s'arrête dès qu'il a rendu la main à l'humain, via la même voie que Ctrl+C.

    def sortie(ligne: str) -> None:
        s.sortie.append(ligne)
        if "en attente de VOTRE validation" in ligne:
            demon.demander_arret()

    demon._sortie = sortie  # noqa: SLF001 - branchement du test sur la sortie du démon
    chrono = time.monotonic()
    assert demon.boucler() == 0
    assert time.monotonic() - chrono < 60
    assert s.tache(tache_id)["statut"] == "a_valider"
    assert any("arrêté proprement" in ligne for ligne in s.sortie)


def test_jeton_revoque_arrete_le_demon(scenario: Scenario) -> None:
    s = scenario
    agents = s.admin.get("/api/v1/agents-locaux").json()
    assert s.admin.post(f"/api/v1/agents-locaux/{agents[0]['id']}/revoquer").status_code == 200
    demon = s.demon()
    with pytest.raises(JetonRefuse):
        demon.sonder_une_fois()
    assert demon.boucler() == 3
    assert any("ARRÊT" in ligne for ligne in s.sortie)


# ---------------------------------------------------------------------------
# Démon sans navigateur : battement de cœur, action inconnue, erreurs, réseau
# ---------------------------------------------------------------------------


class _FenetreFactice:
    def __init__(self) -> None:
        self.premier_plan = 0

    def page(self) -> object:
        return object()

    def amener_au_premier_plan(self) -> None:
        self.premier_plan += 1


class _ClientEspion:
    """Enveloppe un client HTTP et note les appels."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self.appels: list[str] = []

    def get(self, url: str, **kw: Any) -> httpx.Response:
        self.appels.append("GET " + url)
        return self._client.get(url, **kw)

    def post(self, url: str, **kw: Any) -> httpx.Response:
        self.appels.append("POST " + url)
        return self._client.post(url, **kw)


@pytest.fixture()
def sans_navigateur(
    application: FastAPI, deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest]
) -> tuple[TestClient, _ClientEspion, str]:
    admin, _ = connecter_client(application, deux_bureaux[0].admin.email)
    _, jeton = enroler_agent(admin)
    espion = _ClientEspion(client_agent(application, jeton))
    rep = admin.post("/api/v1/candidats", json={"nom": "Sans", "prenom": "Nav", "email": "sans.nav@exemple-fictif.dz"})
    cid = rep.json()["id"]
    r = admin.post(
        f"/api/v1/candidats/{cid}/voeux",
        json={"intitule": "Master Fictif", "etablissement": "Université Fictive", "niveau": "Master 1"},
    )
    vid = r.json()["id"]
    admin.patch(f"/api/v1/candidats/{cid}/voeux/{vid}", json={"motivation": "Lettre complète."})
    admin.post(f"/api/v1/candidats/{cid}/voeux/{vid}/valider")
    return admin, espion, cid


def test_battement_de_coeur_pendant_une_longue_execution(
    sans_navigateur: Any,
) -> None:
    admin, espion, cid = sans_navigateur
    tache_id = creer_tache_pc(admin, cid).json()["id"]

    def lente(ctx: ContexteExecution) -> ResultatExecution:
        time.sleep(0.6)
        return ResultatExecution(recapitulatif={"ok": True})

    demon = DemonEcoute(
        client_api=espion,
        fenetre=_FenetreFactice(),
        executeurs={ACTION_AJOUTER_VOEUX_PANIER: lente},
        url_serveur=URL_SERVEUR,
        intervalle_battement_s=0.1,
        sortie=lambda _l: None,
    )
    assert demon.sonder_une_fois() is True
    battements = [a for a in espion.appels if a.endswith("/battement-coeur")]
    assert len(battements) >= 2 and all(tache_id in b for b in battements)
    assert admin.get(f"/api/v1/taches/{tache_id}").json()["statut"] == "a_valider"


def test_action_inconnue_de_l_agent_suspend_au_lieu_de_planter(sans_navigateur: Any) -> None:
    admin, espion, cid = sans_navigateur
    tache_id = creer_tache_pc(admin, cid).json()["id"]
    reservee = espion.post("/api/v1/taches/reserver-suivante").json()["tache"]
    assert reservee["id"] == tache_id
    demon = DemonEcoute(
        client_api=espion,
        fenetre=_FenetreFactice(),
        executeurs={},  # cette version de l'agent ne connaît aucune action
        url_serveur=URL_SERVEUR,
        sortie=lambda _l: None,
    )
    demon._traiter(reservee)  # noqa: SLF001
    tache = admin.get(f"/api/v1/taches/{tache_id}").json()
    assert tache["statut"] == "suspendue" and "ne sait pas exécuter" in tache["message_alerte"]


def test_erreur_d_un_executeur_n_expose_aucune_donnee_et_le_demon_continue(sans_navigateur: Any) -> None:
    admin, espion, cid = sans_navigateur
    tache_id = creer_tache_pc(admin, cid).json()["id"]

    def casse(_ctx: ContexteExecution) -> ResultatExecution:
        raise ValueError("Dupont Jean 12345 ne doit jamais fuiter")

    demon = DemonEcoute(
        client_api=espion,
        fenetre=_FenetreFactice(),
        executeurs={ACTION_AJOUTER_VOEUX_PANIER: casse},
        url_serveur=URL_SERVEUR,
        sortie=lambda _l: None,
    )
    assert demon.sonder_une_fois() is True
    tache = admin.get(f"/api/v1/taches/{tache_id}").json()
    assert tache["statut"] == "en_erreur"
    assert "ValueError" in tache["message_alerte"] and "Dupont" not in tache["message_alerte"]
    assert demon.sonder_une_fois() is False  # le démon est toujours en état de sonder


def test_serveur_injoignable_le_demon_reessaie_sans_planter() -> None:
    def transport(_requete: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("serveur éteint")

    client = httpx.Client(transport=httpx.MockTransport(transport), base_url=URL_SERVEUR)
    sorties: list[str] = []
    demon = DemonEcoute(
        client_api=client,
        fenetre=_FenetreFactice(),
        executeurs={ACTION_AJOUTER_VOEUX_PANIER: lambda c: ResultatExecution()},
        url_serveur=URL_SERVEUR,
        intervalle_sondage_s=0.01,
        sortie=sorties.append,
    )
    threading.Timer(0.3, demon.demander_arret).start()
    assert demon.boucler() == 0
    assert any("injoignable" in ligne for ligne in sorties)


# ---------------------------------------------------------------------------
# Ouverture du navigateur : ordre des canaux, profil par bureau, fenêtre visible
# ---------------------------------------------------------------------------


class _FaussePage:
    def __init__(self) -> None:
        self.premier_plan = 0

    def bring_to_front(self) -> None:
        self.premier_plan += 1


class _FauxContexte:
    def __init__(self) -> None:
        self.pages = [_FaussePage()]

    def close(self) -> None:
        self.pages = []


class _FauxChromium:
    def __init__(self, canaux_disponibles: set[str | None]) -> None:
        self.disponibles = canaux_disponibles
        self.appels: list[dict[str, Any]] = []

    def launch_persistent_context(self, **options: Any) -> _FauxContexte:
        self.appels.append(options)
        if options.get("channel") not in self.disponibles:
            raise RuntimeError("canal non installé")
        return _FauxContexte()


class _FauxPlaywright:
    def __init__(self, canaux_disponibles: set[str | None]) -> None:
        self.chromium = _FauxChromium(canaux_disponibles)


def test_ouverture_chrome_puis_edge_puis_chromium_profil_par_bureau(tmp_path: Path) -> None:
    pw = _FauxPlaywright({None})  # ni Chrome ni Edge
    contexte, canal = ouvrir_contexte_visible(pw, tmp_path / "bureau-1", headless=False)
    assert canal == "chromium" and contexte.pages
    essais = pw.chromium.appels
    assert [e.get("channel") for e in essais] == ["chrome", "msedge", None]
    assert all(e["headless"] is False and e["no_viewport"] is True for e in essais)
    # Un profil par navigateur, sous le dossier du bureau.
    profils = [Path(e["user_data_dir"]) for e in essais]
    assert len({p.name for p in profils}) == 3 and all(p.parent == tmp_path / "bureau-1" for p in profils)

    pw_edge = _FauxPlaywright({"msedge"})
    _, canal = ouvrir_contexte_visible(pw_edge, tmp_path / "bureau-2")
    assert canal == "msedge"


def test_ouverture_echoue_avec_un_message_clair_si_aucun_navigateur(tmp_path: Path) -> None:
    with pytest.raises(ErreurOuvertureNavigateur, match="playwright install chromium"):
        ouvrir_contexte_visible(_FauxPlaywright(set()), tmp_path / "b")


def test_fenetre_visible_premier_plan_reouverture_si_fermee_par_l_humain(tmp_path: Path) -> None:
    pw = _FauxPlaywright({"chrome"})
    fenetre = FenetreVisible(pw, tmp_path / "b", headless=False)
    page = fenetre.page()
    assert page.premier_plan == 1 and fenetre.canal == "chrome"  # bring_to_front à l'ouverture
    fenetre.amener_au_premier_plan()
    assert page.premier_plan == 2
    assert fenetre.page() is page  # réutilisée tant qu'elle est ouverte

    fenetre._contexte.close()  # noqa: SLF001 - l'humain ferme la fenêtre
    autre = fenetre.page()
    assert autre is not page and len(pw.chromium.appels) == 2  # rouverte automatiquement


class _EspionChromium:
    def __init__(self, reel: Any) -> None:
        self._reel = reel
        self.appels: list[dict[str, Any]] = []

    def launch_persistent_context(self, **options: Any) -> Any:
        self.appels.append(options)
        return self._reel.launch_persistent_context(**options)


class _EspionPlaywright:
    def __init__(self, reel: Any) -> None:
        self.chromium = _EspionChromium(reel.chromium)


def test_fenetre_reellement_visible_executant_la_tache(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
    tmp_path: Path,
    playwright_sync: Any,
) -> None:
    """Navigateur en `headless=False` (vraie fenêtre sur le bureau). Sauté s'il n'y a pas d'écran."""
    espion = _EspionPlaywright(playwright_sync)
    s = Scenario(application, deux_bureaux[0], tmp_path, espion)
    # Ordre de production (Chrome > Edge > Chromium) mais avec la page de démo servie par interception.
    s.fenetre = FenetreDeTest(espion, tmp_path / "profils" / "visible", s.serveur_demo, headless=False)
    s.fenetre._canaux = ("chrome", "msedge", None)  # noqa: SLF001
    try:
        try:
            s.fenetre.page()
        except ErreurOuvertureNavigateur as exc:
            pytest.skip(f"Aucune fenêtre de navigateur ne peut s'ouvrir dans cet environnement (pas d'écran ?) : {exc}")
        tache_id = s.creer_tache(s.candidat_avec_voeux())
        assert s.demon().sonder_une_fois() is True
        assert s.tache(tache_id)["statut"] == "a_valider"
        assert espion.chromium.appels and espion.chromium.appels[-1]["headless"] is False
        assert s.fenetre.canal in {"chrome", "msedge", "chromium"}
    finally:
        s.fermer()


# ---------------------------------------------------------------------------
# Lanceur en ligne de commande
# ---------------------------------------------------------------------------


def _charger_lanceur() -> Any:
    chemin = Path(__file__).resolve().parents[2] / "agent_local" / "lanceur.py"
    spec = importlib.util.spec_from_file_location("lanceur_agent_local", chemin)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lanceur_mode_ecouter_sans_jeton_refuse(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("BE_JETON_AGENT", raising=False)
    code = _charger_lanceur().main(["--mode", "ecouter", "--url-serveur", "http://127.0.0.1:9"])
    assert code == 2
    assert "BE_JETON_AGENT" in capsys.readouterr().err


def test_lanceur_mode_ecouter_serveur_injoignable(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("BE_JETON_AGENT", "be_agent_factice")
    code = _charger_lanceur().main(["--mode", "ecouter", "--url-serveur", "http://127.0.0.1:9"])
    assert code == 2
    err = capsys.readouterr().err
    assert "injoignable" in err and "be_agent_factice" not in err  # le jeton n'est jamais affiché


def test_lanceur_les_autres_modes_exigent_toujours_la_config_portail() -> None:
    with pytest.raises(SystemExit) as exc:
        _charger_lanceur().main(["--mode", "executer"])
    assert exc.value.code == 2
