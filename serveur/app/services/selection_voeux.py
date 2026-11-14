"""Sélection de vœux (max 7) selon les prérequis RÉELS des fiches du catalogue du bureau.

Filtres durs : candidatures fermées, date limite dépassée, niveau de diplôme, moyenne, langue
(`prerequis_formation`), domaine souhaité. Calendrier de la démarche via `echeances_demarche`.

Règles :
- R4 : une exigence INCONNUE (fiche) ou une donnée de profil ABSENTE ne vaut jamais « ok » : le vœu passe
  « à vérifier » avec la raison. Rien n'est complété par défaut.
- Un écart de langue d'UN niveau (ex. profil B2, exigence C1) ne donne jamais « réaliste » ni « sûr » :
  le vœu est « ambitieux » avec l'écart affiché. Deux niveaux d'écart ou plus : vœu exclu.
- R5 : le profil et les sorties ne contiennent aucune identité ; l'audit ne contient que des compteurs.
- Lecture seule : ce service ne crée aucun vœu (la création reste une action humaine via l'API des vœux).
"""

from __future__ import annotations

import calendar
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.modeles.journal_audit import ResultatAudit
from app.schemas.selection_voeux import (
    CritereSortie,
    ExigencesOfficielles,
    NiveauLangueProfil,
    ProfilEtudiant,
    ReponseSuggestions,
    VoeuExclu,
    VoeuSuggere,
)
from app.services import audit, catalogue_formations
from app.services import demarches_bureau as service_demarches
from app.services.candidats import obtenir_candidat_orm
from app.services.echeances_demarche import calculer_echeances
from app.services.fiche_formation import (
    CODE_DATE_LIMITE,
    CODE_LANGUE,
    CODE_MOYENNE,
    CODE_NIVEAU_ENTREE,
    FicheEntree,
    exigences_inconnues,
    normaliser,
)
from app.services.prerequis_formation import NIVEAUX_CECRL

# Source : config/demarches/campus_france.yaml (« validité TCF : 2 ans »).
VALIDITE_TCF_MOIS = 24
# Source : docs/ecoles_privees_france.md §1.4 (DELF et DALF acquis à vie).
CERTIFICATS_SANS_EXPIRATION = frozenset({"DELF", "DALF"})
# Écart de langue toléré comme « ambitieux » (au-delà : exclu) et marges « sûr » (réglages de classement,
# pas des exigences officielles).
ECART_LANGUE_AMBITIEUX_MAX = 1
MARGE_SURE_MOYENNE = 2.0
MAX_EXCLUS_RENVOYES = 100
ORDRE_CATEGORIE = {"sur": 0, "realiste": 1, "ambitieux": 2, "a_verifier": 3}
AVIS = (
    "Suggestions non contraignantes : aucun voeu n'a été créé. La création d'un voeu reste une action "
    "humaine. Toute exigence « à vérifier » doit être contrôlée sur la page officielle avant de s'y fier."
)

OK, ECART, KO, INCONNU, NON_APPLICABLE = "ok", "ecart", "ko", "inconnu", "non_applicable"


@dataclass(frozen=True)
class Critere:
    code: str
    resultat: str
    exigence: str
    donnee: str
    detail: str
    marge: float | None = None


def _ajouter_mois(depart: date, mois: int) -> date:
    total = depart.month - 1 + mois
    annee, mois_cible = depart.year + total // 12, total % 12 + 1
    return date(annee, mois_cible, min(depart.day, calendar.monthrange(annee, mois_cible)[1]))


def _fmt(valeur: float) -> str:
    return f"{valeur:g}".replace(".", ",")


# ----------------------------------------------------------------------------- critères


