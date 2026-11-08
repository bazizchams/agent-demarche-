"""Tests de la Phase 5 — Modules séparés Campus France & IRCC pour portails réels :
- Inspection des portails YAML (`GET /api/v1/portails`), statuts Règle 6 (`non testé` par défaut
  pour les portails réels, `testé sur page de démo` pour les pages de démo) et homologation
  réservée exclusivement à l'administrateur humain du bureau (`POST /api/v1/portails/{code}/valider-portail-reel`)
- Vérification préalable des URLs officielles et blocage des domaines non autorisés ou HTTP non chiffré (correction défaut D8)
- Module dédié `ModulePortailCampusFrance` (`config/portails/campus_france_reel.yaml`) :
  diagnostic en lecture seule, navigation par onglets, pré-remplissage, téléversement des 6 pièces,
  captures d'écran PNG de contrôle à chaque étape et arrêt strict avant le bouton final
- Module dédié `ModulePortailIRCCCanada` (`config/portails/ircc_reel.yaml` — correction défaut D7) :
  diagnostic en lecture seule, navigation par étapes, pré-remplissage DLI + fonds, téléversement des 6 pièces
  (dont LAP/PAL ou CAQ et IMM 5645), captures d'écran PNG de contrôle et arrêt strict avant signature/transmission
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from playwright.sync_api import Route, sync_playwright

from app.agent_local.config_portail import charger_config_portail
from app.agent_local.garde_fous import ErreurSoumissionFinaleInterdite
from app.agent_local.portails import (
    ModulePortailCampusFrance,
    ModulePortailIRCCCanada,
    verifier_url_officielle_portail,
)
from app.api.dependances import EN_TETE_JETON_AGENT
from app.core.config import Parametres
from tests.conftest import DonneesBureauTest, connecter_client
from tests.test_agent_local_playwright_demo import (
    PIECES_CAMPUS_FRANCE,
    PIECES_IRCC,
    _creer_candidat_complet,
)

HTML_SIMULATION_PORTAIL_EEF = """<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8" /><title>Études en France</title></head>
<body>
  <div id="bandeau-identite-candidat">Connecté — Dossier DZ</div>
  <nav>
    <button id="onglet-informations-personnelles-eef" type="button">Rubrique Identité</button>
    <button id="onglet-cursus-diplomes-eef" type="button">Rubrique Cursus</button>
    <button id="onglet-panier-formations-eef" type="button">Rubrique Formations</button>
  </nav>

  <section>
    <input id="eef-nom-famille" type="text" />
    <input id="eef-prenom-candidat" type="text" />
    <select id="eef-civilite-sexe"><option value="">-</option><option value="F">F</option><option value="M">M</option></select>
    <input id="eef-date-naissance" type="date" />
    <input id="eef-ville-naissance" type="text" />
    <input id="eef-nationalite" type="text" />
    <input id="eef-pays-residence" type="text" />
    <input id="eef-email-contact" type="email" />
    <input id="eef-telephone-mobile" type="tel" />
    <input id="eef-numero-piece-identite" type="text" />
    <input id="eef-date-validite-piece" type="date" />
  </section>

  <section>
    <input id="eef-dernier-niveau-etudes" type="text" />
    <input id="eef-upload-passeport" type="file" />
    <input id="eef-upload-photo-identite" type="file" />
    <input id="eef-upload-releve-bac" type="file" />
    <input id="eef-upload-diplome-bac" type="file" />
    <input id="eef-upload-releves-superieur" type="file" />
    <input id="eef-upload-cv" type="file" />
  </section>

  <section>
    <input id="eef-intitule-formation-visee" type="text" />
    <input id="eef-etablissement-accueil" type="text" />
  </section>

  <button id="btn-enregistrer-rubrique-eef" type="button">Enregistrer la rubrique</button>
  <div id="temoin-rubriques-completes-eef" style="display:none;">Rubriques enregistrées</div>

  <button id="btn-soumettre-dossier-eef" data-action-officielle="soumettre-dossier-eef" type="button">
    Soumettre le dossier
  </button>

  <script>
    window.__ONGLETS_CLIQUES__ = [];
    window.__EEF_SOUMIS__ = false;
    ['onglet-informations-personnelles-eef', 'onglet-cursus-diplomes-eef', 'onglet-panier-formations-eef'].forEach(id => {
      document.getElementById(id).addEventListener('click', () => window.__ONGLETS_CLIQUES__.push(id));
    });
    document.getElementById('btn-enregistrer-rubrique-eef').addEventListener('click', () => {
      document.getElementById('temoin-rubriques-completes-eef').style.display = 'block';
    });
    document.getElementById('btn-soumettre-dossier-eef').addEventListener('click', () => {
      window.__EEF_SOUMIS__ = true;
    });
  </script>
