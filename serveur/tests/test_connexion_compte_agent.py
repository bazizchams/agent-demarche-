"""Connexion aux portails et creation de compte Etudes en France par l'agent local (coffre, consentement, R1/R2/R3/R4).

Navigateur : vrai Chromium Playwright ; les pages de demonstration (`/demo/eef-compte/...`) sont servies par
interception depuis l'application de test. L'humain est simule DANS le fil de l'agent (remplacement de `_pause`).
Donnees fictives uniquement ; marqueurs de mot de passe pour verifier l'absence de fuite.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy import update

from app.agent_local import action_connexion_portail as acp
from app.agent_local import action_creation_compte_eef as acc
from app.agent_local import formulaires_portail as fp
from app.agent_local.demon_ecoute import DemonEcoute
from app.core.config import Parametres
from app.db.base import maintenant_utc
from app.db.tenant import definir_tenant
from app.modeles.echange_coffre import EchangeCoffre
from app.modeles.tache import (
    ACTION_AJOUTER_VOEUX_PANIER,
    ACTION_CONNEXION_PORTAIL,
    ACTION_CREATION_COMPTE_EEF,
)
from tests.conftest import DonneesBureauTest, connecter_client
from tests.test_agent_ecoute_demon import Scenario, playwright_sync  # noqa: F401 (fixture)
from tests.test_agent_ecoute_serveur import client_agent, enroler_agent

MDP_COFFRE = "MdpCoffre-Qx71-MARQUEUR"
MDP_HUMAIN = "MdpHumain-Wv52-MARQUEUR"
EMAIL = "etudiant.compte@exemple-fictif.dz"
URL = "http://testserver"


class Banc(Scenario):
    def demon(self, **kw: Any) -> DemonEcoute:  # type: ignore[override]
        from app.agent_local.action_voeux_demo import executer_ajout_voeux_demo

        return DemonEcoute(
            client_api=self.agent,
            fenetre=self.fenetre,
            executeurs={
                ACTION_AJOUTER_VOEUX_PANIER: executer_ajout_voeux_demo,
                ACTION_CONNEXION_PORTAIL: acp.executer_connexion_portail,
                ACTION_CREATION_COMPTE_EEF: acc.executer_creation_compte_eef,
            },
            url_serveur=URL,
            intervalle_sondage_s=0.05,
            intervalle_battement_s=3600,
            sortie=self.sortie.append,
        )

    def candidat(self, **champs: Any) -> str:
        corps = {"nom": "Compte", "prenom": "Etudiant", "email": EMAIL, "consentement_signe": True}
        corps.update(champs)
        corps = {k: v for k, v in corps.items() if v is not None}
        rep = self.admin.post("/api/v1/candidats", json=corps)
        assert rep.status_code == 201, rep.text
        return rep.json()["id"]

    def coffre(self, cid: str, portail: str = "etudes_en_france", mdp: str = MDP_COFFRE) -> None:
        rep = self.admin.put(
            f"/api/v1/candidats/{cid}/coffre/{portail}",
            json={"identifiant": EMAIL, "mot_de_passe": mdp, "consentement": True},
        )
        assert rep.status_code == 200, rep.text

    def tache_pc(self, cid: str, action: str, demarche: str, portail: str | None = None) -> str:
        corps = {"candidat_id": cid, "code_demarche": demarche, "action": action}
        if portail:
            corps["portail"] = portail
        rep = self.admin.post("/api/v1/taches", json=corps)
        assert rep.status_code == 201, rep.text
        return rep.json()["id"]

    def evenements(self, tache_id: str) -> str:
        return self.admin.get(f"/api/v1/taches/{tache_id}/evenements").text


@pytest.fixture()
def banc(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
    tmp_path: Path,
    playwright_sync: Any,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> Any:
    b = Banc(application, deux_bureaux[0], tmp_path, playwright_sync)
    b.bureaux = deux_bureaux  # type: ignore[attr-defined]
    monkeypatch.setattr(acp, "INTERVALLE_S", 0.05)
    monkeypatch.setattr(acp, "ATTENTE_CONSENTEMENT_S", 5.0)
    monkeypatch.setattr(acp, "ATTENTE_HUMAIN_S", 8.0)
    monkeypatch.setattr(acp, "ATTENTE_CONFIRMATION_S", 3.0)
    try:
        yield b
    finally:
        b.fermer()


def _variante(monkeypatch: pytest.MonkeyPatch, module: Any, suffixe: str) -> None:
    original = fp.url_cible
    monkeypatch.setattr(module, "url_cible", lambda p, f, u: original(p, f, u) + suffixe)


def _humain_unique(monkeypatch: pytest.MonkeyPatch, action: Callable[[Any], None]) -> None:
    """Remplace `_pause` : l'humain agit une seule fois (dans le fil de l'agent), puis l'agent poursuit."""
    fait: list[bool] = []

    def pause(ctx: Any, jr: Any, duree_s: float) -> None:
        if not fait:
            fait.append(True)
            action(ctx)
        ctx.page.wait_for_timeout(50)

    monkeypatch.setattr(acp, "_pause", pause)


