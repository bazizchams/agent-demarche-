"""Connexion automatique au portail via le coffre (Règles 2, 3 et 5), sur HTML local."""

from __future__ import annotations

import json
import logging
import traceback
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from playwright.sync_api import Page, sync_playwright
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.agent_local import connexion_portail
from app.agent_local.config_portail import ConfigPortailYAML
from app.agent_local.connexion_portail import connecter_si_necessaire
from app.agent_local.executeur_playwright import (
    ParametresConnexionCoffre,
    executer_tache_sur_page_playwright,
)
from app.agent_local.garde_fous import SuspensionRequiseParGardeFou
from app.db.tenant import definir_tenant
from app.modeles.journal_audit import EntreeAudit
from app.services import coffre_identifiants as coffre
from tests.conftest import DonneesBureauTest, connecter_client

IDENTIFIANT = "ident-portail-agent-5512"
MOT_DE_PASSE = "Mdp-Agent-Ultra-Secret-7391!"
PORTAIL = "etudes_en_france"

PAGE_PORTAIL = """
<html><body>
<div id="alerte-fermee" style="{fermee}">Session fermee</div>
<div id="bandeau-connecte" style="{ouverte}">Connecte</div>
<div id="captcha" style="{captcha}">CAPTCHA</div>
<form id="f" onsubmit="return false">
  <input id="login-id" type="text" />
  <input id="login-mdp" type="password" {readonly_mdp} />
  <button id="login-ok" type="button">Se connecter</button>
</form>
<button id="btn-final" type="button">Envoyer</button>
<script>
window.__tentatives = 0;
document.getElementById('login-ok').addEventListener('click', function () {{
  window.__tentatives += 1;
  const ok = document.getElementById('login-id').value === '{ident}'
          && document.getElementById('login-mdp').value === '{mdp}';
  if ('{apres}' === 'captcha') {{
    document.getElementById('captcha').style.display = 'block';
  }} else if (ok) {{
    document.getElementById('alerte-fermee').style.display = 'none';
    document.getElementById('bandeau-connecte').style.display = 'block';
  }}
}});
</script></body></html>
"""


def _html(
    *, ouverte: bool = False, captcha: bool = False, apres: str = "", ident: str = IDENTIFIANT,
    mdp: str = MOT_DE_PASSE, readonly_mdp: bool = False,
) -> str:
    return PAGE_PORTAIL.format(
        fermee="display:none" if ouverte else "display:block",
        ouverte="display:block" if ouverte else "display:none",
        captcha="display:block" if captcha else "display:none",
        readonly_mdp="readonly" if readonly_mdp else "",
        apres=apres, ident=ident, mdp=mdp,
    )


def _config(*, avec_login: bool = True) -> ConfigPortailYAML:
    donnees: dict[str, Any] = dict(
        code_demarche="campus_france", nom_portail="Portail local de test", chemin_url="/x",
        temoin_session_ouverte="#bandeau-connecte", detecteur_session_fermee="#alerte-fermee",
        detecteurs_blocage_securite=["#captcha"],
        selecteurs_soumission_interdits=["#btn-final"],
    )
    if avec_login:
        donnees.update(
            selecteur_identifiant="#login-id", selecteur_mot_de_passe="#login-mdp",
            selecteur_bouton_connexion="#login-ok",
        )
    return ConfigPortailYAML.model_validate(donnees)


@pytest.fixture()
def page() -> Iterator[Page]:
    with sync_playwright() as p:
        navigateur = p.chromium.launch(headless=True)
        yield navigateur.new_page()
        navigateur.close()


class _Contexte:
    def __init__(self, application: FastAPI, fabrique: sessionmaker[Session],
                 bureau: DonneesBureauTest) -> None:
        self.cle = application.state.cle_maitresse
        self.bureau = bureau
        client, _ = connecter_client(application, bureau.employe.email)
        rep = client.post("/api/v1/candidats", json={"nom": "TESTEUR", "prenom": "Fictif"})
        assert rep.status_code == 201, rep.text
        self.candidat_id = uuid.UUID(rep.json()["id"])
        self.fabrique = fabrique

    def stocker_identifiants(self, db: Session) -> None:
        coffre.enregistrer(
            db, candidat_id=self.candidat_id, portail=PORTAIL, identifiant=IDENTIFIANT,
            mot_de_passe=MOT_DE_PASSE, consentement=True, acteur_id=self.bureau.employe.id,
            cle_maitresse=self.cle,
        )

    def connecter(self, page: Page, db: Session, config: ConfigPortailYAML) -> Any:
        return connecter_si_necessaire(
            page, db, self.bureau.bureau.id, self.candidat_id, PORTAIL, config, "ouverture",
            cle_maitresse=self.cle,
        )


