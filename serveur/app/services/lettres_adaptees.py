"""Adaptation de la lettre de motivation à CHAQUE formation (phase P5).

Entrées (toutes issues du dossier, jamais inventées, règle 4) :
- points forts CONFIRMÉS (non expirés) avec leur pièce justificative (`deductions_dossier`) ;
- projet professionnel VALIDÉ (jamais un brouillon) ;
- fiche officielle du catalogue correspondant au vœu : spécificités, exigences ;
- écart profil/exigences calculé par `selection_voeux` (reconnu honnêtement dans la lettre).

Contrôle post-génération (réutilise `projet_professionnel.controler_texte`) : chiffre, note, niveau,
certificat, diplôme, établissement ou intitulé cité mais absent des faits fournis ; moins de deux
éléments propres à la formation ou de deux faits du dossier cités ; écart non mentionné ; texte non
français ; lettre quasi identique à celle d'un autre vœu. Tout élément bloque la validation : un
marqueur « [À COMPLÉTER ... ] » est ajouté au texte (mécanisme de `voeux.valider_voeu`).

Limites : contrôle lexical (nombres en lettres non détectés) ; non rejoué après une édition humaine.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modeles.document import DocumentCandidat
from app.modeles.point_fort import PointFort, ProjetProfessionnel, StatutPointFort, StatutProjet
from app.modeles.voeu_formation import MAX_CARACTERES_MOTIVATION
from app.core.chiffrement import dechiffrer_champ
from app.schemas.selection_voeux import NiveauLangueProfil, ProfilEtudiant
from app.services import catalogue_formations
from app.services.deductions_dossier import (
    ALERTE_EXPIRE,
    CATEGORIE_LANGUE,
    CATEGORIE_PARCOURS,
    vers_sortie,
)
from app.services.fiche_formation import FicheEntree, normaliser
from app.services.lettres_motivation import FaitsParcours, VoeuPourLettre
from app.services.prerequis_formation import NIVEAUX_CECRL
from app.services.projet_professionnel import _AAD_TEXTE, _RE_MARQUEUR, controler_texte
from app.services.selection_voeux import selectionner

CARACTERES_PAR_PAGE_A4 = 3000
# Consigne du propriétaire : l'Inalco demande une lettre d'une page A4.
LIMITES_PAR_ETABLISSEMENT = {"inalco": CARACTERES_PAR_PAGE_A4}
RESERVE_MARQUEUR = 60  # place gardée pour le marqueur de blocage ajouté en fin de lettre
SEUIL_SIMILARITE = 0.7  # « quasi identique » ; deux formations distinctes donnent ~0.5 (faits du dossier communs)
LONGUEUR_PROJET_MAX = 800
MARQUEUR_COURT = "[À COMPLÉTER : vérifier les éléments signalés.]"

_RE_PAGES = re.compile(r"(\d+)\s*pages?\s*(?:a4|A4)|(?:a4|A4)\s*[:(]?\s*(\d+)\s*pages?", re.IGNORECASE)
_RE_ECART = re.compile(r"(Français|Anglais).*?exigé ([ABC][12]), profil ([ABC][12])")
_PREFIXES_ECART = ("Priorité", "Niveau de diplôme insuffisant", "Moyenne insuffisante")
_MOTS_ORGANISME = ("Université", "Universite", "École", "Ecole", "Institut", "Faculté", "Faculte",
                   "Lycée", "Lycee", "IUT", "INSA", "Polytech", "Inalco", "INALCO")
_CONNECTEURS = {"de", "du", "des", "la", "le", "les", "et", "d", "l"}
_STOP_FR = {"le", "la", "les", "de", "des", "du", "et", "je", "mon", "ma", "mes", "une", "un", "pour",
            "que", "qui", "dans", "est", "en", "au", "avec", "cette"}
_STOP_EN = {"the", "and", "of", "to", "is", "my", "with", "for", "that", "this", "in", "are", "have"}


@dataclass(frozen=True)
class ContexteLettre:
    voeu: VoeuPourLettre
    faits: FaitsParcours
    faits_texte: str
    distinctifs: list[str]
    limite: int
    ecarts_niveaux: list[tuple[str, str]]  # (niveau du dossier, niveau exigé)
    elements_amont: list[str] = field(default_factory=list)
    nb_faits_dossier: int = 0
    fiche_trouvee: bool = False


# ------------------------------------------------------------------ utilitaires purs
def _norm(texte: str) -> str:
    sans = "".join(c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9+']+", " ", sans.lower().replace("’", "'")).split())


def limite_caracteres(fiche: FicheEntree | None, etablissement: str) -> int:
    """Limite de la lettre : 4000 (portail), réduite par la contrainte de la fiche (1 page A4 ≈ 3000)."""
    limite = MAX_CARACTERES_MOTIVATION
    nom = normaliser(etablissement)
    for cle, valeur in LIMITES_PAR_ETABLISSEMENT.items():
        if cle in nom:
            limite = min(limite, valeur)
    for piece in (fiche.pieces if fiche else []):
        m = _RE_PAGES.search(piece)
        if m and "lettre" in normaliser(piece):
            limite = min(limite, int(m.group(1) or m.group(2)) * CARACTERES_PAR_PAGE_A4)
    return limite


def lignes_officielles(fiche: FicheEntree) -> list[str]:
    """Spécificités lues sur la fiche (rien d'absent n'est ajouté)."""
    lignes = [f"formation « {fiche.intitule} » à {fiche.etablissement}"]
    entree = fiche.niveau_entree_libelle or (
        f"Bac +{fiche.niveau_entree_bac_plus}" if fiche.niveau_entree_bac_plus else None)
    if entree:
        lignes.append(f"niveau d'entrée {entree}")
    if fiche.francais_min:
        lignes.append(f"niveau de français exigé {fiche.francais_min}")
    if fiche.anglais_min:
        lignes.append(f"niveau d'anglais exigé {fiche.anglais_min} (formation comportant de l'anglais)")
    if fiche.priorite_c1:
        lignes.append("priorité aux candidats de niveau C1")
    if fiche.domaines:
        lignes.append("domaines : " + ", ".join(fiche.domaines))
    return lignes


def _jetons(texte: str) -> set[str]:
    return {j for j in _norm(texte).replace("'", " ").split() if len(j) >= 4 or j.isdigit()}


def _fait_cite(fait: str, texte_norm: str) -> bool:
    jetons = _jetons(re.sub(r"\(pièce[^)]*\)", "", fait))
    if not jetons:
        return False
    return sum(1 for j in jetons if re.search(rf"(?<![a-z0-9]){re.escape(j)}(?![a-z0-9])", texte_norm)) / len(jetons) >= 0.6


def _organismes(texte: str) -> list[str]:
    """Noms d'organismes cités (« Université de Lorraine ») : mot-clé puis mots capitalisés/connecteurs."""
    trouves: list[str] = []
    mots = list(re.finditer(r"[\w\-]+", texte))
    i = 0
    while i < len(mots):
        if mots[i].group() not in _MOTS_ORGANISME:
            i += 1
            continue
        fin, j, derniere_cap = i, i + 1, i
        while j < len(mots) and texte[mots[j - 1].end():mots[j].start()].strip(" ") == "" \
                and "\n" not in texte[mots[j - 1].end():mots[j].start()]:
            mot = mots[j].group().strip("'’-")
            if mot[:1].isupper():
                derniere_cap = j
            elif mot.lower() not in _CONNECTEURS:
                break
            j += 1
        fin = derniere_cap
        if fin > i:
            trouves.append(texte[mots[i].start():mots[fin].end()])
        i = max(j, i + 1)
    return trouves


