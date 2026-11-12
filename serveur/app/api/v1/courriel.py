"""Routes liées aux courriels : mot de passe oublié, réinitialisation, vérification d'adresse.

Les routes « demande » répondent toujours de la même façon (202, même texte) que le compte
existe ou non, et l'envoi se fait après la réponse (le temps de réponse ne révèle rien).
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status
from pydantic import Field
from sqlalchemy.orm import Session

from app.api.dependances import ContexteAuth, obtenir_contexte_auth_brut, obtenir_db
from app.core.config import Parametres, obtenir_parametres
from app.schemas.auth import EmailNormalise, MotDePasse
from app.schemas.commun import SchemaEntree, SchemaSortie
from app.services import courriels
from app.services import jetons_courriel as service

routeur = APIRouter(prefix="/auth", tags=["courriels"])

MESSAGE_DEMANDE_ACCEPTEE = (
    "Si un compte correspond à cette adresse, un courriel de réinitialisation vient d'être envoyé."
)
JetonCourrielTexte = Field(min_length=20, max_length=200)


class MotDePasseOublieEntree(SchemaEntree):
    email: EmailNormalise


class ReinitialisationEntree(SchemaEntree):
    jeton: str = JetonCourrielTexte
    nouveau_mot_de_passe: MotDePasse


class ConfirmationAdresseEntree(SchemaEntree):
    jeton: str = JetonCourrielTexte


class MessageSortie(SchemaSortie):
    message: str


def _limiteur(requete: Request) -> service.LimiteurDemandes:
    etat = requete.app.state
    if not hasattr(etat, "limiteur_reinitialisation"):
        etat.limiteur_reinitialisation = service.LimiteurDemandes()
    return etat.limiteur_reinitialisation


@routeur.post(
    "/mot-de-passe-oublie", response_model=MessageSortie, status_code=status.HTTP_202_ACCEPTED
)
def mot_de_passe_oublie(
    donnees: MotDePasseOublieEntree,
    requete: Request,
    taches: BackgroundTasks,
    db: Session = Depends(obtenir_db),
    parametres: Parametres = Depends(obtenir_parametres),
) -> MessageSortie:
    ip = requete.client.host if requete.client else "inconnue"
    service.verifier_limite_ip(_limiteur(requete), ip, parametres)
    courriel = service.demander_reinitialisation(db, email=donnees.email, parametres=parametres)
    if courriel is not None:
        taches.add_task(courriels.envoyer_courriel, courriel, parametres)
    return MessageSortie(message=MESSAGE_DEMANDE_ACCEPTEE)


@routeur.post("/reinitialisation-mot-de-passe", status_code=status.HTTP_204_NO_CONTENT)
def reinitialiser(
    donnees: ReinitialisationEntree,
    requete: Request,
    db: Session = Depends(obtenir_db),
    parametres: Parametres = Depends(obtenir_parametres),
) -> Response:
    ip = requete.client.host if requete.client else "inconnue"
    service.verifier_limite_ip(_limiteur(requete), ip, parametres)
    service.reinitialiser_mot_de_passe(
        db, jeton_clair=donnees.jeton, nouveau_mot_de_passe=donnees.nouveau_mot_de_passe,
        parametres=parametres,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@routeur.post("/verification-adresse", status_code=status.HTTP_204_NO_CONTENT)
def confirmer_adresse(
    donnees: ConfirmationAdresseEntree,
    requete: Request,
    db: Session = Depends(obtenir_db),
    parametres: Parametres = Depends(obtenir_parametres),
) -> Response:
    ip = requete.client.host if requete.client else "inconnue"
    service.verifier_limite_ip(_limiteur(requete), ip, parametres)
    service.confirmer_adresse(db, jeton_clair=donnees.jeton)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@routeur.post(
    "/verification-adresse/renvoyer", response_model=MessageSortie,
    status_code=status.HTTP_202_ACCEPTED,
)
def renvoyer_verification(
    taches: BackgroundTasks,
    ctx: ContexteAuth = Depends(obtenir_contexte_auth_brut),
    parametres: Parametres = Depends(obtenir_parametres),
) -> MessageSortie:
    """Session humaine requise (cookie + CSRF). Utilisable même avant le changement du mot de
    passe temporaire."""
    courriel = service.preparer_verification_adresse(
        ctx.db, utilisateur=ctx.utilisateur, parametres=parametres
    )
    if courriel is not None:
        taches.add_task(courriels.envoyer_courriel, courriel, parametres)
    return MessageSortie(message="Si votre adresse n'est pas encore confirmée, un courriel vous a été envoyé.")
