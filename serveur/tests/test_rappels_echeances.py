"""Envoi réel des rappels d'échéance : destinataires, idempotence, isolation, absence de PII.

Aucune donnée réelle : adresses, noms et démarches fictifs. Le transport « mémoire » ne fait
aucun envoi réseau.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import cli
from app.core.config import RACINE_SERVEUR, Environnement
from app.db.base import maintenant_utc
from app.db.session import creer_moteur
from app.db.tenant import definir_tenant, sans_filtre_tenant
from app.modeles.candidat import Candidat
from app.modeles.demarche_bureau import DemarcheBureau
from app.modeles.journal_audit import EntreeAudit
from app.modeles.rappel_echeance import RappelEcheanceEnvoye
from app.modeles.tache import StatutTache, TacheDossier
from app.services import courriels, rappels_echeances
from tests.conftest import DonneesBureauTest, connecter_client

CODE_DEMARCHE = "visa_rappel"
CODE_ECHEANCE = "limite"
NOM_CANDIDAT_SECRET = "ZZNOMSECRETZZ"
JOUR_J = date(2026, 12, 1)
AUJOURDHUI_6J = date(2026, 11, 25)  # 6 jours avant : seuils 30 et 7 dus
AUJOURDHUI_29J = date(2026, 11, 2)  # 29 jours avant : seuil 30 dû seulement
URL_RAPPELS = "/api/v1/demarches/rappels-echeances"

Bureaux = tuple[DonneesBureauTest, DonneesBureauTest]


class Collecteur(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@pytest.fixture(autouse=True)
def boite_vide():
    courriels.boite_memoire.vider()
    yield
    courriels.boite_memoire.vider()


@pytest.fixture()
def journaux():
    collecteur = Collecteur()
    racine = logging.getLogger("app")
    racine.addHandler(collecteur)
    try:
        yield collecteur
    finally:
        racine.removeHandler(collecteur)


def _definition(rappels: list[int] | None = None, jours_depuis_aujourdhui: int | None = None) -> dict:
    date_fixe = (
        (date.today() + timedelta(days=jours_depuis_aujourdhui)).isoformat()
        if jours_depuis_aujourdhui is not None
        else "2026-12-01"
    )
    echeance = {"code": CODE_ECHEANCE, "libelle": "Date limite de dépôt", "date_fixe": date_fixe}
    if rappels is not None:
        echeance["rappel_jours_avant"] = rappels
    return {"code": CODE_DEMARCHE, "libelle": "Visa de test", "echeances": [echeance]}


def _preparer_bureau(
    fabrique, donnees: DonneesBureauTest, *, statut=StatutTache.EN_COURS, verifier=True,
    definition: dict | None = None, avec_tache: bool = True,
) -> None:
    """Démarche du bureau + un candidat + une tâche ouverte ; adresses vérifiées."""
    with fabrique() as db:
        definir_tenant(db, donnees.bureau.id)
        db.add(DemarcheBureau(code=CODE_DEMARCHE, definition=definition or _definition()))
        if avec_tache:
            candidat = Candidat(
                nom_chiffre="x", prenom_chiffre="x", idx_nom=NOM_CANDIDAT_SECRET[:10],
                idx_prenom="p",
            )
            db.add(candidat)
            db.flush()
            db.add(TacheDossier(candidat_id=candidat.id, code_demarche=CODE_DEMARCHE, statut=statut))
        if verifier:
            for u in (donnees.admin, donnees.employe, donnees.lecteur):
                ligne = db.get(type(u), u.id)
                ligne.email_verifie_le = maintenant_utc()
        db.commit()


def _lancer(fabrique, donnees, parametres, aujourd_hui=AUJOURDHUI_6J, **kw):
    with fabrique() as db:
        definir_tenant(db, donnees.bureau.id)
        return rappels_echeances.envoyer_rappels_bureau(
            db, parametres, aujourd_hui=aujourd_hui, **kw
        )


def _enregistres(fabrique) -> list[RappelEcheanceEnvoye]:
    with fabrique() as db, sans_filtre_tenant(db):
        return list(db.scalars(select(RappelEcheanceEnvoye)))


def test_un_courriel_par_echeance_aux_destinataires_pertinents(
    fabrique_sessions, parametres_test, deux_bureaux: Bureaux
) -> None:
    a, _ = deux_bureaux
    _preparer_bureau(fabrique_sessions, a)

    resume = _lancer(fabrique_sessions, a, parametres_test)

    boite = courriels.boite_memoire.lister()
    # Admin + employé : UN courriel chacun (pas un par seuil) ; le lecteur est exclu.
    assert sorted(c.destinataire for c in boite) == sorted([a.admin.email, a.employe.email])
    assert all(c.type == "rappel_echeance" for c in boite)
    assert "Date limite de dépôt" in boite[0].texte
    assert "2026-12-01" in boite[0].texte
    assert "dans 6 jour(s)" in boite[0].texte
    assert resume.echeances_notifiees == 1
    assert resume.courriels_envoyes == 2
    assert sorted(r.seuil_jours for r in _enregistres(fabrique_sessions)) == [7, 30]


def test_destinataires_actifs_verifies_et_role_gestionnaire_seulement(
    fabrique_sessions, parametres_test, deux_bureaux: Bureaux
) -> None:
    a, _ = deux_bureaux
    _preparer_bureau(fabrique_sessions, a)
    with fabrique_sessions() as db:
        definir_tenant(db, a.bureau.id)
        db.get(type(a.employe), a.employe.id).actif = False
        db.commit()

    _lancer(fabrique_sessions, a, parametres_test)
    assert [c.destinataire for c in courriels.boite_memoire.lister()] == [a.admin.email]


def test_aucune_adresse_verifiee_aucun_envoi_et_rien_de_marque(
    fabrique_sessions, parametres_test, deux_bureaux: Bureaux
) -> None:
    a, _ = deux_bureaux
    _preparer_bureau(fabrique_sessions, a, verifier=False)

    resume = _lancer(fabrique_sessions, a, parametres_test)

    assert courriels.boite_memoire.lister() == []
    assert resume.sans_destinataire == 1
    assert _enregistres(fabrique_sessions) == []


def test_idempotence_pas_de_second_envoi(
    fabrique_sessions, parametres_test, deux_bureaux: Bureaux
) -> None:
    a, _ = deux_bureaux
    _preparer_bureau(fabrique_sessions, a)

    _lancer(fabrique_sessions, a, parametres_test)
    courriels.boite_memoire.vider()
    resume = _lancer(fabrique_sessions, a, parametres_test)

    assert courriels.boite_memoire.lister() == []
    assert resume.courriels_envoyes == 0
    assert resume.deja_envoyes == 1


def test_nouveau_seuil_franchi_declenche_un_nouvel_envoi(
    fabrique_sessions, parametres_test, deux_bureaux: Bureaux
) -> None:
    a, _ = deux_bureaux
    _preparer_bureau(fabrique_sessions, a)
    _lancer(fabrique_sessions, a, parametres_test, aujourd_hui=AUJOURDHUI_29J)
    assert sorted(r.seuil_jours for r in _enregistres(fabrique_sessions)) == [30]
    courriels.boite_memoire.vider()

    _lancer(fabrique_sessions, a, parametres_test, aujourd_hui=AUJOURDHUI_6J)

    assert len(courriels.boite_memoire.lister()) == 2
    assert sorted(r.seuil_jours for r in _enregistres(fabrique_sessions)) == [7, 30]


def test_pas_de_rappel_hors_fenetre_ni_sans_tache_ouverte(
    fabrique_sessions, parametres_test, deux_bureaux: Bureaux
) -> None:
    a, b = deux_bureaux
    _preparer_bureau(fabrique_sessions, a)
    _preparer_bureau(fabrique_sessions, b, statut=StatutTache.TERMINEE)

    # Trop tôt (100 jours avant) : aucun seuil dû.
    _lancer(fabrique_sessions, a, parametres_test, aujourd_hui=date(2026, 8, 23))
    # Échéance passée : aucun rappel.
    _lancer(fabrique_sessions, a, parametres_test, aujourd_hui=date(2026, 12, 2))
    # Tâche terminée : la démarche n'est pas « en cours ».
    _lancer(fabrique_sessions, b, parametres_test)

    assert courriels.boite_memoire.lister() == []
    assert _enregistres(fabrique_sessions) == []


def test_echeance_relative_sans_date_de_reference_n_est_pas_inventee(
    fabrique_sessions, parametres_test, deux_bureaux: Bureaux
) -> None:
    a, _ = deux_bureaux
    relative = {
        "code": CODE_DEMARCHE, "libelle": "Relative",
        "echeances": [
            {"code": "rel", "libelle": "Avant la rentrée", "reference": "rentree",
             "jours_avant_reference": 10},
        ],
    }
    _preparer_bureau(fabrique_sessions, a, definition=relative)

    _lancer(fabrique_sessions, a, parametres_test)
    assert courriels.boite_memoire.lister() == []

    _lancer(fabrique_sessions, a, parametres_test, date_rentree=date(2026, 12, 10))
    assert len(courriels.boite_memoire.lister()) == 2


def test_isolation_entre_bureaux(
    fabrique_sessions, parametres_test, deux_bureaux: Bureaux
) -> None:
    a, b = deux_bureaux
    _preparer_bureau(fabrique_sessions, a)
    # Le bureau B a des utilisateurs vérifiés mais aucune tâche ni démarche.
    _preparer_bureau(fabrique_sessions, b, avec_tache=False)

    _lancer(fabrique_sessions, a, parametres_test)
    destinataires = {c.destinataire for c in courriels.boite_memoire.lister()}
    assert destinataires == {a.admin.email, a.employe.email}

    courriels.boite_memoire.vider()
    _lancer(fabrique_sessions, b, parametres_test)
    assert courriels.boite_memoire.lister() == []
    assert {r.tenant_id for r in _enregistres(fabrique_sessions)} == {a.bureau.id}


def test_meme_code_dans_deux_bureaux_chacun_recoit_son_rappel(
    fabrique_sessions, parametres_test, deux_bureaux: Bureaux
) -> None:
    a, b = deux_bureaux
    _preparer_bureau(fabrique_sessions, a)
    _preparer_bureau(fabrique_sessions, b)

    _lancer(fabrique_sessions, a, parametres_test)
    _lancer(fabrique_sessions, b, parametres_test)

    assert len(courriels.boite_memoire.lister()) == 4
    assert {r.tenant_id for r in _enregistres(fabrique_sessions)} == {a.bureau.id, b.bureau.id}


def test_aucune_donnee_personnelle_dans_courriel_audit_et_journaux(
    fabrique_sessions, parametres_test, deux_bureaux: Bureaux, journaux: Collecteur
) -> None:
    a, _ = deux_bureaux
    _preparer_bureau(fabrique_sessions, a)

    _lancer(fabrique_sessions, a, parametres_test)

    for c in courriels.boite_memoire.lister():
        assert NOM_CANDIDAT_SECRET not in c.texte + c.html + c.sujet
    with fabrique_sessions() as db, sans_filtre_tenant(db):
        entrees = list(db.scalars(select(EntreeAudit).where(EntreeAudit.action.like("rappel%"))))
    assert entrees, "l'envoi doit être tracé dans l'audit"
    assert NOM_CANDIDAT_SECRET not in str([e.details for e in entrees])
    textes = " ".join(journaux.messages + [str(e.details) for e in entrees])
    for adresse in (a.admin.email, a.employe.email):
        assert adresse not in textes


def test_echec_d_envoi_ne_marque_rien_et_ne_leve_pas(
    fabrique_sessions, parametres_test, deux_bureaux: Bureaux, monkeypatch
) -> None:
    a, _ = deux_bureaux
    _preparer_bureau(fabrique_sessions, a)
    monkeypatch.setattr(rappels_echeances.courriels, "envoyer_courriel", lambda *_a, **_k: False)

    resume = _lancer(fabrique_sessions, a, parametres_test)

    assert resume.echecs == 1
    assert resume.courriels_envoyes == 0
    assert _enregistres(fabrique_sessions) == []

    # Quand le transport revient, le rappel part bien (rien n'avait été marqué).
    monkeypatch.undo()
    resume = _lancer(fabrique_sessions, a, parametres_test)
    assert resume.courriels_envoyes == 2
    assert len(_enregistres(fabrique_sessions)) == 2


def test_exception_du_transport_est_contenue(
    fabrique_sessions, parametres_test, deux_bureaux: Bureaux, monkeypatch
) -> None:
    a, _ = deux_bureaux
    _preparer_bureau(fabrique_sessions, a)

    def explose(*_a, **_k):
        raise RuntimeError("smtp en panne")

    monkeypatch.setattr(rappels_echeances.courriels, "envoyer_courriel", explose)
    resume = _lancer(fabrique_sessions, a, parametres_test)
    assert resume.echecs == 1
    assert _enregistres(fabrique_sessions) == []


def test_production_sans_smtp_n_envoie_rien_et_ne_marque_rien(
    fabrique_sessions, parametres_test, deux_bureaux: Bureaux
) -> None:
    a, _ = deux_bureaux
    _preparer_bureau(fabrique_sessions, a)
    prod = parametres_test.model_copy(update={"environnement": Environnement.PRODUCTION})
    assert prod.transport_courriel_effectif == "memoire"

    resume = _lancer(fabrique_sessions, a, prod)

    assert resume.echecs == 1
    assert courriels.boite_memoire.lister() == []
    assert _enregistres(fabrique_sessions) == []


def test_contrainte_d_unicite_en_base(
    fabrique_sessions, parametres_test, deux_bureaux: Bureaux
) -> None:
    a, _ = deux_bureaux

    def _ligne() -> RappelEcheanceEnvoye:
        return RappelEcheanceEnvoye(
            code_demarche="d", code_echeance="e", seuil_jours=7, date_echeance=JOUR_J
        )

    with fabrique_sessions() as db:
        definir_tenant(db, a.bureau.id)
        db.add(_ligne())
        db.commit()
        db.add(_ligne())
        with pytest.raises(IntegrityError):
            db.commit()


def test_tous_les_bureaux_actifs_sont_traites_chacun_avec_ses_donnees(
    fabrique_sessions, parametres_test, deux_bureaux: Bureaux
) -> None:
    a, b = deux_bureaux
    _preparer_bureau(fabrique_sessions, a)
    _preparer_bureau(fabrique_sessions, b)
    with fabrique_sessions() as db, sans_filtre_tenant(db):
        db.get(type(b.bureau), b.bureau.id).actif = False
        db.commit()

    resumes = rappels_echeances.envoyer_rappels_tous_bureaux(
        fabrique_sessions, parametres_test, aujourd_hui=AUJOURDHUI_6J
    )

    assert len(resumes) == 1
    assert {c.destinataire for c in courriels.boite_memoire.lister()} == {
        a.admin.email, a.employe.email,
    }


# --- Endpoint -----------------------------------------------------------------------------


def test_endpoint_administrateur_declenche_et_reste_idempotent(
    application: FastAPI, fabrique_sessions, deux_bureaux: Bureaux
) -> None:
    a, _ = deux_bureaux
    _preparer_bureau(fabrique_sessions, a, definition=_definition([30], 5))
    client, _ = connecter_client(application, a.admin.email)

    premiere = client.post(URL_RAPPELS)
    assert premiere.status_code == 200, premiere.text
    assert premiere.json()["courriels_envoyes"] == 2
    seconde = client.post(URL_RAPPELS)
    assert seconde.status_code == 200
    assert seconde.json()["courriels_envoyes"] == 0


def test_endpoint_refuse_employe_et_absence_de_csrf(
    application: FastAPI, fabrique_sessions, deux_bureaux: Bureaux
) -> None:
    a, _ = deux_bureaux
    _preparer_bureau(fabrique_sessions, a)
    employe, _ = connecter_client(application, a.employe.email)
    assert employe.post(URL_RAPPELS).status_code == 403

    admin, _ = connecter_client(application, a.admin.email)
    del admin.headers["X-CSRF-Token"]
    assert admin.post(URL_RAPPELS).status_code == 403
    assert courriels.boite_memoire.lister() == []


def test_endpoint_exige_authentification(application: FastAPI) -> None:
    from fastapi.testclient import TestClient

    assert TestClient(application).post(URL_RAPPELS).status_code in (401, 403)


def test_endpoint_n_atteint_que_le_bureau_de_l_appelant(
    application: FastAPI, fabrique_sessions, deux_bureaux: Bureaux
) -> None:
    a, b = deux_bureaux
    _preparer_bureau(fabrique_sessions, a, definition=_definition([30], 5))
    _preparer_bureau(fabrique_sessions, b, definition=_definition([30], 5))
    client_b, _ = connecter_client(application, b.admin.email)

    assert client_b.post(URL_RAPPELS).status_code == 200

    destinataires = {c.destinataire for c in courriels.boite_memoire.lister()}
    assert destinataires <= {b.admin.email, b.employe.email}
    assert {r.tenant_id for r in _enregistres(fabrique_sessions)} <= {b.bureau.id}


# --- Commande CLI -------------------------------------------------------------------------


def test_cli_envoie_pour_tous_les_bureaux_et_est_idempotente(
    fabrique_sessions, parametres_test, deux_bureaux: Bureaux, monkeypatch, capsys
) -> None:
    a, _ = deux_bureaux
    _preparer_bureau(fabrique_sessions, a, definition=_definition([100000]))
    monkeypatch.setattr(cli, "obtenir_parametres", lambda: parametres_test)

    assert cli.main(["envoyer-rappels-echeances", "--date", "2026-11-25"]) == 0
    sortie = capsys.readouterr().out
    assert "courriels_envoyes=2" in sortie
    assert cli.main(["envoyer-rappels-echeances", "--date", "2026-11-25"]) == 0
    assert "courriels_envoyes=0" in capsys.readouterr().out
    assert a.admin.email not in sortie


def test_cli_slug_inconnu_et_date_invalide(
    parametres_test, deux_bureaux: Bureaux, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(cli, "obtenir_parametres", lambda: parametres_test)
    assert cli.main(["envoyer-rappels-echeances", "--slug", "inconnu"]) == 1
    assert cli.main(["envoyer-rappels-echeances", "--date", "pas-une-date"]) == 2
    capsys.readouterr()


def test_cli_code_retour_1_si_un_envoi_echoue(
    fabrique_sessions, parametres_test, deux_bureaux: Bureaux, monkeypatch
) -> None:
    a, _ = deux_bureaux
    _preparer_bureau(fabrique_sessions, a)
    monkeypatch.setattr(cli, "obtenir_parametres", lambda: parametres_test)
    monkeypatch.setattr(rappels_echeances.courriels, "envoyer_courriel", lambda *_a, **_k: False)
    assert cli.main(["envoyer-rappels-echeances", "--date", "2026-11-25", "--slug", "bureau-alpha"]) == 1


# --- Migration ----------------------------------------------------------------------------


def _config(url: str) -> Config:
    cfg = Config(str(RACINE_SERVEUR / "alembic.ini"))
    cfg.set_main_option("script_location", str(RACINE_SERVEUR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_migration_cree_la_table_avec_contrainte_unique_sur_sqlite(tmp_path) -> None:
    from sqlalchemy import inspect

    url = f"sqlite:///{(tmp_path / 'm.db').as_posix()}"
    cfg = _config(url)
    command.upgrade(cfg, "head")
    moteur = creer_moteur(url)
    try:
        inspecteur = inspect(moteur)
        assert "rappels_echeances_envoyes" in inspecteur.get_table_names()
        uniques = inspecteur.get_unique_constraints("rappels_echeances_envoyes")
        assert any(
            set(u["column_names"])
            == {"tenant_id", "code_demarche", "code_echeance", "seuil_jours", "date_echeance"}
            for u in uniques
        )
    finally:
        moteur.dispose()
    command.downgrade(cfg, "0010_jetons_courriel")
    moteur = creer_moteur(url)
    try:
        assert "rappels_echeances_envoyes" not in inspect(moteur).get_table_names()
    finally:
        moteur.dispose()
    command.upgrade(cfg, "head")


def test_ddl_postgresql_genere_sans_erreur(capsys) -> None:
    """Mode hors-ligne : le SQL PostgreSQL de la migration se génère (aucune connexion)."""
    cfg = _config("postgresql+psycopg://u:p@localhost/db")
    command.upgrade(cfg, "0010_jetons_courriel:0011_rappels_echeances_envoyes", sql=True)
    sql = capsys.readouterr().out
    assert "CREATE TABLE rappels_echeances_envoyes" in sql
    assert "UNIQUE (tenant_id, code_demarche, code_echeance, seuil_jours, date_echeance)" in sql


def test_execution_concurrente_deja_inscrite_n_envoie_rien(
    fabrique_sessions, parametres_test, deux_bureaux: Bureaux, monkeypatch
) -> None:
    a, _ = deux_bureaux
    _preparer_bureau(fabrique_sessions, a)
    _lancer(fabrique_sessions, a, parametres_test)
    courriels.boite_memoire.vider()
    # Simule une autre exécution qui a inscrit les seuils entre la lecture et la réservation.
    monkeypatch.setattr(rappels_echeances, "_seuils_deja_envoyes", lambda *_a, **_k: set())

    resume = _lancer(fabrique_sessions, a, parametres_test)

    assert courriels.boite_memoire.lister() == []
    assert resume.deja_envoyes == 1
    assert len(_enregistres(fabrique_sessions)) == 2
