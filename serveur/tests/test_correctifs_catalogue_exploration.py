"""Régressions de la revue de sécurité : catalogue (R6 sur toute URL, source yaml refusée, exigences
confirmées préservées, date strictement plus récente) et exploration (identifiants de lien, fetch sans redirection)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI

from app.agent_local.domaines_officiels import politique_depuis_parametres
from app.agent_local.portails import exploration_catalogue as exploration
from tests.conftest import connecter_client

URL = "/api/v1/catalogue-formations/fiches"
OFFICIELLE = "https://etudesenfrance.diplomatie.gouv.fr/catalogue-formations/formation/1/site/2"
FICHE = {
    "etablissement": "Université Fictive", "intitule": "Master Fictif", "niveau_entree_bac_plus": 4,
    "francais_min": "B2", "date_releve": "2026-11-13", "source": "manuel",
}


def _client(application: FastAPI, deux_bureaux):
    client, _ = connecter_client(application, deux_bureaux[0].employe.email)
    return client


def test_url_hors_domaine_officiel_refusee_meme_en_source_manuelle(application: FastAPI, deux_bureaux) -> None:
    c = _client(application, deux_bureaux)
    pirate = {**FICHE, "url_officielle": "https://pirate.example.com/x"}
    assert c.post(URL, json={"fiches": [pirate]}).status_code == 422
    assert c.post(URL, json={"fiches": [{**FICHE, "url_officielle": OFFICIELLE}]}).status_code == 200


def test_source_yaml_refusee_depuis_l_api(application: FastAPI, deux_bureaux) -> None:
    c = _client(application, deux_bureaux)
    assert c.post(URL, json={"fiches": [{**FICHE, "source": "yaml"}]}).status_code == 422


def test_import_non_manuel_n_ecrase_pas_les_exigences_confirmees(application: FastAPI, deux_bureaux) -> None:
    c = _client(application, deux_bureaux)
    c.post(URL, json={"fiches": [{**FICHE, "aucune_exigence_confirmee": ["moyenne"]}]})
    plus_recente = {**FICHE, "source": "exploration", "date_releve": "2026-11-14", "url_officielle": OFFICIELLE}
    assert c.post(URL, json={"fiches": [plus_recente]}).json()["mises_a_jour"] == 1
    assert c.get("/api/v1/catalogue-formations").json()[0]["aucune_exigence_confirmee"] == ["moyenne"]
    # un import manuel plus récent, lui, peut la modifier
    manuel = {**FICHE, "date_releve": "2026-11-15", "aucune_exigence_confirmee": []}
    c.post(URL, json={"fiches": [manuel]})
    assert c.get("/api/v1/catalogue-formations").json()[0]["aucune_exigence_confirmee"] == []


def test_meme_date_manuelle_ne_modifie_pas_les_exigences_confirmees(application: FastAPI, deux_bureaux) -> None:
    c = _client(application, deux_bureaux)
    c.post(URL, json={"fiches": [{**FICHE, "aucune_exigence_confirmee": ["moyenne"]}]})
    c.post(URL, json={"fiches": [{**FICHE, "aucune_exigence_confirmee": []}]})  # même date : pas strictement plus récent
    assert c.get("/api/v1/catalogue-formations").json()[0]["aucune_exigence_confirmee"] == ["moyenne"]


class _Locator:
    def __init__(self, hrefs: list[str]) -> None:
        self.hrefs = hrefs

    def evaluate_all(self, _js: str) -> list[str]:
        return self.hrefs


class _Page:
    def __init__(self, hrefs: list[str]) -> None:
        self.url = "https://etudesenfrance.diplomatie.gouv.fr/catalogue-formations"
        self.hrefs, self.lus = hrefs, []

    def locator(self, _s: str) -> _Locator:
        return _Locator(self.hrefs)

    def evaluate(self, _js: str, api: str) -> dict[str, Any]:
        self.lus.append(api)
        return {"__erreur": 404}


def test_exploration_ignore_les_identifiants_non_conformes(parametres_test) -> None:
    base = "https://etudesenfrance.diplomatie.gouv.fr/catalogue-formations/formation/"
    page = _Page([base + "12%2F..%2Fadmin/site/3", base + "a.b/site/3", base + "4/site/x:y", base + "ok_1-2/site/S-3"])
    res = exploration.explorer_catalogue(page, politique_depuis_parametres(parametres_test))
    assert len(page.lus) == 1 and "/formations/ok_1-2/site/S-3" in page.lus[0]
    assert len([i for i in res.ignorees if "Identifiant" in i["raison"]]) == 3


def test_fetch_sans_redirection_automatique() -> None:
    assert 'redirect: "manual"' in exploration._JS_LIRE_FICHE_GET
