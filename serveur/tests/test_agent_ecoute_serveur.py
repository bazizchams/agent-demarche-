"""Côté serveur de « Ouvrir sur mon PC » : réservation atomique des tâches, jeton agent, vœux servis.

Données fictives uniquement. Aucun navigateur ici (voir `test_agent_ecoute_demon.py`).
"""

from __future__ import annotations

import threading
import uuid
from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependances import EN_TETE_JETON_AGENT
from app.db.base import maintenant_utc
from app.db.tenant import definir_tenant
from app.modeles.tache import TacheDossier, VerrouDossier
from tests.conftest import DonneesBureauTest, connecter_client

MARQUEUR_MDP = "MdpCoffre-Zk93-SECRET"
MOTIVATION = "Madame, Monsieur, je candidate avec sérieux à cette formation."


def creer_candidat_avec_voeux(
    client: TestClient, *, nom: str = "Testeur", valides: int = 1, brouillons: int = 0
) -> tuple[str, list[str], list[str]]:
    rep = client.post(
        "/api/v1/candidats",
        json={"nom": nom, "prenom": "Ouvrir", "email": f"{nom.lower()}.pc@exemple-fictif.dz"},
    )
    assert rep.status_code == 201, rep.text
    candidat_id = rep.json()["id"]
    ids_valides: list[str] = []
    ids_brouillons: list[str] = []
    for i in range(valides + brouillons):
        r = client.post(
            f"/api/v1/candidats/{candidat_id}/voeux",
            json={
                "intitule": f"Master Fictif {i}",
                "etablissement": f"Université Fictive {i}",
                "niveau": "Master 1",
            },
        )
        assert r.status_code == 201, r.text
        voeu_id = r.json()["id"]
        if i < valides:
            assert client.patch(
                f"/api/v1/candidats/{candidat_id}/voeux/{voeu_id}", json={"motivation": MOTIVATION}
            ).status_code == 200
            assert client.post(f"/api/v1/candidats/{candidat_id}/voeux/{voeu_id}/valider").status_code == 200
            ids_valides.append(voeu_id)
        else:
            ids_brouillons.append(voeu_id)
    return candidat_id, ids_valides, ids_brouillons


def enroler_agent(admin: TestClient, nom: str = "PC-Test") -> tuple[str, str]:
    rep = admin.post("/api/v1/agents-locaux", json={"nom_machine": nom})
    assert rep.status_code == 201, rep.text
    return rep.json()["agent"]["id"], rep.json()["jeton_secret"]


def client_agent(application: FastAPI, jeton: str) -> TestClient:
    c = TestClient(application)
    c.headers[EN_TETE_JETON_AGENT] = jeton
    return c


def creer_tache_pc(admin: TestClient, candidat_id: str) -> Any:
    return admin.post(
        "/api/v1/taches",
        json={
            "candidat_id": candidat_id,
            "code_demarche": "campus_france",
            "action": "ajouter_voeux_panier",
        },
    )


@pytest.fixture()
def admin_a(application: FastAPI, deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest]) -> TestClient:
    client, _ = connecter_client(application, deux_bureaux[0].admin.email)
    return client


# ---------------------------------------------------------------------------
# Création de la tâche (bouton « Ouvrir sur mon PC »)
# ---------------------------------------------------------------------------


def test_creation_refusee_sans_voeu_valide(admin_a: TestClient) -> None:
    candidat_id, _, _ = creer_candidat_avec_voeux(admin_a, valides=0, brouillons=2)
    rep = creer_tache_pc(admin_a, candidat_id)
    assert rep.status_code == 422, rep.text
    assert "validé" in rep.json()["detail"]


def test_creation_en_attente_puis_doublon_refuse(admin_a: TestClient) -> None:
    candidat_id, _, _ = creer_candidat_avec_voeux(admin_a)
    rep = creer_tache_pc(admin_a, candidat_id)
    assert rep.status_code == 201, rep.text
    tache = rep.json()
    assert tache["statut"] == "en_attente"
    assert tache["action"] == "ajouter_voeux_panier"
    assert tache["agent_local_id"] is None
    assert creer_tache_pc(admin_a, candidat_id).status_code == 409


