"""Co-Pilote navigateur EN LIGNE : une session par bureau, pont sécurisé, Règle 6, vue opérateur.

Playwright Chromium headless sur la page de démonstration (`http://portail.local/demo/...`, interceptée par
le pilote) ou sur du HTML local. Aucune connexion à un vrai portail. Données fictives uniquement.
"""

from __future__ import annotations

import struct
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.agent_local.domaines_officiels import PolitiqueNavigation, politique_depuis_parametres
from app.agent_local.sessions_navigateur import (
    RegistreSessionsNavigateur,
    SessionNavigateur,
    dossier_profil_bureau,
)
from app.api.dependances import EN_TETE_CSRF, EN_TETE_JETON_AGENT
from app.core.config import Environnement, Parametres
from app.core.erreurs import LimiteAtteinte
from tests.conftest import DonneesBureauTest, connecter_client
from tests.test_acces_abonnement import _regler_abonnement
from tests.test_panier_voeux_demo import _creer_candidat

URL_DEMO = "http://portail.local/demo/campus-france"
TEXTE_SECRET = "Secret2FA-483920"

HTML_PAGE_CONTROLE = """
<html><body style="margin:0;height:5000px">
<input id="champ" style="position:absolute;left:100px;top:100px;width:300px;height:40px">
<a id="piege" href="https://pirate.example.org/x?jeton=abc"
   style="position:absolute;left:100px;top:300px;width:300px;height:40px;display:block">piege</a>
<div id="bloc-captcha-securite" style="position:absolute;left:600px;top:100px">CAPTCHA</div>
</body></html>
"""


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------


class FausseHorloge:
    def __init__(self) -> None:
        self.maintenant = 1000.0

    def __call__(self) -> float:
        return self.maintenant

    def avancer(self, secondes: float) -> None:
        self.maintenant += secondes


class FauxGestionnaire:
    def __init__(self) -> None:
        self.jeton_bridge_local = uuid.uuid4().hex
        self.arrete = False

    def arreter(self) -> None:
        self.arrete = True


def _registre_factice(horloge: FausseHorloge) -> tuple[RegistreSessionsNavigateur, list[FauxGestionnaire]]:
    crees: list[FauxGestionnaire] = []

    def fabrique(_tenant: uuid.UUID, _parametres: Parametres, _dossier: Path) -> Any:
        g = FauxGestionnaire()
        crees.append(g)
        return g

    return (
        RegistreSessionsNavigateur(horloge=horloge, fabrique=fabrique, intervalle_surveillance_s=None),
        crees,
    )


def _dimensions_jpeg(octets: bytes) -> tuple[int, int]:
    """(largeur, hauteur) lues dans le marqueur SOF du JPEG (sans dépendance à Pillow)."""
    assert octets[:2] == b"\xff\xd8", "pas un JPEG"
    i = 2
    while i < len(octets) - 9:
        assert octets[i] == 0xFF
        marqueur = octets[i + 1]
        longueur = struct.unpack(">H", octets[i + 2 : i + 4])[0]
        if marqueur in (0xC0, 0xC1, 0xC2):
            hauteur, largeur = struct.unpack(">HH", octets[i + 5 : i + 9])
            return largeur, hauteur
        i += 2 + longueur
    raise AssertionError("marqueur SOF introuvable")


def _dans_page(session: SessionNavigateur, fn: Any) -> Any:
    g = session.gestionnaire
    return g._executor.submit(lambda: fn(g._page)).result(timeout=30)


def _ouvrir_demo(client: TestClient, url: str = URL_DEMO) -> dict[str, Any]:
    rep = client.post(
        "/api/v1/portails/action-dom-directe",
        json={"type_operation": "naviguer", "url_destination": url, "ouvrir_fenetre_visible": False},
    )
    assert rep.status_code == 200, rep.text
    return rep.json()


def _session_du_bureau(application: FastAPI, bureau: DonneesBureauTest) -> SessionNavigateur:
    session = application.state.registre_navigateur.existante(bureau.bureau.id)
    assert session is not None
    return session


@pytest.fixture()
def deux_clients(
    application: FastAPI, deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest]
) -> tuple[TestClient, TestClient]:
    a, b = deux_bureaux
    return connecter_client(application, a.admin.email)[0], connecter_client(application, b.admin.email)[0]


