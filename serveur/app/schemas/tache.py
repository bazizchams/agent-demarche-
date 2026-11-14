"""Schémas Pydantic v2 de la Phase 3 :
- Agents locaux (`AgentLocalCreation`, `AgentLocalSortie`, `AgentLocalEnroleSortie`)
- Tâches longues et machine à états (`TacheCreation`, `TacheSortie`, `EtapeTacheSortie`)
- Verrous exclusifs par dossier (`VerrouDossierSortie`)
- Centre de validation humaine (`SoumissionValidationEntree`, `ValidationHumaineEntree`,
  `RejetValidationEntree`, `DecisionValidationSortie`, `SyntheseCentreValidationSortie`)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.modeles.tache import (
    MotifSuspensionTache,
    StatutEtapeTache,
    StatutTache,
    TypeDecisionValidation,
)
from app.schemas.candidat import CandidatSortie
from app.schemas.commun import SchemaEntree, SchemaSortie
from app.schemas.document import DocumentSortie


# ---------------------------------------------------------------------------
# Agents locaux (poste de travail du bureau exécutant Playwright)
# ---------------------------------------------------------------------------

class AgentLocalCreation(SchemaEntree):
    nom_machine: str = Field(min_length=2, max_length=120)


class AgentLocalSortie(SchemaSortie):
    id: uuid.UUID
    nom_machine: str
    actif: bool
    cree_par_id: uuid.UUID | None
    derniere_activite_le: datetime | None
    # Vrai si l'agent a donné signe de vie récemment (sondage ou battement de cœur).
    en_ligne: bool = False
    cree_le: datetime


class AgentLocalIdentiteSortie(SchemaSortie):
    """Identité de l'agent appelant (jeton X-Agent-Token) : sert à nommer le profil navigateur du bureau."""

    agent_id: uuid.UUID
    bureau_id: uuid.UUID
    nom_machine: str


class AgentLocalEnroleSortie(SchemaSortie):
    agent: AgentLocalSortie
    jeton_secret: str


# ---------------------------------------------------------------------------
# Étapes, verrous et décisions de validation humaine
# ---------------------------------------------------------------------------

class EtapeTacheSortie(SchemaSortie):
    id: uuid.UUID
    ordre: int
    code_etape: str
    libelle: str
    statut: StatutEtapeTache
    cle_idempotence: str | None
    detail_execution: str | None
    message_erreur: str | None
    nb_tentatives: int
    commencee_le: datetime | None
    terminee_le: datetime | None


class VerrouDossierSortie(SchemaSortie):
    id: uuid.UUID
    candidat_id: uuid.UUID
    tache_id: uuid.UUID
    detenteur: str
    acquis_le: datetime
    expire_le: datetime


class DecisionValidationSortie(SchemaSortie):
    id: uuid.UUID
    tache_id: uuid.UUID
    candidat_id: uuid.UUID
    decideur_id: uuid.UUID
    decision: TypeDecisionValidation
    confirmation_explicite: bool
    commentaire: str | None
    reinitialiser_depuis_etape: str | None
    cree_le: datetime


# ---------------------------------------------------------------------------
# Tâches dossiers (machine à états)
# ---------------------------------------------------------------------------

class TacheCreation(SchemaEntree):
    candidat_id: uuid.UUID
    code_demarche: str = Field(min_length=1, max_length=60)
    # Défaut : pré-remplissage par étapes YAML. Sinon une action « Ouvrir sur mon PC ».
    action: str = Field(default="preremplissage", min_length=1, max_length=40)


class DemarrerTacheEntree(SchemaEntree):
    detenteur: str | None = Field(default=None, min_length=1, max_length=120)


class TerminerEtapeEntree(SchemaEntree):
    cle_idempotence: str = Field(min_length=1, max_length=120)
    detail_execution: str | None = Field(default=None, max_length=2000)


class SuspendreTacheEntree(SchemaEntree):
    motif: MotifSuspensionTache
    message_alerte: str = Field(min_length=3, max_length=500)
    code_etape: str | None = Field(default=None, min_length=1, max_length=80)
    champs_manquants: list[str] = Field(default_factory=list)
    pieces_manquantes: list[str] = Field(default_factory=list)


class SignalerErreurTacheEntree(SchemaEntree):
    message_erreur: str = Field(min_length=3, max_length=500)
    code_etape: str | None = Field(default=None, min_length=1, max_length=80)


class SoumissionValidationEntree(SchemaEntree):
    recapitulatif_remplissage: dict[str, Any] = Field(default_factory=dict)
    message_alerte: str | None = Field(
        default="Pré-remplissage terminé et arrêté avant soumission finale : en attente de validation humaine.",
        max_length=500,
    )


class ValidationHumaineEntree(SchemaEntree):
    confirmation_humaine_explicite: bool
    commentaire: str | None = Field(default=None, max_length=1000)


class RejetValidationEntree(SchemaEntree):
    commentaire: str = Field(min_length=3, max_length=1000)
    reinitialiser_depuis_etape: str | None = Field(default=None, min_length=1, max_length=80)


class TacheSortie(SchemaSortie):
    id: uuid.UUID
    candidat_id: uuid.UUID
    code_demarche: str
    action: str = "preremplissage"
    statut: StatutTache
    motif_suspension: MotifSuspensionTache | None
    message_alerte: str | None
    champs_manquants: list[str]
    pieces_manquantes: list[str]
    recapitulatif_remplissage: dict[str, Any] | None
    capture_controle_disponible: bool
    type_mime_capture_controle: str | None
    prochaine_etape_a_executer: str | None
    verrou_actif: VerrouDossierSortie | None
    creee_par_id: uuid.UUID | None
    agent_local_id: uuid.UUID | None
    demarree_le: datetime | None
    suspendue_le: datetime | None
    soumise_validation_le: datetime | None
    terminee_le: datetime | None
    cree_le: datetime
    modifie_le: datetime
    etapes: list[EtapeTacheSortie]
    decisions_validation: list[DecisionValidationSortie]


class SyntheseCentreValidationSortie(SchemaSortie):
    taches_a_valider: list[TacheSortie]
    taches_suspendues: list[TacheSortie]
    total_a_valider: int
    total_suspendues: int


class ContexteDossierExecutionSortie(SchemaSortie):
    """Données déchiffrées transmises à l'Agent Local uniquement pendant qu'il détient
    une tâche à l'état `en_cours`."""

    tache: TacheSortie
    candidat: CandidatSortie
    documents: list[DocumentSortie]


class ReservationTacheSortie(SchemaSortie):
    """Réponse de la réservation atomique : `tache` vaut `None` quand rien n'attend cet agent."""

    tache: TacheSortie | None = None


class VoeuAAjouterSortie(SchemaSortie):
    """Un vœu VALIDÉ servi à l'agent (jamais un brouillon). Ne contient aucun identifiant de portail."""

    voeu_id: uuid.UUID
    rang: int
    intitule: str
    etablissement: str
    niveau: str
    voie: str
    motivation: str


class VoeuxAAjouterSortie(SchemaSortie):
    tache_id: uuid.UUID
    voeux: list[VoeuAAjouterSortie]