def test_action_inconnue_ou_autre_demarche_refusee(admin_a: TestClient) -> None:
    candidat_id, _, _ = creer_candidat_avec_voeux(admin_a)
    rep = admin_a.post(
        "/api/v1/taches",
        json={"candidat_id": candidat_id, "code_demarche": "campus_france", "action": "format_disque"},
    )
    assert rep.status_code == 422
    rep = admin_a.post(
        "/api/v1/taches",
        json={
            "candidat_id": candidat_id,
            "code_demarche": "ircc_permis_etudes",
            "action": "ajouter_voeux_panier",
        },
    )
    assert rep.status_code == 422


def test_une_tache_pc_ne_se_demarre_pas_a_la_main(admin_a: TestClient) -> None:
    candidat_id, _, _ = creer_candidat_avec_voeux(admin_a)
    tache_id = creer_tache_pc(admin_a, candidat_id).json()["id"]
    assert admin_a.post(f"/api/v1/taches/{tache_id}/demarrer").status_code == 409


# ---------------------------------------------------------------------------
# Jeton agent
# ---------------------------------------------------------------------------


def test_reservation_exige_un_jeton_agent(application: FastAPI, admin_a: TestClient) -> None:
    sans_jeton = TestClient(application)
    assert sans_jeton.post("/api/v1/taches/reserver-suivante").status_code == 401
    # Un humain connecté (cookie) n'est pas un agent : refusé aussi.
    assert admin_a.post("/api/v1/taches/reserver-suivante").status_code == 401
    assert client_agent(application, "be_agent_inconnu").post("/api/v1/taches/reserver-suivante").status_code == 401


def test_jeton_revoque_refuse_partout(application: FastAPI, admin_a: TestClient) -> None:
    candidat_id, _, _ = creer_candidat_avec_voeux(admin_a)
    tache_id = creer_tache_pc(admin_a, candidat_id).json()["id"]
    agent_id, jeton = enroler_agent(admin_a)
    agent = client_agent(application, jeton)
    assert agent.post("/api/v1/taches/reserver-suivante").json()["tache"]["id"] == tache_id

    assert admin_a.post(f"/api/v1/agents-locaux/{agent_id}/revoquer").status_code == 200

    assert agent.post("/api/v1/taches/reserver-suivante").status_code == 403
    assert agent.get(f"/api/v1/taches/{tache_id}/voeux-a-ajouter").status_code == 403
    assert agent.post(f"/api/v1/taches/{tache_id}/battement-coeur").status_code == 403
    assert agent.get("/api/v1/agents-locaux/moi").status_code == 403


def test_identite_agent_et_statut_en_ligne(application: FastAPI, admin_a: TestClient) -> None:
    agent_id, jeton = enroler_agent(admin_a, "PC-Compta")
    agents = admin_a.get("/api/v1/agents-locaux").json()
    assert [a["en_ligne"] for a in agents] == [False]  # jamais vu

    moi = client_agent(application, jeton).get("/api/v1/agents-locaux/moi")
    assert moi.status_code == 200
    assert moi.json()["agent_id"] == agent_id and moi.json()["nom_machine"] == "PC-Compta"
    assert admin_a.get("/api/v1/agents-locaux").json()[0]["en_ligne"] is True


# ---------------------------------------------------------------------------
# Réservation atomique
# ---------------------------------------------------------------------------


def test_reservation_rien_a_faire(application: FastAPI, admin_a: TestClient) -> None:
    _, jeton = enroler_agent(admin_a)
    rep = client_agent(application, jeton).post("/api/v1/taches/reserver-suivante")
    assert rep.status_code == 200 and rep.json() == {"tache": None}


def test_reservation_prend_la_plus_ancienne_et_la_passe_en_cours(
    application: FastAPI, admin_a: TestClient
) -> None:
    c1, _, _ = creer_candidat_avec_voeux(admin_a, nom="Premier")
    c2, _, _ = creer_candidat_avec_voeux(admin_a, nom="Second")
    t1 = creer_tache_pc(admin_a, c1).json()["id"]
    t2 = creer_tache_pc(admin_a, c2).json()["id"]
    agent_id, jeton = enroler_agent(admin_a)
    agent = client_agent(application, jeton)

    premiere = agent.post("/api/v1/taches/reserver-suivante").json()["tache"]
    assert premiere["id"] == t1 and premiere["statut"] == "en_cours"
    assert premiere["agent_local_id"] == agent_id
    assert premiere["verrou_actif"] is not None  # le dossier est verrouillé pour l'agent
    seconde = agent.post("/api/v1/taches/reserver-suivante").json()["tache"]
    assert seconde["id"] == t2
    assert agent.post("/api/v1/taches/reserver-suivante").json() == {"tache": None}


