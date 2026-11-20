"""Action `connexion_portail` de l'Agent Local : ouvrir la page de connexion OFFICIELLE d'un portail (Études en France ou
IRCC/CléGC) et s'y connecter, sans jamais contourner un CAPTCHA ni une double authentification.

- R6 : page vérifiée avant et après navigation (`formulaires_portail.motif_url_refusee`).
- R2 : CAPTCHA / 2FA avant la saisie => suspension (aucun identifiant demandé) ; après la saisie => suspension aussi
  (reprise humaine puis nouvelle tentative : la session ouverte est reconnue sans ressaisie).
- R3 : AVEC identifiants au coffre, l'agent attend le consentement donné dans l'interface web (« Autoriser l'agent à se
  connecter »), reçoit les identifiants UNE fois (60 s), les saisit et les efface. SANS identifiants, il ne demande
  rien dans le panneau (aucun champ de mot de passe) : l'humain les tape dans le formulaire du portail ; l'agent les lit
  au moment de la soumission humaine (`capture_identifiants`) et, la connexion réussie, les dépose chiffrés pour que
  l'interface web propose de les enregistrer dans le coffre (consentement explicite).
- Aucune valeur secrète dans les journaux, messages, exceptions ni sur le disque ; toute exception de la saisie est
  remplacée par un message fixe (le journal d'appel Playwright pourrait citer la valeur).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.agent_local.capture_identifiants import Capteur, capteur_pour
from app.agent_local.demon_ecoute import ContexteExecution, ResultatExecution
from app.agent_local.formulaires_portail import (
    DELAI_CHAMP_MS,
    FormulairesPortail,
    SecretEphemere,
    captcha_visible,
    charger_formulaires,
    localiser_champ,
    motif_url_refusee,
    session_ouverte,
    url_cible,
)
from app.agent_local.garde_fous import SuspensionRequiseParGardeFou
from app.agent_local.journal_agent import JournalAgent
from app.modeles.tache import ACTION_CONNEXION_PORTAIL, MotifSuspensionTache

journal = logging.getLogger("app.agent_local.action_connexion_portail")

CODE_ETAPE = "connexion_portail"
ATTENTE_CONSENTEMENT_S = 300.0
ATTENTE_HUMAIN_S = 600.0
INTERVALLE_S = 2.0
ATTENTE_CONFIRMATION_S = 15.0
PORTAILS = ("etudes_en_france", "ircc")


def _suspension(message: str, motif: MotifSuspensionTache = MotifSuspensionTache.ACTION_UTILISATEUR_PORTAIL):
    return SuspensionRequiseParGardeFou(motif=motif, message_alerte=message, code_etape=CODE_ETAPE)


def executer_connexion_portail(ctx: ContexteExecution) -> ResultatExecution:
    jr = JournalAgent.depuis_contexte(ctx)
    try:
        return _executer(ctx, jr)
    except SuspensionRequiseParGardeFou as susp:
        if susp.code_etape == CODE_ETAPE:
            jr.demander_humain(susp.message_alerte)
        raise


def _pause(ctx: ContexteExecution, jr: JournalAgent, duree_s: float) -> None:
    jr.point_de_controle()
    ctx.page.wait_for_timeout(int(duree_s * 1000))


def _ouvrir_page(ctx: ContexteExecution, formulaires: FormulairesPortail) -> None:
    page_form = formulaires.connexion
    url = url_cible(page_form, formulaires, ctx.url_serveur)
    motif = motif_url_refusee(url, formulaires, ctx.url_serveur)
    if motif:
        raise _suspension(motif, MotifSuspensionTache.AUTRE)
    reponse = ctx.page.goto(url, wait_until="domcontentloaded")
    if reponse is None or reponse.status >= 400:
        raise RuntimeError("page de connexion indisponible")
    motif = motif_url_refusee(ctx.page.url or "", formulaires, ctx.url_serveur)
    if motif:  # redirection hors des domaines autorisés
        raise _suspension(motif, MotifSuspensionTache.AUTRE)
    ctx.amener_au_premier_plan()


def _verifier_securite(ctx: ContexteExecution, formulaires: FormulairesPortail, moment: str) -> None:
    if captcha_visible(ctx.page, formulaires.detecteurs_captcha):  # R2
        raise _suspension(
            f"Contrôle de sécurité (CAPTCHA ou double authentification) {moment} : résolvez-le vous-même dans la "
            "fenêtre ouverte sur votre PC, puis reprenez la tâche (règle 2). Je n'y touche pas."
        )


def _reponse_json(reponse: Any) -> dict[str, Any]:
    try:
        return dict(reponse.json())
    except Exception:  # noqa: BLE001
        return {}


def _attendre_remise(ctx: ContexteExecution, jr: JournalAgent) -> SecretEphemere | tuple[SecretEphemere, SecretEphemere]:
    """Interroge la remise jusqu'au consentement (403 = pas encore autorisé). Renvoie (identifiant, mot de passe)."""
    fin = time.monotonic() + ATTENTE_CONSENTEMENT_S
    while time.monotonic() < fin:
        jr.point_de_controle()
        rep = ctx.client_api.post(f"/api/v1/taches/{ctx.tache_id}/identifiants-portail/remise")
        if rep.status_code == 200:
            corps = _reponse_json(rep)
            paire = (SecretEphemere(str(corps.get("identifiant", ""))), SecretEphemere(str(corps.get("mot_de_passe", ""))))
            corps.clear()
            return paire  # type: ignore[return-value]
        if rep.status_code == 404:
            raise _suspension(
                "Aucun identifiant n'est enregistré dans le coffre : relancez la connexion pour taper vos "
                "identifiants vous-même dans le formulaire du portail.",
                MotifSuspensionTache.DONNEE_MANQUANTE,
            )
        if rep.status_code not in (403, 409):
            raise RuntimeError(f"remise refusée (HTTP {rep.status_code})")
        _pause(ctx, jr, INTERVALLE_S)
    raise _suspension(
        "Aucune autorisation reçue dans le délai : relancez la tâche puis cliquez sur « Autoriser l'agent à se "
        "connecter » dans l'interface web."
    )


