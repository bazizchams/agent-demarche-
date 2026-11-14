"""Corpus de test SYNTHÉTIQUE pour le futur parseur de relevés de notes et diplômes algériens.

Aucun vrai document : établissements, identités, notes, dates et numéros de bac sont FICTIFS.
Chaque document est une page de texte brut (lignes séparées par \\n), tel qu'une couche texte
ou un OCR idéal la fournirait. Pour chaque document :
- `attendu` : valeurs canoniques, uniquement pour ce qui est écrit sans ambiguïté ;
- `absents` : champs qui ne doivent PAS être produits (information absente, ambiguë ou douteuse).

`variantes_bruitees` produit des altérations réalistes (accents perdus, virgules décimales
remplacées par des points, confusions OCR, espaces parasites) sans jamais ajouter ni retirer
de lignes.
"""

from __future__ import annotations

import random
import re
import unicodedata
from dataclasses import dataclass

TYPES_PIECE = frozenset(
    {"releves_notes_superieur", "releve_notes_bac", "diplomes_et_releves", "diplome_bac"}
)
BORNE_MOYENNE = 20

# Substitutions OCR : un caractère -> un caractère (jamais de saut de ligne).
_SUBSTITUTIONS_OCR = {
    "0": "O",
    "O": "0",
    "l": "1",
    "é": "e",
    "è": "e",
    "ê": "e",
    "à": "a",
    "â": "a",
    "ô": "o",
    "û": "u",
    "ç": "c",
}
_CONFUSIONS_CHIFFRE_UN = ("l", "I")

_ENTETE_REPUBLIQUE = (
    "RÉPUBLIQUE ALGÉRIENNE DÉMOCRATIQUE ET POPULAIRE",
    "MINISTÈRE DE L'ENSEIGNEMENT SUPÉRIEUR ET DE LA RECHERCHE SCIENTIFIQUE",
)


@dataclass(frozen=True)
class DocumentSynthetique:
    nom: str
    type_piece: str
    texte: str
    attendu: dict[str, str]
    absents: tuple[str, ...]


def _page(*lignes: str) -> str:
    return "\n".join(lignes)