def test_reservation_filtre_sur_les_actions_connues_de_l_agent(
    application: FastAPI, admin_a: TestClient
) -> None:
    c1, _, _ = creer_candidat_avec_voeux(admin_a)
    creer_tache_pc(admin_a, c1)
    _, jeton = enroler_agent(admin_a)
    agent = client_agent(application, jeton)
    rep = agent.post("/api/v1/taches/reserver-suivante", params={"actions": ["autre_action"]})
    assert rep.json() == {"tache": None}
    rep = agent.post("/api/v1/taches/reserver-suivante", params={"actions": ["ajouter_voeux_panier"]})
    assert rep.json()["tache"] is not None


def test_reservation_atomique_une_seule_tache_prise_par_un_seul_agent(
    application: FastAPI, admin_a: TestClient
) -> None:
    """Huit agents se ruent en même temps sur UNE tâche : un seul la reçoit."""
    candidat_id, _, _ = creer_candidat_avec_voeux(admin_a)
    tache_id = creer_tache_pc(admin_a, candidat_id).json()["id"]
    jetons = [enroler_agent(admin_a, f"PC-{i}")[1] for i in range(8)]
    barriere = threading.Barrier(len(jetons))
    resultats: list[Any] = [None] * len(jetons)

    def courir(i: int) -> None:
        agent = client_agent(application, jetons[i])
        barriere.wait()
        rep = agent.post("/api/v1/taches/reserver-suivante")
        resultats[i] = (rep.status_code, rep.json())

    fils = [threading.Thread(target=courir, args=(i,)) for i in range(len(jetons))]
    for f in fils:
        f.start()
    for f in fils:
        f.join(timeout=60)

    assert all(r is not None and r[0] == 200 for r in resultats), resultats
    gagnants = [r[1]["tache"] for r in resultats if r[1]["tache"] is not None]
    assert len(gagnants) == 1 and gagnants[0]["id"] == tache_id


def test_reservation_concurrente_chaque_tache_prise_exactement_une_fois(
    application: FastAPI, admin_a: TestClient
) -> None:
    ids = []
    for i in range(6):
        c, _, _ = creer_candidat_avec_voeux(admin_a, nom=f"Cand{i}")
        ids.append(creer_tache_pc(admin_a, c).json()["id"])
    jetons = [enroler_agent(admin_a, f"PC-{i}")[1] for i in range(3)]
    prises: list[list[str]] = [[] for _ in jetons]
    erreurs: list[int] = []
    barriere = threading.Barrier(len(jetons))

    def boucler(i: int) -> None:
        agent = client_agent(application, jetons[i])
        barriere.wait()
        while True:
            rep = agent.post("/api/v1/taches/reserver-suivante")
            if rep.status_code != 200:
                erreurs.append(rep.status_code)
                return
            tache = rep.json()["tache"]
            if tache is None:
                return
            prises[i].append(tache["id"])

    fils = [threading.Thread(target=boucler, args=(i,)) for i in range(len(jetons))]
    for f in fils:
        f.start()
    for f in fils:
        f.join(timeout=60)

    assert erreurs == []
    toutes = [t for liste in prises for t in liste]
    assert sorted(toutes) == sorted(ids)  # aucune perdue, aucun doublon


def test_deux_bureaux_ne_se_voient_pas(
    application: FastAPI, deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest], admin_a: TestClient
) -> None:
    candidat_id, _, _ = creer_candidat_avec_voeux(admin_a)
    tache_id = creer_tache_pc(admin_a, candidat_id).json()["id"]
    admin_b, _ = connecter_client(application, deux_bureaux[1].admin.email)
    _, jeton_b = enroler_agent(admin_b, "PC-Beta")
    agent_b = client_agent(application, jeton_b)
    assert agent_b.post("/api/v1/taches/reserver-suivante").json() == {"tache": None}
    assert agent_b.get(f"/api/v1/taches/{tache_id}/voeux-a-ajouter").status_code == 404


