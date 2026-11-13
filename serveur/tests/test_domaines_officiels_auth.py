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


# --- Études en France : domaines de connexion / création de compte (relevé du 2026-11-13) -----------------------
# Source : docs/sources_demarches.md, section « Études en France : connexion et création de compte ».

from pathlib import Path  # noqa: E402

from app.agent_local.config_portail import ModePortail, charger_config_portail  # noqa: E402

YAML_EEF_REEL = Path(__file__).resolve().parents[2] / "config" / "portails" / "campus_france_reel.yaml"

DOMAINES_EEF_VERIFIES_2026_11_13 = {
    "etudesenfrance.diplomatie.gouv.fr",
    "pastel.diplomatie.gouv.fr",
    "www.algerie.campusfrance.org",
    "algerie.campusfrance.org",
    "paiement.if-algerie.com",
}


def test_domaines_etudes_en_france_verifies_presents_dans_le_yaml() -> None:
    cfg = charger_config_portail(YAML_EEF_REEL)
    assert cfg.mode_portail == ModePortail.REEL
    assert DOMAINES_EEF_VERIFIES_2026_11_13 <= {d.lower() for d in cfg.domaines_autorises}


def test_domaines_etudes_en_france_commentaires_de_verification() -> None:
    texte = YAML_EEF_REEL.read_text(encoding="utf-8")
    assert texte.count("vérifié le 2026-11-13 sur https://") >= len(DOMAINES_EEF_VERIFIES_2026_11_13)


@pytest.mark.parametrize(
    "url",
    [
        "https://etudesenfrance.diplomatie.gouv.fr/connexion",
        "https://etudesenfrance.diplomatie.gouv.fr/connexion/mot-de-passe-oublie",
        "https://etudesenfrance.diplomatie.gouv.fr/inscription",
        "https://pastel.diplomatie.gouv.fr/etudesenfrance",
        "https://pastel.diplomatie.gouv.fr/etudesenfrance/dyn/public/login.html?ecf=DZ&locale=fr_DZ",
        "https://algerie.campusfrance.org/",
        "https://www.algerie.campusfrance.org/utilisation-de-la-plateforme-etudes-en-france",
        "https://paiement.if-algerie.com/verifier-statut",
    ],
)
def test_domaines_etudes_en_france_pages_connexion_acceptees(parametres_test: Parametres, url: str) -> None:
    assert politique_depuis_parametres(parametres_test).motif_refus(url) is None


@pytest.mark.parametrize(
    "url",
    [
        # Ressources seulement (scripts) : volontairement non autorisé en navigation principale.
        "https://cdn.diplomatie.gouv.fr/yui/yui/3.8.1/yui/yui-min.js",
        # Domaines parents trop larges ou voisins non relevés.
        "https://diplomatie.gouv.fr/",
        "https://campusfrance.org/",
        "https://if-algerie.com/",
        "https://etudesenfrance.diplomatie.gouv.fr.connexion-eef.example/connexion",
        "http://etudesenfrance.diplomatie.gouv.fr/connexion",
    ],
)
def test_domaines_etudes_en_france_hotes_non_releves_refuses(parametres_test: Parametres, url: str) -> None:
    assert politique_depuis_parametres(parametres_test).motif_refus(url) is not None


# --- IRCC : domaines de connexion (relevé du 2026-11-13 sur canada.ca) -------------------------------------------
# Source : docs/sources_demarches.md, section « Domaines d'authentification des portails réels (Règle 6) ».

YAML_IRCC_REEL = Path(__file__).resolve().parents[2] / "config" / "portails" / "ircc_reel.yaml"

DOMAINES_IRCC_VERIFIES_2026_11_13 = {
    "portal-portail.apps.cic.gc.ca",  # IRCC Portal
    "onlineservices-servicesenligne-cic.fjgc-gccf.gc.ca",  # compte sécurisé IRCC (GCKey / Sign-In Partner)
    "clegc-gckey.gc.ca",  # CléGC
    "services.signin.interac-id.ca",  # partenaire de connexion Interac
    "ircc-services.canada.ca",  # IRCC Portal – New version
}


def test_domaines_ircc_verifies_presents_dans_le_yaml() -> None:
    cfg = charger_config_portail(YAML_IRCC_REEL)
    assert cfg.mode_portail == ModePortail.REEL
    assert DOMAINES_IRCC_VERIFIES_2026_11_13 <= {d.lower() for d in cfg.domaines_autorises}


def test_domaines_ircc_commentaires_de_verification() -> None:
    texte = YAML_IRCC_REEL.read_text(encoding="utf-8")
    assert texte.count("vérifié le 2026-11-13 sur https://www.canada.ca/") >= len(DOMAINES_IRCC_VERIFIES_2026_11_13)


@pytest.mark.parametrize(
    "url",
    [
        "https://onlineservices-servicesenligne-cic.fjgc-gccf.gc.ca/mycic/gccf?lang=fra&idp=gckey&svc=/mycic/start",
        "https://onlineservices-servicesenligne-cic.fjgc-gccf.gc.ca/mycic/gccf?lang=eng&idp=securekey&svc=/mycic/start",
        "https://clegc-gckey.gc.ca/j/eng/l",
        "https://services.signin.interac-id.ca/cbs/saml/login?l=1&lang=eng",
        "https://portal-portail.apps.cic.gc.ca/signin?lang=en",
        "https://portal-portail.apps.cic.gc.ca/portal/signin?lang=en",
        "https://ircc-services.canada.ca/cxp/s/login/?language=en_CA&c__LanguageCode=en",
    ],
)
def test_domaines_ircc_pages_connexion_acceptees(parametres_test: Parametres, url: str) -> None:
    assert politique_depuis_parametres(parametres_test).motif_refus(url) is None


@pytest.mark.parametrize(
    "url",
    [
        # hCaptcha chargé par la page CléGC : jamais une destination de navigation (règle 2 : pause).
        "https://newassets.hcaptcha.com/captcha/v1/",
        "https://hcaptcha.com/",
        # Domaines parents trop larges ou voisins non relevés.
        "https://gc.ca/",
        "https://fjgc-gccf.gc.ca/",
        "https://interac-id.ca/",
        "https://canada.ca/",
        # Centre de réception des demandes de visa (prestataire) : documenté, pas un domaine de connexion.
        "https://visa.vfsglobal.com/dza/en/can",
        "https://clegc-gckey.gc.ca.connexion-ircc.example/j/eng/l",
        "http://clegc-gckey.gc.ca/j/eng/l",
    ],
)
def test_domaines_ircc_hotes_non_releves_refuses(parametres_test: Parametres, url: str) -> None:
    assert politique_depuis_parametres(parametres_test).motif_refus(url) is not None
