"""Service de gestion des candidats (CRUD chiffré, recherche par index aveugle, archivage).

Respect des règles non négociables :
- Règle 4 : aucun champ facultatif ne reçoit de valeur inventée.
- Règle 5 : aucune donnée personnelle dans les journaux ni dans le journal d'audit.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.chiffrement import (
    calculer_index_aveugle,
    chiffrer_champ,
    dechiffrer_champ,
)
from app.core.erreurs import Conflit, NonTrouve
from app.db.base import maintenant_utc
from app.db.tenant import tenant_courant
from app.modeles.abonnement import AbonnementBureau
from app.modeles.candidat import Candidat, StatutCandidat
from app.modeles.journal_audit import ResultatAudit
from app.schemas.candidat import CandidatCreation, CandidatModification, CandidatSortie
from app.services import audit


def _exiger_tenant(db: Session) -> uuid.UUID:
    tid = tenant_courant(db)
    if tid is None:
        raise RuntimeError("Contexte bureau (tenant) manquant sur la session.")
    return tid


def dechiffrer_candidat(c: Candidat, cle_maitresse: bytes) -> CandidatSortie:
    tid = c.tenant_id
    dn_str = dechiffrer_champ(
        cle_maitresse, tid, "date_naissance", c.date_naissance_chiffree
    )
    return CandidatSortie(
        id=c.id,
        nom=dechiffrer_champ(cle_maitresse, tid, "nom", c.nom_chiffre) or "",
        prenom=dechiffrer_champ(cle_maitresse, tid, "prenom", c.prenom_chiffre) or "",
        sexe=c.sexe,
        date_naissance=date.fromisoformat(dn_str) if dn_str else None,
        lieu_naissance=dechiffrer_champ(
            cle_maitresse, tid, "lieu_naissance", c.lieu_naissance_chiffre
        ),
        nationalite=c.nationalite,
        pays_residence=c.pays_residence,
        email=dechiffrer_champ(cle_maitresse, tid, "email", c.email_chiffre),
        telephone=dechiffrer_champ(
            cle_maitresse, tid, "telephone", c.telephone_chiffre
        ),
        numero_passeport=dechiffrer_champ(
            cle_maitresse, tid, "numero_passeport", c.numero_passeport_chiffre
        ),
        date_expiration_passeport=c.date_expiration_passeport,
        adresse=dechiffrer_champ(cle_maitresse, tid, "adresse", c.adresse_chiffree),
        niveau_actuel=c.niveau_actuel,
        programme_vise=c.programme_vise,
        etablissement_vise=c.etablissement_vise,
        fonds_disponibles_eur=c.fonds_disponibles_eur,
        notes_internes=dechiffrer_champ(
            cle_maitresse, tid, "notes_internes", c.notes_internes_chiffrees
        ),
        consentement_signe=c.consentement_signe,
        date_consentement=c.date_consentement,
        statut=c.statut,
        archive_le=c.archive_le,
        cree_le=c.cree_le,
        modifie_le=c.modifie_le,
    )


def obtenir_candidat_orm(db: Session, candidat_id: uuid.UUID) -> Candidat:
    c = db.scalar(select(Candidat).where(Candidat.id == candidat_id))
    if c is None:
        raise NonTrouve("Candidat introuvable.")
    return c


def obtenir_candidat(
    db: Session, *, candidat_id: uuid.UUID, cle_maitresse: bytes
) -> CandidatSortie:
    c = obtenir_candidat_orm(db, candidat_id)
    return dechiffrer_candidat(c, cle_maitresse)


def creer_candidat(
    db: Session,
    *,
    donnees: CandidatCreation,
    acteur_id: uuid.UUID,
    cle_maitresse: bytes,
) -> CandidatSortie:
    tid = _exiger_tenant(db)

    abo = db.scalar(select(AbonnementBureau).where(AbonnementBureau.tenant_id == tid))
    if abo is not None:
        nb_actifs = (
            db.scalar(
                select(func.count(Candidat.id)).where(
                    Candidat.statut == StatutCandidat.ACTIF
                )
            )
            or 0
        )
        if nb_actifs >= abo.quota_dossiers_mensuels:
            raise Conflit(
                f"Quota mensuel de dossiers atteint ({abo.quota_dossiers_mensuels}) pour votre forfait '{abo.forfait.value}'."
            )

    idx_nom = calculer_index_aveugle(cle_maitresse, tid, "nom", donnees.nom)
    idx_prenom = calculer_index_aveugle(cle_maitresse, tid, "prenom", donnees.prenom)
    assert idx_nom is not None and idx_prenom is not None

    idx_email = calculer_index_aveugle(cle_maitresse, tid, "email", donnees.email)
    idx_passeport = calculer_index_aveugle(
        cle_maitresse, tid, "passeport", donnees.numero_passeport
    )

    if idx_passeport is not None:
        existant = db.scalar(
            select(Candidat.id).where(Candidat.idx_passeport == idx_passeport)
        )
        if existant is not None:
            raise Conflit(
                "Un candidat avec ce numéro de passeport existe déjà dans ce bureau."
            )

    maintenant = maintenant_utc()
    c = Candidat(
        id=uuid.uuid4(),
        tenant_id=tid,
        nom_chiffre=chiffrer_champ(cle_maitresse, tid, "nom", donnees.nom) or "",
        prenom_chiffre=chiffrer_champ(cle_maitresse, tid, "prenom", donnees.prenom) or "",
        date_naissance_chiffree=chiffrer_champ(
            cle_maitresse,
            tid,
            "date_naissance",
            donnees.date_naissance.isoformat() if donnees.date_naissance else None,
        ),
        lieu_naissance_chiffre=chiffrer_champ(
            cle_maitresse, tid, "lieu_naissance", donnees.lieu_naissance
        ),
        email_chiffre=chiffrer_champ(cle_maitresse, tid, "email", donnees.email),
        telephone_chiffre=chiffrer_champ(
            cle_maitresse, tid, "telephone", donnees.telephone
        ),
        numero_passeport_chiffre=chiffrer_champ(
            cle_maitresse, tid, "numero_passeport", donnees.numero_passeport
        ),
        adresse_chiffree=chiffrer_champ(cle_maitresse, tid, "adresse", donnees.adresse),
        notes_internes_chiffrees=chiffrer_champ(
            cle_maitresse, tid, "notes_internes", donnees.notes_internes
        ),
        idx_nom=idx_nom,
        idx_prenom=idx_prenom,
        idx_email=idx_email,
        idx_passeport=idx_passeport,
        sexe=donnees.sexe,
        nationalite=donnees.nationalite,
        pays_residence=donnees.pays_residence,
        date_expiration_passeport=donnees.date_expiration_passeport,
        niveau_actuel=donnees.niveau_actuel,
        programme_vise=donnees.programme_vise,
        etablissement_vise=donnees.etablissement_vise,
        fonds_disponibles_eur=donnees.fonds_disponibles_eur,
        consentement_signe=donnees.consentement_signe,
        date_consentement=maintenant if donnees.consentement_signe else None,
        statut=StatutCandidat.ACTIF,
    )
    db.add(c)
    db.flush()

    audit.journaliser(
        db,
        "candidat.creation",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="candidat",
        ressource_id=c.id,
    )
    db.commit()
    return dechiffrer_candidat(c, cle_maitresse)


def lister_candidats(
    db: Session,
    *,
    cle_maitresse: bytes,
    page: int,
    taille: int,
    statut: StatutCandidat | None = StatutCandidat.ACTIF,
    recherche: str | None = None,
) -> tuple[list[CandidatSortie], int]:
    tid = _exiger_tenant(db)
    conditions = []
    if statut is not None:
        conditions.append(Candidat.statut == statut)

    if recherche and recherche.strip():
        terme = recherche.strip()
        mots = [m for m in terme.split() if m]
        # Recherche par index aveugle (nom, prénom, e-mail, passeport) sur le terme
        # complet et sur chaque mot (ex. "KACI Salim").
        idx_noms = {
            h
            for m in [terme, *mots]
            if (h := calculer_index_aveugle(cle_maitresse, tid, "nom", m))
        }
        idx_prenoms = {
            h
            for m in [terme, *mots]
            if (h := calculer_index_aveugle(cle_maitresse, tid, "prenom", m))
        }
        idx_email = calculer_index_aveugle(cle_maitresse, tid, "email", terme)
        idx_pass = calculer_index_aveugle(cle_maitresse, tid, "passeport", terme)

        clauses_idx = []
        if idx_noms:
            clauses_idx.append(Candidat.idx_nom.in_(idx_noms))
        if idx_prenoms:
            clauses_idx.append(Candidat.idx_prenom.in_(idx_prenoms))
        if idx_email:
            clauses_idx.append(Candidat.idx_email == idx_email)
        if idx_pass:
            clauses_idx.append(Candidat.idx_passeport == idx_pass)

        conditions_avec_idx = [*conditions, or_(*clauses_idx)]
        total = (
            db.scalar(select(func.count(Candidat.id)).where(*conditions_avec_idx))
            or 0
        )
        lignes = db.scalars(
            select(Candidat)
            .where(*conditions_avec_idx)
            .order_by(Candidat.cree_le.desc(), Candidat.id)
            .offset((page - 1) * taille)
            .limit(taille)
        ).all()
        return [dechiffrer_candidat(c, cle_maitresse) for c in lignes], total

    total = db.scalar(select(func.count(Candidat.id)).where(*conditions)) or 0
    lignes = db.scalars(
        select(Candidat)
        .where(*conditions)
        .order_by(Candidat.cree_le.desc(), Candidat.id)
        .offset((page - 1) * taille)
        .limit(taille)
    ).all()
    return [dechiffrer_candidat(c, cle_maitresse) for c in lignes], total


def modifier_candidat(
    db: Session,
    *,
    candidat_id: uuid.UUID,
    donnees: CandidatModification,
    acteur_id: uuid.UUID,
    cle_maitresse: bytes,
) -> CandidatSortie:
    tid = _exiger_tenant(db)
    c = obtenir_candidat_orm(db, candidat_id)
    champs_fournis = donnees.model_fields_set

    if "nom" in champs_fournis and donnees.nom is not None:
        c.nom_chiffre = chiffrer_champ(cle_maitresse, tid, "nom", donnees.nom) or ""
        c.idx_nom = calculer_index_aveugle(cle_maitresse, tid, "nom", donnees.nom) or ""

    if "prenom" in champs_fournis and donnees.prenom is not None:
        c.prenom_chiffre = (
            chiffrer_champ(cle_maitresse, tid, "prenom", donnees.prenom) or ""
        )
        c.idx_prenom = (
            calculer_index_aveugle(cle_maitresse, tid, "prenom", donnees.prenom) or ""
        )

    if "date_naissance" in champs_fournis:
        c.date_naissance_chiffree = chiffrer_champ(
            cle_maitresse,
            tid,
            "date_naissance",
            donnees.date_naissance.isoformat() if donnees.date_naissance else None,
        )

    if "lieu_naissance" in champs_fournis:
        c.lieu_naissance_chiffre = chiffrer_champ(
            cle_maitresse, tid, "lieu_naissance", donnees.lieu_naissance
        )

    if "email" in champs_fournis:
        c.email_chiffre = chiffrer_champ(cle_maitresse, tid, "email", donnees.email)
        c.idx_email = calculer_index_aveugle(cle_maitresse, tid, "email", donnees.email)

    if "telephone" in champs_fournis:
        c.telephone_chiffre = chiffrer_champ(
            cle_maitresse, tid, "telephone", donnees.telephone
        )

    if "numero_passeport" in champs_fournis:
        nouv_idx_pass = calculer_index_aveugle(
            cle_maitresse, tid, "passeport", donnees.numero_passeport
        )
        if nouv_idx_pass is not None and nouv_idx_pass != c.idx_passeport:
            conflit = db.scalar(
                select(Candidat.id).where(
                    Candidat.idx_passeport == nouv_idx_pass,
                    Candidat.id != c.id,
                )
            )
            if conflit is not None:
                raise Conflit(
                    "Un autre candidat possède déjà ce numéro de passeport dans ce bureau."
                )
        c.numero_passeport_chiffre = chiffrer_champ(
            cle_maitresse, tid, "numero_passeport", donnees.numero_passeport
        )
        c.idx_passeport = nouv_idx_pass

    if "adresse" in champs_fournis:
        c.adresse_chiffree = chiffrer_champ(
            cle_maitresse, tid, "adresse", donnees.adresse
        )

    if "notes_internes" in champs_fournis:
        c.notes_internes_chiffrees = chiffrer_champ(
            cle_maitresse, tid, "notes_internes", donnees.notes_internes
        )

    for attr_simple in (
        "sexe",
        "nationalite",
        "pays_residence",
        "date_expiration_passeport",
        "niveau_actuel",
        "programme_vise",
        "etablissement_vise",
        "fonds_disponibles_eur",
    ):
        if attr_simple in champs_fournis:
            setattr(c, attr_simple, getattr(donnees, attr_simple))

    if "consentement_signe" in champs_fournis and donnees.consentement_signe is not None:
        if donnees.consentement_signe and not c.consentement_signe:
            c.date_consentement = maintenant_utc()
        elif not donnees.consentement_signe:
            c.date_consentement = None
        c.consentement_signe = donnees.consentement_signe

    audit.journaliser(
        db,
        "candidat.modification",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="candidat",
        ressource_id=c.id,
        details={"nb_champs_modifies": len(champs_fournis)},
    )
    db.commit()
    return dechiffrer_candidat(c, cle_maitresse)


def changer_statut_archivage(
    db: Session,
    *,
    candidat_id: uuid.UUID,
    archiver: bool,
    acteur_id: uuid.UUID,
    cle_maitresse: bytes,
) -> CandidatSortie:
    c = obtenir_candidat_orm(db, candidat_id)
    if archiver:
        c.statut = StatutCandidat.ARCHIVE
        c.archive_le = maintenant_utc()
        action = "candidat.archivage"
    else:
        c.statut = StatutCandidat.ACTIF
        c.archive_le = None
        action = "candidat.restauration"

    audit.journaliser(
        db,
        action,
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="candidat",
        ressource_id=c.id,
    )
    db.commit()
    return dechiffrer_candidat(c, cle_maitresse)