def _tout_le_texte(b: Banc, tmp_path: Path, tache_id: str, caplog: pytest.LogCaptureFixture) -> str:
    octets = (tmp_path / "test_bureau.db").read_bytes()
    audit = b.admin.get("/api/v1/audit?taille=100").text
    return "\n".join(
        [octets.decode("latin-1"), audit, b.evenements(tache_id), b.admin.get(f"/api/v1/taches/{tache_id}").text,
         "\n".join(b.sortie), caplog.text]
    )


# --------------------------------------------------------------------------- API : consentement, usage unique, expiration
def _tache_detenue(b: Banc) -> tuple[str, str]:
    cid = b.candidat()
    b.coffre(cid)
    tid = b.tache_pc(cid, ACTION_CONNEXION_PORTAIL, "compte_etudes_en_france", "etudes_en_france")
    rep = b.agent.post("/api/v1/taches/reserver-suivante", params={"actions": [ACTION_CONNEXION_PORTAIL]})
    assert rep.json()["tache"]["id"] == tid
    return cid, tid


def test_aucun_identifiant_sans_consentement_puis_usage_unique(banc: Banc) -> None:
    _, tid = _tache_detenue(banc)
    rep = banc.agent.post(f"/api/v1/taches/{tid}/identifiants-portail/remise")
    assert rep.status_code == 403 and MDP_COFFRE not in rep.text

    # L'humain autorise : un autre agent du bureau ne reçoit rien, le détenteur reçoit UNE fois.
    assert banc.admin.post(f"/api/v1/taches/{tid}/autoriser-connexion").status_code == 200
    _, jeton2 = enroler_agent(banc.admin, "PC-Autre")
    autre = client_agent(banc.application, jeton2)
    assert autre.post(f"/api/v1/taches/{tid}/identifiants-portail/remise").status_code == 403
    ok = banc.agent.post(f"/api/v1/taches/{tid}/identifiants-portail/remise")
    assert ok.status_code == 200 and ok.json()["mot_de_passe"] == MDP_COFFRE
    assert ok.headers["cache-control"] == "no-store"
    assert banc.agent.post(f"/api/v1/taches/{tid}/identifiants-portail/remise").status_code == 403
    # Un humain (cookie) n'obtient jamais les identifiants par cette route.
    assert banc.admin.post(f"/api/v1/taches/{tid}/identifiants-portail/remise").status_code in (401, 403)


def test_autorisation_expiree_apres_60_secondes(banc: Banc, fabrique_sessions: Any,
                                                deux_bureaux: Any) -> None:
    _, tid = _tache_detenue(banc)
    rep = banc.admin.post(f"/api/v1/taches/{tid}/autoriser-connexion")
    assert rep.json()["duree_secondes"] == 60
    with fabrique_sessions() as db:
        definir_tenant(db, deux_bureaux[0].bureau.id)
        db.execute(update(EchangeCoffre).values(expire_le=maintenant_utc().replace(year=2020)))
        db.commit()
    assert banc.agent.post(f"/api/v1/taches/{tid}/identifiants-portail/remise").status_code == 403


