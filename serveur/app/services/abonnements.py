"""Service de gestion des abonnements SaaS mensuels, de la facturation Stripe,
des quotas par bureau et de l'acceptation des Conditions Générales d'Utilisation (Phase 6)."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Environnement, Parametres
from app.core.erreurs import AccesRefuse, Conflit, DonneesInvalides, ServiceIndisponible
from app.db.base import maintenant_utc
from app.db.tenant import definir_tenant, sans_filtre_tenant, tenant_courant
from app.modeles.abonnement import AbonnementBureau, ForfaitAbonnement
from app.modeles.bureau import Bureau
from app.modeles.candidat import Candidat, StatutCandidat
from app.modeles.journal_audit import ResultatAudit
from app.schemas.abonnement_conformite import (
    AbonnementBureauSortie,
    AcceptationCGUEntree,
    ForfaitCatalogueSortie,
    SessionCheckoutStripeSortie,
    TexteCGUSortie,
)
from app.services import audit, paiement_stripe

CATALOGUE_FORFAITS: dict[ForfaitAbonnement, tuple[str, int, int]] = {
    ForfaitAbonnement.STARTER: ("Forfait Starter (Petit Bureau)", 49, 30),
    ForfaitAbonnement.PROFESSIONNEL: ("Forfait Professionnel (Agence Active)", 129, 150),
    ForfaitAbonnement.ENTREPRISE: ("Forfait Entreprise (Multi-Conseillers)", 299, 1000),
}

TEXTE_CGU_OFFICIEL = """CONDITIONS GÉNÉRALES D'UTILISATION (CGU) — PLATEFORME « AGENT BUREAU D'ÉTUDES »

1. Objet du service :
La plateforme fournit aux bureaux d'études et d'accompagnement un outil de gestion chiffrée des dossiers candidats (Campus France / Études en France et IRCC Canada) et d'assistance au pré-remplissage local.

2. Règles de sécurité non négociables :
- Article 2.1 (Validation humaine obligatoire — Règle 1) : L'agent local s'arrête obligatoirement avant le bouton final de soumission. L'opérateur humain du bureau vérifie la capture de contrôle et clique lui-même sur le bouton d'envoi officiel.
- Article 2.2 (Contrôles de sécurité et sessions — Règles 2 et 3) : Aucun mot de passe de portail officiel ni CléGC n'est stocké par la plateforme. L'ouverture de session, les CAPTCHA et la double authentification (2FA) sont gérés exclusivement par l'humain dans le navigateur local du bureau.
- Article 2.3 (Exactitude des données — Règle 4) : Aucune valeur par défaut n'est jamais inventée par le logiciel. Toute donnée ou pièce manquante entraîne la suspension automatique de la tâche.

3. Conformité à la Loi algérienne n° 18-07 et au RGPD :
Le bureau d'études agit en qualité de responsable de traitement vis-à-vis de ses candidats et s'engage à recueillir leur consentement explicite préalable avant la saisie de leurs pièces d'identité et justificatifs."""


def _exiger_tenant(db: Session) -> uuid.UUID:
    tid = tenant_courant(db)
    if tid is None:
        raise RuntimeError("Contexte bureau (tenant) manquant sur la session.")
    return tid


def lister_catalogue_forfaits() -> list[ForfaitCatalogueSortie]:
    return [
        ForfaitCatalogueSortie(
            forfait=forfait,
            libelle=libelle,
            prix_mensuel_eur=prix,
            quota_dossiers_mensuels=quota,
        )
        for forfait, (libelle, prix, quota) in CATALOGUE_FORFAITS.items()
    ]


def obtenir_texte_cgu(parametres: Parametres) -> TexteCGUSortie:
    empreinte = hashlib.sha256(TEXTE_CGU_OFFICIEL.encode("utf-8")).hexdigest()
    return TexteCGUSortie(
        version_cgu=parametres.version_cgu_courante,
        texte_complet=TEXTE_CGU_OFFICIEL,
        empreinte_sha256=empreinte,
    )


