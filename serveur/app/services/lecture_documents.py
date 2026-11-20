"""Lecteur A des documents : texte natif des PDF, sinon OCR local (RapidOCR, fra + eng).

- Couche texte d'abord (pypdf) : exacte, rapide ; une page sans texte exploitable passe par l'OCR
  sur ses images intégrées ; une image (PNG, JPEG) passe directement par l'OCR.
- Tout est LOCAL : aucun contenu de document ne quitte le serveur.
- Les dépendances vivent dans l'extra `lecture` (pyproject.toml) et sont importées au dernier
  moment : sans l'extra, l'application et ses tests fonctionnent ; seule la lecture d'un
  document répond par une erreur claire (503) disant quoi installer.
- Jamais de contenu de document dans les messages d'erreur ni les journaux (règle 5).
- Bornes anti-abus (un fichier déposé est une entrée non fiable) : une image au-delà de
  `MAX_PIXELS_IMAGE` est refusée AVANT l'OCR (dimensions lues par Pillow sans décoder l'image),
  le nombre d'images décodées par page est plafonné et la lecture d'un PDF s'arrête au-delà de
  `DELAI_MAX_LECTURE_S` (avertissement : lecture partielle).
"""

from __future__ import annotations

import io
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

from app.core.erreurs import DonneesInvalides, ServiceIndisponible

MAX_PAGES_LUES = 30
MAX_PIXELS_IMAGE = 25_000_000  # ~25 Mpx : au-delà, refus avant tout décodage ou OCR
MAX_IMAGES_PAR_PAGE = 5
DELAI_MAX_LECTURE_S = 120.0  # durée totale maximale de lecture d'un document (vérifiée entre les pages)
SEUIL_COUCHE_TEXTE = 20  # caractères non blancs minimum pour considérer qu'une page a un texte natif
ORIGINE_COUCHE_TEXTE = "couche_texte"
ORIGINE_OCR = "ocr"
TYPES_IMAGE = ("image/png", "image/jpeg")
CONSEIL_INSTALLATION = "installez l'extra « lecture » du serveur (pip install -e .[lecture])"


@dataclass(frozen=True)
class PageTexte:
    numero: int
    texte: str
    origine: str  # « couche_texte » ou « ocr »
    confiance: float


@dataclass(frozen=True)
class ResultatLecture:
    pages: tuple[PageTexte, ...]
    avertissements: tuple[str, ...]


@dataclass(frozen=True)
class ImagePage:
    page: int
    octets: bytes
    type_mime: str


class MoteurOcr(Protocol):
    def reconnaitre(self, image: bytes) -> list[tuple[str, float]]: ...


class LecteurDocument(Protocol):
    """Contrat injectable (dépendance FastAPI) : lecture du texte et des images d'un document."""

    def lire_texte(self, contenu: bytes, type_mime: str) -> ResultatLecture: ...

    def extraire_images(self, contenu: bytes, type_mime: str) -> list[ImagePage]: ...


# ----------------------------------------------------------------------------- imports paresseux
def _importer_pypdf() -> Any:
    import pypdf  # noqa: PLC0415 - import paresseux voulu (extra optionnel)

    return pypdf


def _importer_pillow() -> Any:
    from PIL import Image  # noqa: PLC0415 - import paresseux voulu (extra optionnel)

    return Image


def _verifier_dimensions_image(octets: bytes) -> None:
    """Refuse une image de plus de `MAX_PIXELS_IMAGE` pixels sans la décoder (en-tête seulement).
    Sans Pillow, aucun OCR réel n'est possible non plus (RapidOCR en dépend) : rien à protéger."""
    try:
        image_pil = _importer_pillow()
    except ImportError:
        return
    image_pil.MAX_IMAGE_PIXELS = MAX_PIXELS_IMAGE  # Pillow refuse lui-même les bombes de décompression
    try:
        with image_pil.open(io.BytesIO(octets)) as image:
            largeur, hauteur = image.size
    except Exception as exc:  # image corrompue ou bombe détectée par Pillow : jamais de détail du contenu
        raise DonneesInvalides("Image illisible ou trop grande : lecture impossible.") from exc
    if largeur * hauteur > MAX_PIXELS_IMAGE:
        raise DonneesInvalides(
            f"Image trop grande (plus de {MAX_PIXELS_IMAGE // 1_000_000} millions de pixels) : lecture impossible."
        )


