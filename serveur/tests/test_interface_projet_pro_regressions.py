"""Régressions de l'écran « Projet professionnel » : confirmation de remplacement, enregistrement
avant validation, gestion des erreurs de chargement. Tests statiques sur ecran.JS_PROJET / ecran.HTML_VUE."""

from __future__ import annotations

import re

from app.interface.design import ecran_projet as ecran
from app.interface.routeur_interface import HTML_INTERFACE_FR

_ID_CONFIRMATION = "pp-confirmation"
_ID_BTN_CONFIRMER = "pp-btn-confirmer-remplacement"
_ID_BTN_ANNULER = "pp-btn-annuler-remplacement"
_URL_VALIDER = '"/projet-professionnel/valider"'
_MESSAGE_ECHEC_CHARGEMENT = "Impossible de charger"


def _source_gestionnaire(identifiant: str) -> str:
    """Source du gestionnaire `getElementById(identifiant).addEventListener(...)` jusqu'à son `});` de fermeture."""
    debut = ecran.JS_PROJET.find(f'getElementById("{identifiant}").addEventListener')
    assert debut != -1, f"gestionnaire introuvable : {identifiant}"
    fin = re.search(r"\n\s{0,4}\}\);", ecran.JS_PROJET[debut:])
    assert fin is not None, f"fin de gestionnaire introuvable : {identifiant}"
    return ecran.JS_PROJET[debut: debut + fin.end()]


def _source_fonction_de_premier_niveau(entete: str) -> str:
    """Source d'une fonction top-level dont l'en-tête est donné, jusqu'à son `}` de fermeture (indentation 4)."""
    debut = ecran.JS_PROJET.find(entete)
    assert debut != -1, f"fonction introuvable : {entete}"
    fin = re.search(r"\n    \}\n", ecran.JS_PROJET[debut:])
    assert fin is not None, f"fin de fonction introuvable : {entete}"
    return ecran.JS_PROJET[debut: debut + fin.end()]


# --- H1 : confirmation de remplacement -------------------------------------------------------


def test_bloc_confirmation_de_remplacement_cache_par_defaut() -> None:
    balises = re.findall(rf'<[^>]*\bid="{_ID_CONFIRMATION}"[^>]*>', ecran.HTML_VUE)
    assert len(balises) == 1, "bloc pp-confirmation absent ou dupliqué"
    classe = re.search(r'class="([^"]*)"', balises[0])
    assert classe is not None, "le bloc pp-confirmation n'a pas de classe"
    assert "cache" in classe.group(1).split(), "le bloc pp-confirmation doit être caché par défaut"


def test_boutons_de_confirmation_de_remplacement_dans_le_bloc() -> None:
    html = ecran.HTML_VUE
    debut = html.find(f'id="{_ID_CONFIRMATION}"')
    assert debut != -1, "bloc pp-confirmation absent"
    fin = html.find("</section>", debut)
    assert fin != -1
    bloc = html[debut:fin]
    for identifiant in (_ID_BTN_CONFIRMER, _ID_BTN_ANNULER):
        assert f'id="{identifiant}"' in html, identifiant
        assert f'id="{identifiant}"' in bloc, f"{identifiant} hors du bloc pp-confirmation"


def test_aucune_boite_de_dialogue_native() -> None:
    js = ecran.JS_PROJET
    assert re.search(r"(?<![A-Za-z_])confirm\(", js) is None, "confirm( natif interdit"
    assert re.search(r"(?<![A-Za-z_])prompt\(", js) is None, "prompt( interdit"


def test_javascript_reference_les_trois_ids_de_confirmation() -> None:
    js = ecran.JS_PROJET
    for identifiant in (_ID_CONFIRMATION, _ID_BTN_CONFIRMER, _ID_BTN_ANNULER):
        assert f'getElementById("{identifiant}")' in js, identifiant


def test_generer_n_envoie_plus_remplacer_directement_et_utilise_remplacer_valide() -> None:
    js = ecran.JS_PROJET
    assert "remplacer: ppVersion !== null" not in js
    assert "remplacer_valide" in js


def test_ids_de_confirmation_presents_et_uniques_dans_la_page_complete() -> None:
    for identifiant in (_ID_CONFIRMATION, _ID_BTN_CONFIRMER, _ID_BTN_ANNULER):
        assert HTML_INTERFACE_FR.count(f'id="{identifiant}"') == 1, identifiant


# --- M1 : Valider enregistre d'abord ---------------------------------------------------------


def test_texte_charge_du_serveur_memorise_dans_ppTexteCharge() -> None:
    assert "ppTexteCharge" in ecran.JS_PROJET


def test_valider_envoie_un_put_avant_l_appel_de_validation() -> None:
    source = _source_gestionnaire("pp-btn-valider")
    position_put = source.find('method: "PUT"')
    position_valider = source.find(_URL_VALIDER)
    assert position_put != -1, "pas de PUT dans le gestionnaire de pp-btn-valider"
    assert position_valider != -1, "pas d'appel à /projet-professionnel/valider dans le gestionnaire"
    assert position_put < position_valider, "le PUT doit précéder la validation"


def test_valider_utilise_la_version_renvoyee_par_le_put() -> None:
    source = _source_gestionnaire("pp-btn-valider")
    assert ".version" in source


# --- M2 : erreurs de chargement --------------------------------------------------------------


def test_actualiser_gere_le_statut_404() -> None:
    assert "status === 404" in ecran.JS_PROJET


def test_actualiser_notifie_projet_et_points_forts_en_erreur() -> None:
    source = _source_fonction_de_premier_niveau("async function ppActualiser()")
    assert source.count("notifier(") >= 2, "ppActualiser doit notifier l'erreur projet et l'erreur points forts"


def test_message_impossible_de_charger_present_au_moins_deux_fois() -> None:
    assert ecran.JS_PROJET.count(_MESSAGE_ECHEC_CHARGEMENT) >= 2


# --- Invariants existants ---------------------------------------------------------------------


def test_invariants_sans_insertion_html_et_sans_antislash() -> None:
    js = ecran.JS_PROJET
    assert "innerHTML" not in js
    assert "outerHTML" not in js
    assert "insertAdjacentHTML" not in js
    assert "\\" not in js and "\\" not in ecran.HTML_VUE
