"""Parseurs déterministes du lecteur A : MRZ de passeport (OACI 9303), dates, moyennes,
certificats de langue (TCF, DELF, DALF, IELTS).

Principes (règle 4) :
- un texte sans information ne produit AUCUNE valeur ; jamais de date ni de niveau « par défaut » ;
- une valeur douteuse n'est ni corrigée ni devinée : elle est marquée `valide=False` avec un
  `motif` (code technique) pour que la fusion la renvoie à la vérification humaine ;
- chaque valeur garde son extrait littéral (la ligne du document) et sa page.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation

# --- Noms des champs lus -------------------------------------------------------------------------
NOM = "nom"
PRENOM = "prenom"
DATE_NAISSANCE = "date_naissance"
SEXE = "sexe"
NATIONALITE_CODE = "nationalite_code"
NUMERO_PASSEPORT = "numero_passeport"
DATE_EXPIRATION_PASSEPORT = "date_expiration_passeport"
MOYENNE_GENERALE = "moyenne_generale"
CERTIFICAT_TYPE = "certificat_langue_type"
CERTIFICAT_DATE = "certificat_langue_date"
NIVEAU_FRANCAIS = "niveau_francais"
NIVEAU_ANGLAIS = "niveau_anglais"
IELTS_BANDE = "ielts_bande"

CHAMPS_CONNUS = frozenset(
    {
        NOM, PRENOM, DATE_NAISSANCE, SEXE, NATIONALITE_CODE, NUMERO_PASSEPORT,
        DATE_EXPIRATION_PASSEPORT, MOYENNE_GENERALE, CERTIFICAT_TYPE, CERTIFICAT_DATE,
        NIVEAU_FRANCAIS, NIVEAU_ANGLAIS, IELTS_BANDE,
    }
)
CHAMPS_DATES = frozenset({DATE_NAISSANCE, DATE_EXPIRATION_PASSEPORT, CERTIFICAT_DATE})
NIVEAUX_CECRL = ("A1", "A2", "B1", "B2", "C1", "C2")
TYPES_CERTIFICAT = ("TCF", "DELF", "DALF", "IELTS")
NIVEAUX_PAR_DIPLOME = {
    "DELF": ("A1", "A2", "B1", "B2"),
    "DALF": ("C1", "C2"),
    "TCF": NIVEAUX_CECRL,
}

FAMILLE_PASSEPORT = "passeport"
FAMILLE_RELEVE = "releve_notes"
FAMILLE_CERTIFICAT = "certificat_langue"
_FAMILLE_PAR_TYPE_PIECE = {
    "passeport": FAMILLE_PASSEPORT,
    "releve_notes_bac": FAMILLE_RELEVE,
    "releves_notes_superieur": FAMILLE_RELEVE,
    "diplome_bac": FAMILLE_RELEVE,
    "diplomes_et_releves": FAMILLE_RELEVE,
    "resultats_test_langue": FAMILLE_CERTIFICAT,
    "attestation_langue_francaise": FAMILLE_CERTIFICAT,
}


@dataclass(frozen=True)
class ChampLu:
    """Valeur lue par un lecteur, avec sa preuve (extrait littéral et page)."""

    champ: str
    valeur: str
    extrait: str
    page: int
    confiance: float
    valide: bool = True
    motif: str | None = None
    controle_fort: bool = False  # vérifiée par une somme de contrôle indépendante (OACI)
    ancre: str | None = None  # fragment littéral dont la valeur est dérivée (doit être dans l'extrait)


def famille_pour_type_piece(type_piece: str) -> str | None:
    return _FAMILLE_PAR_TYPE_PIECE.get(type_piece)


def _sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c))


# ================================================================== dates
_MOIS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
    "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
_RE_DATE_NUM = re.compile(r"(?<!\d)(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})(?!\d)")
_RE_DATE_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_RE_DATE_TEXTE = re.compile(
    r"(?<!\d)(\d{1,2})(?:er|re)?\s+(" + "|".join(_MOIS) + r")\s+(\d{4})(?!\d)", re.IGNORECASE
)


def _date_ou_none(annee: int, mois: int, jour: int) -> date | None:
    try:
        return date(annee, mois, jour)
    except ValueError:
        return None


def extraire_dates(texte: str) -> list[date]:
    """Toutes les dates valides du texte, dans l'ordre de lecture. Les années à deux chiffres
    sont refusées (ambiguës) ; une date impossible (31/02) est ignorée."""
    trouvees: list[tuple[int, date | None]] = []
    for m in _RE_DATE_ISO.finditer(texte):
        trouvees.append((m.start(), _date_ou_none(int(m.group(1)), int(m.group(2)), int(m.group(3)))))
    for m in _RE_DATE_NUM.finditer(texte):
        if _RE_DATE_ISO.match(texte, m.start()):
            continue
        trouvees.append((m.start(), _date_ou_none(int(m.group(3)), int(m.group(2)), int(m.group(1)))))
    sans_accent = _sans_accents(texte)
    for m in _RE_DATE_TEXTE.finditer(sans_accent):
        mois = _MOIS[m.group(2).lower()]
        trouvees.append((m.start(), _date_ou_none(int(m.group(3)), mois, int(m.group(1)))))
    return [d for _, d in sorted(trouvees, key=lambda t: t[0]) if d is not None]


def analyser_date(texte: str) -> date | None:
    dates = extraire_dates(texte)
    return dates[0] if dates else None


# ================================================================== valeurs : validation et forme canonique
def _decimal(valeur: str) -> Decimal | None:
    try:
        d = Decimal(valeur.strip().replace(",", "."))
    except InvalidOperation:
        return None
    return d if d.is_finite() else None


def _forme_decimale(d: Decimal) -> str:
    return format(d.normalize(), "f")


def normaliser_valeur(champ: str, valeur: str) -> str:
    """Forme canonique d'une valeur, utilisée pour comparer deux lectures et pour stocker."""
    brut = " ".join(valeur.split())
    if champ in CHAMPS_DATES:
        d = analyser_date(brut)
        return d.isoformat() if d else brut
    if champ in (MOYENNE_GENERALE, IELTS_BANDE):
        d = _decimal(brut)
        return _forme_decimale(d) if d is not None else brut
    if champ == NUMERO_PASSEPORT:
        return brut.replace(" ", "").upper()
    if champ in (SEXE, NATIONALITE_CODE, NIVEAU_FRANCAIS, NIVEAU_ANGLAIS, CERTIFICAT_TYPE):
        return brut.upper()
    return brut


