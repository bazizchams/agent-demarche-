"""Lanceur en ligne de commande de l'Agent Local Playwright sur le PC Windows du bureau (Phases 4 & 5).

Modes disponibles :
- `--mode diagnostiquer` : inspecte en lecture seule la page ouverte dans le navigateur du bureau
  (domaine autorisé, session ouverte Règle 3, absence de CAPTCHA/2FA Règle 2, présence des sélecteurs YAML Règle 7,
  boutons de soumission finale verrouillés Règle 1) et génère une capture PNG de diagnostic.
- `--mode executer` (défaut) : exécute le module dédié (`ModulePortailCampusFrance` ou `ModulePortailIRCCCanada`)
  en mode « pré-remplissage + captures d'écran de contrôle + arrêt strict avant envoi ».
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

# Permet d'importer `app.agent_local` depuis le dossier voisin `serveur/`
RACINE_PLATEFORME = Path(__file__).resolve().parents[1]
DOSSIER_SERVEUR = RACINE_PLATEFORME / "serveur"
if str(DOSSIER_SERVEUR) not in sys.path:
    sys.path.insert(0, str(DOSSIER_SERVEUR))

from app.agent_local.config_portail import charger_config_portail  # noqa: E402
from app.agent_local.portails import (  # noqa: E402
    ModulePortailCampusFrance,
    ModulePortailIRCCCanada,
    diagnostiquer_page_portail,
    verifier_url_officielle_portail,
)
from app.api.dependances import EN_TETE_JETON_AGENT  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(
        prog="python lanceur.py",
        description=(
            "Agent Local Playwright — Modules Campus France & IRCC "
            "(navigateur visible, profil dédié, captures de contrôle, arrêt avant envoi final)."
        ),
    )
    analyseur.add_argument(
        "--mode",
        choices=["executer", "diagnostiquer"],
        default="executer",
        help="Mode d'action : 'diagnostiquer' (lecture seule) ou 'executer' (pré-remplissage + arrêt avant envoi)",
    )
    analyseur.add_argument(
        "--url-serveur",
        default="http://127.0.0.1:8000",
        help="URL de l'API du serveur",
    )
    analyseur.add_argument(
        "--jeton-agent",
        default="",
        help="Jeton X-Agent-Token généré par l'administrateur (requis en mode executer)",
    )
    analyseur.add_argument(
        "--tache-id",
        default="",
        help="Identifiant UUID de la tâche à exécuter (requis en mode executer)",
    )
    analyseur.add_argument(
        "--config-portail",
        required=True,
        help="Chemin du fichier YAML du portail (ex: config/portails/campus_france_reel.yaml)",
    )
    analyseur.add_argument(
        "--url-base-portail",
        default="",
        help="URL de base du portail (par défaut déduite de url_officielle ou http://127.0.0.1:8000)",
    )
    analyseur.add_argument(
        "--ne-pas-naviguer",
        action="store_true",
        help="Utilise l'onglet déjà ouvert par l'opérateur sans recharger l'URL initiale",
    )
    analyseur.add_argument(
        "--profil-navigateur",
        default=str(RACINE_PLATEFORME / "agent_local" / "profil_chromium"),
        help="Dossier du profil Chromium dédié au bureau",
    )
    analyseur.add_argument(
        "--dossier-captures",
        default=str(RACINE_PLATEFORME / "agent_local" / "captures_controle"),
        help="Dossier local où enregistrer les captures PNG de contrôle étape par étape",
    )
    analyseur.add_argument(
        "--headless",
        action="store_true",
        help="Mode sans fenêtre (pour tests automatisés uniquement)",
    )
    args = analyseur.parse_args(argv)

    config_portail = charger_config_portail(Path(args.config_portail))
    dossier_profil = Path(args.profil_navigateur)
    dossier_profil.mkdir(parents=True, exist_ok=True)
    dossier_captures = Path(args.dossier_captures)
    dossier_captures.mkdir(parents=True, exist_ok=True)

    verif_url = verifier_url_officielle_portail(config_portail)
    if not verif_url.protocole_https_valide or not verif_url.domaine_autorise:
        print(f"[ERREUR URL YAML] {verif_url.message}", file=sys.stderr)
        return 2

    if config_portail.code_demarche == ModulePortailCampusFrance.CODE_DEMARCHE_ATTENDU:
        module_portail = ModulePortailCampusFrance(config_portail)
        url_base_defaut = "https://pastel.diplomatie.gouv.fr"
    elif config_portail.code_demarche == ModulePortailIRCCCanada.CODE_DEMARCHE_ATTENDU:
        module_portail = ModulePortailIRCCCanada(config_portail)
        url_base_defaut = "https://portal-portail.apps.cic.gc.ca"
    else:
        module_portail = None
        url_base_defaut = "http://127.0.0.1:8000"

    url_base = args.url_base_portail or (
        url_base_defaut
        if config_portail.mode_portail.value == "reel"
        else "http://127.0.0.1:8000"
    )

    if args.mode == "diagnostiquer":
        with sync_playwright() as p:
            contexte_nav = p.chromium.launch_persistent_context(
                user_data_dir=str(dossier_profil),
                headless=args.headless,
                viewport={"width": 1280, "height": 900},
            )
            try:
                page = (
                    contexte_nav.pages[0]
                    if contexte_nav.pages
                    else contexte_nav.new_page()
                )
                if not args.ne_pas_naviguer:
                    cible_nav = config_portail.url_officielle or (
                        url_base.rstrip("/") + config_portail.chemin_url
                    )
                    page.goto(cible_nav, wait_until="domcontentloaded")
                rapport = (
                    module_portail.diagnostiquer_page_ouverte(
                        page, dossier_captures_locales=dossier_captures
                    )
                    if module_portail
                    else diagnostiquer_page_portail(
                        page, config_portail, dossier_captures_locales=dossier_captures
                    )
                )
                print(
                    f"=== Diagnostic Portail : {rapport.nom_portail} ({rapport.code_portail}) ===\n"
                    f"- URL courante               : {rapport.url_courante}\n"
                    f"- Protocole HTTPS valide     : {rapport.protocole_https_valide}\n"
                    f"- Domaine autorisé           : {rapport.domaine_autorise}\n"
                    f"- Session ouverte (Règle 3)  : {rapport.session_ouverte_detectee}\n"
                    f"- CAPTCHA / 2FA (Règle 2)    : {rapport.blocage_captcha_ou_2fa_detecte}\n"
                    f"- Sélecteurs YAML détectés   : {len(rapport.selecteurs_detectes)}\n"
                    f"- Sélecteurs YAML manquants  : {len(rapport.selecteurs_manquants)} {rapport.selecteurs_manquants}\n"
                    f"- Boutons finaux verrouillés : {rapport.boutons_soumission_interdits_visibles}\n"
                    f"- Capture diagnostic         : {rapport.chemin_capture_diagnostic}\n"
                    f"- Prêt pour pré-remplissage  : {rapport.pret_pour_preremplissage}"
                )
                return 0 if rapport.pret_pour_preremplissage else 1
            finally:
                contexte_nav.close()

    if not args.jeton_agent or not args.tache_id:
        print(
            "En mode 'executer', --jeton-agent et --tache-id sont obligatoires.",
            file=sys.stderr,
        )
        return 2

    with (
        httpx.Client(
            base_url=args.url_serveur,
            headers={EN_TETE_JETON_AGENT: args.jeton_agent},
            timeout=30.0,
        ) as client_api,
        sync_playwright() as p,
    ):
        contexte_nav = p.chromium.launch_persistent_context(
            user_data_dir=str(dossier_profil),
            headless=args.headless,
            viewport={"width": 1280, "height": 900},
        )
        try:
            page = (
                contexte_nav.pages[0]
                if contexte_nav.pages
                else contexte_nav.new_page()
            )
            assert module_portail is not None
            resultat = module_portail.executer_preremplissage_avec_arret_avant_envoi(
                page,
                tache_id=args.tache_id,
                client_api=client_api,
                url_base_portail=url_base,
                naviguer_au_demarrage=not args.ne_pas_naviguer,
                dossier_captures_locales=dossier_captures,
            )
            print(
                f"Résultat tâche {resultat.tache_id} : statut={resultat.statut_final} "
                f"étapes_exécutées={len(resultat.etapes_executees_dans_ce_cycle)} "
                f"étapes_sautées={len(resultat.etapes_sautees_idempotence)} "
                f"captures_prises={len(resultat.captures_prises)}"
            )
            return 0 if resultat.statut_final in {"a_valider", "suspendue"} else 1
        finally:
            contexte_nav.close()


if __name__ == "__main__":
    raise SystemExit(main())
