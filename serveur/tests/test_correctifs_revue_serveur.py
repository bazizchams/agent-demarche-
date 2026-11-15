"""Régressions de la revue de code (H1, M3, M4, M6, M8, BAS) : un test par défaut corrigé. Données synthétiques."""

from __future__ import annotations

from typing import Any

import pytest

from app.core.erreurs import ServiceIndisponible
from app.modeles.journal_audit import EntreeAudit
from app.db.tenant import definir_tenant
from app.services.llm import ReponseLLM, obtenir_client_llm_optionnel
from tests.test_deductions_projet_api import (  # noqa: F401 - fixture `ctx` réutilisée
    _confirmer_tout,
    _dossier_complet,
    _projet_modele_complet,
    ctx,
)


def _url(cid: str, suite: str = "") -> str:
    return f"/api/v1/candidats/{cid}/projet-professionnel{suite}"


def _projet_valide(c: dict) -> tuple[str, dict]:
    cid = _dossier_complet(c, "2025-12-01")
    _confirmer_tout(c, cid)
    p = _projet_modele_complet(c, cid)
    ok = c["client_a"].post(_url(cid, "/valider"), json={"version": p["version"]})
    assert ok.status_code == 200, ok.text
    return cid, ok.json()


# ------------------------------------------------------------------ H1
def test_h1_remplacer_un_projet_valide_exige_remplacer_valide(ctx: dict) -> None:
    cl = ctx["client_a"]
    cid, valide = _projet_valide(ctx)
    refus = cl.post(_url(cid, "/generer"), json={"remplacer": True})
    assert refus.status_code == 409
    lu = cl.get(_url(cid)).json()
    assert lu["statut"] == "valide" and lu["texte"] == valide["texte"] and lu["version"] == valide["version"]
    ok = cl.post(_url(cid, "/generer"), json={"remplacer": True, "remplacer_valide": True})
    assert ok.status_code == 200
    assert ok.json()["statut"] == "brouillon" and ok.json()["version"] == valide["version"] + 1


def test_h1_remplacer_un_brouillon_reste_possible_sans_remplacer_valide(ctx: dict) -> None:
    cl = ctx["client_a"]
    cid = _dossier_complet(ctx, "2025-12-01")
    assert cl.post(_url(cid, "/generer")).status_code == 200
    assert cl.post(_url(cid, "/generer"), json={"remplacer": True}).status_code == 200


# ------------------------------------------------------------------ M6
class _LLMAvecTokens:
    def generer(self, *, systeme: str, message: str, outil: Any = None, max_tokens: int = 0, images: Any = None) -> ReponseLLM:
        return ReponseLLM(texte="Je prépare un projet d'études en France.", tokens_entree=321, tokens_sortie=123)


class _LLMEnPanne:
    def generer(self, **_kw: Any) -> ReponseLLM:
        raise ServiceIndisponible("Le service d'IA ne répond pas.")


def _audits_ia(c: dict) -> list[EntreeAudit]:
    with c["app"].state.fabrique_sessions() as db:
        definir_tenant(db, c["a"].bureau.id)
        return [e for e in db.query(EntreeAudit) if e.action == "ia.appel"]


def test_m6_appel_ia_trace_avec_les_vrais_tokens(ctx: dict) -> None:
    ctx["app"].dependency_overrides[obtenir_client_llm_optionnel] = lambda: _LLMAvecTokens()
    cid = _dossier_complet(ctx, "2025-12-01")
    assert ctx["client_a"].post(_url(cid, "/generer")).status_code == 200
    audits = _audits_ia(ctx)
    assert len(audits) == 1
    assert audits[0].details["tokens_entree"] == 321 and audits[0].details["tokens_sortie"] == 123


def test_m6_echec_du_client_est_trace_et_consomme_le_quota(ctx: dict) -> None:
    ctx["app"].dependency_overrides[obtenir_client_llm_optionnel] = lambda: _LLMEnPanne()
    cid = _dossier_complet(ctx, "2025-12-01")
    rep = ctx["client_a"].post(_url(cid, "/generer"))
    assert rep.status_code == 503
    assert len(_audits_ia(ctx)) == 1


