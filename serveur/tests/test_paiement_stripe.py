"""Tests du paiement Stripe : création de session Checkout (httpx simulé, aucun réseau)
et traitement des webhooks (statuts réels, résolution du bureau, isolation)."""

from __future__ import annotations

import json
import time
import uuid
from datetime import timezone

import httpx
import pytest
from sqlalchemy import select

from app.core.config import Environnement, Parametres
from app.core.erreurs import AccesRefuse, ServiceIndisponible
from app.db.tenant import definir_tenant, sans_filtre_tenant
from app.modeles.abonnement import AbonnementBureau, ForfaitAbonnement
from app.modeles.bureau import Bureau
from app.services import abonnements, paiement_stripe
from tests.conftest import DonneesBureauTest

CLE = "sk_test_CLE_TRES_SECRETE_123"
SECRET_WH = "whsec_test_secret_unique"


class FausseReponse:
    def __init__(self, statut: int = 200, corps=None, json_ok: bool = True) -> None:
        self.status_code = statut
        self._corps = corps
        self._json_ok = json_ok

    def json(self):
        if not self._json_ok:
            raise ValueError("illisible")
        return self._corps


class JournalAppels(list):
    etat: dict


@pytest.fixture()
def appels(monkeypatch):
    """Remplace httpx.post ; enregistre les appels et renvoie la réponse programmée."""
    journal = JournalAppels()
    etat = {"reponse": FausseReponse(200, {"id": "cs_test_abc", "url": "https://checkout.stripe.com/c/pay/cs_test_abc"})}

    def faux_post(url, **kwargs):
        journal.append({"url": url, **kwargs})
        rep = etat["reponse"]
        if isinstance(rep, Exception):
            raise rep
        return rep

    monkeypatch.setattr(httpx, "post", faux_post)
    journal.etat = etat
    return journal


def _params(base: Parametres, **maj) -> Parametres:
    return base.model_copy(
        update={
            "stripe_cle_secrete": CLE,
            "stripe_secret_webhook": SECRET_WH,
            "stripe_prix_professionnel": "price_pro_123",
            "url_publique_plateforme": "https://app.exemple.com/",
            **maj,
        }
    )


def _preparer_abo(fabrique, tid: uuid.UUID, parametres: Parametres, **champs) -> None:
    with fabrique() as db:
        definir_tenant(db, tid)
        abo = abonnements._obtenir_ou_creer_abonnement_orm(db)
        abo.cgu_version_acceptee = parametres.version_cgu_courante
        for k, v in champs.items():
            setattr(abo, k, v)
        db.commit()


def _checkout(fabrique, tid, parametres, forfait=ForfaitAbonnement.PROFESSIONNEL, acteur=None):
    with fabrique() as db:
        definir_tenant(db, tid)
        return abonnements.creer_session_checkout_stripe(
            db, forfait=forfait, acteur_id=acteur, parametres=parametres
        )


def _webhook(fabrique, parametres, evenement: dict) -> dict:
    corps = json.dumps(evenement).encode()
    sig = abonnements.construire_en_tete_signature_stripe(corps, parametres.stripe_secret_webhook)
    with fabrique() as db:
        return abonnements.traiter_evenement_webhook_stripe(
            db, charge_utile_octets=corps, en_tete_signature=sig, parametres=parametres
        )


def _etat(fabrique, tid: uuid.UUID):
    with fabrique() as db:
        with sans_filtre_tenant(db):
            abo = db.scalar(select(AbonnementBureau).where(AbonnementBureau.tenant_id == tid))
            bureau = db.get(Bureau, tid)
            return abo, bureau.actif


def _evt(type_evt: str, objet: dict) -> dict:
    return {"id": "evt_1", "type": type_evt, "data": {"object": objet}}


# ---------------------------------------------------------------- Checkout


