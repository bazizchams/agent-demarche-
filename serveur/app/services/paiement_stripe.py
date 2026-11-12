"""Petit client Stripe (Checkout) via `httpx`, sans SDK.

Aucune donnée personnelle n'est envoyée à Stripe (ni e-mail, ni nom) : Stripe les collecte
lui-même sur sa page de paiement. La clé secrète et le corps des réponses ne sont jamais
repris dans les messages d'erreur ni dans les journaux.
"""

from __future__ import annotations

import uuid

import httpx

from app.core.config import Parametres
from app.core.erreurs import ServiceIndisponible
from app.modeles.abonnement import ForfaitAbonnement

URL_SESSIONS_CHECKOUT = "https://api.stripe.com/v1/checkout/sessions"
DELAI_STRIPE_SECONDES = 20.0

MESSAGE_INDISPONIBLE = (
    "Le service de paiement est momentanément indisponible. Veuillez réessayer plus tard."
)
MESSAGE_NON_CONFIGURE_FORFAIT = "Paiement en ligne non configuré pour ce forfait"


def identifiant_prix_forfait(parametres: Parametres, forfait: ForfaitAbonnement) -> str | None:
    prix = {
        ForfaitAbonnement.STARTER: parametres.stripe_prix_starter,
        ForfaitAbonnement.PROFESSIONNEL: parametres.stripe_prix_professionnel,
        ForfaitAbonnement.ENTREPRISE: parametres.stripe_prix_entreprise,
    }[forfait]
    return prix.strip() if prix and prix.strip() else None


def construire_corps_session(
    parametres: Parametres,
    *,
    tenant_id: uuid.UUID,
    forfait: ForfaitAbonnement,
    stripe_customer_id: str | None = None,
) -> dict[str, str]:
    prix = identifiant_prix_forfait(parametres, forfait)
    base = (parametres.url_publique_plateforme or "").strip().rstrip("/")
    if not prix or not base:
        raise ServiceIndisponible(MESSAGE_NON_CONFIGURE_FORFAIT)
    corps = {
        "mode": "subscription",
        "line_items[0][price]": prix,
        "line_items[0][quantity]": "1",
        "client_reference_id": str(tenant_id),
        "metadata[tenant_id]": str(tenant_id),
        "metadata[forfait]": forfait.value,
        "subscription_data[metadata][tenant_id]": str(tenant_id),
        "subscription_data[metadata][forfait]": forfait.value,
        "success_url": f"{base}/?paiement=reussi",
        "cancel_url": f"{base}/?paiement=annule",
    }
    if stripe_customer_id:
        corps["customer"] = stripe_customer_id
    return corps


def creer_session_checkout(
    parametres: Parametres,
    *,
    tenant_id: uuid.UUID,
    forfait: ForfaitAbonnement,
    stripe_customer_id: str | None = None,
) -> tuple[str, str]:
    """Crée une session Stripe Checkout (mode abonnement) et renvoie `(session_id, url)`."""
    cle = parametres.stripe_cle_secrete
    if not cle:
        raise ServiceIndisponible("Paiement en ligne non configuré")
    corps = construire_corps_session(
        parametres,
        tenant_id=tenant_id,
        forfait=forfait,
        stripe_customer_id=stripe_customer_id,
    )
    try:
        reponse = httpx.post(
            URL_SESSIONS_CHECKOUT,
            data=corps,
            headers={"Authorization": f"Bearer {cle}"},
            timeout=DELAI_STRIPE_SECONDES,
        )
    except Exception:  # réseau, délai, TLS... (message d'origine jamais repris)
        raise ServiceIndisponible(MESSAGE_INDISPONIBLE) from None

    code = reponse.status_code
    if code in (401, 403):
        raise ServiceIndisponible(
            "Le paiement en ligne est mal configuré. Contactez le support de la plateforme."
        )
    if code != 200:
        raise ServiceIndisponible(MESSAGE_INDISPONIBLE)
    try:
        donnees = reponse.json()
    except Exception:
        raise ServiceIndisponible(MESSAGE_INDISPONIBLE) from None
    if not isinstance(donnees, dict):
        raise ServiceIndisponible(MESSAGE_INDISPONIBLE)
    session_id = donnees.get("id")
    url = donnees.get("url")
    if not isinstance(session_id, str) or not session_id or not isinstance(url, str) or not url:
        raise ServiceIndisponible(MESSAGE_INDISPONIBLE)
    return session_id, url
