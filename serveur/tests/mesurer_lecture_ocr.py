"""Mesure la lecture OCR du corpus synthétique (outil de test ; ne modifie aucun parseur).

Usage : python tests/mesurer_lecture_ocr.py [--json chemin_fichier]

Pour chaque cas : LecteurDocumentLocal().lire_texte (une seule instance, moteur OCR partagé)
puis extraire_champs(famille, pages), comparés aux valeurs attendues (forme normalisée, casefold).
Issue par champ attendu :
- ok      : valeur validée et identique ;
- faux    : valeur validée mais différente (grave) ;
- refuse  : lue mais marquée invalide par le parseur (non fiable, à vérifier) ;
- absent  : aucun champ produit pour ce nom.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from app.services.extraction_champs import ChampLu, extraire_champs, normaliser_valeur  # noqa: E402
from app.services.lecture_documents import LecteurDocumentLocal  # noqa: E402
from tests.outils_corpus_ocr import DEGRADATIONS, FAMILLES, CasCorpus, fabriquer_corpus  # noqa: E402

LONGUEUR_EXTRAIT = 80
TOP_ECHECS = 15
OK, FAUX, REFUSE, ABSENT = "ok", "faux", "refuse", "absent"
CHAMPS_DATE_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class Constat:
    cas: str
    famille: str
    degradation: str
    champ: str
    attendu: str
    issue: str
    lu: str | None
    motif: str | None
    extrait: str
    cause: str


@dataclass
class Compte:
    attendus: int = 0
    ok: int = 0
    faux: int = 0
    refuse: int = 0
    absent: int = 0
    hors_attendu: int = 0

    def ajouter(self, issue: str) -> None:
        self.attendus += 1
        setattr(self, issue, getattr(self, issue) + 1)

    def taux(self) -> float:
        return self.ok / self.attendus if self.attendus else 0.0


@dataclass
class Bilan:
    constats: list[Constat] = field(default_factory=list)
    par_famille_degradation: dict[tuple[str, str], Compte] = field(default_factory=dict)
    par_famille: dict[str, Compte] = field(default_factory=dict)
    par_degradation: dict[str, Compte] = field(default_factory=dict)
    total: Compte = field(default_factory=Compte)
    erreurs_lecture: list[str] = field(default_factory=list)


# ----------------------------------------------------------------------------- comparaison
def _cle(champ: str, valeur: str) -> str:
    return normaliser_valeur(champ, valeur).casefold()


def _sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn")


def _compact(texte: str) -> str:
    return re.sub(r"\s+", "", _sans_accents(texte).casefold())


def _formes_attendues(champ: str, attendu: str) -> list[str]:
    """Formes sous lesquelles la valeur peut apparaître dans le texte OCR (pour le diagnostic)."""
    formes = [attendu]
    if CHAMPS_DATE_ISO.fullmatch(attendu):
        aaaa, mm, jj = attendu[:4], attendu[5:7], attendu[8:10]
        formes += [f"{jj}/{mm}/{aaaa}", f"{jj}.{mm}.{aaaa}", f"{jj}-{mm}-{aaaa}", aaaa[2:] + mm + jj]
    if re.fullmatch(r"\d+(\.\d+)?", attendu):
        formes += [attendu.replace(".", ","), f"{float(attendu):.2f}".replace(".", ",")]
    return formes


def _valeur_presente_dans_ocr(champ: str, attendu: str, ocr: str) -> bool:
    texte = _compact(ocr)
    return any(_compact(forme) in texte for forme in _formes_attendues(champ, attendu))


def _extrait_autour(ocr: str, attendu: str) -> str:
    """Fenêtre de 80 caractères de la ligne OCR la plus proche de la valeur attendue."""
    lignes = [ligne.strip() for ligne in ocr.splitlines() if ligne.strip()]
    if not lignes:
        return "(OCR vide)"
    cible = _sans_accents(attendu).casefold()
    meilleure, meilleur_debut, meilleure_taille = lignes[0], 0, -1
    for ligne in lignes:
        bas = _sans_accents(ligne).casefold()
        bloc = SequenceMatcher(None, bas, cible, autojunk=False).find_longest_match(0, len(bas), 0, len(cible))
        if bloc.size > meilleure_taille:
            meilleure, meilleur_debut, meilleure_taille = ligne, bloc.a, bloc.size
    debut = max(0, meilleur_debut - LONGUEUR_EXTRAIT // 2)
    return meilleure[debut : debut + LONGUEUR_EXTRAIT]


def _cause(issue: str, champ: str, attendu: str, lu: ChampLu | None, ocr: str) -> str:
    if issue == ABSENT:
        if _valeur_presente_dans_ocr(champ, attendu, ocr):
            return "valeur lue par l'OCR mais non rattachée par le parseur"
        return "OCR déformé : valeur absente du texte lu"
    if issue == REFUSE:
        return f"refusé par le parseur (motif {lu.motif if lu else '?'})"
    return "valeur validée mais différente (faux)"


# ----------------------------------------------------------------------------- évaluation d'un cas
def _evaluer_cas(cas: CasCorpus, lecteur: LecteurDocumentLocal, bilan: Bilan) -> tuple[list[Constat], int]:
    try:
        resultat = lecteur.lire_texte(cas.octets, cas.type_mime)
    except Exception as exc:  # seul le type d'exception est gardé : le message peut citer le contenu
        bilan.erreurs_lecture.append(f"{cas.nom} ({type(exc).__name__})")
        pages: list[tuple[int, str]] = []
    else:
        pages = [(p.numero, p.texte) for p in resultat.pages]
    ocr = "\n".join(texte for _, texte in pages)
    lus = {c.champ: c for c in extraire_champs(cas.famille, pages)} if pages else {}

    constats: list[Constat] = []
    for champ, attendu in cas.attendu.items():
        lu = lus.get(champ)
        if lu is None:
            issue = ABSENT
        elif not lu.valide:
            issue = REFUSE
        elif _cle(champ, lu.valeur) == _cle(champ, attendu):
            issue = OK
        else:
            issue = FAUX
        constats.append(
            Constat(
                cas=cas.nom, famille=cas.famille, degradation=cas.degradation, champ=champ, attendu=attendu,
                issue=issue, lu=lu.valeur if lu else None, motif=lu.motif if lu else None,
                extrait=_extrait_autour(ocr, attendu) if ocr else "(OCR vide)",
                cause=_cause(issue, champ, attendu, lu, ocr) if issue != OK else "",
            )
        )
    hors = sum(1 for champ, c in lus.items() if c.valide and champ not in cas.attendu)
    return constats, hors


def _enregistrer(bilan: Bilan, cas: CasCorpus, constats: list[Constat], hors: int) -> None:
    cle = (cas.famille, cas.degradation)
    comptes = (
        bilan.par_famille_degradation.setdefault(cle, Compte()),
        bilan.par_famille.setdefault(cas.famille, Compte()),
        bilan.par_degradation.setdefault(cas.degradation, Compte()),
        bilan.total,
    )
    for constat in constats:
        bilan.constats.append(constat)
        for compte in comptes:
            compte.ajouter(constat.issue)
    for compte in comptes:
        compte.hors_attendu += hors


# ----------------------------------------------------------------------------- affichage
def _pourcent(compte: Compte) -> str:
    return f"{compte.ok}/{compte.attendus} ({compte.taux() * 100:4.0f}%)"


def _tableau_taux(bilan: Bilan) -> list[str]:
    entete = f"{'famille':<17}" + "".join(f"{d:<19}" for d in DEGRADATIONS) + f"{'TOTAL':<19}"
    lignes = ["Taux de champs corrects (ok / attendus) par famille et dégradation", entete, "-" * len(entete)]
    for famille in FAMILLES:
        cellules = [
            _pourcent(bilan.par_famille_degradation.get((famille, d), Compte())).ljust(19) for d in DEGRADATIONS
        ]
        lignes.append(f"{famille:<17}" + "".join(cellules) + _pourcent(bilan.par_famille.get(famille, Compte())))
    lignes.append("-" * len(entete))
    cellules = [_pourcent(bilan.par_degradation.get(d, Compte())).ljust(19) for d in DEGRADATIONS]
    lignes.append(f"{'TOTAL':<17}" + "".join(cellules) + _pourcent(bilan.total))
    return lignes


def _tableau_fautes(bilan: Bilan) -> list[str]:
    entete = f"{'famille':<17}{'attendus':>9}{'ok':>6}{'FAUX':>7}{'refusés':>9}{'absents':>9}{'hors attendu':>14}"
    lignes = ["Fautes par famille (FAUX = lu mais différent, grave)", entete, "-" * len(entete)]
    for famille in [*FAMILLES, "TOTAL"]:
        c = bilan.total if famille == "TOTAL" else bilan.par_famille.get(famille, Compte())
        lignes.append(
            f"{famille:<17}{c.attendus:>9}{c.ok:>6}{c.faux:>7}{c.refuse:>9}{c.absent:>9}{c.hors_attendu:>14}"
        )
    return lignes


def _echecs(bilan: Bilan) -> list[str]:
    lignes = ["", "Liste complète des échecs (cas, champ, attendu, lu, extrait OCR)"]
    for c in bilan.constats:
        if c.issue == OK:
            continue
        lu = c.lu if c.lu is not None else "(absent)"
        lignes.append(
            f"- [{c.issue}] {c.cas} | {c.champ} | attendu={c.attendu!r} | lu={lu!r} | "
            f"extrait={c.extrait!r} | cause : {c.cause}"
        )
    return lignes


def _top_echecs(bilan: Bilan) -> list[str]:
    groupes: dict[tuple[str, str, str], list[Constat]] = defaultdict(list)
    for c in bilan.constats:
        if c.issue != OK:
            groupes[(c.famille, c.champ, c.cause)].append(c)
    classes = sorted(groupes.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:TOP_ECHECS]
    lignes = [f"", f"Top {TOP_ECHECS} des échecs les plus fréquents (famille, champ, cause apparente)"]
    for rang, ((famille, champ, cause), liste) in enumerate(classes, start=1):
        exemples = "; ".join(
            f"{c.cas}: attendu={c.attendu!r} lu={c.lu!r}" for c in liste[:2]
        )
        lignes.append(f"{rang:>2}. x{len(liste):<3} {famille}/{champ} : {cause}")
        lignes.append(f"      ex. {exemples}")
    return lignes


def _json(bilan: Bilan, duree_s: float) -> dict:
    def compte_dict(c: Compte) -> dict:
        return {**asdict(c), "taux_ok": round(c.taux(), 4)}

    return {
        "duree_s": round(duree_s, 1),
        "total": compte_dict(bilan.total),
        "par_famille": {f: compte_dict(c) for f, c in bilan.par_famille.items()},
        "par_degradation": {d: compte_dict(c) for d, c in bilan.par_degradation.items()},
        "par_famille_degradation": {
            f"{f}/{d}": compte_dict(c) for (f, d), c in bilan.par_famille_degradation.items()
        },
        "erreurs_lecture": bilan.erreurs_lecture,
        "constats": [asdict(c) for c in bilan.constats],
    }


def _configurer_sortie() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def main() -> int:
    _configurer_sortie()
    parseur = argparse.ArgumentParser(description="Mesure la lecture OCR du corpus synthétique.")
    parseur.add_argument("--json", metavar="FICHIER", help="écrit les chiffres et tous les constats en JSON")
    options = parseur.parse_args()

    cas_corpus = fabriquer_corpus()
    print(f"Corpus : {len(cas_corpus)} cas ({len(FAMILLES)} familles x {len(DEGRADATIONS)} dégradations)")
    lecteur = LecteurDocumentLocal()  # une seule instance : le moteur OCR est chargé une fois
    bilan = Bilan()
    debut = time.monotonic()
    for numero, cas in enumerate(cas_corpus, start=1):
        debut_cas = time.monotonic()
        constats, hors = _evaluer_cas(cas, lecteur, bilan)
        _enregistrer(bilan, cas, constats, hors)
        ok = sum(1 for c in constats if c.issue == OK)
        print(f"[{numero:>2}/{len(cas_corpus)}] {cas.nom:<32} {ok}/{len(constats)} ok  "
              f"({time.monotonic() - debut_cas:.1f} s)", flush=True)
    duree = time.monotonic() - debut

    print()
    for bloc in (_tableau_taux(bilan), [""], _tableau_fautes(bilan), _echecs(bilan), _top_echecs(bilan)):
        print("\n".join(bloc))
    if bilan.erreurs_lecture:
        print("\nCas en erreur de lecture (type d'exception seulement) : " + ", ".join(bilan.erreurs_lecture))
    print(f"\nDurée totale : {duree:.0f} s")

    if options.json:
        Path(options.json).write_text(json.dumps(_json(bilan, duree), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON écrit : {options.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
