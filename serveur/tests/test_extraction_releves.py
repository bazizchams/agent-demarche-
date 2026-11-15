"""Parseur des relevés de notes et diplômes algériens (corpus SYNTHÉTIQUE uniquement).

Règle 4 : valeur = extrait littéral ancré ; rien n'est déduit ; une lecture douteuse (OCR,
date impossible, deux valeurs) est marquée `valide=False` et n'est jamais « choisie ».
"""

from __future__ import annotations

import unicodedata

import pytest

from app.services.extraction_champs import (
    DIPLOME_ETABLISSEMENT,
    DIPLOME_INTITULE,
    MENTION,
    RANG,
    extraire_champs,
    famille_pour_type_piece,
    valeur_valide,
)
from app.services.extraction_releves import analyser_releve
from app.services.fusion_extractions import valeur_ancree
from tests import bruit_ocr_cible as bruit
from tests import corpus_releves_synthetique as base
from tests.corpus_releves_complement import DOCUMENTS_COMPLEMENT

TOUS = base.DOCUMENTS + DOCUMENTS_COMPLEMENT


def _sa(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn")


def _valides(texte: str) -> dict[str, str]:
    return {c.champ: c.valeur for c in analyser_releve(texte, 1) if c.valide}


@pytest.mark.parametrize("doc", TOUS, ids=lambda d: d.nom)
def test_valeurs_attendues_lues_exactement(doc) -> None:
    lus = _valides(doc.texte)
    for champ, attendu in doc.attendu.items():
        assert lus.get(champ) == attendu, (champ, lus.get(champ))


@pytest.mark.parametrize("doc", TOUS, ids=lambda d: d.nom)
def test_champs_absents_jamais_valides(doc) -> None:
    lus = _valides(doc.texte)
    for champ in doc.absents:
        assert champ not in lus, champ


@pytest.mark.parametrize("doc", TOUS, ids=lambda d: d.nom)
def test_chaque_valeur_a_un_extrait_litteral_ancre_et_une_page(doc) -> None:
    for c in analyser_releve(doc.texte, 3):
        assert c.page == 3
        assert c.extrait.strip() and c.extrait.strip() in doc.texte
        assert valeur_ancree(c, doc.texte), (c.champ, c.valeur, c.extrait)


@pytest.mark.parametrize("doc", TOUS, ids=lambda d: d.nom)
def test_toute_valeur_valide_respecte_valeur_valide(doc) -> None:
    for c in analyser_releve(doc.texte, 1):
        if c.valide:
            assert valeur_valide(c.champ, c.valeur), (c.champ, c.valeur)
        if c.champ.startswith("moyenne") and c.valide:
            assert 0 <= float(c.valeur) <= 20


def _variantes(doc) -> dict[str, str]:
    return {**base.variantes_bruitees(doc), **bruit.variantes_ciblees(doc.texte)}


@pytest.mark.parametrize("doc", TOUS, ids=lambda d: d.nom)
def test_variantes_bruitees_jamais_de_valeur_fausse_validee(doc) -> None:
    propre = _valides(doc.texte)
    for nom, texte in _variantes(doc).items():
        for champ, valeur in _valides(texte).items():
            assert champ in propre, (nom, champ, valeur)
            assert _sa(valeur) == _sa(propre[champ]), (nom, champ, valeur, propre[champ])


@pytest.mark.parametrize("doc", TOUS, ids=lambda d: d.nom)
def test_variantes_sans_perte_de_sens_donnent_les_memes_valeurs(doc) -> None:
    propre = {c: _sa(v) for c, v in _valides(doc.texte).items()}
    for nom in ("accents_perdus", "virgule_point", "espaces_parasites"):
        lus = {c: _sa(v) for c, v in _valides(base.variantes_bruitees(doc)[nom]).items()}
        assert lus == propre, nom
    assert {c: _sa(v) for c, v in _valides(bruit.accents_perdus(doc.texte)).items()} == propre
    assert {c: _sa(v) for c, v in _valides(bruit.virgule_perdue(doc.texte)).items()} == propre


def test_chiffres_confondus_proposes_mais_jamais_valides_en_silence() -> None:
    texte = (
        "Moyenne du semestre 3 : l2,85\nCrédits acquis semestre 3 : 3O\nRang : l2/42\n"
        "Né(e) le : l2/08/2001 à Alger"
    )
    par_champ = {c.champ: c for c in analyser_releve(texte, 1)}
    assert par_champ["moyenne_semestre_3"].valeur == "12.85" and not par_champ["moyenne_semestre_3"].valide
    assert par_champ["moyenne_semestre_3"].motif == "ocr_a_confirmer"
    assert par_champ["credits_semestre_3"].valeur == "30" and not par_champ["credits_semestre_3"].valide
    assert par_champ["rang"].valeur == "12/42" and not par_champ["rang"].valide
    assert par_champ["date_naissance"].valeur == "2001-08-12" and not par_champ["date_naissance"].valide
    for c in par_champ.values():
        assert valeur_ancree(c, texte), c.champ


def test_moyenne_generale_ocr_n_est_pas_tronquee() -> None:
    (c,) = [x for x in analyser_releve("Moyenne générale : 1O,5\n", 1) if x.champ == "moyenne_generale"]
    assert not c.valide and c.valeur == "10.5"
    assert [x for x in analyser_releve("Moyenne générale : 14,5O\n", 1) if x.valide] == []


def test_texte_vide_ou_sans_information_ne_produit_rien() -> None:
    for t in ("", "Lorem ipsum 12 dolor", "Moyenne : 12\nRang\nMention\n"):
        assert analyser_releve(t, 1) == []


def test_mention_jamais_deduite_de_la_moyenne() -> None:
    assert "mention" not in _valides("Moyenne générale : 17,50/20\n")


@pytest.mark.parametrize(
    ("ligne", "valeur"),
    [
        ("Mention : Très bien", "Très bien"),
        ("Mention : Tres Bien", "Très bien"),
        ("MENTION ASSEZ BIEN", "Assez bien"),
        ("Mention : Passable", "Passable"),
        ("Mention: Bien", "Bien"),
    ],
)
def test_mentions(ligne: str, valeur: str) -> None:
    assert _valides(ligne) == {MENTION: valeur}


@pytest.mark.parametrize(
    ("ligne", "valeur"),
    [
        ("Rang : 5", "5"),
        ("Rang : 5ème / 120", "5/120"),
        ("Classement : 12 sur 150", "12/150"),
        ("Rang : 3 sur 45", "3/45"),
    ],
)
def test_rangs(ligne: str, valeur: str) -> None:
    assert _valides(ligne) == {RANG: valeur}


def test_rang_incoherent_ou_nul_invalide() -> None:
    for ligne in ("Rang : 0", "Rang : 50/42"):
        (c,) = analyser_releve(ligne, 1)
        assert not c.valide


def test_bareme_different_et_hors_bornes_invalides() -> None:
    (c,) = analyser_releve("Moyenne du semestre 1 : 14/10", 1)
    assert not c.valide and c.motif == "bareme_different"
    (c,) = analyser_releve("Moy. S2 : 23,5", 1)
    assert not c.valide and c.motif == "moyenne_hors_bornes"


def test_semestre_hors_plage_ignore() -> None:
    assert analyser_releve("Moyenne du semestre 11 : 12,00", 1) == []


def test_intitule_prioritaire_sur_mention_incidente() -> None:
    texte = "RELEVÉ DE NOTES — MASTER 1\nTitulaire d'une Licence en informatique\n"
    assert _valides(texte)[DIPLOME_INTITULE] == "Master"


def test_deux_intitules_concurrents_sont_ambigus() -> None:
    (c,) = [x for x in analyser_releve("Diplôme de Licence\nDiplôme : Master\n", 1) if x.champ == DIPLOME_INTITULE]
    assert not c.valide and c.motif == "valeurs_multiples"


def test_etablissement_ministere_ignore_et_deux_universites_ambigues() -> None:
    assert DIPLOME_ETABLISSEMENT not in _valides("MINISTÈRE DE L'ENSEIGNEMENT SUPÉRIEUR\n")
    lus = analyser_releve("Université Fictive A\nUniversité Fictive B\n", 1)
    (c,) = [x for x in lus if x.champ == DIPLOME_ETABLISSEMENT]
    assert not c.valide


def test_texte_avec_chiffre_colle_a_une_lettre_est_suspect() -> None:
    lus = analyser_releve("Établissement : Université de Sab1e\n", 1)
    (c,) = [x for x in lus if x.champ == DIPLOME_ETABLISSEMENT]
    assert not c.valide and c.motif == "ocr_suspect"


def test_date_naissance_implausible_ou_impossible_non_validee() -> None:
    assert "date_naissance" not in _valides("Né(e) le 31/02/2000 à Alger")
    assert "date_naissance" not in _valides("Né(e) le 01/01/1800 à Alger")


def test_extraire_champs_releve_multi_pages_et_valeurs_multiples() -> None:
    assert famille_pour_type_piece("diplomes_et_releves") == "releve_notes"
    pages = [(1, "Moyenne du semestre 1 : 12,00"), (2, "Moyenne du semestre 1 : 13,00\nMoyenne du semestre 2 : 11,00")]
    par = {c.champ: c for c in extraire_champs("releve_notes", pages)}
    assert not par["moyenne_semestre_1"].valide and par["moyenne_semestre_1"].motif == "valeurs_multiples"
    assert par["moyenne_semestre_2"].valide and par["moyenne_semestre_2"].page == 2


def test_moyenne_annuelle_distincte_de_la_generale() -> None:
    assert _valides("Moyenne annuelle : 14,07\n") == {"moyenne_annuelle": "14.07"}


@pytest.mark.parametrize(
    ("champ", "valeur", "attendu"),
    [
        ("mention", "Très bien", True), ("mention", "Super", False),
        ("rang", "12/150", True), ("rang", "0", False),
        ("diplome_annee", "2022", True), ("diplome_annee", "1900", False),
        ("annee_universitaire", "2021/2022", True), ("annee_universitaire", "2021/2023", False),
        ("moyenne_semestre_3", "12.5", True), ("moyenne_semestre_3", "21", False),
        ("credits_semestre_1", "30", True), ("credits_semestre_1", "abc", False),
        ("numero_bac", "19123456", True), ("session", "Juin 2024", True),
        ("decision_jury", "Admis", True), ("decision_jury", "Peut-être", False),
        ("diplome_intitule", "Licence", True), ("lieu_naissance", "A1ger", False),
    ],
)
def test_valeur_valide_nouveaux_champs(champ: str, valeur: str, attendu: bool) -> None:
    assert valeur_valide(champ, valeur) is attendu


def test_bareme_illisible_n_est_pas_ignore() -> None:
    for texte in ("Moyenne générale : 14/I0", "Moyenne générale : 14/2O", "Rang : 5/4O", "Moyenne annuelle : 12/2O"):
        assert _valides(texte) == {}, texte


def test_les_champs_lus_declenchent_les_points_forts_de_deductions_dossier() -> None:
    import uuid
    from datetime import date as _date

    from app.services.deductions_dossier import FaitConfirme, deduire

    doc = base.par_nom("diplome_master")
    rang_doc = _valides("Rang : 5/42")
    lus = {**_valides(doc.texte), **rang_doc}
    ident = uuid.uuid4()
    faits = [FaitConfirme(ident, c, v, 1, f"{c}: {v}") for c, v in lus.items()]
    regles = {p.regle for p in deduire(faits, _date(2026, 11, 14))}
    assert {"mention", "rang", "parcours", "moyenne_generale"} <= regles


def test_diplome_sans_releve_de_notes_est_propose_comme_releve() -> None:
    from app.services.classification_pieces import deviner_type_piece

    for nom in ("diplome_licence", "diplome_master", "diplome_deua"):
        c = deviner_type_piece([(1, base.par_nom(nom).texte)])
        assert c.famille == "releve_notes", nom
        assert c.confirmation_humaine_requise or c.confiance >= 0.9


def test_moyenne_sans_qualificatif_en_debut_de_ligne_est_lue() -> None:
    """Recette : « Moyenne 13,10/20 » sur un relevé de licence donnait seulement « Licence »."""
    lus = _valides("RELEVÉ DE NOTES\nLicence en informatique\nMoyenne 13,10/20")
    assert lus.get("moyenne_generale") == "13.1"
    assert lus.get("diplome_intitule") == "Licence"


def test_moyenne_sans_qualificatif_jamais_inventee() -> None:
    # En-tête de tableau, moyenne de semestre, barème différent, ligne de module : jamais une moyenne générale.
    assert "moyenne_generale" not in _valides("Licence\nUnité | Module | Coef | Crédits | Moyenne |")
    assert "moyenne_generale" not in _valides("Licence\nMoyenne du semestre 3 : 12,85")
    assert "moyenne_generale" not in _valides("Licence\nAlgorithmique  Moyenne 13,10/20")
    assert "moyenne_generale" not in _valides("Licence\nMoyenne 13,10/40")
    assert "moyenne_generale" not in _valides("Licence\nSans moyenne")
