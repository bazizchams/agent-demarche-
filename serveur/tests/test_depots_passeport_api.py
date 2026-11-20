"""Dépôt d'un passeport sans fiche : propositions MRZ, confirmation humaine, doublon, isolation, purge, audit.
Tout est synthétique (spécimen OACI du corpus)."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.extractions import obtenir_lecteur_document
from app.db.base import maintenant_utc
from app.db.tenant import definir_tenant, sans_filtre_tenant
from app.modeles.depot_passeport import DepotPasseport
from app.modeles.extraction_document import ExtractionDocument
from app.modeles.journal_audit import EntreeAudit
from tests import corpus_synthetique as corpus
from tests.conftest import DonneesBureauTest, connecter_client
from tests.test_extractions_api import LecteurFactice

PII = ("ERIKSSON", "ANNA", "L898902C3", "1974-08-12", "740812", "2012-04-15", "120415")
VALEURS_CONFIRMEES = {
    "confirme": True,
    "nom": "ERIKSSON",
    "prenom": "ANNA MARIA",
    "date_naissance": "1974-08-12",
    "sexe": "F",
    "nationalite": "UTO",
    "numero_passeport": "L898902C3",
    "date_expiration_passeport": "2012-04-15",
}
URL = "/api/v1/depots-passeport"


@pytest.fixture()
def ctx(application: FastAPI, deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest]) -> Iterator[dict]:
    application.dependency_overrides[obtenir_lecteur_document] = lambda: LecteurFactice()
    a, b = deux_bureaux
    client_a, _ = connecter_client(application, a.employe.email)
    client_b, _ = connecter_client(application, b.employe.email)
    client_lecteur, _ = connecter_client(application, a.lecteur.email)
    try:
        yield {"a": a, "b": b, "client_a": client_a, "client_b": client_b, "lecteur": client_lecteur}
    finally:
        application.dependency_overrides.pop(obtenir_lecteur_document, None)


def _deposer(client: TestClient, texte: str = corpus.TEXTE_PASSEPORT_VALIDE):
    return client.post(URL, files={"fichier": ("scan.pdf", corpus.pdf_factice([texte]), "application/pdf")})


def _nb_candidats(client: TestClient) -> int:
    return client.get("/api/v1/candidats").json()["total"]


def _par_champ(depot: dict) -> dict[str, dict]:
    return {p["champ"]: p for p in depot["propositions"]}


# ------------------------------------------------------------------ MRZ valide : confirmation obligatoire
def test_mrz_valide_propose_sans_creer_puis_fiche_creee_apres_confirmation(ctx: dict) -> None:
    client = ctx["client_a"]
    rep = _deposer(client)
    assert rep.status_code == 201, rep.text
    depot = rep.json()
    assert depot["statut"] == "propose" and depot["saisie_manuelle_requise"] is False
    champs = _par_champ(depot)
    assert set(champs) == {
        "nom", "prenom", "date_naissance", "sexe", "nationalite", "numero_passeport", "date_expiration_passeport"
    }
    assert champs["numero_passeport"]["valeur"] == "L898902C3"
    assert champs["date_naissance"]["valeur"] == "1974-08-12"
    assert champs["nationalite"]["valeur"] == "UTO" and champs["sexe"]["valeur"] == "F"
    assert "L898902C36UTO" in champs["numero_passeport"]["extrait"]
    assert all(p["statut"] == "a_confirmer" for p in depot["propositions"])
    assert depot["candidat_existant_id"] is None
    assert _nb_candidats(client) == 0  # une proposition n'est pas une fiche

    refus = client.post(f"{URL}/{depot['id']}/creer-fiche", json={**VALEURS_CONFIRMEES, "confirme": False})
    assert refus.status_code == 422 and _nb_candidats(client) == 0

    rep = client.post(f"{URL}/{depot['id']}/creer-fiche", json=VALEURS_CONFIRMEES)
    assert rep.status_code == 201, rep.text
    corps = rep.json()
    fiche = corps["candidat"]
    assert (fiche["nom"], fiche["prenom"], fiche["numero_passeport"]) == ("ERIKSSON", "ANNA MARIA", "L898902C3")
    assert fiche["date_naissance"] == "1974-08-12" and fiche["sexe"] == "F" and fiche["nationalite"] == "UTO"
    assert fiche["date_expiration_passeport"] == "2012-04-15"
    assert corps["extractions_validees"] >= 6
    docs = client.get(f"/api/v1/candidats/{fiche['id']}/documents").json()
    assert [d["type_piece"] for d in docs] == ["passeport"] and docs[0]["id"] == corps["document_id"]
    extractions = client.get(f"/api/v1/candidats/{fiche['id']}/extractions").json()
    par = {e["champ"]: e for e in extractions}
    assert par["numero_passeport"]["statut"] == "valide_humain" and par["numero_passeport"]["applique_le"]
    assert par["nom"]["statut"] == "valide_humain"
    assert client.get(f"{URL}/{depot['id']}").status_code == 404  # dépôt consommé


def test_valeur_corrigee_par_l_humain_et_champ_omis_reste_vide(ctx: dict) -> None:
    client = ctx["client_a"]
    depot = _deposer(client).json()
    corps = {"confirme": True, "nom": "Eriksson-Lund", "prenom": "Anna Maria", "numero_passeport": "L898902C3"}
    rep = client.post(f"{URL}/{depot['id']}/creer-fiche", json=corps)
    assert rep.status_code == 201, rep.text
    fiche = rep.json()["candidat"]
    assert fiche["nom"] == "Eriksson-Lund"
    assert fiche["date_naissance"] is None and fiche["sexe"] is None and fiche["nationalite"] is None  # règle 4
    par = {e["champ"]: e for e in client.get(f"/api/v1/candidats/{fiche['id']}/extractions").json()}
    assert par["nom"]["statut"] == "valide_humain" and par["nom"]["motif"] == "corrige_humain"
    assert par["nom"]["valeur"] == "Eriksson-Lund"
    assert par["date_naissance"]["statut"] != "valide_humain"  # non confirmée : jamais appliquée


# ------------------------------------------------------------------ MRZ invalide
def test_mrz_invalide_aucune_proposition_saisie_manuelle(ctx: dict) -> None:
    client = ctx["client_a"]
    rep = _deposer(client, corpus.TEXTE_PASSEPORT_INVALIDE)
    assert rep.status_code == 201
    depot = rep.json()
    assert depot["statut"] == "saisie_manuelle" and depot["saisie_manuelle_requise"] is True
    assert depot["propositions"] == []
    assert any("manuellement" in a for a in depot["avertissements"])
    assert _nb_candidats(client) == 0
    rep = client.post(
        f"{URL}/{depot['id']}/creer-fiche", json={"confirme": True, "nom": "Saisi", "prenom": "Main"}
    )
    assert rep.status_code == 201
    fiche = rep.json()["candidat"]
    assert fiche["numero_passeport"] is None and fiche["date_naissance"] is None


def test_document_sans_mrz_saisie_manuelle(ctx: dict) -> None:
    depot = _deposer(ctx["client_a"], "Page sans zone lisible par machine.").json()
    assert depot["statut"] == "saisie_manuelle" and depot["propositions"] == []


def test_fichier_non_autorise_refuse(ctx: dict) -> None:
    rep = ctx["client_a"].post(URL, files={"fichier": ("x.pdf", b"MZ-pas-un-pdf", "application/pdf")})
    assert rep.status_code == 422


# ------------------------------------------------------------------ doublon
def test_doublon_passeport_conflit_avec_lien_et_rien_cree(ctx: dict) -> None:
    client = ctx["client_a"]
    existant = client.post(
        "/api/v1/candidats", json={"nom": "Autre", "prenom": "Etudiant", "numero_passeport": "L898902C3"}
    ).json()["id"]
    depot = _deposer(client).json()
    assert depot["candidat_existant_id"] == existant
    rep = client.post(f"{URL}/{depot['id']}/creer-fiche", json=VALEURS_CONFIRMEES)
    assert rep.status_code == 409
    corps = rep.json()
    assert corps["code"] == "passeport_deja_utilise"
    assert corps["candidat_id"] == existant and corps["lien"] == f"/api/v1/candidats/{existant}"
    assert "L898902C3" not in rep.text
    assert _nb_candidats(client) == 1
    assert client.get(f"/api/v1/candidats/{existant}/documents").json() == []
    assert client.get(f"{URL}/{depot['id']}").status_code == 200  # dépôt conservé


# ------------------------------------------------------------------ isolation et rôles
def test_isolation_entre_bureaux(ctx: dict) -> None:
    depot = _deposer(ctx["client_a"]).json()
    b = ctx["client_b"]
    assert b.get(f"{URL}/{depot['id']}").status_code == 404
    assert b.delete(f"{URL}/{depot['id']}").status_code == 404
    assert b.post(f"{URL}/{depot['id']}/creer-fiche", json=VALEURS_CONFIRMEES).status_code == 404
    assert _nb_candidats(b) == 0 and _nb_candidats(ctx["client_a"]) == 0
    assert ctx["client_a"].get(f"{URL}/{depot['id']}").status_code == 200


def test_lecture_seule_ne_peut_pas_deposer_ni_creer(ctx: dict) -> None:
    depot = _deposer(ctx["client_a"]).json()
    lecteur = ctx["lecteur"]
    assert _deposer(lecteur).status_code == 403
    assert lecteur.post(f"{URL}/{depot['id']}/creer-fiche", json=VALEURS_CONFIRMEES).status_code == 403


def test_csrf_obligatoire(application: FastAPI, ctx: dict) -> None:
    client_sans_csrf = TestClient(application)
    rep = client_sans_csrf.post(URL, files={"fichier": ("s.pdf", corpus.pdf_factice(["x"]), "application/pdf")})
    assert rep.status_code in (401, 403)


# ------------------------------------------------------------------ purge 24 h
def _vieillir(fabrique: sessionmaker[Session], bureau_id: uuid.UUID, depot_id: str, heures: int) -> None:
    with fabrique() as db:
        with sans_filtre_tenant(db):
            db.execute(
                update(DepotPasseport)
                .where(DepotPasseport.id == uuid.UUID(depot_id))
                .values(cree_le=maintenant_utc() - timedelta(hours=heures))
            )
            db.commit()


def _fichiers_depots(parametres_test) -> list[Path]:
    return list(Path(parametres_test.dossier_stockage).rglob("depots/*.bin"))


def test_purge_des_depots_de_plus_de_24h(ctx: dict, fabrique_sessions, parametres_test) -> None:
    client = ctx["client_a"]
    vieux = _deposer(client).json()["id"]
    recent = _deposer(client, corpus.TEXTE_PASSEPORT_INVALIDE).json()["id"]
    assert len(_fichiers_depots(parametres_test)) == 2
    _vieillir(fabrique_sessions, ctx["a"].bureau.id, vieux, 25)
    assert client.get(f"{URL}/{vieux}").status_code == 404  # expiré : introuvable même avant la purge
    assert len(_fichiers_depots(parametres_test)) == 1
    assert client.post(
        f"{URL}/{vieux}/creer-fiche", json=VALEURS_CONFIRMEES
    ).status_code == 404 and _nb_candidats(client) == 0
    assert client.get(f"{URL}/{recent}").status_code == 200


def test_purge_opportuniste_a_chaque_depot_tous_bureaux(ctx: dict, fabrique_sessions, parametres_test) -> None:
    vieux_b = _deposer(ctx["client_b"]).json()["id"]
    _vieillir(fabrique_sessions, ctx["b"].bureau.id, vieux_b, 30)
    _deposer(ctx["client_a"])  # un dépôt du bureau A déclenche la purge système
    with fabrique_sessions() as db, sans_filtre_tenant(db):
        ids = {str(i) for i in db.scalars(select(DepotPasseport.id))}
    assert vieux_b not in ids
    assert len(_fichiers_depots(parametres_test)) == 1


# ------------------------------------------------------------------ chiffrement et audit sans PII
def test_aucune_donnee_en_clair_ni_dans_l_audit(ctx: dict, fabrique_sessions, parametres_test) -> None:
    client = ctx["client_a"]
    depot = _deposer(client).json()
    client.post(f"{URL}/{depot['id']}/creer-fiche", json=VALEURS_CONFIRMEES)
    depot2 = _deposer(client).json()  # un second dépôt, conservé : on inspecte sa ligne
    with fabrique_sessions() as db:
        definir_tenant(db, ctx["a"].bureau.id)
        ligne = db.scalar(select(DepotPasseport).where(DepotPasseport.id == uuid.UUID(depot2["id"])))
        assert ligne is not None
        brut = json.dumps(
            [ligne.nom_fichier_chiffre, ligne.propositions_chiffrees, ligne.statut, ligne.chemin_stockage_relatif]
        )
        octets = (Path(parametres_test.dossier_stockage) / ligne.chemin_stockage_relatif).read_bytes()
        audits = [(a.action, json.dumps(a.details or {})) for a in db.scalars(select(EntreeAudit))]
        extractions = [e.valeur_chiffree + e.extrait_chiffre for e in db.scalars(select(ExtractionDocument))]
    for secret in PII:
        assert secret not in brut and secret.encode() not in octets
        assert all(secret not in d for _, d in audits)
        assert all(secret not in e for e in extractions)
    actions = {a for a, _ in audits}
    assert {"depot_passeport.depot", "depot_passeport.creer_fiche"} <= actions
