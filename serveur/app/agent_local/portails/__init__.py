"""Modules séparés des portails officiels (Phase 5) :
- `verificateur_portail` : vérification préalable des URLs officielles, des domaines autorisés (défaut D8)
  et diagnostic en lecture seule des sélecteurs YAML présents sur la page.
- `campus_france` : module dédié Études en France / Campus France Algérie en mode
  « pré-remplissage + captures de contrôle + arrêt strict avant envoi ».
- `ircc_canada` : module dédié IRCC Canada (Permis d'études) en mode
  « pré-remplissage + captures de contrôle + arrêt strict avant signature/transmission ».
"""

from app.agent_local.portails.campus_france import ModulePortailCampusFrance
from app.agent_local.portails.ircc_canada import ModulePortailIRCCCanada
from app.agent_local.portails.verificateur_portail import (
    RapportDiagnosticPagePortail,
    ResultatVerificationURL,
    diagnostiquer_page_portail,
    verifier_url_officielle_portail,
)

__all__ = [
    "ModulePortailCampusFrance",
    "ModulePortailIRCCCanada",
    "RapportDiagnosticPagePortail",
    "ResultatVerificationURL",
    "diagnostiquer_page_portail",
    "verifier_url_officielle_portail",
]