def test_checkout_corps_exact_sans_donnee_personnelle(
    deux_bureaux, fabrique_sessions, parametres_test, appels
) -> None:
    a, _ = deux_bureaux
    p = _params(parametres_test)
    _preparer_abo(fabrique_sessions, a.bureau.id, p)
    sortie = _checkout(fabrique_sessions, a.bureau.id, p, acteur=a.admin.id)

    assert sortie.simulation is False
    assert sortie.session_id == "cs_test_abc"
    assert len(appels) == 1
    appel = appels[0]
    assert appel["url"] == "https://api.stripe.com/v1/checkout/sessions"
    assert appel["headers"] == {"Authorization": f"Bearer {CLE}"}
    assert appel["timeout"] == 20.0
    tid = str(a.bureau.id)
    assert appel["data"] == {
        "mode": "subscription",
        "line_items[0][price]": "price_pro_123",
        "line_items[0][quantity]": "1",
        "client_reference_id": tid,
        "metadata[tenant_id]": tid,
        "metadata[forfait]": "professionnel",
        "subscription_data[metadata][tenant_id]": tid,
        "subscription_data[metadata][forfait]": "professionnel",
        "success_url": "https://app.exemple.com/?paiement=reussi",
        "cancel_url": "https://app.exemple.com/?paiement=annule",
    }
    texte = json.dumps(appel["data"]).lower()
    assert "email" not in texte and "@" not in texte and "alpha" not in texte


def test_checkout_envoie_customer_connu(
    deux_bureaux, fabrique_sessions, parametres_test, appels
) -> None:
    a, _ = deux_bureaux
    p = _params(parametres_test)
    _preparer_abo(fabrique_sessions, a.bureau.id, p, stripe_customer_id="cus_connu")
    _checkout(fabrique_sessions, a.bureau.id, p, acteur=a.admin.id)
    assert appels[0]["data"]["customer"] == "cus_connu"


def test_checkout_prix_ou_url_manquant(
    deux_bureaux, fabrique_sessions, parametres_test, appels
) -> None:
    a, _ = deux_bureaux
    p = _params(parametres_test, stripe_prix_professionnel=None)
    _preparer_abo(fabrique_sessions, a.bureau.id, p)
    with pytest.raises(ServiceIndisponible, match="non configuré pour ce forfait"):
        _checkout(fabrique_sessions, a.bureau.id, p, acteur=a.admin.id)
    p2 = _params(parametres_test, url_publique_plateforme=None)
    with pytest.raises(ServiceIndisponible, match="non configuré pour ce forfait"):
        _checkout(fabrique_sessions, a.bureau.id, p2, acteur=a.admin.id)
    assert appels == []


def test_checkout_sans_cle_production_503_et_test_simulation(
    deux_bureaux, fabrique_sessions, parametres_test, appels
) -> None:
    a, _ = deux_bureaux
    _preparer_abo(fabrique_sessions, a.bureau.id, parametres_test)
    prod = parametres_test.model_copy(
        update={"environnement": Environnement.PRODUCTION, "stripe_cle_secrete": None}
    )
    with pytest.raises(ServiceIndisponible, match="Paiement en ligne non configuré"):
        _checkout(fabrique_sessions, a.bureau.id, prod, acteur=a.admin.id)

    sortie = _checkout(fabrique_sessions, a.bureau.id, parametres_test, acteur=a.admin.id)
    assert sortie.simulation is True
    assert sortie.session_id.startswith("cs_test_")
    assert "checkout.stripe.com" in sortie.url_checkout
    assert appels == []


@pytest.mark.parametrize(
    "reponse",
    [
        FausseReponse(401, {"error": {"message": "Invalid API Key sk_test_CLE_TRES_SECRETE_123"}}),
        FausseReponse(402, {"error": "corps secret"}),
        FausseReponse(500, {"error": "corps secret"}),
        FausseReponse(200, json_ok=False),
        FausseReponse(200, {"id": "cs_1"}),
        FausseReponse(200, {"url": "https://x"}),
        httpx.ConnectTimeout("delai depasse avec sk_test_CLE_TRES_SECRETE_123"),
    ],
)
def test_checkout_erreurs_stripe_donnent_503_sans_fuite(
    deux_bureaux, fabrique_sessions, parametres_test, appels, reponse
) -> None:
    a, _ = deux_bureaux
    p = _params(parametres_test)
    _preparer_abo(fabrique_sessions, a.bureau.id, p)
    appels.etat["reponse"] = reponse  # type: ignore[attr-defined]
    with pytest.raises(ServiceIndisponible) as info:
        _checkout(fabrique_sessions, a.bureau.id, p, acteur=a.admin.id)
    assert info.value.statut_http == 503
    message = str(info.value) + repr(info.value.__cause__) + repr(info.value.__context__ is None)
    assert CLE not in message and "corps secret" not in message
    assert getattr(info.value, "__cause__", None) is None


