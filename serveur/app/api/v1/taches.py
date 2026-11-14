"""Routes de gestion des tâches longues, des étapes idempotentes, des verrous exclusifs
par dossier et des décisions de validation humaine (Phase 3)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependances import (
    EN_TETE_JETON_AGENT,
    ContexteAgentLocal,
    ContexteAuth,
    ContexteExecutionTache,
    exiger_roles,
    obtenir_agent_local_requis,
    obtenir_cle_maitresse,
    obtenir_contexte_auth,
    obtenir_contexte_auth_brut,
    obtenir_contexte_execution_tache,
    obtenir_db,
)
from app.core.config import Parametres, obtenir_parametres
from app.modeles.tache import ACTION_PREREMPLISSAGE, StatutTache
from app.modeles.utilisateur import Role
from app.schemas.commun import Page
from app.schemas.tache import (
    ContexteDossierExecutionSortie,
    DemarrerTacheEntree,
    RejetValidationEntree,
    ReservationTacheSortie,
    SignalerErreurTacheEntree,
    SoumissionValidationEntree,
    SuspendreTacheEntree,
    TacheCreation,
    TacheSortie,
    TerminerEtapeEntree,
    ValidationHumaineEntree,
    VoeuxAAjouterSortie,
)
from app.services import agents_locaux as service_agents
from app.services import reservation_taches as service_reservation
from app.services import taches as service_taches
from app.services import taches_ouverture_pc as service_ouverture_pc

routeur = APIRouter(prefix="/taches", tags=["tâches et validation humaine"])

ExigerEcritureHumaine = Depends(exiger_roles(Role.ADMINISTRATEUR, Role.EMPLOYE))


def _obtenir_db_lecture_tache(
    requete: Request,
    db: Session = Depends(obtenir_db),
    parametres: Parametres = Depends(obtenir_parametres),
) -> Session:
    """Permet la lecture des tâches du bureau soit par un utilisateur authentifié (y compris
    `lecture_seule`), soit par un agent local enrôlé du bureau (`X-Agent-Token`)."""
    jeton_agent = requete.headers.get(EN_TETE_JETON_AGENT)
    if jeton_agent:
        service_agents.verifier_jeton_agent_local(db, jeton_clair=jeton_agent)
        return db
    obtenir_contexte_auth(
        obtenir_contexte_auth_brut(requete=requete, db=db, parametres=parametres)
    )
    return db


@routeur.get("", response_model=Page[TacheSortie])
def lister(
    page: int = Query(default=1, ge=1),
    taille: int = Query(default=20, ge=1, le=100),
    statut: StatutTache | None = Query(default=None),
    candidat_id: uuid.UUID | None = Query(default=None),
    code_demarche: str | None = Query(default=None, max_length=60),
    db: Session = Depends(_obtenir_db_lecture_tache),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> Page[TacheSortie]:
    elements, total = service_taches.lister_taches(
        db,
        cle_maitresse=cle_maitresse,
        page=page,
        taille=taille,
        statut=statut,
        candidat_id=candidat_id,
        code_demarche=code_demarche,
    )
    return Page(elements=elements, total=total, page=page, taille=taille)


@routeur.post("", response_model=TacheSortie, status_code=status.HTTP_201_CREATED)
def creer(
    donnees: TacheCreation,
    ctx: ContexteAuth = ExigerEcritureHumaine,
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> TacheSortie:
    if donnees.action != ACTION_PREREMPLISSAGE:
        return service_ouverture_pc.creer_tache_ouverture_pc(
            ctx.db,
            donnees=donnees,
            acteur_id=ctx.utilisateur.id,
            cle_maitresse=cle_maitresse,
        )
    return service_taches.creer_tache(
        ctx.db,
        donnees=donnees,
        acteur_id=ctx.utilisateur.id,
        parametres=parametres,
        cle_maitresse=cle_maitresse,
    )


@routeur.post("/reserver-suivante", response_model=ReservationTacheSortie)
def reserver_suivante(
    actions: list[str] | None = Query(default=None, max_length=10),
    ctx: ContexteAgentLocal = Depends(obtenir_agent_local_requis),
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> ReservationTacheSortie:
    """Réservation ATOMIQUE (compare-and-swap) de la plus ancienne tâche « Ouvrir sur mon PC » en
    attente du bureau de l'agent. Deux agents ne reçoivent jamais la même tâche. Jeton agent obligatoire."""
    tache = service_reservation.reserver_tache_suivante(
        ctx.db,
        agent=ctx.agent_local,
        parametres=parametres,
        cle_maitresse=cle_maitresse,
        actions=actions,
    )
    return ReservationTacheSortie(tache=tache)


