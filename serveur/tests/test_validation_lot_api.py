"""Validation en lot des valeurs fiables + remplissage de la fiche (un clic humain). Tout est synthétique."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests import corpus_synthetique as corpus
from tests.conftest import connecter_client
from tests.test_extractions_api import (  # noqa: F401 - fixture `contexte` réutilisée
    PII,
    _creer_candidat,
    _deposer,
    _extraire,
    _par_champ,
    contexte,
)

RELEVE_UNIVERSITE = (
    "RELEVÉ DE NOTES\nDiplôme : Licence en Informatique\nAnnée universitaire : 2023/2024\n"
    "Moyenne annuelle : 13,42/20\nMention : Bien\n"
)


def _fiche(client: TestClient, cid: str) -> dict:
    rep = client.get(f"/api/v1/candidats/{cid}")
    assert rep.status_code == 200, rep.text
    return rep.json()


def _lot(client: TestClient, cid: str, **corps: object):
    return client.post(f"/api/v1/candidats/{cid}/extractions/valider-lot", json=corps or None)


def test_lot_valide_les_valeurs_fiables_et_remplit_la_fiche(contexte: dict) -> None:
    client = contexte["client_a"]
    cid = _creer_candidat(client)
    did = _deposer(client, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE])
    _extraire(client, cid, did)
    avant = client.get(f"/api/v1/candidats/{cid}/extractions/synthese").json()
    # Le spécimen n'a que la MRZ, sans zone visuelle : nom et prénom (sans chiffre de contrôle) ne sont
    # jamais validés en lot, ils restent à confirmer un par un.
    assert avant["nb_fiables"] >= 4 and avant["nb_douteuses"] <= 2

    rep = _lot(client, cid)
    assert rep.status_code == 200, rep.text
    corps = rep.json()
    assert corps["nb_valides"] == avant["nb_fiables"]
    champs_remplis = {a["champ"] for a in corps["rapport"]["appliques"]}
    assert {"numero_passeport", "date_naissance", "sexe", "date_expiration_passeport", "nationalite_code"} <= champs_remplis
    fiche = _fiche(client, cid)
    assert fiche["numero_passeport"] == "L898902C3"
    assert fiche["date_naissance"] == "1974-08-12"
    assert fiche["sexe"] == "F"
    assert fiche["nationalite"]  # code pays converti, jamais deviné au-delà de la table
    toutes = client.get(f"/api/v1/candidats/{cid}/extractions").json()
    assert all(e["statut"] == "valide_humain" and e["applique_le"] for e in toutes if e["champ"] in champs_remplis)


def test_valeur_douteuse_exclue_du_lot_et_listee(contexte: dict) -> None:
    client = contexte["client_a"]
    cid = _creer_candidat(client)
    did = _deposer(client, cid, "releve_notes_bac", [corpus.TEXTE_RELEVE_BAC])
    champs = _par_champ(_extraire(client, cid, did))
    syn = client.get(f"/api/v1/candidats/{cid}/extractions/synthese").json()
    assert syn["nb_fiables"] == 0 and syn["nb_douteuses"] >= 1
    assert "niveau_francais" in syn["a_completer"]

    corps = _lot(client, cid).json()
    assert corps["nb_valides"] == 0 and corps["nb_douteuses_restantes"] >= 1
    apres = client.get(f"/api/v1/candidats/{cid}/extractions").json()
    assert {e["id"]: e["statut"] for e in apres}[champs["moyenne_generale"]["id"]] == "a_verifier"
    # une douteuse demandée explicitement dans le lot est refusée (ignorée), jamais confirmée
    corps = _lot(client, cid, extraction_ids=[champs["moyenne_generale"]["id"]]).json()
    assert corps["nb_valides"] == 0 and corps["nb_ignores"] == 1


def test_meme_valeur_sur_deux_pieces_est_fiable(contexte: dict) -> None:
    client = contexte["client_a"]
    cid = _creer_candidat(client)
    for n in range(2):  # texte légèrement différent : le dépôt refuse deux fichiers identiques
        _extraire(client, cid, _deposer(client, cid, "releve_notes_bac", [corpus.TEXTE_RELEVE_BAC + "x" * n]))
    syn = client.get(f"/api/v1/candidats/{cid}/extractions/synthese").json()
    assert {i["raison"] for i in syn["items"] if i["niveau"] == "fiable"} == {"concordance_deux_pieces"}
    assert _lot(client, cid).json()["nb_valides"] >= 2


def test_deux_pieces_discordantes_restent_douteuses(contexte: dict) -> None:
    client = contexte["client_a"]
    cid = _creer_candidat(client)
    _extraire(client, cid, _deposer(client, cid, "releve_notes_bac", [corpus.TEXTE_RELEVE_BAC]))
    r2 = _extraire(client, cid, _deposer(client, cid, "releve_notes_bac", [corpus.TEXTE_RELEVE_BAC.replace("14,52", "11,00")]))
    moyennes: set[str] = set()
    ids = {_par_champ(r)["moyenne_generale"]["id"] for r in (r2,)}
    syn = client.get(f"/api/v1/candidats/{cid}/extractions/synthese").json()
    items = {i["extraction_id"]: i for i in syn["items"]}
    toutes = client.get(f"/api/v1/candidats/{cid}/extractions").json()
    id_moyennes = {e["id"] for e in toutes if e["champ"] == "moyenne_generale"} | ids | moyennes
    assert len(id_moyennes) == 2 and {items[i]["niveau"] for i in id_moyennes} == {"douteuse"}
    _lot(client, cid)
    apres = {e["id"]: e["statut"] for e in client.get(f"/api/v1/candidats/{cid}/extractions").json()}
    assert all(apres[i] != "valide_humain" for i in id_moyennes)


def test_lot_n_ecrase_jamais_une_valeur_deja_saisie(contexte: dict) -> None:
    client = contexte["client_a"]
    cid = _creer_candidat(client, date_naissance="1990-01-01")
    _extraire(client, cid, _deposer(client, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE]))
    syn = client.get(f"/api/v1/candidats/{cid}/extractions/synthese").json()
    assert any(i["conflit_fiche"] for i in syn["items"])
    rapport = _lot(client, cid).json()["rapport"]
    assert "date_naissance" in {c["champ"] for c in rapport["conflits"]}
    fiche = _fiche(client, cid)
    assert fiche["date_naissance"] == "1990-01-01"  # inchangée
    assert fiche["numero_passeport"] == "L898902C3"  # les autres champs sont remplis


def test_diplome_reporte_sur_niveau_actuel_et_lieu_naissance(contexte: dict) -> None:
    client = contexte["client_a"]
    cid = _creer_candidat(client)
    texte = RELEVE_UNIVERSITE + "Né(e) le 14/03/2002 à Tizi Ouzou\n"
    for n in range(2):
        _extraire(client, cid, _deposer(client, cid, "releves_notes_superieur", [texte + "Copie " * n]))
    _lot(client, cid)
    assert (_fiche(client, cid)["niveau_actuel"] or "").startswith("Licence")


def test_lot_roles_csrf_et_lecture_seule(contexte: dict, application: FastAPI) -> None:
    client = contexte["client_a"]
    cid = _creer_candidat(client)
    _extraire(client, cid, _deposer(client, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE]))
    url = f"/api/v1/candidats/{cid}/extractions/valider-lot"
    lecteur, _ = connecter_client(application, contexte["a"].lecteur.email)
    assert lecteur.post(url).status_code == 403
    assert lecteur.get(f"/api/v1/candidats/{cid}/extractions/synthese").status_code == 200
    sans_csrf = TestClient(application)
    sans_csrf.cookies.update(client.cookies)
    assert sans_csrf.post(url).status_code == 403
    assert TestClient(application).post(url).status_code == 401
    assert client.get(f"/api/v1/candidats/{cid}/extractions").json()  # rien n'a été validé par les refus
    assert all(e["statut"] != "valide_humain" for e in client.get(f"/api/v1/candidats/{cid}/extractions").json())


def test_lot_isolation_entre_bureaux(contexte: dict) -> None:
    ca, cb = contexte["client_a"], contexte["client_b"]
    cid = _creer_candidat(ca)
    _extraire(ca, cid, _deposer(ca, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE]))
    assert cb.post(f"/api/v1/candidats/{cid}/extractions/valider-lot").status_code == 404
    assert cb.get(f"/api/v1/candidats/{cid}/extractions/synthese").status_code == 404
    assert all(e["statut"] != "valide_humain" for e in ca.get(f"/api/v1/candidats/{cid}/extractions").json())


def test_lot_audit_sans_donnee_personnelle(contexte: dict, caplog: pytest.LogCaptureFixture) -> None:
    client = contexte["client_a"]
    cid = _creer_candidat(client)
    _extraire(client, cid, _deposer(client, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE]))
    assert _lot(client, cid).status_code == 200
    with contexte["app"].state.moteur.connect() as conn:
        audits = conn.execute(text("SELECT action, details FROM journal_audit")).all()
    lot = [a for a in audits if a.action == "extraction.valider_lot"]
    assert len(lot) == 1 and "nb_valides" in str(lot[0].details)
    tout = " ".join(f"{a.action} {a.details}" for a in audits) + caplog.text
    for secret in PII:
        assert secret not in tout
