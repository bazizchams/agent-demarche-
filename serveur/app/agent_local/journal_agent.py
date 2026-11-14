"""Journal de l'agent : l'agent « parle » dans le panneau de discussion de la fenêtre ET au serveur.

API : `dire(texte)`, `agir(libelle, element=None)`, `alerter(texte)`, `demander_humain(motif)`.
Chaque message va dans le panneau injecté dans la fenêtre visible (`panneau_discussion.py`) et est envoyé au
serveur (`POST /api/v1/taches/{id}/evenements`) pour la discussion de l'interface web.

Garanties :
- Règles 3 et 5 : tout texte est MASQUÉ avant affichage et envoi (`masquer_texte_sensible`) ; la valeur d'un
  champ n'est jamais lue ; le libellé d'un champ sensible (mot de passe, identifiant, passeport, identité)
  est remplacé par une formule neutre.
- La discussion ne doit JAMAIS faire échouer la tâche : toute panne (panneau, réseau) est journalisée sans
  donnée et ignorée. Seule exception voulue : l'arrêt demandé par l'humain (`ArretDemandeParHumain`).
- Une consigne de l'utilisateur est du texte : si elle contredit les règles 1/2/3/6 l'agent refuse poliment
  (« je ne peux pas valider à votre place, c'est à vous de… ») et ne l'exécute pas.
- Pause : `agir()` / `point_de_controle()` attendent tant que l'humain a demandé la pause (depuis le panneau
  ou l'interface web), sans jamais contourner un CAPTCHA ni une validation.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.agent_local.garde_fous import SuspensionRequiseParGardeFou
from app.agent_local.panneau_discussion import PontPanneau, pont_pour
from app.modeles.tache import MotifSuspensionTache
from app.services.consignes_agent import analyser_consigne, masquer_texte_sensible

journal = logging.getLogger("app.agent_local.journal_agent")

CHEMIN_TACHES = "/api/v1/taches"
LIBELLE_CHAMP_PROTEGE = "un champ protégé (sa valeur n'est jamais lue ni enregistrée)"
INTERVALLE_SERVEUR_S = 2.0
INTERVALLE_PAUSE_MS = 400
MOTIFS_COMMANDES_PANNEAU = {"pause", "reprise", "arret"}


class ArretDemandeParHumain(SuspensionRequiseParGardeFou):
    """L'utilisateur a cliqué sur « Arrêter » : le démon suspend la tâche (reprise possible depuis l'interface)."""

    def __init__(self) -> None:
        super().__init__(
            motif=MotifSuspensionTache.AUTRE,
            message_alerte="Arrêt demandé par l'utilisateur : tâche suspendue, reprenez-la quand vous voulez.",
            code_etape="arret_utilisateur",
        )


class JournalAgent:
    def __init__(
        self,
        *,
        tache_id: str,
        client_api: Any = None,
        pont: PontPanneau | None = None,
        amener_au_premier_plan: Any = None,
        intervalle_serveur_s: float = INTERVALLE_SERVEUR_S,
    ) -> None:
        self._tache_id = str(tache_id)
        self._client = client_api
        self._pont = pont
        self._premier_plan = amener_au_premier_plan
        self._intervalle_serveur = intervalle_serveur_s
        self._derniere_lecture = 0.0
        self._pause = False
        self._arret = False
        self._pause_annoncee = False
        self.consignes: list[str] = []
        self._messages_panneau: list[str] = []
        if pont is not None:
            pont.lier(self)

    # ------------------------------------------------------------------ construction
    @classmethod
    def depuis_contexte(cls, ctx: Any, **options: Any) -> JournalAgent:
        """Journal d'une tâche à partir du `ContexteExecution` du démon. Si le panneau ne peut pas être
        installé, le journal fonctionne quand même (serveur seul)."""
        pont: PontPanneau | None = None
        try:
            pont = pont_pour(ctx.page)
            pont.installer()
        except Exception as exc:
            journal.warning("Panneau de discussion indisponible : %s", type(exc).__name__)
            pont = None
        instance = cls(
            tache_id=ctx.tache_id,
            client_api=getattr(ctx, "client_api", None),
            pont=pont,
            amener_au_premier_plan=getattr(ctx, "amener_au_premier_plan", None),
            **options,
        )
        instance._definir_etat("travaille")
        return instance

    # ------------------------------------------------------------------ API publique
    def dire(self, texte: str) -> None:
        """L'agent annonce ce qu'il va faire / a fait."""
        self._emettre("agent", texte)

    def agir(self, libelle: str, element: Any = None) -> None:
        """Annonce une action et, si `element` (sélecteur CSS ou `Locator`) est fourni, le surligne en direct.
        Respecte la pause / l'arrêt demandés avant d'agir."""
        self.point_de_controle()
        texte = libelle
        if element is not None and self._pont is not None:
            resultat = self._pont.surligner(element)
            if resultat["sensible"]:
                texte = f"{libelle} : {LIBELLE_CHAMP_PROTEGE}"
        self._emettre("action", texte)

    def alerter(self, texte: str) -> None:
        """Signale un problème."""
        self._emettre("alerte", texte)

    def demander_humain(self, motif: str) -> None:
        """Demande de l'aide (CAPTCHA, 2FA, connexion à faire soi-même, validation du récapitulatif)."""
        self._emettre("demande_humaine", motif)
        self._definir_etat("attente_humain")

    def terminer(self, texte: str | None = None) -> None:
        if texte:
            self.dire(texte)
        self._definir_etat("termine")

    def point_de_controle(self) -> None:
        """À appeler entre deux actions : applique Pause / Arrêt et lit les consignes en attente."""
        self._vider_messages_panneau()
        self._lire_serveur(force=False)
        if self._arret:
            self._definir_etat("arrete")
            raise ArretDemandeParHumain
        if not self._pause:
            return
        if not self._pause_annoncee:
            self._pause_annoncee = True
            self._emettre("agent", "Je suis en pause. Cliquez sur « Reprendre » quand vous voulez que je continue.")
            self._definir_etat("pause")
        while self._pause and not self._arret:
            if self._pont is not None:
                self._pont.attendre(INTERVALLE_PAUSE_MS)
            else:
                time.sleep(INTERVALLE_PAUSE_MS / 1000)
            self._vider_messages_panneau()
            self._lire_serveur(force=False)
        self._pause_annoncee = False
        if self._arret:
            self._definir_etat("arrete")
            raise ArretDemandeParHumain
        self._emettre("agent", "Je reprends.")
        self._definir_etat("travaille")

    # ------------------------------------------------------------------ entrées (panneau et serveur)
    def sur_message_panneau(self, texte: str) -> None:
        """Message tapé dans le panneau de la fenêtre. Appelé par le pont dans le fil Playwright : on ne fait
        QUE le mettre en file (appeler la page depuis ce callback bloquerait) ; il est traité au prochain
        point de contrôle (`agir`, `dire`, `point_de_controle`)."""
        self._messages_panneau.append(texte)

    def _vider_messages_panneau(self) -> None:
        en_attente, self._messages_panneau = self._messages_panneau, []
        for texte in en_attente:
            propre = masquer_texte_sensible(texte)
            if not propre:
                continue
            self._envoyer("utilisateur", propre)
            self._traiter_consigne(propre)

    def sur_commande_panneau(self, code: str) -> None:
        if code not in MOTIFS_COMMANDES_PANNEAU:
            return
        self._envoyer("commande", {"pause": "Pause demandée.", "reprise": "Reprise demandée.", "arret": "Arrêt demandé."}[code], code=code)
        self._appliquer_commande(code)

    # ------------------------------------------------------------------ interne
    def _traiter_consigne(self, texte: str) -> None:
        refus = analyser_consigne(texte)
        if refus is not None:
            self.dire(refus.message)
            return
        self.consignes.append(texte)
        self.dire(
            "Consigne notée. Je ne peux pas encore l'appliquer automatiquement : je continue la tâche prévue "
            "et un humain du bureau en tiendra compte."
        )

    def _appliquer_commande(self, code: str) -> None:
        if code == "pause":
            self._pause = True
        elif code == "reprise":
            self._pause = False
        elif code == "arret":
            self._arret = True
            self._pause = False
        elif code == "premier_plan" and self._premier_plan is not None:
            try:
                self._premier_plan()
            except Exception as exc:
                journal.info("Mise au premier plan impossible : %s", type(exc).__name__)

    def _lire_serveur(self, *, force: bool) -> None:
        if self._client is None:
            return
        maintenant = time.monotonic()
        if not force and maintenant - self._derniere_lecture < self._intervalle_serveur:
            return
        self._derniere_lecture = maintenant
        try:
            reponse = self._client.get(f"{CHEMIN_TACHES}/{self._tache_id}/messages-en-attente")
            if reponse.status_code != 200:
                return
            donnees = reponse.json()
        except Exception as exc:
            journal.info("Consignes du serveur illisibles : %s", type(exc).__name__)
            return
        for code in donnees.get("commandes", []):
            self._appliquer_commande(str(code))
        for message in donnees.get("messages", []):
            self._traiter_consigne(masquer_texte_sensible(str(message.get("texte", ""))))
        if donnees.get("etat") == "pause":
            self._pause = True
        elif donnees.get("etat") == "arret":
            self._arret = True
        elif donnees.get("etat") == "en_cours" and not self._arret:
            self._pause = False

    def _definir_etat(self, etat: str) -> None:
        if self._pont is not None:
            self._pont.definir_etat(etat)

    def _emettre(self, type_: str, texte: str) -> None:
        self._vider_messages_panneau()
        propre = masquer_texte_sensible(texte)
        if not propre:
            return
        if self._pont is not None:
            try:
                self._pont.ajouter(type_, propre)
            except Exception as exc:
                journal.info("Message non affiché : %s", type(exc).__name__)
        self._envoyer(type_, propre)

    def _envoyer(self, type_: str, texte: str, *, code: str | None = None) -> None:
        if self._client is None:
            return
        corps: dict[str, Any] = {"type": type_, "texte": texte}
        if code:
            corps["code"] = code
        try:
            reponse = self._client.post(f"{CHEMIN_TACHES}/{self._tache_id}/evenements", json=corps)
            if reponse.status_code >= 400:
                journal.info("Événement refusé par le serveur (HTTP %s).", reponse.status_code)
        except Exception as exc:  # la discussion ne fait jamais échouer la tâche
            journal.info("Événement non envoyé : %s", type(exc).__name__)