def test_checkout_via_api_simulation(application, deux_bureaux, parametres_test) -> None:
    from tests.conftest import connecter_client

    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.admin.email)
    client.post(
        "/api/v1/abonnement/cgu/accepter",
        json={"acceptation_explicite": True, "version_cgu": parametres_test.version_cgu_courante},
    )
    r = client.post("/api/v1/abonnement/checkout-stripe", json={"forfait": "starter"})
    assert r.status_code == 201
    assert r.json()["simulation"] is True


# ---------------------------------------------------------------- Webhook


def test_webhook_secret_par_defaut_refuse_en_production(
    deux_bureaux, fabrique_sessions, parametres_test
) -> None:
    a, _ = deux_bureaux
    prod = parametres_test.model_copy(update={"environnement": Environnement.PRODUCTION})
    assert prod.stripe_secret_webhook == "whsec_dev_local_secret_change_me"
    evt = _evt("invoice.payment_failed", {"metadata": {"tenant_id": str(a.bureau.id)}})
    with pytest.raises(AccesRefuse):
        _webhook(fabrique_sessions, prod, evt)
    abo, _actif = _etat(fabrique_sessions, a.bureau.id)
    assert abo is None or abo.statut_stripe != "past_due"


def test_webhook_signature_invalide_refusee(deux_bureaux, fabrique_sessions, parametres_test) -> None:
    a, _ = deux_bureaux
    p = _params(parametres_test)
    corps = json.dumps(_evt("invoice.paid", {"metadata": {"tenant_id": str(a.bureau.id)}})).encode()
    mauvaise = abonnements.construire_en_tete_signature_stripe(corps, "autre_secret")
    with fabrique_sessions() as db:
        with pytest.raises(AccesRefuse):
            abonnements.traiter_evenement_webhook_stripe(
                db, charge_utile_octets=corps, en_tete_signature=mauvaise, parametres=p
            )
        with pytest.raises(AccesRefuse):
            abonnements.traiter_evenement_webhook_stripe(
                db, charge_utile_octets=corps, en_tete_signature=None, parametres=p
            )


def test_webhook_resolution_par_customer_et_subscription(
    deux_bureaux, fabrique_sessions, parametres_test
) -> None:
    a, b = deux_bureaux
    p = _params(parametres_test)
    _preparer_abo(fabrique_sessions, a.bureau.id, p, stripe_customer_id="cus_A", statut_stripe="active")
    _preparer_abo(fabrique_sessions, b.bureau.id, p, stripe_subscription_id="sub_B", statut_stripe="active")

    r1 = _webhook(fabrique_sessions, p, _evt("invoice.payment_failed", {"customer": "cus_A"}))
    assert r1["statut"] == "suspendu"
    abo_a, actif_a = _etat(fabrique_sessions, a.bureau.id)
    abo_b, _ = _etat(fabrique_sessions, b.bureau.id)
    assert abo_a.statut_stripe == "past_due"
    assert abo_b.statut_stripe == "active"  # isolation
    assert actif_a is True  # le webhook ne touche plus bureau.actif

    _webhook(fabrique_sessions, p, _evt("customer.subscription.deleted", {"id": "sub_B", "object": "subscription"}))
    abo_a, _ = _etat(fabrique_sessions, a.bureau.id)
    abo_b, actif_b = _etat(fabrique_sessions, b.bureau.id)
    assert abo_b.statut_stripe == "canceled" and actif_b is True
    assert abo_a.statut_stripe == "past_due"


def test_webhook_resolution_par_subscription_details(
    deux_bureaux, fabrique_sessions, parametres_test
) -> None:
    a, _ = deux_bureaux
    p = _params(parametres_test)
    _preparer_abo(fabrique_sessions, a.bureau.id, p, statut_stripe="active")
    tid = str(a.bureau.id)
    _webhook(
        fabrique_sessions,
        p,
        _evt("invoice.payment_failed", {"parent": {"subscription_details": {"metadata": {"tenant_id": tid}}}}),
    )
    abo, _ = _etat(fabrique_sessions, a.bureau.id)
    assert abo.statut_stripe == "past_due"


