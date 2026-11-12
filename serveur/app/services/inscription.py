"""Inscription d'une agence en libre-service : bureau, administrateur et abonnement d'essai."""

from __future__ import annotations

import re
import time
import unicodedata
import uuid
from collections import defaultdict, deque
from datetime import timedelta
from threading import Lock

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Environnement, Parametres
from app.core.erreurs import Conflit, DonneesInvalides, LimiteAtteinte
from app.db.base import maintenant_utc
from app.db.tenant import definir_tenant, sans_filtre_tenant
from app.modeles.abonnement import ForfaitAbonnement
from app.modeles.bureau import Bureau
from app.modeles.journal_audit import ResultatAudit
from app.modeles.utilisateur import Utilisateur
from app.services import abonnements as service_abonnements
from app.services import audit
from app.services.bureaux import provisionner_bureau_et_admin

MESSAGE_EMAIL_INDISPONIBLE = (
    "Impossible de créer le compte avec ces informations. "
    "Si vous avez déjà un compte, connectez-vous."
)
FENETRE_LIMITE_SECONDES = 3600


class LimiteurInscriptions:
    """Limitation simple en mémoire : N tentatives par adresse IP sur une heure glissante."""

    def __init__(self) -> None:
        self._essais: dict[str, deque[float]] = defaultdict(deque)
        self._verrou = Lock()

    def verifier_et_compter(self, cle: str, maximum: int) -> None:
        maintenant = time.monotonic()
        with self._verrou:
            file = self._essais[cle]
            while file and maintenant - file[0] > FENETRE_LIMITE_SECONDES:
                file.popleft()
            if len(file) >= maximum:
                raise LimiteAtteinte(
                    "Trop de demandes d'inscription depuis cette connexion. Réessayez plus tard."
                )
            file.append(maintenant)


def verifier_limite(
    limiteur: LimiteurInscriptions, ip: str, parametres: Parametres
) -> None:
    if (
        parametres.environnement is Environnement.TEST
        and not parametres.inscription_limite_active_en_test
    ):
        return
    limiteur.verifier_et_compter(ip, parametres.inscription_max_par_heure_par_ip)


def deriver_slug_base(nom_bureau: str) -> str:
    texte = unicodedata.normalize("NFKD", nom_bureau)
    texte = texte.encode("ascii", "ignore").decode("ascii").lower()
    texte = re.sub(r"[^a-z0-9]+", "-", texte).strip("-")[:50].strip("-")
    if len(texte) < 3:
        texte = f"bureau-{texte}".strip("-") if texte else "bureau"
        if len(texte) < 3:
            texte = "bureau"
    return texte


def _slug_disponible(db: Session, slug_base: str) -> str:
    with sans_filtre_tenant(db):
        existants = set(
            db.scalars(select(Bureau.slug).where(Bureau.slug.like(f"{slug_base}%")))
        )
    if slug_base not in existants:
        return slug_base
    n = 2
    while f"{slug_base}-{n}" in existants:
        n += 1
    return f"{slug_base}-{n}"


def inscrire_bureau(
    db: Session,
    *,
    nom_bureau: str,
    email_admin: str,
    nom_admin: str,
    mot_de_passe: str,
    accepte_cgu: bool,
    forfait: ForfaitAbonnement,
    parametres: Parametres,
) -> Bureau:
    if not accepte_cgu:
        raise DonneesInvalides(
            "L'acceptation des Conditions Générales d'Utilisation est obligatoire."
        )
    email_norm = email_admin.strip().lower()
    with sans_filtre_tenant(db):
        if db.scalar(select(Utilisateur.id).where(Utilisateur.email == email_norm)):
            raise Conflit(MESSAGE_EMAIL_INDISPONIBLE)

    slug = _slug_disponible(db, deriver_slug_base(nom_bureau))
    try:
        bureau, admin = provisionner_bureau_et_admin(
            db,
            nom_bureau=nom_bureau,
            slug=slug,
            email_admin=email_norm,
            nom_admin=nom_admin,
            mot_de_passe_admin=mot_de_passe,
            parametres=parametres,
            doit_changer_mot_de_passe=False,
        )
    except Conflit as exc:
        # Course entre deux inscriptions : message neutre, sans révéler le motif.
        raise Conflit(MESSAGE_EMAIL_INDISPONIBLE) from exc

    # Abonnement d'essai (30 jours) au forfait choisi, avec acceptation des CGU.
    definir_tenant(db, bureau.id)
    abo = service_abonnements._obtenir_ou_creer_abonnement_orm(db)
    libelle, prix, quota = service_abonnements.CATALOGUE_FORFAITS[forfait]
    abo.forfait = forfait
    abo.prix_mensuel_eur = prix
    abo.quota_dossiers_mensuels = quota
    abo.statut_stripe = "trialing"
    abo.periode_courante_fin = maintenant_utc() + timedelta(days=30)
    abo.cgu_version_acceptee = parametres.version_cgu_courante
    abo.cgu_acceptees_le = maintenant_utc()
    abo.cgu_acceptees_par_id = admin.id
    audit.journaliser(
        db,
        "bureau.inscription_libre_service",
        ResultatAudit.SUCCES,
        acteur_id=admin.id,
        ressource_type="abonnement",
        ressource_id=abo.id,
        details={
            "forfait": forfait.value,
            "version_cgu": parametres.version_cgu_courante,
            "essai_jours": 30,
        },
    )
    db.commit()
    return bureau


def nouvel_identifiant_factice() -> uuid.UUID:
    return uuid.uuid4()
