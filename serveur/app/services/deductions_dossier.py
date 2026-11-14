"""Déductions vérifiables du dossier (phase P2) : points forts calculés par des règles
DÉTERMINISTES à partir des seules extractions confirmées par un humain (`STATUTS_APPLICABLES`, aujourd'hui `valide_humain` seul).

Garanties (règles 1, 4 et 5) :
- aucune IA ici ; un fait absent ou douteux ne produit aucun point fort (jamais de valeur
  inventée) ; un champ non géré par les parseurs actuels reste simplement sans point fort ;
- chaque point fort cite sa pièce (document, page, extrait littéral) : sans preuve, il n'existe
  pas ; le texte et l'extrait sont chiffrés en base ;
- un point fort naît `a_verifier` ; seul un humain le confirme ou le rejette ; le niveau de
  langue de la fiche n'est appliqué qu'après cette confirmation et sans écraser une valeur ;
- l'audit ne contient que des identifiants, des compteurs et des codes.
"""

from __future__ import annotations

import calendar
import hashlib
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.chiffrement import chiffrer_champ, dechiffrer_champ
from app.core.erreurs import Conflit, DonneesInvalides, NonTrouve
from app.db.base import maintenant_utc
from app.db.tenant import tenant_courant
from app.modeles.extraction_document import STATUTS_APPLICABLES, ExtractionDocument
from app.modeles.journal_audit import ResultatAudit
from app.modeles.point_fort import PointFort, StatutPointFort
from app.schemas.candidat import CandidatModification
from app.schemas.deduction import ApplicationNiveauSortie, PointFortSortie, ResultatDeductionsSortie
from app.services import audit
from app.services.transaction import commit_ou_conflit
from app.services.candidats import modifier_candidat, obtenir_candidat, obtenir_candidat_orm
from app.services.extraction_champs import (
    CERTIFICAT_DATE,
    CERTIFICAT_TYPE,
    IELTS_BANDE,
    MOYENNE_GENERALE,
    NIVEAU_ANGLAIS,
    NIVEAU_FRANCAIS,
)
from app.services.extractions import _AAD_VALEUR

# Champs lus en plus de ceux des parseurs P1 actuels : tant qu'une lecture ne les produit pas
# (relevé enrichi, saisie humaine corrigée), aucune déduction n'en est tirée.
MENTION = "mention"
RANG = "rang"
DIPLOME_INTITULE = "diplome_intitule"
DIPLOME_ANNEE = "diplome_annee"
DIPLOME_ETABLISSEMENT = "diplome_etablissement"

CATEGORIE_MOYENNE, CATEGORIE_RANG, CATEGORIE_LANGUE, CATEGORIE_PARCOURS = "moyenne", "rang", "langue", "parcours"

ALERTE_EXPIRE = "certificat_expire"
ALERTE_DATE_ABSENTE = "date_absente"
ALERTE_DATE_INCOHERENTE = "date_incoherente"
ALERTE_TYPE_ABSENT = "type_absent"
ALERTE_NON_VERIFIABLE = "validite_non_verifiable"
ALERTE_PREUVE_INVALIDEE = "preuve_invalidee"

VALIDITE_TCF_MOIS = 24
TYPES_SANS_EXPIRATION = frozenset({"DELF", "DALF"})
_MENTIONS = {
    "passable": "Passable",
    "assez bien": "Assez bien",
    "bien": "Bien",
    "tres bien": "Très bien",
    "excellent": "Excellent",
}
_AAD_TEXTE, _AAD_EXTRAIT = "point_fort_texte", "point_fort_extrait"
_PRIORITE_ALERTES = (ALERTE_EXPIRE, ALERTE_DATE_INCOHERENTE, ALERTE_DATE_ABSENTE, ALERTE_TYPE_ABSENT, ALERTE_NON_VERIFIABLE)