def _est_francais(texte: str) -> bool:
    mots = _norm(texte).replace("'", " ").split()
    return sum(m in _STOP_FR for m in mots) >= sum(m in _STOP_EN for m in mots)


def _corps(texte: str) -> str:
    return _RE_MARQUEUR.sub(" ", texte)


def similarite(a: str, b: str) -> float:
    """Jaccard sur les suites de 3 mots (0 = rien en commun, 1 = identiques). Marqueurs ignorés."""
    def ensemble(t: str) -> set[tuple[str, ...]]:
        mots = _norm(_corps(t)).split()
        return {tuple(mots[i:i + 3]) for i in range(max(len(mots) - 2, 0))}
    ea, eb = ensemble(a), ensemble(b)
    return len(ea & eb) / len(ea | eb) if ea and eb else 0.0


def controler_lettre(texte: str, ctx: ContexteLettre) -> list[str]:
    """Éléments à vérifier (liste vide = lettre conforme)."""
    corps = _corps(texte)
    faits_norm = _norm(ctx.faits_texte)
    texte_norm = _norm(corps)
    elements = [e for e in controler_texte(texte, ctx.faits_texte) if not e.startswith("Des marqueurs")]
    for org in _organismes(corps):
        if _norm(org) not in faits_norm:
            elements.append(f"Établissement « {org} » absent des faits fournis.")
    for titre in re.findall(r"«\s*([^»]{3,200}?)\s*»", corps):
        if _norm(titre) not in faits_norm:
            elements.append(f"Intitulé « {titre} » absent des faits fournis.")
    if sum(1 for d in ctx.distinctifs if _norm(d) and _norm(d) in texte_norm) < min(2, len(ctx.distinctifs)):
        elements.append("La lettre cite moins de deux éléments propres à cette formation.")
    faits = [*ctx.faits.parcours, *ctx.faits.points_forts, *ctx.faits.langues]
    if len(faits) < 2:
        elements.append("Moins de deux faits vérifiables dans le dossier : lettre à compléter.")
    elif sum(_fait_cite(f, texte_norm) for f in faits) < 2:
        elements.append("La lettre cite moins de deux faits vérifiables du dossier.")
    for profil, requis in ctx.ecarts_niveaux:
        if profil.lower() not in texte_norm.split() or requis.lower() not in texte_norm.split():
            elements.append(f"L'écart de niveau (dossier {profil}, exigé {requis}) n'est pas reconnu dans la lettre.")
    if not _est_francais(corps):
        elements.append("La lettre ne semble pas rédigée en français.")
    return elements


