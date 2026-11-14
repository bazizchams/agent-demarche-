"""Lettres adaptées à chaque formation (P5) : faits du dossier, fiche officielle, écart honnête,
contrôle anti-invention, similarité, longueur, identité et isolation. Données synthétiques."""

from __future__ import annotations

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
from app.services import catalogue_formations
from app.services.fiche_formation import FicheEntree
from app.services.lettres_adaptees import (
    SEUIL_SIMILARITE,
    ContexteLettre,
    _organismes,
    avec_marqueur,
    controler_lettre,
    limite_caracteres,
    similarite,
)
from app.services.lettres_motivation import FaitsParcours, VoeuPourLettre
from app.services.llm import ReponseLLM, obtenir_client_llm_optionnel
from tests import corpus_synthetique as corpus
from tests.conftest import DonneesBureauTest, connecter_client

NOM, PRENOM, PASSEPORT = "Ouazzani-Testeur", "Tamazight", "ZZ7654321"
LORRAINE = ("Université de Lorraine", "Master Traitement automatique des langues")
INALCO = ("Inalco", "Master Langues et sociétés")


class ClientEcho:
    """Faux modèle : rédige une lettre à partir des blocs reçus (donc propre à chaque formation)."""

    def __init__(self, texte: str | None = None) -> None:
        self.texte, self.messages = texte, []

    def generer(self, *, systeme: str, message: str, outil: Any = None, max_tokens: int = 0, images: Any = None):
        self.messages.append(message)
        if self.texte is not None:
            return ReponseLLM(texte=self.texte)
        def bloc(nom: str) -> str:
            m = re.search(rf"<{nom}>\n(.*?)\n</{nom}>", message, re.S)
            return " ".join(x.lstrip("- ") for x in m.group(1).splitlines()) if m else ""
        intit = re.search(r"Intitulé : (.*)", message).group(1)
        etab = re.search(r"Établissement : (.*)", message).group(1)
        ecart = bloc("ecarts_a_reconnaitre")
        reconnu = "" if ecart.startswith("(non") else f" Je reconnais que {ecart}."
        return ReponseLLM(texte=(
            f"Madame, Monsieur,\n\nJe candidate à la formation « {intit} » de {etab}. "
            f"La fiche officielle indique : {bloc('specificites_formation')}.\n\n"
            f"Mes acquis : {bloc('points_forts')} {bloc('langues')}.{reconnu}\n\n[Prénom NOM]"
        ))


@pytest.fixture()
def ctx(application: FastAPI, deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest]) -> Iterator[dict]:
    a, b = deux_bureaux
    c = {"app": application, "a": a, "cl": connecter_client(application, a.employe.email)[0],
         "cb": connecter_client(application, b.employe.email)[0]}
    try:
        yield c
    finally:
        application.dependency_overrides.pop(obtenir_client_llm_optionnel, None)


def _extraction(c: dict, cid: str, did: str, champ: str, valeur: str, extrait: str) -> None:
    app = c["app"]
    with app.state.fabrique_sessions() as db:
        definir_tenant(db, c["a"].bureau.id)
        tid = c["a"].bureau.id
        db.add(ExtractionDocument(
            id=uuid.uuid4(), tenant_id=tid, document_id=uuid.UUID(did), candidat_id=uuid.UUID(cid), champ=champ,
            valeur_chiffree=chiffrer_champ(app.state.cle_maitresse, tid, "extraction_valeur", valeur),
            extrait_chiffre=chiffrer_champ(app.state.cle_maitresse, tid, "extraction_extrait", extrait),
            page=1, source="A", confiance=0.9, statut=StatutExtraction.VALIDE_HUMAIN,
        ))
        db.commit()


def _document(cl: TestClient, cid: str, type_piece: str) -> str:
    rep = cl.post(f"/api/v1/candidats/{cid}/documents", data={"type_piece": type_piece},
                  files={"fichier": (f"{uuid.uuid4().hex}.pdf", corpus.pdf_factice([uuid.uuid4().hex]), "application/pdf")})
    assert rep.status_code == 201, rep.text
    return rep.json()["id"]


