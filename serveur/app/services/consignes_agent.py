"""Outils PURS (sans base ni réseau) de la discussion de l'agent : masquage et garde des consignes.

- `masquer_texte_sensible` : retire d'un texte court tout ce qui ressemble à un mot de passe, un
  identifiant, un numéro de passeport, une adresse e-mail ou un long nombre (règles 3 et 5). Utilisé
  côté agent AVANT l'envoi et côté serveur AVANT le stockage (défense en profondeur).
- `analyser_consigne` : une consigne écrite par l'utilisateur dans la discussion est du TEXTE. Elle ne
  peut JAMAIS lever les règles 1 (validation humaine), 2 (CAPTCHA/2FA), 3 (coffre) ni 6 (domaines
  officiels) : si elle les contredit, on renvoie le refus poli à afficher. Heuristique de conversation :
  la garantie réelle est structurelle (l'agent n'a ni la capacité de valider, ni de contourner, ni
  accès aux mots de passe, ni de naviguer hors des domaines autorisés).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

MARQUE_MASQUE = "[masqué]"
LONGUEUR_MAX_EVENEMENT = 500

_MOTS_SENSIBLES = (
    r"mots? de passe|mdp|password|passwd|pwd|identifiant|login|nom d'utilisateur|"
    r"passe?port|numéro de passeport|numero de passeport|"
    r"jeton|token|secret|code (?:sms|de vérification|de verification|otp)|otp|iban|carte bancaire"
)
_RE_VALEUR_APRES_LIBELLE = re.compile(
    rf"(?i)\b({_MOTS_SENSIBLES})\b(\s*(?:est|:|=|->|→)\s*|\s+)(?!\[masqué\])(\S+)"
)
_RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_RE_PASSEPORT = re.compile(r"\b[A-Za-z]{1,2}\d{6,9}\b")
_RE_LONG_NOMBRE = re.compile(r"\b\d[\d .-]{5,}\d\b")


def masquer_texte_sensible(texte: str, *, longueur_max: int = LONGUEUR_MAX_EVENEMENT) -> str:
    """Texte sûr à journaliser : valeurs sensibles remplacées par `[masqué]`, longueur bornée."""
    resultat = _RE_VALEUR_APRES_LIBELLE.sub(lambda m: f"{m.group(1)}{m.group(2)}{MARQUE_MASQUE}", texte)
    resultat = _RE_EMAIL.sub("[e-mail masqué]", resultat)
    resultat = _RE_PASSEPORT.sub(MARQUE_MASQUE, resultat)
    resultat = _RE_LONG_NOMBRE.sub("[nombre masqué]", resultat)
    resultat = " ".join(resultat.split())
    if len(resultat) > longueur_max:
        resultat = resultat[: longueur_max - 1].rstrip() + "…"
    return resultat


_RE_CHAMP_SENSIBLE = re.compile(
    r"(?i)pass(?:word|wd)|pwd|mot.?de.?passe|mdp|identifiant|login|username|user.?name|"
    r"passeport|passport|otp|secret|token|iban|card|carte|cvv|ssn|email|e-mail|courriel|"
    r"naissance|birth|telephone|phone|nom|prenom|first.?name|last.?name"
)


def element_est_sensible(element: dict[str, str] | None) -> bool:
    """Un champ de formulaire est « sensible » (mot de passe, identifiant, passeport, identité…) selon son
    type et ses attributs `name`/`id`/`autocomplete`/`aria-label`/`placeholder`. Le libellé d'un tel champ
    n'est jamais transmis et sa valeur ne l'est JAMAIS."""
    if not element:
        return False
    if (element.get("type") or "").lower() in {"password", "email", "tel"}:
        return True
    return any(
        _RE_CHAMP_SENSIBLE.search(element.get(cle) or "")
        for cle in ("name", "id", "autocomplete", "aria-label", "placeholder")
    )


@dataclass(frozen=True)
class RefusConsigne:
    regle: str
    message: str


def _normaliser(texte: str) -> str:
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode("ascii")
    return " ".join(sans_accents.lower().replace("'", " ").replace("-", " ").split())


_VERBES_ENVOI = re.compile(
    r"\b(envoie|envoyer|soumets|soumettre|transmets|transmettre|valide|valider|finalise|finaliser|certifie|certifier)\b"
)
_OBJETS_ENVOI = re.compile(
    r"\b(dossier|demande|candidature|formulaire|recapitulatif|definitif|definitivement|officiel|officielle|"
    r"a ma place|pour moi|tout de suite|maintenant)\b"
)
_RE_R1_CLIC = re.compile(r"\bclique(?:r)? sur (?:le bouton )?(envoyer|soumettre|valider|confirmer|transmettre)\b")
_RE_R1_VOEUX = re.compile(r"\b(envoie|envoyer|soumets|soumettre|transmets|transmettre) (?:les |mes |ces )?voeux\b")
_RE_R2 = re.compile(r"\b(captcha|recaptcha|hcaptcha|2fa|double authentification|verification en deux etapes)\b")
_VERBES_R2 = re.compile(
    r"\b(contourn\w*|resou\w*|saut\w*|ignor\w*|bypass\w*|passe|passer|desactiv\w*|remplis\w*|tape\w*|"
    r"saisis\w*|devine\w*|fais|entre|automatis\w*)\b"
)
_RE_R3_LIBELLE = re.compile(r"\b(mot de passe|mots de passe|mdp|password|identifiants?|code secret|coffre)\b")
_VERBES_R3 = re.compile(
    r"\b(donne\w*|ecris\w*|affich\w*|montr\w*|tape\w*|saisis\w*|entre|remplis\w*|utilis\w*|envoie\w*|"
    r"revel\w*|dis|lis|copie\w*|retrouv\w*|devine\w*|ouvre\w*)\b"
)
_RE_URL = re.compile(r"(https?://|www\.|\b[a-z0-9-]+\.(?:com|fr|net|org|dz|ca|io|gov|info|xyz|ru|cn)\b)")
_VERBES_R6 = re.compile(
    r"\b(ouvre\w*|va|aller|navigue\w*|visite\w*|charge\w*|connecte\w*|rends toi|redirige\w*)\b"
)

REFUS_R1 = RefusConsigne(
    "R1",
    "Je ne peux pas valider ni envoyer à votre place : c'est à vous de contrôler le récapitulatif puis de "
    "valider dans le Centre de validation. Je m'arrête toujours avant tout envoi officiel.",
)
REFUS_R2 = RefusConsigne(
    "R2",
    "Je ne contourne jamais un CAPTCHA ni une double authentification : c'est à vous de les résoudre dans la "
    "fenêtre, puis de me demander de reprendre.",
)
REFUS_R3 = RefusConsigne(
    "R3",
    "Je ne peux ni lire, ni afficher, ni taper vos mots de passe : ils restent dans le coffre chiffré. "
    "Si une connexion est nécessaire, c'est à vous de la faire vous-même dans la fenêtre.",
)
REFUS_R6 = RefusConsigne(
    "R6",
    "Je ne peux pas ouvrir cette adresse : je n'ouvre que les domaines officiels autorisés par le bureau. "
    "Si vous avez besoin d'une autre page, ouvrez-la vous-même dans votre navigateur.",
)


def analyser_consigne(texte: str) -> RefusConsigne | None:
    """`None` si la consigne est acceptable comme simple texte ; sinon le refus à afficher."""
    t = _normaliser(texte)
    if _RE_R2.search(t) and _VERBES_R2.search(t):
        return REFUS_R2
    if _RE_R3_LIBELLE.search(t) and _VERBES_R3.search(t):
        return REFUS_R3
    if _RE_URL.search(t) and _VERBES_R6.search(t):
        return REFUS_R6
    if _RE_R1_CLIC.search(t) or _RE_R1_VOEUX.search(t):
        return REFUS_R1
    if _VERBES_ENVOI.search(t) and _OBJETS_ENVOI.search(t):
        return REFUS_R1
    return None