DOCUMENTS: tuple[DocumentSynthetique, ...] = (
    DocumentSynthetique(
        nom="releve_licence_s3",
        type_piece="releves_notes_superieur",
        texte=_page(
            *_ENTETE_REPUBLIQUE,
            "FACULTÉ DES SCIENCES EXACTES (FICTIVE) — DÉPARTEMENT D'INFORMATIQUE",
            "Établissement : Université Fictive de Sable-Rouge",
            "RELEVÉ DE NOTES — LICENCE — SEMESTRE 3",
            "Année universitaire : 2022/2023",
            "Nom : FICTIF",
            "Prénom : Karim",
            "Né(e) le : 12/08/2001 à : Alger",
            "Diplôme : Licence",
            "Filière : Mathématiques et informatique",
            "Spécialité : Informatique",
            "Unité | Module | Coef | Crédits | Moyenne |",
            "UE1 | Algorithmique avancée | 4 | 6 | 13,00 |",
            "UE1 | Structures de données | 3 | 5 | 12,50 |",
            "UE2 | Bases de données | 3 | 5 | 14,00 |",
            "UE2 | Programmation orientée objet | 3 | 5 | 11,75 |",
            "UE3 | Systèmes d'exploitation | 2 | 4 | 12,00 |",
            "UE3 | Réseaux informatiques | 2 | 5 | 13,50 |",
            "Moyenne du semestre 3 : 12,85",
            "Crédits acquis semestre 3 : 30",
            "Décision du jury : Admis(e)",
        ),
        attendu={
            "nom": "FICTIF",
            "prenom": "Karim",
            "date_naissance": "2001-08-12",
            "lieu_naissance": "Alger",
            "annee_universitaire": "2022/2023",
            "diplome_intitule": "Licence",
            "diplome_filiere": "Mathématiques et informatique",
            "diplome_specialite": "Informatique",
            "diplome_etablissement": "Université Fictive de Sable-Rouge",
            "moyenne_semestre_3": "12.85",
            "credits_semestre_3": "30",
        },
        absents=("credits_acquis",),
    ),
    DocumentSynthetique(
        nom="releve_master_annuel",
        type_piece="releves_notes_superieur",
        texte=_page(
            *_ENTETE_REPUBLIQUE,
            "Établissement : Université Fictive de Sable-Rouge",
            "RELEVÉ DE NOTES — MASTER 2",
            "Nom : FICTIVE",
            "Prénom : Lamia",
            "Diplôme : Master",
            "Filière : Informatique",
            "Spécialité : Systèmes d'information",
            "Année universitaire : 2023/2024",
            "Session : Juin 2024",
            "Semestre 3 | Big Data | 4 | 14,00",
            "Semestre 3 | Génie logiciel | 3 | 14,50",
            "Semestre 4 | Sécurité des systèmes | 4 | 13,50",
            "Semestre 4 | Projet de fin d'études | 6 | 14,00",
            "Moyenne du semestre 3 : 14,20",
            "Crédits acquis semestre 3 : 30",
            "Moy. S4 : 13,94",
            "Crédits acquis semestre 4 : 30",
            "Moyenne annuelle : 14,07",
            "Mention : Bien",
            "Rang : 5/42",
        ),
        attendu={
            "nom": "FICTIVE",
            "prenom": "Lamia",
            "diplome_intitule": "Master",
            "diplome_filiere": "Informatique",
            "diplome_specialite": "Systèmes d'information",
            "diplome_etablissement": "Université Fictive de Sable-Rouge",
            "annee_universitaire": "2023/2024",
            "session": "Juin 2024",
            "moyenne_semestre_3": "14.2",
            "moyenne_semestre_4": "13.94",
            "moyenne_annuelle": "14.07",
            "credits_semestre_3": "30",
            "credits_semestre_4": "30",
            "mention": "Bien",
            "rang": "5/42",
        },
        absents=("credits_acquis", "diplome_annee"),
    ),
    DocumentSynthetique(
        nom="releve_bac",
        type_piece="releve_notes_bac",
        texte=_page(
            "RELEVÉ DE NOTES DU BACCALAURÉAT — SESSION 2019",
            "RÉPUBLIQUE ALGÉRIENNE DÉMOCRATIQUE ET POPULAIRE",
            "MINISTÈRE DE L'ÉDUCATION NATIONALE (FICTIF)",
            "Lycée Exemple",
            "Nom : TESTEUR",
            "Prénom : Yasmine",
            "N° d'inscription au baccalauréat : 19123456",
            "Série : Sciences expérimentales",
            "Matière | Coefficient | Note /20",
            "Mathématiques | 7 | 16,00",
            "Physique-Chimie | 6 | 14,00",
            "Sciences de la nature et de la vie | 5 | 15,00",
            "Français | 2 | 13,00",
            "Anglais | 2 | 14,00",
            "Philosophie | 2 | 11,75",
            "Moyenne générale : 14,52/20",
            "Mention : Assez bien",
        ),
        attendu={
            "nom": "TESTEUR",
            "prenom": "Yasmine",
            "session": "2019",
            "diplome_etablissement": "Lycée Exemple",
            "numero_bac": "19123456",
            "bac_serie": "Sciences expérimentales",
            "moyenne_generale": "14.52",
            "mention": "Assez bien",
        },
        absents=("diplome_filiere", "annee_universitaire"),
    ),
    DocumentSynthetique(
        nom="diplome_licence",
        type_piece="diplomes_et_releves",
        texte=_page(
            *_ENTETE_REPUBLIQUE,
            "DIPLÔME DE LICENCE",
            "Université Fictive de Sable-Rouge",
            "Domaine : Sciences et technologies",
            "Filière : Informatique",
            "Spécialité : Réseaux et systèmes",
            "Nom : EXEMPLAIRE",
            "Prénom : Sofiane",
            "Né(e) le 03/05/2000 à Oran",
            "Date d'obtention : 06/07/2023",
            "Mention : Bien",
        ),
        attendu={
            "nom": "EXEMPLAIRE",
            "prenom": "Sofiane",
            "date_naissance": "2000-05-03",
            "lieu_naissance": "Oran",
            "diplome_intitule": "Licence",
            "diplome_filiere": "Informatique",
            "diplome_specialite": "Réseaux et systèmes",
            "diplome_etablissement": "Université Fictive de Sable-Rouge",
            "diplome_annee": "2023",
            "mention": "Bien",
        },
        absents=("annee_universitaire", "moyenne_generale"),
    ),
    DocumentSynthetique(
        nom="diplome_master",
        type_piece="diplomes_et_releves",
        texte=_page(
            *_ENTETE_REPUBLIQUE,
            "DIPLÔME DE MASTER",
            "Université Fictive de Sable-Rouge",
            "Filière : Mathématiques appliquées",
            "Spécialité : Modélisation et calcul scientifique",
            "Nom : PROTOTYPE",
            "Prénom : Nadia",
            "Né(e) le 21/11/1999 à Constantine",
            "Date d'obtention : 15/07/2025",
            "Moyenne générale : 15,12",
            "Mention : Très bien",
        ),
        attendu={
            "nom": "PROTOTYPE",
            "prenom": "Nadia",
            "date_naissance": "1999-11-21",
            "lieu_naissance": "Constantine",
            "diplome_intitule": "Master",
            "diplome_filiere": "Mathématiques appliquées",
            "diplome_specialite": "Modélisation et calcul scientifique",
            "diplome_etablissement": "Université Fictive de Sable-Rouge",
            "diplome_annee": "2025",
            "moyenne_generale": "15.12",
            "mention": "Très bien",
        },
        absents=("rang", "annee_universitaire"),
    ),
    DocumentSynthetique(
        nom="diplome_deua",
        type_piece="diplomes_et_releves",
        texte=_page(
            *_ENTETE_REPUBLIQUE,
            "DIPLÔME D'ÉTUDES UNIVERSITAIRES APPLIQUÉES (DEUA)",
            "Diplôme : DEUA",
            "Centre Universitaire Exemple",
            "Filière : Gestion",
            "Spécialité : Comptabilité et finance",
            "Nom : SPECIMEN",
            "Prénom : Rachid",
            "Né(e) le 30/09/2001 à Annaba",
            "Année d'obtention : 2022",
            "Mention : Passable",
        ),
        attendu={
            "nom": "SPECIMEN",
            "prenom": "Rachid",
            "date_naissance": "2001-09-30",
            "lieu_naissance": "Annaba",
            "diplome_intitule": "DEUA",
            "diplome_filiere": "Gestion",
            "diplome_specialite": "Comptabilité et finance",
            "diplome_etablissement": "Centre Universitaire Exemple",
            "diplome_annee": "2022",
            "mention": "Passable",
        },
        absents=("session", "moyenne_generale"),
    ),
    DocumentSynthetique(
        nom="diplome_bac",
        type_piece="diplome_bac",
        texte=_page(
            *_ENTETE_REPUBLIQUE,
            "DIPLÔME DU BACCALAURÉAT DE L'ENSEIGNEMENT SECONDAIRE",
            "Session : Juin 2018",
            "Série : Mathématiques",
            "N° Bac : 18765432",
            "Nom : MODELE",
            "Prénom : Amine",
            "Né(e) le 14/02/2000 à Sétif",
            "Mention : Très bien",
        ),
        attendu={
            "nom": "MODELE",
            "prenom": "Amine",
            "date_naissance": "2000-02-14",
            "lieu_naissance": "Sétif",
            "diplome_intitule": "Baccalauréat",
            "session": "Juin 2018",
            "bac_serie": "Mathématiques",
            "numero_bac": "18765432",
            "mention": "Très bien",
        },
        absents=("diplome_annee", "diplome_filiere", "annee_universitaire"),
    ),
    DocumentSynthetique(
        nom="releve_arabe_mixte",
        type_piece="releves_notes_superieur",
        texte=_page(
            "الجمهورية الجزائرية الديمقراطية الشعبية",
            "وزارة التعليم العالي والبحث العلمي",
            *_ENTETE_REPUBLIQUE,
            "Établissement : Jamiat Fictiya de Sable-Rouge",
            "Faculté : Kulliyat al-Iqtisad wa al-Tijara (fictive)",
            "RELEVÉ DE NOTES — LICENCE — SEMESTRE 1",
            "Nom : FICTIVA",
            "Prénom : Samira",
            "Spécialité : Gestion",
            "Année universitaire : 2021/2022",
            "Unité | Module | Coef | Crédits | Moyenne |",
            "UE1 | Comptabilité générale | 4 | 6 | 10,50 |",
            "UE1 | Mathématiques financières | 3 | 5 | 12,25 |",
            "UE2 | Droit des affaires | 2 | 4 | 11,50 |",
            "Moyenne générale : 11,25/20",
            "Mention : Passable",
        ),
        attendu={
            "nom": "FICTIVA",
            "prenom": "Samira",
            "diplome_specialite": "Gestion",
            "annee_universitaire": "2021/2022",
            "diplome_etablissement": "Jamiat Fictiya de Sable-Rouge",
            "moyenne_generale": "11.25",
            "mention": "Passable",
        },
        absents=("credits_acquis", "diplome_annee"),
    ),
    DocumentSynthetique(
        nom="releve_sans_information",
        type_piece="releves_notes_superieur",
        texte=_page(
            *_ENTETE_REPUBLIQUE,
            "RELEVÉ DE NOTES — LICENCE — SEMESTRE 2",
            "Nom : ANONYME",
            "Prénom : Walid",
            "Unité | Module | Coef | Crédits | Moyenne |",
            "UE1 | Analyse numérique | 4 | 6 | 9,00 |",
            "UE1 | Probabilités | 3 | 5 | 8,50 |",
            "UE2 | Langage C | 3 | 5 | 10,00 |",
            "Mention : néant",
        ),
        attendu={"nom": "ANONYME", "prenom": "Walid"},
        absents=("moyenne_generale", "mention", "rang", "date_naissance"),
    ),
    DocumentSynthetique(
        nom="releve_pieges",
        type_piece="releves_notes_superieur",
        texte=_page(
            *_ENTETE_REPUBLIQUE,
            "RELEVÉ DE NOTES — LICENCE",
            "Nom : PIEGE",
            "Prénom : Hakim",
            "Année universitaire : 2022/2025",
            "Date d'obtention : 31/02/2023",
            "Rang : 0",
            "Moyenne générale : 14/10",
        ),
        attendu={"nom": "PIEGE", "prenom": "Hakim"},
        absents=("moyenne_generale", "rang", "annee_universitaire", "diplome_annee"),
    ),
)


