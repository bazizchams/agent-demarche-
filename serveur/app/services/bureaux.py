"""Gestion des bureaux (tenants) et provisionnement initial."""

from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Parametres
from app.core.erreurs import Conflit, DonneesInvalides, NonTrouve
from app.core.securite import hacher_mot_de_passe, verifier_robustesse
from app.db.tenant import definir_tenant, sans_filtre_tenant, tenant_courant
from app.modeles.bureau import Bureau
from app.modeles.journal_audit import ResultatAudit
from app.modeles.utilisateur import Role, Utilisateur
from app.services import audit

_MOTIF_SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9\-]{1,61}[a-z0-9])$")


def valider_slug(slug: str) -> str:
    s = slug.strip().lower()
    if not _MOTIF_SLUG.match(s):
        raise DonneesInvalides(
            "Identifiant de bureau (slug) invalide : lettres minuscules, chiffres et tirets (3 à 63 caractères)."
        )
    return s


def obtenir_bureau_courant(db: Session) -> Bureau:
    tid = tenant_courant(db)
    if tid is None:
        raise NonTrouve("Bureau introuvable.")
    bureau = db.get(Bureau, tid)
    if bureau is None:
        raise NonTrouve("Bureau introuvable.")
    return bureau


def renommer_bureau_courant(
    db: Session, *, nouveau_nom: str, acteur_id: uuid.UUID
) -> Bureau:
    bureau = obtenir_bureau_courant(db)
    bureau.nom = nouveau_nom.strip()
    audit.journaliser(
        db,
        "bureau.modification",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="bureau",
        ressource_id=bureau.id,
    )
    db.commit()
    return bureau


def provisionner_bureau_et_admin(
    db: Session,
    *,
    nom_bureau: str,
    slug: str,
    email_admin: str,
    nom_admin: str,
    mot_de_passe_admin: str,
    parametres: Parametres,
    doit_changer_mot_de_passe: bool = False,
) -> tuple[Bureau, Utilisateur]:
    """Crée un nouveau bureau et son premier administrateur dans une seule transaction.
    Utilisé par l'outil d'administration en ligne de commande (et plus tard par l'inscription SaaS)."""
    slug_valide = valider_slug(slug)
    email_norm = email_admin.strip().lower()
    problemes = verifier_robustesse(
        mot_de_passe_admin, parametres.longueur_min_mot_de_passe
    )
    if problemes:
        raise DonneesInvalides(
            "Mot de passe administrateur trop faible (" + " ; ".join(problemes) + ")."
        )

    with sans_filtre_tenant(db):
        if db.scalar(select(Bureau.id).where(Bureau.slug == slug_valide)) is not None:
            raise Conflit("Un bureau avec cet identifiant (slug) existe déjà.")
        if db.scalar(select(Utilisateur.id).where(Utilisateur.email == email_norm)) is not None:
            raise Conflit("Cette adresse e-mail est déjà utilisée.")

        bureau = Bureau(id=uuid.uuid4(), nom=nom_bureau.strip(), slug=slug_valide, actif=True)
        db.add(bureau)
        db.flush()

    definir_tenant(db, bureau.id)
    admin = Utilisateur(
        id=uuid.uuid4(),
        tenant_id=bureau.id,
        email=email_norm,
        nom_affiche=nom_admin.strip(),
        empreinte_mot_de_passe=hacher_mot_de_passe(mot_de_passe_admin),
        role=Role.ADMINISTRATEUR,
        actif=True,
        doit_changer_mot_de_passe=doit_changer_mot_de_passe,
    )
    db.add(admin)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise Conflit("Conflit d'unicité lors de la création du bureau.") from exc

    audit.journaliser(
        db,
        "bureau.provisionnement",
        ResultatAudit.SUCCES,
        acteur_id=admin.id,
        ressource_type="bureau",
        ressource_id=bureau.id,
    )
    db.commit()
    return bureau, admin
