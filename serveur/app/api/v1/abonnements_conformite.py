"""Routes API v1 de la Phase 6 :
- Abonnements SaaS mensuels, catalogue de forfaits, acceptation CGU et webhooks Stripe
- Conformité Loi algérienne n° 18-07 (consentement explicite des candidats, révocation,
  suppression définitive / droit à l'oubli et purge automatisée des archives expirées)
- Sauvegardes chiffrées (AES-256-GCM) par bureau et vérification d'intégrité
"""

from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.dependances import (
    ContexteAuth,
    exiger_roles,
    obtenir_cle_maitresse,
    obtenir_contexte_auth,
    obtenir_db,
)
from app.core.config import Parametres, obtenir_parametres
from app.modeles.utilisateur import Role
from app.schemas.abonnement_conformite import (
    AbonnementBureauSortie,
    AcceptationCGUEntree,
    ChangementForfaitEntree,
    ConsentementCandidatEntree,
    ForfaitCatalogueSortie,
    PolitiqueConservationEntree,
    PreuveConsentementSortie,
    ResultatPurgeConservationSortie,
    SauvegardeChiffreeSortie,
    SessionCheckoutStripeSortie,
    TexteCGUSortie,
    VerificationSauvegardeSortie,
)
from app.services import abonnements as service_abonnements
from app.services import conformite as service_conformite
from app.services import sauvegardes as service_sauvegardes

routeur = APIRouter(tags=["abonnements-conformite-sauvegardes"])


# ---------------------------------------------------------------------------
# 1. Abonnements SaaS, CGU et Webhooks Stripe
# ---------------------------------------------------------------------------


@routeur.get(
    "/abonnement/forfaits",
    response_model=list[ForfaitCatalogueSortie],
)
def lister_forfaits_catalogue(
    _ctx: ContexteAuth = Depends(obtenir_contexte_auth),
) -> list[ForfaitCatalogueSortie]:
    return service_abonnements.lister_catalogue_forfaits()


@routeur.get(
    "/abonnement",
    response_model=AbonnementBureauSortie,
)
def lire_abonnement_courant(
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
) -> AbonnementBureauSortie:
    return service_abonnements.obtenir_abonnement_bureau(ctx.db)


@routeur.get(
    "/abonnement/cgu",
    response_model=TexteCGUSortie,
)
def lire_texte_cgu(
    _ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    parametres: Parametres = Depends(obtenir_parametres),
) -> TexteCGUSortie:
    return service_abonnements.obtenir_texte_cgu(parametres)


@routeur.post(
    "/abonnement/cgu/accepter",
    response_model=AbonnementBureauSortie,
)
def accepter_cgu(
    donnees: AcceptationCGUEntree,
    ctx: ContexteAuth = Depends(exiger_roles(Role.ADMINISTRATEUR)),
    parametres: Parametres = Depends(obtenir_parametres),
) -> AbonnementBureauSortie:
    return service_abonnements.accepter_cgu_bureau(
        ctx.db,
        donnees=donnees,
        acteur_id=ctx.utilisateur.id,
        parametres=parametres,
    )


@routeur.put(
    "/abonnement/politique-conservation",
    response_model=AbonnementBureauSortie,
)
def modifier_politique_conservation(
    donnees: PolitiqueConservationEntree,
    ctx: ContexteAuth = Depends(exiger_roles(Role.ADMINISTRATEUR)),
) -> AbonnementBureauSortie:
    return service_abonnements.mettre_a_jour_politique_conservation(
        ctx.db,
        duree_conservation_jours=donnees.duree_conservation_jours,
        acteur_id=ctx.utilisateur.id,
    )


@routeur.post(
    "/abonnement/checkout-stripe",
    response_model=SessionCheckoutStripeSortie,
    status_code=status.HTTP_201_CREATED,
)
def creer_checkout_stripe(
    donnees: ChangementForfaitEntree,
    ctx: ContexteAuth = Depends(exiger_roles(Role.ADMINISTRATEUR)),
    parametres: Parametres = Depends(obtenir_parametres),
) -> SessionCheckoutStripeSortie:
    return service_abonnements.creer_session_checkout_stripe(
        ctx.db,
        forfait=donnees.forfait,
        acteur_id=ctx.utilisateur.id,
        parametres=parametres,
    )


@routeur.post(
    "/webhooks/stripe",
    status_code=status.HTTP_200_OK,
)
async def recevoir_webhook_stripe(
    requete: Request,
    db: Session = Depends(obtenir_db),
    parametres: Parametres = Depends(obtenir_parametres),
) -> dict[str, str]:
    """Point d'entrée des webhooks Stripe (authentifié cryptographiquement par `Stripe-Signature`)."""
    corps_brut = await requete.body()
    en_tete_sig = requete.headers.get("Stripe-Signature")
    return service_abonnements.traiter_evenement_webhook_stripe(
        db,
        charge_utile_octets=corps_brut,
        en_tete_signature=en_tete_sig,
        parametres=parametres,
    )


# ---------------------------------------------------------------------------
# 2. Conformité Loi 18-07 : Consentement candidat, Révocation & Droit à l'oubli
# ---------------------------------------------------------------------------


