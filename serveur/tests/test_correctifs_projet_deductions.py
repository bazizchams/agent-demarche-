"""Régressions de la revue de sécurité : verrou de version (TOCTOU), point fort confirmé jamais réécrit
en silence, validité du certificat recalculée à l'usage, courses d'unicité -> Conflit 409."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.core.chiffrement import chiffrer_champ
from app.core.erreurs import Conflit, DonneesInvalides
from app.db.tenant import definir_tenant
from app.modeles.extraction_document import ExtractionDocument
from app.modeles.point_fort import PointFort, ProjetProfessionnel, StatutPointFort, StatutProjet
from app.services import deductions_dossier as ded
from app.services import projet_professionnel as pp
from tests.test_deductions_projet_api import (
    _calculer, _candidat, _confirmer_tout, _dossier_complet, _projet_modele_complet, ctx,  # noqa: F401
)


def _session(c: dict):
    db = c["app"].state.fabrique_sessions()
    definir_tenant(db, c["a"].bureau.id)
    return db


def _acteur(c: dict) -> uuid.UUID:
    return c["a"].employe.id


def _course_unique(monkeypatch: pytest.MonkeyPatch, db) -> None:
    def echec() -> None:
        raise IntegrityError("INSERT", {}, Exception("unique"))
    monkeypatch.setattr(db, "commit", echec)


# ---------------------------------------------------------------- 1. TOCTOU
def _projet_valide_sans_version_perdue(c: dict) -> tuple[str, int]:
    cid = _dossier_complet(c, "2025-12-01")
    _confirmer_tout(c, cid)
    p = _projet_modele_complet(c, cid)
    return cid, p["version"]


def _modifier_en_parallele(c: dict, cid: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Après le contrôle de version, une autre session modifie le projet (texte non contrôlé)."""
    reel = pp._exiger_version

    def piege(p, version):
        reel(p, version)
        with _session(c) as autre:
            autre.execute(update(ProjetProfessionnel).where(ProjetProfessionnel.id == p.id).values(version=p.version + 1))
            autre.commit()
    monkeypatch.setattr(pp, "_exiger_version", piege)


def test_valider_refuse_si_le_projet_change_apres_le_controle(ctx: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    cid, version = _projet_valide_sans_version_perdue(ctx)
    _modifier_en_parallele(ctx, cid, monkeypatch)
    with _session(ctx) as db, pytest.raises(Conflit):
        pp.valider_projet(db, candidat_id=uuid.UUID(cid), version=version, acteur_id=_acteur(ctx),
                          cle_maitresse=ctx["app"].state.cle_maitresse)
    with _session(ctx) as db:
        assert db.scalar(select(ProjetProfessionnel)).statut is StatutProjet.BROUILLON


def test_modifier_refuse_si_le_projet_change_apres_le_controle(ctx: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    cid, version = _projet_valide_sans_version_perdue(ctx)
    _modifier_en_parallele(ctx, cid, monkeypatch)
    with _session(ctx) as db, pytest.raises(Conflit):
        pp.modifier_projet(db, candidat_id=uuid.UUID(cid), texte="autre", version=version, acteur_id=_acteur(ctx),
                           cle_maitresse=ctx["app"].state.cle_maitresse)


# ---------------------------------------------------------------- 2. point confirmé jamais réécrit
def test_point_confirme_dont_l_extrait_change_repasse_a_verifier(ctx: dict) -> None:
    cid = _dossier_complet(ctx, "2025-12-01")
    _confirmer_tout(ctx, cid)
    app = ctx["app"]
    with _session(ctx) as db:
        e = db.scalar(select(ExtractionDocument).where(ExtractionDocument.champ == "niveau_francais"))
        e.extrait_chiffre = chiffrer_champ(app.state.cle_maitresse, e.tenant_id, "extraction_extrait", "Niveau obtenu : B2 (relu)")
        db.commit()
    pts = _calculer(ctx, cid)["points_forts"]
    langue = next(p for p in pts if p["regle"] == "certificat_langue")
    assert langue["statut"] == "a_verifier" and langue["extrait"].endswith("(relu)")
    assert next(p for p in pts if p["regle"] == "moyenne_generale")["statut"] == "confirme"


# ---------------------------------------------------------------- 3. validité à l'usage
def _langue_confirmee_valable_hier(c: dict) -> str:
    """Point confirmé alors que le TCF était valable (référence passée) ; aujourd'hui il est expiré."""
    cid = _dossier_complet(c, "2024-01-15")
    with _session(c) as db:
        ded.calculer_points_forts(db, candidat_id=uuid.UUID(cid), acteur_id=_acteur(c),
                                  cle_maitresse=c["app"].state.cle_maitresse, date_reference=date(2024, 6, 1))
        for p in db.scalars(select(PointFort)):
            p.statut = StatutPointFort.CONFIRME
            assert p.alerte is None or p.regle != "certificat_langue"
        db.commit()
    return cid


def test_projet_ecarte_un_certificat_expire_meme_si_l_alerte_stockee_est_vide(ctx: dict) -> None:
    cid = _langue_confirmee_valable_hier(ctx)
    with _session(ctx) as db:
        _, _, utilises, ecartes = pp.construire_faits(db, uuid.UUID(cid), ctx["app"].state.cle_maitresse)
    assert ecartes == 1 and utilises == 1


def test_appliquer_niveau_refuse_un_certificat_expire_meme_si_l_alerte_stockee_est_vide(ctx: dict) -> None:
    cid = _langue_confirmee_valable_hier(ctx)
    with _session(ctx) as db:
        pf = db.scalar(select(PointFort).where(PointFort.regle == "certificat_langue"))
        with pytest.raises(DonneesInvalides):
            ded.appliquer_niveau_a_fiche(db, candidat_id=uuid.UUID(cid), point_id=pf.id, acteur_id=_acteur(ctx),
                                         cle_maitresse=ctx["app"].state.cle_maitresse)


# ---------------------------------------------------------------- 4. courses d'unicité
def test_calculer_en_course_donne_un_conflit(ctx: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    cid = _dossier_complet(ctx, "2025-12-01")
    with _session(ctx) as db:
        _course_unique(monkeypatch, db)
        with pytest.raises(Conflit):
            ded.calculer_points_forts(db, candidat_id=uuid.UUID(cid), acteur_id=_acteur(ctx),
                                      cle_maitresse=ctx["app"].state.cle_maitresse)


def test_generer_en_course_donne_un_conflit(ctx: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    cid = _candidat(ctx["client_a"])
    with _session(ctx) as db:
        _course_unique(monkeypatch, db)
        with pytest.raises(Conflit):
            pp.generer_projet(db, None, candidat_id=uuid.UUID(cid), acteur_id=_acteur(ctx),
                              cle_maitresse=ctx["app"].state.cle_maitresse)


def test_enregistrer_fiches_en_course_donne_un_conflit(ctx: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import catalogue_formations as cat
    from app.services.fiche_formation import FicheEntree
    fiche = FicheEntree(etablissement="U", intitule="M", niveau_entree_bac_plus=4, date_releve=date(2026, 11, 1), source="manuel")
    with _session(ctx) as db:
        _course_unique(monkeypatch, db)
        with pytest.raises(Conflit):
            cat.enregistrer_fiches(db, [fiche], acteur_id=_acteur(ctx))
