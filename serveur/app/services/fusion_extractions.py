"""Double lecture A/B champ par champ et contrôles croisés entre pièces.

Règle de fusion (règle 4, jamais de valeur fausse en silence) :
- `auto`        : lecteurs A et B concordent ET les deux extraits sont ancrés littéralement dans le
                  texte de la page ; ou (exception documentée) lecture A vérifiée par les chiffres
                  de contrôle OACI de la MRZ et non contredite par B ;
- `a_verifier`  : tout le reste (discordance, lecture unique, valeur invalide) : la valeur n'est
                  JAMAIS appliquée à la fiche sans validation humaine ;
- `rejete`      : valeur non ancrée dans le document (aucun extrait littéral qui la porte).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from app.core.chiffrement import normaliser_pour_index
from app.modeles.extraction_document import StatutExtraction
from app.services.extraction_champs import (
    CHAMPS_CONNUS,
    CHAMPS_DATES,
    DATE_EXPIRATION_PASSEPORT,
    DATE_NAISSANCE,
    IELTS_BANDE,
    MOYENNE_GENERALE,
    NATIONALITE_CODE,
    NOM,
    NUMERO_PASSEPORT,
    PRENOM,
    ChampLu,
    extraire_dates,
    normaliser_valeur,
    valeur_valide,
)

DELAI_EXPIRATION_PROCHE_JOURS = 180
_CHAMPS_TEXTE_LONG = frozenset({NOM, PRENOM, NUMERO_PASSEPORT, NATIONALITE_CODE})
_RE_NOMBRE = re.compile(r"\d+(?:[.,]\d+)?")


@dataclass(frozen=True)
class ChampFusionne:
    champ: str
    valeur: str
    extrait: str
    page: int | None
    source: str  # « A » ou « B » : lecteur dont la valeur est retenue
    confiance: float
    statut: StatutExtraction
    motif: str | None = None
    valeur_alternative: str | None = None


def _sans_accents_casefold(texte: str) -> str:
    sans = "".join(c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c))
    return sans.casefold()


def _compact(texte: str) -> str:
    return re.sub(r"\s+", "", _sans_accents_casefold(texte))


def _valeur_dans_extrait(champ: str, valeur: str, extrait: str) -> bool:
    cible = normaliser_valeur(champ, valeur)
    if champ in CHAMPS_DATES:
        return any(d.isoformat() == cible for d in extraire_dates(extrait))
    if champ in (MOYENNE_GENERALE, IELTS_BANDE):
        try:
            attendu = Decimal(cible)
            return any(Decimal(n.replace(",", ".")) == attendu for n in _RE_NOMBRE.findall(extrait))
        except InvalidOperation:
            return False
    if champ in _CHAMPS_TEXTE_LONG:
        return bool(_compact(valeur)) and _compact(valeur) in _compact(extrait)
    # Jetons courts (sexe, niveau, type de test) : mot entier, pour ne pas ancrer « F » dans « Français ».
    motif = rf"(?<![a-z0-9]){re.escape(_compact(valeur))}(?![a-z0-9])"
    return bool(re.search(motif, _sans_accents_casefold(extrait)))


def valeur_ancree(lu: ChampLu, texte_page: str | None) -> bool:
    """Ancrage littéral : l'extrait cité figure dans le texte de la page ET porte la valeur."""
    if not texte_page or not lu.extrait or not lu.extrait.strip():
        return False
    if _compact(lu.extrait) not in _compact(texte_page):
        return False
    if lu.ancre is not None:
        return _compact(lu.ancre) in _compact(lu.extrait)
    return _valeur_dans_extrait(lu.champ, lu.valeur, lu.extrait)


def _equivalentes(champ: str, x: str, y: str) -> bool:
    if champ in _CHAMPS_TEXTE_LONG:
        return _compact(x) == _compact(y)
    return normaliser_valeur(champ, x) == normaliser_valeur(champ, y)


def _indexer(lectures: Sequence[ChampLu] | None) -> dict[str, ChampLu]:
    index: dict[str, ChampLu] = {}
    for lu in lectures or ():
        if lu.champ in CHAMPS_CONNUS and lu.champ not in index and lu.valeur.strip():
            index[lu.champ] = lu
    return index


def _fusion(
    lu: ChampLu,
    source: str,
    statut: StatutExtraction,
    motif: str | None,
    *,
    confiance: float | None = None,
    alternative: str | None = None,
) -> ChampFusionne:
    return ChampFusionne(
        champ=lu.champ,
        valeur=normaliser_valeur(lu.champ, lu.valeur) if source == "B" else lu.valeur,
        extrait=lu.extrait,
        page=lu.page,
        source=source,
        confiance=lu.confiance if confiance is None else confiance,
        statut=statut,
        motif=motif,
        valeur_alternative=alternative,
    )


def fusionner_lectures(
    lecture_a: Sequence[ChampLu],
    lecture_b: Sequence[ChampLu] | None,
    textes_pages: Mapping[int, str],
    *,
    autoriser_controle_mrz: bool = True,
) -> list[ChampFusionne]:
    """Fusionne la lecture A (déterministe) et la lecture B (vision, `None` si absente)."""
    a_par_champ, b_par_champ = _indexer(lecture_a), _indexer(lecture_b)
    b_a_lu = lecture_b is not None
    resultats: list[ChampFusionne] = []
    for champ in [*a_par_champ, *(c for c in b_par_champ if c not in a_par_champ)]:
        a, b = a_par_champ.get(champ), b_par_champ.get(champ)
        if a is not None:
            resultats.append(_fusion_avec_a(a, b, b_a_lu, textes_pages, autoriser_controle_mrz))
        elif b is not None:
            resultats.append(_fusion_b_seul(b, textes_pages))
    return resultats


