"""Régressions de la revue de sécurité : un test par correctif (H1, M1 à M5, B1, B3, B5, B6).

Données fictives uniquement ; aucun navigateur réel (fausses fenêtres et fausses pages) ni réseau.
"""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.agent_local import action_voeux_demo, lanceur_ecoute, ouverture_visible
from app.agent_local.demon_ecoute import ContexteExecution, DemonEcoute, ResultatExecution
from app.agent_local.ouverture_visible import (
    FenetreVisible,
    dossier_profils_par_defaut,
    restreindre_acces_utilisateur,
)
from app.api.v1.extractions import obtenir_lecteur_document
from app.core.chiffrement import charger_ou_creer_cle_maitresse
from app.core.erreurs import DonneesInvalides
from app.interface import ecran_revue_extractions as ecran
from app.main import creer_application
from app.modeles.extraction_document import STATUTS_APPLICABLES, StatutExtraction
from app.modeles.tache import ACTION_AJOUTER_VOEUX_PANIER, StatutTache, TacheDossier, VerrouDossier
from app.services import extractions as service_extractions
from app.services import lecture_documents as lecture
from app.services.lecture_documents import LecteurDocumentLocal
from tests import corpus_synthetique as corpus
from tests.conftest import DonneesBureauTest, connecter_client
from tests.test_agent_ecoute_serveur import (  # noqa: F401 - `admin_a` est une fixture réutilisée
    admin_a,
    client_agent,
    creer_candidat_avec_voeux,
    creer_tache_pc,
    enroler_agent,
)
from tests.test_extractions_api import LecteurFactice, _creer_candidat, _deposer, _extraire, _par_champ

RACINE_PLATEFORME = Path(__file__).resolve().parents[2]


# ===================================================================== H1 : profil navigateur et .gitignore


def test_h1_gitignore_exclut_profils_captures_et_venv_agent() -> None:
    lignes = {
        ligne.strip()
        for ligne in (RACINE_PLATEFORME / ".gitignore").read_text(encoding="utf-8").splitlines()
    }
    for motif in (
        "agent_local/profil_chromium/",
        "**/profil_chromium/",
        "agent_local/captures_controle/",
        "agent_local/.venv-agent/",
    ):
        assert motif in lignes, motif


def test_h1_profil_par_defaut_sous_localappdata_jamais_dans_le_depot(tmp_path: Path) -> None:
    dossier = dossier_profils_par_defaut({"LOCALAPPDATA": str(tmp_path)})
    assert dossier == tmp_path / "AgentBureau" / "profil_chromium"
    assert RACINE_PLATEFORME not in dossier.parents


def test_h1_acl_restreintes_a_l_utilisateur_courant(tmp_path: Path) -> None:
    appels: list[list[str]] = []

    def faux_icacls(commande: list[str], **_kw: Any) -> SimpleNamespace:
        appels.append(commande)
        return SimpleNamespace(returncode=0)

    assert restreindre_acces_utilisateur(
        tmp_path, utilisateur="PC\\alice", executer=faux_icacls, est_windows=True
    )
    commande = appels[0]
    assert commande[0].lower() == "icacls" and str(tmp_path) in commande
    assert "/inheritance:r" in commande and "/grant:r" in commande
    assert "PC\\alice:(OI)(CI)F" in commande


def test_h1_echec_d_icacls_ne_bloque_pas_le_lancement(tmp_path: Path) -> None:
    def casse(_commande: list[str], **_kw: Any) -> SimpleNamespace:
        raise OSError("icacls introuvable")

    assert restreindre_acces_utilisateur(
        tmp_path, utilisateur="PC\\alice", executer=casse, est_windows=True
    ) is False


