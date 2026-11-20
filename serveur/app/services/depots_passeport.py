"""Dépôt d'un passeport SANS fiche : lecture de la MRZ, propositions, confirmation humaine, création de la fiche.

Garanties (règles 1, 4 et 5) :
- une proposition n'est JAMAIS une fiche : le candidat n'est créé qu'avec les valeurs que l'humain
  confirme ou corrige explicitement (`confirme=True`) ;
- une MRZ dont un chiffre de contrôle est faux (ou introuvable) ne produit AUCUNE proposition :
  la saisie manuelle est proposée, rien n'est deviné ;
- fichier et propositions sont chiffrés (clé du bureau) ; l'audit ne contient que des identifiants et des codes ;
- un dépôt non converti est purgé après 24 h (fichier et ligne) ;
- un numéro de passeport déjà présent dans le bureau bloque la création (conflit avec renvoi à la fiche).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.chiffrement import (
    calculer_empreinte_document,
    calculer_index_aveugle,
    chiffrer_champ,
    chiffrer_octets,
    dechiffrer_champ,
    dechiffrer_octets,
    normaliser_pour_index,
)
from app.core.config import Parametres
from app.core.erreurs import Conflit, DonneesInvalides, NonTrouve, ServiceIndisponible
from app.db.base import maintenant_utc
from app.db.tenant import sans_filtre_tenant, tenant_courant
from app.modeles.candidat import Candidat
from app.modeles.depot_passeport import STATUT_PROPOSE, STATUT_SAISIE_MANUELLE, DepotPasseport
from app.modeles.extraction_document import ExtractionDocument
from app.modeles.journal_audit import ResultatAudit
from app.schemas.candidat import CandidatCreation
from app.schemas.depot_passeport import (
    CreationFicheEntree,
    DepotPasseportSortie,
    FicheCreeeSortie,
    PropositionSortie,
)
from app.services import audit
from app.services.candidats import creer_candidat
from app.services.documents import (
    _detecter_type_mime_par_signature,
    _normaliser_nom_fichier,
    _resoudre_chemin_stockage,
    deposer_document,
)
from app.services.extraction_champs import (
    DATE_EXPIRATION_PASSEPORT,
    DATE_NAISSANCE,
    NATIONALITE_CODE,
    NOM,
    NUMERO_PASSEPORT,
    PRENOM,
    SEXE,
    ChampLu,
    extraire_champs,
    normaliser_valeur,
    valeur_valide,
)
from app.services.extractions import decider_extraction, lancer_extraction_document, lister_extractions
from app.services.lecture_documents import LecteurDocument

DUREE_CONSERVATION_HEURES = 24
TYPE_PIECE_PASSEPORT = "passeport"
STATUT_PROPOSITION = "a_confirmer"
_AAD_NOM, _AAD_PROPOSITIONS = "depot_passeport_nom", "depot_passeport_propositions"
# Champ lu -> nom exposé (celui de la fiche) ; l'ordre est celui de l'affichage.
_CHAMPS_PROPOSES = (
    (NOM, "nom"),
    (PRENOM, "prenom"),
    (DATE_NAISSANCE, "date_naissance"),
    (SEXE, "sexe"),
    (NATIONALITE_CODE, "nationalite"),
    (NUMERO_PASSEPORT, "numero_passeport"),
    (DATE_EXPIRATION_PASSEPORT, "date_expiration_passeport"),
)
_CHAMPS_MRZ_FORTS = (NUMERO_PASSEPORT, DATE_NAISSANCE, DATE_EXPIRATION_PASSEPORT)
MESSAGE_SAISIE_MANUELLE = (
    "La zone lisible par machine (MRZ) du passeport est absente, illisible ou invalide : "
    "aucune valeur n'est proposée. Saisissez les informations manuellement."
)


class PasseportDejaUtilise(Conflit):
    """Un candidat du bureau a déjà ce numéro de passeport (le message ne contient aucune valeur)."""

    code = "passeport_deja_utilise"

    def __init__(self, candidat_id: uuid.UUID) -> None:
        super().__init__("Un candidat de ce bureau possède déjà ce numéro de passeport : aucune fiche créée.")
        self.candidat_id = candidat_id


def _tid(db: Session) -> uuid.UUID:
    tid = tenant_courant(db)
    if tid is None:
        raise RuntimeError("Contexte bureau (tenant) manquant sur la session.")
    return tid


def _chemin(depot_tenant: uuid.UUID, depot_id: uuid.UUID) -> str:
    return f"{depot_tenant}/depots/{depot_id}.bin"


def _expire_le(depot: DepotPasseport) -> datetime:
    return depot.cree_le + timedelta(hours=DUREE_CONSERVATION_HEURES)


def _candidat_par_passeport(db: Session, cle: bytes, tid: uuid.UUID, numero: str | None) -> uuid.UUID | None:
    idx = calculer_index_aveugle(cle, tid, "passeport", numero)
    if idx is None:
        return None
    return db.scalar(select(Candidat.id).where(Candidat.idx_passeport == idx))


# ================================================================== purge
def purger_depots_expires(
    db: Session, *, parametres: Parametres, acteur_id: uuid.UUID | None = None, maintenant: datetime | None = None
) -> int:
    """Supprime, tous bureaux confondus (opération système), les dépôts de plus de 24 h et leurs fichiers.
    L'audit n'est écrit que pour le bureau de la session courante (aucun contenu, seulement un nombre)."""
    limite = (maintenant or maintenant_utc()) - timedelta(hours=DUREE_CONSERVATION_HEURES)
    tenant = tenant_courant(db)
    with sans_filtre_tenant(db):
        lignes = db.execute(
            select(DepotPasseport.id, DepotPasseport.tenant_id, DepotPasseport.chemin_stockage_relatif).where(
                DepotPasseport.cree_le < limite
            )
        ).all()
        if not lignes:
            return 0
        db.execute(delete(DepotPasseport).where(DepotPasseport.id.in_([ligne.id for ligne in lignes])))
        db.commit()
    for ligne in lignes:
        chemin = _resoudre_chemin_stockage(parametres.dossier_stockage, ligne.chemin_stockage_relatif)
        chemin.unlink(missing_ok=True)
    propres = sum(1 for ligne in lignes if ligne.tenant_id == tenant)
    if tenant is not None and propres:
        audit.journaliser(
            db, "depot_passeport.purge", ResultatAudit.SUCCES, acteur_id=acteur_id,
            ressource_type="depot_passeport", details={"nb_depots_purges": propres},
        )
        db.commit()
    return len(lignes)


def _obtenir(db: Session, depot_id: uuid.UUID, parametres: Parametres) -> DepotPasseport:
    depot = db.scalar(select(DepotPasseport).where(DepotPasseport.id == depot_id))
    if depot is None:
        raise NonTrouve("Dépôt introuvable ou expiré.")
    if depot.cree_le < maintenant_utc() - timedelta(hours=DUREE_CONSERVATION_HEURES):
        purger_depots_expires(db, parametres=parametres)
        raise NonTrouve("Dépôt introuvable ou expiré.")
    return depot


# ================================================================== lecture MRZ
def _propositions_fiables(champs: list[ChampLu]) -> list[ChampLu]:
    """Liste vide si la MRZ n'est pas intégralement vérifiée (numéro et deux dates : chiffres de contrôle OK)."""
    par_champ = {c.champ: c for c in champs}
    for requis in _CHAMPS_MRZ_FORTS:
        c = par_champ.get(requis)
        if c is None or not c.valide or not c.controle_fort:
            return []
    return [c for c in champs if c.valide]