def _trouver_paire_mrz(textes: list[str]) -> tuple[str, str] | None:
    """Paire de lignes MRZ consécutives (ligne 1 « P< »), réparée et vérifiée par les chiffres de contrôle."""
    from app.services.extraction_champs import reparer_lignes_mrz  # noqa: PLC0415 - évite un cycle d'import

    for i, premiere in enumerate(textes[:-1]):
        if premiere.upper().replace(" ", "").startswith("P<"):
            reparee = reparer_lignes_mrz(premiere, textes[i + 1])
            if reparee is not None:
                return reparee
    return None


def _bandes_mrz(image: bytes) -> list[bytes]:
    """Bandes candidates (PNG) autour de la dernière zone d'encre de la page, agrandies ×2 puis ×1."""
    try:
        image_pil = _importer_pillow()
        from PIL import ImageOps  # noqa: PLC0415

        with image_pil.open(io.BytesIO(image)) as brute:
            gris = brute.convert("L")
        largeur, hauteur = gris.size
        donnees = gris.tobytes()
        derniere = -1
        for y in range(hauteur - 1, -1, -1):
            ligne = donnees[y * largeur : (y + 1) * largeur]
            if sum(1 for p in ligne if p < 140) > 3:
                derniere = y
                break
        if derniere < 0:
            return []
        bande = gris.crop((0, max(0, derniere - 180), largeur, min(hauteur, derniere + 25)))
        resultat = []
        for facteur in (2, 1):
            agrandie = ImageOps.autocontrast(bande.resize((bande.width * facteur, bande.height * facteur)))
            tampon = io.BytesIO()
            agrandie.save(tampon, format="PNG")
            resultat.append(tampon.getvalue())
        return resultat
    except Exception:  # image exotique : la lecture normale reste valable
        return []


class _MoteurRapidOcr:
    """Adaptateur RapidOCR (v2 `rapidocr`, ou v1 `rapidocr_onnxruntime`)."""

    def __init__(self, moteur: Any) -> None:
        self._moteur = moteur

    def reconnaitre(self, image: bytes) -> list[tuple[str, float]]:
        try:
            sortie = self._moteur(image)
        except Exception as exc:  # le message d'une exception d'OCR peut citer un contenu
            raise ServiceIndisponible("Le moteur OCR local a échoué sur cette image.") from exc
        textes = getattr(sortie, "txts", None)
        if textes is not None:
            scores = getattr(sortie, "scores", None) or [1.0] * len(textes)
            return [(str(t), float(s)) for t, s in zip(textes, scores)]
        resultat = sortie[0] if isinstance(sortie, tuple) else sortie
        return [(str(ligne[1]), float(ligne[2])) for ligne in (resultat or [])]


@lru_cache(maxsize=1)
def _moteur_rapidocr_partage() -> _MoteurRapidOcr:
    try:
        from rapidocr import RapidOCR  # noqa: PLC0415 - v2

        # Modèle « fr » (alphabet latin accentué) : « latin » n'existe pas dans toutes les versions et son échec
        # n'apparaît qu'à la première lecture (ce qui rendait toute lecture indisponible).
        moteur = RapidOCR(params={"Rec.lang_type": "fr"})
    except ImportError:
        from rapidocr_onnxruntime import RapidOCR as RapidOCRv1  # noqa: PLC0415

        moteur = RapidOCRv1()
    return _MoteurRapidOcr(moteur)


