"""Vérification des prérequis de langue des vœux sur le portail Études en France (LECTURE SEULE).

Utilisé par le Co-Pilote Playwright AVANT tout ajout au panier, la page étant déjà connectée au
vrai portail. Pour chaque vœu :

1. recherche de la formation dans le catalogue (`/catalogue-formations`, champ « Libellé de la
   formation », Entrée) avec correspondance STRICTE de l'intitulé ET de l'établissement (normalisés) ;
2. lecture du JSON de la fiche par `fetch` GET (jamais de POST, jamais d'écriture) ;
3. analyse des exigences de langue (prérequis + procédure d'inscription) via le service
   `app.services.prerequis_formation`, puis évaluation face au niveau du candidat.

Règles : R4 (aucune valeur inventée : niveau absent => « inconnu »), R5 (aucune donnée personnelle
dans les messages renvoyés ; seuls `voeu_id` et des libellés de statut sont utilisés).
Aucun clic sur un bouton d'action, aucune case cochée, aucune soumission.
"""

from __future__ import annotations

import html as _html
import re
import unicodedata
from typing import Any
from urllib.parse import quote

from playwright.sync_api import Page

SELECTEUR_LIEN_RESULTAT = 'a[href^="/catalogue-formations/formation/"]'
LIBELLE_CHAMP_RECHERCHE = "Libellé de la formation"
PATRON_HREF_FORMATION = re.compile(r"^/catalogue-formations/formation/([^/?#]+)/site/([^/?#]+)")
PATRON_BALISE = re.compile(r"<[^>]+>")
DELAI_RESULTATS_MS = 1500

STATUT_OK = "ok"
STATUT_INSUFFISANT = "insuffisant"
STATUT_INCONNU = "inconnu"
STATUT_INTROUVABLE = "introuvable"
STATUT_AMBIGU = "ambigu"
STATUT_ERREUR = "erreur"

_STATUTS_ADEQUATION = {STATUT_OK, STATUT_INSUFFISANT, STATUT_INCONNU}


