"""Accès au modèle Claude (API Messages d'Anthropic) pour les fonctions d'assistance IA.

- Le client est injectable (`ClientLLM`) : les tests utilisent un faux client, jamais le réseau.
- Aucune donnée personnelle ne doit être transmise ici : les appelants construisent un
  contexte anonymisé. Les corps de réponse de l'API ne sont jamais journalisés.
- Un plafond mensuel d'appels par bureau dépend du forfait d'abonnement ; chaque appel est
  tracé dans le journal d'audit (`ia.appel`, sans contenu).
"""

from __future__ import annotations

import base64
import ipaddress
import json
import time
import uuid
from urllib.parse import urlparse
from dataclasses import dataclass
from datetime import datetime, timezone
from collections.abc import Sequence
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
from app.services.anonymisation_ia import ClientAnonymisant

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
class ImageEntree:
    """Image transmise à un modèle de vision. Elle contient des données personnelles : seul un
    client LOCAL l'accepte (`ClientOpenAICompatible` vers un hôte local)."""

    octets: bytes
    type_mime: str


MESSAGE_IMAGE_REFUSEE = (
    "Envoi d'image refusé : une image contient des données personnelles et ne peut être "
    "transmise qu'à un modèle de vision exécuté en local (hôte local ou réseau privé)."
)


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
        images: Sequence[ImageEntree] | None = None,
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
        images: Sequence[ImageEntree] | None = None,
    ) -> ReponseLLM:
        if images:  # service hébergé chez un tiers : jamais d'image (données personnelles)
            raise ServiceIndisponible(MESSAGE_IMAGE_REFUSEE)
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


def _pause(secondes: float) -> None:
    """Attente entre deux tentatives (remplaçable dans les tests)."""
    time.sleep(secondes)


def _extraire_objet_json(texte: str) -> dict[str, Any] | None:
    """Extrait un objet JSON d'un texte libre (modèles sans appel d'outil natif)."""
    debut, fin = texte.find("{"), texte.rfind("}")
    if debut < 0 or fin <= debut:
        return None
    try:
        objet = json.loads(texte[debut : fin + 1])
    except ValueError:
        return None
    return objet if isinstance(objet, dict) else None


class ClientOpenAICompatible:
    """Client de l'API « chat/completions » compatible OpenAI : Ollama, llama.cpp, Groq,
    Gemini, Mistral, OpenRouter, etc. La clé est facultative (modèle local). Elle n'apparaît
    jamais dans les erreurs ni les journaux ; les corps de réponse non plus."""

    def __init__(
        self,
        *,
        url_base: str,
        modele: str,
        cle: str | None = None,
        delai_secondes: int = 90,
        tentatives: int = 2,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._url = url_base.rstrip("/") + "/chat/completions"
        self._modele = modele
        self._cle = cle or None
        self._delai = delai_secondes
        self._tentatives = max(1, tentatives)
        self._transport = transport

    def _envoyer(self, corps: dict[str, Any]) -> httpx.Response:
        entetes = {"content-type": "application/json"}
        if self._cle:
            entetes["authorization"] = f"Bearer {self._cle}"
        derniere: ServiceIndisponible | None = None
        for essai in range(self._tentatives):
            if essai:
                _pause(min(0.5 * 2 ** (essai - 1), 8.0))
            try:
                with httpx.Client(transport=self._transport, timeout=self._delai) as http:
                    rep = http.post(self._url, headers=entetes, json=corps)
            except httpx.HTTPError:
                # Le message de l'exception httpx n'est jamais repris (il peut contenir l'URL).
                derniere = ServiceIndisponible("Le service d'IA est momentanément injoignable.")
                continue
            if rep.status_code == 429 or rep.status_code >= 500:
                derniere = ServiceIndisponible(
                    "Le service d'IA est saturé, réessayez dans un instant."
                )
                continue
            return rep
        assert derniere is not None
        raise derniere

    def generer(
        self,
        *,
        systeme: str,
        message: str,
        outil: dict[str, Any] | None = None,
        max_tokens: int = 4096,
        images: Sequence[ImageEntree] | None = None,
    ) -> ReponseLLM:
        contenu_utilisateur: str | list[dict[str, Any]] = message
        if images:
            if not hote_est_local(self._url):  # contrôle à la source, avant tout appel réseau
                raise ServiceIndisponible(MESSAGE_IMAGE_REFUSEE)
            contenu_utilisateur = [{"type": "text", "text": message}] + [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{img.type_mime};base64,"
                        + base64.b64encode(img.octets).decode("ascii")
                    },
                }
                for img in images
            ]
        corps: dict[str, Any] = {
            "model": self._modele,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": systeme},
                {"role": "user", "content": contenu_utilisateur},
            ],
        }
        if outil is not None:
            corps["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": outil["name"],
                        "description": outil.get("description", ""),
                        "parameters": outil["input_schema"],
                    },
                }
            ]
            corps["tool_choice"] = {"type": "function", "function": {"name": outil["name"]}}
        rep = self._envoyer(corps)
        if rep.status_code == 400 and outil is not None:
            # Modèle sans appel d'outil : on redemande une réponse JSON dans le texte.
            corps.pop("tools")
            corps.pop("tool_choice")
            corps["messages"][0]["content"] = (
                systeme
                + "\n\nRéponds UNIQUEMENT par un objet JSON valide conforme à ce schéma, "
                "sans texte autour :\n"
                + json.dumps(outil["input_schema"], ensure_ascii=False)
            )
            rep = self._envoyer(corps)
        if rep.status_code in (401, 403):
            raise ServiceIndisponible(
                "La clé API du service d'IA est invalide ou non autorisée "
                "(à signaler à l'administrateur de la plateforme)."
            )
        if rep.status_code != 200:
            raise ServiceIndisponible("Le service d'IA a refusé la demande.")
        return self._lire_reponse(rep, avec_outil=outil is not None)

    @staticmethod
    def _lire_reponse(rep: httpx.Response, *, avec_outil: bool) -> ReponseLLM:
        try:
            donnees = rep.json()
        except ValueError as exc:
            raise ServiceIndisponible("Réponse illisible du service d'IA.") from exc
        choix = donnees.get("choices") if isinstance(donnees, dict) else None
        if not isinstance(choix, list) or not choix or not isinstance(choix[0], dict):
            raise ServiceIndisponible("Réponse illisible du service d'IA.")
        msg = choix[0].get("message")
        if not isinstance(msg, dict):
            raise ServiceIndisponible("Réponse illisible du service d'IA.")
        contenu = msg.get("content")
        texte = contenu.strip() if isinstance(contenu, str) else ""
        entree_outil: dict[str, Any] | None = None
        appels = msg.get("tool_calls")
        if isinstance(appels, list) and appels and isinstance(appels[0], dict):
            args = (appels[0].get("function") or {}).get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = None
            entree_outil = args if isinstance(args, dict) else None
        if avec_outil and entree_outil is None and texte:
            entree_outil = _extraire_objet_json(texte)
        usage = donnees.get("usage")
        if not isinstance(usage, dict):
            usage = {}
        return ReponseLLM(
            texte=texte,
            outil=entree_outil,
            tokens_entree=int(usage.get("prompt_tokens", 0) or 0),
            tokens_sortie=int(usage.get("completion_tokens", 0) or 0),
        )


