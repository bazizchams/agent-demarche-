"""Validité des certificats de langue (règle unique, partagée par les points forts et les suggestions de vœux).

TCF : 24 mois (config/demarches/campus_france.yaml) ; DELF et DALF : acquis à vie
(docs/ecoles_privees_france.md §1.4) ; tout autre type ou type absent : jamais déduit (« non vérifiable »).
La date de référence est TOUJOURS passée en paramètre : aucun accès à l'horloge ici.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

VALIDITE_TCF_MOIS = 24
SANS_EXPIRATION = frozenset({"DELF", "DALF"})

VALIDE, SANS_EXPIRATION_STATUT, EXPIRE = "valide", "sans_expiration", "expire"
NON_VERIFIABLE_TYPE_ABSENT, NON_VERIFIABLE_TYPE = "non_verifiable_type_absent", "non_verifiable_type"
NON_VERIFIABLE_DATE_ABSENTE, DATE_INCOHERENTE = "non_verifiable_date_absente", "date_incoherente"


@dataclass(frozen=True)
class ValiditeCertificat:
    statut: str
    fin: date | None = None  # fin de validité (TCF seulement)


def ajouter_mois(depart: date, mois: int) -> date:
    total = depart.month - 1 + mois
    annee, mois_cible = depart.year + total // 12, total % 12 + 1
    return date(annee, mois_cible, min(depart.day, calendar.monthrange(annee, mois_cible)[1]))


def evaluer_validite(type_cert: str | None, date_passage: date | None, reference: date) -> ValiditeCertificat:
    if type_cert in SANS_EXPIRATION:
        return ValiditeCertificat(SANS_EXPIRATION_STATUT)
    if type_cert is None:
        return ValiditeCertificat(NON_VERIFIABLE_TYPE_ABSENT)
    if type_cert != "TCF":
        return ValiditeCertificat(NON_VERIFIABLE_TYPE)
    if date_passage is None:
        return ValiditeCertificat(NON_VERIFIABLE_DATE_ABSENTE)
    if date_passage > reference:
        return ValiditeCertificat(DATE_INCOHERENTE)
    fin = ajouter_mois(date_passage, VALIDITE_TCF_MOIS)
    return ValiditeCertificat(EXPIRE if reference > fin else VALIDE, fin)
