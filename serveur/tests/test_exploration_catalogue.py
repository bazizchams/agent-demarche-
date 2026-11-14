"""Exploration du catalogue Études en France : GET seulement, domaines officiels (R6), sortie au format du
catalogue. Testée sur une PAGE DE DÉMO LOCALE (Chromium headless, requêtes interceptées : aucun accès réseau,
jamais le vrai portail) et sur des pages factices pour les refus."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from playwright.sync_api import Page, Route, sync_playwright

from app.agent_local.domaines_officiels import PolitiqueNavigation, politique_depuis_parametres
from app.agent_local.portails.exploration_catalogue import (
    explorer_catalogue,
    fiches_depuis_json_portail,
)
from app.core.config import Parametres
from app.services.fiche_formation import FicheEntree, exigences_inconnues

RELEVE = date(2026, 11, 13)
BASE = "http://portail.local/demo/exploration"
URL_LISTE = f"{BASE}/catalogue-formations"
PIRATE = "https://etudesenfrance.diplomatie.gouv.fr.pirate.example/catalogue-formations/formation/9/site/9"

HTML_LISTE = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><title>Démo exploration</title></head>
<body><h1>Catalogue (page de démonstration locale)</h1>
<form id="recherche"><label for="q">Libellé de la formation</label><input id="q" type="text">
<button type="submit">Rechercher</button></form>
<button id="piege" type="button">Ajouter au panier</button>
<ul>
<li><a href="{BASE}/catalogue-formations/formation/1/site/10"><h3>Master Sciences du langage</h3></a><p>Université Fictive A</p></li>
<li><a href="{BASE}/catalogue-formations/formation/2/site/20"><h3>Licence Informatique</h3></a><p>Université Fictive B</p></li>
<li><a href="{BASE}/catalogue-formations/formation/3/site/30"><h3>Sans établissement</h3></a></li>
<li><a href="{BASE}/catalogue-formations/formation/4/site/40"><h3>Fiche en erreur</h3></a></li>
<li><a href="{BASE}/catalogue-formations/formation/1/site/10">Doublon du premier lien</a></li>
<li><a href="{PIRATE}"><h3>Lien imitateur</h3></a></li>
</ul>
<script>
window.__journal = [];
document.addEventListener("click", e => window.__journal.push("clic"), true);
document.addEventListener("submit", e => {{ window.__journal.push("soumission"); e.preventDefault(); }}, true);
document.addEventListener("input", e => window.__journal.push("saisie"), true);
</script></body></html>"""

FICHES_API: dict[str, dict[str, Any]] = {
    "1": {
        "formationInformationGenerale": {
            "libelleFormation": "Master Sciences du langage",
            "libelleEtablissement": "Université Fictive A",
            "preRequis": {"value": "<p>Niveau de langue fran&ccedil;aise exig&eacute; : C1 (TCF, DELF, DALF).</p>"},
        },
        "formationsInformationsEntree": [
            {"valeurComNiveau": "Bac +4", "dateFin": "2026-12-22", "ferme": False,
             "procedureInscription": {"value": "Procédure fictive."}},
            {"valeurComNiveau": "Bac +5", "dateFin": "2026-10-01", "ferme": True,
             "procedureInscription": {"value": "Procédure fictive."}},
        ],
    },
    "2": {
        "formationInformationGenerale": {
            "libelleFormation": "Licence Informatique",
            "libelleEtablissement": "Université Fictive B",
            "preRequis": {"value": "Niveau B2 exigé en français"},
        },
        "formationsInformationsEntree": [{"valeurComNiveau": "Bac +3", "dateFin": "2027-01-15", "ferme": False}],
    },
    "3": {"formationInformationGenerale": {"libelleFormation": "Sans établissement"}},
}


class Demo:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.requetes: list[tuple[str, str]] = []
        page.route("**/*", self._servir)

    def _servir(self, route: Route) -> None:
        req = route.request
        self.requetes.append((req.method, req.url))
        if req.url.startswith(URL_LISTE):
            route.fulfill(status=200, content_type="text/html; charset=utf-8", body=HTML_LISTE)
        elif "/parcours-api/espace-etudiant/catalogue/formations/" in req.url:
            id_formation = req.url.split("/formations/")[1].split("/")[0]
            if id_formation in FICHES_API:
                route.fulfill(status=200, content_type="application/json", body=json.dumps(FICHES_API[id_formation]))
            else:
                route.fulfill(status=404, content_type="application/json", body="{}")
        else:
            route.abort()  # tout le reste (dont le domaine imitateur) est coupé

    def journal(self) -> list[str]:
        return self.page.evaluate("window.__journal")


