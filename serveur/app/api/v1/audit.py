"""Consultation du journal d'audit du bureau (réservée aux administrateurs)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependances import ContexteAuth, exiger_roles
from app.modeles.utilisateur import Role
from app.schemas.bureau import EntreeAuditSortie
from app.schemas.commun import Page
from app.services import audit as service_audit

routeur = APIRouter(prefix="/audit", tags=["audit"])


@routeur.get("", response_model=Page[EntreeAuditSortie])
def lister(
    page: int = Query(default=1, ge=1),
    taille: int = Query(default=50, ge=1, le=200),
    action: str | None = Query(default=None, max_length=80),
    ctx: ContexteAuth = Depends(exiger_roles(Role.ADMINISTRATEUR)),
) -> Page[EntreeAuditSortie]:
    elements, total = service_audit.lister(
        ctx.db, page=page, taille=taille, action=action
    )
    return Page(
        elements=[EntreeAuditSortie.model_validate(e) for e in elements],
        total=total,
        page=page,
        taille=taille,
    )
