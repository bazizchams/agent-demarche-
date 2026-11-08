"""Chiffrement au repos (AES-256-GCM), protection DPAPI Windows et index aveugles HMAC.

Architecture cryptographique :
- Une clé maîtresse de 256 bits (32 octets) est protégée localement par Windows DPAPI
  (`CryptProtectData` / `CryptUnprotectData` via `ctypes`, sans dépendance tierce fragile)
  dans `donnees/cle_maitresse.dpapi`, ou fournie via `BE_CLE_MAITRESSE_BASE64`.
- Une clé de secours imprimable (Base32 par blocs de 4 caractères + somme de contrôle)
  peut être exportée par l'administrateur pour parer à une réinstallation de Windows.
- Pour chaque bureau (`tenant_id`), deux sous-clés de 256 bits sont dérivées via HKDF-SHA256 :
  1. `cle_chiffrement` : chiffre les champs sensibles en base et les fichiers sur disque
     en AES-256-GCM avec des données associées authentifiées (AAD) incluant le `tenant_id`.
     Un texte chiffré ou un fichier d'un bureau A est donc cryptographiquement indéchiffrable
     dans le contexte d'un bureau B.
  2. `cle_index` : calcule les index aveugles HMAC-SHA256 pour la recherche (nom, prénom,
     e-mail, n° de passeport) et l'empreinte de détection des doublons de documents.
"""

from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes
import hashlib
import hmac
import os
import re
import sys
import unicodedata
import uuid
from functools import lru_cache
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import Parametres

TAILLE_CLE_OCTETS = 32
TAILLE_NONCE_OCTETS = 12
PREFIXE_CHAMP_CHIFFRE = "v1:"
ENTETE_FICHIER_CHIFFRE = b"BEENC01"


class ErreurChiffrement(RuntimeError):
    """Échec de déchiffrement ou d'intégrité cryptographique."""


# ---------------------------------------------------------------------------
# Protection Windows DPAPI (CryptProtectData / CryptUnprotectData)
# ---------------------------------------------------------------------------

class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


_CRYPTPROTECT_UI_FORBIDDEN = 0x1


def _creer_blob(donnees: bytes) -> tuple[_DataBlob, ctypes.Array[ctypes.c_ubyte]]:
    tampon = (ctypes.c_ubyte * len(donnees)).from_buffer_copy(donnees)
    blob = _DataBlob(len(donnees), ctypes.cast(tampon, ctypes.POINTER(ctypes.c_ubyte)))
    return blob, tampon


def proteger_dpapi(donnees_claires: bytes) -> bytes:
    """Chiffre `donnees_claires` avec la clé DPAPI du compte utilisateur Windows courant."""
    if sys.platform != "win32":
        raise ErreurChiffrement("DPAPI n'est disponible que sous Windows.")
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    entree, _garde = _creer_blob(donnees_claires)
    sortie = _DataBlob()
    succes = crypt32.CryptProtectData(
        ctypes.byref(entree),
        "BureauEtudesCleMaitresse",
        None,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(sortie),
    )
    if not succes:
        raise ErreurChiffrement("Échec de CryptProtectData (Windows DPAPI).")
    try:
        return ctypes.string_at(sortie.pbData, sortie.cbData)
    finally:
        kernel32.LocalFree(sortie.pbData)


def deproteger_dpapi(donnees_protegees: bytes) -> bytes:
    """Déchiffre un bloc protégé par Windows DPAPI."""
    if sys.platform != "win32":
        raise ErreurChiffrement("DPAPI n'est disponible que sous Windows.")
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    entree, _garde = _creer_blob(donnees_protegees)
    sortie = _DataBlob()
    succes = crypt32.CryptUnprotectData(
        ctypes.byref(entree),
        None,
        None,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(sortie),
    )
    if not succes:
        raise ErreurChiffrement("Échec de CryptUnprotectData (Windows DPAPI).")
    try:
        return ctypes.string_at(sortie.pbData, sortie.cbData)
    finally:
        kernel32.LocalFree(sortie.pbData)


# ---------------------------------------------------------------------------
# Clé maîtresse et clé de secours imprimable
# ---------------------------------------------------------------------------

def exporter_cle_secours(cle_maitresse: bytes) -> str:
    """Encode une clé de 32 octets en groupes lisibles Base32 avec 4 octets de contrôle."""
    if len(cle_maitresse) != TAILLE_CLE_OCTETS:
        raise ValueError("La clé maîtresse doit mesurer exactement 32 octets.")
    controle = hashlib.sha256(b"be-secours:" + cle_maitresse).digest()[:4]
    b32 = base64.b32encode(cle_maitresse + controle).decode("ascii").rstrip("=")
    groupes = [b32[i : i + 4] for i in range(0, len(b32), 4)]
    return "-".join(groupes)


