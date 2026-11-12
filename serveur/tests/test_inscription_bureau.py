"""Tests de l'inscription en libre-service et des pages publiques."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Parametres
from app.db.tenant import sans_filtre_tenant
from app.main import creer_application
from app.modeles.journal_audit import EntreeAudit
from app.services.abonnements import CATALOGUE_FORFAITS
from tests.conftest import MOT_DE_PASSE_FORT, connecter_client

URL = "/api/v1/inscription"


def _corps(**surcharge):
    corps = {
        "nom_bureau": "Agence Horizon Fictive",
        "email_admin": "directrice@horizon-fictif.dz",
        "nom_admin": "Samira Fictive",
        "mot_de_passe": MOT_DE_PASSE_FORT,
        "accepte_cgu": True,
    }
    corps.update(surcharge)
    return corps


def _application_avec(application, parametres_test, **champs):
    from tests.conftest import charger_ou_creer_cle_maitresse

    cfg = parametres_test.model_copy(update=champs)
    app = creer_application(cfg)
    app.state.cle_maitresse = charger_ou_creer_cle_maitresse(cfg)
    app.state.moteur = application.state.moteur
    app.state.fabrique_sessions = application.state.fabrique_sessions
    return app


def test_inscription_puis_connexion(application):
    client = TestClient(application)
    rep = client.post(URL, json=_corps(forfait="professionnel"))
    assert rep.status_code == 201, rep.text
    data = rep.json()
    assert data["slug"] == "agence-horizon-fictive"
    assert "connect" in data["message"].lower()
    c, _ = connecter_client(application, "directrice@horizon-fictif.dz")
    assert c.get("/api/v1/abonnement").json()["forfait"] == "professionnel"
    abo = c.get("/api/v1/abonnement").json()
    assert abo["statut_stripe"] == "trialing"
    assert abo["cgu_version_acceptee"]


def test_isolation_candidats(application, deux_bureaux):
    TestClient(application).post(URL, json=_corps())
    c, _ = connecter_client(application, "directrice@horizon-fictif.dz")
    rep = c.get("/api/v1/candidats")
    assert rep.status_code == 200
    corps = rep.json()
    liste = corps if isinstance(corps, list) else corps.get("elements", corps.get("items", []))
    assert liste == []


def test_refus_sans_cgu(application):
    rep = TestClient(application).post(URL, json=_corps(accepte_cgu=False))
    assert rep.status_code == 422


def test_mot_de_passe_faible(application):
    rep = TestClient(application).post(URL, json=_corps(mot_de_passe="abc"))
    assert rep.status_code == 422


def test_email_en_double_message_neutre(application):
    client = TestClient(application)
    assert client.post(URL, json=_corps()).status_code == 201
    rep = client.post(URL, json=_corps(nom_bureau="Autre Agence"))
    assert rep.status_code == 409
    assert "directrice@" not in rep.text
    assert "existe" not in rep.json()["detail"].lower()


def test_collision_de_slug(application):
    client = TestClient(application)
    r1 = client.post(URL, json=_corps()).json()
    r2 = client.post(
        URL, json=_corps(email_admin="autre@horizon-fictif.dz")
    ).json()
    assert r1["slug"] == "agence-horizon-fictive"
    assert r2["slug"] == "agence-horizon-fictive-2"


def test_inscriptions_fermees(application, parametres_test):
    app = _application_avec(application, parametres_test, inscriptions_ouvertes=False)
    assert TestClient(app).post(URL, json=_corps()).status_code == 403


def test_champ_piege(application, fabrique_sessions):
    rep = TestClient(application).post(URL, json=_corps(site_web="http://spam.example"))
    assert rep.status_code == 201
    from app.modeles.bureau import Bureau

    with fabrique_sessions() as db:
        with sans_filtre_tenant(db):
            assert db.scalar(select(Bureau.id)) is None


def test_limitation_de_debit(application, parametres_test):
    app = _application_avec(
        application,
        parametres_test,
        inscription_limite_active_en_test=True,
        inscription_max_par_heure_par_ip=2,
    )
    client = TestClient(app)
    codes = [
        client.post(
            URL, json=_corps(email_admin=f"u{i}@horizon-fictif.dz", nom_bureau=f"Agence {i}")
        ).status_code
        for i in range(3)
    ]
    assert codes == [201, 201, 429]


def test_pages_publiques(application):
    client = TestClient(application)
    for chemin in ("/bienvenue", "/inscription"):
        rep = client.get(chemin)
        assert rep.status_code == 200
        assert "text/html" in rep.headers["content-type"]
        for libelle, _prix, _quota in CATALOGUE_FORFAITS.values():
            assert libelle.replace("'", "&#x27;") in rep.text or libelle in rep.text
    assert "Créer mon bureau" in client.get("/bienvenue").text
    assert client.get("/api/v1/inscription/cgu").status_code == 200
    assert len(client.get("/api/v1/inscription/forfaits").json()) == 3


def test_audit_sans_donnee_personnelle(application, fabrique_sessions):
    TestClient(application).post(URL, json=_corps())
    with fabrique_sessions() as db:
        with sans_filtre_tenant(db):
            entrees = list(db.scalars(select(EntreeAudit)))
    assert entrees
    texte = json.dumps(
        [{"a": e.action, "d": e.details} for e in entrees], default=str
    ).lower()
    for interdit in ("horizon", "directrice", "samira", "@"):
        assert interdit not in texte
