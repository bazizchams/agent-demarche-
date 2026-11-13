"""Procédures IRCC de base ajoutées le 2026-11-13 : visa de visiteur, visite familiale / super visa, Entrée express.

Vérifie qu'elles se chargent avec le validateur du projet (`ConfigDemarche` via `charger_demarches_base`),
qu'elles s'arrêtent avant la soumission finale (règle 1), que les frais sont en CAD tels que relevés
sur canada.ca, et qu'elles citent des sources officielles.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.pieces_requises import charger_demarches_base

DOSSIER = Path(__file__).resolve().parents[2] / "config" / "demarches"

PROCEDURES_IRCC = ("ircc_visa_visiteur", "ircc_visite_famille_super_visa", "ircc_entree_express_rp")


@pytest.fixture(scope="module")
def demarches():
    return charger_demarches_base(DOSSIER)


def test_procedures_ircc_se_chargent(demarches) -> None:
    assert set(PROCEDURES_IRCC) <= set(demarches)


@pytest.mark.parametrize("code", PROCEDURES_IRCC)
def test_procedure_ircc_arret_avant_soumission(demarches, code: str) -> None:
    d = demarches[code]
    assert d.etapes_tache[-1].code == "controle_avant_validation_humaine"
    assert "soumission" in d.etapes_tache[-1].libelle.lower()
    consignes = (d.instructions_agent or "").lower()
    assert "règle 1" in consignes and "règle 2" in consignes
    assert "passeport" in {p.type_piece for p in d.pieces_requises}


@pytest.mark.parametrize("code", PROCEDURES_IRCC)
def test_procedure_ircc_frais_en_cad_et_sources(demarches, code: str) -> None:
    d = demarches[code]
    assert d.frais and all(f.devise == "CAD" and f.beneficiaire == "IRCC" for f in d.frais)
    assert any(f.montant == 85 for f in d.frais), "frais de biométrie (85 CAD) attendus"
    texte = (DOSSIER / f"{code}.yaml").read_text(encoding="utf-8")
    assert "https://www.canada.ca/en/immigration-refugees-citizenship/" in texte
    assert "2026-11-13" in texte
    assert all("canada.ca" in p.reference for p in d.veille_reglementaire)


def test_montants_releves_sur_canada_ca(demarches) -> None:
    visiteur = {f.montant for f in demarches["ircc_visa_visiteur"].frais}
    assert {100, 500, 85, 170} <= visiteur
    rp = {f.montant for f in demarches["ircc_entree_express_rp"].frais}
    assert {990, 600, 270, 85} <= rp


def test_entree_express_deux_arrets_et_programmes(demarches) -> None:
    d = demarches["ircc_entree_express_rp"]
    codes = [e.code for e in d.etapes_tache]
    assert "controle_profil_avant_validation_humaine" in codes
    assert codes.index("controle_profil_avant_validation_humaine") < codes.index(
        "preparation_demande_rp_apres_invitation"
    )
    programmes = d.veille_reglementaire[0].resume
    for programme in ("TQF", "CEC", "TMF", "PNP"):
        assert programme in programmes


def test_super_visa_exigences_specifiques(demarches) -> None:
    types = {p.type_piece for p in demarches["ircc_visite_famille_super_visa"].pieces_requises}
    assert {
        "preuve_lien_parente",
        "lettre_invitation_hote",
        "assurance_maladie_super_visa",
        "preuve_examen_medical",
    } <= types
