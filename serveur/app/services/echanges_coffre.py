"""Remise a usage unique des identifiants du coffre a l'agent local, et depot des identifiants saisis par l'humain
(Regle 3), pour les taches « connexion_portail » et « creation_compte_eef ».

Garanties :
- JAMAIS de remise sans consentement explicite donne dans l'interface web POUR CETTE tache. L'autorisation dure
  `DUREE_AUTORISATION_S` (60 s) et ne sert qu'UNE fois : l'usage est pose par un compare-and-swap
  (`UPDATE ... WHERE utilise_le IS NULL AND expire_le > maintenant`) ;
- seul l'agent local DETENTEUR de la tache (jeton X-Agent-Token, tache `en_cours`) les recoit ;
- l'audit, les erreurs et les evenements ne contiennent que des identifiants opaques ;
- les identifiants deposes par l'agent (lus dans le formulaire au moment de la soumission HUMAINE) sont chiffres,
  valables `DUREE_DEPOT_S` secondes, et ne peuvent aller QUE dans le coffre, sur decision de l'humain.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.chiffrement import chiffrer_champ, dechiffrer_champ
from app.core.erreurs import AccesRefuse, Conflit, DonneesInvalides, NonTrouve
from app.db.base import maintenant_utc
from app.db.tenant import tenant_courant
from app.modeles.agent_local import AgentLocal
from app.modeles.echange_coffre import (
    CHAMP_ECHANGE_IDENTIFIANT,
    CHAMP_ECHANGE_MOT_DE_PASSE,
    DUREE_AUTORISATION_S,
    DUREE_DEPOT_S,
    EchangeCoffre,
    NatureEchange,
)
from app.modeles.journal_audit import ResultatAudit
from app.modeles.tache import (
    ACTION_CONNEXION_PORTAIL,
    ACTION_CREATION_COMPTE_EEF,
    StatutTache,
    TacheDossier,
)
from app.services import audit, coffre_identifiants
from app.services.candidats import obtenir_candidat
from app.services.taches.etat import _exiger_detenteur_agent, _obtenir_tache_orm

LONGUEUR_MAX_SECRET = coffre_identifiants.LONGUEUR_MAX_SECRET
AUTORISATION = NatureEchange.AUTORISATION_LECTURE.value
DEPOT = NatureEchange.DEPOT_A_ENREGISTRER.value


def _tenant(db: Session) -> uuid.UUID:
    tid = tenant_courant(db)
    if tid is None:
        raise RuntimeError("Contexte bureau (tenant) manquant sur la session.")
    return tid


def _auditer(db: Session, action: str, tache: TacheDossier, acteur_id: uuid.UUID | None, **details: Any) -> None:
    audit.journaliser(
        db,
        action,
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="tache",
        ressource_id=tache.id,
        details={"candidat_id": str(tache.candidat_id), "portail": tache.portail, **details},
    )


def _supprimer(db: Session, tid: uuid.UUID, *conditions: Any) -> None:
    db.execute(
        delete(EchangeCoffre).where(EchangeCoffre.tenant_id == tid, *conditions).execution_options(
            synchronize_session=False
        )
    )


def _purger(db: Session, tid: uuid.UUID) -> None:
    """Supprime les echanges expires ou consommes (rien ne traine en base)."""
    _supprimer(db, tid, EchangeCoffre.expire_le <= maintenant_utc())
    _supprimer(db, tid, EchangeCoffre.nature == AUTORISATION, EchangeCoffre.utilise_le.is_not(None))
    db.commit()


def _tache_action(db: Session, tache_id: uuid.UUID, action: str) -> TacheDossier:
    tache = _obtenir_tache_orm(db, tache_id)
    if tache.action != action or tache.portail is None:
        raise Conflit("Cette operation ne concerne pas l'action de cette tache.")
    return tache


def _tache_detenue(db: Session, tache_id: uuid.UUID, agent: AgentLocal, action: str) -> TacheDossier:
    tache = _tache_action(db, tache_id, action)
    _exiger_detenteur_agent(tache, agent.id)
    if tache.statut is not StatutTache.EN_COURS or tache.agent_local_id != agent.id:
        raise AccesRefuse("Cette tache n'est pas reservee par cet agent.")
    return tache


def _coffre_existe(db: Session, tache: TacheDossier) -> bool:
    return bool(
        coffre_identifiants.statut(db, candidat_id=tache.candidat_id, portail=tache.portail or "")["existe"]
    )


# ------------------------------------------------------- consentement (humain) et remise (agent)
def etat_coffre_pour_agent(db: Session, *, tache_id: uuid.UUID, agent: AgentLocal) -> dict[str, bool]:
    tache = _tache_detenue(db, tache_id, agent, ACTION_CONNEXION_PORTAIL)
    return {"existe": _coffre_existe(db, tache)}


def autoriser_connexion(db: Session, *, tache_id: uuid.UUID, acteur_id: uuid.UUID) -> dict[str, Any]:
    """Consentement explicite de l'humain pour CETTE tache : valable 60 s, a usage unique."""
    tid = _tenant(db)
    _purger(db, tid)
    tache = _tache_action(db, tache_id, ACTION_CONNEXION_PORTAIL)
    if tache.statut is not StatutTache.EN_COURS or tache.agent_local_id is None:
        raise Conflit("L'agent ne detient pas encore cette tache : attendez qu'il demande l'autorisation.")
    if not _coffre_existe(db, tache):
        raise Conflit("Aucun identifiant n'est enregistre dans le coffre pour ce portail.")
    _supprimer(db, tid, EchangeCoffre.tache_id == tache.id, EchangeCoffre.nature == AUTORISATION)
    expire = maintenant_utc() + timedelta(seconds=DUREE_AUTORISATION_S)
    db.add(
        EchangeCoffre(
            id=uuid.uuid4(),
            tenant_id=tid,
            tache_id=tache.id,
            candidat_id=tache.candidat_id,
            portail=tache.portail,
            nature=AUTORISATION,
            accorde_par_id=acteur_id,
            agent_local_id=tache.agent_local_id,
            expire_le=expire,
        )
    )
    _auditer(db, "coffre.autorisation_connexion", tache, acteur_id, duree_s=DUREE_AUTORISATION_S)
    db.commit()
    return {"expire_le": expire, "duree_secondes": DUREE_AUTORISATION_S}