def avec_marqueur(texte: str, elements: list[str]) -> str:
    """Ajoute un marqueur bloquant (détail si la place le permet, sinon version courte)."""
    if not elements:
        return texte
    detail = "[À COMPLÉTER : vérifier avant validation. " + " ".join(elements[:3]) + "]"
    marqueur = detail if len(texte) + 2 + len(detail) <= MAX_CARACTERES_MOTIVATION else MARQUEUR_COURT
    return f"{texte}\n\n{marqueur}"


# ------------------------------------------------------------------ accès dossier
def _points_confirmes(db: Session, candidat_id: uuid.UUID, cle: bytes) -> list[tuple[PointFort, str, str]]:
    lignes = db.scalars(
        select(PointFort).where(PointFort.candidat_id == candidat_id,
                                PointFort.statut == StatutPointFort.CONFIRME)
        .order_by(PointFort.cree_le, PointFort.id)
    )
    types = {d.id: d.type_piece for d in db.scalars(select(DocumentCandidat).where(
        DocumentCandidat.candidat_id == candidat_id))}
    sortie = []
    for p in lignes:
        if p.alerte == ALERTE_EXPIRE:
            continue
        piece = str(getattr(types.get(p.document_id), "value", types.get(p.document_id)) or "dossier")
        sortie.append((p, vers_sortie(p, cle).texte, piece.replace("_", " ")))
    return sortie


def _projet_valide(db: Session, candidat_id: uuid.UUID, cle: bytes) -> str | None:
    p = db.scalar(select(ProjetProfessionnel).where(ProjetProfessionnel.candidat_id == candidat_id))
    if p is None or p.statut is not StatutProjet.VALIDE:
        return None
    texte = dechiffrer_champ(cle, p.tenant_id, _AAD_TEXTE, p.texte_chiffre) or ""
    reste = [par for par in re.split(r"\n\s*\n", _RE_MARQUEUR.sub("", texte))
             if par.strip() and not par.strip().startswith(_REPRISES_FAITS)]
    return _tronquer("\n\n".join(par.strip() for par in reste)) or None


# Paragraphes du projet qui reprennent seulement les faits (déjà présents dans la lettre).
_REPRISES_FAITS = ("Mon parcours", "Mes acquis", "Mes langues")


def _tronquer(texte: str) -> str:
    if len(texte) <= LONGUEUR_PROJET_MAX:
        return texte
    coupe = texte[:LONGUEUR_PROJET_MAX]
    fin = max(coupe.rfind(". "), coupe.rfind(".\n"))
    return coupe[:fin + 1] if fin > 0 else coupe


def _fiche_du_voeu(db: Session, intitule: str, etablissement: str, url: str | None) -> FicheEntree | None:
    fiches = [f for _, f in catalogue_formations.charger_fiches(db)]
    cible = (normaliser(etablissement), normaliser(intitule))
    for f in fiches:
        if (normaliser(f.etablissement), normaliser(f.intitule)) == cible:
            return f
    if url:
        return next((f for f in fiches if f.url_officielle == url), None)
    return None


def _langue_cible(fait: str, langue: str) -> bool:
    return normaliser(langue) in normaliser(fait).split()


def _ecarts(fiche: FicheEntree, nf: str | None, na: str | None, jour: date) -> tuple[list[str], list[tuple[str, str]], list[str]]:
    """(phrases d'écart, couples (niveau dossier, exigé), éléments à vérifier) selon `selection_voeux`."""
    profil = ProfilEtudiant(francais=NiveauLangueProfil(niveau=nf), anglais=NiveauLangueProfil(niveau=na))
    rep = selectionner([(uuid.uuid4(), fiche)], profil, aujourd_hui=jour)
    brut = (rep.propositions[0].ecarts if rep.propositions else
            (rep.exclus[0].raisons if rep.exclus else []))
    lignes = [e for e in brut if _RE_ECART.search(e) or e.startswith(_PREFIXES_ECART)]
    phrases, couples = [], []
    for ligne in lignes:
        m = _RE_ECART.search(ligne)
        if m:
            phrases.append(f"mon niveau actuel en {m.group(1).lower()} est {m.group(3)}, "
                           f"alors que la formation exige {m.group(2)}")
            couples.append((m.group(3), m.group(2)))
        else:
            phrases.append(ligne.rstrip("."))
    elements = [f"Écart profil/exigences à discuter avec le candidat : {l}" for l in lignes]
    if rep.exclus and not rep.propositions:
        elements.append("La sélection exclurait ce vœu (incompatibilité certaine) : à confirmer.")
    return phrases, couples, elements