def importer_cle_secours(code_secours: str) -> bytes:
    """Vérifie la somme de contrôle et reconstitue les 32 octets de la clé maîtresse."""
    nettoye = re.sub(r"[\s\-]", "", code_secours).upper()
    rembourrage = "=" * ((8 - len(nettoye) % 8) % 8)
    try:
        brut = base64.b32decode(nettoye + rembourrage, casefold=True)
    except Exception as exc:
        raise ValueError("Format de clé de secours invalide.") from exc
    if len(brut) != TAILLE_CLE_OCTETS + 4:
        raise ValueError("Longueur de clé de secours invalide.")
    cle, controle = brut[:TAILLE_CLE_OCTETS], brut[TAILLE_CLE_OCTETS:]
    attendu = hashlib.sha256(b"be-secours:" + cle).digest()[:4]
    if not hmac.compare_digest(controle, attendu):
        raise ValueError("Somme de contrôle de la clé de secours invalide.")
    return cle


def charger_ou_creer_cle_maitresse(parametres: Parametres) -> bytes:
    """Retourne les 32 octets de la clé maîtresse (variable d'env ou fichier DPAPI)."""
    if parametres.cle_maitresse_base64:
        try:
            cle = base64.urlsafe_b64decode(parametres.cle_maitresse_base64.strip())
        except Exception as exc:
            raise ErreurChiffrement("BE_CLE_MAITRESSE_BASE64 invalide.") from exc
        if len(cle) != TAILLE_CLE_OCTETS:
            raise ErreurChiffrement("BE_CLE_MAITRESSE_BASE64 doit décoder vers 32 octets.")
        return cle

    chemin: Path = parametres.fichier_cle_dpapi
    if chemin.exists():
        cle = deproteger_dpapi(chemin.read_bytes())
        if len(cle) != TAILLE_CLE_OCTETS:
            raise ErreurChiffrement("Fichier de clé DPAPI corrompu.")
        return cle

    chemin.parent.mkdir(parents=True, exist_ok=True)
    nouvelle_cle = os.urandom(TAILLE_CLE_OCTETS)
    chemin.write_bytes(proteger_dpapi(nouvelle_cle))
    return nouvelle_cle


# ---------------------------------------------------------------------------
# Dérivation par bureau (HKDF-SHA256)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=256)
def _deriver_sous_cle(cle_maitresse: bytes, tenant_id: uuid.UUID, usage: str) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=TAILLE_CLE_OCTETS,
        salt=tenant_id.bytes,
        info=f"bureau-etudes:{usage}".encode("utf-8"),
    )
    return hkdf.derive(cle_maitresse)


def deriver_cle_chiffrement_bureau(cle_maitresse: bytes, tenant_id: uuid.UUID) -> bytes:
    return _deriver_sous_cle(cle_maitresse, tenant_id, "aes-256-gcm")


def deriver_cle_index_bureau(cle_maitresse: bytes, tenant_id: uuid.UUID) -> bytes:
    return _deriver_sous_cle(cle_maitresse, tenant_id, "hmac-index-sha256")


# ---------------------------------------------------------------------------
# Chiffrement de champs (base de données) et de fichiers (documents)
# ---------------------------------------------------------------------------

def _aad_champ(tenant_id: uuid.UUID, nom_champ: str) -> bytes:
    return f"tenant:{tenant_id}:champ:{nom_champ}".encode("utf-8")


def chiffrer_champ(
    cle_maitresse: bytes,
    tenant_id: uuid.UUID,
    nom_champ: str,
    valeur_claire: str | None,
) -> str | None:
    """Chiffre un champ texte avec AES-256-GCM lié au `tenant_id` et au nom du champ.
    Préserve `None` tel quel (règle 4 : aucune valeur par défaut inventée)."""
    if valeur_claire is None:
        return None
    cle = deriver_cle_chiffrement_bureau(cle_maitresse, tenant_id)
    nonce = os.urandom(TAILLE_NONCE_OCTETS)
    chiffre = AESGCM(cle).encrypt(
        nonce, valeur_claire.encode("utf-8"), _aad_champ(tenant_id, nom_champ)
    )
    jeton = base64.urlsafe_b64encode(nonce + chiffre).decode("ascii")
    return PREFIXE_CHAMP_CHIFFRE + jeton


