"""Déductions vérifiables (P2) et projet professionnel (P3) : API, isolation, audit et journaux
sans identité, sortie IA sans identité, validation humaine. Données synthétiques."""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.chiffrement import chiffrer_champ
from app.db.tenant import definir_tenant
from app.modeles.extraction_document import ExtractionDocument, StatutExtraction
from app.modeles.journal_audit import EntreeAudit
from app.modeles.point_fort import PointFort
from app.services.llm import ReponseLLM, obtenir_client_llm_optionnel
from tests import corpus_synthetique as corpus
from tests.conftest import DonneesBureauTest, connecter_client

NOM, PRENOM, PASSEPORT = "Eriksson", "Annamaria", "L898902C3"
EXTRAIT_MOY = "Moyenne generale : 14,52 / 20"
EXTRAIT_TCF = "Niveau obtenu : B2"
AUJOURDHUI = date.today()


class FauxLLM:
    def __init__(self, texte: str) -> None:
        self.texte, self.recus = texte, []

    def generer(self, *, systeme: str, message: str, outil: Any = None, max_tokens: int = 0, images: Any = None) -> ReponseLLM:
        self.recus.append(systeme + "\n" + message)
        return ReponseLLM(texte=self.texte)


@pytest.fixture()
def ctx(application: FastAPI, deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest]) -> Iterator[dict]:
    a, b = deux_bureaux
    client_a, _ = connecter_client(application, a.employe.email)
    client_b, _ = connecter_client(application, b.employe.email)
    client_l, _ = connecter_client(application, a.lecteur.email)
    try:
        yield {"app": application, "a": a, "client_a": client_a, "client_b": client_b, "client_l": client_l}
    finally:
        application.dependency_overrides.pop(obtenir_client_llm_optionnel, None)


def _candidat(client: TestClient, **extra: Any) -> str:
    rep = client.post("/api/v1/candidats", json={"nom": NOM, "prenom": PRENOM, "numero_passeport": PASSEPORT, **extra})
    assert rep.status_code == 201, rep.text
    return rep.json()["id"]


def _document(client: TestClient, cid: str, type_piece: str) -> str:
    rep = client.post(
        f"/api/v1/candidats/{cid}/documents", data={"type_piece": type_piece},
        files={"fichier": (f"{uuid.uuid4().hex}.pdf", corpus.pdf_factice([uuid.uuid4().hex]), "application/pdf")},
    )
    assert rep.status_code == 201, rep.text
    return rep.json()["id"]


def _extraction(c: dict, cid: str, did: str, champ: str, valeur: str, extrait: str,
                statut: StatutExtraction = StatutExtraction.VALIDE_HUMAIN) -> None:
    app = c["app"]
    with app.state.fabrique_sessions() as db:
        definir_tenant(db, c["a"].bureau.id)
        cle, tid = app.state.cle_maitresse, c["a"].bureau.id
        db.add(ExtractionDocument(
            id=uuid.uuid4(), tenant_id=tid, document_id=uuid.UUID(did), candidat_id=uuid.UUID(cid), champ=champ,
            valeur_chiffree=chiffrer_champ(cle, tid, "extraction_valeur", valeur),
            extrait_chiffre=chiffrer_champ(cle, tid, "extraction_extrait", extrait),
            page=1, source="A", confiance=0.9, statut=statut,
        ))
        db.commit()


def _dossier_complet(c: dict, date_tcf: str | None = None) -> str:
    cl = c["client_a"]
    cid = _candidat(cl, programme_vise="Master en informatique")
    releve = _document(cl, cid, "releve_notes_bac")
    _extraction(c, cid, releve, "moyenne_generale", "14.52", EXTRAIT_MOY)
    cert = _document(cl, cid, "resultats_test_langue")
    _extraction(c, cid, cert, "certificat_langue_type", "TCF", "TCF Canada")
    _extraction(c, cid, cert, "niveau_francais", "B2", EXTRAIT_TCF)
    if date_tcf:
        _extraction(c, cid, cert, "certificat_langue_date", date_tcf, "Date de passation : " + date_tcf)
    return cid


def _calculer(c: dict, cid: str) -> dict:
    rep = c["client_a"].post(f"/api/v1/candidats/{cid}/deductions/calculer")
    assert rep.status_code == 200, rep.text
    return rep.json()


def _confirmer_tout(c: dict, cid: str) -> list[dict]:
    pts = _calculer(c, cid)["points_forts"]
    for p in pts:
        if p["alerte"] != "certificat_expire":
            assert c["client_a"].post(f"/api/v1/candidats/{cid}/points-forts/{p['id']}/confirmer").status_code == 200
    return pts


