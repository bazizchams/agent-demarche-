"""Validation humaine d'un récapitulatif avant soumission officielle (Règle 1).

Principe : l'agent (ou un employé) PROPOSE un récapitulatif ; seul un humain authentifié
(administrateur ou employé) peut le VALIDER. Juste avant l'envoi, l'empreinte du contenu
réellement à envoyer est comparée à celle validée : toute différence invalide la validation.
Une validation n'autorise qu'UN seul envoi.

Branchement prévu (NON actif : l'arrêt avant le bouton final reste en vigueur) :
`app/agent_local/garde_fous.py::verifier_selecteur_non_interdit` bloque toujours le clic de
soumission finale. Quand la mise en œuvre sera activée, l'exécuteur (`executeur_playwright.py`)
appellera `exiger_validation_pour_envoi(db, validation_id, contenu_actuel)` juste avant ce
clic (au lieu de l'interdiction absolue), puis `marquer_envoyee(...)` après succès.

Audit (Règle 5) : uniquement des identifiants opaques, des codes et l'empreinte SHA-256.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.chiffrement import chiffrer_champ, dechiffrer_champ
from app.core.erreurs import AccesRefuse, Conflit, DonneesInvalides, NonTrouve
from app.db.base import maintenant_utc
from app.db.tenant import tenant_courant
from app.modeles.journal_audit import ResultatAudit
from app.modeles.utilisateur import Role, Utilisateur
from app.modeles.validation_recapitulatif import (
    StatutValidationRecapitulatif as Statut,
    ValidationRecapitulatif,
)
from app.services import audit
from app.services.candidats import obtenir_candidat_orm

NOM_CHAMP_CONTENU = "validations_recapitulatif.contenu"
CLE_CHAMPS_MANQUANTS = "champs_manquants"
RESSOURCE = "validation_recapitulatif"
ROLES_VALIDEURS = {Role.ADMINISTRATEUR, Role.EMPLOYE}


def calculer_empreinte(contenu: dict[str, Any]) -> str:
    """SHA-256 hexadécimal du JSON canonique (clés triées, sans espaces)."""
    canonique = json.dumps(contenu, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonique.encode("utf-8")).hexdigest()


def champs_manquants(contenu: dict[str, Any]) -> list[str]:
    valeur = contenu.get(CLE_CHAMPS_MANQUANTS) or []
    return [str(c) for c in valeur] if isinstance(valeur, list) else ["champs_manquants_invalide"]


def _tenant(db: Session) -> uuid.UUID:
    tid = tenant_courant(db)
    if tid is None:
        raise AccesRefuse("Bureau non défini pour cette session.")
    return tid


def obtenir(db: Session, validation_id: uuid.UUID) -> ValidationRecapitulatif:
    v = db.scalar(
        select(ValidationRecapitulatif).where(ValidationRecapitulatif.id == validation_id)
    )
    if v is None:
        raise NonTrouve("Validation de récapitulatif introuvable.")
    return v


def lister(
    db: Session, *, candidat_id: uuid.UUID | None = None, statut: Statut | None = None
) -> list[ValidationRecapitulatif]:
    requete = select(ValidationRecapitulatif).order_by(
        ValidationRecapitulatif.cree_le.desc(), ValidationRecapitulatif.id
    )
    if candidat_id is not None:
        requete = requete.where(ValidationRecapitulatif.candidat_id == candidat_id)
    if statut is not None:
        requete = requete.where(ValidationRecapitulatif.statut == statut)
    return list(db.scalars(requete).all())


def dechiffrer_contenu(
    db: Session, v: ValidationRecapitulatif, *, cle_maitresse: bytes
) -> dict[str, Any]:
    clair = dechiffrer_champ(cle_maitresse, _tenant(db), NOM_CHAMP_CONTENU, v.contenu_chiffre)
    return json.loads(clair or "{}")


def _tracer(
    db: Session, action: str, v: ValidationRecapitulatif, *, acteur_id: uuid.UUID | None,
    resultat: ResultatAudit = ResultatAudit.SUCCES, **details: Any,
) -> None:
    audit.journaliser(
        db, action, resultat, acteur_id=acteur_id, ressource_type=RESSOURCE,
        ressource_id=v.id,
        details={
            "empreinte": v.empreinte, "candidat_id": str(v.candidat_id),
            "portail": v.portail, "type_demarche": v.type_demarche, **details,
        },
    )


def proposer(
    db: Session,
    *,
    candidat_id: uuid.UUID,
    portail: str,
    type_demarche: str,
    contenu: dict[str, Any],
    cle_maitresse: bytes,
    acteur_id: uuid.UUID | None = None,
    par_agent: bool = False,
) -> ValidationRecapitulatif:
    """Crée une proposition `en_attente` ; invalide les propositions encore ouvertes
    (en attente ou validées, non envoyées) du même candidat / portail / démarche."""
    if not isinstance(contenu, dict) or not contenu:
        raise DonneesInvalides("Le récapitulatif à valider est vide.")
    obtenir_candidat_orm(db, candidat_id)  # 404 si candidat d'un autre bureau
    tid = _tenant(db)

    precedentes = db.scalars(
        select(ValidationRecapitulatif).where(
            ValidationRecapitulatif.candidat_id == candidat_id,
            ValidationRecapitulatif.portail == portail,
            ValidationRecapitulatif.type_demarche == type_demarche,
            ValidationRecapitulatif.statut.in_([Statut.EN_ATTENTE, Statut.VALIDEE]),
        )
    ).all()
    for ancienne in precedentes:
        ancienne.statut = Statut.INVALIDEE
        _tracer(db, "validation_recapitulatif.invalide", ancienne, acteur_id=acteur_id,
                motif="nouvelle_proposition")

    v = ValidationRecapitulatif(
        id=uuid.uuid4(), tenant_id=tid, candidat_id=candidat_id, portail=portail,
        type_demarche=type_demarche,
        contenu_chiffre=chiffrer_champ(
            cle_maitresse, tid, NOM_CHAMP_CONTENU,
            json.dumps(contenu, sort_keys=True, ensure_ascii=False, separators=(",", ":")),
        ),
        empreinte=calculer_empreinte(contenu), statut=Statut.EN_ATTENTE,
    )
    db.add(v)
    _tracer(db, "validation_recapitulatif.propose", v, acteur_id=acteur_id,
            auteur="agent" if par_agent else "humain",
            nb_champs_manquants=len(champs_manquants(contenu)))
    db.commit()
    return v


def _exiger_humain_valideur(
    db: Session, v: ValidationRecapitulatif, utilisateur: Utilisateur | None, action: str
) -> Utilisateur:
    """Règle 1 : jamais un agent, jamais un compte en lecture seule."""
    if utilisateur is None or utilisateur.role not in ROLES_VALIDEURS:
        audit.journaliser(
            db, f"validation_recapitulatif.{action}", ResultatAudit.REFUS,
            acteur_id=utilisateur.id if utilisateur else None,
            ressource_type=RESSOURCE, ressource_id=v.id,
            details={"motif": "acteur_non_autorise"},
        )
        db.commit()
        raise AccesRefuse(
            "Seul un employé ou un administrateur authentifié peut valider ou refuser "
            "un récapitulatif."
        )
    return utilisateur


def _exiger_en_attente(v: ValidationRecapitulatif) -> None:
    if v.statut != Statut.EN_ATTENTE:
        raise Conflit(f"Ce récapitulatif n'est plus en attente (statut : {v.statut.value}).")


def valider(
    db: Session, validation_id: uuid.UUID, *, utilisateur: Utilisateur | None,
    cle_maitresse: bytes,
) -> ValidationRecapitulatif:
    v = obtenir(db, validation_id)
    humain = _exiger_humain_valideur(db, v, utilisateur, "valide")
    _exiger_en_attente(v)
    manquants = champs_manquants(dechiffrer_contenu(db, v, cle_maitresse=cle_maitresse))
    if manquants:  # Règle 4 : jamais de valeur inventée
        raise DonneesInvalides(
            f"Récapitulatif non validable : {len(manquants)} champ(s) manquant(s) à compléter."
        )
    v.statut = Statut.VALIDEE
    v.validee_par = humain.id
    v.validee_le = maintenant_utc()
    _tracer(db, "validation_recapitulatif.valide", v, acteur_id=humain.id)
    db.commit()
    return v


def refuser(
    db: Session, validation_id: uuid.UUID, *, utilisateur: Utilisateur | None
) -> ValidationRecapitulatif:
    v = obtenir(db, validation_id)
    humain = _exiger_humain_valideur(db, v, utilisateur, "refuse")
    _exiger_en_attente(v)
    v.statut = Statut.REFUSEE
    v.validee_par = humain.id
    v.validee_le = maintenant_utc()
    _tracer(db, "validation_recapitulatif.refuse", v, acteur_id=humain.id)
    db.commit()
    return v


def verifier_avant_envoi(
    db: Session, validation_id: uuid.UUID, contenu_actuel: dict[str, Any]
) -> ValidationRecapitulatif:
    """À appeler juste avant l'envoi : exige statut `validee` ET contenu identique."""
    v = obtenir(db, validation_id)
    if v.statut != Statut.VALIDEE:
        raise AccesRefuse(
            f"Envoi refusé : le récapitulatif n'est pas validé (statut : {v.statut.value})."
        )
    if calculer_empreinte(contenu_actuel) != v.empreinte:
        v.statut = Statut.INVALIDEE
        _tracer(db, "validation_recapitulatif.invalide", v, acteur_id=None,
                motif="contenu_modifie_avant_envoi")
        db.commit()
        raise Conflit(
            "Envoi refusé : le contenu a changé depuis la validation humaine. "
            "Un nouveau récapitulatif doit être proposé et validé."
        )
    return v


def marquer_envoyee(
    db: Session, validation_id: uuid.UUID, *, acteur_id: uuid.UUID | None = None
) -> ValidationRecapitulatif:
    """Usage unique : seule une validation `validee` peut passer à `envoyee`."""
    v = obtenir(db, validation_id)
    if v.statut != Statut.VALIDEE:
        raise Conflit(
            f"Envoi impossible : validation non utilisable (statut : {v.statut.value})."
        )
    v.statut = Statut.ENVOYEE
    v.envoyee_le = maintenant_utc()
    _tracer(db, "validation_recapitulatif.envoye", v, acteur_id=acteur_id)
    db.commit()
    return v


def exiger_validation_pour_envoi(
    db: Session, validation_id: uuid.UUID | None, contenu_actuel: dict[str, Any]
) -> ValidationRecapitulatif:
    """GARDE DE SOUMISSION FINALE (Règle 1). À appeler avant toute action de soumission
    officielle ; lève une erreur métier si aucune validation humaine valable n'existe.
    Après l'envoi réussi, appeler `marquer_envoyee`."""
    if validation_id is None:
        raise AccesRefuse("Envoi refusé : aucune validation humaine du récapitulatif.")
    return verifier_avant_envoi(db, validation_id, contenu_actuel)
