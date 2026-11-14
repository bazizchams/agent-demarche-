"""Schémas Pydantic des points forts vérifiables (P2) et du projet professionnel (P3).

Les valeurs (textes, extraits) ne sortent que par ces schémas, à un utilisateur authentifié du
bureau ; aucune n'est reprise dans un message d'erreur.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.modeles.point_fort import StatutPointFort, StatutProjet
from app.schemas.commun import SchemaEntree, SchemaSortie


class PointFortSortie(SchemaSortie):
    id: uuid.UUID
    candidat_id: uuid.UUID
    categorie: str
    regle: str
    texte: str
    document_id: uuid.UUID
    page: int | None
    extrait: str
    statut: StatutPointFort
    alerte: str | None
    champ_fiche: str | None
    valeur_fiche: str | None
    decide_par_id: uuid.UUID | None
    decide_le: datetime | None
    applique_le: datetime | None


class ResultatDeductionsSortie(SchemaSortie):
    points_forts: list[PointFortSortie]
    nb_crees: int
    nb_mis_a_jour: int
    nb_retires: int


class ApplicationNiveauSortie(SchemaSortie):
    champ: str
    resultat: str  # "applique" | "deja_identique"
    point_fort: PointFortSortie


class ProjetGenereEntree(SchemaEntree):
    remplacer: bool = False


class ProjetModificationEntree(SchemaEntree):
    texte: str = Field(min_length=1, max_length=6000)
    version: int = Field(ge=1)


class ProjetValidationEntree(SchemaEntree):
    version: int = Field(ge=1)


class ProjetProfessionnelSortie(SchemaSortie):
    id: uuid.UUID
    candidat_id: uuid.UUID
    texte: str
    version: int
    statut: StatutProjet
    origine: str
    elements_a_verifier: list[str]
    marqueurs_restants: bool
    validable: bool
    nb_points_forts_utilises: int
    nb_points_forts_ecartes: int
    valide_par_id: uuid.UUID | None
    valide_le: datetime | None
    cree_le: datetime
    modifie_le: datetime