def test_autre_bureau_ne_recoit_rien(banc: Banc, application: FastAPI) -> None:
    _, tid = _tache_detenue(banc)
    assert banc.admin.post(f"/api/v1/taches/{tid}/autoriser-connexion").status_code == 200
    admin_b, _ = connecter_client(application, banc.bureaux[1].admin.email)  # type: ignore[attr-defined]
    _, jeton_b = enroler_agent(admin_b, "PC-B")
    agent_b = client_agent(application, jeton_b)
    rep = agent_b.post(f"/api/v1/taches/{tid}/identifiants-portail/remise")
    assert rep.status_code in (403, 404) and MDP_COFFRE not in rep.text
    assert admin_b.post(f"/api/v1/taches/{tid}/autoriser-connexion").status_code in (403, 404)


def test_consentement_exige_une_tache_detenue_et_un_coffre(banc: Banc) -> None:
    cid = banc.candidat()
    tid = banc.tache_pc(cid, ACTION_CONNEXION_PORTAIL, "compte_etudes_en_france", "etudes_en_france")
    assert banc.admin.post(f"/api/v1/taches/{tid}/autoriser-connexion").status_code == 409  # pas détenue
    banc.agent.post("/api/v1/taches/reserver-suivante", params={"actions": [ACTION_CONNEXION_PORTAIL]})
    assert banc.admin.post(f"/api/v1/taches/{tid}/autoriser-connexion").status_code == 409  # coffre vide