def _projet_modele_complet(c: dict, cid: str) -> dict:
    """Génère le modèle, retire les marqueurs : texte validable et factuel."""
    cl = c["client_a"]
    p = cl.post(f"/api/v1/candidats/{cid}/projet-professionnel/generer").json()
    texte = re.sub(r"\[À COMPLÉTER[^\]]*\]", "", p["texte"]) + " Je souhaite devenir développeur."
    rep = cl.put(f"/api/v1/candidats/{cid}/projet-professionnel", json={"texte": texte, "version": p["version"]})
    assert rep.status_code == 200, rep.text
    return rep.json()


# ------------------------------------------------------------------ P2
def test_chaque_point_fort_cite_sa_piece(ctx: dict) -> None:
    cid = _dossier_complet(ctx, "2025-12-01")
    pts = _calculer(ctx, cid)["points_forts"]
    assert {p["regle"] for p in pts} == {"moyenne_generale", "certificat_langue"}
    for p in pts:
        assert p["document_id"] and p["extrait"] and p["statut"] == "a_verifier"
    moy = next(p for p in pts if p["regle"] == "moyenne_generale")
    assert moy["texte"] == "Moyenne générale de 14,52/20" and moy["extrait"] == EXTRAIT_MOY and moy["page"] == 1
    langue = next(p for p in pts if p["regle"] == "certificat_langue")
    assert "B2" in langue["texte"] and "TCF" in langue["texte"] and langue["champ_fiche"] == "niveau_francais"


def test_rien_sans_extraction_confirmee(ctx: dict) -> None:
    cl = ctx["client_a"]
    cid = _candidat(cl)
    did = _document(cl, cid, "releve_notes_bac")
    _extraction(ctx, cid, did, "moyenne_generale", "15", EXTRAIT_MOY, StatutExtraction.A_VERIFIER)
    _extraction(ctx, cid, _document(cl, cid, "releve_notes_bac"), "moyenne_generale", "16", EXTRAIT_MOY, StatutExtraction.REJETE)
    assert _calculer(ctx, cid)["points_forts"] == []
    _extraction(ctx, cid, _document(cl, cid, "releve_notes_bac"), "moyenne_generale", "17", EXTRAIT_MOY, StatutExtraction.AUTO)
    assert _calculer(ctx, cid)["points_forts"] == []  # une lecture « auto » seule n'est pas confirmée (règles 1 et 4)
    _extraction(ctx, cid, _document(cl, cid, "releve_notes_bac"), "moyenne_generale", "18", EXTRAIT_MOY, StatutExtraction.VALIDE_HUMAIN)
    assert len(_calculer(ctx, cid)["points_forts"]) == 1


def test_certificat_tcf_expire_signale_et_non_confirmable(ctx: dict) -> None:
    cid = _dossier_complet(ctx, "2020-01-15")
    langue = next(p for p in _calculer(ctx, cid)["points_forts"] if p["regle"] == "certificat_langue")
    assert langue["alerte"] == "certificat_expire" and "expiré" in langue["texte"]
    cl = ctx["client_a"]
    assert cl.post(f"/api/v1/candidats/{cid}/points-forts/{langue['id']}/confirmer").status_code == 422


def test_certificat_sans_date_ou_autre_type_validite_non_verifiable(ctx: dict) -> None:
    cid = _dossier_complet(ctx)  # TCF sans date
    langue = next(p for p in _calculer(ctx, cid)["points_forts"] if p["regle"] == "certificat_langue")
    assert langue["alerte"] == "date_absente" and "non vérifiable" in langue["texte"]


def test_niveau_applique_a_la_fiche_seulement_apres_confirmation_sans_ecraser(ctx: dict) -> None:
    cl = ctx["client_a"]
    cid = _dossier_complet(ctx, "2025-12-01")
    langue = next(p for p in _calculer(ctx, cid)["points_forts"] if p["regle"] == "certificat_langue")
    url = f"/api/v1/candidats/{cid}/points-forts/{langue['id']}/appliquer-niveau"
    assert cl.post(url).status_code == 422  # pas encore confirmé
    assert cl.get(f"/api/v1/candidats/{cid}").json()["niveau_francais"] is None
    cl.post(f"/api/v1/candidats/{cid}/points-forts/{langue['id']}/confirmer")
    assert cl.post(url).json()["resultat"] == "applique"
    assert cl.get(f"/api/v1/candidats/{cid}").json()["niveau_francais"] == "B2"
    assert cl.post(url).json()["resultat"] == "deja_identique"
    cl.patch(f"/api/v1/candidats/{cid}", json={"niveau_francais": "C1"})
    assert cl.post(url).status_code == 409  # jamais écrasé


