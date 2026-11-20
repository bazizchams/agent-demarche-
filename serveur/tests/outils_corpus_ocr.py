"""Corpus OCR SYNTHÉTIQUE pour mesurer la lecture des documents (outil de test, aucune donnée réelle).

Pour chaque famille (passeport, relevé de notes, certificat de langue), 4 documents fictifs sont
rendus en pages A4 (1240x1754) puis soumis à 5 dégradations : 20 cas par famille, 60 au total.

- Graine fixe (random.Random(42)) : deux appels produisent exactement les mêmes octets.
- Les `attendu` ne contiennent que ce que le texte porte réellement et que le parseur de la
  famille sait lire. Un certificat ne porte pas d'identité exploitée par le parseur : nom, prénom
  et date de naissance y figurent comme texte mais ne sont pas attendus.
- Les chiffres de contrôle OACI 9303 de la MRZ sont calculés ici, indépendamment du parseur.
"""

from __future__ import annotations

import io
import random
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

LARGEUR_PAGE = 1240
HAUTEUR_PAGE = 1754
GRAINE = 42
DEGRADATIONS = ("propre", "bruit", "rotation", "flou", "pdf_scanne")
SIGMA_BRUIT = 10.0
ANGLE_ROTATION_DEG = 1.5
RAYON_FLOU = 0.8
RESOLUTION_PDF_DPI = 150.0
MARGE_GAUCHE = 90
Y_DEPART = 130

FAMILLE_PASSEPORT = "passeport"
FAMILLE_RELEVE = "releve_notes"
FAMILLE_CERTIFICAT = "certificat_langue"
FAMILLES = (FAMILLE_PASSEPORT, FAMILLE_RELEVE, FAMILLE_CERTIFICAT)
TYPE_PIECE_PAR_FAMILLE = {
    FAMILLE_PASSEPORT: "passeport",
    FAMILLE_RELEVE: "releves_notes_superieur",
    FAMILLE_CERTIFICAT: "resultats_test_langue",
}

POLICE_CORPS = r"C:\Windows\Fonts\arial.ttf"
POLICE_GRAS = r"C:\Windows\Fonts\arialbd.ttf"
POLICE_MRZ = r"C:\Windows\Fonts\cour.ttf"  # OCR-B absente : Courier New

_ALPHABET_OACI = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_POIDS_OACI = (7, 3, 1)
_PIED_DE_PAGE = "Document fictif de test - aucune donnée réelle"


@dataclass(frozen=True)
class CasCorpus:
    nom: str
    famille: str
    type_piece: str
    octets: bytes
    type_mime: str
    attendu: dict[str, str]
    degradation: str


@dataclass(frozen=True)
class _Ligne:
    texte: str
    taille: int = 30
    gras: bool = False
    mono: bool = False
    espace_avant: int = 0


# ----------------------------------------------------------------------------- données fictives
_PASSEPORTS = (
    {"nom": "BENALI", "prenoms": "SOFIANE", "sexe": "M", "naissance": "1979-04-12",
     "expiration": "2031-05-20", "numero": "198765432", "lieu": "ALGER"},
    {"nom": "KACI", "prenoms": "AMINA FATIMA", "sexe": "F", "naissance": "1992-11-03",
     "expiration": "2029-01-14", "numero": "DZ4418273", "lieu": "ORAN"},
    {"nom": "TOUMI", "prenoms": "YACINE", "sexe": "M", "naissance": "2001-07-29",
     "expiration": "2028-09-02", "numero": "C7291035Z", "lieu": "CONSTANTINE"},
    {"nom": "AISSAOUI", "prenoms": "LYNDA", "sexe": "F", "naissance": "1986-02-17",
     "expiration": "2032-03-08", "numero": "DA0873412", "lieu": "BATNA"},
)