# --------------------------------------------------------------------------- navigateur : connexion
def test_connexion_par_le_coffre_apres_consentement_sans_fuite(
    banc: Banc, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    cid = banc.candidat()
    banc.coffre(cid)
    tid = banc.tache_pc(cid, ACTION_CONNEXION_PORTAIL, "compte_etudes_en_france", "etudes_en_france")
    _humain_unique(monkeypatch, lambda ctx: banc.admin.post(f"/api/v1/taches/{tid}/autoriser-connexion"))
    assert banc.demon().sonder_une_fois() is True
    tache = banc.tache(tid)
    assert tache["statut"] == "a_valider" and tache["recapitulatif_remplissage"]["mode"] == "coffre"
    assert banc.dans_page("document.body.innerText").count("Se déconnecter") == 1
    texte = _tout_le_texte(banc, tmp_path, tid, caplog)
    assert MDP_COFFRE not in texte and EMAIL not in banc.evenements(tid)
    audit = banc.admin.get("/api/v1/audit?taille=100").text
    assert "coffre.autorisation_connexion" in audit and "coffre.remis_agent" in audit
    assert "Connexion confirmée" in banc.evenements(tid)


def test_captcha_avant_la_saisie_met_en_pause_sans_lire_le_coffre(
    banc: Banc, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = banc.candidat()
    banc.coffre(cid)
    tid = banc.tache_pc(cid, ACTION_CONNEXION_PORTAIL, "compte_etudes_en_france", "etudes_en_france")
    _variante(monkeypatch, acp, "?captcha=1")
    assert banc.demon().sonder_une_fois() is True
    tache = banc.tache(tid)
    assert tache["statut"] == "suspendue" and "CAPTCHA" in tache["message_alerte"]
    audit = banc.admin.get("/api/v1/audit?taille=100").text
    assert "coffre.remis_agent" not in audit and "coffre.utilise" not in audit
    assert "résolvez-le vous-même" in banc.evenements(tid)


def test_sans_identifiants_demande_humaine_sans_champ_de_mot_de_passe_puis_depot_pour_le_coffre(
    banc: Banc, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    cid = banc.candidat()
    tid = banc.tache_pc(cid, ACTION_CONNEXION_PORTAIL, "ircc_permis_etudes", "ircc")

    def humain(ctx: Any) -> None:  # l'humain tape dans le formulaire du portail puis le soumet
        ctx.page.get_by_label("Nom d'utilisateur").fill(EMAIL)
        ctx.page.get_by_label("Mot de passe", exact=True).fill(MDP_HUMAIN)
        ctx.page.get_by_role("button", name="Se connecter").click()

    _humain_unique(monkeypatch, humain)
    assert banc.demon().sonder_une_fois() is True
    tache = banc.tache(tid)
    assert tache["statut"] == "a_valider" and tache["recapitulatif_remplissage"]["mode"] == "manuel"
    assert "Tapez vos identifiants directement dans le formulaire du portail" in banc.evenements(tid)
    # Aucun champ de mot de passe dans le panneau injecté (script sans <input type=password>).
    source = (Path(acp.__file__).parent / "panneau_discussion.py").read_text(encoding="utf-8")
    assert "type=\"password\"" not in source and "type='password'" not in source
    assert "createElement(\"input\")" not in source and "createElement('input')" not in source

    # L'interface web (pas le panneau) propose l'enregistrement ; refus sans consentement, accord avec.
    etat = banc.admin.get(f"/api/v1/taches/{tid}/depot-identifiants").json()
    assert etat["present"] is True and set(etat) == {"present", "portail", "expire_le"}
    assert banc.admin.post(f"/api/v1/taches/{tid}/depot-identifiants/enregistrer",
                           json={"consentement": False}).status_code == 422
    assert banc.admin.get(f"/api/v1/candidats/{cid}/coffre/ircc").json()["existe"] is False
    assert MDP_HUMAIN not in _tout_le_texte(banc, tmp_path, tid, caplog)
    rep = banc.admin.post(f"/api/v1/taches/{tid}/depot-identifiants/enregistrer", json={"consentement": True})
    assert rep.status_code == 200 and MDP_HUMAIN not in rep.text
    assert banc.admin.get(f"/api/v1/candidats/{cid}/coffre/ircc").json()["existe"] is True
    assert banc.admin.get(f"/api/v1/taches/{tid}/depot-identifiants").json()["present"] is False
    assert MDP_HUMAIN not in _tout_le_texte(banc, tmp_path, tid, caplog)


# --------------------------------------------------------------------------- navigateur : creation de compte
def _valeurs_page(b: Banc) -> dict[str, Any]:
    return b.dans_page(
        """() => ({prenom: a1.value, nom: a2.value, espace: a3.value, mail: a5.value,
                   mdp_egaux: a6.value === a7.value && a6.value.length >= 12, c1: c1.checked, c2: c2.checked,
                   soumissions: window.__SOUMISSIONS__.length})"""
    )


def test_creation_de_compte_arret_avant_soumission_mot_de_passe_au_coffre(
    banc: Banc, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    cid = banc.candidat()
    tid = banc.tache_pc(cid, ACTION_CREATION_COMPTE_EEF, "compte_etudes_en_france")
    assert banc.demon().sonder_une_fois() is True
    tache = banc.tache(tid)
    assert tache["statut"] == "a_valider"
    recap = tache["recapitulatif_remplissage"]
    assert recap["bouton_inscription_clique"] is False and recap["mot_de_passe_enregistre_au_coffre"] is True
    assert "region_residence" in recap["a_faire_par_un_humain"]
    page = _valeurs_page(banc)
    assert page == {"prenom": "Etudiant", "nom": "Compte", "espace": "Espace Campus France Algérie", "mail": EMAIL,
                    "mdp_egaux": True, "c1": False, "c2": False, "soumissions": 0}
    # Le mot de passe est AU COFFRE avant la soumission, et l'agent peut le relire apres consentement.
    assert banc.admin.get(f"/api/v1/candidats/{cid}/coffre/etudes_en_france").json()["existe"] is True
    mdp_page = banc.dans_page("a6.value")
    assert MDP_COFFRE not in mdp_page and len(mdp_page) >= 12
    banc.agent.post("/api/v1/taches/reserver-suivante")  # aucune autre tâche
    texte = _tout_le_texte(banc, tmp_path, tid, caplog)
    assert mdp_page not in texte and "Je m'arrête AVANT" in banc.evenements(tid)


def test_creation_champ_manquant_arret_sans_ouvrir_le_portail(banc: Banc) -> None:
    cid = banc.candidat(email=None)
    tid = banc.tache_pc(cid, ACTION_CREATION_COMPTE_EEF, "compte_etudes_en_france")
    assert banc.demon().sonder_une_fois() is True
    tache = banc.tache(tid)
    assert tache["statut"] == "suspendue" and tache["champs_manquants"] == ["email"]
    assert tache["motif_suspension"] == "donnee_manquante"
    assert banc.admin.get(f"/api/v1/candidats/{cid}/coffre/etudes_en_france").json()["existe"] is False
    assert "demo/eef-compte" not in (banc.fenetre.page().url or "")


def test_creation_sans_consentement_ou_avec_compte_existant_ou_captcha(
    banc: Banc, monkeypatch: pytest.MonkeyPatch
) -> None:
    sans = banc.candidat(nom="Sans", consentement_signe=False, email="sans@exemple-fictif.dz")
    t1 = banc.tache_pc(sans, ACTION_CREATION_COMPTE_EEF, "compte_etudes_en_france")
    assert banc.demon().sonder_une_fois() is True
    assert banc.tache(t1)["statut"] == "suspendue"

    deja = banc.candidat(nom="Deja", email="deja@exemple-fictif.dz")
    banc.coffre(deja)
    t2 = banc.tache_pc(deja, ACTION_CREATION_COMPTE_EEF, "compte_etudes_en_france")
    assert banc.demon().sonder_une_fois() is True
    assert "second compte" in banc.tache(t2)["message_alerte"]

    capt = banc.candidat(nom="Capt", email="capt@exemple-fictif.dz")
    t3 = banc.tache_pc(capt, ACTION_CREATION_COMPTE_EEF, "compte_etudes_en_france")
    _variante(monkeypatch, acc, "?captcha=1")
    assert banc.demon().sonder_une_fois() is True
    assert banc.tache(t3)["statut"] == "suspendue" and "CAPTCHA" in banc.tache(t3)["message_alerte"]
    assert banc.admin.get(f"/api/v1/candidats/{capt}/coffre/etudes_en_france").json()["existe"] is False


# --------------------------------------------------------------------------- unites
def test_mot_de_passe_genere_conforme_et_secret_efface() -> None:
    regles = fp.charger_formulaires("etudes_en_france").inscription.regles_mot_de_passe  # type: ignore[union-attr]
    for _ in range(50):
        assert fp.mot_de_passe_conforme(fp.generer_mot_de_passe(regles), regles)
    secret = fp.SecretEphemere("abc")
    assert "abc" not in repr(secret) and secret.valeur() == "abc"
    secret.effacer()
    assert secret.efface


def test_domaines_regle_6(parametres_test: Parametres) -> None:
    f = fp.charger_formulaires("ircc")
    assert fp.motif_url_refusee("http://testserver/demo/gckey/connexion", f, URL) is None
    assert fp.motif_url_refusee("http://testserver/autre", f, URL) is not None
    assert fp.motif_url_refusee("https://pirate.example/demo/x", f, URL) is not None
    reel = f.model_copy(update={"statut": fp.STATUT_REEL_HOMOLOGUE})
    assert fp.motif_url_refusee("https://clegc-gckey.gc.ca/j/fra/l", reel, URL) is None
    assert fp.motif_url_refusee("https://clegc-gckey.gc.ca.pirate.example/j", reel, URL) is not None
    assert "ReqID" not in fp.url_cible(f.connexion, reel, URL)
