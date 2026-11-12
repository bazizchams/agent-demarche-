"""Exécuteur Playwright de l'Agent Local (Phases 4 & 5).

Fonctionnement :
- Communique avec le serveur uniquement via l'API authentifiée (`X-Agent-Token`).
- Lit les sélecteurs et les étapes depuis le fichier YAML du portail (`config/portails/*.yaml` — Règle 7).
- Saute automatiquement toute étape déjà à l'état `terminee` (reprise idempotente sans rejouer les étapes).
- Vérifie à chaque étape le domaine autorisé (défaut D8), la session ouverte (Règle 3) et l'absence de CAPTCHA/2FA (Règle 2).
- Refuse d'inventer toute valeur par défaut si une donnée ou une pièce manque (Règle 4).
- Prend des captures d'écran PNG de contrôle (par étape si configuré et obligatoirement avant arrêt final),
  les chiffre en AES-256-GCM sur le serveur (et les enregistre en local si `dossier_captures_locales` est fourni).
- S'arrête obligatoirement avant le bouton final de soumission (Règle 1 — Option A) et soumet la tâche
  au Centre de validation humaine (`a_valider`).
"""

from __future__ import annotations

import logging
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

from playwright.sync_api import Page
from sqlalchemy.orm import Session

from app.agent_local.config_portail import (
    ConfigEtapeAutomatisation,
    ConfigPortailYAML,
    ModePortail,
    TypeActionEtapePortail,
    TypeChampPortail,
)
from app.agent_local.connexion_portail import connecter_si_necessaire
from app.agent_local.garde_fous import (
    SuspensionRequiseParGardeFou,
    cliquer_securise,
    verifier_selecteur_non_interdit,
    verifier_session_et_absence_captcha,
)
from app.agent_local.soumission_validee import soumettre_apres_validation
from app.core.erreurs import ErreurMetier

journal = logging.getLogger("app.agent_local")


@dataclass
class ParametresConnexionCoffre:
    """Optionnel : active la connexion automatique via le coffre (Règle 3)."""

    db: Session
    tenant: uuid.UUID
    candidat_id: uuid.UUID
    portail: str  # code coffre : "etudes_en_france" ou "ircc"
    cle_maitresse: bytes = field(repr=False)


@dataclass
class ParametresSoumissionValidee:
    """Optionnel : autorise le clic final UNIQUEMENT si la validation humaine couvre ce contenu."""

    db: Session
    validation_id: uuid.UUID | None
    contenu_actuel: dict[str, Any]
    selecteur_final: str


class ClientHttpAgentProtocol(Protocol):
    """Protocole compatible à la fois avec `httpx.Client` (en production / processus séparé)
    et `fastapi.testclient.TestClient` (en tests d'intégration)."""

    def get(self, url: str, **kwargs: Any) -> Any: ...
    def post(self, url: str, **kwargs: Any) -> Any: ...


@dataclass
class ResultatExecutionAgentLocal:
    tache_id: str
    statut_final: str
    etapes_executees_dans_ce_cycle: list[str] = field(default_factory=list)
    etapes_sautees_idempotence: list[str] = field(default_factory=list)
    captures_prises: list[str] = field(default_factory=list)
    motif_suspension: str | None = None
    message_alerte: str | None = None


