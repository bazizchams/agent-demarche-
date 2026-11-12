"""Contrôle d'accès lié à l'abonnement du bureau.

Principe : un bureau dont l'essai est terminé, dont le paiement a échoué au-delà du délai de
grâce, ou dont l'abonnement est résilié passe en LECTURE SEULE. Il n'est jamais verrouillé :
- il peut toujours se connecter, consulter, télécharger et exporter ses données (il reste
  responsable de traitement vis-à-vis de ses candidats, loi 18-07 / RGPD) ;
- il peut toujours payer (abonnement, CGU) pour retrouver l'accès complet ;
- les droits des candidats restent exerçables (retrait du consentement, suppression définitive).
Seules les autres écritures sont refusées (402).

`Bureau.actif` reste un interrupteur manuel de l'exploitant (blocage total), indépendant d'ici.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Parametres
from app.core.erreurs import NonTrouve, PaiementRequis
from app.db.base import maintenant_utc
from app.db.tenant import definir_tenant, sans_filtre_tenant, tenant_courant
from app.modeles.abonnement import AbonnementBureau, ForfaitAbonnement
from app.modeles.bureau import Bureau
from app.modeles.journal_audit import ResultatAudit

STATUT_ESSAI = "trialing"
STATUT_ACTIF = "active"
STATUT_IMPAYE = "past_due"
STATUT_RESILIE = "canceled"
STATUT_OFFERT = "offert"  # accordé par l'exploitant de la plateforme (hors Stripe)

METHODES_ECRITURE = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Écritures qui restent possibles en lecture seule (voir l'en-tête du module).
_CHEMINS_TOUJOURS_AUTORISES = tuple(
    re.compile(motif)
    for motif in (
        r"^/api/v1/auth/",
        r"^/api/v1/abonnement(/|$)",
        r"^/api/v1/candidats/[^/]+/consentement/revoquer$",
        r"^/api/v1/candidats/[^/]+/suppression-definitive$",
        r"^/api/v1/conformite/purger-archives-expirees$",
        r"^/api/v1/sauvegardes$",
    )
)

_SUITE_LECTURE_SEULE = (
    " Votre bureau est en lecture seule : vos dossiers restent consultables et exportables. "
    "Souscrivez ou régularisez votre forfait (Paramètres, Abonnement) pour reprendre."
)


@dataclass(frozen=True)
class AccesAbonnement:
    acces_complet: bool
    motif: str  # essai | actif | offert | grace_impaye | essai_termine | impaye | resilie | offre_terminee | statut_inconnu
    statut: str
    fin: datetime | None
    jours_restants: int | None
    message: str


def _en_utc(valeur: datetime | None) -> datetime | None:
    """`periode_courante_fin` est relue sans fuseau par SQLite (colonne DateTime simple) :
    elle est toujours enregistrée en UTC, on lui rend donc son fuseau avant de comparer."""
    if valeur is not None and valeur.tzinfo is None:
        return valeur.replace(tzinfo=timezone.utc)
    return valeur


def _jours_restants(fin: datetime | None, maintenant: datetime) -> int | None:
    if fin is None:
        return None
    return max(0, math.ceil((fin - maintenant).total_seconds() / 86400))


def evaluer_acces(
    db: Session, parametres: Parametres, *, maintenant: datetime | None = None
) -> AccesAbonnement:
    """État d'accès du bureau courant. Lecture pure : n'écrit jamais en base."""
    tid = tenant_courant(db)
    if tid is None:
        raise RuntimeError("Contexte bureau (tenant) manquant sur la session.")
    maintenant = maintenant or maintenant_utc()
    essai = timedelta(days=parametres.duree_essai_jours)

    abo = db.scalar(select(AbonnementBureau))
    if abo is None:
        # Aucun abonnement enregistré : l'essai court depuis la création du bureau.
        bureau = db.get(Bureau, tid)
        statut = STATUT_ESSAI
        debut = (_en_utc(bureau.cree_le) if bureau else None) or maintenant
        fin: datetime | None = debut + essai
        modifie_le = maintenant
    else:
        statut = abo.statut_stripe
        fin = _en_utc(abo.periode_courante_fin)
        modifie_le = _en_utc(abo.modifie_le) or maintenant
        if statut == STATUT_ESSAI and fin is None:
            fin = (_en_utc(abo.cree_le) or maintenant) + essai

    def _etat(complet: bool, motif: str, message: str, fin_affichee: datetime | None) -> AccesAbonnement:
        return AccesAbonnement(
            acces_complet=complet,
            motif=motif,
            statut=statut,
            fin=fin_affichee,
            jours_restants=_jours_restants(fin_affichee, maintenant),
            message=message,
        )

    if statut == STATUT_ACTIF:
        return _etat(True, "actif", "Abonnement actif.", fin)

    if statut == STATUT_OFFERT:
        if fin is None or maintenant <= fin:
            return _etat(True, "offert", "Abonnement offert par la plateforme.", fin)
        return _etat(
            False, "offre_terminee", "Votre accès offert est terminé." + _SUITE_LECTURE_SEULE, fin
        )

    if statut == STATUT_ESSAI:
        if fin is not None and maintenant <= fin:
            return _etat(True, "essai", "Période d'essai en cours.", fin)
        return _etat(
            False, "essai_termine", "Votre période d'essai est terminée." + _SUITE_LECTURE_SEULE, fin
        )

    if statut == STATUT_IMPAYE:
        limite = modifie_le + timedelta(days=parametres.jours_grace_impaye)
        if maintenant <= limite:
            return _etat(
                True,
                "grace_impaye",
                "Le dernier paiement a échoué : régularisez-le avant la fin du délai de grâce.",
                limite,
            )
        return _etat(
            False, "impaye", "Le paiement de votre abonnement a échoué." + _SUITE_LECTURE_SEULE, limite
        )

    if statut == STATUT_RESILIE:
        return _etat(False, "resilie", "Votre abonnement est résilié." + _SUITE_LECTURE_SEULE, fin)

    return _etat(
        False,
        "statut_inconnu",
        "L'état de votre abonnement n'a pas pu être déterminé : contactez le support."
        + _SUITE_LECTURE_SEULE,
        fin,
    )


def chemin_toujours_autorise(chemin: str) -> bool:
    return any(motif.search(chemin) for motif in _CHEMINS_TOUJOURS_AUTORISES)


def exiger_ecriture_autorisee(
    *, methode: str, chemin: str, db: Session, parametres: Parametres
) -> None:
    """À appeler une fois le bureau fixé sur la session. Refuse (402) une écriture quand
    le bureau est en lecture seule. Sans effet si le contrôle est désactivé."""
    if not parametres.blocage_abonnement_actif:
        return
    if methode.upper() not in METHODES_ECRITURE:
        return
    if chemin_toujours_autorise(chemin):
        return
    acces = evaluer_acces(db, parametres)
    if not acces.acces_complet:
        raise PaiementRequis(acces.message)


def offrir_abonnement(
    db: Session,
    *,
    slug: str,
    forfait: ForfaitAbonnement,
    jours: int | None,
) -> AbonnementBureau:
    """Accorde à un bureau un accès complet hors paiement (réservé à l'exploitant, via la CLI).
    `jours=None` : sans date de fin."""
    from app.services import abonnements as service_abonnements
    from app.services import audit

    with sans_filtre_tenant(db):
        bureau = db.scalar(select(Bureau).where(Bureau.slug == slug.strip().lower()))
    if bureau is None:
        raise NonTrouve("Bureau introuvable.")
    definir_tenant(db, bureau.id)
    abo = service_abonnements._obtenir_ou_creer_abonnement_orm(db)
    _libelle, prix, quota = service_abonnements.CATALOGUE_FORFAITS[forfait]
    abo.forfait = forfait
    abo.prix_mensuel_eur = prix
    abo.quota_dossiers_mensuels = quota
    abo.statut_stripe = STATUT_OFFERT
    abo.periode_courante_fin = (
        maintenant_utc() + timedelta(days=jours) if jours is not None else None
    )
    audit.journaliser(
        db,
        "abonnement.offert_par_plateforme",
        ResultatAudit.SUCCES,
        ressource_type="abonnement",
        ressource_id=abo.id,
        details={"forfait": forfait.value, "jours": jours if jours is not None else "illimite"},
    )
    db.commit()
    return abo