def test_h1_le_demon_restreint_la_racine_des_profils(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    restreints: list[Path] = []
    monkeypatch.setattr(lanceur_ecoute, "restreindre_acces_utilisateur", lambda d: restreints.append(d) or True)
    racine = tmp_path / "profils"
    code = lanceur_ecoute.lancer_ecoute(
        url_serveur="http://127.0.0.1:9", jeton_agent="be_agent_factice", racine_profils=racine
    )
    assert code == 2  # serveur injoignable : mais le profil est protégé avant toute connexion
    assert restreints == [racine]


def _charger_lanceur() -> Any:
    chemin = RACINE_PLATEFORME / "agent_local" / "lanceur.py"
    spec = importlib.util.spec_from_file_location("lanceur_agent_local_revue", chemin)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_h1_le_lanceur_utilise_le_profil_par_defaut_hors_du_depot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    recu: dict[str, Any] = {}
    monkeypatch.setattr(lanceur_ecoute, "lancer_ecoute", lambda **kw: recu.update(kw) or 0)
    assert _charger_lanceur().main(["--mode", "ecouter"]) == 0
    assert recu["racine_profils"] == tmp_path / "AgentBureau" / "profil_chromium"


def test_h1_script_powershell_profil_localappdata_et_acl() -> None:
    script = (RACINE_PLATEFORME / "agent_local" / "lancer_agent.ps1").read_text(encoding="utf-8-sig")
    assert "LOCALAPPDATA" in script and "icacls" in script and "/inheritance:r" in script
    assert 'Join-Path $dossierAgent "profil_chromium"' not in script


# ===================================================================== B1 : jeton jamais en clair sur http distant


@pytest.mark.parametrize(
    "url",
    [
        "http://serveur.exemple-fictif.dz",
        "http://192.168.1.10:8000",
        "http://127.0.0.1.exemple-fictif.dz",
        "http://localhost:80@exemple-fictif.dz",
    ],
)
def test_b1_http_hors_localhost_refuse_avant_tout_envoi_du_jeton(
    url: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = lanceur_ecoute.lancer_ecoute(url_serveur=url, jeton_agent="be_agent_secret", racine_profils=tmp_path)
    err = capsys.readouterr().err
    assert code == 2 and "https" in err and "be_agent_secret" not in err


@pytest.mark.parametrize(
    "url", ["https://serveur.exemple-fictif.dz", "http://127.0.0.1:8000", "http://localhost:8000/"]
)
def test_b1_urls_autorisees(url: str) -> None:
    assert lanceur_ecoute.url_serveur_autorisee(url) is True


def test_b1_script_powershell_refuse_http_distant() -> None:
    script = (RACINE_PLATEFORME / "agent_local" / "lancer_agent.ps1").read_text(encoding="utf-8-sig")
    assert "Attention : cette adresse n'est pas chiffrée" not in script
    assert r"(:\d+)?(/|$)" in script  # port strict : pas de contournement par `localhost:80@hote`
    assert "refus" in script.lower()


# ===================================================================== M1 : pièces et contexte de la tâche


def test_m1_contexte_et_pieces_jamais_servis_a_une_tache_ouvrir_sur_mon_pc(
    application: FastAPI, admin_a: Any
) -> None:
    candidat_id, _, _ = creer_candidat_avec_voeux(admin_a)
    tache_id = creer_tache_pc(admin_a, candidat_id).json()["id"]
    _, jeton1 = enroler_agent(admin_a, "PC-1")
    _, jeton2 = enroler_agent(admin_a, "PC-2")
    detenteur, autre = client_agent(application, jeton1), client_agent(application, jeton2)
    assert detenteur.post("/api/v1/taches/reserver-suivante").json()["tache"]["id"] == tache_id

    contexte = f"/api/v1/taches/{tache_id}/contexte-execution"
    piece = f"/api/v1/taches/{tache_id}/documents/{uuid.uuid4()}/telecharger"
    for chemin in (contexte, piece):
        # Le détenteur lui-même n'a pas besoin des pièces pour ajouter des vœux : refus.
        assert detenteur.get(chemin).status_code == 403, chemin
        rep = autre.get(chemin)
        assert rep.status_code == 403 and "autre agent" in rep.json()["detail"], chemin


# ===================================================================== M2 : page d'arrivée de l'agent


URL_SERVEUR = "http://127.0.0.1:8000"


class _PageStricte:
    """Fausse page : toute interaction autre que `goto` est enregistrée (et doit rester vide)."""

    def __init__(self, url_apres_goto: str) -> None:
        self._url_apres = url_apres_goto
        self.url = "about:blank"
        self.interactions: list[str] = []

    def goto(self, url: str, **_kw: Any) -> SimpleNamespace:
        self.url = self._url_apres
        return SimpleNamespace(status=200)

    def __getattr__(self, nom: str) -> Any:
        def _appel(*_a: Any, **_kw: Any) -> Any:
            self.interactions.append(nom)
            raise AssertionError(f"interaction interdite : {nom}")

        return _appel


class _ClientVoeux:
    def get(self, url: str, **_kw: Any) -> httpx.Response:
        corps = {
            "voeux": [
                {
                    "voeu_id": str(uuid.uuid4()),
                    "intitule": "Master Fictif",
                    "etablissement": "Université Fictive",
                    "niveau": "Master 1",
                    "motivation": "Lettre fictive.",
                }
            ]
        }
        return httpx.Response(200, json=corps, request=httpx.Request("GET", "http://x" + url))


def _contexte(page: Any) -> ContexteExecution:
    return ContexteExecution(
        tache={"id": str(uuid.uuid4())},
        client_api=_ClientVoeux(),  # type: ignore[arg-type]
        page=page,
        url_serveur=URL_SERVEUR,
        amener_au_premier_plan=lambda: None,
    )


@pytest.mark.parametrize(
    "arrivee",
    [
        "http://pirate.exemple-fictif.dz/demo/campus-france",  # autre hôte
        "http://127.0.0.1:9999/demo/campus-france",  # autre port
        "https://127.0.0.1:8000/demo/campus-france",  # autre schéma
        "http://127.0.0.1:8000/connexion",  # autre chemin (redirection de connexion)
        "http://127.0.0.1.pirate.exemple-fictif.dz/demo/campus-france",  # hôte de ressemblance
    ],
)
def test_m2_page_d_arrivee_inattendue_aucune_interaction(arrivee: str) -> None:
    page = _PageStricte(arrivee)
    with pytest.raises(RuntimeError, match="attendue"):
        action_voeux_demo.executer_ajout_voeux_demo(_contexte(page))
    assert page.interactions == []  # ni remplissage, ni capture, ni lecture de la page


def test_m2_page_d_arrivee_attendue_acceptee() -> None:
    page = _PageStricte(URL_SERVEUR + "/demo/campus-france")
    action_voeux_demo._ouvrir_page_demo(_contexte(page))  # noqa: SLF001
    page.url = URL_SERVEUR + "/demo/campus-france/"  # barre finale tolérée
    action_voeux_demo._verifier_page_attendue(page, URL_SERVEUR)  # noqa: SLF001


# ===================================================================== M3 : profil navigateur par candidat


class _FauxContexte:
    def __init__(self) -> None:
        self.pages = [SimpleNamespace(bring_to_front=lambda: None)]
        self.ferme = False

    def close(self) -> None:
        self.ferme = True
        self.pages = []


class _FauxChromium:
    def __init__(self) -> None:
        self.appels: list[dict[str, Any]] = []
        self.contextes: list[_FauxContexte] = []

    def launch_persistent_context(self, **options: Any) -> _FauxContexte:
        self.appels.append(options)
        self.contextes.append(_FauxContexte())
        return self.contextes[-1]


def test_m3_un_profil_par_candidat_et_par_canal(tmp_path: Path) -> None:
    pw = SimpleNamespace(chromium=_FauxChromium())
    fenetre = FenetreVisible(pw, tmp_path / "bureau", canaux=("chrome",), headless=True)
    cand_a, cand_b = str(uuid.uuid4()), str(uuid.uuid4())

    fenetre.choisir_candidat(cand_a)
    fenetre.page()
    fenetre.choisir_candidat(cand_a)
    fenetre.page()
    assert len(pw.chromium.appels) == 1  # même candidat : fenêtre réutilisée

    fenetre.choisir_candidat(cand_b)
    fenetre.page()
    profils = [Path(a["user_data_dir"]) for a in pw.chromium.appels]
    assert profils == [tmp_path / "bureau" / cand_a / "chrome", tmp_path / "bureau" / cand_b / "chrome"]
    assert pw.chromium.contextes[0].ferme is True  # la session du candidat A n'est plus ouverte


@pytest.mark.parametrize("intrus", ["../autre-bureau", "..\\x", "a/b", "", "pas-un-uuid"])
def test_m3_identifiant_de_candidat_invalide_refuse(tmp_path: Path, intrus: str) -> None:
    fenetre = FenetreVisible(SimpleNamespace(chromium=_FauxChromium()), tmp_path, canaux=("chrome",))
    with pytest.raises(ValueError):
        fenetre.choisir_candidat(intrus)


class _FenetreEspionne:
    def __init__(self) -> None:
        self.evenements: list[str] = []

    def choisir_candidat(self, candidat_id: str) -> None:
        self.evenements.append(f"candidat:{candidat_id}")

    def page(self) -> object:
        self.evenements.append("page")
        return object()

    def amener_au_premier_plan(self) -> None:
        self.evenements.append("premier_plan")


def test_m3_le_demon_choisit_le_candidat_de_la_tache_avant_d_ouvrir_la_page() -> None:
    fenetre = _FenetreEspionne()
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _r: httpx.Response(200, json={})), base_url="http://127.0.0.1:8000"
    )
    demon = DemonEcoute(
        client_api=client,
        fenetre=fenetre,
        executeurs={ACTION_AJOUTER_VOEUX_PANIER: lambda _c: ResultatExecution()},
        url_serveur="http://127.0.0.1:8000",
        intervalle_battement_s=3600,
        sortie=lambda _l: None,
    )
    candidat = str(uuid.uuid4())
    demon._traiter({"id": str(uuid.uuid4()), "action": ACTION_AJOUTER_VOEUX_PANIER, "candidat_id": candidat})  # noqa: SLF001
    assert fenetre.evenements[0] == f"candidat:{candidat}"
    assert "page" in fenetre.evenements


