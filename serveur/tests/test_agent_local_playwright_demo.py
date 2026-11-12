"""Tests de bout en bout (E2E) de la Phase 4 avec Playwright Chromium :
- Interface web en français (`/` et `/interface`) et désactivation automatique des pages `/demo/*` en production
- Garde-fou Règle 1 (`ErreurSoumissionFinaleInterdite`) empêchant techniquement tout clic sur le bouton final
- Scénario E2E Playwright Campus France :
  1. Pause automatique si la session portail n'est pas ouverte par l'humain (Règle 3)
  2. Pause automatique si un CAPTCHA / 2FA est visible (Règle 2)
  3. Remplissage exact sans confusion entre `#champ-nom-famille` et `#champ-prenom` (correction défaut D2)
  4. Reprise idempotente après incident sans rejouer les étapes déjà `terminee`
  5. Téléversement des pièces déchiffrées à la volée, enregistrement du brouillon, capture d'écran PNG
     de contrôle chiffrée au repos, et arrêt strict avant le bouton final (`__SOUMISSION_FINALE_CLIQUEE__ === false`)
  6. Approbation finale par un opérateur humain au Centre de validation humaine
- Scénario E2E Playwright IRCC Permis d'études Canada sur `/demo/ircc`
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from playwright.sync_api import Route, sync_playwright

from app.agent_local.config_portail import charger_config_portail
from app.agent_local.executeur_playwright import executer_tache_sur_page_playwright
from app.agent_local.garde_fous import (
    ErreurSoumissionFinaleInterdite,
    verifier_selecteur_non_interdit,
)
from app.api.dependances import EN_TETE_JETON_AGENT
from app.core.chiffrement import ENTETE_FICHIER_CHIFFRE
from app.core.config import Environnement, Parametres
from app.main import creer_application
from tests.conftest import DonneesBureauTest, connecter_client

EXEMPLE_PDF = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"

PIECES_CAMPUS_FRANCE = [
    "passeport",
    "photo_identite",
    "releve_notes_bac",
    "diplome_bac",
    "releves_notes_superieur",
    "cv",
]

PIECES_IRCC = [
    "passeport",
    "lettre_admission_dli",
    "attestation_provinciale_pal_caq",
    "preuve_financiere",
    "photo_identite",
    "formulaire_imm5645",
]


def _creer_candidat_complet(
    client: TestClient,
    *,
    nom: str,
    prenom: str,
    numero_passeport: str,
    etablissement_vise: str,
    programme_vise: str,
    fonds_disponibles_eur: int,
    types_pieces: list[str],
) -> str:
    rep_c = client.post(
        "/api/v1/candidats",
        json={
            "nom": nom,
            "prenom": prenom,
            "sexe": "F",
            "date_naissance": "2002-05-14",
            "lieu_naissance": "Oran",
            "nationalite": "Algérienne",
            "pays_residence": "Algérie",
            "email": f"{prenom.lower()}.{nom.lower()}@exemple-fictif.dz",
            "telephone": "+213550112233",
            "numero_passeport": numero_passeport,
            "date_expiration_passeport": (date.today() + timedelta(days=900)).isoformat(),
            "niveau_actuel": "Licence 3 Informatique",
            "programme_vise": programme_vise,
            "etablissement_vise": etablissement_vise,
            "fonds_disponibles_eur": fonds_disponibles_eur,
            "consentement_signe": True,
        },
    )
    assert rep_c.status_code == 201, rep_c.text
    cid = rep_c.json()["id"]

    exp_valide = (date.today() + timedelta(days=500)).isoformat()
    for idx, tp in enumerate(types_pieces):
        contenu = EXEMPLE_PDF + f"% piece-{tp}-{idx}-{nom}\n".encode("ascii")
        rep_d = client.post(
            f"/api/v1/candidats/{cid}/documents",
            data={"type_piece": tp, "date_expiration": exp_valide},
            files={"fichier": (f"{tp}.pdf", contenu, "application/pdf")},
        )
        assert rep_d.status_code == 201, rep_d.text

    return cid


def test_interface_francais_et_pages_demo_desactivees_en_production(
    application: FastAPI,
    tmp_path: Path,
) -> None:
    client = TestClient(application)

    # 1. Interface web complète en français accessible sur / et /interface
    for chemin in ("/", "/interface"):
        rep_ui = client.get(chemin)
        assert rep_ui.status_code == 200
        texte = rep_ui.text
        assert "Agent Bureau d'Études" in texte
        assert "Tableau de bord" in texte
        # Navigation refondue : entrées regroupées par tâche, sans numéros d'onglet.
        assert "Étudiants et fiches" in texte
        assert "Pièces et identifiants" in texte
        assert "Conseiller et score" in texte
        assert "Campus France" in texte
        assert "IRCC Canada" in texte
        assert "Centre de validation" in texte
        assert "Journal d'audit" in texte
        assert "Abonnement et sauvegardes" in texte

    # 2. Pages de démonstration disponibles hors production
    assert client.get("/demo/campus-france").status_code == 200
    assert client.get("/demo/ircc").status_code == 200

    # 3. En environnement PRODUCTION, les routes /demo/* ne sont pas montées (404)
    params_prod = Parametres(
        environnement=Environnement.PRODUCTION,
        url_base_donnees=f"sqlite:///{(tmp_path / 'prod.db').as_posix()}",
        cookie_securise=True,
        fichier_cle_dpapi=tmp_path / "cle_prod.dpapi",
        dossier_stockage=tmp_path / "stockage_prod",
    )
    app_prod = creer_application(params_prod)
    client_prod = TestClient(app_prod)
    assert client_prod.get("/demo/campus-france").status_code == 404
    assert client_prod.get("/demo/ircc").status_code == 404


def test_garde_fou_regle1_interdit_formellement_clic_soumission_finale(
    parametres_test: Parametres,
) -> None:
    cfg_cf = charger_config_portail(
        parametres_test.dossier_portails / "demo_campus_france.yaml"
    )
    cfg_ircc = charger_config_portail(
        parametres_test.dossier_portails / "demo_ircc.yaml"
    )

    # Le bouton d'enregistrement de brouillon est autorisé
    verifier_selecteur_non_interdit("#btn-enregistrer-brouillon", cfg_cf)
    verifier_selecteur_non_interdit("#btn-enregistrer-brouillon-ircc", cfg_ircc)

    # Tout sélecteur de soumission finale officielle lève immédiatement ErreurSoumissionFinaleInterdite
    with pytest.raises(ErreurSoumissionFinaleInterdite):
        verifier_selecteur_non_interdit("#btn-soumission-finale-officielle", cfg_cf)

    with pytest.raises(ErreurSoumissionFinaleInterdite):
        verifier_selecteur_non_interdit("#btn-soumission-finale-ircc", cfg_ircc)

    with pytest.raises(ErreurSoumissionFinaleInterdite):
        verifier_selecteur_non_interdit(
            "button[data-action='soumettre-definitivement']", cfg_cf
        )


def test_playwright_e2e_campus_france_pause_reprise_idempotente_et_arret_avant_envoi(
    application: FastAPI,
    parametres_test: Parametres,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    donnees_a, _ = deux_bureaux
    client_admin, _ = connecter_client(application, donnees_a.admin.email)

    # 1. Création d'un dossier complet Campus France et enrôlement de l'agent local du bureau
    cid = _creer_candidat_complet(
        client_admin,
        nom="BENALI",
        prenom="Yasmine",
        numero_passeport="DZ8844221",
        etablissement_vise="Sorbonne Université",
        programme_vise="Master 1 Intelligence Artificielle",
        fonds_disponibles_eur=9200,
        types_pieces=PIECES_CAMPUS_FRANCE,
    )

    rep_ag = client_admin.post(
        "/api/v1/agents-locaux",
        json={"nom_machine": "PC-Agent-Playwright-CF"},
    )
    assert rep_ag.status_code == 201, rep_ag.text
    jeton_agent = rep_ag.json()["jeton_secret"]

    client_agent = TestClient(application)
    client_agent.headers[EN_TETE_JETON_AGENT] = jeton_agent

    # 2. Création de la tâche Campus France (étape 1 'verification_prerequis_dossier' déjà terminée)
    rep_t = client_admin.post(
        "/api/v1/taches",
        json={"candidat_id": cid, "code_demarche": "campus_france"},
    )
    assert rep_t.status_code == 201, rep_t.text
    tid = rep_t.json()["id"]
    assert rep_t.json()["statut"] == "en_attente"

    cfg_cf = charger_config_portail(
        parametres_test.dossier_portails / "demo_campus_france.yaml"
    )
    client_public = TestClient(application)

    with sync_playwright() as p:
        navigateur = p.chromium.launch(headless=True)
        contexte_nav = navigateur.new_context(viewport={"width": 1280, "height": 900})
        page = contexte_nav.new_page()

        def servir_demo_fastapi(route: Route) -> None:
            chemin = route.request.url.replace("http://portail.local", "")
            rep = client_public.get(chemin)
            route.fulfill(
                status=rep.status_code,
                headers=dict(rep.headers),
                body=rep.content,
            )

        page.route("http://portail.local/**", servir_demo_fastapi)

        # =====================================================================
        # CYCLE 1 — Règle 3 : Session non ouverte par l'humain (?session_ouverte=0)
        # =====================================================================
        res_1 = executer_tache_sur_page_playwright(
            page,
            tache_id=tid,
            client_api=client_agent,
            config_portail=cfg_cf,
            url_base_portail="http://portail.local",
            parametres_url="?session_ouverte=0&captcha=0",
        )
        assert res_1.statut_final == "suspendue"
        assert res_1.motif_suspension == "action_utilisateur_portail"
        assert res_1.etapes_sautees_idempotence == []
        assert res_1.etapes_executees_dans_ce_cycle == []

        # =====================================================================
        # CYCLE 2 — Règle 2 : Session ouverte mais CAPTCHA actif (?captcha=1)
        # =====================================================================
        assert client_admin.post(f"/api/v1/taches/{tid}/reprendre").status_code == 200
        res_2 = executer_tache_sur_page_playwright(
            page,
            tache_id=tid,
            client_api=client_agent,
            config_portail=cfg_cf,
            url_base_portail="http://portail.local",
            parametres_url="?session_ouverte=1&captcha=1",
        )
        assert res_2.statut_final == "suspendue"
        assert res_2.motif_suspension == "action_utilisateur_portail"
        assert res_2.message_alerte is not None and "CAPTCHA" in res_2.message_alerte
        assert res_2.etapes_executees_dans_ce_cycle == []

        # =====================================================================
        # CYCLE 3 — Exécution des étapes 2 et 3 puis pause simulée à l'étape 4
        # (sélecteur d'upload temporairement absent pour vérifier la reprise idempotente)
        # =====================================================================
        assert client_admin.post(f"/api/v1/taches/{tid}/reprendre").status_code == 200
        page.goto(
            "http://portail.local/demo/campus-france?session_ouverte=1&captcha=0",
            wait_until="domcontentloaded",
        )
        # On retire temporairement #upload-passeport pour provoquer une pause à l'étape
        # 'saisie_cursus_et_diplomes' APRÈS que 'ouverture_session_etudes_en_france'
        # et 'saisie_informations_personnelles' ont réussi
        page.evaluate(
            """() => {
                const el = document.querySelector('#upload-passeport');
                el.setAttribute('id', 'upload-passeport-masque-temporairement');
            }"""
        )

        res_3 = executer_tache_sur_page_playwright(
            page,
            tache_id=tid,
            client_api=client_agent,
            config_portail=cfg_cf,
            url_base_portail="http://portail.local",
            naviguer_au_demarrage=False,
        )
        assert res_3.statut_final == "suspendue"
        assert res_3.motif_suspension == "selecteur_portail_introuvable"
        assert res_3.etapes_sautees_idempotence == []
        assert res_3.etapes_executees_dans_ce_cycle == [
            "ouverture_session_etudes_en_france",
            "saisie_informations_personnelles",
        ]

        # Vérification correction défaut D2 : #champ-nom-famille et #champ-prenom contiennent tous deux "nom"
        # dans leur id, mais les sélecteurs YAML exacts ont rempli chacun sans écraser l'autre !
        assert page.locator("#champ-nom-famille").input_value() == "BENALI"
        assert page.locator("#champ-prenom").input_value() == "Yasmine"
        assert page.locator("#champ-date-naissance").input_value() == "2002-05-14"
        assert page.locator("#champ-lieu-naissance").input_value() == "Oran"
        assert page.locator("#champ-numero-passeport").input_value() == "DZ8844221"

        # =====================================================================
        # CYCLE 4 — Reprise idempotente : les étapes déjà `terminee` ne sont JAMAIS rejouées,
        # seules les 3 étapes restantes s'exécutent
        # =====================================================================
        page.evaluate(
            """() => {
                const el = document.querySelector('#upload-passeport-masque-temporairement');
                el.setAttribute('id', 'upload-passeport');
            }"""
        )
        page.locator("#champ-nom-famille").fill("BENALI_TEMOIN_IDEMPOTENCE")

        assert client_admin.post(f"/api/v1/taches/{tid}/reprendre").status_code == 200
        res_4 = executer_tache_sur_page_playwright(
            page,
            tache_id=tid,
            client_api=client_agent,
            config_portail=cfg_cf,
            url_base_portail="http://portail.local",
            naviguer_au_demarrage=False,
        )
        assert res_4.statut_final == "a_valider"
        assert res_4.etapes_sautees_idempotence == [
            "ouverture_session_etudes_en_france",
            "saisie_informations_personnelles",
        ]
        assert res_4.etapes_executees_dans_ce_cycle == [
            "saisie_cursus_et_diplomes",
            "selection_formations_et_motivations",
            "controle_avant_validation_humaine",
        ]

        # Preuve d'idempotence DOM : l'étape 'saisie_informations_personnelles' n'a pas été rejouée
        assert page.locator("#champ-nom-famille").input_value() == "BENALI_TEMOIN_IDEMPOTENCE"
        # Les étapes suivantes ont rempli le cursus, les formations et téléversé les 6 pièces
        assert page.locator("#champ-niveau-actuel").input_value() == "Licence 3 Informatique"
        assert (
            page.locator("#champ-programme-vise").input_value()
            == "Master 1 Intelligence Artificielle"
        )
        assert page.locator("#champ-etablissement-vise").input_value() == "Sorbonne Université"

        nb_fichiers_joints = page.evaluate(
            """() => {
                const selecteurs = [
                    '#upload-passeport',
                    '#upload-photo-identite',
                    '#upload-releve-notes-bac',
                    '#upload-diplome-bac',
                    '#upload-releves-notes-superieur',
                    '#upload-cv'
                ];
                return selecteurs.map(s => document.querySelector(s).files.length);
            }"""
        )
        assert nb_fichiers_joints == [1, 1, 1, 1, 1, 1]

        # Le brouillon a été enregistré, mais le bouton de soumission finale n'a JAMAIS été cliqué (Règle 1)
        assert page.evaluate("window.__BROUILLON_ENREGISTRE__") is True
        assert page.evaluate("window.__SOUMISSION_FINALE_CLIQUEE__") is False

        navigateur.close()

    # 3. Vérification de la capture d'écran de contrôle chiffrée au repos et lisible via l'API
    synthese_val = client_admin.get("/api/v1/validations/en-attente").json()
    assert any(t["id"] == tid for t in synthese_val["taches_a_valider"])

    fichiers_captures = list((parametres_test.dossier_stockage / str(donnees_a.bureau.id) / "captures").glob("*.bin"))
    assert len(fichiers_captures) == 1
    assert fichiers_captures[0].read_bytes().startswith(ENTETE_FICHIER_CHIFFRE)

    rep_png = client_admin.get(f"/api/v1/taches/{tid}/capture-controle")
    assert rep_png.status_code == 200
    assert rep_png.headers["content-type"] == "image/png"
    assert rep_png.content.startswith(b"\x89PNG\r\n\x1a\n")

    # 4. Validation humaine finale par l'opérateur (Règle 1)
    rep_val = client_admin.post(
        f"/api/v1/taches/{tid}/valider",
        json={
            "confirmation_humaine_explicite": True,
            "commentaire": "Capture Playwright Campus France vérifiée, je soumets manuellement dans le navigateur.",
        },
    )
    assert rep_val.status_code == 200, rep_val.text
    assert rep_val.json()["statut"] == "terminee"


def test_playwright_e2e_ircc_remplissage_televersement_et_arret_avant_envoi(
    application: FastAPI,
    parametres_test: Parametres,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    donnees_a, _ = deux_bureaux
    client_admin, _ = connecter_client(application, donnees_a.admin.email)

    cid = _creer_candidat_complet(
        client_admin,
        nom="KHELIFI",
        prenom="Amine",
        numero_passeport="DZ9911004",
        etablissement_vise="Université de Montréal (DLI O19359011033)",
        programme_vise="Maîtrise en Génie Logiciel",
        fonds_disponibles_eur=19500,
        types_pieces=PIECES_IRCC,
    )

    rep_ag = client_admin.post(
        "/api/v1/agents-locaux",
        json={"nom_machine": "PC-Agent-Playwright-IRCC"},
    )
    assert rep_ag.status_code == 201
    client_agent = TestClient(application)
    client_agent.headers[EN_TETE_JETON_AGENT] = rep_ag.json()["jeton_secret"]

    rep_t = client_admin.post(
        "/api/v1/taches",
        json={"candidat_id": cid, "code_demarche": "ircc_permis_etudes"},
    )
    assert rep_t.status_code == 201, rep_t.text
    tid = rep_t.json()["id"]

    cfg_ircc = charger_config_portail(
        parametres_test.dossier_portails / "demo_ircc.yaml"
    )
    client_public = TestClient(application)

    with sync_playwright() as p:
        navigateur = p.chromium.launch(headless=True)
        page = navigateur.new_page(viewport={"width": 1280, "height": 900})

        def servir_demo_ircc(route: Route) -> None:
            chemin = route.request.url.replace("http://portail.local", "")
            rep = client_public.get(chemin)
            route.fulfill(
                status=rep.status_code,
                headers=dict(rep.headers),
                body=rep.content,
            )

        page.route("http://portail.local/**", servir_demo_ircc)

        res = executer_tache_sur_page_playwright(
            page,
            tache_id=tid,
            client_api=client_agent,
            config_portail=cfg_ircc,
            url_base_portail="http://portail.local",
            parametres_url="?session_ouverte=1&captcha=0",
        )
        assert res.statut_final == "a_valider"
        assert res.etapes_sautees_idempotence == []
        assert res.etapes_executees_dans_ce_cycle == [
            "ouverture_session_portail_ircc",
            "saisie_identite_et_passeport",
            "saisie_projet_etudes_dli",
            "televersement_justificatifs_ircc",
            "controle_avant_validation_humaine",
        ]

        assert page.locator("#ircc-nom-famille").input_value() == "KHELIFI"
        assert page.locator("#ircc-prenom").input_value() == "Amine"
        assert (
            page.locator("#ircc-etablissement-dli").input_value()
            == "Université de Montréal (DLI O19359011033)"
        )
        assert page.locator("#ircc-fonds-disponibles-eur").input_value() == "19500"

        nb_fichiers_ircc = page.evaluate(
            """() => {
                const selecteurs = [
                    '#ircc-upload-passeport',
                    '#ircc-upload-lettre-admission-dli',
                    '#ircc-upload-pal-caq',
                    '#ircc-upload-preuve-financiere',
                    '#ircc-upload-photo-identite',
                    '#ircc-upload-imm5645'
                ];
                return selecteurs.map(s => document.querySelector(s).files.length);
            }"""
        )
        assert nb_fichiers_ircc == [1, 1, 1, 1, 1, 1]

        # Règle 1 : brouillon enregistré mais bouton final IRCC jamais cliqué
        assert page.evaluate("window.__BROUILLON_ENREGISTRE__") is True
        assert page.evaluate("window.__SOUMISSION_FINALE_CLIQUEE__") is False

        navigateur.close()

    rep_png = client_admin.get(f"/api/v1/taches/{tid}/capture-controle")
    assert rep_png.status_code == 200
    assert rep_png.content.startswith(b"\x89PNG\r\n\x1a\n")
