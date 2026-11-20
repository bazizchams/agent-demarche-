"""Écran de revue : bouton « Tout confirmer et remplir la fiche » (Playwright, API simulée)."""

from __future__ import annotations

import json

from fastapi import FastAPI

from app.interface import ecran_revue_extractions as ecran
from tests.test_interface_coffre_validation import CANDIDAT_ID, _moquettes, _page_simulee

DOC_ID = "33333333-3333-4333-8333-333333333333"
ID_FIABLE, ID_DOUTEUSE = "44444444-4444-4444-8444-444444444441", "44444444-4444-4444-8444-444444444442"
PIEGE = "<img src=x onerror=\"window.__pwned = 1\">"


def _extraction(identifiant: str, champ: str, valeur: str, statut: str, motif: str | None) -> dict:
    return {
        "id": identifiant, "document_id": DOC_ID, "candidat_id": CANDIDAT_ID, "champ": champ, "valeur": valeur,
        "valeur_alternative": None, "page": 1, "extrait": "Ligne du document : " + valeur, "source": "A",
        "confiance": 0.9, "statut": statut, "motif": motif, "decide_par_id": None, "decide_le": None,
        "applique_le": None, "cree_le": "2026-11-20T10:00:00", "modifie_le": "2026-11-20T10:00:00",
    }


def _moq(role: str, nb_fiables: int = 1) -> dict:
    base = f"/api/v1/candidats/{CANDIDAT_ID}"
    moq = _moquettes(role)
    moq[("GET", base + "/documents")] = (200, [])
    moq[("GET", base + "/extractions")] = (200, [
        _extraction(ID_FIABLE, "numero_passeport", "L898902C3", "auto", "controle_icao"),
        _extraction(ID_DOUTEUSE, "moyenne_generale", PIEGE, "a_verifier", "double_lecture_absente"),
    ])
    moq[("GET", base + "/extractions/synthese")] = (200, {
        "nb_fiables": nb_fiables, "nb_douteuses": 1, "nb_deja_confirmees": 0,
        "items": [
            {"extraction_id": ID_FIABLE, "niveau": "fiable", "raison": "mrz_valide", "conflit_fiche": False},
            {"extraction_id": ID_DOUTEUSE, "niveau": "douteuse", "raison": "double_lecture_absente", "conflit_fiche": False},
        ],
        "a_completer": ["niveau_francais", "mention"],
    })
    moq[("POST", base + "/extractions/valider-lot")] = (200, {
        "nb_valides": 1, "nb_ignores": 0, "nb_douteuses_restantes": 1,
        "rapport": {"appliques": [{"champ": "numero_passeport", "extraction_id": ID_FIABLE}], "conflits": [],
                    "deja_identiques": [], "hors_fiche": [], "a_verifier_restants": 1},
    })
    return moq


def _ouvrir(page) -> None:
    page.click('aside button.nav-btn[data-vue="vue-revue-extractions"]')
    page.wait_for_selector("#rx-liste .carte")


def test_statique_bouton_lot_present_et_envoie_seulement_les_fiables() -> None:
    assert "Tout confirmer et remplir la fiche" in ecran.HTML_VUE
    assert "rxIdsFiables()" in ecran.JS_REVUE and "/extractions/valider-lot" in ecran.JS_REVUE


def test_un_clic_confirme_les_fiables_surligne_les_douteuses_et_liste_a_completer(application: FastAPI) -> None:
    with _page_simulee(application, _moq("employe")) as (page, erreurs, requetes):
        _ouvrir(page)
        assert page.locator("#rx-liste .rx-carte.rx-douteuse").count() == 1  # seule la douteuse est surlignée
        assert "1 valeur(s) fiable(s)" in page.inner_text("#rx-lot-texte")
        assert "Niveau de français" in page.inner_text("#rx-lot-details")
        assert page.evaluate("window.__pwned") is None  # valeur piégée affichée en texte
        page.click("#rx-btn-lot")
        page.wait_for_function("document.getElementById('notif-statut').textContent.includes('rempli')"
                               " || document.body.textContent.includes('champ(s) de la fiche rempli')")
        envoi = next(r for r in requetes if r["chemin"].endswith("/extractions/valider-lot"))
        assert envoi["methode"] == "POST" and envoi["csrf"] == "csrf-test"
        assert json.loads(envoi["corps"]) == {"extraction_ids": [ID_FIABLE]}  # jamais la douteuse
        # aucune confirmation individuelle n'a été envoyée pour la douteuse
        assert not any(r["chemin"].endswith(f"/{ID_DOUTEUSE}/valider") for r in requetes)
    assert erreurs == []


def test_lecture_seule_ne_peut_pas_lancer_le_lot(application: FastAPI) -> None:
    with _page_simulee(application, _moq("lecture_seule")) as (page, erreurs, requetes):
        _ouvrir(page)
        assert page.is_disabled("#rx-btn-lot")
        assert not any(r["chemin"].endswith("/valider-lot") for r in requetes)
    assert erreurs == []


def test_bouton_lot_inactif_sans_valeur_fiable(application: FastAPI) -> None:
    moq = _moq("employe", nb_fiables=0)
    base = f"/api/v1/candidats/{CANDIDAT_ID}/extractions/synthese"
    corps = moq[("GET", base)][1]
    corps["items"] = [i for i in corps["items"] if i["niveau"] == "douteuse"]
    with _page_simulee(application, moq) as (page, erreurs, requetes):
        _ouvrir(page)
        assert page.is_disabled("#rx-btn-lot")
    assert erreurs == []
