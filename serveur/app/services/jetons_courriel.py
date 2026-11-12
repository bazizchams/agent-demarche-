"""Jetons à usage unique par courriel : vérification d'adresse et mot de passe oublié.

Principes :
- jeton aléatoire de 256 bits ; seule l'empreinte SHA-256 est stockée en base ;
- usage unique garanti par une mise à jour atomique (`utilise_le IS NULL`) ;
- vérification d'adresse : 48 h ; réinitialisation du mot de passe : 1 h (paramétrable) ;
- « mot de passe oublié » : même résultat pour l'appelant que le compte existe ou non
  (aucune énumération), limite de débit par IP et par compte ;
- une réinitialisation réussie applique la politique de mot de passe, révoque TOUTES les
  sessions actives et invalide tous les autres jetons de réinitialisation du compte ;
- audit et journaux : identifiants opaques et codes uniquement (règle 5), jamais d'adresse,
  de nom, de lien ni de jeton.

Comportement quand l'adresse n'est pas vérifiée (décision) : la connexion reste permise et
`email_verifie` est exposé à l'interface (bandeau « confirmez votre adresse ») ; en revanche la
validation humaine d'un récapitulatif avant soumission officielle (envoi sensible, règle 1) est
refusée tant que l'adresse n'est pas vérifiée (`exiger_adresse_verifiee`, actif par défaut en
production uniquement).
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict, deque
from datetime import timedelta
from threading import Lock

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import Environnement, Parametres
from app.core.erreurs import AccesRefuse, DonneesInvalides, LimiteAtteinte
from app.core.securite import (
    empreinte_jeton,
    generer_jeton,
    hacher_mot_de_passe,
    verifier_robustesse,
)
from app.db.base import maintenant_utc
from app.db.tenant import definir_tenant, sans_filtre_tenant
from app.modeles.bureau import Bureau
from app.modeles.jeton_courriel import JetonCourriel, ObjetJetonCourriel
from app.modeles.journal_audit import ResultatAudit
from app.modeles.session_utilisateur import SessionUtilisateur
from app.modeles.utilisateur import Utilisateur
from app.services import audit, courriels

journal = logging.getLogger("app.jetons_courriel")

MESSAGE_LIEN_INVALIDE = "Ce lien est invalide ou a expiré. Demandez-en un nouveau."
MESSAGE_LIMITE = "Trop de demandes depuis cette connexion. Réessayez plus tard."
MESSAGE_ADRESSE_NON_VERIFIEE = (
    "Confirmez d'abord votre adresse e-mail (lien reçu par courriel) avant de valider "
    "un récapitulatif destiné à un envoi officiel."
)
FENETRE_LIMITE_SECONDES = 3600


class LimiteurDemandes:
    """Fenêtre glissante en mémoire : N demandes par clé (adresse IP) et par heure."""

    def __init__(self) -> None:
        self._essais: dict[str, deque[float]] = defaultdict(deque)
        self._verrou = Lock()

    def verifier_et_compter(self, cle: str, maximum: int) -> None:
        maintenant = time.monotonic()
        with self._verrou:
            file = self._essais[cle]
            while file and maintenant - file[0] > FENETRE_LIMITE_SECONDES:
                file.popleft()
            if len(file) >= maximum:
                raise LimiteAtteinte(MESSAGE_LIMITE)
            file.append(maintenant)


def verifier_limite_ip(limiteur: LimiteurDemandes, ip: str, parametres: Parametres) -> None:
    if (
        parametres.environnement is Environnement.TEST
        and not parametres.reinitialisation_limite_active_en_test
    ):
        return
    limiteur.verifier_et_compter(ip, parametres.reinitialisation_max_par_heure_par_ip)


# --- Primitives -------------------------------------------------------------------------

def _compter_recents(db: Session, utilisateur_id: uuid.UUID, objet: ObjetJetonCourriel) -> int:
    depuis = maintenant_utc() - timedelta(seconds=FENETRE_LIMITE_SECONDES)
    return (
        db.scalar(
            select(func.count(JetonCourriel.id)).where(
                JetonCourriel.utilisateur_id == utilisateur_id,
                JetonCourriel.objet == objet,
                JetonCourriel.cree_le >= depuis,
            )
        )
        or 0
    )


def _invalider_jetons(db: Session, utilisateur_id: uuid.UUID, objet: ObjetJetonCourriel) -> None:
    db.execute(
        update(JetonCourriel)
        .where(
            JetonCourriel.utilisateur_id == utilisateur_id,
            JetonCourriel.objet == objet,
            JetonCourriel.utilise_le.is_(None),
        )
        .values(utilise_le=maintenant_utc())
    )


def _emettre_jeton(
    db: Session, utilisateur: Utilisateur, objet: ObjetJetonCourriel, duree: timedelta
) -> str:
    """Crée un jeton (les précédents, non utilisés, sont invalidés) et renvoie sa valeur
    claire, qui ne doit servir qu'à construire le courriel."""
    _invalider_jetons(db, utilisateur.id, objet)
    clair = generer_jeton()
    maintenant = maintenant_utc()
    db.add(
        JetonCourriel(
            utilisateur_id=utilisateur.id,
            objet=objet,
            empreinte=empreinte_jeton(clair),
            cree_le=maintenant,
            expire_le=maintenant + duree,
        )
    )
    db.flush()
    return clair