# ---------------------------------------------------------------------------
# Registre (sans navigateur : fabrique factice, horloge injectée)
# ---------------------------------------------------------------------------


def test_registre_session_par_bureau_creation_paresseuse_et_profils_isoles(parametres_test: Parametres) -> None:
    registre, crees = _registre_factice(FausseHorloge())
    a, b = uuid.uuid4(), uuid.uuid4()
    assert crees == [] and registre.nombre_sessions() == 0  # rien n'est créé à l'avance

    sa = registre.obtenir(a, parametres_test)
    sb = registre.obtenir(b, parametres_test)

    assert registre.obtenir(a, parametres_test) is sa  # même bureau : même session
    assert sa is not sb and sa.gestionnaire is not sb.gestionnaire
    assert sa.dossier_profil != sb.dossier_profil
    assert sa.dossier_profil == dossier_profil_bureau(parametres_test, a)
    assert sa.dossier_profil.name == str(a)
    assert sa.dossier_profil.parent.name == "profil_navigateur_agent"
    assert sa.jeton_bridge != sb.jeton_bridge
    assert registre.par_jeton(sa.jeton_bridge) is sa
    assert registre.par_jeton(sb.jeton_bridge) is sb
    assert registre.par_jeton("faux") is None and registre.par_jeton("") is None and registre.par_jeton(None) is None
    registre.fermer_tout()


def test_registre_limite_de_sessions_simultanees(parametres_test: Parametres) -> None:
    assert parametres_test.navigateur_max_sessions == 3  # défaut
    registre, _ = _registre_factice(FausseHorloge())
    bureaux = [uuid.uuid4() for _ in range(4)]
    for t in bureaux[:3]:
        registre.obtenir(t, parametres_test)

    with pytest.raises(LimiteAtteinte):
        registre.obtenir(bureaux[3], parametres_test)
    registre.obtenir(bureaux[0], parametres_test)  # un bureau déjà servi n'est jamais refusé

    assert registre.fermer(bureaux[1]) is True
    registre.obtenir(bureaux[3], parametres_test)  # une place s'est libérée
    assert registre.nombre_sessions() == 3
    registre.fermer_tout()


def test_registre_fermeture_sur_inactivite_avec_horloge_injectee(parametres_test: Parametres) -> None:
    assert parametres_test.navigateur_inactivite_minutes == 15  # défaut
    horloge = FausseHorloge()
    registre, crees = _registre_factice(horloge)
    inactif, actif = uuid.uuid4(), uuid.uuid4()
    registre.obtenir(inactif, parametres_test)
    registre.obtenir(actif, parametres_test)

    horloge.avancer(14 * 60)
    assert registre.purger_inactives() == []
    registre.toucher(actif)  # l'activité repousse l'échéance
    horloge.avancer(2 * 60)  # 16 min pour `inactif`, 2 min pour `actif`

    assert registre.purger_inactives() == [inactif]
    assert registre.existante(inactif) is None
    assert registre.existante(actif) is not None
    assert crees[0].arrete is True and crees[1].arrete is False

    horloge.avancer(15 * 60)
    assert registre.existante(actif) is None  # l'accès lui-même purge les sessions expirées
    assert crees[1].arrete is True


def test_registre_arret_ferme_tout_et_revocation_efface_le_profil(
    parametres_test: Parametres, tmp_path: Path
) -> None:
    registre, crees = _registre_factice(FausseHorloge())
    a, b = uuid.uuid4(), uuid.uuid4()
    sa = registre.obtenir(a, parametres_test)
    sb = registre.obtenir(b, parametres_test)
    for s in (sa, sb):
        s.dossier_profil.mkdir(parents=True)
        (s.dossier_profil / "Cookies").write_text("cookie-portail-fictif")

    registre.revoquer(a, parametres_test)
    assert not sa.dossier_profil.exists() and crees[0].arrete is True
    assert sb.dossier_profil.exists()  # l'autre bureau n'est pas touché

    # Révocation sans session ouverte : le profil restant est tout de même effacé
    reste = dossier_profil_bureau(parametres_test, uuid.uuid4())
    reste.mkdir(parents=True)
    (reste / "Cookies").write_text("x")
    registre.revoquer(uuid.UUID(reste.name), parametres_test)
    assert not reste.exists()

    registre.fermer_tout()
    assert crees[1].arrete is True and registre.nombre_sessions() == 0
    assert sb.dossier_profil.exists()  # l'arrêt de l'application garde le profil (reprise de session)