def _serialiser(champs: list[ChampLu]) -> list[dict[str, object]]:
    par_champ = {c.champ: c for c in champs}
    return [
        {"champ": nom, "valeur": c.valeur, "extrait": c.extrait, "page": c.page, "confiance": c.confiance}
        for lu, nom in _CHAMPS_PROPOSES
        if (c := par_champ.get(lu)) is not None
    ]


def _sortie(db: Session, depot: DepotPasseport, cle: bytes, avertissements: list[str]) -> DepotPasseportSortie:
    brut = dechiffrer_champ(cle, depot.tenant_id, _AAD_PROPOSITIONS, depot.propositions_chiffrees)
    propositions = [
        PropositionSortie(statut=STATUT_PROPOSITION, **p) for p in (json.loads(brut) if brut else [])
    ]
    numero = next((p.valeur for p in propositions if p.champ == "numero_passeport"), None)
    return DepotPasseportSortie(
        id=depot.id,
        statut=depot.statut,
        propositions=propositions,
        saisie_manuelle_requise=depot.statut == STATUT_SAISIE_MANUELLE,
        avertissements=avertissements,
        candidat_existant_id=_candidat_par_passeport(db, cle, depot.tenant_id, numero),
        expire_le=_expire_le(depot),
        cree_le=depot.cree_le,
    )