def _charger_jeton_valide(
    db: Session, jeton_clair: str, objet: ObjetJetonCourriel
) -> tuple[JetonCourriel, Utilisateur]:
    """Retrouve le jeton par son empreinte, vérifie objet, usage, expiration et compte, puis
    fixe le bureau de la session. Message unique en cas d'échec (aucune distinction exploitable)."""
    maintenant = maintenant_utc()
    with sans_filtre_tenant(db):
        jeton = db.scalar(
            select(JetonCourriel).where(JetonCourriel.empreinte == empreinte_jeton(jeton_clair))
        )
        if jeton is None or jeton.objet is not objet:
            raise DonneesInvalides(MESSAGE_LIEN_INVALIDE)
        utilisateur = db.get(Utilisateur, jeton.utilisateur_id)
        bureau = db.get(Bureau, jeton.tenant_id)

    definir_tenant(db, jeton.tenant_id)
    if jeton.utilise_le is not None or jeton.expire_le <= maintenant:
        audit.journaliser(
            db, f"auth.{objet.value}", ResultatAudit.REFUS, acteur_id=jeton.utilisateur_id,
            ressource_type="utilisateur", ressource_id=jeton.utilisateur_id,
            details={"motif": "jeton_expire_ou_deja_utilise"},
        )
        db.commit()
        raise DonneesInvalides(MESSAGE_LIEN_INVALIDE)
    if utilisateur is None or not utilisateur.actif or bureau is None or not bureau.actif:
        raise DonneesInvalides(MESSAGE_LIEN_INVALIDE)
    return jeton, utilisateur


def _revendiquer(db: Session, jeton: JetonCourriel) -> None:
    """Marque le jeton utilisé de façon atomique : une seule requête concurrente réussit."""
    resultat = db.execute(
        update(JetonCourriel)
        .where(JetonCourriel.id == jeton.id, JetonCourriel.utilise_le.is_(None))
        .values(utilise_le=maintenant_utc())
        .execution_options(synchronize_session=False)
    )
    if resultat.rowcount != 1:
        db.rollback()
        raise DonneesInvalides(MESSAGE_LIEN_INVALIDE)


# --- Vérification d'adresse -------------------------------------------------------------

def preparer_verification_adresse(
    db: Session, *, utilisateur: Utilisateur, parametres: Parametres
) -> courriels.Courriel | None:
    """Émet le jeton (le bureau de la session doit être celui de l'utilisateur) et prépare le
    courriel. None si l'adresse est déjà vérifiée ou si aucune URL publique n'est connue."""
    if utilisateur.email_verifie:
        return None
    if _compter_recents(
        db, utilisateur.id, ObjetJetonCourriel.VERIFICATION_ADRESSE
    ) >= parametres.reinitialisation_max_par_heure_par_compte:
        raise LimiteAtteinte("Trop de courriels de confirmation demandés. Réessayez plus tard.")
    clair = _emettre_jeton(
        db, utilisateur, ObjetJetonCourriel.VERIFICATION_ADRESSE,
        timedelta(hours=parametres.duree_jeton_verification_heures),
    )
    audit.journaliser(
        db, "auth.verification_adresse_envoyee", ResultatAudit.SUCCES,
        acteur_id=utilisateur.id, ressource_type="utilisateur", ressource_id=utilisateur.id,
    )
    db.commit()
    lien = courriels.construire_lien(parametres, courriels.CHEMIN_VERIFICATION_ADRESSE, clair)
    return courriels.gabarit_verification_adresse(
        utilisateur.email, lien, parametres.duree_jeton_verification_heures
    )


def envoyer_verification_adresse(
    db: Session, *, utilisateur: Utilisateur, parametres: Parametres
) -> bool:
    """Prépare puis envoie le courriel de vérification. Ne lève jamais (inscription,
    création de compte) : un échec d'envoi est journalisé sans donnée personnelle."""
    try:
        courriel = preparer_verification_adresse(db, utilisateur=utilisateur, parametres=parametres)
    except Exception as exc:  # noqa: BLE001
        journal.error("Préparation du courriel de vérification impossible (%s).", type(exc).__name__)
        return False
    return courriel is not None and courriels.envoyer_courriel(courriel, parametres)


