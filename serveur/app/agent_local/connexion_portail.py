"""Connexion automatique au portail via le coffre chiffré (Règles 2, 3 et 5).

- Règle 2 : CAPTCHA / 2FA vérifiés avant ET après la saisie ; s'il y en a un -> suspension,
  jamais de contournement, jamais de saisie.
- Règle 3 : l'identifiant et le mot de passe ne sont lus que par un appel de service direct
  (`coffre_identifiants.lire_pour_agent`), au moment de la connexion. Aucun endpoint HTTP.
  Une seule tentative par appel (pas de nouvel essai : risque de blocage du compte du candidat).
- Règle 5 : le mot de passe n'apparaît dans aucun log, message, exception ni valeur de retour.
  Toute exception Playwright (dont le journal d'appel peut citer la valeur saisie) est remplacée
  par un message fixe et la cause d'origine n'est pas conservée.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from playwright.sync_api import Page
from sqlalchemy.orm import Session

from app.agent_local.config_portail import ConfigPortailYAML
from app.agent_local.garde_fous import (
    SuspensionRequiseParGardeFou,
    session_portail_ouverte,
    verifier_absence_captcha_2fa,
    verifier_selecteur_non_interdit,
)
from app.db.tenant import definir_tenant
from app.modeles.tache import MotifSuspensionTache
from app.services import coffre_identifiants

journal = logging.getLogger("app.agent_local.connexion")

DELAI_CONNEXION_MS = 15_000


@dataclass(frozen=True)
class ResultatConnexion:
    """Aucune donnée d'identification : seulement ce qui s'est passé."""

    session_deja_ouverte: bool
    connexion_effectuee: bool


def _suspension(
    message: str,
    code_etape: str,
    motif: MotifSuspensionTache = MotifSuspensionTache.ACTION_UTILISATEUR_PORTAIL,
) -> SuspensionRequiseParGardeFou:
    return SuspensionRequiseParGardeFou(motif=motif, message_alerte=message, code_etape=code_etape)


def _selecteurs_connexion(config: ConfigPortailYAML) -> tuple[str, str, str] | None:
    if not (
        config.selecteur_identifiant
        and config.selecteur_mot_de_passe
        and config.selecteur_bouton_connexion
    ):
        return None
    return (
        config.selecteur_identifiant,
        config.selecteur_mot_de_passe,
        config.selecteur_bouton_connexion,
    )


def _lire_coffre(
    db: Session,
    tenant: uuid.UUID,
    candidat_id: uuid.UUID,
    portail: str,
    cle_maitresse: bytes,
    code_etape: str,
) -> coffre_identifiants.IdentifiantsClairs:
    definir_tenant(db, tenant)
    echec = False
    clairs = None
    try:
        clairs = coffre_identifiants.lire_pour_agent(
            db, candidat_id=candidat_id, portail=portail, cle_maitresse=cle_maitresse
        )
    except Exception:  # noqa: BLE001 - message fixe, cause volontairement non conservée
        echec = True
    if echec or clairs is None:
        raise _suspension(
            "Identifiants du portail absents du coffre (ou consentement du candidat non recueilli) : "
            "enregistrez-les dans le coffre ou connectez-vous manuellement puis reprenez la tâche.",
            code_etape,
        )
    return clairs


def _saisir_et_valider(
    page: Page, sels: tuple[str, str, str], clairs: coffre_identifiants.IdentifiantsClairs
) -> bool:
    """Retourne False si une erreur Playwright survient (message jamais propagé)."""
    sel_id, sel_mdp, sel_btn = sels
    try:
        page.locator(sel_id).first.fill(clairs.identifiant, timeout=DELAI_CONNEXION_MS)
        page.locator(sel_mdp).first.fill(clairs.mot_de_passe, timeout=DELAI_CONNEXION_MS)
        page.locator(sel_btn).first.click(timeout=DELAI_CONNEXION_MS)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=DELAI_CONNEXION_MS)
        except Exception:  # noqa: BLE001 - pas de navigation : page dynamique, on re-vérifie ensuite
            pass
        return True
    except Exception:  # noqa: BLE001 - le journal d'appel Playwright peut citer la valeur saisie
        return False


def connecter_si_necessaire(
    page: Page,
    db: Session,
    tenant: uuid.UUID,
    candidat_id: uuid.UUID,
    portail: str,
    config_portail: ConfigPortailYAML,
    code_etape: str,
    *,
    cle_maitresse: bytes,
) -> ResultatConnexion:
    """Ouvre la session du portail avec les identifiants du coffre si elle ne l'est pas déjà.

    Lève `SuspensionRequiseParGardeFou` (jamais de contournement) si : CAPTCHA/2FA présent,
    connexion automatique non configurée, coffre vide, champ introuvable, échec ou blocage
    de sécurité après la connexion.
    """
    # 1. Règle 2 en premier : aucun contrôle de sécurité, aucune saisie.
    verifier_absence_captcha_2fa(page, config_portail, code_etape=code_etape)

    # 2. Session déjà ouverte : rien à faire (et surtout aucune lecture du coffre).
    if session_portail_ouverte(page, config_portail):
        return ResultatConnexion(session_deja_ouverte=True, connexion_effectuee=False)

    # 3. Connexion automatique non décrite dans le YAML : manuel.
    sels = _selecteurs_connexion(config_portail)
    if sels is None:
        raise _suspension(
            "Connexion manuelle requise : le portail n'a pas de champs de connexion décrits "
            "dans sa configuration. Ouvrez la session dans le navigateur puis reprenez la tâche.",
            code_etape,
        )
    for sel in sels:
        verifier_selecteur_non_interdit(sel, config_portail)
    for sel in sels:
        if page.locator(sel).count() == 0:
            raise _suspension(
                f"Sélecteur de connexion YAML introuvable sur la page : '{sel}' (règle 7).",
                code_etape,
                MotifSuspensionTache.SELECTEUR_PORTAIL_INTROUVABLE,
            )

    # 4. Lecture du coffre (appel de service direct) puis saisie.
    clairs = _lire_coffre(db, tenant, candidat_id, portail, cle_maitresse, code_etape)
    try:
        saisie_ok = _saisir_et_valider(page, sels, clairs)
    finally:
        del clairs
    if not saisie_ok:
        raise _suspension(
            "La saisie des identifiants a échoué sur la page du portail : connectez-vous "
            "manuellement puis reprenez la tâche.",
            code_etape,
        )

    # 5. Règle 2 de nouveau (un CAPTCHA/2FA apparaît souvent après le login), puis confirmation.
    verifier_absence_captcha_2fa(page, config_portail, code_etape=code_etape)
    if not session_portail_ouverte(page, config_portail):
        raise _suspension(
            "Connexion non confirmée après la saisie des identifiants (identifiants refusés ou "
            "portail inattendu) : aucune nouvelle tentative automatique ; connectez-vous manuellement.",
            code_etape,
        )
    journal.info("Connexion portail effectuée via le coffre (étape %s).", code_etape)
    return ResultatConnexion(session_deja_ouverte=False, connexion_effectuee=True)
