"""Routes d'inspection des configurations YAML des portails (Règle 7), de vérification
des URLs officielles (défaut D8), d'enregistrement de la validation humaine sur portail réel (Règle 6),
et de pilotage direct en temps réel du navigateur Co-Pilote IA (style Perplexity Assistant / Claude Cowork)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.responses import JSONResponse
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent_local.config_portail import (
    ConfigPortailYAML,
    ModePortail,
    StatutTestFonctionnalite,
    lister_configs_portails,
)
from app.agent_local.portails.verificateur_portail import verifier_url_officielle_portail
from app.agent_local.domaines_officiels import politique_depuis_parametres
from app.agent_local.sessions_navigateur import (
    RegistreSessionsNavigateur,
    SessionNavigateur,
    etat_session_absente,
    headless_pour,
)
from app.api.dependances import (
    ContexteAuth,
    exiger_roles,
    obtenir_contexte_auth,
    obtenir_db,
    obtenir_registre_navigateur,
)
from app.core.config import Parametres, obtenir_parametres
from app.core.erreurs import DonneesInvalides, NonAutorise, NonTrouve
from app.modeles.journal_audit import EntreeAudit, ResultatAudit
from app.modeles.utilisateur import Role
from app.schemas.commun import SchemaEntree, SchemaSortie
from app.services import audit

routeur = APIRouter(prefix="/portails", tags=["portails campus france et ircc"])

ExigerAdminHumain = Depends(exiger_roles(Role.ADMINISTRATEUR))


class SynthesePortailSortie(SchemaSortie):
    code_portail: str
    code_demarche: str
    nom_portail: str
    mode_portail: ModePortail
    url_officielle: str | None
    chemin_url: str
    domaines_autorises: list[str]
    nb_etapes_automatisation: int
    selecteurs_soumission_interdits: list[str]
    statut_test_regle6: StatutTestFonctionnalite
    valide_par_administrateur_id: uuid.UUID | None = None
    valide_le: datetime | None = None


class VerificationURLPortailSortie(SchemaSortie):
    code_portail: str
    url_cible: str
    protocole_https_valide: bool
    domaine_autorise: bool
    message: str


class HomologationPortailReelEntree(SchemaEntree):
    confirmation_humaine_explicite: bool
    observations: str | None = Field(default=None, max_length=500)


def _construire_synthese_portail(
    db: Session, cfg: ConfigPortailYAML
) -> SynthesePortailSortie:
    code = cfg.code_portail or cfg.code_demarche
    statut = cfg.statut_test_initial
    valide_par: uuid.UUID | None = None
    valide_le: datetime | None = None

    entrees = db.scalars(
        select(EntreeAudit)
        .where(
            EntreeAudit.action == "portail.validation_humaine_portail_reel",
            EntreeAudit.resultat == ResultatAudit.SUCCES,
        )
        .order_by(EntreeAudit.horodatage.desc())
    ).all()

    for entree in entrees:
        if not entree.details:
            continue
        if entree.details.get("code_portail") == code:
            statut = StatutTestFonctionnalite.VALIDE_SUR_PORTAIL_REEL
            valide_par = entree.acteur_id
            valide_le = entree.horodatage
            break

    return SynthesePortailSortie(
        code_portail=code,
        code_demarche=cfg.code_demarche,
        nom_portail=cfg.nom_portail,
        mode_portail=cfg.mode_portail,
        url_officielle=cfg.url_officielle,
        chemin_url=cfg.chemin_url,
        domaines_autorises=cfg.domaines_autorises,
        nb_etapes_automatisation=len(cfg.etapes_automatisation),
        selecteurs_soumission_interdits=cfg.selecteurs_soumission_interdits,
        statut_test_regle6=statut,
        valide_par_administrateur_id=valide_par,
        valide_le=valide_le,
    )


@routeur.get("", response_model=list[SynthesePortailSortie])
def lister_portails(
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    parametres: Parametres = Depends(obtenir_parametres),
) -> list[SynthesePortailSortie]:
    configs = lister_configs_portails(parametres.dossier_portails)
    return [_construire_synthese_portail(ctx.db, cfg) for cfg in configs.values()]


@routeur.get(
    "/{code_portail}/verifier-url",
    response_model=VerificationURLPortailSortie,
)
def verifier_url_portail(
    code_portail: str,
    _ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    parametres: Parametres = Depends(obtenir_parametres),
) -> VerificationURLPortailSortie:
    configs = lister_configs_portails(parametres.dossier_portails)
    cfg = configs.get(code_portail)
    if cfg is None:
        raise NonTrouve("Configuration de portail introuvable.")
    res = verifier_url_officielle_portail(cfg)
    return VerificationURLPortailSortie(
        code_portail=res.code_portail,
        url_cible=res.url_cible,
        protocole_https_valide=res.protocole_https_valide,
        domaine_autorise=res.domaine_autorise,
        message=res.message,
    )


@routeur.post(
    "/{code_portail}/valider-portail-reel",
    response_model=SynthesePortailSortie,
)
def enregistrer_validation_humaine_portail_reel(
    code_portail: str,
    donnees: HomologationPortailReelEntree,
    ctx: ContexteAuth = ExigerAdminHumain,
    parametres: Parametres = Depends(obtenir_parametres),
) -> SynthesePortailSortie:
    """Permet exclusivement à l'administrateur humain du bureau d'attester qu'il a validé
    lui-même le module sur le portail officiel réel (Règle 6)."""
    if not donnees.confirmation_humaine_explicite:
        raise DonneesInvalides(
            "La confirmation humaine explicite (confirmation_humaine_explicite=true) est obligatoire (Règle 6)."
        )

    configs = lister_configs_portails(parametres.dossier_portails)
    cfg = configs.get(code_portail)
    if cfg is None:
        raise NonTrouve("Configuration de portail introuvable.")
    if cfg.mode_portail != ModePortail.REEL:
        raise DonneesInvalides(
            "Seul un portail configuré en mode 'reel' peut recevoir le statut 'validé sur portail réel'."
        )

    audit.journaliser(
        ctx.db,
        "portail.validation_humaine_portail_reel",
        ResultatAudit.SUCCES,
        acteur_id=ctx.utilisateur.id,
        ressource_type="portail",
        details={
            "code_portail": code_portail,
            "code_demarche": cfg.code_demarche,
            "statut_regle6": StatutTestFonctionnalite.VALIDE_SUR_PORTAIL_REEL.value,
        },
    )
    ctx.db.commit()
    return _construire_synthese_portail(ctx.db, cfg)


# ---------------------------------------------------------------------------
# Guide officiel Études en France (Septembre 2026 — Algérie) & Co-Pilote Navigateur Direct
# ---------------------------------------------------------------------------

ExigerOperateurHumain = Depends(exiger_roles(Role.ADMINISTRATEUR, Role.EMPLOYE))


class VoeuPanierEntree(SchemaEntree):
    """Un vœu à ajouter au panier Campus France. La validité de la motivation (non vide, 4 000 caractères
    max) est contrôlée par le Co-Pilote et rapportée par vœu (statut `motivation_invalide`)."""

    voeu_id: str = Field(min_length=1, max_length=80)
    intitule: str = Field(default="", max_length=300)
    etablissement: str = Field(default="", max_length=300)
    niveau: str | None = Field(default=None, max_length=100)
    motivation: str = Field(default="", max_length=20000)


class PilotageNavigateurEntree(SchemaEntree):
    candidat_id: uuid.UUID
    code_demarche: str = Field(default="campus_france", min_length=2, max_length=60)
    cible: str = Field(default="campus_france_officiel", min_length=2, max_length=80)
    action: str = Field(default="preremplissage_complet", min_length=2, max_length=80)
    instruction_libre: str | None = Field(default=None, max_length=1000)
    ouvrir_fenetre_visible: bool = True
    synchroniser_tache: bool = True
    prendre_capture: bool = True
    # Action « ajouter_voeux_panier » : liste des vœux (optionnelle, ignorée pour les autres actions)
    voeux: list[VoeuPanierEntree] | None = Field(default=None, max_length=20)


class PilotageNavigateurSortie(SchemaSortie):
    succes: bool
    code_demarche: str
    cible: str
    action_executee: str
    url_courante: str
    titre_page: str
    resume_francais: str
    reponse_agent: str = ""
    etapes_realisees: list[str]
    champs_remplis_libelles: list[str]
    pieces_televersees_libelles: list[str]
    champs_manquants_libelles: list[str]
    avertissements_securite: list[str]
    elements_interactifs_page: list[dict[str, str]] = Field(default_factory=list)
    modifications_candidat_detectees: dict[str, Any] = Field(default_factory=dict)
    arret_regle1_avant_soumission: bool
    blocage_captcha_ou_2fa: bool
    attente_connexion_humaine_regle3: bool
    mode_controle_direct: bool = True
    capture_base64: str | None = None
    tache_id: uuid.UUID | None = None
    statut_tache: str | None = None
    pieces_manquantes_tache: list[str] = Field(default_factory=list)
    # Résultat par vœu : voeu_id, intitule, etablissement, statut, motivation_enregistree, nb_caracteres
    resultats_voeux: list[dict[str, Any]] = Field(default_factory=list)
    # Chemin du fichier de calibration écrit par l'action « cartographier_page »
    fichier_calibration: str | None = None


class ActionDomDirecteEntree(SchemaEntree):
    type_operation: str = Field(..., min_length=2, max_length=40)
    selecteur: str | None = Field(default=None, max_length=300)
    valeur: str | None = Field(default=None, max_length=2000)
    url_destination: str | None = Field(default=None, max_length=500)
    ouvrir_fenetre_visible: bool = True


class CopiloteBridgeEntree(SchemaEntree):
    instruction_libre: str = Field(..., min_length=1, max_length=1000)
    url_courante: str | None = Field(default=None, max_length=500)


@routeur.get("/campus-france/guide-2026")
def obtenir_guide_campus_france_2026(
    _ctx: ContexteAuth = Depends(obtenir_contexte_auth),
) -> dict:
    """Retourne le référentiel complet du Guide Études en France — Septembre 2026 (Campus France Algérie)."""
    from app.agent_local.guide_campus_france_2026 import GUIDE_CAMPUS_FRANCE_SEPTEMBRE_2026

    return GUIDE_CAMPUS_FRANCE_SEPTEMBRE_2026


@routeur.get("/etat-navigateur")
def obtenir_etat_temps_reel_navigateur(
    ctx: ContexteAuth = ExigerOperateurHumain,
    registre: RegistreSessionsNavigateur = Depends(obtenir_registre_navigateur),
) -> dict[str, Any]:
    """Retourne en temps réel (< 25 ms, sans capture d'écran) l'état de l'onglet actif
    du navigateur DU BUREAU, ses champs et boutons interactifs et le journal d'actions.
    Ne crée jamais de session."""
    session = registre.existante(ctx.utilisateur.tenant_id)
    if session is None:
        return etat_session_absente()
    return session.gestionnaire.obtenir_etat_temps_reel()


@routeur.post("/action-dom-directe")
def executer_action_dom_directe_navigateur(
    donnees: ActionDomDirecteEntree,
    ctx: ContexteAuth = ExigerOperateurHumain,
    parametres: Parametres = Depends(obtenir_parametres),
    registre: RegistreSessionsNavigateur = Depends(obtenir_registre_navigateur),
) -> dict[str, Any]:
    """Exécute instantanément une action directe dans le DOM du navigateur du bureau (clic, saisie,
    navigation, défilement, mise au premier plan de la fenêtre) sans capture d'écran.
    Toute navigation est soumise à la Règle 6 (domaines HTTPS officiels des YAML)."""
    session = registre.obtenir(ctx.utilisateur.tenant_id, parametres)
    return session.gestionnaire.executer_action_dom_directe(
        type_operation=donnees.type_operation,
        selecteur=donnees.selecteur,
        valeur=donnees.valeur,
        url_destination=donnees.url_destination,
        dossier_profil=session.dossier_profil,
        headless=headless_pour(parametres, ouvrir_fenetre_visible=donnees.ouvrir_fenetre_visible),
    )


def _en_tetes_cors_copilote(origine: str | None) -> dict[str, str]:
    """CORS du pont : jamais « * » ni cookies (pas d'Allow-Credentials). L'origine n'est reflétée que si
    c'est celle d'une page officielle (HTTPS, domaines des YAML) ou de démonstration hors production."""
    return {
        "Access-Control-Allow-Origin": origine or "null",
        "Vary": "Origin",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-Copilote-Bridge-Token",
        "Access-Control-Allow-Private-Network": "true",
    }


@routeur.options("/copilote-bridge")
def options_copilote_bridge(
    requete: Request,
    parametres: Parametres = Depends(obtenir_parametres),
) -> Response:
    origine = requete.headers.get("origin")
    if not politique_depuis_parametres(parametres).origine_autorisee(origine):
        return Response(status_code=403, headers={"Vary": "Origin"})
    return Response(status_code=204, headers=_en_tetes_cors_copilote(origine))


@routeur.post("/copilote-bridge")
def executer_depuis_barre_laterale_navigateur(
    donnees: CopiloteBridgeEntree,
    requete: Request,
    x_copilote_bridge_token: str | None = Header(default=None),
    parametres: Parametres = Depends(obtenir_parametres),
    registre: RegistreSessionsNavigateur = Depends(obtenir_registre_navigateur),
    db: Session = Depends(obtenir_db),
) -> JSONResponse:
    """Pont temps réel appelé par la barre latérale Co-Pilote IA injectée dans la page du navigateur
    (même sur un domaine externe comme `etudesenfrance.diplomatie.gouv.fr`).

    Authentification : UNIQUEMENT le jeton propre à la session navigateur du bureau
    (`X-Copilote-Bridge-Token`, aléatoire, régénéré à chaque session). La simple présence d'un
    cookie de session ne suffit plus (la page officielle n'envoie de toute façon pas nos cookies)."""
    from app.core.erreurs import AccesRefuse
    from app.db.tenant import definir_tenant
    from app.services import acces_abonnement

    origine = requete.headers.get("origin")
    if origine and not politique_depuis_parametres(parametres).origine_autorisee(origine):
        raise AccesRefuse("Origine non autorisée pour le pont Co-Pilote.")

    session = registre.par_jeton(x_copilote_bridge_token)
    if session is None:
        raise NonAutorise("Jeton de pont Co-Pilote navigateur invalide.")

    # Le bureau de la session pilote l'isolation ORM, l'abonnement (lecture seule => 402) et l'audit.
    definir_tenant(db, session.tenant_id)
    acces_abonnement.exiger_ecriture_autorisee(
        methode="POST", chemin=requete.url.path, db=db, parametres=parametres
    )
    registre.toucher(session.tenant_id)

    gest = session.gestionnaire
    resultat = gest.executer_action(
        code_demarche=gest._derniere_demarche,
        cible=gest._derniere_cible,
        action="instruction_libre",
        instruction_libre=donnees.instruction_libre,
        candidat=dict(gest._dernier_candidat),
        documents_dechiffres=[],
        dossier_profil=session.dossier_profil,
        headless=headless_pour(parametres),
        prendre_capture=False,
    )
    # R5 : ni le texte de l'instruction ni l'URL dans l'audit.
    audit.journaliser(
        db,
        "navigateur.pont_copilote",
        ResultatAudit.SUCCES if resultat.succes else ResultatAudit.REFUS,
        ressource_type="navigateur",
        details={"action": "instruction_libre"},
    )
    db.commit()
    return JSONResponse(
        status_code=200,
        headers=_en_tetes_cors_copilote(origine) if origine else None,
        content={
            "succes": resultat.succes,
            "resume_francais": resultat.resume_francais,
            "reponse_agent": resultat.reponse_agent,
            "etapes_realisees": resultat.etapes_realisees,
            "champs_remplis_libelles": resultat.champs_remplis_libelles,
            "url_courante": resultat.url_courante,
            "titre_page": resultat.titre_page,
        },
    )


def _instruction_necessite_documents(action: str, instruction_libre: str | None) -> bool:
    if action in {"preremplissage_complet", "preremplir_scolarite_et_langues", "televerser_pieces_ircc"}:
        return True
    if not instruction_libre:
        return False
    inst_low = instruction_libre.lower()
    return any(
        m in inst_low
        for m in (
            "tout",
            "complet",
            "intégralité",
            "integralite",
            "scolarit",
            "pièce",
            "piece",
            "justificatif",
            "télévers",
            "televers",
            "upload",
            "joindre",
            "cv",
            "passeport",
            "photo",
            "bac",
            "relev",
            "diplôm",
            "diplom",
            "tcf",
            "delf",
            "pal",
            "caq",
            "imm",
            "loa",
            "formulaire",
            "dossier",
        )
    )


@routeur.post("/piloter-navigateur", response_model=PilotageNavigateurSortie)
def piloter_navigateur_portail(
    donnees: PilotageNavigateurEntree,
    ctx: ContexteAuth = ExigerOperateurHumain,
    parametres: Parametres = Depends(obtenir_parametres),
    registre: RegistreSessionsNavigateur = Depends(obtenir_registre_navigateur),
    cle_maitresse: bytes = Depends(
        __import__("app.api.dependances", fromlist=["obtenir_cle_maitresse"]).obtenir_cle_maitresse
    ),
) -> PilotageNavigateurSortie:
    """Pilote directement le navigateur en temps réel via Playwright sur le vrai site
    Campus France / IRCC ou sur la page locale, comprend et exécute l'instruction en langage naturel
    de l'opérateur, et retourne l'état interactif en direct ainsi que la réponse du Co-Pilote."""
    from app.agent_local.pilote_navigateur import (
        ACTION_AJOUTER_VOEUX_PANIER,
        ACTIONS_PANIER_ET_CALIBRATION,
    )
    from app.modeles.tache import StatutTache, TacheDossier
    from app.schemas.candidat import CandidatModification
    from app.schemas.tache import (
        DemarrerTacheEntree,
        SoumissionValidationEntree,
        TacheCreation,
        TerminerEtapeEntree,
    )
    from app.services import candidats as service_candidats
    from app.services import documents as service_documents
    from app.services import taches as service_taches

    cand = service_candidats.obtenir_candidat(
        ctx.db, candidat_id=donnees.candidat_id, cle_maitresse=cle_maitresse
    )

    docs_dechiffres: list[tuple[str, str, str, bytes]] = []
    if _instruction_necessite_documents(donnees.action, donnees.instruction_libre):
        docs_meta = service_documents.lister_documents_candidat(
            ctx.db, candidat_id=cand.id, cle_maitresse=cle_maitresse
        )
        for d in docs_meta:
            try:
                meta, octets = service_documents.lire_document_dechiffre(
                    ctx.db,
                    candidat_id=cand.id,
                    document_id=d.id,
                    parametres=parametres,
                    cle_maitresse=cle_maitresse,
                )
                docs_dechiffres.append((meta.type_piece, meta.nom_fichier_origine, meta.type_mime, octets))
            except Exception:
                continue

    session_bureau: SessionNavigateur = registre.obtenir(ctx.utilisateur.tenant_id, parametres)
    headless = headless_pour(parametres, ouvrir_fenetre_visible=donnees.ouvrir_fenetre_visible)
    dossier_profil = session_bureau.dossier_profil

    # Si synchroniser_tache est actif pour un pré-remplissage complet, on prend une capture de contrôle Règle 1
    besoin_capture = donnees.prendre_capture or (
        donnees.synchroniser_tache and donnees.action == "preremplissage_complet"
    )

    # Règle 6 : « homologué » = le portail réel de cette démarche porte le statut « validé sur portail réel »
    # (attestation humaine de l'administrateur). Sans cela, l'ajout de vœux est refusé hors page de démo.
    est_action_panier = donnees.action in ACTIONS_PANIER_ET_CALIBRATION
    portail_homologue = False
    if donnees.action == ACTION_AJOUTER_VOEUX_PANIER and not donnees.cible.startswith("demo_"):
        for cfg_portail in lister_configs_portails(parametres.dossier_portails).values():
            if cfg_portail.mode_portail == ModePortail.REEL and cfg_portail.code_demarche == donnees.code_demarche:
                synthese = _construire_synthese_portail(ctx.db, cfg_portail)
                if synthese.statut_test_regle6 == StatutTestFonctionnalite.VALIDE_SUR_PORTAIL_REEL:
                    portail_homologue = True
                    break

    # Vœux à envoyer au panier : ceux fournis explicitement, sinon UNIQUEMENT les vœux VALIDÉS par
    # l'opérateur en base (lettre relue, sans repère « À COMPLÉTER »). Rien n'est jamais inventé (R4).
    voeux_a_envoyer: list[dict[str, Any]] | None = (
        [v.model_dump() for v in donnees.voeux] if donnees.voeux else None
    )
    if donnees.action == ACTION_AJOUTER_VOEUX_PANIER and voeux_a_envoyer is None:
        from app.core.erreurs import DonneesInvalides
        from app.services import voeux as service_voeux

        valides = service_voeux.lister_voeux_pour_panier(ctx.db, cand.id, cle_maitresse)
        voeux_a_envoyer = [
            {
                "voeu_id": str(v["voeu_id"]),
                "intitule": v["intitule"],
                "etablissement": v["etablissement"],
                "niveau": v["niveau"],
                "motivation": v["motivation"] or "",
            }
            for v in valides
        ]
        if not voeux_a_envoyer:
            raise DonneesInvalides(
                "Aucun vœu validé pour ce candidat : rédigez puis validez au moins un vœu "
                "(onglet Campus France, « Vœux et lettres de motivation »)."
            )

    resultat = session_bureau.gestionnaire.executer_action(
        code_demarche=donnees.code_demarche,
        cible=donnees.cible,
        action=donnees.action,
        instruction_libre=donnees.instruction_libre,
        candidat=cand.model_dump(mode="json"),
        documents_dechiffres=docs_dechiffres,
        dossier_profil=dossier_profil,
        headless=headless,
        prendre_capture=besoin_capture,
        voeux=voeux_a_envoyer,
        portail_homologue=portail_homologue,
    )

    # Les vœux réellement ajoutés au panier passent au statut « dans le panier ». Jamais après un
    # essai sur la page de démonstration : le vrai panier de l'étudiante n'a alors pas changé.
    if (
        donnees.action == ACTION_AJOUTER_VOEUX_PANIER
        and not donnees.cible.startswith("demo_")
        and resultat.resultats_voeux
    ):
        from app.core.erreurs import ErreurMetier
        from app.services import voeux as service_voeux

        for r in resultat.resultats_voeux:
            if r.get("statut") == "ajoute" and r.get("motivation_enregistree"):
                try:
                    service_voeux.marquer_ajoute_au_panier(
                        ctx.db,
                        candidat_id=cand.id,
                        voeu_id=uuid.UUID(str(r["voeu_id"])),
                        acteur_id=ctx.utilisateur.id,
                        cle_maitresse=cle_maitresse,
                    )
                except (ErreurMetier, ValueError):
                    continue  # vœu fourni hors base ou pas au statut validé : rien à marquer

    # Si l'opérateur a dicté de nouvelles valeurs en langage naturel (ex: « mets Oran comme ville »),
    # on met à jour automatiquement la fiche chiffrée du candidat.
    if resultat.modifications_candidat_detectees:
        try:
            modif_dict: dict[str, Any] = {}
            for k, v in resultat.modifications_candidat_detectees.items():
                if k == "fonds_disponibles_eur":
                    try:
                        modif_dict[k] = int(v)
                    except Exception:
                        pass
                elif k in {
                    "nom",
                    "prenom",
                    "lieu_naissance",
                    "nationalite",
                    "pays_residence",
                    "email",
                    "telephone",
                    "numero_passeport",
                    "niveau_actuel",
                    "programme_vise",
                    "etablissement_vise",
                }:
                    modif_dict[k] = str(v)
            if modif_dict:
                service_candidats.modifier_candidat(
                    ctx.db,
                    candidat_id=cand.id,
                    donnees=CandidatModification(**modif_dict),
                    acteur_id=ctx.utilisateur.id,
                    cle_maitresse=cle_maitresse,
                )
        except Exception:
            pass

    tache_id_retour: uuid.UUID | None = None
    statut_tache_retour: str | None = None
    pieces_manquantes_tache: list[str] = []

    # Synchronisation optionnelle avec la machine à états des tâches et le Centre de validation humaine
    if (
        donnees.synchroniser_tache
        and not est_action_panier
        and donnees.code_demarche in {"campus_france", "ircc_permis_etudes"}
    ):
        try:
            tache_existante = ctx.db.scalar(
                select(TacheDossier).where(
                    TacheDossier.candidat_id == cand.id,
                    TacheDossier.code_demarche == donnees.code_demarche,
                    TacheDossier.statut.in_(
                        {
                            StatutTache.EN_ATTENTE,
                            StatutTache.EN_COURS,
                            StatutTache.SUSPENDUE,
                            StatutTache.A_VALIDER,
                        }
                    ),
                )
            )
            if tache_existante is None:
                t_sortie = service_taches.creer_tache(
                    ctx.db,
                    donnees=TacheCreation(
                        candidat_id=cand.id, code_demarche=donnees.code_demarche
                    ),
                    acteur_id=ctx.utilisateur.id,
                    parametres=parametres,
                    cle_maitresse=cle_maitresse,
                )
            else:
                t_sortie = service_taches.obtenir_tache(
                    ctx.db, tache_id=tache_existante.id, cle_maitresse=cle_maitresse
                )

            if t_sortie.statut == StatutTache.SUSPENDUE:
                try:
                    t_sortie = service_taches.reprendre_tache(
                        ctx.db,
                        tache_id=t_sortie.id,
                        acteur_id=ctx.utilisateur.id,
                        parametres=parametres,
                        cle_maitresse=cle_maitresse,
                    )
                except Exception:
                    pass

            est_preremplissage_suffisant = (
                donnees.action == "preremplissage_complet"
                or len(resultat.champs_remplis_libelles) >= 5
            )

            if (
                t_sortie.statut == StatutTache.EN_ATTENTE
                and est_preremplissage_suffisant
                and resultat.succes
            ):
                t_sortie = service_taches.demarrer_tache(
                    ctx.db,
                    tache_id=t_sortie.id,
                    donnees=DemarrerTacheEntree(detenteur="pilote-navigateur-direct"),
                    acteur_id=ctx.utilisateur.id,
                    agent_local_id=None,
                    parametres=parametres,
                    cle_maitresse=cle_maitresse,
                )
                for etape in t_sortie.etapes:
                    if etape.statut.value != "terminee":
                        t_sortie = service_taches.terminer_etape_tache(
                            ctx.db,
                            tache_id=t_sortie.id,
                            code_etape=etape.code_etape,
                            donnees=TerminerEtapeEntree(
                                cle_idempotence=f"pilote-{t_sortie.id}-{etape.code_etape}",
                                detail_execution=f"Exécuté par le Co-Pilote Navigateur ({donnees.cible})",
                            ),
                            acteur_id=ctx.utilisateur.id,
                            agent_local_id=None,
                            parametres=parametres,
                            cle_maitresse=cle_maitresse,
                        )
                if resultat.capture_png_octets:
                    service_taches.deposer_capture_controle(
                        ctx.db,
                        tache_id=t_sortie.id,
                        contenu_clair=resultat.capture_png_octets,
                        acteur_id=ctx.utilisateur.id,
                        agent_local_id=None,
                        parametres=parametres,
                        cle_maitresse=cle_maitresse,
                    )
                t_sortie = service_taches.soumettre_pour_validation_humaine(
                    ctx.db,
                    tache_id=t_sortie.id,
                    donnees=SoumissionValidationEntree(
                        recapitulatif_remplissage={
                            "portail_cible": donnees.cible,
                            "url_finale": resultat.url_courante,
                            "champs_remplis": resultat.champs_remplis_libelles,
                            "pieces_jointes": resultat.pieces_televersees_libelles,
                            "etapes_realisees": resultat.etapes_realisees,
                            "bouton_soumission_finale_clique": False,
                        },
                        message_alerte=(
                            "Pré-remplissage effectué en direct par le Co-Pilote Navigateur et arrêté avant soumission finale (Règle 1). "
                            "Prêt pour contrôle et validation humaine."
                        ),
                    ),
                    acteur_id=ctx.utilisateur.id,
                    agent_local_id=None,
                    cle_maitresse=cle_maitresse,
                )
            elif (
                t_sortie.statut == StatutTache.A_VALIDER
                and resultat.succes
                and resultat.capture_png_octets
            ):
                t_sortie = service_taches.deposer_capture_controle(
                    ctx.db,
                    tache_id=t_sortie.id,
                    contenu_clair=resultat.capture_png_octets,
                    acteur_id=ctx.utilisateur.id,
                    agent_local_id=None,
                    parametres=parametres,
                    cle_maitresse=cle_maitresse,
                )

            tache_id_retour = t_sortie.id
            statut_tache_retour = t_sortie.statut.value
            pieces_manquantes_tache = list(t_sortie.pieces_manquantes or [])
        except Exception:
            pass

    details_audit: dict[str, Any] = {
        "code_demarche": donnees.code_demarche,
        "cible": donnees.cible,
        "action": donnees.action,
        "nb_champs_remplis": len(resultat.champs_remplis_libelles),
        "nb_pieces_televersees": len(resultat.pieces_televersees_libelles),
        "arret_regle1": resultat.arret_regle1_avant_soumission,
    }
    if est_action_panier:
        # R5 : uniquement des compteurs — jamais de texte de motivation, d'intitulé ni de nom
        details_audit["nb_voeux_demandes"] = len(voeux_a_envoyer or [])
        for statut_voeu in {r["statut"] for r in resultat.resultats_voeux}:
            details_audit[f"nb_voeux_{statut_voeu}"] = sum(
                1 for r in resultat.resultats_voeux if r["statut"] == statut_voeu
            )
        details_audit["nb_motivations_enregistrees"] = sum(
            1 for r in resultat.resultats_voeux if r["motivation_enregistree"]
        )
        details_audit["portail_homologue"] = portail_homologue
        details_audit["blocage_captcha_ou_2fa"] = resultat.blocage_captcha_ou_2fa
        if resultat.fichier_calibration:
            details_audit["calibration_enregistree"] = True

    audit.journaliser(
        ctx.db,
        "portail.pilotage_navigateur",
        ResultatAudit.SUCCES if resultat.succes else ResultatAudit.REFUS,
        acteur_id=ctx.utilisateur.id,
        ressource_type="candidat",
        ressource_id=cand.id,
        details=details_audit,
    )
    ctx.db.commit()

    return PilotageNavigateurSortie(
        succes=resultat.succes,
        code_demarche=resultat.code_demarche,
        cible=resultat.cible,
        action_executee=resultat.action_executee,
        url_courante=resultat.url_courante,
        titre_page=resultat.titre_page,
        resume_francais=resultat.resume_francais,
        reponse_agent=resultat.reponse_agent,
        etapes_realisees=resultat.etapes_realisees,
        champs_remplis_libelles=resultat.champs_remplis_libelles,
        pieces_televersees_libelles=resultat.pieces_televersees_libelles,
        champs_manquants_libelles=resultat.champs_manquants_libelles,
        avertissements_securite=resultat.avertissements_securite,
        elements_interactifs_page=resultat.elements_interactifs_page,
        modifications_candidat_detectees=resultat.modifications_candidat_detectees,
        arret_regle1_avant_soumission=resultat.arret_regle1_avant_soumission,
        blocage_captcha_ou_2fa=resultat.blocage_captcha_ou_2fa,
        attente_connexion_humaine_regle3=resultat.attente_connexion_humaine_regle3,
        mode_controle_direct=True,
        capture_base64=resultat.capture_base64,
        tache_id=tache_id_retour,
        statut_tache=statut_tache_retour,
        pieces_manquantes_tache=pieces_manquantes_tache,
        resultats_voeux=resultat.resultats_voeux,
        fichier_calibration=resultat.fichier_calibration,
    )
