"""Coffre d'identifiants portail (regle 3) : consentement, chiffrement, isolation, API sans secret."""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi import FastAPI
from sqlalchemy import select, text

from app.core.erreurs import DonneesInvalides
from app.db.tenant import definir_tenant
from app.modeles.journal_audit import EntreeAudit
from app.services import coffre_identifiants as coffre
from tests.conftest import connecter_client

IDENTIFIANT = "ident-portail-secret-7731"
MOT_DE_PASSE = "Mdp-Portail-Tres-Secret-9482!"
CORPS = {"identifiant": IDENTIFIANT, "mot_de_passe": MOT_DE_PASSE, "consentement": True}


def _candidat(client) -> str:
    rep = client.post("/api/v1/candidats", json={"nom": "TESTEUR", "prenom": "Fictif"})
    assert rep.status_code == 201, rep.text
    return rep.json()["id"]


def _url(cid: str, portail: str = "etudes_en_france") -> str:
    return f"/api/v1/candidats/{cid}/coffre/{portail}"


def _cle(application: FastAPI) -> bytes:
    return application.state.cle_maitresse


def test_consentement_obligatoire(application: FastAPI, deux_bureaux) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.employe.email)
    cid = _candidat(client)
    rep = client.put(_url(cid), json={**CORPS, "consentement": False})
    assert rep.status_code == 422
    rep = client.put(_url(cid), json={"identifiant": "x", "mot_de_passe": "y"})
    assert rep.status_code == 422
    assert client.get(_url(cid)).json()["existe"] is False


def test_service_refuse_sans_consentement(
    application: FastAPI, fabrique_sessions, deux_bureaux
) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.employe.email)
    cid = uuid.UUID(_candidat(client))
    with fabrique_sessions() as db:
        definir_tenant(db, a.bureau.id)
        with pytest.raises(DonneesInvalides) as exc:
            coffre.enregistrer(
                db,
                candidat_id=cid,
                portail="ircc",
                identifiant=IDENTIFIANT,
                mot_de_passe=MOT_DE_PASSE,
                consentement=False,
                acteur_id=a.employe.id,
                cle_maitresse=_cle(application),
            )
        assert MOT_DE_PASSE not in str(exc.value) and IDENTIFIANT not in str(exc.value)


def test_valeur_en_base_non_claire_et_aller_retour(
    application: FastAPI, fabrique_sessions, moteur_db, deux_bureaux
) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.employe.email)
    cid = _candidat(client)
    assert client.put(_url(cid), json=CORPS).status_code == 200

    with moteur_db.connect() as conn:
        lignes = conn.execute(
            text("SELECT identifiant_chiffre, mot_de_passe_chiffre FROM identifiants_portail")
        ).all()
    assert len(lignes) == 1
    for valeur in lignes[0]:
        assert valeur.startswith("v1:")
        assert IDENTIFIANT not in valeur and MOT_DE_PASSE not in valeur
    assert lignes[0][0] != lignes[0][1]

    with fabrique_sessions() as db:
        definir_tenant(db, a.bureau.id)
        clairs = coffre.lire_pour_agent(
            db,
            candidat_id=uuid.UUID(cid),
            portail="etudes_en_france",
            cle_maitresse=_cle(application),
            acteur_id=a.employe.id,
        )
        assert clairs.identifiant == IDENTIFIANT
        assert clairs.mot_de_passe == MOT_DE_PASSE
        assert MOT_DE_PASSE not in repr(clairs) and MOT_DE_PASSE not in str(clairs)
        ligne = db.scalar(select(coffre.IdentifiantPortail))
        assert MOT_DE_PASSE not in repr(ligne)
        assert ligne.consentement_par == a.employe.id


def test_isolation_entre_bureaux(application: FastAPI, fabrique_sessions, deux_bureaux) -> None:
    a, b = deux_bureaux
    client_a, _ = connecter_client(application, a.employe.email)
    cid = _candidat(client_a)
    assert client_a.put(_url(cid), json=CORPS).status_code == 200

    client_b, _ = connecter_client(application, b.employe.email)
    assert client_b.get(_url(cid)).status_code == 404
    assert client_b.put(_url(cid), json=CORPS).status_code == 404
    assert client_b.delete(_url(cid)).status_code == 404

    with fabrique_sessions() as db:
        definir_tenant(db, b.bureau.id)
        assert db.scalars(select(coffre.IdentifiantPortail)).all() == []
        with pytest.raises(Exception):
            coffre.lire_pour_agent(
                db,
                candidat_id=uuid.UUID(cid),
                portail="etudes_en_france",
                cle_maitresse=_cle(application),
            )


