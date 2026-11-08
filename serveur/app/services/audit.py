"""Écriture dans le journal d'audit (sans données personnelles)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.journalisation import masquer_pii
from app.modeles.journal_audit import EntreeAudit, ResultatAudit

_TYPES_SIMPLES = (str, int, float, bool, type(None))


def _assainir(details: dict[str, Any] | None) -> dict[str, Any] | None:
    """N'accepte que des valeurs simples, masque les motifs PII, tronque les textes.
    Les appelants doivent déjà ne transmettre que des codes et identifiants."""
    if not details:
        return None
    propre: dict[str, Any] = {}
    for cle, valeur in details.items():
        if not isinstance(valeur, _TYPES_SIMPLES):
            valeur = str(valeur)
        if isinstance(valeur, str):
            valeur = masquer_pii(valeur)[:200]
        propre[str(cle)[:60]] = valeur
    return propre


def journaliser(
    db: Session,
    action: str,
    resultat: ResultatAudit,
    *,
    acteur_id: uuid.UUID | None = None,
    ressource_type: str | None = None,
    ressource_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
) -> EntreeAudit:
    """Ajoute une entrée au journal du bureau courant. Le commit reste à l'appelant,
    pour que l'action et sa trace soient enregistrées dans la même transaction."""
    entree = EntreeAudit(
        id=uuid.uuid4(),
        acteur_id=acteur_id,
        action=action,
        resultat=resultat,
        ressource_type=ressource_type,
        ressource_id=ressource_id,
        details=_assainir(details),
    )
    db.add(entree)
    return entree


def lister(
    db: Session, *, page: int, taille: int, action: str | None = None
) -> tuple[list[EntreeAudit], int]:
    conditions = [EntreeAudit.action == action] if action else []
    total = db.scalar(select(func.count(EntreeAudit.id)).where(*conditions)) or 0
    elements = db.scalars(
        select(EntreeAudit)
        .where(*conditions)
        .order_by(EntreeAudit.horodatage.desc(), EntreeAudit.id)
        .offset((page - 1) * taille)
        .limit(taille)
    ).all()
    return list(elements), total
