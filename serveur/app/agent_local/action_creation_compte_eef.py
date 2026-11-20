"""Action `creation_compte_eef` : préparer la création d'un compte Études en France pour un candidat.

- R4 : seuls les champs de la fiche (prénom, nom, e-mail) sont saisis ; une valeur manquante => arrêt AVANT d'ouvrir le
  portail, avec la liste des champs manquants. Rien n'est inventé. La région de résidence n'existe pas sur la fiche : elle
  est laissée à l'humain (signalée dans le récapitulatif), comme les deux cases de consentement.
- Un seul compte par candidat : des identifiants déjà au coffre => arrêt.
- R6 : page d'inscription officielle (ou démonstration) vérifiée avant et après navigation.
- R2 : CAPTCHA / 2FA => suspension ; le code de vérification reçu par e-mail est une action humaine.
- R3 : mot de passe généré conforme aux règles du YAML, saisi dans les deux champs, enregistré au coffre AVEC l'e-mail
  AVANT toute soumission (si l'enregistrement échoue, les champs de mot de passe sont vidés) ; jamais journalisé.
- R1 : l'agent ne clique JAMAIS « S'inscrire » : il s'arrête et demande la validation humaine.
"""

from __future__ import annotations

import logging
from typing import Any

from app.agent_local.action_connexion_portail import _reponse_json
from app.agent_local.demon_ecoute import ContexteExecution, ResultatExecution
from app.agent_local.formulaires_portail import (
    DELAI_CHAMP_MS,
    FormulairesPortail,
    PageFormulaire,
    SecretEphemere,
    captcha_visible,
    charger_formulaires,
    generer_mot_de_passe,
    localiser_champ,
    mot_de_passe_conforme,
    motif_url_refusee,
    url_cible,
)
from app.agent_local.garde_fous import SuspensionRequiseParGardeFou
from app.agent_local.journal_agent import JournalAgent
from app.modeles.tache import ACTION_CREATION_COMPTE_EEF, MotifSuspensionTache

journal = logging.getLogger("app.agent_local.action_creation_compte_eef")

CODE_ETAPE = "creation_compte_eef"
CHAMPS_FICHE = ("prenom", "nom", "email")
LIBELLES_FICHE = {"prenom": "prénom", "nom": "nom", "email": "adresse e-mail"}


def _suspension(message: str, motif: MotifSuspensionTache = MotifSuspensionTache.ACTION_UTILISATEUR_PORTAIL,
                champs: list[str] | None = None) -> SuspensionRequiseParGardeFou:
    return SuspensionRequiseParGardeFou(
        motif=motif, message_alerte=message, code_etape=CODE_ETAPE, champs_manquants=champs or []
    )


def executer_creation_compte_eef(ctx: ContexteExecution) -> ResultatExecution:
    jr = JournalAgent.depuis_contexte(ctx)
    try:
        return _executer(ctx, jr)
    except SuspensionRequiseParGardeFou as susp:
        if susp.code_etape == CODE_ETAPE:
            jr.demander_humain(susp.message_alerte)
        raise


def _lire_fiche(ctx: ContexteExecution) -> dict[str, Any]:
    rep = ctx.client_api.get(f"/api/v1/taches/{ctx.tache_id}/champs-compte-eef")
    rep.raise_for_status()
    return _reponse_json(rep)


def _verifier_fiche(fiche: dict[str, Any]) -> None:
    if fiche.get("coffre_existe"):
        raise _suspension(
            "Des identifiants Études en France sont déjà dans le coffre pour ce candidat : je ne crée pas de second "
            "compte (consigne officielle). Utilisez plutôt « Se connecter au portail ».",
            MotifSuspensionTache.AUTRE,
        )
    manquants = [c for c in CHAMPS_FICHE if not fiche.get(c)]
    if manquants:
        noms = ", ".join(LIBELLES_FICHE[c] for c in manquants)
        raise _suspension(
            f"Je ne peux pas créer le compte : la fiche du candidat ne contient pas son {noms}. Je n'invente rien : "
            "complétez la fiche puis reprenez la tâche (règle 4).",
            MotifSuspensionTache.DONNEE_MANQUANTE,
            manquants,
        )
    if not fiche.get("consentement_signe"):
        raise _suspension(
            "Le consentement écrit du candidat n'est pas enregistré sur sa fiche : je ne crée pas de compte à son "
            "nom (règle 3). Enregistrez-le puis reprenez la tâche.",
            MotifSuspensionTache.DONNEE_MANQUANTE,
            ["consentement_signe"],
        )