def valeur_valide(champ: str, valeur: str) -> bool:
    """Vrai si la valeur (forme canonique) est acceptable pour ce champ."""
    if champ not in CHAMPS_CONNUS or not valeur or not valeur.strip():
        return False
    v = valeur.strip()
    if champ in CHAMPS_DATES:
        try:
            date.fromisoformat(v)
        except ValueError:
            return False
        return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", v))
    if champ == SEXE:
        return v in ("M", "F")
    if champ == MOYENNE_GENERALE:
        d = _decimal(v)
        return d is not None and Decimal(0) <= d <= Decimal(20)
    if champ == IELTS_BANDE:
        d = _decimal(v)
        return d is not None and Decimal(0) <= d <= Decimal(9) and (d * 2) % 1 == 0
    if champ in (NIVEAU_FRANCAIS, NIVEAU_ANGLAIS):
        return v.upper() in NIVEAUX_CECRL
    if champ == CERTIFICAT_TYPE:
        return v.upper() in TYPES_CERTIFICAT
    if champ == NATIONALITE_CODE:
        return bool(re.fullmatch(r"[A-Za-z]{3}", v))
    if champ == NUMERO_PASSEPORT:
        return bool(re.fullmatch(r"[A-Za-z0-9]{4,20}", v.replace(" ", "")))
    return len(v) <= 120  # nom, prénom


# ================================================================== MRZ (OACI 9303, TD3)
_POIDS_MRZ = (7, 3, 1)
_RE_MRZ_L2 = re.compile(r"^[A-Z0-9<]{9}\d[A-Z<]{3}\d{6}\d[MF<]\d{6}\d[A-Z0-9<]{14}[\d<]\d$")


def _valeur_mrz(c: str) -> int:
    if c == "<":
        return 0
    if c.isdigit():
        return int(c)
    return ord(c) - ord("A") + 10


def calculer_chiffre_controle(champ: str) -> str:
    """Chiffre de contrôle OACI 9303 : somme des valeurs pondérées 7-3-1, modulo 10."""
    return str(sum(_valeur_mrz(c) * _POIDS_MRZ[i % 3] for i, c in enumerate(champ)) % 10)


def _controle_ok(champ: str, attendu: str) -> bool:
    if calculer_chiffre_controle(champ) == attendu:
        return True
    # Champ facultatif entièrement vide : le chiffre de contrôle peut être « < ».
    return set(champ) == {"<"} and attendu == "<"


