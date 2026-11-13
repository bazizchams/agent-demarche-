"""Envoi par courriel des rappels d'échéance des démarches en cours.

Pour chaque démarche ayant au moins une tâche ouverte dans le bureau, `calculer_echeances`
indique les seuils de rappel dus (`rappels_dus`). Le service envoie UN courriel par échéance
aux membres du bureau qui gèrent les dossiers (administrateurs et employés actifs dont
l'adresse est vérifiée).

Garanties :
- idempotence : chaque (démarche, échéance, seuil, date d'échéance) n'est notifié qu'une fois
  (table `rappels_echeances_envoyes`, contrainte d'unicité, réservation avant envoi) ;
- un échec d'envoi (SMTP absent ou en panne) n'enregistre rien et ne lève pas : le rappel
  repartira à la prochaine exécution ;
- multi-bureaux : tout passe par une session liée à UN bureau (filtre tenant) ;
- règle 5 : le courriel, l'audit et les journaux ne portent que le libellé de l'échéance,
  la date, les jours restants et le lien de la plateforme (jamais de candidat ni d'adresse) ;
- règle 4 : une échéance relative dont la date de référence manque n'est pas calculée.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, replace
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Environnement, Parametres
from app.core.erreurs import NonTrouve
from app.db.base import maintenant_utc
from app.db.tenant import definir_tenant, sans_filtre_tenant
from app.modeles.bureau import Bureau
from app.modeles.journal_audit import ResultatAudit
from app.modeles.rappel_echeance import RappelEcheanceEnvoye
from app.modeles.tache import TacheDossier
from app.modeles.utilisateur import Role, Utilisateur
from app.services import audit, courriels, demarches_bureau
from app.services.echeances_demarche import calculer_echeances
from app.services.taches import STATUTS_TACHE_OUVERTE

journal = logging.getLogger("app.rappels_echeances")

ROLES_DESTINATAIRES = (Role.ADMINISTRATEUR, Role.EMPLOYE)


@dataclass(frozen=True)
class ResumeRappels:
    """Compteurs seulement (aucune donnée personnelle)."""

    demarches_examinees: int = 0
    echeances_notifiees: int = 0
    courriels_envoyes: int = 0
    deja_envoyes: int = 0
    sans_destinataire: int = 0
    echecs: int = 0

    def __add__(self, autre: "ResumeRappels") -> "ResumeRappels":
        return ResumeRappels(
            *(getattr(self, f) + getattr(autre, f) for f in self.__dataclass_fields__)
        )

    def en_texte(self) -> str:
        return " ".join(f"{f}={getattr(self, f)}" for f in self.__dataclass_fields__)


def _adresses_destinataires(db: Session) -> list[str]:
    lignes = db.scalars(
        select(Utilisateur)
        .where(
            Utilisateur.actif.is_(True),
            Utilisateur.email_verifie_le.is_not(None),
            Utilisateur.role.in_(ROLES_DESTINATAIRES),
        )
        .order_by(Utilisateur.email)
    )
    return [u.email for u in lignes]


def _codes_demarches_en_cours(db: Session) -> list[str]:
    return list(
        db.scalars(
            select(TacheDossier.code_demarche)
            .where(TacheDossier.statut.in_(STATUTS_TACHE_OUVERTE))
            .distinct()
            .order_by(TacheDossier.code_demarche)
        )
    )


def _seuils_deja_envoyes(
    db: Session, code_demarche: str, code_echeance: str, date_echeance: date
) -> set[int]:
    return set(
        db.scalars(
            select(RappelEcheanceEnvoye.seuil_jours).where(
                RappelEcheanceEnvoye.code_demarche == code_demarche,
                RappelEcheanceEnvoye.code_echeance == code_echeance,
                RappelEcheanceEnvoye.date_echeance == date_echeance,
            )
        )
    )


def _reserver(db: Session, code_demarche: str, echeance: dict, seuils: list[int]) -> bool:
    """Inscrit les seuils avant l'envoi (transaction ouverte, non validée). Faux si une autre
    exécution concurrente les a déjà inscrits (contrainte d'unicité) : la transaction est
    alors annulée et rien n'est envoyé."""
    for seuil in seuils:
        db.add(
            RappelEcheanceEnvoye(
                code_demarche=code_demarche,
                code_echeance=echeance["code"],
                seuil_jours=seuil,
                date_echeance=echeance["date"],
                envoye_le=maintenant_utc(),
            )
        )
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return False
    return True


def _transport_utilisable(parametres: Parametres) -> bool:
    """En production, le transport « mémoire » (SMTP non configuré) n'envoie rien : le rappel
    ne doit pas être compté comme envoyé."""
    return (
        parametres.environnement is not Environnement.PRODUCTION
        or parametres.transport_courriel_effectif == "smtp"
    )


def _envoyer_a_tous(
    adresses: list[str], echeance: dict, lien: str | None, parametres: Parametres
) -> int:
    """Nombre de destinataires dont le transport a accepté le courriel (ne lève jamais)."""
    if not _transport_utilisable(parametres):
        journal.warning("Rappels non envoyés : SMTP non configuré en production.")
        return 0
    acceptes = 0
    for adresse in adresses:
        courriel = courriels.gabarit_rappel_echeance(
            adresse,
            echeance["libelle"],
            echeance["date"].isoformat(),
            echeance["jours_restants"],
            lien,
        )
        try:
            if courriels.envoyer_courriel(courriel, parametres):
                acceptes += 1
        except Exception as exc:  # noqa: BLE001 - jamais le message : il peut citer l'adresse
            journal.error("Échec d'envoi d'un rappel (erreur=%s).", type(exc).__name__)
    return acceptes


def _traiter_echeance(
    db: Session,
    parametres: Parametres,
    code_demarche: str,
    echeance: dict,
    adresses: list[str],
    lien: str | None,
) -> ResumeRappels:
    dus = echeance["rappels_dus"]
    deja = _seuils_deja_envoyes(db, code_demarche, echeance["code"], echeance["date"])
    a_envoyer = [s for s in dus if s not in deja]
    if not a_envoyer:
        return ResumeRappels(deja_envoyes=1)
    if not adresses:
        return ResumeRappels(sans_destinataire=1)

    if not _reserver(db, code_demarche, echeance, a_envoyer):
        return ResumeRappels(deja_envoyes=1)

    acceptes = _envoyer_a_tous(adresses, echeance, lien, parametres)
    details = {
        "code_demarche": code_demarche,
        "code_echeance": echeance["code"],
        "seuils": ",".join(str(s) for s in a_envoyer),
        "destinataires": acceptes,
    }
    if acceptes == 0:
        db.rollback()  # rien n'est marqué : nouvel essai à la prochaine exécution
        audit.journaliser(
            db, "rappel_echeance.echec", ResultatAudit.ECHEC,
            ressource_type="demarche", details=details,
        )
        db.commit()
        return ResumeRappels(echecs=1)
    audit.journaliser(
        db, "rappel_echeance.envoi", ResultatAudit.SUCCES,
        ressource_type="demarche", details=details,
    )
    db.commit()
    return ResumeRappels(echeances_notifiees=1, courriels_envoyes=acceptes)


def envoyer_rappels_bureau(
    db: Session,
    parametres: Parametres,
    *,
    aujourd_hui: date | None = None,
    date_rentree: date | None = None,
) -> ResumeRappels:
    """Envoie les rappels dus du bureau de la session (`definir_tenant` obligatoire)."""
    jour = aujourd_hui or maintenant_utc().date()
    adresses = _adresses_destinataires(db)
    lien = courriels.url_base(parametres) or None
    total = ResumeRappels()
    for code in _codes_demarches_en_cours(db):
        try:
            definition, _meta = demarches_bureau.obtenir(db, parametres.dossier_demarches, code)
        except NonTrouve:
            continue  # démarche désactivée ou retirée : plus de rappel
        total = replace(total, demarches_examinees=total.demarches_examinees + 1)
        for echeance in calculer_echeances(definition, aujourd_hui=jour, date_rentree=date_rentree):
            if echeance["rappels_dus"]:
                total += _traiter_echeance(db, parametres, code, echeance, adresses, lien)
    return total


def envoyer_rappels_tous_bureaux(
    fabrique: sessionmaker[Session],
    parametres: Parametres,
    *,
    slug: str | None = None,
    aujourd_hui: date | None = None,
    date_rentree: date | None = None,
) -> list[ResumeRappels]:
    """Une session et un filtre tenant par bureau actif (un seul bureau si `slug`)."""
    with fabrique() as db, sans_filtre_tenant(db):
        requete = select(Bureau.id).where(Bureau.actif.is_(True))
        if slug:
            requete = requete.where(Bureau.slug == slug)
        identifiants: list[uuid.UUID] = list(db.scalars(requete.order_by(Bureau.cree_le)))
    resumes: list[ResumeRappels] = []
    for bureau_id in identifiants:
        with fabrique() as db:
            definir_tenant(db, bureau_id)
            resumes.append(
                envoyer_rappels_bureau(
                    db, parametres, aujourd_hui=aujourd_hui, date_rentree=date_rentree
                )
            )
    return resumes
