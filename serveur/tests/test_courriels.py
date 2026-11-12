"""Tests des courriels et des deux parcours : vérification d'adresse et mot de passe oublié.

Aucune donnée réelle : adresses et noms fictifs. Le transport « mémoire » ne fait aucun envoi réseau.
"""

from __future__ import annotations

import hashlib
import logging
import re
import smtplib
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.core.config import Environnement, Parametres
from app.core.erreurs import AccesRefuse
from app.db.base import maintenant_utc
from app.db.tenant import sans_filtre_tenant
from app.main import creer_application
from app.modeles.jeton_courriel import JetonCourriel, ObjetJetonCourriel
from app.modeles.journal_audit import EntreeAudit
from app.modeles.session_utilisateur import SessionUtilisateur
from app.modeles.utilisateur import Utilisateur
from app.services import courriels, jetons_courriel
from tests.conftest import (
    MOT_DE_PASSE_FORT,
    MOT_DE_PASSE_NOUVEAU,
    charger_ou_creer_cle_maitresse,
    connecter_client,
)

EMAIL = "admin.alpha@bureau-fictif.dz"
INSCRIPTION = "/api/v1/inscription"
OUBLI = "/api/v1/auth/mot-de-passe-oublie"
REINIT = "/api/v1/auth/reinitialisation-mot-de-passe"
VERIF = "/api/v1/auth/verification-adresse"
MOTIF_JETON = re.compile(r"#jeton=([A-Za-z0-9_\-]+)")