# ---------------------------------------------------------------------------
# Règle 6 : politique de navigation
# ---------------------------------------------------------------------------


def test_politique_domaines_officiels_issus_des_yaml(parametres_test: Parametres) -> None:
    politique = politique_depuis_parametres(parametres_test)
    assert "etudesenfrance.diplomatie.gouv.fr" in politique.domaines_https
    assert "portal-portail.apps.cic.gc.ca" in politique.domaines_https
    assert politique.autoriser_demo is True  # environnement de test

    assert politique.motif_refus("https://etudesenfrance.diplomatie.gouv.fr/connexion?x=1") is None
    assert politique.motif_refus("https://paiement.if-algerie.com") is None
    assert politique.motif_refus(URL_DEMO) is None
    assert politique.motif_refus("http://portail.local/demo/ircc?captcha=1") is None


@pytest.mark.parametrize(
    "url",
    [
        "http://etudesenfrance.diplomatie.gouv.fr/",  # http au lieu de https
        "https://etudesenfrance.diplomatie.gouv.fr.pirate.example/",  # domaine imitateur (préfixe)
        "https://pirate-etudesenfrance.diplomatie.gouv.fr.example.org/",
        "https://diplomatie.gouv.fr/",  # parent non listé
        "https://sous.etudesenfrance.diplomatie.gouv.fr/",  # sous-domaine non listé
        "https://etudesenfrance.diplomatie.gouv.fr@pirate.example/",  # identifiants intégrés
        "https://etudesenfrance.diplomatie.gouv.fr:8443/",  # port non standard
        "https://pirate.example.org/",
        "javascript:alert(1)",
        "file:///C:/Windows/win.ini",
        "about:blank",
        "",
        "http://portail.local.pirate.example/demo/x",  # démo imitée
        "http://portail.local/autre-chemin",  # hors /demo
        "https://portail.local/demonstration",
    ],
)
def test_politique_refuse_liens_http_et_domaines_imitateurs(parametres_test: Parametres, url: str) -> None:
    motif = politique_depuis_parametres(parametres_test).motif_refus(url)
    assert motif is not None and "Règle 6" in motif
    assert "?" not in motif and "jeton" not in motif  # le message ne reflète pas l'URL complète


def test_politique_en_production_refuse_la_demo(parametres_test: Parametres) -> None:
    prod = PolitiqueNavigation(
        domaines_https=politique_depuis_parametres(parametres_test).domaines_https, autoriser_demo=False
    )
    assert prod.motif_refus(URL_DEMO) is not None
    assert prod.motif_refus("https://etudesenfrance.diplomatie.gouv.fr/") is None
    assert not prod.origine_autorisee("http://portail.local")
    assert prod.origine_autorisee("https://etudesenfrance.diplomatie.gouv.fr")
    assert not prod.origine_autorisee("https://etudesenfrance.diplomatie.gouv.fr.pirate.example")
    assert not prod.origine_autorisee("null") and not prod.origine_autorisee(None)


def test_configuration_mode_serveur_et_url_du_pont() -> None:
    prod = Parametres(environnement=Environnement.PRODUCTION, url_base_donnees="sqlite://", cookie_securise=True)
    assert prod.navigateur_serveur_actif is True
    assert prod.url_serveur_copilote == ""  # production sans URL publique : pont désactivé
    prod_url = Parametres(
        environnement=Environnement.PRODUCTION,
        url_base_donnees="sqlite://",
        url_publique_plateforme="https://app.exemple.dz/",
        cookie_securise=True,
    )
    assert prod_url.url_serveur_copilote == "https://app.exemple.dz"
    local = Parametres(environnement=Environnement.LOCAL, url_base_donnees="sqlite://")
    assert local.navigateur_serveur_actif is False
    assert Parametres(
        environnement=Environnement.LOCAL, url_base_donnees="sqlite://", navigateur_serveur=True
    ).navigateur_serveur_actif


