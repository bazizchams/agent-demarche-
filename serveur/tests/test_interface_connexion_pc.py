"""Boutons « Se connecter au portail », « Créer le compte Études en France », consentement et enregistrement au coffre.

Meme banc que `test_interface_ouverture_pc.py` : vrai Chromium, API simulee. Regle 3 : aucun champ de mot de passe.
"""

from __future__ import annotations

from typing import Any

from playwright.sync_api import Page

from app.interface.design.js_ouverture_pc import JS_OUVERTURE_PC
from app.interface.design.vues_ouverture_pc import HTML_OUVERTURE_PC
from tests.test_interface_ouverture_pc import _cache, _texte, page_ui  # noqa: F401 (fixture)

CONNEXION = {"id": "c1", "action": "connexion_portail", "statut": "en_cours", "message_alerte": None}


def _charger(page: Page, taches: list[dict[str, Any]]) -> None:
    page.evaluate(
        """(t) => { reponsesApi.taches = t; reponsesApi.agents = [{id: 'a', actif: true, en_ligne: true}];
                    reponsesApi.tache = t[0] || null; reponsesApi.depot = { present: false }; }""",
        taches,
    )
    page.evaluate("ouvSurChangementCandidat({ id: 'cand-1' })")
    page.wait_for_function("!document.getElementById('btn-se-connecter-portail').disabled")


def _appels(page: Page) -> list[dict[str, Any]]:
    return page.evaluate("appelsApi")


def test_pas_de_champ_de_mot_de_passe_dans_l_interface() -> None:
    assert 'type="password"' not in HTML_OUVERTURE_PC and "type=password" not in HTML_OUVERTURE_PC
    assert "innerHTML" not in JS_OUVERTURE_PC and chr(92) not in JS_OUVERTURE_PC


def test_les_deux_boutons_creent_la_bonne_tache(page_ui: Page) -> None:
    _charger(page_ui, [])
    page_ui.evaluate("reponsesApi.creation = { statut: 201, corps: { id: 't9', action: 'connexion_portail', statut: 'en_attente' } }")
    page_ui.select_option("#select-portail-connexion", "ircc")
    page_ui.click("#btn-se-connecter-portail")
    page_ui.wait_for_function("document.getElementById('connexion-pc-etat').textContent.includes('en attente')")
    envoi = [a for a in _appels(page_ui) if a["methode"] == "POST"][-1]["corps"]
    assert envoi == {"candidat_id": "cand-1", "code_demarche": "ircc_permis_etudes", "action": "connexion_portail",
                     "portail": "ircc"}
    page_ui.evaluate("reponsesApi.creation = { statut: 201, corps: { id: 't10', action: 'creation_compte_eef', statut: 'en_attente' } }")
    page_ui.click("#btn-creer-compte-eef")
    page_ui.wait_for_function("appelsApi.filter((a) => a.methode === 'POST').length === 2")
    envoi = [a for a in _appels(page_ui) if a["methode"] == "POST"][-1]["corps"]
    assert envoi == {"candidat_id": "cand-1", "code_demarche": "compte_etudes_en_france",
                     "action": "creation_compte_eef"}


def test_le_bouton_autoriser_n_apparait_que_pour_une_connexion_detenue_par_l_agent(page_ui: Page) -> None:
    _charger(page_ui, [{**CONNEXION, "statut": "en_attente"}])
    assert _cache(page_ui, "btn-autoriser-agent") is True
    _charger(page_ui, [CONNEXION])
    assert _cache(page_ui, "btn-autoriser-agent") is False
    assert "Autoriser l'agent à se connecter" in _texte(page_ui, "btn-autoriser-agent")
    _charger(page_ui, [{**CONNEXION, "action": "creation_compte_eef"}])
    assert _cache(page_ui, "btn-autoriser-agent") is True


def test_proposition_d_enregistrement_dans_l_interface_avec_consentement(page_ui: Page) -> None:
    page_ui.evaluate(
        """() => { const base = appelApi;
           appelApi = async (url, options) => {
             if (url.endsWith('/depot-identifiants')) { appelsApi.push({ url, methode: (options && options.method) || 'GET' });
               return reponse(200, { present: true, portail: 'ircc', expire_le: null }); }
             if (url.endsWith('/enregistrer')) { appelsApi.push({ url, methode: 'POST', corps: JSON.parse(options.body) });
               return JSON.parse(options.body).consentement ? reponse(200, { portail: 'ircc', existe: true })
                                                             : reponse(422, { detail: 'consentement requis' }); }
             return base(url, options); }; }"""
    )
    _charger(page_ui, [{**CONNEXION, "statut": "a_valider"}])
    page_ui.wait_for_function("!document.getElementById('depot-identifiants-bloc').classList.contains('cache')")
    page_ui.click("#btn-depot-enregistrer")  # sans consentement coché : le serveur est seul juge, la case est transmise
    page_ui.check("#depot-consentement")
    page_ui.click("#btn-depot-enregistrer")
    page_ui.wait_for_function("document.getElementById('depot-identifiants-bloc').classList.contains('cache')")
    envois = [a["corps"] for a in _appels(page_ui) if a["url"].endswith("/enregistrer")]
    assert envois[0] == {"consentement": False} and envois[-1] == {"consentement": True}
    assert not page_ui.evaluate("document.querySelector('#carte-ouverture-pc input[type=password]') !== null")
