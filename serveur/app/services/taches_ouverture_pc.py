"""Tâches « Ouvrir sur mon PC » : création et reprise (sans étapes YAML ni prérequis de démarche).

Ces tâches sont exécutées dans la fenêtre VISIBLE de l'Agent Local sur le PC du bureau. Elles suivent la
machine à états commune (`en_attente -> en_cours -> suspendue | a_valider | en_erreur`) et ne peuvent
jamais atteindre `terminee` sans validation humaine (Règle 1).

Règle 4 : aucune tâche « vœux » n'est créée sans au moins un vœu au statut VALIDÉ (rien n'est inventé).
Règle 3 : aucun identifiant de portail ne transite par ces tâches.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.erreurs import Conflit, DonneesInvalides
from app.db.base import maintenant_utc
from app.db.tenant import tenant_courant
from app.modeles.journal_audit import ResultatAudit
from app.modeles.tache import (
    ACTION_AJOUTER_VOEUX_PANIER,
    ACTION_CONNEXION_PORTAIL,
    ACTION_CREATION_COMPTE_EEF,
    ACTIONS_OUVERTURE_PC,
    StatutTache,
    TacheDossier,
)
from app.modeles.voeu_formation import StatutVoeu
from app.schemas.tache import TacheCreation, TacheSortie
from app.services import audit
from app.services import voeux as service_voeux
from app.services.candidats import obtenir_candidat
from app.services.taches import (
    STATUTS_TACHE_OUVERTE,
    _serialiser_tache,
    _verifier_transition,
)

CODE_DEMARCHE_CAMPUS_FRANCE = "campus_france"
CODE_DEMARCHE_COMPTE_EEF = "compte_etudes_en_france"
PORTAIL_EEF = "etudes_en_france"
PORTAIL_IRCC = "ircc"
MESSAGE_AUCUN_VOEU_VALIDE = (
    "Aucun vœu validé pour ce candidat : rédigez puis validez au moins un vœu "
    "(onglet Campus France, « Vœux et lettres de motivation »)."
)


def nombre_voeux_valides(db: Session, candidat_id: uuid.UUID, cle_maitresse: bytes) -> int:
    return sum(
        1
        for v in service_voeux.lister_voeux(db, candidat_id, cle_maitresse)
        if v["statut"] == StatutVoeu.VALIDE
    )


def _portail_de_la_demande(donnees: TacheCreation) -> str | None:
    """Valide la démarche et le portail selon l'action ; renvoie le portail visé (nul pour les vœux)."""
    if donnees.action == ACTION_AJOUTER_VOEUX_PANIER:
        if donnees.code_demarche != CODE_DEMARCHE_CAMPUS_FRANCE:
            raise DonneesInvalides(
                "L'action « ajouter_voeux_panier » concerne uniquement la démarche Campus France."
            )
        return None
    if donnees.action == ACTION_CREATION_COMPTE_EEF:
        if donnees.code_demarche not in (CODE_DEMARCHE_COMPTE_EEF, CODE_DEMARCHE_CAMPUS_FRANCE):
            raise DonneesInvalides(
                "La création de compte Études en France concerne les démarches Campus France et "
                "« compte_etudes_en_france »."
            )
        return PORTAIL_EEF
    if donnees.action == ACTION_CONNEXION_PORTAIL:
        deduit = (
            PORTAIL_IRCC
            if donnees.code_demarche.startswith("ircc")
            else PORTAIL_EEF
            if donnees.code_demarche in (CODE_DEMARCHE_COMPTE_EEF, CODE_DEMARCHE_CAMPUS_FRANCE)
            else None
        )
        portail = donnees.portail or deduit
        if portail not in (PORTAIL_EEF, PORTAIL_IRCC):
            raise DonneesInvalides("Portail à préciser : etudes_en_france ou ircc.")
        if deduit is not None and portail != deduit:
            raise DonneesInvalides("Ce portail ne correspond pas à la démarche choisie.")
        return portail
    raise DonneesInvalides("Action inconnue pour « Ouvrir sur mon PC ».")


def creer_tache_ouverture_pc(
    db: Session,
    *,
    donnees: TacheCreation,
    acteur_id: uuid.UUID,
    cle_maitresse: bytes,
) -> TacheSortie:
    tid = tenant_courant(db)
    if tid is None:
        raise RuntimeError("Contexte bureau (tenant) manquant sur la session.")
    if donnees.action not in ACTIONS_OUVERTURE_PC:
        raise DonneesInvalides("Action inconnue pour « Ouvrir sur mon PC ».")
    portail = _portail_de_la_demande(donnees)

    candidat = obtenir_candidat(db, candidat_id=donnees.candidat_id, cle_maitresse=cle_maitresse)
    if donnees.action == ACTION_AJOUTER_VOEUX_PANIER and (
        nombre_voeux_valides(db, candidat.id, cle_maitresse) == 0
    ):
        raise DonneesInvalides(MESSAGE_AUCUN_VOEU_VALIDE)

    deja_ouverte = db.scalar(
        select(TacheDossier.id).where(
            TacheDossier.candidat_id == candidat.id,
            TacheDossier.action == donnees.action,
            TacheDossier.statut.in_(STATUTS_TACHE_OUVERTE),
            *([TacheDossier.portail == portail] if portail else []),
        )
    )
    if deja_ouverte is not None:
        raise Conflit(
            "Une ouverture sur le PC est déjà en attente, en cours ou à valider pour ce candidat."
        )

    tache = TacheDossier(
        id=uuid.uuid4(),
        tenant_id=tid,
        candidat_id=candidat.id,
        code_demarche=donnees.code_demarche,
        action=donnees.action,
        portail=portail,
        statut=StatutTache.EN_ATTENTE,
        creee_par_id=acteur_id,
    )
    db.add(tache)
    db.flush()
    audit.journaliser(
        db,
        "tache.creation_ouverture_pc",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="tache",
        ressource_id=tache.id,
        details={
            "action": donnees.action,
            "code_demarche": donnees.code_demarche,
            **({"portail": portail} if portail else {}),
        },
    )
    db.commit()
    db.refresh(tache)
    return _serialiser_tache(db, tache, cle_maitresse)


def reprendre_tache_ouverture_pc(
    db: Session,
    *,
    tache: TacheDossier,
    acteur_id: uuid.UUID,
    cle_maitresse: bytes,
) -> TacheSortie:
    """Remet une tâche suspendue (CAPTCHA/2FA résolu par l'humain dans la fenêtre) ou en erreur en attente."""
    _verifier_transition(tache.statut, StatutTache.EN_ATTENTE)
    if tache.action == ACTION_AJOUTER_VOEUX_PANIER and nombre_voeux_valides(
        db, tache.candidat_id, cle_maitresse
    ) == 0:
        raise Conflit(MESSAGE_AUCUN_VOEU_VALIDE)

    tache.statut = StatutTache.EN_ATTENTE
    tache.motif_suspension = None
    tache.message_alerte = None
    tache.champs_manquants_json = None
    tache.pieces_manquantes_json = None
    tache.agent_local_id = None
    tache.suspendue_le = None
    audit.journaliser(
        db,
        "tache.reprise",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="tache",
        ressource_id=tache.id,
        details={"action": tache.action, "reprise_le": maintenant_utc().isoformat()},
    )
    db.commit()
    return _serialiser_tache(db, tache, cle_maitresse)
