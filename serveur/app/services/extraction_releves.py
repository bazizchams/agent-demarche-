"""Parseur déterministe des relevés de notes et diplômes ALGÉRIENS (lecteur A, famille « relevé »).

Lit, ligne par ligne, ce qui est ÉCRIT : intitulé du diplôme, filière, spécialité, établissement,
année universitaire, moyennes (générale, annuelle, par semestre), crédits par semestre, mention,
rang, décision du jury, session, année d'obtention, nom, prénom, date et lieu de naissance, numéro
et série du baccalauréat.

Principes (règle 4, jamais de valeur inventée ni de déduction silencieuse) :
- chaque valeur garde sa ligne littérale (`extrait`), son fragment ancré (`ancre`) et sa page ;
- une mention n'est jamais déduite d'une moyenne, une année d'obtention jamais déduite de l'année
  universitaire, un niveau jamais calculé ;
- OCR : un jeton numérique abîmé (O/0, l/1, I/1) n'est JAMAIS validé : la valeur « réparée » est
  seulement proposée (`valide=False`, motif `ocr_a_confirmer`) avec le fragment littéral lu ;
- un texte libre mêlant lettres et chiffres dans un même mot (« Sab1e ») est `ocr_suspect` ;
- deux valeurs différentes pour le même champ : `valeurs_multiples`, jamais un choix au hasard ;
- les lignes de tableau de modules (coefficients, crédits par module) ne produisent rien.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import replace
from datetime import date
from decimal import Decimal, InvalidOperation

from app.services.extraction_champs import (
    ANNEE_UNIVERSITAIRE,
    BAC_SERIE,
    DATE_NAISSANCE,
    DECISION_JURY,
    DIPLOME_ANNEE,
    DIPLOME_ETABLISSEMENT,
    DIPLOME_FILIERE,
    DIPLOME_INTITULE,
    DIPLOME_SPECIALITE,
    LIEU_NAISSANCE,
    MENTION,
    MENTIONS,
    MOYENNE_ANNUELLE,
    MOYENNE_GENERALE,
    NOM,
    NUMERO_BAC,
    PREFIXE_CREDITS_SEMESTRE,
    PREFIXE_MOYENNE_SEMESTRE,
    PRENOM,
    RANG,
    SEMESTRES_MAX,
    SESSION,
    ChampLu,
    analyser_moyenne,
    extraire_dates,
    normaliser_valeur,
    valeur_valide,
)

CONFIANCE_LECTURE = 0.85
CONFIANCE_TEXTE = 0.8
CONFIANCE_DOUTEUSE = 0.3
CONFIANCE_OCR = 0.4
AGE_MINIMUM_NAISSANCE = 14
ANNEE_NAISSANCE_MINIMUM = 1940
LONGUEUR_MAX_VALEUR = 120

_TEXTES_A_CONTROLER = frozenset(
    {NOM, PRENOM, LIEU_NAISSANCE, DIPLOME_FILIERE, DIPLOME_SPECIALITE, DIPLOME_ETABLISSEMENT, BAC_SERIE}
)
_RE_NOM_PROPRE = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ '’\-]*")


# ================================================================== texte aligné (sans accents, même longueur)
def _base(car: str) -> str:
    decompose = unicodedata.normalize("NFKD", car)
    premier = decompose[0] if decompose else car
    bas = premier.lower()
    return "'" if premier == "’" else (bas if len(bas) == 1 else premier)


def _sa(texte: str) -> str:
    """Minuscules sans accents, MÊME longueur que `texte` (les positions sont réutilisables)."""
    return "".join(_base(c) for c in texte)


_RE_COUPE = re.compile(r"\s{2,}|\s*[|;]\s*|\s+[A-Za-zÀ-ÿ'’./° ]{2,25}:(?:\s|$)")


def _valeur_apres(texte: str, debut: int) -> tuple[str, int] | None:
    """Valeur libre commençant à `debut` : coupée au prochain séparateur ou libellé ; (valeur, position)."""
    reste = texte[debut:]
    coupe = _RE_COUPE.search(reste)
    brut = reste[: coupe.start()] if coupe else reste
    nu = brut.strip(" \t.,;:-_")
    if not nu:
        return None
    return nu, debut + brut.index(nu)


def _mot_suspect(valeur: str) -> bool:
    """Vrai si un mot mêle lettres et chiffres (« Sab1e », « 0ran »)."""
    for jeton in re.split(r"[\s\-'’/.,()]+", valeur):
        if re.search(r"\d", jeton) and re.search(r"[A-Za-zÀ-ÿ]", jeton):
            return True
    return False


# ================================================================== fabrique de ChampLu
def _champ(
    champ: str, valeur: str, ligne: str, page: int, ancre: str, *, motif: str | None = None, confiance: float | None = None
) -> ChampLu:
    """ChampLu contrôlé : valeur canonique, validité vérifiée, jamais de valeur douteuse validée."""
    canon = normaliser_valeur(champ, valeur)
    extrait = ligne.strip()
    if motif is None and champ in _TEXTES_A_CONTROLER and _mot_suspect(canon):
        motif = "ocr_suspect"
    if motif is None and champ in (NOM, PRENOM) and not _RE_NOM_PROPRE.fullmatch(canon):
        motif = "caracteres_invalides"
    if motif is None and (len(canon) > LONGUEUR_MAX_VALEUR or not valeur_valide(champ, canon)):
        motif = "valeur_invalide"
    if motif is not None:
        return ChampLu(champ, canon, extrait, page, CONFIANCE_DOUTEUSE, valide=False, motif=motif, ancre=ancre)
    taux = CONFIANCE_TEXTE if champ in _TEXTES_A_CONTROLER else CONFIANCE_LECTURE
    return ChampLu(champ, canon, extrait, page, confiance if confiance is not None else taux, ancre=ancre)


_NUM = r"(\d{1,3}(?:[.,]\d{1,3})?)(?![.,]?[0-9a-z])"
# Barème facultatif : s'il est écrit (« /20 »), il doit être lisible en entier (jamais « /2O » ignoré).
_BASE = r"(?:\s*/\s*(\d{1,3})(?![0-9a-z])|(?!\s*/))"
_EFFECTIF = r"(?:\s*(?:/|sur)\s*(\d{1,%d})(?![0-9a-z])|(?!\s*(?:/|sur)))"


def _decimal(valeur: str) -> Decimal | None:
    try:
        d = Decimal(valeur.replace(",", "."))
    except InvalidOperation:
        return None
    return d if d.is_finite() else None


def _moyenne(champ: str, nombre: str, base: str | None, ligne: str, page: int, ancre: str) -> ChampLu:
    d = _decimal(nombre)
    motif = None
    if base is not None and base != "20":
        motif = "bareme_different"
    elif d is None or not Decimal(0) <= d <= Decimal(20):
        motif = "moyenne_hors_bornes"
    return _champ(champ, nombre, ligne, page, ancre, motif=motif)


# ================================================================== extracteurs par ligne
_RE_SEM = re.compile(
    r"(?:moyenne|moy\.?)\s*(?:generale\s*)?(?:du\s+|de\s+|au\s+)?(?:semestre|sem\.?|s)\s*(?:n°\s*|no\s*)?(\d{1,2})"
    r"(?![0-9a-z])[\s:=\-]*" + _NUM + _BASE
)
_RE_SEM_INVERSE = re.compile(
    r"semestre\s*(\d{1,2})(?![0-9a-z])\s*[:\-]?\s*(?:moyenne|moy\.?)\s*[:=\-]?\s*" + _NUM + _BASE
)
_RE_ANNUELLE = re.compile(r"(?:moyenne|moy\.?)\s*annuelle[\s:=\-]*" + _NUM + _BASE)
_RE_CREDITS = re.compile(
    r"\bcredits?\s*(?:obtenus?|acquis|capitalises?|valides?)\s*(?:du\s+|au\s+|de\s+)?(?:semestre|sem\.?|s)\s*(\d{1,2})"
    r"(?![0-9a-z])[\s:=\-]*(\d{1,3})(?![.,]?[0-9a-z])" + _EFFECTIF % 3
)
_RE_MENTION = re.compile(r"\bmention\b[^a-z0-9\n]{0,6}(tres\s+bien|assez\s+bien|passable|excellent|bien)(?![a-z0-9])")
_RE_RANG = re.compile(
    r"\b(?:rang|classement)\b[^a-z0-9\n]{0,25}?(\d{1,4})(?:\s*(?:er|ere|eme|ieme|e)\b)?"
    + _EFFECTIF % 4 + r"(?![0-9a-z])"
)
_RE_DECISION = re.compile(
    r"\b(?:decisions?(?:\s+du\s+jury)?|resultat(?:\s+final)?)\b[\s:=\-]*(admis|ajourn|redoubl|rattrap|exclu)"
)
_MOIS = "janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre"
_RE_SESSION = re.compile(r"\bsession\b[\s:=\-]*((?:(?:" + _MOIS + r")\s+)?(?:19|20)\d{2})(?![0-9a-z])")
_RE_AU = re.compile(
    r"\b(?:annee\s+(?:universitaire|scolaire)|a\.u\.?)\s*[:=\-]?\s*((?:19|20)\d{2})\s*[/\-]\s*((?:19|20)\d{2})(?![0-9a-z])"
)
_RE_ANNEE_OBTENTION = re.compile(
    r"\b(?:annee\s+d.obtention|obtenue?\s+en)\b[\s:=\-]*((?:19|20)\d{2})(?![0-9a-z])"
)
_RE_DATE_OBTENTION = re.compile(
    r"\bdate\s+d.obtention\b[\s:=\-]*(\d{1,2}\s*[/.\-]\s*\d{1,2}\s*[/.\-]\s*((?:19|20)\d{2}))(?![0-9a-z])"
)
_RE_CUE_NAISSANCE = re.compile(r"\bne(?:e|\(e\))?\s+le\b|\bdate\s+(?:et\s+lieu\s+)?de\s+naissance\b")
_RE_DATE_NAISSANCE = re.compile(
    r"[\s:=\-]*(\d{1,2}\s*[/.\-]\s*\d{1,2}\s*[/.\-]\s*\d{4}|\d{1,2}(?:er)?\s+[a-z]+\s+\d{4})(?![0-9a-z])"
)
_RE_APRES_DATE = re.compile(r"\s*[,;]?\s*a(?![a-z0-9])\s*:?\s*(?=\S)")
_RE_LIEU = re.compile(r"\blieu\s+de\s+naissance\b[\s:=\-]*(?=[^\s\d])")
_RE_NOM = re.compile(r"^\W*(nom|prenom)\s*[:=]\s*(?=\S)")
_RE_LIBELLE = re.compile(r"^\W*(etablissement(?:\s+[a-z]+){0,2}?|specialite|filiere|serie)\s*[:=]\s*(?=\S)")
_RE_ETAB_NU = re.compile(r"^\W*(universite|ecole|institut|centre\s+universitaire|lycee)\b")
_RE_NUM_BAC = re.compile(
    r"\b(?:n°|no\.?|numero)\s*(?:d.inscription(?:\s+au\s+bac\w*)?|du\s+bac\w*|bac\w*)[\s:=\-]*(\d{5,15})(?![0-9a-z])"
)


def _semestres(ligne: str, sa: str, page: int) -> list[ChampLu]:
    sorties: list[ChampLu] = []
    for motif in (_RE_SEM, _RE_SEM_INVERSE):
        for m in motif.finditer(sa):
            numero = int(m.group(1))
            if 1 <= numero <= SEMESTRES_MAX:
                sorties.append(
                    _moyenne(f"{PREFIXE_MOYENNE_SEMESTRE}{numero}", m.group(2), m.group(3), ligne, page, ligne[m.start(2) : m.end(2)])
                )
    for m in _RE_CREDITS.finditer(sa):
        numero = int(m.group(1))
        if not 1 <= numero <= SEMESTRES_MAX:
            continue
        total = m.group(3)
        motif_credits = "credits_incoherents" if total is not None and int(m.group(2)) > int(total) else None
        sorties.append(
            _champ(f"{PREFIXE_CREDITS_SEMESTRE}{numero}", m.group(2), ligne, page, ligne[m.start(2) : m.end(2)], motif=motif_credits)
        )
    for m in _RE_ANNUELLE.finditer(sa):
        sorties.append(_moyenne(MOYENNE_ANNUELLE, m.group(1), m.group(2), ligne, page, ligne[m.start(1) : m.end(1)]))
    return sorties


def _mention_rang_decision(ligne: str, sa: str, page: int) -> list[ChampLu]:
    sorties: list[ChampLu] = []
    m = _RE_MENTION.search(sa)
    if m:
        cle = " ".join(m.group(1).split())
        sorties.append(_champ(MENTION, MENTIONS[cle], ligne, page, ligne[m.start(1) : m.end(1)]))
    m = _RE_RANG.search(sa)
    if m:
        rang, effectif = m.group(1), m.group(2)
        valeur = f"{int(rang)}/{int(effectif)}" if effectif else str(int(rang))
        sorties.append(_champ(RANG, valeur, ligne, page, ligne[m.start(1) : m.end()], motif=None if int(rang) >= 1 else "rang_invalide"))
    m = _RE_DECISION.search(sa)
    if m:
        lu = _valeur_apres(ligne, m.start(1))
        if lu:
            texte, debut = lu
            propre = " ".join(re.sub(r"\((?:e|es|s)\)", "", texte).split())
            sorties.append(_champ(DECISION_JURY, propre, ligne, page, ligne[debut : debut + len(texte)]))
    return sorties


def _annees(ligne: str, sa: str, page: int) -> list[ChampLu]:
    sorties: list[ChampLu] = []
    m = _RE_SESSION.search(sa)
    if m:
        sorties.append(_champ(SESSION, ligne[m.start(1) : m.end(1)], ligne, page, ligne[m.start(1) : m.end(1)]))
    m = _RE_AU.search(sa)
    if m:
        debut, fin = int(m.group(1)), int(m.group(2))
        sorties.append(
            _champ(
                ANNEE_UNIVERSITAIRE, f"{debut}/{fin}", ligne, page, ligne[m.start(1) : m.end(2)],
                motif=None if fin == debut + 1 else "annee_universitaire_incoherente",
            )
        )
    m = _RE_ANNEE_OBTENTION.search(sa)
    if m:
        sorties.append(_champ(DIPLOME_ANNEE, m.group(1), ligne, page, ligne[m.start(1) : m.end(1)]))
    m = _RE_DATE_OBTENTION.search(sa)
    if m and len(extraire_dates(ligne[m.start(1) : m.end(1)])) == 1:  # une date impossible ne donne rien
        sorties.append(_champ(DIPLOME_ANNEE, m.group(2), ligne, page, ligne[m.start(1) : m.end(1)]))
    return sorties


def _naissance(ligne: str, sa: str, page: int) -> list[ChampLu]:
    sorties: list[ChampLu] = []
    cue = _RE_CUE_NAISSANCE.search(sa)
    if cue:
        md = _RE_DATE_NAISSANCE.match(sa, cue.end())
        if md:
            literal = ligne[md.start(1) : md.end(1)]
            dates = extraire_dates(literal)
            if not dates:
                sorties.append(ChampLu(DATE_NAISSANCE, literal, ligne.strip(), page, CONFIANCE_DOUTEUSE, valide=False, motif="date_invalide", ancre=literal))
            else:
                plausible = ANNEE_NAISSANCE_MINIMUM <= dates[0].year <= date.today().year - AGE_MINIMUM_NAISSANCE
                sorties.append(
                    _champ(DATE_NAISSANCE, dates[0].isoformat(), ligne, page, literal, motif=None if plausible else "date_naissance_implausible")
                )
            ml = _RE_APRES_DATE.match(sa, md.end())
            lieu = _valeur_apres(ligne, ml.end()) if ml else None
            if lieu:
                sorties.append(_champ(LIEU_NAISSANCE, lieu[0], ligne, page, lieu[0]))
    for ml in _RE_LIEU.finditer(sa):
        lieu = _valeur_apres(ligne, ml.end())
        if lieu:
            sorties.append(_champ(LIEU_NAISSANCE, lieu[0], ligne, page, lieu[0]))
    return sorties


def _identite_et_libelles(ligne: str, sa: str, page: int, contexte_bac: bool) -> list[ChampLu]:
    sorties: list[ChampLu] = []
    m = _RE_NOM.match(sa)
    if m and (lu := _valeur_apres(ligne, m.end())):
        sorties.append(_champ(NOM if m.group(1) == "nom" else PRENOM, lu[0], ligne, page, lu[0]))
    m = _RE_LIBELLE.match(sa)
    if m and (lu := _valeur_apres(ligne, m.end())):
        libelle = m.group(1)
        if libelle.startswith("etablissement"):
            champ = DIPLOME_ETABLISSEMENT
        elif libelle == "specialite":
            champ = None if contexte_bac else DIPLOME_SPECIALITE
        elif libelle == "filiere":
            champ = BAC_SERIE if contexte_bac else DIPLOME_FILIERE
        else:
            champ = BAC_SERIE if contexte_bac else None
        if champ is not None:
            sorties.append(_champ(champ, lu[0], ligne, page, lu[0]))
    elif (m := _RE_ETAB_NU.match(sa)) and (lu := _valeur_apres(ligne, m.start(1))):
        sorties.append(_champ(DIPLOME_ETABLISSEMENT, lu[0], ligne, page, lu[0]))
    if contexte_bac and (m := _RE_NUM_BAC.search(sa)):
        sorties.append(_champ(NUMERO_BAC, m.group(1), ligne, page, ligne[m.start(1) : m.end(1)]))
    return sorties


def _lire_ligne(ligne: str, page: int, contexte_bac: bool) -> list[ChampLu]:
    sa = _sa(ligne)
    return (
        _semestres(ligne, sa, page)
        + _mention_rang_decision(ligne, sa, page)
        + _annees(ligne, sa, page)
        + _naissance(ligne, sa, page)
        + _identite_et_libelles(ligne, sa, page, contexte_bac)
    )


# ================================================================== intitulé du diplôme
_INTITULES = (
    ("DEUA", re.compile(r"\bdeua\b|diplome\s+d.etudes\s+universitaires\s+appliquees")),
    ("Baccalauréat", re.compile(r"\bbaccalaureat\b|\bbakaloria\b")),
    ("Licence", re.compile(r"\blicence\b|\blissans\b")),
    ("Master", re.compile(r"\bmaster\b")),
    ("Doctorat", re.compile(r"\bdoctorat\b")),
    ("Magister", re.compile(r"\bmagister\b")),
)
_RE_LIGNE_TITRE = re.compile(r"diplome|intitule|grade|releve|attestation|niveau|formation|cycle|domaine")


def _intitule(lignes: list[str], page: int) -> ChampLu | None:
    """Intitulé écrit dans une ligne de titre (priorité) ; deux intitulés distincts : ambigu."""
    titres: list[tuple[str, str, str]] = []
    autres: list[tuple[str, str, str]] = []
    for ligne in lignes:
        sa = _sa(ligne)
        cible = titres if _RE_LIGNE_TITRE.search(sa) else autres
        for canon, motif in _INTITULES:
            m = motif.search(sa)
            if m:
                cible.append((canon, ligne, ligne[m.start() : m.end()]))
    retenus = titres or autres
    if not retenus:
        return None
    canon, ligne, ancre = retenus[0]
    ambigu = len({c for c, _, _ in retenus}) > 1
    return _champ(DIPLOME_INTITULE, canon, ligne, page, ancre, motif="valeurs_multiples" if ambigu else None)


# ================================================================== réparation OCR (proposition seulement)
_RE_JETON = re.compile(r"(?<![A-Za-z0-9])[0-9OolI][0-9OolI.,/\-]*(?![A-Za-z0-9])")
_REPARATION = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1"})


def _reparer(ligne: str) -> tuple[str, list[tuple[int, int]]]:
    """Corrige O/o→0 et l/I→1 dans les seuls jetons numériques (au moins un vrai chiffre).
    Même longueur ; renvoie aussi les positions modifiées."""
    zones: list[tuple[int, int]] = []

    def corriger(m: re.Match[str]) -> str:
        jeton = m.group(0)
        if not any(c.isdigit() for c in jeton) or not any(c in "OolI" for c in jeton):
            return jeton
        zones.append(m.span())
        return jeton.translate(_REPARATION)

    return _RE_JETON.sub(corriger, ligne), zones


def _ancre_litterale(ligne: str, repare: str, ancre: str | None, zones: list[tuple[int, int]]) -> str:
    pos = repare.find(ancre) if ancre else -1
    if pos >= 0:
        return ligne[pos : pos + len(ancre or "")]
    debut, fin = zones[0]
    return ligne[debut:fin]


def _proposer_ocr(ligne: str, lu: ChampLu, repare: str, zones: list[tuple[int, int]]) -> ChampLu:
    ancre = _ancre_litterale(ligne, repare, lu.ancre, zones)
    motif = "ocr_a_confirmer" if lu.valide else lu.motif
    return replace(
        lu, extrait=ligne.strip(), ancre=ancre, valide=False, motif=motif,
        confiance=min(lu.confiance, CONFIANCE_OCR),
    )


# ================================================================== assemblage
def _cle_comparaison(champ: str, valeur: str) -> str:
    return _sa(normaliser_valeur(champ, valeur)) if champ in _TEXTES_A_CONTROLER else normaliser_valeur(champ, valeur)


def _reduire(candidats: list[ChampLu]) -> list[ChampLu]:
    """Un résultat par champ ; valeurs différentes : `valeurs_multiples` (jamais un choix au hasard)."""
    groupes: dict[str, list[ChampLu]] = {}
    for c in candidats:
        groupes.setdefault(c.champ, []).append(c)
    sorties: list[ChampLu] = []
    for champ, liste in groupes.items():
        premier = next((c for c in liste if c.valide), liste[0])
        if len({_cle_comparaison(champ, c.valeur) for c in liste}) > 1:
            motif = premier.motif if not premier.valide and premier.motif else "valeurs_multiples"
            premier = replace(premier, valide=False, motif=motif, confiance=min(premier.confiance, CONFIANCE_DOUTEUSE))
        sorties.append(premier)
    return sorties


def _moyennes_generales(lignes: list[str], page: int, contexte_diplome: bool = False) -> list[ChampLu]:
    """Moyenne générale/finale/du bac (jamais « annuelle », qui a son propre champ)."""
    retenues = [ligne for ligne in lignes if "annuelle" not in _sa(ligne)]
    sorties = analyser_moyenne("\n".join(retenues), page, moyenne_nue=contexte_diplome)
    for ligne in retenues:
        if analyser_moyenne(ligne, page, moyenne_nue=contexte_diplome):
            continue
        repare, zones = _reparer(ligne)
        if not zones:
            continue
        for lu in analyser_moyenne(repare, page):
            sorties.append(_proposer_ocr(ligne, lu, repare, zones))
    return sorties


def analyser_releve(texte: str, page: int = 1) -> list[ChampLu]:
    """Champs lus d'une page de relevé ou de diplôme ; aucun texte pertinent : aucune valeur."""
    lignes = [ligne for ligne in texte.splitlines() if ligne.strip()]
    intitule = _intitule(lignes, page)
    contexte_bac = intitule is not None and intitule.valide and intitule.valeur == "Baccalauréat"
    candidats: list[ChampLu] = [intitule] if intitule else []
    candidats += _moyennes_generales(lignes, page, intitule is not None and intitule.valide)
    for ligne in lignes:
        lus = _lire_ligne(ligne, page, contexte_bac)
        candidats += lus
        repare, zones = _reparer(ligne)
        if not zones:
            continue
        deja = {c.champ for c in lus}
        candidats += [
            _proposer_ocr(ligne, lu, repare, zones)
            for lu in _lire_ligne(repare, page, contexte_bac)
            if lu.champ not in deja
        ]
    return _reduire(candidats)