def _trouver_lignes_mrz(texte: str) -> tuple[str, str, str, str] | None:
    """(ligne 1 brute, ligne 2 brute, ligne 1 compacte, ligne 2 compacte) ou None."""
    lignes = [(brute.strip(), re.sub(r"\s+", "", brute).upper()) for brute in texte.splitlines()]
    lignes = [(b, c) for b, c in lignes if c]
    for i in range(len(lignes) - 1):
        b1, c1 = lignes[i]
        b2, c2 = lignes[i + 1]
        if len(c1) == 44 and c1.startswith("P<") and "<<" in c1 and len(c2) == 44 and _RE_MRZ_L2.match(c2):
            return b1, b2, c1, c2
    return None


def _date_mrz(aammjj: str, *, naissance: bool, pivot: int) -> date | None:
    yy = int(aammjj[0:2])
    annee = (2000 + yy if yy <= pivot else 1900 + yy) if naissance else 2000 + yy
    return _date_ou_none(annee, int(aammjj[2:4]), int(aammjj[4:6]))


def _noms_mrz(ligne1: str) -> tuple[str, str]:
    reste = ligne1[5:].rstrip("<")
    nom, _, prenoms = reste.partition("<<")
    return " ".join(nom.replace("<", " ").split()), " ".join(prenoms.replace("<", " ").split())


def analyser_mrz(texte: str, page: int = 1, *, annee_pivot: int | None = None) -> list[ChampLu]:
    """Lit la zone MRZ d'un passeport (2 lignes de 44 caractères) et vérifie les chiffres de
    contrôle. Les champs sont « forts » (`controle_fort`) seulement si TOUS les contrôles
    (numéro, naissance, expiration, champ facultatif, composite) sont corrects."""
    lignes = _trouver_lignes_mrz(texte)
    if lignes is None:
        return []
    brute1, brute2, l1, l2 = lignes
    pivot = (annee_pivot if annee_pivot is not None else date.today().year) % 100

    numero9, cle_numero = l2[0:9], l2[9]
    naissance, cle_naissance = l2[13:19], l2[19]
    sexe = l2[20]
    expiration, cle_expiration = l2[21:27], l2[27]
    perso, cle_perso = l2[28:42], l2[42]
    composite_ok = calculer_chiffre_controle(l2[0:10] + l2[13:20] + l2[21:43]) == l2[43]
    controles = {
        NUMERO_PASSEPORT: _controle_ok(numero9, cle_numero),
        DATE_NAISSANCE: _controle_ok(naissance, cle_naissance),
        DATE_EXPIRATION_PASSEPORT: _controle_ok(expiration, cle_expiration),
    }
    perso_ok = _controle_ok(perso, cle_perso)
    tout_ok = all(controles.values()) and perso_ok and composite_ok

    def champ(nom: str, valeur: str, extrait: str, ancre: str, propre_ok: bool | None) -> ChampLu:
        if propre_ok is False:
            return ChampLu(nom, valeur, extrait, page, 0.3, valide=False, motif="mrz_controle_invalide", ancre=ancre)
        if tout_ok and propre_ok is True:
            return ChampLu(nom, valeur, extrait, page, 1.0, controle_fort=True, ancre=ancre)
        base = 0.5 if propre_ok is True else (0.8 if tout_ok else 0.5)
        return ChampLu(nom, valeur, extrait, page, base, ancre=ancre)

    resultats: list[ChampLu] = []
    numero = numero9.replace("<", "")
    if numero:
        resultats.append(champ(NUMERO_PASSEPORT, numero, brute2, numero9, controles[NUMERO_PASSEPORT]))
    for nom_champ, aammjj, est_naissance in (
        (DATE_NAISSANCE, naissance, True),
        (DATE_EXPIRATION_PASSEPORT, expiration, False),
    ):
        d = _date_mrz(aammjj, naissance=est_naissance, pivot=pivot)
        if d is None:
            resultats.append(ChampLu(nom_champ, aammjj, brute2, page, 0.0, valide=False, motif="mrz_date_invalide", ancre=aammjj))
        else:
            resultats.append(champ(nom_champ, d.isoformat(), brute2, aammjj, controles[nom_champ]))
    if sexe in ("M", "F"):
        resultats.append(champ(SEXE, sexe, brute2, sexe, True if composite_ok else None))
    nationalite = l2[10:13].replace("<", "")
    if nationalite:
        resultats.append(champ(NATIONALITE_CODE, nationalite, brute2, l2[10:13], None))
    nom, prenoms = _noms_mrz(l1)
    for nom_champ, valeur in ((NOM, nom), (PRENOM, prenoms)):
        if not valeur:
            continue
        if not re.fullmatch(r"[A-Z ]+", valeur):
            resultats.append(
                ChampLu(nom_champ, valeur, brute1, page, 0.2, valide=False, motif="mrz_caracteres_invalides", ancre=valeur.split()[0])
            )
        else:
            resultats.append(champ(nom_champ, valeur, brute1, valeur.split()[0], None))
    return resultats


