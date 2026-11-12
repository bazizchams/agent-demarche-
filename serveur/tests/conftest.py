"""Fixtures Pytest communes (uniquement des données fictives, jamais de données réelles)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependances import EN_TETE_CSRF
from app.core.chiffrement import charger_ou_creer_cle_maitresse
from app.core.config import Environnement, Parametres
from app.core.securite import hacher_mot_de_passe
from app.db.base import Base
from app.db.session import creer_fabrique_sessions, creer_moteur
from app.db.tenant import definir_tenant
from app.main import creer_application
from app.modeles.bureau import Bureau
from app.modeles.utilisateur import Role, Utilisateur
from app.services.bureaux import provisionner_bureau_et_admin

MOT_DE_PASSE_FORT = "MotDePasse!2026#Fort"
MOT_DE_PASSE_NOUVEAU = "Nouveau!2026#Solide9"


@pytest.fixture()
def parametres_test(tmp_path: Path) -> Parametres:
    chemin_db = (tmp_path / "test_bureau.db").as_posix()
    return Parametres(
        environnement=Environnement.TEST,
        url_base_donnees=f"sqlite:///{chemin_db}",
        cookie_securise=False,
        duree_session_minutes=60,
        inactivite_session_minutes=30,
        longueur_min_mot_de_passe=12,
        max_echecs_connexion=3,
        duree_verrouillage_minutes=15,
        fichier_cle_dpapi=tmp_path / "cle_maitresse.dpapi",
        dossier_stockage=tmp_path / "stockage",
        dossier_sauvegardes=tmp_path / "sauvegardes",
    )


@pytest.fixture()
def moteur_db(parametres_test: Parametres) -> Iterator[Engine]:
    moteur = creer_moteur(parametres_test.url_base_donnees)
    Base.metadata.create_all(moteur)
    try:
        yield moteur
    finally:
        moteur.dispose()


@pytest.fixture()
def fabrique_sessions(moteur_db: Engine) -> sessionmaker[Session]:
    return creer_fabrique_sessions(moteur_db)


@pytest.fixture()
def application(
    parametres_test: Parametres,
    moteur_db: Engine,
    fabrique_sessions: sessionmaker[Session],
) -> Iterator[FastAPI]:
    app = creer_application(parametres_test)
    app.state.cle_maitresse = charger_ou_creer_cle_maitresse(parametres_test)
    app.state.moteur = moteur_db
    app.state.fabrique_sessions = fabrique_sessions
    try:
        yield app
    finally:
        # Les TestClient sans `with` n'exécutent pas l'arrêt de l'application : on ferme ici les
        # navigateurs Co-Pilote (un par bureau) éventuellement ouverts par le test.
        registre = getattr(app.state, "registre_navigateur", None)
        if registre is not None:
            registre.fermer_tout()


@dataclass
class DonneesBureauTest:
    bureau: Bureau
    admin: Utilisateur
    employe: Utilisateur
    lecteur: Utilisateur


def _creer_membre(
    db: Session,
    *,
    bureau: Bureau,
    email: str,
    nom_affiche: str,
    role: Role,
    doit_changer: bool = False,
) -> Utilisateur:
    u = Utilisateur(
        tenant_id=bureau.id,
        email=email,
        nom_affiche=nom_affiche,
        empreinte_mot_de_passe=hacher_mot_de_passe(MOT_DE_PASSE_FORT),
        role=role,
        actif=True,
        doit_changer_mot_de_passe=doit_changer,
    )
    db.add(u)
    db.flush()
    return u


@pytest.fixture()
def deux_bureaux(
    fabrique_sessions: sessionmaker[Session],
    parametres_test: Parametres,
) -> tuple[DonneesBureauTest, DonneesBureauTest]:
    """Crée deux bureaux totalement distincts (A et B), chacun avec un administrateur,
    un employé et un compte en lecture seule."""
    with fabrique_sessions() as db_a:
        bureau_a, admin_a = provisionner_bureau_et_admin(
            db_a,
            nom_bureau="Bureau Alpha Fictif",
            slug="bureau-alpha",
            email_admin="admin.alpha@bureau-fictif.dz",
            nom_admin="Admin Alpha",
            mot_de_passe_admin=MOT_DE_PASSE_FORT,
            parametres=parametres_test,
        )
        definir_tenant(db_a, bureau_a.id)
        employe_a = _creer_membre(
            db_a,
            bureau=bureau_a,
            email="employe.alpha@bureau-fictif.dz",
            nom_affiche="Employé Alpha",
            role=Role.EMPLOYE,
        )
        lecteur_a = _creer_membre(
            db_a,
            bureau=bureau_a,
            email="lecteur.alpha@bureau-fictif.dz",
            nom_affiche="Lecteur Alpha",
            role=Role.LECTURE_SEULE,
        )
        db_a.commit()

    with fabrique_sessions() as db_b:
        bureau_b, admin_b = provisionner_bureau_et_admin(
            db_b,
            nom_bureau="Bureau Beta Fictif",
            slug="bureau-beta",
            email_admin="admin.beta@bureau-fictif.dz",
            nom_admin="Admin Beta",
            mot_de_passe_admin=MOT_DE_PASSE_FORT,
            parametres=parametres_test,
        )
        definir_tenant(db_b, bureau_b.id)
        employe_b = _creer_membre(
            db_b,
            bureau=bureau_b,
            email="employe.beta@bureau-fictif.dz",
            nom_affiche="Employé Beta",
            role=Role.EMPLOYE,
        )
        lecteur_b = _creer_membre(
            db_b,
            bureau=bureau_b,
            email="lecteur.beta@bureau-fictif.dz",
            nom_affiche="Lecteur Beta",
            role=Role.LECTURE_SEULE,
        )
        db_b.commit()

    return (
        DonneesBureauTest(bureau=bureau_a, admin=admin_a, employe=employe_a, lecteur=lecteur_a),
        DonneesBureauTest(bureau=bureau_b, admin=admin_b, employe=employe_b, lecteur=lecteur_b),
    )


def connecter_client(
    application: FastAPI, email: str, mot_de_passe: str = MOT_DE_PASSE_FORT
) -> tuple[TestClient, str]:
    """Ouvre un TestClient authentifié et renvoie `(client, jeton_csrf)`."""
    client = TestClient(application)
    rep = client.post(
        "/api/v1/auth/connexion",
        json={"email": email, "mot_de_passe": mot_de_passe},
    )
    assert rep.status_code == 200, rep.text
    jeton_csrf = rep.json()["jeton_csrf"]
    client.headers[EN_TETE_CSRF] = jeton_csrf
    return client, jeton_csrf
