"""Discussion de l'agent en direct : événements d'une tâche, consignes de l'humain, commandes, purge.

Garanties :
- Texte court CHIFFRÉ (clé du bureau) et MASQUÉ avant stockage (mot de passe, identifiant, passeport, e-mail,
  longs nombres) : règles 3 et 5. Le serveur ne reçoit jamais de valeur de formulaire.
- Une consigne de l'utilisateur est du TEXTE : si elle contredit les règles 1, 2, 3 ou 6, elle est
  marquée `refusee`, jamais transmise à l'agent comme instruction, et une réponse polie de refus est
  ajoutée à la discussion. Elle ne change jamais l'état de la tâche.
- Isolation par bureau (filtre tenant de la session) ; seul l'agent détenteur de la tâche écrit ses événements.
- Purge automatique des événements de plus de 7 jours.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.chiffrement import chiffrer_champ, dechiffrer_champ
from app.core.erreurs import AccesRefuse, Conflit, NonTrouve
from app.db.base import maintenant_utc
from app.db.tenant import sans_filtre_tenant, tenant_courant
from app.modeles.evenement_agent import (
    CODE_CONSIGNE_REFUSEE,
    CODES_COMMANDE,
    AuteurEvenement,
    EvenementAgent,
    TypeEvenementAgent,
)
from app.modeles.journal_audit import ResultatAudit
from app.modeles.tache import StatutTache, TacheDossier
from app.schemas.evenement_agent import (
    CommandeSortie,
    EvenementEntree,
    EvenementSortie,
    ListeEvenementsSortie,
    MessageSortie,
    MessagesEnAttenteSortie,
)
from app.services import audit
from app.services.consignes_agent import analyser_consigne, masquer_texte_sensible
from app.services.taches import _obtenir_tache_orm

NOM_CHAMP = "evenement_agent"
DUREE_CONSERVATION_JOURS = 7
NB_MAX_LISTE = 500
NB_TENTATIVES_SEQ = 6
INTERVALLE_PURGE_S = 3600.0
STATUTS_FERMES = frozenset({StatutTache.TERMINEE, StatutTache.ANNULEE})
_derniere_purge = 0.0


def _tid(db: Session) -> uuid.UUID:
    tid = tenant_courant(db)
    if tid is None:
        raise RuntimeError("Contexte bureau (tenant) manquant sur la session.")
    return tid


def _sortie(e: EvenementAgent, cle: bytes) -> EvenementSortie:
    return EvenementSortie(
        id=e.id,
        tache_id=e.tache_id,
        seq=e.seq,
        type=e.type,  # type: ignore[arg-type]
        auteur=e.auteur,  # type: ignore[arg-type]
        code=e.code,
        texte=dechiffrer_champ(cle, e.tenant_id, NOM_CHAMP, e.texte_chiffre) or "",
        cree_le=e.cree_le,
        traite=e.traite_le is not None,
    )


def _ajouter(
    db: Session,
    *,
    tache: TacheDossier,
    type_: TypeEvenementAgent,
    auteur: AuteurEvenement,
    texte: str,
    cle: bytes,
    code: str | None = None,
    traite: bool = False,
) -> EvenementAgent:
    """Insère un événement avec le prochain `seq` de la tâche (nouvel essai si deux écritures se croisent)."""
    tid = _tid(db)
    propre = masquer_texte_sensible(texte)
    if not propre:
        raise Conflit("Message vide après masquage des données sensibles.")
    chiffre = chiffrer_champ(cle, tid, NOM_CHAMP, propre)
    for _ in range(NB_TENTATIVES_SEQ):
        dernier = db.scalar(select(func.max(EvenementAgent.seq)).where(EvenementAgent.tache_id == tache.id)) or 0
        evenement = EvenementAgent(
            tenant_id=tid,
            tache_id=tache.id,
            seq=dernier + 1,
            type=type_.value,
            auteur=auteur.value,
            code=code,
            texte_chiffre=chiffre,
            traite_le=maintenant_utc() if traite else None,
        )
        db.add(evenement)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        return evenement
    raise Conflit("Journal de l'agent occupé : réessayez.")


def _purger_si_utile(db: Session) -> None:
    global _derniere_purge
    maintenant = time.monotonic()
    if maintenant - _derniere_purge < INTERVALLE_PURGE_S:
        return
    _derniere_purge = maintenant
    purger_evenements_expires(db)


def purger_evenements_expires(
    db: Session, *, maintenant: datetime | None = None, jours: int = DUREE_CONSERVATION_JOURS
) -> int:
    """Supprime, tous bureaux confondus (opération système), les événements de plus de `jours` jours."""
    limite = (maintenant or maintenant_utc()) - timedelta(days=jours)
    with sans_filtre_tenant(db):
        resultat = db.execute(delete(EvenementAgent).where(EvenementAgent.cree_le < limite))
        db.commit()
    return int(resultat.rowcount or 0)


# --------------------------------------------------------------------------- côté agent
def enregistrer_evenement_agent(
    db: Session, *, tache_id: uuid.UUID, agent_id: uuid.UUID, donnees: EvenementEntree, cle: bytes
) -> EvenementSortie:
    """Événement émis par l'agent détenteur de la tâche (jamais un autre agent, jamais un autre bureau)."""
    tache = _obtenir_tache_orm(db, tache_id)
    if tache.agent_local_id != agent_id:
        raise AccesRefuse("Cette tâche n'est pas détenue par cet agent : événement refusé.")
    type_ = TypeEvenementAgent(donnees.type)
    code = donnees.code
    if type_ is TypeEvenementAgent.COMMANDE:
        if code not in CODES_COMMANDE:
            raise Conflit("Commande inconnue.")
    else:
        code = None
    # Un message tapé par l'humain dans le panneau de SA fenêtre est relayé comme `utilisateur`/`commande`.
    relaye_humain = type_ in (TypeEvenementAgent.UTILISATEUR, TypeEvenementAgent.COMMANDE)
    evenement = _ajouter(
        db,
        tache=tache,
        type_=type_,
        auteur=AuteurEvenement.HUMAIN if relaye_humain else AuteurEvenement.AGENT,
        texte=donnees.texte,
        cle=cle,
        code=code,
        traite=relaye_humain,
    )
    _purger_si_utile(db)
    return _sortie(evenement, cle)