# ---------------------------------------------------------------------------
# Vue opérateur : rôles, CSRF, abonnement, validation stricte (sans navigateur)
# ---------------------------------------------------------------------------

CORPS_VALIDE = {"type": "touche", "touche": "Tab"}


def test_vue_operateur_roles_agent_csrf_et_aucune_session(
    application: FastAPI, deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest]
) -> None:
    a, _ = deux_bureaux
    admin, _ = connecter_client(application, a.admin.email)
    employe, _ = connecter_client(application, a.employe.email)
    lecteur, _ = connecter_client(application, a.lecteur.email)

    for client in (admin, employe):  # humains ADMINISTRATEUR / EMPLOYE
        capture = client.get("/api/v1/navigateur/capture")
        assert capture.status_code == 204 and capture.headers["cache-control"] == "no-store"
        etat = client.get("/api/v1/navigateur/etat")
        assert etat.status_code == 200 and etat.json()["session_active"] is False
        assert client.post("/api/v1/navigateur/controle", json=CORPS_VALIDE).status_code == 404
        assert client.post("/api/v1/navigateur/fermer").json() == {"ferme": False}

    # LECTURE_SEULE refusé partout
    assert lecteur.get("/api/v1/navigateur/capture").status_code == 403
    assert lecteur.get("/api/v1/navigateur/etat").status_code == 403
    assert lecteur.post("/api/v1/navigateur/controle", json=CORPS_VALIDE).status_code == 403
    assert lecteur.post("/api/v1/navigateur/fermer").status_code == 403

    # Jeton d'agent local : refusé (ces routes n'acceptent que la session d'un humain)
    agent = TestClient(application)
    en_tetes = {EN_TETE_JETON_AGENT: "jeton-agent-fictif"}
    assert agent.get("/api/v1/navigateur/capture", headers=en_tetes).status_code == 401
    assert agent.post("/api/v1/navigateur/controle", json=CORPS_VALIDE, headers=en_tetes).status_code == 401
    assert agent.post("/api/v1/navigateur/fermer", headers=en_tetes).status_code == 401
    assert TestClient(application).get("/api/v1/navigateur/etat").status_code == 401

    # CSRF obligatoire sur les POST
    for chemin, corps in (("controle", CORPS_VALIDE), ("fermer", None)):
        rep = admin.post(f"/api/v1/navigateur/{chemin}", json=corps, headers={EN_TETE_CSRF: "faux"})
        assert rep.status_code == 403, chemin


def test_vue_operateur_bloquee_en_lecture_seule_abonnement(
    application: FastAPI,
    parametres_test: Parametres,
    fabrique_sessions: sessionmaker[Session],
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    a, _ = deux_bureaux
    parametres_test.blocage_abonnement_expire = True
    admin, _ = connecter_client(application, a.admin.email)
    _regler_abonnement(fabrique_sessions, a.bureau.id, statut="canceled")

    assert admin.post("/api/v1/navigateur/controle", json=CORPS_VALIDE).status_code == 402
    assert admin.post("/api/v1/navigateur/fermer").status_code == 402
    assert admin.get("/api/v1/navigateur/capture").status_code == 204  # la consultation reste possible


@pytest.mark.parametrize(
    "corps",
    [
        {"type": "clic", "x": 1280, "y": 10},  # hors viewport (largeur 1280)
        {"type": "clic", "x": 10, "y": 900},  # hors viewport (hauteur 900)
        {"type": "clic", "x": -1, "y": 10},
        {"type": "clic", "x": 10},  # y manquant
        {"type": "clic", "x": "dix", "y": 10},
        {"type": "texte", "texte": "a" * 501},  # trop long
        {"type": "texte", "texte": ""},
        {"type": "texte"},
        {"type": "texte", "texte": "ligne1\nligne2"},  # caractère de contrôle (passer par « touche »)
        {"type": "touche", "touche": "F12"},  # hors liste blanche
        {"type": "touche", "touche": "Control+c"},
        {"type": "touche"},
        {"type": "defilement", "delta_y": 2001},
        {"type": "defilement", "delta_y": -2001},
        {"type": "defilement"},
        {"type": "deplacer", "x": 1, "y": 1},  # type inconnu
        {"type": "touche", "touche": "Tab", "role": "administrateur"},  # champ inconnu
    ],
)
def test_controle_validation_stricte(
    application: FastAPI, deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest], corps: dict[str, Any]
) -> None:
    admin, _ = connecter_client(application, deux_bureaux[0].admin.email)
    rep = admin.post("/api/v1/navigateur/controle", json=corps)
    assert rep.status_code == 422, rep.text
    assert "texte" not in rep.text or "a" * 50 not in rep.text  # la valeur soumise n'est jamais renvoyée


