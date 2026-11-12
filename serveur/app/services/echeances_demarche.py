"""Calcul des échéances d'une démarche (date fixe ou relative à la rentrée / au dépôt)."""

from __future__ import annotations

from datetime import date, timedelta

from app.services.pieces_requises import ConfigDemarche

SEUIL_URGENTE_JOURS = 7
SEUIL_PROCHE_JOURS = 30


def _statut(jours_restants: int | None) -> str:
    if jours_restants is None:
        return "indeterminee"
    if jours_restants < 0:
        return "depassee"
    if jours_restants <= SEUIL_URGENTE_JOURS:
        return "urgente"
    if jours_restants <= SEUIL_PROCHE_JOURS:
        return "proche"
    return "a_venir"


def calculer_echeances(
    demarche: ConfigDemarche,
    *,
    aujourd_hui: date,
    date_rentree: date | None = None,
    date_depot: date | None = None,
) -> list[dict]:
    """Une entrée par échéance ; date None (statut « indeterminee ») si non calculable
    (jamais de date inventée : la date de référence manque)."""
    references = {"rentree": date_rentree, "depot": date_depot}
    resultat: list[dict] = []
    for ech in demarche.echeances:
        if ech.date_fixe is not None:
            echeance = ech.date_fixe
        else:
            base = references.get(ech.reference or "")
            echeance = (
                base - timedelta(days=ech.jours_avant_reference or 0)
                if base is not None
                else None
            )
        jours = (echeance - aujourd_hui).days if echeance is not None else None
        rappels = (
            sorted((r for r in set(ech.rappel_jours_avant) if jours <= r), reverse=True)
            if jours is not None and jours >= 0
            else []
        )
        resultat.append(
            {
                "code": ech.code,
                "libelle": ech.libelle,
                "date": echeance,
                "jours_restants": jours,
                "statut": _statut(jours),
                "rappels_dus": rappels,
            }
        )
    return resultat