def test_aucune_reponse_api_ne_contient_le_secret(application: FastAPI, deux_bureaux) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.employe.email)
    cid = _candidat(client)
    reponses = [
        client.put(_url(cid), json=CORPS),
        client.put(_url(cid), json=CORPS),  # remplacement
        client.get(_url(cid)),
        client.put(_url(cid, "inconnu"), json=CORPS),
        client.put(_url(cid), json={**CORPS, "consentement": False}),
        client.put(_url(cid), json={"identifiant": IDENTIFIANT, "mot_de_passe": MOT_DE_PASSE}),
        client.put(_url(cid), json={**CORPS, "extra": 1}),
        client.get(f"/api/v1/candidats/{cid}"),
        client.get("/api/v1/audit"),
    ]
    for rep in reponses:
        assert IDENTIFIANT not in rep.text and MOT_DE_PASSE not in rep.text
    statut = reponses[2].json()
    assert statut["existe"] is True
    assert set(statut) == {
        "portail",
        "existe",
        "consentement_recueilli_le",
        "cree_le",
        "mis_a_jour_le",
    }


def test_suppression_par_portail_et_avec_le_candidat(
    application: FastAPI, fabrique_sessions, deux_bureaux
) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.admin.email)
    cid = _candidat(client)
    assert client.put(_url(cid, "ircc"), json=CORPS).status_code == 200
    assert client.put(_url(cid), json=CORPS).status_code == 200
    assert client.delete(_url(cid, "ircc")).status_code == 204
    assert client.get(_url(cid, "ircc")).json()["existe"] is False
    assert client.get(_url(cid)).json()["existe"] is True
    assert client.delete(_url(cid, "ircc")).status_code == 404

    with fabrique_sessions() as db:
        definir_tenant(db, a.bureau.id)
        assert (
            coffre.supprimer_tout_candidat(
                db, candidat_id=uuid.UUID(cid), acteur_id=a.admin.id
            )
            == 1
        )
        assert db.scalars(select(coffre.IdentifiantPortail)).all() == []


def test_suppression_du_dossier_candidat_purge_le_coffre(
    application: FastAPI, fabrique_sessions, deux_bureaux, parametres_test
) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.admin.email)
    cid = _candidat(client)
    assert client.put(_url(cid), json=CORPS).status_code == 200
    from app.services import conformite

    with fabrique_sessions() as db:
        definir_tenant(db, a.bureau.id)
        conformite.supprimer_definitivement_dossier_candidat(
            db,
            candidat_id=uuid.UUID(cid),
            acteur_id=a.admin.id,
            parametres=parametres_test,
        )
    with fabrique_sessions() as db:
        definir_tenant(db, a.bureau.id)
        assert db.scalars(select(coffre.IdentifiantPortail)).all() == []


def test_lecture_seule_refusee(application: FastAPI, deux_bureaux) -> None:
    a, _ = deux_bureaux
    admin, _ = connecter_client(application, a.admin.email)
    cid = _candidat(admin)
    assert admin.put(_url(cid), json=CORPS).status_code == 200
    lecteur, _ = connecter_client(application, a.lecteur.email)
    assert lecteur.put(_url(cid), json=CORPS).status_code == 403
    assert lecteur.delete(_url(cid)).status_code == 403
    rep = lecteur.get(_url(cid))
    assert rep.status_code == 200
    assert IDENTIFIANT not in rep.text and MOT_DE_PASSE not in rep.text


def test_audit_sans_secret(application: FastAPI, fabrique_sessions, deux_bureaux) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.employe.email)
    cid = _candidat(client)
    client.put(_url(cid), json=CORPS)
    with fabrique_sessions() as db:
        definir_tenant(db, a.bureau.id)
        coffre.lire_pour_agent(
            db,
            candidat_id=uuid.UUID(cid),
            portail="etudes_en_france",
            cle_maitresse=_cle(application),
            acteur_id=a.employe.id,
        )
    client.delete(_url(cid))
    with fabrique_sessions() as db:
        definir_tenant(db, a.bureau.id)
        entrees = [
            e for e in db.scalars(select(EntreeAudit)).all() if e.action.startswith("coffre.")
        ]
    assert {e.action for e in entrees} == {"coffre.cree", "coffre.utilise", "coffre.supprime"}
    brut = json.dumps(
        [[e.action, e.ressource_type, str(e.ressource_id), e.details] for e in entrees]
    )
    for interdit in (IDENTIFIANT, MOT_DE_PASSE, "TESTEUR", "Fictif", a.employe.email):
        assert interdit not in brut
    assert all(e.details["portail"] == "etudes_en_france" for e in entrees)