# ---------------------------------------------------------------------------
# Navigateur réel (Chromium headless) : isolation, vue opérateur, pont, Règle 6
# ---------------------------------------------------------------------------


def test_isolation_entre_deux_bureaux_et_fermeture_apres_inactivite(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
    deux_clients: tuple[TestClient, TestClient],
) -> None:
    a, b = deux_bureaux
    client_a, client_b = deux_clients
    horloge = FausseHorloge()
    registre = RegistreSessionsNavigateur(horloge=horloge, intervalle_surveillance_s=None)
    application.state.registre_navigateur = registre

    _ouvrir_demo(client_a)
    assert registre.nombre_sessions() == 1
    # B n'a rien : il ne voit pas le navigateur de A et n'en déclenche pas la création
    assert client_b.get("/api/v1/navigateur/capture").status_code == 204
    assert client_b.get("/api/v1/navigateur/etat").json()["session_active"] is False
    assert client_b.post("/api/v1/navigateur/controle", json=CORPS_VALIDE).status_code == 404
    assert client_b.post("/api/v1/navigateur/fermer").json() == {"ferme": False}
    assert registre.nombre_sessions() == 1

    _ouvrir_demo(client_b, "http://portail.local/demo/ircc")
    sa, sb = _session_du_bureau(application, a), _session_du_bureau(application, b)
    assert sa is not sb and sa.gestionnaire is not sb.gestionnaire
    assert sa.gestionnaire._page is not sb.gestionnaire._page
    assert sa.gestionnaire.jeton_bridge_local != sb.gestionnaire.jeton_bridge_local
    assert sa.dossier_profil != sb.dossier_profil
    assert sa.dossier_profil.is_dir() and sb.dossier_profil.is_dir()  # profils Chromium distincts
    assert str(a.bureau.id) in str(sa.dossier_profil) and str(b.bureau.id) in str(sb.dossier_profil)
    assert "/demo/campus-france" in client_a.get("/api/v1/navigateur/etat").json()["url_courante"]
    assert "/demo/ircc" in client_b.get("/api/v1/navigateur/etat").json()["url_courante"]

    # Fermer chez A ne touche pas B
    assert client_a.post("/api/v1/navigateur/fermer").json() == {"ferme": True}
    assert registre.existante(a.bureau.id) is None and registre.existante(b.bureau.id) is sb
    assert sa.gestionnaire._page is None
    assert not sb.gestionnaire._page.is_closed()

    # Inactivité : B est fermé automatiquement après 15 minutes
    horloge.avancer(16 * 60)
    assert registre.purger_inactives() == [b.bureau.id]
    assert sb.gestionnaire._page is None and registre.nombre_sessions() == 0
    assert client_b.get("/api/v1/navigateur/capture").status_code == 204


