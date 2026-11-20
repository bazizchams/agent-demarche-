"""Formulaires de connexion / d'inscription des portails (`config/portails/formulaires/*.yaml`, règle 7) et outils
communs aux actions `connexion_portail` et `creation_compte_eef`.

- Les champs sont retrouvés par LIBELLÉ accessible (expression régulière du YAML), jamais par id (application React
  aux id générés). Un champ introuvable ou ambigu => l'appelant s'arrête et demande à l'humain (règle 4).
- Règle 6 : la page ouverte est vérifiée AVANT et APRÈS navigation : hôte officiel en HTTPS (YAML des portails réels) ou,
  pour la démonstration, la page `/demo/` du serveur de l'agent. Le portail réel n'est utilisé que si l'administrateur a
  attesté « validé sur portail réel » ; sinon seules les pages de démonstration du serveur sont ouvertes.
- Règle 3 : `SecretEphemere` garde un secret dans un `bytearray` effacé après usage (jamais dans un journal ni sur disque).
"""

from __future__ import annotations

import re
import secrets
import string
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.agent_local.config_portail import ModePortail, lister_configs_portails
from app.agent_local.domaines_officiels import PolitiqueNavigation
from app.core.config import RACINE_PLATEFORME

DOSSIER_FORMULAIRES = RACINE_PLATEFORME / "config" / "portails" / "formulaires"
STATUT_REEL_HOMOLOGUE = "validé sur portail réel"
DELAI_CHAMP_MS = 8_000


class ChampFormulaire(BaseModel):
    model_config = ConfigDict(extra="forbid")

    libelle_regex: str = Field(min_length=1, max_length=300)
    type: str = Field(pattern="^(texte|mot_de_passe|liste)$")


class RegleMotDePasse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    longueur_min: int = Field(ge=8, le=200)
    minuscule: bool = True
    majuscule: bool = True
    chiffre: bool = True
    special: bool = True