def _verifier_domaine_page_autorise(
    page: Page, config_portail: ConfigPortailYAML, *, code_etape: str
) -> None:
    """Corrige le défaut D8 : vérifie que la page courante appartient bien aux domaines
    officiels autorisés dans le fichier YAML du portail."""
    if not config_portail.domaines_autorises:
        return
    analyse = urlparse(page.url)
    hote = (analyse.hostname or "").lower()
    autorises = {d.lower().strip() for d in config_portail.domaines_autorises}
    if hote not in autorises:
        raise SuspensionRequiseParGardeFou(
            motif=__import__(
                "app.modeles.tache", fromlist=["MotifSuspensionTache"]
            ).MotifSuspensionTache.ACTION_UTILISATEUR_PORTAIL,
            message_alerte=(
                f"Domaine d'URL non autorisé ou redirection inattendue ('{hote}'). "
                f"Domaines attendus : {', '.join(sorted(autorises))} (défaut D8 / Règle 7)."
            ),
            code_etape=code_etape,
        )
    if config_portail.mode_portail == ModePortail.REEL and analyse.scheme != "https":
        raise SuspensionRequiseParGardeFou(
            motif=__import__(
                "app.modeles.tache", fromlist=["MotifSuspensionTache"]
            ).MotifSuspensionTache.ACTION_UTILISATEUR_PORTAIL,
            message_alerte=(
                f"Protocole non sécurisé ('{analyse.scheme}') sur un portail réel : HTTPS est obligatoire."
            ),
            code_etape=code_etape,
        )


def _enregistrer_capture_controle(
    page: Page,
    *,
    tache_id: str,
    code_etape: str,
    client_api: ClientHttpAgentProtocol,
    dossier_captures_locales: Path | None,
    captures_prises: list[str],
) -> None:
    octets_png = page.screenshot(full_page=True, type="png")
    if dossier_captures_locales is not None:
        dossier_captures_locales.mkdir(parents=True, exist_ok=True)
        fichier_local = dossier_captures_locales / f"capture_{tache_id}_{code_etape}.png"
        fichier_local.write_bytes(octets_png)

    rep_cap = client_api.post(
        f"/api/v1/taches/{tache_id}/capture-controle",
        files={"fichier": (f"capture_{code_etape}.png", octets_png, "image/png")},
    )
    if rep_cap.status_code != 200:
        raise RuntimeError(
            f"Échec de l'envoi de la capture de contrôle pour l'étape {code_etape} ({rep_cap.status_code})."
        )
    captures_prises.append(code_etape)


def _remplir_champs_etape(
    page: Page,
    *,
    etape_cfg: ConfigEtapeAutomatisation,
    candidat: dict[str, Any],
    config_portail: ConfigPortailYAML,
    champs_saisis_recap: dict[str, str],
) -> None:
    manquants: list[str] = []
    for ch in etape_cfg.champs:
        val = candidat.get(ch.champ_candidat)
        if val is None or (isinstance(val, str) and not val.strip()):
            if ch.obligatoire:
                manquants.append(ch.champ_candidat)

    if manquants:
        raise SuspensionRequiseParGardeFou(
            motif=__import__(
                "app.modeles.tache", fromlist=["MotifSuspensionTache"]
            ).MotifSuspensionTache.DONNEE_MANQUANTE,
            message_alerte=(
                f"Donnée(s) obligatoire(s) manquante(s) pour l'étape '{etape_cfg.code_etape}' : "
                f"{', '.join(manquants)} (règle 4 : aucune valeur par défaut inventée)."
            ),
            code_etape=etape_cfg.code_etape,
            champs_manquants=manquants,
        )

    for ch in etape_cfg.champs:
        verifier_selecteur_non_interdit(ch.selecteur, config_portail)
        val = candidat.get(ch.champ_candidat)
        if val is None:
            continue
        loc = page.locator(ch.selecteur)
        if loc.count() == 0:
            raise SuspensionRequiseParGardeFou(
                motif=__import__(
                    "app.modeles.tache", fromlist=["MotifSuspensionTache"]
                ).MotifSuspensionTache.SELECTEUR_PORTAIL_INTROUVABLE,
                message_alerte=(
                    f"Sélecteur YAML '{ch.selecteur}' introuvable sur la page pour le champ "
                    f"'{ch.champ_candidat}' (règle 7)."
                ),
                code_etape=etape_cfg.code_etape,
            )

        texte_val = str(val)
        if ch.type_champ == TypeChampPortail.LISTE:
            loc.first.select_option(texte_val)
        else:
            loc.first.fill(texte_val)
        # On note uniquement le nom technique du champ et du sélecteur (aucune PII dans les logs)
        champs_saisis_recap[ch.champ_candidat] = ch.selecteur


