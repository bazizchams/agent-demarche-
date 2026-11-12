"""Validation humaine d'un récapitulatif avant soumission officielle (Règle 1 réécrite)."""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependances import EN_TETE_JETON_AGENT
from app.core.erreurs import AccesRefuse, Conflit
from app.db.tenant import definir_tenant
from app.modeles.journal_audit import EntreeAudit
from app.services import validation_recapitulatif as service
from tests.conftest import DonneesBureauTest, connecter_client

BASE = "/api/v1/validations-recapitulatif"
NOM_SECRET = "MANSOURI-Zohra"
CONTENU = {"nom": NOM_SECRET, "voeux": ["Informatique Lyon"], "champs_manquants": []}


def _creer_candidat(client: TestClient) -> str:
    rep = client.post("/api/v1/candidats", json={"nom": "MANSOURI", "prenom": "Zohra"})
    assert rep.status_code == 201, rep.text
    return rep.json()["id"]


def _proposition(cid: str, contenu: dict | None = None) -> dict:
    return {
        "candidat_id": cid, "portail": "campus_france",
        "type_demarche": "campus_france", "contenu": contenu or CONTENU,
    }


def _client_agent(application: FastAPI, client_admin: TestClient) -> TestClient:
    rep = client_admin.post("/api/v1/agents-locaux", json={"nom_machine": "PC-TEST-01"})
    assert rep.status_code == 201, rep.text
    agent = TestClient(application)
    agent.headers[EN_TETE_JETON_AGENT] = rep.json()["jeton_secret"]
    return agent


def test_agent_peut_proposer_mais_pas_valider(
    application: FastAPI, deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest]
) -> None:
    a, _ = deux_bureaux
    employe, _ = connecter_client(application, a.employe.email)
    admin, _ = connecter_client(application, a.admin.email)
    cid = _creer_candidat(employe)
    agent = _client_agent(application, admin)

    rep = agent.post(BASE, json=_proposition(cid))
    assert rep.status_code == 201, rep.text
    assert rep.json()["statut"] == "en_attente"
    assert rep.json()["contenu"] is None  # l'agent ne relit pas le contenu
    vid = rep.json()["id"]

    # Jeton agent seul : refusé sur valider et refuser, et ne peut pas lire.
    assert agent.post(f"{BASE}/{vid}/valider").status_code in (401, 403)
    assert agent.post(f"{BASE}/{vid}/refuser").status_code in (401, 403)
    assert agent.get(f"{BASE}/{vid}").status_code in (401, 403)
    assert employe.get(f"{BASE}/{vid}").json()["statut"] == "en_attente"


def test_lecture_seule_ne_peut_pas_valider(
    application: FastAPI, deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest]
) -> None:
    a, _ = deux_bureaux
    employe, _ = connecter_client(application, a.employe.email)
    lecteur, _ = connecter_client(application, a.lecteur.email)
    cid = _creer_candidat(employe)
    vid = employe.post(BASE, json=_proposition(cid)).json()["id"]
    assert lecteur.post(f"{BASE}/{vid}/valider").status_code == 403
    assert lecteur.post(f"{BASE}/{vid}/refuser").status_code == 403
    assert lecteur.get(f"{BASE}/{vid}").status_code == 403


def test_employe_valide_et_voit_le_contenu_dechiffre(
    application: FastAPI, deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest]
) -> None:
    a, _ = deux_bureaux
    employe, _ = connecter_client(application, a.employe.email)
    cid = _creer_candidat(employe)
    vid = employe.post(BASE, json=_proposition(cid)).json()["id"]

    rep = employe.post(f"{BASE}/{vid}/valider")
    assert rep.status_code == 200, rep.text
    corps = rep.json()
    assert corps["statut"] == "validee"
    assert corps["validee_par"] == str(a.employe.id)
    assert corps["contenu"]["nom"] == NOM_SECRET
    assert employe.get(BASE, params={"candidat_id": cid}).json()[0]["id"] == vid
    # Une deuxième décision est impossible.
    assert employe.post(f"{BASE}/{vid}/refuser").status_code == 409


def test_refus_humain(
    application: FastAPI, deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest]
) -> None:
    a, _ = deux_bureaux
    admin, _ = connecter_client(application, a.admin.email)
    cid = _creer_candidat(admin)
    vid = admin.post(BASE, json=_proposition(cid)).json()["id"]
    assert admin.post(f"{BASE}/{vid}/refuser").json()["statut"] == "refusee"
    assert admin.post(f"{BASE}/{vid}/valider").status_code == 409


def test_champs_manquants_non_validable(
    application: FastAPI, deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest]
) -> None:
    a, _ = deux_bureaux
    employe, _ = connecter_client(application, a.employe.email)
    cid = _creer_candidat(employe)
    incomplet = {**CONTENU, "champs_manquants": ["date_naissance"]}
    rep = employe.post(BASE, json=_proposition(cid, incomplet))
    assert rep.json()["champs_manquants"] == ["date_naissance"]
    vid = rep.json()["id"]
    refus = employe.post(f"{BASE}/{vid}/valider")
    assert refus.status_code == 422
    assert employe.get(f"{BASE}/{vid}").json()["statut"] == "en_attente"


