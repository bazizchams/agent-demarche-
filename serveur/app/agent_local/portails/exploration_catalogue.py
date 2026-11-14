"""Exploration du catalogue Études en France, en LECTURE SEULE, dans le navigateur de l'utilisateur.

Ce que fait ce module, et rien d'autre :
1. vérifie que l'adresse de la page (et de chaque lien lu) appartient à un domaine HTTPS OFFICIEL des YAML de
   portail (Règle 6, `PolitiqueNavigation`) ; sinon il s'arrête sans rien charger ni lire ;
2. lit les liens de fiches déjà affichés sur la page de résultats (`/catalogue-formations/formation/{id}/site/{site}`) ;
3. lit chaque fiche par `fetch` en méthode GET sur l'API de lecture du portail (jamais POST, jamais d'écriture) ;
4. convertit chaque niveau d'entrée en `FicheEntree` (format du catalogue) avec la DATE DE RELEVÉ.

Interdits (Règle 1) : aucun clic, aucune saisie, aucun formulaire, aucune soumission, aucun bouton d'action.
La recherche (champ « Libellé de la formation », « Rechercher ») reste un geste HUMAIN : l'utilisateur affiche
la liste qu'il veut explorer, puis le Co-Pilote la lit. Seule exception de navigation : `page.goto(url_liste)`
(un GET d'une adresse officielle), uniquement si une adresse de liste est fournie.

Règle 4 : seul ce que la fiche affiche est repris ; niveau d'entrée, langue, date limite, fermeture. La moyenne,
les pièces et le domaine ne sont pas lus : ils restent inconnus (« à vérifier »).
Règle 5 : aucune donnée personnelle n'est lue ni renvoyée (une fiche décrit une formation).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from urllib.parse import urlparse

from pydantic import ValidationError

from app.agent_local.domaines_officiels import PolitiqueNavigation
from app.agent_local.portails.prerequis_catalogue import texte_depuis_html
from app.services.fiche_formation import (
    FicheEntree,
    exigences_langue_depuis_textes,
    niveau_bac_plus_depuis_libelle,
)

SELECTEUR_LIENS_FICHES = 'a[href*="/catalogue-formations/formation/"]'
PATRON_IDENTIFIANT = re.compile(r"[A-Za-z0-9_-]+")
PATRON_LIEN_FICHE = re.compile(r"/catalogue-formations/formation/([^/?#]+)/site/([^/?#]+)")
CHEMIN_API_FICHE = "/parcours-api/espace-etudiant/catalogue/formations/{id_formation}/site/{id_site}"
MAX_FICHES_PAR_EXPLORATION = 50

_JS_LIRE_LIENS = "(els) => els.map(e => e.href || '')"
_JS_LIRE_FICHE_GET = """async (url) => {
    const r = await fetch(url, {
        method: "GET",
        redirect: "manual",
        credentials: "include",
        headers: { "Accept": "application/json" }
    });
    if (r.type === "opaqueredirect" || r.redirected) return { __erreur: "redirection" };
    if (!r.ok) return { __erreur: r.status };
    return await r.json();
}"""


@dataclass(frozen=True)
class ResultatExploration:
    """Sortie de l'exploration : fiches au format du catalogue, éléments ignorés (avec raison), refus éventuel."""

    fiches: list[FicheEntree] = field(default_factory=list)
    ignorees: list[dict[str, str]] = field(default_factory=list)
    nb_liens_trouves: int = 0
    refus: str | None = None

    def fiches_json(self) -> list[dict[str, Any]]:
        """Charge utile prête pour `POST /api/v1/catalogue-formations/fiches` (`{"fiches": [...]}`)."""
        return [f.model_dump(mode="json") for f in self.fiches]


def _date_iso(valeur: Any) -> date | None:
    try:
        return date.fromisoformat(str(valeur)[:10])
    except (TypeError, ValueError):
        return None


