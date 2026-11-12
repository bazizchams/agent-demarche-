"""Accès au modèle Claude (API Messages d'Anthropic) pour les fonctions d'assistance IA.

- Le client est injectable (`ClientLLM`) : les tests utilisent un faux client, jamais le réseau.
- Aucune donnée personnelle ne doit être transmise ici : les appelants construisent un
  contexte anonymisé. Les corps de réponse de l'API ne sont jamais journalisés.
- Un plafond mensuel d'appels par bureau dépend du forfait d'abonnement ; chaque appel est
  tracé dans le journal d'audit (`ia.appel`, sans contenu).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

import httpx
from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Parametres, obtenir_parametres
from app.core.erreurs import LimiteAtteinte, ServiceIndisponible
from app.modeles.abonnement import AbonnementBureau, ForfaitAbonnement
from app.modeles.journal_audit import EntreeAudit, ResultatAudit
from app.services import audit

VERSION_API_ANTHROPIC = "2023-06-01"

# Appels IA par mois et par bureau, selon le forfait.
QUOTA_IA_MENSUEL: dict[ForfaitAbonnement, int] = {
    ForfaitAbonnement.STARTER: 100,
    ForfaitAbonnement.PROFESSIONNEL: 600,
    ForfaitAbonnement.ENTREPRISE: 3000,
}

# Plafond pendant la période d'essai gratuite, tous forfaits confondus.
QUOTA_IA_ESSAI = 30

ACTION_AUDIT_APPEL_IA = "ia.appel"


@dataclass(frozen=True)
class ReponseLLM:
    texte: str
    outil: dict[str, Any] | None = None
    tokens_entree: int = 0
    tokens_sortie: int = 0


class ClientLLM(Protocol):
    def generer(
        self,
        *,
        systeme: str,
        message: str,
        outil: dict[str, Any] | None = None,
        max_tokens: int = 4096,
    ) -> ReponseLLM: ...


class ClientAnthropic:
    def __init__(self, *, cle: str, modele: str, url: str, delai_secondes: int) -> None:
        self._cle = cle
        self._modele = modele
        self._url = url
        self._delai = delai_secondes

    def generer(
        self,
        *,
        systeme: str,
        message: str,
        outil: dict[str, Any] | None = None,
        max_tokens: int = 4096,
    ) -> ReponseLLM:
        corps: dict[str, Any] = {
            "model": self._modele,
            "max_tokens": max_tokens,
            "system": systeme,
            "messages": [{"role": "user", "content": message}],
        }
        if outil is not None:
            # Sortie structurée : le modèle est contraint de répondre via cet outil.
            corps["tools"] = [outil]
            corps["tool_choice"] = {"type": "tool", "name": outil["name"]}
        try:
            rep = httpx.post(
                self._url,
                headers={
                    "x-api-key": self._cle,
                    "anthropic-version": VERSION_API_ANTHROPIC,
                    "content-type": "application/json",
                },
                json=corps,
                timeout=self._delai,
            )
        except httpx.HTTPError as exc:
            raise ServiceIndisponible(
                "Le service d'IA est momentanément injoignable."
            ) from exc
        if rep.status_code in (401, 403):
            raise ServiceIndisponible(
                "La clé API du service d'IA est invalide ou non autorisée "
                "(à signaler à l'administrateur de la plateforme)."
            )
        if rep.status_code == 429 or rep.status_code >= 500:
            raise ServiceIndisponible(
                "Le service d'IA est saturé, réessayez dans un instant."
            )
        if rep.status_code != 200:
            raise ServiceIndisponible("Le service d'IA a refusé la demande.")
        try:
            donnees = rep.json()
        except ValueError as exc:
            raise ServiceIndisponible("Réponse illisible du service d'IA.") from exc
        if not isinstance(donnees, dict):
            raise ServiceIndisponible("Réponse illisible du service d'IA.")
        blocs = [b for b in (donnees.get("content") or []) if isinstance(b, dict)]
        texte = "".join(str(b.get("text", "")) for b in blocs if b.get("type") == "text")
        entree_outil = next((b.get("input") for b in blocs if b.get("type") == "tool_use"), None)
        usage = donnees.get("usage")
        if not isinstance(usage, dict):
            usage = {}
        return ReponseLLM(
            texte=texte.strip(),
            outil=entree_outil if isinstance(entree_outil, dict) else None,
            tokens_entree=int(usage.get("input_tokens", 0) or 0),
            tokens_sortie=int(usage.get("output_tokens", 0) or 0),
        )


def obtenir_client_llm(
    parametres: Parametres = Depends(obtenir_parametres),
) -> ClientLLM:
    """Dépendance FastAPI (remplaçable dans les tests par un faux client)."""
    if not parametres.cle_api_anthropic:
        raise ServiceIndisponible(
            "L'assistant IA n'est pas activé sur cette plateforme (clé API manquante)."
        )
    return ClientAnthropic(
        cle=parametres.cle_api_anthropic,
        modele=parametres.modele_llm,
        url=parametres.url_api_anthropic,
        delai_secondes=parametres.delai_llm_secondes,
    )


def obtenir_client_llm_optionnel(
    parametres: Parametres = Depends(obtenir_parametres),
) -> ClientLLM | None:
    """Comme `obtenir_client_llm`, mais renvoie None sans clé API (repli sur un modèle local)."""
    if not parametres.cle_api_anthropic:
        return None
    return obtenir_client_llm(parametres)


def _debut_du_mois() -> datetime:
    maintenant = datetime.now(timezone.utc)
    return maintenant.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def appels_ia_ce_mois(db: Session) -> int:
    return (
        db.scalar(
            select(func.count(EntreeAudit.id)).where(
                EntreeAudit.action == ACTION_AUDIT_APPEL_IA,
                EntreeAudit.horodatage >= _debut_du_mois(),
            )
        )
        or 0
    )


def plafond_ia(db: Session) -> int:
    """Plafond mensuel effectif du bureau courant. Pendant la période d'essai (ou sans
    abonnement enregistré), il est limité à `QUOTA_IA_ESSAI` quel que soit le forfait choisi :
    l'inscription est libre et les appels sont payés par la clé de la plateforme."""
    abo = db.scalar(select(AbonnementBureau))
    if abo is None:
        return min(QUOTA_IA_MENSUEL[ForfaitAbonnement.STARTER], QUOTA_IA_ESSAI)
    plafond = QUOTA_IA_MENSUEL[abo.forfait]
    if abo.statut_stripe == "trialing":
        plafond = min(plafond, QUOTA_IA_ESSAI)
    return plafond


def verifier_quota(db: Session) -> None:
    plafond = plafond_ia(db)
    if appels_ia_ce_mois(db) >= plafond:
        raise LimiteAtteinte(
            f"Plafond mensuel de {plafond} demandes à l'assistant IA atteint pour votre "
            "forfait. Passez à un forfait supérieur ou attendez le mois prochain."
        )


def tracer_appel(
    db: Session, *, acteur_id: uuid.UUID, fonction: str, reponse: ReponseLLM
) -> None:
    """Journalise l'appel (sans contenu). Le commit reste à l'appelant."""
    audit.journaliser(
        db,
        ACTION_AUDIT_APPEL_IA,
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="ia",
        details={
            "fonction": fonction,
            "tokens_entree": reponse.tokens_entree,
            "tokens_sortie": reponse.tokens_sortie,
        },
    )