def remettre_identifiants(
    db: Session, *, tache_id: uuid.UUID, agent: AgentLocal, cle_maitresse: bytes
) -> coffre_identifiants.IdentifiantsClairs:
    """Remet les identifiants a l'agent detenteur, une seule fois, dans les 60 s qui suivent le consentement."""
    tid = _tenant(db)
    tache = _tache_detenue(db, tache_id, agent, ACTION_CONNEXION_PORTAIL)
    if not _coffre_existe(db, tache):
        raise NonTrouve("Aucun identifiant enregistre pour ce portail.")
    maintenant = maintenant_utc()
    autorisation_id = db.scalar(
        select(EchangeCoffre.id)
        .where(
            EchangeCoffre.tenant_id == tid,
            EchangeCoffre.tache_id == tache.id,
            EchangeCoffre.nature == AUTORISATION,
            EchangeCoffre.agent_local_id == agent.id,
            EchangeCoffre.utilise_le.is_(None),
            EchangeCoffre.expire_le > maintenant,
        )
        .order_by(EchangeCoffre.cree_le.desc())
        .limit(1)
    )
    if autorisation_id is None:
        raise AccesRefuse("Aucune autorisation valide : l'humain doit d'abord autoriser la connexion.")
    resultat = db.execute(
        update(EchangeCoffre)
        .where(
            EchangeCoffre.id == autorisation_id,
            EchangeCoffre.tenant_id == tid,
            EchangeCoffre.utilise_le.is_(None),
            EchangeCoffre.expire_le > maintenant,
        )
        .values(utilise_le=maintenant)
        .execution_options(synchronize_session=False)
    )
    db.commit()
    if resultat.rowcount != 1:
        raise AccesRefuse("Autorisation deja utilisee ou expiree.")
    clairs = coffre_identifiants.lire_pour_agent(
        db,
        candidat_id=tache.candidat_id,
        portail=tache.portail or "",
        cle_maitresse=cle_maitresse,
        acteur_id=None,
    )
    _auditer(db, "coffre.remis_agent", tache, None, agent_local_id=str(agent.id))
    db.commit()
    return clairs


