"""Catalogue de formations par bureau et endpoint `POST /api/v1/voeux/suggestions` : import des 15 écoles,
isolation multi-bureaux, rôle, CSRF, lecture seule (aucun vœu créé), audit sans donnée personnelle, R6."""

from __future__ import annotations

import json
from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependances import EN_TETE_CSRF
from app.db.tenant import definir_tenant
from app.modeles.fiche_formation import FicheFormation, StatutFiche
from app.modeles.journal_audit import EntreeAudit
from app.modeles.voeu_formation import VoeuFormation
from tests.conftest import DonneesBureauTest, connecter_client

NOM_CANDIDAT = "TESTEUR"
PRENOM_CANDIDAT = "Fictif"
URL_SUGGESTIONS = "/api/v1/voeux/suggestions"
PROFIL_B2 = {
    "niveau_diplome_bac_plus": 3,
    "moyennes": {"derniere_annee": 14.5},
    "francais": {"niveau": "B2", "certificat": {"type": "DELF", "date_obtention": "2025-06-01"}},
    "domaines_souhaites": ["ingenieur"],
    "date_rentree": "2027-09-01",
}
FICHE_EXPLOREE = {
    "etablissement": "Université Fictive",
    "intitule": "Master Fictif",
    "niveau_entree_bac_plus": 4,
    "francais_min": "B2",
    "date_releve": "2026-11-13",
    "source": "exploration",
    "url_officielle": "https://etudesenfrance.diplomatie.gouv.fr/catalogue-formations/formation/1/site/2",
}


def _importer(client: TestClient) -> dict:
    rep = client.post("/api/v1/catalogue-formations/import-ecoles")
    assert rep.status_code == 200, rep.text
    return rep.json()


def _audits(fabrique: sessionmaker[Session], donnees: DonneesBureauTest) -> list[EntreeAudit]:
    with fabrique() as db:
        definir_tenant(db, donnees.bureau.id)
        return list(db.scalars(select(EntreeAudit)).all())


def test_import_des_15_ecoles_est_idempotent_et_tout_est_a_verifier(
    application: FastAPI, deux_bureaux, fabrique_sessions
) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.employe.email)
    premier = _importer(client)
    assert premier["ecoles"] == 15 and premier["crees"] == 46 and premier["mises_a_jour"] == 0
    second = _importer(client)
    assert second["crees"] == 0 and second["mises_a_jour"] == 46
    with fabrique_sessions() as db:
        definir_tenant(db, a.bureau.id)
        fiches = list(db.scalars(select(FicheFormation)).all())
    assert len(fiches) == 46
    assert all(f.statut == StatutFiche.A_VERIFIER and f.exigences_a_verifier for f in fiches)
    assert all(f.date_releve == date(2026, 11, 13) and f.url_officielle for f in fiches)


def test_isolation_entre_bureaux_catalogue_et_suggestions(application: FastAPI, deux_bureaux) -> None:
    a, b = deux_bureaux
    client_a, _ = connecter_client(application, a.employe.email)
    client_b, _ = connecter_client(application, b.employe.email)
    _importer(client_a)
    assert len(client_a.get("/api/v1/catalogue-formations").json()) == 46
    assert client_b.get("/api/v1/catalogue-formations").json() == []
    rep_b = client_b.post(URL_SUGGESTIONS, json={"profil": PROFIL_B2})
    assert rep_b.status_code == 200
    assert rep_b.json()["propositions"] == [] and rep_b.json()["nb_fiches_examinees"] == 0
    assert rep_b.json()["avertissements"]
    rep_a = client_a.post(URL_SUGGESTIONS, json={"profil": PROFIL_B2})
    assert rep_a.json()["nb_fiches_examinees"] == 46


def test_candidat_d_un_autre_bureau_donne_404(application: FastAPI, deux_bureaux) -> None:
    a, b = deux_bureaux
    client_a, _ = connecter_client(application, a.employe.email)
    client_b, _ = connecter_client(application, b.employe.email)
    cid = client_a.post("/api/v1/candidats", json={"nom": NOM_CANDIDAT, "prenom": PRENOM_CANDIDAT}).json()["id"]
    assert client_b.post(URL_SUGGESTIONS, json={"profil": PROFIL_B2, "candidat_id": cid}).status_code == 404
    assert client_a.post(URL_SUGGESTIONS, json={"profil": PROFIL_B2, "candidat_id": cid}).status_code == 200


def test_suggestions_ecoles_importees_sont_a_verifier_et_jamais_ok_sur_l_inconnu(
    application: FastAPI, deux_bureaux
) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.employe.email)
    _importer(client)
    rep = client.post(URL_SUGGESTIONS, json={"profil": PROFIL_B2})
    assert rep.status_code == 200, rep.text
    corps = rep.json()
    assert 1 <= len(corps["propositions"]) <= 7
    for p in corps["propositions"]:
        assert p["a_verifier"] and p["categorie"] in ("a_verifier", "ambitieux")
        assert "niveau_entree" in p["exigences"]["exigences_a_verifier"]
        assert p["exigences"]["url_officielle"].startswith("https://")
        assert p["exigences"]["date_releve"] == "2026-11-13"
    esiea = [p for p in corps["propositions"] if p["etablissement"] == "ESIEA"]
    assert esiea and esiea[0]["exigences"]["francais_min"] == "B2"