def _televerser_fichiers_etape(
    page: Page,
    *,
    tache_id: str,
    etape_cfg: ConfigEtapeAutomatisation,
    documents: list[dict[str, Any]],
    client_api: ClientHttpAgentProtocol,
    config_portail: ConfigPortailYAML,
    pieces_televersees_recap: list[str],
) -> None:
    if not etape_cfg.fichiers:
        return

    par_type: dict[str, dict[str, Any]] = {}
    for d in documents:
        par_type[d["type_piece"]] = d

    pieces_manquantes = [
        f.type_piece
        for f in etape_cfg.fichiers
        if f.obligatoire and f.type_piece not in par_type
    ]
    if pieces_manquantes:
        raise SuspensionRequiseParGardeFou(
            motif=__import__(
                "app.modeles.tache", fromlist=["MotifSuspensionTache"]
            ).MotifSuspensionTache.PIECE_MANQUANTE_OU_INVALIDE,
            message_alerte=(
                f"Pièce(s) obligatoire(s) introuvable(s) pour l'étape '{etape_cfg.code_etape}' : "
                f"{', '.join(pieces_manquantes)} (règle 4)."
            ),
            code_etape=etape_cfg.code_etape,
            pieces_manquantes=pieces_manquantes,
        )

    with tempfile.TemporaryDirectory(prefix="be_agent_upload_") as dossier_tmp:
        racine_tmp = Path(dossier_tmp)
        for f_cfg in etape_cfg.fichiers:
            doc = par_type.get(f_cfg.type_piece)
            if doc is None:
                continue
            verifier_selecteur_non_interdit(f_cfg.selecteur, config_portail)
            loc = page.locator(f_cfg.selecteur)
            if loc.count() == 0:
                raise SuspensionRequiseParGardeFou(
                    motif=__import__(
                        "app.modeles.tache", fromlist=["MotifSuspensionTache"]
                    ).MotifSuspensionTache.SELECTEUR_PORTAIL_INTROUVABLE,
                    message_alerte=(
                        f"Sélecteur de téléversement '{f_cfg.selecteur}' introuvable pour "
                        f"la pièce '{f_cfg.type_piece}' (règle 7)."
                    ),
                    code_etape=etape_cfg.code_etape,
                )

            rep_bin = client_api.get(
                f"/api/v1/taches/{tache_id}/documents/{doc['id']}/telecharger"
            )
            if rep_bin.status_code != 200:
                raise RuntimeError(
                    f"Échec du téléchargement de la pièce {f_cfg.type_piece} (statut {rep_bin.status_code})."
                )
            ext = ".pdf" if doc.get("type_mime") == "application/pdf" else ".png"
            chemin_fichier_tmp = racine_tmp / f"{f_cfg.type_piece}{ext}"
            chemin_fichier_tmp.write_bytes(rep_bin.content)
            loc.first.set_input_files(str(chemin_fichier_tmp))
            pieces_televersees_recap.append(f_cfg.type_piece)


