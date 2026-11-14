"""API de lecture des documents : extraction, revue humaine, application à la fiche, isolation,
chiffrement des valeurs et audit sans donnée personnelle. Tout est synthétique."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.extractions import obtenir_lecteur_document, obtenir_lecteur_vision
from app.db.tenant import definir_tenant
from app.modeles.extraction_document import ExtractionDocument
from app.modeles.journal_audit import EntreeAudit
from app.services import lecture_documents as lecture
from app.services.lecture_documents import ImagePage, PageTexte, ResultatLecture
from app.services.lecture_vision import LecteurVision
from app.services.llm import ReponseLLM
from tests import corpus_synthetique as corpus
from tests.conftest import DonneesBureauTest, connecter_client

PII = ("ERIKSSON", "ANNA MARIA", "L898902C3", "1974-08-12", "740812", "14,52")


class LecteurFactice:
    """Lit les faux PDF du corpus (texte brut après `%PDF-1.4\\n`, pages séparées par \\f)."""

    def lire_texte(self, contenu: bytes, type_mime: str) -> ResultatLecture:
        corps = contenu.split(b"\n", 1)[1].decode("utf-8")
        pages = tuple(
            PageTexte(numero=i, texte=t, origine="couche_texte", confiance=1.0)
            for i, t in enumerate(corps.split("\f"), start=1)
        )
        return ResultatLecture(pages=pages, avertissements=())

    def extraire_images(self, contenu: bytes, type_mime: str) -> list[ImagePage]:
        return [ImagePage(page=1, octets=b"\x89PNG-factice", type_mime="image/png")]


@pytest.fixture()
def contexte(application: FastAPI, deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest]) -> Iterator[dict]:
    application.dependency_overrides[obtenir_lecteur_document] = lambda: LecteurFactice()
    a, b = deux_bureaux
    client_a, _ = connecter_client(application, a.employe.email)
    client_b, _ = connecter_client(application, b.employe.email)
    try:
        yield {"app": application, "a": a, "b": b, "client_a": client_a, "client_b": client_b}
    finally:
        application.dependency_overrides.pop(obtenir_lecteur_document, None)
        application.dependency_overrides.pop(obtenir_lecteur_vision, None)


def _creer_candidat(client: TestClient, **extra: Any) -> str:
    corps = {"nom": "Eriksson", "prenom": "Anna", **extra}
    rep = client.post("/api/v1/candidats", json=corps)
    assert rep.status_code == 201, rep.text
    return rep.json()["id"]


def _deposer(client: TestClient, cid: str, type_piece: str, pages: list[str]) -> str:
    rep = client.post(
        f"/api/v1/candidats/{cid}/documents",
        data={"type_piece": type_piece},
        files={"fichier": (f"{uuid.uuid4().hex}.pdf", corpus.pdf_factice(pages), "application/pdf")},
    )
    assert rep.status_code == 201, rep.text
    return rep.json()["id"]


def _extraire(client: TestClient, cid: str, did: str) -> dict:
    rep = client.post(f"/api/v1/candidats/{cid}/documents/{did}/extraire")
    assert rep.status_code == 200, rep.text
    return rep.json()


def _par_champ(resultat: dict) -> dict[str, dict]:
    return {e["champ"]: e for e in resultat["extractions"]}


# ---------------------------------------------------------------------- extraction


def test_extraction_passeport_mrz_valide_sans_lecteur_b(contexte: dict) -> None:
    client = contexte["client_a"]
    cid = _creer_candidat(client)
    did = _deposer(client, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE])
    res = _extraire(client, cid, did)
    champs = _par_champ(res)
    assert res["lecteur_b_utilise"] is False
    assert res["classification"]["type_piece_propose"] == "passeport"
    assert champs["numero_passeport"]["valeur"] == "L898902C3"
    assert champs["numero_passeport"]["statut"] == "auto"
    assert champs["numero_passeport"]["source"] == "A"
    assert champs["numero_passeport"]["page"] == 1
    assert "L898902C36UTO" in champs["numero_passeport"]["extrait"]
    assert champs["nom"]["statut"] == "a_verifier" and champs["nom"]["motif"] == "double_lecture_absente"
    # Le type de pièce du document n'est jamais modifié par la lecture (garde D3).
    docs = client.get(f"/api/v1/candidats/{cid}/documents").json()
    assert [d["type_piece"] for d in docs] == ["passeport"]


def test_zero_valeur_par_defaut_sur_document_sans_information(contexte: dict) -> None:
    client = contexte["client_a"]
    cid = _creer_candidat(client)
    did = _deposer(client, cid, "passeport", ["Page presque vide, rien de lisible."])
    res = _extraire(client, cid, did)
    assert res["extractions"] == []
    assert client.get(f"/api/v1/candidats/{cid}/extractions").json() == []
    assert client.post(f"/api/v1/candidats/{cid}/extractions/appliquer").json()["appliques"] == []


def test_type_inconnu_et_confiance_basse_aucune_extraction_et_confirmation_requise(contexte: dict) -> None:
    client = contexte["client_a"]
    cid = _creer_candidat(client)
    did = _deposer(client, cid, "lettre_explicative", ["Texte libre sans rien de reconnaissable."])
    res = _extraire(client, cid, did)
    assert res["extractions"] == []
    assert res["classification"]["confirmation_humaine_requise"] is True
    assert any("confirm" in a.lower() for a in res["avertissements"])


def test_type_declare_inconnu_mais_contenu_reconnu_avec_confiance_haute_est_lu(contexte: dict) -> None:
    client = contexte["client_a"]
    cid = _creer_candidat(client)
    did = _deposer(client, cid, "autre_piece", [corpus.TEXTE_PASSEPORT_VALIDE])
    res = _extraire(client, cid, did)
    assert "numero_passeport" in _par_champ(res)
    docs = client.get(f"/api/v1/candidats/{cid}/documents").json()
    assert docs[0]["type_piece"] == "autre_piece"  # jamais réécrit


def test_type_declare_incoherent_avec_le_contenu_est_signale(contexte: dict) -> None:
    client = contexte["client_a"]
    cid = _creer_candidat(client)
    did = _deposer(client, cid, "releve_notes_bac", [corpus.TEXTE_PASSEPORT_VALIDE])
    res = _extraire(client, cid, did)
    assert any("incoh" in a.lower() for a in res["avertissements"])


def test_valeurs_et_extraits_chiffres_en_base_audit_et_journaux_sans_pii(
    contexte: dict, caplog: pytest.LogCaptureFixture
) -> None:
    client = contexte["client_a"]
    caplog.set_level(logging.DEBUG)
    cid = _creer_candidat(client)
    d1 = _deposer(client, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE])
    d2 = _deposer(client, cid, "releve_notes_bac", [corpus.TEXTE_RELEVE_BAC])
    _extraire(client, cid, d1)
    _extraire(client, cid, d2)

    moteur = contexte["app"].state.moteur
    with moteur.connect() as conn:
        lignes = conn.execute(text("SELECT * FROM extractions_documents")).mappings().all()
        audits = conn.execute(text("SELECT action, details FROM journal_audit")).all()
    assert lignes
    for ligne in lignes:
        assert ligne["valeur_chiffree"].startswith("v1:")
        assert ligne["extrait_chiffre"].startswith("v1:")
        brut = " ".join(str(v) for v in ligne.values())
        for secret in PII:
            assert secret not in brut
    assert any(a.action == "extraction.lancer" for a in audits)
    tout = " ".join(f"{a.action} {a.details}" for a in audits) + caplog.text
    for secret in PII:
        assert secret not in tout


def test_relecture_remplace_les_extractions_non_decidees_et_garde_les_decisions_humaines(contexte: dict) -> None:
    client = contexte["client_a"]
    cid = _creer_candidat(client)
    did = _deposer(client, cid, "releve_notes_bac", [corpus.TEXTE_RELEVE_BAC])
    premier = _par_champ(_extraire(client, cid, did))
    client.post(f"/api/v1/candidats/{cid}/extractions/{premier['moyenne_generale']['id']}/valider")
    second = _par_champ(_extraire(client, cid, did))
    assert second["moyenne_generale"]["id"] == premier["moyenne_generale"]["id"]
    assert second["moyenne_generale"]["statut"] == "valide_humain"
    assert len(client.get(f"/api/v1/candidats/{cid}/extractions").json()) == 1


# ---------------------------------------------------------------------- revue humaine


def test_valider_rejeter_corriger(contexte: dict) -> None:
    client = contexte["client_a"]
    cid = _creer_candidat(client)
    did = _deposer(client, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE])
    champs = _par_champ(_extraire(client, cid, did))
    base = f"/api/v1/candidats/{cid}/extractions"

    rep = client.post(f"{base}/{champs['nom']['id']}/valider")
    assert rep.status_code == 200 and rep.json()["statut"] == "valide_humain"

    rep = client.post(f"{base}/{champs['prenom']['id']}/rejeter")
    assert rep.status_code == 200 and rep.json()["statut"] == "rejete"

    rep = client.post(f"{base}/{champs['nationalite_code']['id']}/corriger", json={"valeur": "DZA"})
    assert rep.status_code == 200
    assert rep.json()["valeur"] == "DZA" and rep.json()["statut"] == "valide_humain"
    assert rep.json()["motif"] == "corrige_humain"

    rep = client.post(f"{base}/{champs['date_naissance']['id']}/corriger", json={"valeur": "1974-13-45"})
    assert rep.status_code == 422  # date impossible : jamais acceptée
    rep = client.post(f"{base}/{champs['date_naissance']['id']}/corriger", json={"valeur": "12/08/1974"})
    assert rep.status_code == 200 and rep.json()["valeur"] == "1974-08-12"  # saisie JJ/MM/AAAA normalisée

    audits = [
        a.action for a in _audits(contexte)
    ]
    assert {"extraction.valider", "extraction.rejeter", "extraction.corriger"} <= set(audits)


def _audits(contexte: dict) -> list[EntreeAudit]:
    fabrique: sessionmaker[Session] = contexte["app"].state.fabrique_sessions
    with fabrique() as db:
        definir_tenant(db, contexte["a"].bureau.id)
        from sqlalchemy import select

        return list(db.scalars(select(EntreeAudit)))


def test_valider_une_valeur_invalide_est_refuse(contexte: dict) -> None:
    client = contexte["client_a"]
    cid = _creer_candidat(client)
    did = _deposer(client, cid, "releve_notes_bac", ["Moyenne générale : 25/20"])
    champs = _par_champ(_extraire(client, cid, did))
    assert champs["moyenne_generale"]["motif"] == "moyenne_hors_bornes"
    rep = client.post(f"/api/v1/candidats/{cid}/extractions/{champs['moyenne_generale']['id']}/valider")
    assert rep.status_code == 422


def test_roles_et_csrf(contexte: dict, application: FastAPI) -> None:
    client = contexte["client_a"]
    cid = _creer_candidat(client)
    did = _deposer(client, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE])
    champs = _par_champ(_extraire(client, cid, did))
    url = f"/api/v1/candidats/{cid}/extractions/{champs['nom']['id']}/valider"

    lecteur, _ = connecter_client(application, contexte["a"].lecteur.email)
    assert lecteur.post(url).status_code == 403
    assert lecteur.post(f"/api/v1/candidats/{cid}/documents/{did}/extraire").status_code == 403
    assert lecteur.get(f"/api/v1/candidats/{cid}/extractions").status_code == 200  # lecture seule

    sans_csrf = TestClient(application)
    sans_csrf.cookies.update(client.cookies)
    assert sans_csrf.post(url).status_code == 403
    sans_auth = TestClient(application)
    assert sans_auth.post(url).status_code == 401


# ---------------------------------------------------------------------- application à la fiche


def test_appliquer_ne_prend_que_les_champs_confirmes_et_n_ecrase_jamais(contexte: dict) -> None:
    client = contexte["client_a"]
    cid = _creer_candidat(client, date_naissance="1980-01-01", nom="Eriksson")
    did = _deposer(client, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE])
    champs = _par_champ(_extraire(client, cid, did))
    base = f"/api/v1/candidats/{cid}/extractions"
    client.post(f"{base}/{champs['nom']['id']}/valider")  # nom identique à la fiche

    rapport = client.post(f"{base}/appliquer").json()
    appliques = {a["champ"] for a in rapport["appliques"]}
    conflits = {c["champ"] for c in rapport["conflits"]}
    assert appliques == {"numero_passeport", "date_expiration_passeport", "sexe"}
    assert conflits == {"date_naissance"}  # fiche déjà saisie (1980-01-01) : jamais écrasée
    assert rapport["a_verifier_restants"] >= 1  # prénom non confirmé

    fiche = client.get(f"/api/v1/candidats/{cid}").json()
    assert fiche["numero_passeport"] == "L898902C3"
    assert fiche["date_expiration_passeport"] == "2012-04-15"
    assert fiche["sexe"] == "F"
    assert fiche["date_naissance"] == "1980-01-01"
    assert fiche["prenom"] == "Anna"

    rapport2 = client.post(f"{base}/appliquer").json()
    assert rapport2["appliques"] == []  # idempotent
    liste = {e["champ"]: e for e in client.get(base).json()}
    assert liste["numero_passeport"]["applique_le"] is not None
    assert liste["date_naissance"]["applique_le"] is None


def test_appliquer_ignore_a_verifier_et_rejete(contexte: dict) -> None:
    client = contexte["client_a"]
    cid = _creer_candidat(client)
    did = _deposer(client, cid, "releve_notes_bac", [corpus.TEXTE_RELEVE_BAC])
    champs = _par_champ(_extraire(client, cid, did))
    assert champs["moyenne_generale"]["statut"] == "a_verifier"
    rapport = client.post(f"/api/v1/candidats/{cid}/extractions/appliquer").json()
    assert rapport["appliques"] == [] and rapport["a_verifier_restants"] == 1


def test_appliquer_niveau_de_langue_confirme(contexte: dict) -> None:
    client = contexte["client_a"]
    cid = _creer_candidat(client)
    did = _deposer(client, cid, "resultats_test_langue", [corpus.TEXTE_TCF])
    champs = _par_champ(_extraire(client, cid, did))
    assert champs["niveau_francais"]["statut"] == "a_verifier"
    client.post(f"/api/v1/candidats/{cid}/extractions/{champs['niveau_francais']['id']}/valider")
    rapport = client.post(f"/api/v1/candidats/{cid}/extractions/appliquer").json()
    assert [a["champ"] for a in rapport["appliques"]] == ["niveau_francais"]
    assert client.get(f"/api/v1/candidats/{cid}").json()["niveau_francais"] == "B2"


def test_appliquer_passeport_deja_utilise_par_un_autre_candidat_est_un_conflit(contexte: dict) -> None:
    client = contexte["client_a"]
    _creer_candidat(client, nom="Autre", prenom="Personne", numero_passeport="L898902C3")
    cid = _creer_candidat(client)
    did = _deposer(client, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE])
    _extraire(client, cid, did)
    rapport = client.post(f"/api/v1/candidats/{cid}/extractions/appliquer").json()
    assert "numero_passeport" in {c["champ"] for c in rapport["conflits"]}
    assert "numero_passeport" not in {a["champ"] for a in rapport["appliques"]}
    assert "date_expiration_passeport" in {a["champ"] for a in rapport["appliques"]}


# ---------------------------------------------------------------------- contrôles croisés, lot


def test_lot_porte_d_entree_completude_et_controles_croises(contexte: dict) -> None:
    client = contexte["client_a"]
    cid = _creer_candidat(client)
    _deposer(client, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE])
    _deposer(client, cid, "releve_notes_bac", [corpus.TEXTE_RELEVE_ANDERSSON])
    rep = client.post(f"/api/v1/candidats/{cid}/extractions/lot", params={"code_demarche": "campus_france"})
    assert rep.status_code == 200, rep.text
    corps = rep.json()
    assert len(corps["documents"]) == 2
    assert corps["completude"]["code_demarche"] == "campus_france"
    assert "diplome_bac" in corps["completude"]["pieces_manquantes_ou_invalides"]
    assert corps["dossier_complet"] is False
    assert corps["completude"]["pieces_manquantes_ou_invalides"]  # liste fournie avant traitement


def test_controles_croises_degradent_les_valeurs_auto_en_a_verifier(contexte: dict) -> None:
    client = contexte["client_a"]
    cid = _creer_candidat(client)
    l1, l2 = corpus.construire_mrz(
        nom="ANDERSSON", prenoms="PAUL", numero="XY7654321",
        naissance_aammjj="750812", sexe="M", expiration_aammjj="340101",
    )
    _deposer(client, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE])
    _deposer(client, cid, "autre_piece", [f"{l1}\n{l2}\n"])
    corps = client.post(f"/api/v1/candidats/{cid}/extractions/lot").json()
    codes = {a["code"] for a in corps["alertes"]}
    assert {"nom_discordant", "date_naissance_discordante"} <= codes
    tous = client.get(f"/api/v1/candidats/{cid}/extractions").json()
    assert all(e["statut"] != "auto" for e in tous if e["champ"] in {"nom", "date_naissance"})
    assert any(e["motif"] == "discordance_inter_pieces" for e in tous)
    rapport = client.post(f"/api/v1/candidats/{cid}/extractions/appliquer").json()
    assert "date_naissance" not in {a["champ"] for a in rapport["appliques"]}


def test_alerte_expiration_du_passeport(contexte: dict) -> None:
    client = contexte["client_a"]
    cid = _creer_candidat(client)
    did = _deposer(client, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE])  # expire en 2012
    res = _extraire(client, cid, did)
    assert "passeport_expire" in {a["code"] for a in res["alertes"]}


# ---------------------------------------------------------------------- lecteur B (vision)


class _VisionFactice:
    def __init__(self, champs: list[dict[str, Any]]) -> None:
        self.champs = champs

    def generer(self, **kw: Any) -> ReponseLLM:
        return ReponseLLM(texte="", outil={"champs": self.champs})


def test_discordance_ab_valeur_non_appliquee(contexte: dict) -> None:
    contexte["app"].dependency_overrides[obtenir_lecteur_vision] = lambda: LecteurVision(
        _VisionFactice(
            [{"champ": "numero_passeport", "valeur": "L898902C8", "page": 1, "extrait": corpus.MRZ_L2_VALIDE}]
        )
    )
    client = contexte["client_a"]
    cid = _creer_candidat(client)
    did = _deposer(client, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE])
    res = _extraire(client, cid, did)
    champ = _par_champ(res)["numero_passeport"]
    assert res["lecteur_b_utilise"] is True
    assert champ["statut"] == "a_verifier" and champ["motif"] == "discordance_ab"
    assert champ["valeur_alternative"] == "L898902C8"
    rapport = client.post(f"/api/v1/candidats/{cid}/extractions/appliquer").json()
    assert "numero_passeport" not in {a["champ"] for a in rapport["appliques"]}


def test_valeur_non_ancree_du_lecteur_b_rejetee_et_jamais_appliquee(contexte: dict) -> None:
    contexte["app"].dependency_overrides[obtenir_lecteur_vision] = lambda: LecteurVision(
        _VisionFactice([{"champ": "niveau_francais", "valeur": "C2", "page": 1, "extrait": "Niveau C2"}])
    )
    client = contexte["client_a"]
    cid = _creer_candidat(client)
    did = _deposer(client, cid, "resultats_test_langue", [corpus.TEXTE_DELF_B1])
    champs = _par_champ(_extraire(client, cid, did))
    assert champs["niveau_francais"]["valeur"] == "B1"  # lecture A conservée
    # B voit C2 mais l'ancrage échoue : valeur B jamais retenue ; la lecture A reste a_verifier.
    assert champs["niveau_francais"]["statut"] == "a_verifier"
    assert champs["niveau_francais"]["valeur_alternative"] == "C2"


def test_b_seul_non_ancre_est_rejete(contexte: dict) -> None:
    contexte["app"].dependency_overrides[obtenir_lecteur_vision] = lambda: LecteurVision(
        _VisionFactice([{"champ": "nom", "valeur": "FANTOME", "page": 1, "extrait": "Nom : FANTOME"}])
    )
    client = contexte["client_a"]
    cid = _creer_candidat(client)
    did = _deposer(client, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE])
    champs = _par_champ(_extraire(client, cid, did))
    # Le nom lu par A (MRZ) est ERIKSSON ; B propose FANTOME non ancré : alternative seulement.
    assert champs["nom"]["valeur"] == "ERIKSSON" and champs["nom"]["statut"] == "a_verifier"
    contexte["app"].dependency_overrides[obtenir_lecteur_vision] = lambda: LecteurVision(
        _VisionFactice([{"champ": "moyenne_generale", "valeur": "19", "page": 1, "extrait": "Moyenne : 19"}])
    )
    did2 = _deposer(client, cid, "releve_notes_bac", ["Rien de lisible ici."])
    res = _extraire(client, cid, did2)
    assert _par_champ(res)["moyenne_generale"]["statut"] == "rejete"
    assert _par_champ(res)["moyenne_generale"]["motif"] == "non_ancree"
    rapport = client.post(f"/api/v1/candidats/{cid}/extractions/appliquer").json()
    assert "moyenne_generale" not in {a["champ"] for a in rapport["appliques"]}


def test_vision_non_locale_refusee_au_niveau_api(contexte: dict) -> None:
    from app.core.config import obtenir_parametres

    app = contexte["app"]
    origine = app.dependency_overrides[obtenir_parametres]
    parametres = origine().model_copy(
        update={"vision_active": True, "vision_url_base": "https://api.distant.example/v1", "vision_modele": "m"}
    )
    client = contexte["client_a"]
    cid = _creer_candidat(client)
    did = _deposer(client, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE])
    app.dependency_overrides[obtenir_parametres] = lambda: parametres
    try:
        rep = client.post(f"/api/v1/candidats/{cid}/documents/{did}/extraire")
        assert rep.status_code == 503 and "local" in rep.json()["detail"]
    finally:
        app.dependency_overrides[obtenir_parametres] = origine


# ---------------------------------------------------------------------- lecteur réel / sans extra


def test_pdf_reel_de_bout_en_bout_avec_pypdf(application: FastAPI, deux_bureaux) -> None:
    pytest.importorskip("pypdf")
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.employe.email)
    cid = _creer_candidat(client)
    rep = client.post(
        f"/api/v1/candidats/{cid}/documents",
        data={"type_piece": "passeport"},
        files={"fichier": ("p.pdf", corpus.construire_pdf_texte([corpus.TEXTE_PASSEPORT_VALIDE]), "application/pdf")},
    )
    did = rep.json()["id"]
    champs = _par_champ(_extraire(client, cid, did))
    assert champs["numero_passeport"]["valeur"] == "L898902C3" and champs["numero_passeport"]["statut"] == "auto"


def test_sans_extra_lecture_api_renvoie_503_clair(
    application: FastAPI, deux_bureaux, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _absent() -> Any:
        raise ImportError("absent")

    monkeypatch.setattr(lecture, "_importer_pypdf", _absent)
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.employe.email)
    cid = _creer_candidat(client)
    rep = client.post(
        f"/api/v1/candidats/{cid}/documents",
        data={"type_piece": "passeport"},
        files={"fichier": ("p.pdf", corpus.construire_pdf_texte(["x"]), "application/pdf")},
    )
    rep = client.post(f"/api/v1/candidats/{cid}/documents/{rep.json()['id']}/extraire")
    assert rep.status_code == 503
    assert "lecture" in rep.json()["detail"] and "pip install" in rep.json()["detail"]


# ---------------------------------------------------------------------- isolation


def test_isolation_entre_bureaux_api(contexte: dict) -> None:
    ca, cb = contexte["client_a"], contexte["client_b"]
    cid = _creer_candidat(ca)
    did = _deposer(ca, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE])
    champs = _par_champ(_extraire(ca, cid, did))
    eid = champs["nom"]["id"]
    assert cb.get(f"/api/v1/candidats/{cid}/extractions").status_code == 404
    assert cb.post(f"/api/v1/candidats/{cid}/documents/{did}/extraire").status_code == 404
    assert cb.post(f"/api/v1/candidats/{cid}/extractions/{eid}/valider").status_code == 404
    assert cb.post(f"/api/v1/candidats/{cid}/extractions/appliquer").status_code == 404
    cid_b = _creer_candidat(cb, nom="Autre", prenom="Bureau")
    assert cb.post(f"/api/v1/candidats/{cid_b}/extractions/{eid}/valider").status_code == 404
    assert ca.get(f"/api/v1/candidats/{cid}/extractions/{eid}").status_code in (404, 405)
    assert [e["id"] for e in ca.get(f"/api/v1/candidats/{cid}/extractions").json() if e["champ"] == "nom"] == [eid]


def test_extractions_orm_invisibles_depuis_un_autre_bureau(contexte: dict) -> None:
    ca = contexte["client_a"]
    cid = _creer_candidat(ca)
    did = _deposer(ca, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE])
    _extraire(ca, cid, did)
    fabrique: sessionmaker[Session] = contexte["app"].state.fabrique_sessions
    from sqlalchemy import select

    with fabrique() as db_a:
        definir_tenant(db_a, contexte["a"].bureau.id)
        assert db_a.scalars(select(ExtractionDocument)).all()
    with fabrique() as db_b:
        definir_tenant(db_b, contexte["b"].bureau.id)
        assert db_b.scalars(select(ExtractionDocument)).all() == []