class PageFormulaire(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url_reelle: str
    chemin_demo: str
    champs: dict[str, ChampFormulaire]
    bouton_regex: str | None = None
    valeurs_fixes: dict[str, str] = Field(default_factory=dict)
    cases_laissees_a_l_humain: list[str] = Field(default_factory=list)
    bouton_interdit_regex: str | None = None
    regles_mot_de_passe: RegleMotDePasse | None = None


class TemoinConnecte(BaseModel):
    model_config = ConfigDict(extra="forbid")

    texte_regex: str


class FormulairesPortail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code_portail: str
    releve_le: str
    statut: str
    detecteurs_captcha: list[str]
    temoin_connecte: TemoinConnecte
    connexion: PageFormulaire
    inscription: PageFormulaire | None = None

    @property
    def reel_homologue(self) -> bool:
        return self.statut == STATUT_REEL_HOMOLOGUE


def charger_formulaires(code_portail: str, dossier: Path | None = None) -> FormulairesPortail:
    dossier = dossier or DOSSIER_FORMULAIRES
    for fichier in sorted(dossier.glob("*.yaml")):
        brut: Any = yaml.safe_load(fichier.read_text(encoding="utf-8"))
        if isinstance(brut, dict) and brut.get("code_portail") == code_portail:
            return FormulairesPortail.model_validate(brut)
    raise FileNotFoundError(f"Aucun formulaire configuré pour le portail « {code_portail} ».")


# ------------------------------------------------------------------ règle 6
def _domaines_reels() -> frozenset[str]:
    domaines: set[str] = set()
    for cfg in lister_configs_portails(RACINE_PLATEFORME / "config" / "portails").values():
        if cfg.mode_portail is ModePortail.REEL:
            domaines.update(d.strip().lower() for d in cfg.domaines_autorises if d.strip())
    return frozenset(domaines)


def url_cible(page: PageFormulaire, formulaires: FormulairesPortail, url_serveur: str) -> str:
    """Portail réel seulement s'il est homologué ; sinon la page de démonstration du serveur de l'agent."""
    if formulaires.reel_homologue:
        return page.url_reelle
    return url_serveur.rstrip("/") + page.chemin_demo


def motif_url_refusee(url: str, formulaires: FormulairesPortail, url_serveur: str) -> str | None:
    """None si `url` est autorisée (règle 6), sinon un message sans paramètres d'URL."""
    if formulaires.reel_homologue:
        return PolitiqueNavigation(domaines_https=_domaines_reels(), autoriser_demo=False).motif_refus(url)
    attendue, courante = urlsplit(url_serveur), urlsplit(url or "")
    meme_origine = (attendue.scheme, (attendue.hostname or "").lower(), attendue.port) == (
        courante.scheme, (courante.hostname or "").lower(), courante.port
    )
    if meme_origine and (courante.path or "").startswith("/demo/"):
        return None
    return "Navigation refusée (règle 6) : seule la page de démonstration du serveur est autorisée."


# ------------------------------------------------------------------ champs
def localiser_champ(page: Any, champ: ChampFormulaire) -> Any | None:
    """Le locator du champ, ou None s'il est introuvable ou ambigu (plusieurs correspondances)."""
    loc = page.get_by_label(re.compile(champ.libelle_regex, re.IGNORECASE))
    return loc if loc.count() == 1 else None


def captcha_visible(page: Any, selecteurs: list[str]) -> bool:
    for sel in selecteurs:
        try:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible():
                return True
        except Exception:  # noqa: BLE001 - un sélecteur invalide ne doit pas masquer les autres
            continue
    return False


def session_ouverte(page: Any, formulaires: FormulairesPortail) -> bool:
    """Page « connectée » : le texte témoin (Déconnexion…) est visible et aucun champ de mot de passe n'est affiché."""
    try:
        temoin = page.get_by_text(re.compile(formulaires.temoin_connecte.texte_regex, re.IGNORECASE))
        mdp = page.locator("input[type=password]")
        return (
            temoin.count() > 0
            and temoin.first.is_visible()
            and not (mdp.count() > 0 and mdp.first.is_visible())
        )
    except Exception:  # noqa: BLE001 - page en cours de navigation
        return False


# ------------------------------------------------------------------ secrets
class SecretEphemere:
    """Secret gardé dans un bytearray, effacé après usage (au mieux : CPython peut avoir copié des `str`)."""

    def __init__(self, valeur: str) -> None:
        self._octets = bytearray(valeur.encode("utf-8"))

    def valeur(self) -> str:
        return self._octets.decode("utf-8")

    def effacer(self) -> None:
        for i in range(len(self._octets)):
            self._octets[i] = 0
        self._octets = bytearray()

    @property
    def efface(self) -> bool:
        return len(self._octets) == 0

    def __repr__(self) -> str:
        return "SecretEphemere(<masqué>)"

    __str__ = __repr__


SPECIAUX = "!@#$%^&*()-_=+[]{};:,.?"


def generer_mot_de_passe(regles: RegleMotDePasse, longueur: int = 20) -> str:
    """Mot de passe fort (module `secrets`) conforme aux règles affichées ; jamais journalisé."""
    longueur = max(longueur, regles.longueur_min)
    imposes = []
    if regles.minuscule:
        imposes.append(string.ascii_lowercase)
    if regles.majuscule:
        imposes.append(string.ascii_uppercase)
    if regles.chiffre:
        imposes.append(string.digits)
    if regles.special:
        imposes.append(SPECIAUX)
    alphabet = "".join(imposes) or string.ascii_letters
    caracteres = [secrets.choice(classe) for classe in imposes]
    caracteres += [secrets.choice(alphabet) for _ in range(longueur - len(caracteres))]
    secrets.SystemRandom().shuffle(caracteres)
    return "".join(caracteres)


def mot_de_passe_conforme(valeur: str, regles: RegleMotDePasse) -> bool:
    return (
        len(valeur) >= regles.longueur_min
        and (not regles.minuscule or any(c.islower() for c in valeur))
        and (not regles.majuscule or any(c.isupper() for c in valeur))
        and (not regles.chiffre or any(c.isdigit() for c in valeur))
        and (not regles.special or any(not c.isalnum() for c in valeur))
    )
