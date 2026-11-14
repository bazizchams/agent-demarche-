"""Génération de la lettre de motivation d'un vœu et enregistrement en brouillon.

- Les faits viennent du dossier (points forts confirmés, projet validé, fiche officielle, écart de profil)
  et de ceux fournis par l'agent (jamais inventés) ; aucune identité ne part
  au modèle. La signature « [Prénom NOM] » est remplacée ICI, localement.
- Le résultat est toujours enregistré en brouillon : l'agent relit et valide lui-même.
- Avec une clé API : un appel au modèle, compté dans le plafond mensuel du forfait.
  Sans clé : lettre modèle avec repères « [À COMPLÉTER ...] » (non validable tant qu'ils restent).
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.core.erreurs import DonneesInvalides
from app.modeles.journal_audit import ResultatAudit
from app.modeles.voeu_formation import MAX_CARACTERES_MOTIVATION
from app.services import audit
from app.services import candidats as service_candidats
from app.services import llm
from app.services import voeux as service_voeux
from app.services.anonymisation_ia import ClientAnonymisant, anonymiser
from app.services.lettres_adaptees import (
    RESERVE_MARQUEUR,
    SEUIL_SIMILARITE,
    avec_marqueur,
    construire_contexte,
    controler_lettre,
    similarite,
)
from app.services.lettres_motivation import FaitsParcours, generer_lettre_motivation
from app.services.llm import ClientLLM, ReponseLLM

SIGNATURE_A_REMPLACER = "[Prénom NOM]"


def _similaires(db: Session, candidat_id: uuid.UUID, voeu, texte: str, cle: bytes) -> list[str]:
    elements = []
    for autre in service_voeux._liste_orm(db, candidat_id):
        if autre.id == voeu.id:
            continue
        motivation = service_voeux._motivation_claire(autre, cle)
        if motivation and similarite(texte, motivation) >= SEUIL_SIMILARITE:
            elements.append(f"Lettre quasi identique à celle du vœu de rang {autre.rang} : à personnaliser.")
    return elements


def generer_lettre_pour_voeu(
    db: Session,
    client: ClientLLM | None,
    *,
    candidat_id: uuid.UUID,
    voeu_id: uuid.UUID,
    faits: FaitsParcours,
    acteur_id: uuid.UUID,
    cle_maitresse: bytes,
) -> dict[str, Any]:
    voeu = service_voeux._obtenir_voeu(db, candidat_id, voeu_id)  # 404 si introuvable
    candidat = service_candidats.obtenir_candidat(db, candidat_id=candidat_id, cle_maitresse=cle_maitresse)
    termes = (candidat.nom, candidat.prenom)
    if client is not None:
        llm.verifier_quota(db)
    signature = f"{candidat.prenom} {candidat.nom}"

    ctx = construire_contexte(db, candidat=candidat, voeu=voeu, faits_manuels=faits,
                              cle=cle_maitresse, aujourd_hui=date.today())
    marge_signature = max(0, len(signature) - len(SIGNATURE_A_REMPLACER))
    lettre = generer_lettre_motivation(
        ClientAnonymisant(client, termes) if client is not None else None,
        voeu=ctx.voeu, faits=ctx.faits,
        limite=ctx.limite - RESERVE_MARQUEUR - marge_signature,
    )
    if client is not None:
        llm.tracer_appel(
            db, acteur_id=acteur_id, fonction="lettre_motivation", reponse=ReponseLLM(texte="")
        )

    texte = anonymiser(lettre.texte, termes)  # sortie du modèle sans l'identité du candidat
    bloquants = ["Une donnée d'identité a été détectée et masquée dans le texte généré."] if texte != lettre.texte else []
    bloquants += controler_lettre(texte, ctx)
    texte = texte.replace(SIGNATURE_A_REMPLACER, signature)
    bloquants += _similaires(db, candidat_id, voeu, texte, cle_maitresse)
    texte = avec_marqueur(texte, bloquants)
    if len(texte) > min(ctx.limite + RESERVE_MARQUEUR, MAX_CARACTERES_MOTIVATION):
        raise DonneesInvalides(
            "La lettre dépasse la limite de caractères une fois la signature ajoutée : "
            "raccourcissez les faits fournis."
        )

    sortie = service_voeux.modifier_voeu(
        db,
        candidat_id=candidat_id,
        voeu_id=voeu_id,
        donnees={"motivation": texte},
        acteur_id=acteur_id,
        cle_maitresse=cle_maitresse,
    )
    audit.journaliser(
        db, "voeu.lettre_generer", ResultatAudit.SUCCES, acteur_id=acteur_id,
        ressource_type="voeu_formation", ressource_id=voeu_id,
        details={"origine": lettre.origine, "nb_bloquants": len(bloquants), "nb_faits_dossier": ctx.nb_faits_dossier,
                 "fiche_trouvee": ctx.fiche_trouvee, "limite": ctx.limite},
    )
    db.commit()
    return {
        "voeu": sortie,
        "elements_a_verifier": bloquants + ctx.elements_amont + list(lettre.elements_a_verifier),
        "origine": lettre.origine,
    }
