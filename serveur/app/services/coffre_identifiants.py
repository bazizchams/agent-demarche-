"""Coffre d'identifiants portail (regle 3).

- Identifiant et mot de passe sont chiffres (AES-256-GCM, cle du bureau) ; jamais en clair,
  jamais dans les journaux, l'audit, les exceptions ou les reponses d'API.
- `lire_pour_agent` est la SEULE fonction qui dechiffre : usage interne de l'agent au moment
  de la connexion, jamais exposee par une route.
- Regle 5 : l'audit ne contient que des identifiants opaques, le code du portail et l'acteur.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.chiffrement import chiffrer_champ, dechiffrer_champ
from app.core.erreurs import DonneesInvalides, NonTrouve
from app.db.base import maintenant_utc
from app.db.tenant import tenant_courant
from app.modeles.coffre_identifiants import (
    CHAMP_IDENTIFIANT,
    CHAMP_MOT_DE_PASSE,
    IdentifiantPortail,
)
from app.modeles.journal_audit import ResultatAudit
from app.services import audit
from app.services.candidats import obtenir_candidat_orm

PORTAILS_AUTORISES = ("etudes_en_france", "ircc")
LONGUEUR_MAX_SECRET = 500


@dataclass(frozen=True)
class IdentifiantsClairs:
    """Identifiants dechiffres, a usage interne de l'agent. repr/str sans secret."""

    identifiant: str = field(repr=False)
    mot_de_passe: str = field(repr=False)

    def __repr__(self) -> str:
        return "IdentifiantsClairs(<masque>)"

    __str__ = __repr__


def _tenant(db: Session) -> uuid.UUID:
    tid = tenant_courant(db)
    if tid is None:
        raise RuntimeError("Contexte bureau (tenant) manquant sur la session.")
    return tid


def _verifier_portail(portail: str) -> str:
    if portail not in PORTAILS_AUTORISES:
        raise DonneesInvalides(
            "Portail inconnu (valeurs possibles : " + ", ".join(PORTAILS_AUTORISES) + ")."
        )
    return portail


def _auditer(
    db: Session, action: str, acteur_id: uuid.UUID | None, ressource_id: uuid.UUID, details: dict
) -> None:
    audit.journaliser(
        db,
        action,
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="identifiant_portail",
        ressource_id=ressource_id,
        details=details,
    )


def _obtenir(db: Session, candidat_id: uuid.UUID, portail: str) -> IdentifiantPortail | None:
    return db.scalar(
        select(IdentifiantPortail).where(
            IdentifiantPortail.candidat_id == candidat_id,
            IdentifiantPortail.portail == portail,
        )
    )


def enregistrer(
    db: Session,
    *,
    candidat_id: uuid.UUID,
    portail: str,
    identifiant: str,
    mot_de_passe: str,
    consentement: bool,
    acteur_id: uuid.UUID,
    cle_maitresse: bytes,
) -> dict[str, Any]:
    """Cree ou remplace les identifiants d'un portail. Le consentement du candidat est obligatoire."""
    if consentement is not True:
        raise DonneesInvalides(
            "Le consentement écrit du candidat est obligatoire pour enregistrer ses identifiants."
        )
    _verifier_portail(portail)
    if not identifiant or not mot_de_passe:
        raise DonneesInvalides("L'identifiant et le mot de passe du portail sont obligatoires.")
    if len(identifiant) > LONGUEUR_MAX_SECRET or len(mot_de_passe) > LONGUEUR_MAX_SECRET:
        raise DonneesInvalides("Valeur trop longue.")
    tid = _tenant(db)
    obtenir_candidat_orm(db, candidat_id)  # 404 si inconnu ou d'un autre bureau

    identifiant_chiffre = chiffrer_champ(cle_maitresse, tid, CHAMP_IDENTIFIANT, identifiant)
    mot_de_passe_chiffre = chiffrer_champ(cle_maitresse, tid, CHAMP_MOT_DE_PASSE, mot_de_passe)
    maintenant = maintenant_utc()

    ligne = _obtenir(db, candidat_id, portail)
    action = "coffre.mise_a_jour"
    if ligne is None:
        action = "coffre.cree"
        ligne = IdentifiantPortail(
            id=uuid.uuid4(),
            tenant_id=tid,
            candidat_id=candidat_id,
            portail=portail,
            identifiant_chiffre=identifiant_chiffre,
            mot_de_passe_chiffre=mot_de_passe_chiffre,
            consentement_recueilli_le=maintenant,
            consentement_par=acteur_id,
        )
        db.add(ligne)
    else:
        ligne.identifiant_chiffre = identifiant_chiffre
        ligne.mot_de_passe_chiffre = mot_de_passe_chiffre
        ligne.consentement_recueilli_le = maintenant
        ligne.consentement_par = acteur_id
    db.flush()
    _auditer(
        db, action, acteur_id, ligne.id, {"candidat_id": str(candidat_id), "portail": portail}
    )
    db.commit()
    return _statut_de(ligne)