def _saisir_et_valider(ctx: ContexteExecution, formulaires: FormulairesPortail, identifiant: SecretEphemere,
                       mot_de_passe: SecretEphemere) -> bool:
    page_form = formulaires.connexion
    page = ctx.page
    loc_id = localiser_champ(page, page_form.champs["identifiant"])
    loc_mdp = localiser_champ(page, page_form.champs["mot_de_passe"])
    if loc_id is None or loc_mdp is None or page_form.bouton_regex is None:
        return False
    import re

    bouton = page.get_by_role("button", name=re.compile(page_form.bouton_regex, re.IGNORECASE))
    if bouton.count() != 1:
        return False
    try:
        loc_id.fill(identifiant.valeur(), timeout=DELAI_CHAMP_MS)
        loc_mdp.fill(mot_de_passe.valeur(), timeout=DELAI_CHAMP_MS)
        bouton.click(timeout=DELAI_CHAMP_MS)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=DELAI_CHAMP_MS)
        except Exception:  # noqa: BLE001 - page dynamique
            pass
        return True
    except Exception:  # noqa: BLE001 - le journal d'appel peut citer la valeur saisie : message fixe
        return False


def _connexion_par_coffre(ctx: ContexteExecution, jr: JournalAgent, formulaires: FormulairesPortail) -> None:
    jr.demander_humain(
        "Les identifiants de ce candidat sont dans le coffre. Pour que je m'en serve, cliquez sur « Autoriser l'agent "
        "à se connecter » dans l'interface web (valable 60 secondes, une seule fois). J'attends."
    )
    remis = _attendre_remise(ctx, jr)
    identifiant, mot_de_passe = remis  # type: ignore[misc]
    try:
        jr.dire("Autorisation reçue. Je remplis l'identifiant et le mot de passe (leurs valeurs ne sont jamais affichées).")
        jr.agir("Je saisis l'identifiant du portail", None)
        ok = _saisir_et_valider(ctx, formulaires, identifiant, mot_de_passe)
    finally:
        identifiant.effacer()
        mot_de_passe.effacer()
    if not ok:
        raise _suspension(
            "La saisie des identifiants a échoué sur la page (champ ou bouton introuvable) : connectez-vous "
            "vous-même dans la fenêtre puis reprenez la tâche.",
            MotifSuspensionTache.SELECTEUR_PORTAIL_INTROUVABLE,
        )
    _verifier_securite(ctx, formulaires, "apparu après la saisie")
    fin = time.monotonic() + ATTENTE_CONFIRMATION_S
    while time.monotonic() < fin:
        if session_ouverte(ctx.page, formulaires):
            return
        _pause(ctx, jr, 0.5)
    _verifier_securite(ctx, formulaires, "apparu après la saisie")
    raise _suspension(
        "Connexion non confirmée après la saisie (identifiants refusés ou page inattendue). Je ne réessaie pas, pour "
        "ne pas bloquer le compte : connectez-vous vous-même puis reprenez la tâche."
    )