def _ouvrir_inscription(ctx: ContexteExecution, formulaires: FormulairesPortail, page_form: PageFormulaire) -> None:
    url = url_cible(page_form, formulaires, ctx.url_serveur)
    motif = motif_url_refusee(url, formulaires, ctx.url_serveur)
    if motif:
        raise _suspension(motif, MotifSuspensionTache.AUTRE)
    reponse = ctx.page.goto(url, wait_until="domcontentloaded")
    if reponse is None or reponse.status >= 400:
        raise RuntimeError("page d'inscription indisponible")
    motif = motif_url_refusee(ctx.page.url or "", formulaires, ctx.url_serveur)
    if motif:
        raise _suspension(motif, MotifSuspensionTache.AUTRE)
    ctx.amener_au_premier_plan()


def _localiser_tous(ctx: ContexteExecution, page_form: PageFormulaire) -> dict[str, Any]:
    champs = {cle: localiser_champ(ctx.page, c) for cle, c in page_form.champs.items()}
    absents = [cle for cle, loc in champs.items() if loc is None and cle != "region"]
    if absents:
        raise _suspension(
            "Je ne retrouve pas ces champs sur la page d'inscription (la page a peut-être changé) : "
            + ", ".join(absents) + ". Je m'arrête sans rien envoyer ; terminez à la main ou prévenez l'administrateur.",
            MotifSuspensionTache.SELECTEUR_PORTAIL_INTROUVABLE,
            absents,
        )
    return champs


def _selectionner_espace(champs: dict[str, Any], page_form: PageFormulaire) -> None:
    valeur = page_form.valeurs_fixes.get("espace")
    if not valeur:
        raise _suspension("Espace Campus France de résidence non défini dans la configuration.",
                          MotifSuspensionTache.DONNEE_MANQUANTE, ["espace"])
    try:
        champs["espace"].select_option(label=valeur, timeout=DELAI_CHAMP_MS)
    except Exception:  # noqa: BLE001
        raise _suspension(
            f"L'option « {valeur} » n'existe pas dans la liste des espaces : choisissez-la vous-même.",
            MotifSuspensionTache.SELECTEUR_PORTAIL_INTROUVABLE,
            ["espace"],
        ) from None


def _remplir_texte(champs: dict[str, Any], fiche: dict[str, Any]) -> None:
    for cle in CHAMPS_FICHE:
        champs[cle].fill(str(fiche[cle]), timeout=DELAI_CHAMP_MS)


def _remplir_mot_de_passe(champs: dict[str, Any], secret: SecretEphemere) -> None:
    try:
        champs["mot_de_passe"].fill(secret.valeur(), timeout=DELAI_CHAMP_MS)
        champs["confirmation"].fill(secret.valeur(), timeout=DELAI_CHAMP_MS)
    except Exception:  # noqa: BLE001 - le journal d'appel peut citer la valeur
        raise _suspension("Je n'ai pas pu remplir les champs de mot de passe : rien n'a été enregistré ni envoyé.",
                          MotifSuspensionTache.SELECTEUR_PORTAIL_INTROUVABLE) from None


def _vider_mots_de_passe(champs: dict[str, Any]) -> None:
    for cle in ("mot_de_passe", "confirmation"):
        try:
            champs[cle].fill("", timeout=DELAI_CHAMP_MS)
        except Exception:  # noqa: BLE001
            pass


def _champs_coherents(champs: dict[str, Any], fiche: dict[str, Any]) -> bool:
    try:
        textes = all(champs[c].input_value() == str(fiche[c]) for c in CHAMPS_FICHE)
        return textes and champs["mot_de_passe"].input_value() == champs["confirmation"].input_value() != ""
    except Exception:  # noqa: BLE001
        return False


def _enregistrer_au_coffre(ctx: ContexteExecution, fiche: dict[str, Any], secret: SecretEphemere) -> str | None:
    """None si tout va bien, sinon le message (sans secret) de refus du serveur."""
    rep = ctx.client_api.post(
        f"/api/v1/taches/{ctx.tache_id}/compte-eef/enregistrer-identifiants",
        json={"identifiant": str(fiche["email"]), "mot_de_passe": secret.valeur()},
    )
    if rep.status_code == 200:
        return None
    detail = _reponse_json(rep).get("detail")
    return detail if isinstance(detail, str) else f"refus du serveur (HTTP {rep.status_code})"


