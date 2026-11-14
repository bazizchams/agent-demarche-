"""Réservation ATOMIQUE des tâches « Ouvrir sur mon PC » par les Agents Locaux, et service des vœux.

Réservation : une tâche `en_attente` passe à `en_cours` par une SEULE instruction
`UPDATE ... WHERE statut = 'en_attente'` (compare-and-swap) : si deux agents sondent en même temps,
la base n'accorde la ligne qu'à un seul (`rowcount == 1`) ; l'autre passe à la tâche suivante.
Le verrou exclusif du dossier est ensuite acquis ; s'il est déjà pris par une autre tâche, la
réservation est annulée (retour à `en_attente`) et l'agent passe à la suivante.

Vœux : l'agent ne reçoit QUE les vœux au statut `valide` de la tâche qu'il détient (jamais un brouillon).

Règle 3 : aucun mot de passe de portail n'est servi ici ; la connexion se fait à la main dans la
fenêtre visible (aucune route ne transmet le coffre à un PC).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Parametres
from app.core.erreurs import AccesRefuse, Conflit
from app.db.base import maintenant_utc
from app.db.tenant import tenant_courant
from app.modeles.agent_local import AgentLocal
from app.modeles.journal_audit import ResultatAudit
from app.modeles.tache import (
    ACTION_AJOUTER_VOEUX_PANIER,
    ACTIONS_OUVERTURE_PC,
    StatutTache,
    TacheDossier,
)
from app.modeles.voeu_formation import StatutVoeu
from app.schemas.tache import TacheSortie, VoeuAAjouterSortie, VoeuxAAjouterSortie
from app.services import audit
from app.services import voeux as service_voeux
from app.services.taches import (
    _acquerir_ou_rafraichir_verrou,
    _obtenir_tache_orm,
    _obtenir_verrou_actif,
    _serialiser_tache,
)

NB_CANDIDATES_PAR_SONDAGE = 10


def _basculer(
    db: Session,
    tache_id: uuid.UUID,
    tid: uuid.UUID,
    *,
    de: StatutTache,
    vers: StatutTache,
    agent_id: uuid.UUID | None,
    exiger_agent: uuid.UUID | None = None,
) -> bool:
    """Compare-and-swap : change le statut seulement s'il vaut encore `de`. Vrai si CE appel a gagné."""
    valeurs: dict[str, object] = {"statut": vers, "agent_local_id": agent_id}
    if vers is StatutTache.EN_COURS:
        valeurs.update(demarree_le=maintenant_utc(), motif_suspension=None, message_alerte=None)
    conditions = [
        TacheDossier.id == tache_id,
        TacheDossier.tenant_id == tid,
        TacheDossier.statut == de,
    ]
    if exiger_agent is not None:
        conditions.append(TacheDossier.agent_local_id == exiger_agent)
    resultat = db.execute(
        update(TacheDossier)
        .where(*conditions)
        .values(**valeurs)
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return resultat.rowcount == 1


def liberer_taches_abandonnees(
    db: Session, tid: uuid.UUID, actions: Iterable[str], *, delai_grace_s: int
) -> int:
    """Remet en attente les tâches `en_cours` dont l'agent a disparu (verrou du dossier expiré, plus de
    battement de cœur). Chaque libération est elle aussi un compare-and-swap.

    Délai de grâce : une tâche réservée il y a moins de `delai_grace_s` n'est jamais libérée (entre la
    réservation et l'acquisition du verrou, un autre agent la verrait à tort « sans verrou »)."""
    liberees = 0
    limite = maintenant_utc() - timedelta(seconds=delai_grace_s)
    en_cours = db.execute(
        select(TacheDossier.id, TacheDossier.candidat_id).where(
            TacheDossier.statut == StatutTache.EN_COURS,
            TacheDossier.demarree_le < limite,
            TacheDossier.action.in_(list(actions)),
        )
    ).all()
    for tache_id, candidat_id in en_cours:
        verrou = _obtenir_verrou_actif(db, candidat_id)
        db.commit()  # `_obtenir_verrou_actif` a pu supprimer un verrou expiré
        if verrou is not None and verrou.tache_id == tache_id:
            continue
        if _basculer(
            db, tache_id, tid, de=StatutTache.EN_COURS, vers=StatutTache.EN_ATTENTE, agent_id=None
        ):
            liberees += 1
            audit.journaliser(
                db,
                "tache.liberee_agent_absent",
                ResultatAudit.SUCCES,
                ressource_type="tache",
                ressource_id=tache_id,
            )
            db.commit()
    return liberees


def reserver_tache_suivante(
    db: Session,
    *,
    agent: AgentLocal,
    parametres: Parametres,
    cle_maitresse: bytes,
    actions: Iterable[str] | None = None,
) -> TacheSortie | None:
    """Réserve pour `agent` la plus ancienne tâche `en_attente` qu'il sait exécuter. `None` si rien."""
    tid = tenant_courant(db)
    if tid is None:
        raise RuntimeError("Contexte bureau (tenant) manquant sur la session.")
    permises = sorted(ACTIONS_OUVERTURE_PC & set(actions)) if actions else sorted(ACTIONS_OUVERTURE_PC)
    if not permises:
        return None

    liberer_taches_abandonnees(
        db, tid, permises, delai_grace_s=parametres.duree_verrou_dossier_secondes
    )

    candidates = db.execute(
        select(TacheDossier.id)
        .where(TacheDossier.statut == StatutTache.EN_ATTENTE, TacheDossier.action.in_(permises))
        .order_by(TacheDossier.cree_le, TacheDossier.id)
        .limit(NB_CANDIDATES_PAR_SONDAGE)
    ).scalars().all()

    for tache_id in candidates:
        if not _basculer(
            db, tache_id, tid, de=StatutTache.EN_ATTENTE, vers=StatutTache.EN_COURS, agent_id=agent.id
        ):
            continue  # un autre agent l'a prise entre-temps
        tache = db.scalar(
            select(TacheDossier)
            .where(TacheDossier.id == tache_id)
            .execution_options(populate_existing=True)
        )
        try:
            _acquerir_ou_rafraichir_verrou(
                db,
                tid=tid,
                candidat_id=tache.candidat_id,
                tache_id=tache.id,
                detenteur=f"agent:{agent.id}",
                duree_secondes=parametres.duree_verrou_dossier_secondes,
            )
        except Conflit:
            db.rollback()
            _basculer(
                db,
                tache_id,
                tid,
                de=StatutTache.EN_COURS,
                vers=StatutTache.EN_ATTENTE,
                agent_id=None,
                exiger_agent=agent.id,
            )
            continue
        audit.journaliser(
            db,
            "tache.reservation_agent",
            ResultatAudit.SUCCES,
            ressource_type="tache",
            ressource_id=tache.id,
            details={"agent_local_id": str(agent.id), "action": tache.action},
        )
        db.commit()
        db.refresh(tache)
        return _serialiser_tache(db, tache, cle_maitresse)
    return None


def voeux_valides_pour_agent(
    db: Session,
    *,
    tache_id: uuid.UUID,
    agent: AgentLocal,
    cle_maitresse: bytes,
) -> VoeuxAAjouterSortie:
    """Vœux au statut `valide` (et seulement eux) de la tâche détenue par `agent`, action
    `ajouter_voeux_panier` uniquement."""
    tache = _obtenir_tache_orm(db, tache_id)
    if tache.action != ACTION_AJOUTER_VOEUX_PANIER:
        raise Conflit("Cette tâche n'a pas d'action d'ajout de vœux au panier.")
    if tache.statut is not StatutTache.EN_COURS or tache.agent_local_id != agent.id:
        raise AccesRefuse("Cette tâche n'est pas réservée par cet agent : vœux non communiqués.")

    voeux = [
        VoeuAAjouterSortie(
            voeu_id=v["id"],
            rang=v["rang"],
            intitule=v["intitule"],
            etablissement=v["etablissement"],
            niveau=v["niveau"],
            voie=v["voie"].value,
            motivation=v["motivation"] or "",
        )
        for v in service_voeux.lister_voeux(db, tache.candidat_id, cle_maitresse)
        if v["statut"] == StatutVoeu.VALIDE
    ]
    audit.journaliser(
        db,
        "tache.voeux_servis_agent",
        ResultatAudit.SUCCES,
        ressource_type="tache",
        ressource_id=tache.id,
        details={"agent_local_id": str(agent.id), "nb_voeux": len(voeux)},
    )
    db.commit()
    return VoeuxAAjouterSortie(tache_id=tache.id, voeux=voeux)
