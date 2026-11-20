"""Écran « Dossier automatique » : états du stepper, célébration, mouvement réduit et 375 px (Chromium, API simulée)."""

from __future__ import annotations

from playwright.sync_api import Page

from tests.test_interface_flux_dossier import CODES, Api, _etat, api, page_ui  # noqa: F401  (fixtures réutilisées)


def _ouvrir(page: Page) -> None:
    page.select_option("#fd-etudiant", "c1")
    page.wait_for_selector(".fd-etape")


def test_stepper_quatre_statuts_lisibles_sans_couleur(page_ui: Page, api: Api) -> None:
    api.etat = _etat({"pieces": "termine", "lecture": "en_cours", "revue_valeurs": "a_verifier", "fiche": "bloque"}, 30)
    _ouvrir(page_ui)
    page_ui.wait_for_selector(".fd-etape-bloque")
    for code, statut, texte in [("pieces", "termine", "Terminé"), ("lecture", "en_cours", "En cours"),
                                ("revue_valeurs", "a_verifier", "À vérifier"), ("fiche", "bloque", "Bloqué")]:
        li = page_ui.locator(f'.fd-etape[data-code="{code}"]')
        assert "fd-etape-" + statut in li.get_attribute("class")
        assert texte in li.locator(".badge").inner_text()
    # forme distincte : cercle plein / pointillé / carré arrondi ; icône pour terminé, à vérifier et bloqué
    assert page_ui.locator('.fd-etape[data-code="pieces"] .fd-marqueur svg path.fd-coche').count() == 1
    assert page_ui.locator('.fd-etape[data-code="revue_valeurs"] .fd-marqueur svg').count() == 1
    assert page_ui.locator('.fd-etape[data-code="fiche"] .fd-marqueur svg').count() == 1
    style = page_ui.eval_on_selector('.fd-etape[data-code="revue_valeurs"] .fd-marqueur', "e => getComputedStyle(e).borderTopStyle")
    assert style == "dashed"
    rayon = page_ui.eval_on_selector('.fd-etape[data-code="fiche"] .fd-marqueur', "e => getComputedStyle(e).borderTopLeftRadius")
    assert rayon != "17px" and rayon != "50%"


def test_transition_en_place_coche_tracee_et_compteur(page_ui: Page, api: Api) -> None:
    api.etat = _etat({"pieces": "termine", "lecture": "en_cours"}, 15)
    _ouvrir(page_ui)
    page_ui.wait_for_function("document.getElementById('fd-progres-chiffre').textContent === '15 %'")
    li = page_ui.locator('.fd-etape[data-code="lecture"]')
    page_ui.evaluate("document.querySelector('.fd-etape[data-code=lecture]').setAttribute('data-test', 'meme')")
    api.etat = _etat({"pieces": "termine", "lecture": "termine"}, 30)
    page_ui.click("#fd-btn-actualiser")
    page_ui.wait_for_function("document.getElementById('fd-progres-chiffre').textContent === '30 %'")
    # le même nœud est mis à jour (la transition CSS peut jouer) et la coche est tracée
    assert li.get_attribute("data-test") == "meme"
    assert "fd-etape-termine" in li.get_attribute("class")
    assert li.locator("path.fd-coche-trace").count() == 1
    assert page_ui.locator("#fd-barre").get_attribute("aria-valuenow") == "30"


def test_celebration_prete_pour_validation_sans_envoi(page_ui: Page, api: Api) -> None:
    api.etat = _etat({"pieces": "termine", "lecture": "en_cours"}, 15)
    _ouvrir(page_ui)
    assert page_ui.locator("#fd-pret").is_hidden()
    api.etat = _etat({c: "termine" for c in CODES}, 100)
    page_ui.click("#fd-btn-actualiser")
    page_ui.wait_for_selector("#fd-pret:not(.cache)")
    texte = page_ui.locator("#fd-pret").inner_text()
    assert "prêt pour votre validation" in texte and "Rien n'a été envoyé" in texte
    assert "envoyé au" not in texte.lower() and "validé" not in texte.lower().replace("validation", "")
    assert page_ui.locator("#fd-btn-lancer").get_attribute("data-etat") == "termine"
    assert page_ui.locator("#fd-barre.ok").count() == 1


