"""Isolation multi-bureaux au niveau de l'ORM (défense en profondeur).

Chaque session SQLAlchemy porte le bureau (tenant) de l'utilisateur authentifié.
Deux garde-fous automatiques s'appliquent à TOUTE table héritant de `MixinTenant` :

1. Lecture / UPDATE / DELETE ORM : un critère `tenant_id = <bureau courant>` est ajouté
   à chaque requête (`with_loader_criteria`), y compris aux chargements de relations.
   Sans bureau défini, la requête est REFUSÉE (`ContexteTenantManquant`) au lieu de
   renvoyer les données de tous les bureaux.
2. Écriture (flush) : un objet d'un autre bureau ne peut être ni créé, ni modifié,
   ni supprimé ; le `tenant_id` d'une ligne existante ne peut pas changer.

Seules quelques opérations système (connexion, création d'un bureau) utilisent
`sans_filtre_tenant()`, de façon explicite et localisée.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from itertools import chain

from sqlalchemy import event, inspect
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

from app.db.base import MixinTenant

CLE_TENANT = "tenant_id"
CLE_CONTOURNEMENT = "contournement_tenant"


class ContexteTenantManquant(RuntimeError):
    """Accès à une table métier sans bureau défini sur la session."""


class ViolationTenant(RuntimeError):
    """Tentative d'écriture sur une ligne d'un autre bureau."""


def definir_tenant(session: Session, tenant_id: uuid.UUID) -> None:
    """Fixe le bureau de la session. Une session ne peut pas changer de bureau."""
    actuel = session.info.get(CLE_TENANT)
    if actuel is not None and actuel != tenant_id:
        raise ViolationTenant("Une session ne peut pas changer de bureau.")
    session.info[CLE_TENANT] = tenant_id


def tenant_courant(session: Session) -> uuid.UUID | None:
    return session.info.get(CLE_TENANT)


@contextmanager
def sans_filtre_tenant(session: Session) -> Iterator[Session]:
    """Désactive temporairement le filtre. Réservé aux opérations système auditées."""
    precedent = session.info.get(CLE_CONTOURNEMENT, False)
    session.info[CLE_CONTOURNEMENT] = True
    try:
        yield session
    finally:
        session.info[CLE_CONTOURNEMENT] = precedent


def _concerne_tables_tenant(etat: ORMExecuteState) -> bool:
    return any(issubclass(m.class_, MixinTenant) for m in etat.all_mappers)


@event.listens_for(Session, "do_orm_execute")
def _filtrer_par_tenant(etat: ORMExecuteState) -> None:
    session = etat.session
    if session.info.get(CLE_CONTOURNEMENT):
        return
    if not (etat.is_select or etat.is_update or etat.is_delete):
        return
    # Chargements différés d'attributs / relations : le critère est déjà propagé
    # depuis la requête d'origine (propagate_to_loaders).
    if etat.is_column_load or etat.is_relationship_load:
        return
    tenant_id = session.info.get(CLE_TENANT)
    if tenant_id is None:
        if _concerne_tables_tenant(etat):
            raise ContexteTenantManquant(
                "Requête sur une table métier sans bureau défini : accès refusé."
            )
        return
    # Bureau défini : le critère est TOUJOURS ajouté (il est sans effet si la requête
    # ne touche aucune table métier). Cela couvre aussi les sous-requêtes, que la
    # détection par `all_mappers` pourrait ne pas voir.
    etat.statement = etat.statement.options(
        with_loader_criteria(
            MixinTenant,
            lambda cls: cls.tenant_id == tenant_id,
            include_aliases=True,
        )
    )


@event.listens_for(Session, "before_flush")
def _verifier_ecritures(session: Session, flush_context, instances) -> None:
    if session.info.get(CLE_CONTOURNEMENT):
        return
    tenant_id = session.info.get(CLE_TENANT)

    for objet in session.new:
        if not isinstance(objet, MixinTenant):
            continue
        if tenant_id is None:
            raise ContexteTenantManquant("Création d'une ligne métier sans bureau défini.")
        if objet.tenant_id is None:
            objet.tenant_id = tenant_id
        elif objet.tenant_id != tenant_id:
            raise ViolationTenant("Création d'une ligne pour un autre bureau refusée.")

    for objet in chain(session.dirty, session.deleted):
        if not isinstance(objet, MixinTenant):
            continue
        if tenant_id is None:
            raise ContexteTenantManquant("Modification d'une ligne métier sans bureau défini.")
        historique = inspect(objet).attrs.tenant_id.history
        anciens = [v for v in historique.deleted if v is not None]
        if anciens:
            raise ViolationTenant("Le bureau d'une ligne existante ne peut pas être modifié.")
        if objet.tenant_id != tenant_id:
            raise ViolationTenant("Modification d'une ligne d'un autre bureau refusée.")