# ------------------------------------------------------- depot des identifiants saisis par l'humain
def _verifier_secret(valeur: str) -> None:
    if not valeur or len(valeur) > LONGUEUR_MAX_SECRET:
        raise DonneesInvalides("Identifiant ou mot de passe vide ou trop long.")


def deposer_identifiants_captes(
    db: Session,
    *,
    tache_id: uuid.UUID,
    agent: AgentLocal,
    identifiant: str,
    mot_de_passe: str,
    cle_maitresse: bytes,
) -> None:
    """Identifiants lus dans le formulaire a la soumission HUMAINE, apres une connexion reussie.
    Stockes chiffres 10 minutes, en attente de la decision de l'humain dans l'interface web."""
    tid = _tenant(db)
    _purger(db, tid)
    tache = _tache_detenue(db, tache_id, agent, ACTION_CONNEXION_PORTAIL)
    _verifier_secret(identifiant)
    _verifier_secret(mot_de_passe)
    _supprimer(db, tid, EchangeCoffre.tache_id == tache.id, EchangeCoffre.nature == DEPOT)
    db.add(
        EchangeCoffre(
            id=uuid.uuid4(),
            tenant_id=tid,
            tache_id=tache.id,
            candidat_id=tache.candidat_id,
            portail=tache.portail,
            nature=DEPOT,
            agent_local_id=agent.id,
            expire_le=maintenant_utc() + timedelta(seconds=DUREE_DEPOT_S),
            identifiant_chiffre=chiffrer_champ(cle_maitresse, tid, CHAMP_ECHANGE_IDENTIFIANT, identifiant),
            mot_de_passe_chiffre=chiffrer_champ(cle_maitresse, tid, CHAMP_ECHANGE_MOT_DE_PASSE, mot_de_passe),
        )
    )
    _auditer(db, "coffre.depot_propose", tache, None, agent_local_id=str(agent.id))
    db.commit()


def _depot_actif(db: Session, tid: uuid.UUID, tache_id: uuid.UUID) -> EchangeCoffre | None:
    return db.scalar(
        select(EchangeCoffre).where(
            EchangeCoffre.tenant_id == tid,
            EchangeCoffre.tache_id == tache_id,
            EchangeCoffre.nature == DEPOT,
            EchangeCoffre.expire_le > maintenant_utc(),
        )
    )


def etat_depot(db: Session, *, tache_id: uuid.UUID) -> dict[str, Any]:
    """Existence seule (jamais la valeur)."""
    tid = _tenant(db)
    _purger(db, tid)
    tache = _obtenir_tache_orm(db, tache_id)
    depot = _depot_actif(db, tid, tache.id)
    return {
        "present": depot is not None,
        "portail": tache.portail if depot is not None else None,
        "expire_le": depot.expire_le if depot is not None else None,
    }