def _obtenir_ou_creer_abonnement_orm(db: Session) -> AbonnementBureau:
    tid = _exiger_tenant(db)
    abo = db.scalar(select(AbonnementBureau).where(AbonnementBureau.tenant_id == tid))
    if abo is not None:
        return abo

    _libelle, prix, quota = CATALOGUE_FORFAITS[ForfaitAbonnement.STARTER]
    abo = AbonnementBureau(
        id=uuid.uuid4(),
        tenant_id=tid,
        forfait=ForfaitAbonnement.STARTER,
        quota_dossiers_mensuels=quota,
        prix_mensuel_eur=prix,
        statut_stripe="trialing",
        periode_courante_fin=maintenant_utc() + timedelta(days=30),
        duree_conservation_jours=365,
    )
    db.add(abo)
    db.flush()
    return abo


def _serialiser_abonnement(db: Session, abo: AbonnementBureau) -> AbonnementBureauSortie:
    dossiers_actifs = (
        db.scalar(
            select(func.count(Candidat.id)).where(
                Candidat.statut == StatutCandidat.ACTIF
            )
        )
        or 0
    )
    return AbonnementBureauSortie(
        id=abo.id,
        forfait=abo.forfait,
        quota_dossiers_mensuels=abo.quota_dossiers_mensuels,
        prix_mensuel_eur=abo.prix_mensuel_eur,
        dossiers_actifs_ce_mois=dossiers_actifs,
        stripe_customer_id=abo.stripe_customer_id,
        stripe_subscription_id=abo.stripe_subscription_id,
        statut_stripe=abo.statut_stripe,
        periode_courante_fin=abo.periode_courante_fin,
        cgu_version_acceptee=abo.cgu_version_acceptee,
        cgu_acceptees_le=abo.cgu_acceptees_le,
        cgu_acceptees_par_id=abo.cgu_acceptees_par_id,
        duree_conservation_jours=abo.duree_conservation_jours,
        cree_le=abo.cree_le,
        modifie_le=abo.modifie_le,
    )


def obtenir_abonnement_bureau(db: Session) -> AbonnementBureauSortie:
    abo = _obtenir_ou_creer_abonnement_orm(db)
    db.commit()
    return _serialiser_abonnement(db, abo)


def accepter_cgu_bureau(
    db: Session,
    *,
    donnees: AcceptationCGUEntree,
    acteur_id: uuid.UUID,
    parametres: Parametres,
) -> AbonnementBureauSortie:
    _exiger_tenant(db)
    if not donnees.acceptation_explicite:
        raise DonneesInvalides(
            "L'acceptation explicite des Conditions Générales d'Utilisation est obligatoire."
        )
    if donnees.version_cgu != parametres.version_cgu_courante:
        raise DonneesInvalides(
            f"Version CGU invalide : la version en vigueur est '{parametres.version_cgu_courante}'."
        )

    abo = _obtenir_ou_creer_abonnement_orm(db)
    abo.cgu_version_acceptee = donnees.version_cgu
    abo.cgu_acceptees_le = maintenant_utc()
    abo.cgu_acceptees_par_id = acteur_id

    audit.journaliser(
        db,
        "bureau.acceptation_cgu",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="abonnement",
        ressource_id=abo.id,
        details={"version_cgu": donnees.version_cgu},
    )
    db.commit()
    return _serialiser_abonnement(db, abo)


def mettre_a_jour_politique_conservation(
    db: Session,
    *,
    duree_conservation_jours: int,
    acteur_id: uuid.UUID,
) -> AbonnementBureauSortie:
    _exiger_tenant(db)
    abo = _obtenir_ou_creer_abonnement_orm(db)
    abo.duree_conservation_jours = duree_conservation_jours

    audit.journaliser(
        db,
        "bureau.modification_politique_conservation",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="abonnement",
        ressource_id=abo.id,
        details={"duree_conservation_jours": duree_conservation_jours},
    )
    db.commit()
    return _serialiser_abonnement(db, abo)


