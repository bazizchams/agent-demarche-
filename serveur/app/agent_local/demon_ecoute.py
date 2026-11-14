"""Démon d'écoute de l'Agent Local (`lanceur.py --mode ecouter`).

Boucle : sonder le serveur avec le jeton agent -> réserver ATOMIQUEMENT une tâche en attente de ce bureau
-> l'exécuter dans la fenêtre visible du PC avec battement de cœur -> rendre le résultat -> attendre.

Garanties :
- Réservation côté serveur (`POST /api/v1/taches/reserver-suivante`, compare-and-swap) : deux agents ne
  prennent jamais la même tâche.
- Règle 1 : l'agent ne valide JAMAIS lui-même ; il termine toujours en `a_valider` (arrêt avant l'envoi
  officiel), `suspendue` ou `en_erreur`. Aucune soumission finale ici.
- Règle 2 : CAPTCHA / 2FA => suspension de la tâche ; la fenêtre reste ouverte pour la reprise humaine.
- Règle 3 : aucun mot de passe n'est demandé au serveur ni saisi par l'agent.
- Règle 5 : seuls des identifiants techniques et des statuts sont journalisés (jamais nom, motivation, jeton).
- Arrêt propre : `demander_arret()` (Ctrl+C / fermeture) termine la tâche en cours puis sort.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from app.agent_local.garde_fous import SuspensionRequiseParGardeFou
from app.modeles.tache import MotifSuspensionTache

journal = logging.getLogger("app.agent_local.demon_ecoute")

CHEMIN_TACHES = "/api/v1/taches"
INTERVALLE_SONDAGE_DEFAUT_S = 5.0
INTERVALLE_BATTEMENT_DEFAUT_S = 60.0
ATTENTE_MAX_APRES_ERREUR_S = 60.0
CODES_JETON_REFUSE = (401, 403)

MESSAGE_VALIDATION_HUMAINE = (
    "Vœux ajoutés au panier dans la fenêtre ouverte sur votre PC, arrêt avant tout envoi officiel : "
    "contrôlez la fenêtre puis validez dans le Centre de validation."
)


class JetonRefuse(RuntimeError):
    """Le serveur refuse le jeton (invalide, révoqué ou bureau suspendu) : le démon s'arrête."""


class ClientApi(Protocol):
    """Sous-ensemble de `httpx.Client` utilisé (un `TestClient` convient aussi)."""

    def get(self, url: str, **kwargs: Any) -> httpx.Response: ...

    def post(self, url: str, **kwargs: Any) -> httpx.Response: ...


class FenetreAgent(Protocol):
    def page(self) -> Any: ...

    def amener_au_premier_plan(self) -> None: ...


@dataclass(frozen=True)
class ResultatExecution:
    """Issue d'une action : toujours `a_valider` (arrêt avant envoi) ; la suspension passe par l'exception
    `SuspensionRequiseParGardeFou`."""

    recapitulatif: dict[str, Any] = field(default_factory=dict)
    message_alerte: str = MESSAGE_VALIDATION_HUMAINE
    # Capture PNG de contrôle à déposer (facultative).
    capture_png: bytes | None = None


@dataclass(frozen=True)
class ContexteExecution:
    tache: Mapping[str, Any]
    client_api: ClientApi
    page: Any
    url_serveur: str
    amener_au_premier_plan: Callable[[], None]

    @property
    def tache_id(self) -> str:
        return str(self.tache["id"])


Executeur = Callable[[ContexteExecution], ResultatExecution]


