"""Registre des sessions du Co-Pilote navigateur : UNE session par bureau (tenant_id).

- Profil Chromium isolé : `<dossier_stockage>/profil_navigateur_agent/<tenant_id>`.
- Création paresseuse (le navigateur n'est lancé qu'à la première action), protégée par un verrou.
- Nombre maximal de sessions simultanées (`navigateur_max_sessions`, défaut 3) : au-delà, refus (429).
- Fermeture automatique après inactivité (`navigateur_inactivite_minutes`, défaut 15 min) et à l'arrêt.
- Révocation : fermeture + effacement du profil (cookies de session des portails des candidats).
- Mode serveur (production ou `navigateur_serveur=True`) : headless forcé, jamais de CDP 9222 ni de
  canal chrome/msedge local, navigation limitée aux domaines HTTPS officiels (Règle 6).

Ce module n'importe pas Playwright au chargement : le pilote n'est importé qu'à la création d'une session.
"""

from __future__ import annotations

import logging
import secrets
import shutil
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.agent_local.domaines_officiels import PolitiqueNavigation, politique_depuis_parametres
from app.core.config import Environnement, Parametres
from app.core.erreurs import LimiteAtteinte

if TYPE_CHECKING:  # pragma: no cover
    from app.agent_local.pilote_navigateur import GestionnairePiloteNavigateur

journal = logging.getLogger("app.agent_local.sessions_navigateur")

VIEWPORT_LARGEUR = 1280
VIEWPORT_HAUTEUR = 900
NOM_DOSSIER_PROFILS = "profil_navigateur_agent"

FabriqueGestionnaire = Callable[[uuid.UUID, Parametres, Path], "GestionnairePiloteNavigateur"]


@dataclass
class SessionNavigateur:
    tenant_id: uuid.UUID
    gestionnaire: "GestionnairePiloteNavigateur"
    dossier_profil: Path
    delai_inactivite_s: float
    derniere_activite: float
    mode_serveur: bool = False
    jeton_bridge: str = field(default="", repr=False)

    @property
    def headless_force(self) -> bool:
        return self.mode_serveur


def headless_pour(parametres: Parametres, *, ouvrir_fenetre_visible: bool = True) -> bool:
    """Mode serveur et tests : toujours headless. Sinon, selon le choix de l'opérateur local."""
    if parametres.navigateur_serveur_actif or parametres.environnement is Environnement.TEST:
        return True
    return not ouvrir_fenetre_visible


def dossier_profil_bureau(parametres: Parametres, tenant_id: uuid.UUID) -> Path:
    # str(UUID) : aucun caractère de chemin possible (pas de traversée de dossier).
    return parametres.dossier_stockage / NOM_DOSSIER_PROFILS / str(tenant_id)


def _fabrique_par_defaut(
    tenant_id: uuid.UUID, parametres: Parametres, dossier_profil: Path
) -> "GestionnairePiloteNavigateur":
    from app.agent_local.pilote_navigateur import GestionnairePiloteNavigateur

    return GestionnairePiloteNavigateur(
        mode_serveur=parametres.navigateur_serveur_actif,
        politique_navigation=politique_depuis_parametres(parametres),
        url_serveur=parametres.url_serveur_copilote,
    )