def creer_session_checkout_stripe(
    db: Session,
    *,
    forfait: ForfaitAbonnement,
    acteur_id: uuid.UUID,
    parametres: Parametres,
) -> SessionCheckoutStripeSortie:
    """Prépare une session de souscription Stripe pour le bureau (exige que les CGU aient été acceptées).

    Avec `stripe_cle_secrete` : appel réel à Stripe. Sans clé : indisponible en production,
    comportement simulé (sans appel réseau) en local et en test."""
    tid = _exiger_tenant(db)
    abo = _obtenir_ou_creer_abonnement_orm(db)
    if abo.cgu_version_acceptee != parametres.version_cgu_courante:
        raise Conflit(
            "Veuillez d'abord accepter les Conditions Générales d'Utilisation (CGU) en vigueur avant de souscrire."
        )

    _libelle, prix, _quota = CATALOGUE_FORFAITS[forfait]
    simulation = False
    if parametres.stripe_cle_secrete:
        session_id, url_checkout = paiement_stripe.creer_session_checkout(
            parametres,
            tenant_id=tid,
            forfait=forfait,
            stripe_customer_id=abo.stripe_customer_id,
        )
    elif parametres.environnement is Environnement.PRODUCTION:
        raise ServiceIndisponible("Paiement en ligne non configuré")
    else:
        simulation = True
        session_id = f"cs_test_{uuid.uuid4().hex[:24]}"
        url_checkout = (
            f"https://checkout.stripe.com/c/pay/{session_id}"
            f"?client_reference_id={tid}&plan={forfait.value}"
        )

    audit.journaliser(
        db,
        "abonnement.creation_session_checkout_stripe",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="abonnement",
        ressource_id=abo.id,
        details={
            "forfait_demande": forfait.value,
            "prix_mensuel_eur": prix,
            "session_id": session_id,
            "simulation": simulation,
        },
    )
    db.commit()
    return SessionCheckoutStripeSortie(
        session_id=session_id,
        url_checkout=url_checkout,
        forfait=forfait,
        prix_mensuel_eur=prix,
        simulation=simulation,
    )


def construire_en_tete_signature_stripe(
    charge_utile_octets: bytes,
    secret_webhook: str,
    horodatage_unix: int | None = None,
) -> str:
    """Calcule l'en-tête `Stripe-Signature: t=...,v1=...` standard (HMAC-SHA256)."""
    ts = horodatage_unix if horodatage_unix is not None else int(time.time())
    message_signe = f"{ts}.".encode("ascii") + charge_utile_octets
    signature = hmac.new(
        secret_webhook.encode("utf-8"),
        message_signe,
        hashlib.sha256,
    ).hexdigest()
    return f"t={ts},v1={signature}"


