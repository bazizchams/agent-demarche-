"""Routeur principal de l'API v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    abonnements_conformite,
    acces_abonnement,
    agents_locaux,
    audit,
    auth,
    bureau,
    candidats,
    catalogue_formations,
    coffre_identifiants,
    connexion_portail,
    courriel,
    deductions,
    demarches,
    depots_passeport,
    evenements_agent,
    dossier_automatique,
    extractions,
    ia,
    inscription,
    navigateur_serveur,
    portails,
    projet_professionnel,
    sante,
    taches,
    utilisateurs,
    validation_recapitulatif,
    validations,
    voeux,
    voeux_suggestions,
)

routeur_v1 = APIRouter(prefix="/api/v1")
routeur_v1.include_router(sante.routeur)
routeur_v1.include_router(auth.routeur)
routeur_v1.include_router(courriel.routeur)
routeur_v1.include_router(utilisateurs.routeur)
routeur_v1.include_router(bureau.routeur)
routeur_v1.include_router(candidats.routeur)
routeur_v1.include_router(depots_passeport.routeur)
routeur_v1.include_router(extractions.routeur)
routeur_v1.include_router(deductions.routeur)
routeur_v1.include_router(dossier_automatique.routeur)
routeur_v1.include_router(projet_professionnel.routeur)
routeur_v1.include_router(voeux.routeur)
routeur_v1.include_router(voeux_suggestions.routeur)
routeur_v1.include_router(catalogue_formations.routeur)
routeur_v1.include_router(coffre_identifiants.routeur)
routeur_v1.include_router(demarches.routeur)
routeur_v1.include_router(ia.routeur)
routeur_v1.include_router(portails.routeur)
routeur_v1.include_router(navigateur_serveur.routeur)
routeur_v1.include_router(agents_locaux.routeur)
routeur_v1.include_router(taches.routeur)
routeur_v1.include_router(connexion_portail.routeur)
routeur_v1.include_router(evenements_agent.routeur)
routeur_v1.include_router(validations.routeur)
routeur_v1.include_router(validation_recapitulatif.routeur)
routeur_v1.include_router(acces_abonnement.routeur)
routeur_v1.include_router(abonnements_conformite.routeur)
routeur_v1.include_router(audit.routeur)
routeur_v1.include_router(inscription.routeur)
