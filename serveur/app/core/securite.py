"""Primitives de sécurité : hachage des mots de passe (Argon2id), jetons de session, CSRF.

Les mots de passe des UTILISATEURS DE LA PLATEFORME sont hachés (jamais stockés en clair).
Les mots de passe des PORTAILS OFFICIELS ne sont jamais demandés ni stockés (règle 3).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hacheur = PasswordHasher()  # Argon2id, paramètres RFC 9106 recommandés par argon2-cffi

# Empreinte factice : vérifiée quand l'e-mail est inconnu, pour que le temps de réponse
# ne révèle pas si un compte existe.
_EMPREINTE_FACTICE = _hacheur.hash(secrets.token_urlsafe(16))

LONGUEUR_MAX_MOT_DE_PASSE = 128


def hacher_mot_de_passe(mot_de_passe: str) -> str:
    return _hacheur.hash(mot_de_passe)


def verifier_mot_de_passe(empreinte: str, mot_de_passe: str) -> bool:
    try:
        return _hacheur.verify(empreinte, mot_de_passe)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def verification_factice(mot_de_passe: str) -> None:
    verifier_mot_de_passe(_EMPREINTE_FACTICE, mot_de_passe)


def doit_rehacher(empreinte: str) -> bool:
    return _hacheur.check_needs_rehash(empreinte)


def generer_jeton() -> str:
    """Jeton aléatoire de 256 bits, encodé URL-safe."""
    return secrets.token_urlsafe(32)


def empreinte_jeton(jeton: str) -> str:
    """Seule l'empreinte SHA-256 du jeton de session est stockée en base :
    une fuite de la base ne permet pas de réutiliser les sessions."""
    return hashlib.sha256(jeton.encode("utf-8")).hexdigest()


def comparer_constant(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def verifier_robustesse(mot_de_passe: str, longueur_min: int) -> list[str]:
    """Retourne la liste des problèmes (vide si le mot de passe est acceptable)."""
    problemes: list[str] = []
    if len(mot_de_passe) < longueur_min:
        problemes.append(f"au moins {longueur_min} caractères")
    if len(mot_de_passe) > LONGUEUR_MAX_MOT_DE_PASSE:
        problemes.append(f"au plus {LONGUEUR_MAX_MOT_DE_PASSE} caractères")
    familles = [
        any(c.islower() for c in mot_de_passe),
        any(c.isupper() for c in mot_de_passe),
        any(c.isdigit() for c in mot_de_passe),
        any(not c.isalnum() for c in mot_de_passe),
    ]
    if sum(familles) < 3:
        problemes.append("au moins 3 types parmi : minuscules, majuscules, chiffres, symboles")
    return problemes