def test_etat_vide_illustre_et_erreur_http_413(page_ui: Page, api: Api) -> None:
    page_ui.evaluate("candidatActifId = null; fdChoisirEtudiant(''); fdAfficherSelection()")
    assert page_ui.locator("#fd-vide svg.fd-illu").count() == 1
    assert page_ui.locator("#fd-vide svg.fd-illu").get_attribute("aria-hidden") == "true"
    assert "trop volumineux" in page_ui.evaluate("fdMessageHttp(413, null, 'x')")


def test_mouvement_reduit_aucune_animation_et_infos_completes(page_ui: Page, api: Api) -> None:
    page_ui.emulate_media(reduced_motion="reduce")
    api.etat = _etat({"pieces": "termine", "lecture": "en_cours", "revue_valeurs": "a_verifier"}, 40)
    _ouvrir(page_ui)
    page_ui.wait_for_selector(".fd-etape-a_verifier")
    assert page_ui.evaluate("fdReduit()") is True
    # compteur immédiat, aucune classe d'animation, coche complète, aucune animation CSS en cours
    assert page_ui.locator("#fd-progres-chiffre").inner_text() == "40 %"
    assert page_ui.locator(".fd-entree").count() == 0
    nb = page_ui.evaluate("document.querySelectorAll('#vue-flux-dossier .fd-etape').length && "
                          "document.getAnimations().filter(a => a.effect && a.effect.target && a.effect.target.closest && a.effect.target.closest('#vue-flux-dossier') && a.playState === 'running' && a.transitionProperty === undefined && a.animationName).length")
    assert nb == 0
    assert page_ui.locator(".fd-etape").count() == 9
    assert "À vérifier" in page_ui.locator(".fd-etape-a_verifier .badge").inner_text()
    assert page_ui.get_by_role("button", name="Confirmer les 6 valeurs lues").count() == 1


def test_depot_fichier_barre_et_etat_et_375px(page_ui: Page, api: Api) -> None:
    page_ui.set_viewport_size({"width": 375, "height": 812})
    api.etat = _etat({"pieces": "termine", "lecture": "a_verifier"}, 25, ["cv"])
    _ouvrir(page_ui)
    page_ui.set_input_files("#fd-fichiers", [{"name": "passeport.pdf", "mimeType": "application/pdf", "buffer": b"%PDF"}])
    assert page_ui.locator(".fd-fichier .fd-fichier-barre").count() == 1
    assert page_ui.locator(".fd-fichier .fd-fichier-barre").get_attribute("aria-valuenow") == "0"
    page_ui.click("#fd-btn-envoyer")
    page_ui.wait_for_selector(".fd-fichier .badge-ok")
    assert page_ui.locator(".fd-fichier .fd-fichier-barre").get_attribute("aria-valuenow") == "100"
    deborde = page_ui.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
    assert deborde is False


def test_libelles_francais_des_etapes_et_detail_masque(page_ui: Page, api: Api) -> None:
    _ouvrir(page_ui)
    res = page_ui.evaluate(
        "[fdLibelleEtape({code: 'revue_valeurs', libelle: 'Étape revue_valeurs'}),"
        " fdLibelleEtape({code: 'points_forts', libelle: ''}),"
        " fdLibelleEtape({code: 'lecture'}),"
        " fdLibelleEtape({code: 'x', libelle: 'Étape Vœux'}),"
        " fdDetailEtape({code: 'pieces', detail: 'Détail pieces'}),"
        " fdDetailEtape({code: 'pieces', detail: '  '}),"
        " fdDetailEtape({code: 'pieces', detail: '3 pièces reçues'})]")
    assert res == ["Revue des valeurs", "Points forts", "Lecture des pièces", "Vœux", "", "", "3 pièces reçues"]
    assert "Étape " not in "".join(page_ui.locator(".fd-etape .fd-titre").all_inner_texts())