def enregistrer_depot(
    db: Session, *, tache_id: uuid.UUID, acteur_id: uuid.UUID, consentement: bool, cle_maitresse: bytes
) -> dict[str, Any]:
    """L'humain accepte : les identifiants vont dans le coffre (consentement du candidat obligatoire)."""
    tid = _tenant(db)
    _purger(db, tid)
    if consentement is not True:
        raise DonneesInvalides(
            "Le consentement écrit du candidat est obligatoire pour enregistrer ses identifiants."
        )
    tache = _obtenir_tache_orm(db, tache_id)
    depot = _depot_actif(db, tid, tache.id)
    if depot is None or depot.identifiant_chiffre is None or depot.mot_de_passe_chiffre is None:
        raise NonTrouve("Aucun identifiant en attente d'enregistrement (delai depasse ou deja traite).")
    identifiant = dechiffrer_champ(cle_maitresse, tid, CHAMP_ECHANGE_IDENTIFIANT, depot.identifiant_chiffre)
    mot_de_passe = dechiffrer_champ(cle_maitresse, tid, CHAMP_ECHANGE_MOT_DE_PASSE, depot.mot_de_passe_chiffre)
    statut = coffre_identifiants.enregistrer(
        db,
        candidat_id=tache.candidat_id,
        portail=tache.portail or "",
        identifiant=identifiant,
        mot_de_passe=mot_de_passe,
        consentement=True,
        acteur_id=acteur_id,
        cle_maitresse=cle_maitresse,
    )
    db.delete(depot)
    _auditer(db, "coffre.depot_enregistre", tache, acteur_id)
    db.commit()
    return statut


def refuser_depot(db: Session, *, tache_id: uuid.UUID, acteur_id: uuid.UUID) -> None:
    tid = _tenant(db)
    tache = _obtenir_tache_orm(db, tache_id)
    _supprimer(db, tid, EchangeCoffre.tache_id == tache.id, EchangeCoffre.nature == DEPOT)
    _auditer(db, "coffre.depot_refuse", tache, acteur_id)
    db.commit()


# ------------------------------------------------------- creation de compte Etudes en France
def champs_compte_pour_agent(
    db: Session, *, tache_id: uuid.UUID, agent: AgentLocal, cle_maitresse: bytes
) -> dict[str, Any]:
    """Minimisation : seulement ce que le formulaire d'inscription demande. Regle 4 : absent => None."""
    tache = _tache_detenue(db, tache_id, agent, ACTION_CREATION_COMPTE_EEF)
    candidat = obtenir_candidat(db, candidat_id=tache.candidat_id, cle_maitresse=cle_maitresse)
    _auditer(db, "tache.champs_compte_servis_agent", tache, None, agent_local_id=str(agent.id))
    db.commit()
    return {
        "prenom": candidat.prenom or None,
        "nom": candidat.nom or None,
        "email": candidat.email or None,
        "consentement_signe": bool(candidat.consentement_signe),
        "coffre_existe": _coffre_existe(db, tache),
    }


def enregistrer_compte_cree(
    db: Session,
    *,
    tache_id: uuid.UUID,
    agent: AgentLocal,
    identifiant: str,
    mot_de_passe: str,
    cle_maitresse: bytes,
) -> dict[str, Any]:
    """L'agent range dans le coffre l'e-mail et le mot de passe generes, AVANT la soumission du formulaire."""
    tache = _tache_detenue(db, tache_id, agent, ACTION_CREATION_COMPTE_EEF)
    _verifier_secret(identifiant)
    _verifier_secret(mot_de_passe)
    candidat = obtenir_candidat(db, candidat_id=tache.candidat_id, cle_maitresse=cle_maitresse)
    if not candidat.consentement_signe:
        raise Conflit("Le consentement écrit du candidat n'est pas enregistré sur sa fiche.")
    if not candidat.email or identifiant.strip().lower() != candidat.email.strip().lower():
        raise DonneesInvalides("L'identifiant doit être l'adresse e-mail de la fiche du candidat.")
    if _coffre_existe(db, tache):
        raise Conflit("Des identifiants existent déjà dans le coffre pour ce portail : pas de second compte.")
    if tache.creee_par_id is None:
        raise Conflit("Aucun humain n'a lancé cette tâche : consentement non traçable.")
    statut = coffre_identifiants.enregistrer(
        db,
        candidat_id=tache.candidat_id,
        portail=tache.portail or "",
        identifiant=identifiant,
        mot_de_passe=mot_de_passe,
        consentement=True,
        acteur_id=tache.creee_par_id,
        cle_maitresse=cle_maitresse,
    )
    _auditer(db, "coffre.compte_cree_enregistre", tache, None, agent_local_id=str(agent.id))
    db.commit()
    return statut