def test_tache_abandonnee_par_un_agent_disparu_est_reprise_par_un_autre(
    application: FastAPI,
    admin_a: TestClient,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
    fabrique_sessions: sessionmaker[Session],
) -> None:
    candidat_id, _, _ = creer_candidat_avec_voeux(admin_a)
    tache_id = creer_tache_pc(admin_a, candidat_id).json()["id"]
    id1, jeton1 = enroler_agent(admin_a, "PC-1")
    id2, jeton2 = enroler_agent(admin_a, "PC-2")
    a1, a2 = client_agent(application, jeton1), client_agent(application, jeton2)
    assert a1.post("/api/v1/taches/reserver-suivante").json()["tache"]["agent_local_id"] == id1
    # Tant que le battement de cœur est à jour, l'agent 2 ne prend rien.
    assert a2.post("/api/v1/taches/reserver-suivante").json() == {"tache": None}

    with fabrique_sessions() as db:  # le PC 1 s'éteint : son verrou expire sans battement de cœur
        definir_tenant(db, deux_bureaux[0].bureau.id)
        for verrou in db.query(VerrouDossier).all():
            verrou.expire_le = maintenant_utc() - timedelta(seconds=5)
        for tache in db.query(TacheDossier).all():  # réservée il y a longtemps (hors délai de grâce)
            tache.demarree_le = maintenant_utc() - timedelta(hours=2)
        db.commit()

    reprise = a2.post("/api/v1/taches/reserver-suivante").json()["tache"]
    assert reprise["id"] == tache_id and reprise["agent_local_id"] == id2
    # L'ancien agent n'a plus aucun droit sur la tâche.
    assert a1.get(f"/api/v1/taches/{tache_id}/voeux-a-ajouter").status_code == 403


# ---------------------------------------------------------------------------
# Vœux servis (validés uniquement) et règles R1 / R3
# ---------------------------------------------------------------------------


def test_seuls_les_voeux_valides_sont_servis_a_l_agent_detenteur(
    application: FastAPI, admin_a: TestClient
) -> None:
    candidat_id, valides, brouillons = creer_candidat_avec_voeux(admin_a, valides=2, brouillons=1)
    tache_id = creer_tache_pc(admin_a, candidat_id).json()["id"]
    _, jeton = enroler_agent(admin_a)
    _, jeton_autre = enroler_agent(admin_a, "PC-Autre")
    agent, autre = client_agent(application, jeton), client_agent(application, jeton_autre)

    # Pas encore réservée : rien n'est communiqué, même à un agent enrôlé.
    assert agent.get(f"/api/v1/taches/{tache_id}/voeux-a-ajouter").status_code == 403
    assert agent.post("/api/v1/taches/reserver-suivante").json()["tache"]["id"] == tache_id
    # Un autre agent du même bureau, qui ne détient pas la tâche, ne reçoit rien non plus.
    assert autre.get(f"/api/v1/taches/{tache_id}/voeux-a-ajouter").status_code == 403

    rep = agent.get(f"/api/v1/taches/{tache_id}/voeux-a-ajouter")
    assert rep.status_code == 200, rep.text
    servis = rep.json()["voeux"]
    assert sorted(v["voeu_id"] for v in servis) == sorted(valides)
    assert brouillons[0] not in {v["voeu_id"] for v in servis}
    assert all(v["motivation"] == MOTIVATION for v in servis)
    # Pas de statut ni d'identifiant de portail : uniquement ce qu'il faut pour saisir le vœu.
    assert set(servis[0]) == {"voeu_id", "rang", "intitule", "etablissement", "niveau", "voie", "motivation"}