def test_vue_operateur_capture_controle_humain_et_audit_sans_texte_saisi(
    application: FastAPI,
    parametres_test: Parametres,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    parametres_test.navigateur_serveur = True  # mode serveur : headless forcé, pas de CDP, garde R6 navigateur
    a, _ = deux_bureaux
    admin, _ = connecter_client(application, a.admin.email)
    employe, _ = connecter_client(application, a.employe.email)

    # `ouvrir_fenetre_visible=True` demandé : le mode serveur impose tout de même le headless
    rep = admin.post(
        "/api/v1/portails/action-dom-directe",
        json={"type_operation": "naviguer", "url_destination": URL_DEMO + "?captcha=0", "ouvrir_fenetre_visible": True},
    )
    assert rep.status_code == 200 and rep.json()["succes"] is True, rep.text
    session = _session_du_bureau(application, a)
    gest = session.gestionnaire
    assert session.mode_serveur and gest._mode_serveur
    assert gest._mode_headless_actif is True
    assert gest._navigateur_cdp is None  # jamais de rattachement CDP 9222 en mode serveur

    # Capture : JPEG valide 1280x900, jamais mis en cache
    capture = employe.get("/api/v1/navigateur/capture")
    assert capture.status_code == 200
    assert capture.headers["content-type"] == "image/jpeg"
    assert capture.headers["cache-control"] == "no-store"
    assert _dimensions_jpeg(capture.content) == (1280, 900)

    # État : URL SANS paramètres
    etat = admin.get("/api/v1/navigateur/etat").json()
    assert etat["session_active"] is True and etat["navigateur_ouvert"] is True
    assert etat["url_courante"] == URL_DEMO and "?" not in etat["url_courante"]
    assert etat["mode_serveur"] is True and etat["controle_securite_detecte"] is False

    # Page de test : champ de saisie, CAPTCHA visible (R2), lien piège vers un domaine non officiel
    _dans_page(session, lambda p: p.set_content(HTML_PAGE_CONTROLE))
    assert admin.get("/api/v1/navigateur/etat").json()["controle_securite_detecte"] is True

    # Contrôle humain : clic (focus), saisie, touche, défilement
    assert admin.post("/api/v1/navigateur/controle", json={"type": "clic", "x": 150, "y": 120}).status_code == 200
    rep_texte = admin.post("/api/v1/navigateur/controle", json={"type": "texte", "texte": TEXTE_SECRET})
    assert rep_texte.status_code == 200 and rep_texte.json() == {"succes": True, "type": "texte"}
    assert TEXTE_SECRET not in rep_texte.text
    assert _dans_page(session, lambda p: p.input_value("#champ")) == TEXTE_SECRET
    assert employe.post("/api/v1/navigateur/controle", json={"type": "touche", "touche": "Backspace"}).status_code == 200
    assert _dans_page(session, lambda p: p.input_value("#champ")) == TEXTE_SECRET[:-1]
    assert admin.post("/api/v1/navigateur/controle", json={"type": "defilement", "delta_y": 600}).status_code == 200
    _dans_page(session, lambda p: p.wait_for_function("window.scrollY > 0", timeout=5000))

    # Mode serveur : un clic sur un lien vers un domaine non officiel est bloqué dans le navigateur (R6)
    assert admin.post("/api/v1/navigateur/controle", json={"type": "defilement", "delta_y": -2000}).status_code == 200
    _dans_page(session, lambda p: p.wait_for_function("window.scrollY === 0", timeout=5000))
    assert admin.post("/api/v1/navigateur/controle", json={"type": "clic", "x": 150, "y": 320}).status_code == 200
    _dans_page(session, lambda p: p.wait_for_timeout(800))
    url_apres = _dans_page(session, lambda p: p.url)
    assert "pirate" not in url_apres and "/demo/campus-france" in url_apres
    assert gest.nb_navigations_bloquees >= 1  # c'est bien la garde R6 qui a bloqué (pas une erreur réseau)

    # Audit R5 : compte + type d'action, JAMAIS le texte saisi ni d'URL
    rep_audit = admin.get("/api/v1/audit", params={"action": "navigateur.controle_humain", "taille": 50})
    assert rep_audit.status_code == 200, rep_audit.text
    texte_audit = rep_audit.text
    assert TEXTE_SECRET not in texte_audit and TEXTE_SECRET[:8] not in texte_audit
    for interdit in ("portail.local", "http", "pirate", "captcha"):
        assert interdit not in texte_audit
    assert '"type_action"' in texte_audit and "texte" in texte_audit and "touche" in texte_audit
    assert str(a.admin.id) in texte_audit and str(a.employe.id) in texte_audit
    # Rien non plus dans la liste complète du journal (action-dom-directe, etc.)
    assert TEXTE_SECRET not in admin.get("/api/v1/audit", params={"taille": 100}).text

    # Fermeture + effacement du profil
    assert session.dossier_profil.is_dir()
    assert admin.post("/api/v1/navigateur/fermer", params={"effacer_profil": "true"}).json() == {"ferme": True}
    assert not session.dossier_profil.exists()
    assert admin.get("/api/v1/navigateur/capture").status_code == 204
    assert admin.post("/api/v1/navigateur/controle", json=CORPS_VALIDE).status_code == 404


def test_pont_refuse_le_simple_cookie_et_exige_le_jeton_de_la_session(
    application: FastAPI, deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest]
) -> None:
    a, b = deux_bureaux
    admin_a, _ = connecter_client(application, a.admin.email)
    admin_b, _ = connecter_client(application, b.admin.email)
    _ouvrir_demo(admin_a)
    _ouvrir_demo(admin_b)
    sa, sb = _session_du_bureau(application, a), _session_du_bureau(application, b)
    sa.gestionnaire._derniere_cible = "demo_campus_france"
    sb.gestionnaire._derniere_cible = "demo_campus_france"
    instruction = {"instruction_libre": "descends en bas de la page ZEBRE-8841", "url_courante": URL_DEMO}
    chemin = "/api/v1/portails/copilote-bridge"
    origine_officielle = "https://etudesenfrance.diplomatie.gouv.fr"

    # 1. Faille corrigée : un cookie de session valide SANS jeton ne suffit plus
    assert admin_a.post(chemin, json=instruction).status_code == 401
    assert admin_a.post(chemin, json=instruction, headers={"X-Copilote-Bridge-Token": ""}).status_code == 401
    assert admin_a.post(chemin, json=instruction, headers={"X-Copilote-Bridge-Token": "faux"}).status_code == 401
    # Cookie bidon : idem
    bidon = TestClient(application)
    bidon.cookies.set("be_session", "cookie-quelconque")
    assert bidon.post(chemin, json=instruction).status_code == 401

    # 2. Le jeton d'un autre bureau n'ouvre que SA session (jamais celle de A)
    anonyme = TestClient(application)
    rep_b = anonyme.post(
        chemin, json=instruction, headers={"X-Copilote-Bridge-Token": sb.jeton_bridge, "Origin": origine_officielle}
    )
    assert rep_b.status_code == 200, rep_b.text
    assert "/demo/campus-france" in rep_b.json()["url_courante"]
    assert sa.gestionnaire._historique_actions == [] or all(
        "ZEBRE" not in str(h) for h in sa.gestionnaire._historique_actions
    )
    assert any("descends" in str(h) for h in sb.gestionnaire._historique_actions)

    # 3. CORS : jamais « * » ni cookies ; origine réfléchie seulement si officielle
    assert rep_b.headers["access-control-allow-origin"] == origine_officielle
    assert rep_b.headers["access-control-allow-origin"] != "*"
    assert "access-control-allow-credentials" not in rep_b.headers
    assert "Origin" in rep_b.headers["vary"]
    rep_pirate = anonyme.post(
        chemin,
        json=instruction,
        headers={"X-Copilote-Bridge-Token": sa.jeton_bridge, "Origin": "https://pirate.example.org"},
    )
    assert rep_pirate.status_code == 403 and "access-control-allow-origin" not in rep_pirate.headers
    preflight_ok = anonyme.options(chemin, headers={"Origin": origine_officielle, "Access-Control-Request-Method": "POST"})
    assert preflight_ok.status_code == 204
    assert preflight_ok.headers["access-control-allow-origin"] == origine_officielle
    preflight_pirate = anonyme.options(chemin, headers={"Origin": "https://pirate.example.org"})
    assert preflight_pirate.status_code == 403 and "access-control-allow-origin" not in preflight_pirate.headers
    assert anonyme.options(chemin).status_code == 403  # sans origine : pas de CORS

    # 4. R5 : audit du pont sans le texte de l'instruction
    texte_audit = admin_b.get("/api/v1/audit", params={"action": "navigateur.pont_copilote", "taille": 20}).text
    assert "navigateur.pont_copilote" in texte_audit and "ZEBRE" not in texte_audit and "descends" not in texte_audit

    # 5. Session fermée => jeton mort
    assert admin_b.post("/api/v1/navigateur/fermer").json() == {"ferme": True}
    assert anonyme.post(chemin, json=instruction, headers={"X-Copilote-Bridge-Token": sb.jeton_bridge}).status_code == 401


