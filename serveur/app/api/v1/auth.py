"""Routes d'authentification : connexion, déconnexion, profil courant, mot de passe."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.dependances import (
    ContexteAuth,
    obtenir_contexte_auth_brut,
    obtenir_db,
)
from app.core.config import Parametres, obtenir_parametres
from app.schemas.auth import (
    ChangementMotDePasseEntree,
    ConnexionEntree,
    ConnexionSortie,
    UtilisateurSortie,
)
from app.services import auth as service_auth

routeur = APIRouter(prefix="/auth", tags=["authentification"])


@routeur.post("/connexion", response_model=ConnexionSortie)
def connexion(
    donnees: ConnexionEntree,
    reponse: Response,
    db: Session = Depends(obtenir_db),
    parametres: Parametres = Depends(obtenir_parametres),
) -> ConnexionSortie:
    creee = service_auth.authentifier_et_creer_session(
        db,
        email=donnees.email,
        mot_de_passe=donnees.mot_de_passe,
        parametres=parametres,
    )
    reponse.set_cookie(
        key=parametres.nom_cookie_session,
        value=creee.jeton_clair,
        max_age=parametres.duree_session_minutes * 60,
        httponly=True,
        secure=parametres.cookie_securise,
        samesite="lax",
        path="/",
    )
    return ConnexionSortie(
        utilisateur=UtilisateurSortie.model_validate(creee.utilisateur),
        jeton_csrf=creee.session.jeton_csrf,
        expire_le=creee.session.expire_le,
    )


@routeur.post("/deconnexion", status_code=status.HTTP_204_NO_CONTENT)
def deconnexion(
    reponse: Response,
    ctx: ContexteAuth = Depends(obtenir_contexte_auth_brut),
    parametres: Parametres = Depends(obtenir_parametres),
) -> Response:
    service_auth.revoquer_session(
        ctx.db, session_obj=ctx.session, acteur_id=ctx.utilisateur.id
    )
    reponse.delete_cookie(key=parametres.nom_cookie_session, path="/")
    reponse.status_code = status.HTTP_204_NO_CONTENT
    return reponse


@routeur.get("/moi", response_model=ConnexionSortie)
def profil_courant(
    ctx: ContexteAuth = Depends(obtenir_contexte_auth_brut),
) -> ConnexionSortie:
    return ConnexionSortie(
        utilisateur=UtilisateurSortie.model_validate(ctx.utilisateur),
        jeton_csrf=ctx.session.jeton_csrf,
        expire_le=ctx.session.expire_le,
    )


@routeur.post("/mot-de-passe", status_code=status.HTTP_204_NO_CONTENT)
def changer_mot_de_passe(
    donnees: ChangementMotDePasseEntree,
    ctx: ContexteAuth = Depends(obtenir_contexte_auth_brut),
    parametres: Parametres = Depends(obtenir_parametres),
) -> Response:
    service_auth.changer_mot_de_passe(
        ctx.db,
        utilisateur=ctx.utilisateur,
        session_courante=ctx.session,
        mot_de_passe_actuel=donnees.mot_de_passe_actuel,
        nouveau_mot_de_passe=donnees.nouveau_mot_de_passe,
        parametres=parametres,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