def _fiche(c: dict, etab: str, intitule: str, **kw: Any) -> None:
    with c["app"].state.fabrique_sessions() as db:
        definir_tenant(db, c["a"].bureau.id)
        catalogue_formations.enregistrer_fiches(
            db, [FicheEntree(etablissement=etab, intitule=intitule, date_releve=date.today(), source="manuel", **kw)],
            acteur_id=None)


def _dossier(c: dict, projet_valide: bool = True) -> tuple[str, str, str]:
    """Candidat (B2 français, C1 anglais) : moyenne et TCF confirmés, projet validé, 2 fiches, 2 vœux."""
    cl = c["cl"]
    rep = cl.post("/api/v1/candidats", json={"nom": NOM, "prenom": PRENOM, "numero_passeport": PASSEPORT,
                                              "niveau_francais": "B2", "niveau_anglais": "C1"})
    assert rep.status_code == 201, rep.text
    cid = rep.json()["id"]
    _extraction(c, cid, _document(cl, cid, "releve_notes_bac"), "moyenne_generale", "14.52", "Moyenne generale : 14,52 / 20")
    cert = _document(cl, cid, "resultats_test_langue")
    _extraction(c, cid, cert, "certificat_langue_type", "TCF", "TCF Canada")
    _extraction(c, cid, cert, "niveau_francais", "B2", "Niveau obtenu : B2")
    _extraction(c, cid, cert, "certificat_langue_date", "2025-12-01", "Date de passation : 2025-12-01")
    for p in cl.post(f"/api/v1/candidats/{cid}/deductions/calculer").json()["points_forts"]:
        if p["alerte"] != "certificat_expire":
            assert cl.post(f"/api/v1/candidats/{cid}/points-forts/{p['id']}/confirmer").status_code == 200
    if projet_valide:
        p = cl.post(f"/api/v1/candidats/{cid}/projet-professionnel/generer").json()
        texte = re.sub(r"\[À COMPLÉTER[^\]]*\]", "", p["texte"]) + " Je souhaite devenir enseignant-chercheur."
        p = cl.put(f"/api/v1/candidats/{cid}/projet-professionnel", json={"texte": texte, "version": p["version"]}).json()
        assert cl.post(f"/api/v1/candidats/{cid}/projet-professionnel/valider", json={"version": p["version"]}).status_code == 200
    _fiche(c, *LORRAINE, francais_min="C1", anglais_min="B2", domaines=["Linguistique informatique"])
    _fiche(c, *INALCO, francais_min="B2", domaines=["Langues orientales"])
    voeux = []
    for etab, intit in (LORRAINE, INALCO):
        r = cl.post(f"/api/v1/candidats/{cid}/voeux", json={"intitule": intit, "etablissement": etab, "niveau": "Master 1"})
        assert r.status_code == 201, r.text
        voeux.append(r.json()["id"])
    return cid, voeux[0], voeux[1]


def _generer(c: dict, cid: str, vid: str, client: Any = None, faits: dict | None = None) -> Any:
    if client is not None:
        c["app"].dependency_overrides[obtenir_client_llm_optionnel] = lambda: client
    try:
        return c["cl"].post(f"/api/v1/candidats/{cid}/voeux/{vid}/lettre/generer", json=faits or {})
    finally:
        c["app"].dependency_overrides.pop(obtenir_client_llm_optionnel, None)


# ------------------------------------------------------------------ API
def test_modele_deux_formations_deux_lettres_differentes_et_ecart_honnete(ctx: dict) -> None:
    cid, v1, v2 = _dossier(ctx)
    r1, r2 = _generer(ctx, cid, v1), _generer(ctx, cid, v2)
    assert r1.status_code == r2.status_code == 200, r1.text
    l1, l2 = r1.json()["voeu"]["motivation"], r2.json()["voeu"]["motivation"]
    assert similarite(l1, l2) < SEUIL_SIMILARITE
    assert "« Master Traitement automatique des langues »" in l1 and "Université de Lorraine" in l1
    assert "Linguistique informatique" in l1 and "Langues orientales" in l2
    assert "14,52/20" in l1 and "B2" in l1 and "pièce : releve notes bac" in l1  # faits + preuve
    assert "Je souhaite devenir enseignant-chercheur" in l1  # projet validé
    assert "mon niveau actuel en français est B2" in l1 and "exige C1" in l1  # écart reconnu
    assert "exige C1" not in l2  # pas d'écart pour l'Inalco
    assert "[À COMPLÉTER" in l1 and r1.json()["origine"] == "modele"
    assert len(l2) <= 3000  # 1 page A4 pour l'Inalco
    assert ctx["cl"].post(f"/api/v1/candidats/{cid}/voeux/{v1}/valider").status_code == 422


