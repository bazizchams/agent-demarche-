"""Règle 6 en ligne : politique de navigation du Co-Pilote (domaines HTTPS officiels uniquement).

Les domaines officiels viennent EXCLUSIVEMENT des fichiers YAML `config/portails/*.yaml` des portails
en mode « reel » (`domaines_autorises`). Comparaison sur le nom d'hôte EXACT (pas de sous-domaine
implicite, pas de « se termine par ») pour écarter les domaines imitateurs
(ex. `etudesenfrance.diplomatie.gouv.fr.pirate.example`). Les pages de démonstration `/demo/...`
ne sont acceptées que hors production.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from app.core.config import Environnement, Parametres

# Hôtes servant les pages de démonstration (hors production uniquement) : l'hôte virtuel intercepté par
# le pilote, et l'application elle-même en local.
HOTES_DEMO: frozenset[str] = frozenset({"portail.local", "127.0.0.1", "localhost", "::1"})
PREFIXE_CHEMIN_DEMO = "/demo/"


@dataclass(frozen=True)
class PolitiqueNavigation:
    domaines_https: frozenset[str]
    autoriser_demo: bool = False

    def motif_refus(self, url: str | None) -> str | None:
        """None si la navigation vers `url` est autorisée, sinon un message en français
        (jamais l'URL complète : seulement l'hôte, sans paramètres)."""
        brut = (url or "").strip()
        if not brut:
            return "Navigation refusée (Règle 6) : adresse vide."
        try:
            analyse = urlparse(brut)
            hote = (analyse.hostname or "").lower().rstrip(".")
            port = analyse.port
        except ValueError:
            return "Navigation refusée (Règle 6) : adresse invalide."

        schema = analyse.scheme.lower()
        if analyse.username is not None or analyse.password is not None:
            return "Navigation refusée (Règle 6) : adresse avec identifiants intégrés."

        if schema == "https" and hote in self.domaines_https and port in (None, 443):
            return None

        if (
            self.autoriser_demo
            and schema in ("http", "https")
            and hote in HOTES_DEMO
            and (analyse.path or "").startswith(PREFIXE_CHEMIN_DEMO)
        ):
            return None

        if schema != "https":
            return (
                "Navigation refusée (Règle 6) : seules les adresses HTTPS des portails officiels "
                "sont autorisées."
            )
        return (
            f"Navigation refusée (Règle 6) : le domaine « {hote or '?'} » ne figure pas parmi les "
            "domaines officiels autorisés."
        )

    def origine_autorisee(self, origine: str | None) -> bool:
        """Utilisé pour le CORS du pont : l'origine (schéma + hôte) d'une page officielle ou de démo."""
        if not origine:
            return False
        try:
            analyse = urlparse(origine)
            hote = (analyse.hostname or "").lower().rstrip(".")
        except ValueError:
            return False
        if analyse.path not in ("", "/") or analyse.username is not None:
            return False
        if analyse.scheme == "https" and hote in self.domaines_https and analyse.port in (None, 443):
            return True
        return self.autoriser_demo and analyse.scheme in ("http", "https") and hote in HOTES_DEMO


def charger_domaines_officiels(parametres: Parametres) -> frozenset[str]:
    from app.agent_local.config_portail import ModePortail, lister_configs_portails

    domaines: set[str] = set()
    for cfg in lister_configs_portails(parametres.dossier_portails).values():
        if cfg.mode_portail != ModePortail.REEL:
            continue
        domaines.update(d.strip().lower() for d in cfg.domaines_autorises if d.strip())
    return frozenset(domaines)


def politique_depuis_parametres(parametres: Parametres) -> PolitiqueNavigation:
    return PolitiqueNavigation(
        domaines_https=charger_domaines_officiels(parametres),
        autoriser_demo=parametres.environnement is not Environnement.PRODUCTION,
    )
