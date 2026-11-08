"""Garde-fous de sécurité de l'Agent Local Playwright (Phase 4) :
- Règle 1 (Option A) : interdiction absolue de cliquer sur un sélecteur de soumission finale
  (`ErreurSoumissionFinaleInterdite`).
- Règle 2 : détection immédiate de tout CAPTCHA ou contrôle de double authentification (2FA)
  et suspension de la tâche (`SuspensionRequiseParGardeFou`).
- Règle 3 : vérification que la session a bien été ouverte par l'humain dans le navigateur.
- Règle 4 : refus d'inventer toute valeur par défaut si une donnée ou une pièce requise manque.
- Règle 7 : suspension propre si un sélecteur YAML n'est plus présent sur la page.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from playwright.sync_api import Page

from app.agent_local.config_portail import ConfigPortailYAML
from app.modeles.tache import MotifSuspensionTache


class ErreurSoumissionFinaleInterdite(RuntimeError):
    """Levée immédiatement si une instruction tente de cliquer sur un sélecteur
    de soumission officielle finale (Règle 1 — Option A)."""


@dataclass
class SuspensionRequiseParGardeFou(Exception):
    motif: MotifSuspensionTache
    message_alerte: str
    code_etape: str
    champs_manquants: list[str] = field(default_factory=list)
    pieces_manquantes: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return f"[{self.motif.value}] ({self.code_etape}) {self.message_alerte}"


def verifier_selecteur_non_interdit(
    selecteur: str, config_portail: ConfigPortailYAML
) -> None:
    """Règle 1 (Option A) : bloque techniquement tout clic sur un bouton de soumission finale."""
    sel_norm = selecteur.strip()
    interdits = {s.strip() for s in config_portail.selecteurs_soumission_interdits}
    if sel_norm in interdits:
        raise ErreurSoumissionFinaleInterdite(
            f"Règle 1 : clic formellement interdit sur le sélecteur de soumission finale '{sel_norm}'."
        )
    mots_interdits = ("soumission-finale", "soumettre-definitivement", "transmettre-demande")
    if any(m in sel_norm.lower() for m in mots_interdits):
        raise ErreurSoumissionFinaleInterdite(
            f"Règle 1 : le sélecteur '{sel_norm}' correspond à une action de soumission finale réservée à l'humain."
        )


def cliquer_securise(
    page: Page, selecteur: str, config_portail: ConfigPortailYAML, *, code_etape: str
) -> None:
    """Vérifie le garde-fou Règle 1 et l'existence du sélecteur (Règle 7) avant de cliquer."""
    verifier_selecteur_non_interdit(selecteur, config_portail)
    loc = page.locator(selecteur)
    if loc.count() == 0:
        raise SuspensionRequiseParGardeFou(
            motif=MotifSuspensionTache.SELECTEUR_PORTAIL_INTROUVABLE,
            message_alerte=f"Sélecteur YAML introuvable sur la page : '{selecteur}' (règle 7).",
            code_etape=code_etape,
        )
    loc.first.click()


def verifier_session_et_absence_captcha(
    page: Page, config_portail: ConfigPortailYAML, *, code_etape: str
) -> None:
    """Applique les Règles 2 et 3 sur la page courante :
    - Si un détecteur de CAPTCHA ou 2FA est visible -> suspend la tâche (`action_utilisateur_portail`).
    - Si la session portail n'est pas ouverte par l'opérateur -> suspend la tâche (`action_utilisateur_portail`)."""
    # 1. Règle 2 : détection CAPTCHA / 2FA en priorité
    for sel_sec in config_portail.detecteurs_blocage_securite:
        loc_sec = page.locator(sel_sec)
        if loc_sec.count() > 0 and loc_sec.first.is_visible():
            raise SuspensionRequiseParGardeFou(
                motif=MotifSuspensionTache.ACTION_UTILISATEUR_PORTAIL,
                message_alerte=(
                    f"Contrôle de sécurité (CAPTCHA / 2FA '{sel_sec}') détecté : "
                    "veuillez le résoudre dans le navigateur puis reprendre la tâche (règle 2)."
                ),
                code_etape=code_etape,
            )

    # 2. Règle 3 : détection d'une session non connectée
    if config_portail.detecteur_session_fermee:
        loc_fermee = page.locator(config_portail.detecteur_session_fermee)
        if loc_fermee.count() > 0 and loc_fermee.first.is_visible():
            raise SuspensionRequiseParGardeFou(
                motif=MotifSuspensionTache.ACTION_UTILISATEUR_PORTAIL,
                message_alerte=(
                    "Session portail non connectée : veuillez ouvrir la session dans le navigateur "
                    "avant de reprendre la tâche (règle 3 : aucun mot de passe stocké)."
                ),
                code_etape=code_etape,
            )

    loc_ouverte = page.locator(config_portail.temoin_session_ouverte)
    if loc_ouverte.count() == 0 or not loc_ouverte.first.is_visible():
        raise SuspensionRequiseParGardeFou(
            motif=MotifSuspensionTache.ACTION_UTILISATEUR_PORTAIL,
            message_alerte=(
                f"Témoin de session ouverte ('{config_portail.temoin_session_ouverte}') absent : "
                "veuillez vous authentifier manuellement sur le portail puis reprendre la tâche (règle 3)."
            ),
            code_etape=code_etape,
        )
