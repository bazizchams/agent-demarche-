"""Chargement des référentiels YAML de démarches et calcul des pièces manquantes / expirées.

Règle 4 : tout champ requis non renseigné est signalé (jamais complété par défaut).
Règle 7 : la définition des démarches et des pièces requises vit dans `config/demarches/*.yaml`.
"""

from __future__ import annotations

import enum
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.erreurs import DonneesInvalides, NonTrouve
from app.db.tenant import tenant_courant
from app.modeles.demarche_bureau import DemarcheBureau
from app.modeles.document import DocumentCandidat
from app.schemas.candidat import CandidatSortie
from app.schemas.document import (
    DemarcheResumeSortie,
    EtatCompletudeDemarcheSortie,
    StatutPieceRequise,
    VerificationPieceSortie,
)


OPERATEURS_CONDITION = (
    "egal",
    "different",
    "contient",
    "renseigne",
    "non_renseigne",
    "superieur_ou_egal",
    "inferieur",
)
_OPERATEURS_SANS_VALEUR = ("renseigne", "non_renseigne")


class ConditionSimple(BaseModel):
    """Condition portant sur un champ de la fiche candidat (CandidatSortie)."""

    model_config = ConfigDict(extra="forbid")

    champ: str = Field(min_length=1, max_length=80)
    operateur: Literal[
        "egal",
        "different",
        "contient",
        "renseigne",
        "non_renseigne",
        "superieur_ou_egal",
        "inferieur",
    ]
    valeur: str | int | None = None

    @model_validator(mode="after")
    def _valeur_coherente(self) -> "ConditionSimple":
        if self.operateur not in _OPERATEURS_SANS_VALEUR and self.valeur is None:
            raise ValueError(f"L'opérateur « {self.operateur} » exige une valeur.")
        if isinstance(self.valeur, str) and len(self.valeur) > 200:
            raise ValueError("Valeur de condition trop longue (200 caractères maximum).")
        return self


def _normaliser_texte(texte: str) -> str:
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c)
    )
    return " ".join(sans_accents.casefold().split())


def _valeur_candidat(candidat: CandidatSortie, champ: str):
    valeur = getattr(candidat, champ, None)
    if isinstance(valeur, enum.Enum):
        valeur = valeur.value
    if isinstance(valeur, str) and not valeur.strip():
        return None
    return valeur


def _comparable(valeur) -> float | None:
    if isinstance(valeur, bool):
        return None
    if isinstance(valeur, (int, float)):
        return float(valeur)
    if isinstance(valeur, (date, datetime)):
        return None
    if isinstance(valeur, str):
        try:
            return float(valeur.strip().replace(",", "."))
        except ValueError:
            return None
    return None


def evaluer_condition(condition: ConditionSimple, candidat: CandidatSortie) -> bool | None:
    """Vrai / faux, ou None si la condition est indéterminée (champ candidat vide
    avec un opérateur autre que renseigne / non_renseigne, ou valeurs non comparables)."""
    valeur = _valeur_candidat(candidat, condition.champ)
    op = condition.operateur
    if op == "renseigne":
        return valeur is not None
    if op == "non_renseigne":
        return valeur is None
    if valeur is None:
        return None
    attendu = condition.valeur
    if op in ("superieur_ou_egal", "inferieur"):
        if isinstance(valeur, (date, datetime)):
            try:
                ref = date.fromisoformat(str(attendu)[:10])
            except ValueError:
                return None
            courant = valeur.date() if isinstance(valeur, datetime) else valeur
            return courant >= ref if op == "superieur_ou_egal" else courant < ref
        gauche, droite = _comparable(valeur), _comparable(attendu)
        if gauche is None or droite is None:
            return None
        return gauche >= droite if op == "superieur_ou_egal" else gauche < droite
    texte_candidat = _normaliser_texte(str(valeur))
    texte_attendu = _normaliser_texte(str(attendu))
    if op == "egal":
        return texte_candidat == texte_attendu
    if op == "different":
        return texte_candidat != texte_attendu
    return texte_attendu in texte_candidat  # contient


def _resoudre_condition(
    condition: ConditionSimple | None, candidat: CandidatSortie
) -> tuple[bool, str | None]:
    """(exigee, note). Indéterminé => exigée par prudence, avec une note."""
    if condition is None:
        return True, None
    resultat = evaluer_condition(condition, candidat)
    if resultat is None:
        return True, (
            f"Condition indéterminée (champ « {condition.champ} » non renseigné) : "
            "pièce exigée par prudence."
        )
    return resultat, None


class ConfigPieceRequise(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type_piece: str = Field(min_length=1, max_length=80)
    libelle: str = Field(min_length=1, max_length=200)
    obligatoire: bool = True
    exige_date_expiration: bool = False
    validite_minimale_jours: int = Field(default=0, ge=0)
    si: ConditionSimple | None = None


class ConfigChampConditionnel(BaseModel):
    """Champ candidat requis seulement si la condition est vraie."""

    model_config = ConfigDict(extra="forbid")

    champ: str = Field(min_length=1, max_length=80)
    si: ConditionSimple


class ConfigEcheance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=60)
    libelle: str = Field(min_length=1, max_length=200)
    date_fixe: date | None = None
    jours_avant_reference: int | None = Field(default=None, ge=-3650, le=3650)
    reference: Literal["rentree", "depot"] | None = None
    rappel_jours_avant: list[int] = Field(default_factory=lambda: [30, 7, 1], max_length=20)

    @model_validator(mode="after")
    def _coherence(self) -> "ConfigEcheance":
        relative = self.jours_avant_reference is not None or self.reference is not None
        if self.date_fixe is not None and relative:
            raise ValueError("Une échéance est soit à date fixe, soit relative à une référence.")
        if self.date_fixe is None:
            if self.jours_avant_reference is None or self.reference is None:
                raise ValueError(
                    "Une échéance exige une date fixe, ou jours_avant_reference et reference."
                )
        if any(r < 0 for r in self.rappel_jours_avant):
            raise ValueError("Les rappels sont des nombres de jours positifs ou nuls.")
        return self


class ConfigModeleDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=60)
    libelle: str = Field(min_length=1, max_length=200)
    type: Literal["lettre_motivation", "cv", "lettre_explicative", "courriel", "autre"] = "autre"
    consignes: str = Field(default="", max_length=2000)
    longueur_max_caracteres: int | None = Field(default=None, ge=1, le=100_000)
    obligatoire: bool = False


class ConfigFrais(BaseModel):
    model_config = ConfigDict(extra="forbid")

    libelle: str = Field(min_length=1, max_length=200)
    montant: float = Field(ge=0)
    devise: str = Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    beneficiaire: str | None = Field(default=None, max_length=200)
    moment: str | None = Field(default=None, max_length=200)


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
    champs_conditionnels: list[ConfigChampConditionnel] = Field(default_factory=list)
    echeances: list[ConfigEcheance] = Field(default_factory=list)
    modeles_documents: list[ConfigModeleDocument] = Field(default_factory=list)
    instructions_agent: str | None = Field(default=None, max_length=4000)
    frais: list[ConfigFrais] = Field(default_factory=list)


def charger_demarches_base(dossier: Path) -> dict[str, ConfigDemarche]:
    """Démarches de base communes à tous les bureaux (fichiers YAML)."""
    if not dossier.exists():
        return {}
    demarches: dict[str, ConfigDemarche] = {}
    for fichier in sorted(dossier.glob("*.yaml")):
        brut = yaml.safe_load(fichier.read_text(encoding="utf-8"))
        cfg = ConfigDemarche.model_validate(brut)
        demarches[cfg.code] = cfg
    return demarches


def charger_demarches(
    dossier: Path, db: Session | None = None
) -> dict[str, ConfigDemarche]:
    """Démarches visibles par le bureau courant : base YAML, puis celles du bureau.

    Sans session (ou sans bureau défini), seules les démarches de base sont renvoyées.
    Une démarche du bureau remplace la démarche de base de même code ; si elle est
    désactivée, elle est retirée de la liste pour ce bureau.
    """
    demarches = charger_demarches_base(dossier)
    if db is None or tenant_courant(db) is None:
        return demarches
    for ligne in db.scalars(select(DemarcheBureau).order_by(DemarcheBureau.code)):
        if not ligne.actif:
            demarches.pop(ligne.code, None)
            continue
        demarches[ligne.code] = ConfigDemarche.model_validate(ligne.definition)
    return demarches


def lister_demarches(
    dossier: Path, db: Session | None = None
) -> list[DemarcheResumeSortie]:
    demarches = charger_demarches(dossier, db)
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


def obtenir_demarche(
    dossier: Path, code: str, db: Session | None = None
) -> ConfigDemarche:
    demarches = charger_demarches(dossier, db)
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
    champs_non_applicables: list[str] = []
    champs_a_verifier = list(demarche.champs_candidat_requis)
    for cc in demarche.champs_conditionnels:
        exigee, _note = _resoudre_condition(cc.si, candidat)
        if exigee:
            if cc.champ not in champs_a_verifier:
                champs_a_verifier.append(cc.champ)
        else:
            champs_non_applicables.append(cc.champ)
    for nom_champ in champs_a_verifier:
        valeur = getattr(candidat, nom_champ, None)
        if valeur is None or (isinstance(valeur, str) and not valeur.strip()):
            champs_manquants.append(nom_champ)

    # Indexe le document le plus récent pour chaque type_piece
    par_type: dict[str, DocumentCandidat] = {}
    for doc in sorted(documents, key=lambda d: (d.cree_le, str(d.id))):
        par_type[doc.type_piece] = doc

    verifications: list[VerificationPieceSortie] = []
    pieces_ko: list[str] = []
    pieces_non_applicables: list[str] = []
    notes_indeterminees: dict[str, str] = {}

    for regle in demarche.pieces_requises:
        exigee, note = _resoudre_condition(regle.si, candidat)
        if not exigee:
            pieces_non_applicables.append(regle.type_piece)
            verifications.append(
                VerificationPieceSortie(
                    type_piece=regle.type_piece,
                    libelle=regle.libelle,
                    obligatoire=False,
                    statut=StatutPieceRequise.NON_APPLICABLE,
                    detail="Non applicable : la condition de cette pièce n'est pas remplie.",
                )
            )
            continue
        if note:
            notes_indeterminees[regle.type_piece] = note
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

    if notes_indeterminees:
        verifications = [
            v.model_copy(
                update={"detail": f"{v.detail} {notes_indeterminees[v.type_piece]}".strip()}
            )
            if v.type_piece in notes_indeterminees
            else v
            for v in verifications
        ]

    return EtatCompletudeDemarcheSortie(
        code_demarche=demarche.code,
        libelle_demarche=demarche.libelle,
        pret_pour_prerequis=(len(champs_manquants) == 0 and len(pieces_ko) == 0),
        champs_candidat_manquants=champs_manquants,
        pieces_manquantes_ou_invalides=pieces_ko,
        pieces=verifications,
        pieces_non_applicables=pieces_non_applicables,
        champs_non_applicables=champs_non_applicables,
    )