def _connexion_manuelle(ctx: ContexteExecution, jr: JournalAgent, formulaires: FormulairesPortail, capteur: Capteur) -> bool:
    """Retourne vrai si des identifiants ont été captés (à proposer pour le coffre)."""
    jr.demander_humain(
        "Aucun identifiant n'est enregistré pour ce candidat. Tapez vos identifiants directement dans le formulaire "
        "du portail, puis validez-le vous-même. Je n'en demande aucun ici."
    )
    capteur.activer()
    fin = time.monotonic() + ATTENTE_HUMAIN_S
    while time.monotonic() < fin:
        if session_ouverte(ctx.page, formulaires):
            return capteur.a_une_valeur
        _pause(ctx, jr, 1.0)
    raise _suspension("Connexion non faite dans le délai : reprenez la tâche quand vous êtes prêt.")


def _deposer_pour_coffre(ctx: ContexteExecution, jr: JournalAgent, capteur: Capteur) -> bool:
    valeurs = capteur.lire()
    if valeurs is None:
        return False
    try:
        rep = ctx.client_api.post(
            f"/api/v1/taches/{ctx.tache_id}/depot-identifiants",
            json={"identifiant": valeurs[0], "mot_de_passe": valeurs[1]},
        )
    finally:
        capteur.vider()
        del valeurs
    return rep.status_code == 204


def _executer(ctx: ContexteExecution, jr: JournalAgent) -> ResultatExecution:
    portail = str(ctx.tache.get("portail") or "")
    if portail not in PORTAILS:
        raise _suspension("Portail inconnu pour cette tâche.", MotifSuspensionTache.AUTRE)
    formulaires = charger_formulaires(portail)
    jr.dire("Bonjour, je m'occupe de la connexion au portail. J'ouvre sa page de connexion officielle.")
    capteur = capteur_pour(ctx.page, lambda url: motif_url_refusee(url, formulaires, ctx.url_serveur) is None)
    capteur.desactiver()
    _ouvrir_page(ctx, formulaires)
    jr.dire("Je vérifie qu'aucun CAPTCHA ni double authentification n'est demandé.")
    _verifier_securite(ctx, formulaires, "affiché sur la page")

    mode = "session_deja_ouverte"
    propose_coffre = False
    if session_ouverte(ctx.page, formulaires):
        jr.dire("Vous êtes déjà connecté à ce portail : je n'ai rien à saisir.")
    else:
        rep = ctx.client_api.get(f"/api/v1/taches/{ctx.tache_id}/coffre-etat")
        rep.raise_for_status()
        if _reponse_json(rep).get("existe"):
            mode = "coffre"
            _connexion_par_coffre(ctx, jr, formulaires)
        else:
            mode = "manuel"
            try:
                if _connexion_manuelle(ctx, jr, formulaires, capteur):
                    propose_coffre = _deposer_pour_coffre(ctx, jr, capteur)
            finally:
                capteur.desactiver()
                capteur.vider()
    jr.dire("Connexion confirmée : la page du portail est ouverte sur un compte connecté.")
    if propose_coffre:
        jr.dire(
            "Vous pouvez enregistrer ces identifiants dans le coffre : l'interface web vous le propose "
            "(avec le consentement du candidat). Rien n'est enregistré sans votre accord."
        )
    jr.demander_humain("Connexion terminée : clôturez la tâche en la validant dans le Centre de validation.")
    return ResultatExecution(
        recapitulatif={
            "action": ACTION_CONNEXION_PORTAIL,
            "portail": portail,
            "connexion": "reussie",
            "mode": mode,
            "enregistrement_coffre_propose": propose_coffre,
            "arret_avant_soumission_finale": True,
        },
        message_alerte=(
            "Connexion au portail établie dans la fenêtre ouverte sur votre PC. Aucune démarche n'a été envoyée : "
            "contrôlez la fenêtre puis clôturez la tâche dans le Centre de validation."
        ),
    )