@routeur.get("/conformite/texte-consentement")
def lire_texte_consentement_loi_18_07(
    _ctx: ContexteAuth = Depends(obtenir_contexte_auth),
    parametres: Parametres = Depends(obtenir_parametres),
) -> dict[str, str]:
    texte = service_conformite.TEXTE_CONSENTEMENT_LOI_18_07
    empreinte = hashlib.sha256(texte.encode("utf-8")).hexdigest()
    return {
        "version_consentement": parametres.version_consentement_loi_18_07,
        "texte_complet": texte,
        "empreinte_sha256": empreinte,
    }


@routeur.post(
    "/candidats/{candidat_id}/consentement",
    response_model=PreuveConsentementSortie,
    status_code=status.HTTP_201_CREATED,
)
def recueillir_consentement_candidat(
    candidat_id: uuid.UUID,
    donnees: ConsentementCandidatEntree,
    ctx: ContexteAuth = Depends(exiger_roles(Role.ADMINISTRATEUR, Role.EMPLOYE)),
    parametres: Parametres = Depends(obtenir_parametres),
) -> PreuveConsentementSortie:
    return service_conformite.enregistrer_consentement_candidat(
        ctx.db,
        candidat_id=candidat_id,
        donnees=donnees,
        acteur_id=ctx.utilisateur.id,
        parametres=parametres,
    )


@routeur.post(
    "/candidats/{candidat_id}/consentement/revoquer",
    response_model=PreuveConsentementSortie,
)
def revoquer_consentement_candidat(
    candidat_id: uuid.UUID,
    ctx: ContexteAuth = Depends(exiger_roles(Role.ADMINISTRATEUR, Role.EMPLOYE)),
) -> PreuveConsentementSortie:
    return service_conformite.revoquer_consentement_candidat(
        ctx.db,
        candidat_id=candidat_id,
        acteur_id=ctx.utilisateur.id,
    )


@routeur.get(
    "/candidats/{candidat_id}/consentements",
    response_model=list[PreuveConsentementSortie],
)
def lister_consentements_candidat(
    candidat_id: uuid.UUID,
    ctx: ContexteAuth = Depends(obtenir_contexte_auth),
) -> list[PreuveConsentementSortie]:
    return service_conformite.lister_preuves_consentement_candidat(
        ctx.db,
        candidat_id=candidat_id,
    )


@routeur.delete(
    "/candidats/{candidat_id}/suppression-definitive",
    status_code=status.HTTP_200_OK,
)
def supprimer_definitivement_candidat(
    candidat_id: uuid.UUID,
    ctx: ContexteAuth = Depends(exiger_roles(Role.ADMINISTRATEUR)),
    parametres: Parametres = Depends(obtenir_parametres),
) -> dict[str, int | str]:
    return service_conformite.supprimer_definitivement_dossier_candidat(
        ctx.db,
        candidat_id=candidat_id,
        acteur_id=ctx.utilisateur.id,
        parametres=parametres,
    )


@routeur.post(
    "/conformite/purger-archives-expirees",
    response_model=ResultatPurgeConservationSortie,
)
def purger_archives_expirees(
    ctx: ContexteAuth = Depends(exiger_roles(Role.ADMINISTRATEUR)),
    parametres: Parametres = Depends(obtenir_parametres),
) -> ResultatPurgeConservationSortie:
    return service_conformite.purger_dossiers_archives_expires(
        ctx.db,
        acteur_id=ctx.utilisateur.id,
        parametres=parametres,
    )


# ---------------------------------------------------------------------------
# 3. Sauvegardes chiffrées (AES-256-GCM) et vérification d'intégrité
# ---------------------------------------------------------------------------


@routeur.post(
    "/sauvegardes",
    response_model=SauvegardeChiffreeSortie,
    status_code=status.HTTP_201_CREATED,
)
def creer_sauvegarde_chiffree(
    ctx: ContexteAuth = Depends(exiger_roles(Role.ADMINISTRATEUR)),
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> SauvegardeChiffreeSortie:
    return service_sauvegardes.creer_sauvegarde_chiffree_bureau(
        ctx.db,
        acteur_id=ctx.utilisateur.id,
        parametres=parametres,
        cle_maitresse=cle_maitresse,
    )


@routeur.get(
    "/sauvegardes",
    response_model=list[SauvegardeChiffreeSortie],
)
def lister_sauvegardes(
    ctx: ContexteAuth = Depends(exiger_roles(Role.ADMINISTRATEUR)),
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> list[SauvegardeChiffreeSortie]:
    return service_sauvegardes.lister_sauvegardes_bureau(
        ctx.db,
        parametres=parametres,
        cle_maitresse=cle_maitresse,
    )


@routeur.get(
    "/sauvegardes/{nom_fichier}/verifier",
    response_model=VerificationSauvegardeSortie,
)
def verifier_sauvegarde(
    nom_fichier: str,
    ctx: ContexteAuth = Depends(exiger_roles(Role.ADMINISTRATEUR)),
    parametres: Parametres = Depends(obtenir_parametres),
    cle_maitresse: bytes = Depends(obtenir_cle_maitresse),
) -> VerificationSauvegardeSortie:
    return service_sauvegardes.verifier_integrite_sauvegarde(
        ctx.db,
        nom_fichier=nom_fichier,
        parametres=parametres,
        cle_maitresse=cle_maitresse,
    )