@pytest.fixture()
def ctx(application: FastAPI, fabrique_sessions: sessionmaker[Session], deux_bureaux):
    return _Contexte(application, fabrique_sessions, deux_bureaux[0])


def _actions_audit(db: Session) -> list[str]:
    return [e.action for e in db.scalars(select(EntreeAudit)).all()]


def _aucune_trace_du_secret(texte: str) -> None:
    assert MOT_DE_PASSE not in texte
    assert IDENTIFIANT not in texte


def _suspension_propre(exc: SuspensionRequiseParGardeFou) -> None:
    visible = str(exc) + repr(exc) + exc.message_alerte + "".join(traceback.format_exception(exc))
    _aucune_trace_du_secret(visible)
    assert exc.__cause__ is None and exc.__context__ is None


def test_connexion_reussie_via_coffre_sans_fuite_du_mot_de_passe(
    page: Page, ctx: _Contexte, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    page.set_content(_html())
    with ctx.fabrique() as db:
        definir_tenant(db, ctx.bureau.bureau.id)
        ctx.stocker_identifiants(db)
        resultat = ctx.connecter(page, db, _config())

        assert resultat.connexion_effectuee is True and resultat.session_deja_ouverte is False
        _aucune_trace_du_secret(repr(resultat))
        assert page.locator("#bandeau-connecte").is_visible()
        assert page.evaluate("window.__tentatives") == 1
        assert "coffre.utilise" in _actions_audit(db)
        audit_texte = json.dumps(
            [e.details for e in db.scalars(select(EntreeAudit)).all()], default=str
        )
        _aucune_trace_du_secret(audit_texte)
    _aucune_trace_du_secret(caplog.text)


def test_session_deja_ouverte_ne_lit_pas_le_coffre(page: Page, ctx: _Contexte) -> None:
    page.set_content(_html(ouverte=True))
    with ctx.fabrique() as db:
        definir_tenant(db, ctx.bureau.bureau.id)
        ctx.stocker_identifiants(db)
        resultat = ctx.connecter(page, db, _config())
        assert resultat.session_deja_ouverte is True and resultat.connexion_effectuee is False
        assert page.input_value("#login-id") == ""
        assert "coffre.utilise" not in _actions_audit(db)


def test_captcha_present_suspend_sans_saisie_ni_lecture_du_coffre(page: Page, ctx: _Contexte) -> None:
    page.set_content(_html(captcha=True))
    with ctx.fabrique() as db:
        definir_tenant(db, ctx.bureau.bureau.id)
        ctx.stocker_identifiants(db)
        with pytest.raises(SuspensionRequiseParGardeFou) as exc:
            ctx.connecter(page, db, _config())
        assert "CAPTCHA" in exc.value.message_alerte
        _suspension_propre(exc.value)
        assert page.input_value("#login-id") == "" and page.input_value("#login-mdp") == ""
        assert page.evaluate("window.__tentatives") == 0
        assert "coffre.utilise" not in _actions_audit(db)


def test_captcha_apparaissant_apres_la_connexion_suspend(
    page: Page, ctx: _Contexte, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    page.set_content(_html(apres="captcha"))
    with ctx.fabrique() as db:
        definir_tenant(db, ctx.bureau.bureau.id)
        ctx.stocker_identifiants(db)
        with pytest.raises(SuspensionRequiseParGardeFou) as exc:
            ctx.connecter(page, db, _config())
        assert "CAPTCHA" in exc.value.message_alerte
        _suspension_propre(exc.value)
    _aucune_trace_du_secret(caplog.text)


def test_coffre_vide_suspend_action_utilisateur_portail(page: Page, ctx: _Contexte) -> None:
    page.set_content(_html())
    with ctx.fabrique() as db:
        definir_tenant(db, ctx.bureau.bureau.id)
        with pytest.raises(SuspensionRequiseParGardeFou) as exc:
            ctx.connecter(page, db, _config())
        assert exc.value.motif.value == "action_utilisateur_portail"
        assert "coffre" in exc.value.message_alerte
        assert page.input_value("#login-id") == "" and page.evaluate("window.__tentatives") == 0


def test_sans_selecteurs_de_connexion_dans_le_yaml_connexion_manuelle(
    page: Page, ctx: _Contexte
) -> None:
    page.set_content(_html())
    with ctx.fabrique() as db:
        definir_tenant(db, ctx.bureau.bureau.id)
        ctx.stocker_identifiants(db)
        with pytest.raises(SuspensionRequiseParGardeFou) as exc:
            ctx.connecter(page, db, _config(avec_login=False))
        assert "Connexion manuelle requise" in exc.value.message_alerte
        assert "coffre.utilise" not in _actions_audit(db)


def test_identifiants_refuses_une_seule_tentative(page: Page, ctx: _Contexte) -> None:
    page.set_content(_html(mdp="autre-mot-de-passe"))
    with ctx.fabrique() as db:
        definir_tenant(db, ctx.bureau.bureau.id)
        ctx.stocker_identifiants(db)
        with pytest.raises(SuspensionRequiseParGardeFou) as exc:
            ctx.connecter(page, db, _config())
        assert "non confirmée" in exc.value.message_alerte
        _suspension_propre(exc.value)
        assert page.evaluate("window.__tentatives") == 1


def test_erreur_playwright_ne_laisse_pas_fuiter_le_mot_de_passe(
    page: Page, ctx: _Contexte, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Champ en lecture seule : Playwright expire ; son journal d'appel citerait la valeur."""
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(connexion_portail, "DELAI_CONNEXION_MS", 1500)
    page.set_content(_html(readonly_mdp=True))
    with ctx.fabrique() as db:
        definir_tenant(db, ctx.bureau.bureau.id)
        ctx.stocker_identifiants(db)
        with pytest.raises(SuspensionRequiseParGardeFou) as exc:
            ctx.connecter(page, db, _config())
        assert "saisie" in exc.value.message_alerte
        _suspension_propre(exc.value)
    _aucune_trace_du_secret(caplog.text)


def test_selecteur_de_connexion_interdit_refuse(page: Page, ctx: _Contexte) -> None:
    """Un sélecteur de connexion ne peut jamais désigner le bouton de soumission finale."""
    from app.agent_local.garde_fous import ErreurSoumissionFinaleInterdite

    page.set_content(_html())
    config = _config().model_copy(update={"selecteur_bouton_connexion": "#btn-final"})
    with ctx.fabrique() as db:
        definir_tenant(db, ctx.bureau.bureau.id)
        ctx.stocker_identifiants(db)
        with pytest.raises(ErreurSoumissionFinaleInterdite):
            ctx.connecter(page, db, config)
        assert "coffre.utilise" not in _actions_audit(db)


class _ClientApiFactice:
    """Imite l'API serveur strictement nécessaire à l'exécuteur (étape de vérification de session)."""

    def __init__(self) -> None:
        self.posts: list[tuple[str, Any]] = []

    class _Rep:
        def __init__(self, donnees: dict, code: int = 200) -> None:
            self._d, self.status_code = donnees, code
            self.text = json.dumps(donnees)

        def json(self) -> dict:
            return self._d

    def get(self, url: str, **_: Any) -> "_ClientApiFactice._Rep":
        if url.endswith("/contexte-execution"):
            return self._Rep({"candidat": {}, "documents": [],
                              "tache": {"etapes": [{"code_etape": "ouverture", "statut": "a_faire"}]}})
        return self._Rep({"statut": "en_cours"})

    def post(self, url: str, **kwargs: Any) -> "_ClientApiFactice._Rep":
        self.posts.append((url, kwargs.get("json")))
        return self._Rep({"statut": "a_valider" if "soumettre-validation" in url else "suspendue"})


def _config_avec_etape() -> ConfigPortailYAML:
    base = _config().model_dump(mode="json")
    base["etapes_automatisation"] = [
        {"code_etape": "ouverture", "type_action": "verifier_session_et_securite"}
    ]
    return ConfigPortailYAML.model_validate(base)


def test_executeur_se_connecte_via_coffre_quand_parametre_fourni(
    page: Page, ctx: _Contexte
) -> None:
    page.set_content(_html())
    client = _ClientApiFactice()
    with ctx.fabrique() as db:
        definir_tenant(db, ctx.bureau.bureau.id)
        ctx.stocker_identifiants(db)
        res = executer_tache_sur_page_playwright(
            page, tache_id="t1", client_api=client, config_portail=_config_avec_etape(),
            url_base_portail="http://x", naviguer_au_demarrage=False,
            connexion=ParametresConnexionCoffre(
                db=db, tenant=ctx.bureau.bureau.id, candidat_id=ctx.candidat_id,
                portail=PORTAIL, cle_maitresse=ctx.cle,
            ),
        )
    assert res.statut_final == "a_valider" and res.etapes_executees_dans_ce_cycle == ["ouverture"]
    _aucune_trace_du_secret(json.dumps(client.posts, default=str))


def test_executeur_par_defaut_ne_se_connecte_pas(page: Page, ctx: _Contexte) -> None:
    page.set_content(_html())
    client = _ClientApiFactice()
    res = executer_tache_sur_page_playwright(
        page, tache_id="t1", client_api=client, config_portail=_config_avec_etape(),
        url_base_portail="http://x", naviguer_au_demarrage=False,
    )
    assert res.statut_final == "suspendue" and res.motif_suspension == "action_utilisateur_portail"
    assert page.evaluate("window.__tentatives") == 0
