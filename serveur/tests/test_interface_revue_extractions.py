"""Écran de revue des valeurs lues : tests statiques sur le HTML servi (guide de design)."""

from __future__ import annotations

import re

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.interface import ecran_revue_extractions as ecran
from app.interface.routeur_interface import HTML_INTERFACE_FR


def test_page_servie_avec_l_ecran_de_revue(application: FastAPI) -> None:
    rep = TestClient(application).get("/")
    assert rep.status_code == 200
    for fragment in (
        'data-vue="vue-revue-extractions"',
        'id="vue-revue-extractions"',
        "Lecture des documents",
        "Rien n'est écrit sur la fiche sans votre confirmation",
        'id="rx-btn-lire"',
        'id="rx-btn-appliquer"',
    ):
        assert fragment in rep.text, fragment


def test_identifiants_uniques_et_cibles_presentes() -> None:
    ids = re.findall(r"""\bid="([^"]+)\"""", HTML_INTERFACE_FR)
    assert len(ids) == len(set(ids)), "identifiants HTML dupliqués"
    for cible in re.findall(r"""getElementById\("(rx-[^"]+)"\)""", ecran.JS_REVUE):
        assert cible in ids, cible


def test_javascript_sans_insertion_de_html_ni_stockage_ni_console() -> None:
    js = ecran.JS_REVUE
    for interdit in (
        "innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "console.",
        "localStorage", "sessionStorage", "indexedDB", "document.cookie", "alert(",
    ):
        assert interdit not in js, interdit
    assert "textContent" in js and "createElement" in js
    assert "\\" not in js and "\\" not in ecran.HTML_VUE  # aucun antislash : page servie depuis une chaîne Python


def test_couleurs_uniquement_par_tokens_du_design() -> None:
    style = ecran.STYLE_REVUE
    assert re.findall(r"#[0-9a-fA-F]{3,8}", style) == []  # aucune couleur hexadécimale littérale
    assert "rgb(" not in style and "hsl(" not in style
    assert "var(--" in style


def test_boutons_de_revue_presents_et_ecriture_reservee_aux_humains() -> None:
    js = ecran.JS_REVUE
    for libelle in ("Confirmer", "Corriger", "Rejeter"):
        assert f'"{libelle}"' in js
    assert 'roleActif === "administrateur" || roleActif === "employe"' in js
