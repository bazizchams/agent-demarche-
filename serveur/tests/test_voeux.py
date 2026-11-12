"""Voeux de formation : limites, statuts, isolation, chiffrement, audit sans texte de motivation."""

from __future__ import annotations

import json

from fastapi import FastAPI
from sqlalchemy import text

from app.db.tenant import definir_tenant
from app.modeles.journal_audit import EntreeAudit
from app.services.voeux import lister_voeux_pour_panier
from sqlalchemy import select
from tests.conftest import DonneesBureauTest, connecter_client

MOTIVATION = "Mon projet professionnel secret est la cryptographie appliquee."


def _candidat(client) -> str:
    rep = client.post("/api/v1/candidats", json={"nom": "TESTEUR", "prenom": "Fictif"})
    assert rep.status_code == 201, rep.text
    return rep.json()["id"]


def _corps(i: int = 1, **extra) -> dict:
    corps = {
        "intitule": f"Master Informatique {i}",
        "etablissement": f"Universite Fictive {i}",
        "niveau": "Master 1",
    }
    corps.update(extra)
    return corps


def _base(cid: str) -> str:
    return f"/api/v1/candidats/{cid}/voeux"


def test_creation_et_liste_triee(application: FastAPI, deux_bureaux) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.employe.email)
    cid = _candidat(client)
    r1 = client.post(_base(cid), json=_corps(1, motivation=MOTIVATION))
    assert r1.status_code == 201, r1.text
    assert r1.json()["rang"] == 1
    assert r1.json()["statut"] == "brouillon"
    assert r1.json()["voie"] == "hors_dap"
    assert r1.json()["nb_caracteres_motivation"] == len(MOTIVATION)
    r2 = client.post(_base(cid), json=_corps(2))
    assert r2.json()["rang"] == 2
    assert r2.json()["motivation"] is None
    liste = client.get(_base(cid)).json()
    assert [v["rang"] for v in liste] == [1, 2]
    assert liste[0]["motivation"] == MOTIVATION


def test_limite_de_7_et_doublon(application: FastAPI, deux_bureaux) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.admin.email)
    cid = _candidat(client)
    for i in range(1, 8):
        assert client.post(_base(cid), json=_corps(i)).status_code == 201
    assert client.post(_base(cid), json=_corps(8)).status_code == 409
    cid2 = _candidat(client)
    assert client.post(_base(cid2), json=_corps(1)).status_code == 201
    assert client.post(_base(cid2), json=_corps(1)).status_code == 409


def test_validation_exige_une_motivation(application: FastAPI, deux_bureaux) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.admin.email)
    cid = _candidat(client)
    vid = client.post(_base(cid), json=_corps()).json()["id"]
    assert client.post(f"{_base(cid)}/{vid}/valider").status_code == 422
    client.patch(f"{_base(cid)}/{vid}", json={"motivation": "   "})
    assert client.post(f"{_base(cid)}/{vid}/valider").status_code == 422


def test_motivation_trop_longue_refusee(application: FastAPI, deux_bureaux) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.admin.email)
    cid = _candidat(client)
    vid = client.post(_base(cid), json=_corps()).json()["id"]
    assert client.patch(f"{_base(cid)}/{vid}", json={"motivation": "x" * 4001}).status_code == 422
    assert client.patch(f"{_base(cid)}/{vid}", json={"motivation": "x" * 4000}).status_code == 200
    assert client.post(_base(cid), json=_corps(2, motivation="y" * 4001)).status_code == 422


def test_transitions_de_statut(application: FastAPI, deux_bureaux) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.admin.email)
    cid = _candidat(client)
    vid = client.post(_base(cid), json=_corps(motivation=MOTIVATION)).json()["id"]
    # brouillon -> marquer-ajoute refuse
    assert client.post(f"{_base(cid)}/{vid}/marquer-ajoute").status_code == 409
    rep = client.post(f"{_base(cid)}/{vid}/valider")
    assert rep.status_code == 200 and rep.json()["statut"] == "valide"
    # le panier ne contient que valide / ajoute_au_panier
    vid2 = client.post(_base(cid), json=_corps(2, motivation="autre")).json()["id"]
    panier = _panier(application, a, cid)
    assert [str(p["voeu_id"]) for p in panier] == [vid]
    assert panier[0]["motivation"] == MOTIVATION
    rep = client.post(f"{_base(cid)}/{vid}/marquer-ajoute")
    assert rep.json()["statut"] == "ajoute_au_panier"
    # modifier la motivation remet en brouillon
    rep = client.patch(f"{_base(cid)}/{vid}", json={"motivation": "nouveau texte"})
    assert rep.json()["statut"] == "brouillon"
    client.post(f"{_base(cid)}/{vid}/valider")
    # modifier l'intitule aussi
    rep = client.patch(f"{_base(cid)}/{vid}", json={"intitule": "Autre intitule"})
    assert rep.json()["statut"] == "brouillon"
    # modifier la justification ne change pas le statut
    client.post(f"{_base(cid)}/{vid}/valider")
    rep = client.patch(f"{_base(cid)}/{vid}", json={"justification": "Bon choix"})
    assert rep.json()["statut"] == "valide"
    assert vid2


