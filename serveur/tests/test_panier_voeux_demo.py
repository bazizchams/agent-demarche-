"""Tests (Playwright Chromium headless) du panier de vœux Campus France sur la page de démonstration
`/demo/campus-france` : ajout de formations + texte de motivation par formation, garde-fous Règle 1/2/4/5,
refus sur le vrai portail non homologué (Règle 6) et action de calibration `cartographier_page`.

Aucun serveur n'est lancé : le pilote sert la page de démo via `page.route("http://portail.local/demo/**")`.
Toutes les données sont fictives ; aucun accès à `serveur/donnees/`.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from playwright.sync_api import Page

from app.agent_local.pilote_navigateur import (
    GestionnairePiloteNavigateur,
    ResultatActionNavigateur,
    _detecter_captcha_ou_2fa_sur_page,
    _est_element_soumission_interdit_regle1,
    pilote_navigateur_global,
)
from app.agent_local.portails.panier_voeux import (
    PROFIL_PANIER_DEMO,
    ProfilSelecteursPanier,
    ajouter_voeux_au_panier,
)
from app.core.config import Parametres
from tests.conftest import DonneesBureauTest, connecter_client

CLES_RESULTAT_VOEU = {
    "voeu_id",
    "intitule",
    "etablissement",
    "statut",
    "motivation_enregistree",
    "nb_caracteres",
}
STATUTS_VALIDES = {
    "ajoute",
    "deja_present",
    "introuvable",
    "ambigu",
    "refuse_limite",
    "motivation_invalide",
    "erreur",
}
JS_ESPION_CLICS = """() => {
    window.__CLICS_INTERDITS__ = [];
    document.addEventListener('click', (e) => {
        const cible = e.target.closest('#case-certif-exactitude, #case-certif-prerequis, #btn-soumission-finale-officielle, #btn-enregistrer-brouillon');
        if (cible) window.__CLICS_INTERDITS__.push(cible.id);
    }, true);
}"""


class Navigation:
    """Fixture : un pilote Playwright isolé (profil dans tmp_path) + helpers thread-safe."""

    def __init__(self, tmp_path: Path) -> None:
        self.g = GestionnairePiloteNavigateur()
        self.dossier_profil = tmp_path / "stockage" / "profil_navigateur_agent"
        self.dossier_calibration = tmp_path / "stockage" / "calibration"

    def action(
        self,
        action: str,
        *,
        voeux: list[dict[str, Any]] | None = None,
        cible: str = "demo_campus_france",
        instruction_libre: str | None = None,
        portail_homologue: bool = False,
    ) -> ResultatActionNavigateur:
        return self.g.executer_action(
            code_demarche="campus_france",
            cible=cible,
            action=action,
            instruction_libre=instruction_libre,
            candidat={},
            documents_dechiffres=[],
            dossier_profil=self.dossier_profil,
            headless=True,
            prendre_capture=True,
            voeux=voeux,
            portail_homologue=portail_homologue,
        )

    def ouvrir_demo(self) -> None:
        res = self.action("ouvrir_portail")
        assert "/demo/campus-france" in res.url_courante
        self.dans_page(lambda p: p.evaluate(JS_ESPION_CLICS))

    def dans_page(self, fn: Callable[[Page], Any]) -> Any:
        assert self.g._page is not None
        return self.g._executor.submit(lambda: fn(self.g._page)).result(timeout=30)

    def etat_panier(self) -> list[dict[str, Any]]:
        return self.dans_page(
            lambda p: p.evaluate(
                """() => Array.from(document.querySelectorAll('#panier-liste .panier-item')).map(li => ({
                    id: li.dataset.formationId,
                    statut: li.dataset.statut,
                    longueur: li.querySelector('textarea.panier-motivation').value.length,
                }))"""
            )
        )

    def clics_interdits(self) -> list[str]:
        return self.dans_page(lambda p: p.evaluate("window.__CLICS_INTERDITS__"))


@pytest.fixture()
def nav(tmp_path: Path) -> Iterator[Navigation]:
    n = Navigation(tmp_path)
    try:
        yield n
    finally:
        n.g.fermer()


def _motivation(voeu_id: str, taille: int = 300) -> str:
    base = f"MOTIVATION-UNIQUE-{voeu_id} : mon projet d'études est cohérent avec mon parcours. "
    return (base * (taille // len(base) + 1))[:taille]


def _voeu(
    voeu_id: str,
    intitule: str,
    etablissement: str,
    *,
    motivation: str | None = None,
    niveau: str | None = None,
) -> dict[str, Any]:
    return {
        "voeu_id": voeu_id,
        "intitule": intitule,
        "etablissement": etablissement,
        "niveau": niveau,
        "motivation": _motivation(voeu_id) if motivation is None else motivation,
    }


V_IA_SORBONNE = ("Master 1 Intelligence Artificielle", "Sorbonne Université")
V_INFO_SACLAY = ("Master 1 Informatique", "Université Paris-Saclay")
V_INFO_LORRAINE = ("Master 1 Informatique", "Université de Lorraine")


def _verifier_aucun_texte_sensible(res: ResultatActionNavigateur, marqueur: str = "MOTIVATION-UNIQUE") -> None:
    """R5 : aucun texte de motivation dans le résumé, la réponse, les étapes ni les avertissements."""
    textes = [res.resume_francais, res.reponse_agent, *res.etapes_realisees, *res.avertissements_securite]
    assert all(marqueur not in t for t in textes)


def _verifier_resultat_conforme(res: ResultatActionNavigateur, nb_attendu: int) -> None:
    assert len(res.resultats_voeux) == nb_attendu
    for r in res.resultats_voeux:
        assert set(r.keys()) == CLES_RESULTAT_VOEU
        assert r["statut"] in STATUTS_VALIDES
        assert isinstance(r["motivation_enregistree"], bool)
        assert isinstance(r["nb_caracteres"], int)
    assert res.arret_regle1_avant_soumission is True
    assert res.capture_png_octets is not None and res.capture_png_octets.startswith(b"\x89PNG")
    _verifier_aucun_texte_sensible(res)


def test_ajout_de_trois_voeux_avec_motivation_et_garde_fous(nav: Navigation) -> None:
    nav.ouvrir_demo()
    voeux = [
        _voeu("v1", *V_IA_SORBONNE, niveau="Master 1"),
        # Normalisation casse / accents / ponctuation
        _voeu("v2", "MASTER 1 informatique", "universite paris-saclay"),
        _voeu("v3", *V_INFO_LORRAINE),
    ]
    res = nav.action("ajouter_voeux_panier", voeux=voeux)

    assert res.succes is True
    assert res.blocage_captcha_ou_2fa is False
    _verifier_resultat_conforme(res, 3)
    for r, v in zip(res.resultats_voeux, voeux):
        assert r["voeu_id"] == v["voeu_id"]
        assert r["statut"] == "ajoute"
        assert r["motivation_enregistree"] is True
        assert r["nb_caracteres"] == len(v["motivation"])

    panier = nav.etat_panier()
    assert [p["id"] for p in panier] == ["f-001", "f-002", "f-006"]
    assert all(p["statut"] == "motivation_enregistree" for p in panier)
    assert [p["longueur"] for p in panier] == [len(v["motivation"]) for v in voeux]
    assert nav.dans_page(lambda p: p.locator("#panier-compteur").inner_text()) == "3 / 7"
    assert nav.dans_page(lambda p: p.evaluate("window.__MOTIVATIONS_ENREGISTREES__")) == 3

    # Règle 1 : ni soumission, ni case de certification, ni brouillon global cliqués
    assert nav.clics_interdits() == []
    assert nav.dans_page(lambda p: p.evaluate("window.__SOUMISSION_FINALE_CLIQUEE__")) is False
    assert nav.dans_page(lambda p: p.evaluate("window.__BROUILLON_ENREGISTRE__")) is False
    assert nav.dans_page(lambda p: p.locator("#case-certif-exactitude").is_checked()) is True
    assert nav.dans_page(lambda p: p.locator("#case-certif-prerequis").is_checked()) is True
    # Les zones de motivation du panier ne fuitent pas dans les éléments interactifs renvoyés (R5)
    assert res.elements_interactifs_page == []


def test_doublon_deja_present_sans_duplication(nav: Navigation) -> None:
    nav.ouvrir_demo()
    premier = nav.action("ajouter_voeux_panier", voeux=[_voeu("v1", *V_IA_SORBONNE)])
    assert premier.resultats_voeux[0]["statut"] == "ajoute"

    # Doublon dans un appel ultérieur ET doublon au sein d'un même appel
    res = nav.action(
        "ajouter_voeux_panier",
        voeux=[
            _voeu("v1bis", *V_IA_SORBONNE),
            _voeu("v2", *V_INFO_SACLAY),
            _voeu("v2bis", *V_INFO_SACLAY),
        ],
    )
    _verifier_resultat_conforme(res, 3)
    assert [r["statut"] for r in res.resultats_voeux] == ["deja_present", "ajoute", "deja_present"]
    assert [r["motivation_enregistree"] for r in res.resultats_voeux] == [False, True, False]
    assert [p["id"] for p in nav.etat_panier()] == ["f-001", "f-002"]


def test_voeu_introuvable_et_ambigu_ne_rien_ajouter(nav: Navigation) -> None:
    nav.ouvrir_demo()
    res = nav.action(
        "ajouter_voeux_panier",
        voeux=[
            _voeu("absent", "Master 1 Astrophysique Quantique", "Université de Lille"),
            # Intitulé existant mais pas dans cet établissement : jamais d'approximation
            _voeu("mauvais_etab", "Master 1 Intelligence Artificielle", "Université de Lille"),
            # Deux entrées identiques (campus Nancy et Metz) : ambigu, même avec le niveau
            _voeu("ambigu", "Licence 3 Informatique", "Université de Lorraine", niveau="Licence 3"),
        ],
    )
    _verifier_resultat_conforme(res, 3)
    assert [r["statut"] for r in res.resultats_voeux] == ["introuvable", "introuvable", "ambigu"]
    assert all(r["motivation_enregistree"] is False for r in res.resultats_voeux)
    assert nav.etat_panier() == []
    assert any("plusieurs formations" in a for a in res.avertissements_securite)


def test_limite_de_sept_formations(nav: Navigation) -> None:
    nav.ouvrir_demo()
    cibles = [
        ("Master 1 Intelligence Artificielle", "Sorbonne Université"),
        ("Master 1 Informatique", "Université Paris-Saclay"),
        ("Master 2 Data Science", "Université de Lyon"),
        ("Master 1 Informatique", "Université de Lorraine"),
        ("Master 2 Cybersécurité", "Université de Rennes"),
        ("Diplôme d'ingénieur Génie Logiciel", "INSA Lyon"),
        ("Master 1 Intelligence Artificielle", "Université Côte d'Azur"),
        ("Master 1 Mathématiques Appliquées", "Université de Bordeaux"),
    ]
    res = nav.action(
        "ajouter_voeux_panier",
        voeux=[_voeu(f"v{i}", intitule, etab) for i, (intitule, etab) in enumerate(cibles)],
    )
    _verifier_resultat_conforme(res, 8)
    assert [r["statut"] for r in res.resultats_voeux] == ["ajoute"] * 7 + ["refuse_limite"]
    assert res.resultats_voeux[7]["motivation_enregistree"] is False
    assert len(nav.etat_panier()) == 7
    assert nav.dans_page(lambda p: p.locator("#panier-compteur").inner_text()) == "7 / 7"
    assert nav.clics_interdits() == []


def test_motivation_vide_ou_trop_longue_refusee_et_4000_acceptee(nav: Navigation) -> None:
    nav.ouvrir_demo()
    res = nav.action(
        "ajouter_voeux_panier",
        voeux=[
            _voeu("vide", *V_IA_SORBONNE, motivation="   "),
            _voeu("trop_longue", *V_INFO_SACLAY, motivation="x" * 4001),
            _voeu("limite", *V_INFO_LORRAINE, motivation="y" * 4000),
        ],
    )
    _verifier_resultat_conforme(res, 3)
    assert [r["statut"] for r in res.resultats_voeux] == ["motivation_invalide", "motivation_invalide", "ajoute"]
    assert [r["motivation_enregistree"] for r in res.resultats_voeux] == [False, False, True]
    assert res.resultats_voeux[2]["nb_caracteres"] == 4000
    # Rien n'a été ajouté pour les motivations invalides : seule la formation valide est au panier
    assert [p["id"] for p in nav.etat_panier()] == ["f-006"]


def test_champ_manquant_jamais_invente(nav: Navigation) -> None:
    nav.ouvrir_demo()
    res = nav.action("ajouter_voeux_panier", voeux=[_voeu("v1", "Master 1 Informatique", "")])
    assert res.resultats_voeux[0]["statut"] == "erreur"
    assert nav.etat_panier() == []


def test_gardes_regle1_aucun_clic_sur_soumission_ou_certification(nav: Navigation) -> None:
    """Même si un profil de sélecteurs pointait par erreur vers la soumission finale ou une case de
    certification, le garde Règle 1 empêche le clic."""
    nav.ouvrir_demo()

    def tenter(sel_bouton: str) -> list[dict[str, Any]]:
        profil_piege = ProfilSelecteursPanier(
            **{**PROFIL_PANIER_DEMO.__dict__, "bouton_rechercher": sel_bouton}
        )

        def _go(page: Page) -> list[dict[str, Any]]:
            resultats, _notes, _blocage = ajouter_voeux_au_panier(
                page,
                [_voeu("v1", *V_IA_SORBONNE)],
                profil=profil_piege,
                est_interdit=_est_element_soumission_interdit_regle1,
                detecteur_blocage=_detecter_captcha_ou_2fa_sur_page,
            )
            return resultats

        return nav.dans_page(_go)

    assert tenter("#btn-soumission-finale-officielle")[0]["statut"] in {"introuvable", "erreur"}
    assert tenter("#case-certif-exactitude")[0]["statut"] in {"introuvable", "erreur"}
    assert tenter("#case-certif-prerequis")[0]["statut"] in {"introuvable", "erreur"}
    assert nav.clics_interdits() == []
    assert nav.dans_page(lambda p: p.evaluate("window.__SOUMISSION_FINALE_CLIQUEE__")) is False
    assert nav.dans_page(lambda p: p.locator("#case-certif-exactitude").is_checked()) is True
    assert nav.etat_panier() == []


def test_pause_immediate_si_captcha(nav: Navigation) -> None:
    # 1. CAPTCHA déjà présent à l'ouverture : l'action se met en pause avant tout vœu
    res = nav.action(
        "ajouter_voeux_panier",
        voeux=[_voeu("v1", *V_IA_SORBONNE)],
        instruction_libre="va sur http://portail.local/demo/campus-france?captcha=1",
    )
    assert res.succes is False
    assert res.blocage_captcha_ou_2fa is True
    assert res.resultats_voeux == []
    assert nav.etat_panier() == []

    # 2. CAPTCHA détecté en cours de route : tous les vœux restent non traités (statut « erreur »)
    nav.action("ouvrir_portail", instruction_libre="va sur http://portail.local/demo/campus-france?captcha=0")
    nav.dans_page(lambda p: p.evaluate(JS_ESPION_CLICS))

    def _go(page: Page) -> list[dict[str, Any]]:
        resultats, _notes, blocage = ajouter_voeux_au_panier(
            page,
            [_voeu("v1", *V_IA_SORBONNE), _voeu("v2", *V_INFO_SACLAY)],
            profil=PROFIL_PANIER_DEMO,
            est_interdit=_est_element_soumission_interdit_regle1,
            detecteur_blocage=lambda _p: True,
        )
        assert blocage is True
        return resultats

    resultats = nav.dans_page(_go)
    assert [r["statut"] for r in resultats] == ["erreur", "erreur"]
    assert nav.etat_panier() == []


def test_action_refusee_sur_vrai_portail_non_homologue(nav: Navigation) -> None:
    res = nav.action(
        "ajouter_voeux_panier",
        voeux=[_voeu("v1", *V_IA_SORBONNE)],
        cible="campus_france_officiel",
        portail_homologue=False,
    )
    assert res.succes is False
    assert "homologué" in res.reponse_agent and "non testé" in res.reponse_agent
    assert res.resultats_voeux == []
    # Refus AVANT toute ouverture de navigateur : le vrai portail n'est jamais contacté
    assert nav.g._page is None
    _verifier_aucun_texte_sensible(res)

    res2 = nav.action("ajouter_voeux_panier", voeux=[], cible="campus_france_pastel")
    assert res2.succes is False and "homologué" in res2.reponse_agent


def test_cartographier_page_ne_stocke_aucune_valeur_de_champ(nav: Navigation) -> None:
    nav.ouvrir_demo()
    # Saisies SENSIBLES fictives qui ne doivent jamais apparaître dans la calibration
    secrets = {
        "#champ-nom-famille": "NOM-SECRET-XYZ",
        "#champ-email": "secret.personne@exemple-fictif.dz",
        "#champ-numero-passeport": "DZ99887766",
        "#champ-texte-motivation": "MOTIVATION-SECRETE-ABC",
    }
    for sel, valeur in secrets.items():
        nav.dans_page(lambda p, s=sel, v=valeur: p.locator(s).fill(v))
    nav.dans_page(lambda p: p.locator("#champ-sexe").select_option("F"))
    nav.dans_page(lambda p: p.locator("#champ-nom-famille").evaluate("e => e.setAttribute('data-valeur-saisie', 'FUITE-DATA')"))

    # La calibration s'exécute sur la page courante (vrai portail non homologué compris) sans cliquer
    res = nav.action("cartographier_page", cible="campus_france_officiel")
    assert res.succes is True
    assert res.fichier_calibration is not None
    fichier = Path(res.fichier_calibration)
    assert fichier.parent == nav.dossier_calibration
    assert fichier.suffix == ".json" and fichier.exists()

    brut = fichier.read_text(encoding="utf-8")
    for valeur in secrets.values():
        assert valeur not in brut
    for fuite in ("FUITE-DATA", "Masculin", "Féminin"):
        assert fuite not in brut

    contenu = json.loads(brut)
    assert contenu["nb_elements"] == len(contenu["elements"]) > 20
    ids = {e["id"] for e in contenu["elements"]}
    assert {"champ-nom-famille", "champ-texte-motivation", "btn-soumission-finale-officielle", "catalogue-recherche"} <= ids
    for e in contenu["elements"]:
        assert set(e.keys()) == {
            "balise", "role", "texte", "id", "name", "classes", "data", "placeholder", "type", "visible",
        }
        assert len(e["texte"]) <= 80
        assert "value" not in e and "valeur" not in e
    bouton_final = next(e for e in contenu["elements"] if e["id"] == "btn-soumission-finale-officielle")
    assert bouton_final["data"].get("data-action-officielle") == "soumettre-definitivement"
    assert "query" not in json.dumps(contenu["url"])

    # Aucun clic ni modification : les valeurs saisies sont intactes, rien d'interdit cliqué
    assert nav.clics_interdits() == []
    assert nav.dans_page(lambda p: p.locator("#champ-nom-famille").input_value()) == "NOM-SECRET-XYZ"
    assert nav.dans_page(lambda p: p.evaluate("window.__SOUMISSION_FINALE_CLIQUEE__")) is False


# ---------------------------------------------------------------------------
# API : champ `voeux`, refus non homologué, audit sans donnée personnelle
# ---------------------------------------------------------------------------


def _creer_candidat(client: TestClient) -> str:
    rep = client.post(
        "/api/v1/candidats",
        json={
            "nom": "TESTNOM",
            "prenom": "Testprenom",
            "sexe": "F",
            "date_naissance": "2002-05-14",
            "lieu_naissance": "Oran",
            "nationalite": "Algérienne",
            "pays_residence": "Algérie",
            "email": "testprenom.testnom@exemple-fictif.dz",
            "telephone": "+213550112233",
            "numero_passeport": "DZ1234567",
            "date_expiration_passeport": (date.today() + timedelta(days=900)).isoformat(),
            "niveau_actuel": "Licence 3 Informatique",
            "programme_vise": "Master 1 Intelligence Artificielle",
            "etablissement_vise": "Sorbonne Université",
            "fonds_disponibles_eur": 9000,
            "consentement_signe": True,
        },
    )
    assert rep.status_code == 201, rep.text
    return rep.json()["id"]


def test_api_voeux_demo_refus_non_homologue_et_audit_sans_pii(
    application: FastAPI,
    parametres_test: Parametres,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    donnees_a, _ = deux_bureaux
    client, _ = connecter_client(application, donnees_a.admin.email)
    cid = _creer_candidat(client)
    motivation_secrete = "MOTIVATION-UNIQUE-API : texte confidentiel du candidat."

    try:
        # 1. Vrai portail non homologué : refusé, navigateur jamais ouvert
        rep_refus = client.post(
            "/api/v1/portails/piloter-navigateur",
            json={
                "candidat_id": cid,
                "code_demarche": "campus_france",
                "cible": "campus_france_officiel",
                "action": "ajouter_voeux_panier",
                "voeux": [
                    {
                        "voeu_id": "v1",
                        "intitule": "Master 1 Intelligence Artificielle",
                        "etablissement": "Sorbonne Université",
                        "motivation": motivation_secrete,
                    }
                ],
            },
        )
        assert rep_refus.status_code == 200, rep_refus.text
        corps = rep_refus.json()
        assert corps["succes"] is False
        assert "homologué" in corps["reponse_agent"]
        assert corps["resultats_voeux"] == []

        # 2. Démo : fonctionne et rapporte un résultat structuré par vœu
        rep_demo = client.post(
            "/api/v1/portails/piloter-navigateur",
            json={
                "candidat_id": cid,
                "code_demarche": "campus_france",
                "cible": "demo_campus_france",
                "action": "ajouter_voeux_panier",
                "voeux": [
                    {
                        "voeu_id": "v1",
                        "intitule": "Master 1 Intelligence Artificielle",
                        "etablissement": "Sorbonne Université",
                        "niveau": "Master 1",
                        "motivation": motivation_secrete,
                    },
                    {
                        "voeu_id": "v2",
                        "intitule": "Master 1 Inconnu",
                        "etablissement": "Université Imaginaire",
                        "motivation": motivation_secrete,
                    },
                ],
            },
        )
        assert rep_demo.status_code == 200, rep_demo.text
        corps = rep_demo.json()
        assert [r["statut"] for r in corps["resultats_voeux"]] == ["ajoute", "introuvable"]
        assert corps["resultats_voeux"][0]["motivation_enregistree"] is True
        assert corps["resultats_voeux"][0]["nb_caracteres"] == len(motivation_secrete)
        assert corps["tache_id"] is None  # pas de synchronisation « validation humaine » pour cette action
        assert motivation_secrete not in rep_demo.text

        # 3. Corps invalide : un champ inconnu reste refusé (extra=forbid)
        assert (
            client.post(
                "/api/v1/portails/piloter-navigateur",
                json={"candidat_id": cid, "voeux": [{"voeu_id": "x", "inconnu": 1}]},
            ).status_code
            == 422
        )

        # 4. Audit : compteurs uniquement, jamais de motivation, d'intitulé ni de nom (R5)
        rep_audit = client.get("/api/v1/audit", params={"action": "portail.pilotage_navigateur", "taille": 50})
        assert rep_audit.status_code == 200, rep_audit.text
        texte_audit = rep_audit.text
        for interdit in (motivation_secrete, "MOTIVATION-UNIQUE", "TESTNOM", "Testprenom", "Sorbonne", "Intelligence"):
            assert interdit not in texte_audit
        assert '"nb_voeux_ajoute"' in texte_audit or "nb_voeux_ajoute" in texte_audit
    finally:
        pilote_navigateur_global.fermer()
