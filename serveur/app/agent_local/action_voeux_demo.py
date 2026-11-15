"""Action `ajouter_voeux_panier` de l'Agent Local sur la PAGE DE DÉMONSTRATION `/demo/campus-france`.

Le vrai portail Études en France reste soumis à l'homologation (Règle 6) : cette action n'ouvre jamais
d'autre adresse que la page de démonstration du serveur de l'agent (`<url_serveur>/demo/campus-france`),
qui n'existe pas en production (404 => erreur claire, rien n'est tenté ailleurs).

Règles :
- R1 : ajoute des vœux au panier de DÉMONSTRATION puis s'arrête (`a_valider`) ; aucune certification,
  aucun bouton de soumission (garde `_est_element_soumission_interdit_regle1` + mots interdits du panier).
- R2 : CAPTCHA / 2FA avant ou pendant => `SuspensionRequiseParGardeFou` (reprise humaine dans la fenêtre).
- R3 : session non connectée => suspension : l'humain se connecte lui-même dans la fenêtre visible.
  Aucun mot de passe n'est demandé au serveur ni saisi ici.
- R4 : aucun vœu validé => suspension (rien n'est inventé). R5 : ni motivation ni nom dans les sorties.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlsplit

from app.agent_local.demon_ecoute import ContexteExecution, ResultatExecution
from app.agent_local.garde_fous import SuspensionRequiseParGardeFou
from app.agent_local.journal_agent import JournalAgent
from app.agent_local.pilote_navigateur import (
    _detecter_captcha_ou_2fa_sur_page,
    _est_element_soumission_interdit_regle1,
)
from app.agent_local.portails.panier_voeux import (
    PROFIL_PANIER_DEMO,
    STATUT_AJOUTE,
    STATUT_DEJA_PRESENT,
    ajouter_voeux_au_panier,
)
from app.modeles.tache import ACTION_AJOUTER_VOEUX_PANIER, MotifSuspensionTache

journal = logging.getLogger("app.agent_local.action_voeux_demo")

CHEMIN_PAGE_DEMO = "/demo/campus-france"
CODE_ETAPE = "ajout_voeux_panier_demo"
SELECTEUR_SESSION_FERMEE = "#alerte-session-non-connectee"
STATUTS_REUSSIS = {STATUT_AJOUTE, STATUT_DEJA_PRESENT}


def message_voeux_non_ajoutes(statuts: list[str]) -> str:
    """Message d'alerte quand des vœux n'ont pas été ajoutés ; dit pourquoi un vœu est « introuvable »."""
    echecs = sum(1 for st in statuts if st not in STATUTS_REUSSIS)
    message = (
        f"{echecs} vœu(x) sur {len(statuts)} n'ont pas pu être ajoutés "
        "(introuvable, ambigu ou refusé) : contrôlez la fenêtre ouverte sur votre PC avant de valider."
    )
    if "introuvable" in statuts:
        message += (
            " Un vœu « introuvable » n'est pas forcément une erreur : la page de démonstration ne connaît "
            "que son propre catalogue fictif, pas le catalogue réel d'Études en France ; un vœu absent de "
            "ce catalogue de démonstration ne peut donc pas y être ajouté."
        )
    return message


def _suspension(motif: MotifSuspensionTache, message: str) -> SuspensionRequiseParGardeFou:
    return SuspensionRequiseParGardeFou(motif=motif, message_alerte=message, code_etape=CODE_ETAPE)


def _lire_voeux(ctx: ContexteExecution) -> list[dict[str, Any]]:
    """Vœux VALIDÉS servis par le serveur à l'agent qui détient la tâche (jamais un brouillon)."""
    reponse = ctx.client_api.get(f"/api/v1/taches/{ctx.tache_id}/voeux-a-ajouter")
    reponse.raise_for_status()
    return [
        {
            "voeu_id": str(v["voeu_id"]),
            "intitule": v["intitule"],
            "etablissement": v["etablissement"],
            "niveau": v["niveau"],
            "motivation": v["motivation"],
        }
        for v in reponse.json()["voeux"]
    ]


PORTS_PAR_DEFAUT = {"http": 80, "https": 443}


def _origine(url: str) -> tuple[str, str, int | None]:
    """(schéma, hôte, port) normalisés : le port par défaut du schéma est rendu explicite."""
    morceaux = urlsplit(url)
    schema = morceaux.scheme.lower()
    return schema, (morceaux.hostname or "").lower(), morceaux.port or PORTS_PAR_DEFAUT.get(schema)


def _verifier_page_attendue(page: Any, url_serveur: str) -> None:
    """Après la navigation : la page doit être exactement celle du serveur de l'agent (schéma, hôte, port et
    chemin). Une redirection ailleurs fait échouer la tâche AVANT tout remplissage ou capture."""
    attendue = urlsplit(url_serveur + CHEMIN_PAGE_DEMO)
    courante = urlsplit(page.url or "")
    if _origine(page.url or "") != _origine(url_serveur) or courante.path.rstrip("/") != attendue.path:
        raise RuntimeError("la page d'arrivée n'est pas la page de démonstration attendue : tâche interrompue")


def _ouvrir_page_demo(ctx: ContexteExecution) -> None:
    page = ctx.page
    reponse = page.goto(ctx.url_serveur + CHEMIN_PAGE_DEMO, wait_until="domcontentloaded")
    if reponse is None or reponse.status != 200:
        raise RuntimeError("page de démonstration indisponible (désactivée en production)")
    _verifier_page_attendue(page, ctx.url_serveur)
    ctx.amener_au_premier_plan()


