"""Verrous exclusifs par dossier candidat."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.erreurs import Conflit
from app.db.base import maintenant_utc
from app.modeles.tache import VerrouDossier

MESSAGE_DOSSIER_VERROUILLE = (
    "Ce dossier candidat est déjà verrouillé par une autre tâche en cours d'exécution."
)


def _obtenir_verrou_actif(
    db: Session, candidat_id: uuid.UUID
) -> VerrouDossier | None:
    maintenant = maintenant_utc()
    verrou = db.scalar(
        select(VerrouDossier).where(VerrouDossier.candidat_id == candidat_id)
    )
    if verrou is None:
        return None
    if verrou.expire_le <= maintenant:
        db.delete(verrou)
        db.flush()
        return None
    return verrou


def _acquerir_ou_rafraichir_verrou(
    db: Session,
    *,
    tid: uuid.UUID,
    candidat_id: uuid.UUID,
    tache_id: uuid.UUID,
    detenteur: str,
    duree_secondes: int,
) -> VerrouDossier:
    maintenant = maintenant_utc()
    expiration = maintenant + timedelta(seconds=duree_secondes)
    verrou_existant = _obtenir_verrou_actif(db, candidat_id)

    if verrou_existant is not None:
        if verrou_existant.tache_id != tache_id:
            raise Conflit(MESSAGE_DOSSIER_VERROUILLE)
        verrou_existant.detenteur = detenteur
        verrou_existant.expire_le = expiration
        db.flush()
        return verrou_existant

    nouveau_verrou = VerrouDossier(
        id=uuid.uuid4(),
        tenant_id=tid,
        candidat_id=candidat_id,
        tache_id=tache_id,
        detenteur=detenteur,
        acquis_le=maintenant,
        expire_le=expiration,
    )
    db.add(nouveau_verrou)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise Conflit(MESSAGE_DOSSIER_VERROUILLE) from exc
    return nouveau_verrou


def _liberer_verrou_dossier(db: Session, *, tache_id: uuid.UUID) -> None:
    verrou = db.scalar(
        select(VerrouDossier).where(VerrouDossier.tache_id == tache_id)
    )
    if verrou is not None:
        db.delete(verrou)
        db.flush()
