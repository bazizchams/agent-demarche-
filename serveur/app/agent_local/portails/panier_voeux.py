"""Panier de vœux Campus France : ajout de formations + texte de motivation, et calibration du DOM.

Deux capacités du Co-Pilote Playwright, volontairement indépendantes de `pilote_navigateur.py`
(les gardes Règle 1 / Règle 2 y sont injectés en paramètres pour éviter tout import circulaire) :

1. `ajouter_voeux_au_panier` — pour chaque vœu : recherche dans le catalogue, vérification STRICTE de
   la correspondance intitulé ET établissement (casse/accents normalisés), anti-doublon, limite de 7,
   validation de la motivation (non vide, 4 000 caractères max), ajout, saisie de la motivation et clic
   sur « Enregistrer » de la formation. Jamais de case de certification, jamais de bouton de soumission.
   Deux modes de profil :
   - `mode="css"` : page de démonstration `/demo/campus-france` (sélecteurs CSS de la démo) ;
   - `mode="roles"` : VRAI portail Études en France (application React aux identifiants générés :
     AUCUN identifiant ni classe CSS n'est utilisé, uniquement des locators par rôle, libellé et texte).
2. `cartographier_page` — action de calibration pour le vrai portail : liste des éléments interactifs
   (balise, rôle, libellé tronqué et passé dans `masquer_pii`, id, name, classes, data-*, placeholder,
   type) écrite dans `<dossier>/<horodatage>.json`. Aucune valeur saisie ni contenu de champ n'est lu,
   aucun clic n'est effectué.

Règles : R1 (arrêt avant soumission), R2 (pause CAPTCHA/2FA), R4 (aucune valeur inventée),
R5 (aucune donnée personnelle ni texte de motivation dans les notes/journaux produits ici).

STATUT DU PROFIL RÉEL : `PROFIL_PANIER_REEL` est écrit d'après la structure OBSERVÉE du vrai portail le
2026-11-11 (arbre d'accessibilité, session connectée) et validé uniquement contre une MAQUETTE FIDÈLE
(`app/demo/maquette_eef_reel.py`). Il reste `teste=False` : l'action est refusée sur le vrai domaine tant que
l'administrateur n'a pas homologué le portail (voir `pilote_navigateur.py`, Règle 6). Points non confirmés :
structure interne de l'éditeur de texte riche (essais défensifs : iframe, contenteditable, textarea),
comportement exact après « Ajouter au panier » (on vérifie par l'API de lecture puis dans le panier).
Le POST de recherche du catalogue (corps inconnu) n'est JAMAIS appelé ; seul un GET de lecture de la fiche l'est.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from playwright.sync_api import Locator, Page

from app.core.journalisation import masquer_pii

LIMITE_VOEUX_PANIER = 7
LONGUEUR_MAX_MOTIVATION = 4000
LONGUEUR_MAX_LIBELLE_CALIBRATION = 80

STATUT_AJOUTE = "ajoute"
STATUT_DEJA_PRESENT = "deja_present"
STATUT_INTROUVABLE = "introuvable"
STATUT_AMBIGU = "ambigu"
STATUT_FERME = "ferme"
STATUT_REFUSE_LIMITE = "refuse_limite"
STATUT_MOTIVATION_INVALIDE = "motivation_invalide"
STATUT_ERREUR = "erreur"

# Règle 1 : tout élément dont le nom (texte visible ou aria-label) contient l'un de ces mots n'est JAMAIS cliqué,
# quel que soit le profil (« Supprimer » une formation, « Soumettre » le dossier, cases « je certifie… »).
MOTS_INTERDITS_CLIC_PANIER: tuple[str, ...] = ("supprimer", "soumettre", "certifie")

MODE_CSS = "css"
MODE_ROLES = "roles"


@dataclass(frozen=True)
class ProfilSelecteursPanier:
    """Profil d'un portail pour le catalogue, le panier et les motivations.

    `mode="css"` utilise les champs `recherche` … `suffixe_item_motivation_enregistree` (démo).
    `mode="roles"` utilise les champs `libelle_*`, `chemin_*` et `prefixe_*` (vrai portail, sans CSS).
    """

    nom: str
    teste: bool
    recherche: str = ""
    bouton_rechercher: str | None = None
    resultats_items: str = ""
    bouton_ajouter_dans_item: str = ""
    panier_items: str = ""
    motivation_dans_item: str = ""
    bouton_enregistrer_dans_item: str = ""
    # Sélecteur CSS ajouté à un élément du panier lorsque sa motivation est enregistrée
    suffixe_item_motivation_enregistree: str = ""
    attr_id: str = "data-formation-id"
    attr_intitule: str = "data-intitule"
    attr_etablissement: str = "data-etablissement"
    attr_niveau: str = "data-niveau"
    # --- Mode « roles » (vrai portail) ---
    mode: str = MODE_CSS
    # Origine imposée (vrai portail) ; None = origine de la page courante (maquette de test locale)
    origine: str | None = None
    prefixe_chemin: str = ""
    prefixe_api: str = "/parcours-api"
    chemin_catalogue: str = "/catalogue-formations"
    chemin_panier: str = "/mon-dossier-candidature/panier-formations"
    libelle_champ_recherche: str = "Libellé de la formation"
    libelle_bouton_rechercher: str = "Rechercher"
    libelle_bouton_ajouter: str = "Ajouter au panier"
    libelle_bouton_enregistrer: str = "Enregistrer"
    libelle_titre_motivation: str = "Texte de motivation"
    libelle_a_completer: str = "À compléter"
    largeur_page: int = 1280
    hauteur_page: int = 900


# Portail de démonstration (/demo/campus-france) : testé par tests/test_panier_voeux_demo.py
PROFIL_PANIER_DEMO = ProfilSelecteursPanier(
    nom="demo_campus_france",
    teste=True,
    recherche="#catalogue-recherche",
    bouton_rechercher="#btn-catalogue-rechercher",
    resultats_items="#catalogue-resultats .catalogue-item",
    bouton_ajouter_dans_item="button.btn-ajouter-formation",
    panier_items="#panier-liste .panier-item",
    motivation_dans_item="textarea.panier-motivation",
    bouton_enregistrer_dans_item="button.btn-enregistrer-motivation",
    suffixe_item_motivation_enregistree='[data-statut="motivation_enregistree"]',
    mode=MODE_CSS,
)

# VRAI portail Études en France (relevé du 2026-11-11) : locators par rôle / libellé / texte UNIQUEMENT.
# `teste=False` : validé contre la maquette fidèle, jamais homologué sur le vrai portail (Règle 6).
PROFIL_PANIER_REEL = ProfilSelecteursPanier(
    nom="campus_france_reel",
    teste=False,
    mode=MODE_ROLES,
    origine="https://etudesenfrance.diplomatie.gouv.fr",
)


def profil_maquette_eef() -> ProfilSelecteursPanier:
    """Même logique que `PROFIL_PANIER_REEL`, appliquée à la maquette locale `/demo/eef-reel/...`."""
    from dataclasses import replace

    return replace(
        PROFIL_PANIER_REEL,
        nom="maquette_eef_reel",
        origine=None,
        prefixe_chemin="/demo/eef-reel",
        prefixe_api="/demo/eef-reel/parcours-api",
    )


def normaliser_texte_voeu(texte: str | None) -> str:
    """Minuscule, sans accents, ponctuation et espaces multiples réduits à une espace."""
    brut = unicodedata.normalize("NFKD", texte or "")
    sans_accents = "".join(c for c in brut if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", sans_accents.lower()).strip()


def _nouveau_resultat(voeu: dict[str, Any], statut: str, *, motivation_enregistree: bool = False, nb: int = 0) -> dict[str, Any]:
    return {
        "voeu_id": str(voeu.get("voeu_id") or ""),
        "intitule": str(voeu.get("intitule") or ""),
        "etablissement": str(voeu.get("etablissement") or ""),
        "statut": statut,
        "motivation_enregistree": motivation_enregistree,
        "nb_caracteres": nb,
    }


def _echapper_valeur_attribut_css(valeur: str) -> str:
    return valeur.replace("\\", "\\\\").replace('"', '\\"')


def _nom_interdit(*textes: str | None) -> bool:
    """Règle 1 : « Supprimer », « Soumettre », « certifie » (cases de certification) ne sont jamais cliqués."""
    norm = normaliser_texte_voeu(" ".join(t or "" for t in textes))
    return any(mot in norm for mot in MOTS_INTERDITS_CLIC_PANIER)


def _lire_elements(page: Page, selecteur: str, profil: ProfilSelecteursPanier) -> list[dict[str, str]]:
    """Lit uniquement les attributs publics d'identification du catalogue / panier (jamais de saisie)."""
    return page.locator(selecteur).evaluate_all(
        """(els, attrs) => els.map(e => ({
            id: e.getAttribute(attrs[0]) || "",
            intitule: e.getAttribute(attrs[1]) || "",
            etablissement: e.getAttribute(attrs[2]) || "",
            niveau: e.getAttribute(attrs[3]) || ""
        }))""",
        [profil.attr_id, profil.attr_intitule, profil.attr_etablissement, profil.attr_niveau],
    )


