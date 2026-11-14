"""Tests d'isolation multi-bureaux (ORM et API HTTP) et d'immuabilité de l'audit.

Exigence d'architecture : un bureau ne peut JAMAIS lire, modifier ni supprimer les
données d'un autre bureau, ni deviner leur existence.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.securite import hacher_mot_de_passe
from app.db.base import Base, MixinTenant
from app.db.tenant import (
    ContexteTenantManquant,
    ViolationTenant,
    definir_tenant,
    sans_filtre_tenant,
)
from app.modeles.journal_audit import (
    EntreeAudit,
    JournalAuditImmuable,
    ResultatAudit,
)
from app.modeles.utilisateur import Role, Utilisateur
from tests.conftest import (
    MOT_DE_PASSE_FORT,
    MOT_DE_PASSE_NOUVEAU,
    DonneesBureauTest,
    connecter_client,
)


def test_toutes_les_tables_metier_portent_tenant_id() -> None:
    """Garde-fou d'architecture : toute nouvelle table ajoutée dans les phases suivantes
    DOIT hériter de MixinTenant et posséder une colonne `tenant_id` non nulle."""
    tables_sans_tenant_autorisees = {"bureaux"}
    for nom_table, table in Base.metadata.tables.items():
        if nom_table in tables_sans_tenant_autorisees:
            continue
        assert "tenant_id" in table.c, (
            f"La table '{nom_table}' ne possède pas de colonne tenant_id."
        )
        colonne = table.c["tenant_id"]
        assert not colonne.nullable, (
            f"La colonne '{nom_table}.tenant_id' doit être NOT NULL."
        )
        cibles_fk = {fk.target_fullname for fk in colonne.foreign_keys}
        assert "bureaux.id" in cibles_fk, (
            f"'{nom_table}.tenant_id' doit référencer 'bureaux.id'."
        )

    for mapper in Base.registry.mappers:
        cls = mapper.class_
        if cls.__tablename__ in tables_sans_tenant_autorisees:
            continue
        assert issubclass(cls, MixinTenant), (
            f"Le modèle {cls.__name__} doit hériter de MixinTenant."
        )


def test_requete_orm_sans_tenant_est_refusee(
    fabrique_sessions: sessionmaker[Session],
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    bureau_a, _ = deux_bureaux
    with fabrique_sessions() as db:
        with pytest.raises(ContexteTenantManquant):
            db.scalars(select(Utilisateur)).all()

        with pytest.raises(ContexteTenantManquant):
            db.execute(
                update(Utilisateur)
                .where(Utilisateur.id == bureau_a.admin.id)
                .values(nom_affiche="Pirate")
            )

        with pytest.raises(ContexteTenantManquant):
            db.execute(
                delete(Utilisateur).where(Utilisateur.id == bureau_a.admin.id)
            )

        with pytest.raises(ContexteTenantManquant):
            db.add(
                Utilisateur(
                    tenant_id=bureau_a.bureau.id,
                    email="intrus@fictif.invalid",
                    nom_affiche="Intrus",
                    empreinte_mot_de_passe=hacher_mot_de_passe(MOT_DE_PASSE_FORT),
                    role=Role.EMPLOYE,
                )
            )
            db.flush()


def test_isolation_orm_lecture_et_ecriture_entre_bureaux(
    fabrique_sessions: sessionmaker[Session],
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    donnees_a, donnees_b = deux_bureaux

    with fabrique_sessions() as db_a:
        definir_tenant(db_a, donnees_a.bureau.id)

        # Lecture : seuls les membres du bureau A sont visibles.
        ids_visibles = set(db_a.scalars(select(Utilisateur.id)).all())
        assert ids_visibles == {
            donnees_a.admin.id,
            donnees_a.employe.id,
            donnees_a.lecteur.id,
        }

        # Même par identifiant exact, un utilisateur du bureau B est invisible.
        assert (
            db_a.scalar(
                select(Utilisateur).where(Utilisateur.id == donnees_b.admin.id)
            )
            is None
        )
        assert db_a.get(Utilisateur, donnees_b.admin.id) is None

        # UPDATE / DELETE ciblant l'identifiant du bureau B n'affectent aucune ligne.
        res_upd = db_a.execute(
            update(Utilisateur)
            .where(Utilisateur.id == donnees_b.admin.id)
            .values(nom_affiche="Modifié depuis A")
        )
        assert res_upd.rowcount == 0

        res_del = db_a.execute(
            delete(Utilisateur).where(Utilisateur.id == donnees_b.employe.id)
        )
        assert res_del.rowcount == 0

        # Impossible de changer le bureau d'une session SQLAlchemy déjà ouverte.
        with pytest.raises(ViolationTenant):
            definir_tenant(db_a, donnees_b.bureau.id)

        # Impossible de créer une ligne en forçant le tenant_id du bureau B.
        db_a.add(
            Utilisateur(
                tenant_id=donnees_b.bureau.id,
                email="cheval.troie@fictif.invalid",
                nom_affiche="Cheval",
                empreinte_mot_de_passe=hacher_mot_de_passe(MOT_DE_PASSE_FORT),
                role=Role.EMPLOYE,
            )
        )
        with pytest.raises(ViolationTenant):
            db_a.flush()
        db_a.rollback()

        # Impossible de déplacer un utilisateur existant du bureau A vers le bureau B.
        u_a = db_a.scalar(
            select(Utilisateur).where(Utilisateur.id == donnees_a.employe.id)
        )
        assert u_a is not None
        u_a.tenant_id = donnees_b.bureau.id
        with pytest.raises(ViolationTenant):
            db_a.flush()
        db_a.rollback()


def test_journal_audit_est_immuable(
    fabrique_sessions: sessionmaker[Session],
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    donnees_a, _ = deux_bureaux
    with fabrique_sessions() as db:
        definir_tenant(db, donnees_a.bureau.id)
        entree = db.scalar(select(EntreeAudit))
        assert entree is not None

        entree.action = "trace.falsifiee"
        with pytest.raises(JournalAuditImmuable):
            db.flush()
        db.rollback()

        entree = db.scalar(select(EntreeAudit))
        assert entree is not None
        db.delete(entree)
        with pytest.raises(JournalAuditImmuable):
            db.flush()
        db.rollback()

        with pytest.raises(JournalAuditImmuable):
            db.execute(
                update(EntreeAudit).values(resultat=ResultatAudit.ECHEC)
            )

        with pytest.raises(JournalAuditImmuable):
            db.execute(delete(EntreeAudit))


def test_isolation_api_http_complete_entre_bureau_a_et_bureau_b(
    application: FastAPI,
    fabrique_sessions: sessionmaker[Session],
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
) -> None:
    donnees_a, donnees_b = deux_bureaux
    client_a, _ = connecter_client(application, donnees_a.admin.email)

    # 1. Liste des utilisateurs : uniquement ceux du bureau A.
    rep_liste = client_a.get("/api/v1/utilisateurs")
    assert rep_liste.status_code == 200
    emails_vus = {u["email"] for u in rep_liste.json()["elements"]}
    assert emails_vus == {
        donnees_a.admin.email,
        donnees_a.employe.email,
        donnees_a.lecteur.email,
    }

    # 2. Lecture directe d'un utilisateur du bureau B -> 404 (pas 403).
    for cible_b in (donnees_b.admin, donnees_b.employe, donnees_b.lecteur):
        rep_detail = client_a.get(f"/api/v1/utilisateurs/{cible_b.id}")
        assert rep_detail.status_code == 404

    # 3. Modification d'un utilisateur du bureau B -> 404 et aucune modification en base.
    rep_patch = client_a.patch(
        f"/api/v1/utilisateurs/{donnees_b.employe.id}",
        json={"nom_affiche": "Sabotage", "actif": False},
    )
    assert rep_patch.status_code == 404

    # 4. Réinitialisation du mot de passe d'un utilisateur du bureau B -> 404.
    rep_reinit = client_a.post(
        f"/api/v1/utilisateurs/{donnees_b.employe.id}/reinitialiser-mot-de-passe",
        json={"mot_de_passe_temporaire": MOT_DE_PASSE_NOUVEAU},
    )
    assert rep_reinit.status_code == 404

    # 5. Tentative d'injection de `tenant_id` lors de la création -> 422 (champ interdit).
    rep_injection = client_a.post(
        "/api/v1/utilisateurs",
        json={
            "email": "injecte@bureau-fictif.dz",
            "nom_affiche": "Injecté",
            "role": "employe",
            "mot_de_passe_temporaire": MOT_DE_PASSE_NOUVEAU,
            "tenant_id": str(donnees_b.bureau.id),
        },
    )
    assert rep_injection.status_code == 422

    # 6. Le journal d'audit vu par A ne contient aucun événement ni acteur du bureau B.
    rep_audit = client_a.get("/api/v1/audit")
    assert rep_audit.status_code == 200
    acteurs_b = {
        str(donnees_b.admin.id),
        str(donnees_b.employe.id),
        str(donnees_b.lecteur.id),
    }
    for entree in rep_audit.json()["elements"]:
        assert entree["acteur_id"] not in acteurs_b
        assert entree["ressource_id"] != str(donnees_b.bureau.id)

    # 7. Renommer son bureau ne modifie que le bureau A.
    rep_bureau = client_a.patch("/api/v1/bureau", json={"nom": "Bureau Alpha Renommé"})
    assert rep_bureau.status_code == 200

    with fabrique_sessions() as db, sans_filtre_tenant(db):
        employe_b_intact = db.get(Utilisateur, donnees_b.employe.id)
        assert employe_b_intact is not None
        assert employe_b_intact.nom_affiche == "Employé Beta"
        assert employe_b_intact.actif is True
        bureau_b_intact = db.get(type(donnees_b.bureau), donnees_b.bureau.id)
        assert bureau_b_intact is not None
        assert bureau_b_intact.nom == "Bureau Beta Fictif"


def test_extractions_documents_isolees_entre_bureaux_orm(
    fabrique_sessions: sessionmaker[Session],
    deux_bureaux: tuple[DonneesBureauTest, DonneesBureauTest],
    application: FastAPI,
) -> None:
    """Lecture des documents : une extraction du bureau A est invisible, non modifiable et non
    supprimable depuis le bureau B ; une création pour un autre bureau est refusée."""
    import uuid

    from app.core.chiffrement import chiffrer_champ
    from app.modeles.extraction_document import ExtractionDocument, StatutExtraction
    from app.services.candidats import creer_candidat
    from app.schemas.candidat import CandidatCreation
    from app.services.documents import deposer_document
    from tests import corpus_synthetique as corpus

    donnees_a, donnees_b = deux_bureaux
    cle = application.state.cle_maitresse
    parametres = application.dependency_overrides[
        __import__("app.core.config", fromlist=["obtenir_parametres"]).obtenir_parametres
    ]()
    with fabrique_sessions() as db_a:
        definir_tenant(db_a, donnees_a.bureau.id)
        cand = creer_candidat(
            db_a, donnees=CandidatCreation(nom="Test", prenom="Isolation"),
            acteur_id=donnees_a.admin.id, cle_maitresse=cle,
        )
        doc = deposer_document(
            db_a, candidat_id=cand.id, type_piece="passeport", nom_fichier_origine="p.pdf",
            contenu_clair=corpus.pdf_factice(["x"]), date_expiration=None,
            acteur_id=donnees_a.admin.id, parametres=parametres, cle_maitresse=cle,
        )
        extraction = ExtractionDocument(
            id=uuid.uuid4(), tenant_id=donnees_a.bureau.id, document_id=doc.id, candidat_id=cand.id,
            champ="nom", valeur_chiffree=chiffrer_champ(cle, donnees_a.bureau.id, "extraction_valeur", "X") or "",
            extrait_chiffre=chiffrer_champ(cle, donnees_a.bureau.id, "extraction_extrait", "X") or "",
            source="A", confiance=0.5, statut=StatutExtraction.A_VERIFIER,
        )
        db_a.add(extraction)
        db_a.commit()
        extraction_id = extraction.id
        assert db_a.scalar(select(ExtractionDocument.id)) == extraction_id

    with fabrique_sessions() as db_b:
        definir_tenant(db_b, donnees_b.bureau.id)
        assert db_b.scalars(select(ExtractionDocument)).all() == []
        assert db_b.get(ExtractionDocument, extraction_id) is None
        res_upd = db_b.execute(
            update(ExtractionDocument)
            .where(ExtractionDocument.id == extraction_id)
            .values(statut=StatutExtraction.VALIDE_HUMAIN)
        )
        assert res_upd.rowcount == 0
        assert db_b.execute(delete(ExtractionDocument).where(ExtractionDocument.id == extraction_id)).rowcount == 0
        with pytest.raises(ViolationTenant):
            db_b.add(
                ExtractionDocument(
                    id=uuid.uuid4(), tenant_id=donnees_a.bureau.id, document_id=doc.id, candidat_id=cand.id,
                    champ="prenom", valeur_chiffree="v1:x", extrait_chiffre="v1:x", source="A",
                    confiance=0.1, statut=StatutExtraction.REJETE,
                )
            )
            db_b.flush()
        db_b.rollback()

    with fabrique_sessions() as db_a2:
        definir_tenant(db_a2, donnees_a.bureau.id)
        intacte = db_a2.get(ExtractionDocument, extraction_id)
        assert intacte is not None and intacte.statut is StatutExtraction.A_VERIFIER
