"""Soumission finale uniquement après validation humaine (Règle 1 réécrite), sur HTML local."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from playwright.sync_api import Page, sync_playwright
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.agent_local.config_portail import ConfigPortailYAML
from app.agent_local.executeur_playwright import (
    ParametresSoumissionValidee,
    executer_tache_sur_page_playwright,
)
from app.agent_local.garde_fous import (
    ErreurSoumissionFinaleInterdite,
    SuspensionRequiseParGardeFou,
    cliquer_securise,
)
from app.agent_local.soumission_validee import soumettre_apres_validation
from app.api.dependances import EN_TETE_JETON_AGENT
from app.core.erreurs import AccesRefuse, Conflit
from app.db.tenant import definir_tenant
from app.modeles.journal_audit import EntreeAudit
from app.services import validation_recapitulatif as validations
from tests.conftest import DonneesBureauTest, connecter_client
from tests.test_connexion_portail import _ClientApiFactice

BASE = "/api/v1/validations-recapitulatif"
CONTENU = {"nom": "MANSOURI-Zohra", "voeux": ["Informatique Lyon"], "champs_manquants": []}
FINAL = "#btn-final"

PAGE = """
<html><body>
<div id="bandeau-connecte">Connecte</div>
<div id="captcha" style="display:{captcha}">CAPTCHA</div>
<button id="btn-final" type="button">Envoyer</button>
<script>
window.__envois = 0;
document.getElementById('btn-final').addEventListener('click', function () {{ window.__envois += 1; }});
</script></body></html>
"""


def _config() -> ConfigPortailYAML:
    return ConfigPortailYAML.model_validate(dict(
        code_demarche="campus_france", nom_portail="Portail local de test", chemin_url="/x",
        temoin_session_ouverte="#bandeau-connecte", detecteurs_blocage_securite=["#captcha"],
        selecteurs_soumission_interdits=[FINAL],
        etapes_automatisation=[
            {"code_etape": "ouverture", "type_action": "verifier_session_et_securite"}
        ],
    ))


@pytest.fixture()
def page() -> Iterator[Page]:
    with sync_playwright() as p:
        navigateur = p.chromium.launch(headless=True)
        yield navigateur.new_page()
        navigateur.close()


class _Env:
    def __init__(self, application: FastAPI, fabrique: sessionmaker[Session],
                 bureau: DonneesBureauTest) -> None:
        self.application, self.fabrique, self.bureau = application, fabrique, bureau
        self.employe, _ = connecter_client(application, bureau.employe.email)
        self.admin, _ = connecter_client(application, bureau.admin.email)
        rep = self.employe.post("/api/v1/candidats", json={"nom": "MANSOURI", "prenom": "Zohra"})
        assert rep.status_code == 201, rep.text
        self.cid = rep.json()["id"]

    def proposer(self, contenu: dict | None = None) -> uuid.UUID:
        rep = self.employe.post(BASE, json={
            "candidat_id": self.cid, "portail": "campus_france",
            "type_demarche": "campus_france", "contenu": contenu or CONTENU,
        })
        assert rep.status_code == 201, rep.text
        return uuid.UUID(rep.json()["id"])

    def proposer_et_valider(self, contenu: dict | None = None) -> uuid.UUID:
        vid = self.proposer(contenu)
        assert self.employe.post(f"{BASE}/{vid}/valider").status_code == 200
        return vid

    def statut(self, db: Session, vid: uuid.UUID) -> str:
        return validations.obtenir(db, vid).statut.value

    def db(self) -> Session:
        db = self.fabrique()
        definir_tenant(db, self.bureau.bureau.id)
        return db


@pytest.fixture()
def env(application: FastAPI, fabrique_sessions: sessionmaker[Session], deux_bureaux) -> _Env:
    return _Env(application, fabrique_sessions, deux_bureaux[0])


def _envois(page: Page) -> int:
    return page.evaluate("window.__envois")


def test_soumission_ok_avec_validation_humaine_puis_marquee_envoyee(page: Page, env: _Env) -> None:
    page.set_content(PAGE.format(captcha="none"))
    vid = env.proposer_et_valider()
    with env.db() as db:
        res = soumettre_apres_validation(page, db, vid, dict(CONTENU), FINAL, _config())
        assert res.envoyee is True and res.validation_id == vid
        assert _envois(page) == 1
        assert env.statut(db, vid) == "envoyee"
        actions = [e.action for e in db.scalars(select(EntreeAudit)).all()]
        assert "validation_recapitulatif.envoye" in actions
        details = json.dumps([e.details for e in db.scalars(select(EntreeAudit)).all()], default=str)
        assert "MANSOURI" not in details and "Lyon" not in details


def test_refus_sans_validation(page: Page, env: _Env) -> None:
    page.set_content(PAGE.format(captcha="none"))
    with env.db() as db:
        with pytest.raises(AccesRefuse):
            soumettre_apres_validation(page, db, None, dict(CONTENU), FINAL, _config())
        vid = env.proposer()  # en attente : non validée
        with pytest.raises(AccesRefuse):
            soumettre_apres_validation(page, db, vid, dict(CONTENU), FINAL, _config())
    assert _envois(page) == 0


def test_refus_si_validation_refusee_ou_invalidee(page: Page, env: _Env) -> None:
    page.set_content(PAGE.format(captcha="none"))
    vid_refusee = env.proposer()
    assert env.employe.post(f"{BASE}/{vid_refusee}/refuser").status_code == 200
    with env.db() as db:
        with pytest.raises(AccesRefuse):
            soumettre_apres_validation(page, db, vid_refusee, dict(CONTENU), FINAL, _config())
        ancienne = env.proposer_et_valider()
        env.proposer({**CONTENU, "voeux": ["Autre"]})  # invalide la précédente
        with pytest.raises(AccesRefuse):
            soumettre_apres_validation(page, db, ancienne, dict(CONTENU), FINAL, _config())
    assert _envois(page) == 0


def test_refus_apres_modification_du_contenu(page: Page, env: _Env) -> None:
    page.set_content(PAGE.format(captcha="none"))
    vid = env.proposer_et_valider()
    with env.db() as db:
        with pytest.raises(Conflit):
            soumettre_apres_validation(
                page, db, vid, {**CONTENU, "voeux": ["Autre formation"]}, FINAL, _config()
            )
        assert env.statut(db, vid) == "invalidee"
        with pytest.raises(AccesRefuse):  # plus jamais envoyable, même avec le contenu d'origine
            soumettre_apres_validation(page, db, vid, dict(CONTENU), FINAL, _config())
    assert _envois(page) == 0


def test_refus_du_deuxieme_envoi(page: Page, env: _Env) -> None:
    page.set_content(PAGE.format(captcha="none"))
    vid = env.proposer_et_valider()
    with env.db() as db:
        soumettre_apres_validation(page, db, vid, dict(CONTENU), FINAL, _config())
        with pytest.raises(AccesRefuse):
            soumettre_apres_validation(page, db, vid, dict(CONTENU), FINAL, _config())
    assert _envois(page) == 1


def test_validation_proposee_par_un_agent_ne_peut_pas_etre_validee_par_lui(
    page: Page, application: FastAPI, env: _Env
) -> None:
    page.set_content(PAGE.format(captcha="none"))
    rep = env.admin.post("/api/v1/agents-locaux", json={"nom_machine": "PC-TEST-SOUMISSION"})
    assert rep.status_code == 201, rep.text
    agent = TestClient(application)
    agent.headers[EN_TETE_JETON_AGENT] = rep.json()["jeton_secret"]
    rep_p = agent.post(BASE, json={
        "candidat_id": env.cid, "portail": "campus_france",
        "type_demarche": "campus_france", "contenu": CONTENU,
    })
    assert rep_p.status_code == 201, rep_p.text
    vid = uuid.UUID(rep_p.json()["id"])
    assert agent.post(f"{BASE}/{vid}/valider").status_code in (401, 403)
    with env.db() as db:
        with pytest.raises(AccesRefuse):
            soumettre_apres_validation(page, db, vid, dict(CONTENU), FINAL, _config())
    assert _envois(page) == 0


def test_captcha_juste_avant_le_clic_suspend_sans_consommer_la_validation(
    page: Page, env: _Env
) -> None:
    page.set_content(PAGE.format(captcha="block"))
    vid = env.proposer_et_valider()
    with env.db() as db:
        with pytest.raises(SuspensionRequiseParGardeFou) as exc:
            soumettre_apres_validation(page, db, vid, dict(CONTENU), FINAL, _config())
        assert "CAPTCHA" in exc.value.message_alerte
        assert env.statut(db, vid) == "validee"  # toujours utilisable après résolution humaine
    assert _envois(page) == 0


def test_selecteur_non_declare_comme_bouton_final_refuse(page: Page, env: _Env) -> None:
    page.set_content(PAGE.format(captcha="none"))
    vid = env.proposer_et_valider()
    with env.db() as db:
        with pytest.raises(AccesRefuse):
            soumettre_apres_validation(page, db, vid, dict(CONTENU), "#captcha", _config())
        assert env.statut(db, vid) == "validee"
    assert _envois(page) == 0


def test_echec_du_clic_ne_marque_pas_envoyee(page: Page, env: _Env) -> None:
    page.set_content(PAGE.format(captcha="none").replace('id="btn-final"', 'id="autre"'))
    vid = env.proposer_et_valider()
    with env.db() as db:
        with pytest.raises(SuspensionRequiseParGardeFou) as exc:
            soumettre_apres_validation(page, db, vid, dict(CONTENU), FINAL, _config())
        assert exc.value.motif.value == "selecteur_portail_introuvable"
        assert env.statut(db, vid) == "validee"


def test_le_blocage_generique_reste_actif_sur_les_autres_chemins(page: Page, env: _Env) -> None:
    page.set_content(PAGE.format(captcha="none"))
    vid = env.proposer_et_valider()  # même avec une validation valable...
    assert vid
    with pytest.raises(ErreurSoumissionFinaleInterdite):
        cliquer_securise(page, FINAL, _config(), code_etape="x")
    assert _envois(page) == 0


def test_executeur_par_defaut_s_arrete_avant_le_bouton_final(page: Page) -> None:
    page.set_content(PAGE.format(captcha="none"))
    client = _ClientApiFactice()
    res = executer_tache_sur_page_playwright(
        page, tache_id="t1", client_api=client, config_portail=_config(),
        url_base_portail="http://x", naviguer_au_demarrage=False,
    )
    assert res.statut_final == "a_valider" and _envois(page) == 0
    recap = _recap(client)
    assert recap["bouton_soumission_finale_clique"] is False


def _recap(client: _ClientApiFactice) -> dict[str, Any]:
    corps = next(j for u, j in client.posts if "soumettre-validation" in u)
    return corps["recapitulatif_remplissage"]


def test_executeur_clique_le_bouton_final_avec_validation(page: Page, env: _Env) -> None:
    page.set_content(PAGE.format(captcha="none"))
    vid = env.proposer_et_valider()
    client = _ClientApiFactice()
    with env.db() as db:
        res = executer_tache_sur_page_playwright(
            page, tache_id="t1", client_api=client, config_portail=_config(),
            url_base_portail="http://x", naviguer_au_demarrage=False,
            soumission=ParametresSoumissionValidee(
                db=db, validation_id=vid, contenu_actuel=dict(CONTENU), selecteur_final=FINAL
            ),
        )
        assert env.statut(db, vid) == "envoyee"
    assert res.statut_final == "a_valider" and _envois(page) == 1
    assert _recap(client)["bouton_soumission_finale_clique"] is True


def test_executeur_sans_validation_valable_ne_clique_pas(page: Page, env: _Env) -> None:
    page.set_content(PAGE.format(captcha="none"))
    vid = env.proposer()  # jamais validée
    client = _ClientApiFactice()
    with env.db() as db:
        executer_tache_sur_page_playwright(
            page, tache_id="t1", client_api=client, config_portail=_config(),
            url_base_portail="http://x", naviguer_au_demarrage=False,
            soumission=ParametresSoumissionValidee(
                db=db, validation_id=vid, contenu_actuel=dict(CONTENU), selecteur_final=FINAL
            ),
        )
    recap = _recap(client)
    assert _envois(page) == 0
    assert recap["bouton_soumission_finale_clique"] is False
    assert recap["soumission_refusee"] == "acces_refuse"
