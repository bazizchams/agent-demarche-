"""Analyse des prérequis de langue d'une formation (Études en France) : extraction et adéquation."""

from __future__ import annotations

import pytest

from app.services.prerequis_formation import (
    NIVEAUX_CECRL,
    ExigenceLangue,
    analyser_prerequis,
    evaluer_adequation,
)

TEXTE_1 = "Niveau de langue française exigé : C1 (TCF, DELF, DALF, etc...)"
TEXTE_2 = (
    "Pour les candidats étrangers, un certificat attestant le niveau de compétences en français (C1)"
    "Pour tous les candidats : un certificat attestant le niveau de compétences en anglais (B2)."
)
TEXTE_3 = (
    "Niveau de français : Le niveau 4 du référentiel européen (B2 pour le TCF) est exigé pour tous "
    "les candidats qui ne sont pas originaires de pays francophones où le français est la langue "
    "officielle à titre exclusif. La priorité sera accordée aux candidats attestant d'un niveau C1."
)
TEXTE_4 = "Avoir un niveau C1 minimum au TCF"
TEXTE_5 = "Formation ... Niveau B2 exigé en français"
TEXTE_6 = (
    "Attestation de langue française, niveau C1 du cadre européen de référence pour les langues "
    "(CECRL) minimum (DALF ou TCF complet : épreuves obligatoires et complémentaires)"
)
TEXTE_7_HTML = (
    "<p>Niveau&nbsp;<strong>B2</strong> exig&eacute; en fran&ccedil;ais.</p>"
    "<p>Pour les autres&nbsp;: sans objet.</p>"
)
TEXTE_8_URL = "https://www.etudes-en-france.fr/formation/12345"


@pytest.mark.parametrize(
    ("texte", "francais", "anglais", "priorite"),
    [
        (TEXTE_1, "C1", None, False),
        (TEXTE_2, "C1", "B2", False),
        (TEXTE_3, "B2", None, True),
        (TEXTE_4, "C1", None, False),
        (TEXTE_5, "B2", None, False),
        (TEXTE_6, "C1", None, False),
        (TEXTE_7_HTML, "B2", None, False),
    ],
)
def test_extraction_niveaux_cas_reels(texte, francais, anglais, priorite):
    exigence = analyser_prerequis(texte)
    assert exigence.francais_min == francais
    assert exigence.anglais_min == anglais
    assert exigence.priorite_c1 is priorite
    assert 1 <= len(exigence.extraits) <= 3
    assert all(len(e) <= 200 for e in exigence.extraits)


def test_priorite_c1_sans_exigence_c1():
    exigence = analyser_prerequis(TEXTE_3)
    assert exigence.francais_min == "B2"
    assert exigence.priorite_c1 is True


def test_texte_sans_mention_de_langue_donne_none():
    exigence = analyser_prerequis(TEXTE_8_URL)
    assert exigence.francais_min is None
    assert exigence.anglais_min is None
    assert exigence.priorite_c1 is False
    assert exigence.extraits == ()


@pytest.mark.parametrize("texte", [None, "", "   ", "<p>&nbsp;</p>"])
def test_texte_vide_donne_none(texte):
    exigence = analyser_prerequis(texte)
    assert exigence == ExigenceLangue(francais_min=None, anglais_min=None)


def test_exigence_est_immuable():
    exigence = analyser_prerequis(TEXTE_1)
    with pytest.raises(AttributeError):
        exigence.francais_min = "B1"  # type: ignore[misc]


def test_html_entites_et_espaces_normalises():
    exigence = analyser_prerequis(TEXTE_7_HTML)
    assert exigence.francais_min == "B2"
    assert all("<" not in e and "&" not in e for e in exigence.extraits)


def test_candidat_b2_contre_exigence_c1_insuffisant():
    exigence = ExigenceLangue(francais_min="C1", anglais_min=None)
    rapport = evaluer_adequation(exigence, francais_candidat="B2")
    assert rapport["statut"] == "insuffisant"
    assert "Français exigé : C1, niveau du candidat : B2" in rapport["messages"]


def test_candidat_c1_contre_exigence_b2_ok():
    exigence = ExigenceLangue(francais_min="B2", anglais_min=None)
    rapport = evaluer_adequation(exigence, francais_candidat="C1")
    assert rapport == {"statut": "ok", "messages": []}


def test_candidat_absent_donne_inconnu():
    exigence = ExigenceLangue(francais_min="C1", anglais_min=None)
    rapport = evaluer_adequation(exigence, francais_candidat=None)
    assert rapport["statut"] == "inconnu"
    assert rapport["messages"]


def test_priorite_c1_message_si_candidat_sous_c1():
    exigence = analyser_prerequis(TEXTE_3)
    rapport = evaluer_adequation(exigence, francais_candidat="B2")
    assert rapport["statut"] == "ok"
    assert "Priorité aux candidats C1" in rapport["messages"]


def test_priorite_c1_pas_de_message_si_candidat_c1():
    exigence = analyser_prerequis(TEXTE_3)
    rapport = evaluer_adequation(exigence, francais_candidat="C1")
    assert rapport == {"statut": "ok", "messages": []}


def test_anglais_manquant_donne_inconnu_sauf_si_insuffisant():
    exigence = analyser_prerequis(TEXTE_2)
    assert evaluer_adequation(exigence, francais_candidat="C1")["statut"] == "inconnu"
    assert evaluer_adequation(exigence, francais_candidat="B1")["statut"] == "insuffisant"
    rapport = evaluer_adequation(exigence, francais_candidat="C1", anglais_candidat="C1")
    assert rapport["statut"] == "ok"


def test_exigence_vide_donne_inconnu():
    rapport = evaluer_adequation(ExigenceLangue(None, None), francais_candidat="C2")
    assert rapport["statut"] == "inconnu"
    assert rapport["messages"]


def test_niveaux_cecrl_ordonnes():
    assert NIVEAUX_CECRL == ("A1", "A2", "B1", "B2", "C1", "C2")
