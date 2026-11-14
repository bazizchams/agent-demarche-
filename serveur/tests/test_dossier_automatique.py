"""Dossier automatique (P7) : enchaînement sur le corpus synthétique, reprise idempotente, pièces manquantes,
aucune validation automatique (R1), isolation, rôles, CSRF, audit et journaux sans donnée personnelle."""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.v1.extractions import obtenir_lecteur_document, obtenir_lecteur_vision
from app.db.tenant import definir_tenant
from app.modeles.extraction_document import ExtractionDocument, StatutExtraction
from app.modeles.journal_audit import EntreeAudit
from app.modeles.point_fort import PointFort, StatutPointFort
from app.modeles.voeu_formation import StatutVoeu, VoeuFormation
from app.schemas.dossier_automatique import CODES_ETAPES
from tests import corpus_synthetique as corpus
from tests.conftest import DonneesBureauTest, connecter_client
from tests.test_extractions_api import LecteurFactice

PII = ("Eriksson", "ERIKSSON", "Anna", "L898902C3", "1974-08-12", "14,52", "14.52")
CLES_ETAPE = {"code", "libelle", "statut", "detail", "action_humaine", "lien_ecran", "compteurs"}
STATUTS = {"a_faire", "en_cours", "termine", "a_verifier", "bloque"}


@pytest.fixture()
def ctx(application: FastAPI, deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest]) -> Iterator[dict]:
    application.dependency_overrides[obtenir_lecteur_document] = lambda: LecteurFactice()
    a, b = deux_bureaux
    try:
        yield {
            "app": application, "a": a,
            "client_a": connecter_client(application, a.employe.email)[0],
            "client_b": connecter_client(application, b.employe.email)[0],
            "client_l": connecter_client(application, a.lecteur.email)[0],
        }
    finally:
        application.dependency_overrides.pop(obtenir_lecteur_document, None)
        application.dependency_overrides.pop(obtenir_lecteur_vision, None)


def _candidat(cl: TestClient) -> str:
    rep = cl.post("/api/v1/candidats", json={"nom": "Eriksson", "prenom": "Anna Maria"})
    assert rep.status_code == 201, rep.text
    return rep.json()["id"]


def _doc(cl: TestClient, cid: str, type_piece: str, pages: list[str]) -> str:
    rep = cl.post(
        f"/api/v1/candidats/{cid}/documents", data={"type_piece": type_piece},
        files={"fichier": (f"{uuid.uuid4().hex}.pdf", corpus.pdf_factice(pages), "application/pdf")},
    )
    assert rep.status_code == 201, rep.text
    return rep.json()["id"]


def _deposer_corpus(cl: TestClient, cid: str) -> None:
    _doc(cl, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE])
    _doc(cl, cid, "releve_notes_bac", [corpus.TEXTE_RELEVE_BAC])
    _doc(cl, cid, "resultats_test_langue", [corpus.TEXTE_TCF])


def _lancer(cl: TestClient, cid: str) -> dict:
    rep = cl.post(f"/api/v1/candidats/{cid}/dossier-automatique/lancer")
    assert rep.status_code == 200, rep.text
    return rep.json()


def _etat(cl: TestClient, cid: str) -> dict:
    rep = cl.get(f"/api/v1/candidats/{cid}/dossier-automatique/etat")
    assert rep.status_code == 200, rep.text
    return rep.json()


def _etape(etat: dict, code: str) -> dict:
    return next(e for e in etat["etapes"] if e["code"] == code)


def _confirmer_valeurs(cl: TestClient, cid: str) -> int:
    n = 0
    for e in cl.get(f"/api/v1/candidats/{cid}/extractions").json():
        if e["statut"] in ("auto", "a_verifier"):
            rep = cl.post(f"/api/v1/candidats/{cid}/extractions/{e['id']}/valider")
            assert rep.status_code == 200, rep.text
            n += 1
    return n


def _confirmer_points(cl: TestClient, cid: str) -> int:
    pts = [p for p in cl.get(f"/api/v1/candidats/{cid}/points-forts").json() if p["statut"] == "a_verifier"]
    for p in pts:
        assert cl.post(f"/api/v1/candidats/{cid}/points-forts/{p['id']}/confirmer").status_code == 200
    return len(pts)


def test_contrat_etat_candidat_vide(ctx: dict) -> None:
    cl = ctx["client_a"]
    cid = _candidat(cl)
    etat = _etat(cl, cid)
    assert set(etat) == {"candidat_id", "progression", "etapes", "pieces_manquantes"}
    assert etat["candidat_id"] == cid and etat["progression"] == 0
    assert tuple(e["code"] for e in etat["etapes"]) == CODES_ETAPES
    for e in etat["etapes"]:
        assert set(e) == CLES_ETAPE and e["statut"] in STATUTS
        assert all(isinstance(v, int) for v in e["compteurs"].values())
    assert _etape(etat, "pieces")["statut"] == "bloque" and _etape(etat, "pieces")["action_humaine"]
    assert "Photo d'identité aux normes" in etat["pieces_manquantes"]
    assert _etape(etat, "navigateur")["statut"] == "a_faire"