# ===================================================================== M4 : une valeur « auto » exige un clic humain


def test_m4_seule_la_confirmation_humaine_rend_une_valeur_applicable() -> None:
    assert STATUTS_APPLICABLES == frozenset({StatutExtraction.VALIDE_HUMAIN})


def test_m4_une_valeur_auto_n_atteint_la_fiche_qu_apres_confirmation(
    application: FastAPI, deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest]
) -> None:
    application.dependency_overrides[obtenir_lecteur_document] = lambda: LecteurFactice()
    try:
        client, _ = connecter_client(application, deux_bureaux[0].employe.email)
        cid = _creer_candidat(client)
        did = _deposer(client, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE])
        champs = _par_champ(_extraire(client, cid, did))
        assert champs["numero_passeport"]["statut"] == "auto"  # MRZ valide

        base = f"/api/v1/candidats/{cid}/extractions"
        assert client.post(f"{base}/appliquer").json()["appliques"] == []
        assert client.get(f"/api/v1/candidats/{cid}").json()["numero_passeport"] in (None, "")

        assert client.post(f"{base}/{champs['numero_passeport']['id']}/valider").status_code == 200
        rapport = client.post(f"{base}/appliquer").json()
        assert [a["champ"] for a in rapport["appliques"]] == ["numero_passeport"]
        assert client.get(f"/api/v1/candidats/{cid}").json()["numero_passeport"] == "L898902C3"
    finally:
        application.dependency_overrides.pop(obtenir_lecteur_document, None)


