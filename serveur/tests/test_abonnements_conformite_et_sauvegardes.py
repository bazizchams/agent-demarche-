"""Tests d'intégration de la Phase 6 :
- Abonnements SaaS mensuels, acceptation obligatoire des CGU, webhooks Stripe signés HMAC-SHA256 et quotas
- Conformité Loi algérienne n° 18-07 : recueil du consentement candidat, révocation suspendant les tâches actives
- Droit à l'oubli (suppression définitive base + fichiers chiffrés sans PII dans l'audit) et purge de conservation
- Sauvegardes chiffrées AES-256-GCM liées au `tenant_id` (AAD) et durcissement HTTPS/HSTS en production
"""

from __future__ import annotations

import io
import json
import os
import shutil
import time
import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Environnement, Parametres
from app.db.base import maintenant_utc
from app.db.tenant import definir_tenant
from app.main import creer_application
from app.modeles.abonnement import AbonnementBureau
from app.modeles.candidat import Candidat
from app.modeles.document import DocumentCandidat
from app.modeles.journal_audit import EntreeAudit
from app.services.abonnements import construire_en_tete_signature_stripe
from tests.conftest import DonneesBureauTest, connecter_client


def _creer_candidat(client: TestClient, *, nom: str, passeport: str) -> dict:
    r = client.post(
        "/api/v1/candidats",
        json={
            "nom": nom,
            "prenom": "Yasmine",
            "sexe": "F",
            "date_naissance": "2002-04-12",
            "lieu_naissance": "Alger",
            "nationalite": "Algérienne",
            "pays_residence": "Algérie",
            "numero_passeport": passeport,
            "date_expiration_passeport": "2030-09-01",
            "email": f"{nom.lower()}@exemple.dz",
            "telephone": "+213555112233",
            "adresse": "Hydra, Alger",
            "niveau_actuel": "Licence 3 Informatique",
            "programme_vise": "Master 1 Génie Logiciel",
            "etablissement_vise": "Université Paris-Saclay",
            "fonds_disponibles_eur": 8500,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _televerser_piece_pdf(client: TestClient, candidat_id: str) -> dict:
    contenu_pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n" + os.urandom(32)
    r = client.post(
        f"/api/v1/candidats/{candidat_id}/documents",
        data={
            "type_piece": "passeport",
            "date_expiration_piece": "2030-09-01",
        },
        files={"fichier": ("passeport.pdf", io.BytesIO(contenu_pdf), "application/pdf")},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_abonnement_cgu_webhook_stripe_et_quota_mensuel(
    application,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
    fabrique_sessions,
    parametres_test,
) -> None:
    bureau_a, _ = deux_bureaux
    client, _ = connecter_client(application, bureau_a.admin.email)
    tenant_id = str(bureau_a.bureau.id)

    # 1. Catalogue des forfaits mensuels
    r_cat = client.get("/api/v1/abonnement/forfaits")
    assert r_cat.status_code == 200
    forfaits = {f["forfait"]: f for f in r_cat.json()}
    assert set(forfaits.keys()) == {"starter", "professionnel", "entreprise"}
    assert forfaits["professionnel"]["quota_dossiers_mensuels"] == 150

    # 2. Tentative de création d'une session Stripe Checkout AVANT acceptation des CGU -> 409
    r_refus_cgu = client.post(
        "/api/v1/abonnement/checkout-stripe",
        json={"forfait": "professionnel"},
    )
    assert r_refus_cgu.status_code == 409

    # 3. Lecture et acceptation explicite des CGU par l'administrateur du bureau
    r_cgu = client.get("/api/v1/abonnement/cgu")
    assert r_cgu.status_code == 200
    version_cgu = r_cgu.json()["version_cgu"]
    assert "Règle 1" in r_cgu.json()["texte_complet"]

    r_acc = client.post(
        "/api/v1/abonnement/cgu/accepter",
        json={"acceptation_explicite": True, "version_cgu": version_cgu},
    )
    assert r_acc.status_code == 200
    assert r_acc.json()["cgu_version_acceptee"] == version_cgu

    # 4. Création de la session Stripe Checkout après acceptation des CGU
    r_chk = client.post(
        "/api/v1/abonnement/checkout-stripe",
        json={"forfait": "professionnel"},
    )
    assert r_chk.status_code == 201
    assert r_chk.json()["forfait"] == "professionnel"
    assert "checkout.stripe.com" in r_chk.json()["url_checkout"]

    # 5. Sécurité du Webhook Stripe : signature manquante, invalide ou expirée -> 403
    charge_activation = json.dumps(
        {
            "id": "evt_test_01",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_live_123",
                    "client_reference_id": tenant_id,
                    "customer": "cus_alger_01",
                    "subscription": "sub_alger_01",
                    "metadata": {"forfait": "professionnel", "tenant_id": tenant_id},
                }
            },
        }
    ).encode("utf-8")

    assert (
        client.post("/api/v1/webhooks/stripe", content=charge_activation).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/webhooks/stripe",
            content=charge_activation,
            headers={"Stripe-Signature": "t=1700000000,v1=deadbeef"},
        ).status_code
        == 403
    )
    sig_expiree = construire_en_tete_signature_stripe(
        charge_activation,
        parametres_test.stripe_secret_webhook,
        horodatage_unix=int(time.time()) - 900,
    )
    assert (
        client.post(
            "/api/v1/webhooks/stripe",
            content=charge_activation,
            headers={"Stripe-Signature": sig_expiree},
        ).status_code
        == 403
    )

    # 6. Webhook Stripe valide -> passage au forfait Professionnel (quota 150)
    sig_valide = construire_en_tete_signature_stripe(
        charge_activation,
        parametres_test.stripe_secret_webhook,
    )
    r_wh = client.post(
        "/api/v1/webhooks/stripe",
        content=charge_activation,
        headers={"Stripe-Signature": sig_valide},
    )
    assert r_wh.status_code == 200
    assert r_wh.json()["statut"] == "active"

    r_abo = client.get("/api/v1/abonnement")
    assert r_abo.status_code == 200
    assert r_abo.json()["forfait"] == "professionnel"
    assert r_abo.json()["quota_dossiers_mensuels"] == 150
    assert r_abo.json()["statut_stripe"] == "active"

    # 7. Application stricte du quota de dossiers actifs
    _creer_candidat(client, nom="Bensalem", passeport="DZ8000001")
    with fabrique_sessions() as db:
        tid = uuid.UUID(tenant_id)
        definir_tenant(db, tid)
        abo_db = db.scalar(select(AbonnementBureau).where(AbonnementBureau.tenant_id == tid))
        abo_db.quota_dossiers_mensuels = 1
        db.commit()

    r_depassement = client.post(
        "/api/v1/candidats",
        json={
            "nom": "DeuxiemeCandidat",
            "prenom": "Karim",
            "numero_passeport": "DZ8000002",
        },
    )
    assert r_depassement.status_code == 409
    assert "Quota" in r_depassement.json()["detail"]

    # 8. Webhook d'impayé Stripe (`invoice.payment_failed`) -> suspension immédiate du bureau
    charge_impaye = json.dumps(
        {
            "id": "evt_test_02",
            "type": "invoice.payment_failed",
            "data": {
                "object": {
                    "customer": "cus_alger_01",
                    "metadata": {"tenant_id": tenant_id},
                }
            },
        }
    ).encode("utf-8")
    sig_impaye = construire_en_tete_signature_stripe(
        charge_impaye,
        parametres_test.stripe_secret_webhook,
    )
    r_wh_impaye = client.post(
        "/api/v1/webhooks/stripe",
        content=charge_impaye,
        headers={"Stripe-Signature": sig_impaye},
    )
    assert r_wh_impaye.status_code == 200
    assert r_wh_impaye.json()["statut"] == "suspendu"

    # Toute requête authentifiée du bureau suspendu est immédiatement bloquée (403)
    r_bloque = client.get("/api/v1/candidats")
    assert r_bloque.status_code == 403