def _lire_passeport(
    lecteur: LecteurDocument, contenu: bytes, type_mime: str, avertissements: list[str]
) -> list[ChampLu]:
    try:
        lecture = lecteur.lire_texte(contenu, type_mime)
    except (DonneesInvalides, ServiceIndisponible) as exc:
        avertissements.append(f"Lecture automatique impossible : {exc.message}")
        return []
    avertissements.extend(lecture.avertissements)
    champs = extraire_champs("passeport", [(p.numero, p.texte) for p in lecture.pages])
    fiables = _propositions_fiables(champs)
    if not fiables:
        avertissements.append(MESSAGE_SAISIE_MANUELLE)
    return fiables


# ================================================================== dépôt
def deposer_passeport(
    db: Session,
    *,
    nom_fichier_origine: str,
    contenu_clair: bytes,
    acteur_id: uuid.UUID,
    parametres: Parametres,
    cle_maitresse: bytes,
    lecteur_document: LecteurDocument,
) -> DepotPasseportSortie:
    tid = _tid(db)
    purger_depots_expires(db, parametres=parametres, acteur_id=acteur_id)
    if not contenu_clair:
        raise DonneesInvalides("Le fichier déposé est vide.")
    if len(contenu_clair) > parametres.taille_max_document_octets:
        raise DonneesInvalides(
            f"Le fichier dépasse la taille maximale autorisée ({parametres.taille_max_document_octets} octets)."
        )
    type_mime = _detecter_type_mime_par_signature(contenu_clair)

    avertissements: list[str] = []
    fiables = _lire_passeport(lecteur_document, contenu_clair, type_mime, avertissements)

    depot_id = uuid.uuid4()
    chemin_relatif = _chemin(tid, depot_id)
    chemin = _resoudre_chemin_stockage(parametres.dossier_stockage, chemin_relatif)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(
        chiffrer_octets(
            cle_maitresse, tenant_id=tid, candidat_id=depot_id, document_id=depot_id, contenu_clair=contenu_clair
        )
    )
    propositions = _serialiser(fiables)
    depot = DepotPasseport(
        id=depot_id,
        tenant_id=tid,
        depose_par_id=acteur_id,
        nom_fichier_chiffre=chiffrer_champ(cle_maitresse, tid, _AAD_NOM, _normaliser_nom_fichier(nom_fichier_origine)) or "",
        type_mime=type_mime,
        taille_octets=len(contenu_clair),
        empreinte_contenu=calculer_empreinte_document(cle_maitresse, tid, contenu_clair),
        chemin_stockage_relatif=chemin_relatif,
        statut=STATUT_PROPOSE if propositions else STATUT_SAISIE_MANUELLE,
        propositions_chiffrees=chiffrer_champ(cle_maitresse, tid, _AAD_PROPOSITIONS, json.dumps(propositions))
        if propositions else None,
    )
    try:
        db.add(depot)
        db.flush()
        audit.journaliser(
            db, "depot_passeport.depot", ResultatAudit.SUCCES, acteur_id=acteur_id,
            ressource_type="depot_passeport", ressource_id=depot.id,
            details={"statut": depot.statut, "nb_propositions": len(propositions), "taille_octets": depot.taille_octets},
        )
        db.commit()
    except Exception:
        db.rollback()
        chemin.unlink(missing_ok=True)
        raise
    return _sortie(db, depot, cle_maitresse, avertissements)


def obtenir_depot(
    db: Session, *, depot_id: uuid.UUID, parametres: Parametres, cle_maitresse: bytes,
    reserve_au_deposant: uuid.UUID | None = None,
) -> DepotPasseportSortie:
    """`reserve_au_deposant` : si fourni, seul ce déposant peut lire le dépôt (sinon introuvable)."""
    depot = _obtenir(db, depot_id, parametres)
    if reserve_au_deposant is not None and depot.depose_par_id != reserve_au_deposant:
        raise NonTrouve("Dépôt introuvable ou expiré.")
    avertissements = [MESSAGE_SAISIE_MANUELLE] if depot.statut == STATUT_SAISIE_MANUELLE else []
    return _sortie(db, depot, cle_maitresse, avertissements)