def test_script_injecte_sans_adresse_codee_en_dur() -> None:
    from app.agent_local.pilote_navigateur import SCRIPT_COPILOTE_COWORK_INJECTE

    assert "127.0.0.1:8000" not in SCRIPT_COPILOTE_COWORK_INJECTE
    assert 'credentials: "omit"' in SCRIPT_COPILOTE_COWORK_INJECTE


def test_url_du_serveur_injectee_dans_la_page_vient_des_parametres(
    application: FastAPI,
    parametres_test: Parametres,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    parametres_test.url_publique_plateforme = "https://app.exemple-bureau.dz/"
    a, _ = deux_bureaux
    admin, _ = connecter_client(application, a.admin.email)
    _ouvrir_demo(admin)
    session = _session_du_bureau(application, a)
    valeurs = _dans_page(
        session, lambda p: p.evaluate("() => [window.__COWORK_URL_SERVEUR__, window.__COWORK_JETON_BRIDGE__]")
    )
    assert valeurs[0] == "https://app.exemple-bureau.dz"
    assert valeurs[1] == session.jeton_bridge


def test_r6_navigation_refusee_hors_domaines_officiels_en_ligne(
    application: FastAPI, parametres_test: Parametres, deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest]
) -> None:
    a, _ = deux_bureaux
    admin, _ = connecter_client(application, a.admin.email)
    _ouvrir_demo(admin)
    session = _session_du_bureau(application, a)

    refusees = [
        "https://pirate.example.org/login",
        "http://etudesenfrance.diplomatie.gouv.fr/",  # lien http://
        "https://etudesenfrance.diplomatie.gouv.fr.pirate.example/",  # domaine lookalike
        "http://portail.local.pirate.example/demo/campus-france",
        "javascript:alert(1)",
    ]
    for url in refusees:
        rep = admin.post(
            "/api/v1/portails/action-dom-directe",
            json={"type_operation": "naviguer", "url_destination": url},
        )
        assert rep.status_code == 200, rep.text
        corps = rep.json()
        assert corps["succes"] is False, url
        assert "Règle 6" in corps["message"], url
        assert "/demo/campus-france" in corps["url_courante"], url  # le navigateur n'a pas bougé

    # Instruction libre contenant une URL non officielle : refusée sans naviguer
    cid = _creer_candidat(admin)
    for url in ("https://pirate.example.org/x", "http://etudesenfrance.diplomatie.gouv.fr/"):
        rep = admin.post(
            "/api/v1/portails/piloter-navigateur",
            json={
                "candidat_id": cid,
                "code_demarche": "campus_france",
                "cible": "demo_campus_france",
                "action": "instruction_libre",
                "instruction_libre": f"va sur {url}",
                "synchroniser_tache": False,
                "prendre_capture": False,
            },
        )
        assert rep.status_code == 200, rep.text
        assert rep.json()["succes"] is False
        assert "Règle 6" in rep.json()["reponse_agent"]
    assert "/demo/campus-france" in _dans_page(session, lambda p: p.url)

    # Un domaine officiel en HTTPS et la démo restent autorisés (la politique, pas le réseau, est testée ici)
    assert (
        politique_depuis_parametres(parametres_test).motif_refus(
            "https://www.algerie.campusfrance.org/horaires-d-attention-au-public"
        )
        is None
    )
    rep_ok = admin.post(
        "/api/v1/portails/action-dom-directe",
        json={"type_operation": "naviguer", "url_destination": "http://portail.local/demo/ircc"},
    )
    assert rep_ok.json()["succes"] is True and "/demo/ircc" in rep_ok.json()["url_courante"]

    # Audit : aucune URL ni paramètre
    texte_audit = admin.get("/api/v1/audit", params={"taille": 100}).text
    assert "pirate" not in texte_audit


def test_aucune_route_n_utilise_le_pilote_global_partage() -> None:
    racine = Path(__file__).resolve().parents[1] / "app" / "api"
    for fichier in racine.rglob("*.py"):
        assert "pilote_navigateur_global" not in fichier.read_text(encoding="utf-8"), fichier.name
