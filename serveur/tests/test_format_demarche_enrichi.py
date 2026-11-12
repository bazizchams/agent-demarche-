"""Format de démarche enrichi : conditions, échéances, modèles de documents, frais."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI

from app.modeles.candidat import StatutCandidat
from app.schemas.candidat import CandidatSortie
from app.schemas.document import StatutPieceRequise
from app.services.echeances_demarche import calculer_echeances
from app.services.pieces_requises import (
    ConditionSimple,
    ConfigDemarche,
    charger_demarches_base,
    evaluer_condition,
    verifier_completude_dossier,
)
from tests.conftest import DonneesBureauTest, connecter_client

DOSSIER_YAML = Path(__file__).resolve().parents[2] / "config" / "demarches"


def _candidat(**champs) -> CandidatSortie:
    base = dict(
        id=uuid.uuid4(), nom="TEST", prenom="Fictif", sexe=None, date_naissance=None,
        lieu_naissance=None, nationalite=None, pays_residence=None, email=None,
        telephone=None, numero_passeport=None, date_expiration_passeport=None,
        adresse=None, niveau_actuel=None, programme_vise=None, etablissement_vise=None,
        fonds_disponibles_eur=None, notes_internes=None, consentement_signe=False,
        date_consentement=None, statut=StatutCandidat.ACTIF, archive_le=None,
        cree_le=datetime(2026, 1, 1, tzinfo=timezone.utc),
        modifie_le=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    base.update(champs)
    return CandidatSortie(**base)


def _doc(type_piece: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(), type_piece=type_piece, date_expiration=None,
        cree_le=datetime(2026, 1, 1),
    )


def _cond(champ, operateur, valeur=None) -> ConditionSimple:
    return ConditionSimple(champ=champ, operateur=operateur, valeur=valeur)


# --- Rétro-compatibilité -----------------------------------------------------


def test_les_yaml_existants_se_chargent_avec_les_nouveaux_champs_vides() -> None:
    demarches = charger_demarches_base(DOSSIER_YAML)
    assert "campus_france" in demarches and "ircc_permis_etudes" in demarches
    for d in demarches.values():
        assert d.echeances == [] or all(e.code for e in d.echeances)
        assert d.instructions_agent is None or isinstance(d.instructions_agent, str)
    cf = demarches["campus_france"]
    assert all(p.si is None for p in cf.pieces_requises)


# --- Opérateurs de condition --------------------------------------------------


def test_operateurs_texte_insensibles_casse_et_accents() -> None:
    c = _candidat(niveau_actuel="Licence 3 — Édition MASTER")
    assert evaluer_condition(_cond("niveau_actuel", "contient", "master"), c) is True
    assert evaluer_condition(_cond("niveau_actuel", "contient", "édition"), c) is True
    assert evaluer_condition(_cond("niveau_actuel", "contient", "doctorat"), c) is False
    c2 = _candidat(nationalite="Algérienne")
    assert evaluer_condition(_cond("nationalite", "egal", "algerienne"), c2) is True
    assert evaluer_condition(_cond("nationalite", "different", "algerienne"), c2) is False
    assert evaluer_condition(_cond("nationalite", "different", "française"), c2) is True


def test_operateurs_renseigne_et_numeriques() -> None:
    vide = _candidat()
    plein = _candidat(email="a@exemple.dz", fonds_disponibles_eur=7500)
    assert evaluer_condition(_cond("email", "renseigne"), vide) is False
    assert evaluer_condition(_cond("email", "non_renseigne"), vide) is True
    assert evaluer_condition(_cond("email", "renseigne"), plein) is True
    assert evaluer_condition(_cond("fonds_disponibles_eur", "superieur_ou_egal", 7500), plein) is True
    assert evaluer_condition(_cond("fonds_disponibles_eur", "superieur_ou_egal", 8000), plein) is False
    assert evaluer_condition(_cond("fonds_disponibles_eur", "inferieur", 8000), plein) is True
    # Champ vide : indéterminé pour les autres opérateurs.
    assert evaluer_condition(_cond("fonds_disponibles_eur", "inferieur", 8000), vide) is None
    assert evaluer_condition(_cond("niveau_actuel", "egal", "x"), vide) is None


def test_condition_exige_une_valeur_sauf_renseigne() -> None:
    with pytest.raises(ValueError):
        ConditionSimple(champ="nom", operateur="egal")


# --- Complétude ---------------------------------------------------------------


def _demarche_conditionnelle() -> ConfigDemarche:
    return ConfigDemarche.model_validate(
        {
            "code": "cond",
            "libelle": "Démarche conditionnelle",
            "champs_conditionnels": [
                {"champ": "etablissement_vise", "si": {"champ": "niveau_actuel", "operateur": "contient", "valeur": "master"}}
            ],
            "pieces_requises": [
                {"type_piece": "passeport", "libelle": "Passeport"},
                {
                    "type_piece": "lettre_master",
                    "libelle": "Lettre de motivation spécifique",
                    "si": {"champ": "niveau_actuel", "operateur": "contient", "valeur": "master"},
                },
            ],
        }
    )


def test_completude_condition_vraie_la_piece_est_exigee() -> None:
    etat = verifier_completude_dossier(
        candidat=_candidat(niveau_actuel="Master 1"),
        documents=[_doc("passeport")],
        demarche=_demarche_conditionnelle(),
    )
    assert "lettre_master" in etat.pieces_manquantes_ou_invalides
    assert etat.pieces_non_applicables == []
    assert "etablissement_vise" in etat.champs_candidat_manquants
    assert etat.pret_pour_prerequis is False


def test_completude_condition_fausse_la_piece_est_ignoree() -> None:
    etat = verifier_completude_dossier(
        candidat=_candidat(niveau_actuel="Licence 3"),
        documents=[_doc("passeport")],
        demarche=_demarche_conditionnelle(),
    )
    assert etat.pieces_non_applicables == ["lettre_master"]
    assert etat.champs_non_applicables == ["etablissement_vise"]
    assert etat.pieces_manquantes_ou_invalides == []
    assert etat.pret_pour_prerequis is True
    piece = next(p for p in etat.pieces if p.type_piece == "lettre_master")
    assert piece.statut == StatutPieceRequise.NON_APPLICABLE
    assert piece.obligatoire is False


def test_completude_condition_indeterminee_la_piece_reste_exigee_avec_message() -> None:
    etat = verifier_completude_dossier(
        candidat=_candidat(niveau_actuel=None),
        documents=[_doc("passeport")],
        demarche=_demarche_conditionnelle(),
    )
    assert "lettre_master" in etat.pieces_manquantes_ou_invalides
    piece = next(p for p in etat.pieces if p.type_piece == "lettre_master")
    assert piece.statut == StatutPieceRequise.MANQUANTE
    assert "indéterminée" in (piece.detail or "")
    assert "etablissement_vise" in etat.champs_candidat_manquants


# --- Échéances ----------------------------------------------------------------


def _demarche_echeances() -> ConfigDemarche:
    return ConfigDemarche.model_validate(
        {
            "code": "ech",
            "libelle": "Avec échéances",
            "echeances": [
                {"code": "fixe", "libelle": "Date limite", "date_fixe": "2026-12-01"},
                {"code": "rel", "libelle": "Visa", "jours_avant_reference": 60, "reference": "rentree"},
                {"code": "depot", "libelle": "Complément", "jours_avant_reference": -10, "reference": "depot"},
            ],
        }
    )


def _par_code(liste: list[dict]) -> dict[str, dict]:
    return {e["code"]: e for e in liste}


def test_echeances_date_fixe_et_statuts() -> None:
    d = _demarche_echeances()
    e = _par_code(calculer_echeances(d, aujourd_hui=date(2026, 11, 11)))
    assert e["fixe"]["date"] == date(2026, 12, 1)
    assert e["fixe"]["jours_restants"] == 20
    assert e["fixe"]["statut"] == "proche"
    assert e["fixe"]["rappels_dus"] == [30]
    assert _par_code(calculer_echeances(d, aujourd_hui=date(2026, 11, 25)))["fixe"]["statut"] == "urgente"
    assert _par_code(calculer_echeances(d, aujourd_hui=date(2026, 11, 25)))["fixe"]["rappels_dus"] == [30, 7]
    assert _par_code(calculer_echeances(d, aujourd_hui=date(2026, 10, 1)))["fixe"]["statut"] == "a_venir"
    depassee = _par_code(calculer_echeances(d, aujourd_hui=date(2026, 12, 2)))["fixe"]
    assert depassee["statut"] == "depassee" and depassee["jours_restants"] == -1
    assert depassee["rappels_dus"] == []


def test_echeances_relatives_et_indeterminees() -> None:
    d = _demarche_echeances()
    sans_ref = _par_code(calculer_echeances(d, aujourd_hui=date(2026, 11, 11)))
    assert sans_ref["rel"]["date"] is None
    assert sans_ref["rel"]["statut"] == "indeterminee"
    assert sans_ref["rel"]["jours_restants"] is None

    avec = _par_code(
        calculer_echeances(
            d,
            aujourd_hui=date(2026, 11, 11),
            date_rentree=date(2027, 1, 10),
            date_depot=date(2026, 11, 1),
        )
    )
    assert avec["rel"]["date"] == date(2026, 11, 11)
    assert avec["rel"]["statut"] == "urgente"
    assert avec["rel"]["jours_restants"] == 0
    assert avec["depot"]["date"] == date(2026, 11, 11)  # 10 jours après le dépôt


# --- API ----------------------------------------------------------------------


def _demarche_api() -> dict:
    return {
        "code": "visa_enrichi",
        "libelle": "Visa enrichi",
        "champs_candidat_requis": ["nom"],
        "pieces_requises": [
            {"type_piece": "passeport", "libelle": "Passeport"},
            {
                "type_piece": "lettre_master",
                "libelle": "Lettre spécifique",
                "si": {"champ": "niveau_actuel", "operateur": "contient", "valeur": "master"},
            },
        ],
        "echeances": [
            {"code": "limite", "libelle": "Date limite", "date_fixe": "2099-01-01", "rappel_jours_avant": [10, 2]},
            {"code": "visa", "libelle": "Visa", "jours_avant_reference": 30, "reference": "rentree"},
        ],
        "modeles_documents": [
            {
                "code": "lm", "libelle": "Lettre de motivation", "type": "lettre_motivation",
                "consignes": "Une page, ton formel.", "longueur_max_caracteres": 3000, "obligatoire": True,
            }
        ],
        "instructions_agent": "Ne jamais promettre de résultat.",
        "frais": [{"libelle": "Frais de dossier", "montant": 50.5, "devise": "EUR", "beneficiaire": "Campus", "moment": "au dépôt"}],
    }


def test_creation_et_relecture_d_une_demarche_enrichie(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.admin.email)
    rep = client.post("/api/v1/demarches", json=_demarche_api())
    assert rep.status_code == 201, rep.text
    rel = client.get("/api/v1/demarches/visa_enrichi")
    assert rel.status_code == 200
    d = rel.json()["definition"]
    assert d["pieces_requises"][1]["si"]["operateur"] == "contient"
    assert d["pieces_requises"][0]["si"] is None
    assert d["echeances"][0]["date_fixe"] == "2099-01-01"
    assert d["echeances"][1]["rappel_jours_avant"] == [30, 7, 1]
    assert d["modeles_documents"][0]["type"] == "lettre_motivation"
    assert d["instructions_agent"] == "Ne jamais promettre de résultat."
    assert d["frais"][0]["devise"] == "EUR"


def test_refus_champ_de_condition_inconnu_et_codes_en_double(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.admin.email)

    mauvais = _demarche_api()
    mauvais["pieces_requises"][1]["si"]["champ"] = "champ_qui_n_existe_pas"
    assert client.post("/api/v1/demarches", json=mauvais).status_code in (400, 422)

    mauvais = _demarche_api()
    mauvais["champs_conditionnels"] = [
        {"champ": "inconnu", "si": {"champ": "niveau_actuel", "operateur": "renseigne"}}
    ]
    assert client.post("/api/v1/demarches", json=mauvais).status_code in (400, 422)

    mauvais = _demarche_api()
    mauvais["echeances"].append({"code": "limite", "libelle": "Doublon", "date_fixe": "2099-02-01"})
    assert client.post("/api/v1/demarches", json=mauvais).status_code in (400, 422)

    mauvais = _demarche_api()
    mauvais["modeles_documents"].append({"code": "lm", "libelle": "Doublon"})
    assert client.post("/api/v1/demarches", json=mauvais).status_code in (400, 422)

    mauvais = _demarche_api()
    mauvais["echeances"][0]["rappel_jours_avant"] = [-1]
    assert client.post("/api/v1/demarches", json=mauvais).status_code in (400, 422)

    mauvais = _demarche_api()
    mauvais["frais"][0]["devise"] = "EURO"
    assert client.post("/api/v1/demarches", json=mauvais).status_code in (400, 422)

    ok = _demarche_api()
    assert client.post("/api/v1/demarches", json=ok).status_code == 201


def test_route_echeances(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    a, _ = deux_bureaux
    client, _ = connecter_client(application, a.admin.email)
    assert client.post("/api/v1/demarches", json=_demarche_api()).status_code == 201

    rep = client.get("/api/v1/demarches/visa_enrichi/echeances")
    assert rep.status_code == 200, rep.text
    e = _par_code(rep.json())
    assert e["limite"]["date"] == "2099-01-01"
    assert e["limite"]["statut"] == "a_venir"
    assert e["visa"]["statut"] == "indeterminee" and e["visa"]["date"] is None

    rep = client.get(
        "/api/v1/demarches/visa_enrichi/echeances", params={"date_rentree": "2020-01-31"}
    )
    e = _par_code(rep.json())
    assert e["visa"]["date"] == "2020-01-01"
    assert e["visa"]["statut"] == "depassee"

    assert client.get("/api/v1/demarches/inexistante/echeances").status_code == 404
    assert client.get(
        "/api/v1/demarches/visa_enrichi/echeances", params={"date_rentree": "pas-une-date"}
    ).status_code == 422
    # Un employé (lecture) peut consulter ; un client non authentifié non.
    employe, _ = connecter_client(application, a.employe.email)
    assert employe.get("/api/v1/demarches/visa_enrichi/echeances").status_code == 200