def messages_en_attente(
    db: Session, *, tache_id: uuid.UUID, agent_id: uuid.UUID, cle: bytes
) -> MessagesEnAttenteSortie:
    """Consignes et commandes de l'humain pas encore vues par l'agent (elles sont marquées traitées).
    Une consigne refusée (règles 1/2/3/6) n'est jamais rendue comme instruction."""
    tache = _obtenir_tache_orm(db, tache_id)
    if tache.agent_local_id != agent_id:
        raise AccesRefuse("Cette tâche n'est pas détenue par cet agent.")
    lignes = db.scalars(
        select(EvenementAgent)
        .where(
            EvenementAgent.tache_id == tache_id,
            EvenementAgent.auteur == AuteurEvenement.HUMAIN.value,
            EvenementAgent.traite_le.is_(None),
        )
        .order_by(EvenementAgent.seq)
    ).all()
    messages: list[EvenementSortie] = []
    commandes: list[str] = []
    for ligne in lignes:
        if ligne.type == TypeEvenementAgent.COMMANDE.value and ligne.code:
            commandes.append(ligne.code)
        elif ligne.type == TypeEvenementAgent.UTILISATEUR.value and ligne.code != CODE_CONSIGNE_REFUSEE:
            messages.append(_sortie(ligne, cle))
        ligne.traite_le = maintenant_utc()
    db.commit()
    return MessagesEnAttenteSortie(messages=messages, commandes=commandes, etat=etat_agent(db, tache_id))


def etat_agent(db: Session, tache_id: uuid.UUID) -> str:
    """Dernier ordre pause/reprise/arret de l'humain : `pause`, `arret` ou `en_cours`."""
    code = db.scalar(
        select(EvenementAgent.code)
        .where(
            EvenementAgent.tache_id == tache_id,
            EvenementAgent.type == TypeEvenementAgent.COMMANDE.value,
            EvenementAgent.code.in_(("pause", "reprise", "arret")),
        )
        .order_by(EvenementAgent.seq.desc())
        .limit(1)
    )
    return {"pause": "pause", "arret": "arret"}.get(code or "", "en_cours")