def test_preuve_invalidee_si_l_extraction_disparait(ctx: dict) -> None:
    cid = _dossier_complet(ctx)
    pts = _confirmer_tout(ctx, cid)
    with ctx["app"].state.fabrique_sessions() as db:
        definir_tenant(db, ctx["a"].bureau.id)
        for e in db.query(ExtractionDocument).filter(ExtractionDocument.champ == "moyenne_generale"):
            e.statut = StatutExtraction.REJETE
        db.commit()
    res = _calculer(ctx, cid)
    moy = next(p for p in res["points_forts"] if p["regle"] == "moyenne_generale")
    assert moy["statut"] == "rejete" and moy["alerte"] == "preuve_invalidee" and len(pts) == 2


def test_lecture_seule_ne_peut_ni_calculer_ni_confirmer_mais_lit(ctx: dict) -> None:
    cid = _dossier_complet(ctx)
    pts = _calculer(ctx, cid)["points_forts"]
    cl = ctx["client_l"]
    assert cl.post(f"/api/v1/candidats/{cid}/deductions/calculer").status_code == 403
    assert cl.post(f"/api/v1/candidats/{cid}/points-forts/{pts[0]['id']}/confirmer").status_code == 403
    assert cl.get(f"/api/v1/candidats/{cid}/points-forts").status_code == 200


def test_csrf_obligatoire_sur_ecriture(ctx: dict) -> None:
    cid = _dossier_complet(ctx)
    cl = ctx["client_a"]
    jeton = cl.headers.pop("X-CSRF-Token")
    assert cl.post(f"/api/v1/candidats/{cid}/deductions/calculer").status_code == 403
    assert cl.post(f"/api/v1/candidats/{cid}/projet-professionnel/generer").status_code == 403
    cl.headers["X-CSRF-Token"] = jeton


def test_isolation_tenant_points_forts_et_projet(ctx: dict) -> None:
    cid = _dossier_complet(ctx)
    pts = _confirmer_tout(ctx, cid)
    ctx["client_a"].post(f"/api/v1/candidats/{cid}/projet-professionnel/generer")
    b = ctx["client_b"]
    assert b.post(f"/api/v1/candidats/{cid}/deductions/calculer").status_code == 404
    assert b.get(f"/api/v1/candidats/{cid}/points-forts").status_code == 404
    assert b.post(f"/api/v1/candidats/{cid}/points-forts/{pts[0]['id']}/rejeter").status_code == 404
    assert b.get(f"/api/v1/candidats/{cid}/projet-professionnel").status_code == 404
    assert b.post(f"/api/v1/candidats/{cid}/projet-professionnel/generer").status_code == 404
    cid_b = _candidat(b)
    assert b.post(f"/api/v1/candidats/{cid_b}/points-forts/{pts[0]['id']}/rejeter").status_code == 404


def test_texte_et_extrait_chiffres_en_base(ctx: dict) -> None:
    cid = _dossier_complet(ctx)
    _calculer(ctx, cid)
    with ctx["app"].state.fabrique_sessions() as db:
        definir_tenant(db, ctx["a"].bureau.id)
        for p in db.query(PointFort):
            assert "14,52" not in p.texte_chiffre and "Moyenne" not in p.extrait_chiffre


# ------------------------------------------------------------------ P3
def test_modele_sans_ia_a_des_marqueurs_qui_bloquent_la_validation(ctx: dict) -> None:
    cl = ctx["client_a"]
    cid = _dossier_complet(ctx, "2025-12-01")
    _confirmer_tout(ctx, cid)
    p = cl.post(f"/api/v1/candidats/{cid}/projet-professionnel/generer").json()
    assert p["origine"] == "modele" and "[À COMPLÉTER" in p["texte"] and p["marqueurs_restants"]
    assert "14,52" in p["texte"] and not p["validable"]
    rep = cl.post(f"/api/v1/candidats/{cid}/projet-professionnel/valider", json={"version": p["version"]})
    assert rep.status_code == 422
    assert cl.get(f"/api/v1/candidats/{cid}/projet-professionnel").json()["statut"] == "brouillon"


