"""Schémas d'authentification et d'utilisateurs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, EmailStr, Field

from app.core.securite import LONGUEUR_MAX_MOT_DE_PASSE
from app.modeles.utilisateur import Role
from app.schemas.commun import SchemaEntree, SchemaSortie


def normaliser_email(valeur: str) -> str:
    return valeur.strip().lower()


EmailNormalise = Annotated[EmailStr, AfterValidator(normaliser_email)]
MotDePasse = Annotated[str, Field(min_length=1, max_length=LONGUEUR_MAX_MOT_DE_PASSE)]


class ConnexionEntree(SchemaEntree):
    email: EmailNormalise
    mot_de_passe: MotDePasse


class UtilisateurSortie(SchemaSortie):
    id: uuid.UUID
    email: str
    nom_affiche: str
    role: Role
    actif: bool
    doit_changer_mot_de_passe: bool
    cree_le: datetime
    derniere_connexion_le: datetime | None


class ConnexionSortie(SchemaSortie):
    utilisateur: UtilisateurSortie
    jeton_csrf: str
    expire_le: datetime


class ChangementMotDePasseEntree(SchemaEntree):
    mot_de_passe_actuel: MotDePasse
    nouveau_mot_de_passe: MotDePasse


class UtilisateurCreation(SchemaEntree):
    email: EmailNormalise
    nom_affiche: str = Field(min_length=1, max_length=120)
    role: Role
    mot_de_passe_temporaire: MotDePasse


class UtilisateurModification(SchemaEntree):
    nom_affiche: str | None = Field(default=None, min_length=1, max_length=120)
    role: Role | None = None
    actif: bool | None = None


class ReinitialisationMotDePasseEntree(SchemaEntree):
    mot_de_passe_temporaire: MotDePasse
