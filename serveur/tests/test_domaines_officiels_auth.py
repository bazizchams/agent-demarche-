"""Règle 6 : domaines officiels (portails réels) issus des YAML, y compris les domaines d'authentification.

Aucun accès réseau. On vérifie que chaque hôte déclaré dans `domaines_autorises` est accepté en HTTPS,
que les imitateurs, le HTTP et les formes douteuses sont refusés, et que les YAML ne contiennent que des
hôtes exacts (pas de joker, de schéma, de chemin ni de port).
"""

from __future__ import annotations

import re

import pytest

from app.agent_local.domaines_officiels import politique_depuis_parametres
from app.core.config import Parametres

HOTE_EXACT = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")


def _domaines(parametres: Parametres) -> list[str]:
    return sorted(politique_depuis_parametres(parametres).domaines_https)


def test_domaines_yaml_sont_des_hotes_exacts(parametres_test: Parametres) -> None:
    domaines = _domaines(parametres_test)
    assert domaines, "aucun domaine officiel chargé depuis config/portails"
    for domaine in domaines:
        assert HOTE_EXACT.match(domaine), f"hôte non exact dans les YAML : {domaine}"
        assert "*" not in domaine
    # Pas de domaine de tête trop large (ex. « gc.ca », « gouv.fr », « org ») : au moins 3 labels
    # ou un domaine de société explicite.
    for domaine in domaines:
        assert domaine.count(".") >= 2, f"domaine trop large : {domaine}"


def test_chaque_domaine_officiel_est_accepte_en_https(parametres_test: Parametres) -> None:
    politique = politique_depuis_parametres(parametres_test)
    for domaine in _domaines(parametres_test):
        assert politique.motif_refus(f"https://{domaine}/") is None
        assert politique.motif_refus(f"https://{domaine.upper()}/chemin?lang=fr") is None
        assert politique.origine_autorisee(f"https://{domaine}") is True


def test_chaque_domaine_officiel_est_refuse_en_http(parametres_test: Parametres) -> None:
    politique = politique_depuis_parametres(parametres_test)
    for domaine in _domaines(parametres_test):
        motif = politique.motif_refus(f"http://{domaine}/")
        assert motif is not None and "HTTPS" in motif


def test_imitateurs_des_domaines_officiels_sont_refuses(parametres_test: Parametres) -> None:
    politique = politique_depuis_parametres(parametres_test)
    for domaine in _domaines(parametres_test):
        imitateurs = [
            f"https://{domaine}.pirate.example/",  # officiel en préfixe
            f"https://pirate-{domaine}/",  # tiret collé
            f"https://sous.{domaine}/",  # sous-domaine implicite non déclaré
            f"https://{domaine}@pirate.example/",  # identifiants intégrés
            f"https://pirate.example/{domaine}/",  # domaine dans le chemin
            f"https://{domaine}:8443/",  # port non standard
            f"https://{domaine.replace('.', '-')}.example/",
        ]
        for url in imitateurs:
            assert politique.motif_refus(url) is not None, f"imitateur accepté : {url}"
        assert politique.origine_autorisee(f"https://{domaine}.pirate.example") is False


@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        "javascript:alert(1)",
        "data:text/html,<b>x</b>",
        "ftp://portal-portail.apps.cic.gc.ca/",
        "https://",
        "https://localhost/",
        "https://127.0.0.1/",
    ],
)
def test_schemas_et_hotes_inattendus_refuses(parametres_test: Parametres, url: str) -> None:
    assert politique_depuis_parametres(parametres_test).motif_refus(url) is not None


def test_domaines_connexion_documentes_dans_les_yaml(parametres_test: Parametres) -> None:
    """Hôtes de connexion déjà vérifiés (relevé docs/portail_etudes_en_france_reel.md et URL officielle IRCC)."""
    politique = politique_depuis_parametres(parametres_test)
    for url in (
        "https://pastel.diplomatie.gouv.fr/etudesenfrance/dyn/public/authentification/login.html",
        "https://portal-portail.apps.cic.gc.ca/signin?lang=fr",
    ):
        assert politique.motif_refus(url) is None