def _supprimer_depot(db: Session, depot: DepotPasseport, parametres: Parametres) -> None:
    chemin = _resoudre_chemin_stockage(parametres.dossier_stockage, depot.chemin_stockage_relatif)
    db.delete(depot)
    db.flush()
    chemin.unlink(missing_ok=True)


def supprimer_depot(
    db: Session, *, depot_id: uuid.UUID, acteur_id: uuid.UUID, parametres: Parametres
) -> None:
    depot = _obtenir(db, depot_id, parametres)
    _supprimer_depot(db, depot, parametres)
    audit.journaliser(
        db, "depot_passeport.suppression", ResultatAudit.SUCCES, acteur_id=acteur_id,
        ressource_type="depot_passeport", ressource_id=depot_id,
    )
    db.commit()


# ================================================================== création de la fiche
def _valeurs_confirmees(donnees: CreationFicheEntree) -> tuple[CandidatCreation, dict[str, str]]:
    """Valide les valeurs confirmées ; renvoie la création et les valeurs par champ LU (pour les extractions)."""
    if not donnees.confirme:
        raise DonneesInvalides("Confirmation humaine requise : cochez la confirmation des valeurs avant de créer la fiche.")
    nom, prenom = " ".join(donnees.nom.split()), " ".join(donnees.prenom.split())
    if not nom or not prenom:
        raise DonneesInvalides("Le nom et le prénom sont obligatoires.")
    numero = None
    if donnees.numero_passeport is not None:
        numero = normaliser_valeur(NUMERO_PASSEPORT, donnees.numero_passeport)
        if not valeur_valide(NUMERO_PASSEPORT, numero):
            raise DonneesInvalides("Le numéro de passeport saisi n'est pas valide.")
    creation = CandidatCreation(
        nom=nom, prenom=prenom, sexe=donnees.sexe, date_naissance=donnees.date_naissance,
        nationalite=donnees.nationalite, numero_passeport=numero,
        date_expiration_passeport=donnees.date_expiration_passeport,
    )
    confirmees = {NOM: nom, PRENOM: prenom}
    if donnees.date_naissance:
        confirmees[DATE_NAISSANCE] = donnees.date_naissance.isoformat()
    if donnees.sexe:
        confirmees[SEXE] = donnees.sexe.value
    if donnees.nationalite:
        confirmees[NATIONALITE_CODE] = normaliser_valeur(NATIONALITE_CODE, donnees.nationalite)
    if numero:
        confirmees[NUMERO_PASSEPORT] = numero
    if donnees.date_expiration_passeport:
        confirmees[DATE_EXPIRATION_PASSEPORT] = donnees.date_expiration_passeport.isoformat()
    return creation, confirmees


def _memes_valeurs(champ: str, lue: str, confirmee: str) -> bool:
    if champ in (NOM, PRENOM):
        return normaliser_pour_index(lue) == normaliser_pour_index(confirmee)
    return normaliser_valeur(champ, lue) == confirmee


def _marquer_extractions(
    db: Session, *, candidat_id: uuid.UUID, document_id: uuid.UUID, confirmees: dict[str, str],
    acteur_id: uuid.UUID, cle: bytes,
) -> int:
    """Chaque valeur lue confirmée devient `valide_humain` (valeur corrigée si l'humain l'a changée) ;
    une valeur lue que l'humain n'a pas confirmée reste telle quelle. Les valeurs écrites sur la fiche sont `appliquees`."""
    lignes = lister_extractions(db, candidat_id=candidat_id, cle_maitresse=cle, document_id=document_id)
    appliquees: list[uuid.UUID] = []
    for ligne in lignes:
        confirmee = confirmees.get(ligne.champ)
        if confirmee is None:
            continue
        if _memes_valeurs(ligne.champ, ligne.valeur, confirmee):
            action, valeur = "valider", None
        elif valeur_valide(ligne.champ, confirmee):
            action, valeur = "corriger", confirmee
        else:  # ex. nationalité saisie en toutes lettres : la valeur lue (code) n'est pas celle de la fiche
            decider_extraction(
                db, candidat_id=candidat_id, extraction_id=ligne.id, action="rejeter",
                valeur_corrigee=None, acteur_id=acteur_id, cle_maitresse=cle,
            )
            continue
        decider_extraction(
            db, candidat_id=candidat_id, extraction_id=ligne.id, action=action,
            valeur_corrigee=valeur, acteur_id=acteur_id, cle_maitresse=cle,
        )
        appliquees.append(ligne.id)
    if appliquees:
        maintenant = maintenant_utc()
        for e in db.scalars(select(ExtractionDocument).where(ExtractionDocument.id.in_(appliquees))):
            e.applique_le = maintenant
        db.commit()
    return len(appliquees)


