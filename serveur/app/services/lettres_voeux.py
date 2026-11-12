"""Génération de la lettre de motivation d'un vœu et enregistrement en brouillon.

- Les faits du parcours sont fournis par l'agent (jamais inventés) ; aucune identité ne part
  au modèle. La signature « [Prénom NOM] » est remplacée ICI, localement.
- Le résultat est toujours enregistré en brouillon : l'agent relit et valide lui-même.
- Avec une clé API : un appel au modèle, compté dans le plafond mensuel du forfait.
  Sans clé : lettre modèle avec repères « [À COMPLÉTER ...] » (non validable tant qu'ils restent).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.erreurs import DonneesInvalides
from app.modeles.voeu_formation import MAX_CARACTERES_MOTIVATION
from app.services import candidats as service_candidats
from app.services import llm
from app.services import voeux as service_voeux
from app.services.lettres_motivation import (
    FaitsParcours,
    VoeuPourLettre,
    generer_lettre_motivation,
)
from app.services.llm import ClientLLM, ReponseLLM

SIGNATURE_A_REMPLACER = "[Prénom NOM]"


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
    if client is not None:
        llm.verifier_quota(db)

    lettre = generer_lettre_motivation(
        client,
        voeu=VoeuPourLettre(
            intitule=voeu.intitule,
            etablissement=voeu.etablissement,
            niveau=voeu.niveau,
            justification=voeu.justification,
        ),
        faits=faits,
    )
    if client is not None:
        llm.tracer_appel(
            db, acteur_id=acteur_id, fonction="lettre_motivation", reponse=ReponseLLM(texte="")
        )

    candidat = service_candidats.obtenir_candidat(
        db, candidat_id=candidat_id, cle_maitresse=cle_maitresse
    )
    texte = lettre.texte.replace(SIGNATURE_A_REMPLACER, f"{candidat.prenom} {candidat.nom}")
    if len(texte) > MAX_CARACTERES_MOTIVATION:
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
    return {
        "voeu": sortie,
        "elements_a_verifier": list(lettre.elements_a_verifier),
        "origine": lettre.origine,
    }