def _critere_langue(
    libelle: str,
    requis: str,
    langue: NiveauLangueProfil,
    *,
    aujourd_hui: date,
    date_rentree: date | None,
) -> Critere:
    code = libelle.lower()
    exigence = f"{libelle} {requis}"
    niveau = langue.niveau
    if niveau is None:
        return Critere(code, INCONNU, exigence, "non renseigné", f"Niveau de {code} du profil absent.")
    ecart = NIVEAUX_CECRL.index(requis) - NIVEAUX_CECRL.index(niveau)
    certificat = langue.certificat
    preuve = "certificat non renseigné"
    if certificat and certificat.type:
        preuve = (
            f"{certificat.type} du {certificat.date_obtention.isoformat()}"
            if certificat.date_obtention
            else f"{certificat.type} sans date"
        )
    donnee = f"{libelle} {niveau} ({preuve})"
    if ecart > ECART_LANGUE_AMBITIEUX_MAX:
        return Critere(code, KO, exigence, donnee, f"{libelle} : {ecart} niveaux d'écart (exigé {requis}, profil {niveau}).")
    if ecart >= 1:
        return Critere(
            code, ECART, exigence, donnee,
            f"{libelle} : exigé {requis}, profil {niveau} (1 niveau d'écart, à combler avant la date limite).",
        )
    motif = _motif_certificat_insuffisant(libelle, langue, aujourd_hui, date_rentree)
    if motif:
        return Critere(code, INCONNU, exigence, donnee, motif)
    return Critere(code, OK, exigence, donnee, f"{libelle} : exigé {requis}, profil {niveau}.", marge=float(-ecart))


def _motif_certificat_insuffisant(
    libelle: str, langue: NiveauLangueProfil, aujourd_hui: date, date_rentree: date | None
) -> str | None:
    """None si le niveau est justifié par un certificat daté et valide ; sinon la raison (« à vérifier »)."""
    certificat = langue.certificat
    if certificat is None or certificat.type is None:
        return f"Niveau de {libelle.lower()} déclaré sans certificat : justificatif à fournir."
    if certificat.date_obtention is None:
        return f"Date du certificat de {libelle.lower()} absente."
    if certificat.date_obtention > aujourd_hui:
        return f"Date du certificat de {libelle.lower()} postérieure à aujourd'hui : incohérente."
    if certificat.type in CERTIFICATS_SANS_EXPIRATION:
        return None
    if certificat.type == "TCF":
        expiration = _ajouter_mois(certificat.date_obtention, VALIDITE_TCF_MOIS)
        reference = date_rentree or aujourd_hui
        if expiration < reference:
            return (
                f"TCF du {certificat.date_obtention.isoformat()} expiré le {expiration.isoformat()} "
                f"(validité {VALIDITE_TCF_MOIS // 12} ans) avant le {reference.isoformat()} : à renouveler."
            )
        return None
    return f"Validité du certificat {certificat.type} non vérifiable : à contrôler."


def _critere_langues(
    fiche: FicheEntree, inconnues: list[str], profil: ProfilEtudiant, aujourd_hui: date
) -> list[Critere]:
    if CODE_LANGUE in inconnues:
        extrait = f" (texte relevé : {fiche.langue_texte[:150]})" if fiche.langue_texte else ""
        raison = (
            "Exigences de langue alternatives selon le parcours" if fiche.langue_ambigue
            else "Exigence de langue non lue sur la source"
        )
        return [Critere("langue", INCONNU, "à vérifier", "—", f"{raison}{extrait} : à vérifier sur la page officielle.")]
    criteres: list[Critere] = []
    if fiche.francais_min:
        criteres.append(_critere_langue("Français", fiche.francais_min, profil.francais,
                                        aujourd_hui=aujourd_hui, date_rentree=profil.date_rentree))
    if fiche.anglais_min:
        criteres.append(_critere_langue("Anglais", fiche.anglais_min, profil.anglais,
                                        aujourd_hui=aujourd_hui, date_rentree=profil.date_rentree))
    return criteres