class CollecteurJournaux(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@pytest.fixture(autouse=True)
def boite_vide():
    courriels.boite_memoire.vider()
    yield
    courriels.boite_memoire.vider()


@pytest.fixture()
def journaux(application):
    """Collecte tout ce que l'application journalise (le logger `app` ne se propage pas à caplog)."""
    collecteur = CollecteurJournaux()
    racine = logging.getLogger("app")
    racine.addHandler(collecteur)
    try:
        yield collecteur
    finally:
        racine.removeHandler(collecteur)


def _jeton_du_dernier_courriel(type_courriel: str) -> str:
    courriel = [c for c in courriels.boite_memoire.lister() if c.type == type_courriel][-1]
    trouve = MOTIF_JETON.search(courriel.texte)
    assert trouve, "le courriel doit contenir un lien avec jeton"
    # Le lien est identique dans la version HTML.
    assert trouve.group(1) in courriel.html
    return trouve.group(1)


def _tous_les_jetons(fabrique) -> list[JetonCourriel]:
    with fabrique() as db, sans_filtre_tenant(db):
        return list(db.scalars(select(JetonCourriel)))


def _application(application, parametres_test, **champs):
    cfg = parametres_test.model_copy(update=champs)
    app = creer_application(cfg)
    app.state.cle_maitresse = charger_ou_creer_cle_maitresse(cfg)
    app.state.moteur = application.state.moteur
    app.state.fabrique_sessions = application.state.fabrique_sessions
    return app


def _inscrire(client: TestClient, email: str = "directrice@horizon-fictif.dz") -> None:
    rep = client.post(
        INSCRIPTION,
        json={
            "nom_bureau": "Agence Horizon Fictive",
            "email_admin": email,
            "nom_admin": "Samira Fictive",
            "mot_de_passe": MOT_DE_PASSE_FORT,
            "accepte_cgu": True,
        },
    )
    assert rep.status_code == 201, rep.text


# --- Vérification d'adresse ---------------------------------------------------------------

def test_inscription_envoie_un_courriel_de_verification_et_confirme_l_adresse(
    application, fabrique_sessions
):
    client = TestClient(application)
    _inscrire(client)

    envoyes = courriels.boite_memoire.lister()
    assert [c.type for c in envoyes] == ["verification_adresse"]
    assert envoyes[0].destinataire == "directrice@horizon-fictif.dz"
    assert "Confirmer mon adresse" in envoyes[0].html

    # Connexion permise avant confirmation, avec l'indicateur pour le bandeau.
    c, _ = connecter_client(application, "directrice@horizon-fictif.dz")
    assert c.get("/api/v1/auth/moi").json()["utilisateur"]["email_verifie"] is False

    jeton = _jeton_du_dernier_courriel("verification_adresse")
    assert client.post(VERIF, json={"jeton": jeton}).status_code == 204
    assert c.get("/api/v1/auth/moi").json()["utilisateur"]["email_verifie"] is True

    # Usage unique.
    rejeu = client.post(VERIF, json={"jeton": jeton})
    assert rejeu.status_code == 422


def test_jeton_de_verification_expire_est_refuse(application, fabrique_sessions):
    client = TestClient(application)
    _inscrire(client)
    jeton = _jeton_du_dernier_courriel("verification_adresse")
    with fabrique_sessions() as db, sans_filtre_tenant(db):
        db.execute(update(JetonCourriel).values(expire_le=maintenant_utc() - timedelta(seconds=1)))
        db.commit()

    assert client.post(VERIF, json={"jeton": jeton}).status_code == 422
    with fabrique_sessions() as db, sans_filtre_tenant(db):
        assert all(not u.email_verifie for u in db.scalars(select(Utilisateur)))


def test_jeton_verification_expire_apres_48_heures_par_defaut(application, fabrique_sessions):
    _inscrire(TestClient(application))
    (jeton,) = _tous_les_jetons(fabrique_sessions)
    duree = jeton.expire_le - jeton.cree_le
    assert timedelta(hours=47, minutes=59) < duree <= timedelta(hours=48, seconds=1)


def test_jetons_stockes_haches_jamais_en_clair(application, fabrique_sessions):
    client = TestClient(application)
    _inscrire(client)
    jeton = _jeton_du_dernier_courriel("verification_adresse")

    (ligne,) = _tous_les_jetons(fabrique_sessions)
    assert ligne.empreinte == hashlib.sha256(jeton.encode("utf-8")).hexdigest()
    assert jeton not in repr(ligne)
    # Le jeton clair n'apparaît dans aucune colonne d'aucune table.
    with fabrique_sessions() as db:
        brut = db.connection()
        tables = brut.exec_driver_sql("select name from sqlite_master where type='table'").fetchall()
        for (nom,) in tables:
            for rangee in brut.exec_driver_sql(f'select * from "{nom}"').fetchall():  # noqa: S608
                assert jeton not in " ".join(str(v) for v in rangee)


def test_renvoi_de_verification_exige_une_session_et_limite_le_debit(application):
    client = TestClient(application)
    _inscrire(client)
    assert client.post("/api/v1/auth/verification-adresse/renvoyer").status_code in (401, 403)

    c, _ = connecter_client(application, "directrice@horizon-fictif.dz")
    courriels.boite_memoire.vider()
    assert c.post("/api/v1/auth/verification-adresse/renvoyer").status_code == 202
    assert len(courriels.boite_memoire.lister()) == 1
    # L'inscription a déjà compté pour 1 envoi, ce renvoi pour 2, le suivant pour 3, puis limite.
    assert c.post("/api/v1/auth/verification-adresse/renvoyer").status_code == 202
    assert c.post("/api/v1/auth/verification-adresse/renvoyer").status_code == 429


def test_le_renvoi_invalide_le_jeton_precedent(application):
    client = TestClient(application)
    _inscrire(client)
    premier = _jeton_du_dernier_courriel("verification_adresse")
    c, _ = connecter_client(application, "directrice@horizon-fictif.dz")
    assert c.post("/api/v1/auth/verification-adresse/renvoyer").status_code == 202
    second = _jeton_du_dernier_courriel("verification_adresse")

    assert client.post(VERIF, json={"jeton": premier}).status_code == 422
    assert client.post(VERIF, json={"jeton": second}).status_code == 204


def test_envoi_sensible_refuse_tant_que_l_adresse_n_est_pas_verifiee(parametres_test):
    exigee = parametres_test.model_copy(update={"exiger_adresse_verifiee": True})
    non_exigee = parametres_test.model_copy(update={"exiger_adresse_verifiee": False})
    utilisateur = Utilisateur(email=EMAIL, nom_affiche="X", empreinte_mot_de_passe="x", role=None)

    jetons_courriel.exiger_adresse_verifiee(utilisateur, non_exigee)  # permis
    with pytest.raises(AccesRefuse):
        jetons_courriel.exiger_adresse_verifiee(utilisateur, exigee)
    utilisateur.email_verifie_le = maintenant_utc()
    jetons_courriel.exiger_adresse_verifiee(utilisateur, exigee)

    # Par défaut : exigé uniquement en production.
    assert parametres_test.adresse_verifiee_exigee is False
    assert parametres_test.model_copy(
        update={"environnement": Environnement.PRODUCTION}
    ).adresse_verifiee_exigee is True


# --- Mot de passe oublié ------------------------------------------------------------------

def test_reponse_identique_que_le_compte_existe_ou_non(application, deux_bureaux):
    client = TestClient(application)
    connu = client.post(OUBLI, json={"email": EMAIL})
    assert len(courriels.boite_memoire.lister()) == 1
    courriels.boite_memoire.vider()
    inconnu = client.post(OUBLI, json={"email": "personne@inconnu-fictif.dz"})

    assert connu.status_code == inconnu.status_code == 202
    assert connu.json() == inconnu.json()
    assert courriels.boite_memoire.lister() == []  # rien n'est envoyé à une adresse inconnue


def test_compte_desactive_ne_recoit_rien_et_la_reponse_est_identique(
    application, deux_bureaux, fabrique_sessions
):
    with fabrique_sessions() as db, sans_filtre_tenant(db):
        db.execute(update(Utilisateur).where(Utilisateur.email == EMAIL).values(actif=False))
        db.commit()
    rep = TestClient(application).post(OUBLI, json={"email": EMAIL})
    assert rep.status_code == 202
    assert courriels.boite_memoire.lister() == []


def test_limite_de_debit_par_ip_et_par_compte(application, parametres_test, deux_bureaux):
    # Par compte : au-delà de 3 demandes par heure, plus d'envoi, même réponse (pas d'indice).
    client = TestClient(application)
    reponses = [client.post(OUBLI, json={"email": EMAIL}) for _ in range(5)]
    assert {r.status_code for r in reponses} == {202}
    assert len({r.text for r in reponses}) == 1
    assert len(courriels.boite_memoire.lister()) == 3

    # Par IP : 429 dès que la limite est atteinte, que l'adresse existe ou non.
    app = _application(
        application, parametres_test,
        reinitialisation_limite_active_en_test=True, reinitialisation_max_par_heure_par_ip=2,
    )
    c = TestClient(app)
    assert c.post(OUBLI, json={"email": "a@inconnu-fictif.dz"}).status_code == 202
    assert c.post(OUBLI, json={"email": "b@inconnu-fictif.dz"}).status_code == 202
    assert c.post(OUBLI, json={"email": "c@inconnu-fictif.dz"}).status_code == 429


def test_reinitialisation_complete(application, deux_bureaux, fabrique_sessions):
    ancien_client, _ = connecter_client(application, EMAIL)
    assert ancien_client.get("/api/v1/auth/moi").status_code == 200

    client = TestClient(application)
    client.post(OUBLI, json={"email": EMAIL})
    jeton = _jeton_du_dernier_courriel("mot_de_passe_oublie")

    # Politique de mot de passe appliquée, le jeton reste utilisable après un refus.
    faible = client.post(REINIT, json={"jeton": jeton, "nouveau_mot_de_passe": "court"})
    assert faible.status_code == 422
    bon = client.post(REINIT, json={"jeton": jeton, "nouveau_mot_de_passe": MOT_DE_PASSE_NOUVEAU})
    assert bon.status_code == 204

    # La session ouverte avant la réinitialisation est révoquée.
    assert ancien_client.get("/api/v1/auth/moi").status_code == 401
    with fabrique_sessions() as db, sans_filtre_tenant(db):
        assert all(s.revoquee_le is not None for s in db.scalars(select(SessionUtilisateur)))

    # Nouveau mot de passe seul valide ; l'ancien est refusé.
    ancien = client.post("/api/v1/auth/connexion", json={"email": EMAIL, "mot_de_passe": MOT_DE_PASSE_FORT})
    assert ancien.status_code == 401
    nouveau = client.post(
        "/api/v1/auth/connexion", json={"email": EMAIL, "mot_de_passe": MOT_DE_PASSE_NOUVEAU}
    )
    assert nouveau.status_code == 200
    assert nouveau.json()["utilisateur"]["email_verifie"] is True  # le lien prouve l'accès à la boîte

    # Usage unique.
    rejeu = client.post(REINIT, json={"jeton": jeton, "nouveau_mot_de_passe": "Autre!2026#Solide77"})
    assert rejeu.status_code == 422


def test_jeton_de_reinitialisation_expire_apres_une_heure(application, deux_bureaux, fabrique_sessions):
    client = TestClient(application)
    client.post(OUBLI, json={"email": EMAIL})
    jeton = _jeton_du_dernier_courriel("mot_de_passe_oublie")
    (ligne,) = _tous_les_jetons(fabrique_sessions)
    assert timedelta(minutes=59) < ligne.expire_le - ligne.cree_le <= timedelta(minutes=60, seconds=1)

    with fabrique_sessions() as db, sans_filtre_tenant(db):
        db.execute(update(JetonCourriel).values(expire_le=maintenant_utc() - timedelta(seconds=1)))
        db.commit()
    rep = client.post(REINIT, json={"jeton": jeton, "nouveau_mot_de_passe": MOT_DE_PASSE_NOUVEAU})
    assert rep.status_code == 422
    # Le mot de passe n'a pas changé.
    assert client.post(
        "/api/v1/auth/connexion", json={"email": EMAIL, "mot_de_passe": MOT_DE_PASSE_FORT}
    ).status_code == 200


def test_nouvelle_demande_invalide_la_precedente_et_les_jetons_ne_sont_pas_interchangeables(
    application, deux_bureaux
):
    client = TestClient(application)
    client.post(OUBLI, json={"email": EMAIL})
    premier = _jeton_du_dernier_courriel("mot_de_passe_oublie")
    client.post(OUBLI, json={"email": EMAIL})
    second = _jeton_du_dernier_courriel("mot_de_passe_oublie")

    corps = {"nouveau_mot_de_passe": MOT_DE_PASSE_NOUVEAU}
    assert client.post(REINIT, json={"jeton": premier, **corps}).status_code == 422
    # Un jeton de réinitialisation ne confirme pas une adresse (objet distinct).
    assert client.post(VERIF, json={"jeton": second}).status_code == 422
    assert client.post(REINIT, json={"jeton": second, **corps}).status_code == 204


def test_jeton_inconnu_ou_malforme_donne_le_meme_refus(application, deux_bureaux):
    client = TestClient(application)
    inconnu = client.post(REINIT, json={"jeton": "x" * 43, "nouveau_mot_de_passe": MOT_DE_PASSE_NOUVEAU})
    assert inconnu.status_code == 422
    assert inconnu.json()["detail"] == jetons_courriel.MESSAGE_LIEN_INVALIDE
    assert client.post(REINIT, json={"jeton": "court", "nouveau_mot_de_passe": MOT_DE_PASSE_NOUVEAU}).status_code == 422


# --- Aucune donnée personnelle ni jeton dans les journaux et l'audit ----------------------

def test_aucun_jeton_ni_courriel_dans_les_journaux_ni_l_audit(
    application, fabrique_sessions, journaux
):
    client = TestClient(application)
    adresse = "directrice@horizon-fictif.dz"
    _inscrire(client, adresse)
    jeton_verif = _jeton_du_dernier_courriel("verification_adresse")
    client.post(VERIF, json={"jeton": jeton_verif})
    client.post(OUBLI, json={"email": adresse})
    client.post(OUBLI, json={"email": "inconnu@inconnu-fictif.dz"})
    jeton_mdp = _jeton_du_dernier_courriel("mot_de_passe_oublie")
    client.post(REINIT, json={"jeton": jeton_mdp, "nouveau_mot_de_passe": "court"})
    client.post(REINIT, json={"jeton": jeton_mdp, "nouveau_mot_de_passe": MOT_DE_PASSE_NOUVEAU})
    client.post(REINIT, json={"jeton": jeton_mdp, "nouveau_mot_de_passe": MOT_DE_PASSE_NOUVEAU})

    interdits = [jeton_verif, jeton_mdp, adresse, "inconnu@inconnu-fictif.dz", "Samira", "#jeton=",
                 "nouveau-mot-de-passe", MOT_DE_PASSE_NOUVEAU]
    assert journaux.messages, "des événements doivent être journalisés"
    for message in journaux.messages:
        for interdit in interdits:
            assert interdit not in message

    with fabrique_sessions() as db, sans_filtre_tenant(db):
        entrees = list(db.scalars(select(EntreeAudit)))
    actions = {e.action for e in entrees}
    assert {
        "auth.verification_adresse_envoyee", "auth.adresse_verifiee",
        "auth.reinitialisation_demandee", "auth.reinitialisation_mot_de_passe",
    } <= actions
    texte_audit = " ".join(f"{e.action} {e.details} {e.ressource_type}" for e in entrees)
    for interdit in interdits:
        assert interdit not in texte_audit
    assert "@" not in texte_audit


# --- Transports et gabarits ---------------------------------------------------------------

def test_transport_memoire_hors_production_ou_sans_configuration(parametres_test):
    complet = {"smtp_hote": "smtp.exemple-fictif.dz", "smtp_expediteur": "no-reply@exemple-fictif.dz"}
    assert parametres_test.transport_courriel_effectif == "memoire"
    assert parametres_test.model_copy(update=complet).transport_courriel_effectif == "memoire"
    prod = {"environnement": Environnement.PRODUCTION}
    assert parametres_test.model_copy(update=prod).transport_courriel_effectif == "memoire"
    assert parametres_test.model_copy(update={**prod, **complet}).transport_courriel_effectif == "smtp"
    assert parametres_test.model_copy(
        update={**prod, **complet, "courriel_transport": "memoire"}
    ).transport_courriel_effectif == "memoire"


class FauxSMTP:
    """Remplace smtplib.SMTP : aucune connexion réseau."""

    instances: list["FauxSMTP"] = []
    echec = False

    def __init__(self, hote, port, timeout=None):
        if FauxSMTP.echec:
            raise OSError(f"connexion refusée vers {hote} pour directrice@horizon-fictif.dz")
        self.appels: list[str] = []
        self.message = None
        FauxSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self, context=None):
        self.appels.append("starttls")

    def login(self, utilisateur, mot_de_passe):
        self.appels.append("login")

    def send_message(self, message):
        self.appels.append("send")
        self.message = message