def _verifier_securite_avant(ctx: ContexteExecution) -> None:
    page = ctx.page
    if _detecter_captcha_ou_2fa_sur_page(page):  # R2
        raise _suspension(
            MotifSuspensionTache.ACTION_UTILISATEUR_PORTAIL,
            "Contrôle de sécurité (CAPTCHA ou 2FA) détecté dans la fenêtre : résolvez-le vous-même "
            "dans la fenêtre ouverte sur votre PC, puis reprenez la tâche (règle 2).",
        )
    alerte = page.locator(SELECTEUR_SESSION_FERMEE)
    if alerte.count() > 0 and alerte.first.is_visible():  # R3 : connexion manuelle
        raise _suspension(
            MotifSuspensionTache.ACTION_UTILISATEUR_PORTAIL,
            "Session non connectée : connectez-vous vous-même dans la fenêtre ouverte sur votre PC "
            "(l'agent ne tape jamais votre mot de passe), puis reprenez la tâche (règle 3).",
        )


def executer_ajout_voeux_demo(ctx: ContexteExecution) -> ResultatExecution:
    """Annonce chaque étape dans la discussion de la fenêtre (`journal_agent`) ; toute suspension (R2, R3, R4)
    y devient une demande d'aide à l'humain avant d'être relancée au démon."""
    journal_agent = JournalAgent.depuis_contexte(ctx)
    try:
        return _executer(ctx, journal_agent)
    except SuspensionRequiseParGardeFou as susp:
        if susp.code_etape == CODE_ETAPE:
            journal_agent.demander_humain(susp.message_alerte)
        raise


def _executer(ctx: ContexteExecution, jr: JournalAgent) -> ResultatExecution:
    jr.dire("Bonjour, je prépare l'ajout de vos vœux validés au panier de démonstration.")
    voeux = _lire_voeux(ctx)
    if not voeux:  # R4
        raise _suspension(
            MotifSuspensionTache.DONNEE_MANQUANTE,
            "Aucun vœu validé n'est plus disponible pour ce candidat : validez au moins un vœu "
            "puis reprenez la tâche (règle 4).",
        )

    jr.dire(f"J'ai {len(voeux)} vœu(x) validé(s) à ajouter. J'ouvre la page de démonstration du portail.")
    _ouvrir_page_demo(ctx)
    jr.dire("Je vérifie qu'aucun CAPTCHA ni double authentification n'est demandé et que vous êtes connecté.")
    _verifier_securite_avant(ctx)

    jr.agir("Je me place sur la recherche de formations", PROFIL_PANIER_DEMO.recherche)
    jr.dire("J'ajoute les vœux au panier, un par un.")
    resultats, _notes, blocage = ajouter_voeux_au_panier(
        ctx.page,
        voeux,
        profil=PROFIL_PANIER_DEMO,
        est_interdit=_est_element_soumission_interdit_regle1,
        detecteur_blocage=_detecter_captcha_ou_2fa_sur_page,
    )
    if blocage:  # R2 en cours de route
        raise _suspension(
            MotifSuspensionTache.ACTION_UTILISATEUR_PORTAIL,
            "Contrôle de sécurité (CAPTCHA ou 2FA) apparu pendant l'ajout des vœux : résolvez-le dans "
            "la fenêtre ouverte sur votre PC, puis reprenez la tâche (règle 2).",
        )

    ctx.amener_au_premier_plan()
    jr.dire("Les vœux sont traités. Je prends une capture de contrôle pour le Centre de validation.")
    try:
        capture = ctx.page.screenshot(type="png")
    except Exception as exc:  # la capture n'est qu'un plus : on ne fait jamais échouer la tâche pour elle
        journal.warning("Capture de contrôle impossible : %s", type(exc).__name__)
        capture = None

    reussis = sum(1 for r in resultats if r["statut"] in STATUTS_REUSSIS)
    recapitulatif = {
        "action": ACTION_AJOUTER_VOEUX_PANIER,
        "cible": "page_de_demonstration_locale",
        "nb_voeux_traites": len(resultats),
        "nb_voeux_ajoutes_ou_deja_presents": reussis,
        "voeux": [
            {
                "voeu_id": r["voeu_id"],
                "statut": r["statut"],
                "motivation_enregistree": r["motivation_enregistree"],
                "nb_caracteres": r["nb_caracteres"],
            }
            for r in resultats
        ],
        "arret_avant_soumission_finale": True,
    }
    if reussis == len(resultats):
        message = (
            "Vœux ajoutés au panier de démonstration dans la fenêtre ouverte sur votre PC, arrêt avant "
            "tout envoi officiel : contrôlez la fenêtre puis validez dans le Centre de validation."
        )
    else:
        message = message_voeux_non_ajoutes([r["statut"] for r in resultats])
    if reussis == len(resultats):
        jr.dire(f"J'ai ajouté {reussis} vœu(x) au panier. Je m'arrête ici : je n'envoie rien.")
    else:
        jr.alerter(f"{len(resultats) - reussis} vœu(x) sur {len(resultats)} n'ont pas pu être ajoutés.")
    jr.demander_humain(
        "Contrôlez le panier dans cette fenêtre, puis validez le récapitulatif dans le Centre de validation : "
        "je ne peux pas valider à votre place."
    )
    return ResultatExecution(recapitulatif=recapitulatif, message_alerte=message, capture_png=capture)