</body>
</html>"""

HTML_SIMULATION_PORTAIL_IRCC = """<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8" /><title>Portail IRCC Permis d'études</title></head>
<body>
  <div id="ircc-banniere-compte-actif">Session IRCC ouverte par l'opérateur</div>
  <nav>
    <button id="etape-ircc-identite-passeport" type="button">Étape Identité</button>
    <button id="etape-ircc-etudes-dli-fonds" type="button">Étape DLI &amp; Fonds</button>
    <button id="etape-ircc-pieces-justificatives" type="button">Étape Justificatifs</button>
  </nav>

  <section>
    <input id="ircc-reel-nom-famille" type="text" />
    <input id="ircc-reel-prenom" type="text" />
    <select id="ircc-reel-sexe"><option value="">-</option><option value="F">F</option><option value="M">M</option></select>
    <input id="ircc-reel-date-naissance" type="date" />
    <input id="ircc-reel-ville-naissance" type="text" />
    <input id="ircc-reel-citoyennete" type="text" />
    <input id="ircc-reel-pays-residence" type="text" />
    <input id="ircc-reel-courriel" type="email" />
    <input id="ircc-reel-telephone" type="tel" />
    <input id="ircc-reel-numero-passeport" type="text" />
    <input id="ircc-reel-expiration-passeport" type="date" />
  </section>

  <section>
    <input id="ircc-reel-etablissement-dli" type="text" />
    <input id="ircc-reel-programme-etudes" type="text" />
    <input id="ircc-reel-fonds-disponibles-eur" type="number" />
  </section>

  <section>
    <input id="ircc-reel-upload-passeport" type="file" />
    <input id="ircc-reel-upload-loa-dli" type="file" />
    <input id="ircc-reel-upload-pal-caq" type="file" />
    <input id="ircc-reel-upload-preuve-fonds" type="file" />
    <input id="ircc-reel-upload-photo" type="file" />
    <input id="ircc-reel-upload-imm5645" type="file" />
  </section>

  <button id="btn-ircc-sauvegarder-demande" type="button">Sauvegarder la demande</button>
  <div id="banniere-ircc-brouillon-pret" style="display:none;">Demande sauvegardée</div>

  <button id="btn-ircc-transmettre-et-payer" type="button">Transmettre et payer</button>
  <button id="btn-ircc-signature-electronique-finale" type="button">Signature électronique finale</button>

  <script>
    window.__ETAPES_IRCC_CLIQUEES__ = [];
    window.__IRCC_TRANSMIS__ = false;
    ['etape-ircc-identite-passeport', 'etape-ircc-etudes-dli-fonds', 'etape-ircc-pieces-justificatives'].forEach(id => {
      document.getElementById(id).addEventListener('click', () => window.__ETAPES_IRCC_CLIQUEES__.push(id));
    });
    document.getElementById('btn-ircc-sauvegarder-demande').addEventListener('click', () => {
      document.getElementById('banniere-ircc-brouillon-pret').style.display = 'block';
    });
    document.getElementById('btn-ircc-transmettre-et-payer').addEventListener('click', () => {
      window.__IRCC_TRANSMIS__ = true;
    });
    document.getElementById('btn-ircc-signature-electronique-finale').addEventListener('click', () => {
      window.__IRCC_TRANSMIS__ = true;
    });
  </script>