def _cliquer_garde(
    locator: Locator,
    selecteur_decrit: str,
    est_interdit: Callable[[str, str, str], bool],
) -> bool:
    """Clic protégé par le garde Règle 1 existant (sélecteur, texte visible, data-action-officielle)
    et par la liste d'interdits du panier (« Supprimer », « Soumettre », « certifie »)."""
    if est_interdit(selecteur_decrit, "", "") or _nom_interdit(selecteur_decrit):
        return False
    if locator.count() == 0:
        return False
    cible = locator.first
    if not cible.is_visible():
        return False
    try:
        texte = cible.inner_text(timeout=500) or ""
    except Exception:
        texte = ""
    try:
        attr_off = cible.get_attribute("data-action-officielle", timeout=500) or ""
    except Exception:
        attr_off = ""
    try:
        type_attr = (cible.get_attribute("type", timeout=500) or "").lower()
    except Exception:
        type_attr = ""
    try:
        aria = cible.get_attribute("aria-label", timeout=500) or ""
    except Exception:
        aria = ""
    if type_attr in {"checkbox", "radio"}:
        # Cases (dont celles de certification) : jamais cochées par l'agent.
        return False
    if est_interdit(selecteur_decrit, texte, attr_off) or _nom_interdit(texte, aria):
        return False
    cible.click(timeout=2500)
    return True


def _selectionner_correspondance(
    candidats: list[dict[str, str]], voeu: dict[str, Any]
) -> tuple[str, dict[str, str] | None, int]:
    """Retourne (statut, candidat, index) avec statut in {"ok", "introuvable", "ambigu"}.

    Correspondance STRICTE sur l'intitulé ET l'établissement (normalisés). Si plusieurs entrées
    correspondent, le niveau (s'il est fourni) permet de départager ; sinon => ambigu.
    """
    intitule = normaliser_texte_voeu(voeu.get("intitule"))
    etab = normaliser_texte_voeu(voeu.get("etablissement"))
    indices = [
        i
        for i, c in enumerate(candidats)
        if normaliser_texte_voeu(c["intitule"]) == intitule
        and normaliser_texte_voeu(c["etablissement"]) == etab
    ]
    if len(indices) > 1 and voeu.get("niveau"):
        niv = normaliser_texte_voeu(voeu.get("niveau"))
        par_niveau = [i for i in indices if normaliser_texte_voeu(candidats[i]["niveau"]) == niv]
        if par_niveau:
            indices = par_niveau
    if not indices:
        return "introuvable", None, -1
    if len(indices) > 1:
        return "ambigu", None, -1
    return "ok", candidats[indices[0]], indices[0]


def valider_voeu(voeu: dict[str, Any]) -> tuple[str | None, str]:
    """Contrôles préalables sans toucher à la page. Retourne (statut_refus | None, motivation_normalisee)."""
    if not str(voeu.get("intitule") or "").strip() or not str(voeu.get("etablissement") or "").strip():
        return STATUT_ERREUR, ""  # R4 : on n'invente ni intitulé ni établissement
    motivation = str(voeu.get("motivation") or "").replace("\r\n", "\n").replace("\r", "\n")
    if not motivation.strip() or len(motivation) > LONGUEUR_MAX_MOTIVATION:
        return STATUT_MOTIVATION_INVALIDE, motivation
    return None, motivation


