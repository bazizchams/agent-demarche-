"""Création d'une tâche, de ses étapes (issues du YAML de la démarche) et consultation."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Parametres
from app.core.erreurs import Conflit
from app.db.base import maintenant_utc
from app.modeles.journal_audit import ResultatAudit
from app.modeles.tache import (
    ACTION_PREREMPLISSAGE,
    EtapeTache,
    MotifSuspensionTache,
    StatutEtapeTache,
    StatutTache,
    TacheDossier,
)
from app.schemas.tache import TacheCreation, TacheSortie
from app.services import audit
from app.services.candidats import obtenir_candidat
from app.services.documents import lister_documents_orm
from app.services.pieces_requises import (
    obtenir_demarche,
    verifier_completude_dossier,
)
from app.services.taches.etat import (
    STATUTS_TACHE_OUVERTE,
    _exiger_tenant,
    _obtenir_tache_orm,
)
from app.services.taches.serialisation import _serialiser_tache

MESSAGE_ALERTE_CREATION = (
    "Dossier incomplet (Règle 4 : aucune valeur par défaut inventée). "
    "Complétez les données ou pièces signalées avant de reprendre la tâche."
)


def _motif_prerequis(completude: Any) -> MotifSuspensionTache:
    return (
        MotifSuspensionTache.DONNEE_MANQUANTE
        if completude.champs_candidat_manquants
        else MotifSuspensionTache.PIECE_MANQUANTE_OU_INVALIDE
    )


def _exiger_aucune_tache_ouverte(
    db: Session, candidat_id: uuid.UUID, code_demarche: str
) -> None:
    tache_ouverte = db.scalar(
        select(TacheDossier.id).where(
            TacheDossier.candidat_id == candidat_id,
            TacheDossier.code_demarche == code_demarche,
            TacheDossier.action == ACTION_PREREMPLISSAGE,
            TacheDossier.statut.in_(STATUTS_TACHE_OUVERTE),
        )
    )
    if tache_ouverte is not None:
        raise Conflit(
            "Une tâche est déjà active ou en attente de validation pour ce candidat et cette démarche."
        )


def _construire_tache(
    *,
    tid: uuid.UUID,
    candidat_id: uuid.UUID,
    code_demarche: str,
    completude: Any,
    acteur_id: uuid.UUID,
    maintenant: datetime,
) -> TacheDossier:
    tache_id = uuid.uuid4()
    if not completude.pret_pour_prerequis:
        return TacheDossier(
            id=tache_id,
            tenant_id=tid,
            candidat_id=candidat_id,
            code_demarche=code_demarche,
            statut=StatutTache.SUSPENDUE,
            motif_suspension=_motif_prerequis(completude),
            message_alerte=MESSAGE_ALERTE_CREATION,
            champs_manquants_json=json.dumps(completude.champs_candidat_manquants),
            pieces_manquantes_json=json.dumps(
                completude.pieces_manquantes_ou_invalides
            ),
            creee_par_id=acteur_id,
            suspendue_le=maintenant,
        )
    return TacheDossier(
        id=tache_id,
        tenant_id=tid,
        candidat_id=candidat_id,
        code_demarche=code_demarche,
        statut=StatutTache.EN_ATTENTE,
        creee_par_id=acteur_id,
    )


def _etat_initial_etape(
    est_premiere: bool, pret: bool, maintenant: datetime
) -> tuple[StatutEtapeTache, str | None, datetime | None, datetime | None]:
    """Retourne (statut, clé d'idempotence, commencée le, terminée le)."""
    if est_premiere and pret:
        return StatutEtapeTache.TERMINEE, "prerequis-initiaux-ok", maintenant, maintenant
    if est_premiere and not pret:
        return StatutEtapeTache.SUSPENDUE, None, maintenant, None
    return StatutEtapeTache.A_FAIRE, None, None, None


def _creer_etapes(
    db: Session,
    *,
    tid: uuid.UUID,
    tache: TacheDossier,
    demarche: Any,
    pret: bool,
    maintenant: datetime,
) -> None:
    for idx, cfg_etape in enumerate(demarche.etapes_tache, start=1):
        est_premiere = idx == 1
        statut_etape, cle_idem, commencee, terminee = _etat_initial_etape(
            est_premiere, pret, maintenant
        )
        db.add(
            EtapeTache(
                id=uuid.uuid4(),
                tenant_id=tid,
                tache_id=tache.id,
                ordre=idx,
                code_etape=cfg_etape.code,
                libelle=cfg_etape.libelle,
                statut=statut_etape,
                cle_idempotence=cle_idem,
                nb_tentatives=1 if est_premiere else 0,
                commencee_le=commencee,
                terminee_le=terminee,
            )
        )


def creer_tache(
    db: Session,
    *,
    donnees: TacheCreation,
    acteur_id: uuid.UUID,
    parametres: Parametres,
    cle_maitresse: bytes,
) -> TacheSortie:
    """Crée une tâche longue pour un candidat et une démarche.
    Applique immédiatement la Règle 4 : si des champs candidats ou des pièces justificatives
    obligatoires manquent ou sont invalides, la tâche naît à l'état `suspendue` avec l'alerte
    détaillée (aucune valeur par défaut n'est inventée)."""
    tid = _exiger_tenant(db)

    candidat = obtenir_candidat(
        db, candidat_id=donnees.candidat_id, cle_maitresse=cle_maitresse
    )
    docs_orm = lister_documents_orm(db, candidat_id=candidat.id)
    demarche = obtenir_demarche(
        parametres.dossier_demarches, donnees.code_demarche, db
    )
    _exiger_aucune_tache_ouverte(db, candidat.id, demarche.code)

    completude = verifier_completude_dossier(
        candidat=candidat,
        documents=docs_orm,
        demarche=demarche,
    )
    maintenant = maintenant_utc()
    tache = _construire_tache(
        tid=tid,
        candidat_id=candidat.id,
        code_demarche=demarche.code,
        completude=completude,
        acteur_id=acteur_id,
        maintenant=maintenant,
    )
    db.add(tache)
    db.flush()

    _creer_etapes(
        db,
        tid=tid,
        tache=tache,
        demarche=demarche,
        pret=completude.pret_pour_prerequis,
        maintenant=maintenant,
    )
    db.flush()
    db.refresh(tache)

    audit.journaliser(
        db,
        "tache.creation"
        if completude.pret_pour_prerequis
        else "tache.creation_suspendue_prerequis",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="tache",
        ressource_id=tache.id,
        details={
            "code_demarche": demarche.code,
            "statut_initial": tache.statut.value,
            "nb_champs_manquants": len(completude.champs_candidat_manquants),
            "nb_pieces_invalides": len(completude.pieces_manquantes_ou_invalides),
        },
    )
    db.commit()
    return _serialiser_tache(db, tache, cle_maitresse)


def obtenir_tache(
    db: Session, *, tache_id: uuid.UUID, cle_maitresse: bytes
) -> TacheSortie:
    tache = _obtenir_tache_orm(db, tache_id)
    return _serialiser_tache(db, tache, cle_maitresse)


def lister_taches(
    db: Session,
    *,
    cle_maitresse: bytes,
    page: int = 1,
    taille: int = 20,
    statut: StatutTache | None = None,
    candidat_id: uuid.UUID | None = None,
    code_demarche: str | None = None,
) -> tuple[list[TacheSortie], int]:
    _exiger_tenant(db)
    conditions = []
    if statut is not None:
        conditions.append(TacheDossier.statut == statut)
    if candidat_id is not None:
        conditions.append(TacheDossier.candidat_id == candidat_id)
    if code_demarche is not None:
        conditions.append(TacheDossier.code_demarche == code_demarche)

    total = db.scalar(select(func.count(TacheDossier.id)).where(*conditions)) or 0
    lignes = db.scalars(
        select(TacheDossier)
        .where(*conditions)
        .order_by(TacheDossier.cree_le.desc(), TacheDossier.id)
        .offset((page - 1) * taille)
        .limit(taille)
    ).all()
    return [_serialiser_tache(db, t, cle_maitresse) for t in lignes], total