def test_suggestions_ne_creent_aucun_voeu_et_sont_auditees_sans_pii(
    application: FastAPI, deux_bureaux, fabrique_sessions
) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.employe.email)
    cid = client.post("/api/v1/candidats", json={"nom": NOM_CANDIDAT, "prenom": PRENOM_CANDIDAT}).json()["id"]
    _importer(client)
    rep = client.post(URL_SUGGESTIONS, json={"profil": PROFIL_B2, "candidat_id": cid})
    assert rep.status_code == 200
    # lecture seule : aucun vœu créé, ni en base, ni via l'API des vœux
    assert client.get(f"/api/v1/candidats/{cid}/voeux").json() == []
    with fabrique_sessions() as db:
        definir_tenant(db, a.bureau.id)
        assert db.scalars(select(VoeuFormation)).first() is None
    # sortie sans identité (ni nom, ni prénom, ni identifiant de candidat)
    texte = rep.text
    for interdit in (NOM_CANDIDAT, PRENOM_CANDIDAT, cid):
        assert interdit not in texte
    # audit : compteurs uniquement
    entrees = [e for e in _audits(fabrique_sessions, a) if e.action == "voeux.suggestions"]
    assert len(entrees) == 1
    assert set(entrees[0].details) == {
        "nb_fiches", "nb_propositions", "nb_a_verifier", "nb_exclus", "avec_candidat", "avec_demarche",
    }
    tout_l_audit = json.dumps([e.details for e in _audits(fabrique_sessions, a)], default=str)
    for interdit in (NOM_CANDIDAT, PRENOM_CANDIDAT, "DELF", "14.5", "ingenieur"):
        assert interdit not in tout_l_audit


def test_le_profil_refuse_toute_identite_ou_champ_inconnu(application: FastAPI, deux_bureaux) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.employe.email)
    for extra in ({"nom": NOM_CANDIDAT}, {"date_naissance": "2001-01-01"}, {"passeport": "AB123456"}):
        rep = client.post(URL_SUGGESTIONS, json={"profil": {**PROFIL_B2, **extra}})
        assert rep.status_code == 422
        assert NOM_CANDIDAT not in rep.text


def test_role_lecture_seule_refuse_et_csrf_obligatoire(application: FastAPI, deux_bureaux) -> None:
    a, _ = deux_bureaux
    lecteur, _ = connecter_client(application, a.lecteur.email)
    assert lecteur.post(URL_SUGGESTIONS, json={"profil": PROFIL_B2}).status_code == 403
    assert lecteur.post("/api/v1/catalogue-formations/import-ecoles").status_code == 403
    sans_csrf, _ = connecter_client(application, a.employe.email)
    del sans_csrf.headers[EN_TETE_CSRF]
    assert sans_csrf.post(URL_SUGGESTIONS, json={"profil": PROFIL_B2}).status_code == 403
    anonyme = TestClient(application)
    assert anonyme.post(URL_SUGGESTIONS, json={"profil": PROFIL_B2}).status_code == 401


def test_cas_reel_b2_face_a_une_fiche_c1_importee_n_est_pas_realiste(
    application: FastAPI, deux_bureaux
) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.employe.email)
    complete = {
        **FICHE_EXPLOREE,
        "francais_min": "C1",
        "priorite_c1": True,
        "moyenne_min": 12,
        "moyenne_reference": "derniere_annee",
        "date_limite": "2099-12-31",
    }
    rep = client.post("/api/v1/catalogue-formations/fiches", json={"fiches": [complete]})
    assert rep.status_code == 200, rep.text
    sortie = client.post(URL_SUGGESTIONS, json={"profil": {**PROFIL_B2, "domaines_souhaites": []}}).json()
    assert [p["categorie"] for p in sortie["propositions"]] == ["ambitieux"]
    assert any("C1" in e and "B2" in e for e in sortie["propositions"][0]["ecarts"])


def test_import_de_fiches_explorees_exige_un_domaine_officiel_regle_6(
    application: FastAPI, deux_bureaux
) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.employe.email)
    imitateur = {**FICHE_EXPLOREE, "url_officielle": "https://etudesenfrance.diplomatie.gouv.fr.pirate.example/x"}
    assert client.post("/api/v1/catalogue-formations/fiches", json={"fiches": [imitateur]}).status_code == 422
    http = {**FICHE_EXPLOREE, "url_officielle": "http://etudesenfrance.diplomatie.gouv.fr/x"}
    assert client.post("/api/v1/catalogue-formations/fiches", json={"fiches": [http]}).status_code == 422
    ok = client.post("/api/v1/catalogue-formations/fiches", json={"fiches": [FICHE_EXPLOREE]})
    assert ok.status_code == 200 and ok.json()["crees"] == 1


def test_fiche_plus_ancienne_ne_remplace_pas_un_releve_recent(application: FastAPI, deux_bureaux) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.employe.email)
    client.post("/api/v1/catalogue-formations/fiches", json={"fiches": [FICHE_EXPLOREE]})
    ancienne = {**FICHE_EXPLOREE, "francais_min": "C1", "date_releve": "2026-01-01"}
    rep = client.post("/api/v1/catalogue-formations/fiches", json={"fiches": [ancienne]})
    assert rep.json() == {"crees": 0, "mises_a_jour": 0, "ignorees_plus_anciennes": 1}
    fiches = client.get("/api/v1/catalogue-formations").json()
    assert fiches[0]["francais_min"] == "B2"


def test_demarche_inconnue_donne_404_et_demarche_connue_ajoute_le_calendrier(
    application: FastAPI, deux_bureaux
) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.employe.email)
    assert client.post(URL_SUGGESTIONS, json={"profil": PROFIL_B2, "code_demarche": "inconnue_x"}).status_code == 404
    rep = client.post(URL_SUGGESTIONS, json={"profil": PROFIL_B2, "code_demarche": "compte_etudes_en_france"})
    assert rep.status_code == 200
    assert isinstance(rep.json()["calendrier_demarche"], list)
