"""Chargement des référentiels YAML de démarches et calcul des pièces manquantes / expirées.

Règle 4 : tout champ requis non renseigné est signalé (jamais complété par défaut).
Règle 7 : la définition des démarches et des pièces requises vit dans `config/demarches/*.yaml`.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.core.erreurs import DonneesInvalides, NonTrouve
from app.modeles.document import DocumentCandidat
from app.schemas.candidat import CandidatSortie
from app.schemas.document import (
    DemarcheResumeSortie,
    EtatCompletudeDemarcheSortie,
    StatutPieceRequise,
    VerificationPieceSortie,
)


class ConfigPieceRequise(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type_piece: str = Field(min_length=1, max_length=80)
    libelle: str = Field(min_length=1, max_length=200)
    obligatoire: bool = True
    exige_date_expiration: bool = False
    validite_minimale_jours: int = Field(default=0, ge=0)


class ConfigPointVeille(BaseModel):
    model_config = ConfigDict(extra="forbid")

    titre: str = Field(min_length=1, max_length=200)
    resume: str = Field(min_length=1, max_length=1000)
    reference: str = Field(default="", max_length=200)


class ConfigEtapeDemarche(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=80)
    libelle: str = Field(min_length=1, max_length=200)


ETAPES_PAR_DEFAUT: list[ConfigEtapeDemarche] = [
    ConfigEtapeDemarche(
        code="verification_prerequis_dossier",
        libelle="Vérification des prérequis et de la validité des pièces",
    ),
    ConfigEtapeDemarche(
        code="ouverture_session_portail",
        libelle="Vérification de la session portail ouverte par l'opérateur",
    ),
    ConfigEtapeDemarche(
        code="preremplissage_formulaire",
        libelle="Pré-remplissage des champs et téléversement des pièces",
    ),
    ConfigEtapeDemarche(
        code="controle_avant_validation_humaine",
        libelle="Capture de contrôle et arrêt de sécurité avant soumission finale",
    ),
]


class ConfigDemarche(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=60)
    libelle: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=500)
    seuil_fonds_recommande_eur: int | None = Field(default=None, ge=0)
    veille_reglementaire: list[ConfigPointVeille] = Field(default_factory=list)
    champs_candidat_requis: list[str] = Field(default_factory=list)
    pieces_requises: list[ConfigPieceRequise] = Field(default_factory=list)
    etapes_tache: list[ConfigEtapeDemarche] = Field(
        default_factory=lambda: list(ETAPES_PAR_DEFAUT)
    )


def charger_demarches(dossier: Path) -> dict[str, ConfigDemarche]:
    if not dossier.exists():
        return {}
    demarches: dict[str, ConfigDemarche] = {}
    for fichier in sorted(dossier.glob("*.yaml")):
        brut = yaml.safe_load(fichier.read_text(encoding="utf-8"))
        cfg = ConfigDemarche.model_validate(brut)
        demarches[cfg.code] = cfg
    return demarches


def lister_demarches(dossier: Path) -> list[DemarcheResumeSortie]:
    demarches = charger_demarches(dossier)
    return [
        DemarcheResumeSortie(
            code=d.code,
            libelle=d.libelle,
            description=d.description,
            seuil_fonds_recommande_eur=d.seuil_fonds_recommande_eur,
            champs_candidat_requis=list(d.champs_candidat_requis),
            types_pieces_connus=[p.type_piece for p in d.pieces_requises],
        )
        for d in demarches.values()
    ]


def obtenir_demarche(dossier: Path, code: str) -> ConfigDemarche:
    demarches = charger_demarches(dossier)
    if code not in demarches:
        raise NonTrouve("Démarche inconnue.")
    return demarches[code]


def verifier_type_piece_autorise(dossier: Path, type_piece: str) -> str:
    """Normalise et vérifie le format de `type_piece` (identifiant technique snake_case)."""
    propre = type_piece.strip().lower()
    if not propre or not all(c.isalnum() or c == "_" for c in propre):
        raise DonneesInvalides(
            "Type de pièce invalide (utiliser un identifiant en minuscules et underscores, ex. 'passeport')."
        )
    return propre


def verifier_completude_dossier(
    *,
    candidat: CandidatSortie,
    documents: list[DocumentCandidat],
    demarche: ConfigDemarche,
    date_reference: date | None = None,
) -> EtatCompletudeDemarcheSortie:
    aujourdhui = date_reference or date.today()

    champs_manquants: list[str] = []
    for nom_champ in demarche.champs_candidat_requis:
        valeur = getattr(candidat, nom_champ, None)
        if valeur is None or (isinstance(valeur, str) and not valeur.strip()):
            champs_manquants.append(nom_champ)

    # Indexe le document le plus récent pour chaque type_piece
    par_type: dict[str, DocumentCandidat] = {}
    for doc in sorted(documents, key=lambda d: (d.cree_le, str(d.id))):
        par_type[doc.type_piece] = doc

    verifications: list[VerificationPieceSortie] = []
    pieces_ko: list[str] = []

    for regle in demarche.pieces_requises:
        doc = par_type.get(regle.type_piece)
        if doc is None:
            verifications.append(
                VerificationPieceSortie(
                    type_piece=regle.type_piece,
                    libelle=regle.libelle,
                    obligatoire=regle.obligatoire,
                    statut=StatutPieceRequise.MANQUANTE,
                    detail="Aucun document déposé pour ce type de pièce.",
                )
            )
            if regle.obligatoire:
                pieces_ko.append(regle.type_piece)
            continue

        date_exp = doc.date_expiration
        if date_exp is None and regle.type_piece == "passeport":
            date_exp = candidat.date_expiration_passeport

        if regle.exige_date_expiration and date_exp is None:
            verifications.append(
                VerificationPieceSortie(
                    type_piece=regle.type_piece,
                    libelle=regle.libelle,
                    obligatoire=regle.obligatoire,
                    statut=StatutPieceRequise.EXPIRATION_NON_RENSEIGNEE,
                    document_id=doc.id,
                    detail="La date d'expiration est obligatoire pour cette pièce.",
                )
            )
            pieces_ko.append(regle.type_piece)
            continue

        if date_exp is not None:
            if date_exp < aujourdhui:
                verifications.append(
                    VerificationPieceSortie(
                        type_piece=regle.type_piece,
                        libelle=regle.libelle,
                        obligatoire=regle.obligatoire,
                        statut=StatutPieceRequise.EXPIREE,
                        document_id=doc.id,
                        date_expiration=date_exp,
                        detail="Document expiré.",
                    )
                )
                pieces_ko.append(regle.type_piece)
                continue

            seuil = aujourdhui + timedelta(days=regle.validite_minimale_jours)
            if regle.validite_minimale_jours > 0 and date_exp < seuil:
                verifications.append(
                    VerificationPieceSortie(
                        type_piece=regle.type_piece,
                        libelle=regle.libelle,
                        obligatoire=regle.obligatoire,
                        statut=StatutPieceRequise.VALIDITE_INSUFFISANTE,
                        document_id=doc.id,
                        date_expiration=date_exp,
                        detail=(
                            f"Validité restante insuffisante (minimum requis : "
                            f"{regle.validite_minimale_jours} jours)."
                        ),
                    )
                )
                pieces_ko.append(regle.type_piece)
                continue

        verifications.append(
            VerificationPieceSortie(
                type_piece=regle.type_piece,
                libelle=regle.libelle,
                obligatoire=regle.obligatoire,
                statut=StatutPieceRequise.VALIDE,
                document_id=doc.id,
                date_expiration=date_exp,
            )
        )

    return EtatCompletudeDemarcheSortie(
        code_demarche=demarche.code,
        libelle_demarche=demarche.libelle,
        pret_pour_prerequis=(len(champs_manquants) == 0 and len(pieces_ko) == 0),
        champs_candidat_manquants=champs_manquants,
        pieces_manquantes_ou_invalides=pieces_ko,
        pieces=verifications,
    )
