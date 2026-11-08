"""Tests d'authentification, de sécurité des sessions, de CSRF et des rôles."""

from __future__ import annotations

from datetime import timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependances import EN_TETE_CSRF
from app.db.tenant import sans_filtre_tenant
from app.modeles.bureau import Bureau
from app.modeles.session_utilisateur import SessionUtilisateur
from tests.conftest import (
    MOT_DE_PASSE_FORT,
    MOT_DE_PASSE_NOUVEAU,
    DonneesBureauTest,
    connecter_client,
)


def test_connexion_deconnexion_et_protection_csrf(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    donnees_a, _ = deux_bureaux
    client, jeton_csrf = connecter_client(application, donnees_a.admin.email)
    rep_sante = client.get("/api/v1/sante")
    assert rep_sante.status_code == 200
    assert rep_sante.json() == {"statut": "ok"}
    assert rep_sante.headers["X-Content-Type-Options"] == "nosniff"
    assert rep_sante.headers["X-Frame-Options"] == "DENY"
    assert rep_sante.headers["Cache-Control"] == "no-store"

    # Sans en-tête CSRF, toute opération mutante est refusée (403).
    del client.headers[EN_TETE_CSRF]
    rep_sans_csrf = client.patch("/api/v1/bureau", json={"nom": "Sans CSRF"})
    assert rep_sans_csrf.status_code == 403

    # Avec un faux jeton CSRF, refusée également.
    client.headers[EN_TETE_CSRF] = "jeton_invalide"
    rep_faux_csrf = client.patch("/api/v1/bureau", json={"nom": "Faux CSRF"})
    assert rep_faux_csrf.status_code == 403

    # Avec le bon jeton CSRF, l'opération réussit puis la déconnexion révoque la session.
    client.headers[EN_TETE_CSRF] = jeton_csrf
    rep_deconnexion = client.post("/api/v1/auth/deconnexion")
    assert rep_deconnexion.status_code == 204

    rep_apres = client.get("/api/v1/auth/moi")
    assert rep_apres.status_code == 401


def test_verrouillage_apres_echecs_consecutifs(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    donnees_a, _ = deux_bureaux
    client = TestClient(application)

    # max_echecs_connexion = 3 dans la configuration de test.
    for _ in range(3):
        rep = client.post(
            "/api/v1/auth/connexion",
            json={"email": donnees_a.employe.email, "mot_de_passe": "MauvaisMotDePasse!1"},
        )
        assert rep.status_code == 401

    # Même avec le bon mot de passe, le compte verrouillé est refusé.
    rep_verrouille = client.post(
        "/api/v1/auth/connexion",
        json={"email": donnees_a.employe.email, "mot_de_passe": MOT_DE_PASSE_FORT},
    )
    assert rep_verrouille.status_code == 401


def test_expiration_par_inactivite(
    application: FastAPI,
    fabrique_sessions: sessionmaker[Session],
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    donnees_a, _ = deux_bureaux
    client, _ = connecter_client(application, donnees_a.employe.email)

    with fabrique_sessions() as db, sans_filtre_tenant(db):
        sess = db.query(SessionUtilisateur).filter_by(
            utilisateur_id=donnees_a.employe.id
        ).one()
        sess.derniere_activite_le = sess.derniere_activite_le - timedelta(minutes=31)
        db.commit()

    rep = client.get("/api/v1/bureau")
    assert rep.status_code == 401


def test_mot_de_passe_temporaire_bloque_tout_sauf_changement(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    donnees_a, _ = deux_bureaux
    client_admin, _ = connecter_client(application, donnees_a.admin.email)

    rep_creation = client_admin.post(
        "/api/v1/utilisateurs",
        json={
            "email": "nouveau.membre@bureau-fictif.dz",
            "nom_affiche": "Nouveau Membre",
            "role": "employe",
            "mot_de_passe_temporaire": MOT_DE_PASSE_FORT,
        },
    )
    assert rep_creation.status_code == 201
    assert rep_creation.json()["doit_changer_mot_de_passe"] is True

    client_nouveau, _ = connecter_client(application, "nouveau.membre@bureau-fictif.dz")

    # Toute route métier est bloquée tant que le mot de passe temporaire n'est pas changé.
    assert client_nouveau.get("/api/v1/bureau").status_code == 403

    # Le changement de mot de passe vers un mot de passe trop faible est refusé (422).
    rep_faible = client_nouveau.post(
        "/api/v1/auth/mot-de-passe",
        json={
            "mot_de_passe_actuel": MOT_DE_PASSE_FORT,
            "nouveau_mot_de_passe": "tropcourt",
        },
    )
    assert rep_faible.status_code == 422

    # Le changement vers un mot de passe robuste débloque le compte.
    rep_ok = client_nouveau.post(
        "/api/v1/auth/mot-de-passe",
        json={
            "mot_de_passe_actuel": MOT_DE_PASSE_FORT,
            "nouveau_mot_de_passe": MOT_DE_PASSE_NOUVEAU,
        },
    )
    assert rep_ok.status_code == 204
    assert client_nouveau.get("/api/v1/bureau").status_code == 200


def test_matrice_des_roles_et_protection_dernier_administrateur(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    donnees_a, _ = deux_bureaux
    client_employe, _ = connecter_client(application, donnees_a.employe.email)
    client_lecteur, _ = connecter_client(application, donnees_a.lecteur.email)
    client_admin, _ = connecter_client(application, donnees_a.admin.email)

    # Employé et lecture seule peuvent consulter les infos du bureau, mais pas le renommer
    # ni gérer les utilisateurs, ni lire le journal d'audit.
    for client_non_admin in (client_employe, client_lecteur):
        assert client_non_admin.get("/api/v1/bureau").status_code == 200
        assert client_non_admin.patch("/api/v1/bureau", json={"nom": "Interdit"}).status_code == 403
        assert client_non_admin.get("/api/v1/utilisateurs").status_code == 403
        assert client_non_admin.get("/api/v1/audit").status_code == 403

    # L'administrateur ne peut pas se rétrograder ni se désactiver s'il est le seul admin actif.
    rep_retro = client_admin.patch(
        f"/api/v1/utilisateurs/{donnees_a.admin.id}",
        json={"role": "employe"},
    )
    assert rep_retro.status_code == 409

    rep_desact = client_admin.patch(
        f"/api/v1/utilisateurs/{donnees_a.admin.id}",
        json={"actif": False},
    )
    assert rep_desact.status_code == 409


def test_suspension_abonnement_bureau_bloque_sessions_existantes(
    application: FastAPI,
    fabrique_sessions: sessionmaker[Session],
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    donnees_a, _ = deux_bureaux
    client_a, _ = connecter_client(application, donnees_a.admin.email)
    assert client_a.get("/api/v1/bureau").status_code == 200

    with fabrique_sessions() as db, sans_filtre_tenant(db):
        bureau = db.get(Bureau, donnees_a.bureau.id)
        assert bureau is not None
        bureau.actif = False
        db.commit()

    assert client_a.get("/api/v1/bureau").status_code == 403


def test_cli_provisionnement_et_liste_bureaux(
    parametres_test,
    moteur_db,
    monkeypatch,
    capsys,
) -> None:
    from app import cli

    monkeypatch.setattr(cli, "obtenir_parametres", lambda: parametres_test)
    code_creation = cli.main(
        [
            "creer-bureau",
            "--nom",
            "Bureau Oran Test",
            "--slug",
            "bureau-oran",
            "--email-admin",
            "admin.oran@bureau-fictif.dz",
            "--nom-admin",
            "Admin Oran",
            "--mot-de-passe",
            MOT_DE_PASSE_FORT,
        ]
    )
    assert code_creation == 0

    code_doublon = cli.main(
        [
            "creer-bureau",
            "--nom",
            "Bureau Oran Bis",
            "--slug",
            "bureau-oran",
            "--email-admin",
            "autre@bureau-fictif.dz",
            "--nom-admin",
            "Autre",
            "--mot-de-passe",
            MOT_DE_PASSE_FORT,
        ]
    )
    assert code_doublon == 1

    code_liste = cli.main(["lister-bureaux"])
    assert code_liste == 0
    sortie = capsys.readouterr().out
    assert "bureau-oran" in sortie

