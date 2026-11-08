"""Vérificateur d'URLs officielles et diagnostic en lecture seule des sélecteurs YAML (Phase 5).

Corrige le défaut D8 de l'audit Phase 0 (« URLs jamais vérifiées ») et permet à l'opérateur
humain de diagnostiquer la page ouverte dans son navigateur (session, CAPTCHA, présence des
sélecteurs YAML et verrouillage du bouton final) sans jamais soumettre ni modifier le dossier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import Page

from app.agent_local.config_portail import ConfigPortailYAML, ModePortail


@dataclass
class ResultatVerificationURL:
    code_portail: str
    url_cible: str
    protocole_https_valide: bool
    domaine_autorise: bool
    accessible_http: bool | None = None
    statut_http: int | None = None
    message: str = ""


@dataclass
class RapportDiagnosticPagePortail:
    code_portail: str
    nom_portail: str
    url_courante: str
    protocole_https_valide: bool
    domaine_autorise: bool
    session_ouverte_detectee: bool
    session_fermee_detectee: bool
    blocage_captcha_ou_2fa_detecte: bool
    selecteurs_detectes: list[str] = field(default_factory=list)
    selecteurs_manquants: list[str] = field(default_factory=list)
    boutons_soumission_interdits_visibles: list[str] = field(default_factory=list)
    chemin_capture_diagnostic: str | None = None
    pret_pour_preremplissage: bool = False


def verifier_url_officielle_portail(
    config_portail: ConfigPortailYAML,
    *,
    url_surcharge: str | None = None,
    client_http: Any | None = None,
) -> ResultatVerificationURL:
    """Vérifie la conformité de l'URL d'un portail (protocole HTTPS, domaine autorisé dans le YAML,
    et disponibilité HTTP si un `client_http` est fourni)."""
    code = config_portail.code_portail or config_portail.code_demarche
    url_cible = (url_surcharge or config_portail.url_officielle or config_portail.chemin_url).strip()
    analyse = urlparse(url_cible)
    hote = (analyse.hostname or "").lower()

    https_ok = (
        analyse.scheme == "https"
        if config_portail.mode_portail == ModePortail.REEL
        else analyse.scheme in {"http", "https", ""}
    )
    if config_portail.domaines_autorises:
        autorises = {d.lower().strip() for d in config_portail.domaines_autorises}
        domaine_ok = hote in autorises
    else:
        domaine_ok = True

    if not https_ok:
        return ResultatVerificationURL(
            code_portail=code,
            url_cible=url_cible,
            protocole_https_valide=False,
            domaine_autorise=domaine_ok,
            accessible_http=False,
            message="Protocole HTTPS obligatoire pour un portail réel.",
        )

    if not domaine_ok:
        return ResultatVerificationURL(
            code_portail=code,
            url_cible=url_cible,
            protocole_https_valide=https_ok,
            domaine_autorise=False,
            accessible_http=False,
            message=f"Le domaine '{hote}' ne figure pas dans domaines_autorises du fichier YAML.",
        )

    if client_http is None:
        return ResultatVerificationURL(
            code_portail=code,
            url_cible=url_cible,
            protocole_https_valide=https_ok,
            domaine_autorise=domaine_ok,
            accessible_http=None,
            message="Format d'URL et domaine validés par rapport au YAML.",
        )

    try:
        rep = client_http.get(url_cible)
        code_http = int(rep.status_code)
        accessible = 200 <= code_http < 400
        return ResultatVerificationURL(
            code_portail=code,
            url_cible=url_cible,
            protocole_https_valide=https_ok,
            domaine_autorise=domaine_ok,
            accessible_http=accessible,
            statut_http=code_http,
            message="Portail accessible." if accessible else f"Erreur HTTP {code_http}.",
        )
    except Exception as exc:
        return ResultatVerificationURL(
            code_portail=code,
            url_cible=url_cible,
            protocole_https_valide=https_ok,
            domaine_autorise=domaine_ok,
            accessible_http=False,
            statut_http=None,
            message=f"Portail injoignable ({type(exc).__name__}).",
        )


def diagnostiquer_page_portail(
    page: Page,
    config_portail: ConfigPortailYAML,
    *,
    dossier_captures_locales: Path | None = None,
) -> RapportDiagnosticPagePortail:
    """Inspecte en lecture seule la page actuellement ouverte dans Playwright :
    - Aucun champ n'est modifié, aucun bouton n'est cliqué (Règle 1).
    - Vérifie le domaine, l'ouverture de session (Règle 3), l'absence de CAPTCHA/2FA (Règle 2)
      et recense tous les sélecteurs YAML présents ou absents sur la page (Règle 7)."""
    code = config_portail.code_portail or config_portail.code_demarche
    url_courante = page.url
    analyse = urlparse(url_courante)
    hote = (analyse.hostname or "").lower()

    https_ok = (
        analyse.scheme == "https"
        if config_portail.mode_portail == ModePortail.REEL
        else True
    )
    if config_portail.domaines_autorises:
        autorises = {d.lower().strip() for d in config_portail.domaines_autorises}
        domaine_ok = hote in autorises
    else:
        domaine_ok = True

    loc_ouverte = page.locator(config_portail.temoin_session_ouverte)
    session_ouverte = loc_ouverte.count() > 0 and loc_ouverte.first.is_visible()

    session_fermee = False
    if config_portail.detecteur_session_fermee:
        loc_fermee = page.locator(config_portail.detecteur_session_fermee)
        session_fermee = loc_fermee.count() > 0 and loc_fermee.first.is_visible()

    captcha_ou_2fa = False
    for sel_sec in config_portail.detecteurs_blocage_securite:
        loc_sec = page.locator(sel_sec)
        if loc_sec.count() > 0 and loc_sec.first.is_visible():
            captcha_ou_2fa = True
            break

    selecteurs_detectes: list[str] = []
    selecteurs_manquants: list[str] = []

    tous_selecteurs: list[str] = []
    for etape in config_portail.etapes_automatisation:
        if etape.selecteur_navigation_onglet:
            tous_selecteurs.append(etape.selecteur_navigation_onglet)
        for ch in etape.champs:
            tous_selecteurs.append(ch.selecteur)
        for f in etape.fichiers:
            tous_selecteurs.append(f.selecteur)
    if config_portail.selecteur_enregistrer_brouillon:
        tous_selecteurs.append(config_portail.selecteur_enregistrer_brouillon)

    vus: set[str] = set()
    for sel in tous_selecteurs:
        if sel in vus:
            continue
        vus.add(sel)
        if page.locator(sel).count() > 0:
            selecteurs_detectes.append(sel)
        else:
            selecteurs_manquants.append(sel)

    boutons_interdits_visibles: list[str] = []
    for sel_int in config_portail.selecteurs_soumission_interdits:
        loc_int = page.locator(sel_int)
        if loc_int.count() > 0:
            boutons_interdits_visibles.append(sel_int)

    chemin_capture: str | None = None
    if dossier_captures_locales is not None:
        dossier_captures_locales.mkdir(parents=True, exist_ok=True)
        cible = dossier_captures_locales / f"diagnostic_{code}.png"
        cible.write_bytes(page.screenshot(full_page=True, type="png"))
        chemin_capture = str(cible)

    pret = (
        https_ok
        and domaine_ok
        and session_ouverte
        and not session_fermee
        and not captcha_ou_2fa
        and len(selecteurs_manquants) == 0
    )

    return RapportDiagnosticPagePortail(
        code_portail=code,
        nom_portail=config_portail.nom_portail,
        url_courante=url_courante,
        protocole_https_valide=https_ok,
        domaine_autorise=domaine_ok,
        session_ouverte_detectee=session_ouverte,
        session_fermee_detectee=session_fermee,
        blocage_captcha_ou_2fa_detecte=captcha_ou_2fa,
        selecteurs_detectes=selecteurs_detectes,
        selecteurs_manquants=selecteurs_manquants,
        boutons_soumission_interdits_visibles=boutons_interdits_visibles,
        chemin_capture_diagnostic=chemin_capture,
        pret_pour_preremplissage=pret,
    )
