"""Voeux de formation (panier Campus France) : creation, edition, validation, suppression.

- Regle 4 : aucune motivation n'est generee ni inventee ; un voeu sans motivation ne se valide pas.
- Regle 5 : l'audit ne contient que des codes et identifiants (jamais de motivation, nom, etc.).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.chiffrement import chiffrer_champ, dechiffrer_champ
from app.core.erreurs import Conflit, DonneesInvalides, NonTrouve
from app.db.tenant import tenant_courant
from app.modeles.journal_audit import ResultatAudit
from app.modeles.voeu_formation import (
    MAX_CARACTERES_MOTIVATION,
    MAX_VOEUX,
    StatutVoeu,
    VoeuFormation,
    VoieVoeu,
)
from app.services import audit
from app.services.candidats import obtenir_candidat_orm

CHAMP_MOTIVATION = "motivation_voeu"
MARQUEURS_A_COMPLETER = ("[à compléter", "[prénom nom]")
_CHAMPS_TEXTE_MODIFIABLES = ("intitule", "etablissement", "niveau", "url_source", "justification")


def _tenant(db: Session) -> uuid.UUID:
    tid = tenant_courant(db)
    if tid is None:
        raise RuntimeError("Contexte bureau (tenant) manquant sur la session.")
    return tid


def _verifier_motivation(texte: str | None) -> str | None:
    if texte is None:
        return None
    if len(texte) > MAX_CARACTERES_MOTIVATION:
        raise DonneesInvalides(
            f"La motivation dépasse {MAX_CARACTERES_MOTIVATION} caractères."
        )
    return texte


def _motivation_claire(voeu: VoeuFormation, cle_maitresse: bytes) -> str | None:
    return dechiffrer_champ(
        cle_maitresse, voeu.tenant_id, CHAMP_MOTIVATION, voeu.motivation_chiffree
    )


def _liste_orm(db: Session, candidat_id: uuid.UUID) -> list[VoeuFormation]:
    return list(
        db.scalars(
            select(VoeuFormation)
            .where(VoeuFormation.candidat_id == candidat_id)
            .order_by(VoeuFormation.rang, VoeuFormation.cree_le)
        ).all()
    )


def vers_dict(voeu: VoeuFormation, cle_maitresse: bytes) -> dict[str, Any]:
    motivation = _motivation_claire(voeu, cle_maitresse)
    return {
        "id": voeu.id,
        "candidat_id": voeu.candidat_id,
        "rang": voeu.rang,
        "intitule": voeu.intitule,
        "etablissement": voeu.etablissement,
        "niveau": voeu.niveau,
        "voie": voeu.voie,
        "url_source": voeu.url_source,
        "justification": voeu.justification,
        "motivation": motivation,
        "nb_caracteres_motivation": len(motivation) if motivation else 0,
        "statut": voeu.statut,
        "cree_le": voeu.cree_le,
        "modifie_le": voeu.modifie_le,
    }


def _obtenir_voeu(db: Session, candidat_id: uuid.UUID, voeu_id: uuid.UUID) -> VoeuFormation:
    obtenir_candidat_orm(db, candidat_id)  # 404 si inconnu ou d'un autre bureau
    voeu = db.scalar(
        select(VoeuFormation).where(
            VoeuFormation.id == voeu_id, VoeuFormation.candidat_id == candidat_id
        )
    )
    if voeu is None:
        raise NonTrouve("Voeu introuvable.")
    return voeu


def _auditer(
    db: Session, action: str, acteur_id: uuid.UUID, voeu_id: uuid.UUID, details: dict[str, Any]
) -> None:
    audit.journaliser(
        db,
        action,
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="voeu_formation",
        ressource_id=voeu_id,
        details=details,
    )


def lister_voeux(db: Session, candidat_id: uuid.UUID, cle_maitresse: bytes) -> list[dict[str, Any]]:
    obtenir_candidat_orm(db, candidat_id)
    return [vers_dict(v, cle_maitresse) for v in _liste_orm(db, candidat_id)]


def creer_voeu(
    db: Session,
    *,
    candidat_id: uuid.UUID,
    donnees: dict[str, Any],
    acteur_id: uuid.UUID,
    cle_maitresse: bytes,
) -> dict[str, Any]:
    tid = _tenant(db)
    obtenir_candidat_orm(db, candidat_id)
    existants = _liste_orm(db, candidat_id)
    if len(existants) >= MAX_VOEUX:
        raise Conflit(f"Le panier est limité à {MAX_VOEUX} voeux.")
    if any(
        v.intitule == donnees["intitule"] and v.etablissement == donnees["etablissement"]
        for v in existants
    ):
        raise Conflit("Ce voeu existe déjà pour ce candidat.")
    motivation = _verifier_motivation(donnees.get("motivation"))
    voeu = VoeuFormation(
        tenant_id=tid,
        candidat_id=candidat_id,
        rang=len(existants) + 1,
        intitule=donnees["intitule"],
        etablissement=donnees["etablissement"],
        niveau=donnees["niveau"],
        voie=donnees.get("voie") or VoieVoeu.HORS_DAP,
        url_source=donnees.get("url_source"),
        justification=donnees.get("justification"),
        motivation_chiffree=chiffrer_champ(cle_maitresse, tid, CHAMP_MOTIVATION, motivation),
        statut=StatutVoeu.BROUILLON,
    )
    db.add(voeu)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise Conflit("Ce voeu existe déjà pour ce candidat.") from exc
    _auditer(
        db,
        "voeu.creation",
        acteur_id,
        voeu.id,
        {"candidat_id": str(candidat_id), "rang": voeu.rang, "voie": voeu.voie.value},
    )
    db.commit()
    return vers_dict(voeu, cle_maitresse)


def modifier_voeu(
    db: Session,
    *,
    candidat_id: uuid.UUID,
    voeu_id: uuid.UUID,
    donnees: dict[str, Any],
    acteur_id: uuid.UUID,
    cle_maitresse: bytes,
) -> dict[str, Any]:
    """`donnees` ne contient que les champs fournis (exclude_unset)."""
    voeu = _obtenir_voeu(db, candidat_id, voeu_id)
    tid = voeu.tenant_id
    champs: list[str] = []
    remise_brouillon = False

    for nom in _CHAMPS_TEXTE_MODIFIABLES:
        if nom in donnees:
            if donnees[nom] != getattr(voeu, nom):
                champs.append(nom)
                if nom in ("intitule", "etablissement"):
                    remise_brouillon = True
            setattr(voeu, nom, donnees[nom])
    if "voie" in donnees and donnees["voie"] is not None:
        if donnees["voie"] != voeu.voie:
            champs.append("voie")
        voeu.voie = donnees["voie"]
    if "motivation" in donnees:
        motivation = _verifier_motivation(donnees["motivation"])
        if motivation != _motivation_claire(voeu, cle_maitresse):
            champs.append("motivation")
            remise_brouillon = True
        voeu.motivation_chiffree = chiffrer_champ(cle_maitresse, tid, CHAMP_MOTIVATION, motivation)

    if remise_brouillon:
        voeu.statut = StatutVoeu.BROUILLON

    if "rang" in donnees and donnees["rang"] is not None and donnees["rang"] != voeu.rang:
        autres = [v for v in _liste_orm(db, candidat_id) if v.id != voeu.id]
        position = min(max(donnees["rang"], 1), len(autres) + 1)
        autres.insert(position - 1, voeu)
        for i, v in enumerate(autres, start=1):
            v.rang = i
        champs.append("rang")

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise Conflit("Ce voeu existe déjà pour ce candidat.") from exc
    _auditer(
        db,
        "voeu.modification",
        acteur_id,
        voeu.id,
        {"candidat_id": str(candidat_id), "champs": ",".join(champs), "statut": voeu.statut.value},
    )
    db.commit()
    return vers_dict(voeu, cle_maitresse)


def valider_voeu(
    db: Session,
    *,
    candidat_id: uuid.UUID,
    voeu_id: uuid.UUID,
    acteur_id: uuid.UUID,
    cle_maitresse: bytes,
) -> dict[str, Any]:
    voeu = _obtenir_voeu(db, candidat_id, voeu_id)
    if voeu.statut != StatutVoeu.BROUILLON:
        raise Conflit("Seul un voeu au statut brouillon peut être validé.")
    motivation = _motivation_claire(voeu, cle_maitresse)
    if not motivation or not motivation.strip():
        raise DonneesInvalides("Une motivation non vide est nécessaire pour valider le voeu.")
    # Règle 4 : une lettre qui contient encore des repères à remplir ne part jamais au portail.
    if any(m in motivation.lower() for m in MARQUEURS_A_COMPLETER):
        raise DonneesInvalides(
            "La motivation contient encore des repères à remplir ([À COMPLÉTER ...] ou "
            "[Prénom NOM]). Complétez-les avant de valider."
        )
    voeu.statut = StatutVoeu.VALIDE
    _auditer(db, "voeu.validation", acteur_id, voeu.id, {"candidat_id": str(candidat_id)})
    db.commit()
    return vers_dict(voeu, cle_maitresse)


def marquer_ajoute_au_panier(
    db: Session,
    *,
    candidat_id: uuid.UUID,
    voeu_id: uuid.UUID,
    acteur_id: uuid.UUID,
    cle_maitresse: bytes,
) -> dict[str, Any]:
    voeu = _obtenir_voeu(db, candidat_id, voeu_id)
    if voeu.statut != StatutVoeu.VALIDE:
        raise Conflit("Seul un voeu validé peut être marqué comme ajouté au panier.")
    voeu.statut = StatutVoeu.AJOUTE_AU_PANIER
    _auditer(db, "voeu.ajout_panier", acteur_id, voeu.id, {"candidat_id": str(candidat_id)})
    db.commit()
    return vers_dict(voeu, cle_maitresse)


def supprimer_voeu(
    db: Session, *, candidat_id: uuid.UUID, voeu_id: uuid.UUID, acteur_id: uuid.UUID
) -> None:
    voeu = _obtenir_voeu(db, candidat_id, voeu_id)
    id_voeu, rang = voeu.id, voeu.rang
    db.delete(voeu)
    db.flush()
    for i, v in enumerate(_liste_orm(db, candidat_id), start=1):
        v.rang = i
    _auditer(
        db,
        "voeu.suppression",
        acteur_id,
        id_voeu,
        {"candidat_id": str(candidat_id), "rang": rang},
    )
    db.commit()


def lister_voeux_pour_panier(
    db: Session, candidat_id: uuid.UUID, cle_maitresse: bytes
) -> list[dict[str, Any]]:
    """Voeux prets pour le panier (valides ou deja ajoutes), tries par rang."""
    return [
        {
            "voeu_id": v.id,
            "rang": v.rang,
            "intitule": v.intitule,
            "etablissement": v.etablissement,
            "niveau": v.niveau,
            "voie": v.voie.value,
            "motivation": _motivation_claire(v, cle_maitresse),
        }
        for v in _liste_orm(db, candidat_id)
        if v.statut in (StatutVoeu.VALIDE, StatutVoeu.AJOUTE_AU_PANIER)
    ]