# ------------------------------------------------------------------ M3, M4, M8 (lecture des documents)
from app.core.erreurs import ServiceIndisponible as _Indispo  # noqa: E402
from app.services import extractions as service_extractions  # noqa: E402
from tests import corpus_synthetique as corpus  # noqa: E402
from tests.test_deductions_projet_api import EXTRAIT_MOY, _candidat, _document, _extraction  # noqa: E402
from tests.test_extractions_api import (  # noqa: E402, F401 - fixture `contexte` réutilisée
    LecteurFactice,
    _creer_candidat,
    _deposer,
    _extraire,
    contexte,
)


def _point_moyenne_confirme(c: dict) -> tuple[str, dict, dict]:
    """Moyenne validée par un humain (insérée en base : indépendant des parseurs de relevés), point fort
    calculé puis confirmé."""
    cl = c["client_a"]
    cid = _candidat(cl)
    did = _document(cl, cid, "releve_notes_bac")
    _extraction(c, cid, did, "moyenne_generale", "14.52", EXTRAIT_MOY)
    base = f"/api/v1/candidats/{cid}"
    moyenne = next(e for e in cl.get(f"{base}/extractions").json() if e["champ"] == "moyenne_generale")
    pts = cl.post(f"{base}/deductions/calculer").json()["points_forts"]
    assert len(pts) == 1
    assert cl.post(f"{base}/points-forts/{pts[0]['id']}/confirmer").status_code == 200
    return cid, moyenne, pts[0]


def _points(c: dict, cid: str) -> list[dict]:
    return c["client_a"].get(f"/api/v1/candidats/{cid}/points-forts").json()


def test_m3_rejeter_l_extraction_invalide_le_point_fort_confirme(ctx: dict) -> None:
    cid, moyenne, point = _point_moyenne_confirme(ctx)
    rep = ctx["client_a"].post(f"/api/v1/candidats/{cid}/extractions/{moyenne['id']}/rejeter")
    assert rep.status_code == 200
    apres = next(p for p in _points(ctx, cid) if p["id"] == point["id"])
    assert apres["statut"] == "rejete" and apres["alerte"] == "preuve_invalidee"


def test_m3_corriger_l_extraction_ne_laisse_pas_le_point_confirme_sur_l_ancienne_valeur(ctx: dict) -> None:
    cid, moyenne, point = _point_moyenne_confirme(ctx)
    rep = ctx["client_a"].post(
        f"/api/v1/candidats/{cid}/extractions/{moyenne['id']}/corriger", json={"valeur": "11,00"}
    )
    assert rep.status_code == 200
    pts = _points(ctx, cid)
    ancien = next(p for p in pts if p["id"] == point["id"])
    assert ancien["statut"] != "confirme"
    assert not any(p["statut"] == "confirme" and "14,52" in p["texte"] for p in pts)


def test_m4_valeur_corrigee_cite_la_correction_et_non_l_extrait_ocr_d_origine(ctx: dict) -> None:
    cid, moyenne, _ = _point_moyenne_confirme(ctx)
    cl = ctx["client_a"]
    cl.post(f"/api/v1/candidats/{cid}/extractions/{moyenne['id']}/corriger", json={"valeur": "11,00"})
    nouveau = next(p for p in _points(ctx, cid) if p["statut"] == "a_verifier" and p["regle"] == "moyenne_generale")
    assert "Moyenne générale : 14,52" not in nouveau["extrait"]
    assert nouveau["extrait"].startswith("Valeur corrigée par l'opérateur")


