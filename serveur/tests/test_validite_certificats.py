"""Validité des certificats de langue : module partagé `app.services.validite_certificats`.

Tests écrits avant l'implémentation (TDD). La date de référence est toujours passée en paramètre :
le résultat ne doit jamais dépendre de la date du jour.
"""

from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from app.services.validite_certificats import (
    SANS_EXPIRATION,
    VALIDITE_TCF_MOIS,
    ValiditeCertificat,
    ajouter_mois,
    evaluer_validite,
)

PASSAGE_TCF = date(2024, 11, 14)
FIN_TCF = date(2026, 11, 14)
REFERENCE_NEUTRE = date(2026, 6, 1)


# ============================================================ constantes


def test_validite_tcf_est_de_24_mois():
    assert VALIDITE_TCF_MOIS == 24


def test_types_sans_expiration_sont_delf_et_dalf():
    assert SANS_EXPIRATION == frozenset({"DELF", "DALF"})
    assert isinstance(SANS_EXPIRATION, frozenset)


# ============================================================ ajouter_mois


@pytest.mark.parametrize(
    ("depart", "mois", "attendu"),
    [
        (date(2024, 1, 31), 1, date(2024, 2, 29)),   # année bissextile : dernier jour de février
        (date(2023, 1, 31), 1, date(2023, 2, 28)),   # année non bissextile
        (date(2024, 11, 14), 24, date(2026, 11, 14)),
        (date(2024, 2, 29), 12, date(2025, 2, 28)),  # 29 février ramené au 28 l'année suivante
        (date(2024, 12, 31), 2, date(2025, 2, 28)),  # franchissement d'année
    ],
)
def test_ajouter_mois_ramene_au_dernier_jour_du_mois_cible(depart, mois, attendu):
    assert ajouter_mois(depart, mois) == attendu


# ============================================================ bornes du 24e mois (passage 2024-11-14)


@pytest.mark.parametrize(
    ("reference", "statut", "fin"),
    [
        pytest.param(date(2026, 11, 13), "valide", FIN_TCF, id="veille-du-24e-mois"),
        pytest.param(FIN_TCF, "valide", FIN_TCF, id="jour-du-24e-mois-reste-valide"),
        pytest.param(date(2026, 11, 15), "expire", FIN_TCF, id="lendemain-du-24e-mois-expire"),
    ],
)
def test_bornes_de_validite_tcf_autour_de_la_fin(reference, statut, fin):
    resultat = evaluer_validite("TCF", PASSAGE_TCF, reference)

    assert resultat.statut == statut
    assert resultat.fin == fin


def test_tcf_passe_le_jour_meme_est_valide_avec_fin_renseignee():
    resultat = evaluer_validite("TCF", PASSAGE_TCF, PASSAGE_TCF)

    assert resultat == ValiditeCertificat(statut="valide", fin=FIN_TCF)


# ============================================================ DELF / DALF


@pytest.mark.parametrize(
    ("type_cert", "date_passage"),
    [
        pytest.param("DELF", date(2000, 1, 1), id="delf-tres-ancien"),
        pytest.param("DALF", date(1995, 3, 1), id="dalf-tres-ancien"),
        pytest.param("DELF", None, id="delf-sans-date"),
        pytest.param("DALF", None, id="dalf-sans-date"),
    ],
)
def test_delf_et_dalf_sont_sans_expiration_meme_tres_anciens_ou_sans_date(type_cert, date_passage):
    resultat = evaluer_validite(type_cert, date_passage, REFERENCE_NEUTRE)

    assert resultat == ValiditeCertificat(statut="sans_expiration", fin=None)


# ============================================================ statuts non vérifiables


def test_type_absent_donne_non_verifiable_type_absent():
    resultat = evaluer_validite(None, PASSAGE_TCF, REFERENCE_NEUTRE)

    assert resultat == ValiditeCertificat(statut="non_verifiable_type_absent", fin=None)


def test_type_absent_et_date_absente_donne_non_verifiable_type_absent():
    resultat = evaluer_validite(None, None, REFERENCE_NEUTRE)

    assert resultat == ValiditeCertificat(statut="non_verifiable_type_absent", fin=None)


@pytest.mark.parametrize("type_cert", ["TOEIC", "IELTS", "TOEFL"])
def test_autre_type_donne_non_verifiable_type(type_cert):
    resultat = evaluer_validite(type_cert, PASSAGE_TCF, REFERENCE_NEUTRE)

    assert resultat == ValiditeCertificat(statut="non_verifiable_type", fin=None)


def test_tcf_sans_date_donne_non_verifiable_date_absente():
    resultat = evaluer_validite("TCF", None, REFERENCE_NEUTRE)

    assert resultat == ValiditeCertificat(statut="non_verifiable_date_absente", fin=None)


def test_tcf_date_posterieure_a_la_reference_donne_date_incoherente():
    resultat = evaluer_validite("TCF", date(2026, 11, 15), date(2026, 11, 14))

    assert resultat == ValiditeCertificat(statut="date_incoherente", fin=None)


# ============================================================ date de référence explicite


def test_meme_entree_avec_references_differentes_donne_des_statuts_differents_et_la_meme_fin():
    references_et_statuts = [
        (date(2024, 11, 14), "valide"),
        (date(2026, 11, 14), "valide"),
        (date(2026, 11, 15), "expire"),
        (date(2030, 1, 1), "expire"),
    ]

    for reference, statut_attendu in references_et_statuts:
        resultat = evaluer_validite("TCF", PASSAGE_TCF, reference)
        assert resultat.statut == statut_attendu, reference
        assert resultat.fin == FIN_TCF, reference


def test_resultat_deterministe_pour_des_entrees_identiques():
    premier = evaluer_validite("TCF", PASSAGE_TCF, REFERENCE_NEUTRE)
    second = evaluer_validite("TCF", PASSAGE_TCF, REFERENCE_NEUTRE)

    assert premier == second


def test_validite_certificat_est_immuable():
    resultat = evaluer_validite("TCF", PASSAGE_TCF, REFERENCE_NEUTRE)

    with pytest.raises(FrozenInstanceError):
        resultat.statut = "expire"  # type: ignore[misc]
