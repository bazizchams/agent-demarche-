"""Capture des identifiants tapés PAR L'HUMAIN dans le formulaire du portail (règle 3), pour proposer ensuite, dans
l'interface web (jamais dans le panneau injecté), de les enregistrer dans le coffre avec consentement.

Principe : un script injecté écoute l'événement `submit` (phase de capture) ; au moment où l'humain soumet, il lit le
champ de mot de passe et le champ d'identifiant qui le précède et les passe à une fonction Python exposée par Playwright
(nom aléatoire par contexte). La fonction ignore tout appel venant d'une page non autorisée (règle 6) ou quand aucune
capture n'est active. Les valeurs restent en MÉMOIRE de l'agent (`bytearray` effacé), jamais sur son disque, jamais dans
un journal. Le panneau de discussion ne contient aucun champ de saisie de mot de passe.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from typing import Any
from weakref import WeakKeyDictionary

from app.agent_local.formulaires_portail import SecretEphemere

_SCRIPT = """
(() => {
  const NOM = "%NOM%";
  document.addEventListener("submit", (e) => {
    try {
      const f = e.target;
      if (!f || !f.querySelector) return;
      const mdp = f.querySelector("input[type=password]");
      if (!mdp || !mdp.value || typeof window[NOM] !== "function") return;
      const champs = Array.from(f.querySelectorAll("input")).filter(
        (i) => ["text", "email", ""].includes((i.getAttribute("type") || "").toLowerCase()) && i.value);
      const avant = champs.filter((i) => i.compareDocumentPosition(mdp) & Node.DOCUMENT_POSITION_FOLLOWING);
      const id = (avant.length ? avant[avant.length - 1] : champs[0]);
      if (id) window[NOM](id.value, mdp.value);
    } catch (_) { /* jamais d'effet sur la page */ }
  }, true);
})();
"""


class Capteur:
    """Dernier couple (identifiant, mot de passe) soumis par l'humain pendant que la capture est active."""

    def __init__(self) -> None:
        self.actif = False
        self._identifiant: SecretEphemere | None = None
        self._mot_de_passe: SecretEphemere | None = None

    def activer(self) -> None:
        self.vider()
        self.actif = True

    def desactiver(self) -> None:
        self.actif = False

    def enregistrer(self, identifiant: str, mot_de_passe: str) -> None:
        if not self.actif:
            return
        self.vider()
        self._identifiant = SecretEphemere(identifiant)
        self._mot_de_passe = SecretEphemere(mot_de_passe)

    @property
    def a_une_valeur(self) -> bool:
        return self._mot_de_passe is not None and not self._mot_de_passe.efface

    def lire(self) -> tuple[str, str] | None:
        if not self.a_une_valeur or self._identifiant is None or self._mot_de_passe is None:
            return None
        return self._identifiant.valeur(), self._mot_de_passe.valeur()

    def vider(self) -> None:
        for secret in (self._identifiant, self._mot_de_passe):
            if secret is not None:
                secret.effacer()
        self._identifiant = self._mot_de_passe = None


_PAR_CONTEXTE: WeakKeyDictionary[Any, Capteur] = WeakKeyDictionary()


def capteur_pour(page: Any, url_autorisee: Callable[[str], bool]) -> Capteur:
    """Installe (une fois par contexte de navigateur) le script et la fonction exposée ; renvoie le capteur."""
    contexte = page.context
    existant = _PAR_CONTEXTE.get(contexte)
    if existant is not None:
        return existant
    capteur = Capteur()
    nom = "__be_" + secrets.token_hex(8)

    def _recevoir(source: Any, identifiant: str, mot_de_passe: str) -> None:
        try:
            if isinstance(identifiant, str) and isinstance(mot_de_passe, str) and url_autorisee(source["frame"].url):
                capteur.enregistrer(identifiant, mot_de_passe)
        except Exception:  # noqa: BLE001 - jamais de message pouvant citer une valeur
            return

    contexte.expose_binding(nom, _recevoir)
    contexte.add_init_script(_SCRIPT.replace("%NOM%", nom))
    # Les pages déjà ouvertes ne recevront le script qu'à leur prochaine navigation.
    _PAR_CONTEXTE[contexte] = capteur
    return capteur