def test_modification_du_contenu_invalide_la_validation_et_usage_unique(
    application: FastAPI,
    fabrique_sessions: sessionmaker[Session],
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    a, _ = deux_bureaux
    employe, _ = connecter_client(application, a.employe.email)
    cid = _creer_candidat(employe)
    cle = application.state.cle_maitresse

    def _valider_nouvelle() -> uuid.UUID:
        vid = employe.post(BASE, json=_proposition(cid)).json()["id"]
        assert employe.post(f"{BASE}/{vid}/valider").status_code == 200
        return uuid.UUID(vid)

    with fabrique_sessions() as db:
        definir_tenant(db, a.bureau.id)
        # 1. Contenu modifié -> invalidée, envoi refusé.
        vid = _valider_nouvelle()
        with pytest.raises(Conflit):
            service.exiger_validation_pour_envoi(db, vid, {**CONTENU, "voeux": ["Autre"]})
        assert service.obtenir(db, vid).statut.value == "invalidee"
        with pytest.raises(AccesRefuse):  # plus jamais envoyable
            service.exiger_validation_pour_envoi(db, vid, CONTENU)

        # 2. Contenu identique -> accepté, puis usage unique.
        vid2 = _valider_nouvelle()
        service.exiger_validation_pour_envoi(db, vid2, dict(CONTENU))
        service.marquer_envoyee(db, vid2)
        assert service.obtenir(db, vid2).statut.value == "envoyee"
        with pytest.raises(Conflit):
            service.marquer_envoyee(db, vid2)
        with pytest.raises(AccesRefuse):
            service.exiger_validation_pour_envoi(db, vid2, CONTENU)

        # 3. Sans validation, ou en attente : refusé.
        with pytest.raises(AccesRefuse):
            service.exiger_validation_pour_envoi(db, None, CONTENU)
        vid3 = uuid.UUID(employe.post(BASE, json=_proposition(cid)).json()["id"])
        with pytest.raises(AccesRefuse):
            service.exiger_validation_pour_envoi(db, vid3, CONTENU)
    assert cle  # la clé maîtresse existe côté application


def test_nouvelle_proposition_invalide_les_precedentes(
    application: FastAPI, deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest]
) -> None:
    a, _ = deux_bureaux
    employe, _ = connecter_client(application, a.employe.email)
    cid = _creer_candidat(employe)
    v1 = employe.post(BASE, json=_proposition(cid)).json()["id"]
    v2 = employe.post(BASE, json=_proposition(cid, {**CONTENU, "voeux": ["X"]})).json()["id"]
    assert employe.get(f"{BASE}/{v1}").json()["statut"] == "invalidee"
    assert employe.get(f"{BASE}/{v2}").json()["statut"] == "en_attente"
    assert employe.post(f"{BASE}/{v1}/valider").status_code == 409


def test_isolation_entre_bureaux(
    application: FastAPI, deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest]
) -> None:
    a, b = deux_bureaux
    employe_a, _ = connecter_client(application, a.employe.email)
    employe_b, _ = connecter_client(application, b.employe.email)
    cid = _creer_candidat(employe_a)
    vid = employe_a.post(BASE, json=_proposition(cid)).json()["id"]

    assert employe_b.get(f"{BASE}/{vid}").status_code == 404
    assert employe_b.post(f"{BASE}/{vid}/valider").status_code == 404
    assert employe_b.get(BASE).json() == []
    assert employe_b.post(BASE, json=_proposition(cid)).status_code == 404


def test_audit_sans_donnee_personnelle_et_contenu_chiffre_en_base(
    application: FastAPI,
    fabrique_sessions: sessionmaker[Session],
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    a, _ = deux_bureaux
    employe, _ = connecter_client(application, a.employe.email)
    cid = _creer_candidat(employe)
    vid = employe.post(BASE, json=_proposition(cid)).json()["id"]
    employe.post(f"{BASE}/{vid}/valider")
    vid2 = employe.post(BASE, json=_proposition(cid, {**CONTENU, "voeux": ["Y"]})).json()["id"]
    employe.post(f"{BASE}/{vid2}/refuser")

    with fabrique_sessions() as db:
        definir_tenant(db, a.bureau.id)
        entrees = db.scalars(
            select(EntreeAudit).where(EntreeAudit.action.like("validation_recapitulatif.%"))
        ).all()
        actions = {e.action for e in entrees}
        assert {
            "validation_recapitulatif.propose",
            "validation_recapitulatif.valide",
            "validation_recapitulatif.refuse",
            "validation_recapitulatif.invalide",
        } <= actions
        valide = next(e for e in entrees if e.action.endswith(".valide"))
        assert valide.acteur_id == a.employe.id and valide.details["empreinte"]
        vidu = uuid.UUID(vid)
        assert valide.ressource_id == vidu
        vidage = json.dumps([e.details for e in entrees]) + str(
            [(e.action, e.ressource_type) for e in entrees]
        )
        for interdit in (NOM_SECRET, "MANSOURI", "Zohra", "Lyon", a.employe.email):
            assert interdit not in vidage

        brut = db.execute(text("SELECT contenu_chiffre FROM validations_recapitulatif")).scalars().all()
        assert len(brut) == 2
        for valeur in brut:
            assert "MANSOURI" not in valeur and "Lyon" not in valeur
            assert valeur != json.dumps(CONTENU, sort_keys=True)