def test_m4_ecran_de_revue_confirmer_pour_les_valeurs_auto() -> None:
    js = ecran.JS_REVUE
    bloc_statuts = js.split("const RX_STATUTS", 1)[1].split("};", 1)[0]
    assert "à confirmer" in bloc_statuts.split("auto:", 1)[1].split("]", 1)[0]
    assert 'extraction.statut !== "valide_humain"' in js  # Confirmer visible pour auto, à vérifier, rejeté
    assert '!== "auto"' not in js
    assert "même une valeur lue automatiquement" in ecran.HTML_VUE


# ===================================================================== M5 : lecture bornée et débit limité


def _faux_pillow(largeur: int, hauteur: int) -> SimpleNamespace:
    class _Image:
        size = (largeur, hauteur)

        def __enter__(self) -> "_Image":
            return self

        def __exit__(self, *_a: Any) -> None:
            return None

    return SimpleNamespace(MAX_IMAGE_PIXELS=None, open=lambda _flux: _Image())


class _MoteurSurveille:
    def __init__(self) -> None:
        self.appels = 0

    def reconnaitre(self, _image: bytes) -> list[tuple[str, float]]:
        self.appels += 1
        return [("texte", 0.9)]


def test_m5_image_au_dela_de_25_megapixels_refusee_avant_l_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    faux = _faux_pillow(6000, 5000)  # 30 Mpx
    monkeypatch.setattr(lecture, "_importer_pillow", lambda: faux)
    moteur = _MoteurSurveille()
    with pytest.raises(DonneesInvalides, match="trop grande"):
        LecteurDocumentLocal(moteur_ocr=moteur).lire_texte(corpus.construire_png_minimal(), "image/png")
    assert moteur.appels == 0
    assert faux.MAX_IMAGE_PIXELS == lecture.MAX_PIXELS_IMAGE == 25_000_000


