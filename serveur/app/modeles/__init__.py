"""Modèles ORM. Importer ce paquet enregistre toutes les tables dans Base.metadata."""

from app.modeles.abonnement import (
    AbonnementBureau,
    ForfaitAbonnement,
    PreuveConsentementCandidat,
)
from app.modeles.agent_local import AgentLocal
from app.modeles.bureau import Bureau
from app.modeles.candidat import Candidat, SexeCandidat, StatutCandidat
from app.modeles.coffre_identifiants import IdentifiantPortail
from app.modeles.validation_recapitulatif import ValidationRecapitulatif
from app.modeles.demarche_bureau import DemarcheBureau
from app.modeles.discussion_dossier import (
    AuteurMessageDossier,
    MessageDiscussionDossier,
)
from app.modeles.document import DocumentCandidat
from app.modeles.evenement_agent import EvenementAgent
from app.modeles.extraction_document import ExtractionDocument, StatutExtraction
from app.modeles.fiche_formation import FicheFormation, StatutFiche
from app.modeles.jeton_courriel import JetonCourriel, ObjetJetonCourriel
from app.modeles.journal_audit import EntreeAudit, ResultatAudit
from app.modeles.point_fort import PointFort, ProjetProfessionnel, StatutPointFort, StatutProjet
from app.modeles.rappel_echeance import RappelEcheanceEnvoye
from app.modeles.session_utilisateur import SessionUtilisateur
from app.modeles.tache import (
    DecisionValidationHumaine,
    EtapeTache,
    MotifSuspensionTache,
    StatutEtapeTache,
    StatutTache,
    TacheDossier,
    TypeDecisionValidation,
    VerrouDossier,
)
from app.modeles.utilisateur import Role, Utilisateur
from app.modeles.voeu_formation import StatutVoeu, VoeuFormation, VoieVoeu

__all__ = [
    "AbonnementBureau",
    "AgentLocal",
    "AuteurMessageDossier",
    "Bureau",
    "Candidat",
    "DecisionValidationHumaine",
    "DemarcheBureau",
    "DocumentCandidat",
    "EntreeAudit",
    "EtapeTache",
    "ExtractionDocument",
    "FicheFormation",
    "IdentifiantPortail",
    "JetonCourriel",
    "ObjetJetonCourriel",
    "ValidationRecapitulatif",
    "ForfaitAbonnement",
    "MessageDiscussionDossier",
    "MotifSuspensionTache",
    "EvenementAgent",
    "PointFort",
    "PreuveConsentementCandidat",
    "ProjetProfessionnel",
    "StatutPointFort",
    "StatutProjet",
    "RappelEcheanceEnvoye",
    "ResultatAudit",
    "Role",
    "SessionUtilisateur",
    "SexeCandidat",
    "StatutCandidat",
    "StatutFiche",
    "StatutEtapeTache",
    "StatutExtraction",
    "StatutTache",
    "TacheDossier",
    "TypeDecisionValidation",
    "Utilisateur",
    "VerrouDossier",
    "StatutVoeu",
    "VoeuFormation",
    "VoieVoeu",
]
