"""Tests de l'assistant IA : aucun appel réseau (faux client LLM / faux httpx.post)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.core.erreurs import ServiceIndisponible
from app.modeles.abonnement import ForfaitAbonnement
from app.services import assistant_ia, llm
from app.services.llm import ClientAnthropic, ReponseLLM, obtenir_client_llm
from app.services.pieces_requises import ConfigDemarche
from tests.conftest import connecter_client

TEXTE_VALIDE = "Procédure fictive de test. " * 10  # > 80 caractères


class FauxClient:
    def __init__(self, reponse: ReponseLLM) -> None:
        self.reponse = reponse
        self.appels: list[dict[str, Any]] = []

    def generer(self, **kwargs: Any) -> ReponseLLM:
        self.appels.append(kwargs)
        return self.reponse


def _outil_valide() -> dict[str, Any]:
    return {
        "code": "Visa Test!",
        "libelle": "Visa de test",
        "description": "Procédure fictive",
        "champs_candidat_requis": ["nom", "champ_inconnu", "email"],
        "pieces_requises": [
            {"type_piece": "passeport", "libelle": "Passeport", "obligatoire": True}
        ],
    }


def _brancher(application, reponse: ReponseLLM) -> FauxClient:
    faux = FauxClient(reponse)
    application.dependency_overrides[obtenir_client_llm] = lambda: faux
    return faux


# ---------------------------------------------------------------- 6. statut / 503


def test_statut_sans_cle_et_routes_503(application, deux_bureaux) -> None:
    bureau_a, _ = deux_bureaux
    admin, _ = connecter_client(application, bureau_a.admin.email)
    r = admin.get("/api/v1/ia/statut")
    assert r.status_code == 200
    corps = r.json()
    assert {k: corps[k] for k in ("active", "appels_ce_mois", "plafond_mensuel")} == {
        "active": False,
        "appels_ce_mois": 0,
        # Bureau en période d'essai : plafond d'essai, quel que soit le forfait.
        "plafond_mensuel": min(
            llm.QUOTA_IA_MENSUEL[ForfaitAbonnement.STARTER], llm.QUOTA_IA_ESSAI
        ),
    }
    assert corps["fournisseur"] == "anthropic" and corps["donnees_quittent_serveur"] is False
    r = admin.post("/api/v1/ia/procedures/generer", json={"texte": TEXTE_VALIDE})
    assert r.status_code == 503


def test_statut_active_avec_cle(application, deux_bureaux) -> None:
    from app.core.config import obtenir_parametres

    base = obtenir_parametres()
    surcharge = base.model_copy(update={"cle_api_anthropic": "cle-factice"})
    application.dependency_overrides[obtenir_parametres] = lambda: surcharge
    bureau_a, _ = deux_bureaux
    lecteur, _ = connecter_client(application, bureau_a.lecteur.email)
    r = lecteur.get("/api/v1/ia/statut")
    assert r.status_code == 200
    assert r.json()["active"] is True


# ---------------------------------------------------------------- 1. génération


def test_generation_procedure_brouillon_non_enregistre(application, deux_bureaux) -> None:
    bureau_a, _ = deux_bureaux
    faux = _brancher(application, ReponseLLM(texte="", outil=_outil_valide(), tokens_entree=10, tokens_sortie=5))
    admin, _ = connecter_client(application, bureau_a.admin.email)

    r = admin.post("/api/v1/ia/procedures/generer", json={"texte": TEXTE_VALIDE})
    assert r.status_code == 200, r.text
    corps = r.json()
    assert corps["brouillon"]["code"] == "visa_test"
    assert corps["brouillon"]["champs_candidat_requis"] == ["nom", "email"]
    assert any("champ_inconnu" in a for a in corps["avertissements"])
    assert corps["brouillon"]["pieces_requises"][0]["type_piece"] == "passeport"

    # L'outil est forcé et son schéma est autonome.
    outil = faux.appels[0]["outil"]
    assert outil["name"] == "proposer_procedure"
    assert outil["input_schema"]["type"] == "object"
    assert "properties" in outil["input_schema"]
    assert "<source>" in faux.appels[0]["message"]

    # Rien n'est enregistré.
    assert admin.get("/api/v1/demarches/visa_test").status_code == 404

    # L'appel est tracé.
    assert admin.get("/api/v1/ia/statut").json()["appels_ce_mois"] == 1


def test_generation_sans_outil_422_mais_appel_trace(application, deux_bureaux) -> None:
    bureau_a, _ = deux_bureaux
    _brancher(application, ReponseLLM(texte="Je ne sais pas."))
    admin, _ = connecter_client(application, bureau_a.admin.email)
    r = admin.post("/api/v1/ia/procedures/generer", json={"texte": TEXTE_VALIDE})
    assert r.status_code == 422
    assert admin.get("/api/v1/ia/statut").json()["appels_ce_mois"] == 1


def test_generation_brouillon_invalide_422(application, deux_bureaux) -> None:
    bureau_a, _ = deux_bureaux
    _brancher(application, ReponseLLM(texte="", outil={"code": "x"}))  # libelle manquant
    admin, _ = connecter_client(application, bureau_a.admin.email)
    r = admin.post("/api/v1/ia/procedures/generer", json={"texte": TEXTE_VALIDE})
    assert r.status_code == 422


def test_generation_texte_trop_court_ou_trop_long(application, deux_bureaux) -> None:
    bureau_a, _ = deux_bureaux
    faux = _brancher(application, ReponseLLM(texte="", outil=_outil_valide()))
    admin, _ = connecter_client(application, bureau_a.admin.email)
    assert admin.post("/api/v1/ia/procedures/generer", json={"texte": "court"}).status_code == 422
    long = "a" * (assistant_ia.TAILLE_MAX_TEXTE_SOURCE + 1)
    assert admin.post("/api/v1/ia/procedures/generer", json={"texte": long}).status_code == 422
    # Au-delà de la limite d'entrée de l'API : refusé aussi.
    enorme = "a" * (assistant_ia.TAILLE_MAX_TEXTE_SOURCE + 2000)
    assert admin.post("/api/v1/ia/procedures/generer", json={"texte": enorme}).status_code == 422
    assert faux.appels == []
    assert admin.get("/api/v1/ia/statut").json()["appels_ce_mois"] == 0


def test_generation_reservee_aux_administrateurs(application, deux_bureaux) -> None:
    bureau_a, _ = deux_bureaux
    faux = _brancher(application, ReponseLLM(texte="", outil=_outil_valide()))
    for email in (bureau_a.employe.email, bureau_a.lecteur.email):
        client, _ = connecter_client(application, email)
        r = client.post("/api/v1/ia/procedures/generer", json={"texte": TEXTE_VALIDE})
        assert r.status_code == 403
    assert faux.appels == []


# ---------------------------------------------------------------- 2. quota


def test_quota_mensuel_starter(application, deux_bureaux, monkeypatch) -> None:
    monkeypatch.setitem(llm.QUOTA_IA_MENSUEL, ForfaitAbonnement.STARTER, 1)
    bureau_a, _ = deux_bureaux
    _brancher(application, ReponseLLM(texte="", outil=_outil_valide()))
    admin, _ = connecter_client(application, bureau_a.admin.email)
    assert admin.post("/api/v1/ia/procedures/generer", json={"texte": TEXTE_VALIDE}).status_code == 200
    assert admin.post("/api/v1/ia/procedures/generer", json={"texte": TEXTE_VALIDE}).status_code == 429
    assert admin.get("/api/v1/ia/statut").json()["plafond_mensuel"] == 1


# ---------------------------------------------------------------- 3. assistant dossier


def _creer_candidat_distinctif(client) -> dict:
    r = client.post(
        "/api/v1/candidats",
        json={
            "nom": "Belkarouizz",
            "prenom": "Zoubeidaxx",
            "sexe": "F",
            "date_naissance": "2002-04-12",
            "lieu_naissance": "Alger",
            "nationalite": "Algérienne",
            "pays_residence": "Algérie",
            "numero_passeport": "XQ7788991",
            "date_expiration_passeport": "2030-09-01",
            "email": "belkarouizz.unique@exemple.dz",
            "telephone": "+213555112233",
            "adresse": "Hydra, Alger",
            "niveau_actuel": "Licence 3 Informatique",
            "programme_vise": "Master 1 Génie Logiciel",
            "etablissement_vise": "Université Paris-Saclay",
            "fonds_disponibles_eur": 8500,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


VALEURS_IDENTIFIANTES = [
    "Belkarouizz",
    "Zoubeidaxx",
    "belkarouizz.unique@exemple.dz",
    "XQ7788991",
    "+213555112233",
    "555112233",
    "Hydra",
]


def test_assistant_dossier_sans_pii_et_roles(application, deux_bureaux) -> None:
    bureau_a, bureau_b = deux_bureaux
    admin, _ = connecter_client(application, bureau_a.admin.email)
    candidat = _creer_candidat_distinctif(admin)
    faux = _brancher(application, ReponseLLM(texte="Réunissez le passeport.", tokens_entree=3, tokens_sortie=2))

    employe, _ = connecter_client(application, bureau_a.employe.email)
    question = "Que manque-t-il pour jean.dupont@exemple.com, tel +213 661 23 45 67, passeport 123456789 ?"
    r = employe.post(
        f"/api/v1/ia/dossiers/{candidat['id']}/assistant",
        json={"code_demarche": "campus_france", "question": question},
    )
    assert r.status_code == 200, r.text
    assert r.json()["reponse"] == "Réunissez le passeport."
    assert "mention" in r.json()

    message = faux.appels[0]["message"]
    for valeur in VALEURS_IDENTIFIANTES:
        assert valeur not in message, valeur
    for pii in ("jean.dupont@exemple.com", "661 23 45 67", "123456789"):
        assert pii not in message, pii
    assert "[email]" in message
    assert "Procédure :" in message

    # Lecteur : interdit.
    lecteur, _ = connecter_client(application, bureau_a.lecteur.email)
    r = lecteur.post(
        f"/api/v1/ia/dossiers/{candidat['id']}/assistant",
        json={"code_demarche": "campus_france", "question": "Où en est-on ?"},
    )
    assert r.status_code == 403

    # Isolation : un autre bureau ne voit pas ce candidat.
    admin_b, _ = connecter_client(application, bureau_b.admin.email)
    nb = len(faux.appels)
    r = admin_b.post(
        f"/api/v1/ia/dossiers/{candidat['id']}/assistant",
        json={"code_demarche": "campus_france", "question": "Où en est-on ?"},
    )
    assert r.status_code == 404
    assert len(faux.appels) == nb


def test_assistant_dossier_demarche_inconnue_et_reponse_vide(application, deux_bureaux) -> None:
    bureau_a, _ = deux_bureaux
    admin, _ = connecter_client(application, bureau_a.admin.email)
    candidat = _creer_candidat_distinctif(admin)
    _brancher(application, ReponseLLM(texte=""))
    r = admin.post(
        f"/api/v1/ia/dossiers/{candidat['id']}/assistant",
        json={"code_demarche": "inexistante", "question": "Bonjour ?"},
    )
    assert r.status_code in (404, 422)
    r = admin.post(
        f"/api/v1/ia/dossiers/{candidat['id']}/assistant",
        json={"code_demarche": "campus_france", "question": "Bonjour ?"},
    )
    assert r.status_code == 422  # réponse vide


# ---------------------------------------------------------------- 4. ClientAnthropic


class FausseReponseHttp:
    def __init__(self, statut: int = 200, donnees: Any = None, corps_brut: str | None = None) -> None:
        self.status_code = statut
        self._donnees = donnees
        self.text = corps_brut if corps_brut is not None else json.dumps(donnees)

    def json(self) -> Any:
        if self._donnees is None:
            raise ValueError("pas du JSON")
        return self._donnees


def _client() -> ClientAnthropic:
    return ClientAnthropic(
        cle="cle-secrete-xyz", modele="modele-test", url="https://exemple.test/v1/messages", delai_secondes=7
    )


def test_client_anthropic_requete_et_reponse(monkeypatch) -> None:
    capture: dict[str, Any] = {}

    def faux_post(url, **kwargs):
        capture["url"] = url
        capture.update(kwargs)
        return FausseReponseHttp(
            200,
            {
                "content": [
                    {"type": "text", "text": " Bonjour "},
                    {"type": "tool_use", "name": "outil_x", "input": {"a": 1}},
                    {"type": "text", "text": "monde "},
                ],
                "usage": {"input_tokens": 12, "output_tokens": 34},
            },
        )

    monkeypatch.setattr(httpx, "post", faux_post)
    outil = {"name": "outil_x", "description": "d", "input_schema": {"type": "object", "properties": {}}}
    rep = _client().generer(systeme="SYS", message="MSG", outil=outil, max_tokens=99)

    assert capture["url"] == "https://exemple.test/v1/messages"
    assert capture["timeout"] == 7
    assert capture["headers"]["x-api-key"] == "cle-secrete-xyz"
    assert capture["headers"]["anthropic-version"] == llm.VERSION_API_ANTHROPIC
    corps = capture["json"]
    assert corps["model"] == "modele-test"
    assert corps["max_tokens"] == 99
    assert corps["system"] == "SYS"
    assert corps["messages"] == [{"role": "user", "content": "MSG"}]
    assert corps["tools"] == [outil]
    assert corps["tool_choice"] == {"type": "tool", "name": "outil_x"}
    assert rep.texte == "Bonjour monde"
    assert rep.outil == {"a": 1}
    assert (rep.tokens_entree, rep.tokens_sortie) == (12, 34)


def test_client_anthropic_sans_outil(monkeypatch) -> None:
    capture: dict[str, Any] = {}

    def faux_post(url, **kwargs):
        capture.update(kwargs)
        return FausseReponseHttp(200, {"content": [{"type": "text", "text": "ok"}]})

    monkeypatch.setattr(httpx, "post", faux_post)
    rep = _client().generer(systeme="s", message="m")
    assert "tools" not in capture["json"] and "tool_choice" not in capture["json"]
    assert rep.texte == "ok" and rep.outil is None
    assert (rep.tokens_entree, rep.tokens_sortie) == (0, 0)


@pytest.mark.parametrize("statut", [401, 403, 429, 500, 503, 400])
def test_client_anthropic_erreurs_http_sans_fuite(monkeypatch, statut) -> None:
    secret = "CORPS-SECRET-NE-PAS-FUIR cle-secrete-xyz"
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FausseReponseHttp(statut, None, secret))
    with pytest.raises(ServiceIndisponible) as exc:
        _client().generer(systeme="s", message="m")
    assert "SECRET" not in str(exc.value) and "cle-secrete" not in str(exc.value)


@pytest.mark.parametrize(
    "erreur", [httpx.TimeoutException("délai dépassé cle-secrete-xyz"), httpx.ConnectError("boom")]
)
def test_client_anthropic_reseau(monkeypatch, erreur) -> None:
    def faux_post(*a, **k):
        raise erreur

    monkeypatch.setattr(httpx, "post", faux_post)
    with pytest.raises(ServiceIndisponible) as exc:
        _client().generer(systeme="s", message="m")
    assert "cle-secrete" not in str(exc.value)


def test_client_anthropic_reponse_illisible(monkeypatch) -> None:
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FausseReponseHttp(200, None, "<html>"))
    with pytest.raises(ServiceIndisponible):
        _client().generer(systeme="s", message="m")


def test_client_anthropic_json_non_objet(monkeypatch) -> None:
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FausseReponseHttp(200, ["pas", "un", "objet"]))
    with pytest.raises(ServiceIndisponible):
        _client().generer(systeme="s", message="m")


# ---------------------------------------------------------------- 5. schéma de l'outil


def test_schema_outil_acceptable() -> None:
    schema = assistant_ia.schema_outil_procedure()
    assert schema["type"] == "object"
    assert "properties" in schema and "code" in schema["properties"]
    assert "code" in schema["required"]
    texte = json.dumps(schema)
    assert "$ref" not in texte and "$defs" not in texte
    # Les sous-objets sont bien développés.
    items = schema["properties"]["pieces_requises"]["items"]
    assert items["type"] == "object" and "type_piece" in items["properties"]
    # Le schéma aplati reste équivalent : une définition valide passe toujours la validation.
    ConfigDemarche.model_validate(_outil_valide() | {"code": "visa_test"})
