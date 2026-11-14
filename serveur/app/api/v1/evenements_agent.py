"""Routes de la discussion de l'agent en direct (événements, consignes, commandes, flux SSE).

- Agent (jeton `X-Agent-Token`, détenteur de la tâche) : `POST /taches/{id}/evenements`,
  `GET /taches/{id}/messages-en-attente`.
- Humain (CSRF, rôle administrateur/employé pour écrire ; lecture seule autorisée en lecture) :
  `GET /taches/{id}/evenements?depuis=`, flux `GET /taches/{id}/evenements/flux` (SSE, repli : interrogation),
  `POST /taches/{id}/messages`, `POST /taches/{id}/pause|reprise|arret|premier-plan`.
Une consigne ne lève jamais les règles 1/2/3/6 (voir `services/consignes_agent.py`).
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import StreamingResponse

from app.api.dependances import (
    ContexteAgentLocal,
    ContexteAuth,
    exiger_roles,
    obtenir_agent_local_requis,
    obtenir_cle_maitresse,
    obtenir_contexte_auth,
)
from app.db.tenant import definir_tenant, tenant_courant
from app.modeles.utilisateur import Role
from app.schemas.evenement_agent import (
    CommandeSortie,
    EvenementEntree,
    EvenementSortie,
    ListeEvenementsSortie,
    MessageEntree,
    MessageSortie,
    MessagesEnAttenteSortie,
)
from app.services import evenements_agent as service

routeur = APIRouter(prefix="/taches", tags=["discussion de l'agent"])

ExigerEcritureHumaine = Depends(exiger_roles(Role.ADMINISTRATEUR, Role.EMPLOYE))
DUREE_FLUX_DEFAUT_S = 25.0
DUREE_FLUX_MAX_S = 55.0
INTERVALLE_FLUX_S = 1.0


@routeur.post("/{tache_id}/evenements", response_model=EvenementSortie, status_code=status.HTTP_201_CREATED)
def publier_evenement(
    tache_id: uuid.UUID,
    donnees: EvenementEntree,
    ctx: ContexteAgentLocal = Depends(obtenir_agent_local_requis),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> EvenementSortie:
    return service.enregistrer_evenement_agent(
        ctx.db, tache_id=tache_id, agent_id=ctx.agent_local.id, donnees=donnees, cle=cle_maitresse
    )


@routeur.get("/{tache_id}/messages-en-attente", response_model=MessagesEnAttenteSortie)
def messages_en_attente(
    tache_id: uuid.UUID,
    ctx: ContexteAgentLocal = Depends(obtenir_agent_local_requis),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> MessagesEnAttenteSortie:
    return service.messages_en_attente(
        ctx.db, tache_id=tache_id, agent_id=ctx.agent_local.id, cle=cle_maitresse
    )


@routeur.get("/{tache_id}/evenements", response_model=ListeEvenementsSortie)
def lister_evenements(
    tache_id: uuid.UUID,
    depuis: int = Query(default=0, ge=0),
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> ListeEvenementsSortie:
    return service.lister_evenements(ctx.db, tache_id=tache_id, depuis=depuis, cle=cle_maitresse)


def _ligne_sse(evenement: str, donnees: object, identifiant: int | None = None) -> str:
    entete = f"id: {identifiant}\n" if identifiant is not None else ""
    return f"{entete}event: {evenement}\ndata: {json.dumps(donnees, ensure_ascii=False, default=str)}\n\n"


def _generer_flux(
    requete: Request, tenant_id: uuid.UUID, tache_id: uuid.UUID, depuis: int, cle: bytes, duree_s: float
) -> Iterator[str]:
    """Flux SSE : session propre (celle de la requête est fermée dès le retour de la route). Il se termine
    après `duree_s` : `EventSource` se reconnecte seul avec `Last-Event-ID`."""
    session = requete.app.state.fabrique_sessions()
    definir_tenant(session, tenant_id)
    try:
        debut = time.monotonic()
        dernier_etat = ""
        yield "retry: 3000\n\n"
        while True:
            session.rollback()  # nouvelle lecture (SQLite : instantané frais)
            liste = service.lister_evenements(session, tache_id=tache_id, depuis=depuis, cle=cle)
            for e in liste.elements:
                yield _ligne_sse("evenement", json.loads(e.model_dump_json()), e.seq)
                depuis = e.seq
            if liste.etat != dernier_etat:
                dernier_etat = liste.etat
                yield _ligne_sse("etat", {"etat": liste.etat})
            if time.monotonic() - debut >= duree_s:
                yield _ligne_sse("fin", {"dernier": depuis})
                return
            time.sleep(INTERVALLE_FLUX_S)
    finally:
        session.close()


@routeur.get("/{tache_id}/evenements/flux")
def flux_evenements(
    tache_id: uuid.UUID,
    requete: Request,
    depuis: int = Query(default=0, ge=0),
    duree_max_s: float = Query(default=DUREE_FLUX_DEFAUT_S, gt=0, le=DUREE_FLUX_MAX_S),
    dernier_id: str | None = Header(default=None, alias="Last-Event-ID"),
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> StreamingResponse:
    service.verifier_tache_visible(ctx.db, tache_id)  # 404 si autre bureau
    if dernier_id and dernier_id.isdigit():
        depuis = max(depuis, int(dernier_id))
    tenant_id = tenant_courant(ctx.db)
    assert tenant_id is not None
    return StreamingResponse(
        _generer_flux(requete, tenant_id, tache_id, depuis, cle_maitresse, duree_max_s),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@routeur.post("/{tache_id}/messages", response_model=MessageSortie, status_code=status.HTTP_201_CREATED)
def envoyer_message(
    tache_id: uuid.UUID,
    donnees: MessageEntree,
    ctx: ContexteAuth = ExigerEcritureHumaine,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> MessageSortie:
    return service.poster_message_humain(
        ctx.db, tache_id=tache_id, acteur_id=ctx.utilisateur.id, texte=donnees.texte, cle=cle_maitresse
    )


def _commande(code: str, tache_id: uuid.UUID, ctx: ContexteAuth, cle: bytes) -> CommandeSortie:
    return service.poster_commande_humaine(
        ctx.db, tache_id=tache_id, acteur_id=ctx.utilisateur.id, code=code, cle=cle
    )


@routeur.post("/{tache_id}/pause", response_model=CommandeSortie)
def pause(
    tache_id: uuid.UUID, ctx: ContexteAuth = ExigerEcritureHumaine, cle: bytes = Depends(obtenir_cle_maitresse)
) -> CommandeSortie:
    return _commande("pause", tache_id, ctx, cle)


@routeur.post("/{tache_id}/reprise", response_model=CommandeSortie)
def reprise(
    tache_id: uuid.UUID, ctx: ContexteAuth = ExigerEcritureHumaine, cle: bytes = Depends(obtenir_cle_maitresse)
) -> CommandeSortie:
    return _commande("reprise", tache_id, ctx, cle)


@routeur.post("/{tache_id}/arret", response_model=CommandeSortie)
def arret(
    tache_id: uuid.UUID, ctx: ContexteAuth = ExigerEcritureHumaine, cle: bytes = Depends(obtenir_cle_maitresse)
) -> CommandeSortie:
    return _commande("arret", tache_id, ctx, cle)


@routeur.post("/{tache_id}/premier-plan", response_model=CommandeSortie)
def premier_plan(
    tache_id: uuid.UUID, ctx: ContexteAuth = ExigerEcritureHumaine, cle: bytes = Depends(obtenir_cle_maitresse)
) -> CommandeSortie:
    """« Voir la fenêtre sur mon PC » : demande à l'agent d'amener sa fenêtre au premier plan."""
    return _commande("premier_plan", tache_id, ctx, cle)