_RELEVES = (
    {"diplome": "Licence", "intitule": "Licence en Informatique", "filiere": "Informatique",
     "etablissement": "Université Fictive de Sidi-Exemple", "annee": "2023/2024", "session": "Juin 2024",
     "s1": "12,50", "s2": "13,10", "annuelle": "13,42", "mention": "Assez bien", "decision": "Admis",
     "nom": "KACI", "prenom": "Amina", "naissance": "2002-03-14", "lieu": "Oran"},
    {"diplome": "Licence", "intitule": "Licence en Mathématiques", "filiere": "Mathématiques",
     "etablissement": "Université Fictive de Test-Ville", "annee": "2022/2023", "session": "Juillet 2023",
     "s1": "14,25", "s2": "11,80", "annuelle": "12,90", "mention": "Bien", "decision": "Admis",
     "nom": "TOUMI", "prenom": "Yacine", "naissance": "2001-07-29", "lieu": "Constantine"},
    {"diplome": "Master", "intitule": "Master en Gestion", "filiere": "Gestion",
     "etablissement": "Université Fictive de Sidi-Exemple", "annee": "2024/2025", "session": "2025",
     "s1": "15,00", "s2": "16,40", "annuelle": "15,70", "mention": "Très bien", "decision": "Ajourné",
     "nom": "AISSAOUI", "prenom": "Lynda", "naissance": "1986-02-17", "lieu": "Batna"},
    {"diplome": "Licence", "intitule": "Licence en Physique", "filiere": "Physique",
     "etablissement": "Université Fictive de Test-Ville", "annee": "2021/2022", "session": "Juin 2022",
     "s1": "11,00", "s2": "10,50", "annuelle": "10,75", "mention": "Passable", "decision": "Admis",
     "nom": "HAMDI", "prenom": "Nadir", "naissance": "1999-10-05", "lieu": "Tlemcen"},
)

_CERTIFICATS = (
    {"nom": "MEZIANE", "prenom": "SAMIA", "naissance": "04/08/1998", "niveau": "B2", "passation": "12/03/2025"},
    {"nom": "BOUKHALFA", "prenom": "RAYAN", "naissance": "17/05/2001", "niveau": "C1", "passation": "02/11/2024"},
    {"nom": "LARBI", "prenom": "KARIMA", "naissance": "23/12/1990", "niveau": "A2", "passation": "27/06/2023"},
    {"nom": "OUALI", "prenom": "ILYAS", "naissance": "09/09/2003", "niveau": "B1", "passation": "09/01/2026"},
)


# ----------------------------------------------------------------------------- utilitaires de forme
def _iso_depuis_fr(jour_mois_annee: str) -> str:
    jj, mm, aaaa = jour_mois_annee.split("/")
    return f"{aaaa}-{mm}-{jj}"


def _fr_depuis_iso(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}"


def _aammjj(iso: str) -> str:
    return iso[2:4] + iso[5:7] + iso[8:10]


def _decimal_canonique(nombre_fr: str) -> str:
    return format(Decimal(nombre_fr.replace(",", ".")).normalize(), "f")


# ----------------------------------------------------------------------------- MRZ OACI (TD3)
def chiffre_oaci(champ: str) -> str:
    """Chiffre de contrôle OACI 9303 : pondérations 7-3-1 répétées, « < » vaut 0, modulo 10."""
    total = 0
    for i, car in enumerate(champ):
        valeur = 0 if car == "<" else _ALPHABET_OACI.index(car)
        total += valeur * _POIDS_OACI[i % 3]
    return str(total % 10)


def construire_mrz(
    *, nom: str, prenoms: str, numero: str, naissance_iso: str, sexe: str, expiration_iso: str, pays: str = "DZA"
) -> tuple[str, str]:
    """Deux lignes MRZ TD3 de 44 caractères, chiffres de contrôle corrects."""
    ligne1 = f"P<{pays}" + "<".join(nom.split()) + "<<" + "<".join(prenoms.split())
    ligne1 = ligne1.ljust(44, "<")
    if len(ligne1) != 44:
        raise ValueError("nom et prénoms trop longs pour la ligne MRZ")
    naissance = _aammjj(naissance_iso)
    expiration = _aammjj(expiration_iso)
    facultatif = "<" * 14
    c_numero = chiffre_oaci(numero)
    c_naissance = chiffre_oaci(naissance)
    c_expiration = chiffre_oaci(expiration)
    c_facultatif = "<"
    composite = chiffre_oaci(numero + c_numero + naissance + c_naissance + expiration + c_expiration
                             + facultatif + c_facultatif)
    ligne2 = (numero + c_numero + pays + naissance + c_naissance + sexe + expiration + c_expiration
              + facultatif + c_facultatif + composite)
    assert len(ligne2) == 44, len(ligne2)
    return ligne1, ligne2


