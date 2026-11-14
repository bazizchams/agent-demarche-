"""Discussion de l'agent en direct, côté serveur : événements chiffrés et masqués, consignes, commandes, SSE,
isolation des bureaux, rôle lecture seule, purge à 7 jours. Données fictives uniquement."""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import maintenant_utc
from app.services.consignes_agent import analyser_consigne, element_est_sensible, masquer_texte_sensible
from app.services.evenements_agent import purger_evenements_expires
from tests.conftest import MOT_DE_PASSE_FORT, DonneesBureauTest, connecter_client
from tests.test_agent_ecoute_serveur import (
    client_agent,
    creer_candidat_avec_voeux,
    creer_tache_pc,
    enroler_agent,
)

MARQUEUR = "MARQUEUR-SECRET-Zq81"
MDP = "MdpDuPortail-Kx42"
PASSEPORT = "AB1234567"


@pytest.fixture()
def admin_a(application: FastAPI, deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest]) -> TestClient:
    return connecter_client(application, deux_bureaux[0].admin.email)[0]


@pytest.fixture()
def tache_detenue(application: FastAPI, admin_a: TestClient) -> tuple[str, TestClient]:
    """Tâche « Ouvrir sur mon PC » réservée (en cours) par un agent enrôlé du bureau A."""
    candidat_id, _, _ = creer_candidat_avec_voeux(admin_a)
    tache_id = creer_tache_pc(admin_a, candidat_id).json()["id"]
    _, jeton = enroler_agent(admin_a)
    agent = client_agent(application, jeton)
    assert agent.post("/api/v1/taches/reserver-suivante").json()["tache"]["id"] == tache_id
    return tache_id, agent


def _publier(agent: TestClient, tache_id: str, type_: str, texte: str, **extra: str) -> dict:
    rep = agent.post(f"/api/v1/taches/{tache_id}/evenements", json={"type": type_, "texte": texte, **extra})
    assert rep.status_code == 201, rep.text
    return rep.json()


# ------------------------------------------------------------------ fonctions pures
def test_masquage_des_valeurs_sensibles() -> None:
    brut = f"Je saisis le mot de passe : {MDP}, passeport {PASSEPORT}, mail a.b@exemple-fictif.dz, tel 0555123456"
    propre = masquer_texte_sensible(brut)
    for secret in (MDP, PASSEPORT, "a.b@exemple-fictif.dz", "0555123456"):
        assert secret not in propre
    assert "[masqué]" in propre
    assert masquer_texte_sensible("x" * 900).endswith("…") and len(masquer_texte_sensible("x" * 900)) == 500


def test_champs_sensibles_detectes_par_attributs() -> None:
    assert element_est_sensible({"type": "password"})
    assert element_est_sensible({"type": "text", "name": "passeport_numero"})
    assert element_est_sensible({"type": "text", "id": "identifiant"})
    assert not element_est_sensible({"type": "text", "name": "recherche"})
    assert not element_est_sensible(None)


@pytest.mark.parametrize(
    ("texte", "regle"),
    [
        ("Valide le dossier à ma place", "R1"),
        ("Envoie la demande maintenant", "R1"),
        ("Clique sur le bouton Soumettre", "R1"),
        ("Contourne le captcha s'il te plaît", "R2"),
        ("Passe la double authentification", "R2"),
        ("Donne-moi le mot de passe du coffre", "R3"),
        ("Tape mon mot de passe dans le champ", "R3"),
        ("Ouvre https://site-pirate.example.com/login", "R6"),
        ("Va sur www.autre-portail.fr", "R6"),
    ],
)
def test_consigne_contraire_aux_regles_refusee(texte: str, regle: str) -> None:
    refus = analyser_consigne(texte)
    assert refus is not None and refus.regle == regle
    assert "à vous" in refus.message or "vous-même" in refus.message