def _statut_de(ligne: IdentifiantPortail) -> dict[str, Any]:
    return {
        "portail": ligne.portail,
        "existe": True,
        "consentement_recueilli_le": ligne.consentement_recueilli_le,
        "cree_le": ligne.cree_le,
        "mis_a_jour_le": ligne.mis_a_jour_le,
    }


def statut(db: Session, *, candidat_id: uuid.UUID, portail: str) -> dict[str, Any]:
    """Existence et dates uniquement : JAMAIS la valeur des identifiants."""
    _verifier_portail(portail)
    obtenir_candidat_orm(db, candidat_id)
    ligne = _obtenir(db, candidat_id, portail)
    if ligne is None:
        return {
            "portail": portail,
            "existe": False,
            "consentement_recueilli_le": None,
            "cree_le": None,
            "mis_a_jour_le": None,
        }
    return _statut_de(ligne)


def lire_pour_agent(
    db: Session,
    *,
    candidat_id: uuid.UUID,
    portail: str,
    cle_maitresse: bytes,
    acteur_id: uuid.UUID | None = None,
) -> IdentifiantsClairs:
    """SEULE fonction qui dechiffre. Reservee a l'agent, au moment de la connexion au portail.
    Ne jamais exposer son resultat par une route, un log ou un message d'erreur."""
    _verifier_portail(portail)
    tid = _tenant(db)
    obtenir_candidat_orm(db, candidat_id)
    ligne = _obtenir(db, candidat_id, portail)
    if ligne is None:
        raise NonTrouve("Aucun identifiant enregistré pour ce portail.")
    clairs = IdentifiantsClairs(
        identifiant=dechiffrer_champ(cle_maitresse, tid, CHAMP_IDENTIFIANT, ligne.identifiant_chiffre),
        mot_de_passe=dechiffrer_champ(
            cle_maitresse, tid, CHAMP_MOT_DE_PASSE, ligne.mot_de_passe_chiffre
        ),
    )
    _auditer(
        db,
        "coffre.utilise",
        acteur_id,
        ligne.id,
        {"candidat_id": str(candidat_id), "portail": portail},
    )
    db.commit()
    return clairs


def supprimer(
    db: Session, *, candidat_id: uuid.UUID, portail: str, acteur_id: uuid.UUID
) -> None:
    _verifier_portail(portail)
    obtenir_candidat_orm(db, candidat_id)
    ligne = _obtenir(db, candidat_id, portail)
    if ligne is None:
        raise NonTrouve("Aucun identifiant enregistré pour ce portail.")
    id_ligne = ligne.id
    db.delete(ligne)
    db.flush()
    _auditer(
        db,
        "coffre.supprime",
        acteur_id,
        id_ligne,
        {"candidat_id": str(candidat_id), "portail": portail},
    )
    db.commit()


def supprimer_tout_candidat(
    db: Session, *, candidat_id: uuid.UUID, acteur_id: uuid.UUID | None, valider: bool = True
) -> int:
    """Supprime tous les identifiants du candidat (revocation, suppression du dossier).
    Avec `valider=False`, l'appelant garde la main sur le commit (meme transaction)."""
    lignes = list(
        db.scalars(
            select(IdentifiantPortail).where(IdentifiantPortail.candidat_id == candidat_id)
        ).all()
    )
    for ligne in lignes:
        id_ligne, portail = ligne.id, ligne.portail
        db.delete(ligne)
        db.flush()
        _auditer(
            db,
            "coffre.supprime",
            acteur_id,
            id_ligne,
            {"candidat_id": str(candidat_id), "portail": portail},
        )
    if valider:
        db.commit()
    return len(lignes)
