"""Démarches définies par bureau : ajout, personnalisation, désactivation, isolation."""

from __future__ import annotations

from fastapi import FastAPI

from tests.conftest import DonneesBureauTest, connecter_client


def _visa_tourisme(libelle: str = "Visa touristique Schengen") -> dict:
    return {
        "code": "visa_touristique",
        "libelle": libelle,
        "description": "Demande de visa court séjour.",
        "champs_candidat_requis": ["nom", "prenom", "numero_passeport"],
        "pieces_requises": [
            {
                "type_piece": "passeport",
                "libelle": "Passeport",
                "obligatoire": True,
                "exige_date_expiration": True,
                "validite_minimale_jours": 90,
            },
            {"type_piece": "reservation_hotel", "libelle": "Réservation d'hôtel"},
        ],
    }


def _codes(client) -> set[str]:
    rep = client.get("/api/v1/demarches")
    assert rep.status_code == 200, rep.text
    return {d["code"] for d in rep.json()}


def test_un_administrateur_ajoute_une_demarche_visible_de_son_bureau_seulement(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    a, b = deux_bureaux
    client_a, _ = connecter_client(application, a.admin.email)
    client_b, _ = connecter_client(application, b.admin.email)

    rep = client_a.post("/api/v1/demarches", json=_visa_tourisme())
    assert rep.status_code == 201, rep.text
    assert rep.json()["version"] == 1
    assert rep.json()["source"] == "bureau"

    assert "visa_touristique" in _codes(client_a)
    assert "visa_touristique" not in _codes(client_b)
    # Les démarches de base restent visibles des deux bureaux.
    assert "campus_france" in _codes(client_a)
    assert "campus_france" in _codes(client_b)


def test_un_employe_ne_peut_pas_ecrire(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.employe.email)
    assert client.post("/api/v1/demarches", json=_visa_tourisme()).status_code == 403
    assert client.get("/api/v1/demarches").status_code == 200


def test_personnaliser_une_demarche_de_base_incremente_la_version(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    a, b = deux_bureaux
    client_a, _ = connecter_client(application, a.admin.email)
    client_b, _ = connecter_client(application, b.admin.email)

    base = client_a.get("/api/v1/demarches/campus_france").json()
    assert base["source"] == "base"
    definition = base["definition"]
    definition["libelle"] = "Campus France — version World Destination"

    rep = client_a.put("/api/v1/demarches/campus_france", json=definition)
    assert rep.status_code == 200, rep.text
    assert rep.json()["version"] == 1
    definition["description"] = "Seconde modification."
    rep = client_a.put("/api/v1/demarches/campus_france", json=definition)
    assert rep.json()["version"] == 2

    libelle_a = client_a.get("/api/v1/demarches/campus_france").json()["definition"]["libelle"]
    libelle_b = client_b.get("/api/v1/demarches/campus_france").json()["definition"]["libelle"]
    assert libelle_a == "Campus France — version World Destination"
    assert libelle_b != libelle_a


def test_desactiver_masque_la_demarche_pour_ce_bureau_seulement(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    a, b = deux_bureaux
    client_a, _ = connecter_client(application, a.admin.email)
    client_b, _ = connecter_client(application, b.admin.email)

    assert client_a.delete("/api/v1/demarches/campus_france").status_code == 204
    assert "campus_france" not in _codes(client_a)
    assert client_a.get("/api/v1/demarches/campus_france").status_code == 404
    assert "campus_france" in _codes(client_b)

    # La réactivation passe par une nouvelle écriture.
    definition = client_b.get("/api/v1/demarches/campus_france").json()["definition"]
    assert client_a.put("/api/v1/demarches/campus_france", json=definition).status_code == 200
    assert "campus_france" in _codes(client_a)


def test_validation_des_definitions(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.admin.email)

    # Champ inconnu refusé (extra="forbid").
    mauvais = _visa_tourisme()
    mauvais["champ_inconnu"] = 1
    assert client.post("/api/v1/demarches", json=mauvais).status_code in (400, 422)

    # Code invalide.
    mauvais = _visa_tourisme()
    mauvais["code"] = "Visa Touristique!"
    assert client.post("/api/v1/demarches", json=mauvais).status_code in (400, 422)

    # Doublon de type de pièce.
    mauvais = _visa_tourisme()
    mauvais["pieces_requises"].append({"type_piece": "passeport", "libelle": "Autre"})
    assert client.post("/api/v1/demarches", json=mauvais).status_code in (400, 422)

    # Création puis doublon de code.
    assert client.post("/api/v1/demarches", json=_visa_tourisme()).status_code == 201
    assert client.post("/api/v1/demarches", json=_visa_tourisme()).status_code == 409
    # Code de base : il faut passer par la modification.
    base = client.get("/api/v1/demarches/campus_france").json()["definition"]
    assert client.post("/api/v1/demarches", json=base).status_code == 409

    # Le code de l'URL doit correspondre au corps.
    rep = client.put("/api/v1/demarches/autre_code", json=_visa_tourisme())
    assert rep.status_code in (400, 404, 422)
