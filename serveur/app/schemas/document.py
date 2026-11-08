"""Schémas Pydantic v2 des documents et du contrôle des pièces requises par démarche."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from app.schemas.commun import SchemaSortie


class DocumentSortie(SchemaSortie):
    id: uuid.UUID
    candidat_id: uuid.UUID
    type_piece: str
    nom_fichier_origine: str
    type_mime: str
    taille_octets: int
    empreinte_contenu: str
    date_expiration: date | None
    ajoute_par_id: uuid.UUID | None
    cree_le: datetime


class StatutPieceRequise(str, enum.Enum):
    VALIDE = "valide"
    MANQUANTE = "manquante"
    EXPIREE = "expiree"
    VALIDITE_INSUFFISANTE = "validite_insuffisante"
    EXPIRATION_NON_RENSEIGNEE = "expiration_non_renseignee"


class VerificationPieceSortie(SchemaSortie):
    type_piece: str
    libelle: str
    obligatoire: bool
    statut: StatutPieceRequise
    document_id: uuid.UUID | None = None
    date_expiration: date | None = None
    detail: str | None = None


class EtatCompletudeDemarcheSortie(SchemaSortie):
    code_demarche: str
    libelle_demarche: str
    pret_pour_prerequis: bool
    champs_candidat_manquants: list[str]
    pieces_manquantes_ou_invalides: list[str]
    pieces: list[VerificationPieceSortie]


class DemarcheResumeSortie(SchemaSortie):
    code: str
    libelle: str
    description: str
    seuil_fonds_recommande_eur: int | None = None
    champs_candidat_requis: list[str]
    types_pieces_connus: list[str]


class PointVeilleReglementaireSortie(SchemaSortie):
    titre: str
    resume: str
    reference: str


class CritereEvaluationSortie(SchemaSortie):
    code: str
    libelle: str
    points_obtenus: int
    points_max: int
    commentaire: str


class EvaluationDossierSortie(SchemaSortie):
    candidat_id: uuid.UUID
    code_demarche: str
    libelle_demarche: str
    pourcentage_acceptation_estime: int
    niveau_solidite: str
    pret_pour_soumission_humaine: bool
    meilleure_action_recommandee: str
    points_forts: list[str]
    risques_et_blocages: list[str]
    actions_prioritaires: list[str]
    criteres: list[CritereEvaluationSortie]
    veille_reglementaire: list[PointVeilleReglementaireSortie]
    avertissement: str


class QuestionDiscussionEntree(
    __import__("app.schemas.commun", fromlist=["SchemaEntree"]).SchemaEntree
):
    code_demarche: str = __import__("pydantic").Field(min_length=1, max_length=60)
    message: str = __import__("pydantic").Field(min_length=2, max_length=2000)


class MessageDiscussionSortie(SchemaSortie):
    id: uuid.UUID
    candidat_id: uuid.UUID
    code_demarche: str
    auteur: str
    utilisateur_id: uuid.UUID | None
    contenu: str
    score_solidite_pourcent: int | None
    cree_le: datetime


class EchangeDiscussionSortie(SchemaSortie):
    question: MessageDiscussionSortie
    reponse: MessageDiscussionSortie
    evaluation: EvaluationDossierSortie
