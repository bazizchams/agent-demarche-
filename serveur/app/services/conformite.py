"""Service de conformité légale (Loi algérienne n° 18-07 et RGPD — Phase 6) :
- Recueil probant et révocation du consentement explicite des candidats (`PreuveConsentementCandidat`)
- Droit à l'effacement : suppression définitive d'un dossier candidat et destruction de tous ses
  fichiers chiffrés sur disque (documents + captures d'écran de contrôle) sans trace de PII dans les logs (Règle 5)
- Politique de conservation automatisée : purge définitive des dossiers archivés ayant dépassé
  `duree_conservation_jours` configuré par le bureau
"""

from __future__ import annotations

import hashlib
import shutil
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Parametres
from app.core.erreurs import DonneesInvalides, NonTrouve
from app.db.base import maintenant_utc
from app.db.tenant import tenant_courant
from app.modeles.abonnement import AbonnementBureau, PreuveConsentementCandidat
from app.modeles.candidat import Candidat, StatutCandidat
from app.modeles.document import DocumentCandidat
from app.modeles.journal_audit import ResultatAudit
from app.modeles.tache import MotifSuspensionTache, StatutTache, TacheDossier
from app.schemas.abonnement_conformite import (
    ConsentementCandidatEntree,
    PreuveConsentementSortie,
    ResultatPurgeConservationSortie,
)
from app.services import audit
from app.services.documents import _resoudre_chemin_stockage

TEXTE_CONSENTEMENT_LOI_18_07 = """FORMULAIRE DE CONSENTEMENT EXPLICITE DU CANDIDAT (LOI ALGÉRIENNE N° 18-07)

Je soussigné(e), candidat(e) accompagné(e) par le bureau d'études, autorise expressément le traitement
et le stockage chiffré (AES-256-GCM) de mes données personnelles et de mes pièces justificatives aux seules
fins de la constitution et du pré-remplissage supervisé de mon dossier d'études (Campus France / Études en
France ou IRCC Canada).

Je suis informé(e) :
1. qu'aucune demande officielle n'est jamais transmise sans vérification et validation humaine finale ;
2. qu'aucun mot de passe de mes comptes personnels n'est conservé par le logiciel ;
3. que je dispose à tout moment d'un droit d'accès, de rectification, de retrait de consentement et de
   suppression définitive de l'intégralité de mes données et documents."""


def _exiger_tenant(db: Session) -> uuid.UUID:
    tid = tenant_courant(db)
    if tid is None:
        raise RuntimeError("Contexte bureau (tenant) manquant sur la session.")
    return tid


def _obtenir_candidat_orm(db: Session, candidat_id: uuid.UUID) -> Candidat:
    c = db.scalar(select(Candidat).where(Candidat.id == candidat_id))
    if c is None:
        raise NonTrouve("Candidat introuvable.")
    return c


def enregistrer_consentement_candidat(
    db: Session,
    *,
    candidat_id: uuid.UUID,
    donnees: ConsentementCandidatEntree,
    acteur_id: uuid.UUID,
    parametres: Parametres,
) -> PreuveConsentementSortie:
    tid = _exiger_tenant(db)
    if not donnees.consentement_explicite:
        raise DonneesInvalides(
            "Le consentement explicite du candidat (consentement_explicite=true) est obligatoire."
        )

    candidat = _obtenir_candidat_orm(db, candidat_id)
    maintenant = maintenant_utc()
    empreinte = hashlib.sha256(
        TEXTE_CONSENTEMENT_LOI_18_07.encode("utf-8")
    ).hexdigest()

    preuve = PreuveConsentementCandidat(
        id=uuid.uuid4(),
        tenant_id=tid,
        candidat_id=candidat.id,
        version_texte_consentement=parametres.version_consentement_loi_18_07,
        mode_recueil=donnees.mode_recueil,
        empreinte_texte_sha256=empreinte,
        recueilli_par_id=acteur_id,
        recueilli_le=maintenant,
    )
    db.add(preuve)

    candidat.consentement_signe = True
    candidat.date_consentement = maintenant
    db.flush()

    audit.journaliser(
        db,
        "conformite.recueil_consentement_candidat",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="candidat",
        ressource_id=candidat.id,
        details={
            "preuve_id": str(preuve.id),
            "version": parametres.version_consentement_loi_18_07,
            "mode_recueil": donnees.mode_recueil,
        },
    )
    db.commit()
    return PreuveConsentementSortie.model_validate(preuve)


def revoquer_consentement_candidat(
    db: Session,
    *,
    candidat_id: uuid.UUID,
    acteur_id: uuid.UUID,
) -> PreuveConsentementSortie:
    """Révoque le consentement du candidat et suspend immédiatement toute tâche ouverte sur son dossier."""
    _exiger_tenant(db)
    candidat = _obtenir_candidat_orm(db, candidat_id)
    maintenant = maintenant_utc()

    derniere_preuve = db.scalar(
        select(PreuveConsentementCandidat)
        .where(
            PreuveConsentementCandidat.candidat_id == candidat.id,
            PreuveConsentementCandidat.revoque_le.is_(None),
        )
        .order_by(PreuveConsentementCandidat.recueilli_le.desc())
    )
    if derniere_preuve is None:
        raise NonTrouve("Aucun consentement actif trouvé pour ce candidat.")

    derniere_preuve.revoque_le = maintenant
    candidat.consentement_signe = False

    # Suspend immédiatement toute tâche en attente ou en cours pour ce candidat
    taches_actives = db.scalars(
        select(TacheDossier).where(
            TacheDossier.candidat_id == candidat.id,
            TacheDossier.statut.in_({StatutTache.EN_ATTENTE, StatutTache.EN_COURS}),
        )
    ).all()
    for t in taches_actives:
        t.statut = StatutTache.SUSPENDUE
        t.motif_suspension = MotifSuspensionTache.DONNEE_MANQUANTE
        t.message_alerte = "Consentement candidat révoqué (Loi 18-07) : traitement suspendu."
        t.suspendue_le = maintenant

    audit.journaliser(
        db,
        "conformite.revocation_consentement_candidat",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="candidat",
        ressource_id=candidat.id,
        details={"preuve_id": str(derniere_preuve.id)},
    )
    db.commit()
    return PreuveConsentementSortie.model_validate(derniere_preuve)


