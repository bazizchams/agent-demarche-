"""Mode lecture seule quand l'essai est terminé ou l'abonnement suspendu."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependances import EN_TETE_JETON_AGENT
from app.core.config import Parametres
from app.db.base import maintenant_utc
from app.db.tenant import definir_tenant
from app.modeles.abonnement import ForfaitAbonnement
from app.services import abonnements as service_abonnements
from app.services import acces_abonnement as service_acces
from app.services import llm
from tests.conftest import DonneesBureauTest, connecter_client

CANDIDAT = {"nom": "Essai", "prenom": "Abonnement"}


@pytest.fixture()
def blocage_actif(parametres_test: Parametres) -> Parametres:
    parametres_test.blocage_abonnement_expire = True
    return parametres_test


def _regler_abonnement(
    fabrique: sessionmaker[Session],
    bureau_id: uuid.UUID,
    *,
    statut: str,
    fin_dans_jours: int | None = None,
    modifie_il_y_a_jours: int | None = None,
    forfait: ForfaitAbonnement | None = None,
) -> None:
    with fabrique() as db:
        definir_tenant(db, bureau_id)
        abo = service_abonnements._obtenir_ou_creer_abonnement_orm(db)
        abo.statut_stripe = statut
        abo.periode_courante_fin = (
            maintenant_utc() + timedelta(days=fin_dans_jours) if fin_dans_jours is not None else None
        )
        if forfait is not None:
            abo.forfait = forfait
        if modifie_il_y_a_jours is not None:
            abo.modifie_le = maintenant_utc() - timedelta(days=modifie_il_y_a_jours)
        db.commit()


def test_sans_controle_rien_n_est_bloque(
    application: FastAPI,
    fabrique_sessions: sessionmaker[Session],
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    """Hors production (réglage par défaut), un essai expiré ne bloque rien."""
    a, _ = deux_bureaux
    _regler_abonnement(fabrique_sessions, a.bureau.id, statut="trialing", fin_dans_jours=-5)
    client, _ = connecter_client(application, a.admin.email)
    assert client.post("/api/v1/candidats", json=CANDIDAT).status_code == 201
    acces = client.get("/api/v1/abonnement/acces").json()
    assert acces["controle_actif"] is False
    assert acces["acces_complet"] is False and acces["motif"] == "essai_termine"


def test_essai_en_cours_puis_termine(
    application: FastAPI,
    blocage_actif: Parametres,
    fabrique_sessions: sessionmaker[Session],
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    a, b = deux_bureaux
    client, _ = connecter_client(application, a.admin.email)

    # Bureau tout neuf, sans abonnement enregistré : essai compté depuis sa création.
    acces = client.get("/api/v1/abonnement/acces").json()
    assert acces["controle_actif"] is True
    assert acces["acces_complet"] is True and acces["motif"] == "essai"
    assert 28 <= acces["jours_restants"] <= 30
    rep = client.post("/api/v1/candidats", json=CANDIDAT)
    assert rep.status_code == 201, rep.text
    candidat_id = rep.json()["id"]

    _regler_abonnement(fabrique_sessions, a.bureau.id, statut="trialing", fin_dans_jours=-1)

    # Écritures refusées (402), avec un message utile.
    rep = client.post("/api/v1/candidats", json={"nom": "Autre", "prenom": "Refuse"})
    assert rep.status_code == 402, rep.text
    assert rep.json()["code"] == "abonnement_requis"
    assert "lecture seule" in rep.json()["detail"]
    assert client.patch(f"/api/v1/candidats/{candidat_id}", json={"nom": "Modif"}).status_code == 402
    assert client.post("/api/v1/demarches", json={"code": "x_test", "libelle": "X"}).status_code == 402

    # Lecture toujours possible : les données restent consultables.
    assert client.get("/api/v1/candidats").status_code == 200
    assert client.get(f"/api/v1/candidats/{candidat_id}").status_code == 200
    assert client.get("/api/v1/abonnement").status_code == 200

    # Paiement et droits des candidats jamais bloqués par l'abonnement.
    rep = client.post(
        "/api/v1/abonnement/cgu/accepter",
        json={"version_cgu": blocage_actif.version_cgu_courante, "acceptation_explicite": True},
    )
    assert rep.status_code != 402, rep.text
    assert client.post(
        "/api/v1/abonnement/checkout-stripe", json={"forfait": "starter"}
    ).status_code != 402
    assert client.post(
        f"/api/v1/candidats/{candidat_id}/consentement/revoquer", json={}
    ).status_code != 402
    assert client.delete(
        f"/api/v1/candidats/{uuid.uuid4()}/suppression-definitive"
    ).status_code != 402

    # L'autre bureau n'est pas concerné.
    client_b, _ = connecter_client(application, b.admin.email)
    assert client_b.post("/api/v1/candidats", json=CANDIDAT).status_code == 201

    # La déconnexion reste possible.
    assert client.post("/api/v1/auth/deconnexion").status_code == 204


@pytest.mark.parametrize(
    ("statut", "fin", "modifie", "complet", "motif"),
    [
        ("active", -40, None, True, "actif"),  # la date ne compte pas pour un abonnement actif
        ("canceled", 10, None, False, "resilie"),
        ("past_due", 10, 1, True, "grace_impaye"),
        ("past_due", 10, 30, False, "impaye"),
        ("offert", None, None, True, "offert"),
        ("offert", -1, None, False, "offre_terminee"),
        ("etat_bizarre", 10, None, False, "statut_inconnu"),
    ],
)
def test_statuts_d_abonnement(
    application: FastAPI,
    blocage_actif: Parametres,
    fabrique_sessions: sessionmaker[Session],
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
    statut: str,
    fin: int | None,
    modifie: int | None,
    complet: bool,
    motif: str,
) -> None:
    a, _ = deux_bureaux
    _regler_abonnement(
        fabrique_sessions, a.bureau.id, statut=statut, fin_dans_jours=fin, modifie_il_y_a_jours=modifie
    )
    client, _ = connecter_client(application, a.admin.email)
    acces = client.get("/api/v1/abonnement/acces").json()
    assert (acces["acces_complet"], acces["motif"]) == (complet, motif)
    attendu = 201 if complet else 402
    assert client.post("/api/v1/candidats", json=CANDIDAT).status_code == attendu


def test_agent_local_ne_contourne_pas_la_lecture_seule(
    application: FastAPI,
    blocage_actif: Parametres,
    fabrique_sessions: sessionmaker[Session],
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.admin.email)
    rep = client.post("/api/v1/agents-locaux", json={"nom_machine": "PC-TEST-01"})
    assert rep.status_code == 201, rep.text
    client_agent = TestClient(application)
    client_agent.headers[EN_TETE_JETON_AGENT] = rep.json()["jeton_secret"]
    tache_inconnue = uuid.uuid4()

    # Abonnement valide : la demande atteint la route (tâche inconnue -> 404).
    assert client_agent.post(f"/api/v1/taches/{tache_inconnue}/demarrer").status_code == 404

    _regler_abonnement(fabrique_sessions, a.bureau.id, statut="canceled")
    assert client_agent.post(f"/api/v1/taches/{tache_inconnue}/demarrer").status_code == 402
    assert client_agent.get("/api/v1/taches").status_code == 200  # lecture toujours possible


def test_offrir_abonnement_par_l_exploitant(
    application: FastAPI,
    blocage_actif: Parametres,
    fabrique_sessions: sessionmaker[Session],
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    a, _ = deux_bureaux
    _regler_abonnement(fabrique_sessions, a.bureau.id, statut="trialing", fin_dans_jours=-3)
    client, _ = connecter_client(application, a.admin.email)
    assert client.post("/api/v1/candidats", json=CANDIDAT).status_code == 402

    with fabrique_sessions() as db:
        service_acces.offrir_abonnement(
            db, slug=a.bureau.slug, forfait=ForfaitAbonnement.ENTREPRISE, jours=None
        )

    assert client.post("/api/v1/candidats", json=CANDIDAT).status_code == 201
    acces = client.get("/api/v1/abonnement/acces").json()
    assert acces["motif"] == "offert" and acces["fin"] is None
    # Hors essai : le plafond IA redevient celui du forfait.
    assert client.get("/api/v1/ia/statut").json()["plafond_mensuel"] == llm.QUOTA_IA_MENSUEL[
        ForfaitAbonnement.ENTREPRISE
    ]


def test_plafond_ia_reduit_pendant_l_essai(
    application: FastAPI,
    fabrique_sessions: sessionmaker[Session],
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    """Un essai gratuit au forfait Entreprise ne donne pas 3000 appels payés par la plateforme."""
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.admin.email)
    _regler_abonnement(
        fabrique_sessions, a.bureau.id, statut="trialing", fin_dans_jours=20,
        forfait=ForfaitAbonnement.ENTREPRISE,
    )
    assert client.get("/api/v1/ia/statut").json()["plafond_mensuel"] == llm.QUOTA_IA_ESSAI
    _regler_abonnement(
        fabrique_sessions, a.bureau.id, statut="active", fin_dans_jours=20,
        forfait=ForfaitAbonnement.ENTREPRISE,
    )
    assert client.get("/api/v1/ia/statut").json()["plafond_mensuel"] == llm.QUOTA_IA_MENSUEL[
        ForfaitAbonnement.ENTREPRISE
    ]


def test_chemins_toujours_autorises() -> None:
    oui = [
        "/api/v1/auth/deconnexion",
        "/api/v1/auth/mot-de-passe",
        "/api/v1/abonnement/checkout-stripe",
        "/api/v1/abonnement/cgu/accepter",
        f"/api/v1/candidats/{uuid.uuid4()}/consentement/revoquer",
        f"/api/v1/candidats/{uuid.uuid4()}/suppression-definitive",
        "/api/v1/sauvegardes",
    ]
    non = [
        "/api/v1/candidats",
        f"/api/v1/candidats/{uuid.uuid4()}/consentement",
        f"/api/v1/candidats/{uuid.uuid4()}/documents",
        "/api/v1/demarches",
        "/api/v1/ia/procedures/generer",
        "/api/v1/portails/piloter-navigateur",
        "/api/v1/abonnements-pirates",
        "/api/v1/candidats/x/suppression-definitive/extra",
    ]
    assert all(service_acces.chemin_toujours_autorise(c) for c in oui)
    assert not any(service_acces.chemin_toujours_autorise(c) for c in non)