# ================================================================== moyennes
_RE_MOYENNE = re.compile(
    r"(?:moyenne|moy\.?)\s*(?:generale|annuelle|finale|(?:au|du)\s+bac\w*|bac\w*)"
    r"[\s:=\-]*(\d{1,3}(?:[.,]\d{1,2})?)(?:\s*/\s*(\d{1,3}))?",
    re.IGNORECASE,
)


def analyser_moyenne(texte: str, page: int = 1) -> list[ChampLu]:
    """Moyenne générale libellée comme telle, au barème /20 et dans [0, 20]."""
    trouvees: list[tuple[str, str, str | None, str]] = []
    for ligne in texte.splitlines():
        m = _RE_MOYENNE.search(_sans_accents(ligne))
        if m:
            trouvees.append((m.group(1).replace(",", "."), ligne.strip(), m.group(2), m.group(0)))
    if not trouvees:
        return []
    valeurs = {normaliser_valeur(MOYENNE_GENERALE, t[0]) for t in trouvees}
    nombre, extrait, base, ancre = trouvees[0]
    nombre = normaliser_valeur(MOYENNE_GENERALE, nombre)
    if len(valeurs) > 1:
        return [ChampLu(MOYENNE_GENERALE, nombre, extrait, page, 0.3, valide=False, motif="moyenne_ambigue")]
    if base is not None and base != "20":
        return [ChampLu(MOYENNE_GENERALE, nombre, extrait, page, 0.3, valide=False, motif="bareme_different")]
    if not valeur_valide(MOYENNE_GENERALE, nombre):
        return [ChampLu(MOYENNE_GENERALE, nombre, extrait, page, 0.3, valide=False, motif="moyenne_hors_bornes")]
    return [ChampLu(MOYENNE_GENERALE, nombre, extrait, page, 0.85)]


# ================================================================== certificats de langue
_RE_TYPE = {t: re.compile(rf"\b{t}\b", re.IGNORECASE) for t in TYPES_CERTIFICAT}
_RE_NIVEAU = re.compile(r"\b([ABC][12])\b", re.IGNORECASE)
_RE_BANDE = re.compile(r"overall\s+band\s+score\D{0,5}(\d(?:[.,]\d)?)", re.IGNORECASE)
_RE_CECRL = re.compile(r"cefr[^A-Za-z0-9\n]{0,15}(?:level)?[^A-Za-z0-9\n]{0,5}([ABC][12])\b", re.IGNORECASE)
_RE_MOT_DATE = re.compile(
    r"date\s+(?:de\s+passation|d.obtention|de\s+l.examen|du\s+test|de\s+session)"
    r"|test\s+date|date\s+of\s+(?:test|examination)|session",
    re.IGNORECASE,
)


def _niveaux_dans(ligne: str) -> list[str]:
    return [n.upper() for n in _RE_NIVEAU.findall(ligne)]


def _choisir_niveau(lignes: list[str], type_certificat: str) -> tuple[str, str, bool] | None:
    """(niveau, ligne source, ambigu) selon des règles de priorité explicites."""
    sans = [(ligne, _sans_accents(ligne).lower()) for ligne in lignes]
    etapes: list[Callable[[str, str], bool]] = [
        lambda _l, bas: "niveau" in bas and bool(re.search(r"global|obtenu|atteint|final", bas)),
        lambda _l, bas: "niveau" in bas,
        lambda _l, bas: type_certificat != "TCF" and type_certificat.lower() in bas,
    ]
    for critere in etapes:
        retenues = [(ligne, _niveaux_dans(ligne)) for ligne, bas in sans if critere(ligne, bas)]
        retenues = [(ligne, n) for ligne, n in retenues if n]
        if retenues:
            distincts = {x for _, n in retenues for x in n}
            ligne, niveaux = retenues[0]
            return niveaux[0], ligne.strip(), len(distincts) > 1
    tous = [(ligne, _niveaux_dans(ligne)) for ligne in lignes]
    tous = [(ligne, n) for ligne, n in tous if n]
    if not tous:
        return None
    distincts = {x for _, n in tous for x in n}
    ligne, niveaux = tous[0]
    return niveaux[0], ligne.strip(), len(distincts) > 1


