"""Contrôles de qualité sur tous les YAML de config/demarches."""

from pathlib import Path

import pytest

from app.services.pieces_requises import charger_demarches_base

DOSSIER = Path(__file__).resolve().parents[2] / "config" / "demarches"

CHAMPS_VALIDES = {
    "nom", "prenom", "sexe", "date_naissance", "lieu_naissance", "nationalite",
    "pays_residence", "email", "telephone", "numero_passeport",
    "date_expiration_passeport", "adresse", "niveau_actuel", "programme_vise",
    "etablissement_vise", "fonds_disponibles_eur",
}

NOUVELLES = {
    "ecoles_privees_france",
    "canada_dep_dec_quebec",
    "visa_touristique_schengen",
    "canada_residence_permanente",
}


def _fichiers():
    return sorted(DOSSIER.glob("*.yaml"))


def test_tous_les_yaml_se_chargent():
    demarches = charger_demarches_base(DOSSIER)
    assert len(demarches) == len(_fichiers())
    assert NOUVELLES <= set(demarches)


def test_codes_uniques_et_egaux_au_nom_de_fichier():
    demarches = charger_demarches_base(DOSSIER)
    for fichier in _fichiers():
        assert fichier.stem in demarches, fichier.name
        assert demarches[fichier.stem].code == fichier.stem


@pytest.mark.parametrize("code", sorted(p.stem for p in _fichiers()))
def test_contenu_minimal(code):
    d = charger_demarches_base(DOSSIER)[code]
    assert len(d.pieces_requises) >= 3
    assert len(d.veille_reglementaire) >= 3
    for point in d.veille_reglementaire:
        assert point.reference.strip()
    assert set(d.champs_candidat_requis) <= CHAMPS_VALIDES
    types = [p.type_piece for p in d.pieces_requises]
    assert len(types) == len(set(types))
    for t in types:
        assert t == t.lower() and t.isascii() and " " not in t