def _panier(application: FastAPI, donnees: DonneesBureauTest, cid: str) -> list[dict]:
    import uuid

    with application.state.fabrique_sessions() as db:
        definir_tenant(db, donnees.bureau.id)
        return lister_voeux_pour_panier(db, uuid.UUID(cid), application.state.cle_maitresse)


def test_suppression_recompacte_et_rang_modifiable(application: FastAPI, deux_bureaux) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.admin.email)
    cid = _candidat(client)
    ids = [client.post(_base(cid), json=_corps(i)).json()["id"] for i in (1, 2, 3)]
    assert client.delete(f"{_base(cid)}/{ids[0]}").status_code == 204
    liste = client.get(_base(cid)).json()
    assert [(v["id"], v["rang"]) for v in liste] == [(ids[1], 1), (ids[2], 2)]
    client.patch(f"{_base(cid)}/{ids[2]}", json={"rang": 1})
    liste = client.get(_base(cid)).json()
    assert [v["id"] for v in liste] == [ids[2], ids[1]]
    assert [v["rang"] for v in liste] == [1, 2]


def test_isolation_entre_bureaux(application: FastAPI, deux_bureaux) -> None:
    a, b = deux_bureaux
    client_a, _ = connecter_client(application, a.admin.email)
    client_b, _ = connecter_client(application, b.admin.email)
    cid = _candidat(client_a)
    vid = client_a.post(_base(cid), json=_corps(motivation=MOTIVATION)).json()["id"]
    assert client_b.get(_base(cid)).status_code == 404
    assert client_b.post(_base(cid), json=_corps()).status_code == 404
    assert client_b.patch(f"{_base(cid)}/{vid}", json={"niveau": "M2"}).status_code == 404
    assert client_b.post(f"{_base(cid)}/{vid}/valider").status_code == 404
    assert client_b.delete(f"{_base(cid)}/{vid}").status_code == 404
    cid_b = _candidat(client_b)
    assert client_b.patch(f"{_base(cid_b)}/{vid}", json={"niveau": "M2"}).status_code == 404


def test_lecture_seule_refusee_en_ecriture(application: FastAPI, deux_bureaux) -> None:
    a, _ = deux_bureaux
    admin, _ = connecter_client(application, a.admin.email)
    cid = _candidat(admin)
    vid = admin.post(_base(cid), json=_corps(motivation=MOTIVATION)).json()["id"]
    lecteur, _ = connecter_client(application, a.lecteur.email)
    assert lecteur.get(_base(cid)).status_code == 200
    assert lecteur.post(_base(cid), json=_corps(2)).status_code == 403
    assert lecteur.patch(f"{_base(cid)}/{vid}", json={"niveau": "M2"}).status_code == 403
    assert lecteur.post(f"{_base(cid)}/{vid}/valider").status_code == 403
    assert lecteur.post(f"{_base(cid)}/{vid}/marquer-ajoute").status_code == 403
    assert lecteur.delete(f"{_base(cid)}/{vid}").status_code == 403


def test_motivation_chiffree_en_base_et_audit_sans_texte(
    application: FastAPI, deux_bureaux, fabrique_sessions
) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.admin.email)
    cid = _candidat(client)
    vid = client.post(_base(cid), json=_corps(motivation=MOTIVATION)).json()["id"]
    client.patch(f"{_base(cid)}/{vid}", json={"motivation": MOTIVATION + " suite"})
    client.post(f"{_base(cid)}/{vid}/valider")
    client.post(f"{_base(cid)}/{vid}/marquer-ajoute")
    client.delete(f"{_base(cid)}/{vid}")
    vid2 = client.post(_base(cid), json=_corps(2, motivation=MOTIVATION)).json()["id"]

    with fabrique_sessions() as db:
        brut = db.execute(
            text("SELECT motivation_chiffree FROM voeux_formations WHERE id = :i"),
            {"i": vid2.replace("-", "")},
        ).scalar_one()
        assert brut and "cryptographie" not in brut and MOTIVATION not in brut

        definir_tenant(db, a.bureau.id)
        entrees = db.scalars(
            select(EntreeAudit).where(EntreeAudit.action.like("voeu.%"))
        ).all()
        actions = {e.action for e in entrees}
        assert {
            "voeu.creation",
            "voeu.modification",
            "voeu.validation",
            "voeu.ajout_panier",
            "voeu.suppression",
        } <= actions
        for e in entrees:
            sérialisé = json.dumps(e.details or {}, ensure_ascii=False)
            assert "cryptographie" not in sérialisé
            assert "Informatique" not in sérialisé and "TESTEUR" not in sérialisé