class DemonEcoute:
    def __init__(
        self,
        *,
        client_api: ClientApi,
        fenetre: FenetreAgent,
        executeurs: Mapping[str, Executeur],
        url_serveur: str,
        intervalle_sondage_s: float = INTERVALLE_SONDAGE_DEFAUT_S,
        intervalle_battement_s: float = INTERVALLE_BATTEMENT_DEFAUT_S,
        sortie: Callable[[str], None] = print,
    ) -> None:
        self._client = client_api
        self._fenetre = fenetre
        self._executeurs = dict(executeurs)
        self._url_serveur = url_serveur.rstrip("/")
        self._intervalle_sondage = intervalle_sondage_s
        self._intervalle_battement = intervalle_battement_s
        self._sortie = sortie
        self._arret = threading.Event()

    # ------------------------------------------------------------------ arrêt
    def demander_arret(self) -> None:
        self._arret.set()

    @property
    def arret_demande(self) -> bool:
        return self._arret.is_set()

    # ---------------------------------------------------------------- boucle
    def boucler(self) -> int:
        """Retourne 0 à l'arrêt demandé, 3 si le jeton est refusé."""
        attente_erreur = self._intervalle_sondage
        self._sortie(
            "Agent Local à l'écoute : j'attends les tâches « Ouvrir sur mon PC » de votre bureau "
            "(Ctrl+C pour arrêter)."
        )
        while not self._arret.is_set():
            try:
                a_travaille = self.sonder_une_fois()
                attente_erreur = self._intervalle_sondage
            except JetonRefuse as exc:
                self._sortie(f"ARRÊT : {exc}")
                return 3
            except httpx.HTTPError as exc:
                if isinstance(exc, httpx.HTTPStatusError):
                    cause = f"le serveur répond {exc.response.status_code}"
                else:
                    cause = f"serveur injoignable ({type(exc).__name__})"
                self._sortie(f"Sondage impossible : {cause} ; nouvelle tentative dans {int(attente_erreur)} s.")
                self._arret.wait(attente_erreur)
                attente_erreur = min(attente_erreur * 2, ATTENTE_MAX_APRES_ERREUR_S)
                continue
            if not a_travaille:
                self._arret.wait(self._intervalle_sondage)
        self._sortie("Agent Local arrêté proprement.")
        return 0

    def sonder_une_fois(self) -> bool:
        """Un sondage : réserve et exécute au plus une tâche. Vrai si une tâche a été traitée."""
        reponse = self._client.post(
            f"{CHEMIN_TACHES}/reserver-suivante", params={"actions": sorted(self._executeurs)}
        )
        if reponse.status_code in CODES_JETON_REFUSE:
            raise JetonRefuse(
                "le serveur refuse le jeton de cet agent (invalide, révoqué ou bureau suspendu). "
                "Demandez un nouveau jeton à l'administrateur du bureau."
            )
        if reponse.status_code != 200:
            raise httpx.HTTPStatusError(
                f"réponse {reponse.status_code}", request=reponse.request, response=reponse
            )
        tache = reponse.json().get("tache")
        if tache is None:
            return False
        self._traiter(tache)
        return True

    # --------------------------------------------------------------- exécution
    def _traiter(self, tache: Mapping[str, Any]) -> None:
        tache_id = str(tache["id"])
        action = str(tache.get("action", ""))
        self._sortie(f"Tâche {tache_id} réservée (action : {action}).")
        executeur = self._executeurs.get(action)
        if executeur is None:
            self._suspendre(
                tache_id,
                MotifSuspensionTache.AUTRE,
                f"Cette version de l'agent ne sait pas exécuter l'action « {action} ».",
            )
            return

        arret_battement = threading.Event()
        fil = threading.Thread(
            target=self._battre_coeur, args=(tache_id, arret_battement), name="battement_coeur", daemon=True
        )
        fil.start()
        try:
            self._fenetre.amener_au_premier_plan()
            contexte = ContexteExecution(
                tache=tache,
                client_api=self._client,
                page=self._fenetre.page(),
                url_serveur=self._url_serveur,
                amener_au_premier_plan=self._fenetre.amener_au_premier_plan,
            )
            resultat = executeur(contexte)
            self._rendre_resultat(tache_id, resultat)
        except SuspensionRequiseParGardeFou as susp:
            self._fenetre.amener_au_premier_plan()
            self._suspendre(tache_id, susp.motif, susp.message_alerte, code_etape=None)
        except JetonRefuse:
            raise
        except Exception as exc:  # une erreur d'une tâche ne doit jamais tuer le démon
            journal.warning("Tâche %s en erreur : %s", tache_id, type(exc).__name__)
            self._signaler_erreur(tache_id, f"Erreur de l'agent local ({type(exc).__name__}).")
        finally:
            arret_battement.set()
            fil.join(timeout=5)

    def _battre_coeur(self, tache_id: str, arret: threading.Event) -> None:
        while not arret.wait(self._intervalle_battement):
            try:
                self._client.post(f"{CHEMIN_TACHES}/{tache_id}/battement-coeur")
            except Exception as exc:
                journal.warning("Battement de cœur manqué : %s", type(exc).__name__)

    def _rendre_resultat(self, tache_id: str, resultat: ResultatExecution) -> None:
        if resultat.capture_png:
            rep = self._client.post(
                f"{CHEMIN_TACHES}/{tache_id}/capture-controle",
                files={"fichier": ("controle.png", resultat.capture_png, "image/png")},
            )
            if rep.status_code != 200:
                journal.warning("Capture de contrôle refusée (HTTP %s).", rep.status_code)
        rep = self._client.post(
            f"{CHEMIN_TACHES}/{tache_id}/soumettre-validation",
            json={
                "recapitulatif_remplissage": resultat.recapitulatif,
                "message_alerte": resultat.message_alerte,
            },
        )
        if rep.status_code == 200:
            self._sortie(
                f"Tâche {tache_id} : arrêt avant envoi, en attente de VOTRE validation. "
                "La fenêtre reste ouverte pour contrôle."
            )
        else:
            self._sortie(f"Tâche {tache_id} : le serveur a refusé le passage à la validation (HTTP {rep.status_code}).")

    def _suspendre(
        self,
        tache_id: str,
        motif: MotifSuspensionTache,
        message: str,
        *,
        code_etape: str | None = None,
    ) -> None:
        corps: dict[str, Any] = {"motif": motif.value, "message_alerte": message[:500]}
        if code_etape:
            corps["code_etape"] = code_etape
        rep = self._client.post(f"{CHEMIN_TACHES}/{tache_id}/suspendre", json=corps)
        self._sortie(
            f"Tâche {tache_id} suspendue : {message} "
            + ("(reprenez-la depuis l'interface après intervention dans la fenêtre)" if rep.status_code == 200 else "")
        )

    def _signaler_erreur(self, tache_id: str, message: str) -> None:
        rep = self._client.post(f"{CHEMIN_TACHES}/{tache_id}/erreur", json={"message_erreur": message[:500]})
        self._sortie(f"Tâche {tache_id} en erreur : {message}" + ("" if rep.status_code == 200 else " (non transmis)"))