def test_enchainement_complet_s_arrete_a_chaque_validation_humaine(ctx: dict) -> None:
    cl = ctx["client_a"]
    cid = _candidat(cl)
    _deposer_corpus(cl, cid)

    etat = _lancer(cl, cid)  # lecture + classement auto / à vérifier
    assert _etape(etat, "lecture")["statut"] == "termine"
    revue = _etape(etat, "revue_valeurs")
    assert revue["statut"] == "a_verifier" and revue["compteurs"]["a_confirmer"] > 0
    assert revue["action_humaine"] == f"Confirmer {revue['compteurs']['a_confirmer']} valeurs lues"
    assert revue["compteurs"]["auto"] >= 1  # numéro de passeport (MRZ valide)
    assert _etape(etat, "points_forts")["statut"] == "a_faire"
    assert _etape(etat, "projet_professionnel")["statut"] == "a_faire"
    with ctx["app"].state.fabrique_sessions() as db:  # rien n'est validé à la place de l'humain
        definir_tenant(db, ctx["a"].bureau.id)
        assert not [e for e in db.scalars(select(ExtractionDocument)) if e.statut is StatutExtraction.VALIDE_HUMAIN]

    assert _confirmer_valeurs(cl, cid) > 0  # l'humain confirme
    etat = _lancer(cl, cid)
    assert _etape(etat, "revue_valeurs")["statut"] == "termine"
    assert _etape(etat, "fiche")["compteurs"]["valeurs_a_reporter"] == 0
    fiche = cl.get(f"/api/v1/candidats/{cid}").json()
    assert fiche["numero_passeport"] == "L898902C3" and fiche["niveau_francais"] == "B2"
    pf = _etape(etat, "points_forts")
    assert pf["statut"] == "a_verifier" and pf["compteurs"]["a_confirmer"] >= 1
    assert _etape(etat, "projet_professionnel")["statut"] == "a_faire"

    assert _confirmer_points(cl, cid) >= 1
    etat = _lancer(cl, cid)  # brouillon du projet : jamais validé par l'orchestrateur
    projet = _etape(etat, "projet_professionnel")
    assert projet["statut"] == "a_verifier" and "projet professionnel" in projet["action_humaine"]
    brouillon = cl.get(f"/api/v1/candidats/{cid}/projet-professionnel").json()
    assert brouillon["statut"] == "brouillon"
    assert _etape(etat, "voeux")["statut"] == "bloque"  # catalogue vide : action explicite
    assert _etape(etat, "lettres")["statut"] == "a_faire"

    assert cl.post("/api/v1/catalogue-formations/import-ecoles").status_code == 200
    etat = _etat(cl, cid)
    voeux = _etape(etat, "voeux")
    assert voeux["statut"] == "a_verifier" and voeux["compteurs"]["propositions"] > 0
    assert cl.get(f"/api/v1/candidats/{cid}/voeux").json() == []  # aucun vœu créé

    texte = "Je souhaite poursuivre mes études en informatique, mon objectif est de devenir ingénieure."
    rep = cl.put(f"/api/v1/candidats/{cid}/projet-professionnel", json={"texte": texte, "version": brouillon["version"]})
    assert rep.status_code == 200, rep.text
    rep = cl.post(f"/api/v1/candidats/{cid}/projet-professionnel/valider", json={"version": rep.json()["version"]})
    assert rep.status_code == 200, rep.text
    rep = cl.post(f"/api/v1/candidats/{cid}/voeux", json={"intitule": "Master Fictif", "etablissement": "Université Fictive", "niveau": "Master"})
    assert rep.status_code == 201, rep.text
    voeu_id = rep.json()["id"]

    etat = _lancer(cl, cid)  # le vœu retenu par l'humain reçoit un brouillon de lettre
    lettres = _etape(etat, "lettres")
    assert lettres["statut"] == "a_verifier" and lettres["compteurs"]["brouillons"] == 1
    assert lettres["action_humaine"] == "Relire et valider 1 lettre(s)"
    voeux_liste = cl.get(f"/api/v1/candidats/{cid}/voeux").json()
    assert len(voeux_liste) == 1 and voeux_liste[0]["statut"] == "brouillon" and voeux_liste[0]["motivation"]
    assert _etape(etat, "navigateur")["statut"] == "a_faire"
    assert _etape(etat, "voeux")["statut"] == "termine"
    assert voeu_id == voeux_liste[0]["id"]