def _charger_moteur_rapidocr() -> MoteurOcr:
    return _moteur_rapidocr_partage()


# ----------------------------------------------------------------------------- lecteur local
def _mime_depuis_signature(octets: bytes) -> str | None:
    if octets.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if octets.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


class LecteurDocumentLocal:
    def __init__(self, moteur_ocr: MoteurOcr | None = None) -> None:
        self._moteur_ocr = moteur_ocr

    # -- OCR
    def _ocr(self) -> MoteurOcr:
        if self._moteur_ocr is None:
            try:
                self._moteur_ocr = _charger_moteur_rapidocr()
            except ImportError as exc:
                raise ServiceIndisponible(
                    "La lecture par OCR n'est pas disponible : " + CONSEIL_INSTALLATION + "."
                ) from exc
        return self._moteur_ocr

    def _page_ocr(self, numero: int, image: bytes) -> PageTexte:
        _verifier_dimensions_image(image)
        lignes = [(t.strip(), s) for t, s in self._ocr().reconnaitre(image) if t and t.strip()]
        lignes = self._completer_mrz(image, lignes)
        if not lignes:
            return PageTexte(numero, "", ORIGINE_OCR, 0.0)
        confiance = sum(s for _, s in lignes) / len(lignes)
        return PageTexte(numero, "\n".join(t for t, _ in lignes), ORIGINE_OCR, confiance)

    def _completer_mrz(self, image: bytes, lignes: list[tuple[str, float]]) -> list[tuple[str, float]]:
        """Passeport : la zone MRZ (petits caractères « < ») est mal lue sur la page entière. Si une ligne 1
        de MRZ est vue mais pas la paire complète valide, on relit la dernière bande d'encre de la page,
        agrandie, puis on remplace les lignes MRZ par la paire corrigée dont les chiffres de contrôle sont
        TOUS bons. Sinon le texte reste tel que lu (aucune correction non vérifiée)."""
        if not any(t.upper().replace(" ", "").startswith("P<") for t, _ in lignes):
            return lignes
        paire = _trouver_paire_mrz([t for t, _ in lignes])  # paire lisible : au moins corrige O/0 des noms
        if paire is not None:
            return self._remplacer_mrz(lignes, paire)

        for bande in _bandes_mrz(image):
            textes = [t for t, _ in self._ocr().reconnaitre(bande) if t and t.strip()]
            paire = _trouver_paire_mrz(textes)
            if paire is not None:
                break
        if paire is None:
            return lignes
        return self._remplacer_mrz(lignes, paire)

    @staticmethod
    def _remplacer_mrz(lignes: list[tuple[str, float]], paire: tuple[str, str]) -> list[tuple[str, float]]:
        garde = [(t, s) for t, s in lignes if "<" not in t and not t.upper().replace(" ", "").startswith("P<")]
        return [*garde, (paire[0], 1.0), (paire[1], 1.0)]

    # -- PDF
    @staticmethod
    def _pypdf() -> Any:
        try:
            return _importer_pypdf()
        except ImportError as exc:
            raise ServiceIndisponible(
                "La lecture des PDF n'est pas disponible : " + CONSEIL_INSTALLATION + "."
            ) from exc

    def _ouvrir_pdf(self, contenu: bytes) -> Any:
        pypdf = self._pypdf()
        try:
            lecteur = pypdf.PdfReader(io.BytesIO(contenu))
            if lecteur.is_encrypted and not lecteur.decrypt(""):
                raise DonneesInvalides("PDF protégé par mot de passe : lecture impossible.")
            _ = len(lecteur.pages)
        except DonneesInvalides:
            raise
        except Exception as exc:
            raise DonneesInvalides("PDF illisible ou corrompu : lecture impossible.") from exc
        return lecteur

    @staticmethod
    def _images_de_page(page: Any, echec: list[bool] | None = None) -> list[tuple[bytes, str]]:
        """Images intégrées de la page ; en cas d'échec d'accès, ajoute True à `echec` (sans détail)."""
        images: list[tuple[bytes, str]] = []
        try:
            for img in page.images:
                mime = _mime_depuis_signature(img.data)
                if mime is not None:
                    images.append((img.data, mime))
                if len(images) >= MAX_IMAGES_PAR_PAGE:
                    break  # plafond : on n'extrait pas (ni ne décode) les images suivantes
        except Exception:  # image exotique ou flux invalide : jamais de détail (peut citer un contenu)
            if echec is not None:
                echec.append(True)
            return []
        return images

    def _lire_pdf(self, contenu: bytes) -> ResultatLecture:
        lecteur = self._ouvrir_pdf(contenu)
        pages: list[PageTexte] = []
        avertissements: list[str] = []
        total = len(lecteur.pages)
        if total > MAX_PAGES_LUES:
            avertissements.append(f"Seules les {MAX_PAGES_LUES} premières pages sur {total} ont été lues.")
        debut = time.monotonic()
        for numero, page in enumerate(lecteur.pages[:MAX_PAGES_LUES], start=1):
            if numero > 1 and time.monotonic() - debut > DELAI_MAX_LECTURE_S:
                avertissements.append(
                    f"Délai de lecture dépassé : seules les {numero - 1} premières pages ont été lues."
                )
                break
            echec_texte = False
            try:
                texte = (page.extract_text() or "").strip()
            except Exception:  # le message d'une exception peut citer un contenu : on ne le recopie pas
                texte, echec_texte = "", True
                avertissements.append(f"Page {numero} : échec d'extraction de la couche texte.")
            if len("".join(texte.split())) >= SEUIL_COUCHE_TEXTE:
                pages.append(PageTexte(numero, texte, ORIGINE_COUCHE_TEXTE, 1.0))
                continue
            echec_images: list[bool] = []
            images = self._images_de_page(page, echec_images)
            if echec_images:
                avertissements.append(f"Page {numero} : échec d'extraction des images.")
            if not images:
                pages.append(PageTexte(numero, texte, ORIGINE_COUCHE_TEXTE, 1.0 if texte else 0.0))
                if not echec_texte and not echec_images:
                    avertissements.append(f"Page {numero} : aucun texte exploitable.")
                continue
            lue = self._page_ocr(numero, images[0][0])
            pages.append(lue)
            if not lue.texte:
                avertissements.append(f"Page {numero} : l'OCR n'a trouvé aucun texte.")
        return ResultatLecture(tuple(pages), tuple(avertissements))

    # -- interface publique
    def lire_texte(self, contenu: bytes, type_mime: str) -> ResultatLecture:
        if type_mime == "application/pdf":
            return self._lire_pdf(contenu)
        if type_mime in TYPES_IMAGE:
            page = self._page_ocr(1, contenu)
            avert = () if page.texte else ("Page 1 : l'OCR n'a trouvé aucun texte.",)
            return ResultatLecture((page,), avert)
        raise DonneesInvalides("Type de document non lisible (PDF, PNG ou JPEG attendus).")

    def extraire_images(self, contenu: bytes, type_mime: str) -> list[ImagePage]:
        """Images à transmettre au lecteur B : le document lui-même si c'est une image, sinon
        la première image intégrée de chaque page (PDF numérique : aucune, rien à voir)."""
        if type_mime in TYPES_IMAGE:
            return [ImagePage(page=1, octets=contenu, type_mime=type_mime)]
        if type_mime != "application/pdf":
            raise DonneesInvalides("Type de document non lisible (PDF, PNG ou JPEG attendus).")
        lecteur = self._ouvrir_pdf(contenu)
        resultat: list[ImagePage] = []
        for numero, page in enumerate(lecteur.pages[:MAX_PAGES_LUES], start=1):
            images = self._images_de_page(page)
            if images:
                resultat.append(ImagePage(page=numero, octets=images[0][0], type_mime=images[0][1]))
        return resultat