</body>
</html>"""


def test_api_portails_statuts_regle6_verification_url_et_homologation_admin_uniquement(
    application: FastAPI,
    parametres_test: Parametres,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    donnees_a, donnees_b = deux_bureaux
    client_admin_a, _ = connecter_client(application, donnees_a.admin.email)
    client_employe_a, _ = connecter_client(application, donnees_a.employe.email)
    client_admin_b, _ = connecter_client(application, donnees_b.admin.email)

    # 1. Liste initiale des portails : démo = 'testé sur page de démo', réel = 'non testé' (Règle 6)
    rep_liste = client_admin_a.get("/api/v1/portails")
    assert rep_liste.status_code == 200
    par_code = {p["code_portail"]: p for p in rep_liste.json()}
    assert set(par_code.keys()) >= {
        "demo_campus_france",
        "demo_ircc",
        "campus_france_reel",
        "ircc_reel",
    }
    assert par_code["demo_campus_france"]["statut_test_regle6"] == "testé sur page de démo"
    assert par_code["demo_ircc"]["statut_test_regle6"] == "testé sur page de démo"
    assert par_code["campus_france_reel"]["statut_test_regle6"] == "non testé"
    assert par_code["ircc_reel"]["statut_test_regle6"] == "non testé"

    # 2. Vérification d'URL officielle et rejet des domaines non autorisés ou non HTTPS (défaut D8)
    for code_reel in ("campus_france_reel", "ircc_reel"):
        rep_u = client_admin_a.get(f"/api/v1/portails/{code_reel}/verifier-url")
        assert rep_u.status_code == 200
        assert rep_u.json()["protocole_https_valide"] is True
        assert rep_u.json()["domaine_autorise"] is True

    cfg_cf_reel = charger_config_portail(
        parametres_test.dossier_portails / "campus_france_reel.yaml"
    )
    res_http = verifier_url_officielle_portail(
        cfg_cf_reel, url_surcharge="http://pastel.diplomatie.gouv.fr/etudesenfrance"
    )
    assert res_http.protocole_https_valide is False

    res_domaine = verifier_url_officielle_portail(
        cfg_cf_reel, url_surcharge="https://faux-portail.exemple.org/etudesenfrance"
    )
    assert res_domaine.domaine_autorise is False

    # 3. Un employé (non-admin) ne peut pas homologuer un portail réel (403)
    assert (
        client_employe_a.post(
            "/api/v1/portails/campus_france_reel/valider-portail-reel",
            json={"confirmation_humaine_explicite": True},
        ).status_code
        == 403
    )

    # 4. Sans confirmation_humaine_explicite=true, l'homologation est refusée (422)
    assert (
        client_admin_a.post(
            "/api/v1/portails/campus_france_reel/valider-portail-reel",
            json={"confirmation_humaine_explicite": False},
        ).status_code
        == 422
    )

    # 5. L'administrateur humain du Bureau A valide Campus France après son test réel
    rep_homol = client_admin_a.post(
        "/api/v1/portails/campus_france_reel/valider-portail-reel",
        json={
            "confirmation_humaine_explicite": True,
            "observations": "Validé manuellement par le dirigeant sur pastel.diplomatie.gouv.fr.",
        },
    )
    assert rep_homol.status_code == 200, rep_homol.text
    assert rep_homol.json()["statut_test_regle6"] == "validé sur portail réel"
    assert rep_homol.json()["valide_par_administrateur_id"] == str(donnees_a.admin.id)

    # 6. Isolation multi-bureaux : pour le Bureau B, campus_france_reel reste 'non testé'
    par_code_b = {
        p["code_portail"]: p for p in client_admin_b.get("/api/v1/portails").json()
    }
    assert par_code_b["campus_france_reel"]["statut_test_regle6"] == "non testé"


def test_module_campus_france_reel_diagnostic_captures_et_arret_avant_envoi(
    application: FastAPI,
    parametres_test: Parametres,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
    tmp_path: Path,
) -> None:
    donnees_a, _ = deux_bureaux
    client_admin, _ = connecter_client(application, donnees_a.admin.email)

    module_cf = ModulePortailCampusFrance.depuis_fichier_yaml(
        parametres_test.dossier_portails / "campus_france_reel.yaml"
    )

    # Garde-fou Règle 1 : impossible d'instancier ModulePortailCampusFrance sans sélecteurs interdits
    cfg_sans_interdit = module_cf.config.model_copy(
        update={"selecteurs_soumission_interdits": []}
    )
    with pytest.raises(ErreurSoumissionFinaleInterdite):
        ModulePortailCampusFrance(cfg_sans_interdit)

    cid = _creer_candidat_complet(
        client_admin,
        nom="ZEROUAL",
        prenom="Lina",
        numero_passeport="DZ7700112",
        etablissement_vise="Université Paris-Saclay",
        programme_vise="Master 2 Science des Données",
        fonds_disponibles_eur=9800,
        types_pieces=PIECES_CAMPUS_FRANCE,
    )
    jeton_agent = client_admin.post(
        "/api/v1/agents-locaux", json={"nom_machine": "PC-Bureau-CF-Reel"}
    ).json()["jeton_secret"]
    client_agent = TestClient(application)
    client_agent.headers[EN_TETE_JETON_AGENT] = jeton_agent

    tid = client_admin.post(
        "/api/v1/taches",
        json={"candidat_id": cid, "code_demarche": "campus_france"},
    ).json()["id"]

    dossier_captures = tmp_path / "captures_cf_locales"

    with sync_playwright() as p:
        navigateur = p.chromium.launch(headless=True)
        page = navigateur.new_page(viewport={"width": 1280, "height": 900})

        def servir_eef(route: Route) -> None:
            route.fulfill(
                status=200,
                headers={"Content-Type": "text/html; charset=utf-8"},
                body=HTML_SIMULATION_PORTAIL_EEF.encode("utf-8"),
            )

        page.route("https://pastel.diplomatie.gouv.fr/**", servir_eef)
        page.route("https://intrus.exemple.org/**", servir_eef)

        # 1. Test du garde-fou domaine non autorisé (défaut D8)
        page.goto("https://intrus.exemple.org/etudesenfrance", wait_until="domcontentloaded")
        res_domaine = module_cf.executer_preremplissage_avec_arret_avant_envoi(
            page,
            tache_id=tid,
            client_api=client_agent,
            naviguer_au_demarrage=False,
            dossier_captures_locales=dossier_captures,
        )
        assert res_domaine.statut_final == "suspendue"
        assert res_domaine.motif_suspension == "action_utilisateur_portail"
        assert res_domaine.message_alerte is not None and "Domaine d'URL non autorisé" in res_domaine.message_alerte

        # 2. Diagnostic en lecture seule sur le domaine officiel autorisé
        page.goto(
            "https://pastel.diplomatie.gouv.fr/etudesenfrance",
            wait_until="domcontentloaded",
        )
        diag = module_cf.diagnostiquer_page_ouverte(
            page, dossier_captures_locales=dossier_captures
        )
        assert diag.protocole_https_valide is True
        assert diag.domaine_autorise is True
        assert diag.session_ouverte_detectee is True
        assert diag.blocage_captcha_ou_2fa_detecte is False
        assert diag.selecteurs_manquants == []
        assert "#btn-soumettre-dossier-eef" in diag.boutons_soumission_interdits_visibles
        assert diag.pret_pour_preremplissage is True
        assert diag.chemin_capture_diagnostic is not None
        assert Path(diag.chemin_capture_diagnostic).exists()

        # 3. Reprise et exécution complète avec captures de contrôle par étape + arrêt avant envoi
        assert client_admin.post(f"/api/v1/taches/{tid}/reprendre").status_code == 200
        res_exec = module_cf.executer_preremplissage_avec_arret_avant_envoi(
            page,
            tache_id=tid,
            client_api=client_agent,
            url_base_portail="https://pastel.diplomatie.gouv.fr",
            naviguer_au_demarrage=False,
            dossier_captures_locales=dossier_captures,
        )
        assert res_exec.statut_final == "a_valider"
        assert res_exec.captures_prises == [
            "saisie_informations_personnelles",
            "saisie_cursus_et_diplomes",
            "selection_formations_et_motivations",
            "controle_avant_validation_humaine",
        ]
        for code_cap in res_exec.captures_prises:
            assert (dossier_captures / f"capture_{tid}_{code_cap}.png").exists()

        assert page.evaluate("window.__ONGLETS_CLIQUES__") == [
            "onglet-informations-personnelles-eef",
            "onglet-cursus-diplomes-eef",
            "onglet-panier-formations-eef",
        ]
        assert page.locator("#eef-nom-famille").input_value() == "ZEROUAL"
        assert page.locator("#eef-prenom-candidat").input_value() == "Lina"
        assert page.locator("#eef-etablissement-accueil").input_value() == "Université Paris-Saclay"
        assert page.evaluate("window.__EEF_SOUMIS__") is False

        navigateur.close()


def test_module_ircc_canada_reel_diagnostic_captures_et_arret_avant_envoi(
    application: FastAPI,
    parametres_test: Parametres,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
    tmp_path: Path,
) -> None:
    donnees_a, _ = deux_bureaux
    client_admin, _ = connecter_client(application, donnees_a.admin.email)

    module_ircc = ModulePortailIRCCCanada.depuis_fichier_yaml(
        parametres_test.dossier_portails / "ircc_reel.yaml"
    )

    cid = _creer_candidat_complet(
        client_admin,
        nom="BOUZID",
        prenom="Rayan",
        numero_passeport="DZ6655443",
        etablissement_vise="Université Laval (DLI O19359011020)",
        programme_vise="Baccalauréat en Informatique",
        fonds_disponibles_eur=21000,
        types_pieces=PIECES_IRCC,
    )
    jeton_agent = client_admin.post(
        "/api/v1/agents-locaux", json={"nom_machine": "PC-Bureau-IRCC-Reel"}
    ).json()["jeton_secret"]
    client_agent = TestClient(application)
    client_agent.headers[EN_TETE_JETON_AGENT] = jeton_agent

    tid = client_admin.post(
        "/api/v1/taches",
        json={"candidat_id": cid, "code_demarche": "ircc_permis_etudes"},
    ).json()["id"]

    dossier_captures = tmp_path / "captures_ircc_locales"

    with sync_playwright() as p:
        navigateur = p.chromium.launch(headless=True)
        page = navigateur.new_page(viewport={"width": 1280, "height": 900})

        def servir_ircc(route: Route) -> None:
            route.fulfill(
                status=200,
                headers={"Content-Type": "text/html; charset=utf-8"},
                body=HTML_SIMULATION_PORTAIL_IRCC.encode("utf-8"),
            )

        page.route("https://portal-portail.apps.cic.gc.ca/**", servir_ircc)

        page.goto(
            "https://portal-portail.apps.cic.gc.ca/study-permit-application",
            wait_until="domcontentloaded",
        )
        diag = module_ircc.diagnostiquer_page_ouverte(
            page, dossier_captures_locales=dossier_captures
        )
        assert diag.pret_pour_preremplissage is True
        assert diag.selecteurs_manquants == []
        assert set(diag.boutons_soumission_interdits_visibles) == {
            "#btn-ircc-transmettre-et-payer",
            "#btn-ircc-signature-electronique-finale",
        }

        res_exec = module_ircc.executer_preremplissage_avec_arret_avant_envoi(
            page,
            tache_id=tid,
            client_api=client_agent,
            url_base_portail="https://portal-portail.apps.cic.gc.ca",
            naviguer_au_demarrage=False,
            dossier_captures_locales=dossier_captures,
        )
        assert res_exec.statut_final == "a_valider"
        assert res_exec.captures_prises == [
            "saisie_identite_et_passeport",
            "saisie_projet_etudes_dli",
            "televersement_justificatifs_ircc",
            "controle_avant_validation_humaine",
        ]
        for code_cap in res_exec.captures_prises:
            assert (dossier_captures / f"capture_{tid}_{code_cap}.png").exists()

        assert page.evaluate("window.__ETAPES_IRCC_CLIQUEES__") == [
            "etape-ircc-identite-passeport",
            "etape-ircc-etudes-dli-fonds",
            "etape-ircc-pieces-justificatives",
        ]
        assert page.locator("#ircc-reel-nom-famille").input_value() == "BOUZID"
        assert page.locator("#ircc-reel-prenom").input_value() == "Rayan"
        assert (
            page.locator("#ircc-reel-etablissement-dli").input_value()
            == "Université Laval (DLI O19359011020)"
        )
        assert page.locator("#ircc-reel-fonds-disponibles-eur").input_value() == "21000"
        assert page.evaluate("window.__IRCC_TRANSMIS__") is False

        navigateur.close()


def test_guide_campus_france_septembre_2026_pilote_navigateur_et_interface_sans_json_brut(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    donnees_a, _ = deux_bureaux
    client_admin, _ = connecter_client(application, donnees_a.admin.email)

    # 1. Vérification du guide officiel Septembre 2026 (96 pages — Campus France Algérie)
    rep_guide = client_admin.get("/api/v1/portails/campus-france/guide-2026")
    assert rep_guide.status_code == 200, rep_guide.text
    guide = rep_guide.json()
    assert "Septembre 2026" in guide["titre"]
    assert guide["pays"] == "Algérie"
    assert guide["identifiant_format"] == "DZXX-XXXXX"
    assert (
        guide["urls_officielles"]["plateforme_etudes_en_france"]
        == "https://etudesenfrance.diplomatie.gouv.fr/"
    )
    assert (
        guide["urls_officielles"]["paiement_ifa_algerie"]
        == "https://paiement.if-algerie.com"
    )
    assert [a["ville"] for a in guide["antennes_algerie"]] == [
        "Alger",
        "Annaba",
        "Constantine",
        "Oran",
        "Tlemcen",
    ]
    assert len(guide["calendrier_2026_2027"]) == 4
    assert guide["frais_dossier_algerie"]["plein_tarif"]["montant_dzd"] == 20000
    assert guide["frais_dossier_algerie"]["demi_tarif"]["montant_dzd"] == 10000
    assert guide["frais_dossier_algerie"]["gratuite"]["montant_dzd"] == 0
    assert len(guide["sections_navigation"]) == 5

    # 2. Création d'un candidat sans pièces initiales pour tester les libellés français
    #    sans code technique snake_case et la génération en 1 clic des spécimens PDF
    rep_cand = client_admin.post(
        "/api/v1/candidats",
        json={
            "nom": "MANSOURI",
            "prenom": "Meriem",
            "sexe": "F",
            "date_naissance": "2003-03-19",
            "lieu_naissance": "Alger",
            "nationalite": "Algérienne",
            "pays_residence": "Algérie",
            "email": "meriem.mansouri@exemple-fictif.dz",
            "telephone": "+213551223344",
            "numero_passeport": "DZ1122334",
            "date_expiration_passeport": (date.today() + timedelta(days=950)).isoformat(),
            "niveau_actuel": "Licence 3 Informatique (USTHB)",
            "programme_vise": "Master 1 Génie Logiciel",
            "etablissement_vise": "Université Claude Bernard Lyon 1",
            "fonds_disponibles_eur": 8500,
            "consentement_signe": True,
        },
    )
    assert rep_cand.status_code == 201, rep_cand.text
    cid = rep_cand.json()["id"]

    # L'évaluation initiale ne doit contenir aucun code snake_case entre parenthèses
    rep_eval_init = client_admin.get(
        f"/api/v1/candidats/{cid}/evaluation/campus_france",
    )
    assert rep_eval_init.status_code == 200
    eval_init = rep_eval_init.json()
    Textes_humains = (
        eval_init["meilleure_action_recommandee"]
        + " "
        + " ".join(eval_init["points_forts"])
        + " "
        + " ".join(eval_init["risques_et_blocages"])
        + " "
        + " ".join(eval_init["actions_prioritaires"])
        + " "
        + " ".join(c["commentaire"] for c in eval_init["criteres"])
    )
    for code_interdit in (
        "(passeport)",
        "(photo_identite)",
        "(releve_notes_bac)",
        "(diplome_bac)",
        "(releves_notes_superieur)",
        "(cv)",
    ):
        assert code_interdit not in Textes_humains

    # 3. Génération en 1 clic des spécimens PDF pour toutes les pièces manquantes
    rep_spec = client_admin.post(
        f"/api/v1/candidats/{cid}/documents/specimens-demo",
        params={"code_demarche": "campus_france"},
    )
    assert rep_spec.status_code == 201, rep_spec.text
    assert len(rep_spec.json()) == 7

    rep_comp = client_admin.get(
        f"/api/v1/candidats/{cid}/completude/campus_france",
    )
    assert rep_comp.status_code == 200
    assert rep_comp.json()["pret_pour_prerequis"] is True

    # 4. Discussion Conseiller sur les règles spécifiques du guide Septembre 2026
    for question, mot_attendu in (
        ("Quels sont les frais de dossier Campus France en DZD ?", "20 000 DZD"),
        ("Quel est le calendrier 2026-2027 pour les candidatures en Algérie ?", "15 décembre 2026"),
        ("Combien de formations puis-je mettre dans mon panier et combien de caractères pour les motivations ?", "4 000 caractères"),
        ("Comment fonctionne le dossier pré-consulaire après acceptation ?", "CAPAGO"),
    ):
        rep_disc = client_admin.post(
            f"/api/v1/candidats/{cid}/discussion",
            json={"code_demarche": "campus_france", "message": question},
        )
        assert rep_disc.status_code == 201, rep_disc.text
        dernier_msg = rep_disc.json()["reponse"]
        assert dernier_msg["auteur"] == "assistant"
        assert mot_attendu in dernier_msg["contenu"]

    # 5. Garde-fou Règle 1 dans le pilote navigateur : toute consigne demandant de soumettre (même sans accent ou synonyme) est bloquée
    for consigne_interdite in (
        "Cliquer sur Soumettre définitivement le dossier",
        "Soumettre definitivement le dossier",
        "Soumettre le dossier maintenant",
        "Soumettre mon dossier Campus France",
        "Transmettre la demande IRCC",
        "Signature electronique finale",
    ):
        rep_interdit = client_admin.post(
            "/api/v1/portails/piloter-navigateur",
            json={
                "candidat_id": cid,
                "code_demarche": "campus_france",
                "cible": "demo_campus_france",
                "action": "instruction_libre",
                "instruction_libre": consigne_interdite,
                "ouvrir_fenetre_visible": False,
                "synchroniser_tache": False,
            },
        )
        assert rep_interdit.status_code == 200, rep_interdit.text
        res_interdit = rep_interdit.json()
        assert res_interdit["succes"] is False, f"Devait bloquer: {consigne_interdite}"
        assert res_interdit["arret_regle1_avant_soumission"] is True
        assert "Règle 1" in res_interdit["resume_francais"]

    # Actions étape par étape du Guide Septembre 2026 (inscription + pré-consulaire 4 étapes)
    rep_inscr = client_admin.post(
        "/api/v1/portails/piloter-navigateur",
        json={
            "candidat_id": cid,
            "code_demarche": "campus_france",
            "cible": "demo_campus_france",
            "action": "inscription_compte",
            "ouvrir_fenetre_visible": False,
            "synchroniser_tache": False,
        },
    )
    assert rep_inscr.status_code == 200
    assert any("Espace Campus France Algérie" in ch for ch in rep_inscr.json()["champs_remplis_libelles"])

    rep_precons = client_admin.post(
        "/api/v1/portails/piloter-navigateur",
        json={
            "candidat_id": cid,
            "code_demarche": "campus_france",
            "cible": "demo_campus_france",
            "action": "preremplir_dossier_preconsulaire",
            "ouvrir_fenetre_visible": False,
            "synchroniser_tache": False,
        },
    )
    assert rep_precons.status_code == 200
    assert any("Étape 3/4" in ch for ch in rep_precons.json()["champs_remplis_libelles"])
    assert any("Étape 4/4" in ch for ch in rep_precons.json()["champs_remplis_libelles"])

    # Exécution complète par instruction libre avec négation explicite ("sans soumettre définitivement le dossier")
    rep_pilote = client_admin.post(
        "/api/v1/portails/piloter-navigateur",
        json={
            "candidat_id": cid,
            "code_demarche": "campus_france",
            "cible": "demo_campus_france",
            "action": "instruction_libre",
            "instruction_libre": (
                "Pré-remplir l'intégralité du dossier Campus France (éligibilité, identité, "
                "scolarité et 2 activités, langues, panier de formations, motivation et pré-consulaire) "
                "sans soumettre définitivement le dossier"
            ),
            "ouvrir_fenetre_visible": False,
            "synchroniser_tache": True,
        },
    )
    assert rep_pilote.status_code == 200, rep_pilote.text
    res_pilote = rep_pilote.json()
    assert res_pilote["succes"] is True
    assert res_pilote["arret_regle1_avant_soumission"] is True
    assert res_pilote["statut_tache"] == "a_valider"
    assert res_pilote["capture_base64"] is not None and len(res_pilote["capture_base64"]) > 100
    assert len(res_pilote["champs_remplis_libelles"]) >= 18
    assert len(res_pilote["pieces_televersees_libelles"]) == 7

    # Bascule immédiate de Campus France vers IRCC Canada dans le même navigateur géré
    rep_spec_ircc = client_admin.post(
        f"/api/v1/candidats/{cid}/documents/specimens-demo?code_demarche=ircc_permis_etudes"
    )
    assert rep_spec_ircc.status_code == 201
    rep_pilote_ircc = client_admin.post(
        "/api/v1/portails/piloter-navigateur",
        json={
            "candidat_id": cid,
            "code_demarche": "ircc_permis_etudes",
            "cible": "demo_ircc",
            "action": "instruction_libre",
            "instruction_libre": "Pré-remplir le formulaire IRCC IMM 1294, téléverser les pièces et arrêter avant transmission",
            "ouvrir_fenetre_visible": False,
            "synchroniser_tache": True,
        },
    )
    assert rep_pilote_ircc.status_code == 200, rep_pilote_ircc.text
    res_pilote_ircc = rep_pilote_ircc.json()
    assert res_pilote_ircc["succes"] is True
    assert "/demo/ircc" in res_pilote_ircc["url_courante"]
    assert res_pilote_ircc["statut_tache"] == "a_valider"
    assert len(res_pilote_ircc["champs_remplis_libelles"]) >= 7
    assert len(res_pilote_ircc["pieces_televersees_libelles"]) == 6

    from app.agent_local.pilote_navigateur import pilote_navigateur_global

    pilote_navigateur_global.fermer()

    # 6. Test de l'interface web complète avec Playwright : zéro JSON brut affiché à l'opérateur
    client_public = TestClient(application)
    with sync_playwright() as p:
        navigateur = p.chromium.launch(headless=True)
        page = navigateur.new_page(viewport={"width": 1366, "height": 900})

        def routeur_local(route: Route) -> None:
            chemin = route.request.url.replace("http://interface.local", "")
            methode = route.request.method.upper()
            corps = route.request.post_data_buffer
            en_tetes: dict[str, str] = {}
            for k, v in route.request.headers.items():
                if k.lower() in ("content-type", "x-csrf-token"):
                    en_tetes[k] = v
            rep = client_public.request(
                methode,
                chemin,
                content=corps,
                headers=en_tetes,
            )
            route.fulfill(
                status=rep.status_code,
                headers={"Content-Type": rep.headers.get("content-type", "text/plain; charset=utf-8")},
                body=rep.content,
            )

        page.route("http://interface.local/**", routeur_local)
        page.goto("http://interface.local/", wait_until="domcontentloaded")
        page.wait_for_timeout(300)

        # Connexion via le formulaire de l'interface avec les identifiants du Bureau A
        from tests.conftest import MOT_DE_PASSE_FORT

        page.locator("#login-email").fill(donnees_a.admin.email)
        page.locator("#login-mdp").fill(MOT_DE_PASSE_FORT)
        page.locator("#btn-se-connecter").click()
        page.wait_for_timeout(500)
        assert "Administrateur du bureau" in page.locator("#etat-utilisateur").inner_text()
        assert "MANSOURI" in page.locator("#bandeau-candidat-actif").inner_text()

        # Onglet 3 : Documents & Pièces requises -> le sélecteur ne contient aucun code snake_case
        page.locator("aside button.nav-btn[data-vue='vue-documents']").click()
        texte_options = page.locator("#doc-type-piece").inner_text()
        assert "(passeport)" not in texte_options
        assert "(photo_identite)" not in texte_options
        assert "Passeport biométrique en cours de validité" in texte_options

        page.locator("#btn-verifier-completude").click()
        page.wait_for_timeout(400)
        texte_completude = page.locator("#zone-completude").inner_text()
        assert "Dossier complet" in texte_completude
        assert "{" not in texte_completude
        assert "pieces_manquantes_ou_invalides" not in texte_completude

        # Onglet 4 : Discussion & Score d'acceptation -> calcul du score et envoi d'une question au Conseiller
        page.locator("aside button.nav-btn[data-vue='vue-conseiller']").click()
        page.locator("#btn-calculer-score").click()
        page.wait_for_timeout(400)
        texte_score = page.locator("#zone-score-acceptation").inner_text()
        assert "Score d'acceptation estimé" in texte_score
        assert "{" not in texte_score
        assert "pourcentage_acceptation_estime" not in texte_score

        page.locator("#msg-discussion").fill(
            "Quels sont les frais Campus France Algérie et comment fonctionne la réduction CAPAGO ?"
        )
        page.locator("#btn-envoyer-discussion").click()
        page.wait_for_timeout(600)
        texte_fil = page.locator("#fil-discussion").inner_text()
        assert "20 000 DZD" in texte_fil
        assert "Assistant Conseiller Réglementaire" in texte_fil

        # Onglet 5 : Campus France -> Guide Septembre 2026 affiché + création de tâche sans JSON brut
        page.locator("aside button.nav-btn[data-vue='vue-campus-france']").click()
        page.wait_for_timeout(300)
        texte_cf = page.locator("#vue-campus-france").inner_text()
        assert "20 000 DZD" in texte_cf
        assert "Alger" in texte_cf

        page.locator("#btn-creer-tache-cf").click()
        page.wait_for_timeout(500)
        texte_retour_cf = page.locator("#zone-retour-cf").inner_text()
        assert "Suivi de la tâche Campus France" in texte_retour_cf
        assert "null" not in texte_retour_cf
        assert "{" not in texte_retour_cf

        # Onglet 7 : Centre de validation humaine -> affichage du candidat, du récapitulatif et validation Règle 1
        page.locator("aside button.nav-btn[data-vue='vue-validation-humaine']").click()
        page.wait_for_timeout(500)
        texte_val = page.locator("#liste-centre-validation").inner_text()
        assert "MANSOURI" in texte_val
        assert "Champs pré-remplis vérifiés" in texte_val
        assert "{" not in texte_val
        assert "null" not in texte_val

        navigateur.close()