def ajouter_voeux_au_panier(
    page: Page,
    voeux: list[dict[str, Any]],
    *,
    profil: ProfilSelecteursPanier,
    est_interdit: Callable[[str, str, str], bool],
    detecteur_blocage: Callable[[Page], bool],
) -> tuple[list[dict[str, Any]], list[str], bool]:
    """Ajoute les vœux au panier. Retourne (résultats par vœu, notes sans PII, blocage_captcha_2fa).

    Les notes ne citent que `voeu_id` et des statuts (jamais de motivation ni de nom).
    """
    if profil.mode == MODE_ROLES:
        return _ajouter_voeux_roles(
            page, voeux, profil=profil, est_interdit=est_interdit, detecteur_blocage=detecteur_blocage
        )
    return _ajouter_voeux_css(
        page, voeux, profil=profil, est_interdit=est_interdit, detecteur_blocage=detecteur_blocage
    )


def _ajouter_voeux_css(
    page: Page,
    voeux: list[dict[str, Any]],
    *,
    profil: ProfilSelecteursPanier,
    est_interdit: Callable[[str, str, str], bool],
    detecteur_blocage: Callable[[Page], bool],
) -> tuple[list[dict[str, Any]], list[str], bool]:
    """Mode « css » : page de démonstration."""
    resultats: list[dict[str, Any]] = []
    notes: list[str] = []
    blocage = False

    if page.locator(profil.recherche).count() == 0:
        for v in voeux:
            resultats.append(_nouveau_resultat(v, STATUT_ERREUR))
        notes.append(
            "Catalogue de formations introuvable sur la page courante : aucun vœu ajouté "
            f"(profil de sélecteurs « {profil.nom} »)."
        )
        return resultats, notes, False

    for index_voeu, voeu in enumerate(voeux):
        if blocage or detecteur_blocage(page):
            blocage = True
            resultats.append(_nouveau_resultat(voeu, STATUT_ERREUR))
            continue

        refus, motivation = valider_voeu(voeu)
        if refus is not None:
            resultats.append(_nouveau_resultat(voeu, refus, nb=len(motivation)))
            notes.append(f"Vœu {voeu.get('voeu_id')} : {refus} (non ajouté).")
            continue

        res = _nouveau_resultat(voeu, STATUT_ERREUR, nb=len(motivation))
        resultats.append(res)
        try:
            # 1. Recherche dans le catalogue
            champ = page.locator(profil.recherche).first
            champ.fill(str(voeu["intitule"]).strip(), timeout=3000)
            if profil.bouton_rechercher:
                _cliquer_garde(page.locator(profil.bouton_rechercher), profil.bouton_rechercher, est_interdit)
            else:
                champ.press("Enter")
            page.wait_for_timeout(250)
            if detecteur_blocage(page):
                blocage = True
                continue

            candidats = _lire_elements(page, profil.resultats_items, profil)
            statut_match, candidat, idx = _selectionner_correspondance(candidats, voeu)
            if statut_match == "introuvable":
                res["statut"] = STATUT_INTROUVABLE
                notes.append(f"Vœu {voeu.get('voeu_id')} : aucune formation du catalogue ne correspond (rien ajouté).")
                continue
            if statut_match == "ambigu":
                res["statut"] = STATUT_AMBIGU
                notes.append(f"Vœu {voeu.get('voeu_id')} : plusieurs formations correspondent (rien ajouté).")
                continue
            assert candidat is not None

            # 2. Anti-doublon puis limite (sur l'état réel du panier)
            panier = _lire_elements(page, profil.panier_items, profil)
            if any(p["id"] == candidat["id"] for p in panier):
                res["statut"] = STATUT_DEJA_PRESENT
                continue
            if len(panier) >= LIMITE_VOEUX_PANIER:
                res["statut"] = STATUT_REFUSE_LIMITE
                notes.append(
                    f"Vœu {voeu.get('voeu_id')} : panier plein ({LIMITE_VOEUX_PANIER} formations maximum), non ajouté."
                )
                continue

            # 3. Ajout de la formation
            item_catalogue = page.locator(profil.resultats_items).nth(idx)
            bouton_ajout = item_catalogue.locator(profil.bouton_ajouter_dans_item)
            if bouton_ajout.count() != 1 or not _cliquer_garde(
                bouton_ajout, profil.bouton_ajouter_dans_item, est_interdit
            ):
                notes.append(f"Vœu {voeu.get('voeu_id')} : bouton d'ajout indisponible (rien ajouté).")
                continue
            sel_item_panier = (
                f'{profil.panier_items}[{profil.attr_id}="{_echapper_valeur_attribut_css(candidat["id"])}"]'
            )
            try:
                page.locator(sel_item_panier).first.wait_for(state="attached", timeout=2500)
            except Exception:
                notes.append(f"Vœu {voeu.get('voeu_id')} : ajout non confirmé par le portail.")
                continue
            res["statut"] = STATUT_AJOUTE
            if detecteur_blocage(page):
                blocage = True
                continue

            # 4. Motivation : saisie puis « Enregistrer » de la formation
            item_panier = page.locator(sel_item_panier).first
            zone = item_panier.locator(profil.motivation_dans_item).first
            zone.fill(motivation, timeout=3000)
            if len(zone.input_value()) != len(motivation):
                notes.append(f"Vœu {voeu.get('voeu_id')} : motivation tronquée par le portail, non enregistrée.")
                continue
            bouton_enreg = item_panier.locator(profil.bouton_enregistrer_dans_item)
            if bouton_enreg.count() != 1 or not _cliquer_garde(
                bouton_enreg, profil.bouton_enregistrer_dans_item, est_interdit
            ):
                notes.append(f"Vœu {voeu.get('voeu_id')} : bouton « Enregistrer » indisponible.")
                continue
            try:
                page.locator(sel_item_panier + profil.suffixe_item_motivation_enregistree).first.wait_for(
                    state="attached", timeout=2500
                )
                res["motivation_enregistree"] = True
            except Exception:
                notes.append(f"Vœu {voeu.get('voeu_id')} : enregistrement de la motivation non confirmé.")
            if detecteur_blocage(page):
                blocage = True
        except Exception as exc:  # noqa: BLE001 — jamais de texte d'exception (peut contenir des saisies)
            if res["statut"] not in (STATUT_AJOUTE,):
                res["statut"] = STATUT_ERREUR
            notes.append(f"Vœu {voeu.get('voeu_id')} : erreur technique ({type(exc).__name__}).")

    if blocage:
        notes.append(
            "CAPTCHA ou double authentification détecté (Règle 2) : pause immédiate, vœux restants non traités."
        )
    return resultats, notes, blocage