@pytest.fixture()
def demo() -> Iterator[Demo]:
    with sync_playwright() as pw:
        navigateur = pw.chromium.launch(headless=True)
        try:
            page = navigateur.new_page()
            d = Demo(page)
            page.goto(URL_LISTE)
            yield d
        finally:
            navigateur.close()


@pytest.fixture()
def politique(parametres_test: Parametres) -> PolitiqueNavigation:
    return politique_depuis_parametres(parametres_test)  # YAML réels + démo locale (hors production)


def test_exploration_page_de_demo_produit_des_fiches_au_format_du_catalogue(
    demo: Demo, politique: PolitiqueNavigation
) -> None:
    res = explorer_catalogue(demo.page, politique, date_releve=RELEVE)
    assert res.refus is None and res.nb_liens_trouves == 6
    cles = [(f.etablissement, f.intitule, f.niveau_entree_bac_plus) for f in res.fiches]
    assert cles == [
        ("Université Fictive A", "Master Sciences du langage", 4),
        ("Université Fictive A", "Master Sciences du langage", 5),
        ("Université Fictive B", "Licence Informatique", 3),
    ]
    quatre, cinq, trois = res.fiches
    assert quatre.francais_min == "C1" and quatre.date_limite == date(2026, 12, 22) and quatre.ferme is False
    assert cinq.ferme is True and cinq.niveau_entree_libelle == "Bac +5"
    assert trois.francais_min == "B2"
    assert all(f.date_releve == RELEVE and f.source == "exploration" for f in res.fiches)
    assert all(f.url_officielle is None for f in res.fiches)  # page de démo http : jamais une URL officielle
    # Règle 4 : moyenne, pièces et domaine ne sont pas lus => restent inconnus
    assert all("moyenne" in exigences_inconnues(f) for f in res.fiches)
    assert all(f.moyenne_min is None and f.pieces == [] and f.domaines == [] for f in res.fiches)
    # fiches ignorées avec raison : sans établissement, en erreur HTTP, lien imitateur (R6)
    raisons = {i["fiche"]: i["raison"] for i in res.ignorees}
    assert "établissement absent" in raisons["3"] and "404" in raisons["4"] and "Règle 6" in raisons["9"]


def test_exploration_n_emet_que_des_get_et_ne_clique_ni_ne_saisit_ni_ne_soumet(
    demo: Demo, politique: PolitiqueNavigation
) -> None:
    avant = len(demo.requetes)
    explorer_catalogue(demo.page, politique, date_releve=RELEVE)
    nouvelles = demo.requetes[avant:]
    assert nouvelles and all(methode == "GET" for methode, _ in nouvelles)
    assert all("/parcours-api/espace-etudiant/catalogue/formations/" in url for _, url in nouvelles)
    assert not any("pirate.example" in url for _, url in demo.requetes)  # jamais chargé
    assert demo.journal() == []  # aucun clic, aucune saisie, aucune soumission
    assert demo.page.url == URL_LISTE  # la page n'a pas bougé


def test_exploration_avec_adresse_de_liste_fait_un_get_officiel(demo: Demo, politique: PolitiqueNavigation) -> None:
    demo.page.goto("about:blank")
    res = explorer_catalogue(demo.page, politique, url_liste=URL_LISTE, date_releve=RELEVE)
    assert res.refus is None and len(res.fiches) == 3
    assert all(methode == "GET" for methode, _ in demo.requetes)


def test_limite_du_nombre_de_fiches_lues(demo: Demo, politique: PolitiqueNavigation) -> None:
    res = explorer_catalogue(demo.page, politique, max_fiches=1, date_releve=RELEVE)
    assert len(res.fiches) == 2 and any("au-delà de la limite" in i["raison"] for i in res.ignorees)