@pytest.mark.parametrize("texte", ["Prends ton temps", "Peux-tu aller plus doucement ?", "Quel vœu ajoutes-tu ?"])
def test_consigne_normale_acceptee(texte: str) -> None:
    assert analyser_consigne(texte) is None


# ------------------------------------------------------------------ événements de l'agent
def test_evenement_chiffre_en_base_et_masque(
    admin_a: TestClient, tache_detenue: tuple[str, TestClient], fabrique_sessions: sessionmaker[Session]
) -> None:
    tache_id, agent = tache_detenue
    ev = _publier(agent, tache_id, "action", f"Je remplis le mot de passe : {MDP} et {PASSEPORT} ({MARQUEUR})")
    assert MDP not in ev["texte"] and PASSEPORT not in ev["texte"] and MARQUEUR in ev["texte"]
    with fabrique_sessions() as db:
        brut = db.execute(text("SELECT texte_chiffre FROM evenements_agent")).scalars().all()
    assert len(brut) == 1
    assert MARQUEUR not in brut[0] and MDP not in brut[0] and "Je remplis" not in brut[0]  # chiffré
    liste = admin_a.get(f"/api/v1/taches/{tache_id}/evenements").json()
    assert [e["seq"] for e in liste["elements"]] == [1] and liste["etat"] == "en_cours"
    assert MDP not in json.dumps(liste) and PASSEPORT not in json.dumps(liste)


def test_seq_croissant_et_curseur_depuis(admin_a: TestClient, tache_detenue: tuple[str, TestClient]) -> None:
    tache_id, agent = tache_detenue
    for i in range(3):
        _publier(agent, tache_id, "agent", f"Étape {i}")
    liste = admin_a.get(f"/api/v1/taches/{tache_id}/evenements?depuis=1").json()
    assert [e["seq"] for e in liste["elements"]] == [2, 3] and liste["dernier"] == 3


def test_evenement_reserve_a_l_agent_detenteur(
    application: FastAPI, admin_a: TestClient, tache_detenue: tuple[str, TestClient]
) -> None:
    tache_id, _ = tache_detenue
    _, autre_jeton = enroler_agent(admin_a, "PC-Autre")
    autre = client_agent(application, autre_jeton)
    rep = autre.post(f"/api/v1/taches/{tache_id}/evenements", json={"type": "agent", "texte": "intrus"})
    assert rep.status_code == 403
    assert autre.get(f"/api/v1/taches/{tache_id}/messages-en-attente").status_code == 403
    # un humain (cookie) ne peut pas publier au nom de l'agent
    assert admin_a.post(f"/api/v1/taches/{tache_id}/evenements", json={"type": "agent", "texte": "x"}).status_code == 401
    assert client_agent(application, "be_agent_inconnu").post(
        f"/api/v1/taches/{tache_id}/evenements", json={"type": "agent", "texte": "x"}
    ).status_code == 401


def test_type_et_commande_invalides(tache_detenue: tuple[str, TestClient]) -> None:
    tache_id, agent = tache_detenue
    assert agent.post(f"/api/v1/taches/{tache_id}/evenements", json={"type": "secret", "texte": "x"}).status_code == 422
    assert agent.post(
        f"/api/v1/taches/{tache_id}/evenements", json={"type": "commande", "texte": "x", "code": "format"}
    ).status_code == 409


# ------------------------------------------------------------------ consignes et commandes
def test_consigne_normale_recuperee_une_seule_fois_par_l_agent(
    admin_a: TestClient, tache_detenue: tuple[str, TestClient]
) -> None:
    tache_id, agent = tache_detenue
    rep = admin_a.post(f"/api/v1/taches/{tache_id}/messages", json={"texte": f"Va doucement {MARQUEUR}"})
    assert rep.status_code == 201 and rep.json()["refuse"] is False
    attente = agent.get(f"/api/v1/taches/{tache_id}/messages-en-attente").json()
    assert [m["texte"] for m in attente["messages"]] == [f"Va doucement {MARQUEUR}"]
    assert agent.get(f"/api/v1/taches/{tache_id}/messages-en-attente").json()["messages"] == []