# ---------------------------------------------------------------------------
# Mode « roles » : vrai portail Études en France (locators par rôle / libellé / texte)
# ---------------------------------------------------------------------------

_RE_NIVEAU_ENTREE = re.compile(r"niveau d.entr.e\s*:?\s*(?:\|\s*)?(bac\s*\+\s*\d+)", re.IGNORECASE)
_RE_COMPTEUR = re.compile(r"\d+\s*/\s*\d+\s*caract", re.IGNORECASE)
_RE_NOMBRE_SUR_MAX = re.compile(r"(\d+)\s*/\s*\d+")
_RE_NB_FORMATIONS = re.compile(r"(\d+)\s+formations?\s+ajout", re.IGNORECASE)
_RE_IDS_FICHE = re.compile(r"/formation/([^/?#]+)/site/([^/?#]+)")

# Résultats du catalogue : liens `a[href^=".../formation/"]` (attribut stable du routage, pas un id React).
# La « carte » est le plus grand ancêtre (jusqu'à li/article) qui ne contient que CE lien de résultat.
_JS_CARTES_RESULTATS = """(prefixe) => {
  const sel = 'a[href^="' + prefixe + '"]';
  const lignes = (t) => String(t || '').split('\\n').map(s => s.trim()).filter(Boolean);
  return Array.from(document.querySelectorAll(sel)).map((a, i) => {
    let carte = a;
    for (let n = 0; n < 6 && carte.parentElement; n++) {
      if (['LI', 'ARTICLE'].includes(carte.tagName)) break;
      const p = carte.parentElement;
      if (p.querySelectorAll(sel).length !== 1) break;
      carte = p;
    }
    const ll = lignes(a.innerText);
    return { i: i, href: a.getAttribute('href') || '', intitule: ll[0] || '', lignes: lignes(carte.innerText) };
  });
}"""

# Fiche formation : titres de niveau (« Bac +4 »…) et boutons « Ajouter au panier ». Chaque bouton est relié au
# titre du plus proche conteneur qui contient au moins un titre de niveau ; il n'est exploitable que si ce
# conteneur ne contient qu'UN titre de niveau.
_JS_SECTIONS_NIVEAU = """(libelleBouton) => {
  const RE = /^\\s*Bac\\s*\\+\\s*\\d+\\s*$/i;
  const norm = (t) => String(t || '').replace(/\\s+/g, ' ').trim();
  const titres = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6,[role="heading"]'))
    .filter(h => RE.test(h.textContent || ''));
  const boutons = Array.from(document.querySelectorAll('button,[role="button"]'))
    .filter(b => norm(b.getAttribute('aria-label') || b.textContent).toLowerCase() === libelleBouton.toLowerCase());
  const sections = titres.map(h => ({ niveau: norm(h.textContent), boutons: 0, index_bouton: -1 }));
  boutons.forEach((b, bi) => {
    let n = b.parentElement;
    while (n) {
      const dedans = titres.filter(h => n.contains(h));
      if (dedans.length) {
        if (dedans.length === 1) {
          const k = titres.indexOf(dedans[0]);
          sections[k].boutons += 1;
          sections[k].index_bouton = bi;
        }
        break;
      }
      n = n.parentElement;
    }
  });
  return { sections: sections, nb_boutons: boutons.length };
}"""

_JS_MARQUER_BOUTON = """([libelleBouton, bi]) => {
  const norm = (t) => String(t || '').replace(/\\s+/g, ' ').trim();
  const boutons = Array.from(document.querySelectorAll('button,[role="button"]'))
    .filter(b => norm(b.getAttribute('aria-label') || b.textContent).toLowerCase() === libelleBouton.toLowerCase());
  document.querySelectorAll('[data-copilote-cible]').forEach(e => e.removeAttribute('data-copilote-cible'));
  if (!boutons[bi]) return false;
  boutons[bi].setAttribute('data-copilote-cible', '1');
  return true;
}"""

_JS_DEMARQUER = """() => document.querySelectorAll('[data-copilote-cible]').forEach(e => e.removeAttribute('data-copilote-cible'))"""

# Un `article` par formation du panier : titre = premier heading qui n'est pas « Texte de motivation… ».
_JS_ARTICLES_PANIER = """(els, libelleMotivation) => els.map(a => {
  const lignes = String(a.innerText || '').split('\\n').map(s => s.trim()).filter(Boolean);
  const titres = Array.from(a.querySelectorAll('h1,h2,h3,h4,h5,h6,[role="heading"]'))
    .map(h => (h.textContent || '').replace(/\\s+/g, ' ').trim())
    .filter(t => t && !t.toLowerCase().includes(libelleMotivation.toLowerCase()));
  return { titre: titres[0] || '', lignes: lignes };
})"""

_JS_FETCH_FICHE = """async (url) => {
  try {
    const r = await fetch(url, { method: 'GET', credentials: 'include', headers: { Accept: 'application/json' } });
    if (!r.ok) return { statut_http: r.status, entrees: null };
    const j = await r.json();
    const entrees = (j.formationsInformationsEntree || []).map(e => ({
      niveau: String(e.valeurComNiveau || ''),
      ferme: !!e.ferme,
      connecte: !!e.connecte,
      ajoute_au_panier: !!e.ajouteAuPanier,
      date_fin: String(e.dateFin || '')
    }));
    return { statut_http: r.status, entrees: entrees };
  } catch (e) {
    return { statut_http: 0, entrees: null };
  }
}"""


def _base_url(page: Page, profil: ProfilSelecteursPanier) -> str:
    if profil.origine:
        return profil.origine.rstrip("/")
    u = urlsplit(page.url or "")
    return f"{u.scheme}://{u.netloc}"


def _aller_a(page: Page, profil: ProfilSelecteursPanier, chemin: str) -> bool:
    """Navigue vers une page du portail ; False si on n'arrive pas sur le domaine attendu (session fermée,
    redirection vers la connexion, etc.). Jamais de saisie d'identifiants : l'humain se connecte (Règle 3)."""
    base = _base_url(page, profil)
    attendu = urlsplit(base).hostname
    page.goto(f"{base}{profil.prefixe_chemin}{chemin}", wait_until="domcontentloaded", timeout=20000)
    try:
        page.wait_for_load_state("networkidle", timeout=4000)
    except Exception:
        pass
    courant = urlsplit(page.url or "").hostname
    return bool(attendu) and courant == attendu