def construire_contexte(
    db: Session, *, candidat, voeu, faits_manuels: FaitsParcours, cle: bytes, aujourd_hui: date
) -> ContexteLettre:
    """Assemble tout ce qui alimente la lettre d'un vœu. `candidat` : sortie déchiffrée, `voeu` : ORM."""
    elements: list[str] = []
    parcours: list[str] = []
    forts: list[str] = []
    langues: list[str] = []
    niveaux = {"niveau_francais": candidat.niveau_francais, "niveau_anglais": candidat.niveau_anglais}
    for p, texte, piece in _points_confirmes(db, voeu.candidat_id, cle):
        ligne = f"{texte} (pièce : {piece})"
        {CATEGORIE_PARCOURS: parcours, CATEGORIE_LANGUE: langues}.get(p.categorie, forts).append(ligne)
        if p.champ_fiche in niveaux and not niveaux[p.champ_fiche]:
            niveaux[p.champ_fiche] = p.valeur_fiche
    nb_dossier = len(parcours) + len(forts) + len(langues)
    if nb_dossier == 0:
        elements.append("Aucun point fort confirmé dans le dossier : seuls les faits fournis à la main sont utilisés.")
    parcours += [x for x in faits_manuels.parcours if x not in parcours]
    forts += [x for x in faits_manuels.points_forts if x not in forts]
    langues += [x for x in faits_manuels.langues if x not in langues]

    projet = _projet_valide(db, voeu.candidat_id, cle)
    if projet is None:
        projet = faits_manuels.projet
        elements.append("Projet professionnel non validé : non utilisé (sauf texte fourni à la main).")

    fiche = _fiche_du_voeu(db, voeu.intitule, voeu.etablissement, voeu.url_source)
    specif = ([f"raison indiquée pour ce choix : {voeu.justification}"] if voeu.justification else [])
    ecarts: list[str] = []
    couples: list[tuple[str, str]] = []
    axes: list[str] = []
    distinctifs = [voeu.intitule, voeu.etablissement]
    if fiche is None:
        elements.append("Fiche de formation absente du catalogue : informations officielles non disponibles.")
    else:
        specif += lignes_officielles(fiche)
        distinctifs += [*fiche.domaines]
        nf = niveaux["niveau_francais"] if niveaux["niveau_francais"] in NIVEAUX_CECRL else None
        na = niveaux["niveau_anglais"] if niveaux["niveau_anglais"] in NIVEAUX_CECRL else None
        ecarts, couples, extra = _ecarts(fiche, nf, na, aujourd_hui)
        elements += extra
        for langue, requis in (("Français", fiche.francais_min), ("Anglais", fiche.anglais_min)):
            if requis:
                axes += [f"{f} (la formation exige {langue.lower()} {requis})"
                         for f in [*langues, *forts, *parcours] if _langue_cible(f, langue)][:1]
        # Les faits qui répondent aux exigences passent en tête.
        langues.sort(key=lambda f: not any(_langue_cible(f, l) for l, r in
                                           (("Français", fiche.francais_min), ("Anglais", fiche.anglais_min)) if r))
    limite = limite_caracteres(fiche, voeu.etablissement)
    faits = FaitsParcours(parcours=parcours, points_forts=forts, langues=langues, projet=projet,
                          remarques=faits_manuels.remarques)
    texte_faits = "\n".join([*parcours, *forts, *langues, projet or "", voeu.intitule, voeu.etablissement,
                             voeu.niveau, *specif, *ecarts, *axes, faits_manuels.remarques or ""])
    return ContexteLettre(
        voeu=VoeuPourLettre(intitule=voeu.intitule, etablissement=voeu.etablissement, niveau=voeu.niveau,
                            justification=" ; ".join(specif) or None, specificites=specif,
                            ecarts=ecarts, axes=axes),
        faits=faits, faits_texte=texte_faits, distinctifs=distinctifs, limite=limite,
        ecarts_niveaux=couples, elements_amont=elements, nb_faits_dossier=nb_dossier,
        fiche_trouvee=fiche is not None,
    )
