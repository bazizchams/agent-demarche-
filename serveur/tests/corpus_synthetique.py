"""Corpus de test SYNTHÉTIQUE pour la lecture des documents (aucun vrai document, aucune vraie personne).

Les identités ci-dessous sont fictives. Le passeport « ERIKSSON Anna Maria » est le spécimen
public de la norme OACI 9303 (valeurs de contrôle vérifiables indépendamment du code testé).
"""

from __future__ import annotations

import struct
import zlib

# --- Spécimen OACI 9303 (TD3), valide : chiffres de contrôle 6, 2, 9, 1 et 0 ---------------
MRZ_L1_VALIDE = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
MRZ_L2_VALIDE = "L898902C36UTO7408122F1204159ZE184226B<<<<<10"
# Même spécimen, mais le chiffre de contrôle du numéro de passeport est faux (6 -> 7).
MRZ_L2_INVALIDE = "L898902C37UTO7408122F1204159ZE184226B<<<<<10"

TEXTE_PASSEPORT_VALIDE = (
    "PASSEPORT / PASSPORT\nRÉPUBLIQUE FICTIVE D'UTOPIA\n"
    f"{MRZ_L1_VALIDE}\n{MRZ_L2_VALIDE}\n"
)
TEXTE_PASSEPORT_INVALIDE = (
    "PASSEPORT / PASSPORT\nRÉPUBLIQUE FICTIVE D'UTOPIA\n"
    f"{MRZ_L1_VALIDE}\n{MRZ_L2_INVALIDE}\n"
)
# Texte bruité (OCR) : espaces parasites dans les lignes MRZ, lignes de bruit autour.
TEXTE_PASSEPORT_BRUITE = (
    "~~ pa55eport |||  scan 300dpi\n"
    "P < UTOERIKSSON << ANNA < MARIA <<<<<<<<<<<<<<<<<<<\n"
    "L898902C36 UTO 7408122F1204159 ZE184226B<<<<<10\n"
    "...  \n"
)

TEXTE_RELEVE_BAC = (
    "RELEVÉ DE NOTES DU BACCALAURÉAT — SESSION 2023\n"
    "Établissement fictif : Lycée Exemple\n"
    "Mathématiques : 15,00\nPhysique : 13,50\n"
    "Moyenne générale : 14,52/20\n"
)
TEXTE_RELEVE_ANDERSSON = "RELEVÉ DE NOTES\nNom : ANDERSSON\nPrénom : Anna\nMoyenne générale : 12,10/20\n"

TEXTE_TCF = (
    "TEST DE CONNAISSANCE DU FRANÇAIS — TCF\n"
    "Attestation de résultats\n"
    "Niveau global obtenu : B2\n"
    "Date de passation : 12/03/2025\n"
)
TEXTE_DELF_B1 = "DIPLÔME D'ÉTUDES EN LANGUE FRANÇAISE DELF\nNiveau B1\nDate d'obtention : 03/06/2024\n"
TEXTE_DELF_INCOHERENT = "DELF\nNiveau C1\n"
TEXTE_TCF_PAR_COMPETENCE = (
    "TCF — Attestation de résultats\n"
    "Compréhension orale : B2\nCompréhension écrite : C1\nExpression orale : B1\n"
)
TEXTE_IELTS = "IELTS Test Report Form\nOverall Band Score 6.5\nTest date: 14 March 2025\n"
TEXTE_IELTS_CECRL = "IELTS Test Report Form\nOverall Band Score 7.0\nCEFR level: C1\n"


# --- Construction d'une MRZ avec chiffres de contrôle (implémentation indépendante du code testé) --
def _valeur(c: str) -> int:
    if c == "<":
        return 0
    if c.isdigit():
        return int(c)
    return ord(c) - ord("A") + 10


def chiffre_controle(champ: str) -> str:
    poids = (7, 3, 1)
    return str(sum(_valeur(c) * poids[i % 3] for i, c in enumerate(champ)) % 10)


def construire_mrz(
    *, nom: str, prenoms: str, numero: str, naissance_aammjj: str, sexe: str,
    expiration_aammjj: str, nationalite: str = "UTO",
) -> tuple[str, str]:
    l1 = ("P<" + nationalite + nom + "<<" + prenoms.replace(" ", "<")).ljust(44, "<")[:44]
    numero9 = numero.ljust(9, "<")
    perso = "<" * 14
    corps = (
        numero9 + chiffre_controle(numero9) + nationalite
        + naissance_aammjj + chiffre_controle(naissance_aammjj) + sexe
        + expiration_aammjj + chiffre_controle(expiration_aammjj)
        + perso + chiffre_controle(perso)
    )
    composite = chiffre_controle(corps[0:10] + corps[13:20] + corps[21:43])
    return l1, corps + composite


# --- PDF numérique minimal (couche texte) et PNG minimal ---------------------------------------
def _echapper_pdf(ligne: str) -> bytes:
    brut = ligne.encode("cp1252", errors="replace")
    return brut.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def construire_pdf_texte(pages: list[str]) -> bytes:
    """PDF 1.4 avec police Helvetica (WinAnsi) : une chaîne par page, lignes séparées par \\n."""
    objets: list[bytes] = []
    nb = len(pages)
    ids_pages = [4 + 2 * i for i in range(nb)]
    objets.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{i} 0 R" for i in ids_pages)
    objets.append(f"<< /Type /Pages /Kids [{kids}] /Count {nb} >>".encode())
    objets.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    for i, texte in enumerate(pages):
        flux = b"BT /F1 11 Tf 40 780 Td 14 TL\n"
        for ligne in texte.split("\n"):
            flux += b"(" + _echapper_pdf(ligne) + b") Tj T*\n"
        flux += b"ET"
        objets.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>"
            ).encode()
        )
        objets.append(b"<< /Length " + str(len(flux)).encode() + b" >>\nstream\n" + flux + b"\nendstream")
    sortie = bytearray(b"%PDF-1.4\n")
    positions = []
    for n, corps in enumerate(objets, start=1):
        positions.append(len(sortie))
        sortie += f"{n} 0 obj\n".encode() + corps + b"\nendobj\n"
    debut_xref = len(sortie)
    sortie += f"xref\n0 {len(objets) + 1}\n".encode() + b"0000000000 65535 f \n"
    for p in positions:
        sortie += f"{p:010d} 00000 n \n".encode()
    sortie += (
        f"trailer\n<< /Size {len(objets) + 1} /Root 1 0 R >>\nstartxref\n{debut_xref}\n%%EOF\n"
    ).encode()
    return bytes(sortie)


def construire_png_minimal() -> bytes:
    """PNG 1x1 valide (signature + IHDR + IDAT + IEND)."""

    def bloc(type_: bytes, donnees: bytes) -> bytes:
        return (
            struct.pack(">I", len(donnees)) + type_ + donnees
            + struct.pack(">I", zlib.crc32(type_ + donnees) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\xff\xff")
    return b"\x89PNG\r\n\x1a\n" + bloc(b"IHDR", ihdr) + bloc(b"IDAT", idat) + bloc(b"IEND", b"")


def pdf_factice(texte_pages: list[str]) -> bytes:
    """Faux « PDF » (signature %PDF- valide pour le dépôt) dont le contenu est le texte brut :
    lu par `LecteurFactice` des tests, sans dépendre de pypdf."""
    return b"%PDF-1.4\n" + "\f".join(texte_pages).encode("utf-8")