def lister_preuves_consentement_candidat(
    db: Session, *, candidat_id: uuid.UUID
) -> list[PreuveConsentementSortie]:
    _exiger_tenant(db)
    _obtenir_candidat_orm(db, candidat_id)
    lignes = db.scalars(
        select(PreuveConsentementCandidat)
        .where(PreuveConsentementCandidat.candidat_id == candidat_id)
        .order_by(PreuveConsentementCandidat.recueilli_le.desc())
    ).all()
    return [PreuveConsentementSortie.model_validate(p) for p in lignes]


def _detruire_fichiers_chiffres_candidat(
    db: Session,
    *,
    candidat: Candidat,
    parametres: Parametres,
) -> int:
    """Supprime physiquement du disque tous les fichiers chiffrés AES-256-GCM rattachés au candidat."""
    nb_supprimes = 0
    docs = db.scalars(
        select(DocumentCandidat).where(DocumentCandidat.candidat_id == candidat.id)
    ).all()
    for d in docs:
        chemin = _resoudre_chemin_stockage(
            parametres.dossier_stockage, d.chemin_stockage_relatif
        )
        if chemin.exists():
            chemin.unlink()
            nb_supprimes += 1

    taches = db.scalars(
        select(TacheDossier).where(TacheDossier.candidat_id == candidat.id)
    ).all()
    for t in taches:
        if t.chemin_capture_controle_relatif:
            chemin_cap = _resoudre_chemin_stockage(
                parametres.dossier_stockage, t.chemin_capture_controle_relatif
            )
            if chemin_cap.exists():
                chemin_cap.unlink()
                nb_supprimes += 1

    dossier_candidat = (
        parametres.dossier_stockage / str(candidat.tenant_id) / str(candidat.id)
    )
    if dossier_candidat.exists():
        shutil.rmtree(dossier_candidat, ignore_errors=True)

    return nb_supprimes


def supprimer_definitivement_dossier_candidat(
    db: Session,
    *,
    candidat_id: uuid.UUID,
    acteur_id: uuid.UUID,
    parametres: Parametres,
) -> dict[str, int | str]:
    """Droit à l'oubli / suppression définitive : détruit tous les fichiers chiffrés sur disque,
    supprime la fiche candidat et ses tables liées en cascade, et trace uniquement l'UUID opaque
    dans `journal_audit` (Règle 5 : zéro PII)."""
    _exiger_tenant(db)
    candidat = _obtenir_candidat_orm(db, candidat_id)
    cid = candidat.id

    nb_fichiers = _detruire_fichiers_chiffres_candidat(
        db, candidat=candidat, parametres=parametres
    )
    db.delete(candidat)
    db.flush()

    audit.journaliser(
        db,
        "conformite.suppression_definitive_candidat",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="candidat",
        ressource_id=cid,
        details={"nb_fichiers_chiffres_supprimes": nb_fichiers},
    )
    db.commit()
    return {
        "candidat_id": str(cid),
        "nb_fichiers_chiffres_supprimes": nb_fichiers,
    }


def purger_dossiers_archives_expires(
    db: Session,
    *,
    acteur_id: uuid.UUID,
    parametres: Parametres,
) -> ResultatPurgeConservationSortie:
    """Applique la politique de conservation des données du bureau : tous les dossiers à l'état
    `archive` dont `archive_le` est antérieur à `maintenant - duree_conservation_jours` sont
    définitivement purgés (base + fichiers chiffrés)."""
    tid = _exiger_tenant(db)
    abo = db.scalar(select(AbonnementBureau).where(AbonnementBureau.tenant_id == tid))
    duree_jours = abo.duree_conservation_jours if abo is not None else 365
    date_limite = maintenant_utc() - timedelta(days=duree_jours)

    expirables = db.scalars(
        select(Candidat).where(
            Candidat.statut == StatutCandidat.ARCHIVE,
            Candidat.archive_le.is_not(None),
            Candidat.archive_le <= date_limite,
        )
    ).all()

    nb_dossiers = 0
    nb_fichiers = 0
    for c in expirables:
        nb_fichiers += _detruire_fichiers_chiffres_candidat(
            db, candidat=c, parametres=parametres
        )
        db.delete(c)
        nb_dossiers += 1

    db.flush()
    audit.journaliser(
        db,
        "conformite.purge_automatique_conservation",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="bureau",
        ressource_id=tid,
        details={
            "duree_conservation_jours": duree_jours,
            "nb_dossiers_purges": nb_dossiers,
            "nb_fichiers_chiffres_supprimes": nb_fichiers,
        },
    )
    db.commit()
    return ResultatPurgeConservationSortie(
        nb_dossiers_purges=nb_dossiers,
        nb_fichiers_chiffres_supprimes=nb_fichiers,
        duree_conservation_jours=duree_jours,
    )