FOURNISSEUR_ANTHROPIC = "anthropic"
FOURNISSEUR_OPENAI = "openai_compatible"


def hote_est_local(url: str) -> bool:
    """Vrai si l'URL vise cette machine ou le réseau privé (les données ne quittent pas
    le serveur de la plateforme / du bureau)."""
    hote = (urlparse(url).hostname or "").lower()
    if hote in ("localhost", "host.docker.internal", "ollama") or hote.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(hote)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


@dataclass(frozen=True)
class EtatIA:
    fournisseur: str
    active: bool
    modele: str | None
    donnees_quittent_serveur: bool
    message: str


def etat_ia(parametres: Parametres) -> EtatIA:
    """Décrit l'IA configurée, sans jamais exposer la clé ni le chemin complet de l'URL."""
    four = (parametres.ia_fournisseur or FOURNISSEUR_ANTHROPIC).strip().lower()
    if four == FOURNISSEUR_ANTHROPIC:
        if not parametres.cle_api_anthropic:
            return EtatIA(four, False, None, False, "IA désactivée : clé Anthropic non configurée.")
        return EtatIA(
            four, True, parametres.modele_llm, True,
            f"IA Anthropic ({parametres.modele_llm}) : le texte, anonymisé, est envoyé à un "
            "tiers hors du serveur.",
        )
    if four == FOURNISSEUR_OPENAI:
        if not parametres.ia_url_base or not parametres.ia_modele:
            return EtatIA(
                four, False, parametres.ia_modele, False,
                "IA désactivée : BE_IA_URL_BASE et BE_IA_MODELE sont requis.",
            )
        hote = urlparse(parametres.ia_url_base).hostname or "?"
        if hote_est_local(parametres.ia_url_base):
            return EtatIA(
                four, True, parametres.ia_modele, False,
                f"IA locale compatible OpenAI ({parametres.ia_modele}, {hote}) : les données "
                "ne quittent pas le serveur.",
            )
        return EtatIA(
            four, True, parametres.ia_modele, True,
            f"IA hébergée compatible OpenAI ({parametres.ia_modele}, {hote}) : le texte, "
            "anonymisé, est envoyé à un tiers hors du serveur.",
        )
    return EtatIA(four, False, None, False, f"IA désactivée : fournisseur « {four} » inconnu.")


def construire_client(
    parametres: Parametres, *, transport: httpx.BaseTransport | None = None
) -> ClientLLM | None:
    """Client du fournisseur configuré, ou None si l'IA n'est pas activée/configurée.
    Un fournisseur non local est enveloppé par l'anonymisation (règle 5)."""
    etat = etat_ia(parametres)
    if not etat.active:
        return None
    if etat.fournisseur == FOURNISSEUR_ANTHROPIC:
        client: ClientLLM = ClientAnthropic(
            cle=parametres.cle_api_anthropic or "",
            modele=parametres.modele_llm,
            url=parametres.url_api_anthropic,
            delai_secondes=parametres.delai_llm_secondes,
        )
    else:
        client = ClientOpenAICompatible(
            url_base=parametres.ia_url_base or "",
            modele=parametres.ia_modele or "",
            cle=parametres.ia_cle,
            delai_secondes=parametres.delai_llm_secondes,
            tentatives=parametres.ia_tentatives,
            transport=transport,
        )
    return ClientAnonymisant(client) if etat.donnees_quittent_serveur else client


def obtenir_client_llm(
    parametres: Parametres = Depends(obtenir_parametres),
) -> ClientLLM:
    """Dépendance FastAPI (remplaçable dans les tests par un faux client)."""
    client = construire_client(parametres)
    if client is None:
        raise ServiceIndisponible(
            "L'assistant IA n'est pas activé sur cette plateforme : " + etat_ia(parametres).message
        )
    return client


def obtenir_client_llm_optionnel(
    parametres: Parametres = Depends(obtenir_parametres),
) -> ClientLLM | None:
    """Comme `obtenir_client_llm`, mais renvoie None sans IA configurée (repli sur un modèle local)."""
    return construire_client(parametres)


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
