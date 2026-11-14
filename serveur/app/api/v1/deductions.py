"""Routes des déductions vérifiables (phase P2) : calculer les points forts à partir des
extractions confirmées, les lister avec leur pièce, les confirmer ou les rejeter, puis appliquer
à la fiche le niveau de langue d'un point confirmé.

Sécurité : session et CSRF obligatoires sur toute écriture (dépendance commune), rôle
administrateur ou employé pour calculer, décider et appliquer ; lecture seule = consultation.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.api.dependances import ContexteAuth, exiger_roles, obtenir_cle_maitresse, obtenir_contexte_auth
from app.modeles.point_fort import StatutPointFort
from app.modeles.utilisateur import Role
from app.schemas.deduction import ApplicationNiveauSortie, PointFortSortie, ResultatDeductionsSortie
from app.services import deductions_dossier as service

routeur = APIRouter(prefix="/candidats/{candidat_id}", tags=["déductions vérifiables"])

ExigerEcriture = Depends(exiger_roles(Role.ADMINISTRATEUR, Role.EMPLOYE))


@routeur.post("/deductions/calculer", response_model=ResultatDeductionsSortie)
def calculer(
    candidat_id: uuid.UUID,
    ctx: ContexteAuth = ExigerEcriture,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> ResultatDeductionsSortie:
    return service.calculer_points_forts(
        ctx.db, candidat_id=candidat_id, acteur_id=ctx.utilisateur.id, cle_maitresse=cle_maitresse
    )


@routeur.get("/points-forts", response_model=list[PointFortSortie])
def lister(
    candidat_id: uuid.UUID,
    statut: StatutPointFort | None = Query(default=None),
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> list[PointFortSortie]:
    return service.lister_points_forts(ctx.db, candidat_id=candidat_id, cle_maitresse=cle_maitresse, statut=statut)


def _decider(action: str, candidat_id: uuid.UUID, point_id: uuid.UUID, ctx: ContexteAuth, cle: bytes) -> PointFortSortie:
    return service.decider_point_fort(
        ctx.db, candidat_id=candidat_id, point_id=point_id, action=action,
        acteur_id=ctx.utilisateur.id, cle_maitresse=cle,
    )


@routeur.post("/points-forts/{point_id}/confirmer", response_model=PointFortSortie)
def confirmer(
    candidat_id: uuid.UUID,
    point_id: uuid.UUID,
    ctx: ContexteAuth = ExigerEcriture,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> PointFortSortie:
    return _decider("confirmer", candidat_id, point_id, ctx, cle_maitresse)


@routeur.post("/points-forts/{point_id}/rejeter", response_model=PointFortSortie)
def rejeter(
    candidat_id: uuid.UUID,
    point_id: uuid.UUID,
    ctx: ContexteAuth = ExigerEcriture,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> PointFortSortie:
    return _decider("rejeter", candidat_id, point_id, ctx, cle_maitresse)


@routeur.post("/points-forts/{point_id}/appliquer-niveau", response_model=ApplicationNiveauSortie)
def appliquer_niveau(
    candidat_id: uuid.UUID,
    point_id: uuid.UUID,
    ctx: ContexteAuth = ExigerEcriture,
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> ApplicationNiveauSortie:
    return service.appliquer_niveau_a_fiche(
        ctx.db, candidat_id=candidat_id, point_id=point_id, acteur_id=ctx.utilisateur.id, cle_maitresse=cle_maitresse
    )
