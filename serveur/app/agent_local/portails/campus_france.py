"""Module dédié au portail officiel Campus France / Études en France Algérie (Phase 5).

Fonctionne exclusivement en mode « pré-remplissage + captures d'écran de contrôle + arrêt avant envoi » :
- Règle 1 (Option A) : exige qu'au moins un sélecteur de soumission finale soit déclaré interdit
  dans `campus_france_reel.yaml` et ne clique jamais dessus.
- Règle 2 : suspend immédiatement la tâche si un CAPTCHA ou un défi 2FA est détecté.
- Règle 3 : ne stocke aucun mot de passe Études en France ; vérifie que l'opérateur a ouvert la session.
- Règle 4 : refuse toute valeur par défaut inventée si un champ ou une pièce manque.
- Règle 7 : tous les sélecteurs et URLs proviennent de `config/portails/campus_france_reel.yaml`.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page

from app.agent_local.config_portail import ConfigPortailYAML, charger_config_portail
from app.agent_local.executeur_playwright import (
    ClientHttpAgentProtocol,
    ResultatExecutionAgentLocal,
    executer_tache_sur_page_playwright,
)
from app.agent_local.garde_fous import ErreurSoumissionFinaleInterdite
from app.agent_local.portails.verificateur_portail import (
    RapportDiagnosticPagePortail,
    ResultatVerificationURL,
    diagnostiquer_page_portail,
    verifier_url_officielle_portail,
)


class ModulePortailCampusFrance:
    """Pilote le pré-remplissage supervisé du portail Études en France (Campus France Algérie)."""

    CODE_DEMARCHE_ATTENDU = "campus_france"

    def __init__(self, config_portail: ConfigPortailYAML) -> None:
        if config_portail.code_demarche != self.CODE_DEMARCHE_ATTENDU:
            raise ValueError(
                f"Configuration incompatible pour Campus France : code_demarche='{config_portail.code_demarche}'."
            )
        if not config_portail.selecteurs_soumission_interdits:
            raise ErreurSoumissionFinaleInterdite(
                "Règle 1 : la configuration Campus France doit obligatoirement déclarer les "
                "sélecteurs de soumission finale interdits (selecteurs_soumission_interdits)."
            )
        self.config = config_portail

    @classmethod
    def depuis_fichier_yaml(cls, fichier_yaml: Path) -> "ModulePortailCampusFrance":
        return cls(charger_config_portail(fichier_yaml))

    def verifier_url(self, *, url_surcharge: str | None = None, client_http=None) -> ResultatVerificationURL:
        return verifier_url_officielle_portail(
            self.config, url_surcharge=url_surcharge, client_http=client_http
        )

    def diagnostiquer_page_ouverte(
        self, page: Page, *, dossier_captures_locales: Path | None = None
    ) -> RapportDiagnosticPagePortail:
        return diagnostiquer_page_portail(
            page, self.config, dossier_captures_locales=dossier_captures_locales
        )

    def executer_preremplissage_avec_arret_avant_envoi(
        self,
        page: Page,
        *,
        tache_id: str,
        client_api: ClientHttpAgentProtocol,
        url_base_portail: str = "https://pastel.diplomatie.gouv.fr",
        parametres_url: str = "",
        naviguer_au_demarrage: bool = True,
        dossier_captures_locales: Path | None = None,
    ) -> ResultatExecutionAgentLocal:
        return executer_tache_sur_page_playwright(
            page,
            tache_id=tache_id,
            client_api=client_api,
            config_portail=self.config,
            url_base_portail=url_base_portail,
            parametres_url=parametres_url,
            naviguer_au_demarrage=naviguer_au_demarrage,
            dossier_captures_locales=dossier_captures_locales,
        )