def test_sortie_json_valide_le_format_du_catalogue(demo: Demo, politique: PolitiqueNavigation) -> None:
    res = explorer_catalogue(demo.page, politique, date_releve=RELEVE)
    for brut in res.fiches_json():
        assert FicheEntree.model_validate(brut).source == "exploration"
    json.dumps(res.fiches_json())  # sérialisable tel quel pour POST /catalogue-formations/fiches


# ----------------------------------------------------------------------------- refus R6 (pages factices)


class FausseLocalisation:
    def __init__(self, journal: list[str], hrefs: list[str]) -> None:
        self._journal, self._hrefs = journal, hrefs

    def evaluate_all(self, *_: Any) -> list[str]:
        self._journal.append("lecture_liens")
        return self._hrefs


class FausseePage:
    """Page factice qui journalise tout appel : permet de prouver qu'un refus ne touche à rien."""

    def __init__(self, url: str, hrefs: list[str] | None = None, apres_goto: str | None = None) -> None:
        self.url = url
        self.journal: list[str] = []
        self._hrefs = hrefs or []
        self._apres_goto = apres_goto

    def goto(self, url: str) -> None:
        self.journal.append(f"goto {url}")
        if self._apres_goto:
            self.url = self._apres_goto

    def locator(self, _selecteur: str) -> FausseLocalisation:
        return FausseLocalisation(self.journal, self._hrefs)

    def evaluate(self, _js: str, url: str) -> dict[str, Any]:
        self.journal.append(f"get {url}")
        return FICHES_API["2"]


def test_page_hors_domaine_officiel_refusee_sans_rien_lire(politique: PolitiqueNavigation) -> None:
    page = FausseePage("https://pirate.example/catalogue-formations")
    res = explorer_catalogue(page, politique, date_releve=RELEVE)
    assert res.fiches == [] and res.refus and "Règle 6" in res.refus
    assert page.journal == []


def test_domaine_imitateur_et_http_refuses(politique: PolitiqueNavigation) -> None:
    for url in (PIRATE, "http://etudesenfrance.diplomatie.gouv.fr/catalogue-formations"):
        page = FausseePage("about:blank")
        res = explorer_catalogue(page, politique, url_liste=url, date_releve=RELEVE)
        assert res.refus and page.journal == []  # pas même de goto


def test_redirection_hors_domaine_officiel_arrete_la_lecture(politique: PolitiqueNavigation) -> None:
    page = FausseePage("about:blank", apres_goto="https://pirate.example/redirige")
    officielle = "https://etudesenfrance.diplomatie.gouv.fr/catalogue-formations"
    res = explorer_catalogue(page, politique, url_liste=officielle, date_releve=RELEVE)
    assert res.refus and page.journal == [f"goto {officielle}"]


def test_domaine_officiel_des_yaml_est_lu_sans_reseau(politique: PolitiqueNavigation) -> None:
    lien = "https://etudesenfrance.diplomatie.gouv.fr/catalogue-formations/formation/2/site/20"
    page = FausseePage("https://etudesenfrance.diplomatie.gouv.fr/catalogue-formations", [lien])
    res = explorer_catalogue(page, politique, date_releve=RELEVE)
    assert res.refus is None and len(res.fiches) == 1
    assert res.fiches[0].url_officielle == lien
    assert page.journal == [
        "lecture_liens",
        "get https://etudesenfrance.diplomatie.gouv.fr/parcours-api/espace-etudiant/catalogue/formations/2/site/20",
    ]


def test_production_n_accepte_pas_la_page_de_demo(parametres_test: Parametres) -> None:
    prod = PolitiqueNavigation(domaines_https=politique_depuis_parametres(parametres_test).domaines_https,
                               autoriser_demo=False)
    page = FausseePage(URL_LISTE)
    assert explorer_catalogue(page, prod, date_releve=RELEVE).refus and page.journal == []


def test_conversion_json_portail_exige_intitule_et_etablissement() -> None:
    with pytest.raises(ValueError):
        fiches_depuis_json_portail(FICHES_API["3"], url_fiche="https://x.invalid/f", date_releve=RELEVE)
    with pytest.raises(ValueError):
        fiches_depuis_json_portail({}, url_fiche="https://x.invalid/f", date_releve=RELEVE)
