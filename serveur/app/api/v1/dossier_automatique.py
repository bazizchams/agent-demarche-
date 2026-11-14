"""Routes du dossier automatique (phase P7) : lancer l'enchaînement et lire l'état d'avancement.

Sécurité : session et CSRF sur le lancement, rôle administrateur ou employé ; lecture seule = consultation de
l'état. Aucune validation humaine n'est franchie ici (règle 1) et aucun vœu n'est créé ni soumis.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request

from app.api.dependances import ContexteAuth, exiger_roles, obtenir_cle_maitresse, obtenir_contexte_auth
from app.api.v1.extractions import obtenir_lecteur_document, obtenir_lecteur_vision
from app.core.config import Environnement, Parametres, obtenir_parametres
from app.modeles.utilisateur import Role
from app.schemas.dossier_automatique import EtatDossierAutomatiqueSortie, LancerDossierAutomatiqueEntree
from app.services import dossier_automatique as service
from app.services.jetons_courriel import LimiteurDemandes
from app.services.lecture_documents import LecteurDocument
from app.services.lecture_vision import LecteurVision
from app.services.llm import ClientLLM, obtenir_client_llm_optionnel

routeur = APIRouter(prefix="/candidats/{candidat_id}/dossier-automatique", tags=["dossier automatique"])

ExigerEcriture = Depends(exiger_roles(Role.ADMINISTRATEUR, Role.EMPLOYE))


def _limiter(requete: Request, ctx: ContexteAuth, parametres: Parametres) -> None:
    """La lecture des documents est coûteuse : débit limité par utilisateur (inactif en test sauf demande)."""
    if parametres.environnement is Environnement.TEST and not parametres.extraction_limite_active_en_test:
        return
    etat = requete.app.state
    if not hasattr(etat, "limiteur_dossier_automatique"):
        etat.limiteur_dossier_automatique = LimiteurDemandes()
    etat.limiteur_dossier_automatique.verifier_et_compter(
        f"auto:{ctx.utilisateur.id}", parametres.extraction_lot_max_par_heure_par_utilisateur
    )


@routeur.post("/lancer", response_model=EtatDossierAutomatiqueSortie)
def lancer(
    candidat_id: uuid.UUID,
    requete: Request,
    donnees: LancerDossierAutomatiqueEntree | None = None,
    ctx: ContexteAuth = ExigerEcriture,
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
    lecteur: LecteurDocument = Depends(obtenir_lecteur_document),
    vision: LecteurVision | None = Depends(obtenir_lecteur_vision),
    client: ClientLLM | None = Depends(obtenir_client_llm_optionnel),
) -> EtatDossierAutomatiqueSortie:
    _limiter(requete, ctx, parametres)
    return service.lancer(
        ctx.db, client, candidat_id=candidat_id, acteur_id=ctx.utilisateur.id, cle_maitresse=cle_maitresse,
        parametres=parametres, lecteur=lecteur, vision=vision,
        code_demarche=donnees.code_demarche if donnees else None,
    )


@routeur.get("/etat", response_model=EtatDossierAutomatiqueSortie)
def etat(
    candidat_id: uuid.UUID,
    code_demarche: str | None = Query(default=None, min_length=1, max_length=60),
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> EtatDossierAutomatiqueSortie:
    return service.calculer_etat(
        ctx.db, candidat_id=candidat_id, cle_maitresse=cle_maitresse, parametres=parametres,
        code_demarche=code_demarche,
    )