def _fusion_avec_a(
    a: ChampLu, b: ChampLu | None, b_a_lu: bool, textes: Mapping[int, str], autoriser_mrz: bool
) -> ChampFusionne:
    ref = StatutExtraction
    alternative = normaliser_valeur(a.champ, b.valeur) if b is not None else None
    if not valeur_ancree(a, textes.get(a.page)):
        return _fusion(a, "A", ref.REJETE, "non_ancree", confiance=0.0, alternative=alternative)
    if not a.valide:
        return _fusion(a, "A", ref.A_VERIFIER, a.motif or "lecture_invalide", alternative=alternative)
    fort = a.controle_fort and autoriser_mrz
    if b is None:
        if fort:
            return _fusion(a, "A", ref.AUTO, "controle_icao")
        return _fusion(a, "A", ref.A_VERIFIER, "lecteur_b_sans_valeur" if b_a_lu else "double_lecture_absente")
    if not _equivalentes(a.champ, a.valeur, b.valeur):
        return _fusion(a, "A", ref.A_VERIFIER, "discordance_ab", alternative=alternative)
    if not valeur_ancree(b, textes.get(b.page)):
        return _fusion(a, "A", ref.A_VERIFIER, "b_non_ancre")
    return _fusion(a, "A", ref.AUTO, None, confiance=min(a.confiance, b.confiance))


def _fusion_b_seul(b: ChampLu, textes: Mapping[int, str]) -> ChampFusionne:
    ref = StatutExtraction
    valeur = normaliser_valeur(b.champ, b.valeur)
    if not valeur_ancree(b, textes.get(b.page)):
        return _fusion(b, "B", ref.REJETE, "non_ancree", confiance=0.0)
    if not valeur_valide(b.champ, valeur):
        return _fusion(b, "B", ref.REJETE, "valeur_invalide", confiance=0.0)
    return _fusion(b, "B", ref.A_VERIFIER, "lecteur_a_absent", confiance=min(b.confiance, 0.5))


# ================================================================== contrôles croisés


@dataclass(frozen=True)
class ValeurExtraite:
    extraction_id: object | None
    document_id: str
    type_piece: str
    champ: str
    valeur: str


@dataclass(frozen=True)
class AlerteControle:
    code: str
    champ: str | None
    document_ids: tuple[str, ...]
    extraction_ids: tuple[object, ...]
    message: str  # jamais de donnée personnelle (règle 5)


def _jetons(valeur: str) -> frozenset[str]:
    return frozenset(normaliser_pour_index(valeur.replace("-", " ")).split())


def _compatibles(champ: str, x: str, y: str) -> bool:
    if champ == NOM:
        return _jetons(x) == _jetons(y) or _compact(normaliser_pour_index(x)) == _compact(normaliser_pour_index(y))
    if champ == PRENOM:
        jx, jy = _jetons(x), _jetons(y)
        return bool(jx) and bool(jy) and (jx <= jy or jy <= jx)
    return normaliser_valeur(champ, x) == normaliser_valeur(champ, y)


_ALERTES_IDENTITE = {
    NOM: ("nom_discordant", "Le nom lu n'est pas identique entre les pièces du dossier."),
    PRENOM: ("prenom_discordant", "Le prénom lu n'est pas identique entre les pièces du dossier."),
    DATE_NAISSANCE: (
        "date_naissance_discordante",
        "La date de naissance lue n'est pas identique entre les pièces du dossier.",
    ),
}


def controles_croises(valeurs: Sequence[ValeurExtraite], *, date_reference: date) -> list[AlerteControle]:
    """Contrôles entre pièces (nom, prénom, date de naissance) et d'expiration du passeport."""
    alertes: list[AlerteControle] = []
    for champ, (code, message) in _ALERTES_IDENTITE.items():
        lignes = [v for v in valeurs if v.champ == champ and v.valeur.strip()]
        documents = {v.document_id for v in lignes}
        if len(documents) < 2:
            continue
        discordant = any(
            not _compatibles(champ, x.valeur, y.valeur)
            for i, x in enumerate(lignes)
            for y in lignes[i + 1 :]
            if x.document_id != y.document_id
        )
        if discordant:
            alertes.append(
                AlerteControle(
                    code=code,
                    champ=champ,
                    document_ids=tuple(sorted(documents)),
                    extraction_ids=tuple(v.extraction_id for v in lignes if v.extraction_id is not None),
                    message=message,
                )
            )
    for v in valeurs:
        if v.champ != DATE_EXPIRATION_PASSEPORT:
            continue
        try:
            fin = date.fromisoformat(v.valeur)
        except ValueError:
            continue
        if fin < date_reference:
            code, message = "passeport_expire", "Le passeport lu est expiré."
        elif fin < date_reference + timedelta(days=DELAI_EXPIRATION_PROCHE_JOURS):
            code, message = "passeport_expiration_proche", "Le passeport lu expire dans moins de six mois."
        else:
            continue
        ids: tuple[object, ...] = (v.extraction_id,) if v.extraction_id is not None else ()
        alertes.append(AlerteControle(code, v.champ, (v.document_id,), ids, message))
    return alertes
