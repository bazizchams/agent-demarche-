"""La route des pièces spécimens de démonstration n'existe pas en production (404)."""

from __future__ import annotations

from app.core.config import Environnement, obtenir_parametres
from tests.conftest import connecter_client

ROUTE = "/api/v1/candidats/{cid}/documents/specimens-demo"


def _creer_candidat(client) -> str:
    rep = client.post("/api/v1/candidats", json={"nom": "TESTNOM", "prenom": "Testprenom"})
    assert rep.status_code == 201, rep.text
    return rep.json()["id"]


def test_specimens_disponibles_hors_production(application, deux_bureaux, parametres_test):
    admin, _ = connecter_client(application, "admin.alpha@bureau-fictif.dz")
    cid = _creer_candidat(admin)
    rep = admin.post(ROUTE.format(cid=cid), params={"code_demarche": "campus_france"})
    assert rep.status_code == 201, rep.text


def test_specimens_introuvables_en_production(application, deux_bureaux, parametres_test):
    admin, _ = connecter_client(application, "admin.alpha@bureau-fictif.dz")
    cid = _creer_candidat(admin)
    prod = parametres_test.model_copy(update={"environnement": Environnement.PRODUCTION})
    application.dependency_overrides[obtenir_parametres] = lambda: prod
    try:
        rep = admin.post(ROUTE.format(cid=cid), params={"code_demarche": "campus_france"})
    finally:
        application.dependency_overrides.pop(obtenir_parametres, None)
    assert rep.status_code == 404, rep.text
    # Aucune pièce n'a été créée.
    docs = admin.get(f"/api/v1/candidats/{cid}/documents")
    assert docs.status_code == 200
    assert docs.json() == []