# --------------------------------------------------------------------------- côté humain
def lister_evenements(
    db: Session, *, tache_id: uuid.UUID, depuis: int, cle: bytes, limite: int = NB_MAX_LISTE
) -> ListeEvenementsSortie:
    _obtenir_tache_orm(db, tache_id)
    lignes = db.scalars(
        select(EvenementAgent)
        .where(EvenementAgent.tache_id == tache_id, EvenementAgent.seq > depuis)
        .order_by(EvenementAgent.seq)
        .limit(min(limite, NB_MAX_LISTE))
    ).all()
    elements = [_sortie(ligne, cle) for ligne in lignes]
    return ListeEvenementsSortie(
        elements=elements,
        dernier=elements[-1].seq if elements else depuis,
        etat=etat_agent(db, tache_id),  # type: ignore[arg-type]
    )


def poster_message_humain(
    db: Session, *, tache_id: uuid.UUID, acteur_id: uuid.UUID, texte: str, cle: bytes
) -> MessageSortie:
    tache = _obtenir_tache_orm(db, tache_id)
    if tache.statut in STATUTS_FERMES:
        raise Conflit("La tâche est terminée : la discussion est fermée.")
    refus = analyser_consigne(texte)
    message = _ajouter(
        db,
        tache=tache,
        type_=TypeEvenementAgent.UTILISATEUR,
        auteur=AuteurEvenement.HUMAIN,
        texte=texte,
        cle=cle,
        code=CODE_CONSIGNE_REFUSEE if refus else None,
        traite=refus is not None,
    )
    reponse: EvenementSortie | None = None
    if refus is not None:
        poste = _ajouter(
            db, tache=tache, type_=TypeEvenementAgent.AGENT, auteur=AuteurEvenement.AGENT,
            texte=refus.message, cle=cle, traite=True,
        )
        reponse = _sortie(poste, cle)
        audit.journaliser(
            db, "agent.consigne_refusee", ResultatAudit.REFUS, acteur_id=acteur_id,
            ressource_type="tache", ressource_id=tache.id, details={"regle": refus.regle},
        )
        db.commit()
    return MessageSortie(message=_sortie(message, cle), refuse=refus is not None, reponse=reponse)


def poster_commande_humaine(
    db: Session, *, tache_id: uuid.UUID, acteur_id: uuid.UUID, code: str, cle: bytes
) -> CommandeSortie:
    if code not in CODES_COMMANDE:
        raise Conflit("Commande inconnue.")
    tache = _obtenir_tache_orm(db, tache_id)
    if tache.statut is not StatutTache.EN_COURS:
        raise Conflit("L'agent ne travaille pas sur cette tâche en ce moment : commande sans effet.")
    libelles = {
        "pause": "Pause demandée par l'utilisateur.",
        "reprise": "Reprise demandée par l'utilisateur.",
        "arret": "Arrêt demandé par l'utilisateur.",
        "premier_plan": "Fenêtre demandée au premier plan par l'utilisateur.",
    }
    evenement = _ajouter(
        db, tache=tache, type_=TypeEvenementAgent.COMMANDE, auteur=AuteurEvenement.HUMAIN,
        texte=libelles[code], cle=cle, code=code,
    )
    audit.journaliser(
        db, "agent.commande_humaine", ResultatAudit.SUCCES, acteur_id=acteur_id,
        ressource_type="tache", ressource_id=tache.id, details={"commande": code},
    )
    db.commit()
    return CommandeSortie(etat=etat_agent(db, tache_id), evenement=_sortie(evenement, cle))  # type: ignore[arg-type]


def verifier_tache_visible(db: Session, tache_id: uuid.UUID) -> None:
    """Lève `NonTrouve` si la tâche n'existe pas dans le bureau courant (isolation)."""
    if db.scalar(select(TacheDossier.id).where(TacheDossier.id == tache_id)) is None:
        raise NonTrouve("Tâche introuvable.")