def analyser_certificat_langue(texte: str, page: int = 1) -> list[ChampLu]:
    lignes = texte.splitlines()
    types_trouves = [t for t in TYPES_CERTIFICAT if _RE_TYPE[t].search(texte)]
    if not types_trouves:
        return []
    ligne_type = next(ligne.strip() for ligne in lignes if _RE_TYPE[types_trouves[0]].search(ligne))
    if len(types_trouves) > 1:
        return [ChampLu(CERTIFICAT_TYPE, types_trouves[0], ligne_type, page, 0.3, valide=False, motif="type_ambigu")]
    type_certificat = types_trouves[0]
    resultats = [ChampLu(CERTIFICAT_TYPE, type_certificat, ligne_type, page, 0.85)]

    if type_certificat == "IELTS":
        m = _RE_BANDE.search(texte)
        if m:
            ligne = next(ligne.strip() for ligne in lignes if m.group(0) in ligne)
            bande = normaliser_valeur(IELTS_BANDE, m.group(1))
            if valeur_valide(IELTS_BANDE, bande):
                resultats.append(ChampLu(IELTS_BANDE, bande, ligne, page, 0.85))
            else:
                resultats.append(ChampLu(IELTS_BANDE, bande, ligne, page, 0.3, valide=False, motif="bande_hors_bornes"))
        c = _RE_CECRL.search(texte)
        if c:  # niveau CECRL écrit tel quel sur le certificat ; jamais déduit de la bande
            ligne = next(ligne.strip() for ligne in lignes if c.group(0).split("\n")[0] in ligne)
            resultats.append(ChampLu(NIVEAU_ANGLAIS, c.group(1).upper(), ligne, page, 0.8))
    else:
        choix = _choisir_niveau(lignes, type_certificat)
        if choix is not None:
            niveau, ligne, ambigu = choix
            if ambigu:
                resultats.append(ChampLu(NIVEAU_FRANCAIS, niveau, ligne, page, 0.3, valide=False, motif="niveau_ambigu"))
            elif niveau not in NIVEAUX_PAR_DIPLOME[type_certificat]:
                resultats.append(
                    ChampLu(NIVEAU_FRANCAIS, niveau, ligne, page, 0.3, valide=False, motif="niveau_incoherent_avec_diplome")
                )
            else:
                resultats.append(ChampLu(NIVEAU_FRANCAIS, niveau, ligne, page, 0.85))

    for ligne in lignes:
        if _RE_MOT_DATE.search(_sans_accents(ligne)):
            d = analyser_date(ligne)
            if d is not None:
                resultats.append(ChampLu(CERTIFICAT_DATE, d.isoformat(), ligne.strip(), page, 0.8))
                break
    return resultats


# ================================================================== orchestration par famille
_PARSEURS: dict[str, Callable[[str, int], list[ChampLu]]] = {
    FAMILLE_PASSEPORT: lambda t, p: analyser_mrz(t, p),
    FAMILLE_RELEVE: analyser_moyenne,
    FAMILLE_CERTIFICAT: analyser_certificat_langue,
}


def extraire_champs(famille: str, pages: Sequence[tuple[int, str]]) -> list[ChampLu]:
    """Applique le parseur de la famille à chaque page ; une famille inconnue ne produit rien.
    Un champ retrouvé avec des valeurs différentes est marqué invalide (jamais choisi au hasard)."""
    parseur = _PARSEURS.get(famille)
    if parseur is None:
        return []
    gardes: dict[str, ChampLu] = {}
    for numero, texte in pages:
        for c in parseur(texte, numero):
            existant = gardes.get(c.champ)
            if existant is None:
                gardes[c.champ] = c
            elif normaliser_valeur(c.champ, c.valeur) != normaliser_valeur(c.champ, existant.valeur):
                gardes[c.champ] = replace(
                    existant, valide=False, motif="valeurs_multiples", confiance=min(existant.confiance, 0.3),
                    controle_fort=False,
                )
    return list(gardes.values())
