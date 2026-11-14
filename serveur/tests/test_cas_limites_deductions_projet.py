"""Cas limites purs : déductions du dossier et contrôle du projet professionnel.

Aucune base, aucune API : fonctions pures et faux client LLM uniquement.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from app.services.deductions_dossier import (
    ALERTE_DATE_ABSENTE,
    ALERTE_DATE_INCOHERENTE,
    ALERTE_EXPIRE,
    ALERTE_NON_VERIFIABLE,
    ALERTE_TYPE_ABSENT,
    MENTION,
    RANG,
    FaitConfirme,
    ajouter_mois,
    deduire,
    evaluer_validite,
)
from app.services.extraction_champs import MOYENNE_GENERALE, NIVEAU_FRANCAIS
from app.services.lettres_motivation import FaitsParcours
from app.services.llm import ReponseLLM
from app.services.projet_professionnel import controler_texte, generer_texte

REFERENCE = date(2026, 11, 14)
DOCUMENT = uuid.UUID(int=1)
PASSAGE_TCF = date(2024, 11, 14)  # fin de validité : 14/11/2026


def fait(champ: str, valeur: str, extrait: str = "ligne 4 du relevé") -> FaitConfirme:
    return FaitConfirme(document_id=DOCUMENT, champ=champ, valeur=valeur, page=1, extrait=extrait)


class FauxClientLLM:
    """Client LLM factice : renvoie toujours le même texte, sans appel réseau."""

    def __init__(self, texte: str) -> None:
        self._texte = texte

    def generer(self, *, systeme: str, message: str, max_tokens: int, **_: object) -> ReponseLLM:
        return ReponseLLM(texte=self._texte)


# ============================================================ (1) ajouter_mois
@pytest.mark.parametrize(
    ("depart", "mois", "attendu"),
    [
        (date(2026, 1, 31), 1, date(2026, 2, 28)),
        (date(2024, 2, 29), 12, date(2025, 2, 28)),
        (date(2024, 2, 29), 24, date(2026, 2, 28)),
        (date(2026, 3, 31), 1, date(2026, 4, 30)),
        (date(2025, 12, 31), 1, date(2026, 1, 31)),
    ],
)
def test_ajouter_mois_ramene_au_dernier_jour_du_mois_cible(depart, mois, attendu):
    assert ajouter_mois(depart, mois) == attendu


# ============================================================ (2) evaluer_validite
@pytest.mark.parametrize(
    ("reference", "alerte_attendue"),
    [
        (date(2026, 11, 13), None),
        (date(2026, 11, 14), None),
        (date(2026, 11, 15), ALERTE_EXPIRE),
    ],
    ids=["veille_du_24e_mois", "jour_du_24e_mois", "lendemain_du_24e_mois"],
)
def test_tcf_expire_seulement_le_lendemain_du_24e_mois(reference, alerte_attendue):
    _, alerte = evaluer_validite("TCF", PASSAGE_TCF, reference)

    assert alerte == alerte_attendue


def test_tcf_expire_affiche_la_date_de_fin_exacte():
    libelle, _ = evaluer_validite("TCF", PASSAGE_TCF, date(2026, 11, 15))

    assert libelle == "expiré depuis le 14/11/2026"


@pytest.mark.parametrize("type_cert", ["DELF", "DALF"])
def test_delf_et_dalf_sans_expiration_meme_tres_anciens(type_cert):
    resultat = evaluer_validite(type_cert, date(1990, 1, 1), REFERENCE)

    assert resultat == ("sans date d'expiration", None)


@pytest.mark.parametrize(
    ("type_cert", "passage", "alerte_attendue"),
    [
        ("IELTS", date(2025, 1, 1), ALERTE_NON_VERIFIABLE),
        (None, date(2025, 1, 1), ALERTE_TYPE_ABSENT),
        ("TCF", None, ALERTE_DATE_ABSENTE),
        ("TCF", date(2026, 11, 15), ALERTE_DATE_INCOHERENTE),
    ],
    ids=["ielts_non_verifiable", "type_absent", "tcf_sans_date", "tcf_date_future"],
)
def test_validite_jamais_deduite_pour_cas_non_verifiables(type_cert, passage, alerte_attendue):
    libelle, alerte = evaluer_validite(type_cert, passage, REFERENCE)

    assert libelle.startswith("validité non vérifiable")
    assert alerte == alerte_attendue


# ============================================================ (3) deduire
@pytest.mark.parametrize(
    ("champ", "valeur", "extrait", "textes_attendus"),
    [
        (MOYENNE_GENERALE, "20", "ligne 4 du relevé", ["Moyenne générale de 20/20"]),
        (MOYENNE_GENERALE, "20,5", "ligne 4 du relevé", []),
        (MENTION, "Excellente", "ligne 4 du relevé", []),
        (MENTION, "très bien", "ligne 4 du relevé", ["Mention Très bien"]),
        (RANG, "5 sur 3", "ligne 4 du relevé", []),
        (RANG, "5", "ligne 4 du relevé", ["Rang 5"]),
        (NIVEAU_FRANCAIS, "Z9", "ligne 4 du relevé", []),
        (MOYENNE_GENERALE, "15", "   ", []),
    ],
    ids=[
        "moyenne_20_retenue", "moyenne_20_5_ignoree", "mention_inconnue_ignoree",
        "mention_accentuee_retenue", "rang_hors_effectif_ignore", "rang_sans_effectif_retenu",
        "niveau_z9_ignore", "extrait_vide_aucun_point",
    ],
)
def test_deduire_applique_les_regles_de_validite_des_faits(champ, valeur, extrait, textes_attendus):
    points = deduire([fait(champ, valeur, extrait)], REFERENCE)

    assert [p.texte for p in points] == textes_attendus


# ============================================================ (4) controler_texte
def test_virgule_et_point_decimal_sont_equivalents():
    elements = controler_texte("Moyenne de 14,5 sur 20.", "Moyenne générale 14.50 sur 20")

    assert elements == []


def test_chiffre_invente_est_signale():
    elements = controler_texte("J'ai 17 ans d'expérience.", "Licence en droit")

    assert elements == ["Chiffre « 17 » absent des faits fournis."]


def test_certificat_cite_et_absent_des_faits_est_signale():
    elements = controler_texte("Je possède le TCF.", "Licence en droit")

    assert elements == ["Certificat « TCF » absent des faits fournis."]


def test_baccalaureat_equivaut_a_bac():
    elements = controler_texte("Titulaire du baccalauréat.", "Bac série S")

    assert elements == []


def test_master_cite_alors_que_les_faits_donnent_une_licence_est_signale():
    elements = controler_texte("Je vise un master en droit.", "Licence en droit")

    assert elements == ["Diplôme « master » absent des faits fournis."]


def test_marqueur_signale_sans_compter_son_chiffre_comme_invente():
    texte = "Projet : [À COMPLÉTER : x 99] ; formation visée."

    elements = controler_texte(texte, "Licence en droit")

    assert elements == ["Des marqueurs « [À COMPLÉTER » restent dans le texte."]


# ============================================================ (5) generer_texte
def test_sans_client_le_texte_modele_contient_un_marqueur_a_completer():
    faits = FaitsParcours(parcours=[], points_forts=[], langues=[])

    resultat = generer_texte(None, faits=faits, programme=None)

    assert "[À COMPLÉTER" in resultat.texte
    assert resultat.origine == "modele"
    assert resultat.elements_a_verifier


def test_faux_client_citant_un_toefl_absent_des_faits_est_signale():
    client = FauxClientLLM("Je possède le TOEFL 100 et une licence en droit.")
    faits = FaitsParcours(parcours=["Licence en droit"], points_forts=[], langues=[])

    resultat = generer_texte(client, faits=faits, programme=None)

    assert resultat.origine == "ia"
    assert resultat.elements_a_verifier
    assert any("TOEFL" in element for element in resultat.elements_a_verifier)
