"""Gestion des utilisateurs d'un bureau (création, modification, réinitialisation).

Toutes les requêtes s'exécutent dans le contexte du bureau courant (filtré par l'ORM).
Seule la vérification d'unicité globale de l'adresse e-mail regarde hors du bureau,
avec un message neutre qui ne révèle pas à quel bureau appartient un compte existant.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Parametres
from app.core.erreurs import Conflit, DonneesInvalides, NonTrouve
from app.core.securite import hacher_mot_de_passe, verifier_robustesse
from app.db.base import maintenant_utc
from app.db.tenant import sans_filtre_tenant
from app.modeles.journal_audit import ResultatAudit
from app.modeles.session_utilisateur import SessionUtilisateur
from app.modeles.utilisateur import Role, Utilisateur
from app.schemas.auth import UtilisateurCreation, UtilisateurModification
from app.services import audit


def lister_utilisateurs(
    db: Session, *, page: int, taille: int
) -> tuple[list[Utilisateur], int]:
    total = db.scalar(select(func.count(Utilisateur.id))) or 0
    elements = db.scalars(
        select(Utilisateur)
        .order_by(Utilisateur.cree_le.asc(), Utilisateur.id)
        .offset((page - 1) * taille)
        .limit(taille)
    ).all()
    return list(elements), total


def obtenir_utilisateur(db: Session, utilisateur_id: uuid.UUID) -> Utilisateur:
    utilisateur = db.scalar(
        select(Utilisateur).where(Utilisateur.id == utilisateur_id)
    )
    if utilisateur is None:
        raise NonTrouve("Utilisateur introuvable.")
    return utilisateur


def _compter_administrateurs_actifs(db: Session, exclure_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count(Utilisateur.id)).where(
                Utilisateur.role == Role.ADMINISTRATEUR,
                Utilisateur.actif.is_(True),
                Utilisateur.id != exclure_id,
            )
        )
        or 0
    )


def creer_utilisateur(
    db: Session,
    *,
    donnees: UtilisateurCreation,
    acteur_id: uuid.UUID,
    parametres: Parametres,
) -> Utilisateur:
    problemes = verifier_robustesse(
        donnees.mot_de_passe_temporaire, parametres.longueur_min_mot_de_passe
    )
    if problemes:
        raise DonneesInvalides(
            "Mot de passe temporaire trop faible (" + " ; ".join(problemes) + ")."
        )

    email_norm = donnees.email.strip().lower()
    with sans_filtre_tenant(db):
        deja_pris = db.scalar(
            select(Utilisateur.id).where(Utilisateur.email == email_norm)
        )
    if deja_pris is not None:
        raise Conflit("Cette adresse e-mail ne peut pas être utilisée.")

    nouveau = Utilisateur(
        email=email_norm,
        nom_affiche=donnees.nom_affiche,
        empreinte_mot_de_passe=hacher_mot_de_passe(donnees.mot_de_passe_temporaire),
        role=donnees.role,
        actif=True,
        doit_changer_mot_de_passe=True,
    )
    db.add(nouveau)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise Conflit("Cette adresse e-mail ne peut pas être utilisée.") from exc

    audit.journaliser(
        db,
        "utilisateur.creation",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="utilisateur",
        ressource_id=nouveau.id,
        details={"role": nouveau.role.value},
    )
    db.commit()
    return nouveau


def modifier_utilisateur(
    db: Session,
    *,
    utilisateur_id: uuid.UUID,
    donnees: UtilisateurModification,
    acteur_id: uuid.UUID,
) -> Utilisateur:
    cible = obtenir_utilisateur(db, utilisateur_id)

    futur_role = donnees.role if donnees.role is not None else cible.role
    futur_actif = donnees.actif if donnees.actif is not None else cible.actif

    # Interdit de laisser le bureau sans aucun administrateur actif.
    if (
        cible.role == Role.ADMINISTRATEUR
        and cible.actif
        and (futur_role != Role.ADMINISTRATEUR or not futur_actif)
    ):
        if _compter_administrateurs_actifs(db, exclure_id=cible.id) == 0:
            raise Conflit(
                "Impossible de retirer ou désactiver le dernier administrateur actif du bureau."
            )

    changements: dict[str, str | bool] = {}
    if donnees.nom_affiche is not None and donnees.nom_affiche != cible.nom_affiche:
        cible.nom_affiche = donnees.nom_affiche
        changements["nom_affiche_modifie"] = True
    if donnees.role is not None and donnees.role != cible.role:
        cible.role = donnees.role
        changements["role"] = donnees.role.value
    if donnees.actif is not None and donnees.actif != cible.actif:
        cible.actif = donnees.actif
        changements["actif"] = donnees.actif
        if not donnees.actif:
            db.execute(
                update(SessionUtilisateur)
                .where(
                    SessionUtilisateur.utilisateur_id == cible.id,
                    SessionUtilisateur.revoquee_le.is_(None),
                )
                .values(revoquee_le=maintenant_utc())
            )

    audit.journaliser(
        db,
        "utilisateur.modification",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="utilisateur",
        ressource_id=cible.id,
        details=changements or {"aucun_changement": True},
    )
    db.commit()
    return cible


def reinitialiser_mot_de_passe(
    db: Session,
    *,
    utilisateur_id: uuid.UUID,
    mot_de_passe_temporaire: str,
    acteur_id: uuid.UUID,
    parametres: Parametres,
) -> Utilisateur:
    cible = obtenir_utilisateur(db, utilisateur_id)
    problemes = verifier_robustesse(
        mot_de_passe_temporaire, parametres.longueur_min_mot_de_passe
    )
    if problemes:
        raise DonneesInvalides(
            "Mot de passe temporaire trop faible (" + " ; ".join(problemes) + ")."
        )

    maintenant = maintenant_utc()
    cible.empreinte_mot_de_passe = hacher_mot_de_passe(mot_de_passe_temporaire)
    cible.doit_changer_mot_de_passe = True
    cible.echecs_connexion = 0
    cible.verrouille_jusqua = None

    db.execute(
        update(SessionUtilisateur)
        .where(
            SessionUtilisateur.utilisateur_id == cible.id,
            SessionUtilisateur.revoquee_le.is_(None),
        )
        .values(revoquee_le=maintenant)
    )
    audit.journaliser(
        db,
        "utilisateur.reinitialisation_mot_de_passe",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="utilisateur",
        ressource_id=cible.id,
    )
    db.commit()
    return cible
