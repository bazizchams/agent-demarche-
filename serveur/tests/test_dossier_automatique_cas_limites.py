"""Dossier automatique (P7) : cas limites de l'API de lancement et de l'état d'avancement.

Réutilise les fixtures et helpers de `test_dossier_automatique` : corps JSON inconnu ou démarche inconnue,
candidat sans document, PDF sans information, candidat inexistant, progression bornée et monotone."""

from __future__ import annotations

import uuid

from tests.test_dossier_automatique import (  # noqa: F401  (ctx : fixture importée)
    _candidat,
    _confirmer_points,
    _confirmer_valeurs,
    _deposer_corpus,
    _doc,
    _etape,
    _etat,
    _lancer,
    ctx,
)


def test_corps_json_de_lancement_valide_inconnu_et_champ_interdit(ctx: dict) -> None:
    cl = ctx["client_a"]
    cid = _candidat(cl)
    url = f"/api/v1/candidats/{cid}/dossier-automatique/lancer"
    assert cl.post(url, json={"code_demarche": "campus_france"}).status_code == 200
    assert cl.post(url, json={"code_demarche": "inconnue"}).status_code == 404
    assert cl.post(url, json={"x": 1}).status_code == 422


def test_candidat_sans_document_lecture_bloquee_progression_nulle(ctx: dict) -> None:
    cl = ctx["client_a"]
    cid = _candidat(cl)
    etat = _lancer(cl, cid)
    assert _etape(etat, "lecture")["statut"] == "bloque"
    assert _etape(etat, "lecture")["compteurs"]["documents"] == 0
    assert etat["progression"] == 0


def test_pdf_sans_information_lu_une_seule_fois_et_revue_terminee(ctx: dict) -> None:
    cl = ctx["client_a"]
    cid = _candidat(cl)
    _doc(cl, cid, "passeport", ["Page vide"])
    etat = _lancer(cl, cid)
    assert _etape(etat, "lecture")["statut"] == "termine"
    assert _etape(etat, "revue_valeurs")["statut"] == "termine"
    relance = _lancer(cl, cid)
    assert _etape(relance, "lecture")["statut"] == "termine"
    assert _etape(relance, "lecture")["compteurs"]["a_lire"] == 0  # pas relue
    assert _etape(relance, "revue_valeurs")["statut"] == "termine"
    assert _etape(relance, "revue_valeurs")["compteurs"]["a_confirmer"] == 0


def test_candidat_inexistant_donne_404_sur_etat_et_lancement(ctx: dict) -> None:
    cl = ctx["client_a"]
    inconnu = uuid.uuid4()
    base = f"/api/v1/candidats/{inconnu}/dossier-automatique"
    assert cl.get(f"{base}/etat").status_code == 404
    assert cl.post(f"{base}/lancer").status_code == 404


def test_progression_bornee_et_monotone_apres_confirmation(ctx: dict) -> None:
    cl = ctx["client_a"]
    cid = _candidat(cl)
    _deposer_corpus(cl, cid)
    progressions = [_etat(cl, cid)["progression"]]
    progressions.append(_lancer(cl, cid)["progression"])
    assert _confirmer_valeurs(cl, cid) > 0
    progressions.append(_lancer(cl, cid)["progression"])
    _confirmer_points(cl, cid)
    progressions.append(_lancer(cl, cid)["progression"])
    progressions.append(_etat(cl, cid)["progression"])
    assert all(0 <= p <= 100 for p in progressions), progressions
    assert all(avant <= apres for avant, apres in zip(progressions, progressions[1:])), progressions