def executer_tache_sur_page_playwright(
    page: Page,
    *,
    tache_id: str,
    client_api: ClientHttpAgentProtocol,
    config_portail: ConfigPortailYAML,
    url_base_portail: str,
    parametres_url: str = "",
    naviguer_au_demarrage: bool = True,
    dossier_captures_locales: Path | None = None,
    connexion: ParametresConnexionCoffre | None = None,
    soumission: ParametresSoumissionValidee | None = None,
) -> ResultatExecutionAgentLocal:
    """Exécute ou reprend une tâche sur une page Playwright en respectant les 7 règles non négociables."""
    # 1. Récupère l'état actuel de la tâche
    rep_tache = client_api.get(f"/api/v1/taches/{tache_id}")
    if rep_tache.status_code != 200:
        raise RuntimeError(f"Impossible de lire la tâche {tache_id} ({rep_tache.status_code}).")
    etat_tache = rep_tache.json()

    if etat_tache["statut"] == "en_attente":
        rep_dem = client_api.post(f"/api/v1/taches/{tache_id}/demarrer")
        if rep_dem.status_code != 200:
            etat_apres = client_api.get(f"/api/v1/taches/{tache_id}").json()
            return ResultatExecutionAgentLocal(
                tache_id=tache_id,
                statut_final=etat_apres["statut"],
                motif_suspension=etat_apres.get("motif_suspension"),
                message_alerte=etat_apres.get("message_alerte"),
            )
        etat_tache = rep_dem.json()

    # 2. Récupère le contexte déchiffré (candidat + documents) réservé à la tâche `en_cours`
    rep_ctx = client_api.get(f"/api/v1/taches/{tache_id}/contexte-execution")
    if rep_ctx.status_code != 200:
        raise RuntimeError(
            f"Impossible d'obtenir le contexte d'exécution ({rep_ctx.status_code})."
        )
    contexte = rep_ctx.json()
    candidat = contexte["candidat"]
    documents = contexte["documents"]
    etapes_serveur = {e["code_etape"]: e["statut"] for e in contexte["tache"]["etapes"]}

    # 3. Navigation vers la page cible (si demandé)
    if naviguer_au_demarrage:
        url_complete = url_base_portail.rstrip("/") + config_portail.chemin_url + parametres_url
        reponse_nav = page.goto(url_complete, wait_until="domcontentloaded")
        if reponse_nav is not None and reponse_nav.status >= 400:
            rep_susp_http = client_api.post(
                f"/api/v1/taches/{tache_id}/suspendre",
                json={
                    "motif": "action_utilisateur_portail",
                    "code_etape": config_portail.etapes_automatisation[0].code_etape
                    if config_portail.etapes_automatisation
                    else None,
                    "message_alerte": (
                        f"Le portail a répondu avec un statut HTTP {reponse_nav.status} "
                        "(page indisponible ou maintenance — défaut D8)."
                    ),
                },
            )
            t_susp = (
                rep_susp_http.json()
                if rep_susp_http.status_code == 200
                else {"statut": "suspendue"}
            )
            return ResultatExecutionAgentLocal(
                tache_id=tache_id,
                statut_final=t_susp.get("statut", "suspendue"),
                motif_suspension="action_utilisateur_portail",
                message_alerte=f"Statut HTTP {reponse_nav.status}",
            )

    etapes_executees: list[str] = []
    etapes_sautees: list[str] = []
    captures_prises: list[str] = []
    champs_saisis_recap: dict[str, str] = {}
    pieces_televersees_recap: list[str] = []

    soumission_effectuee = False
    soumission_refusee: str | None = None

    try:
        etapes_a_jouer = [
            e.code_etape
            for e in config_portail.etapes_automatisation
            if etapes_serveur.get(e.code_etape) != "terminee"
        ]
        if connexion is not None and etapes_a_jouer:
            connecter_si_necessaire(
                page,
                connexion.db,
                connexion.tenant,
                connexion.candidat_id,
                connexion.portail,
                config_portail,
                etapes_a_jouer[0],
                cle_maitresse=connexion.cle_maitresse,
            )

        for etape_cfg in config_portail.etapes_automatisation:
            code = etape_cfg.code_etape

            # Reprise idempotente : on ne rejoue JAMAIS une étape déjà `terminee`
            if etapes_serveur.get(code) == "terminee":
                etapes_sautees.append(code)
                continue

            # Vérifie le domaine autorisé (D8) ainsi que les Règles 2 et 3 avant chaque étape
            _verifier_domaine_page_autorise(page, config_portail, code_etape=code)
            verifier_session_et_absence_captcha(
                page, config_portail, code_etape=code
            )

            # Navigation éventuelle vers l'onglet ou la rubrique de l'étape (sans jamais cliquer un bouton interdit)
            if etape_cfg.selecteur_navigation_onglet:
                cliquer_securise(
                    page,
                    etape_cfg.selecteur_navigation_onglet,
                    config_portail,
                    code_etape=code,
                )

            if etape_cfg.type_action == TypeActionEtapePortail.VERIFIER_SESSION_ET_SECURITE:
                detail = "Session portail ouverte vérifiée et aucun CAPTCHA/2FA actif."

            elif etape_cfg.type_action == TypeActionEtapePortail.REMPLIR_CHAMPS:
                _remplir_champs_etape(
                    page,
                    etape_cfg=etape_cfg,
                    candidat=candidat,
                    config_portail=config_portail,
                    champs_saisis_recap=champs_saisis_recap,
                )
                if (
                    etape_cfg.cliquer_brouillon_apres
                    and config_portail.selecteur_enregistrer_brouillon
                ):
                    cliquer_securise(
                        page,
                        config_portail.selecteur_enregistrer_brouillon,
                        config_portail,
                        code_etape=code,
                    )
                if etape_cfg.prendre_capture_etape:
                    _enregistrer_capture_controle(
                        page,
                        tache_id=tache_id,
                        code_etape=code,
                        client_api=client_api,
                        dossier_captures_locales=dossier_captures_locales,
                        captures_prises=captures_prises,
                    )
                detail = f"{len(etape_cfg.champs)} champs pré-remplis."

            elif etape_cfg.type_action == TypeActionEtapePortail.REMPLIR_ET_TELEVERSER:
                _remplir_champs_etape(
                    page,
                    etape_cfg=etape_cfg,
                    candidat=candidat,
                    config_portail=config_portail,
                    champs_saisis_recap=champs_saisis_recap,
                )
                _televerser_fichiers_etape(
                    page,
                    tache_id=tache_id,
                    etape_cfg=etape_cfg,
                    documents=documents,
                    client_api=client_api,
                    config_portail=config_portail,
                    pieces_televersees_recap=pieces_televersees_recap,
                )
                if (
                    etape_cfg.cliquer_brouillon_apres
                    and config_portail.selecteur_enregistrer_brouillon
                ):
                    cliquer_securise(
                        page,
                        config_portail.selecteur_enregistrer_brouillon,
                        config_portail,
                        code_etape=code,
                    )
                if etape_cfg.prendre_capture_etape:
                    _enregistrer_capture_controle(
                        page,
                        tache_id=tache_id,
                        code_etape=code,
                        client_api=client_api,
                        dossier_captures_locales=dossier_captures_locales,
                        captures_prises=captures_prises,
                    )
                detail = (
                    f"{len(etape_cfg.champs)} champs remplis et "
                    f"{len(etape_cfg.fichiers)} pièces téléversées."
                )

            elif etape_cfg.type_action == TypeActionEtapePortail.CAPTURE_ET_ARRET_AVANT_ENVOI:
                if etape_cfg.selecteur_temoin_pret:
                    loc_pret = page.locator(etape_cfg.selecteur_temoin_pret)
                    if loc_pret.count() == 0 or not loc_pret.first.is_visible():
                        raise SuspensionRequiseParGardeFou(
                            motif=__import__(
                                "app.modeles.tache", fromlist=["MotifSuspensionTache"]
                            ).MotifSuspensionTache.SELECTEUR_PORTAIL_INTROUVABLE,
                            message_alerte=(
                                f"Témoin d'enregistrement du brouillon ('{etape_cfg.selecteur_temoin_pret}') "
                                "non visible avant la capture de contrôle."
                            ),
                            code_etape=code,
                        )
                # Prend la capture d'écran PNG finale de contrôle et l'envoie chiffrée au serveur
                _enregistrer_capture_controle(
                    page,
                    tache_id=tache_id,
                    code_etape=code,
                    client_api=client_api,
                    dossier_captures_locales=dossier_captures_locales,
                    captures_prises=captures_prises,
                )
                detail = "Capture d'écran de contrôle déposée ; arrêt strict avant le bouton final (Règle 1)."

            else:
                detail = "Étape exécutée."

            rep_term = client_api.post(
                f"/api/v1/taches/{tache_id}/etapes/{code}/terminer",
                json={
                    "cle_idempotence": f"playwright-{tache_id}-{code}",
                    "detail_execution": detail,
                },
            )
            if rep_term.status_code != 200:
                raise RuntimeError(
                    f"Échec de validation de l'étape {code} ({rep_term.status_code})."
                )
            etapes_executees.append(code)

        # 3 bis. Soumission finale : uniquement si une validation humaine valable est fournie.
        # Sans paramètre `soumission` : comportement historique (arrêt avant le bouton final).
        if soumission is not None:
            try:
                soumettre_apres_validation(
                    page,
                    soumission.db,
                    soumission.validation_id,
                    soumission.contenu_actuel,
                    soumission.selecteur_final,
                    config_portail,
                )
                soumission_effectuee = True
            except ErreurMetier as refus:
                soumission_refusee = refus.code  # arrêt avant le bouton, sans clic

        # 4. Toutes les étapes sont terminées : soumission au Centre de validation humaine (état `a_valider`)
        rep_soum = client_api.post(
            f"/api/v1/taches/{tache_id}/soumettre-validation",
            json={
                "recapitulatif_remplissage": {
                    "code_portail": config_portail.code_portail,
                    "nom_portail": config_portail.nom_portail,
                    "mode_portail": config_portail.mode_portail.value,
                    "code_demarche": config_portail.code_demarche,
                    "champs_preremplis": champs_saisis_recap,
                    "pieces_televersees": pieces_televersees_recap,
                    "etapes_executees": etapes_executees,
                    "etapes_sautees_idempotence": etapes_sautees,
                    "captures_etapes": captures_prises,
                    "bouton_soumission_finale_clique": soumission_effectuee,
                    **({"soumission_refusee": soumission_refusee} if soumission_refusee else {}),
                },
                "message_alerte": (
                    "Envoi final effectué après validation humaine du récapitulatif (Règle 1)."
                    if soumission_effectuee
                    else "Pré-remplissage terminé et arrêté avant le bouton d'envoi final (Règle 1). "
                    "Veuillez vérifier la capture et valider humainement."
                ),
            },
        )
        if rep_soum.status_code != 200:
            raise RuntimeError(
                f"Échec du passage à l'état a_valider ({rep_soum.status_code})."
            )
        tache_finale = rep_soum.json()
        return ResultatExecutionAgentLocal(
            tache_id=tache_id,
            statut_final=tache_finale["statut"],
            etapes_executees_dans_ce_cycle=etapes_executees,
            etapes_sautees_idempotence=etapes_sautees,
            captures_prises=captures_prises,
        )

    except SuspensionRequiseParGardeFou as pause:
        rep_susp = client_api.post(
            f"/api/v1/taches/{tache_id}/suspendre",
            json={
                "motif": pause.motif.value,
                "code_etape": pause.code_etape,
                "message_alerte": pause.message_alerte,
                "champs_manquants": pause.champs_manquants,
                "pieces_manquantes": pause.pieces_manquantes,
            },
        )
        tache_susp = rep_susp.json() if rep_susp.status_code == 200 else {"statut": "suspendue"}
        return ResultatExecutionAgentLocal(
            tache_id=tache_id,
            statut_final=tache_susp.get("statut", "suspendue"),
            etapes_executees_dans_ce_cycle=etapes_executees,
            etapes_sautees_idempotence=etapes_sautees,
            captures_prises=captures_prises,
            motif_suspension=pause.motif.value,
            message_alerte=pause.message_alerte,
        )