def test_envoi_smtp_starttls_puis_echec_sans_fuite(monkeypatch, parametres_test, journaux):
    monkeypatch.setattr(smtplib, "SMTP", FauxSMTP)
    FauxSMTP.instances.clear()
    FauxSMTP.echec = False
    cfg = parametres_test.model_copy(
        update={
            "environnement": Environnement.PRODUCTION,
            "smtp_hote": "smtp.exemple-fictif.dz",
            "smtp_expediteur": "no-reply@exemple-fictif.dz",
            "smtp_utilisateur": "robot",
            "smtp_mot_de_passe": "secret-smtp-fictif",
        }
    )
    courriel = courriels.gabarit_verification_adresse(
        "directrice@horizon-fictif.dz", "https://plateforme.exemple/verification-adresse#jeton=ABC", 48
    )
    assert courriels.envoyer_courriel(courriel, cfg) is True
    assert FauxSMTP.instances[0].appels == ["starttls", "login", "send"]
    msg = FauxSMTP.instances[0].message
    assert msg["To"] == "directrice@horizon-fictif.dz"
    assert msg.get_body(("plain",)) is not None and msg.get_body(("html",)) is not None
    assert courriels.boite_memoire.lister() == []

    FauxSMTP.echec = True
    assert courriels.envoyer_courriel(courriel, cfg) is False  # ne lève pas
    for message in journaux.messages:
        assert "horizon-fictif" not in message
        assert "ABC" not in message
        assert "secret-smtp-fictif" not in message
    assert any("OSError" in m for m in journaux.messages)