def test_projet_non_valide_non_utilise(ctx: dict) -> None:
    cid, v1, _ = _dossier(ctx, projet_valide=False)
    rep = _generer(ctx, cid, v1)
    assert "enseignant-chercheur" not in rep.json()["voeu"]["motivation"]
    assert any("Projet professionnel non validé" in e for e in rep.json()["elements_a_verifier"])


def test_ia_lettres_propres_a_chaque_formation_validables_sans_identite(ctx: dict) -> None:
    cid, v1, v2 = _dossier(ctx)
    client = ClientEcho()
    r1, r2 = _generer(ctx, cid, v1, client), _generer(ctx, cid, v2, client)
    assert r1.status_code == r2.status_code == 200, r1.text
    assert r1.json()["origine"] == "ia"
    for secret in (NOM, PRENOM, PASSEPORT):
        assert all(secret not in m for m in client.messages)
    m1 = client.messages[0]
    assert "<specificites_formation>" in m1 and "exigé C1" in m1 and "14,52/20" in m1
    l1, l2 = r1.json()["voeu"]["motivation"], r2.json()["voeu"]["motivation"]
    assert similarite(l1, l2) < SEUIL_SIMILARITE
    assert f"{PRENOM} {NOM}" not in l1 + l2 or l1.endswith(f"{PRENOM} {NOM}")
    assert ctx["cl"].post(f"/api/v1/candidats/{cid}/voeux/{v2}/valider").status_code == 200


def test_fait_invente_detecte_et_validation_bloquee(ctx: dict) -> None:
    cid, v1, _ = _dossier(ctx)
    faux = ("Madame, Monsieur,\n\nLauréat du DELF C2 avec 18/20, ancien de l'Université de Paris, "
            "je candidate à la formation « Master Fantôme » de l'Université de Lorraine. "
            "Moyenne générale de 14,52/20.\n\n[Prénom NOM]")
    rep = _generer(ctx, cid, v1, ClientEcho(faux))
    corps = rep.json()
    txt = " ".join(corps["elements_a_verifier"])
    for attendu in ("« 18 »", "« C2 »", "« DELF »", "Université de Paris", "Master Fantôme"):
        assert attendu in txt, attendu
    assert "[À COMPLÉTER" in corps["voeu"]["motivation"]
    assert ctx["cl"].post(f"/api/v1/candidats/{cid}/voeux/{v1}/valider").status_code == 422


def test_ecart_non_mentionne_bloque_la_validation(ctx: dict) -> None:
    cid, v1, _ = _dossier(ctx)
    lettre = ("Madame, Monsieur,\n\nJe candidate à la formation « Master Traitement automatique des langues » "
              "de l'Université de Lorraine. Moyenne générale de 14,52/20. Français : niveau B2.\n\n[Prénom NOM]")
    rep = _generer(ctx, cid, v1, ClientEcho(lettre))
    assert any("n'est pas reconnu dans la lettre" in e for e in rep.json()["elements_a_verifier"])


def test_meme_lettre_pour_deux_voeux_signalee(ctx: dict) -> None:
    cid, v1, v2 = _dossier(ctx)
    lettre = ("Madame, Monsieur,\n\nJe candidate à la formation « Master Traitement automatique des langues » "
              "de l'Université de Lorraine, Linguistique informatique. Moyenne générale de 14,52/20. "
              "Mon français B2 et mon anglais C1 me permettent de suivre cette formation avec sérieux, "
              "et je reconnais que mon niveau actuel en français est B2 alors que C1 est exigé.\n\n[Prénom NOM]")
    _generer(ctx, cid, v1, ClientEcho(lettre))
    rep = _generer(ctx, cid, v2, ClientEcho(lettre))
    assert any("quasi identique" in e for e in rep.json()["elements_a_verifier"])


