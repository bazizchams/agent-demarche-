"""Ouverture du navigateur VISIBLE de l'Agent Local sur le PC du bureau.

- Ordre de préférence : Google Chrome installé, puis Microsoft Edge (installé d'office sur Windows),
  puis le Chromium fourni par Playwright (`python -m playwright install chromium`).
- Fenêtre visible (`headless=False`, maximisée) amenée au premier plan.
- Profil persistant par bureau ET par navigateur : `<racine_profils>/<bureau_id>/<canal>` (les cookies d'un
  portail restent d'une exécution à l'autre ; deux navigateurs différents ne partagent jamais un profil).
- Règle 3 : le mot de passe d'un portail n'est jamais fourni par ce module ; la connexion se fait à la
  main dans la fenêtre visible. Règle 6 : ce module n'ouvre aucune URL, il fournit seulement la fenêtre.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from playwright.sync_api import BrowserContext, Page

journal = logging.getLogger("app.agent_local.ouverture_visible")

# `None` = Chromium fourni par Playwright.
CANAUX_PAR_DEFAUT: tuple[str | None, ...] = ("chrome", "msedge", None)
NOM_PROFIL_CHROMIUM_PLAYWRIGHT = "chromium"
VIEWPORT_HEADLESS = {"width": 1280, "height": 900}

MESSAGE_AUCUN_NAVIGATEUR = (
    "Aucun navigateur n'a pu être ouvert (Chrome et Edge introuvables, Chromium de Playwright absent). "
    "Installez Google Chrome, ou lancez : python -m playwright install chromium"
)


class ErreurOuvertureNavigateur(RuntimeError):
    """Aucun des navigateurs candidats n'a pu être ouvert."""


def dossier_profil_canal(racine_bureau: Path, canal: str | None) -> Path:
    return racine_bureau / (canal or NOM_PROFIL_CHROMIUM_PLAYWRIGHT)


def ouvrir_contexte_visible(
    playwright: Any,
    racine_profil_bureau: Path,
    *,
    canaux: Sequence[str | None] = CANAUX_PAR_DEFAUT,
    headless: bool = False,
) -> tuple[BrowserContext, str]:
    """Ouvre le premier navigateur disponible dans l'ordre de `canaux`. Retourne (contexte, nom du canal)."""
    derniere_erreur: Exception | None = None
    for canal in canaux:
        profil = dossier_profil_canal(racine_profil_bureau, canal)
        profil.mkdir(parents=True, exist_ok=True)
        options: dict[str, Any] = {"user_data_dir": str(profil), "headless": headless}
        if canal:
            options["channel"] = canal
        if headless:
            options["viewport"] = dict(VIEWPORT_HEADLESS)
        else:
            options["no_viewport"] = True
            options["args"] = ["--start-maximized"]
        try:
            contexte = playwright.chromium.launch_persistent_context(**options)
        except Exception as exc:  # canal non installé ou profil verrouillé : on essaie le suivant
            derniere_erreur = exc
            journal.info("Navigateur « %s » indisponible : %s", canal or "chromium", type(exc).__name__)
            continue
        nom = canal or NOM_PROFIL_CHROMIUM_PLAYWRIGHT
        journal.info("Navigateur ouvert : %s (profil %s)", nom, profil.name)
        return contexte, nom
    raise ErreurOuvertureNavigateur(MESSAGE_AUCUN_NAVIGATEUR) from derniere_erreur


class FenetreVisible:
    """Fenêtre persistante de l'agent : ouverte à la première tâche, réutilisée, rouverte si l'humain la ferme.

    Elle reste ouverte quand une tâche se termine : l'humain contrôle le remplissage dans SA fenêtre.
    """

    def __init__(
        self,
        playwright: Any,
        racine_profil_bureau: Path,
        *,
        canaux: Sequence[str | None] = CANAUX_PAR_DEFAUT,
        headless: bool = False,
    ) -> None:
        self._playwright = playwright
        self._racine = racine_profil_bureau
        self._canaux = tuple(canaux)
        self._headless = headless
        self._contexte: BrowserContext | None = None
        self.canal: str | None = None

    def _contexte_vivant(self) -> bool:
        if self._contexte is None:
            return False
        try:
            return len(self._contexte.pages) > 0
        except Exception:  # le navigateur a été fermé par l'humain
            return False

    def page(self) -> Page:
        vient_de_s_ouvrir = False
        if not self._contexte_vivant():
            self._fermer_silencieusement()
            self._contexte, self.canal = ouvrir_contexte_visible(
                self._playwright, self._racine, canaux=self._canaux, headless=self._headless
            )
            vient_de_s_ouvrir = True
        assert self._contexte is not None
        pages = self._contexte.pages
        page = pages[0] if pages else self._contexte.new_page()
        if vient_de_s_ouvrir and not self._headless:
            try:
                page.bring_to_front()
            except Exception as exc:
                journal.info("Mise au premier plan impossible : %s", type(exc).__name__)
        return page

    def amener_au_premier_plan(self) -> None:
        if self._headless:
            return
        try:
            self.page().bring_to_front()
        except Exception as exc:
            journal.info("Mise au premier plan impossible : %s", type(exc).__name__)

    def _fermer_silencieusement(self) -> None:
        if self._contexte is not None:
            try:
                self._contexte.close()
            except Exception:
                pass
            self._contexte = None

    def fermer(self) -> None:
        self._fermer_silencieusement()
