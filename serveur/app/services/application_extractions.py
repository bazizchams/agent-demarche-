"""Application des valeurs lues à la fiche du candidat.

Garanties (règles 1, 4 et 5) :
- seules les extractions `auto` ou `valide_humain` sont applicables ; `a_verifier` et `rejete`
  ne le sont jamais ;
- une valeur déjà présente sur la fiche n'est JAMAIS écrasée : une valeur différente est
  signalée comme conflit, une valeur identique comme « déjà identique » ;
- deux valeurs applicables différentes pour un même champ sont un conflit, pas un choix ;
- la fiche reste un BROUILLON : rien n'est soumis ; la validation humaine du récapitulatif
  (règle 1) intervient en aval. Le rapport ne contient aucune valeur.

Remarque : le modèle `Candidat` n'a que les statuts `actif` et `archive` ; il n'existe pas de
statut « brouillon » distinct (voir le rapport de livraison).
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.chiffrement import dechiffrer_champ, normaliser_pour_index
from app.core.erreurs import Conflit
from app.db.base import maintenant_utc
from app.modeles.candidat import SexeCandidat
from app.modeles.extraction_document import STATUTS_APPLICABLES, ExtractionDocument, StatutExtraction
from app.modeles.journal_audit import ResultatAudit
from app.schemas.candidat import CandidatModification, CandidatSortie
from app.schemas.extraction import ChampAppliqueSortie, ConflitApplicationSortie, RapportApplicationSortie
from app.services import audit
from app.services.candidats import modifier_candidat, obtenir_candidat
from app.services.extractions import _AAD_VALEUR
from app.services.extraction_champs import (
    DATE_EXPIRATION_PASSEPORT,
    DATE_NAISSANCE,
    NIVEAU_ANGLAIS,
    NIVEAU_FRANCAIS,
    NOM,
    NUMERO_PASSEPORT,
    PRENOM,
    SEXE,
)

# Champ lu -> champ de la fiche candidat (même nom).
CHAMPS_FICHE = (NOM, PRENOM, DATE_NAISSANCE, SEXE, NUMERO_PASSEPORT, DATE_EXPIRATION_PASSEPORT, NIVEAU_FRANCAIS, NIVEAU_ANGLAIS)
_CHAMPS_IDENTITE_TEXTE = (NOM, PRENOM)


def _convertir(champ: str, valeur: str) -> Any:
    if champ in (DATE_NAISSANCE, DATE_EXPIRATION_PASSEPORT):
        return date.fromisoformat(valeur)
    if champ == SEXE:
        return SexeCandidat(valeur)
    if champ in (NIVEAU_FRANCAIS, NIVEAU_ANGLAIS):
        return valeur.upper()
    return valeur


def _identiques(champ: str, actuelle: Any, proposee: Any) -> bool:
    if isinstance(actuelle, SexeCandidat):
        actuelle = actuelle.value
    if isinstance(proposee, SexeCandidat):
        proposee = proposee.value
    if champ in _CHAMPS_IDENTITE_TEXTE:
        return normaliser_pour_index(str(actuelle)) == normaliser_pour_index(str(proposee))
    if champ == NUMERO_PASSEPORT:
        return str(actuelle).replace(" ", "").upper() == str(proposee).replace(" ", "").upper()
    return actuelle == proposee


def _vide(valeur: Any) -> bool:
    return valeur is None or (isinstance(valeur, str) and not valeur.strip())


def _appliquer_modification(
    db: Session, *, candidat_id: uuid.UUID, champs: dict[str, Any], acteur_id: uuid.UUID, cle: bytes
) -> bool:
    """Applique les champs ; renvoie False si le numéro de passeport est déjà pris (rien d'écrit)."""
    if not champs:
        return True
    try:
        modifier_candidat(
            db,
            candidat_id=candidat_id,
            donnees=CandidatModification(**champs),
            acteur_id=acteur_id,
            cle_maitresse=cle,
        )
    except Conflit:
        db.rollback()
        return False
    return True


def appliquer_extractions_a_fiche(
    db: Session, *, candidat_id: uuid.UUID, acteur_id: uuid.UUID, cle_maitresse: bytes
) -> RapportApplicationSortie:
    fiche: CandidatSortie = obtenir_candidat(db, candidat_id=candidat_id, cle_maitresse=cle_maitresse)
    lignes = list(
        db.scalars(
            select(ExtractionDocument)
            .where(ExtractionDocument.candidat_id == candidat_id)
            .order_by(ExtractionDocument.cree_le, ExtractionDocument.champ)
        )
    )
    a_verifier_restants = sum(e.statut is StatutExtraction.A_VERIFIER for e in lignes)
    candidates = [
        e for e in lignes if e.statut in STATUTS_APPLICABLES and e.applique_le is None
    ]
    hors_fiche = sorted({e.champ for e in candidates if e.champ not in CHAMPS_FICHE})

    par_champ: dict[str, list[ExtractionDocument]] = {}
    for e in candidates:
        if e.champ in CHAMPS_FICHE:
            par_champ.setdefault(e.champ, []).append(e)

    appliques: list[tuple[str, ExtractionDocument, Any]] = []
    conflits: list[ConflitApplicationSortie] = []
    deja_identiques: list[str] = []
    for champ, extractions in par_champ.items():
        valeurs = [
            _convertir(champ, dechiffrer_champ(cle_maitresse, e.tenant_id, _AAD_VALEUR, e.valeur_chiffree) or "")
            for e in extractions
        ]
        if any(not _identiques(champ, valeurs[0], v) for v in valeurs[1:]):
            conflits.append(ConflitApplicationSortie(champ=champ, extraction_id=extractions[0].id, raison="valeurs_multiples"))
            continue
        actuelle = getattr(fiche, champ)
        if _vide(actuelle):
            appliques.append((champ, extractions[0], valeurs[0]))
        elif _identiques(champ, actuelle, valeurs[0]):
            deja_identiques.append(champ)
        else:
            conflits.append(ConflitApplicationSortie(champ=champ, extraction_id=extractions[0].id, raison="fiche_deja_renseignee"))

    champs_a_ecrire = {champ: valeur for champ, _, valeur in appliques}
    if not _appliquer_modification(
        db, candidat_id=candidat_id, champs=champs_a_ecrire, acteur_id=acteur_id, cle=cle_maitresse
    ):
        # Numéro de passeport déjà utilisé par un autre candidat du bureau : on l'écarte et on réessaie.
        ecarte = next(e for c, e, _ in appliques if c == NUMERO_PASSEPORT)
        conflits.append(ConflitApplicationSortie(champ=NUMERO_PASSEPORT, extraction_id=ecarte.id, raison="passeport_deja_utilise"))
        appliques = [a for a in appliques if a[0] != NUMERO_PASSEPORT]
        champs_a_ecrire.pop(NUMERO_PASSEPORT, None)
        _appliquer_modification(db, candidat_id=candidat_id, champs=champs_a_ecrire, acteur_id=acteur_id, cle=cle_maitresse)

    maintenant = maintenant_utc()
    for champ, extraction, _ in appliques:
        for e in par_champ[champ]:
            e.applique_le = maintenant
    audit.journaliser(
        db,
        "extraction.appliquer",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="candidat",
        ressource_id=candidat_id,
        details={
            "nb_appliques": len(appliques),
            "nb_conflits": len(conflits),
            "nb_a_verifier_restants": a_verifier_restants,
        },
    )
    db.commit()
    return RapportApplicationSortie(
        appliques=[ChampAppliqueSortie(champ=c, extraction_id=e.id) for c, e, _ in appliques],
        conflits=conflits,
        deja_identiques=sorted(deja_identiques),
        hors_fiche=hors_fiche,
        a_verifier_restants=a_verifier_restants,
    )