class RegistreSessionsNavigateur:
    def __init__(
        self,
        *,
        horloge: Callable[[], float] = time.monotonic,
        fabrique: FabriqueGestionnaire | None = None,
        intervalle_surveillance_s: float | None = 30.0,
    ) -> None:
        self._horloge = horloge
        self._fabrique = fabrique or _fabrique_par_defaut
        self._intervalle = intervalle_surveillance_s
        self._verrou = threading.RLock()
        self._sessions: dict[uuid.UUID, SessionNavigateur] = {}
        self._arret = threading.Event()
        self._surveillant: threading.Thread | None = None

    # ------------------------------------------------------------------ accès
    def obtenir(self, tenant_id: uuid.UUID, parametres: Parametres) -> SessionNavigateur:
        """Session du bureau (créée paresseusement) ; compte comme une activité."""
        a_fermer = self._extraire_inactives()
        with self._verrou:
            session = self._sessions.get(tenant_id)
            if session is None:
                if len(self._sessions) >= parametres.navigateur_max_sessions:
                    self._fermer_sessions(a_fermer)
                    raise LimiteAtteinte(
                        "Le nombre maximal de navigateurs simultanés du serveur est atteint. "
                        "Réessayez dans quelques minutes."
                    )
                dossier = dossier_profil_bureau(parametres, tenant_id)
                gestionnaire = self._fabrique(tenant_id, parametres, dossier)
                session = SessionNavigateur(
                    tenant_id=tenant_id,
                    gestionnaire=gestionnaire,
                    dossier_profil=dossier,
                    delai_inactivite_s=parametres.navigateur_inactivite_minutes * 60.0,
                    derniere_activite=self._horloge(),
                    mode_serveur=parametres.navigateur_serveur_actif,
                    jeton_bridge=getattr(gestionnaire, "jeton_bridge_local", ""),
                )
                self._sessions[tenant_id] = session
                self._demarrer_surveillance()
            session.derniere_activite = self._horloge()
        self._fermer_sessions(a_fermer)
        return session

    def existante(self, tenant_id: uuid.UUID) -> SessionNavigateur | None:
        """Session déjà ouverte du bureau, sans en créer et sans compter comme activité."""
        a_fermer = self._extraire_inactives()
        with self._verrou:
            session = self._sessions.get(tenant_id)
        self._fermer_sessions(a_fermer)
        return session

    def par_jeton(self, jeton: str | None) -> SessionNavigateur | None:
        """Retrouve la session dont le jeton de pont correspond (comparaison à temps constant)."""
        fourni = (jeton or "").strip()
        if not fourni:
            return None
        a_fermer = self._extraire_inactives()
        trouvee: SessionNavigateur | None = None
        with self._verrou:
            for session in self._sessions.values():
                attendu = session.jeton_bridge
                if attendu and secrets.compare_digest(fourni, attendu):
                    trouvee = session
        self._fermer_sessions(a_fermer)
        return trouvee

    def toucher(self, tenant_id: uuid.UUID) -> None:
        with self._verrou:
            session = self._sessions.get(tenant_id)
            if session is not None:
                session.derniere_activite = self._horloge()

    def nombre_sessions(self) -> int:
        with self._verrou:
            return len(self._sessions)

    def secondes_avant_expiration(self, session: SessionNavigateur) -> int:
        reste = session.delai_inactivite_s - (self._horloge() - session.derniere_activite)
        return max(0, int(reste))

    # --------------------------------------------------------------- fermetures
    def fermer(self, tenant_id: uuid.UUID, *, effacer_profil: bool = False) -> bool:
        with self._verrou:
            session = self._sessions.pop(tenant_id, None)
        if session is None:
            return False
        self._fermer_sessions([session], effacer_profil=effacer_profil)
        return True

    def revoquer(self, tenant_id: uuid.UUID, parametres: Parametres) -> None:
        """Révocation d'un bureau : fermeture de sa session ET effacement de son profil navigateur."""
        if not self.fermer(tenant_id, effacer_profil=True):
            self._effacer_profil(dossier_profil_bureau(parametres, tenant_id), parametres.dossier_stockage)

    def purger_inactives(self) -> list[uuid.UUID]:
        a_fermer = self._extraire_inactives()
        self._fermer_sessions(a_fermer)
        return [s.tenant_id for s in a_fermer]

    def fermer_tout(self) -> None:
        self._arret.set()
        with self._verrou:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        self._fermer_sessions(sessions)

    # ------------------------------------------------------------------ interne
    def _extraire_inactives(self) -> list[SessionNavigateur]:
        maintenant = self._horloge()
        with self._verrou:
            expirees = [
                s
                for s in self._sessions.values()
                if maintenant - s.derniere_activite >= s.delai_inactivite_s
            ]
            for s in expirees:
                self._sessions.pop(s.tenant_id, None)
        return expirees

    def _fermer_sessions(
        self, sessions: list[SessionNavigateur], *, effacer_profil: bool = False
    ) -> None:
        # Hors verrou : la fermeture de Chromium peut prendre plusieurs secondes.
        for s in sessions:
            try:
                arreter = getattr(s.gestionnaire, "arreter", None) or s.gestionnaire.fermer
                arreter()
            except Exception as exc:  # fermeture au mieux : ne jamais bloquer les autres bureaux
                journal.warning("Fermeture session navigateur : %s", type(exc).__name__)
            if effacer_profil:
                self._effacer_profil(s.dossier_profil, s.dossier_profil.parent.parent)

    @staticmethod
    def _effacer_profil(dossier: Path, racine_stockage: Path) -> None:
        """N'efface qu'un sous-dossier de `<stockage>/profil_navigateur_agent/`."""
        try:
            base = (racine_stockage / NOM_DOSSIER_PROFILS).resolve()
            cible = dossier.resolve()
            if cible != base and base in cible.parents and cible.exists():
                shutil.rmtree(cible, ignore_errors=True)
        except OSError as exc:
            journal.warning("Effacement profil navigateur : %s", type(exc).__name__)

    def _demarrer_surveillance(self) -> None:
        if not self._intervalle:
            return
        if (
            self._surveillant is not None
            and self._surveillant.is_alive()
            and not self._arret.is_set()
        ):
            return
        arret = self._arret = threading.Event()

        def _boucle() -> None:
            while not arret.wait(self._intervalle):
                try:
                    self.purger_inactives()
                except Exception as exc:  # pragma: no cover - filet de sécurité
                    journal.warning("Surveillance sessions navigateur : %s", type(exc).__name__)

        self._surveillant = threading.Thread(
            target=_boucle, name="surveillance_sessions_navigateur", daemon=True
        )
        self._surveillant.start()


def etat_session_absente() -> dict[str, Any]:
    return {
        "session_active": False,
        "navigateur_ouvert": False,
        "url_courante": "",
        "titre_page": "Aucun navigateur ouvert pour votre bureau",
        "controle_securite_detecte": False,
        "viewport": {"largeur": VIEWPORT_LARGEUR, "hauteur": VIEWPORT_HAUTEUR},
    }