def test_gabarits_en_francais_avec_lien(parametres_test):
    lien = courriels.construire_lien(parametres_test, "/nouveau-mot-de-passe", "JETON123")
    assert lien == "http://127.0.0.1:8000/nouveau-mot-de-passe#jeton=JETON123"
    cfg = parametres_test.model_copy(update={"url_publique_plateforme": "https://app.exemple-fictif.dz/"})
    assert courriels.construire_lien(cfg, "/verification-adresse", "J") == (
        "https://app.exemple-fictif.dz/verification-adresse#jeton=J"
    )
    prod = parametres_test.model_copy(update={"environnement": Environnement.PRODUCTION})
    assert courriels.construire_lien(prod, "/verification-adresse", "J") is None

    c = courriels.gabarit_rappel_echeance("x@exemple-fictif.dz", "Dépôt du dossier", "2026-12-01", 3, lien)
    assert "Rappel d'échéance" in c.sujet and "dans 3 jour(s)" in c.texte and lien in c.html
    assert "Bonjour" in c.texte and "<html lang=\"fr\">" in c.html
    m = courriels.gabarit_mot_de_passe_oublie("x@exemple-fictif.dz", lien, 60)
    assert "60 minutes" in m.texte and "ignorez" in m.texte


def test_pages_publiques_minimales(application):
    client = TestClient(application)
    for chemin, attendu in [
        ("/mot-de-passe-oublie", "Mot de passe oublié"),
        ("/nouveau-mot-de-passe", "nouveau mot de passe"),
        ("/verification-adresse", "Confirmer mon adresse"),
    ]:
        rep = client.get(chemin)
        assert rep.status_code == 200
        assert attendu in rep.text