def _lignes_normalisees(lignes: list[str]) -> set[str]:
    return {normaliser_texte_voeu(ligne) for ligne in lignes}


def _lire_cartes_resultats(page: Page, profil: ProfilSelecteursPanier) -> list[dict[str, Any]]:
    prefixe = f"{profil.prefixe_chemin}{profil.chemin_catalogue}/formation/"
    return page.evaluate(_JS_CARTES_RESULTATS, prefixe) or []


def _candidats_depuis_cartes(cartes: list[dict[str, Any]], voeu: dict[str, Any]) -> list[dict[str, str]]:
    """Filtrage CÔTÉ CLIENT (la recherche du portail est large) : l'établissement est retenu uniquement si l'une
    des lignes de la carte lui est strictement égale (normalisée) ; sinon il reste vide et le candidat est écarté."""
    etab_voeu = normaliser_texte_voeu(voeu.get("etablissement"))
    candidats: list[dict[str, str]] = []
    for c in cartes:
        lignes = [str(x) for x in (c.get("lignes") or [])]
        trouve = _RE_NIVEAU_ENTREE.search(" | ".join(lignes))
        candidats.append(
            {
                "id": str(c.get("href") or ""),
                "intitule": str(c.get("intitule") or ""),
                "etablissement": str(voeu.get("etablissement") or "") if etab_voeu in _lignes_normalisees(lignes) else "",
                "niveau": trouve.group(1) if trouve else "",
            }
        )
    return candidats


def _lire_api_fiche(page: Page, profil: ProfilSelecteursPanier, id_formation: str, id_site: str) -> list[dict[str, Any]] | None:
    """GET de lecture (même session) : entrées de la fiche. None si l'API est indisponible. Jamais de POST."""
    url = f"{profil.prefixe_api}/espace-etudiant/catalogue/formations/{id_formation}/site/{id_site}"
    rep = page.evaluate(_JS_FETCH_FICHE, url) or {}
    entrees = rep.get("entrees")
    return entrees if isinstance(entrees, list) else None


def _entree_pour_niveau(entrees: list[dict[str, Any]] | None, niveau: str) -> dict[str, Any] | None:
    if not entrees:
        return None
    voulu = normaliser_texte_voeu(niveau)
    trouvees = [e for e in entrees if normaliser_texte_voeu(str(e.get("niveau") or "")) == voulu]
    return trouvees[0] if len(trouvees) == 1 else None