def test_projet_complete_puis_valide_par_un_humain(ctx: dict) -> None:
    cl = ctx["client_a"]
    cid = _dossier_complet(ctx, "2025-12-01")
    _confirmer_tout(ctx, cid)
    p = _projet_modele_complet(ctx, cid)
    assert p["elements_a_verifier"] == [], p
    assert p["validable"] and p["version"] == 2
    assert ctx["client_l"].post(f"/api/v1/candidats/{cid}/projet-professionnel/valider", json={"version": 2}).status_code == 403
    assert cl.post(f"/api/v1/candidats/{cid}/projet-professionnel/valider", json={"version": 1}).status_code == 409
    ok = cl.post(f"/api/v1/candidats/{cid}/projet-professionnel/valider", json={"version": 2})
    assert ok.status_code == 200 and ok.json()["statut"] == "valide" and ok.json()["valide_par_id"]
    assert cl.post(f"/api/v1/candidats/{cid}/projet-professionnel/generer").status_code == 409  # pas d'écrasement
    modif = cl.put(f"/api/v1/candidats/{cid}/projet-professionnel", json={"texte": "Autre", "version": 2})
    assert modif.json()["statut"] == "brouillon" and modif.json()["version"] == 3


def test_sans_point_fort_confirme_rien_n_est_utilise(ctx: dict) -> None:
    cid = _dossier_complet(ctx, "2025-12-01")
    _calculer(ctx, cid)  # points non confirmés
    p = ctx["client_a"].post(f"/api/v1/candidats/{cid}/projet-professionnel/generer").json()
    assert "14,52" not in p["texte"] and p["nb_points_forts_utilises"] == 0


def test_fait_invente_detecte_et_validation_bloquee(ctx: dict) -> None:
    cl = ctx["client_a"]
    cid = _dossier_complet(ctx, "2025-12-01")
    _confirmer_tout(ctx, cid)
    ctx["app"].dependency_overrides[obtenir_client_llm_optionnel] = lambda: FauxLLM(
        "Avec une moyenne de 17,8/20, un DELF C1 et un master en droit, je vise ce programme."
    )
    p = cl.post(f"/api/v1/candidats/{cid}/projet-professionnel/generer").json()
    msgs = " ".join(p["elements_a_verifier"])
    for attendu in ("17.8", "DELF", "C1", "master"):
        assert attendu in msgs, attendu
    assert not p["validable"]
    assert cl.post(f"/api/v1/candidats/{cid}/projet-professionnel/valider", json={"version": p["version"]}).status_code == 422
    # le texte corrigé par l'humain (faits seulement) devient validable
    ok = cl.put(f"/api/v1/candidats/{cid}/projet-professionnel",
                json={"texte": "Avec une moyenne de 14,52/20 et un niveau B2 en TCF, je vise ce programme.", "version": p["version"]})
    assert ok.json()["validable"]


def test_sortie_ia_et_journaux_sans_identite(ctx: dict, caplog: pytest.LogCaptureFixture) -> None:
    cl = ctx["client_a"]
    cid = _dossier_complet(ctx, "2025-12-01")
    _confirmer_tout(ctx, cid)
    faux = FauxLLM(f"Moi, {PRENOM} {NOM}, je pars avec 14,52/20 et le passeport {PASSEPORT}.")
    ctx["app"].dependency_overrides[obtenir_client_llm_optionnel] = lambda: faux
    with caplog.at_level(logging.DEBUG):
        p = cl.post(f"/api/v1/candidats/{cid}/projet-professionnel/generer").json()
    assert len(faux.recus) == 1
    for secret in (NOM, PRENOM, PASSEPORT):
        assert secret.lower() not in faux.recus[0].lower()  # rien d'identifiant envoyé au modèle
        assert secret.lower() not in p["texte"].lower()  # ni conservé depuis la sortie du modèle
        assert secret.lower() not in caplog.text.lower()
    assert p["marqueurs_restants"] and not p["validable"]
    with ctx["app"].state.fabrique_sessions() as db:
        definir_tenant(db, ctx["a"].bureau.id)
        audits = [e for e in db.query(EntreeAudit) if e.action.startswith(("deductions.", "projet_professionnel.", "ia."))]
        assert {"deductions.calculer", "deductions.confirmer", "projet_professionnel.generer", "ia.appel"} <= {e.action for e in audits}
        brut = " ".join(str(e.details) for e in audits).lower()
        for secret in (NOM, PRENOM, PASSEPORT, "14,52", "niveau"):
            assert secret.lower() not in brut