def normaliser_texte(texte: str | None) -> str:
    """Minuscule, sans accents, ponctuation réduite à des espaces (même style que panier_voeux)."""
    brut = unicodedata.normalize("NFKD", texte or "")
    sans_accents = "".join(c for c in brut if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", sans_accents.lower()).strip()


def texte_depuis_html(valeur: Any) -> str:
    """Transforme un fragment HTML de fiche en texte brut lisible."""
    if not valeur:
        return ""
    avec_retours = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</div>", "\n", str(valeur))
    sans_balises = PATRON_BALISE.sub(" ", avec_retours)
    texte = _html.unescape(sans_balises)
    lignes = [re.sub(r"\s+", " ", ligne).strip() for ligne in texte.split("\n")]
    return "\n".join(ligne for ligne in lignes if ligne)


def _charger_analyseur(analyseur: Any | None) -> Any:
    """Analyseur injecté (tests) ou module du service, importé à la demande."""
    if analyseur is not None:
        return analyseur
    from app.services import prerequis_formation  # import différé

    return prerequis_formation


def _resultat_vide(voeu: dict[str, Any]) -> dict[str, Any]:
    return {
        "voeu_id": str(voeu.get("voeu_id") or ""),
        "intitule": str(voeu.get("intitule") or ""),
        "etablissement": str(voeu.get("etablissement") or ""),
        "statut": STATUT_ERREUR,
        "francais_min": None,
        "anglais_min": None,
        "priorite_c1": False,
        "niveaux_disponibles": [],
        "dates_limite": [],
        "couts": [],
        "ferme": False,
        "messages": [],
    }


_JS_LIENS_RESULTATS = """(els) => {
    const cartes = [];
    return els.map(e => {
        const carte = e.closest("li, article, tr, [class*='resultat'], [class*='result']") || e.parentElement || e;
        let indice = cartes.indexOf(carte);
        if (indice < 0) { cartes.push(carte); indice = cartes.length - 1; }
        return {
            href: e.getAttribute("href") || "",
            texte: e.innerText || e.textContent || "",
            lignes: (carte.innerText || "").split("\\n"),
            carte: indice
        };
    });
}"""


def _rechercher_formation(page: Page, intitule: str, etablissement: str) -> tuple[str, tuple[str, str] | None]:
    """Retourne (statut, (idFormation, idSite)) avec statut ok | introuvable | ambigu | erreur."""
    champ = page.get_by_label(LIBELLE_CHAMP_RECHERCHE, exact=True)
    champ.fill(intitule, timeout=3000)
    champ.press("Enter")
    try:
        page.locator(SELECTEUR_LIEN_RESULTAT).first.wait_for(state="attached", timeout=DELAI_RESULTATS_MS)
    except Exception:  # noqa: BLE001 — aucun résultat : traité comme « introuvable » ci-dessous
        pass
    liens = page.locator(SELECTEUR_LIEN_RESULTAT).evaluate_all(_JS_LIENS_RESULTATS)

    cible_intitule = normaliser_texte(intitule)
    cible_etablissement = normaliser_texte(etablissement)
    correspondances: list[tuple[int, str, str]] = []
    for lien in liens or []:
        if normaliser_texte(lien.get("texte")) != cible_intitule:
            continue
        lignes = {normaliser_texte(ligne) for ligne in lien.get("lignes") or [] if ligne.strip()}
        if cible_etablissement not in lignes:
            continue
        match = PATRON_HREF_FORMATION.match(str(lien.get("href") or ""))
        if not match:
            continue
        correspondances.append((int(lien.get("carte") or 0), match.group(1), match.group(2)))

    if not correspondances:
        return STATUT_INTROUVABLE, None
    cartes_distinctes = {c for c, _, _ in correspondances}
    identifiants_distincts = {(i, s) for _, i, s in correspondances}
    if len(cartes_distinctes) > 1 or len(identifiants_distincts) > 1:
        return STATUT_AMBIGU, None
    return STATUT_OK, next(iter(identifiants_distincts))


def _lire_fiche(page: Page, id_formation: str, id_site: str) -> dict[str, Any]:
    """GET uniquement, sur l'API de fiche du portail. Retourne le JSON ou {'__erreur': code}."""
    chemin = (
        f"/parcours-api/espace-etudiant/catalogue/formations/"
        f"{quote(id_formation, safe='')}/site/{quote(id_site, safe='')}"
    )
    return page.evaluate(
        """async (url) => {
            const r = await fetch(url, {
                method: "GET",
                credentials: "include",
                headers: { "Accept": "application/json" }
            });
            if (!r.ok) return { __erreur: r.status };
            return await r.json();
        }""",
        chemin,
    )


def _extraire_textes_exigences(fiche: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    info = fiche.get("formationInformationGenerale") or {}
    textes = [texte_depuis_html((info.get("preRequis") or {}).get("value"))]
    entrees = [e for e in (fiche.get("formationsInformationsEntree") or []) if isinstance(e, dict)]
    for entree in entrees:
        textes.append(texte_depuis_html((entree.get("procedureInscription") or {}).get("value")))
    return [t for t in textes if t], entrees


def _appliquer_fiche(
    resultat: dict[str, Any],
    fiche: dict[str, Any],
    module: Any,
    francais_candidat: str | None,
    anglais_candidat: str | None,
) -> None:
    textes, entrees = _extraire_textes_exigences(fiche)
    exigences = [module.analyser_prerequis(t) for t in textes] or [module.analyser_prerequis("")]

    def _attr(obj: Any, nom: str) -> Any:
        return getattr(obj, nom, None)

    retenue = next(
        (e for e in exigences if _attr(e, "francais_min") is not None or _attr(e, "anglais_min") is not None),
        exigences[0],
    )
    francais_min = _attr(retenue, "francais_min")
    anglais_min = _attr(retenue, "anglais_min")
    priorite_c1 = any(bool(_attr(e, "priorite_c1")) for e in exigences)

    niveaux_fr = {str(_attr(e, "francais_min")) for e in exigences if _attr(e, "francais_min") is not None}
    if len(niveaux_fr) > 1:
        resultat["messages"].append(
            "Plusieurs niveaux de français sont mentionnés selon les pages de la fiche : "
            "vérifier le plus exigeant sur le portail."
        )

    messages: list[str] = resultat["messages"]
    if francais_min is None and anglais_min is None:
        statut = STATUT_INCONNU
        messages.append("Aucune mention de niveau de langue dans la fiche : à vérifier sur le portail.")
    elif francais_min is not None and not francais_candidat:
        statut = STATUT_INCONNU
        messages.append("Niveau de français du candidat non renseigné : adéquation non vérifiée.")
    else:
        evaluation = module.evaluer_adequation(
            retenue, francais_candidat=francais_candidat, anglais_candidat=anglais_candidat
        )
        statut = str(evaluation.get("statut") or "")
        if statut not in _STATUTS_ADEQUATION:
            statut = STATUT_INCONNU
        messages.extend(str(m) for m in evaluation.get("messages") or [])

    for entree in entrees:
        libelle_niveau = str(entree.get("valeurComNiveau") or "entrée sans niveau")
        if entree.get("ferme"):
            messages.append(f"Avertissement : une entrée ({libelle_niveau}) est fermée à l'inscription.")
        if entree.get("connecte") is False:
            messages.append(f"Avertissement : une entrée ({libelle_niveau}) n'est pas accessible en mode connecté.")

    resultat.update(
        {
            "statut": statut,
            "francais_min": None if francais_min is None else str(francais_min),
            "anglais_min": None if anglais_min is None else str(anglais_min),
            "priorite_c1": priorite_c1,
            "niveaux_disponibles": [str(e["valeurComNiveau"]) for e in entrees if e.get("valeurComNiveau")],
            "dates_limite": [str(e["dateFin"]) for e in entrees if e.get("dateFin")],
            "couts": [str(e["coutFormation"]) for e in entrees if e.get("coutFormation")],
            "ferme": bool(entrees) and all(bool(e.get("ferme")) for e in entrees),
        }
    )


_MESSAGES_RECHERCHE = {
    STATUT_INTROUVABLE: "Formation introuvable dans le catalogue : aucune correspondance exacte de l'intitulé et de l'établissement.",
    STATUT_AMBIGU: "Plusieurs formations du catalogue correspondent exactement : choisir manuellement avant tout ajout.",
    STATUT_ERREUR: "Recherche impossible dans le catalogue.",
}


def _verifier_un_voeu(
    page: Page,
    voeu: dict[str, Any],
    module: Any,
    francais_candidat: str | None,
    anglais_candidat: str | None,
) -> dict[str, Any]:
    resultat = _resultat_vide(voeu)
    intitule = str(voeu.get("intitule") or "").strip()
    etablissement = str(voeu.get("etablissement") or "").strip()
    if not intitule or not etablissement:
        resultat["messages"].append("Intitulé ou établissement du vœu manquant : vérification impossible.")
        return resultat
    try:
        statut_recherche, cible = _rechercher_formation(page, intitule, etablissement)
        if statut_recherche != STATUT_OK or cible is None:
            resultat["statut"] = statut_recherche
            resultat["messages"].append(_MESSAGES_RECHERCHE.get(statut_recherche, _MESSAGES_RECHERCHE[STATUT_ERREUR]))
            return resultat
        fiche = _lire_fiche(page, cible[0], cible[1])
        if not isinstance(fiche, dict) or "__erreur" in fiche:
            code = fiche.get("__erreur") if isinstance(fiche, dict) else None
            resultat["messages"].append(f"Fiche de formation inaccessible (code HTTP {code or 'inconnu'}).")
            return resultat
        _appliquer_fiche(resultat, fiche, module, francais_candidat, anglais_candidat)
    except Exception as exc:  # noqa: BLE001 — jamais de texte d'exception (peut contenir des saisies)
        resultat["statut"] = STATUT_ERREUR
        resultat["messages"].append(f"Erreur technique ({type(exc).__name__}) : vérification non effectuée.")
    return resultat


def verifier_prerequis_voeux(
    page: Page,
    voeux: list[dict],
    *,
    francais_candidat: str | None,
    anglais_candidat: str | None = None,
    analyseur: Any | None = None,
) -> list[dict]:
    """Vérifie, en lecture seule, les prérequis de langue de chaque vœu. Retourne une liste de résultats.

    `voeux` : liste de {voeu_id, intitule, etablissement, niveau}.
    `analyseur` : objet exposant `analyser_prerequis` et `evaluer_adequation` (injection pour les tests) ;
    par défaut, le module `app.services.prerequis_formation`.
    """
    module = _charger_analyseur(analyseur)
    champ_present = page.get_by_label(LIBELLE_CHAMP_RECHERCHE, exact=True).count() == 1

    resultats: list[dict[str, Any]] = []
    for voeu in voeux:
        if not champ_present:
            resultat = _resultat_vide(voeu)
            resultat["messages"].append(
                "Champ de recherche du catalogue introuvable : la page /catalogue-formations doit être ouverte."
            )
            resultats.append(resultat)
            continue
        resultats.append(_verifier_un_voeu(page, voeu, module, francais_candidat, anglais_candidat))
    return resultats
