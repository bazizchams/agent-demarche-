"""Module dédié au portail officiel IRCC Canada — Demande de permis d'études (Phase 5).

Remplace l'ancienne fonction vide `automatiser_ircc` (défaut D7 de l'audit Phase 0) par un
module complet en mode « pré-remplissage + captures d'écran de contrôle + arrêt avant envoi » :
- Règle 1 (Option A) : exige qu'au moins un sélecteur de signature électronique / transmission
  finale soit déclaré interdit dans `ircc_reel.yaml` et ne clique jamais dessus.
- Règle 2 : suspend immédiatement la tâche si une question de sécurité CléGC, un code 2FA ou un
  CAPTCHA est détecté.
- Règle 3 : ne stocke ni CléGC ni mot de passe IRCC ; vérifie que l'opérateur a ouvert la session.
- Règle 4 : refuse toute valeur par défaut inventée si un champ (EED/DLI, fonds) ou une pièce
  obligatoire (LAP/PAL ou CAQ, LOA, preuve financière, IMM 5645) manque.
- Règle 7 : tous les sélecteurs et URLs proviennent de `config/portails/ircc_reel.yaml`.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page

from app.agent_local.config_portail import ConfigPortailYAML, charger_config_portail
from app.agent_local.executeur_playwright import (
    ClientHttpAgentProtocol,
    ParametresConnexionCoffre,
    ParametresSoumissionValidee,
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


class ModulePortailIRCCCanada:
    """Pilote le pré-remplissage supervisé du portail officiel IRCC Canada (Permis d'études)."""

    CODE_DEMARCHE_ATTENDU = "ircc_permis_etudes"

    def __init__(self, config_portail: ConfigPortailYAML) -> None:
        if config_portail.code_demarche != self.CODE_DEMARCHE_ATTENDU:
            raise ValueError(
                f"Configuration incompatible pour IRCC Canada : code_demarche='{config_portail.code_demarche}'."
            )
        if not config_portail.selecteurs_soumission_interdits:
            raise ErreurSoumissionFinaleInterdite(
                "Règle 1 : la configuration IRCC doit obligatoirement déclarer les "
                "sélecteurs de signature et transmission finale interdits."
            )
        self.config = config_portail

    @classmethod
    def depuis_fichier_yaml(cls, fichier_yaml: Path) -> "ModulePortailIRCCCanada":
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
        url_base_portail: str = "https://portal-portail.apps.cic.gc.ca",
        parametres_url: str = "",
        naviguer_au_demarrage: bool = True,
        dossier_captures_locales: Path | None = None,
        connexion: ParametresConnexionCoffre | None = None,
        soumission: ParametresSoumissionValidee | None = None,
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
            connexion=connexion,
            soumission=soumission,
        )
