"""Lecture réelle (RapidOCR) d'images et de PDF scannés SYNTHÉTIQUES + réparation de la MRZ."""

from __future__ import annotations

import pytest

from app.services.extraction_champs import extraire_champs, reparer_lignes_mrz
from tests import corpus_synthetique as corpus

L1 = corpus.MRZ_L1_VALIDE
L2 = corpus.MRZ_L2_VALIDE


def test_reparation_mrz_corrige_les_confusions_o_zero_et_le_remplissage() -> None:
    l1 = L1.replace("O", "0", 1) if "O" in L1 else L1
    assert reparer_lignes_mrz(l1, L2) == (L1, L2)
    assert reparer_lignes_mrz(L1, L2.replace("<<<<<", "<<<<")) == (L1, L2)  # remplissage trop court


def test_reparation_mrz_refuse_si_un_chiffre_de_controle_reste_faux() -> None:
    assert reparer_lignes_mrz(L1, corpus.MRZ_L2_INVALIDE) is None
    assert reparer_lignes_mrz(L1, "2>>>>>>>>>>>>>>>00606L29L862") is None  # ligne illisible : aucune valeur inventée
    assert reparer_lignes_mrz("RIEN", L2) is None


@pytest.fixture(scope="module")
def cas() -> dict:
    pytest.importorskip("rapidocr")
    pytest.importorskip("PIL")
    from tests.outils_corpus_ocr import fabriquer_corpus  # noqa: PLC0415

    return {c.nom: c for c in fabriquer_corpus()}


@pytest.mark.parametrize(
    "nom",
    ["passeport_01_propre", "passeport_04_pdf_scanne", "passeport_03_bruit", "releve_notes_01_rotation",
     "releve_notes_02_pdf_scanne", "certificat_langue_01_flou"],
)
def test_lecture_ocr_de_documents_synthetiques_sans_valeur_fausse(cas: dict, nom: str) -> None:
    from app.services.lecture_documents import LecteurDocumentLocal  # noqa: PLC0415

    c = cas[nom]
    lecture = LecteurDocumentLocal().lire_texte(c.octets, c.type_mime)
    lus = {f.champ: f.valeur for f in extraire_champs(c.famille, [(p.numero, p.texte) for p in lecture.pages])}
    faux = {k: (lus[k], v) for k, v in c.attendu.items() if k in lus and lus[k] != v}
    absents = [k for k in c.attendu if k not in lus]
    assert faux == {} and absents == []
