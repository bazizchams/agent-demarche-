"""Fournisseurs d'IA (Anthropic / compatible OpenAI) et anonymisation : aucun accès réseau."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
import pytest

from app.core.config import Parametres
from app.core.erreurs import ServiceIndisponible
from app.services import llm
from app.services.anonymisation_ia import ClientAnonymisant, anonymiser
from app.services.llm import (
    ClientAnthropic,
    ClientOpenAICompatible,
    construire_client,
    etat_ia,
    hote_est_local,
)

CLE = "cle-ultra-secrete-123"


def _params(**champs: Any) -> Parametres:
    base = {"ia_fournisseur": "openai_compatible", "ia_modele": "m1", "cle_api_anthropic": None}
    return Parametres(**(base | champs))


@pytest.fixture(autouse=True)
def _sans_attente(monkeypatch):
    monkeypatch.setattr(llm, "_pause", lambda s: None)


def _transport(reponses: list[httpx.Response | Exception], vus: list[httpx.Request]):
    file = list(reponses)

    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        vus.append(requete)
        suivant = file.pop(0) if len(file) > 1 else file[0]
        if isinstance(suivant, Exception):
            raise suivant
        return suivant

    return httpx.MockTransport(gestionnaire)


def _ok(contenu: str = "bonjour", **msg: Any) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": contenu, **msg}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 7},
        },
    )


def _client(transport, **kw: Any) -> ClientOpenAICompatible:
    return ClientOpenAICompatible(
        url_base="http://127.0.0.1:11434/v1/", modele="m1", cle=kw.pop("cle", None),
        tentatives=kw.pop("tentatives", 2), transport=transport, **kw,
    )


OUTIL = {"name": "outil_x", "description": "d", "input_schema": {"type": "object", "properties": {}}}


# ------------------------------------------------------------ sélection du fournisseur


def test_defaut_anthropic_sans_cle_desactive() -> None:
    p = Parametres(cle_api_anthropic=None)
    assert construire_client(p) is None
    assert etat_ia(p).active is False and etat_ia(p).fournisseur == "anthropic"


def test_anthropic_avec_cle_est_anonymise() -> None:
    p = Parametres(cle_api_anthropic=CLE)
    client = construire_client(p)
    assert isinstance(client, ClientAnonymisant)
    assert isinstance(client._client, ClientAnthropic)
    etat = etat_ia(p)
    assert etat.active and etat.donnees_quittent_serveur
    assert CLE not in etat.message


def test_openai_local_sans_anonymisation_ni_cle() -> None:
    p = _params(ia_url_base="http://localhost:11434/v1")
    client = construire_client(p)
    assert isinstance(client, ClientOpenAICompatible)
    etat = etat_ia(p)
    assert etat.active and etat.donnees_quittent_serveur is False
    assert "ne quittent pas" in etat.message


def test_openai_hebergé_est_anonymise() -> None:
    p = _params(ia_url_base="https://api.groq.com/openai/v1", ia_cle=CLE)
    client = construire_client(p)
    assert isinstance(client, ClientAnonymisant)
    etat = etat_ia(p)
    assert etat.donnees_quittent_serveur and "api.groq.com" in etat.message
    assert CLE not in etat.message


def test_openai_configuration_incomplete_ou_fournisseur_inconnu() -> None:
    assert construire_client(_params(ia_url_base=None)) is None
    assert "requis" in etat_ia(_params(ia_url_base=None)).message
    inconnu = _params(ia_fournisseur="truc")
    assert construire_client(inconnu) is None and "inconnu" in etat_ia(inconnu).message
    with pytest.raises(ServiceIndisponible):
        llm.obtenir_client_llm(inconnu)


@pytest.mark.parametrize(
    "url,attendu",
    [
        ("http://localhost:11434/v1", True),
        ("http://127.0.0.1:8080/v1", True),
        ("http://[::1]:8080/v1", True),
        ("http://192.168.1.20:11434/v1", True),
        ("http://host.docker.internal:11434/v1", True),
        ("https://api.mistral.ai/v1", False),
        ("https://8.8.8.8/v1", False),
        ("https://localhost.evil.com/v1", False),
    ],
)
def test_hote_est_local(url, attendu) -> None:
    assert hote_est_local(url) is attendu


# ------------------------------------------------------------ requête / réponse


def test_requete_openai_sans_cle_et_avec_outil() -> None:
    vus: list[httpx.Request] = []
    t = _transport([_ok("", tool_calls=[{"function": {"name": "outil_x", "arguments": '{"a": 1}'}}])], vus)
    rep = _client(t).generer(systeme="SYS", message="MSG", outil=OUTIL, max_tokens=50)
    req = vus[0]
    assert str(req.url) == "http://127.0.0.1:11434/v1/chat/completions"
    assert "authorization" not in req.headers
    corps = json.loads(req.content)
    assert corps["model"] == "m1" and corps["max_tokens"] == 50
    assert corps["messages"] == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "MSG"},
    ]
    assert corps["tools"][0]["function"]["name"] == "outil_x"
    assert corps["tool_choice"]["function"]["name"] == "outil_x"
    assert rep.outil == {"a": 1} and (rep.tokens_entree, rep.tokens_sortie) == (5, 7)


def test_cle_envoyee_en_bearer_si_fournie() -> None:
    vus: list[httpx.Request] = []
    _client(_transport([_ok()], vus), cle=CLE).generer(systeme="s", message="m")
    assert vus[0].headers["authorization"] == f"Bearer {CLE}"


def test_texte_simple() -> None:
    rep = _client(_transport([_ok("  salut ")], [])).generer(systeme="s", message="m")
    assert rep.texte == "salut" and rep.outil is None


def test_json_dans_le_texte_si_pas_d_appel_d_outil() -> None:
    contenu = 'Voici :\n```json\n{"code": "visa_x"}\n```'
    rep = _client(_transport([_ok(contenu)], [])).generer(systeme="s", message="m", outil=OUTIL)
    assert rep.outil == {"code": "visa_x"}


def test_repli_sans_outil_sur_400() -> None:
    vus: list[httpx.Request] = []
    t = _transport([httpx.Response(400, text="tools non supportés"), _ok('{"a": 2}')], vus)
    rep = _client(t).generer(systeme="SYS", message="m", outil=OUTIL)
    assert len(vus) == 2
    second = json.loads(vus[1].content)
    assert "tools" not in second and "JSON" in second["messages"][0]["content"]
    assert rep.outil == {"a": 2}


# ------------------------------------------------------------ erreurs et retries


def test_retries_sur_429_puis_succes() -> None:
    vus: list[httpx.Request] = []
    t = _transport([httpx.Response(429), _ok("ok")], vus)
    assert _client(t, tentatives=3).generer(systeme="s", message="m").texte == "ok"
    assert len(vus) == 2


def test_retries_epuises() -> None:
    vus: list[httpx.Request] = []
    t = _transport([httpx.Response(503)], vus)
    with pytest.raises(ServiceIndisponible, match="saturé"):
        _client(t, tentatives=3).generer(systeme="s", message="m")
    assert len(vus) == 3


def test_erreur_reseau_message_clair() -> None:
    t = _transport([httpx.ConnectError(f"boom {CLE} http://x")], [])
    with pytest.raises(ServiceIndisponible, match="injoignable") as exc:
        _client(t, cle=CLE).generer(systeme="s", message="m")
    assert CLE not in str(exc.value)


@pytest.mark.parametrize("statut", [401, 403, 400, 404, 429, 500])
def test_aucune_cle_ni_corps_dans_les_erreurs(statut) -> None:
    secret = f"CORPS-SECRET {CLE}"
    t = _transport([httpx.Response(statut, text=secret)], [])
    with pytest.raises(ServiceIndisponible) as exc:
        _client(t, cle=CLE, tentatives=1).generer(systeme="s", message="m")
    assert CLE not in str(exc.value) and "SECRET" not in str(exc.value)


@pytest.mark.parametrize(
    "reponse",
    [
        httpx.Response(200, text="<html>"),
        httpx.Response(200, json=["x"]),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"choices": [{"message": "x"}]}),
    ],
)
def test_reponse_illisible(reponse) -> None:
    with pytest.raises(ServiceIndisponible):
        _client(_transport([reponse], [])).generer(systeme="s", message="m")


def test_aucune_cle_dans_les_logs(caplog) -> None:
    t = _transport([httpx.ConnectError("x"), _ok("ok")], [])
    with caplog.at_level(logging.DEBUG):
        _client(t, cle=CLE).generer(systeme="s", message="m")
    assert CLE not in caplog.text


# ------------------------------------------------------------ anonymisation


def test_anonymiser_donnees_personnelles() -> None:
    texte = (
        "Contact jean.dupont@exemple.com ou +213 661 23 45 67 / 0661234567. "
        "Passeport n° 123456789 et 12AB34567, ancien AB1234567. "
        "Nom : Belkacem Amine\nPrénom: Yacine\n"
        "Mme Zoubeida a un dossier. Échéance 2026-12-01, frais 200 EUR."
    )
    sortie = anonymiser(texte, termes=["Zoubeida", "belkacem"])
    for sensible in (
        "jean.dupont", "661 23 45 67", "0661234567", "123456789", "12AB34567",
        "AB1234567", "Belkacem", "Amine", "Yacine", "Zoubeida",
    ):
        assert sensible not in sortie, sensible
    assert "2026-12-01" in sortie and "200 EUR" in sortie


def test_anonymiser_respecte_les_mots() -> None:
    assert anonymiser("Amineral", termes=["Amine"]) == "Amineral"


def test_client_anonymisant_transmet_texte_nettoye() -> None:
    vus: list[httpx.Request] = []
    interne = _client(_transport([_ok("ok")], vus))
    ClientAnonymisant(interne, termes=["Dupont"]).generer(
        systeme="Aide Dupont", message="écris à a@b.dz pour Dupont"
    )
    envoye = vus[0].content.decode()
    assert "a@b.dz" not in envoye and "Dupont" not in envoye and "[email]" in envoye


def test_fournisseur_hebergé_anonymise_avant_envoi() -> None:
    p = _params(ia_url_base="https://api.groq.com/openai/v1", ia_cle=CLE)
    vus: list[httpx.Request] = []
    client = construire_client(p, transport=_transport([_ok("ok")], vus))
    client.generer(systeme="s", message="passeport n° 123456789 de x@y.com")
    envoye = vus[0].content.decode()
    assert "123456789" not in envoye and "x@y.com" not in envoye
    assert vus[0].headers["authorization"] == f"Bearer {CLE}"