def test_limite_inalco_respectee_meme_pour_ia(ctx: dict) -> None:
    cid, _, v2 = _dossier(ctx)
    long = "Madame, Monsieur, " + "Je candidate avec sérieux. " * 130 + "\n\n[Prénom NOM]"
    rep = _generer(ctx, cid, v2, ClientEcho(long))
    assert rep.status_code == 422


def test_audit_sans_identite_et_isolation_bureau(ctx: dict) -> None:
    cid, v1, _ = _dossier(ctx)
    assert _generer(ctx, cid, v1, ClientEcho()).status_code == 200
    with ctx["app"].state.fabrique_sessions() as db:
        definir_tenant(db, ctx["a"].bureau.id)
        entrees = [e for e in db.query(EntreeAudit) if "lettre" in str(e.action) or "voeu" in str(e.action)]
        lignes = [str(e.details) for e in entrees]
        assert any(e.action == "voeu.lettre_generer" for e in entrees)
    assert all(s not in " ".join(lignes) for s in (NOM, PRENOM, PASSEPORT, "14,52"))
    assert ctx["cb"].post(f"/api/v1/candidats/{cid}/voeux/{v1}/lettre/generer", json={}).status_code == 404


# ------------------------------------------------------------------ unitaires
def _contexte(**kw: Any) -> ContexteLettre:
    faits = FaitsParcours(parcours=["Licence de lettres (Université de Béjaïa, 2022)"],
                          points_forts=["Moyenne générale de 14,52/20"], langues=["Anglais : niveau C1"])
    base = dict(voeu=VoeuPourLettre("Master TAL", "Université de Lorraine", "Master 1"), faits=faits,
                faits_texte="\n".join([*faits.parcours, *faits.points_forts, *faits.langues,
                                       "Master TAL", "Université de Lorraine", "Master 1"]),
                distinctifs=["Master TAL", "Université de Lorraine"], limite=4000, ecarts_niveaux=[])
    base.update(kw)
    return ContexteLettre(**base)


def test_lettre_conforme_sans_element() -> None:
    texte = ("Madame, Monsieur, je candidate au « Master TAL » de l'Université de Lorraine. J'ai une licence "
             "de lettres (Université de Béjaïa, 2022) et une moyenne générale de 14,52/20 ; mon anglais est C1.")
    assert controler_lettre(texte, _contexte()) == []


@pytest.mark.parametrize("ajout,attendu", [
    ("Mention très bien avec 17/20.", "« 17 »"),
    ("Titulaire d'un master en robotique.", "robotique"),
    ("Certifié IELTS.", "IELTS"),
    ("J'ai étudié à l'École Polytechnique Fédérale.", "Établissement"),
    ("Niveau B2 en allemand.", "B2"),
])
def test_invention_detectee(ajout: str, attendu: str) -> None:
    base = ("Je candidate au « Master TAL » de l'Université de Lorraine, licence de lettres "
            "(Université de Béjaïa, 2022), moyenne générale de 14,52/20, anglais C1. ")
    assert any(attendu in e for e in controler_lettre(base + ajout, _contexte()))


def test_texte_anglais_et_peu_de_faits_signales() -> None:
    elements = controler_lettre("I apply to the Master TAL at Université de Lorraine with the best of my skills.",
                                _contexte())
    assert any("français" in e for e in elements) and any("deux faits" in e for e in elements)


def test_organismes_et_similarite_et_marqueur() -> None:
    assert _organismes("Je suis à l'Université de Lorraine. Mon parcours") == ["Université de Lorraine"]
    assert similarite("a b c d e f", "a b c d e f") == 1.0 and similarite("a b c d", "x y z w") == 0.0
    assert avec_marqueur("Lettre", []) == "Lettre" and "[À COMPLÉTER" in avec_marqueur("Lettre", ["X"])


def test_limites_par_fiche() -> None:
    f = FicheEntree(etablissement="X", intitule="Y", date_releve=date.today(), source="manuel",
                    pieces=["Lettre de motivation (1 page A4)"])
    assert limite_caracteres(f, "X") == 3000
    assert limite_caracteres(None, "Inalco") == 3000 and limite_caracteres(None, "Autre") == 4000