# ----------------------------------------------------------------------------- rendu des pages
@lru_cache(maxsize=None)
def _police(chemin: str, taille: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(chemin, taille)


def _rendre_page(lignes: list[_Ligne]) -> Image.Image:
    page = Image.new("L", (LARGEUR_PAGE, HAUTEUR_PAGE), 255)
    dessin = ImageDraw.Draw(page)
    y = Y_DEPART
    for ligne in lignes:
        y += ligne.espace_avant
        chemin = POLICE_MRZ if ligne.mono else (POLICE_GRAS if ligne.gras else POLICE_CORPS)
        dessin.text((MARGE_GAUCHE, y), ligne.texte, font=_police(chemin, ligne.taille), fill=0)
        y += int(ligne.taille * 1.6)
    return page


def _page_passeport(d: dict[str, str]) -> tuple[Image.Image, dict[str, str]]:
    mrz1, mrz2 = construire_mrz(
        nom=d["nom"], prenoms=d["prenoms"], numero=d["numero"],
        naissance_iso=d["naissance"], sexe=d["sexe"], expiration_iso=d["expiration"],
    )
    lignes = [
        _Ligne("RÉPUBLIQUE ALGÉRIENNE DÉMOCRATIQUE ET POPULAIRE", 28, gras=True),
        _Ligne("PASSEPORT / PASSPORT", 38, gras=True, espace_avant=20),
        _Ligne("Type / Type : P", 28, espace_avant=30),
        _Ligne("Code du pays / Country code : DZA"),
        _Ligne(f"Nom / Surname : {d['nom']}", espace_avant=30),
        _Ligne(f"Prénoms / Given names : {d['prenoms']}"),
        _Ligne("Nationalité / Nationality : ALGERIENNE"),
        _Ligne(f"Date de naissance / Date of birth : {_fr_depuis_iso(d['naissance'])}"),
        _Ligne(f"Lieu de naissance / Place of birth : {d['lieu']}"),
        _Ligne(f"Sexe / Sex : {d['sexe']}"),
        _Ligne(f"N° passeport / Passport No. : {d['numero']}"),
        _Ligne(f"Date d'expiration / Date of expiry : {_fr_depuis_iso(d['expiration'])}"),
        _Ligne(_PIED_DE_PAGE, 22, espace_avant=40),
        _Ligne(mrz1, 36, mono=True, espace_avant=260),
        _Ligne(mrz2, 36, mono=True),
    ]
    attendu = {
        "nom": d["nom"],
        "prenom": d["prenoms"],
        "date_naissance": d["naissance"],
        "sexe": d["sexe"],
        "nationalite_code": "DZA",
        "numero_passeport": d["numero"],
        "date_expiration_passeport": d["expiration"],
    }
    return _rendre_page(lignes), attendu


def _page_releve(d: dict[str, str]) -> tuple[Image.Image, dict[str, str]]:
    lignes = [
        _Ligne("RÉPUBLIQUE ALGÉRIENNE DÉMOCRATIQUE ET POPULAIRE", 28, gras=True),
        _Ligne("Ministère de l'Enseignement Supérieur et de la Recherche Scientifique", 24),
        _Ligne("RELEVÉ DE NOTES ET DIPLÔME", 36, gras=True, espace_avant=40),
        _Ligne(f"Intitulé du diplôme : {d['intitule']}", espace_avant=30),
        _Ligne(f"Filière : {d['filiere']}"),
        _Ligne(f"Établissement : {d['etablissement']}"),
        _Ligne(f"Année universitaire : {d['annee']}"),
        _Ligne(f"Session : {d['session']}"),
        _Ligne(f"Nom : {d['nom']}", espace_avant=30),
        _Ligne(f"Prénom : {d['prenom']}"),
        _Ligne(f"Né(e) le : {_fr_depuis_iso(d['naissance'])} à {d['lieu']}"),
        _Ligne(f"Moyenne du semestre 1 : {d['s1']}/20", espace_avant=30),
        _Ligne(f"Moyenne du semestre 2 : {d['s2']}/20"),
        _Ligne(f"Moyenne annuelle : {d['annuelle']}/20"),
        _Ligne(f"Mention : {d['mention']}"),
        _Ligne(f"Décision du jury : {d['decision']}"),
        _Ligne(_PIED_DE_PAGE, 22, espace_avant=120),
    ]
    attendu = {
        "diplome_intitule": d["diplome"],
        "diplome_filiere": d["filiere"],
        "diplome_etablissement": d["etablissement"],
        "annee_universitaire": d["annee"],
        "session": d["session"],
        "moyenne_semestre_1": _decimal_canonique(d["s1"]),
        "moyenne_semestre_2": _decimal_canonique(d["s2"]),
        "moyenne_annuelle": _decimal_canonique(d["annuelle"]),
        "mention": d["mention"],
        "decision_jury": d["decision"],
        "nom": d["nom"],
        "prenom": d["prenom"],
        "date_naissance": d["naissance"],
        "lieu_naissance": d["lieu"],
    }
    return _rendre_page(lignes), attendu


def _page_certificat(d: dict[str, str]) -> tuple[Image.Image, dict[str, str]]:
    lignes = [
        _Ligne("ATTESTATION DE RÉSULTATS", 34, gras=True),
        _Ligne("Test de connaissance du français (TCF)", 30),
        _Ligne(f"Nom : {d['nom']}", espace_avant=40),
        _Ligne(f"Prénom : {d['prenom']}"),
        _Ligne(f"Date de naissance : {d['naissance']}"),
        _Ligne(f"Niveau global obtenu : {d['niveau']}", espace_avant=30),
        _Ligne(f"Date de passation : {d['passation']}"),
        _Ligne(_PIED_DE_PAGE, 22, espace_avant=120),
    ]
    attendu = {
        "certificat_langue_type": "TCF",
        "niveau_francais": d["niveau"],
        "certificat_langue_date": _iso_depuis_fr(d["passation"]),
    }
    return _rendre_page(lignes), attendu


# ----------------------------------------------------------------------------- dégradations
def _ajouter_bruit(page: Image.Image, rng: random.Random) -> Image.Image:
    """Bruit gaussien léger : N(0, SIGMA_BRUIT) ajouté au niveau de gris, graine fixe."""
    nombre = page.size[0] * page.size[1]
    valeurs = bytes(min(255, max(0, round(rng.gauss(128, SIGMA_BRUIT)))) for _ in range(nombre))
    bruit = Image.frombytes("L", page.size, valeurs)
    return ImageChops.add(page, bruit, scale=1.0, offset=-128)


def _en_png(page: Image.Image) -> bytes:
    tampon = io.BytesIO()
    page.save(tampon, format="PNG")
    return tampon.getvalue()


def _en_pdf(page: Image.Image) -> bytes:
    """Page propre intégrée dans un PDF sans couche texte (image seule)."""
    tampon = io.BytesIO()
    page.convert("RGB").save(tampon, format="PDF", resolution=RESOLUTION_PDF_DPI)
    return tampon.getvalue()


def _cas_degrades(
    page: Image.Image, rng: random.Random
) -> list[tuple[str, bytes, str]]:
    """(dégradation, octets, type MIME) pour les 5 dégradations, dans un ordre fixe."""
    sorties: list[tuple[str, bytes, str]] = []
    for degradation in DEGRADATIONS:
        if degradation == "propre":
            sorties.append((degradation, _en_png(page), "image/png"))
        elif degradation == "bruit":
            sorties.append((degradation, _en_png(_ajouter_bruit(page, rng)), "image/png"))
        elif degradation == "rotation":
            angle = rng.choice((ANGLE_ROTATION_DEG, -ANGLE_ROTATION_DEG))
            tourne = page.rotate(angle, resample=Image.BICUBIC, fillcolor=255)
            sorties.append((degradation, _en_png(tourne), "image/png"))
        elif degradation == "flou":
            floue = page.filter(ImageFilter.GaussianBlur(RAYON_FLOU))
            sorties.append((degradation, _en_png(floue), "image/png"))
        elif degradation == "pdf_scanne":
            sorties.append((degradation, _en_pdf(page), "application/pdf"))
    return sorties


# ----------------------------------------------------------------------------- point d'entrée
_BUILDERS = {
    FAMILLE_PASSEPORT: (_page_passeport, _PASSEPORTS),
    FAMILLE_RELEVE: (_page_releve, _RELEVES),
    FAMILLE_CERTIFICAT: (_page_certificat, _CERTIFICATS),
}


def fabriquer_corpus() -> list[CasCorpus]:
    """60 cas : 4 documents fictifs par famille x 5 dégradations. Déterministe (graine 42)."""
    rng = random.Random(GRAINE)
    cas: list[CasCorpus] = []
    for famille in FAMILLES:
        construire, documents = _BUILDERS[famille]
        for index, document in enumerate(documents, start=1):
            page, attendu = construire(document)
            for degradation, octets, type_mime in _cas_degrades(page, rng):
                cas.append(
                    CasCorpus(
                        nom=f"{famille}_{index:02d}_{degradation}",
                        famille=famille,
                        type_piece=TYPE_PIECE_PAR_FAMILLE[famille],
                        octets=octets,
                        type_mime=type_mime,
                        attendu=dict(attendu),
                        degradation=degradation,
                    )
                )
    return cas