def _critere_niveau(fiche: FicheEntree, inconnues: list[str], profil: ProfilEtudiant) -> Critere | None:
    if CODE_NIVEAU_ENTREE in inconnues:
        return Critere("niveau_diplome", INCONNU, "à vérifier", "—", "Niveau d'entrée non lu sur la source.")
    requis = fiche.niveau_entree_bac_plus
    if requis is None:
        return None
    exigence = f"entrée Bac +{requis} (diplôme Bac +{max(requis - 1, 0)} validé)"
    if profil.niveau_diplome_bac_plus is None:
        return Critere("niveau_diplome", INCONNU, exigence, "non renseigné", "Niveau de diplôme du profil absent.")
    donnee = f"Bac +{profil.niveau_diplome_bac_plus}"
    if profil.niveau_diplome_bac_plus < requis - 1:
        return Critere("niveau_diplome", KO, exigence, donnee,
                       f"Niveau de diplôme insuffisant (exigé {exigence}, profil {donnee}).")
    return Critere("niveau_diplome", OK, exigence, donnee, f"Niveau de diplôme conforme ({donnee}).")


def _critere_moyenne(fiche: FicheEntree, inconnues: list[str], profil: ProfilEtudiant) -> Critere | None:
    if CODE_MOYENNE in inconnues:
        return Critere("moyenne", INCONNU, "à vérifier", "—",
                       "Moyenne minimale (ou sa référence) non lue sur la source.")
    if fiche.moyenne_min is None:
        return None
    exigence = f"{_fmt(fiche.moyenne_min)}/20 ({fiche.moyenne_reference})"
    valeur = getattr(profil.moyennes, fiche.moyenne_reference or "", None)
    if valeur is None:
        return Critere("moyenne", INCONNU, exigence, "non renseignée",
                       f"Moyenne « {fiche.moyenne_reference} » du profil absente.")
    donnee = f"{_fmt(valeur)}/20"
    if valeur < fiche.moyenne_min:
        return Critere("moyenne", KO, exigence, donnee,
                       f"Moyenne insuffisante (exigé {exigence}, profil {donnee}).")
    return Critere("moyenne", OK, exigence, donnee, f"Moyenne conforme ({donnee}).",
                   marge=valeur - fiche.moyenne_min)


def _critere_calendrier(fiche: FicheEntree, inconnues: list[str], aujourd_hui: date) -> list[Critere]:
    criteres: list[Critere] = []
    if fiche.ferme:
        criteres.append(Critere("candidatures", KO, "ouvertes", "fermées", "Candidatures fermées d'après la fiche."))
    if CODE_DATE_LIMITE in inconnues:
        criteres.append(Critere("date_limite", INCONNU, "à vérifier", "—", "Date limite non lue sur la source."))
    elif fiche.date_limite is not None:
        reste = (fiche.date_limite - aujourd_hui).days
        exigence = f"candidature avant le {fiche.date_limite.isoformat()}"
        if reste < 0:
            criteres.append(Critere("date_limite", KO, exigence, f"aujourd'hui {aujourd_hui.isoformat()}",
                                    f"Date limite dépassée depuis {-reste} jour(s)."))
        else:
            criteres.append(Critere("date_limite", OK, exigence, f"{reste} jour(s) restants",
                                    f"Date limite dans {reste} jour(s)."))
    return criteres


def _critere_domaine(fiche: FicheEntree, profil: ProfilEtudiant) -> Critere | None:
    souhaites = {normaliser(d) for d in profil.domaines_souhaites if normaliser(d)}
    if not souhaites:
        return None
    donnee = ", ".join(profil.domaines_souhaites)
    if not fiche.domaines:
        return Critere("domaine", INCONNU, "à vérifier", donnee, "Domaine de la formation non lu sur la source.")
    if souhaites & {normaliser(d) for d in fiche.domaines}:
        return Critere("domaine", OK, ", ".join(fiche.domaines), donnee, "Domaine conforme au choix du profil.")
    return Critere("domaine", KO, ", ".join(fiche.domaines), donnee, "Domaine hors du choix du profil.")


# ----------------------------------------------------------------------------- évaluation


def _categorie(criteres: list[Critere], fiche: FicheEntree, profil: ProfilEtudiant) -> str:
    francais_sous_c1 = (
        fiche.priorite_c1
        and profil.francais.niveau is not None
        and NIVEAUX_CECRL.index(profil.francais.niveau) < NIVEAUX_CECRL.index("C1")
    )
    if francais_sous_c1 or any(c.resultat == ECART for c in criteres):
        return "ambitieux"
    if any(c.resultat == INCONNU for c in criteres):
        return "a_verifier"
    marges = [c for c in criteres if c.resultat == OK and c.marge is not None]
    confortables = all(
        (c.marge or 0) >= (MARGE_SURE_MOYENNE if c.code == "moyenne" else 1) for c in marges
    )
    return "sur" if marges and confortables else "realiste"


