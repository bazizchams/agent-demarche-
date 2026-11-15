"""Régression : une erreur pendant la lecture d'une page PDF ne doit pas passer pour une page vide.

Aujourd'hui, `_lire_pdf` avale silencieusement les exceptions de `page.extract_text()` et de
`page.images` : la page est alors signalée comme « aucun texte exploitable », ce qui masque la
vraie cause. Ces tests attendent un avertissement distinct qui nomme l'échec et la page, sans
jamais recopier le message de l'exception (il peut citer un contenu du document).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.services import lecture_documents as lecture
from app.services.lecture_documents import LecteurDocumentLocal

PDF_FACTICE = b"%PDF-1.4 faux document, jamais analyse par pypdf reel"
MESSAGE_AUCUN_TEXTE = "aucun texte exploitable"
MESSAGE_ECHEC_COUCHE_TEXTE = "échec d'extraction de la couche texte"
MESSAGE_ECHEC_IMAGES = "échec d'extraction des images"


class _LecteurPdfFactice:
    is_encrypted = False

    def __init__(self, pages: list[Any]) -> None:
        self.pages = pages


class _PageTexteEnEchec:
    """Page dont la couche texte lève une exception ; aucune image."""

    images: list[Any] = []

    def extract_text(self) -> str:
        raise RuntimeError("SECRET-123 contenu du document")


class _PageImagesEnEchec:
    """Page sans texte dont l'accès aux images lève une exception."""

    def extract_text(self) -> str:
        return ""

    @property
    def images(self) -> list[Any]:
        raise RuntimeError("SECRET-456 flux image corrompu")


class _PageVide:
    """Page sans texte et sans image, sans aucune erreur."""

    images: list[Any] = []

    def extract_text(self) -> str:
        return ""


def _installer_pypdf_factice(monkeypatch: pytest.MonkeyPatch, pages: list[Any]) -> None:
    module_pypdf = SimpleNamespace(PdfReader=lambda flux: _LecteurPdfFactice(pages))
    monkeypatch.setattr(lecture, "_importer_pypdf", lambda: module_pypdf)


def test_erreur_extract_text_signalee_comme_echec_sans_fuite_du_contenu(monkeypatch: pytest.MonkeyPatch) -> None:
    _installer_pypdf_factice(monkeypatch, [_PageTexteEnEchec()])

    res = LecteurDocumentLocal().lire_texte(PDF_FACTICE, "application/pdf")

    assert any(MESSAGE_ECHEC_COUCHE_TEXTE in a and "Page 1" in a for a in res.avertissements)
    assert not any(MESSAGE_AUCUN_TEXTE in a for a in res.avertissements)
    assert not any("SECRET-123" in a for a in res.avertissements)


def test_erreur_acces_aux_images_signalee_comme_echec_sans_fuite_du_contenu(monkeypatch: pytest.MonkeyPatch) -> None:
    _installer_pypdf_factice(monkeypatch, [_PageImagesEnEchec()])

    res = LecteurDocumentLocal().lire_texte(PDF_FACTICE, "application/pdf")

    assert any(MESSAGE_ECHEC_IMAGES in a and "Page 1" in a for a in res.avertissements)
    assert not any(MESSAGE_AUCUN_TEXTE in a for a in res.avertissements)
    assert not any("SECRET-456" in a for a in res.avertissements)


def test_page_vide_sans_erreur_garde_le_message_aucun_texte_exploitable(monkeypatch: pytest.MonkeyPatch) -> None:
    _installer_pypdf_factice(monkeypatch, [_PageVide()])

    res = LecteurDocumentLocal().lire_texte(PDF_FACTICE, "application/pdf")

    assert any(MESSAGE_AUCUN_TEXTE in a and "Page 1" in a for a in res.avertissements)
    assert not any("échec d'extraction" in a for a in res.avertissements)
