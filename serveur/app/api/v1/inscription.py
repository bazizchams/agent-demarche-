"""Inscription publique d'une agence (sans session), catalogue et CGU consultables sans connexion."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, status
from pydantic import Field
from sqlalchemy.orm import Session

from app.api.dependances import obtenir_db
from app.core.config import Parametres, obtenir_parametres
from app.core.erreurs import AccesRefuse
from app.modeles.abonnement import ForfaitAbonnement
from app.schemas.abonnement_conformite import ForfaitCatalogueSortie, TexteCGUSortie
from app.schemas.auth import EmailNormalise, MotDePasse
from app.schemas.commun import SchemaEntree, SchemaSortie
from app.services import abonnements as service_abonnements
from app.services import inscription as service

routeur = APIRouter(prefix="/inscription", tags=["inscription"])

MESSAGE_SUCCES = (
    "Votre bureau a été créé avec une période d'essai de 30 jours. "
    "Connectez-vous avec votre adresse e-mail et votre mot de passe."
)


class InscriptionEntree(SchemaEntree):
    nom_bureau: str = Field(min_length=2, max_length=120)
    email_admin: EmailNormalise
    nom_admin: str = Field(min_length=1, max_length=120)
    mot_de_passe: MotDePasse
    accepte_cgu: bool
    forfait: ForfaitAbonnement = ForfaitAbonnement.STARTER
    # Champ piège anti-robot : doit rester vide.
    site_web: str | None = Field(default=None, max_length=500)


class InscriptionSortie(SchemaSortie):
    bureau_id: uuid.UUID
    slug: str
    message: str


def _limiteur(requete: Request) -> service.LimiteurInscriptions:
    etat = requete.app.state
    if not hasattr(etat, "limiteur_inscriptions"):
        etat.limiteur_inscriptions = service.LimiteurInscriptions()
    return etat.limiteur_inscriptions


@routeur.get("/forfaits", response_model=list[ForfaitCatalogueSortie])
def forfaits_publics() -> list[ForfaitCatalogueSortie]:
    return service_abonnements.lister_catalogue_forfaits()


@routeur.get("/cgu", response_model=TexteCGUSortie)
def cgu_publiques(
    parametres: Parametres = Depends(obtenir_parametres),
) -> TexteCGUSortie:
    return service_abonnements.obtenir_texte_cgu(parametres)


@routeur.post(
    "", response_model=InscriptionSortie, status_code=status.HTTP_201_CREATED
)
def inscrire(
    donnees: InscriptionEntree,
    requete: Request,
    db: Session = Depends(obtenir_db),
    parametres: Parametres = Depends(obtenir_parametres),
) -> InscriptionSortie:
    if not parametres.inscriptions_ouvertes:
        raise AccesRefuse("Les inscriptions sont actuellement fermées.")

    ip = requete.client.host if requete.client else "inconnue"
    service.verifier_limite(_limiteur(requete), ip, parametres)

    if donnees.site_web and donnees.site_web.strip():
        # Robot probable : réponse factice, rien n'est créé.
        return InscriptionSortie(
            bureau_id=service.nouvel_identifiant_factice(),
            slug="bureau",
            message=MESSAGE_SUCCES,
        )

    bureau = service.inscrire_bureau(
        db,
        nom_bureau=donnees.nom_bureau,
        email_admin=donnees.email_admin,
        nom_admin=donnees.nom_admin,
        mot_de_passe=donnees.mot_de_passe,
        accepte_cgu=donnees.accepte_cgu,
        forfait=donnees.forfait,
        parametres=parametres,
    )
    return InscriptionSortie(bureau_id=bureau.id, slug=bureau.slug, message=MESSAGE_SUCCES)
