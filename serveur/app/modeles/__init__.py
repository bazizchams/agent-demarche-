"""Modèles ORM. Importer ce paquet enregistre toutes les tables dans Base.metadata."""

from app.modeles.abonnement import (
    AbonnementBureau,
    ForfaitAbonnement,
    PreuveConsentementCandidat,
)
from app.modeles.agent_local import AgentLocal
from app.modeles.bureau import Bureau
from app.modeles.candidat import Candidat, SexeCandidat, StatutCandidat
from app.modeles.discussion_dossier import (
    AuteurMessageDossier,
    MessageDiscussionDossier,
)
from app.modeles.document import DocumentCandidat
from app.modeles.journal_audit import EntreeAudit, ResultatAudit
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

__all__ = [
    "AbonnementBureau",
    "AgentLocal",
    "AuteurMessageDossier",
    "Bureau",
    "Candidat",
    "DecisionValidationHumaine",
    "DocumentCandidat",
    "EntreeAudit",
    "EtapeTache",
    "ForfaitAbonnement",
    "MessageDiscussionDossier",
    "MotifSuspensionTache",
    "PreuveConsentementCandidat",
    "ResultatAudit",
    "Role",
    "SessionUtilisateur",
    "SexeCandidat",
    "StatutCandidat",
    "StatutEtapeTache",
    "StatutTache",
    "TacheDossier",
    "TypeDecisionValidation",
    "Utilisateur",
    "VerrouDossier",
]