def test_m5_image_raisonnable_lue_normalement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lecture, "_importer_pillow", lambda: _faux_pillow(3000, 2000))
    moteur = _MoteurSurveille()
    res = LecteurDocumentLocal(moteur_ocr=moteur).lire_texte(corpus.construire_png_minimal(), "image/png")
    assert moteur.appels == 1 and res.pages[0].texte == "texte"


def test_m5_nombre_d_images_par_page_borne() -> None:
    png = corpus.construire_png_minimal()
    consommees: list[int] = []

    class _Page:
        @property
        def images(self) -> Any:
            for i in range(100):
                consommees.append(i)
                yield SimpleNamespace(data=png)

    images = LecteurDocumentLocal._images_de_page(_Page())  # noqa: SLF001
    assert len(images) <= lecture.MAX_IMAGES_PAR_PAGE
    assert len(consommees) <= lecture.MAX_IMAGES_PAR_PAGE + 1  # on s'arrête sans tout décoder


def test_m5_delai_de_lecture_borne(monkeypatch: pytest.MonkeyPatch) -> None:
    class _PageTexte:
        def extract_text(self) -> str:
            return "x" * 60

    class _Lecteur:
        pages = [_PageTexte() for _ in range(5)]
        is_encrypted = False

    monkeypatch.setattr(lecture, "_importer_pypdf", lambda: SimpleNamespace(PdfReader=lambda _f: _Lecteur()))
    monkeypatch.setattr(lecture, "DELAI_MAX_LECTURE_S", -1.0)  # déjà dépassé dès la 2e page
    res = LecteurDocumentLocal().lire_texte(b"%PDF-1.4", "application/pdf")
    assert 1 <= len(res.pages) < 5
    assert any("délai" in a.lower() for a in res.avertissements)


def test_m5_limitation_de_debit_sur_extraire_et_lot(
    application: FastAPI,
    parametres_test: Any,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    cfg = parametres_test.model_copy(
        update={
            "extraction_limite_active_en_test": True,
            "extraction_max_par_heure_par_utilisateur": 2,
            "extraction_lot_max_par_heure_par_utilisateur": 1,
        }
    )
    app = creer_application(cfg)
    app.state.cle_maitresse = charger_ou_creer_cle_maitresse(cfg)
    app.state.moteur = application.state.moteur
    app.state.fabrique_sessions = application.state.fabrique_sessions
    app.dependency_overrides[obtenir_lecteur_document] = lambda: LecteurFactice()
    client, _ = connecter_client(app, deux_bureaux[0].employe.email)
    cid = _creer_candidat(client)
    did = _deposer(client, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE])

    unitaire = f"/api/v1/candidats/{cid}/documents/{did}/extraire"
    assert [client.post(unitaire).status_code for _ in range(3)] == [200, 200, 429]
    lot = f"/api/v1/candidats/{cid}/extractions/lot"
    assert [client.post(lot).status_code for _ in range(2)] == [200, 429]
    # Un autre utilisateur n'est pas pénalisé.
    autre, _ = connecter_client(app, deux_bureaux[0].admin.email)
    assert autre.post(unitaire).status_code == 200