def fiches_depuis_json_portail(
    fiche_json: dict[str, Any], *, url_fiche: str, date_releve: date
) -> list[FicheEntree]:
    """Convertit le JSON de fiche du portail en fiches du catalogue (une par niveau d'entrée).

    Lève `ValueError` si l'intitulé ou l'établissement manque (la fiche est alors ignorée par l'appelant).
    """
    info = fiche_json.get("formationInformationGenerale")
    if not isinstance(info, dict):
        raise ValueError("Structure de fiche inattendue.")
    etablissement = str(info.get("libelleEtablissement") or "").strip()
    intitule = str(info.get("libelleFormation") or "").strip()
    if not etablissement or not intitule:
        raise ValueError("Intitulé ou établissement absent de la fiche.")

    prerequis = texte_depuis_html((info.get("preRequis") or {}).get("value"))
    entrees = [e for e in (fiche_json.get("formationsInformationsEntree") or []) if isinstance(e, dict)]
    fiches: list[FicheEntree] = []
    for entree in entrees or [{}]:
        libelle = entree.get("valeurComNiveau")
        procedure = texte_depuis_html((entree.get("procedureInscription") or {}).get("value"))
        langue = exigences_langue_depuis_textes([prerequis, procedure])
        fiches.append(
            FicheEntree(
                etablissement=etablissement,
                intitule=intitule,
                niveau_entree_bac_plus=niveau_bac_plus_depuis_libelle(libelle),
                niveau_entree_libelle=str(libelle)[:60] if libelle else None,
                date_limite=_date_iso(entree.get("dateFin")),
                ferme=bool(entree["ferme"]) if "ferme" in entree else None,
                # une page de démonstration locale (http) n'est pas une URL officielle : jamais enregistrée
                url_officielle=url_fiche if url_fiche.lower().startswith("https://") else None,
                date_releve=date_releve,
                source="exploration",
                **langue,
            )
        )
    return fiches


def _hote_et_origine(url: str) -> str:
    analyse = urlparse(url)
    return f"{analyse.scheme}://{analyse.netloc}"


def explorer_catalogue(
    page: Any,
    politique: PolitiqueNavigation,
    *,
    url_liste: str | None = None,
    max_fiches: int = 20,
    date_releve: date | None = None,
) -> ResultatExploration:
    """Lit (GET seulement) les fiches des liens affichés sur `page`. Voir le docstring du module."""
    jour = date_releve or date.today()
    limite = max(1, min(max_fiches, MAX_FICHES_PAR_EXPLORATION))

    cible = url_liste or str(page.url or "")
    motif = politique.motif_refus(cible)
    if motif:
        return ResultatExploration(refus=motif)
    if url_liste:
        page.goto(url_liste)  # GET d'une adresse officielle déjà vérifiée
        motif = politique.motif_refus(str(page.url or ""))  # redirection hors domaine officiel ?
        if motif:
            return ResultatExploration(refus=motif)

    hrefs = page.locator(SELECTEUR_LIENS_FICHES).evaluate_all(_JS_LIRE_LIENS) or []
    ignorees: list[dict[str, str]] = []
    cibles: dict[tuple[str, str], str] = {}
    for href in hrefs:
        correspondance = PATRON_LIEN_FICHE.search(str(href))
        if correspondance is None:
            continue
        if not (PATRON_IDENTIFIANT.fullmatch(correspondance.group(1)) and PATRON_IDENTIFIANT.fullmatch(correspondance.group(2))):
            ignorees.append({"fiche": "*", "raison": "Identifiant de fiche non conforme."})
            continue
        motif_lien = politique.motif_refus(str(href))
        if motif_lien:
            ignorees.append({"fiche": correspondance.group(1), "raison": "Lien hors domaine officiel (Règle 6)."})
            continue
        cibles.setdefault((correspondance.group(1), correspondance.group(2)), str(href))

    fiches: list[FicheEntree] = []
    for (id_formation, id_site), url_fiche in list(cibles.items())[:limite]:
        api = _hote_et_origine(url_fiche) + CHEMIN_API_FICHE.format(id_formation=id_formation, id_site=id_site)
        if politique.motif_refus(str(page.url or "")):
            return ResultatExploration(fiches, ignorees, len(hrefs), refus="Page hors domaine officiel (Règle 6).")
        contenu = page.evaluate(_JS_LIRE_FICHE_GET, api)
        if not isinstance(contenu, dict) or "__erreur" in contenu:
            code = contenu.get("__erreur") if isinstance(contenu, dict) else None
            ignorees.append({"fiche": id_formation, "raison": f"Fiche inaccessible (code HTTP {code or 'inconnu'})."})
            continue
        try:
            fiches.extend(fiches_depuis_json_portail(contenu, url_fiche=url_fiche, date_releve=jour))
        except (ValueError, ValidationError) as exc:
            raison = str(exc) if isinstance(exc, ValueError) and not isinstance(exc, ValidationError) else "Fiche invalide."
            ignorees.append({"fiche": id_formation, "raison": raison})
    if len(cibles) > limite:
        ignorees.append({"fiche": "*", "raison": f"{len(cibles) - limite} fiche(s) au-delà de la limite de {limite}."})
    return ResultatExploration(fiches, ignorees, len(hrefs))