def _ecarts(criteres: list[Critere], fiche: FicheEntree, profil: ProfilEtudiant) -> list[str]:
    ecarts = [f"{c.detail}" for c in criteres if c.resultat in (ECART, INCONNU)]
    if (
        fiche.priorite_c1
        and profil.francais.niveau is not None
        and NIVEAUX_CECRL.index(profil.francais.niveau) < NIVEAUX_CECRL.index("C1")
    ):
        ecarts.append(f"Priorité aux candidats C1 (profil : français {profil.francais.niveau}).")
    return ecarts


def _exigences(fiche: FicheEntree, inconnues: list[str]) -> ExigencesOfficielles:
    return ExigencesOfficielles(
        niveau_entree=fiche.niveau_entree_libelle
        or (f"Bac +{fiche.niveau_entree_bac_plus}" if fiche.niveau_entree_bac_plus else None),
        francais_min=fiche.francais_min,
        anglais_min=fiche.anglais_min,
        priorite_c1=fiche.priorite_c1,
        moyenne_min=fiche.moyenne_min,
        moyenne_reference=fiche.moyenne_reference,
        date_limite=fiche.date_limite,
        pieces=list(fiche.pieces),
        url_officielle=fiche.url_officielle,
        date_releve=fiche.date_releve,
        exigences_a_verifier=inconnues,
    )


def _echeances_depassees(echeances: list[dict] | None) -> list[str]:
    return [
        f"Échéance de la démarche dépassée : {e['libelle']}."
        for e in echeances or []
        if e.get("statut") == "depassee"
    ]


def selectionner(
    fiches: list[tuple[uuid.UUID, FicheEntree]],
    profil: ProfilEtudiant,
    *,
    aujourd_hui: date,
    max_voeux: int = 7,
    echeances: list[dict] | None = None,
) -> ReponseSuggestions:
    """Évalue chaque fiche, exclut les incompatibilités certaines, classe le reste (max `max_voeux`)."""
    retenues: list[tuple[tuple, VoeuSuggere]] = []
    exclus: list[VoeuExclu] = []
    raisons_demarche = _echeances_depassees(echeances)

    for fiche_id, fiche in fiches:
        inconnues = exigences_inconnues(fiche)
        criteres: list[Critere] = []
        criteres += _critere_calendrier(fiche, inconnues, aujourd_hui)
        criteres += [c for c in (_critere_niveau(fiche, inconnues, profil),) if c]
        criteres += _critere_langues(fiche, inconnues, profil, aujourd_hui)
        criteres += [c for c in (_critere_moyenne(fiche, inconnues, profil),) if c]
        criteres += [c for c in (_critere_domaine(fiche, profil),) if c]

        refus = [c.detail for c in criteres if c.resultat == KO]
        if refus:
            exclus.append(VoeuExclu(fiche_id=fiche_id, etablissement=fiche.etablissement,
                                    intitule=fiche.intitule, raisons=refus))
            continue

        raisons = [c.detail for c in criteres if c.resultat == INCONNU] + raisons_demarche
        categorie = _categorie(criteres, fiche, profil)
        if not criteres:
            raisons.append("Aucun critère évaluable : tout est à vérifier sur la page officielle.")
        if raisons and categorie in ("sur", "realiste"):
            categorie = "a_verifier"
        justification = " ; ".join(
            f"{c.code} : exigence {c.exigence}, profil {c.donnee} -> {c.resultat}" for c in criteres
        ) or "Aucun critère évaluable : tout est à vérifier."
        proposition = VoeuSuggere(
            fiche_id=fiche_id,
            rang=0,
            etablissement=fiche.etablissement,
            intitule=fiche.intitule,
            categorie=categorie,
            a_verifier=bool(raisons),
            raisons_a_verifier=raisons,
            justification=justification,
            ecarts=_ecarts(criteres, fiche, profil) + raisons_demarche,
            exigences=_exigences(fiche, inconnues),
            criteres=[
                CritereSortie(critere=c.code, resultat=c.resultat, exigence_officielle=c.exigence,
                              donnee_profil=c.donnee, detail=c.detail)
                for c in criteres
            ],
        )
        cle = (
            bool(raisons),
            ORDRE_CATEGORIE[categorie],
            len(raisons),  # à catégorie égale, les fiches les mieux renseignées d'abord
            fiche.date_limite or date.max,
            normaliser(fiche.etablissement),
            normaliser(fiche.intitule),
        )
        retenues.append((cle, proposition))

    retenues.sort(key=lambda couple: couple[0])
    gardees = [
        p.model_copy(update={"rang": rang}) for rang, (_, p) in enumerate(retenues[:max_voeux], start=1)
    ]
    avertissements: list[str] = []
    if not fiches:
        avertissements.append("Catalogue vide pour ce bureau : importer les fiches avant de chercher.")
    avertissements += [a for a in raisons_demarche]
    return ReponseSuggestions(
        propositions=gardees,
        exclus=exclus[:MAX_EXCLUS_RENVOYES],
        nb_fiches_examinees=len(fiches),
        nb_non_retenues_faute_de_place=max(len(retenues) - max_voeux, 0),
        calendrier_demarche=echeances,
        avertissements=avertissements,
        avis=AVIS,
    )