@routeur.get("/{tache_id}/voeux-a-ajouter", response_model=VoeuxAAjouterSortie)
def voeux_a_ajouter(
    tache_id: uuid.UUID,
    ctx: ContexteAgentLocal = Depends(obtenir_agent_local_requis),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> VoeuxAAjouterSortie:
    """Ne sert QUE les vœux au statut `valide`, à l'agent qui détient la tâche `ajouter_voeux_panier`."""
    return service_reservation.voeux_valides_pour_agent(
        ctx.db, tache_id=tache_id, agent=ctx.agent_local, cle_maitresse=cle_maitresse
    )


@routeur.get("/{tache_id}", response_model=TacheSortie)
def obtenir(
    tache_id: uuid.UUID,
    db: Session = Depends(_obtenir_db_lecture_tache),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> TacheSortie:
    return service_taches.obtenir_tache(
        db, tache_id=tache_id, cle_maitresse=cle_maitresse
    )


@routeur.get(
    "/{tache_id}/contexte-execution",
    response_model=ContexteDossierExecutionSortie,
)
def obtenir_contexte_execution(
    tache_id: uuid.UUID,
    ctx: ContexteExecutionTache = Depends(obtenir_contexte_execution_tache),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> ContexteDossierExecutionSortie:
    return service_taches.obtenir_contexte_dossier_execution(
        ctx.db, tache_id=tache_id, agent_local_id=ctx.agent_local_id, cle_maitresse=cle_maitresse
    )


@routeur.get("/{tache_id}/documents/{document_id}/telecharger")
def telecharger_document_pour_tache(
    tache_id: uuid.UUID,
    document_id: uuid.UUID,
    ctx: ContexteExecutionTache = Depends(obtenir_contexte_execution_tache),
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> Response:
    type_mime, _nom, octets = service_taches.lire_document_pour_tache_en_cours(
        ctx.db,
        tache_id=tache_id,
        document_id=document_id,
        agent_local_id=ctx.agent_local_id,
        parametres=parametres,
        cle_maitresse=cle_maitresse,
    )
    return Response(
        content=octets,
        media_type=type_mime,
        headers={
            "Content-Disposition": f'attachment; filename="{document_id}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@routeur.post("/{tache_id}/demarrer", response_model=TacheSortie)
def demarrer(
    tache_id: uuid.UUID,
    donnees: DemarrerTacheEntree | None = None,
    ctx: ContexteExecutionTache = Depends(obtenir_contexte_execution_tache),
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> TacheSortie:
    return service_taches.demarrer_tache(
        ctx.db,
        tache_id=tache_id,
        donnees=donnees or DemarrerTacheEntree(),
        acteur_id=ctx.acteur_id,
        agent_local_id=ctx.agent_local_id,
        parametres=parametres,
        cle_maitresse=cle_maitresse,
    )


@routeur.post("/{tache_id}/battement-coeur", response_model=TacheSortie)
def battement_coeur(
    tache_id: uuid.UUID,
    ctx: ContexteExecutionTache = Depends(obtenir_contexte_execution_tache),
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> TacheSortie:
    return service_taches.renouveler_verrou_tache(
        ctx.db,
        tache_id=tache_id,
        acteur_id=ctx.acteur_id,
        agent_local_id=ctx.agent_local_id,
        parametres=parametres,
        cle_maitresse=cle_maitresse,
    )


@routeur.post("/{tache_id}/etapes/{code_etape}/terminer", response_model=TacheSortie)
def terminer_etape(
    tache_id: uuid.UUID,
    code_etape: str,
    donnees: TerminerEtapeEntree,
    ctx: ContexteExecutionTache = Depends(obtenir_contexte_execution_tache),
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> TacheSortie:
    return service_taches.terminer_etape_tache(
        ctx.db,
        tache_id=tache_id,
        code_etape=code_etape,
        donnees=donnees,
        acteur_id=ctx.acteur_id,
        agent_local_id=ctx.agent_local_id,
        parametres=parametres,
        cle_maitresse=cle_maitresse,
    )


@routeur.post("/{tache_id}/suspendre", response_model=TacheSortie)
def suspendre(
    tache_id: uuid.UUID,
    donnees: SuspendreTacheEntree,
    ctx: ContexteExecutionTache = Depends(obtenir_contexte_execution_tache),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> TacheSortie:
    return service_taches.suspendre_tache(
        ctx.db,
        tache_id=tache_id,
        donnees=donnees,
        acteur_id=ctx.acteur_id,
        agent_local_id=ctx.agent_local_id,
        cle_maitresse=cle_maitresse,
    )


@routeur.post("/{tache_id}/erreur", response_model=TacheSortie)
def signaler_erreur(
    tache_id: uuid.UUID,
    donnees: SignalerErreurTacheEntree,
    ctx: ContexteExecutionTache = Depends(obtenir_contexte_execution_tache),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> TacheSortie:
    return service_taches.signaler_erreur_tache(
        ctx.db,
        tache_id=tache_id,
        donnees=donnees,
        acteur_id=ctx.acteur_id,
        agent_local_id=ctx.agent_local_id,
        cle_maitresse=cle_maitresse,
    )


@routeur.post("/{tache_id}/reprendre", response_model=TacheSortie)
def reprendre(
    tache_id: uuid.UUID,
    ctx: ContexteAuth = ExigerEcritureHumaine,
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> TacheSortie:
    return service_taches.reprendre_tache(
        ctx.db,
        tache_id=tache_id,
        acteur_id=ctx.utilisateur.id,
        parametres=parametres,
        cle_maitresse=cle_maitresse,
    )


@routeur.post("/{tache_id}/capture-controle", response_model=TacheSortie)
async def deposer_capture_controle(
    tache_id: uuid.UUID,
    fichier: UploadFile = File(...),
    ctx: ContexteExecutionTache = Depends(obtenir_contexte_execution_tache),
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> TacheSortie:
    contenu = await fichier.read(parametres.taille_max_document_octets + 1)
    return service_taches.deposer_capture_controle(
        ctx.db,
        tache_id=tache_id,
        contenu_clair=contenu,
        acteur_id=ctx.acteur_id,
        agent_local_id=ctx.agent_local_id,
        parametres=parametres,
        cle_maitresse=cle_maitresse,
    )


@routeur.get("/{tache_id}/capture-controle")
def telecharger_capture_controle(
    tache_id: uuid.UUID,
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> Response:
    type_mime, octets = service_taches.lire_capture_controle(
        ctx.db,
        tache_id=tache_id,
        parametres=parametres,
        cle_maitresse=cle_maitresse,
    )
    return Response(
        content=octets,
        media_type=type_mime,
        headers={
            "Content-Disposition": f'inline; filename="capture-controle-{tache_id}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@routeur.post("/{tache_id}/soumettre-validation", response_model=TacheSortie)
def soumettre_validation(
    tache_id: uuid.UUID,
    donnees: SoumissionValidationEntree,
    ctx: ContexteExecutionTache = Depends(obtenir_contexte_execution_tache),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> TacheSortie:
    return service_taches.soumettre_pour_validation_humaine(
        ctx.db,
        tache_id=tache_id,
        donnees=donnees,
        acteur_id=ctx.acteur_id,
        agent_local_id=ctx.agent_local_id,
        cle_maitresse=cle_maitresse,
    )


# ---------------------------------------------------------------------------
# Décisions strictement humaines (Règle 1 : jamais d'agent local ici)
# ---------------------------------------------------------------------------

@routeur.post("/{tache_id}/valider", response_model=TacheSortie)
def valider_par_humain(
    tache_id: uuid.UUID,
    donnees: ValidationHumaineEntree,
    ctx: ContexteAuth = ExigerEcritureHumaine,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> TacheSortie:
    return service_taches.valider_par_humain(
        ctx.db,
        tache_id=tache_id,
        donnees=donnees,
        decideur_id=ctx.utilisateur.id,
        cle_maitresse=cle_maitresse,
    )


@routeur.post("/{tache_id}/rejeter-validation", response_model=TacheSortie)
def rejeter_validation_humaine(
    tache_id: uuid.UUID,
    donnees: RejetValidationEntree,
    ctx: ContexteAuth = ExigerEcritureHumaine,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> TacheSortie:
    return service_taches.rejeter_validation_humaine(
        ctx.db,
        tache_id=tache_id,
        donnees=donnees,
        decideur_id=ctx.utilisateur.id,
        cle_maitresse=cle_maitresse,
    )


@routeur.post("/{tache_id}/annuler", response_model=TacheSortie)
def annuler(
    tache_id: uuid.UUID,
    ctx: ContexteAuth = ExigerEcritureHumaine,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> TacheSortie:
    return service_taches.annuler_tache(
        ctx.db,
        tache_id=tache_id,
        acteur_id=ctx.utilisateur.id,
        cle_maitresse=cle_maitresse,
    )
