"""Routeur principal de l'API v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    abonnements_conformite,
    agents_locaux,
    audit,
    auth,
    bureau,
    candidats,
    demarches,
    portails,
    sante,
    taches,
    utilisateurs,
    validations,
)

routeur_v1 = APIRouter(prefix="/api/v1")
routeur_v1.include_router(sante.routeur)
routeur_v1.include_router(auth.routeur)
routeur_v1.include_router(utilisateurs.routeur)
routeur_v1.include_router(bureau.routeur)
routeur_v1.include_router(candidats.routeur)
routeur_v1.include_router(demarches.routeur)
routeur_v1.include_router(portails.routeur)
routeur_v1.include_router(agents_locaux.routeur)
routeur_v1.include_router(taches.routeur)
routeur_v1.include_router(validations.routeur)
routeur_v1.include_router(abonnements_conformite.routeur)
routeur_v1.include_router(audit.routeur)