def verifier_signature_webhook_stripe(
    charge_utile_octets: bytes,
    en_tete_signature: str | None,
    secret_webhook: str,
    *,
    tolerance_secondes: int = 300,
) -> dict:
    """Vérifie cryptographiquement la signature HMAC-SHA256 d'un webhook Stripe
    et sa fraîcheur temporelle avant de désérialiser le JSON."""
    if not en_tete_signature:
        raise AccesRefuse("En-tête Stripe-Signature manquant.")

    morceaux: dict[str, str] = {}
    for element in en_tete_signature.split(","):
        if "=" in element:
            k, v = element.strip().split("=", 1)
            morceaux[k] = v

    if "t" not in morceaux or "v1" not in morceaux:
        raise AccesRefuse("Format d'en-tête Stripe-Signature invalide.")

    try:
        horodatage = int(morceaux["t"])
    except ValueError as exc:
        raise AccesRefuse("Horodatage Stripe-Signature invalide.") from exc

    if abs(int(time.time()) - horodatage) > tolerance_secondes:
        raise AccesRefuse("Signature webhook Stripe expirée (hors fenêtre de tolérance).")

    message_signe = f"{horodatage}.".encode("ascii") + charge_utile_octets
    attendu = hmac.new(
        secret_webhook.encode("utf-8"),
        message_signe,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(attendu, morceaux["v1"]):
        raise AccesRefuse("Signature webhook Stripe invalide.")

    try:
        return json.loads(charge_utile_octets.decode("utf-8"))
    except Exception as exc:
        raise DonneesInvalides("Corps JSON du webhook Stripe invalide.") from exc


SECRET_WEBHOOK_DEVELOPPEMENT = "whsec_dev_local_secret_change_me"

_STATUTS_STRIPE_ACTIFS = {"active", "trialing"}
_STATUTS_STRIPE_IMPAYES = {"past_due", "unpaid"}
_STATUTS_STRIPE_RESILIES = {"canceled", "incomplete_expired"}


def _dict(valeur: object) -> dict:
    return valeur if isinstance(valeur, dict) else {}


def _texte(valeur: object) -> str | None:
    return valeur if isinstance(valeur, str) and valeur else None


def _tenant_depuis_evenement(objet: dict) -> uuid.UUID | None:
    """Cherche le bureau dans l'ordre : client_reference_id, metadata, subscription_details."""
    candidats = [
        objet.get("client_reference_id"),
        _dict(objet.get("metadata")).get("tenant_id"),
        _dict(_dict(objet.get("subscription_details")).get("metadata")).get("tenant_id"),
        _dict(
            _dict(_dict(objet.get("parent")).get("subscription_details")).get("metadata")
        ).get("tenant_id"),
    ]
    for candidat in candidats:
        if not candidat:
            continue
        try:
            return uuid.UUID(str(candidat))
        except ValueError:
            continue
    return None


def _identifiant_abonnement_stripe(objet: dict, type_evt: str) -> str | None:
    direct = _texte(objet.get("subscription"))
    if direct:
        return direct
    parent = _dict(_dict(objet.get("parent")).get("subscription_details"))
    depuis_parent = _texte(parent.get("subscription"))
    if depuis_parent:
        return depuis_parent
    if type_evt.startswith("customer.subscription.") or objet.get("object") == "subscription":
        return _texte(objet.get("id"))
    return None


def _resoudre_bureau(
    db: Session, objet: dict, type_evt: str
) -> tuple[uuid.UUID, Bureau] | None:
    """Retrouve le bureau concerné ; None si introuvable (l'événement est alors ignoré)."""
    with sans_filtre_tenant(db):
        tid = _tenant_depuis_evenement(objet)
        if tid is not None:
            bureau = db.get(Bureau, tid)
            if bureau is not None:
                return tid, bureau

        client = _texte(objet.get("customer"))
        abo = None
        if client:
            abo = db.scalar(
                select(AbonnementBureau).where(AbonnementBureau.stripe_customer_id == client)
            )
        if abo is None:
            sub = _identifiant_abonnement_stripe(objet, type_evt)
            if sub:
                abo = db.scalar(
                    select(AbonnementBureau).where(
                        AbonnementBureau.stripe_subscription_id == sub
                    )
                )
        if abo is None:
            return None
        bureau = db.get(Bureau, abo.tenant_id)
        if bureau is None:
            return None
        return abo.tenant_id, bureau


def _fin_de_periode_facture(objet: dict) -> datetime:
    lignes = _dict(objet.get("lines")).get("data")
    if isinstance(lignes, list) and lignes:
        fin = _dict(_dict(lignes[0]).get("period")).get("end")
        if isinstance(fin, int) and not isinstance(fin, bool) and fin > 0:
            try:
                return datetime.fromtimestamp(fin, tz=timezone.utc)
            except (OverflowError, OSError, ValueError):
                pass
    return maintenant_utc() + timedelta(days=30)


def _appliquer_forfait_metadata(abo: AbonnementBureau, objet: dict) -> ForfaitAbonnement | None:
    code = _dict(objet.get("metadata")).get("forfait")
    if not code:
        return None
    try:
        forfait = ForfaitAbonnement(code)
    except ValueError:
        return None
    _libelle, prix, quota = CATALOGUE_FORFAITS[forfait]
    abo.forfait = forfait
    abo.prix_mensuel_eur = prix
    abo.quota_dossiers_mensuels = quota
    return forfait


def traiter_evenement_webhook_stripe(
    db: Session,
    *,
    charge_utile_octets: bytes,
    en_tete_signature: str | None,
    parametres: Parametres,
) -> dict[str, str]:
    """Traite les événements Stripe vérifiés : `checkout.session.completed`,
    `customer.subscription.updated` / `.deleted`, `invoice.paid`,
    `invoice.payment_succeeded` et `invoice.payment_failed`."""
    if (
        parametres.environnement is Environnement.PRODUCTION
        and parametres.stripe_secret_webhook == SECRET_WEBHOOK_DEVELOPPEMENT
    ):
        # Secret public de développement : n'importe qui pourrait forger un événement.
        raise AccesRefuse("Webhook Stripe refusé : secret de signature non configuré.")

    evenement = verifier_signature_webhook_stripe(
        charge_utile_octets,
        en_tete_signature,
        parametres.stripe_secret_webhook,
    )
    type_evt = str(evenement.get("type", ""))
    objet = _dict(_dict(evenement.get("data")).get("object"))

    resolu = _resoudre_bureau(db, objet, type_evt)
    if resolu is None:
        # 200 volontaire : une erreur ferait rejouer l'événement indéfiniment par Stripe.
        return {"statut": "ignore", "type": type_evt}
    tid, _bureau = resolu

    definir_tenant(db, tid)
    abo = _obtenir_ou_creer_abonnement_orm(db)

    client = _texte(objet.get("customer"))
    sub = _identifiant_abonnement_stripe(objet, type_evt)

    if type_evt == "checkout.session.completed":
        forfait_cible = _appliquer_forfait_metadata(abo, objet) or abo.forfait
        abo.stripe_customer_id = client or abo.stripe_customer_id
        abo.stripe_subscription_id = sub or abo.stripe_subscription_id
        abo.statut_stripe = "active"
        abo.periode_courante_fin = maintenant_utc() + timedelta(days=30)
        audit.journaliser(
            db,
            "abonnement.webhook_activation_stripe",
            ResultatAudit.SUCCES,
            ressource_type="abonnement",
            ressource_id=abo.id,
            details={
                "type_evenement": type_evt,
                "forfait": forfait_cible.value,
                "quota_dossiers_mensuels": abo.quota_dossiers_mensuels,
            },
        )
        db.commit()
        return {"statut": "active", "forfait": forfait_cible.value}

    if type_evt == "customer.subscription.updated":
        statut_reel = str(objet.get("status", ""))
        forfait_cible = _appliquer_forfait_metadata(abo, objet)
        abo.stripe_customer_id = abo.stripe_customer_id or client
        abo.stripe_subscription_id = abo.stripe_subscription_id or sub
        if statut_reel in _STATUTS_STRIPE_ACTIFS:
            nouveau = "active"
        elif statut_reel in _STATUTS_STRIPE_IMPAYES:
            nouveau = "past_due"
        elif statut_reel in _STATUTS_STRIPE_RESILIES:
            nouveau = "canceled"
        else:
            nouveau = None
        if nouveau is not None:
            abo.statut_stripe = nouveau
        audit.journaliser(
            db,
            "abonnement.webhook_mise_a_jour_stripe",
            ResultatAudit.SUCCES,
            ressource_type="abonnement",
            ressource_id=abo.id,
            details={
                "type_evenement": type_evt,
                "statut_stripe": abo.statut_stripe,
                "forfait": abo.forfait.value,
            },
        )
        db.commit()
        if nouveau is None:
            return {"statut": "inchange", "forfait": abo.forfait.value}
        return {
            "statut": "active" if nouveau == "active" else "suspendu",
            "forfait": abo.forfait.value,
        }

    if type_evt in {"invoice.paid", "invoice.payment_succeeded"}:
        abo.stripe_customer_id = abo.stripe_customer_id or client
        abo.stripe_subscription_id = abo.stripe_subscription_id or sub
        abo.statut_stripe = "active"
        abo.periode_courante_fin = _fin_de_periode_facture(objet)
        audit.journaliser(
            db,
            "abonnement.webhook_paiement_stripe",
            ResultatAudit.SUCCES,
            ressource_type="abonnement",
            ressource_id=abo.id,
            details={"type_evenement": type_evt, "statut_stripe": "active"},
        )
        db.commit()
        return {"statut": "active", "forfait": abo.forfait.value}

    if type_evt in {"invoice.payment_failed", "customer.subscription.deleted"}:
        abo.statut_stripe = (
            "past_due" if type_evt == "invoice.payment_failed" else "canceled"
        )
        audit.journaliser(
            db,
            "abonnement.webhook_suspension_stripe",
            ResultatAudit.SUCCES,
            ressource_type="abonnement",
            ressource_id=abo.id,
            details={"type_evenement": type_evt, "statut_stripe": abo.statut_stripe},
        )
        db.commit()
        return {"statut": "suspendu", "forfait": abo.forfait.value}

    return {"statut": "ignore", "type": type_evt}
