"""Schémas Pydantic v2 de la Phase 6 :
- Abonnements SaaS mensuels et facturation Stripe (`AbonnementBureauSortie`, `SessionCheckoutStripeSortie`)
- Conditions Générales d'Utilisation (`TexteCGUSortie`, `AcceptationCGUEntree`)
- Consentement des candidats selon la Loi algérienne 18-07 (`ConsentementCandidatEntree`, `PreuveConsentementSortie`)
- Politique de conservation et suppression définitive des données (`PolitiqueConservationEntree`, `ResultatPurgeConservationSortie`)
- Sauvegardes chiffrées AES-256-GCM (`SauvegardeChiffreeSortie`, `VerificationSauvegardeSortie`)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.modeles.abonnement import ForfaitAbonnement
from app.schemas.commun import SchemaEntree, SchemaSortie


class ForfaitCatalogueSortie(SchemaSortie):
    forfait: ForfaitAbonnement
    libelle: str
    prix_mensuel_eur: int
    quota_dossiers_mensuels: int


class AbonnementBureauSortie(SchemaSortie):
    id: uuid.UUID
    forfait: ForfaitAbonnement
    quota_dossiers_mensuels: int
    prix_mensuel_eur: int
    dossiers_actifs_ce_mois: int
    stripe_customer_id: str | None
    stripe_subscription_id: str | None
    statut_stripe: str
    periode_courante_fin: datetime | None
    cgu_version_acceptee: str | None
    cgu_acceptees_le: datetime | None
    cgu_acceptees_par_id: uuid.UUID | None
    duree_conservation_jours: int
    cree_le: datetime
    modifie_le: datetime


class ChangementForfaitEntree(SchemaEntree):
    forfait: ForfaitAbonnement


class SessionCheckoutStripeSortie(SchemaSortie):
    session_id: str
    url_checkout: str
    forfait: ForfaitAbonnement
    prix_mensuel_eur: int
    simulation: bool = False


class TexteCGUSortie(SchemaSortie):
    version_cgu: str
    texte_complet: str
    empreinte_sha256: str


class AcceptationCGUEntree(SchemaEntree):
    acceptation_explicite: bool
    version_cgu: str = Field(min_length=3, max_length=40)


class PolitiqueConservationEntree(SchemaEntree):
    duree_conservation_jours: int = Field(ge=30, le=3650)


class ConsentementCandidatEntree(SchemaEntree):
    consentement_explicite: bool
    mode_recueil: str = Field(
        default="formulaire_signe_bureau", min_length=3, max_length=60
    )


class PreuveConsentementSortie(SchemaSortie):
    id: uuid.UUID
    candidat_id: uuid.UUID
    version_texte_consentement: str
    mode_recueil: str
    empreinte_texte_sha256: str
    recueilli_par_id: uuid.UUID | None
    recueilli_le: datetime
    revoque_le: datetime | None


class ResultatPurgeConservationSortie(SchemaSortie):
    nb_dossiers_purges: int
    nb_fichiers_chiffres_supprimes: int
    duree_conservation_jours: int


class SauvegardeChiffreeSortie(SchemaSortie):
    nom_fichier: str
    taille_octets: int
    empreinte_sha256: str
    nb_candidats: int
    nb_documents: int
    cree_le: datetime


class VerificationSauvegardeSortie(SchemaSortie):
    nom_fichier: str
    integrite_valide: bool
    tenant_id: uuid.UUID
    nb_candidats: int
    nb_documents: int
    empreinte_sha256: str