# ----------------------------------------------------------------------------- accès base


def _completer_profil(db: Session, profil: ProfilEtudiant, candidat_id: uuid.UUID) -> ProfilEtudiant:
    """Complète les niveaux de langue ABSENTS du profil avec ceux du candidat (404 hors bureau)."""
    candidat = obtenir_candidat_orm(db, candidat_id)
    maj: dict[str, Any] = {}
    for champ, valeur in (("francais", candidat.niveau_francais), ("anglais", candidat.niveau_anglais)):
        courant: NiveauLangueProfil = getattr(profil, champ)
        if courant.niveau is None and valeur in NIVEAUX_CECRL:
            maj[champ] = courant.model_copy(update={"niveau": valeur})
    return profil.model_copy(update=maj) if maj else profil


def _echeances_demarche(
    db: Session, dossier_demarches: Path, code: str, profil: ProfilEtudiant, aujourd_hui: date
) -> list[dict]:
    definition, _meta = service_demarches.obtenir(db, dossier_demarches, code)  # 404 si inconnue
    return calculer_echeances(definition, aujourd_hui=aujourd_hui, date_rentree=profil.date_rentree)


def suggerer_voeux(
    db: Session,
    *,
    profil: ProfilEtudiant,
    acteur_id: uuid.UUID,
    dossier_demarches: Path,
    candidat_id: uuid.UUID | None = None,
    code_demarche: str | None = None,
    max_voeux: int = 7,
    aujourd_hui: date | None = None,
) -> ReponseSuggestions:
    """Lecture seule : ne crée ni ne modifie aucun vœu ; seule une trace d'audit (compteurs) est écrite."""
    jour = aujourd_hui or date.today()
    if candidat_id is not None:
        profil = _completer_profil(db, profil, candidat_id)  # 404 si hors bureau
    echeances = (
        _echeances_demarche(db, dossier_demarches, code_demarche, profil, jour) if code_demarche else None
    )
    reponse = selectionner(
        catalogue_formations.charger_fiches(db),
        profil,
        aujourd_hui=jour,
        max_voeux=max_voeux,
        echeances=echeances,
    )
    audit.journaliser(
        db,
        "voeux.suggestions",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="fiches_formations",
        details={
            "nb_fiches": reponse.nb_fiches_examinees,
            "nb_propositions": len(reponse.propositions),
            "nb_a_verifier": sum(1 for p in reponse.propositions if p.a_verifier),
            "nb_exclus": len(reponse.exclus),
            "avec_candidat": candidat_id is not None,
            "avec_demarche": code_demarche is not None,
        },
    )
    db.commit()
    return reponse
