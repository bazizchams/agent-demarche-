"""Service d'import sécurisé d'un dossier candidat existant (format historique `etudiants/`).

Garde-fous issus de l'audit Phase 0 :
1. Vérifie que l'identité (`nom`, `prenom`) contenue dans `fiche_candidat.json` correspond
   au nom du dossier parent. Bloque immédiatement le cas découvert en Phase 0 où le dossier
   d'un vrai candidat contenait la fiche JSON copiée-collée de « KACI Salim ».
2. Ne devine JAMAIS le type d'une pièce par mot-clé dans le nom de fichier (défaut D3) :
   chaque fichier importé doit recevoir un `type_piece` explicite dans `correspondance_types`.
   Les fichiers non qualifiés sont signalés dans `fichiers_non_importes` sans être rattachés
   à l'aveugle.
3. N'invente aucune valeur par défaut (règle 4).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.chiffrement import normaliser_pour_index
from app.core.config import Parametres
from app.core.erreurs import DonneesInvalides
from app.modeles.candidat import SexeCandidat
from app.schemas.candidat import CandidatCreation, CandidatSortie
from app.schemas.document import DocumentSortie
from app.services.candidats import creer_candidat
from app.services.documents import deposer_document


@dataclass(frozen=True)
class ResultatImportDossier:
    candidat: CandidatSortie
    documents_importes: list[DocumentSortie]
    fichiers_non_importes: list[str]


def _analyser_date(valeur: str | None) -> date | None:
    if not valeur or not valeur.strip():
        return None
    texte = valeur.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texte, fmt).date()
        except ValueError:
            continue
    raise DonneesInvalides("Format de date invalide dans la fiche à importer (attendu JJ/MM/AAAA ou AAAA-MM-JJ).")


def verifier_coherence_nom_dossier(nom_dossier: str, nom: str, prenom: str) -> None:
    """Empêche d'importer une fiche JSON dont le nom/prénom ne correspond pas au dossier."""
    dossier_norm = normaliser_pour_index(nom_dossier.replace("_", " ").replace("-", " "))
    attendu_nom_prenom = normaliser_pour_index(f"{nom} {prenom}")
    attendu_prenom_nom = normaliser_pour_index(f"{prenom} {nom}")
    if dossier_norm not in {attendu_nom_prenom, attendu_prenom_nom}:
        raise DonneesInvalides(
            "Incohérence détectée : le nom du dossier ne correspond pas à l'identité "
            "présente dans fiche_candidat.json. Import bloqué par sécurité."
        )


def convertir_fiche_json_en_schema(
    donnees_brutes: dict[str, Any], *, nom_dossier: str | None = None
) -> CandidatCreation:
    nom = str(donnees_brutes.get("nom") or "").strip()
    prenom = str(donnees_brutes.get("prenom") or "").strip()
    if not nom or not prenom:
        raise DonneesInvalides("Les champs 'nom' et 'prenom' sont obligatoires dans la fiche.")

    if nom_dossier is not None:
        verifier_coherence_nom_dossier(nom_dossier, nom, prenom)

    sexe_brut = donnees_brutes.get("sexe")
    sexe = SexeCandidat(sexe_brut.upper()) if isinstance(sexe_brut, str) and sexe_brut.strip() else None

    fonds_brut = donnees_brutes.get("fonds_disponibles_eur")
    fonds = int(fonds_brut) if fonds_brut is not None else None

    return CandidatCreation(
        nom=nom,
        prenom=prenom,
        sexe=sexe,
        date_naissance=_analyser_date(donnees_brutes.get("date_naissance")),
        lieu_naissance=donnees_brutes.get("lieu_naissance") or None,
        nationalite=donnees_brutes.get("nationalite") or None,
        pays_residence=donnees_brutes.get("pays_residence") or None,
        email=donnees_brutes.get("email") or None,
        telephone=donnees_brutes.get("telephone") or None,
        numero_passeport=donnees_brutes.get("numero_passeport") or None,
        date_expiration_passeport=_analyser_date(
            donnees_brutes.get("date_expiration_passeport")
        ),
        niveau_actuel=donnees_brutes.get("niveau_actuel") or None,
        programme_vise=donnees_brutes.get("programme_vise") or None,
        etablissement_vise=donnees_brutes.get("etablissement_vise") or None,
        fonds_disponibles_eur=fonds,
    )


def importer_dossier_local(
    db: Session,
    *,
    chemin_dossier: Path,
    correspondance_types: dict[str, str],
    dates_expiration: dict[str, date] | None = None,
    remplacer_identite: CandidatCreation | None = None,
    acteur_id: uuid.UUID,
    parametres: Parametres,
    cle_maitresse: bytes,
) -> ResultatImportDossier:
    """Importe un dossier candidat depuis le disque local :
    - si `remplacer_identite` est fourni, l'utilise à la place d'une `fiche_candidat.json`
      absente ou erronée ;
    - sinon, lit `fiche_candidat.json` et vérifie sa cohérence avec le nom du dossier ;
    - n'importe que les fichiers explicitement qualifiés dans `correspondance_types`."""
    if not chemin_dossier.exists() or not chemin_dossier.is_dir():
        raise DonneesInvalides("Le dossier candidat à importer n'existe pas.")

    if remplacer_identite is not None:
        schema_creation = remplacer_identite
    else:
        chemin_fiche = chemin_dossier / "fiche_candidat.json"
        if not chemin_fiche.exists():
            raise DonneesInvalides(
                "Aucune fiche_candidat.json trouvée : veuillez fournir l'identité du candidat."
            )
        try:
            brut = json.loads(chemin_fiche.read_text(encoding="utf-8"))
        except Exception as exc:
            raise DonneesInvalides("Fichier fiche_candidat.json illisible.") from exc
        schema_creation = convertir_fiche_json_en_schema(
            brut, nom_dossier=chemin_dossier.name
        )

    candidat = creer_candidat(
        db,
        donnees=schema_creation,
        acteur_id=acteur_id,
        cle_maitresse=cle_maitresse,
    )

    exp_par_fichier = dates_expiration or {}
    importes: list[DocumentSortie] = []
    non_importes: list[str] = []

    for fichier in sorted(chemin_dossier.iterdir(), key=lambda p: p.name.lower()):
        if not fichier.is_file() or fichier.name.lower() == "fiche_candidat.json":
            continue
        type_piece = correspondance_types.get(fichier.name)
        if not type_piece:
            non_importes.append(fichier.name)
            continue
        doc = deposer_document(
            db,
            candidat_id=candidat.id,
            type_piece=type_piece,
            nom_fichier_origine=fichier.name,
            contenu_clair=fichier.read_bytes(),
            date_expiration=exp_par_fichier.get(fichier.name),
            acteur_id=acteur_id,
            parametres=parametres,
            cle_maitresse=cle_maitresse,
        )
        importes.append(doc)

    return ResultatImportDossier(
        candidat=candidat,
        documents_importes=importes,
        fichiers_non_importes=non_importes,
    )