def confirmer_adresse(db: Session, *, jeton_clair: str) -> None:
    jeton, utilisateur = _charger_jeton_valide(
        db, jeton_clair, ObjetJetonCourriel.VERIFICATION_ADRESSE
    )
    _revendiquer(db, jeton)
    if utilisateur.email_verifie_le is None:
        utilisateur.email_verifie_le = maintenant_utc()
    audit.journaliser(
        db, "auth.adresse_verifiee", ResultatAudit.SUCCES, acteur_id=utilisateur.id,
        ressource_type="utilisateur", ressource_id=utilisateur.id,
    )
    db.commit()


def exiger_adresse_verifiee(utilisateur: Utilisateur, parametres: Parametres) -> None:
    """Garde des envois sensibles : refuse si l'adresse n'est pas vérifiée (quand exigé)."""
    if parametres.adresse_verifiee_exigee and not utilisateur.email_verifie:
        raise AccesRefuse(MESSAGE_ADRESSE_NON_VERIFIEE)


# --- Mot de passe oublié ----------------------------------------------------------------

def demander_reinitialisation(
    db: Session, *, email: str, parametres: Parametres
) -> courriels.Courriel | None:
    """Prépare le courriel de réinitialisation si (et seulement si) un compte actif existe.
    L'appelant répond toujours la même chose, que le résultat soit None ou non."""
    email_norm = email.strip().lower()
    with sans_filtre_tenant(db):
        utilisateur = db.scalar(select(Utilisateur).where(Utilisateur.email == email_norm))
        bureau = db.get(Bureau, utilisateur.tenant_id) if utilisateur is not None else None
    if utilisateur is None or not utilisateur.actif or bureau is None or not bureau.actif:
        return None

    definir_tenant(db, utilisateur.tenant_id)
    objet = ObjetJetonCourriel.REINITIALISATION_MOT_DE_PASSE
    if _compter_recents(db, utilisateur.id, objet) >= parametres.reinitialisation_max_par_heure_par_compte:
        audit.journaliser(
            db, "auth.reinitialisation_demandee", ResultatAudit.REFUS, acteur_id=utilisateur.id,
            ressource_type="utilisateur", ressource_id=utilisateur.id,
            details={"motif": "limite_atteinte"},
        )
        db.commit()
        return None

    clair = _emettre_jeton(
        db, utilisateur, objet, timedelta(minutes=parametres.duree_jeton_reinitialisation_minutes)
    )
    audit.journaliser(
        db, "auth.reinitialisation_demandee", ResultatAudit.SUCCES, acteur_id=utilisateur.id,
        ressource_type="utilisateur", ressource_id=utilisateur.id,
    )
    db.commit()
    lien = courriels.construire_lien(parametres, courriels.CHEMIN_NOUVEAU_MOT_DE_PASSE, clair)
    return courriels.gabarit_mot_de_passe_oublie(
        utilisateur.email, lien, parametres.duree_jeton_reinitialisation_minutes
    )


def reinitialiser_mot_de_passe(
    db: Session, *, jeton_clair: str, nouveau_mot_de_passe: str, parametres: Parametres
) -> None:
    objet = ObjetJetonCourriel.REINITIALISATION_MOT_DE_PASSE
    jeton, utilisateur = _charger_jeton_valide(db, jeton_clair, objet)

    # Politique existante, vérifiée AVANT de consommer le jeton : un mot de passe refusé
    # permet de réessayer avec le même lien.
    problemes = verifier_robustesse(nouveau_mot_de_passe, parametres.longueur_min_mot_de_passe)
    if problemes:
        raise DonneesInvalides("Mot de passe trop faible (" + " ; ".join(problemes) + ").")

    _revendiquer(db, jeton)
    maintenant = maintenant_utc()
    utilisateur.empreinte_mot_de_passe = hacher_mot_de_passe(nouveau_mot_de_passe)
    utilisateur.doit_changer_mot_de_passe = False
    utilisateur.echecs_connexion = 0
    utilisateur.verrouille_jusqua = None
    if utilisateur.email_verifie_le is None:  # le lien reçu prouve l'accès à la boîte
        utilisateur.email_verifie_le = maintenant
    _invalider_jetons(db, utilisateur.id, objet)
    db.execute(
        update(SessionUtilisateur)
        .where(
            SessionUtilisateur.utilisateur_id == utilisateur.id,
            SessionUtilisateur.revoquee_le.is_(None),
        )
        .values(revoquee_le=maintenant)
    )
    audit.journaliser(
        db, "auth.reinitialisation_mot_de_passe", ResultatAudit.SUCCES, acteur_id=utilisateur.id,
        ressource_type="utilisateur", ressource_id=utilisateur.id,
        details={"canal": "courriel"},
    )
    db.commit()
