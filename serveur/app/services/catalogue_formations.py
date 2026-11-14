"""Catalogue de fiches de formation d'un bureau (cache de ce qui a été lu sur les sources officielles).

- Multi-tenant strict : toute lecture/écriture passe par la session du bureau (filtre ORM + `tenant_id`).
- R4 : une exigence non lue reste inconnue ; la fiche est alors « à vérifier ».
- R5 : l'audit ne reçoit que des compteurs et des codes (jamais d'intitulé, ni de donnée de candidat).
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import RACINE_PLATEFORME
from app.core.erreurs import DonneesInvalides
from app.db.tenant import tenant_courant
from app.modeles.fiche_formation import FicheFormation, StatutFiche
from app.modeles.journal_audit import ResultatAudit
from app.services import audit
from app.services.transaction import commit_ou_conflit
from app.services.fiche_formation import (
    FicheEntree,
    cle_fiche,
    exigences_inconnues,
    fiches_depuis_yaml,
)

YAML_ECOLES_PRIVEES = RACINE_PLATEFORME / "config" / "catalogues" / "ecoles_privees_france.yaml"
MAX_FICHES_PAR_IMPORT = 500

_CHAMPS_COPIES = (
    "etablissement",
    "intitule",
    "niveau_entree_bac_plus",
    "niveau_entree_libelle",
    "francais_min",
    "anglais_min",
    "priorite_c1",
    "langue_texte",
    "langue_ambigue",
    "moyenne_min",
    "moyenne_reference",
    "date_limite",
    "ferme",
    "url_officielle",
    "date_releve",
    "source",
)


def _tenant(db: Session) -> uuid.UUID:
    tid = tenant_courant(db)
    if tid is None:
        raise RuntimeError("Contexte bureau (tenant) manquant sur la session.")
    return tid


def _appliquer(orm: FicheFormation, fiche: FicheEntree, *, conserver_confirmees: bool = False) -> None:
    if conserver_confirmees:
        # exigences « aucune » confirmées par un humain : écrasées seulement par un import manuel plus récent
        fiche = fiche.model_copy(update={"aucune_exigence_confirmee": list(orm.aucune_exigence_confirmee or [])})
    for champ in _CHAMPS_COPIES:
        setattr(orm, champ, getattr(fiche, champ))
    orm.pieces = list(fiche.pieces)
    orm.domaines = list(fiche.domaines)
    orm.aucune_exigence_confirmee = list(fiche.aucune_exigence_confirmee)
    orm.cle = cle_fiche(fiche.etablissement, fiche.intitule, fiche.niveau_entree_bac_plus)
    inconnues = exigences_inconnues(fiche)
    orm.exigences_a_verifier = inconnues
    orm.statut = StatutFiche.A_VERIFIER if inconnues else StatutFiche.VERIFIE


def enregistrer_fiches(
    db: Session, fiches: list[FicheEntree], *, acteur_id: uuid.UUID | None
) -> dict[str, int]:
    """Crée ou met à jour (clé : établissement + intitulé + niveau d'entrée) les fiches du bureau.

    Une fiche déjà présente n'est remplacée que par un relevé de date égale ou plus récente ; les exigences confirmées par un humain ne sont
    écrasées que par un import manuel strictement plus récent.
    """
    if len(fiches) > MAX_FICHES_PAR_IMPORT:
        raise DonneesInvalides(f"Import limité à {MAX_FICHES_PAR_IMPORT} fiches par appel.")
    tid = _tenant(db)
    existantes = {f.cle: f for f in db.scalars(select(FicheFormation))}
    crees = mises_a_jour = ignorees = 0
    sources: set[str] = set()
    for fiche in fiches:
        cle = cle_fiche(fiche.etablissement, fiche.intitule, fiche.niveau_entree_bac_plus)
        actuelle = existantes.get(cle)
        sources.add(fiche.source)
        if actuelle is None:
            orm = FicheFormation(tenant_id=tid)
            _appliquer(orm, fiche)
            db.add(orm)
            existantes[cle] = orm
            crees += 1
        elif fiche.date_releve >= actuelle.date_releve:
            plus_recente_manuelle = fiche.source == "manuel" and fiche.date_releve > actuelle.date_releve
            _appliquer(actuelle, fiche, conserver_confirmees=not plus_recente_manuelle)
            mises_a_jour += 1
        else:
            ignorees += 1
    audit.journaliser(
        db,
        "catalogue_formations.import",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="fiches_formations",
        details={
            "crees": crees,
            "mises_a_jour": mises_a_jour,
            "ignorees_plus_anciennes": ignorees,
            "sources": ",".join(sorted(sources)),
        },
    )
    commit_ou_conflit(db, "Import concurrent des mêmes fiches : réessayez.")
    return {"crees": crees, "mises_a_jour": mises_a_jour, "ignorees_plus_anciennes": ignorees}


def importer_ecoles_yaml(
    db: Session, *, acteur_id: uuid.UUID | None, chemin: Path = YAML_ECOLES_PRIVEES
) -> dict[str, int]:
    """Importe les écoles du YAML de référence (une fiche par formation citée)."""
    try:
        contenu: Any = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise DonneesInvalides("Catalogue d'écoles illisible.") from exc
    if not isinstance(contenu, dict):
        raise DonneesInvalides("Catalogue d'écoles invalide.")
    fiches = fiches_depuis_yaml(contenu)
    resultat = enregistrer_fiches(db, fiches, acteur_id=acteur_id)
    resultat["ecoles"] = len({f.etablissement for f in fiches})
    return resultat


def vers_entree(orm: FicheFormation) -> FicheEntree:
    return FicheEntree(
        **{champ: getattr(orm, champ) for champ in _CHAMPS_COPIES},
        pieces=list(orm.pieces or []),
        domaines=list(orm.domaines or []),
        aucune_exigence_confirmee=list(orm.aucune_exigence_confirmee or []),
    )


def charger_fiches(db: Session) -> list[tuple[uuid.UUID, FicheEntree]]:
    """Toutes les fiches du bureau courant (identifiant, fiche), en ordre stable."""
    tid = _tenant(db)
    lignes = db.scalars(
        select(FicheFormation)
        .where(FicheFormation.tenant_id == tid)
        .order_by(FicheFormation.etablissement, FicheFormation.intitule, FicheFormation.cle)
    ).all()
    return [(ligne.id, vers_entree(ligne)) for ligne in lignes]
