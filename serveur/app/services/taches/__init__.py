"""Service de gestion des tâches longues, de la machine à états, des verrous exclusifs
par dossier et du Centre de validation humaine (Phase 3).

Façade du paquet : ré-exporte les mêmes noms que l'ancien module `taches.py`
(publics et privés importés ailleurs).

Règles non négociables appliquées par construction :
- Règle 1 (Option A) : aucune tâche ne peut atteindre l'état `terminee` sans passer par
  `a_valider` puis recevoir une décision humaine explicite (`confirmation_humaine_explicite=True`)
  d'un utilisateur authentifié du bureau. Un jeton d'agent local ne peut jamais valider une tâche.
- Règle 4 : si des champs candidats ou des pièces obligatoires manquent ou sont expirés,
  la tâche passe automatiquement à l'état `suspendue` avec la liste exacte des manques
  (aucune valeur par défaut n'est jamais inventée).
- Règle 5 : aucune donnée personnelle dans les journaux applicatifs ni dans `journal_audit`.
  Le récapitulatif de pré-remplissage, les détails d'étape, la capture de contrôle et les
  commentaires de validation sont chiffrés au repos en AES-256-GCM avec la clé du bureau.
- Règle 7 : les étapes de chaque démarche proviennent des fichiers YAML `config/demarches/*.yaml`.

Modules : `etat` (machine à états, gardes), `verrous`, `serialisation`, `prerequis`,
`creation` (création/consultation), `execution` (démarrage, étapes, annulation),
`interruptions` (suspension, erreur, reprise), `acces_agent` (capture, contexte, pièces),
`validation` (validation humaine).
"""

from app.services.taches.acces_agent import (
    deposer_capture_controle,
    lire_capture_controle,
    lire_document_pour_tache_en_cours,
    obtenir_contexte_dossier_execution,
)
from app.services.taches.creation import creer_tache, lister_taches, obtenir_tache
from app.services.taches.etat import (
    STATUTS_TACHE_OUVERTE,
    TRANSITIONS_AUTORISEES,
    _exiger_action_avec_pieces,
    _exiger_detenteur_agent,
    _exiger_tenant,
    _obtenir_tache_orm,
    _prochaine_etape,
    _verifier_transition,
)
from app.services.taches.execution import (
    annuler_tache,
    demarrer_tache,
    renouveler_verrou_tache,
    terminer_etape_tache,
)
from app.services.taches.interruptions import (
    reprendre_tache,
    signaler_erreur_tache,
    suspendre_tache,
)
from app.services.taches.serialisation import _serialiser_tache
from app.services.taches.validation import (
    obtenir_synthese_centre_validation,
    rejeter_validation_humaine,
    soumettre_pour_validation_humaine,
    valider_par_humain,
)
from app.services.taches.verrous import (
    _acquerir_ou_rafraichir_verrou,
    _liberer_verrou_dossier,
    _obtenir_verrou_actif,
)

__all__ = [
    "STATUTS_TACHE_OUVERTE",
    "TRANSITIONS_AUTORISEES",
    "_acquerir_ou_rafraichir_verrou",
    "_exiger_action_avec_pieces",
    "_exiger_detenteur_agent",
    "_exiger_tenant",
    "_liberer_verrou_dossier",
    "_obtenir_tache_orm",
    "_obtenir_verrou_actif",
    "_prochaine_etape",
    "_serialiser_tache",
    "_verifier_transition",
    "annuler_tache",
    "creer_tache",
    "demarrer_tache",
    "deposer_capture_controle",
    "lire_capture_controle",
    "lire_document_pour_tache_en_cours",
    "lister_taches",
    "obtenir_contexte_dossier_execution",
    "obtenir_synthese_centre_validation",
    "obtenir_tache",
    "rejeter_validation_humaine",
    "renouveler_verrou_tache",
    "reprendre_tache",
    "signaler_erreur_tache",
    "soumettre_pour_validation_humaine",
    "suspendre_tache",
    "terminer_etape_tache",
    "valider_par_humain",
]
