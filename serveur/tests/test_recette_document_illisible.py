"""Recette : un document illisible reste signalé « bloqué » aux lectures suivantes de l'état.

Avant correctif, l'illisibilité n'apparaissait que dans la réponse de `lancer` ; un `GET /etat` (relance
de l'écran, interrogation périodique) la transformait en « en cours », sans fin, et désactivait le bouton.
"""

from __future__ import annotations

import uuid

from app.api.v1.extractions import obtenir_lecteur_document
from app.core.erreurs import DonneesInvalides
from tests import corpus_synthetique as corpus
from tests.test_extractions_api import LecteurFactice
from tests.test_dossier_automatique import (  # noqa: F401  (ctx : fixture importée)
    _candidat,
    _doc,
    _etape,
    _etat,
    _lancer,
    ctx,
)


class LecteurQuiRefuseLesImages(LecteurFactice):
    """Comme le lecteur du corpus, mais une image est illisible (aucun OCR installé, cas réel d'un poste léger)."""

    def lire_texte(self, contenu: bytes, type_mime: str):
        if type_mime.startswith("image/"):
            raise DonneesInvalides("Lecture impossible : aucun OCR n'est installé.")
        return super().lire_texte(contenu, type_mime)


def _deposer_image_illisible(cl, cid: str) -> str:
    rep = cl.post(
        f"/api/v1/candidats/{cid}/documents", data={"type_piece": "photo_identite"},
        files={"fichier": (f"{uuid.uuid4().hex}.png", corpus.construire_png_minimal(), "image/png")},
    )
    assert rep.status_code == 201, rep.text
    return rep.json()["id"]


def test_document_illisible_reste_bloque_apres_relecture_de_l_etat(ctx: dict) -> None:
    ctx["app"].dependency_overrides[obtenir_lecteur_document] = lambda: LecteurQuiRefuseLesImages()
    cl = ctx["client_a"]
    cid = _candidat(cl)
    _doc(cl, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE])
    _deposer_image_illisible(cl, cid)
    lancement = _lancer(cl, cid)
    assert _etape(lancement, "lecture")["statut"] == "bloque"
    for _ in range(2):
        etat = _etat(cl, cid)
        lecture = _etape(etat, "lecture")
        assert lecture["statut"] == "bloque", lecture
        assert lecture["compteurs"]["illisibles"] == 1
        assert "illisible" in lecture["detail"]


def test_page_du_dossier_automatique_branche_la_discussion_en_direct(ctx: dict) -> None:
    page = ctx["client_a"].get("/").text
    assert page.count("function monterDiscussionAgent(") == 1
    assert 'id="fd-carte-discussion"' in page and 'id="fd-discussion"' in page
    assert "fdDiscussion = monterDiscussionAgent(conteneur, tacheId);" in page
    assert page.count("fdSynchroniserDiscussion()") >= 4  # sélection, rendu, ouverture, changement de dossier
