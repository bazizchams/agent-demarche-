"""Orchestrateur du dossier automatique (phase P7) : « je n'envoie que les documents, la plateforme fait le reste ».

Principes :
- L'ÉTAT est recalculé de façon déterministe depuis la base (aucune table) : relancer ne refait que ce qui
  manque et n'écrase aucune décision humaine (les services appelés ont déjà cette garantie).
- Règle 1 : l'orchestrateur ne valide JAMAIS à la place d'un humain (valeurs lues, points forts, projet,
  lettres) et ne crée ni ne soumet aucun vœu ; chaque étape à valider porte une `action_humaine` explicite.
- Règle 4 : rien n'est inventé ; une pièce ou un champ manquant est listé.
- Règle 5 : l'état et l'audit ne contiennent que des codes et des compteurs.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.chiffrement import dechiffrer_champ
from app.core.config import Parametres
from app.core.erreurs import ErreurMetier
from app.modeles.document import DocumentCandidat
from app.modeles.extraction_document import STATUTS_APPLICABLES, ExtractionDocument, StatutExtraction
from app.modeles.journal_audit import EntreeAudit, ResultatAudit
from app.modeles.point_fort import PointFort, StatutPointFort, StatutProjet
from app.modeles.voeu_formation import StatutVoeu
from app.schemas.document import StatutPieceRequise
from app.schemas.dossier_automatique import (
    CODES_ETAPES,
    EtapeDossierSortie,
    EtatDossierAutomatiqueSortie,
    StatutEtape,
)
from app.schemas.selection_voeux import NiveauLangueProfil, ProfilEtudiant
from app.services import audit, catalogue_formations, lettres_voeux, selection_voeux
from app.services import deductions_dossier as service_deductions
from app.services import projet_professionnel as service_projet
from app.services import voeux as service_voeux
from app.services.application_extractions import (
    CHAMPS_FICHE,
    _convertir,
    attribut_fiche,
    _identiques,
    _vide,
    appliquer_extractions_a_fiche,
)
from app.services.candidats import obtenir_candidat
from app.services.documents import lister_documents_orm
from app.services.extraction_champs import NIVEAUX_CECRL
from app.services.extractions import _AAD_VALEUR, lancer_extraction_document
from app.services.lecture_documents import LecteurDocument
from app.services.lecture_vision import LecteurVision
from app.services.lettres_motivation import FaitsParcours
from app.services.llm import ClientLLM
from app.services.pieces_requises import obtenir_demarche, verifier_completude_dossier

CODE_DEMARCHE_DEFAUT = "campus_france"
MAX_VOEUX_SUGGERES = 7
LIMITE_PROJET_LETTRE = 800
ACTION_LECTURE_ILLISIBLE = "dossier_automatique.lecture_illisible"
ATTENTE = "En attente de l'étape précédente."

_LIBELLES = {
    "pieces": "Pièces du dossier",
    "lecture": "Lecture des documents",
    "revue_valeurs": "Revue des valeurs lues",
    "fiche": "Fiche du candidat",
    "points_forts": "Points forts vérifiables",
    "projet_professionnel": "Projet professionnel",
    "voeux": "Choix des vœux",
    "lettres": "Lettres de motivation",
    "navigateur": "Co-Pilote navigateur",
}
_ECRANS = {
    "pieces": "documents",
    "lecture": "documents",
    "revue_valeurs": "revue_extractions",
    "fiche": "fiche",
    "points_forts": "points_forts",
    "projet_professionnel": "projet_professionnel",
    "voeux": "voeux",
    "lettres": "voeux",
    "navigateur": "navigateur",
}
_MOTS_STATUT_PIECE = {
    StatutPieceRequise.EXPIREE: "expirée",
    StatutPieceRequise.VALIDITE_INSUFFISANTE: "validité insuffisante",
    StatutPieceRequise.EXPIRATION_NON_RENSEIGNEE: "date d'expiration à renseigner",
}


@dataclass(frozen=True)
class Incidents:
    """Échecs de la dernière exécution (non persistés : ils ne servent qu'à la réponse de `lancer`)."""

    illisibles: int = 0
    lettres_en_echec: int = 0
    projet_en_echec: bool = False


@dataclass
class _Donnees:
    nb_documents: int = 0
    ids_non_lus: list[uuid.UUID] = field(default_factory=list)
    ids_illisibles: list[uuid.UUID] = field(default_factory=list)
    pieces_manquantes: list[str] = field(default_factory=list)
    nb_champs_manquants: int = 0
    nb_pieces_requises: int = 0
    ext: dict[str, int] = field(default_factory=dict)
    a_reporter: int = 0
    conflits: int = 0
    pts: dict[str, int] = field(default_factory=dict)
    projet: object | None = None
    voeux: list[dict] = field(default_factory=list)
    nb_propositions: int = 0

    @property
    def nb_non_lus(self) -> int:
        return len(self.ids_non_lus)


def _ids_documents_lus(db: Session, candidat_id: uuid.UUID, documents: list[DocumentCandidat]) -> set[uuid.UUID]:
    """Un document est lu s'il a des valeurs OU si une lecture a été journalisée (une lecture qui ne
    trouve rien ne doit pas être refaite à chaque relance)."""
    ids = {d.id for d in documents}
    avec_valeurs = set(
        db.scalars(select(ExtractionDocument.document_id).where(ExtractionDocument.candidat_id == candidat_id))
    )
    journalises = set(
        db.scalars(
            select(EntreeAudit.ressource_id).where(
                EntreeAudit.action == "extraction.lancer", EntreeAudit.resultat == ResultatAudit.SUCCES
            )
        )
    )
    return ids & (avec_valeurs | journalises)


def _diagnostic_fiche(db: Session, candidat_id: uuid.UUID, fiche, cle: bytes) -> tuple[int, int]:
    """(valeurs confirmées à reporter, conflits) : même logique que le report à la fiche, en lecture seule."""
    lignes = db.scalars(
        select(ExtractionDocument).where(
            ExtractionDocument.candidat_id == candidat_id,
            ExtractionDocument.statut.in_(list(STATUTS_APPLICABLES)),
            ExtractionDocument.applique_le.is_(None),
            ExtractionDocument.champ.in_(CHAMPS_FICHE),
        )
    )
    par_champ: dict[str, list[ExtractionDocument]] = {}
    for e in lignes:
        par_champ.setdefault(e.champ, []).append(e)
    a_reporter = conflits = 0
    for champ, exts in par_champ.items():
        try:
            valeurs = [
                _convertir(champ, dechiffrer_champ(cle, e.tenant_id, _AAD_VALEUR, e.valeur_chiffree) or "")
                for e in exts
            ]
            if any(not _identiques(champ, valeurs[0], v) for v in valeurs[1:]):
                conflits += 1
                continue
            actuelle = getattr(fiche, attribut_fiche(champ))
            if _vide(actuelle):
                a_reporter += 1
            elif not _identiques(champ, actuelle, valeurs[0]):
                conflits += 1
        except ValueError:
            conflits += 1
    return a_reporter, conflits


def _profil(fiche) -> ProfilEtudiant:
    """Profil sans identité : niveaux de langue connus de la fiche uniquement (rien n'est inventé)."""

    def langue(valeur: str | None) -> NiveauLangueProfil:
        return NiveauLangueProfil(niveau=valeur if valeur in NIVEAUX_CECRL else None)

    return ProfilEtudiant(francais=langue(fiche.niveau_francais), anglais=langue(fiche.niveau_anglais))


def _collecter(
    db: Session, candidat_id: uuid.UUID, cle: bytes, parametres: Parametres, code_demarche: str, aujourdhui: date
) -> _Donnees:
    d = _Donnees()
    fiche = obtenir_candidat(db, candidat_id=candidat_id, cle_maitresse=cle)
    documents = lister_documents_orm(db, candidat_id=candidat_id)
    d.nb_documents = len(documents)
    lus = _ids_documents_lus(db, candidat_id, documents)
    d.ids_non_lus = [x.id for x in documents if x.id not in lus]
    echecs = set(
        db.scalars(
            select(EntreeAudit.ressource_id).where(
                EntreeAudit.action == ACTION_LECTURE_ILLISIBLE, EntreeAudit.resultat == ResultatAudit.ECHEC
            )
        )
    )
    d.ids_illisibles = [i for i in d.ids_non_lus if i in echecs]

    demarche = obtenir_demarche(parametres.dossier_demarches, code_demarche, db)
    comp = verifier_completude_dossier(
        candidat=fiche, documents=documents, demarche=demarche, date_reference=aujourdhui
    )
    d.nb_champs_manquants = len(comp.champs_candidat_manquants)
    d.nb_pieces_requises = sum(1 for p in comp.pieces if p.statut is not StatutPieceRequise.NON_APPLICABLE)
    for p in comp.pieces:
        if p.type_piece in comp.pieces_manquantes_ou_invalides:
            mot = _MOTS_STATUT_PIECE.get(p.statut)
            d.pieces_manquantes.append(f"{p.libelle} ({mot})" if mot else p.libelle)

    statuts = list(db.scalars(select(ExtractionDocument.statut).where(ExtractionDocument.candidat_id == candidat_id)))
    d.ext = {s.value: statuts.count(s) for s in StatutExtraction}
    d.a_reporter, d.conflits = _diagnostic_fiche(db, candidat_id, fiche, cle)

    points = list(db.scalars(select(PointFort.statut).where(PointFort.candidat_id == candidat_id)))
    d.pts = {s.value: points.count(s) for s in StatutPointFort}

    try:
        d.projet = service_projet.lire_projet(db, candidat_id=candidat_id, cle_maitresse=cle)
    except ErreurMetier:
        d.projet = None
    d.voeux = service_voeux.lister_voeux(db, candidat_id, cle)

    propositions = selection_voeux.selectionner(
        catalogue_formations.charger_fiches(db), _profil(fiche), aujourd_hui=aujourdhui, max_voeux=MAX_VOEUX_SUGGERES
    ).propositions
    d.nb_propositions = len(propositions)
    return d


# ================================================================== étapes
def _e(code: str, statut: StatutEtape, detail: str, action: str | None = None, **compteurs: int) -> EtapeDossierSortie:
    return EtapeDossierSortie(
        code=code, libelle=_LIBELLES[code], statut=statut, detail=detail, action_humaine=action,
        lien_ecran=_ECRANS[code], compteurs=compteurs,
    )


def _pieces(d: _Donnees) -> EtapeDossierSortie:
    n = len(d.pieces_manquantes)
    c = {"documents": d.nb_documents, "pieces_requises": d.nb_pieces_requises, "pieces_manquantes": n,
         "champs_fiche_manquants": d.nb_champs_manquants}
    if d.nb_documents == 0:
        return _e("pieces", StatutEtape.BLOQUE, "Aucun document déposé.", "Déposer les documents du candidat", **c)
    if n:
        return _e("pieces", StatutEtape.BLOQUE, f"{n} pièce(s) manquante(s) ou à renouveler.",
                  f"Déposer ou renouveler {n} pièce(s) : voir la liste", **c)
    return _e("pieces", StatutEtape.TERMINE, "Toutes les pièces requises sont présentes et valides.", **c)


def _lecture(d: _Donnees, inc: Incidents) -> EtapeDossierSortie:
    lus = d.nb_documents - d.nb_non_lus
    illisibles = max(inc.illisibles, len(d.ids_illisibles))  # mémorisés : visibles aussi hors de `lancer`
    c = {"documents": d.nb_documents, "lus": lus, "a_lire": d.nb_non_lus, "illisibles": illisibles}
    if d.nb_documents == 0:
        return _e("lecture", StatutEtape.BLOQUE, "Aucun document à lire.", "Déposer les documents du candidat", **c)
    if illisibles:
        return _e("lecture", StatutEtape.BLOQUE, f"{illisibles} document(s) illisible(s).",
                  f"Remplacer {illisibles} document(s) illisible(s)", **c)
    if d.nb_non_lus == 0:
        return _e("lecture", StatutEtape.TERMINE, f"{lus} document(s) lu(s).", **c)
    st = StatutEtape.EN_COURS if lus else StatutEtape.A_FAIRE
    return _e("lecture", st, f"{d.nb_non_lus} document(s) restant(s) à lire.", **c)


def _revue(d: _Donnees, lecture: EtapeDossierSortie) -> EtapeDossierSortie:
    auto, av = d.ext.get("auto", 0), d.ext.get("a_verifier", 0)
    attente = auto + av
    c = {"auto": auto, "a_verifier": av, "a_confirmer": attente, "confirmees": d.ext.get("valide_humain", 0),
         "rejetees": d.ext.get("rejete", 0)}
    if attente:
        return _e("revue_valeurs", StatutEtape.A_VERIFIER, f"{attente} valeur(s) lue(s) en attente de confirmation.",
                  f"Confirmer {attente} valeurs lues", **c)
    if sum(d.ext.values()):
        return _e("revue_valeurs", StatutEtape.TERMINE, "Toutes les valeurs lues ont été décidées.", **c)
    if lecture.statut is StatutEtape.TERMINE:
        return _e("revue_valeurs", StatutEtape.TERMINE, "Aucune valeur lue dans les documents.", **c)
    return _e("revue_valeurs", StatutEtape.A_FAIRE, ATTENTE, **c)


def _fiche(d: _Donnees, revue: EtapeDossierSortie) -> EtapeDossierSortie:
    c = {"champs_manquants": d.nb_champs_manquants, "valeurs_a_reporter": d.a_reporter, "conflits": d.conflits}
    if d.conflits:
        return _e("fiche", StatutEtape.A_VERIFIER, f"{d.conflits} valeur(s) confirmée(s) en conflit avec la fiche.",
                  f"Arbitrer {d.conflits} conflit(s) entre fiche et documents", **c)
    if d.a_reporter:
        return _e("fiche", StatutEtape.A_FAIRE, f"{d.a_reporter} valeur(s) confirmée(s) à reporter sur la fiche.", **c)
    if revue.statut in (StatutEtape.A_VERIFIER, StatutEtape.A_FAIRE):
        return _e("fiche", StatutEtape.A_FAIRE, ATTENTE, **c)
    if d.nb_champs_manquants:
        return _e("fiche", StatutEtape.A_VERIFIER, f"{d.nb_champs_manquants} champ(s) de la fiche non renseigné(s).",
                  f"Compléter {d.nb_champs_manquants} champ(s) manquant(s) de la fiche", **c)
    return _e("fiche", StatutEtape.TERMINE, "Fiche complète.", **c)


def _points_forts(d: _Donnees, revue: EtapeDossierSortie) -> EtapeDossierSortie:
    pend, conf, rej = d.pts.get("a_verifier", 0), d.pts.get("confirme", 0), d.pts.get("rejete", 0)
    c = {"a_confirmer": pend, "confirmes": conf, "rejetes": rej}
    if pend:
        return _e("points_forts", StatutEtape.A_VERIFIER, f"{pend} point(s) fort(s) à confirmer ou rejeter.",
                  f"Confirmer {pend} point(s) fort(s) avec leur pièce", **c)
    if conf + rej:
        return _e("points_forts", StatutEtape.TERMINE, "Tous les points forts ont été décidés.", **c)
    if revue.statut is not StatutEtape.TERMINE:
        return _e("points_forts", StatutEtape.A_FAIRE, ATTENTE, **c)
    if d.ext.get("valide_humain", 0) == 0:
        return _e("points_forts", StatutEtape.BLOQUE, "Aucune valeur confirmée : rien à déduire.",
                  "Confirmer des valeurs lues ou déposer des pièces lisibles", **c)
    return _e("points_forts", StatutEtape.TERMINE, "Aucun point fort déductible des pièces confirmées.", **c)


def _projet(d: _Donnees, pf: EtapeDossierSortie, inc: Incidents) -> EtapeDossierSortie:
    p = d.projet
    if p is not None:
        c = {"version": p.version, "elements_a_verifier": len(p.elements_a_verifier)}
        if p.statut is StatutProjet.VALIDE:
            return _e("projet_professionnel", StatutEtape.TERMINE, "Projet validé par un humain.", **c)
        action = (
            "Valider le projet professionnel"
            if p.validable
            else "Relire et compléter le projet professionnel avant validation"
        )
        return _e("projet_professionnel", StatutEtape.A_VERIFIER,
                  "Brouillon prêt, en attente de validation humaine.", action, **c)
    conf = d.pts.get("confirme", 0)
    c = {"points_forts_confirmes": conf}
    if pf.statut in (StatutEtape.A_FAIRE, StatutEtape.A_VERIFIER):
        return _e("projet_professionnel", StatutEtape.A_FAIRE, ATTENTE, **c)
    if conf == 0:
        return _e("projet_professionnel", StatutEtape.BLOQUE, "Aucun point fort confirmé pour générer un brouillon.",
                  "Confirmer au moins un point fort ou rédiger le projet à la main", **c)
    if inc.projet_en_echec:
        return _e("projet_professionnel", StatutEtape.BLOQUE, "Génération du brouillon impossible.",
                  "Rédiger le projet professionnel à la main", **c)
    return _e("projet_professionnel", StatutEtape.A_FAIRE, "Brouillon à générer.", **c)


def _voeux(d: _Donnees, revue: EtapeDossierSortie) -> EtapeDossierSortie:
    n = len(d.voeux)
    c = {"voeux": n, "propositions": d.nb_propositions}
    if n:
        return _e("voeux", StatutEtape.TERMINE, f"{n} vœu(x) retenu(s) par un humain.", **c)
    if revue.statut is not StatutEtape.TERMINE:
        return _e("voeux", StatutEtape.A_FAIRE, ATTENTE, **c)
    if d.nb_propositions:
        return _e("voeux", StatutEtape.A_VERIFIER, f"{d.nb_propositions} formation(s) suggérée(s), aucun vœu retenu.",
                  f"Choisir jusqu'à {MAX_VOEUX_SUGGERES} vœux parmi {d.nb_propositions} formation(s) suggérée(s)", **c)
    return _e("voeux", StatutEtape.BLOQUE, "Aucune formation suggérée.",
              "Compléter la fiche ou importer le catalogue des formations", **c)


def _lettres(d: _Donnees, projet: EtapeDossierSortie, inc: Incidents) -> EtapeDossierSortie:
    sans = sum(1 for v in d.voeux if not (v["motivation"] or "").strip())
    brouillons = sum(
        1 for v in d.voeux if (v["motivation"] or "").strip() and v["statut"] == StatutVoeu.BROUILLON.value
    )
    valides = len(d.voeux) - sans - brouillons
    c = {"sans_lettre": sans, "brouillons": brouillons, "validees": valides}
    if not d.voeux:
        return _e("lettres", StatutEtape.A_FAIRE, "En attente du choix des vœux.", **c)
    if sans:
        if projet.statut is not StatutEtape.TERMINE:
            return _e("lettres", StatutEtape.A_FAIRE, "En attente de la validation du projet professionnel.", **c)
        if inc.lettres_en_echec:
            return _e("lettres", StatutEtape.BLOQUE, f"{inc.lettres_en_echec} lettre(s) non générée(s).",
                      f"Rédiger {sans} lettre(s) à la main", **c)
        st = StatutEtape.EN_COURS if brouillons + valides else StatutEtape.A_FAIRE
        return _e("lettres", st, f"{sans} lettre(s) à rédiger.", **c)
    if brouillons:
        return _e("lettres", StatutEtape.A_VERIFIER, f"{brouillons} brouillon(s) de lettre prêts.",
                  f"Relire et valider {brouillons} lettre(s)", **c)
    return _e("lettres", StatutEtape.TERMINE, "Toutes les lettres sont validées.", **c)


def _navigateur(d: _Donnees, amont: list[EtapeDossierSortie]) -> EtapeDossierSortie:
    paniers = sum(1 for v in d.voeux if v["statut"] == StatutVoeu.AJOUTE_AU_PANIER.value)
    c = {"voeux_ajoutes": paniers, "voeux": len(d.voeux)}
    if d.voeux and paniers == len(d.voeux):
        return _e("navigateur", StatutEtape.TERMINE, "Tous les vœux sont dans le panier.", **c)
    if all(e.statut is StatutEtape.TERMINE for e in amont):
        return _e("navigateur", StatutEtape.A_VERIFIER, "Dossier prêt : rien n'est envoyé sans validation humaine.",
                  "Lancer le Co-Pilote navigateur puis valider le récapitulatif avant envoi", **c)
    return _e("navigateur", StatutEtape.A_FAIRE, "En attente des étapes précédentes.", **c)


def _construire_etat(candidat_id: uuid.UUID, d: _Donnees, inc: Incidents) -> EtatDossierAutomatiqueSortie:
    pieces, lecture = _pieces(d), _lecture(d, inc)
    revue = _revue(d, lecture)
    fiche, pf = _fiche(d, revue), _points_forts(d, revue)
    projet = _projet(d, pf, inc)
    voeux, lettres = _voeux(d, revue), _lettres(d, projet, inc)
    amont = [pieces, lecture, revue, fiche, pf, projet, voeux, lettres]
    etapes = [*amont, _navigateur(d, amont)]
    assert tuple(e.code for e in etapes) == CODES_ETAPES
    termines = sum(e.statut is StatutEtape.TERMINE for e in etapes)
    return EtatDossierAutomatiqueSortie(
        candidat_id=str(candidat_id), progression=round(100 * termines / len(etapes)),
        etapes=etapes, pieces_manquantes=list(d.pieces_manquantes),
    )


def calculer_etat(
    db: Session, *, candidat_id: uuid.UUID, cle_maitresse: bytes, parametres: Parametres,
    code_demarche: str | None = None, incidents: Incidents | None = None, aujourdhui: date | None = None,
) -> EtatDossierAutomatiqueSortie:
    """Lecture seule, déterministe : aucune écriture."""
    d = _collecter(
        db, candidat_id, cle_maitresse, parametres, code_demarche or CODE_DEMARCHE_DEFAUT, aujourdhui or date.today()
    )
    return _construire_etat(candidat_id, d, incidents or Incidents())


# ================================================================== exécution
def _lire_documents(
    db: Session, candidat_id: uuid.UUID, ids: list[uuid.UUID], deja_signales: set[uuid.UUID], **kw
) -> int:
    illisibles = 0
    for doc_id in ids:
        try:
            lancer_extraction_document(db, candidat_id=candidat_id, document_id=doc_id, **kw)
        except ErreurMetier:
            db.rollback()
            illisibles += 1
            if doc_id not in deja_signales:  # mémorisé pour que l'état le montre encore après `lancer`
                audit.journaliser(
                    db, ACTION_LECTURE_ILLISIBLE, ResultatAudit.ECHEC, acteur_id=kw["acteur_id"],
                    ressource_type="document", ressource_id=doc_id, details={},
                )
                db.commit()
    return illisibles


def _faits_lettre(db: Session, candidat_id: uuid.UUID, cle: bytes, projet_texte: str) -> FaitsParcours:
    faits, _programme, _utilises, _ecartes = service_projet.construire_faits(db, candidat_id, cle)
    return FaitsParcours(
        parcours=faits.parcours, points_forts=faits.points_forts, langues=faits.langues,
        projet=projet_texte[:LIMITE_PROJET_LETTRE] or None,
    )


def _generer_lettres(
    db: Session, client: ClientLLM | None, d: _Donnees, candidat_id: uuid.UUID, acteur_id: uuid.UUID, cle: bytes
) -> tuple[int, int]:
    """Brouillons de lettres pour les vœux déjà retenus par un humain, jamais d'écrasement."""
    if d.projet is None or d.projet.statut is not StatutProjet.VALIDE:
        return 0, 0
    faits = _faits_lettre(db, candidat_id, cle, d.projet.texte)
    ok = echec = 0
    for v in d.voeux:
        if (v["motivation"] or "").strip():
            continue
        try:
            lettres_voeux.generer_lettre_pour_voeu(
                db, client, candidat_id=candidat_id, voeu_id=v["id"], faits=faits, acteur_id=acteur_id,
                cle_maitresse=cle,
            )
            ok += 1
        except ErreurMetier:
            db.rollback()
            echec += 1
    return ok, echec


def lancer(
    db: Session, client: ClientLLM | None, *, candidat_id: uuid.UUID, acteur_id: uuid.UUID, cle_maitresse: bytes,
    parametres: Parametres, lecteur: LecteurDocument, vision: LecteurVision | None = None,
    code_demarche: str | None = None, aujourdhui: date | None = None,
) -> EtatDossierAutomatiqueSortie:
    """Enchaîne ce qui est automatisable et s'arrête à chaque validation humaine. Idempotent."""
    code, jour = code_demarche or CODE_DEMARCHE_DEFAUT, aujourdhui or date.today()
    cle = cle_maitresse

    def relire() -> _Donnees:
        return _collecter(db, candidat_id, cle, parametres, code, jour)

    d = relire()  # 404 hors bureau ou démarche inconnue
    a_lire = len(d.ids_non_lus)
    illisibles = _lire_documents(
        db, candidat_id, d.ids_non_lus, set(d.ids_illisibles), acteur_id=acteur_id, parametres=parametres, cle_maitresse=cle,
        lecteur_document=lecteur, lecteur_vision=vision,
    )
    d = relire()
    if d.a_reporter:  # uniquement des valeurs déjà confirmées par un humain, jamais d'écrasement
        appliquer_extractions_a_fiche(db, candidat_id=candidat_id, acteur_id=acteur_id, cle_maitresse=cle)
    if d.ext.get("valide_humain", 0) or sum(d.pts.values()):
        service_deductions.calculer_points_forts(
            db, candidat_id=candidat_id, acteur_id=acteur_id, cle_maitresse=cle, date_reference=jour
        )
    d = relire()

    projet_echec = projet_genere = False
    if d.projet is None and d.pts.get("confirme", 0) and not d.pts.get("a_verifier", 0):
        try:
            service_projet.generer_projet(db, client, candidat_id=candidat_id, acteur_id=acteur_id, cle_maitresse=cle)
            projet_genere = True
        except ErreurMetier:
            db.rollback()
            projet_echec = True
        d = relire()

    lettres_ok, lettres_echec = _generer_lettres(db, client, d, candidat_id, acteur_id, cle)
    etat = calculer_etat(
        db, candidat_id=candidat_id, cle_maitresse=cle, parametres=parametres, code_demarche=code,
        incidents=Incidents(illisibles, lettres_echec, projet_echec), aujourdhui=jour,
    )
    audit.journaliser(
        db, "dossier_automatique.lancer", ResultatAudit.SUCCES, acteur_id=acteur_id, ressource_type="candidat",
        ressource_id=candidat_id,
        details={
            "code_demarche": code, "nb_documents_lus": a_lire - illisibles, "nb_illisibles": illisibles,
            "projet_genere": projet_genere, "nb_lettres_generees": lettres_ok, "nb_lettres_en_echec": lettres_echec,
            "progression": etat.progression,
        },
    )
    db.commit()
    return etat
