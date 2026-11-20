"""Accès de l'agent local aux données d'une tâche en cours : capture de contrôle chiffrée,
contexte du dossier et pièces justificatives."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.chiffrement import chiffrer_octets, dechiffrer_octets
from app.core.config import Parametres
from app.core.erreurs import Conflit, DonneesInvalides, NonTrouve
from app.modeles.journal_audit import ResultatAudit
from app.modeles.tache import StatutTache
from app.schemas.tache import ContexteDossierExecutionSortie, TacheSortie
from app.services import audit
from app.services.candidats import obtenir_candidat
from app.services.documents import (
    _detecter_type_mime_par_signature,
    _resoudre_chemin_stockage,
    lire_document_dechiffre,
    lister_documents_candidat,
)
from app.services.taches.etat import (
    _exiger_action_avec_pieces,
    _exiger_detenteur_agent,
    _exiger_tenant,
    _obtenir_tache_orm,
    _texte_agent,
)
from app.services.taches.serialisation import _serialiser_tache


def deposer_capture_controle(
    db: Session,
    *,
    tache_id: uuid.UUID,
    contenu_clair: bytes,
    acteur_id: uuid.UUID | None,
    agent_local_id: uuid.UUID | None,
    parametres: Parametres,
    cle_maitresse: bytes,
) -> TacheSortie:
    """Enregistre de façon chiffrée (AES-256-GCM) la capture d'écran de contrôle
    prise par l'agent local juste avant le bouton d'envoi final."""
    tid = _exiger_tenant(db)
    tache = _obtenir_tache_orm(db, tache_id)
    _exiger_detenteur_agent(tache, agent_local_id)
    if tache.statut not in {StatutTache.EN_COURS, StatutTache.A_VALIDER}:
        raise Conflit(
            "La capture de contrôle ne peut être déposée que sur une tâche en cours ou en attente de validation."
        )

    if not contenu_clair:
        raise DonneesInvalides("Le fichier de capture est vide.")
    if len(contenu_clair) > parametres.taille_max_document_octets:
        raise DonneesInvalides("La capture dépasse la taille maximale autorisée.")

    type_mime = _detecter_type_mime_par_signature(contenu_clair)
    chemin_relatif = f"{tid}/captures/{tache.id}.bin"
    chemin_disque: Path = _resoudre_chemin_stockage(
        parametres.dossier_stockage, chemin_relatif
    )

    octets_chiffres = chiffrer_octets(
        cle_maitresse,
        tenant_id=tid,
        candidat_id=tache.candidat_id,
        document_id=tache.id,
        contenu_clair=contenu_clair,
    )
    chemin_disque.parent.mkdir(parents=True, exist_ok=True)
    chemin_disque.write_bytes(octets_chiffres)

    tache.chemin_capture_controle_relatif = chemin_relatif
    tache.type_mime_capture_controle = type_mime

    audit.journaliser(
        db,
        "tache.depot_capture_controle",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="tache",
        ressource_id=tache.id,
        details={
            "taille_octets": len(contenu_clair),
            "type_mime": type_mime,
            "agent_local_id": _texte_agent(agent_local_id),
        },
    )
    db.commit()
    return _serialiser_tache(db, tache, cle_maitresse)


def lire_capture_controle(
    db: Session,
    *,
    tache_id: uuid.UUID,
    parametres: Parametres,
    cle_maitresse: bytes,
) -> tuple[str, bytes]:
    tache = _obtenir_tache_orm(db, tache_id)
    if not tache.chemin_capture_controle_relatif:
        raise NonTrouve("Aucune capture de contrôle n'est associée à cette tâche.")

    chemin_disque = _resoudre_chemin_stockage(
        parametres.dossier_stockage, tache.chemin_capture_controle_relatif
    )
    if not chemin_disque.exists():
        raise NonTrouve("Fichier de capture introuvable sur le stockage.")

    clair = dechiffrer_octets(
        cle_maitresse,
        tenant_id=tache.tenant_id,
        candidat_id=tache.candidat_id,
        document_id=tache.id,
        contenu_chiffre=chemin_disque.read_bytes(),
    )
    return tache.type_mime_capture_controle or "image/png", clair


def obtenir_contexte_dossier_execution(
    db: Session,
    *,
    tache_id: uuid.UUID,
    agent_local_id: uuid.UUID | None,
    cle_maitresse: bytes,
) -> ContexteDossierExecutionSortie:
    """Retourne les données déchiffrées du candidat et la liste de ses documents
    uniquement si la tâche est actuellement `en_cours` et si l'action en a besoin."""
    _exiger_tenant(db)
    tache = _obtenir_tache_orm(db, tache_id)
    _exiger_detenteur_agent(tache, agent_local_id)
    _exiger_action_avec_pieces(tache)
    if tache.statut != StatutTache.EN_COURS:
        raise Conflit(
            "Le contexte d'exécution du dossier n'est accessible que pour une tâche à l'état 'en_cours'."
        )
    candidat = obtenir_candidat(
        db, candidat_id=tache.candidat_id, cle_maitresse=cle_maitresse
    )
    documents = lister_documents_candidat(
        db, candidat_id=tache.candidat_id, cle_maitresse=cle_maitresse
    )
    return ContexteDossierExecutionSortie(
        tache=_serialiser_tache(db, tache, cle_maitresse),
        candidat=candidat,
        documents=documents,
    )


def lire_document_pour_tache_en_cours(
    db: Session,
    *,
    tache_id: uuid.UUID,
    document_id: uuid.UUID,
    agent_local_id: uuid.UUID | None,
    parametres: Parametres,
    cle_maitresse: bytes,
) -> tuple[str, str, bytes]:
    """Permet à l'Agent Local exécutant une tâche `en_cours` de récupérer le binaire déchiffré
    d'une pièce justificative du candidat afin de la téléverser sur le portail."""
    _exiger_tenant(db)
    tache = _obtenir_tache_orm(db, tache_id)
    _exiger_detenteur_agent(tache, agent_local_id)
    _exiger_action_avec_pieces(tache)
    if tache.statut != StatutTache.EN_COURS:
        raise Conflit(
            "Le téléchargement d'une pièce par l'agent n'est autorisé que pour une tâche à l'état 'en_cours'."
        )
    meta, octets = lire_document_dechiffre(
        db,
        candidat_id=tache.candidat_id,
        document_id=document_id,
        parametres=parametres,
        cle_maitresse=cle_maitresse,
    )
    return meta.type_mime, meta.nom_fichier_origine, octets