# ===================================================================== B3 : révocation d'un agent


def test_b3_revoquer_un_agent_libere_ses_taches_en_cours_dans_la_meme_transaction(
    application: FastAPI,
    admin_a: Any,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
    fabrique_sessions: sessionmaker[Session],
) -> None:
    candidat_id, _, _ = creer_candidat_avec_voeux(admin_a)
    tache_id = creer_tache_pc(admin_a, candidat_id).json()["id"]
    id1, jeton1 = enroler_agent(admin_a, "PC-1")
    _, jeton2 = enroler_agent(admin_a, "PC-2")
    a1, a2 = client_agent(application, jeton1), client_agent(application, jeton2)
    assert a1.post("/api/v1/taches/reserver-suivante").json()["tache"]["id"] == tache_id

    assert admin_a.post(f"/api/v1/agents-locaux/{id1}/revoquer").status_code == 200
    tache = admin_a.get(f"/api/v1/taches/{tache_id}").json()
    assert tache["statut"] == "en_attente" and tache["agent_local_id"] is None

    from app.db.tenant import definir_tenant

    with fabrique_sessions() as db:
        definir_tenant(db, deux_bureaux[0].bureau.id)
        assert db.query(VerrouDossier).count() == 0  # le dossier n'est plus bloqué par l'agent révoqué
        assert db.get(TacheDossier, uuid.UUID(tache_id)).statut is StatutTache.EN_ATTENTE

    # Un autre agent la prend aussitôt, sans attendre l'expiration d'un verrou.
    assert a2.post("/api/v1/taches/reserver-suivante").json()["tache"]["id"] == tache_id


def test_b3_reactiver_un_agent_ne_touche_pas_aux_taches(application: FastAPI, admin_a: Any) -> None:
    candidat_id, _, _ = creer_candidat_avec_voeux(admin_a)
    tache_id = creer_tache_pc(admin_a, candidat_id).json()["id"]
    id1, jeton1 = enroler_agent(admin_a, "PC-1")
    a1 = client_agent(application, jeton1)
    a1.post("/api/v1/taches/reserver-suivante")
    assert admin_a.post(f"/api/v1/agents-locaux/{id1}/activer").status_code == 200
    assert admin_a.get(f"/api/v1/taches/{tache_id}").json()["statut"] == "en_cours"


# ===================================================================== B5 : extraction concurrente


def test_b5_conflit_d_unicite_d_une_extraction_concurrente_relit_au_lieu_d_echouer(
    application: FastAPI,
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application.dependency_overrides[obtenir_lecteur_document] = lambda: LecteurFactice()
    original = service_extractions._persister  # noqa: SLF001
    appels = {"n": 0}

    def concurrent(*args: Any, **kw: Any) -> None:
        appels["n"] += 1
        if appels["n"] == 1:  # une autre requête vient d'insérer les mêmes lignes
            raise IntegrityError("INSERT extractions_documents", {}, Exception("uq_extractions_documents_champ_par_document"))
        original(*args, **kw)

    monkeypatch.setattr(service_extractions, "_persister", concurrent)
    try:
        client, _ = connecter_client(application, deux_bureaux[0].employe.email)
        cid = _creer_candidat(client)
        did = _deposer(client, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE])
        resultat = _extraire(client, cid, did)  # 200, pas 500
        assert appels["n"] == 2
        assert _par_champ(resultat)["numero_passeport"]["valeur"] == "L898902C3"
    finally:
        application.dependency_overrides.pop(obtenir_lecteur_document, None)


# ===================================================================== B6 : URL d'image libérées


def test_b6_les_urls_d_objets_sont_revoquees() -> None:
    js = ecran.JS_REVUE
    assert "URL.revokeObjectURL" in js
    debut_actualiser = js.split("async function rxActualiser", 1)[1][:400]
    assert "rxLibererImages();" in debut_actualiser  # libérées à chaque rafraîchissement de la liste
