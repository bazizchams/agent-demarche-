"""Mode `--mode ecouter` du lanceur : démon d'écoute de l'Agent Local sur le PC du bureau.

Assemble le client API (jeton `X-Agent-Token`), la fenêtre visible (Chrome > Edge > Chromium Playwright,
profil persistant par bureau et par candidat) et le démon. Le jeton se passe de préférence par la variable d'environnement
`BE_JETON_AGENT` (le script `lancer_agent.bat` le fait) : un jeton sur la ligne de commande reste visible
dans la liste des processus.
"""

from __future__ import annotations

import os
import signal
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from types import FrameType
from urllib.parse import urlsplit

import httpx
from playwright.sync_api import sync_playwright

from app.agent_local.action_connexion_portail import executer_connexion_portail
from app.agent_local.action_creation_compte_eef import executer_creation_compte_eef
from app.agent_local.action_voeux_demo import executer_ajout_voeux_demo
from app.agent_local.demon_ecoute import DemonEcoute
from app.agent_local.ouverture_visible import (
    CANAUX_PAR_DEFAUT,
    FenetreVisible,
    restreindre_acces_utilisateur,
)
from app.api.dependances import EN_TETE_JETON_AGENT
from app.modeles.tache import (
    ACTION_AJOUTER_VOEUX_PANIER,
    ACTION_CONNEXION_PORTAIL,
    ACTION_CREATION_COMPTE_EEF,
)

VARIABLE_ENV_JETON = "BE_JETON_AGENT"
CANAUX_CHOISIS: dict[str, tuple[str | None, ...]] = {
    "auto": CANAUX_PAR_DEFAUT,
    "chrome": ("chrome",),
    "msedge": ("msedge",),
    "chromium": (None,),
}
CODE_SORTIE_USAGE = 2
CODE_SORTIE_JETON_REFUSE = 3
HOTES_LOCAUX = frozenset({"localhost", "127.0.0.1"})


def url_serveur_autorisee(url: str) -> bool:
    """https partout ; http seulement vers cette machine (le jeton agent ne circule jamais en clair sur un réseau)."""
    try:
        morceaux = urlsplit(url.strip())
        hote = (morceaux.hostname or "").lower()
        morceaux.port  # noqa: B018 - lève ValueError si le port est invalide
    except ValueError:
        return False
    if not hote:
        return False
    if morceaux.scheme == "https":
        return True
    return morceaux.scheme == "http" and hote in HOTES_LOCAUX


def _installer_arret_propre(demon: DemonEcoute, sortie: Callable[[str], None]) -> None:
    """Premier Ctrl+C / fermeture : arrêt propre après la tâche en cours ; le second interrompt tout."""

    def _gestionnaire(_numero: int, _cadre: FrameType | None) -> None:
        if demon.arret_demande:
            raise KeyboardInterrupt
        sortie("Arrêt demandé : je termine la tâche en cours puis je m'arrête (Ctrl+C encore pour forcer).")
        demon.demander_arret()

    if threading.current_thread() is not threading.main_thread():
        return
    for nom in ("SIGINT", "SIGTERM", "SIGBREAK"):
        numero = getattr(signal, nom, None)
        if numero is not None:
            signal.signal(numero, _gestionnaire)


def lancer_ecoute(
    *,
    url_serveur: str,
    jeton_agent: str,
    racine_profils: Path,
    canal: str = "auto",
    intervalle_sondage_s: float = 5.0,
    headless: bool = False,
    sortie: Callable[[str], None] = print,
) -> int:
    if not url_serveur_autorisee(url_serveur):
        print(
            "Adresse du serveur refusée : le jeton de l'agent ne doit jamais circuler en clair. "
            "Utilisez une adresse https:// (http:// n'est accepté que vers localhost ou 127.0.0.1).",
            file=sys.stderr,
        )
        return CODE_SORTIE_USAGE
    jeton = jeton_agent or os.environ.get(VARIABLE_ENV_JETON, "")
    if not jeton.strip():
        print(
            f"Jeton d'agent manquant : passez --jeton-agent ou définissez {VARIABLE_ENV_JETON} "
            "(utilisez plutôt lancer_agent.bat, qui le demande sans l'afficher).",
            file=sys.stderr,
        )
        return CODE_SORTIE_USAGE

    racine_profils.mkdir(parents=True, exist_ok=True)
    restreindre_acces_utilisateur(racine_profils)  # cookies de portails : réservés à cet utilisateur Windows
    with httpx.Client(
        base_url=url_serveur.rstrip("/"), headers={EN_TETE_JETON_AGENT: jeton.strip()}, timeout=30.0
    ) as client_api:
        try:
            identite = client_api.get("/api/v1/agents-locaux/moi")
        except httpx.HTTPError as exc:
            print(f"Serveur injoignable à {url_serveur} ({type(exc).__name__}).", file=sys.stderr)
            return CODE_SORTIE_USAGE
        if identite.status_code in (401, 403):
            print(
                "Jeton refusé par le serveur (invalide ou révoqué). Demandez un nouveau jeton à "
                "l'administrateur du bureau (Paramètres > Agents locaux).",
                file=sys.stderr,
            )
            return CODE_SORTIE_JETON_REFUSE
        identite.raise_for_status()
        donnees = identite.json()
        sortie(f"Poste « {donnees['nom_machine']} » connecté au bureau {donnees['bureau_id']}.")

        racine_bureau = racine_profils / str(donnees["bureau_id"])
        with sync_playwright() as playwright:
            fenetre = FenetreVisible(
                playwright, racine_bureau, canaux=CANAUX_CHOISIS[canal], headless=headless
            )
            demon = DemonEcoute(
                client_api=client_api,
                fenetre=fenetre,
                executeurs={
                    ACTION_AJOUTER_VOEUX_PANIER: executer_ajout_voeux_demo,
                    ACTION_CONNEXION_PORTAIL: executer_connexion_portail,
                    ACTION_CREATION_COMPTE_EEF: executer_creation_compte_eef,
                },
                url_serveur=url_serveur,
                intervalle_sondage_s=intervalle_sondage_s,
                sortie=sortie,
            )
            _installer_arret_propre(demon, sortie)
            try:
                return demon.boucler()
            except KeyboardInterrupt:
                sortie("Arrêt forcé.")
                return 0
            finally:
                fenetre.fermer()