def test_reprise_idempotente_sans_ecraser_les_decisions_humaines(ctx: dict) -> None:
    cl = ctx["client_a"]
    cid = _candidat(cl)
    _deposer_corpus(cl, cid)
    _lancer(cl, cid)
    exts = cl.get(f"/api/v1/candidats/{cid}/extractions").json()
    rejetee = next(e for e in exts if e["statut"] == "a_verifier")
    assert cl.post(f"/api/v1/candidats/{cid}/extractions/{rejetee['id']}/rejeter").status_code == 200
    _confirmer_valeurs(cl, cid)
    _lancer(cl, cid)
    _confirmer_points(cl, cid)
    premier = _lancer(cl, cid)
    projet = cl.get(f"/api/v1/candidats/{cid}/projet-professionnel").json()
    rep = cl.put(f"/api/v1/candidats/{cid}/projet-professionnel", json={"texte": "Mon texte humain.", "version": projet["version"]})
    version = rep.json()["version"]

    second = _lancer(cl, cid)
    troisieme = _lancer(cl, cid)
    assert second == troisieme
    assert [e["statut"] for e in second["etapes"]] == [e["statut"] for e in premier["etapes"]]
    apres = cl.get(f"/api/v1/candidats/{cid}/projet-professionnel").json()
    assert apres["texte"] == "Mon texte humain." and apres["version"] == version
    exts2 = {e["id"]: e["statut"] for e in cl.get(f"/api/v1/candidats/{cid}/extractions").json()}
    assert exts2[rejetee["id"]] == "rejete" and len(exts2) == len(exts)
    with ctx["app"].state.fabrique_sessions() as db:
        definir_tenant(db, ctx["a"].bureau.id)
        points = list(db.scalars(select(PointFort)))
        assert len({p.cle for p in points}) == len(points)
        assert all(p.statut is StatutPointFort.CONFIRME for p in points)
    assert _etat(cl, cid) == second  # l'état est recalculé de façon déterministe


def test_pieces_manquantes_listees_sans_rien_inventer(ctx: dict) -> None:
    cl = ctx["client_a"]
    cid = _candidat(cl)
    _doc(cl, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE])
    etat = _lancer(cl, cid)
    pieces = _etape(etat, "pieces")
    assert pieces["statut"] == "bloque" and pieces["action_humaine"] and pieces["compteurs"]["pieces_manquantes"] >= 4
    assert "Curriculum Vitae (CV)" in etat["pieces_manquantes"]
    assert any(p.startswith("Passeport") and "expiration" in p for p in etat["pieces_manquantes"])
    assert _etape(etat, "lecture")["statut"] == "termine"  # les pièces présentes sont lues quand même
    assert cl.get(f"/api/v1/candidats/{cid}").json()["date_expiration_passeport"] is None
    assert _etape(etat, "navigateur")["statut"] == "a_faire"


def test_aucune_validation_ni_voeu_automatique(ctx: dict) -> None:
    cl = ctx["client_a"]
    cid = _candidat(cl)
    _deposer_corpus(cl, cid)
    cl.post("/api/v1/catalogue-formations/import-ecoles")
    for _ in range(3):
        etat = _lancer(cl, cid)
    assert _etape(etat, "revue_valeurs")["statut"] == "a_verifier"
    assert _etape(etat, "points_forts")["statut"] == "a_faire"
    with ctx["app"].state.fabrique_sessions() as db:
        definir_tenant(db, ctx["a"].bureau.id)
        assert not list(db.scalars(select(VoeuFormation)))
        assert not [e for e in db.scalars(select(ExtractionDocument)) if e.statut is StatutExtraction.VALIDE_HUMAIN]
        assert not [p for p in db.scalars(select(PointFort)) if p.statut is StatutPointFort.CONFIRME]
    assert cl.get(f"/api/v1/candidats/{cid}/projet-professionnel").status_code == 404
    assert StatutVoeu.AJOUTE_AU_PANIER.value not in json.dumps(etat)


def test_isolation_roles_et_csrf(ctx: dict) -> None:
    cl = ctx["client_a"]
    cid = _candidat(cl)
    base = f"/api/v1/candidats/{cid}/dossier-automatique"
    assert ctx["client_b"].get(f"{base}/etat").status_code == 404
    assert ctx["client_b"].post(f"{base}/lancer").status_code == 404
    assert ctx["client_l"].get(f"{base}/etat").status_code == 200
    assert ctx["client_l"].post(f"{base}/lancer").status_code == 403
    jeton = cl.headers.pop("X-CSRF-Token")
    assert cl.post(f"{base}/lancer").status_code == 403
    cl.headers["X-CSRF-Token"] = jeton
    assert cl.get(f"{base}/etat?code_demarche=inconnue").status_code == 404
    assert TestClient(ctx["app"]).get(f"{base}/etat").status_code == 401


def test_audit_etat_et_journaux_sans_donnee_personnelle(ctx: dict, caplog: pytest.LogCaptureFixture) -> None:
    cl = ctx["client_a"]
    cid = _candidat(cl)
    _deposer_corpus(cl, cid)
    with caplog.at_level(logging.DEBUG):
        etat = _lancer(cl, cid)
        _confirmer_valeurs(cl, cid)
        etat2 = _lancer(cl, cid)
    for texte in (json.dumps(etat, ensure_ascii=False), json.dumps(etat2, ensure_ascii=False), caplog.text):
        for pii in PII:
            assert pii not in texte
    with ctx["app"].state.fabrique_sessions() as db:
        definir_tenant(db, ctx["a"].bureau.id)
        entrees = list(db.scalars(select(EntreeAudit).where(EntreeAudit.action == "dossier_automatique.lancer")))
        assert len(entrees) == 2
        tout = json.dumps([e.details for e in db.scalars(select(EntreeAudit))], ensure_ascii=False, default=str)
    for pii in PII:
        assert pii not in tout