def test_consigne_contraire_aux_regles_refusee_et_jamais_transmise(
    admin_a: TestClient, tache_detenue: tuple[str, TestClient]
) -> None:
    tache_id, agent = tache_detenue
    for texte, regle in (("Valide le dossier à ma place", "R1"), ("Contourne le captcha", "R2")):
        rep = admin_a.post(f"/api/v1/taches/{tache_id}/messages", json={"texte": texte}).json()
        assert rep["refuse"] is True and rep["message"]["code"] == "refusee"
        assert rep["reponse"]["type"] == "agent" and "à vous" in rep["reponse"]["texte"]
    attente = agent.get(f"/api/v1/taches/{tache_id}/messages-en-attente").json()
    assert attente["messages"] == [] and attente["etat"] == "en_cours"
    # l'état de la tâche n'a pas bougé : aucune validation, toujours détenue et en cours
    assert admin_a.get(f"/api/v1/taches/{tache_id}").json()["statut"] == "en_cours"


def test_message_de_l_humain_est_masque(admin_a: TestClient, tache_detenue: tuple[str, TestClient]) -> None:
    tache_id, _ = tache_detenue
    rep = admin_a.post(f"/api/v1/taches/{tache_id}/messages", json={"texte": f"mon mot de passe est {MDP}"}).json()
    assert MDP not in rep["message"]["texte"]


def test_pause_reprise_arret_et_etat(admin_a: TestClient, tache_detenue: tuple[str, TestClient]) -> None:
    tache_id, agent = tache_detenue
    assert admin_a.post(f"/api/v1/taches/{tache_id}/pause").json()["etat"] == "pause"
    attente = agent.get(f"/api/v1/taches/{tache_id}/messages-en-attente").json()
    assert attente["commandes"] == ["pause"] and attente["etat"] == "pause"
    assert agent.get(f"/api/v1/taches/{tache_id}/messages-en-attente").json()["etat"] == "pause"  # persistant
    assert admin_a.post(f"/api/v1/taches/{tache_id}/reprise").json()["etat"] == "en_cours"
    assert admin_a.post(f"/api/v1/taches/{tache_id}/premier-plan").status_code == 200
    assert admin_a.post(f"/api/v1/taches/{tache_id}/arret").json()["etat"] == "arret"
    assert admin_a.get(f"/api/v1/taches/{tache_id}/evenements").json()["etat"] == "arret"


def test_commande_refusee_si_l_agent_ne_travaille_pas(admin_a: TestClient) -> None:
    candidat_id, _, _ = creer_candidat_avec_voeux(admin_a)
    tache_id = creer_tache_pc(admin_a, candidat_id).json()["id"]  # en attente
    assert admin_a.post(f"/api/v1/taches/{tache_id}/pause").status_code == 409


# ------------------------------------------------------------------ rôles et isolation
def test_lecture_seule_lit_mais_ne_pilote_pas(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
    tache_detenue: tuple[str, TestClient],
) -> None:
    tache_id, agent = tache_detenue
    _publier(agent, tache_id, "agent", "Bonjour")
    lecteur, _ = connecter_client(application, deux_bureaux[0].lecteur.email)
    assert lecteur.get(f"/api/v1/taches/{tache_id}/evenements").status_code == 200
    for chemin in ("messages", "pause", "reprise", "arret", "premier-plan"):
        corps = {"texte": "salut"} if chemin == "messages" else None
        assert lecteur.post(f"/api/v1/taches/{tache_id}/{chemin}", json=corps).status_code == 403, chemin


