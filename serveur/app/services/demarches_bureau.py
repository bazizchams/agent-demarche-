"""Gestion des démarches définies par chaque bureau (ajout et modification en ligne).

Une démarche du bureau complète ou remplace la démarche de base de même code (YAML).
Toute écriture est validée par `ConfigDemarche`, journalisée dans l'audit (sans contenu
personnel) et limitée au bureau courant par le filtre tenant.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.erreurs import Conflit, DonneesInvalides, NonTrouve
from app.modeles.demarche_bureau import DemarcheBureau
from app.modeles.journal_audit import ResultatAudit
from app.schemas.candidat import CandidatSortie
from app.services import audit
from app.services.pieces_requises import (
    ConfigDemarche,
    charger_demarches,
    charger_demarches_base,
)

_MOTIF_CODE = re.compile(r"^[a-z][a-z0-9_]{1,59}$")
TAILLE_MAX_DEFINITION_OCTETS = 200_000
MAX_ELEMENTS_PAR_LISTE = 300


def valider_code(code: str) -> str:
    propre = code.strip().lower()
    if propre == "gestion" or not _MOTIF_CODE.match(propre):
        raise DonneesInvalides(
            "Code de démarche invalide : lettres minuscules, chiffres et underscores, "
            "commençant par une lettre (2 à 60 caractères)."
        )
    return propre


def _valider_definition(definition: ConfigDemarche) -> dict:
    """Renvoie la définition sérialisable après contrôles de taille."""
    for nom, liste in (
        ("veille_reglementaire", definition.veille_reglementaire),
        ("champs_candidat_requis", definition.champs_candidat_requis),
        ("pieces_requises", definition.pieces_requises),
        ("etapes_tache", definition.etapes_tache),
        ("champs_conditionnels", definition.champs_conditionnels),
        ("echeances", definition.echeances),
        ("modeles_documents", definition.modeles_documents),
        ("frais", definition.frais),
    ):
        if len(liste) > MAX_ELEMENTS_PAR_LISTE:
            raise DonneesInvalides(
                f"Trop d'éléments dans « {nom} » (maximum {MAX_ELEMENTS_PAR_LISTE})."
            )
    for nom, codes in (
        ("échéance", [e.code for e in definition.echeances]),
        ("modèle de document", [m.code for m in definition.modeles_documents]),
        ("champ conditionnel", [c.champ for c in definition.champs_conditionnels]),
    ):
        if len(codes) != len(set(codes)):
            raise DonneesInvalides(f"Un même code de {nom} apparaît plusieurs fois.")
    champs_candidat = set(CandidatSortie.model_fields)
    conditions = [p.si for p in definition.pieces_requises if p.si is not None]
    conditions += [c.si for c in definition.champs_conditionnels]
    for cond in conditions:
        if cond.champ not in champs_candidat:
            raise DonneesInvalides(
                f"Champ de condition inconnu : « {cond.champ} » n'est pas un champ du candidat."
            )
    for c in definition.champs_conditionnels:
        if c.champ not in champs_candidat:
            raise DonneesInvalides(
                f"Champ conditionnel inconnu : « {c.champ} » n'est pas un champ du candidat."
            )
    types = [p.type_piece for p in definition.pieces_requises]
    if len(types) != len(set(types)):
        raise DonneesInvalides("Un même type de pièce apparaît plusieurs fois.")
    codes_etapes = [e.code for e in definition.etapes_tache]
    if len(codes_etapes) != len(set(codes_etapes)):
        raise DonneesInvalides("Un même code d'étape apparaît plusieurs fois.")
    donnees = definition.model_dump(mode="json")
    if len(json.dumps(donnees).encode("utf-8")) > TAILLE_MAX_DEFINITION_OCTETS:
        raise DonneesInvalides("La définition de la démarche est trop volumineuse.")
    return donnees


def _ligne(db: Session, code: str) -> DemarcheBureau | None:
    return db.scalar(select(DemarcheBureau).where(DemarcheBureau.code == code))


def obtenir(db: Session, dossier_base: Path, code: str) -> tuple[ConfigDemarche, dict]:
    """Démarche visible par le bureau + métadonnées (source, version, actif)."""
    code = valider_code(code)
    ligne = _ligne(db, code)
    if ligne is not None:
        if not ligne.actif:
            raise NonTrouve("Démarche inconnue.")
        meta = {"source": "bureau", "version": ligne.version, "actif": True}
        return ConfigDemarche.model_validate(ligne.definition), meta
    base = charger_demarches_base(dossier_base)
    if code not in base:
        raise NonTrouve("Démarche inconnue.")
    return base[code], {"source": "base", "version": 0, "actif": True}


def lister_metadonnees(db: Session, dossier_base: Path) -> list[dict]:
    """Liste complète (base + bureau) avec la source de chaque démarche."""
    visibles = charger_demarches(dossier_base, db)
    codes_bureau = {
        ligne.code: ligne for ligne in db.scalars(select(DemarcheBureau))
    }
    resultat: list[dict] = []
    for code, cfg in visibles.items():
        ligne = codes_bureau.get(code)
        resultat.append(
            {
                "code": code,
                "libelle": cfg.libelle,
                "source": "bureau" if ligne is not None else "base",
                "version": ligne.version if ligne is not None else 0,
                "actif": True,
            }
        )
    return resultat


def creer(
    db: Session,
    dossier_base: Path,
    definition: ConfigDemarche,
    acteur_id: uuid.UUID,
) -> DemarcheBureau:
    code = valider_code(definition.code)
    if _ligne(db, code) is not None:
        raise Conflit("Une démarche de ce bureau porte déjà ce code (utiliser la modification).")
    if code in charger_demarches_base(dossier_base):
        raise Conflit(
            "Ce code existe dans les démarches de base : utiliser la modification "
            "pour la personnaliser pour votre bureau."
        )
    donnees = _valider_definition(definition.model_copy(update={"code": code}))
    ligne = DemarcheBureau(code=code, version=1, actif=True, definition=donnees)
    db.add(ligne)
    audit.journaliser(
        db,
        "demarche.creation",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="demarche",
        details={"code": code, "version": 1},
    )
    db.commit()
    return ligne


def remplacer(
    db: Session,
    code: str,
    definition: ConfigDemarche,
    acteur_id: uuid.UUID,
    dossier_base: Path,
) -> DemarcheBureau:
    """Modifie la démarche du bureau (ou la crée en personnalisant une démarche de base)."""
    code = valider_code(code)
    if definition.code != code:
        raise DonneesInvalides("Le code du corps de la requête doit être identique à celui de l'URL.")
    donnees = _valider_definition(definition)
    ligne = _ligne(db, code)
    if ligne is None:
        if code not in charger_demarches_base(dossier_base):
            raise NonTrouve("Démarche inconnue.")
        ligne = DemarcheBureau(code=code, version=1, actif=True, definition=donnees)
        db.add(ligne)
    else:
        ligne.definition = donnees
        ligne.version += 1
        ligne.actif = True
    db.flush()
    audit.journaliser(
        db,
        "demarche.modification",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="demarche",
        ressource_id=ligne.id,
        details={"code": code, "version": ligne.version},
    )
    db.commit()
    return ligne


def desactiver(
    db: Session, code: str, acteur_id: uuid.UUID, dossier_base: Path
) -> None:
    """Masque la démarche pour ce bureau (jamais de suppression définitive)."""
    code = valider_code(code)
    ligne = _ligne(db, code)
    if ligne is None:
        base = charger_demarches_base(dossier_base)
        if code not in base:
            raise NonTrouve("Démarche inconnue.")
        ligne = DemarcheBureau(
            code=code,
            version=1,
            actif=False,
            definition=base[code].model_dump(mode="json"),
        )
        db.add(ligne)
    else:
        ligne.actif = False
        ligne.version += 1
    db.flush()
    audit.journaliser(
        db,
        "demarche.desactivation",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="demarche",
        ressource_id=ligne.id,
        details={"code": code},
    )
    db.commit()