def dechiffrer_champ(
    cle_maitresse: bytes,
    tenant_id: uuid.UUID,
    nom_champ: str,
    valeur_chiffree: str | None,
) -> str | None:
    if valeur_chiffree is None:
        return None
    if not valeur_chiffree.startswith(PREFIXE_CHAMP_CHIFFRE):
        raise ErreurChiffrement("Format de champ chiffré inconnu.")
    try:
        brut = base64.urlsafe_b64decode(valeur_chiffree[len(PREFIXE_CHAMP_CHIFFRE) :])
    except Exception as exc:
        raise ErreurChiffrement("Encodage de champ chiffré invalide.") from exc
    if len(brut) < TAILLE_NONCE_OCTETS + 16:
        raise ErreurChiffrement("Champ chiffré tronqué.")
    nonce, chiffre = brut[:TAILLE_NONCE_OCTETS], brut[TAILLE_NONCE_OCTETS:]
    cle = deriver_cle_chiffrement_bureau(cle_maitresse, tenant_id)
    try:
        clair = AESGCM(cle).decrypt(nonce, chiffre, _aad_champ(tenant_id, nom_champ))
    except InvalidTag as exc:
        raise ErreurChiffrement(
            "Échec d'authentification AES-GCM (clé, bureau ou champ incompatible)."
        ) from exc
    return clair.decode("utf-8")


def _aad_fichier(
    tenant_id: uuid.UUID, candidat_id: uuid.UUID, document_id: uuid.UUID
) -> bytes:
    return f"tenant:{tenant_id}:candidat:{candidat_id}:doc:{document_id}".encode("utf-8")


def chiffrer_octets(
    cle_maitresse: bytes,
    *,
    tenant_id: uuid.UUID,
    candidat_id: uuid.UUID,
    document_id: uuid.UUID,
    contenu_clair: bytes,
) -> bytes:
    cle = deriver_cle_chiffrement_bureau(cle_maitresse, tenant_id)
    nonce = os.urandom(TAILLE_NONCE_OCTETS)
    chiffre = AESGCM(cle).encrypt(
        nonce, contenu_clair, _aad_fichier(tenant_id, candidat_id, document_id)
    )
    return ENTETE_FICHIER_CHIFFRE + nonce + chiffre


def dechiffrer_octets(
    cle_maitresse: bytes,
    *,
    tenant_id: uuid.UUID,
    candidat_id: uuid.UUID,
    document_id: uuid.UUID,
    contenu_chiffre: bytes,
) -> bytes:
    taille_entete = len(ENTETE_FICHIER_CHIFFRE)
    if (
        len(contenu_chiffre) < taille_entete + TAILLE_NONCE_OCTETS + 16
        or not contenu_chiffre.startswith(ENTETE_FICHIER_CHIFFRE)
    ):
        raise ErreurChiffrement("En-tête de fichier chiffré invalide ou tronqué.")
    nonce = contenu_chiffre[taille_entete : taille_entete + TAILLE_NONCE_OCTETS]
    chiffre = contenu_chiffre[taille_entete + TAILLE_NONCE_OCTETS :]
    cle = deriver_cle_chiffrement_bureau(cle_maitresse, tenant_id)
    try:
        return AESGCM(cle).decrypt(
            nonce, chiffre, _aad_fichier(tenant_id, candidat_id, document_id)
        )
    except InvalidTag as exc:
        raise ErreurChiffrement(
            "Échec d'authentification AES-GCM du fichier (bureau, candidat ou document incompatible)."
        ) from exc


# ---------------------------------------------------------------------------
# Normalisation, index aveugles de recherche et empreinte de doublon
# ---------------------------------------------------------------------------

def normaliser_pour_index(texte: str) -> str:
    """Supprime les accents, met en minuscules et condense les espaces."""
    decompose = unicodedata.normalize("NFKD", texte)
    sans_accents = "".join(c for c in decompose if not unicodedata.combining(c))
    return " ".join(sans_accents.lower().strip().split())


def calculer_index_aveugle(
    cle_maitresse: bytes,
    tenant_id: uuid.UUID,
    domaine: str,
    valeur: str | None,
) -> str | None:
    if valeur is None or not valeur.strip():
        return None
    norm = normaliser_pour_index(valeur)
    if not norm:
        return None
    cle_idx = deriver_cle_index_bureau(cle_maitresse, tenant_id)
    message = f"{domaine}:{norm}".encode("utf-8")
    return hmac.new(cle_idx, message, hashlib.sha256).hexdigest()


def calculer_empreinte_document(
    cle_maitresse: bytes, tenant_id: uuid.UUID, contenu_clair: bytes
) -> str:
    """Empreinte HMAC-SHA256 du fichier, propre au bureau (aucun recoupement inter-bureaux)."""
    cle_idx = deriver_cle_index_bureau(cle_maitresse, tenant_id)
    return hmac.new(cle_idx, b"doc:" + contenu_clair, hashlib.sha256).hexdigest()
