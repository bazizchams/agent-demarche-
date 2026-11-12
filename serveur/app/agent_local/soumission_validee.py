"""Soumission officielle APRÈS validation humaine (Règle 1 réécrite).

Chemin explicite et unique par lequel l'agent peut cliquer un bouton de soumission finale.
Le blocage générique `garde_fous.verifier_selecteur_non_interdit` reste inchangé pour tous
les autres chemins (`cliquer_securise`, champs, téléversements, navigation...).

Ordre strict :
1. le sélecteur doit être un bouton de soumission finale DÉCLARÉ dans le YAML du portail
   (`selecteurs_soumission_interdits`) : aucun sélecteur arbitraire ne passe par ici ;
2. `exiger_validation_pour_envoi` (statut `validee` ET empreinte identique), puis exigence
   que la validation ait été donnée par un humain (`validee_par` renseigné) ;
3. domaine, session et absence de CAPTCHA/2FA juste avant le clic (Règle 2) ;
4. clic ; 5. `marquer_envoyee` seulement si le clic a réussi (usage unique).
Le contenu du récapitulatif n'est jamais journalisé (Règle 5).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from playwright.sync_api import Page
from sqlalchemy.orm import Session

from app.agent_local.config_portail import ConfigPortailYAML
from app.agent_local.garde_fous import (
    SuspensionRequiseParGardeFou,
    verifier_session_et_absence_captcha,
)
from app.core.erreurs import AccesRefuse
from app.modeles.tache import MotifSuspensionTache
from app.services import validation_recapitulatif as validations

journal = logging.getLogger("app.agent_local.soumission")


@dataclass(frozen=True)
class ResultatSoumission:
    validation_id: uuid.UUID
    empreinte: str
    envoyee: bool = True


def soumettre_apres_validation(
    page: Page,
    db: Session,
    validation_id: uuid.UUID | None,
    contenu_actuel: dict[str, Any],
    selecteur_final: str,
    config_portail: ConfigPortailYAML,
    *,
    code_etape: str = "soumission_finale",
) -> ResultatSoumission:
    """Clique le bouton final si, et seulement si, une validation humaine valable couvre
    exactement `contenu_actuel`. Lève `AccesRefuse` / `Conflit` (refus) ou
    `SuspensionRequiseParGardeFou` (CAPTCHA/2FA, session, sélecteur)."""
    declares = {s.strip() for s in config_portail.selecteurs_soumission_interdits}
    if selecteur_final.strip() not in declares:
        raise AccesRefuse(
            "Envoi refusé : le sélecteur n'est pas un bouton de soumission finale déclaré "
            "dans la configuration du portail."
        )

    validation = validations.exiger_validation_pour_envoi(db, validation_id, contenu_actuel)
    if validation.validee_par is None:  # jamais une validation sans humain identifié
        raise AccesRefuse("Envoi refusé : la validation ne provient pas d'un humain authentifié.")

    verifier_session_et_absence_captcha(page, config_portail, code_etape=code_etape)

    loc = page.locator(selecteur_final)
    if loc.count() == 0:
        raise SuspensionRequiseParGardeFou(
            motif=MotifSuspensionTache.SELECTEUR_PORTAIL_INTROUVABLE,
            message_alerte=f"Bouton d'envoi final introuvable : '{selecteur_final}' (règle 7).",
            code_etape=code_etape,
        )
    loc.first.click()  # seul clic de soumission finale autorisé, après validation

    validations.marquer_envoyee(db, validation.id, acteur_id=None)  # l'agent n'est pas un utilisateur
    journal.info("Soumission finale effectuée après validation humaine (empreinte %s).", validation.empreinte)
    return ResultatSoumission(validation_id=validation.id, empreinte=validation.empreinte)