def par_nom(nom: str) -> DocumentSynthetique:
    for doc in DOCUMENTS:
        if doc.nom == nom:
            return doc
    raise KeyError(f"document synthétique inconnu : {nom!r}")


def bruiter_ocr(texte: str, *, graine: int, intensite: float = 0.03) -> str:
    """Substitutions de caractères déterministes (graine), sans ajout ni suppression de lignes."""
    generateur = random.Random(graine)
    sortie: list[str] = []
    for car in texte:
        eligible = car in _SUBSTITUTIONS_OCR or car == "1"
        if eligible and generateur.random() < intensite:
            car = generateur.choice(_CONFUSIONS_CHIFFRE_UN) if car == "1" else _SUBSTITUTIONS_OCR[car]
        sortie.append(car)
    return "".join(sortie)


def _retirer_accents(texte: str) -> str:
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(car for car in decompose if unicodedata.category(car) != "Mn")


def variantes_bruitees(doc: DocumentSynthetique) -> dict[str, str]:
    texte = doc.texte
    return {
        "accents_perdus": _retirer_accents(texte),
        "virgule_point": re.sub(r"(?<=\d),(?=\d)", ".", texte),
        "ocr_leger": bruiter_ocr(texte, graine=1, intensite=0.02),
        "ocr_fort": bruiter_ocr(texte, graine=2, intensite=0.10),
        "espaces_parasites": texte.replace(" : ", "  :  "),
    }


def verifier_corpus() -> None:
    """Contrôle d'auto-cohérence du corpus ; lève AssertionError en cas d'incohérence."""
    noms = [doc.nom for doc in DOCUMENTS]
    doublons = sorted({nom for nom in noms if noms.count(nom) > 1})
    if doublons:
        raise AssertionError(f"noms de documents en double : {doublons}")
    for doc in DOCUMENTS:
        if doc.type_piece not in TYPES_PIECE:
            raise AssertionError(f"{doc.nom} : type_piece inconnu {doc.type_piece!r}")
        conflits = sorted(set(doc.attendu) & set(doc.absents))
        if conflits:
            raise AssertionError(f"{doc.nom} : champs à la fois attendus et absents {conflits}")
        for champ, valeur in doc.attendu.items():
            if champ.startswith("moyenne") and not 0 <= float(valeur) <= BORNE_MOYENNE:
                raise AssertionError(f"{doc.nom} : {champ}={valeur} hors de [0, {BORNE_MOYENNE}]")
