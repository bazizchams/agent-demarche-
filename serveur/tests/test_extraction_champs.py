"""Parseurs déterministes : MRZ (ICAO 9303), dates, moyennes, certificats de langue.

Règle 4 : un texte sans information ne produit AUCUNE valeur ; une valeur douteuse est marquée
invalide au lieu d'être corrigée ou devinée.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services.extraction_champs import (
    analyser_certificat_langue,
    analyser_date,
    analyser_moyenne,
    analyser_mrz,
    calculer_chiffre_controle,
    extraire_champs,
    famille_pour_type_piece,
    valeur_valide,
)
from tests import corpus_synthetique as corpus


def _par_champ(champs):
    return {c.champ: c for c in champs}


def test_chiffre_controle_conforme_au_specimen_oaci() -> None:
    assert calculer_chiffre_controle("L898902C3") == "6"
    assert calculer_chiffre_controle("740812") == "2"
    assert calculer_chiffre_controle("120415") == "9"
    assert calculer_chiffre_controle("ZE184226B<<<<<") == "1"


def test_chiffre_controle_construit_par_le_corpus_identique() -> None:
    for champ in ("L898902C3", "740812", "AB1234567"):
        assert calculer_chiffre_controle(champ) == corpus.chiffre_controle(champ)


def test_mrz_valide_extrait_tous_les_champs_avec_controle_fort() -> None:
    champs = _par_champ(analyser_mrz(corpus.TEXTE_PASSEPORT_VALIDE, page=1))
    assert champs["numero_passeport"].valeur == "L898902C3"
    assert champs["date_naissance"].valeur == "1974-08-12"
    assert champs["date_expiration_passeport"].valeur == "2012-04-15"
    assert champs["sexe"].valeur == "F"
    assert champs["nom"].valeur == "ERIKSSON"
    assert champs["prenom"].valeur == "ANNA MARIA"
    assert champs["nationalite_code"].valeur == "UTO"
    for nom in ("numero_passeport", "date_naissance", "date_expiration_passeport", "sexe"):
        assert champs[nom].valide and champs[nom].controle_fort and champs[nom].confiance == 1.0
    # Les noms et la nationalité n'ont pas de chiffre de contrôle propre : jamais « fort ».
    for nom in ("nom", "prenom", "nationalite_code"):
        assert not champs[nom].controle_fort
    assert corpus.MRZ_L2_VALIDE in champs["numero_passeport"].extrait
    assert champs["numero_passeport"].page == 1


def test_mrz_chiffre_de_controle_faux_invalide_le_champ_et_retire_le_controle_fort() -> None:
    champs = _par_champ(analyser_mrz(corpus.TEXTE_PASSEPORT_INVALIDE, page=2))
    assert champs["numero_passeport"].valide is False
    assert champs["numero_passeport"].motif == "mrz_controle_invalide"
    assert champs["numero_passeport"].confiance <= 0.3
    # Le contrôle composite échoue : plus aucun champ n'est vérifié par somme de contrôle.
    assert all(not c.controle_fort for c in champs.values())
    assert champs["date_naissance"].confiance < 1.0
    assert champs["numero_passeport"].page == 2


def test_mrz_dans_un_texte_bruite_avec_espaces_parasites() -> None:
    champs = _par_champ(analyser_mrz(corpus.TEXTE_PASSEPORT_BRUITE, page=1))
    assert champs["numero_passeport"].valeur == "L898902C3"
    assert champs["numero_passeport"].controle_fort


def test_mrz_construite_avec_sexe_non_specifie_ne_donne_pas_de_sexe() -> None:
    l1, l2 = corpus.construire_mrz(
        nom="TESTEUR", prenoms="PAUL", numero="AB1234567",
        naissance_aammjj="050101", sexe="<", expiration_aammjj="340101",
    )
    champs = _par_champ(analyser_mrz(l1 + "\n" + l2))
    assert "sexe" not in champs
    assert champs["date_naissance"].valeur == "2005-01-01"
    assert champs["date_expiration_passeport"].valeur == "2034-01-01"


def test_texte_sans_mrz_ne_produit_aucune_valeur() -> None:
    assert analyser_mrz("Bonjour, ceci n'est pas un passeport.\n") == []
    assert analyser_mrz("") == []


@pytest.mark.parametrize(
    ("texte", "attendu"),
    [
        ("12/03/2024", date(2024, 3, 12)),
        ("12.03.2024", date(2024, 3, 12)),
        ("12-03-2024", date(2024, 3, 12)),
        ("2024-03-12", date(2024, 3, 12)),
        ("le 12 mars 2024", date(2024, 3, 12)),
        ("1er février 2025", date(2025, 2, 1)),
        ("14 March 2025", date(2025, 3, 14)),
        ("31/02/2024", None),
        ("12/03/24", None),
        ("pas de date", None),
        ("", None),
    ],
)
def test_analyser_date(texte: str, attendu: date | None) -> None:
    assert analyser_date(texte) == attendu


def test_moyenne_valide() -> None:
    champs = analyser_moyenne(corpus.TEXTE_RELEVE_BAC, page=1)
    assert len(champs) == 1
    c = champs[0]
    assert (c.champ, c.valeur, c.valide, c.page) == ("moyenne_generale", "14.52", True, 1)
    assert "14,52" in c.extrait


def test_moyenne_hors_bornes_est_marquee_invalide() -> None:
    (c,) = analyser_moyenne("Moyenne générale : 25/20", page=1)
    assert c.valide is False and c.motif == "moyenne_hors_bornes"


def test_moyenne_sur_un_autre_bareme_est_marquee_invalide() -> None:
    (c,) = analyser_moyenne("Moyenne générale : 14/10", page=1)
    assert c.valide is False and c.motif == "bareme_different"


def test_moyenne_bornes_incluses() -> None:
    assert analyser_moyenne("Moyenne générale : 20", page=1)[0].valide
    assert analyser_moyenne("Moyenne générale : 0", page=1)[0].valide


def test_moyenne_ambigue_ou_absente() -> None:
    (c,) = analyser_moyenne("Moyenne générale : 12\nMoyenne annuelle : 15\n", page=1)
    assert c.valide is False and c.motif == "moyenne_ambigue"
    assert analyser_moyenne("Mathématiques : 15,00\nPhysique : 13\n", page=1) == []


def test_certificat_tcf_niveau_et_date() -> None:
    champs = _par_champ(analyser_certificat_langue(corpus.TEXTE_TCF, page=1))
    assert champs["certificat_langue_type"].valeur == "TCF"
    assert champs["niveau_francais"].valeur == "B2" and champs["niveau_francais"].valide
    assert champs["certificat_langue_date"].valeur == "2025-03-12"


def test_certificat_delf_et_incoherence_niveau_diplome() -> None:
    champs = _par_champ(analyser_certificat_langue(corpus.TEXTE_DELF_B1, page=1))
    assert champs["certificat_langue_type"].valeur == "DELF"
    assert champs["niveau_francais"].valeur == "B1"
    assert champs["certificat_langue_date"].valeur == "2024-06-03"
    incoherent = _par_champ(analyser_certificat_langue(corpus.TEXTE_DELF_INCOHERENT, page=1))
    assert incoherent["niveau_francais"].valide is False
    assert incoherent["niveau_francais"].motif == "niveau_incoherent_avec_diplome"
    assert "certificat_langue_date" not in incoherent  # aucune date lisible : aucune date inventée


def test_certificat_dalf() -> None:
    champs = _par_champ(analyser_certificat_langue("DALF — Niveau C2\nDate de passation : 01/07/2023\n", page=1))
    assert champs["certificat_langue_type"].valeur == "DALF"
    assert champs["niveau_francais"].valeur == "C2" and champs["niveau_francais"].valide


def test_certificat_tcf_par_competence_sans_niveau_global_est_ambigu() -> None:
    champs = _par_champ(analyser_certificat_langue(corpus.TEXTE_TCF_PAR_COMPETENCE, page=1))
    assert champs["niveau_francais"].valide is False
    assert champs["niveau_francais"].motif == "niveau_ambigu"


def test_certificat_ielts_bande_sans_conversion_en_cecrl() -> None:
    champs = _par_champ(analyser_certificat_langue(corpus.TEXTE_IELTS, page=1))
    assert champs["certificat_langue_type"].valeur == "IELTS"
    assert champs["ielts_bande"].valeur == "6.5" and champs["ielts_bande"].valide
    assert champs["certificat_langue_date"].valeur == "2025-03-14"
    # La bande n'est jamais convertie en niveau CECRL (ce serait une valeur inventée).
    assert "niveau_anglais" not in champs and "niveau_francais" not in champs


def test_certificat_ielts_cecrl_explicite_et_bande_hors_bornes() -> None:
    champs = _par_champ(analyser_certificat_langue(corpus.TEXTE_IELTS_CECRL, page=1))
    assert champs["niveau_anglais"].valeur == "C1"
    hors = _par_champ(analyser_certificat_langue("IELTS\nOverall Band Score 9.5\n", page=1))
    assert hors["ielts_bande"].valide is False and hors["ielts_bande"].motif == "bande_hors_bornes"


def test_certificat_absent() -> None:
    assert analyser_certificat_langue("Relevé de notes sans certificat.", page=1) == []


def test_famille_pour_type_piece() -> None:
    assert famille_pour_type_piece("passeport") == "passeport"
    assert famille_pour_type_piece("releve_notes_bac") == "releve_notes"
    assert famille_pour_type_piece("diplomes_et_releves") == "releve_notes"
    assert famille_pour_type_piece("resultats_test_langue") == "certificat_langue"
    assert famille_pour_type_piece("attestation_langue_francaise") == "certificat_langue"
    assert famille_pour_type_piece("cv") is None


def test_extraire_champs_par_famille_et_pages() -> None:
    pages = [(1, "Page de garde sans valeur"), (2, corpus.TEXTE_PASSEPORT_VALIDE)]
    champs = _par_champ(extraire_champs("passeport", pages))
    assert champs["numero_passeport"].page == 2
    assert extraire_champs("famille_inconnue", pages) == []


@pytest.mark.parametrize(
    ("champ", "valeur", "attendu"),
    [
        ("date_naissance", "1974-08-12", True),
        ("date_naissance", "12/08/1974", False),
        ("date_naissance", "1974-13-45", False),
        ("sexe", "F", True),
        ("sexe", "X", False),
        ("moyenne_generale", "14.52", True),
        ("moyenne_generale", "21", False),
        ("moyenne_generale", "abc", False),
        ("niveau_francais", "B2", True),
        ("niveau_francais", "D1", False),
        ("numero_passeport", "L898902C3", True),
        ("numero_passeport", "  ", False),
        ("champ_inconnu", "x", False),
    ],
)
def test_valeur_valide(champ: str, valeur: str, attendu: bool) -> None:
    assert valeur_valide(champ, valeur) is attendu
