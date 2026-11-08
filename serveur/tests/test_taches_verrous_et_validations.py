"""Tests de la Phase 3 :
- Machine à états persistée (`en_attente -> en_cours -> suspendue -> a_valider -> terminee / annulee / en_erreur`)
- Règle 4 : suspension automatique à la création/au démarrage si un champ ou une pièce obligatoire manque
- Verrou exclusif par dossier (`verrous_dossiers`) empêchant deux tâches de modifier le même candidat simultanément + expiration de bail
- Reprise idempotente par étape (`etapes_taches`) sans jamais rejouer les étapes déjà `terminee`
- Authentification de l'Agent Local par jeton `X-Agent-Token` (et révocation)
- Centre de validation humaine (Règle 1) : capture de contrôle chiffrée, récapitulatif chiffré,
  interdiction pour l'agent local de s'auto-valider, rejet partiel depuis une étape précise et validation humaine explicite
- Isolation multi-bureaux stricte entre Bureau A et Bureau B sur toutes les routes de la Phase 3
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependances import EN_TETE_JETON_AGENT
from app.core.chiffrement import ENTETE_FICHIER_CHIFFRE
from app.core.config import Parametres
from app.db.base import maintenant_utc
from app.db.tenant import sans_filtre_tenant
from app.modeles.tache import TacheDossier, VerrouDossier
from tests.conftest import DonneesBureauTest, connecter_client

EXEMPLE_PDF = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"
EXEMPLE_PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"


def _deposer_toutes_pieces_demarches(
    client: TestClient, candidat_id: str, types_pieces: list[str]
) -> None:
    exp_valide = (date.today() + timedelta(days=365)).isoformat()
    for idx, tp in enumerate(types_pieces):
        contenu = EXEMPLE_PDF + f"% piece-{tp}-{idx}\n".encode("ascii")
        r = client.post(
            f"/api/v1/candidats/{candidat_id}/documents",
            data={"type_piece": tp, "date_expiration": exp_valide},
            files={"fichier": (f"{tp}.pdf", contenu, "application/pdf")},
        )
        assert r.status_code == 201, r.text


def test_regle4_suspension_automatique_et_reprise_apres_completion(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    donnees_a, _ = deux_bureaux
    client_a, _ = connecter_client(application, donnees_a.employe.email)

    # 1. Création d'un candidat avec seulement nom et prénom (incomplet pour Campus France)
    rep_c = client_a.post(
        "/api/v1/candidats",
        json={"nom": "MANSOURI", "prenom": "Karim"},
    )
    assert rep_c.status_code == 201
    cid = rep_c.json()["id"]

    # 2. Création d'une tâche Campus France -> naît automatiquement SUSPENDUE (Règle 4)
    rep_t = client_a.post(
        "/api/v1/taches",
        json={"candidat_id": cid, "code_demarche": "campus_france"},
    )
    assert rep_t.status_code == 201, rep_t.text
    tache = rep_t.json()
    tid = tache["id"]
    assert tache["statut"] == "suspendue"
    assert tache["motif_suspension"] == "donnee_manquante"
    assert "date_naissance" in tache["champs_manquants"]
    assert "passeport" in tache["pieces_manquantes"]
    assert tache["etapes"][0]["code_etape"] == "verification_prerequis_dossier"
    assert tache["etapes"][0]["statut"] == "suspendue"

    # 3. Tenter de reprendre ou de démarrer tant que le dossier est incomplet -> 409 Conflit
    assert client_a.post(f"/api/v1/taches/{tid}/reprendre").status_code == 409
    assert client_a.post(f"/api/v1/taches/{tid}/demarrer").status_code == 409

    # 4. Complétion de la fiche candidat et dépôt des pièces obligatoires Campus France
    exp_valide = (date.today() + timedelta(days=400)).isoformat()
    rep_patch = client_a.patch(
        f"/api/v1/candidats/{cid}",
        json={
            "sexe": "M",
            "date_naissance": "2003-04-12",
            "lieu_naissance": "Constantine",
            "nationalite": "Algérienne",
            "pays_residence": "Algérie",
            "email": "karim.mansouri@etudiant-fictif.dz",
            "telephone": "+213 552 33 44 55",
            "numero_passeport": "DZ77665544",
            "date_expiration_passeport": exp_valide,
            "niveau_actuel": "Licence 3 Informatique",
            "programme_vise": "Master 1 Réseaux",
            "etablissement_vise": "Université Lyon 1",
            "fonds_disponibles_eur": 8500,
        },
    )
    assert rep_patch.status_code == 200

    _deposer_toutes_pieces_demarches(
        client_a,
        cid,
        [
            "passeport",
            "photo_identite",
            "releve_notes_bac",
            "diplome_bac",
            "releves_notes_superieur",
            "cv",
        ],
    )

    # 5. Reprise de la tâche : passe à `en_attente`, l'étape 1 passe à `terminee`
    rep_reprise = client_a.post(f"/api/v1/taches/{tid}/reprendre")
    assert rep_reprise.status_code == 200, rep_reprise.text
    tache_reprise = rep_reprise.json()
    assert tache_reprise["statut"] == "en_attente"
    assert tache_reprise["motif_suspension"] is None
    assert tache_reprise["champs_manquants"] == []
    assert tache_reprise["pieces_manquantes"] == []
    assert tache_reprise["etapes"][0]["statut"] == "terminee"
    assert (
        tache_reprise["prochaine_etape_a_executer"]
        == "ouverture_session_etudes_en_france"
    )


def test_verrou_exclusif_dossier_et_expiration_bail(
    application: FastAPI,
    fabrique_sessions: sessionmaker[Session],
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    donnees_a, _ = deux_bureaux
    client_a, _ = connecter_client(application, donnees_a.admin.email)

    exp_valide = (date.today() + timedelta(days=400)).isoformat()
    rep_c = client_a.post(
        "/api/v1/candidats",
        json={
            "nom": "BOUZID",
            "prenom": "Nadia",
            "sexe": "F",
            "date_naissance": "2001-09-21",
            "lieu_naissance": "Alger",
            "nationalite": "Algérienne",
            "pays_residence": "Algérie",
            "email": "nadia.bouzid@etudiant-fictif.dz",
            "telephone": "+213 553 44 55 66",
            "numero_passeport": "DZ11223344",
            "date_expiration_passeport": exp_valide,
            "niveau_actuel": "Master 1",
            "programme_vise": "Master 2 Data Science",
            "etablissement_vise": "Sorbonne Université",
            "fonds_disponibles_eur": 19000,
        },
    )
    assert rep_c.status_code == 201
    cid = rep_c.json()["id"]

    _deposer_toutes_pieces_demarches(
        client_a,
        cid,
        [
            "passeport",
            "photo_identite",
            "releve_notes_bac",
            "diplome_bac",
            "releves_notes_superieur",
            "cv",
            "lettre_admission_dli",
            "attestation_provinciale_pal_caq",
            "preuve_financiere",
            "formulaire_imm5645",
        ],
    )

    # Création de deux tâches distinctes (Campus France et IRCC) sur le même dossier candidat
    t1 = client_a.post(
        "/api/v1/taches",
        json={"candidat_id": cid, "code_demarche": "campus_france"},
    ).json()
    t2 = client_a.post(
        "/api/v1/taches",
        json={"candidat_id": cid, "code_demarche": "ircc_permis_etudes"},
    ).json()
    assert t1["statut"] == "en_attente"
    assert t2["statut"] == "en_attente"

    # Doublon d'une même démarche déjà active -> 409
    assert (
        client_a.post(
            "/api/v1/taches",
            json={"candidat_id": cid, "code_demarche": "campus_france"},
        ).status_code
        == 409
    )

    # 1. Démarrage de la tâche 1 -> acquiert le verrou exclusif sur le dossier
    rep_dem1 = client_a.post(f"/api/v1/taches/{t1['id']}/demarrer")
    assert rep_dem1.status_code == 200
    assert rep_dem1.json()["statut"] == "en_cours"
    assert rep_dem1.json()["verrou_actif"] is not None

    # 2. Tentative de démarrer la tâche 2 sur le même candidat en parallèle -> 409 Conflit
    rep_dem2_conflit = client_a.post(f"/api/v1/taches/{t2['id']}/demarrer")
    assert rep_dem2_conflit.status_code == 409

    # 3. Suspension de la tâche 1 -> libère automatiquement le verrou du dossier
    rep_susp1 = client_a.post(
        f"/api/v1/taches/{t1['id']}/suspendre",
        json={
            "motif": "action_utilisateur_portail",
            "message_alerte": "En attente d'ouverture de session par l'opérateur.",
        },
    )
    assert rep_susp1.status_code == 200
    assert rep_susp1.json()["verrou_actif"] is None

    # 4. La tâche 2 peut maintenant démarrer et acquérir le verrou
    rep_dem2_ok = client_a.post(f"/api/v1/taches/{t2['id']}/demarrer")
    assert rep_dem2_ok.status_code == 200
    assert rep_dem2_ok.json()["statut"] == "en_cours"

    # 5. Si le bail du verrou de la tâche 2 expire (ex. crash de l'agent local),
    #    une autre tâche remise en attente peut récupérer le verrou sans blocage infini
    with fabrique_sessions() as db, sans_filtre_tenant(db):
        verrou = db.query(VerrouDossier).filter_by(tache_id=uuid.UUID(t2["id"])).one()
        verrou.expire_le = maintenant_utc() - timedelta(seconds=10)
        db.commit()

    assert client_a.post(f"/api/v1/taches/{t1['id']}/reprendre").status_code == 200
    rep_dem1_apres_exp = client_a.post(f"/api/v1/taches/{t1['id']}/demarrer")
    assert rep_dem1_apres_exp.status_code == 200
    assert rep_dem1_apres_exp.json()["verrou_actif"]["tache_id"] == t1["id"]


def test_agent_local_idempotence_etapes_et_centre_validation_humaine(
    application: FastAPI,
    fabrique_sessions: sessionmaker[Session],
    parametres_test: Parametres,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    donnees_a, donnees_b = deux_bureaux
    client_admin_a, _ = connecter_client(application, donnees_a.admin.email)
    client_lecteur_a, _ = connecter_client(application, donnees_a.lecteur.email)
    client_admin_b, _ = connecter_client(application, donnees_b.admin.email)

    # 1. Enrôlement d'un Agent Local pour le Bureau A
    rep_agent = client_admin_a.post(
        "/api/v1/agents-locaux",
        json={"nom_machine": "PC-ACCUEIL-ALGER-01"},
    )
    assert rep_agent.status_code == 201, rep_agent.text
    enrolement = rep_agent.json()
    agent_id = enrolement["agent"]["id"]
    jeton_agent = enrolement["jeton_secret"]
    assert jeton_agent.startswith("be_agent_")

    # Client HTTP représentant l'Agent Local (sans cookie ni CSRF, authentifié par X-Agent-Token)
    client_agent = TestClient(application)
    client_agent.headers[EN_TETE_JETON_AGENT] = jeton_agent

    # 2. Création d'un candidat complet et d'une tâche Campus France
    exp_valide = (date.today() + timedelta(days=400)).isoformat()
    rep_c = client_admin_a.post(
        "/api/v1/candidats",
        json={
            "nom": "HAMIDI",
            "prenom": "Lina",
            "sexe": "F",
            "date_naissance": "2002-02-14",
            "lieu_naissance": "Tizi Ouzou",
            "nationalite": "Algérienne",
            "pays_residence": "Algérie",
            "email": "lina.hamidi@etudiant-fictif.dz",
            "telephone": "+213 554 66 77 88",
            "numero_passeport": "DZ55443322",
            "date_expiration_passeport": exp_valide,
            "niveau_actuel": "Licence 3",
            "programme_vise": "Master Génie Civil",
            "etablissement_vise": "INSA Toulouse",
            "fonds_disponibles_eur": 9200,
        },
    )
    cid = rep_c.json()["id"]
    _deposer_toutes_pieces_demarches(
        client_admin_a,
        cid,
        [
            "passeport",
            "photo_identite",
            "releve_notes_bac",
            "diplome_bac",
            "releves_notes_superieur",
            "cv",
        ],
    )

    rep_t = client_admin_a.post(
        "/api/v1/taches",
        json={"candidat_id": cid, "code_demarche": "campus_france"},
    )
    assert rep_t.status_code == 201
    tid = rep_t.json()["id"]

    # 3. L'Agent Local récupère les tâches en attente et démarre la tâche
    rep_liste_agent = client_agent.get(
        "/api/v1/taches", params={"statut": "en_attente"}
    )
    assert rep_liste_agent.status_code == 200
    assert rep_liste_agent.json()["total"] == 1

    rep_dem = client_agent.post(f"/api/v1/taches/{tid}/demarrer")
    assert rep_dem.status_code == 200
    assert rep_dem.json()["agent_local_id"] == agent_id
    assert (
        rep_dem.json()["prochaine_etape_a_executer"]
        == "ouverture_session_etudes_en_france"
    )

    # Battement de cœur (heartbeat)
    assert client_agent.post(f"/api/v1/taches/{tid}/battement-coeur").status_code == 200

    # 4. Exécution des étapes 2 et 3 + vérification d'idempotence
    for code_etape in (
        "ouverture_session_etudes_en_france",
        "saisie_informations_personnelles",
    ):
        r_et = client_agent.post(
            f"/api/v1/taches/{tid}/etapes/{code_etape}/terminer",
            json={
                "cle_idempotence": f"idem-{code_etape}-1",
                "detail_execution": f"Étape {code_etape} remplie pour Lina HAMIDI",
            },
        )
        assert r_et.status_code == 200, r_et.text

    # Rejouer l'appel `terminer` sur une étape déjà terminée est idempotent (ne ré-exécute pas)
    etape3_avant = next(
        e
        for e in client_agent.get(f"/api/v1/taches/{tid}").json()["etapes"]
        if e["code_etape"] == "saisie_informations_personnelles"
    )
    rep_idem = client_agent.post(
        f"/api/v1/taches/{tid}/etapes/saisie_informations_personnelles/terminer",
        json={"cle_idempotence": "idem-saisie_informations_personnelles-1"},
    )
    assert rep_idem.status_code == 200
    etape3_apres = next(
        e
        for e in rep_idem.json()["etapes"]
        if e["code_etape"] == "saisie_informations_personnelles"
    )
    assert etape3_apres["nb_tentatives"] == etape3_avant["nb_tentatives"]
    assert etape3_apres["terminee_le"] == etape3_avant["terminee_le"]

    # 5. Pause sur l'étape 4 (ex. CAPTCHA détecté — Règle 2), puis reprise :
    #    les étapes 1, 2, 3 restent `terminee` et la reprise pointe directement sur l'étape 4 !
    rep_pause = client_agent.post(
        f"/api/v1/taches/{tid}/suspendre",
        json={
            "motif": "action_utilisateur_portail",
            "code_etape": "saisie_cursus_et_diplomes",
            "message_alerte": "CAPTCHA détecté : intervention humaine requise dans le navigateur (règle 2).",
        },
    )
    assert rep_pause.status_code == 200
    assert rep_pause.json()["statut"] == "suspendue"

    # Le Centre de validation humaine remonte bien la tâche suspendue
    centre_1 = client_admin_a.get("/api/v1/validations/en-attente").json()
    assert centre_1["total_suspendues"] == 1
    assert centre_1["taches_suspendues"][0]["id"] == tid

    # Reprise humaine puis redémarrage par l'Agent Local
    assert client_admin_a.post(f"/api/v1/taches/{tid}/reprendre").status_code == 200
    rep_redem = client_agent.post(f"/api/v1/taches/{tid}/demarrer")
    assert rep_redem.status_code == 200
    assert (
        rep_redem.json()["prochaine_etape_a_executer"] == "saisie_cursus_et_diplomes"
    )
    statuts_etapes = {e["code_etape"]: e["statut"] for e in rep_redem.json()["etapes"]}
    assert statuts_etapes["verification_prerequis_dossier"] == "terminee"
    assert statuts_etapes["ouverture_session_etudes_en_france"] == "terminee"
    assert statuts_etapes["saisie_informations_personnelles"] == "terminee"

    # 6. Impossible de soumettre pour validation humaine tant que toutes les étapes ne sont pas terminées
    assert (
        client_agent.post(
            f"/api/v1/taches/{tid}/soumettre-validation",
            json={"recapitulatif_remplissage": {"etat": "partiel"}},
        ).status_code
        == 409
    )

    # 7. Fin des étapes 4, 5, 6 + dépôt de la capture d'écran de contrôle chiffrée
    for code_etape in (
        "saisie_cursus_et_diplomes",
        "selection_formations_et_motivations",
        "controle_avant_validation_humaine",
    ):
        r_et = client_agent.post(
            f"/api/v1/taches/{tid}/etapes/{code_etape}/terminer",
            json={"cle_idempotence": f"idem-{code_etape}-1"},
        )
        assert r_et.status_code == 200, r_et.text

    rep_cap = client_agent.post(
        f"/api/v1/taches/{tid}/capture-controle",
        files={"fichier": ("controle_avant_envoi.png", EXEMPLE_PNG, "image/png")},
    )
    assert rep_cap.status_code == 200
    assert rep_cap.json()["capture_controle_disponible"] is True

    rep_soum = client_agent.post(
        f"/api/v1/taches/{tid}/soumettre-validation",
        json={
            "recapitulatif_remplissage": {
                "portail": "Études en France",
                "nom_saisi": "HAMIDI",
                "prenom_saisi": "Lina",
                "formations_selectionnees": 3,
                "bouton_soumettre_clique": False,
            }
        },
    )
    assert rep_soum.status_code == 200
    assert rep_soum.json()["statut"] == "a_valider"
    assert rep_soum.json()["verrou_actif"] is None

    # Vérification en base et sur disque : récapitulatif et capture sont chiffrés en AES-256-GCM
    with fabrique_sessions() as db, sans_filtre_tenant(db):
        t_orm = db.get(TacheDossier, uuid.UUID(tid))
        assert t_orm is not None
        assert t_orm.recapitulatif_remplissage_chiffre is not None
        assert "HAMIDI" not in t_orm.recapitulatif_remplissage_chiffre
        assert t_orm.recapitulatif_remplissage_chiffre.startswith("v1:")
        chemin_cap = (
            parametres_test.dossier_stockage
            / (t_orm.chemin_capture_controle_relatif or "")
        )
        octets_cap = chemin_cap.read_bytes()
        assert octets_cap.startswith(ENTETE_FICHIER_CHIFFRE)
        assert b"PNG" not in octets_cap

    # Téléchargement déchiffré de la capture de contrôle par l'opérateur
    rep_dl_cap = client_admin_a.get(f"/api/v1/taches/{tid}/capture-controle")
    assert rep_dl_cap.status_code == 200
    assert rep_dl_cap.content == EXEMPLE_PNG

    # 8. RÈGLE 1 : L'Agent Local ne peut JAMAIS valider lui-même une tâche (401)
    assert (
        client_agent.post(
            f"/api/v1/taches/{tid}/valider",
            json={"confirmation_humaine_explicite": True},
        ).status_code
        == 401
    )
    # Le rôle lecture_seule ne peut pas non plus valider (403)
    assert (
        client_lecteur_a.post(
            f"/api/v1/taches/{tid}/valider",
            json={"confirmation_humaine_explicite": True},
        ).status_code
        == 403
    )
    # Une validation humaine avec `confirmation_humaine_explicite: False` est rejetée (422)
    assert (
        client_admin_a.post(
            f"/api/v1/taches/{tid}/valider",
            json={"confirmation_humaine_explicite": False},
        ).status_code
        == 422
    )

    # 9. Rejet partiel dans le Centre de validation humaine :
    #    l'humain demande de reprendre uniquement à partir de `selection_formations_et_motivations`
    rep_rejet = client_admin_a.post(
        f"/api/v1/taches/{tid}/rejeter-validation",
        json={
            "commentaire": "Remplacer le 3e choix de formation avant validation finale.",
            "reinitialiser_depuis_etape": "selection_formations_et_motivations",
        },
    )
    assert rep_rejet.status_code == 200, rep_rejet.text
    t_rejetee = rep_rejet.json()
    assert t_rejetee["statut"] == "suspendue"
    assert t_rejetee["motif_suspension"] == "rejet_validation_humaine"
    assert (
        t_rejetee["prochaine_etape_a_executer"]
        == "selection_formations_et_motivations"
    )
    statuts_apres_rejet = {e["code_etape"]: e["statut"] for e in t_rejetee["etapes"]}
    # Les 4 premières étapes restent `terminee`, seules les 2 dernières sont revenues à `a_faire`
    assert statuts_apres_rejet["saisie_cursus_et_diplomes"] == "terminee"
    assert statuts_apres_rejet["selection_formations_et_motivations"] == "a_faire"
    assert statuts_apres_rejet["controle_avant_validation_humaine"] == "a_faire"

    # 10. Reprise des 2 dernières étapes, soumission et validation humaine finale
    assert client_admin_a.post(f"/api/v1/taches/{tid}/reprendre").status_code == 200
    assert client_agent.post(f"/api/v1/taches/{tid}/demarrer").status_code == 200
    for code_etape in (
        "selection_formations_et_motivations",
        "controle_avant_validation_humaine",
    ):
        assert (
            client_agent.post(
                f"/api/v1/taches/{tid}/etapes/{code_etape}/terminer",
                json={"cle_idempotence": f"idem-{code_etape}-2"},
            ).status_code
            == 200
        )
    assert (
        client_agent.post(
            f"/api/v1/taches/{tid}/soumettre-validation",
            json={
                "recapitulatif_remplissage": {
                    "portail": "Études en France",
                    "formations_selectionnees": 3,
                    "choix_3_corrige": True,
                }
            },
        ).status_code
        == 200
    )

    # Isolation inter-bureaux : le Bureau B ne voit rien dans son Centre de validation et reçoit 404
    assert (
        client_admin_b.get("/api/v1/validations/en-attente").json()["total_a_valider"]
        == 0
    )
    assert client_admin_b.get(f"/api/v1/taches/{tid}").status_code == 404
    assert (
        client_admin_b.post(
            f"/api/v1/taches/{tid}/valider",
            json={"confirmation_humaine_explicite": True},
        ).status_code
        == 404
    )

    # Validation humaine explicite par l'administrateur du Bureau A
    rep_val = client_admin_a.post(
        f"/api/v1/taches/{tid}/valider",
        json={
            "confirmation_humaine_explicite": True,
            "commentaire": "Pré-remplissage vérifié, prêt pour clic final dans le navigateur.",
        },
    )
    assert rep_val.status_code == 200, rep_val.text
    t_finale = rep_val.json()
    assert t_finale["statut"] == "terminee"
    assert t_finale["terminee_le"] is not None
    assert len(t_finale["decisions_validation"]) == 2
    assert t_finale["decisions_validation"][-1]["decision"] == "approuvee"
    assert t_finale["decisions_validation"][-1]["confirmation_explicite"] is True

    # Une tâche terminée ne peut plus changer d'état (409)
    assert client_admin_a.post(f"/api/v1/taches/{tid}/annuler").status_code == 409

    # 11. Révocation de l'Agent Local -> son jeton est immédiatement bloqué (403)
    rep_rev = client_admin_a.post(f"/api/v1/agents-locaux/{agent_id}/revoquer")
    assert rep_rev.status_code == 200
    assert rep_rev.json()["actif"] is False
    assert client_agent.get("/api/v1/taches").status_code == 403
