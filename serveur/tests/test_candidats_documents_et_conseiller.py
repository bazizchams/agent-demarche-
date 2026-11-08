"""Tests de la Phase 2 :
- Chiffrement AES-256-GCM lié au tenant (AAD), DPAPI Windows et clé de secours imprimable
- Candidats : CRUD, règle 4 (zéro valeur par défaut inventée), chiffrement en base,
  recherche par index aveugle HMAC, archivage et restauration
- Documents : téléversement chiffré, contrôle des signatures binaires (PDF/PNG/JPEG),
  détection des doublons par empreinte HMAC-SHA256, téléchargement et suppression
- Référentiels YAML des démarches : pièces manquantes, pièces expirées et validité minimale
- Conseiller dossier : calcul du pourcentage d'acceptation / solidité, veille réglementaire
  et espace discussion chiffré
- Import sécurisé de dossier local : blocage d'une fiche JSON incohérente avec le nom du dossier
- Isolation stricte entre Bureau A et Bureau B sur toutes les routes de la Phase 2
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from app.core.chiffrement import (
    ENTETE_FICHIER_CHIFFRE,
    ErreurChiffrement,
    chiffrer_champ,
    dechiffrer_champ,
    deproteger_dpapi,
    exporter_cle_secours,
    importer_cle_secours,
    proteger_dpapi,
)
from app.core.config import Parametres
from app.core.erreurs import DonneesInvalides
from app.db.tenant import definir_tenant, sans_filtre_tenant
from app.modeles.candidat import Candidat
from app.modeles.document import DocumentCandidat
from app.schemas.candidat import CandidatCreation
from app.services.import_dossier import importer_dossier_local
from tests.conftest import DonneesBureauTest, connecter_client

EXEMPLE_PDF_VALIDE = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"
EXEMPLE_PNG_VALIDE = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"


def test_dpapi_cle_secours_et_isolation_cryptographique_aad() -> None:
    cle = os.urandom(32)

    # 1. Protection Windows DPAPI aller-retour
    protege = proteger_dpapi(cle)
    assert protege != cle
    assert deproteger_dpapi(protege) == cle

    # 2. Clé de secours imprimable + détection de toute faute de frappe
    code_secours = exporter_cle_secours(cle)
    assert importer_cle_secours(code_secours) == cle
    caractere_alt = "B" if code_secours[0] != "B" else "C"
    with pytest.raises(ValueError):
        importer_cle_secours(caractere_alt + code_secours[1:])

    # 3. Un champ chiffré pour le bureau A est indéchiffrable pour le bureau B
    #    ou pour une autre colonne (AAD).
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    jeton = chiffrer_champ(cle, tenant_a, "numero_passeport", "DZ99887766")
    assert jeton is not None and "DZ99887766" not in jeton
    assert dechiffrer_champ(cle, tenant_a, "numero_passeport", jeton) == "DZ99887766"

    with pytest.raises(ErreurChiffrement):
        dechiffrer_champ(cle, tenant_b, "numero_passeport", jeton)

    with pytest.raises(ErreurChiffrement):
        dechiffrer_champ(cle, tenant_a, "nom", jeton)


def test_candidat_regle4_aucune_valeur_inventee_chiffrement_recherche_et_archivage(
    application: FastAPI,
    fabrique_sessions: sessionmaker[Session],
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    donnees_a, donnees_b = deux_bureaux
    client_a, _ = connecter_client(application, donnees_a.admin.email)
    client_b, _ = connecter_client(application, donnees_b.admin.email)

    # 1. Règle 4 : création avec uniquement nom et prénom -> aucun champ inventé
    rep_min = client_a.post(
        "/api/v1/candidats",
        json={"nom": "BENALI", "prenom": "Amina"},
    )
    assert rep_min.status_code == 201, rep_min.text
    c_min = rep_min.json()
    assert c_min["sexe"] is None
    assert c_min["date_naissance"] is None
    assert c_min["lieu_naissance"] is None
    assert c_min["pays_residence"] is None
    assert c_min["numero_passeport"] is None

    # 2. Création d'un second candidat complet
    rep_complet = client_a.post(
        "/api/v1/candidats",
        json={
            "nom": "MÉZIANI",
            "prenom": "Yacine",
            "sexe": "M",
            "date_naissance": "2002-07-19",
            "lieu_naissance": "Béjaïa",
            "nationalite": "Algérienne",
            "pays_residence": "Algérie",
            "email": "yacine.meziani@etudiant-fictif.dz",
            "telephone": "+213 550 11 22 33",
            "numero_passeport": "P123456789",
            "date_expiration_passeport": (date.today() + timedelta(days=400)).isoformat(),
            "niveau_actuel": "Master 1 Informatique",
            "programme_vise": "Maîtrise en génie logiciel",
            "etablissement_vise": "Université Laval",
            "fonds_disponibles_eur": 18000,
            "consentement_signe": True,
        },
    )
    assert rep_complet.status_code == 201, rep_complet.text
    id_yacine = uuid.UUID(rep_complet.json()["id"])

    # 3. Vérification en base : aucune donnée personnelle en clair dans la ligne SQL
    with fabrique_sessions() as db, sans_filtre_tenant(db):
        ligne = db.get(Candidat, id_yacine)
        assert ligne is not None
        assert "MÉZIANI" not in ligne.nom_chiffre
        assert "Yacine" not in ligne.prenom_chiffre
        assert "2002-07-19" not in (ligne.date_naissance_chiffree or "")
        assert "yacine.meziani" not in (ligne.email_chiffre or "")
        assert "P123456789" not in (ligne.numero_passeport_chiffre or "")
        assert ligne.nom_chiffre.startswith("v1:")

    # 4. Doublon de numéro de passeport au sein du même bureau -> 409
    rep_doublon_pass = client_a.post(
        "/api/v1/candidats",
        json={
            "nom": "AUTRE",
            "prenom": "Candidat",
            "numero_passeport": "P123456789",
        },
    )
    assert rep_doublon_pass.status_code == 409

    # 5. Recherche par index aveugle (insensible aux accents et à la casse)
    for terme in ("meziani", "MÉZIANI", "yacine", "P123456789", "yacine.meziani@etudiant-fictif.dz"):
        rep_rech = client_a.get("/api/v1/candidats", params={"recherche": terme})
        assert rep_rech.status_code == 200
        assert rep_rech.json()["total"] == 1
        assert rep_rech.json()["elements"][0]["id"] == str(id_yacine)

    # 6. Isolation : le bureau B ne voit aucun candidat du bureau A et reçoit 404
    assert client_b.get("/api/v1/candidats").json()["total"] == 0
    assert client_b.get(f"/api/v1/candidats/{id_yacine}").status_code == 404
    assert (
        client_b.patch(f"/api/v1/candidats/{id_yacine}", json={"nom": "Pirate"}).status_code
        == 404
    )

    # 7. Archivage et restauration
    rep_arch = client_a.post(f"/api/v1/candidats/{id_yacine}/archiver")
    assert rep_arch.status_code == 200
    assert rep_arch.json()["statut"] == "archive"
    assert client_a.get("/api/v1/candidats").json()["total"] == 1  # seul BENALI reste actif

    rep_rest = client_a.post(f"/api/v1/candidats/{id_yacine}/restaurer")
    assert rep_rest.status_code == 200
    assert rep_rest.json()["statut"] == "actif"


def test_documents_chiffres_doublons_completude_evaluation_et_discussion(
    application: FastAPI,
    fabrique_sessions: sessionmaker[Session],
    parametres_test: Parametres,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    donnees_a, donnees_b = deux_bureaux
    client_a, _ = connecter_client(application, donnees_a.employe.email)
    client_lecteur_a, _ = connecter_client(application, donnees_a.lecteur.email)
    client_b, _ = connecter_client(application, donnees_b.admin.email)

    exp_valide = (date.today() + timedelta(days=365)).isoformat()
    exp_trop_proche = (date.today() + timedelta(days=60)).isoformat()

    rep_cand = client_a.post(
        "/api/v1/candidats",
        json={
            "nom": " rahmani ",
            "prenom": "Sara",
            "sexe": "F",
            "date_naissance": "2001-11-03",
            "lieu_naissance": "Oran",
            "nationalite": "Algérienne",
            "pays_residence": "Algérie",
            "email": "sara.rahmani@etudiant-fictif.dz",
            "telephone": "+213 551 00 11 22",
            "numero_passeport": "N987654321",
            "date_expiration_passeport": exp_valide,
            "niveau_actuel": "Licence 3",
            "programme_vise": "Master Informatique",
            "etablissement_vise": "Université de Montréal",
            "fonds_disponibles_eur": 18500,
        },
    )
    assert rep_cand.status_code == 201
    cid = rep_cand.json()["id"]

    # 1. Le rôle lecture_seule ne peut pas déposer de document (403)
    rep_interdit = client_lecteur_a.post(
        f"/api/v1/candidats/{cid}/documents",
        data={"type_piece": "passeport", "date_expiration": exp_valide},
        files={"fichier": ("passeport.pdf", EXEMPLE_PDF_VALIDE, "application/pdf")},
    )
    assert rep_interdit.status_code == 403

    # 2. Fichier exécutable déguisé en PDF -> refusé par contrôle des magic bytes (422)
    rep_faux_pdf = client_a.post(
        f"/api/v1/candidats/{cid}/documents",
        data={"type_piece": "passeport", "date_expiration": exp_valide},
        files={"fichier": ("malveillant.pdf", b"MZ\x90\x00executable", "application/pdf")},
    )
    assert rep_faux_pdf.status_code == 422

    # 3. Dépôt d'un passeport dont la validité restante est < 180 jours
    rep_doc_court = client_a.post(
        f"/api/v1/candidats/{cid}/documents",
        data={"type_piece": "passeport", "date_expiration": exp_trop_proche},
        files={"fichier": ("passeport_Sara_éè.pdf", EXEMPLE_PDF_VALIDE, "application/pdf")},
    )
    assert rep_doc_court.status_code == 201, rep_doc_court.text
    doc_id = rep_doc_court.json()["id"]

    # 4. Vérification que le fichier sur disque est chiffré et que le chemin ne contient aucun nom
    with fabrique_sessions() as db, sans_filtre_tenant(db):
        doc_orm = db.get(DocumentCandidat, uuid.UUID(doc_id))
        assert doc_orm is not None
        assert "Sara" not in doc_orm.chemin_stockage_relatif
        assert "Sara" not in doc_orm.nom_fichier_origine_chiffre
        chemin_bin = parametres_test.dossier_stockage / doc_orm.chemin_stockage_relatif
        octets_disque = chemin_bin.read_bytes()
        assert octets_disque.startswith(ENTETE_FICHIER_CHIFFRE)
        assert b"%PDF-" not in octets_disque

    # 5. Téléchargement déchiffré identique à l'original (et isolé du bureau B)
    rep_dl = client_a.get(f"/api/v1/candidats/{cid}/documents/{doc_id}/telecharger")
    assert rep_dl.status_code == 200
    assert rep_dl.content == EXEMPLE_PDF_VALIDE
    assert (
        client_b.get(f"/api/v1/candidats/{cid}/documents/{doc_id}/telecharger").status_code
        == 404
    )

    # 6. Détection de doublon par empreinte HMAC-SHA256 (même sous un autre nom ou type)
    rep_doublon = client_a.post(
        f"/api/v1/candidats/{cid}/documents",
        data={"type_piece": "preuve_financiere"},
        files={"fichier": ("autre_nom.pdf", EXEMPLE_PDF_VALIDE, "application/pdf")},
    )
    assert rep_doublon.status_code == 409

    # 7. Contrôle de complétude IRCC : signale la validité insuffisante du passeport (< 180j)
    #    et les autres pièces obligatoires manquantes
    rep_comp = client_a.get(f"/api/v1/candidats/{cid}/completude/ircc_permis_etudes")
    assert rep_comp.status_code == 200
    comp = rep_comp.json()
    assert comp["pret_pour_prerequis"] is False
    statuts_par_type = {p["type_piece"]: p["statut"] for p in comp["pieces"]}
    assert statuts_par_type["passeport"] == "validite_insuffisante"
    assert statuts_par_type["lettre_admission_dli"] == "manquante"

    # 8. Évaluation du pourcentage d'acceptation et espace discussion conseiller
    rep_eval = client_a.get(f"/api/v1/candidats/{cid}/evaluation/ircc_permis_etudes")
    assert rep_eval.status_code == 200
    ev = rep_eval.json()
    assert 0 <= ev["pourcentage_acceptation_estime"] <= 100
    assert ev["niveau_solidite"] == "incomplet_ou_bloquant"
    assert len(ev["veille_reglementaire"]) >= 3

    rep_disc = client_a.post(
        f"/api/v1/candidats/{cid}/discussion",
        json={
            "code_demarche": "ircc_permis_etudes",
            "message": "Quels sont les nouveaux prérequis financiers et que faire en priorité ?",
        },
    )
    assert rep_disc.status_code == 201, rep_disc.text
    echange = rep_disc.json()
    assert "20 635" in echange["reponse"]["contenu"]
    assert echange["reponse"]["score_solidite_pourcent"] == ev["pourcentage_acceptation_estime"]

    # L'historique de discussion est lisible par le bureau A mais invisible pour le bureau B
    rep_hist = client_a.get(f"/api/v1/candidats/{cid}/discussion")
    assert rep_hist.status_code == 200
    assert len(rep_hist.json()) == 2
    assert client_b.get(f"/api/v1/candidats/{cid}/discussion").status_code == 404

    # 9. Suppression du document à validité courte et dépôt de toutes les pièces IRCC valides
    assert client_a.delete(f"/api/v1/candidats/{cid}/documents/{doc_id}").status_code == 204
    pieces_ircc = [
        ("passeport", exp_valide),
        ("lettre_admission_dli", None),
        ("attestation_provinciale_pal_caq", exp_valide),
        ("preuve_financiere", None),
        ("photo_identite", None),
        ("formulaire_imm5645", None),
        ("lettre_explicative", None),
    ]
    for idx, (tp, exp_d) in enumerate(pieces_ircc):
        contenu_unique = EXEMPLE_PDF_VALIDE + f"% piece {idx}\n".encode("ascii")
        data_form = {"type_piece": tp}
        if exp_d:
            data_form["date_expiration"] = exp_d
        r = client_a.post(
            f"/api/v1/candidats/{cid}/documents",
            data=data_form,
            files={"fichier": (f"{tp}.pdf", contenu_unique, "application/pdf")},
        )
        assert r.status_code == 201, r.text

    rep_eval_complet = client_a.get(
        f"/api/v1/candidats/{cid}/evaluation/ircc_permis_etudes"
    )
    assert rep_eval_complet.status_code == 200
    ev_complet = rep_eval_complet.json()
    assert ev_complet["pret_pour_soumission_humaine"] is True
    assert ev_complet["pourcentage_acceptation_estime"] == 100
    assert ev_complet["niveau_solidite"] == "tres_solide"


def test_import_dossier_local_bloque_fiche_incoherente_et_importe_fichiers_qualifies(
    fabrique_sessions: sessionmaker[Session],
    parametres_test: Parametres,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
    tmp_path: Path,
) -> None:
    donnees_a, _ = deux_bureaux
    cle = os.urandom(32)

    # 1. Reproduction exacte de l'anomalie découverte en Phase 0 :
    #    un dossier "kara_abdeslam" contenant la fiche JSON de "KACI Salim"
    dossier_incoherent = tmp_path / "kara_abdeslam"
    dossier_incoherent.mkdir()
    (dossier_incoherent / "fiche_candidat.json").write_text(
        json.dumps({"nom": "KACI", "prenom": "Salim", "sexe": "M"}),
        encoding="utf-8",
    )
    (dossier_incoherent / "passeport_2026.pdf").write_bytes(EXEMPLE_PDF_VALIDE)
    (dossier_incoherent / "IMG_0001.pdf").write_bytes(EXEMPLE_PNG_VALIDE)

    with fabrique_sessions() as db:
        definir_tenant(db, donnees_a.bureau.id)

        # Sans correction d'identité, l'import est BLOQUÉ par sécurité
        with pytest.raises(DonneesInvalides):
            importer_dossier_local(
                db,
                chemin_dossier=dossier_incoherent,
                correspondance_types={"passeport_2026.pdf": "passeport"},
                acteur_id=donnees_a.admin.id,
                parametres=parametres_test,
                cle_maitresse=cle,
            )

        # Avec l'identité explicite corrigée et la qualification des pièces,
        # seul le fichier qualifié est importé et le fichier ambigu est signalé.
        resultat = importer_dossier_local(
            db,
            chemin_dossier=dossier_incoherent,
            correspondance_types={"passeport_2026.pdf": "passeport"},
            remplacer_identite=CandidatCreation(nom="KARA", prenom="Abdeslam"),
            acteur_id=donnees_a.admin.id,
            parametres=parametres_test,
            cle_maitresse=cle,
        )
        assert resultat.candidat.nom == "KARA"
        assert resultat.candidat.prenom == "Abdeslam"
        assert len(resultat.documents_importes) == 1
        assert resultat.documents_importes[0].type_piece == "passeport"
        assert resultat.fichiers_non_importes == ["IMG_0001.pdf"]