def test_webhook_subscription_updated_traduit_le_vrai_statut(
    deux_bureaux, fabrique_sessions, parametres_test
) -> None:
    a, _ = deux_bureaux
    p = _params(parametres_test)
    tid = str(a.bureau.id)
    _preparer_abo(fabrique_sessions, a.bureau.id, p, statut_stripe="active")

    base = {"id": "sub_1", "customer": "cus_1", "metadata": {"tenant_id": tid}}
    _webhook(fabrique_sessions, p, _evt("customer.subscription.updated", {**base, "status": "past_due"}))
    assert _etat(fabrique_sessions, a.bureau.id)[0].statut_stripe == "past_due"

    _webhook(fabrique_sessions, p, _evt("customer.subscription.updated", {**base, "status": "paused"}))
    assert _etat(fabrique_sessions, a.bureau.id)[0].statut_stripe == "past_due"  # inchangé

    _webhook(
        fabrique_sessions,
        p,
        _evt(
            "customer.subscription.updated",
            {**base, "status": "trialing", "metadata": {"tenant_id": tid, "forfait": "entreprise"}},
        ),
    )
    abo, _ = _etat(fabrique_sessions, a.bureau.id)
    assert abo.statut_stripe == "active"
    assert abo.forfait is ForfaitAbonnement.ENTREPRISE and abo.quota_dossiers_mensuels == 1000
    assert abo.stripe_subscription_id == "sub_1" and abo.stripe_customer_id == "cus_1"

    _webhook(fabrique_sessions, p, _evt("customer.subscription.updated", {**base, "status": "unpaid"}))
    assert _etat(fabrique_sessions, a.bureau.id)[0].statut_stripe == "past_due"
    _webhook(fabrique_sessions, p, _evt("customer.subscription.updated", {**base, "status": "incomplete_expired"}))
    assert _etat(fabrique_sessions, a.bureau.id)[0].statut_stripe == "canceled"


def test_webhook_invoice_paid_reactive_et_fixe_la_periode(
    deux_bureaux, fabrique_sessions, parametres_test
) -> None:
    a, _ = deux_bureaux
    p = _params(parametres_test)
    _preparer_abo(fabrique_sessions, a.bureau.id, p, stripe_customer_id="cus_A", statut_stripe="past_due")
    fin = int(time.time()) + 20 * 86400
    objet = {"customer": "cus_A", "lines": {"data": [{"period": {"end": fin}}]}}
    for type_evt in ("invoice.paid", "invoice.payment_succeeded"):
        _preparer_abo(fabrique_sessions, a.bureau.id, p, statut_stripe="past_due")
        r = _webhook(fabrique_sessions, p, _evt(type_evt, objet))
        assert r["statut"] == "active"
        abo, _ = _etat(fabrique_sessions, a.bureau.id)
        assert abo.statut_stripe == "active"
        periode = abo.periode_courante_fin
        if periode.tzinfo is None:
            periode = periode.replace(tzinfo=timezone.utc)
        assert int(periode.timestamp()) == fin

    # sans ligne de période : +30 jours environ
    _webhook(fabrique_sessions, p, _evt("invoice.paid", {"customer": "cus_A"}))
    abo, _ = _etat(fabrique_sessions, a.bureau.id)
    periode = abo.periode_courante_fin
    if periode.tzinfo is None:
        periode = periode.replace(tzinfo=timezone.utc)
    assert abs(periode.timestamp() - (time.time() + 30 * 86400)) < 300


def test_webhook_checkout_complete_enregistre_les_identifiants(
    deux_bureaux, fabrique_sessions, parametres_test
) -> None:
    a, _ = deux_bureaux
    p = _params(parametres_test)
    tid = str(a.bureau.id)
    r = _webhook(
        fabrique_sessions,
        p,
        _evt(
            "checkout.session.completed",
            {
                "id": "cs_1",
                "client_reference_id": tid,
                "customer": "cus_9",
                "subscription": "sub_9",
                "metadata": {"tenant_id": tid, "forfait": "professionnel"},
            },
        ),
    )
    assert r == {"statut": "active", "forfait": "professionnel"}
    abo, _ = _etat(fabrique_sessions, a.bureau.id)
    assert (abo.stripe_customer_id, abo.stripe_subscription_id) == ("cus_9", "sub_9")
    assert abo.quota_dossiers_mensuels == 150


def test_webhook_bureau_introuvable_est_ignore(deux_bureaux, fabrique_sessions, parametres_test) -> None:
    p = _params(parametres_test)
    r = _webhook(fabrique_sessions, p, _evt("invoice.paid", {"customer": "cus_inconnu"}))
    assert r["statut"] == "ignore"
    r = _webhook(
        fabrique_sessions,
        p,
        _evt("invoice.paid", {"client_reference_id": str(uuid.uuid4()), "customer": "cus_x"}),
    )
    assert r["statut"] == "ignore"
