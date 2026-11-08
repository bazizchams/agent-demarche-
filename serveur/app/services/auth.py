"""Service d'authentification et de gestion des sessions.

Principes de sécurité :
- Les mots de passe sont hachés avec Argon2id.
- Si l'adresse e-mail est inconnue, une vérification Argon2 factice est exécutée
  pour éviter l'énumération des comptes par mesure du temps de réponse.
- Seule l'empreinte SHA-256 du jeton de session est stockée en base.
- Toute session a une durée de vie maximale ET un délai d'expiration par inactivité.
- Un compte est temporairement verrouillé après N échecs consécutifs.
- Le changement de mot de passe révoque toutes les autres sessions de l'utilisateur.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Parametres
from app.core.erreurs import AccesRefuse, DonneesInvalides, NonAuthentifie
from app.core.securite import (
    doit_rehacher,
    empreinte_jeton,
    generer_jeton,
    hacher_mot_de_passe,
    verification_factice,
    verifier_mot_de_passe,
    verifier_robustesse,
)
from app.db.base import maintenant_utc
from app.db.tenant import definir_tenant, sans_filtre_tenant
from app.modeles.bureau import Bureau
from app.modeles.journal_audit import ResultatAudit
from app.modeles.session_utilisateur import SessionUtilisateur
from app.modeles.utilisateur import Utilisateur
from app.services import audit

journal = logging.getLogger("app.auth")

MESSAGE_IDENTIFIANTS_INVALIDES = "Identifiants invalides ou compte indisponible."


@dataclass(frozen=True)
class SessionCreee:
    jeton_clair: str
    session: SessionUtilisateur
    utilisateur: Utilisateur


def authentifier_et_creer_session(
    db: Session,
    *,
    email: str,
    mot_de_passe: str,
    parametres: Parametres,
) -> SessionCreee:
    """Vérifie les identifiants et ouvre une session.

    Pendant la recherche initiale par e-mail, le bureau n'est pas encore connu :
    on utilise `sans_filtre_tenant` uniquement pour charger l'utilisateur et son bureau,
    puis on fixe immédiatement le tenant de la session SQLAlchemy.
    """
    maintenant = maintenant_utc()
    email_normalise = email.strip().lower()

    with sans_filtre_tenant(db):
        utilisateur = db.scalar(
            select(Utilisateur).where(Utilisateur.email == email_normalise)
        )
        if utilisateur is None:
            verification_factice(mot_de_passe)
            journal.info("Tentative de connexion sur un compte inexistant.")
            raise NonAuthentifie(MESSAGE_IDENTIFIANTS_INVALIDES)

        bureau = db.get(Bureau, utilisateur.tenant_id)

    definir_tenant(db, utilisateur.tenant_id)

    if bureau is None or not bureau.actif:
        verification_factice(mot_de_passe)
        audit.journaliser(
            db,
            "auth.connexion",
            ResultatAudit.REFUS,
            acteur_id=utilisateur.id,
            ressource_type="utilisateur",
            ressource_id=utilisateur.id,
            details={"motif": "bureau_inactif"},
        )
        db.commit()
        raise NonAuthentifie(MESSAGE_IDENTIFIANTS_INVALIDES)

    if not utilisateur.actif:
        verification_factice(mot_de_passe)
        audit.journaliser(
            db,
            "auth.connexion",
            ResultatAudit.REFUS,
            acteur_id=utilisateur.id,
            ressource_type="utilisateur",
            ressource_id=utilisateur.id,
            details={"motif": "utilisateur_inactif"},
        )
        db.commit()
        raise NonAuthentifie(MESSAGE_IDENTIFIANTS_INVALIDES)

    if utilisateur.verrouille_jusqua and utilisateur.verrouille_jusqua > maintenant:
        verification_factice(mot_de_passe)
        audit.journaliser(
            db,
            "auth.connexion",
            ResultatAudit.REFUS,
            acteur_id=utilisateur.id,
            ressource_type="utilisateur",
            ressource_id=utilisateur.id,
            details={"motif": "compte_verrouille"},
        )
        db.commit()
        raise NonAuthentifie(MESSAGE_IDENTIFIANTS_INVALIDES)

    if not verifier_mot_de_passe(utilisateur.empreinte_mot_de_passe, mot_de_passe):
        utilisateur.echecs_connexion += 1
        motif = "mot_de_passe_invalide"
        if utilisateur.echecs_connexion >= parametres.max_echecs_connexion:
            utilisateur.verrouille_jusqua = maintenant + timedelta(
                minutes=parametres.duree_verrouillage_minutes
            )
            motif = "compte_verrouille_apres_echecs"
        audit.journaliser(
            db,
            "auth.connexion",
            ResultatAudit.ECHEC,
            acteur_id=utilisateur.id,
            ressource_type="utilisateur",
            ressource_id=utilisateur.id,
            details={"motif": motif, "echecs": utilisateur.echecs_connexion},
        )
        db.commit()
        raise NonAuthentifie(MESSAGE_IDENTIFIANTS_INVALIDES)

    if doit_rehacher(utilisateur.empreinte_mot_de_passe):
        utilisateur.empreinte_mot_de_passe = hacher_mot_de_passe(mot_de_passe)

    utilisateur.echecs_connexion = 0
    utilisateur.verrouille_jusqua = None
    utilisateur.derniere_connexion_le = maintenant

    jeton_clair = generer_jeton()
    jeton_csrf = generer_jeton()
    session_obj = SessionUtilisateur(
        utilisateur_id=utilisateur.id,
        empreinte_jeton=empreinte_jeton(jeton_clair),
        jeton_csrf=jeton_csrf,
        cree_le=maintenant,
        derniere_activite_le=maintenant,
        expire_le=maintenant + timedelta(minutes=parametres.duree_session_minutes),
    )
    db.add(session_obj)
    audit.journaliser(
        db,
        "auth.connexion",
        ResultatAudit.SUCCES,
        acteur_id=utilisateur.id,
        ressource_type="session",
        ressource_id=session_obj.id,
    )
    db.commit()
    return SessionCreee(
        jeton_clair=jeton_clair,
        session=session_obj,
        utilisateur=utilisateur,
    )


def verifier_et_rafraichir_session(
    db: Session,
    *,
    jeton_clair: str,
    parametres: Parametres,
) -> tuple[SessionUtilisateur, Utilisateur]:
    """Charge la session à partir du jeton, fixe le bureau de la session DB,
    vérifie l'expiration et l'inactivité, et met à jour `derniere_activite_le`."""
    maintenant = maintenant_utc()
    empreinte = empreinte_jeton(jeton_clair)

    with sans_filtre_tenant(db):
        session_obj = db.scalar(
            select(SessionUtilisateur).where(
                SessionUtilisateur.empreinte_jeton == empreinte
            )
        )
        if session_obj is None:
            raise NonAuthentifie("Session invalide ou expirée.")
        bureau = db.get(Bureau, session_obj.tenant_id)

    definir_tenant(db, session_obj.tenant_id)

    if session_obj.revoquee_le is not None:
        raise NonAuthentifie("Session révoquée.")

    limite_inactivite = session_obj.derniere_activite_le + timedelta(
        minutes=parametres.inactivite_session_minutes
    )
    if maintenant >= session_obj.expire_le or maintenant >= limite_inactivite:
        session_obj.revoquee_le = maintenant
        db.commit()
        raise NonAuthentifie("Session expirée.")

    utilisateur = session_obj.utilisateur
    if bureau is None or not bureau.actif or utilisateur is None or not utilisateur.actif:
        session_obj.revoquee_le = maintenant
        db.commit()
        raise AccesRefuse("Compte ou bureau désactivé.")

    session_obj.derniere_activite_le = maintenant
    db.commit()
    return session_obj, utilisateur


def revoquer_session(
    db: Session,
    *,
    session_obj: SessionUtilisateur,
    acteur_id,
) -> None:
    session_obj.revoquee_le = maintenant_utc()
    audit.journaliser(
        db,
        "auth.deconnexion",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="session",
        ressource_id=session_obj.id,
    )
    db.commit()


def changer_mot_de_passe(
    db: Session,
    *,
    utilisateur: Utilisateur,
    session_courante: SessionUtilisateur,
    mot_de_passe_actuel: str,
    nouveau_mot_de_passe: str,
    parametres: Parametres,
) -> None:
    if not verifier_mot_de_passe(utilisateur.empreinte_mot_de_passe, mot_de_passe_actuel):
        audit.journaliser(
            db,
            "auth.changement_mot_de_passe",
            ResultatAudit.ECHEC,
            acteur_id=utilisateur.id,
            ressource_type="utilisateur",
            ressource_id=utilisateur.id,
            details={"motif": "mot_de_passe_actuel_incorrect"},
        )
        db.commit()
        raise DonneesInvalides("Le mot de passe actuel est incorrect.")

    if mot_de_passe_actuel == nouveau_mot_de_passe:
        raise DonneesInvalides("Le nouveau mot de passe doit être différent de l'actuel.")

    problemes = verifier_robustesse(
        nouveau_mot_de_passe, parametres.longueur_min_mot_de_passe
    )
    if problemes:
        raise DonneesInvalides(
            "Mot de passe trop faible (" + " ; ".join(problemes) + ")."
        )

    maintenant = maintenant_utc()
    utilisateur.empreinte_mot_de_passe = hacher_mot_de_passe(nouveau_mot_de_passe)
    utilisateur.doit_changer_mot_de_passe = False

    # Révoque toutes les autres sessions actives de cet utilisateur.
    db.execute(
        update(SessionUtilisateur)
        .where(
            SessionUtilisateur.utilisateur_id == utilisateur.id,
            SessionUtilisateur.id != session_courante.id,
            SessionUtilisateur.revoquee_le.is_(None),
        )
        .values(revoquee_le=maintenant)
    )
    audit.journaliser(
        db,
        "auth.changement_mot_de_passe",
        ResultatAudit.SUCCES,
        acteur_id=utilisateur.id,
        ressource_type="utilisateur",
        ressource_id=utilisateur.id,
    )
    db.commit()
