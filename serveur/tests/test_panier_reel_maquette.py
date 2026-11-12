"""Tests (Playwright Chromium headless) du panier de vœux adapté au VRAI portail Études en France, contre une
MAQUETTE FIDÈLE (`/demo/eef-reel/...`, voir `app/demo/maquette_eef_reel.py`) qui reproduit la structure observée
le 2026-11-11 : identifiants générés (aucun CSS utilisable), catalogue + résultats, fiche à deux blocs de niveau,
panier avec articles, bouton de dépliage sans nom, éditeur riche dans un IFRAME, compteur, pièges (Supprimer,
certifications, Soumettre) et affichage mobile < 900 px.

Aucun serveur n'est lancé : le pilote sert la maquette via `page.route("http://portail.local/demo/**")`.
Toutes les données sont fictives ; aucun accès à `serveur/donnees/`.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Page

from app.agent_local.pilote_navigateur import GestionnairePiloteNavigateur, ResultatActionNavigateur
from app.agent_local.portails.panier_voeux import (
    MODE_ROLES,
    PROFIL_PANIER_REEL,
    _choisir_section,
    _nom_interdit,
    profil_maquette_eef,
)

CLES_RESULTAT_VOEU = {"voeu_id", "intitule", "etablissement", "statut", "motivation_enregistree", "nb_caracteres"}
STATUTS_VALIDES = {
    "ajoute",
    "deja_present",
    "introuvable",
    "ambigu",
    "ferme",
    "refuse_limite",
    "motivation_invalide",
    "erreur",
}

NANTERRE = ("Master Sciences du langage", "Université Paris Nanterre")
LORRAINE = ("Master Traitement automatique des langues", "Université de Lorraine")
LILLE_FERME = ("Master Linguistique appliquée", "Université de Lille")
RENNES = ("Licence Informatique", "Université de Rennes")


class Navigation:
    """Fixture : un pilote Playwright isolé (profil dans tmp_path) + helpers thread-safe."""

    def __init__(self, tmp_path: Path) -> None:
        self.g = GestionnairePiloteNavigateur()
        self.dossier_profil = tmp_path / "stockage" / "profil_navigateur_agent"

    def action(
        self,
        action: str,
        *,
        voeux: list[dict[str, Any]] | None = None,
        cible: str = "demo_eef_reel",
        profil: Any = "maquette",
        portail_homologue: bool = False,
    ) -> ResultatActionNavigateur:
        return self.g.executer_action(
            code_demarche="campus_france",
            cible=cible,
            action=action,
            instruction_libre=None,
            candidat={},
            documents_dechiffres=[],
            dossier_profil=self.dossier_profil,
            headless=True,
            prendre_capture=True,
            voeux=voeux,
            portail_homologue=portail_homologue,
            profil_panier=profil_maquette_eef() if profil == "maquette" else profil,
        )

    def ouvrir(self) -> None:
        res = self.action("ouvrir_portail")
        assert "/demo/eef-reel" in res.url_courante

    def dans_page(self, fn: Callable[[Page], Any]) -> Any:
        assert self.g._page is not None
        return self.g._executor.submit(lambda: fn(self.g._page)).result(timeout=30)

    def semer_panier(self, items: list[dict[str, Any]]) -> None:
        self.dans_page(
            lambda p: p.evaluate("(x) => localStorage.setItem('eef-panier', JSON.stringify(x))", items)
        )

    def panier(self) -> list[dict[str, Any]]:
        return self.dans_page(lambda p: p.evaluate("JSON.parse(localStorage.getItem('eef-panier') || '[]')"))

    def journal(self) -> list[dict[str, Any]]:
        return self.dans_page(lambda p: p.evaluate("JSON.parse(localStorage.getItem('eef-journal') || '[]')"))

    def types_journal(self, type_: str) -> list[Any]:
        return [e["detail"] for e in self.journal() if e["type"] == type_]


@pytest.fixture()
def nav(tmp_path: Path) -> Iterator[Navigation]:
    n = Navigation(tmp_path)
    try:
        yield n
    finally:
        n.g.fermer()


def _lettre(voeu_id: str, paragraphes: int = 2) -> str:
    return "\n\n".join(
        f"MOTIVATION-UNIQUE-{voeu_id} paragraphe {k} : mon projet d'études est cohérent avec mon parcours."
        for k in range(1, paragraphes + 1)
    )


def _voeu(
    voeu_id: str,
    intitule: str,
    etablissement: str,
    *,
    niveau: str | None = None,
    motivation: str | None = None,
) -> dict[str, Any]:
    return {
        "voeu_id": voeu_id,
        "intitule": intitule,
        "etablissement": etablissement,
        "niveau": niveau,
        "motivation": _lettre(voeu_id) if motivation is None else motivation,
    }


def _article_seme(
    entree: str, id_f: str, id_s: str, intitule: str, etab: str, niveau: str, *, enregistree: bool = False
) -> dict[str, Any]:
    return {
        "entreeId": entree,
        "idFormation": id_f,
        "idSite": id_s,
        "intitule": intitule,
        "etablissement": etab,
        "site": "Site de test",
        "niveau": niveau,
        "motivation": "Texte déjà enregistré." if enregistree else "",
        "enregistree": enregistree,
    }


def _verifier_resultat_conforme(res: ResultatActionNavigateur, nb_attendu: int) -> None:
    assert len(res.resultats_voeux) == nb_attendu
    for r in res.resultats_voeux:
        assert set(r.keys()) == CLES_RESULTAT_VOEU
        assert r["statut"] in STATUTS_VALIDES
    assert res.arret_regle1_avant_soumission is True
    textes = [res.resume_francais, res.reponse_agent, *res.etapes_realisees, *res.avertissements_securite]
    assert all("MOTIVATION-UNIQUE" not in t for t in textes)  # R5


def _aucun_piege(nav: Navigation) -> None:
    """La maquette détecte tout clic sur Supprimer / certification / Soumettre, et tout appel non GET."""
    assert nav.types_journal("clic_interdit") == []
    assert nav.types_journal("appel_non_get") == []


# ---------------------------------------------------------------------------
# Profil
# ---------------------------------------------------------------------------


def test_profil_reel_sans_selecteur_css() -> None:
    assert PROFIL_PANIER_REEL.mode == MODE_ROLES
    assert PROFIL_PANIER_REEL.teste is False  # jamais homologué (Règle 6)
    assert PROFIL_PANIER_REEL.origine == "https://etudesenfrance.diplomatie.gouv.fr"
    for champ in (
        "recherche",
        "resultats_items",
        "bouton_ajouter_dans_item",
        "panier_items",
        "motivation_dans_item",
        "bouton_enregistrer_dans_item",
    ):
        assert getattr(PROFIL_PANIER_REEL, champ) == ""  # aucun id ni classe CSS
    assert PROFIL_PANIER_REEL.largeur_page == 1280
    maq = profil_maquette_eef()
    assert maq.origine is None and maq.prefixe_chemin == "/demo/eef-reel" and maq.mode == MODE_ROLES


def test_interdits_et_choix_de_section() -> None:
    assert _nom_interdit("Supprimer")
    assert _nom_interdit("Soumettre mon dossier de candidature")
    assert _nom_interdit("J'ai bien relu mon dossier et je certifie l'exactitude des informations")
    assert not _nom_interdit("Ajouter au panier")
    assert not _nom_interdit("Enregistrer")

    deux = [{"niveau": "Bac +4"}, {"niveau": "Bac +5"}]
    assert _choisir_section(deux, {"niveau": "bac+5"})[1] == deux[1]
    assert _choisir_section(deux, {"niveau": None})[0] == "ambigu"
    assert _choisir_section(deux, {"niveau": "Bac +7"})[0] == "ambigu"
    assert _choisir_section(deux[:1], {"niveau": None})[1] == deux[0]
    assert _choisir_section([], {"niveau": "Bac +4"})[0] == "aucune"
    assert _choisir_section([{"niveau": "Bac +4"}, {"niveau": "Bac +4"}], {"niveau": "Bac +4"})[0] == "ambigu"


# ---------------------------------------------------------------------------
# Action sur la maquette
# ---------------------------------------------------------------------------


def test_ajout_de_deux_voeux_dans_le_bon_bloc_de_niveau(nav: Navigation) -> None:
    nav.ouvrir()
    voeux = [
        # « Master Sciences du langage » existe aussi à Strasbourg : l'établissement exact départage
        _voeu("v1", *NANTERRE, niveau="Bac +5"),
        _voeu("v2", *LORRAINE, niveau="Bac +4"),
    ]
    res = nav.action("ajouter_voeux_panier", voeux=voeux)

    assert res.succes is True and res.blocage_captcha_ou_2fa is False
    _verifier_resultat_conforme(res, 2)
    for r, v in zip(res.resultats_voeux, voeux):
        assert r["voeu_id"] == v["voeu_id"]
        assert r["statut"] == "ajoute"
        assert r["motivation_enregistree"] is True
        assert r["nb_caracteres"] == len(v["motivation"])

    # Bons blocs : 1001-b (Bac +5) et 1002-a (Bac +4), jamais l'autre bloc de la même fiche
    panier = nav.panier()
    assert [p["entreeId"] for p in panier] == ["1001-b", "1002-a"]
    assert all(p["enregistree"] for p in panier)
    assert nav.types_journal("ajout") == ["1001-b", "1002-a"]
    # Les sauts de ligne de la lettre sont devenus des paragraphes (lignes vides écartées)
    attendu = [[l for l in v["motivation"].split("\n") if l.strip()] for v in voeux]
    assert [p["motivation"].split("\n") for p in panier] == attendu
    enreg = nav.types_journal("enregistrement")
    assert [e["entreeId"] for e in enreg] == ["1001-b", "1002-a"]
    assert [e["longueur"] for e in enreg] == [sum(len(l) for l in a) for a in attendu]
    assert [e["paragraphes"] for e in enreg] == [2, 2]
    _aucun_piege(nav)
    # Arrêt avant la soumission : le Co-Pilote ne quitte pas le catalogue, la fiche et le panier
    assert "/mon-dossier-candidature/panier-formations" in nav.dans_page(lambda p: p.url)
    assert nav.types_journal("recherche") != []


def test_niveau_absent_avec_deux_blocs_est_ambigu_et_rien_n_est_ajoute(nav: Navigation) -> None:
    nav.ouvrir()
    res = nav.action(
        "ajouter_voeux_panier",
        voeux=[
            _voeu("sans_niveau", *NANTERRE),
            _voeu("niveau_inconnu", *LORRAINE, niveau="Bac +7"),
        ],
    )
    _verifier_resultat_conforme(res, 2)
    assert [r["statut"] for r in res.resultats_voeux] == ["ambigu", "ambigu"]
    assert all(r["motivation_enregistree"] is False for r in res.resultats_voeux)
    assert nav.panier() == []
    assert nav.types_journal("ajout") == []
    _aucun_piege(nav)


def test_une_seule_section_sans_niveau_est_acceptee_et_introuvable_si_etablissement_different(nav: Navigation) -> None:
    nav.ouvrir()
    res = nav.action(
        "ajouter_voeux_panier",
        voeux=[
            _voeu("v1", *RENNES),
            _voeu("v2", "Master Sciences du langage", "Université de Lyon"),  # intitulé existant, autre établissement
        ],
    )
    _verifier_resultat_conforme(res, 2)
    assert [r["statut"] for r in res.resultats_voeux] == ["ajoute", "introuvable"]
    assert [p["entreeId"] for p in nav.panier()] == ["1004-a"]


def test_formation_deja_au_panier(nav: Navigation) -> None:
    nav.ouvrir()
    nav.semer_panier([_article_seme("1001-b", "1001", "5001", *NANTERRE, "Bac +5")])
    res = nav.action("ajouter_voeux_panier", voeux=[_voeu("v1", *NANTERRE, niveau="Bac +5")])
    _verifier_resultat_conforme(res, 1)
    assert res.resultats_voeux[0]["statut"] == "deja_present"
    assert res.resultats_voeux[0]["motivation_enregistree"] is False
    panier = nav.panier()
    assert len(panier) == 1 and panier[0]["enregistree"] is False  # motivation d'un article existant non touchée
    assert nav.types_journal("ajout") == [] and nav.types_journal("enregistrement") == []
    _aucun_piege(nav)


def test_niveau_ferme(nav: Navigation) -> None:
    nav.ouvrir()
    res = nav.action("ajouter_voeux_panier", voeux=[_voeu("v1", *LILLE_FERME, niveau="Bac +5")])
    _verifier_resultat_conforme(res, 1)
    assert res.resultats_voeux[0]["statut"] == "ferme"
    assert nav.panier() == []
    assert any("fermées" in a for a in res.avertissements_securite)
    _aucun_piege(nav)


def test_limite_de_sept_formations_au_panier(nav: Navigation) -> None:
    nav.ouvrir()
    nav.semer_panier(
        [_article_seme(f"x{i}", "9", "9", f"Formation fictive {i}", "Établissement fictif", "Bac +3") for i in range(7)]
    )
    res = nav.action("ajouter_voeux_panier", voeux=[_voeu("v1", *RENNES)])
    _verifier_resultat_conforme(res, 1)
    assert res.resultats_voeux[0]["statut"] == "refuse_limite"
    assert len(nav.panier()) == 7
    assert nav.types_journal("ajout") == []


def test_motivation_vide_trop_longue_refusee_et_4000_acceptee_avec_compteur(nav: Navigation) -> None:
    nav.ouvrir()
    res = nav.action(
        "ajouter_voeux_panier",
        voeux=[
            _voeu("vide", *NANTERRE, niveau="Bac +4", motivation="   "),
            _voeu("trop_longue", *LORRAINE, niveau="Bac +4", motivation="x" * 4001),
            _voeu("limite", *RENNES, motivation="y" * 4000),
        ],
    )
    _verifier_resultat_conforme(res, 3)
    assert [r["statut"] for r in res.resultats_voeux] == ["motivation_invalide", "motivation_invalide", "ajoute"]
    assert [r["motivation_enregistree"] for r in res.resultats_voeux] == [False, False, True]
    assert res.resultats_voeux[2]["nb_caracteres"] == 4000
    assert [p["entreeId"] for p in nav.panier()] == ["1004-a"]
    # Le compteur de l'éditeur affichait bien 4000 avant l'enregistrement
    assert [e["longueur"] for e in nav.types_journal("enregistrement")] == [4000]


def test_compteur_incoherent_la_motivation_n_est_pas_enregistree(nav: Navigation) -> None:
    nav.ouvrir()
    nav.dans_page(lambda p: p.evaluate("localStorage.setItem('eef-sabotage-compteur', 'true')"))
    res = nav.action("ajouter_voeux_panier", voeux=[_voeu("v1", *RENNES)])
    _verifier_resultat_conforme(res, 1)
    # La formation est bien au panier, mais la motivation n'est PAS enregistrée (compteur contrôlé avant « Enregistrer »)
    assert res.resultats_voeux[0]["statut"] == "ajoute"
    assert res.resultats_voeux[0]["motivation_enregistree"] is False
    assert nav.types_journal("enregistrement") == []
    assert any("compteur" in a for a in res.avertissements_securite)


def test_aucun_clic_sur_supprimer_soumettre_certification_et_seul_l_article_du_voeu_est_enregistre(nav: Navigation) -> None:
    nav.ouvrir()
    autre = _article_seme("1002-b", "1002", "5002", *LORRAINE, "Bac +5")
    nav.semer_panier([autre])
    res = nav.action("ajouter_voeux_panier", voeux=[_voeu("v1", *NANTERRE, niveau="Bac +4")])
    assert res.resultats_voeux[0]["statut"] == "ajoute"
    assert res.resultats_voeux[0]["motivation_enregistree"] is True
    panier = nav.panier()
    assert [p["entreeId"] for p in panier] == ["1002-b", "1001-a"]
    assert [p["enregistree"] for p in panier] == [False, True]  # « Enregistrer » de CET article seulement
    assert panier[0]["motivation"] == ""
    _aucun_piege(nav)
    # Garde Règle 1 : même si le profil visait « Supprimer » comme bouton d'enregistrement, aucun clic
    profil_piege = dataclasses.replace(profil_maquette_eef(), libelle_bouton_enregistrer="Supprimer")
    res2 = nav.action("ajouter_voeux_panier", voeux=[_voeu("v2", *LORRAINE, niveau="Bac +4")], profil=profil_piege)
    assert res2.resultats_voeux[0]["statut"] == "ajoute"
    assert res2.resultats_voeux[0]["motivation_enregistree"] is False
    _aucun_piege(nav)
    assert len(nav.panier()) == 3
    # La maquette détecte bien un clic sur un piège (preuve que la détection fonctionne)
    nav.dans_page(lambda p: p.goto("http://portail.local/demo/eef-reel/mon-dossier-candidature"))
    nav.dans_page(lambda p: p.get_by_role("button", name="Soumettre mon dossier de candidature").click())
    assert nav.types_journal("clic_interdit") == ["soumettre"]


def test_affichage_mobile_la_largeur_est_fixee_a_1280(nav: Navigation) -> None:
    nav.ouvrir()
    nav.dans_page(lambda p: p.set_viewport_size({"width": 600, "height": 800}))
    # En mobile, les filtres (dont le champ de recherche) sont cachés derrière « Filtrer les formations »
    assert nav.dans_page(lambda p: p.get_by_label("Libellé de la formation").is_visible()) is False
    assert nav.dans_page(lambda p: p.get_by_role("button", name="Filtrer les formations").is_visible()) is True

    res = nav.action("ajouter_voeux_panier", voeux=[_voeu("v1", *RENNES)])
    assert res.resultats_voeux[0]["statut"] == "ajoute"
    assert res.resultats_voeux[0]["motivation_enregistree"] is True
    assert nav.dans_page(lambda p: p.viewport_size)["width"] == 1280
    _aucun_piege(nav)


def test_profil_reel_applique_a_la_maquette_par_defaut_sans_parametre(nav: Navigation) -> None:
    nav.ouvrir()
    res = nav.action("ajouter_voeux_panier", voeux=[_voeu("v1", *RENNES)], profil=None)
    assert res.resultats_voeux[0]["statut"] == "ajoute"
    assert res.resultats_voeux[0]["motivation_enregistree"] is True


def test_action_toujours_refusee_sur_le_vrai_domaine_non_homologue(nav: Navigation) -> None:
    # Même avec un profil explicite, le vrai portail non homologué est refusé AVANT toute ouverture de navigateur
    res = nav.action(
        "ajouter_voeux_panier",
        voeux=[_voeu("v1", *NANTERRE, niveau="Bac +5")],
        cible="campus_france_officiel",
        portail_homologue=False,
    )
    assert res.succes is False
    assert "homologué" in res.reponse_agent
    assert res.resultats_voeux == []
    assert nav.g._page is None