def creer_fiche_depuis_depot(
    db: Session,
    *,
    depot_id: uuid.UUID,
    donnees: CreationFicheEntree,
    acteur_id: uuid.UUID,
    parametres: Parametres,
    cle_maitresse: bytes,
    lecteur_document: LecteurDocument,
) -> FicheCreeeSortie:
    tid = _tid(db)
    depot = _obtenir(db, depot_id, parametres)
    creation, confirmees = _valeurs_confirmees(donnees)

    existant = _candidat_par_passeport(db, cle_maitresse, tid, creation.numero_passeport)
    if existant is not None:
        audit.journaliser(
            db, "depot_passeport.doublon", ResultatAudit.REFUS, acteur_id=acteur_id,
            ressource_type="depot_passeport", ressource_id=depot.id, details={"candidat_existant_id": str(existant)},
        )
        db.commit()
        raise PasseportDejaUtilise(existant)

    chemin = _resoudre_chemin_stockage(parametres.dossier_stockage, depot.chemin_stockage_relatif)
    if not chemin.exists():
        raise NonTrouve("Fichier du dépôt introuvable : redéposez le passeport.")
    contenu = dechiffrer_octets(
        cle_maitresse, tenant_id=tid, candidat_id=depot.id, document_id=depot.id, contenu_chiffre=chemin.read_bytes()
    )
    nom_fichier = dechiffrer_champ(cle_maitresse, tid, _AAD_NOM, depot.nom_fichier_chiffre) or "passeport"

    try:
        candidat = creer_candidat(db, donnees=creation, acteur_id=acteur_id, cle_maitresse=cle_maitresse)
    except (IntegrityError, Conflit):
        # Course perdue contre une création concurrente du même passeport (index unique en base).
        db.rollback()
        existant = _candidat_par_passeport(db, cle_maitresse, tid, creation.numero_passeport)
        if existant is None:
            raise
        raise PasseportDejaUtilise(existant) from None
    document = deposer_document(
        db, candidat_id=candidat.id, type_piece=TYPE_PIECE_PASSEPORT, nom_fichier_origine=nom_fichier,
        contenu_clair=contenu, date_expiration=donnees.date_expiration_passeport, acteur_id=acteur_id,
        parametres=parametres, cle_maitresse=cle_maitresse,
    )
    avertissements: list[str] = []
    nb_validees = 0
    try:
        lancer_extraction_document(
            db, candidat_id=candidat.id, document_id=document.id, acteur_id=acteur_id, parametres=parametres,
            cle_maitresse=cle_maitresse, lecteur_document=lecteur_document,
        )
        nb_validees = _marquer_extractions(
            db, candidat_id=candidat.id, document_id=document.id, confirmees=confirmees,
            acteur_id=acteur_id, cle=cle_maitresse,
        )
    except (DonneesInvalides, ServiceIndisponible) as exc:
        db.rollback()
        avertissements.append(f"Fiche créée, mais la lecture du document n'a pas pu être rattachée : {exc.message}")

    try:
        depot = _obtenir(db, depot_id, parametres)
    except NonTrouve:
        depot = None  # supprimé ou purgé en concurrence : la fiche est créée, rien d'autre à nettoyer
    if depot is not None:
        _supprimer_depot(db, depot, parametres)
    audit.journaliser(
        db, "depot_passeport.creer_fiche", ResultatAudit.SUCCES, acteur_id=acteur_id,
        ressource_type="candidat", ressource_id=candidat.id,
        details={"depot_id": str(depot_id), "document_id": str(document.id), "nb_extractions_validees": nb_validees},
    )
    db.commit()
    return FicheCreeeSortie(
        candidat=candidat, document_id=document.id, extractions_validees=nb_validees, avertissements=avertissements
    )