def test_csrf_obligatoire_pour_les_ecritures_humaines(
    application: FastAPI, deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest], tache_detenue: tuple[str, TestClient]
) -> None:
    tache_id, _ = tache_detenue
    client = TestClient(application)  # connecté (cookie) mais sans en-tête CSRF
    assert client.post(
        "/api/v1/auth/connexion", json={"email": deux_bureaux[0].admin.email, "mot_de_passe": MOT_DE_PASSE_FORT}
    ).status_code == 200
    assert client.post(f"/api/v1/taches/{tache_id}/pause").status_code in (400, 403)
    assert client.post(f"/api/v1/taches/{tache_id}/messages", json={"texte": "salut"}).status_code in (400, 403)
    assert TestClient(application).post(f"/api/v1/taches/{tache_id}/pause").status_code == 401


def test_isolation_des_bureaux(
    application: FastAPI, deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest], tache_detenue: tuple[str, TestClient]
) -> None:
    tache_id, agent = tache_detenue
    _publier(agent, tache_id, "agent", "Privé au bureau A")
    admin_b, _ = connecter_client(application, deux_bureaux[1].admin.email)
    assert admin_b.get(f"/api/v1/taches/{tache_id}/evenements").status_code == 404
    assert admin_b.get(f"/api/v1/taches/{tache_id}/evenements/flux").status_code == 404
    assert admin_b.post(f"/api/v1/taches/{tache_id}/messages", json={"texte": "intrusion"}).status_code == 404
    assert admin_b.post(f"/api/v1/taches/{tache_id}/pause").status_code == 404
    # l'agent d'un autre bureau ne peut pas non plus écrire sur cette tâche
    _, jeton_b = enroler_agent(admin_b, "PC-B")
    assert client_agent(application, jeton_b).post(
        f"/api/v1/taches/{tache_id}/evenements", json={"type": "agent", "texte": "x"}
    ).status_code == 404


# ------------------------------------------------------------------ flux SSE
def test_flux_sse_envoie_les_evenements_puis_se_termine(
    admin_a: TestClient, tache_detenue: tuple[str, TestClient]
) -> None:
    tache_id, agent = tache_detenue
    _publier(agent, tache_id, "agent", "Premier")
    _publier(agent, tache_id, "demande_humaine", "Connectez-vous vous-même")
    with admin_a.stream("GET", f"/api/v1/taches/{tache_id}/evenements/flux?duree_max_s=1") as rep:
        assert rep.status_code == 200
        assert rep.headers["content-type"].startswith("text/event-stream")
        corps = "".join(rep.iter_text())
    assert "event: evenement" in corps and "id: 1\n" in corps and "id: 2\n" in corps
    assert "Premier" in corps and "Connectez-vous vous-même" in corps
    assert "event: etat" in corps and "event: fin" in corps


def test_flux_sse_reprend_apres_last_event_id(admin_a: TestClient, tache_detenue: tuple[str, TestClient]) -> None:
    tache_id, agent = tache_detenue
    _publier(agent, tache_id, "agent", "Déjà vu")
    _publier(agent, tache_id, "agent", "Nouveau")
    with admin_a.stream(
        "GET", f"/api/v1/taches/{tache_id}/evenements/flux?duree_max_s=1", headers={"Last-Event-ID": "1"}
    ) as rep:
        corps = "".join(rep.iter_text())
    assert "Nouveau" in corps and "Déjà vu" not in corps


# ------------------------------------------------------------------ purge
def test_purge_apres_sept_jours(
    tache_detenue: tuple[str, TestClient], fabrique_sessions: sessionmaker[Session]
) -> None:
    tache_id, agent = tache_detenue
    for i in range(3):
        _publier(agent, tache_id, "agent", f"Message {i}")
    vieux = (maintenant_utc() - timedelta(days=8)).isoformat(sep=" ")
    with fabrique_sessions() as db:
        db.execute(text("UPDATE evenements_agent SET cree_le = :d WHERE seq IN (1, 2)"), {"d": vieux})
        db.commit()
        assert purger_evenements_expires(db) == 2
        restants = db.execute(text("SELECT seq FROM evenements_agent")).scalars().all()
    assert restants == [3]