def test_un_voeu_repasse_en_brouillon_n_est_plus_servi(application: FastAPI, admin_a: TestClient) -> None:
    candidat_id, valides, _ = creer_candidat_avec_voeux(admin_a, valides=2)
    tache_id = creer_tache_pc(admin_a, candidat_id).json()["id"]
    _, jeton = enroler_agent(admin_a)
    agent = client_agent(application, jeton)
    agent.post("/api/v1/taches/reserver-suivante")
    # L'opérateur modifie la lettre du vœu 1 : il repasse en brouillon (à revalider).
    r = admin_a.patch(
        f"/api/v1/candidats/{candidat_id}/voeux/{valides[0]}", json={"motivation": MOTIVATION + " Modifiée."}
    )
    assert r.status_code == 200
    ids = {v["voeu_id"] for v in agent.get(f"/api/v1/taches/{tache_id}/voeux-a-ajouter").json()["voeux"]}
    assert ids == {valides[1]}  # modifié => brouillon => plus jamais servi sans revalidation humaine


def test_r3_aucun_mot_de_passe_du_coffre_ne_transite_vers_l_agent(
    application: FastAPI, admin_a: TestClient
) -> None:
    candidat_id, _, _ = creer_candidat_avec_voeux(admin_a)
    rep = admin_a.put(
        f"/api/v1/candidats/{candidat_id}/coffre/etudes_en_france",
        json={"identifiant": "id-fictif-42", "mot_de_passe": MARQUEUR_MDP, "consentement": True},
    )
    assert rep.status_code == 200, rep.text
    tache_id = creer_tache_pc(admin_a, candidat_id).json()["id"]
    _, jeton = enroler_agent(admin_a)
    agent = client_agent(application, jeton)

    reponses = [
        agent.post("/api/v1/taches/reserver-suivante"),
        agent.get(f"/api/v1/taches/{tache_id}/voeux-a-ajouter"),
        agent.get(f"/api/v1/taches/{tache_id}"),
        agent.get("/api/v1/taches"),
        agent.get("/api/v1/agents-locaux/moi"),
    ]
    for r in reponses:
        assert r.status_code == 200, r.text
        assert MARQUEUR_MDP not in r.text and "id-fictif-42" not in r.text
    # Le coffre n'offre aucune route de lecture à l'agent : statut seulement, et pas avec son jeton.
    assert agent.get(f"/api/v1/candidats/{candidat_id}/coffre/etudes_en_france").status_code == 401


def test_r1_l_agent_ne_peut_jamais_valider_ni_terminer(application: FastAPI, admin_a: TestClient) -> None:
    candidat_id, _, _ = creer_candidat_avec_voeux(admin_a)
    tache_id = creer_tache_pc(admin_a, candidat_id).json()["id"]
    _, jeton = enroler_agent(admin_a)
    agent = client_agent(application, jeton)
    agent.post("/api/v1/taches/reserver-suivante")

    for chemin, corps in (
        (f"/api/v1/taches/{tache_id}/valider", {"confirmation_humaine_explicite": True}),
        (f"/api/v1/taches/{tache_id}/rejeter-validation", {"commentaire": "non"}),
        (f"/api/v1/taches/{tache_id}/annuler", None),
        (f"/api/v1/taches/{tache_id}/reprendre", None),
    ):
        rep = agent.post(chemin, json=corps) if corps else agent.post(chemin)
        assert rep.status_code in (401, 403), (chemin, rep.status_code)
    assert admin_a.get(f"/api/v1/taches/{tache_id}").json()["statut"] == "en_cours"

    # Valider une tâche encore « en cours » est refusé aussi à l'humain (état a_valider requis).
    rep = admin_a.post(f"/api/v1/taches/{tache_id}/valider", json={"confirmation_humaine_explicite": True})
    assert rep.status_code == 409


def test_r2_suspension_par_l_agent_puis_reprise_humaine(application: FastAPI, admin_a: TestClient) -> None:
    candidat_id, _, _ = creer_candidat_avec_voeux(admin_a)
    tache_id = creer_tache_pc(admin_a, candidat_id).json()["id"]
    agent_id, jeton = enroler_agent(admin_a)
    agent = client_agent(application, jeton)
    agent.post("/api/v1/taches/reserver-suivante")

    rep = agent.post(
        f"/api/v1/taches/{tache_id}/suspendre",
        json={
            "motif": "action_utilisateur_portail",
            "message_alerte": "CAPTCHA détecté : à résoudre dans la fenêtre ouverte sur votre PC.",
        },
    )
    assert rep.status_code == 200, rep.text
    assert rep.json()["statut"] == "suspendue" and rep.json()["verrou_actif"] is None

    # Un agent ne reprend pas lui-même : seule la reprise humaine remet la tâche en attente.
    assert agent.post(f"/api/v1/taches/{tache_id}/reprendre").status_code in (401, 403)
    reprise = admin_a.post(f"/api/v1/taches/{tache_id}/reprendre")
    assert reprise.status_code == 200, reprise.text
    assert reprise.json()["statut"] == "en_attente" and reprise.json()["agent_local_id"] is None
    assert agent.post("/api/v1/taches/reserver-suivante").json()["tache"]["id"] == tache_id


