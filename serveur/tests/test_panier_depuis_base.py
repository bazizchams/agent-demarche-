"""Le bouton « Ajouter les vœux validés au panier » lit les vœux VALIDÉS en base."""

from __future__ import annotations

from fastapi import FastAPI

from tests.conftest import DonneesBureauTest, connecter_client


def _candidat_et_voeux(client) -> tuple[str, str, str]:
    rep = client.post(
        "/api/v1/candidats",
        json={"nom": "Testeur", "prenom": "Panier", "email": "panier.testeur@exemple-fictif.dz"},
    )
    assert rep.status_code == 201, rep.text
    candidat_id = rep.json()["id"]
    ids = []
    for intitule, etab in (
        ("Master Traitement automatique des langues", "Université de Lorraine"),
        ("Master Sciences du langage parcours LITL", "Université Toulouse Jean Jaurès"),
    ):
        r = client.post(
            f"/api/v1/candidats/{candidat_id}/voeux",
            json={"intitule": intitule, "etablissement": etab, "niveau": "Master 1"},
        )
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    return candidat_id, ids[0], ids[1]


def _piloter(client, candidat_id: str, **extra):
    corps = {
        "candidat_id": candidat_id,
        "code_demarche": "campus_france",
        "cible": "demo_campus_france",
        "action": "ajouter_voeux_panier",
        "ouvrir_fenetre_visible": False,
        "synchroniser_tache": False,
    }
    corps.update(extra)
    return client.post("/api/v1/portails/piloter-navigateur", json=corps)


def test_sans_voeu_valide_l_action_est_refusee(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.admin.email)
    candidat_id, _, _ = _candidat_et_voeux(client)  # deux vœux en brouillon, aucun validé
    rep = _piloter(client, candidat_id)
    assert rep.status_code == 422, rep.text
    assert "validé" in rep.json()["detail"]


def test_seuls_les_voeux_valides_partent_sur_la_demo_sans_changer_leur_statut(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.admin.email)
    candidat_id, voeu_1, voeu_2 = _candidat_et_voeux(client)

    # Le vœu 1 reçoit une lettre complète et est validé ; le vœu 2 reste en brouillon.
    r = client.patch(
        f"/api/v1/candidats/{candidat_id}/voeux/{voeu_1}",
        json={"motivation": "Madame, Monsieur, je candidate avec sérieux à cette formation."},
    )
    assert r.status_code == 200, r.text
    assert client.post(f"/api/v1/candidats/{candidat_id}/voeux/{voeu_1}/valider").status_code == 200

    rep = _piloter(client, candidat_id)
    assert rep.status_code == 200, rep.text
    resultats = rep.json()["resultats_voeux"]
    assert [r["voeu_id"] for r in resultats] == [voeu_1]  # le brouillon n'est pas envoyé

    # Essai sur la démo : le statut reste « validé » (le vrai panier n'a pas changé).
    liste = client.get(f"/api/v1/candidats/{candidat_id}/voeux").json()
    statuts = {v["id"]: v["statut"] for v in liste}
    assert statuts[voeu_1] == "valide"
    assert statuts[voeu_2] == "brouillon"
