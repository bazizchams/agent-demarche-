"""Service de sauvegardes chiffrées (AES-256-GCM) et de vérification d'intégrité par bureau (Phase 6).

Chaque archive de sauvegarde contient les fiches candidats et métadonnées de documents du bureau,
sérialisées puis chiffrées en AES-256-GCM avec des données authentifiées (AAD) liées au `tenant_id`
du bureau (un autre bureau ne peut jamais déchiffrer l'archive).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.chiffrement import (
    ErreurChiffrement,
    chiffrer_octets,
    dechiffrer_octets,
)
from app.core.config import Parametres
from app.core.erreurs import DonneesInvalides, NonTrouve
from app.db.base import maintenant_utc
from app.db.tenant import tenant_courant
from app.modeles.candidat import Candidat
from app.modeles.document import DocumentCandidat
from app.modeles.journal_audit import ResultatAudit
from app.schemas.abonnement_conformite import (
    SauvegardeChiffreeSortie,
    VerificationSauvegardeSortie,
)
from app.services import audit


def _exiger_tenant(db: Session) -> uuid.UUID:
    tid = tenant_courant(db)
    if tid is None:
        raise RuntimeError("Contexte bureau (tenant) manquant sur la session.")
    return tid


def _dossier_sauvegardes_bureau(parametres: Parametres, tid: uuid.UUID) -> Path:
    dossier = (parametres.dossier_sauvegardes / str(tid)).resolve()
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier


def creer_sauvegarde_chiffree_bureau(
    db: Session,
    *,
    acteur_id: uuid.UUID,
    parametres: Parametres,
    cle_maitresse: bytes,
) -> SauvegardeChiffreeSortie:
    """Crée une archive de sauvegarde chiffrée (AES-256-GCM) pour le bureau courant."""
    tid = _exiger_tenant(db)
    maintenant = maintenant_utc()

    candidats = db.scalars(select(Candidat).order_by(Candidat.cree_le.asc())).all()
    documents = db.scalars(
        select(DocumentCandidat).order_by(DocumentCandidat.cree_le.asc())
    ).all()

    manifeste = {
        "version_format": 1,
        "tenant_id": str(tid),
        "cree_le": maintenant.isoformat(),
        "nb_candidats": len(candidats),
        "nb_documents": len(documents),
        "candidats": [
            {
                "id": str(c.id),
                "nom_chiffre": c.nom_chiffre,
                "prenom_chiffre": c.prenom_chiffre,
                "numero_passeport_chiffre": c.numero_passeport_chiffre,
                "statut": c.statut.value,
                "consentement_signe": c.consentement_signe,
            }
            for c in candidats
        ],
        "documents": [
            {
                "id": str(d.id),
                "candidat_id": str(d.candidat_id),
                "type_piece": d.type_piece,
                "empreinte_contenu": d.empreinte_contenu,
                "chemin_stockage_relatif": d.chemin_stockage_relatif,
                "taille_octets": d.taille_octets,
            }
            for d in documents
        ],
    }

    octets_clairs = json.dumps(manifeste, ensure_ascii=False).encode("utf-8")
    octets_chiffres = chiffrer_octets(
        cle_maitresse,
        tenant_id=tid,
        candidat_id=tid,
        document_id=tid,
        contenu_clair=octets_clairs,
    )
    empreinte_sha256 = hashlib.sha256(octets_chiffres).hexdigest()

    horodatage_nom = maintenant.strftime("%Y%m%d_%H%M%S")
    nom_fichier = f"sauvegarde_{horodatage_nom}_{ uuid.uuid4().hex[:8] }.be.enc"
    dossier = _dossier_sauvegardes_bureau(parametres, tid)
    chemin_archive = dossier / nom_fichier
    chemin_archive.write_bytes(octets_chiffres)

    audit.journaliser(
        db,
        "sauvegarde.creation_archive_chiffree",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="sauvegarde",
        details={
            "nom_fichier": nom_fichier,
            "taille_octets": len(octets_chiffres),
            "empreinte_sha256": empreinte_sha256,
            "nb_candidats": len(candidats),
            "nb_documents": len(documents),
        },
    )
    db.commit()

    return SauvegardeChiffreeSortie(
        nom_fichier=nom_fichier,
        taille_octets=len(octets_chiffres),
        empreinte_sha256=empreinte_sha256,
        nb_candidats=len(candidats),
        nb_documents=len(documents),
        cree_le=maintenant,
    )


def verifier_integrite_sauvegarde(
    db: Session,
    *,
    nom_fichier: str,
    parametres: Parametres,
    cle_maitresse: bytes,
) -> VerificationSauvegardeSortie:
    """Déchiffre et vérifie l'authenticité AES-256-GCM d'une sauvegarde du bureau."""
    tid = _exiger_tenant(db)
    if "/" in nom_fichier or "\\" in nom_fichier or ".." in nom_fichier:
        raise DonneesInvalides("Nom de fichier de sauvegarde invalide.")

    dossier = _dossier_sauvegardes_bureau(parametres, tid)
    chemin = (dossier / nom_fichier).resolve()
    if not chemin.exists() or chemin.parent != dossier:
        raise NonTrouve("Archive de sauvegarde introuvable.")

    octets_chiffres = chemin.read_bytes()
    empreinte = hashlib.sha256(octets_chiffres).hexdigest()

    try:
        octets_clairs = dechiffrer_octets(
            cle_maitresse,
            tenant_id=tid,
            candidat_id=tid,
            document_id=tid,
            contenu_chiffre=octets_chiffres,
        )
        manifeste = json.loads(octets_clairs.decode("utf-8"))
        integrite_ok = str(manifeste.get("tenant_id")) == str(tid)
        nb_cand = int(manifeste.get("nb_candidats", 0))
        nb_docs = int(manifeste.get("nb_documents", 0))
    except (ErreurChiffrement, ValueError, KeyError):
        integrite_ok = False
        nb_cand = 0
        nb_docs = 0

    return VerificationSauvegardeSortie(
        nom_fichier=nom_fichier,
        integrite_valide=integrite_ok,
        tenant_id=tid,
        nb_candidats=nb_cand,
        nb_documents=nb_docs,
        empreinte_sha256=empreinte,
    )


def lister_sauvegardes_bureau(
    db: Session,
    *,
    parametres: Parametres,
    cle_maitresse: bytes,
) -> list[SauvegardeChiffreeSortie]:
    tid = _exiger_tenant(db)
    dossier = _dossier_sauvegardes_bureau(parametres, tid)
    sortie: list[SauvegardeChiffreeSortie] = []

    for f in sorted(dossier.glob("*.be.enc"), reverse=True):
        verif = verifier_integrite_sauvegarde(
            db, nom_fichier=f.name, parametres=parametres, cle_maitresse=cle_maitresse
        )
        stat = f.stat()
        sortie.append(
            SauvegardeChiffreeSortie(
                nom_fichier=f.name,
                taille_octets=stat.st_size,
                empreinte_sha256=verif.empreinte_sha256,
                nb_candidats=verif.nb_candidats,
                nb_documents=verif.nb_documents,
                cree_le=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            )
        )
    return sortie