def _choisir_section(sections: list[dict[str, Any]], voeu: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    """Retourne (« ok » | « ambigu » | « aucune »), section). Le champ `niveau` du vœu choisit la section ;
    absent ou sans correspondance avec plusieurs sections => ambigu (rien n'est ajouté)."""
    if not sections:
        return "aucune", None
    voulu = normaliser_texte_voeu(voeu.get("niveau"))
    if voulu:
        corresp = [s for s in sections if normaliser_texte_voeu(s["niveau"]) == voulu]
        if len(corresp) == 1:
            return "ok", corresp[0]
        if len(corresp) > 1:
            return "ambigu", None
    if len(sections) == 1:
        return "ok", sections[0]
    return "ambigu", None


def _lire_articles_panier(page: Page, profil: ProfilSelecteursPanier) -> list[dict[str, Any]]:
    return page.get_by_role("article").evaluate_all(_JS_ARTICLES_PANIER, profil.libelle_titre_motivation)


def _compter_panier(page: Page, articles: list[dict[str, Any]]) -> int:
    nb = len(articles)
    try:
        texte = page.get_by_text(_RE_NB_FORMATIONS).first.inner_text(timeout=1500)
        m = _RE_NB_FORMATIONS.search(texte)
        if m:
            nb = max(nb, int(m.group(1)))
    except Exception:
        pass
    return nb


def _indices_articles(articles: list[dict[str, Any]], voeu: dict[str, Any], niveau: str) -> list[int]:
    intitule = normaliser_texte_voeu(voeu.get("intitule"))
    etab = normaliser_texte_voeu(voeu.get("etablissement"))
    niv = normaliser_texte_voeu(niveau)
    resultat: list[int] = []
    for i, a in enumerate(articles):
        lignes = _lignes_normalisees([str(x) for x in a.get("lignes") or []])
        if normaliser_texte_voeu(str(a.get("titre") or "")) != intitule or etab not in lignes:
            continue
        if niv and not any(
            re.search(rf"(?:^| ){re.escape(niv)}(?: |$)", ligne) for ligne in lignes
        ):
            continue
        resultat.append(i)
    return resultat


def _trouver_article(page: Page, profil: ProfilSelecteursPanier, voeu: dict[str, Any], niveau: str) -> tuple[Locator | None, int, str]:
    """(locator de l'article, index, « ok » | « absent » | « ambigu »)."""
    indices = _indices_articles(_lire_articles_panier(page, profil), voeu, niveau)
    if len(indices) == 1:
        return page.get_by_role("article").nth(indices[0]), indices[0], "ok"
    return None, -1, ("ambigu" if indices else "absent")


def _cliquer_bouton_marque(page: Page, est_interdit: Callable[[str, str, str], bool], libelle: str) -> bool:
    cible = page.locator("[data-copilote-cible]")
    try:
        return _cliquer_garde(cible, libelle, est_interdit) if cible.count() == 1 else False
    finally:
        try:
            page.evaluate(_JS_DEMARQUER)
        except Exception:
            pass


def _trouver_editeur(art: Locator) -> tuple[str, Locator] | None:
    """Éditeur de texte riche, structure NON confirmée : essais défensifs dans l'ordre
    iframe → body éditable, puis [contenteditable=true], puis textarea."""
    try:
        nb_cadres = art.locator("iframe").count()
    except Exception:
        nb_cadres = 0
    for i in range(nb_cadres):
        corps = art.frame_locator("iframe").nth(i).locator("body")
        try:
            corps.wait_for(state="attached", timeout=3000)
            editable = corps.evaluate("el => el.isContentEditable || el.ownerDocument.designMode === 'on'", timeout=1500)
        except Exception:
            continue
        if editable:
            return "iframe", corps
    ce = art.locator("[contenteditable='true']")
    if ce.count() > 0:
        return "contenteditable", ce.first
    ta = art.locator("textarea")
    if ta.count() > 0:
        return "textarea", ta.first
    return None


def _remplir_editeur(page: Page, genre: str, zone: Locator, paragraphes: list[str]) -> None:
    """Chaque saut de ligne de la lettre devient un paragraphe (touche Entrée de l'éditeur)."""
    if genre == "textarea":
        zone.fill("\n".join(paragraphes), timeout=4000)
        return
    try:
        zone.click(timeout=3000)
    except Exception:
        zone.focus(timeout=2000)
    try:
        page.keyboard.press("ControlOrMeta+A")
    except Exception:
        page.keyboard.press("Control+A")
    page.keyboard.press("Delete")
    for k, paragraphe in enumerate(paragraphes):
        if k:
            page.keyboard.press("Enter")
        page.keyboard.insert_text(paragraphe)


def _lire_compteur(art: Locator) -> int | None:
    compteur = art.get_by_text(_RE_COMPTEUR)
    if compteur.count() == 0:
        return None
    m = _RE_NOMBRE_SUR_MAX.search(compteur.first.inner_text(timeout=1500))
    return int(m.group(1)) if m else None


def _a_completer_present(art: Locator, profil: ProfilSelecteursPanier) -> bool:
    etiquette = art.get_by_text(re.compile(rf"^\s*{re.escape(profil.libelle_a_completer)}\s*$", re.IGNORECASE))
    return etiquette.count() > 0


def _saisir_et_enregistrer_motivation(
    page: Page,
    profil: ProfilSelecteursPanier,
    voeu: dict[str, Any],
    niveau: str,
    motivation: str,
    est_interdit: Callable[[str, str, str], bool],
    notes: list[str],
) -> bool:
    """Motivation de l'article du vœu : dépliage, saisie, contrôle du compteur, « Enregistrer » de CET article
    uniquement, puis contrôle final (le libellé « À compléter » a disparu). Retourne True si tout est vérifié."""
    vid = voeu.get("voeu_id")
    art, _idx, etat = _trouver_article(page, profil, voeu, niveau)
    if art is None:
        notes.append(f"Vœu {vid} : formation introuvable dans le panier pour la motivation ({etat}).")
        return False

    # Dépliage : le bouton n'a PAS de nom accessible, c'est le premier bouton du heading « Texte de motivation… »
    compteur = art.get_by_text(_RE_COMPTEUR)
    if compteur.count() == 0 or not compteur.first.is_visible():
        titre = art.get_by_role("heading", name=re.compile(re.escape(profil.libelle_titre_motivation), re.IGNORECASE))
        bouton = titre.get_by_role("button").first
        if titre.count() == 0:
            notes.append(f"Vœu {vid} : rubrique « {profil.libelle_titre_motivation} » introuvable.")
            return False
        if not _cliquer_garde(bouton, "bouton de dépliage de la motivation", est_interdit):
            notes.append(f"Vœu {vid} : dépliage de la motivation impossible.")
            return False
        try:
            art.get_by_text(_RE_COMPTEUR).first.wait_for(state="visible", timeout=4000)
        except Exception:
            notes.append(f"Vœu {vid} : formulaire de motivation non affiché.")
            return False

    editeur = _trouver_editeur(art)
    if editeur is None:
        notes.append(f"Vœu {vid} : éditeur de motivation introuvable (structure inconnue), rien saisi.")
        return False
    genre, zone = editeur

    paragraphes = [ligne.strip() for ligne in motivation.split("\n") if ligne.strip()]
    attendus = {sum(len(p) for p in paragraphes), len("\n".join(paragraphes))}
    _remplir_editeur(page, genre, zone, paragraphes)

    # Contrôle du compteur affiché avant d'enregistrer
    valeur: int | None = None
    for _ in range(12):
        valeur = _lire_compteur(art)
        if valeur in attendus:
            break
        page.wait_for_timeout(250)
    if valeur not in attendus:
        notes.append(f"Vœu {vid} : compteur de caractères inattendu après saisie, non enregistrée.")
        return False

    # « Enregistrer » de CET article seulement
    bouton_enreg = art.get_by_role("button", name=profil.libelle_bouton_enregistrer, exact=True)
    if bouton_enreg.count() != 1 or not _cliquer_garde(bouton_enreg, profil.libelle_bouton_enregistrer, est_interdit):
        notes.append(f"Vœu {vid} : bouton « {profil.libelle_bouton_enregistrer} » indisponible.")
        return False

    # Contrôle final : le libellé « À compléter » de l'article a disparu
    for _ in range(20):
        art2, _i2, etat2 = _trouver_article(page, profil, voeu, niveau)
        if art2 is not None and not _a_completer_present(art2, profil):
            return True
        page.wait_for_timeout(250)
    notes.append(f"Vœu {vid} : enregistrement de la motivation non confirmé (« {profil.libelle_a_completer} » toujours affiché).")
    return False


def _ajouter_voeux_roles(
    page: Page,
    voeux: list[dict[str, Any]],
    *,
    profil: ProfilSelecteursPanier,
    est_interdit: Callable[[str, str, str], bool],
    detecteur_blocage: Callable[[Page], bool],
) -> tuple[list[dict[str, Any]], list[str], bool]:
    """Mode « roles » : vrai portail Études en France (ou sa maquette fidèle)."""
    resultats: list[dict[str, Any]] = []
    notes: list[str] = []
    blocage = False

    def tout_en_erreur(message: str) -> tuple[list[dict[str, Any]], list[str], bool]:
        for v in voeux:
            resultats.append(_nouveau_resultat(v, STATUT_ERREUR))
        notes.append(message)
        return resultats, notes, False

    # Le site passe en affichage mobile sous ~900 px (filtres cachés) : fenêtre fixée à 1280x900 avant d'agir.
    try:
        page.set_viewport_size({"width": profil.largeur_page, "height": profil.hauteur_page})
    except Exception:
        notes.append("Taille de fenêtre non modifiable : les filtres du catalogue peuvent être masqués (affichage mobile).")

    if detecteur_blocage(page):
        return tout_en_erreur("CAPTCHA ou double authentification détecté (Règle 2) : pause immédiate.")[0], notes, True

    # État initial du panier (anti-limite)
    try:
        if not _aller_a(page, profil, profil.chemin_panier):
            return tout_en_erreur(
                "Le portail n'a pas ouvert le panier (session fermée ou redirection) : connectez-vous "
                "vous-même au portail puis relancez (Règle 3). Aucun vœu ajouté."
            )
        articles_init = _lire_articles_panier(page, profil)
        nb_panier = _compter_panier(page, articles_init)
    except Exception as exc:  # noqa: BLE001
        return tout_en_erreur(f"Panier illisible (erreur technique {type(exc).__name__}) : aucun vœu ajouté.")

    for voeu in voeux:
        if blocage or detecteur_blocage(page):
            blocage = True
            resultats.append(_nouveau_resultat(voeu, STATUT_ERREUR))
            continue

        refus, motivation = valider_voeu(voeu)
        if refus is not None:
            resultats.append(_nouveau_resultat(voeu, refus, nb=len(motivation)))
            notes.append(f"Vœu {voeu.get('voeu_id')} : {refus} (non ajouté).")
            continue

        res = _nouveau_resultat(voeu, STATUT_ERREUR, nb=len(motivation))
        resultats.append(res)
        vid = voeu.get("voeu_id")
        try:
            # 1. Catalogue : champ « Libellé de la formation » + « Rechercher »
            if not _aller_a(page, profil, profil.chemin_catalogue):
                notes.append(f"Vœu {vid} : catalogue inaccessible (session fermée ou redirection).")
                continue
            if detecteur_blocage(page):
                blocage = True
                continue
            champ = page.get_by_label(profil.libelle_champ_recherche)
            if champ.count() == 0 or not champ.first.is_visible():
                notes.append(
                    f"Vœu {vid} : champ « {profil.libelle_champ_recherche} » introuvable "
                    "(affichage mobile ou page inattendue) ; rien ajouté."
                )
                continue
            champ.first.fill(str(voeu["intitule"]).strip(), timeout=3000)
            bouton_rech = page.get_by_role("button", name=profil.libelle_bouton_rechercher, exact=True)
            if not _cliquer_garde(bouton_rech, profil.libelle_bouton_rechercher, est_interdit):
                champ.first.press("Enter")
            try:
                page.wait_for_load_state("networkidle", timeout=4000)
            except Exception:
                pass
            page.wait_for_timeout(250)
            if detecteur_blocage(page):
                blocage = True
                continue

            # 2. Correspondance exacte (intitulé ET établissement) filtrée côté client
            cartes = _lire_cartes_resultats(page, profil)
            candidats = _candidats_depuis_cartes(cartes, voeu)
            statut_match, _candidat, idx = _selectionner_correspondance(candidats, voeu)
            if statut_match == "introuvable":
                res["statut"] = STATUT_INTROUVABLE
                notes.append(f"Vœu {vid} : aucune formation du catalogue ne correspond (rien ajouté).")
                continue
            if statut_match == "ambigu":
                res["statut"] = STATUT_AMBIGU
                notes.append(f"Vœu {vid} : plusieurs formations correspondent (rien ajouté).")
                continue

            # 3. Fiche de la formation
            lien = page.locator(f'a[href^="{profil.prefixe_chemin}{profil.chemin_catalogue}/formation/"]').nth(idx)
            if not _cliquer_garde(lien, "lien de la formation", est_interdit):
                notes.append(f"Vœu {vid} : fiche de la formation inaccessible.")
                continue
            try:
                page.wait_for_url(_RE_IDS_FICHE, timeout=8000)
                page.wait_for_load_state("networkidle", timeout=4000)
            except Exception:
                pass
            ids = _RE_IDS_FICHE.search(page.url or "")
            if not ids:
                notes.append(f"Vœu {vid} : fiche de la formation non ouverte.")
                continue
            id_formation, id_site = ids.group(1), ids.group(2)
            if detecteur_blocage(page):
                blocage = True
                continue

            # 4. Bon bloc de niveau d'entrée
            analyse = page.evaluate(_JS_SECTIONS_NIVEAU, profil.libelle_bouton_ajouter) or {"sections": []}
            etat_choix, section = _choisir_section(analyse.get("sections") or [], voeu)
            if etat_choix == "aucune":
                notes.append(f"Vœu {vid} : aucun titre de niveau d'entrée sur la fiche, rien ajouté.")
                continue
            if etat_choix == "ambigu" or section is None:
                res["statut"] = STATUT_AMBIGU
                notes.append(
                    f"Vœu {vid} : niveau d'entrée absent ou sans correspondance avec plusieurs sections (rien ajouté)."
                )
                continue
            niveau_section = str(section["niveau"])

            # 5. API de lecture (GET, même session) : déjà au panier ? fermé ?
            entrees = _lire_api_fiche(page, profil, id_formation, id_site)
            entree = _entree_pour_niveau(entrees, niveau_section)
            if entree is not None and entree.get("ferme"):
                res["statut"] = STATUT_FERME
                notes.append(f"Vœu {vid} : candidatures fermées pour ce niveau d'entrée (rien ajouté).")
                continue
            if entree is not None and entree.get("ajoute_au_panier"):
                res["statut"] = STATUT_DEJA_PRESENT
                continue
            if section.get("boutons") != 1:
                notes.append(f"Vœu {vid} : bouton « {profil.libelle_bouton_ajouter} » introuvable pour ce niveau (rien ajouté).")
                continue
            if nb_panier >= LIMITE_VOEUX_PANIER:
                res["statut"] = STATUT_REFUSE_LIMITE
                notes.append(f"Vœu {vid} : panier plein ({LIMITE_VOEUX_PANIER} formations maximum), non ajouté.")
                continue

            # 6. « Ajouter au panier » du bon bloc
            if not page.evaluate(_JS_MARQUER_BOUTON, [profil.libelle_bouton_ajouter, section["index_bouton"]]):
                notes.append(f"Vœu {vid} : bouton d'ajout indisponible (rien ajouté).")
                continue
            if not _cliquer_bouton_marque(page, est_interdit, profil.libelle_bouton_ajouter):
                notes.append(f"Vœu {vid} : bouton d'ajout non cliquable (rien ajouté).")
                continue
            confirme_api = entrees is None
            for _ in range(12):
                if entrees is None:
                    break
                relu = _entree_pour_niveau(_lire_api_fiche(page, profil, id_formation, id_site), niveau_section)
                if relu is not None and relu.get("ajoute_au_panier"):
                    confirme_api = True
                    break
                page.wait_for_timeout(250)
            if not confirme_api:
                notes.append(f"Vœu {vid} : ajout non confirmé par le portail (API de lecture).")
                continue
            if detecteur_blocage(page):
                blocage = True
                continue

            # 7. Vérification dans le panier
            if not _aller_a(page, profil, profil.chemin_panier):
                notes.append(f"Vœu {vid} : panier inaccessible après l'ajout.")
                continue
            art, _i, etat_art = _trouver_article(page, profil, voeu, niveau_section)
            if art is None:
                notes.append(f"Vœu {vid} : formation non retrouvée dans le panier après l'ajout ({etat_art}).")
                continue
            nb_panier = _compter_panier(page, _lire_articles_panier(page, profil))
            res["statut"] = STATUT_AJOUTE

            # 8. Motivation puis « Enregistrer », avec vérifications
            if _saisir_et_enregistrer_motivation(page, profil, voeu, niveau_section, motivation, est_interdit, notes):
                res["motivation_enregistree"] = True
            if detecteur_blocage(page):
                blocage = True
        except Exception as exc:  # noqa: BLE001 — jamais de texte d'exception (peut contenir des saisies)
            if res["statut"] != STATUT_AJOUTE:
                res["statut"] = STATUT_ERREUR
            notes.append(f"Vœu {vid} : erreur technique ({type(exc).__name__}).")

    if blocage:
        notes.append(
            "CAPTCHA ou double authentification détecté (Règle 2) : pause immédiate, vœux restants non traités."
        )
    return resultats, notes, blocage


# ---------------------------------------------------------------------------
# Calibration : cartographie des éléments interactifs (aucune valeur lue, aucun clic)
# ---------------------------------------------------------------------------

_SCRIPT_CARTOGRAPHIE = """
(maxElements) => {
  const SELECTEUR = "a, button, input, select, textarea, summary, [role], [onclick], [tabindex], [data-action]";
  const TYPES_BOUTON = ["button", "submit", "reset"];
  const resultats = [];
  const vus = new Set();
  for (const el of document.querySelectorAll(SELECTEUR)) {
    if (resultats.length >= maxElements) break;
    if (vus.has(el)) continue;
    vus.add(el);
    if (el.closest("#__cowork-racine-overlay")) continue;
    const tag = el.tagName.toLowerCase();
    const typeAttr = (el.getAttribute("type") || "").toLowerCase();
    if (tag === "input" && typeAttr === "hidden") continue;

    let texte = "";
    const aria = el.getAttribute("aria-label");
    if (aria) {
      texte = aria;
    } else if (tag === "input" && TYPES_BOUTON.includes(typeAttr)) {
      texte = el.getAttribute("value") || "";          // libellé statique d'un bouton
    } else if (tag === "input" || tag === "select" || tag === "textarea") {
      // Libellé du champ uniquement : jamais value, jamais options, jamais contenu du textarea.
      let lbl = null;
      if (el.id) lbl = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
      if (!lbl) lbl = el.closest("label");
      if (lbl) {
        const clone = lbl.cloneNode(true);
        clone.querySelectorAll("input, select, textarea, option").forEach(n => n.remove());
        texte = clone.textContent || "";
      }
    } else if (el.isContentEditable || ["textbox", "combobox", "searchbox", "spinbutton"].includes(el.getAttribute("role") || "")) {
      texte = "";                                      // contenu éditable = saisie potentielle
    } else {
      texte = el.textContent || "";
    }
    texte = String(texte).replace(/\\s+/g, " ").trim();

    const data = {};
    for (const a of Array.from(el.attributes)) {
      if (a.name.startsWith("data-") && !/value|valeur/i.test(a.name)) data[a.name] = String(a.value).slice(0, 200);
    }
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    const visible = rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden";

    resultats.push({
      balise: tag,
      role: el.getAttribute("role") || "",
      texte: texte,
      id: el.id || "",
      name: el.getAttribute("name") || "",
      classes: (el.getAttribute("class") || "").split(/\\s+/).filter(Boolean),
      data: data,
      placeholder: el.getAttribute("placeholder") || "",
      type: typeAttr,
      visible: visible
    });
  }
  return resultats;
}
"""


def _tronquer_et_masquer(texte: str, longueur: int = LONGUEUR_MAX_LIBELLE_CALIBRATION) -> str:
    return masquer_pii(str(texte or "")[:longueur])


def cartographier_page(
    page: Page,
    *,
    dossier_calibration: Path,
    max_elements: int = 600,
    maintenant: datetime | None = None,
) -> tuple[Path, int]:
    """Enregistre la cartographie des éléments interactifs de la page courante. Retourne (fichier, nb)."""
    bruts: list[dict[str, Any]] = page.evaluate(_SCRIPT_CARTOGRAPHIE, max_elements) or []

    elements: list[dict[str, Any]] = []
    for b in bruts:
        elements.append(
            {
                "balise": str(b.get("balise") or ""),
                "role": _tronquer_et_masquer(b.get("role") or ""),
                "texte": _tronquer_et_masquer(b.get("texte") or ""),
                "id": _tronquer_et_masquer(b.get("id") or "", 120),
                "name": _tronquer_et_masquer(b.get("name") or "", 120),
                "classes": [_tronquer_et_masquer(c, 80) for c in (b.get("classes") or [])][:12],
                "data": {
                    str(k)[:60]: _tronquer_et_masquer(v, LONGUEUR_MAX_LIBELLE_CALIBRATION)
                    for k, v in (b.get("data") or {}).items()
                },
                "placeholder": _tronquer_et_masquer(b.get("placeholder") or ""),
                "type": str(b.get("type") or "")[:30],
                "visible": bool(b.get("visible")),
            }
        )

    instant = maintenant or datetime.now(timezone.utc)
    horodatage = instant.strftime("%Y%m%dT%H%M%S%fZ")
    url = urlsplit(page.url or "")
    url_sure = f"{url.scheme}://{url.netloc}{url.path}" if url.scheme else ""  # sans requête ni fragment
    try:
        titre = page.title() or ""
    except Exception:
        titre = ""

    contenu = {
        "horodatage": horodatage,
        "url": masquer_pii(url_sure)[:300],
        "titre": _tronquer_et_masquer(titre),
        "nb_elements": len(elements),
        "avertissement": (
            "Cartographie de calibration : structure uniquement, aucune valeur saisie ni contenu de champ."
        ),
        "elements": elements,
    }
    dossier_calibration.mkdir(parents=True, exist_ok=True)
    fichier = dossier_calibration / f"{horodatage}.json"
    fichier.write_text(json.dumps(contenu, ensure_ascii=False, indent=2), encoding="utf-8")
    return fichier, len(elements)
