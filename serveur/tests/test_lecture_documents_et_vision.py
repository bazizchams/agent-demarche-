"""Lecteur A (couche texte PDF, OCR local), message clair sans l'extra `lecture`, lecteur B (vision)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.core.config import Parametres
from app.core.erreurs import DonneesInvalides, ServiceIndisponible
from app.services import lecture_documents as lecture
from app.services.anonymisation_ia import ClientAnonymisant
from app.services.lecture_documents import ImagePage, LecteurDocumentLocal
from app.services.lecture_vision import LecteurVision, construire_lecteur_vision
from app.services.llm import ClientAnthropic, ClientOpenAICompatible, ImageEntree, ReponseLLM
from tests import corpus_synthetique as corpus

# ------------------------------------------------------------------ lecteur A


def test_pdf_numerique_lit_la_couche_texte() -> None:
    pytest.importorskip("pypdf")
    pdf = corpus.construire_pdf_texte([corpus.TEXTE_RELEVE_BAC, "Deuxième page : texte simple"])
    res = LecteurDocumentLocal().lire_texte(pdf, "application/pdf")
    assert [p.numero for p in res.pages] == [1, 2]
    assert all(p.origine == "couche_texte" for p in res.pages)
    assert "Moyenne générale : 14,52/20" in res.pages[0].texte
    assert "Deuxième page" in res.pages[1].texte


def test_pdf_numerique_passeport_mrz_lisible_par_les_parseurs() -> None:
    pytest.importorskip("pypdf")
    from app.services.extraction_champs import analyser_mrz

    pdf = corpus.construire_pdf_texte([corpus.TEXTE_PASSEPORT_VALIDE])
    res = LecteurDocumentLocal().lire_texte(pdf, "application/pdf")
    champs = {c.champ: c for c in analyser_mrz(res.pages[0].texte)}
    assert champs["numero_passeport"].valeur == "L898902C3" and champs["numero_passeport"].controle_fort


def test_sans_pypdf_message_clair_et_application_importable(monkeypatch: pytest.MonkeyPatch) -> None:
    def _absent() -> Any:
        raise ImportError("pypdf absent")

    monkeypatch.setattr(lecture, "_importer_pypdf", _absent)
    with pytest.raises(ServiceIndisponible) as exc:
        LecteurDocumentLocal().lire_texte(corpus.construire_pdf_texte(["x"]), "application/pdf")
    assert "lecture" in exc.value.message and "pip install" in exc.value.message


def test_image_sans_moteur_ocr_message_clair(monkeypatch: pytest.MonkeyPatch) -> None:
    def _absent() -> Any:
        raise ImportError("rapidocr absent")

    monkeypatch.setattr(lecture, "_charger_moteur_rapidocr", _absent)
    with pytest.raises(ServiceIndisponible) as exc:
        LecteurDocumentLocal().lire_texte(corpus.construire_png_minimal(), "image/png")
    assert "OCR" in exc.value.message and "lecture" in exc.value.message


class _OcrFactice:
    def __init__(self, lignes: list[tuple[str, float]]) -> None:
        self.appels = 0
        self._lignes = lignes

    def reconnaitre(self, image: bytes) -> list[tuple[str, float]]:
        self.appels += 1
        return self._lignes


def test_image_passe_par_l_ocr_et_confiance_moyenne() -> None:
    ocr = _OcrFactice([("Moyenne générale : 14,52/20", 0.9), ("Nom : DUPONT", 0.7)])
    res = LecteurDocumentLocal(moteur_ocr=ocr).lire_texte(corpus.construire_png_minimal(), "image/png")
    assert ocr.appels == 1
    assert res.pages[0].origine == "ocr"
    assert res.pages[0].texte == "Moyenne générale : 14,52/20\nNom : DUPONT"
    assert res.pages[0].confiance == pytest.approx(0.8)


def test_image_extraite_pour_le_lecteur_b() -> None:
    png = corpus.construire_png_minimal()
    images = LecteurDocumentLocal().extraire_images(png, "image/png")
    assert images == [ImagePage(page=1, octets=png, type_mime="image/png")]


def test_type_mime_non_supporte_refuse() -> None:
    with pytest.raises(DonneesInvalides):
        LecteurDocumentLocal().lire_texte(b"x", "application/zip")


# ------------------------------------------------------------------ lecteur B (vision)


def _params(**kw: Any) -> Parametres:
    return Parametres(environnement="test", **kw)


def test_vision_desactivee_par_defaut() -> None:
    assert _params().vision_active is False
    assert construire_lecteur_vision(_params()) is None
    assert construire_lecteur_vision(_params(vision_url_base="http://127.0.0.1:11434/v1", vision_modele="m")) is None


@pytest.mark.parametrize(
    "url",
    ["https://api.openai.com/v1", "https://exemple.org/v1", "http://8.8.8.8:11434/v1", "http://ollama.exemple.com/v1"],
)
def test_vision_refuse_tout_hote_non_local(url: str) -> None:
    p = _params(vision_active=True, vision_url_base=url, vision_modele="llava")
    with pytest.raises(ServiceIndisponible) as exc:
        construire_lecteur_vision(p)
    assert "local" in exc.value.message


def test_vision_exige_url_et_modele() -> None:
    with pytest.raises(ServiceIndisponible):
        construire_lecteur_vision(_params(vision_active=True))


def test_vision_locale_acceptee() -> None:
    p = _params(vision_active=True, vision_url_base="http://127.0.0.1:11434/v1", vision_modele="llava")
    assert isinstance(construire_lecteur_vision(p), LecteurVision)


def test_client_openai_compatible_refuse_les_images_vers_un_hote_distant_sans_aucun_appel_reseau() -> None:
    appels: list[int] = []

    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        appels.append(1)
        return httpx.Response(200, json={})

    client = ClientOpenAICompatible(
        url_base="https://api.distant.example/v1", modele="m", transport=httpx.MockTransport(gestionnaire)
    )
    with pytest.raises(ServiceIndisponible):
        client.generer(systeme="s", message="m", images=[ImageEntree(octets=b"x", type_mime="image/png")])
    assert appels == []


def test_clients_anthropic_et_anonymisant_refusent_les_images() -> None:
    img = [ImageEntree(octets=b"x", type_mime="image/png")]
    anthropic = ClientAnthropic(cle="k", modele="m", url="https://api.anthropic.com/v1/messages", delai_secondes=5)
    with pytest.raises(ServiceIndisponible):
        anthropic.generer(systeme="s", message="m", images=img)

    class _Interne:
        def generer(self, **kw: Any) -> ReponseLLM:  # pragma: no cover - ne doit jamais être appelé
            raise AssertionError("l'image ne doit pas atteindre le client interne")

    with pytest.raises(ServiceIndisponible):
        ClientAnonymisant(_Interne()).generer(systeme="s", message="m", images=img)  # type: ignore[arg-type]


def test_client_openai_compatible_local_envoie_l_image_en_data_uri() -> None:
    corps_recu: dict[str, Any] = {}

    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        corps_recu.update(json.loads(requete.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}], "usage": {}})

    client = ClientOpenAICompatible(
        url_base="http://127.0.0.1:11434/v1", modele="llava", transport=httpx.MockTransport(gestionnaire)
    )
    client.generer(systeme="s", message="lis", images=[ImageEntree(octets=b"\x89PNG", type_mime="image/png")])
    contenu = corps_recu["messages"][1]["content"]
    assert isinstance(contenu, list)
    assert contenu[0] == {"type": "text", "text": "lis"}
    assert contenu[1]["type"] == "image_url"
    assert contenu[1]["image_url"]["url"].startswith("data:image/png;base64,")


class _ClientVisionFactice:
    def __init__(self, champs: list[dict[str, Any]]) -> None:
        self.champs = champs
        self.images_recues: list[ImageEntree] = []

    def generer(self, *, systeme: str, message: str, outil=None, max_tokens: int = 4096, images=None) -> ReponseLLM:
        self.images_recues = list(images or [])
        return ReponseLLM(texte="", outil={"champs": self.champs})


def test_lecteur_vision_convertit_la_reponse_en_champs_lus() -> None:
    client = _ClientVisionFactice(
        [
            {"champ": "moyenne_generale", "valeur": "14,52", "page": 1, "extrait": "Moyenne générale : 14,52/20"},
            {"champ": "champ_hors_liste", "valeur": "x", "page": 1, "extrait": "x"},
            {"champ": "nom", "valeur": "", "page": 1, "extrait": "Nom :"},
        ]
    )
    lecteur = LecteurVision(client)  # type: ignore[arg-type]
    champs = lecteur.lire_champs(
        [ImagePage(page=1, octets=b"\x89PNG", type_mime="image/png")], famille="releve_notes"
    )
    assert [c.champ for c in champs] == ["moyenne_generale"]  # hors liste et vide ignorés (règle 4)
    assert champs[0].valeur == "14.52" and champs[0].page == 1
    assert len(client.images_recues) == 1


def test_lecteur_vision_reponse_illisible_ne_produit_aucune_valeur() -> None:
    class _Illisible:
        def generer(self, **kw: Any) -> ReponseLLM:
            return ReponseLLM(texte="je ne sais pas", outil=None)

    assert LecteurVision(_Illisible()).lire_champs(  # type: ignore[arg-type]
        [ImagePage(page=1, octets=b"x", type_mime="image/png")], famille="passeport"
    ) == []
