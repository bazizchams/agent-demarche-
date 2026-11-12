"""Lettres de motivation des vœux : génération, signature locale, garde-fous de validation."""

from __future__ import annotations

from fastapi import FastAPI

from app.services.llm import ReponseLLM, obtenir_client_llm_optionnel
from tests.conftest import DonneesBureauTest, connecter_client

NOM = "Ouazzani-Testeur"
PRENOM = "Tamazight"
PASSEPORT = "ZZ7654321"
EMAIL = "ouazzani.testeur@exemple-fictif.dz"

FAITS = {
    "parcours": ["2023-2025 : Master Linguistique et didactique, moyenne 13,16/20, mémoire 16/20"],
    "points_forts": ["Mémoire noté 16/20"],
    "langues": ["Anglais : 17/20 en M1"],
    "projet": "Travailler sur le traitement automatique des langues peu dotées.",
}


class FauxClient:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def generer(self, *, systeme, message, outil=None, max_tokens=4096) -> ReponseLLM:
        self.messages.append(message)
        return ReponseLLM(
            texte="Madame, Monsieur,\n\nJe candidate à cette formation avec sérieux.\n\n[Prénom NOM]",
            tokens_entree=10,
            tokens_sortie=20,
        )


def _preparer(client) -> tuple[str, str]:
    rep = client.post(
        "/api/v1/candidats",
        json={
            "nom": NOM,
            "prenom": PRENOM,
            "sexe": "F",
            "date_naissance": "2001-07-25",
            "nationalite": "Algérienne",
            "pays_residence": "Algérie",
            "numero_passeport": PASSEPORT,
            "email": EMAIL,
            "telephone": "+213555998877",
            "niveau_actuel": "Master 2 Linguistique",
        },
    )
    assert rep.status_code == 201, rep.text
    candidat_id = rep.json()["id"]
    rep = client.post(
        f"/api/v1/candidats/{candidat_id}/voeux",
        json={
            "intitule": "Master Traitement automatique des langues",
            "etablissement": "Université de Lorraine",
            "niveau": "Master 1",
        },
    )
    assert rep.status_code == 201, rep.text
    return candidat_id, rep.json()["id"]


def test_sans_cle_api_lettre_modele_non_validable_tant_que_incomplete(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.admin.email)
    candidat_id, voeu_id = _preparer(client)

    rep = client.post(f"/api/v1/candidats/{candidat_id}/voeux/{voeu_id}/lettre/generer", json={})
    assert rep.status_code == 200, rep.text
    corps = rep.json()
    assert corps["origine"] == "modele"
    assert corps["voeu"]["statut"] == "brouillon"
    assert "[À COMPLÉTER" in corps["voeu"]["motivation"]
    assert f"{PRENOM} {NOM}" in corps["voeu"]["motivation"]  # signature remplacée localement
    assert corps["elements_a_verifier"]

    # Règle 4 : impossible de valider une lettre qui contient encore des repères
    rep = client.post(f"/api/v1/candidats/{candidat_id}/voeux/{voeu_id}/valider")
    assert rep.status_code == 422


def test_avec_client_aucune_identite_envoyee_et_validation_possible(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.admin.email)
    candidat_id, voeu_id = _preparer(client)
    faux = FauxClient()
    application.dependency_overrides[obtenir_client_llm_optionnel] = lambda: faux
    try:
        rep = client.post(
            f"/api/v1/candidats/{candidat_id}/voeux/{voeu_id}/lettre/generer", json=FAITS
        )
        statut_ia = client.get("/api/v1/ia/statut").json()
    finally:
        application.dependency_overrides.pop(obtenir_client_llm_optionnel, None)

    assert rep.status_code == 200, rep.text
    corps = rep.json()
    assert corps["origine"] == "ia"
    assert statut_ia["appels_ce_mois"] == 1

    # Aucune donnée d'identité n'a été transmise au modèle
    assert len(faux.messages) == 1
    for secret in (NOM, PRENOM, PASSEPORT, EMAIL, "213555998877"):
        assert secret not in faux.messages[0]

    # La signature a été remplacée localement par le nom du candidat
    assert f"{PRENOM} {NOM}" in corps["voeu"]["motivation"]
    assert "[Prénom NOM]" not in corps["voeu"]["motivation"]

    rep = client.post(f"/api/v1/candidats/{candidat_id}/voeux/{voeu_id}/valider")
    assert rep.status_code == 200, rep.text
    assert rep.json()["statut"] == "valide"


def test_lecteur_ne_peut_pas_generer_et_autre_bureau_est_isole(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    a, b = deux_bureaux
    client_a, _ = connecter_client(application, a.admin.email)
    candidat_id, voeu_id = _preparer(client_a)
    url = f"/api/v1/candidats/{candidat_id}/voeux/{voeu_id}/lettre/generer"

    client_lecteur, _ = connecter_client(application, a.lecteur.email)
    assert client_lecteur.post(url, json={}).status_code == 403

    client_b, _ = connecter_client(application, b.admin.email)
    assert client_b.post(url, json={}).status_code == 404
