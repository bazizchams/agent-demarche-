"""Contrôle de complétude du dossier (Règle 4) partagé par le démarrage et la reprise."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Parametres
from app.modeles.tache import TacheDossier
from app.services.candidats import obtenir_candidat
from app.services.documents import lister_documents_orm
from app.services.pieces_requises import (
    obtenir_demarche,
    verifier_completude_dossier,
)


def _evaluer_completude_tache(
    db: Session,
    tache: TacheDossier,
    parametres: Parametres,
    cle_maitresse: bytes,
) -> Any:
    candidat = obtenir_candidat(
        db, candidat_id=tache.candidat_id, cle_maitresse=cle_maitresse
    )
    docs_orm = lister_documents_orm(db, candidat_id=tache.candidat_id)
    demarche = obtenir_demarche(
        parametres.dossier_demarches, tache.code_demarche, db
    )
    return verifier_completude_dossier(
        candidat=candidat, documents=docs_orm, demarche=demarche
    )