def test_m4_valider_apres_correction_garde_la_marque_corrige_humain(ctx: dict) -> None:
    cid, moyenne, _ = _point_moyenne_confirme(ctx)
    cl = ctx["client_a"]
    base = f"/api/v1/candidats/{cid}/extractions/{moyenne['id']}"
    assert cl.post(f"{base}/corriger", json={"valeur": "11,00"}).json()["motif"] == "corrige_humain"
    assert cl.post(f"{base}/valider").json()["motif"] == "corrige_humain"


class _LecteurOcrAbsentSurMarqueur(LecteurFactice):
    def lire_texte(self, contenu: bytes, type_mime: str) -> Any:
        if b"OCR-ABSENT" in contenu:
            raise _Indispo("La lecture par OCR n'est pas disponible : installez l'extra.")
        return super().lire_texte(contenu, type_mime)


def test_m8_lot_rapporte_l_ocr_absent_par_document_sans_abandonner_le_lot(contexte: dict) -> None:
    from app.api.v1.extractions import obtenir_lecteur_document

    contexte["app"].dependency_overrides[obtenir_lecteur_document] = lambda: _LecteurOcrAbsentSurMarqueur()
    cl = contexte["client_a"]
    cid = _creer_candidat(cl)
    mauvais = _deposer(cl, cid, "autre_piece", ["OCR-ABSENT"])
    _deposer(cl, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE])
    rep = cl.post(f"/api/v1/candidats/{cid}/extractions/lot")
    assert rep.status_code == 200, rep.text
    corps = rep.json()
    assert [e["document_id"] for e in corps["erreurs"]] == [mauvais]
    assert len(corps["documents"]) == 1
    assert any(e["champ"] == "numero_passeport" for e in cl.get(f"/api/v1/candidats/{cid}/extractions").json())


def test_m8_lot_recalcule_les_controles_une_seule_fois(contexte: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    appels: list[int] = []
    origine = service_extractions._recalculer_controles

    def _compte(*a: Any, **kw: Any) -> Any:
        appels.append(1)
        return origine(*a, **kw)

    monkeypatch.setattr(service_extractions, "_recalculer_controles", _compte)
    cl = contexte["client_a"]
    cid = _creer_candidat(cl)
    _deposer(cl, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE])
    _deposer(cl, cid, "autre_piece", ["Autre page sans valeur lisible."])
    _deposer(cl, cid, "autre_piece", ["Encore une page sans valeur lisible."])
    assert cl.post(f"/api/v1/candidats/{cid}/extractions/lot").status_code == 200
    assert len(appels) == 1


def test_bas_nb_mis_a_jour_ne_compte_que_les_points_reellement_modifies(ctx: dict) -> None:
    cid = _dossier_complet(ctx, "2025-12-01")
    cl = ctx["client_a"]
    premier = cl.post(f"/api/v1/candidats/{cid}/deductions/calculer").json()
    assert premier["nb_crees"] == 2 and premier["nb_mis_a_jour"] == 0
    second = cl.post(f"/api/v1/candidats/{cid}/deductions/calculer").json()
    assert second["nb_crees"] == 0 and second["nb_mis_a_jour"] == 0


def test_bas_second_refus_d_ecriture_n_est_pas_ignore(contexte: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import application_extractions as appli

    monkeypatch.setattr(appli, "_appliquer_modification", lambda *a, **kw: False)
    cl = contexte["client_a"]
    cid = _creer_candidat(cl)
    _extraire(cl, cid, _deposer(cl, cid, "passeport", [corpus.TEXTE_PASSEPORT_VALIDE]))
    base = f"/api/v1/candidats/{cid}/extractions"
    champs = {e["champ"]: e for e in cl.get(base).json()}
    for nom in ("numero_passeport", "date_naissance"):
        assert cl.post(f"{base}/{champs[nom]['id']}/valider").status_code == 200
    rapport = cl.post(f"{base}/appliquer").json()
    assert rapport["appliques"] == []
    assert {c["raison"] for c in rapport["conflits"]} == {"passeport_deja_utilise", "ecriture_impossible"}
    assert all(e["applique_le"] is None for e in cl.get(base).json())
