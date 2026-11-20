"""Régression mobile : « Lancer l'analyse » après un simple choix de fichier, et texte d'attente trompeur."""

from __future__ import annotations

from playwright.sync_api import Page

from tests.test_interface_flux_dossier import Api, api, page_ui  # noqa: F401 - fixtures réutilisées


def test_mobile_lancer_apres_choix_de_fichier_depose_puis_lance(page_ui: Page, api: Api) -> None:
    page_ui.set_viewport_size({"width": 375, "height": 812})
    page_ui.evaluate("candidatActifId = null; fdChoisirEtudiant(''); fdAfficherSelection()")
    page_ui.select_option("#fd-etudiant", "c1")
    page_ui.wait_for_selector("#fd-contenu:not(.cache)")
    page_ui.set_input_files("#fd-fichiers", [{"name": "passeport.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.4"}])
    assert page_ui.locator(".fd-fichier").count() == 1
    page_ui.click("#fd-btn-lancer")  # sans passer par « Envoyer » : un clic suffit
    page_ui.wait_for_selector(".fd-etape-en_cours")
    appels = [(m, c) for m, c in api.appels if m == "POST"]
    iddoc = next(i for i, (_, c) in enumerate(appels) if c.endswith("/documents"))
    idlancer = next(i for i, (_, c) in enumerate(appels) if c.endswith("/dossier-automatique/lancer"))
    assert iddoc < idlancer  # le document est déposé AVANT le lancement
    assert page_ui.locator("#fd-btn-lancer").inner_text().strip() != "Lancer l'analyse"


def test_lancer_avec_fichier_sans_type_explique_quoi_faire_sans_lancer(page_ui: Page, api: Api) -> None:
    page_ui.set_viewport_size({"width": 375, "height": 812})
    page_ui.select_option("#fd-etudiant", "c1")
    page_ui.wait_for_selector("#fd-contenu:not(.cache)")
    page_ui.set_input_files("#fd-fichiers", [{"name": "scan123.png", "mimeType": "image/png", "buffer": b"x"}])
    page_ui.click("#fd-btn-lancer")
    assert "Choisissez le type" in page_ui.locator(".fd-fichier-erreur").inner_text()
    assert not any(c.endswith("/dossier-automatique/lancer") for _, c in api.appels)
    assert page_ui.locator("#fd-btn-lancer").is_enabled()  # le bouton redevient utilisable


def test_texte_d_attente_n_annonce_plus_une_analyse_absente_apres_creation(page_ui: Page) -> None:
    page_ui.select_option("#fd-etudiant", "c1")
    page_ui.wait_for_selector("#fd-contenu:not(.cache)")
    texte = page_ui.locator("#fd-progres-texte").inner_text()
    assert "Aucune analyse lancée" not in texte
    assert "déposez les documents" in texte