def test_tache_visible_dans_la_liste_avec_son_action(application: FastAPI, admin_a: TestClient) -> None:
    candidat_id, _, _ = creer_candidat_avec_voeux(admin_a)
    creer_tache_pc(admin_a, candidat_id)
    liste = admin_a.get("/api/v1/taches", params={"candidat_id": candidat_id}).json()
    assert [t["action"] for t in liste["elements"]] == ["ajouter_voeux_panier"]
    assert uuid.UUID(liste["elements"][0]["id"])


def test_signalement_d_erreur_par_l_agent_et_reprise(application: FastAPI, admin_a: TestClient) -> None:
    candidat_id, _, _ = creer_candidat_avec_voeux(admin_a)
    tache_id = creer_tache_pc(admin_a, candidat_id).json()["id"]
    _, jeton = enroler_agent(admin_a)
    agent = client_agent(application, jeton)
    agent.post("/api/v1/taches/reserver-suivante")
    rep = agent.post(f"/api/v1/taches/{tache_id}/erreur", json={"message_erreur": "Erreur de l'agent local (RuntimeError)."})
    assert rep.status_code == 200, rep.text
    assert rep.json()["statut"] == "en_erreur" and rep.json()["verrou_actif"] is None
    assert admin_a.post(f"/api/v1/taches/{tache_id}/reprendre").json()["statut"] == "en_attente"


def test_un_autre_agent_ne_peut_pas_agir_sur_la_tache_reservee(application: FastAPI, admin_a: TestClient) -> None:
    candidat_id, _, _ = creer_candidat_avec_voeux(admin_a)
    tache_id = creer_tache_pc(admin_a, candidat_id).json()["id"]
    _, jeton1 = enroler_agent(admin_a, "PC-1")
    _, jeton2 = enroler_agent(admin_a, "PC-2")
    a1, a2 = client_agent(application, jeton1), client_agent(application, jeton2)
    a1.post("/api/v1/taches/reserver-suivante")
    for chemin, corps in (
        ("battement-coeur", None),
        ("suspendre", {"motif": "autre", "message_alerte": "tentative d'un autre agent"}),
        ("erreur", {"message_erreur": "tentative d'un autre agent"}),
        ("soumettre-validation", {"recapitulatif_remplissage": {}}),
    ):
        rep = a2.post(f"/api/v1/taches/{tache_id}/{chemin}", json=corps) if corps else a2.post(f"/api/v1/taches/{tache_id}/{chemin}")
        assert rep.status_code == 403, (chemin, rep.status_code, rep.text)
    assert admin_a.get(f"/api/v1/taches/{tache_id}").json()["statut"] == "en_cours"


def test_tache_fraichement_reservee_n_est_jamais_liberee_meme_sans_verrou(
    application: FastAPI,
    admin_a: TestClient,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
    fabrique_sessions: sessionmaker[Session],
) -> None:
    """Régression : entre la réservation et la pose du verrou, un autre agent ne doit pas la reprendre."""
    candidat_id, _, _ = creer_candidat_avec_voeux(admin_a)
    creer_tache_pc(admin_a, candidat_id)
    _, jeton1 = enroler_agent(admin_a, "PC-1")
    _, jeton2 = enroler_agent(admin_a, "PC-2")
    a1, a2 = client_agent(application, jeton1), client_agent(application, jeton2)
    assert a1.post("/api/v1/taches/reserver-suivante").json()["tache"] is not None
    with fabrique_sessions() as db:
        definir_tenant(db, deux_bureaux[0].bureau.id)
        for verrou in db.query(VerrouDossier).all():
            db.delete(verrou)
        db.commit()
    assert a2.post("/api/v1/taches/reserver-suivante").json() == {"tache": None}
