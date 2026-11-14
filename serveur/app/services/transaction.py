"""Validation de transaction avec traduction d'une course d'unicité en conflit métier (409)."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.erreurs import Conflit


def commit_ou_conflit(db: Session, message: str) -> None:
    """Valide la transaction ; sur violation d'unicité (requête concurrente), annule et lève `Conflit`."""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflit(message) from None