def test_consentement_loi_18_07_et_revocation_suspend_taches_actives(
    application,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    bureau_a, _ = deux_bureaux
    client, _ = connecter_client(application, bureau_a.admin.email)
    cand = _creer_candidat(client, nom="Khelifi", passeport="DZ8100001")
    cid = cand["id"]

    # Texte officiel Loi 18-07
    r_txt = client.get("/api/v1/conformite/texte-consentement")
    assert r_txt.status_code == 200
    assert "18-07" in r_txt.json()["texte_complet"]

    # Recueil du consentement explicite
    r_cons = client.post(
        f"/api/v1/candidats/{cid}/consentement",
        json={
            "consentement_explicite": True,
            "mode_recueil": "formulaire_signe_bureau",
        },
    )
    assert r_cons.status_code == 201
    preuve = r_cons.json()
    assert len(preuve["empreinte_texte_sha256"]) == 64
    assert preuve["revoque_le"] is None

    # La fiche candidat reflète `consentement_signe = True`
    r_cand = client.get(f"/api/v1/candidats/{cid}")
    assert r_cand.json()["consentement_signe"] is True

    # Téléversement des 6 pièces obligatoires Campus France pour que la tâche démarre en `en_attente`
    for code_piece in (
        "passeport",
        "photo_identite",
        "releve_notes_bac",
        "diplome_bac",
        "releves_notes_superieur",
        "cv",
    ):
        contenu = (
            b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"
            + code_piece.encode("ascii")
        )
        r_doc = client.post(
            f"/api/v1/candidats/{cid}/documents",
            data={"type_piece": code_piece, "date_expiration_piece": "2030-09-01"},
            files={"fichier": (f"{code_piece}.pdf", io.BytesIO(contenu), "application/pdf")},
        )
        assert r_doc.status_code == 201, r_doc.text

    # Ouverture d'une tâche sur le dossier complet du candidat
    r_tache = client.post(
        "/api/v1/taches",
        json={"candidat_id": cid, "code_demarche": "campus_france"},
    )
    assert r_tache.status_code == 201
    tache_id = r_tache.json()["id"]
    assert r_tache.json()["statut"] == "en_attente"

    # Révocation du consentement -> suspend immédiatement la tâche en cours/en attente
    r_rev = client.post(f"/api/v1/candidats/{cid}/consentement/revoquer")
    assert r_rev.status_code == 200
    assert r_rev.json()["revoque_le"] is not None

    r_cand_apres = client.get(f"/api/v1/candidats/{cid}")
    assert r_cand_apres.json()["consentement_signe"] is False

    r_tache_apres = client.get(f"/api/v1/taches/{tache_id}")
    assert r_tache_apres.status_code == 200
    assert r_tache_apres.json()["statut"] == "suspendue"
    assert r_tache_apres.json()["motif_suspension"] == "donnee_manquante"
    assert "18-07" in r_tache_apres.json()["message_alerte"]


def test_suppression_definitive_droit_oubli_et_purge_conservation_sans_pii(
    application,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
    fabrique_sessions,
    parametres_test,
) -> None:
    bureau_a, _ = deux_bureaux
    client, _ = connecter_client(application, bureau_a.admin.email)
    tid = bureau_a.bureau.id

    # 1. Droit à l'oubli / suppression définitive d'un candidat
    cand1 = _creer_candidat(client, nom="NomSecretEfface", passeport="DZ8200001")
    cid1 = cand1["id"]
    doc1 = _televerser_piece_pdf(client, cid1)

    with fabrique_sessions() as db:
        definir_tenant(db, tid)
        doc_orm = db.get(DocumentCandidat, uuid.UUID(doc1["id"]))
        chemin_bin_1 = (
            parametres_test.dossier_stockage / doc_orm.chemin_stockage_relatif
        ).resolve()
        assert chemin_bin_1.exists()

    r_del = client.delete(f"/api/v1/candidats/{cid1}/suppression-definitive")
    assert r_del.status_code == 200
    assert r_del.json()["nb_fichiers_chiffres_supprimes"] >= 1
    assert not chemin_bin_1.exists()
    assert client.get(f"/api/v1/candidats/{cid1}").status_code == 404

    # Vérification Règle 5 : aucune donnée personnelle dans journal_audit après suppression
    with fabrique_sessions() as db:
        definir_tenant(db, tid)
        entrees = db.scalars(select(EntreeAudit)).all()
        texte_audit = json.dumps([e.details for e in entrees], ensure_ascii=False)
        assert "NomSecretEfface" not in texte_audit
        assert "DZ8200001" not in texte_audit

    # 2. Politique de conservation automatisée (purge des dossiers archivés expirés)
    r_pol = client.put(
        "/api/v1/abonnement/politique-conservation",
        json={"duree_conservation_jours": 90},
    )
    assert r_pol.status_code == 200
    assert r_pol.json()["duree_conservation_jours"] == 90

    cand_ancien = _creer_candidat(client, nom="ArchiveAncienne", passeport="DZ8200002")
    doc_ancien = _televerser_piece_pdf(client, cand_ancien["id"])
    client.post(f"/api/v1/candidats/{cand_ancien['id']}/archiver")

    cand_recent = _creer_candidat(client, nom="ArchiveRecente", passeport="DZ8200003")
    _televerser_piece_pdf(client, cand_recent["id"])
    client.post(f"/api/v1/candidats/{cand_recent['id']}/archiver")

    # On recule la date d'archivage de `cand_ancien` à 120 jours (> 90 jours)
    with fabrique_sessions() as db:
        definir_tenant(db, tid)
        c_old = db.get(Candidat, uuid.UUID(cand_ancien["id"]))
        c_old.archive_le = maintenant_utc() - timedelta(days=120)
        doc_old_orm = db.get(DocumentCandidat, uuid.UUID(doc_ancien["id"]))
        chemin_bin_ancien = (
            parametres_test.dossier_stockage / doc_old_orm.chemin_stockage_relatif
        ).resolve()
        assert chemin_bin_ancien.exists()
        db.commit()

    r_purge = client.post("/api/v1/conformite/purger-archives-expirees")
    assert r_purge.status_code == 200
    res_purge = r_purge.json()
    assert res_purge["nb_dossiers_purges"] == 1
    assert res_purge["nb_fichiers_chiffres_supprimes"] >= 1
    assert not chemin_bin_ancien.exists()

    # L'archive ancienne est purgée (404), mais l'archive récente (0 jour) est intacte (200)
    assert client.get(f"/api/v1/candidats/{cand_ancien['id']}").status_code == 404
    assert client.get(f"/api/v1/candidats/{cand_recent['id']}").status_code == 200


def test_sauvegardes_chiffrees_aes_gcm_isolation_inter_bureaux_et_hsts_production(
    application,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
    parametres_test,
    tmp_path,
) -> None:
    bureau_a, bureau_b = deux_bureaux
    client_a, _ = connecter_client(application, bureau_a.admin.email)
    client_b, _ = connecter_client(application, bureau_b.admin.email)
    tid_a = str(bureau_a.bureau.id)
    tid_b = str(bureau_b.bureau.id)

    cand_a = _creer_candidat(client_a, nom="Mansouri", passeport="DZ8300001")
    _televerser_piece_pdf(client_a, cand_a["id"])

    # Création d'une sauvegarde chiffrée AES-256-GCM pour le Bureau A
    r_sav = client_a.post("/api/v1/sauvegardes")
    assert r_sav.status_code == 201
    sav = r_sav.json()
    nom_fichier = sav["nom_fichier"]
    assert nom_fichier.endswith(".be.enc")
    assert sav["nb_candidats"] == 1
    assert sav["nb_documents"] == 1

    # Vérification d'intégrité par le Bureau A -> valide
    r_verif_a = client_a.get(f"/api/v1/sauvegardes/{nom_fichier}/verifier")
    assert r_verif_a.status_code == 200
    assert r_verif_a.json()["integrite_valide"] is True

    # Copie physique de l'archive du Bureau A dans le répertoire du Bureau B :
    # Grâce à l'AAD AES-256-GCM lié au `tenant_id`, le Bureau B ne peut pas la valider/déchiffrer !
    chemin_a = parametres_test.dossier_sauvegardes / tid_a / nom_fichier
    dossier_b = parametres_test.dossier_sauvegardes / tid_b
    dossier_b.mkdir(parents=True, exist_ok=True)
    shutil.copy2(chemin_a, dossier_b / nom_fichier)

    r_verif_b = client_b.get(f"/api/v1/sauvegardes/{nom_fichier}/verifier")
    assert r_verif_b.status_code == 200
    assert r_verif_b.json()["integrite_valide"] is False
    assert r_verif_b.json()["nb_candidats"] == 0

    # Altération d'un octet du fichier chiffré du Bureau A -> détection immédiate par GCM
    octets = bytearray(chemin_a.read_bytes())
    octets[-1] ^= 0xFF
    chemin_a.write_bytes(bytes(octets))

    r_corrompu = client_a.get(f"/api/v1/sauvegardes/{nom_fichier}/verifier")
    assert r_corrompu.status_code == 200
    assert r_corrompu.json()["integrite_valide"] is False

    # Vérification du durcissement HTTPS / HSTS lorsque `Environnement.PRODUCTION` est actif
    cfg_prod = Parametres(
        environnement=Environnement.PRODUCTION,
        url_base_donnees=parametres_test.url_base_donnees,
        cookie_securise=True,
        cle_maitresse_base64=parametres_test.cle_maitresse_base64,
        dossier_stockage=tmp_path / "prod_docs",
        dossier_sauvegardes=tmp_path / "prod_sav",
    )
    app_prod = creer_application(cfg_prod)
    with TestClient(app_prod) as client_prod:
        r_sante = client_prod.get("/api/v1/sante")
        assert r_sante.status_code == 200
        assert (
            r_sante.headers.get("Strict-Transport-Security")
            == "max-age=63072000; includeSubDomains; preload"
        )
        assert client_prod.get("/docs").status_code == 404
        assert client_prod.get("/demo/campus-france").status_code == 404
