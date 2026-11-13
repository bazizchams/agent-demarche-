"""Procédure « Créer ou reprendre un compte Études en France » (config/demarches/compte_etudes_en_france.yaml).

Chargée par le chargeur/validateur standard des démarches (ConfigDemarche). Vérifie le respect des règles 1 à 4 et 6
dans le contenu de la procédure. Aucun accès réseau.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from app.agent_local.config_portail import charger_config_portail
from app.services.pieces_requises import charger_demarches_base

RACINE = Path(__file__).resolve().parents[2]
DOSSIER_DEMARCHES = RACINE / "config" / "demarches"
CODE = "compte_etudes_en_france"


def _procedure():
    return charger_demarches_base(DOSSIER_DEMARCHES)[CODE]


def test_procedure_compte_eef_se_charge_avec_le_validateur() -> None:
    p = _procedure()
    assert p.code == CODE
    assert len(p.pieces_requises) >= 3 and len(p.veille_reglementaire) >= 3
    assert p.instructions_agent and len(p.instructions_agent) <= 4000
    codes = [e.code for e in p.etapes_tache]
    assert codes[0] == "verification_prerequis_dossier"
    assert codes[-1] == "controle_avant_validation_humaine"
    assert {"verification_compte_existant", "creation_ou_reprise_compte",
            "enregistrement_identifiants_coffre", "enchainement_dossier_candidature"} <= set(codes)


def test_procedure_compte_eef_couvre_creation_reprise_et_enchainement() -> None:
    texte = (_procedure().instructions_agent or "").lower()
    for attendu in ("s'inscrire", "mot de passe oublié", "compte bloqué", "activation",
                    "alger", "annaba", "constantine", "oran", "tlemcen",
                    "identité", "parcours", "langues", "panier", "entretien", "paiement.if-algerie.com"):
        assert attendu in texte, attendu


def test_procedure_compte_eef_respecte_les_regles_de_securite() -> None:
    p = _procedure()
    texte = (p.instructions_agent or "").lower()
    assert "règle 1" in texte and "ne jamais cliquer" in texte  # arrêt avant envoi
    assert "règle 2" in texte and "captcha" in texte  # CAPTCHA / codes laissés au conseiller
    assert "règle 3" in texte and "coffre" in texte  # identifiants au coffre chiffré
    assert "règle 4" in texte
    # Aucun mot de passe ni identifiant en clair dans le YAML.
    brut = (DOSSIER_DEMARCHES / f"{CODE}.yaml").read_text(encoding="utf-8").lower()
    for interdit in ("mot_de_passe:", "password:", "identifiant:"):
        assert interdit not in brut
    assert "consentement_candidat_compte" in {pc.type_piece for pc in p.pieces_requises}


def test_procedure_compte_eef_sources_datees_ou_a_verifier() -> None:
    for point in _procedure().veille_reglementaire:
        assert "2026-11-13" in point.titre or "à vérifier" in point.titre.lower(), point.titre
        assert point.reference.strip()


def test_procedure_compte_eef_domaines_cites_sont_autorises() -> None:
    cfg = charger_config_portail(RACINE / "config" / "portails" / "campus_france_reel.yaml")
    autorises = set(cfg.domaines_autorises)
    texte = _procedure().instructions_agent or ""
    for hote in ("etudesenfrance.diplomatie.gouv.fr", "pastel.diplomatie.gouv.fr",
                 "www.algerie.campusfrance.org", "algerie.campusfrance.org", "paiement.if-algerie.com"):
        assert hote in texte and hote in autorises


def test_procedure_compte_eef_echeances_campagne_2027() -> None:
    echeances = {e.code: e.date_fixe for e in _procedure().echeances}
    assert echeances["soumission_dap_2027"] == date(2026, 12, 15)
    assert echeances["soumission_hors_dap_2027"] == date(2026, 12, 22)
    assert echeances["entretien_2027"] == date(2027, 3, 15)
    assert echeances["choix_definitif_2027"] == date(2027, 5, 31)