@dataclass(frozen=True)
class FaitConfirme:
    """Extraction confirmée, déchiffrée, avec sa preuve."""

    document_id: uuid.UUID
    champ: str
    valeur: str
    page: int | None
    extrait: str


@dataclass(frozen=True)
class PointFortDeduit:
    cle: str
    categorie: str
    regle: str
    texte: str
    document_id: uuid.UUID
    page: int | None
    extrait: str
    alerte: str | None = None
    champ_fiche: str | None = None
    valeur_fiche: str | None = None


# ============================================================ utilitaires purs
def _sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c))


def _decimal_fr(valeur: str) -> str | None:
    try:
        d = Decimal(valeur.strip().replace(",", "."))
    except InvalidOperation:
        return None
    if not d.is_finite() or d < 0 or d > 20:
        return None
    return format(d.normalize(), "f").replace(".", ",")


def _cle(*parties: object) -> str:
    return hashlib.sha256("|".join(str(p) for p in parties).encode("utf-8")).hexdigest()


def ajouter_mois(depart: date, mois: int) -> date:
    total = depart.month - 1 + mois
    annee, m = depart.year + total // 12, total % 12 + 1
    return date(annee, m, min(depart.day, calendar.monthrange(annee, m)[1]))


def _date_fr(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def evaluer_validite(
    type_cert: str | None, date_passage: date | None, reference: date
) -> tuple[str, str | None]:
    """(libellé de validité, code d'alerte). TCF : 24 mois ; DELF/DALF : sans expiration ;
    tout autre type ou type absent : « validité non vérifiable » (jamais déduite)."""
    if type_cert in TYPES_SANS_EXPIRATION:
        return "sans date d'expiration", None
    if type_cert is None:
        return "validité non vérifiable (type de certificat non lu)", ALERTE_TYPE_ABSENT
    if type_cert != "TCF":
        return "validité non vérifiable", ALERTE_NON_VERIFIABLE
    if date_passage is None:
        return "validité non vérifiable (date de passation non lue)", ALERTE_DATE_ABSENTE
    if date_passage > reference:
        return "validité non vérifiable (date de passation postérieure à aujourd'hui)", ALERTE_DATE_INCOHERENTE
    fin = ajouter_mois(date_passage, VALIDITE_TCF_MOIS)
    if reference > fin:
        return f"expiré depuis le {_date_fr(fin)}", ALERTE_EXPIRE
    return f"valable jusqu'au {_date_fr(fin)}", None


def _meilleure_alerte(alertes: list[str]) -> str | None:
    for code in _PRIORITE_ALERTES:
        if code in alertes:
            return code
    return None


def _date_ou_none(valeur: str | None) -> date | None:
    if not valeur:
        return None
    try:
        return date.fromisoformat(valeur)
    except ValueError:
        return None


# ============================================================ règles (une par famille)
def _regle_moyenne(faits: list[FaitConfirme]) -> list[PointFortDeduit]:
    sorties = []
    for f in (x for x in faits if x.champ == MOYENNE_GENERALE):
        texte = _decimal_fr(f.valeur)
        if texte is not None:
            sorties.append(PointFortDeduit(
                _cle("moyenne", f.document_id, texte), CATEGORIE_MOYENNE, "moyenne_generale",
                f"Moyenne générale de {texte}/20", f.document_id, f.page, f.extrait,
            ))
    return sorties


def _regle_mention(faits: list[FaitConfirme]) -> list[PointFortDeduit]:
    sorties = []
    for f in (x for x in faits if x.champ == MENTION):
        libelle = _MENTIONS.get(" ".join(_sans_accents(f.valeur).lower().split()))
        if libelle is not None:
            sorties.append(PointFortDeduit(
                _cle("mention", f.document_id, libelle), CATEGORIE_MOYENNE, "mention",
                f"Mention {libelle}", f.document_id, f.page, f.extrait,
            ))
    return sorties


_RE_RANG = re.compile(r"^\s*(\d{1,4})\s*(?:(?:/|sur)\s*(\d{1,4}))?\s*$", re.IGNORECASE)


def _regle_rang(faits: list[FaitConfirme]) -> list[PointFortDeduit]:
    sorties = []
    for f in (x for x in faits if x.champ == RANG):
        m = _RE_RANG.match(f.valeur)
        if not m:
            continue
        rang, effectif = int(m.group(1)), int(m.group(2)) if m.group(2) else None
        if rang < 1 or (effectif is not None and rang > effectif):
            continue
        texte = f"Rang {rang} sur {effectif}" if effectif else f"Rang {rang}"
        sorties.append(PointFortDeduit(
            _cle("rang", f.document_id, rang, effectif), CATEGORIE_RANG, "rang",
            texte, f.document_id, f.page, f.extrait,
        ))
    return sorties


def _regle_langue(faits: list[FaitConfirme], reference: date) -> list[PointFortDeduit]:
    par_doc: dict[uuid.UUID, dict[str, FaitConfirme]] = {}
    for f in faits:
        par_doc.setdefault(f.document_id, {})[f.champ] = f
    sorties = []
    for doc_id, champs in par_doc.items():
        type_f, date_f, bande_f = champs.get(CERTIFICAT_TYPE), champs.get(CERTIFICAT_DATE), champs.get(IELTS_BANDE)
        for champ_niveau, langue in ((NIVEAU_FRANCAIS, "Français"), (NIVEAU_ANGLAIS, "Anglais")):
            niveau_f = champs.get(champ_niveau)
            niveau = niveau_f.valeur.strip().upper() if niveau_f else ""
            if not re.fullmatch(r"[ABC][12]", niveau):
                continue
            type_cert = type_f.valeur.strip().upper() if type_f else None
            date_passage = _date_ou_none(date_f.valeur if date_f else None)
            validite, alerte = evaluer_validite(type_cert, date_passage, reference)
            morceaux = [type_cert] if type_cert else []
            if date_passage:
                morceaux.append(f"passé le {_date_fr(date_passage)}")
            if bande_f and champ_niveau == NIVEAU_ANGLAIS:
                bande = _decimal_fr(bande_f.valeur)
                if bande:
                    morceaux.append(f"bande {bande}")
            detail = f" ({', '.join(morceaux)})" if morceaux else ""
            sorties.append(PointFortDeduit(
                _cle("langue", doc_id, champ_niveau, niveau, type_cert, date_passage),
                CATEGORIE_LANGUE, "certificat_langue",
                f"{langue} : niveau {niveau}{detail}, {validite}",
                doc_id, niveau_f.page, niveau_f.extrait,
                alerte=_meilleure_alerte([alerte] if alerte else []),
                champ_fiche=champ_niveau, valeur_fiche=niveau,
            ))
    return sorties


def _regle_parcours(faits: list[FaitConfirme], reference: date) -> list[PointFortDeduit]:
    par_doc: dict[uuid.UUID, dict[str, FaitConfirme]] = {}
    for f in faits:
        par_doc.setdefault(f.document_id, {})[f.champ] = f
    sorties = []
    for doc_id, champs in par_doc.items():
        intitule_f = champs.get(DIPLOME_INTITULE)
        if intitule_f is None or not intitule_f.valeur.strip():
            continue
        intitule = " ".join(intitule_f.valeur.split())
        details = []
        etab = champs.get(DIPLOME_ETABLISSEMENT)
        if etab and etab.valeur.strip():
            details.append(" ".join(etab.valeur.split()))
        annee_f = champs.get(DIPLOME_ANNEE)
        annee = annee_f.valeur.strip() if annee_f else ""
        if re.fullmatch(r"\d{4}", annee) and 1950 <= int(annee) <= reference.year:
            details.append(annee)
        else:
            annee = ""
        texte = intitule + (f" ({', '.join(details)})" if details else "")
        sorties.append(PointFortDeduit(
            _cle("parcours", doc_id, intitule, annee, details[0] if etab and details else ""),
            CATEGORIE_PARCOURS, "parcours", texte, doc_id, intitule_f.page, intitule_f.extrait,
        ))
    return sorties


def deduire(faits: list[FaitConfirme], reference: date) -> list[PointFortDeduit]:
    """Toutes les déductions possibles ; un point sans preuve (extrait vide) est écarté."""
    tous = (
        _regle_moyenne(faits) + _regle_mention(faits) + _regle_rang(faits)
        + _regle_langue(faits, reference) + _regle_parcours(faits, reference)
    )
    return [p for p in tous if p.extrait.strip() and p.texte.strip()]


# ============================================================ persistance
def _exiger_tenant(db: Session) -> uuid.UUID:
    tid = tenant_courant(db)
    if tid is None:
        raise RuntimeError("Contexte bureau (tenant) manquant sur la session.")
    return tid


def vers_sortie(p: PointFort, cle_maitresse: bytes) -> PointFortSortie:
    return PointFortSortie(
        id=p.id,
        candidat_id=p.candidat_id,
        categorie=p.categorie,
        regle=p.regle,
        texte=dechiffrer_champ(cle_maitresse, p.tenant_id, _AAD_TEXTE, p.texte_chiffre) or "",
        document_id=p.document_id,
        page=p.page,
        extrait=dechiffrer_champ(cle_maitresse, p.tenant_id, _AAD_EXTRAIT, p.extrait_chiffre) or "",
        statut=p.statut,
        alerte=p.alerte,
        champ_fiche=p.champ_fiche,
        valeur_fiche=p.valeur_fiche,
        decide_par_id=p.decide_par_id,
        decide_le=p.decide_le,
        applique_le=p.applique_le,
    )


def _faits_confirmes(db: Session, candidat_id: uuid.UUID, cle: bytes) -> list[FaitConfirme]:
    lignes = db.scalars(
        select(ExtractionDocument)
        .where(ExtractionDocument.candidat_id == candidat_id)
        .order_by(ExtractionDocument.cree_le, ExtractionDocument.champ)
    )
    return [
        FaitConfirme(
            document_id=e.document_id,
            champ=e.champ,
            valeur=dechiffrer_champ(cle, e.tenant_id, _AAD_VALEUR, e.valeur_chiffree) or "",
            page=e.page,
            extrait=dechiffrer_champ(cle, e.tenant_id, "extraction_extrait", e.extrait_chiffre) or "",
        )
        for e in lignes
        if e.statut in STATUTS_APPLICABLES
    ]


def alerte_a_l_usage(db: Session, p: PointFort, cle: bytes, reference: date | None = None) -> str | None:
    """Alerte courante d'un point : pour un certificat, la validité est recalculée aujourd'hui à partir du
    type et de la date de passation de la pièce (jamais l'alerte stockée, qui a pu vieillir)."""
    if p.regle != "certificat_langue":
        return p.alerte
    champs = {f.champ: f.valeur for f in _faits_confirmes(db, p.candidat_id, cle) if f.document_id == p.document_id}
    if CERTIFICAT_TYPE not in champs and CERTIFICAT_DATE not in champs:
        return p.alerte
    type_cert = champs.get(CERTIFICAT_TYPE, "").strip().upper() or None
    _, alerte = evaluer_validite(type_cert, _date_ou_none(champs.get(CERTIFICAT_DATE)), reference or date.today())
    return alerte if alerte == ALERTE_EXPIRE else p.alerte


def _renseigner(p: PointFort, d: PointFortDeduit, tid: uuid.UUID, cle: bytes) -> None:
    p.texte_chiffre = chiffrer_champ(cle, tid, _AAD_TEXTE, d.texte) or ""
    p.extrait_chiffre = chiffrer_champ(cle, tid, _AAD_EXTRAIT, d.extrait) or ""
    p.page, p.alerte, p.document_id = d.page, d.alerte, d.document_id


def calculer_points_forts(
    db: Session,
    *,
    candidat_id: uuid.UUID,
    acteur_id: uuid.UUID,
    cle_maitresse: bytes,
    date_reference: date | None = None,
) -> ResultatDeductionsSortie:
    tid = _exiger_tenant(db)
    obtenir_candidat_orm(db, candidat_id)  # 404 hors bureau
    deduits = {
        d.cle: d for d in deduire(_faits_confirmes(db, candidat_id, cle_maitresse), date_reference or date.today())
    }
    existants = {p.cle: p for p in db.scalars(select(PointFort).where(PointFort.candidat_id == candidat_id))}
    crees = maj = retires = 0
    for cle, d in deduits.items():
        courant = existants.get(cle)
        if courant is None:
            p = PointFort(
                id=uuid.uuid4(), tenant_id=tid, candidat_id=candidat_id, cle=cle, categorie=d.categorie,
                regle=d.regle, statut=StatutPointFort.A_VERIFIER, champ_fiche=d.champ_fiche,
                valeur_fiche=d.valeur_fiche, texte_chiffre="", extrait_chiffre="", document_id=d.document_id,
            )
            _renseigner(p, d, tid, cle_maitresse)
            db.add(p)
            crees += 1
        else:
            change = (
                dechiffrer_champ(cle_maitresse, tid, _AAD_TEXTE, courant.texte_chiffre) != d.texte
                or dechiffrer_champ(cle_maitresse, tid, _AAD_EXTRAIT, courant.extrait_chiffre) != d.extrait
            )
            _renseigner(courant, d, tid, cle_maitresse)  # même fait : texte et alerte rafraîchis
            if courant.statut is StatutPointFort.CONFIRME and (change or d.alerte == ALERTE_EXPIRE):
                # certificat expiré, texte ou extrait modifié : la confirmation ne vaut plus (jamais de
                # réécriture silencieuse d'un point confirmé)
                courant.statut = StatutPointFort.A_VERIFIER
                courant.decide_par_id = courant.decide_le = None
                courant.applique_le = None
            maj += 1
    for cle, p in existants.items():
        if cle in deduits:
            continue
        if p.statut is StatutPointFort.A_VERIFIER:
            db.delete(p)
            retires += 1
        elif p.statut is StatutPointFort.CONFIRME:  # la preuve n'est plus confirmée
            p.statut, p.alerte = StatutPointFort.REJETE, ALERTE_PREUVE_INVALIDEE
            p.decide_par_id, p.decide_le = None, maintenant_utc()
            retires += 1
    audit.journaliser(
        db, "deductions.calculer", ResultatAudit.SUCCES, acteur_id=acteur_id,
        ressource_type="candidat", ressource_id=candidat_id,
        details={"nb_crees": crees, "nb_mis_a_jour": maj, "nb_retires": retires,
                 "nb_alertes": sum(d.alerte is not None for d in deduits.values())},
    )
    commit_ou_conflit(db, "Calcul concurrent des points forts : réessayez.")
    return ResultatDeductionsSortie(
        points_forts=lister_points_forts(db, candidat_id=candidat_id, cle_maitresse=cle_maitresse),
        nb_crees=crees, nb_mis_a_jour=maj, nb_retires=retires,
    )


def lister_points_forts(
    db: Session, *, candidat_id: uuid.UUID, cle_maitresse: bytes, statut: StatutPointFort | None = None
) -> list[PointFortSortie]:
    obtenir_candidat_orm(db, candidat_id)
    requete = select(PointFort).where(PointFort.candidat_id == candidat_id)
    if statut is not None:
        requete = requete.where(PointFort.statut == statut)
    return [vers_sortie(p, cle_maitresse) for p in db.scalars(requete.order_by(PointFort.cree_le, PointFort.regle, PointFort.id))]


def _obtenir(db: Session, candidat_id: uuid.UUID, point_id: uuid.UUID) -> PointFort:
    obtenir_candidat_orm(db, candidat_id)
    p = db.scalar(select(PointFort).where(PointFort.id == point_id, PointFort.candidat_id == candidat_id))
    if p is None:
        raise NonTrouve("Point fort introuvable.")
    return p


def decider_point_fort(
    db: Session, *, candidat_id: uuid.UUID, point_id: uuid.UUID, action: str, acteur_id: uuid.UUID, cle_maitresse: bytes
) -> PointFortSortie:
    """Décision humaine : `confirmer` ou `rejeter`. Un certificat expiré ne peut pas être confirmé."""
    p = _obtenir(db, candidat_id, point_id)
    if action == "confirmer":
        if p.alerte in (ALERTE_EXPIRE, ALERTE_PREUVE_INVALIDEE):
            raise DonneesInvalides("Ce point fort ne peut pas être confirmé : certificat expiré ou preuve invalidée.")
        p.statut = StatutPointFort.CONFIRME
    elif action == "rejeter":
        p.statut = StatutPointFort.REJETE
    else:  # pragma: no cover - les routes n'appellent que ces deux actions
        raise DonneesInvalides("Action inconnue.")
    p.decide_par_id, p.decide_le = acteur_id, maintenant_utc()
    audit.journaliser(
        db, f"deductions.{action}", ResultatAudit.SUCCES, acteur_id=acteur_id,
        ressource_type="point_fort", ressource_id=p.id,
        details={"candidat_id": str(candidat_id), "regle": p.regle},
    )
    db.commit()
    return vers_sortie(p, cle_maitresse)


def appliquer_niveau_a_fiche(
    db: Session, *, candidat_id: uuid.UUID, point_id: uuid.UUID, acteur_id: uuid.UUID, cle_maitresse: bytes
) -> ApplicationNiveauSortie:
    """Propose le niveau de langue du certificat à la fiche, APRÈS confirmation humaine du point.
    Une valeur différente déjà présente sur la fiche n'est jamais écrasée (conflit)."""
    p = _obtenir(db, candidat_id, point_id)
    if p.statut is not StatutPointFort.CONFIRME or not p.champ_fiche or not p.valeur_fiche:
        raise DonneesInvalides("Seul un niveau de langue confirmé par un humain peut être appliqué à la fiche.")
    if alerte_a_l_usage(db, p, cle_maitresse) == ALERTE_EXPIRE:
        raise DonneesInvalides("Certificat expiré : le niveau ne peut pas être appliqué à la fiche.")
    fiche = obtenir_candidat(db, candidat_id=candidat_id, cle_maitresse=cle_maitresse)
    actuel = getattr(fiche, p.champ_fiche)
    if actuel and str(actuel).upper() != p.valeur_fiche:
        raise Conflit("La fiche porte déjà un autre niveau : il n'est pas écrasé, corrigez-le à la main.")
    resultat = "deja_identique"
    if not actuel:
        modifier_candidat(
            db, candidat_id=candidat_id, donnees=CandidatModification(**{p.champ_fiche: p.valeur_fiche}),
            acteur_id=acteur_id, cle_maitresse=cle_maitresse,
        )
        resultat = "applique"
    p.applique_le = maintenant_utc()
    audit.journaliser(
        db, "deductions.appliquer_niveau", ResultatAudit.SUCCES, acteur_id=acteur_id,
        ressource_type="point_fort", ressource_id=p.id,
        details={"candidat_id": str(candidat_id), "champ": p.champ_fiche, "resultat": resultat},
    )
    db.commit()
    return ApplicationNiveauSortie(champ=p.champ_fiche, resultat=resultat, point_fort=vers_sortie(p, cle_maitresse))