def _executer(ctx: ContexteExecution, jr: JournalAgent) -> ResultatExecution:
    formulaires = charger_formulaires("etudes_en_france")
    page_form = formulaires.inscription
    if page_form is None or page_form.regles_mot_de_passe is None:
        raise _suspension("Formulaire d'inscription non configuré.", MotifSuspensionTache.AUTRE)
    jr.dire("Bonjour, je prépare la création du compte Études en France. Je commence par lire la fiche du candidat.")
    fiche = _lire_fiche(ctx)
    _verifier_fiche(fiche)
    jr.dire("La fiche est complète. J'ouvre la page d'inscription officielle.")
    _ouvrir_inscription(ctx, formulaires, page_form)
    jr.dire("Je vérifie qu'aucun CAPTCHA ni double authentification n'est demandé.")
    if captcha_visible(ctx.page, formulaires.detecteurs_captcha):
        raise _suspension(
            "Contrôle de sécurité (CAPTCHA ou double authentification) affiché : résolvez-le vous-même dans la "
            "fenêtre ouverte sur votre PC, puis reprenez la tâche (règle 2). Je n'y touche pas."
        )
    champs = _localiser_tous(ctx, page_form)
    jr.agir("Je remplis le prénom, le nom et l'adresse e-mail du candidat", champs["prenom"])
    _remplir_texte(champs, fiche)
    jr.agir("Je choisis l'Espace Campus France de résidence", champs["espace"])
    _selectionner_espace(champs, page_form)
    jr.dire(
        "Je génère un mot de passe fort conforme aux règles affichées (12 caractères minimum, minuscule, majuscule, "
        "chiffre, caractère spécial) et je le saisis deux fois. Il ne sera jamais affiché."
    )
    secret = SecretEphemere(generer_mot_de_passe(page_form.regles_mot_de_passe))
    try:
        if not mot_de_passe_conforme(secret.valeur(), page_form.regles_mot_de_passe):
            raise _suspension("Mot de passe généré non conforme.", MotifSuspensionTache.AUTRE)
        _remplir_mot_de_passe(champs, secret)
        if not _champs_coherents(champs, fiche):
            _vider_mots_de_passe(champs)
            raise _suspension(
                "Les champs saisis ne correspondent pas à la fiche : je les ai vidés et je m'arrête sans rien envoyer.",
                MotifSuspensionTache.SELECTEUR_PORTAIL_INTROUVABLE,
            )
        jr.dire("J'enregistre l'e-mail et le mot de passe dans le coffre chiffré AVANT toute soumission.")
        refus = _enregistrer_au_coffre(ctx, fiche, secret)
    finally:
        secret.effacer()
    if refus is not None:
        _vider_mots_de_passe(champs)
        raise _suspension(
            f"Enregistrement dans le coffre impossible ({refus}). J'ai vidé les champs de mot de passe : "
            "rien n'est envoyé.",
            MotifSuspensionTache.AUTRE,
        )
    a_completer = ["case_consentement", "case_france_alumni_facultative"]
    a_completer.insert(0, "region_residence")
    captcha = captcha_visible(ctx.page, formulaires.detecteurs_captcha)
    jr.dire(
        "Le formulaire est rempli et le mot de passe est au coffre. Je m'arrête AVANT le bouton « S'inscrire » : "
        "choisissez la région de résidence, cochez vous-même la case de consentement (et France Alumni si le "
        "candidat le souhaite), résolvez tout CAPTCHA, puis validez. Le code de vérification reçu par e-mail est aussi "
        "à saisir par vous."
    )
    if captcha:
        jr.alerter("Un contrôle de sécurité est affiché : il est à résoudre par vous (règle 2).")
    jr.demander_humain(
        "Contrôlez le formulaire dans cette fenêtre, puis validez le récapitulatif dans le Centre de validation : "
        "je ne peux pas valider ni cliquer « S'inscrire » à votre place."
    )
    return ResultatExecution(
        recapitulatif={
            "action": ACTION_CREATION_COMPTE_EEF,
            "portail": "etudes_en_france",
            "champs_remplis": ["prenom", "nom", "email", "espace_campus_france", "mot_de_passe", "confirmation"],
            "mot_de_passe_enregistre_au_coffre": True,
            "a_faire_par_un_humain": a_completer
            + ["captcha_eventuel", "code_de_verification_par_email", "bouton_s_inscrire"],
            "captcha_affiche": captcha,
            "bouton_inscription_clique": False,
            "arret_avant_soumission_finale": True,
        },
        message_alerte=(
            "Formulaire d'inscription Études en France prérempli dans la fenêtre ouverte sur votre PC, arrêt avant "
            "« S'inscrire » : contrôlez la fenêtre, terminez (région, consentement, CAPTCHA, code reçu par e-mail) "
            "puis validez dans le Centre de validation."
        ),
    )
