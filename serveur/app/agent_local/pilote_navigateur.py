"""Pilote interactif en temps réel de l'Agent Navigateur Playwright (Style Perplexity Browser Assistant
& Claude Cowork) pour Campus France (Études en France — Guide Septembre 2026) et IRCC Canada.

Ce module permet à l'opérateur du bureau :
1. De contrôler directement son vrai navigateur (Chrome, Edge ou Chromium) en temps réel — et non
   via un simple affichage figé par capture d'écran — avec :
   - Une barre latérale Co-Pilote IA injectée directement dans le navigateur (style Perplexity / Claude Cowork).
   - Un curseur IA animé et un surlignage visuel en direct sur chaque champ rempli ou bouton cliqué.
   - Une synchronisation instantanée avec les vrais sites officiels :
     * Campus France / Études en France : `https://etudesenfrance.diplomatie.gouv.fr/`
     * Campus France Algérie : `https://www.algerie.campusfrance.org/horaires-d-attention-au-public`
     * Paiement IFA Algérie : `https://paiement.if-algerie.com`
     * Portail officiel IRCC Canada : `https://portal-portail.apps.cic.gc.ca/signin?lang=fr`
2. De comprendre le langage naturel de l'opérateur :
   - Consignes directes sur la page (« clique sur S'inscrire », « descends en bas », « mets Oran comme ville »,
     « change l'établissement pour Sorbonne Université », « écris amine@exemple.dz dans l'email »,
     « remplis cette page », « cherche Master Informatique »).
   - Questions contextuelles sur la page ouverte (« qu'est-ce qu'il y a sur cette page ? », « que dois-je faire ? »)
     ou sur le dossier / le Guide Études en France Septembre 2026 / IRCC Canada.
3. D'appliquer de façon infranchissable les 7 règles de sécurité :
   - Règle 1 : Arrêt obligatoire avant toute soumission finale officielle.
   - Règle 2 : Pause immédiate si un CAPTCHA ou une double authentification (2FA) apparaît.
   - Règle 3 : Aucun mot de passe portail ni CléGC stocké (saisie humaine de la connexion).
   - Règle 4 : Zéro valeur par défaut inventée si une donnée du candidat manque.
   - Règle 5 : Aucune donnée personnelle (PII) dans les journaux techniques.
"""

from __future__ import annotations

import base64
import concurrent.futures
import json
import logging
import re
import secrets
import tempfile
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from urllib.parse import urlparse

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, Route, sync_playwright

from app.agent_local.domaines_officiels import PolitiqueNavigation
from app.agent_local.guide_campus_france_2026 import (
    GUIDE_CAMPUS_FRANCE_SEPTEMBRE_2026,
    repondre_question_guide_campus_france,
)
from app.agent_local.portails.panier_voeux import (
    PROFIL_PANIER_DEMO,
    PROFIL_PANIER_REEL,
    profil_maquette_eef,
    STATUT_ERREUR as STATUT_ERREUR_VOEU,
    ProfilSelecteursPanier,
    ajouter_voeux_au_panier,
    cartographier_page,
)
from app.services.conseiller_dossier import LIBELLES_CHAMPS_CANDIDAT_FR

journal = logging.getLogger("app.agent_local.pilote")

URLS_CIBLES_OFFICIELS: dict[str, str] = {
    "campus_france_officiel": "https://etudesenfrance.diplomatie.gouv.fr/",
    "campus_france_pastel": "https://pastel.diplomatie.gouv.fr/etudesenfrance",
    "campus_france_algerie": "https://www.algerie.campusfrance.org/horaires-d-attention-au-public",
    "paiement_ifa_algerie": "https://paiement.if-algerie.com",
    "demo_campus_france": "http://portail.local/demo/campus-france",
    # Maquette fidèle du vrai portail Études en France (structure observée) : tests uniquement
    "demo_eef_reel": "http://portail.local/demo/eef-reel/catalogue-formations",
    "ircc_officiel": "https://portal-portail.apps.cic.gc.ca/signin?lang=fr",
    "ircc_canada_info": "https://www.canada.ca/fr/immigration-refugies-citoyennete/services/etudier-canada/permis-etudes.html",
    "demo_ircc": "http://portail.local/demo/ircc",
}

DOMAINES_FAMILLE_CAMPUS_FRANCE: tuple[str, ...] = (
    "diplomatie.gouv.fr",
    "campusfrance.org",
    "if-algerie.com",
    "demo/campus-france",
    "demo/eef-reel",
)

DOMAINES_FAMILLE_IRCC: tuple[str, ...] = (
    "cic.gc.ca",
    "canada.ca",
    "demo/ircc",
)

MOTS_CLES_SOUMISSION_INTERDITE_REGLE1: tuple[str, ...] = (
    "soumettre definitivement",
    "soumettre mon dossier",
    "soumettre le dossier",
    "soumettre ce dossier",
    "soumettre la candidature",
    "soumettre ma candidature",
    "soumettre la demande",
    "soumettre ma demande",
    "soumettre ma declaration",
    "soumettre la declaration",
    "cliquer sur soumettre",
    "clique sur soumettre",
    "appuyer sur soumettre",
    "valider et soumettre",
    "envoyer definitivement",
    "envoi definitif",
    "soumission finale",
    "soumission definitive",
    "confirmer mon rendez-vous",
    "confirmer le rendez-vous",
    "signer et transmettre",
    "signer electroniquement",
    "transmettre la demande",
    "transmettre ma demande",
    "transmettre le dossier",
    "transmettre et payer",
    "payer et transmettre",
    "payer et soumettre",
    "signature electronique finale",
)

CLAUSES_NEGATION_SECURITE_REGLE1: tuple[str, ...] = (
    "sans soumettre",
    "ne pas soumettre",
    "avant de soumettre",
    "avant soumission",
    "avant la soumission",
    "sans transmettre",
    "ne pas transmettre",
    "avant de transmettre",
    "avant transmission",
    "avant la transmission",
    "sans envoyer",
    "ne pas envoyer",
    "arret avant",
    "s'arreter avant",
    "s arreter avant",
)


# ---------------------------------------------------------------------------
# Script Co-Pilote IA injecté directement dans le navigateur (Style Perplexity / Claude Cowork)
# ---------------------------------------------------------------------------

SCRIPT_COPILOTE_COWORK_INJECTE = """
(() => {
  // Jamais dans un iframe (ex. éditeur de texte riche du panier) : le panneau y polluerait le contenu saisi.
  if (window.top !== window) return;
  if (window.__COWORK_COPILOTE_ACTIF__) return;
  window.__COWORK_COPILOTE_ACTIF__ = true;
  window.__COWORK_FILE_COMMANDES__ = window.__COWORK_FILE_COMMANDES__ || [];

  function installerStylesEtOverlay() {
    if (!document.body || document.getElementById("__cowork-racine-overlay")) return;

    const style = document.createElement("style");
    style.id = "__cowork-styles";
    style.textContent = `
      #__cowork-cadre-aura {
        position: fixed;
        inset: 0;
        pointer-events: none;
        z-index: 2147483640;
        box-shadow: inset 0 0 0 3px rgba(37, 99, 235, 0.55), inset 0 0 18px rgba(37, 99, 235, 0.18);
        transition: box-shadow 0.25s ease;
      }
      #__cowork-cadre-aura.actif-action {
        box-shadow: inset 0 0 0 4px rgba(16, 185, 129, 0.8), inset 0 0 28px rgba(16, 185, 129, 0.28);
      }
      #__cowork-curseur-ia {
        position: fixed;
        top: -100px;
        left: -100px;
        z-index: 2147483645;
        pointer-events: none;
        transition: transform 0.28s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.2s ease;
        opacity: 0;
        display: flex;
        align-items: center;
        gap: 6px;
      }
      #__cowork-curseur-ia.visible {
        opacity: 1;
      }
      #__cowork-bulle-curseur {
        background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 100%);
        color: #ffffff;
        font-family: Segoe UI, system-ui, -apple-system, sans-serif;
        font-size: 12px;
        font-weight: 700;
        padding: 5px 10px;
        border-radius: 999px;
        box-shadow: 0 6px 18px rgba(15, 23, 42, 0.38);
        border: 1px solid rgba(147, 197, 253, 0.6);
        white-space: nowrap;
      }
      .__cowork-cible-active {
        outline: 3px solid #2563eb !important;
        outline-offset: 2px !important;
        box-shadow: 0 0 0 5px rgba(37, 99, 235, 0.22) !important;
        transition: outline 0.2s ease, box-shadow 0.2s ease !important;
      }
      #__cowork-dock-assistant {
        position: fixed;
        right: 16px;
        bottom: 16px;
        width: 370px;
        max-width: calc(100vw - 32px);
        background: rgba(15, 23, 42, 0.96);
        color: #f8fafc;
        border: 1px solid rgba(96, 165, 250, 0.45);
        border-radius: 14px;
        box-shadow: 0 16px 40px rgba(2, 6, 23, 0.55);
        z-index: 2147483646;
        font-family: Segoe UI, system-ui, -apple-system, sans-serif;
        overflow: hidden;
        backdrop-filter: blur(10px);
      }
      #__cowork-dock-assistant.reduit {
        width: 260px;
      }
      #__cowork-dock-assistant.reduit #__cowork-dock-corps {
        display: none;
      }
      #__cowork-dock-entete {
        background: linear-gradient(90deg, #1e3a8a 0%, #0f172a 100%);
        padding: 10px 14px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        cursor: pointer;
        border-bottom: 1px solid rgba(148, 163, 184, 0.2);
      }
      #__cowork-dock-entete .titre {
        font-size: 13px;
        font-weight: 700;
        color: #93c5fd;
        display: flex;
        align-items: center;
        gap: 7px;
      }
      #__cowork-dock-entete .point-live {
        width: 9px;
        height: 9px;
        border-radius: 50%;
        background: #22c55e;
        box-shadow: 0 0 8px #22c55e;
        display: inline-block;
      }
      #__cowork-dock-corps {
        padding: 12px;
        display: flex;
        flex-direction: column;
        gap: 9px;
      }
      #__cowork-journal-live {
        max-height: 175px;
        overflow-y: auto;
        background: rgba(30, 41, 59, 0.85);
        border: 1px solid rgba(148, 163, 184, 0.25);
        border-radius: 9px;
        padding: 9px 10px;
        font-size: 12.5px;
        line-height: 1.45;
        color: #e2e8f0;
      }
      .cowork-msg {
        margin-bottom: 7px;
        padding-bottom: 6px;
        border-bottom: 1px solid rgba(148, 163, 184, 0.15);
      }
      .cowork-msg:last-child {
        margin-bottom: 0;
        padding-bottom: 0;
        border-bottom: none;
      }
      .cowork-puces {
        display: flex;
        flex-wrap: wrap;
        gap: 5px;
      }
      .cowork-puce {
        background: rgba(37, 99, 235, 0.25);
        color: #bfdbfe;
        border: 1px solid rgba(96, 165, 250, 0.4);
        border-radius: 999px;
        padding: 4px 9px;
        font-size: 11.5px;
        cursor: pointer;
        font-weight: 600;
      }
      .cowork-puce:hover {
        background: rgba(37, 99, 235, 0.5);
        color: #ffffff;
      }
      .cowork-barre-saisie {
        display: flex;
        gap: 6px;
        align-items: center;
      }
      #__cowork-champ-consigne {
        flex: 1;
        background: #0f172a;
        color: #f8fafc;
        border: 1px solid #475569;
        border-radius: 8px;
        padding: 7px 10px;
        font-size: 12.5px;
        outline: none;
      }
      #__cowork-champ-consigne:focus {
        border-color: #60a5fa;
      }
      .cowork-btn {
        background: #2563eb;
        color: #ffffff;
        border: none;
        border-radius: 8px;
        padding: 7px 11px;
        font-size: 12px;
        font-weight: 700;
        cursor: pointer;
      }
      .cowork-btn:hover {
        background: #1d4ed8;
      }
    `;
    document.head.appendChild(style);

    const racine = document.createElement("div");
    racine.id = "__cowork-racine-overlay";
    racine.innerHTML = `
      <div id="__cowork-cadre-aura"></div>
      <div id="__cowork-curseur-ia">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="#2563eb" stroke="#ffffff" stroke-width="2">
          <path d="M4 3l16 7-7 2-2 7L4 3z"/>
        </svg>
        <span id="__cowork-bulle-curseur">Co-Pilote IA</span>
      </div>
      <div id="__cowork-dock-assistant">
        <div id="__cowork-dock-entete" title="Cliquer pour réduire ou agrandir le Co-Pilote">
          <div class="titre">
            <span class="point-live"></span>
            <span>Co-Pilote Navigateur IA (Direct)</span>
          </div>
          <span id="__cowork-btn-reduire" style="font-size:12px; color:#cbd5e1;">Réduire ▾</span>
        </div>
        <div id="__cowork-dock-corps">
          <div id="__cowork-journal-live">
            <div class="cowork-msg">
              <strong>Co-Pilote actif sur cette page.</strong><br/>
              Écrivez ou dictez ce que je dois faire (ex: <em>« remplis cette page »</em>, <em>« clique sur S'inscrire »</em>, <em>« mets Oran comme ville »</em>, <em>« analyse cette page »</em>). Arrêt garanti avant soumission finale (Règle 1).
            </div>
          </div>
          <div class="cowork-puces">
            <button type="button" class="cowork-puce" data-cmd="Remplis tous les champs de cette page sans soumettre">⚡ Tout remplir ici</button>
            <button type="button" class="cowork-puce" data-cmd="Analyse cette page et explique-moi quoi faire">🔍 Analyser la page</button>
            <button type="button" class="cowork-puce" data-cmd="Remplis mon identité et mon passeport">🪪 Identité</button>
            <button type="button" class="cowork-puce" data-cmd="Remplis mes motivations">✍️ Motivations</button>
            <button type="button" class="cowork-puce" data-cmd="Descends en bas de la page">⬇️ Descendre</button>
          </div>
          <div class="cowork-barre-saisie">
            <input id="__cowork-champ-consigne" type="text" placeholder="Parlez au Co-Pilote (ex: clique sur..., remplis...)" />
            <button id="__cowork-btn-micro" type="button" class="cowork-btn" style="background:#334155;" title="Dicter à la voix">🎤</button>
            <button id="__cowork-btn-envoyer" type="button" class="cowork-btn">Go</button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(racine);

    const dock = document.getElementById("__cowork-dock-assistant");
    document.getElementById("__cowork-dock-entete").addEventListener("click", () => {
      dock.classList.toggle("reduit");
      document.getElementById("__cowork-btn-reduire").textContent =
        dock.classList.contains("reduit") ? "Ouvrir ▴" : "Réduire ▾";
    });

    async function envoyerConsigneLocale(texte) {
      if (!texte || !texte.trim()) return;
      const propre = texte.trim();
      window.__coworkAjouterMessage("Vous", propre);
      window.__COWORK_FILE_COMMANDES__.push(propre);

      // URL du serveur injectée par le pilote (paramètre url_publique_plateforme) : jamais codée en dur.
      // Sans URL, la consigne reste dans la file, relevée par le serveur (état temps réel).
      const urlServeur = window.__COWORK_URL_SERVEUR__ || "";
      const jetonBridge = window.__COWORK_JETON_BRIDGE__ || "";
      if (!urlServeur || !jetonBridge) return;
      try {
        const rep = await fetch(urlServeur + "/api/v1/portails/copilote-bridge", {
          method: "POST",
          credentials: "omit",
          headers: {
            "Content-Type": "application/json",
            "X-Copilote-Bridge-Token": jetonBridge
          },
          body: JSON.stringify({
            instruction_libre: propre,
            url_courante: window.location.href
          })
        });
        if (rep.ok) {
          const data = await rep.json();
          window.__COWORK_FILE_COMMANDES__.pop();
          window.__coworkAjouterMessage("Co-Pilote IA", data.reponse_agent || data.resume_francais || "Action exécutée.");
        }
      } catch (_err) {
        // Si la page bloque le fetch externe, la file window.__COWORK_FILE_COMMANDES__ prend le relais
      }
    }

    document.getElementById("__cowork-btn-envoyer").addEventListener("click", () => {
      const inp = document.getElementById("__cowork-champ-consigne");
      const val = inp.value;
      inp.value = "";
      envoyerConsigneLocale(val);
    });

    document.getElementById("__cowork-champ-consigne").addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") {
        ev.preventDefault();
        const inp = document.getElementById("__cowork-champ-consigne");
        const val = inp.value;
        inp.value = "";
        envoyerConsigneLocale(val);
      }
    });

    document.querySelectorAll("#__cowork-dock-assistant .cowork-puce").forEach((b) => {
      b.addEventListener("click", () => {
        envoyerConsigneLocale(b.getAttribute("data-cmd"));
      });
    });

    const btnMicro = document.getElementById("__cowork-btn-micro");
    const RecoVocale = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (RecoVocale) {
      const reco = new RecoVocale();
      reco.lang = "fr-FR";
      reco.interimResults = false;
      reco.onresult = (ev) => {
        const transcrit = ev.results[0][0].transcript;
        document.getElementById("__cowork-champ-consigne").value = transcrit;
        envoyerConsigneLocale(transcrit);
      };
      btnMicro.addEventListener("click", () => {
        try {
          reco.start();
          window.__coworkAjouterMessage("Co-Pilote IA", "🎤 Écoute vocale active... Parlez maintenant.");
        } catch (_e) {}
      });
    } else {
      btnMicro.style.display = "none";
    }
  }

  window.__coworkAjouterMessage = function(auteur, texte) {
    installerStylesEtOverlay();
    const journalEl = document.getElementById("__cowork-journal-live");
    if (!journalEl) return;
    const div = document.createElement("div");
    div.className = "cowork-msg";
    const strong = document.createElement("strong");
    strong.style.color = auteur === "Vous" ? "#93c5fd" : "#4ade80";
    strong.textContent = auteur + " : ";
    const span = document.createElement("span");
    span.textContent = texte;
    div.appendChild(strong);
    div.appendChild(span);
    journalEl.appendChild(div);
    journalEl.scrollTop = journalEl.scrollHeight;
  };

  window.__coworkAnimerElement = function(el, libelle) {
    installerStylesEtOverlay();
    if (!el) return;
    try {
      document.querySelectorAll(".__cowork-cible-active").forEach((n) => n.classList.remove("__cowork-cible-active"));
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.classList.add("__cowork-cible-active");
      const rect = el.getBoundingClientRect();
      const curseur = document.getElementById("__cowork-curseur-ia");
      const bulle = document.getElementById("__cowork-bulle-curseur");
      const aura = document.getElementById("__cowork-cadre-aura");
      if (bulle && libelle) bulle.textContent = libelle;
      if (aura) aura.classList.add("actif-action");
      if (curseur) {
        const x = Math.max(12, Math.min(window.innerWidth - 220, rect.left + Math.min(rect.width / 2, 80)));
        const y = Math.max(12, Math.min(window.innerHeight - 50, rect.top + Math.min(rect.height / 2, 24)));
        curseur.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px)`;
        curseur.classList.add("visible");
      }
      clearTimeout(window.__coworkTimerCurseur);
      window.__coworkTimerCurseur = setTimeout(() => {
        if (curseur) curseur.classList.remove("visible");
        if (aura) aura.classList.remove("actif-action");
      }, 2200);
    } catch (_e) {}
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", installerStylesEtOverlay);
  } else {
    installerStylesEtOverlay();
  }
})();
"""


def _normaliser_sans_accents(texte: str) -> str:
    decomposed = unicodedata.normalize("NFD", texte.strip().lower())
    sans_accents = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", sans_accents)


@dataclass
class ResultatActionNavigateur:
    succes: bool
    code_demarche: str
    cible: str
    action_executee: str
    url_courante: str
    titre_page: str
    resume_francais: str
    reponse_agent: str = ""
    etapes_realisees: list[str] = field(default_factory=list)
    champs_remplis_libelles: list[str] = field(default_factory=list)
    pieces_televersees_libelles: list[str] = field(default_factory=list)
    champs_manquants_libelles: list[str] = field(default_factory=list)
    avertissements_securite: list[str] = field(default_factory=list)
    elements_interactifs_page: list[dict[str, str]] = field(default_factory=list)
    modifications_candidat_detectees: dict[str, Any] = field(default_factory=dict)
    arret_regle1_avant_soumission: bool = True
    blocage_captcha_ou_2fa: bool = False
    attente_connexion_humaine_regle3: bool = False
    mode_controle_direct: bool = True
    capture_base64: str | None = None
    capture_png_octets: bytes | None = None
    # Action « ajouter_voeux_panier » : un dict par vœu (voeu_id, intitule, etablissement, statut,
    # motivation_enregistree, nb_caracteres) — jamais de texte de motivation.
    resultats_voeux: list[dict[str, Any]] = field(default_factory=list)
    # Action « cartographier_page » : chemin du fichier de calibration (structure du DOM, sans valeurs)
    fichier_calibration: str | None = None


_MESSAGE_REFUS_PORTAIL_NON_HOMOLOGUE = (
    "Action « ajouter_voeux_panier » refusée sur le vrai portail Études en France : le portail n'est pas "
    "homologué (statut « non testé », Règle 6). Les sélecteurs du vrai portail n'ont jamais été validés. "
    "Lancez d'abord « cartographier_page » lors d'une session supervisée où vous êtes connecté, faites "
    "recalibrer les sélecteurs, puis faites valider le portail par l'administrateur. "
    "L'action reste disponible sur la page de démonstration (/demo/campus-france)."
)
ACTION_AJOUTER_VOEUX_PANIER = "ajouter_voeux_panier"
ACTION_CARTOGRAPHIER_PAGE = "cartographier_page"
# Actions qui ne doivent jamais déclencher la synchronisation « tâche / validation humaine »
ACTIONS_PANIER_ET_CALIBRATION: frozenset[str] = frozenset(
    {ACTION_AJOUTER_VOEUX_PANIER, ACTION_CARTOGRAPHIER_PAGE}
)
DOMAINES_OFFICIELS_CAMPUS_FRANCE_REEL: tuple[str, ...] = (
    "etudesenfrance.diplomatie.gouv.fr",
    "pastel.diplomatie.gouv.fr",
    "www.algerie.campusfrance.org",
    "paiement.if-algerie.com",
)


def _verifier_instruction_non_interdite_regle1(instruction: str) -> str | None:
    """Vérifie de façon insensible à la casse et aux accents si l'instruction demande
    de cliquer sur un bouton de soumission officielle ou de transmission finale (Règle 1)."""
    inst_norm = _normaliser_sans_accents(instruction)
    for clause_saine in CLAUSES_NEGATION_SECURITE_REGLE1:
        inst_norm = inst_norm.replace(clause_saine, " ")

    for interdit in MOTS_CLES_SOUMISSION_INTERDITE_REGLE1:
        if interdit in inst_norm:
            return (
                f"Arrêt de sécurité (Règle 1) : l'action « {interdit} » est une soumission officielle "
                "finale strictement réservée à l'opérateur humain. L'agent a préparé le dossier et "
                "s'est arrêté avant le bouton final."
            )
    return None


def _detecter_captcha_ou_2fa_sur_page(page: Page) -> bool:
    selecteurs_sec = (
        "#bloc-captcha-securite",
        "#bloc-captcha-eef",
        "#bloc-2fa-eef",
        "#bloc-captcha-ircc",
        "#bloc-2fa-ircc",
        "#ircc-mfa-prompt",
        "#gckey-security-question",
        ".g-recaptcha",
        ".h-captcha",
        "iframe[src*='recaptcha']",
        "iframe[src*='hcaptcha']",
    )
    for sel in selecteurs_sec:
        try:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible():
                return True
        except Exception:
            continue
    return False


def _portail_reel_non_connecte(page: Page) -> bool:
    """Indique si la page courante d'un portail réel est affichée SANS session opérateur
    (page de connexion, ou lien « Se connecter » visible sans lien de déconnexion)."""
    url = (page.url or "").lower()
    if "/authentification/login" in url or "/login" in url.split("?")[0]:
        return True
    try:
        lien_deconnexion = page.locator(
            "a:has-text('Se déconnecter'), button:has-text('Se déconnecter'), "
            "a:has-text('Déconnexion'), button:has-text('Déconnexion')"
        )
        if lien_deconnexion.count() > 0:
            return False
        lien_connexion = page.locator("a:has-text('Se connecter'), button:has-text('Se connecter')")
        return lien_connexion.count() > 0 and lien_connexion.first.is_visible()
    except Exception:
        return False


def _est_element_soumission_interdit_regle1(sel: str, texte_element: str, attr_officiel: str) -> bool:
    sel_norm = _normaliser_sans_accents(sel)
    if any(
        m in sel_norm
        for m in (
            "soumission-finale",
            "soumettre-definitivement",
            "soumettre-dossier",
            "transmettre-et-payer",
            "signature-electronique-finale",
            "submit-official-application",
            "transmettre-demande-ircc",
        )
    ):
        return True
    if attr_officiel.strip():
        return True
    txt_norm = _normaliser_sans_accents(texte_element)
    if any(
        m in txt_norm
        for m in (
            "soumettre mon dossier",
            "soumettre definitivement",
            "soumettre ma declaration",
            "confirmer mon rendez-vous",
            "signer et transmettre",
            "transmettre la demande",
            "transmettre et payer",
            "signature electronique finale",
        )
    ):
        return True
    return False


def _animer_element_dans_navigateur(page: Page, locator_cible: Any, libelle_action: str) -> None:
    try:
        locator_cible.evaluate(
            "(el, lbl) => { if (window.__coworkAnimerElement) window.__coworkAnimerElement(el, lbl); }",
            libelle_action,
        )
    except Exception:
        pass


def _remplir_si_present(
    page: Page,
    selecteurs: list[str],
    valeur: str | None,
    *,
    type_champ: str = "texte",
    libelle_visuel: str = "",
) -> bool:
    if valeur is None or not str(valeur).strip():
        return False
    texte = str(valeur).strip()
    for sel in selecteurs:
        try:
            loc = page.locator(sel)
            if loc.count() > 0:
                cible = loc.first
                if not cible.is_visible():
                    continue
                _animer_element_dans_navigateur(
                    page,
                    cible,
                    f"✍️ {libelle_visuel or sel} : {texte[:28]}",
                )
                if type_champ == "liste":
                    try:
                        cible.select_option(texte, timeout=1500)
                        return True
                    except Exception:
                        try:
                            cible.select_option(label=texte, timeout=1500)
                            return True
                        except Exception:
                            pass
                else:
                    cible.fill(texte, timeout=1500)
                    return True
        except Exception:
            continue
    return False


def _cliquer_si_present(page: Page, selecteurs: list[str], *, libelle_visuel: str = "") -> bool:
    for sel in selecteurs:
        if _est_element_soumission_interdit_regle1(sel, "", ""):
            continue
        try:
            loc = page.locator(sel)
            if loc.count() > 0:
                cible_loc = loc.first
                if not cible_loc.is_visible():
                    continue
                texte_el = ""
                attr_off = ""
                try:
                    texte_el = cible_loc.inner_text(timeout=400) or ""
                except Exception:
                    pass
                try:
                    attr_off = cible_loc.get_attribute("data-action-officielle", timeout=400) or ""
                except Exception:
                    pass
                if _est_element_soumission_interdit_regle1(sel, texte_el, attr_off):
                    continue
                _animer_element_dans_navigateur(
                    page,
                    cible_loc,
                    f"🖱️ Clic : {libelle_visuel or texte_el.strip()[:30] or sel}",
                )
                cible_loc.click(timeout=1500)
                return True
        except Exception:
            continue
    return False


def _determiner_antenne_algerie(lieu_ou_adresse: str | None) -> str:
    texte = (lieu_ou_adresse or "").lower()
    if any(v in texte for v in ("oran", "mostaganem", "mascara", "sidi bel", "relizane", "tiaret")):
        return "Oran"
    if any(v in texte for v in ("constantine", "sétif", "setif", "batna", "biskra", "jijel", "mila", "oum el bouaghi")):
        return "Constantine"
    if any(v in texte for v in ("annaba", "skikda", "guelma", "tarf", "souk ahras", "tebessa", "tébessa")):
        return "Annaba"
    if any(v in texte for v in ("tlemcen", "temouchent", "témouchent", "saïda", "saida", "bechar", "béchar", "adrar")):
        return "Tlemcen"
    return "Alger"


def _generer_motivation_personnalisee(candidat: dict[str, Any]) -> str:
    nom = candidat.get("nom") or ""
    prenom = candidat.get("prenom") or ""
    niveau = candidat.get("niveau_actuel") or "mon cursus universitaire actuel"
    prog = candidat.get("programme_vise") or "la formation visée"
    etab = candidat.get("etablissement_vise") or "votre établissement"
    return (
        f"Madame, Monsieur,\n\n"
        f"Actuellement titulaire / inscrit(e) en {niveau}, je souhaite vivement intégrer "
        f"la formation « {prog} » au sein de {etab}.\n\n"
        f"Ce projet d'études s'inscrit dans la continuité directe de mon parcours académique "
        f"et répond à mon objectif professionnel d'approfondir mes compétences scientifiques "
        f"et méthodologiques dans un environnement d'excellence reconnu internationalement. "
        f"La qualité des enseignements dispensés à {etab} constitue un atout déterminant "
        f"pour la réussite de mon projet professionnel à l'issue de ma formation.\n\n"
        f"Sérieux(se), rigoureux(se) et pleinement investi(e), je me tiens à votre disposition "
        f"pour tout entretien pédagogique Campus France.\n\n"
        f"Veuillez agréer, Madame, Monsieur, l'expression de ma considération distinguée.\n"
        f"{prenom} {nom}".strip()
    )


def inspecter_elements_interactifs_page(page: Page) -> list[dict[str, str]]:
    """Inspecte en direct le DOM de la page active (< 15 ms) sans capture d'écran,
    pour retourner les champs, listes, zones de texte et boutons visibles."""
    script_inspection = """
    () => {
      const resultats = [];
      const noeuds = document.querySelectorAll(
        "input:not([type='hidden']), select, textarea, button, a[href], [role='button'], span[onclick]"
      );
      for (const el of noeuds) {
        if (resultats.length >= 45) break;
        if (el.closest("#__cowork-racine-overlay")) continue;
        const style = window.getComputedStyle(el);
        if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") continue;
        const rect = el.getBoundingClientRect();
        if (rect.width < 4 || rect.height < 4) continue;

        const tag = el.tagName.toLowerCase();
        const typeAttr = (el.getAttribute("type") || "").toLowerCase();
        let typeEl = "bouton";
        if (tag === "select") typeEl = "liste";
        else if (tag === "textarea") typeEl = "zone_texte";
        else if (tag === "a") typeEl = "lien";
        else if (tag === "input" && !["button", "submit", "reset"].includes(typeAttr)) {
          typeEl = typeAttr === "file" ? "fichier" : "champ";
        }

        let libelle = "";
        if (el.id) {
          const lblFor = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
          if (lblFor) libelle = lblFor.innerText;
        }
        if (!libelle) {
          const parentLbl = el.closest("label");
          if (parentLbl) {
            const clone = parentLbl.cloneNode(true);
            clone.querySelectorAll("input, select, textarea").forEach(n => n.remove());
            libelle = clone.innerText;
          }
        }
        if (!libelle) {
          libelle = el.getAttribute("aria-label")
            || el.getAttribute("placeholder")
            || el.innerText
            || el.getAttribute("value")
            || el.getAttribute("name")
            || el.id
            || "";
        }
        libelle = String(libelle).replace(/\\s+/g, " ").trim().slice(0, 90);
        if (!libelle) continue;

        let selecteur = "";
        if (el.id) selecteur = "#" + el.id;
        else if (el.getAttribute("name")) selecteur = `${tag}[name="${el.getAttribute("name")}"]`;
        else if (typeEl === "bouton" || typeEl === "lien") {
          const court = libelle.slice(0, 40).replace(/"/g, "");
          selecteur = `${tag}:has-text("${court}")`;
        }
        if (!selecteur) continue;

        const attrOff = el.getAttribute("data-action-officielle") || "";
        const valeur = (tag === "input" || tag === "select" || tag === "textarea")
          ? (typeAttr === "password" ? "***" : String(el.value || "").slice(0, 80))
          : "";

        resultats.push({
          type_element: typeEl,
          libelle: libelle,
          selecteur: selecteur,
          valeur: valeur,
          attr_officiel: attrOff
        });
      }
      return resultats;
    }
    """
    try:
        bruts = page.evaluate(script_inspection) or []
    except Exception:
        return []

    propres: list[dict[str, str]] = []
    for item in bruts:
        sel = str(item.get("selecteur") or "")
        lib = str(item.get("libelle") or "")
        attr_off = str(item.get("attr_officiel") or "")
        interdit = _est_element_soumission_interdit_regle1(sel, lib, attr_off)
        propres.append(
            {
                "type_element": str(item.get("type_element") or "champ"),
                "libelle": lib,
                "selecteur": sel,
                "valeur": str(item.get("valeur") or ""),
                "interdit_regle1": "oui" if interdit else "non",
            }
        )
    return propres


def _remplir_formulaire_intelligent_dom(
    page: Page,
    candidat: dict[str, Any],
    champs_remplis: list[str],
) -> int:
    """Parcourt intelligemment le DOM réel de la page active (Campus France officiel, IRCC officiel,
    ou n'importe quel formulaire ouvert) et associe les étiquettes/placeholders/attributs aux données
    réelles du candidat (sans jamais inventer de valeur — Règle 4, ni toucher aux mots de passe — Règle 3)."""
    elements = inspecter_elements_interactifs_page(page)
    nb_ajoutes = 0
    antenne = _determiner_antenne_algerie(candidat.get("lieu_naissance") or candidat.get("adresse"))

    regles_association: list[tuple[tuple[str, ...], tuple[str, ...], str | None, str]] = [
        (("nom de famille", "family name", "last name", "surname", "votre nom"), ("prenom", "first", "payeur", "formation"), candidat.get("nom"), "Nom de famille"),
        (("prenom", "first name", "given name"), ("nom de famille",), candidat.get("prenom"), "Prénom"),
        (("date de naissance", "date of birth", "birth date"), (), candidat.get("date_naissance"), "Date de naissance"),
        (("lieu de naissance", "ville de naissance", "place of birth", "city of birth"), (), candidat.get("lieu_naissance"), "Lieu de naissance"),
        (("nationalite", "citoyennete", "nationality", "citizenship"), (), candidat.get("nationalite"), "Nationalité"),
        (("pays de residence", "country of residence"), (), candidat.get("pays_residence"), "Pays de résidence"),
        (("e-mail", "email", "courriel", "adresse mail"), (), candidat.get("email"), "Adresse e-mail"),
        (("telephone", "mobile", "phone", "tel"), (), candidat.get("telephone"), "Numéro de téléphone"),
        (("numero de piece", "numero de passeport", "numero du passeport", "passport number"), ("expiration", "validite"), candidat.get("numero_passeport"), "Numéro de passeport"),
        (("date limite de validite", "expiration du passeport", "expiry date"), (), candidat.get("date_expiration_passeport"), "Date d'expiration du passeport"),
        (("niveau d'etudes", "dernier niveau", "activite principale"), (), candidat.get("niveau_actuel"), "Niveau d'études actuel"),
        (("intitule de la formation", "programme d'etudes", "formation selectionnee", "nom de la formation"), ("etablissement",), candidat.get("programme_vise"), "Formation / Programme visé"),
        (("etablissement d'accueil", "etablissement d'enseignement", "etablissement vise", "dli"), (), candidat.get("etablissement_vise"), "Établissement visé"),
        (("fonds disponibles", "ressources financieres", "available funds"), (), str(candidat["fonds_disponibles_eur"]) if candidat.get("fonds_disponibles_eur") is not None else None, "Ressources financières disponibles (EUR)"),
        (("adresse postale", "wilaya", "region / antenne"), (), candidat.get("adresse") or candidat.get("lieu_naissance") or antenne, "Adresse / Wilaya"),
        (("vos motivations", "texte de motivation"), (), _generer_motivation_personnalisee(candidat), "Texte de motivation personnalisé"),
    ]

    deja_remplis_norm = {_normaliser_sans_accents(c) for c in champs_remplis}

    for el in elements:
        if el["type_element"] not in ("champ", "liste", "zone_texte"):
            continue
        if el.get("valeur", "").strip():
            continue
        cible_norm = _normaliser_sans_accents(f"{el['libelle']} {el['selecteur']}")
        if any(m in cible_norm for m in ("mot de passe", "password", "clegc", "code secret", "captcha")):
            continue

        for mots_positifs, mots_exclus, valeur_cand, libelle_officiel in regles_association:
            if not valeur_cand or not str(valeur_cand).strip():
                continue
            if any(mp in cible_norm for mp in mots_positifs) and not any(me in cible_norm for me in mots_exclus):
                if _remplir_si_present(
                    page,
                    [el["selecteur"]],
                    str(valeur_cand),
                    type_champ="liste" if el["type_element"] == "liste" else "texte",
                    libelle_visuel=libelle_officiel,
                ):
                    if _normaliser_sans_accents(libelle_officiel) not in deja_remplis_norm:
                        champs_remplis.append(libelle_officiel)
                        deja_remplis_norm.add(_normaliser_sans_accents(libelle_officiel))
                    nb_ajoutes += 1
                break

    return nb_ajoutes


def _extraire_modifications_depuis_instruction(
    instruction: str,
    candidat: dict[str, Any],
) -> list[tuple[str, str, list[str], str]]:
    """Extrait les valeurs personnalisées dictées en langage naturel par l'opérateur, par exemple :
    - « mets Oran comme ville » / « je suis d'Oran »
    - « change l'établissement pour Université Lyon 1 »
    - « écris amine.b@gmail.com dans l'email »
    - « mets Master 2 Data Science comme formation »
    - « j'ai 18000 euros de fonds »
    Retourne une liste de tuples `(cle_candidat, nouvelle_valeur, selecteurs_connus, libelle_fr)`.
    """
    texte = instruction.strip()
    inst_norm = _normaliser_sans_accents(texte)
    extractions: list[tuple[str, str, list[str], str]] = []

    # 1. Adresse e-mail explicite dans la phrase
    m_email = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", texte)
    if m_email and any(w in inst_norm for w in ("email", "e-mail", "mail", "courriel", "mets", "ecris", "change", "identifiant")):
        val_email = m_email.group(1).strip(".,;\"'")
        extractions.append(
            (
                "email",
                val_email,
                ["#champ-email", "#inscr-email", "#login-identifiant-eef", "#eef-email-contact", "#ircc-email", "#ircc-reel-courriel", "input[type='email']"],
                f"Adresse e-mail ({val_email})",
            )
        )

    # 2. Numéro de téléphone explicite dans la phrase
    m_tel = re.search(r"(\+213\s*\d[\d\s]{7,11}|0[567]\d[\d\s]{7,9})", texte)
    if m_tel and any(w in inst_norm for w in ("tel", "telephone", "mobile", "numero", "mets", "ecris", "change")):
        val_tel = re.sub(r"\s+", "", m_tel.group(1))
        extractions.append(
            (
                "telephone",
                val_tel,
                ["#champ-telephone", "#eef-telephone-mobile", "#ircc-telephone", "#ircc-reel-telephone", "input[type='tel']"],
                f"Numéro de téléphone ({val_tel})",
            )
        )

    # 3. Numéro de passeport explicite
    m_pass = re.search(r"\b(passeport)\s*(?:est|c'est|a|au|:|=)?\s*([A-Z0-9]{6,12})\b", texte, flags=re.IGNORECASE)
    if m_pass:
        val_pass = m_pass.group(2).upper()
        extractions.append(
            (
                "numero_passeport",
                val_pass,
                ["#champ-numero-passeport", "#eef-numero-piece-identite", "#ircc-numero-passeport", "#ircc-reel-numero-passeport"],
                f"Numéro de passeport ({val_pass})",
            )
        )

    # 4. Montant financier / Fonds disponibles (EUR / CAD)
    m_fonds = re.search(r"\b(\d{4,6})\s*(?:euros?|eur|€|\$|cad|dinars?)?\b", inst_norm)
    if m_fonds and any(w in inst_norm for w in ("fonds", "ressources", "budget", "euros", "eur", "argent", "finan")):
        val_fonds = m_fonds.group(1)
        extractions.append(
            (
                "fonds_disponibles_eur",
                val_fonds,
                ["#ircc-fonds-disponibles-eur", "#ircc-reel-fonds-disponibles-eur", "input[name*='fonds']"],
                f"Ressources financières disponibles ({val_fonds} EUR)",
            )
        )

    # 5. Ville / Wilaya / Antenne d'Algérie
    villes_algerie = {
        "alger": "Alger",
        "oran": "Oran",
        "constantine": "Constantine",
        "annaba": "Annaba",
        "tlemcen": "Tlemcen",
        "setif": "Sétif",
        "bejaia": "Béjaïa",
        "tizi ouzou": "Tizi Ouzou",
        "blida": "Blida",
        "batna": "Batna",
        "mostaganem": "Mostaganem",
        "skikda": "Skikda",
        "biskra": "Biskra",
    }
    if any(w in inst_norm for w in ("ville", "wilaya", "lieu", "antenne", "region", "adresse", "habite", "suis d'", "suis de ", "mets ")):
        for v_norm, v_propre in villes_algerie.items():
            if re.search(rf"\b{re.escape(v_norm)}\b", inst_norm):
                ant = _determiner_antenne_algerie(v_propre)
                extractions.append(
                    (
                        "lieu_naissance",
                        v_propre,
                        ["#champ-lieu-naissance", "#champ-adresse-postale", "#inscr-region", "#eef-ville-naissance", "#ircc-lieu-naissance", "#ircc-reel-ville-naissance"],
                        f"Ville / Wilaya ({v_propre} — Antenne {ant})",
                    )
                )
                break

    # 6. Patrons génériques « mets [VALEUR] comme/dans [CHAMP] » ou « change [CHAMP] pour/par [VALEUR] »
    definitions_champs: list[tuple[str, tuple[str, ...], list[str], str]] = [
        ("etablissement_vise", ("etablissement", "universite", "ecole", "dli", "eed"), ["#champ-etablissement-vise", "#preconsulaire-etape3-etablissement", "#eef-etablissement-accueil", "#ircc-etablissement-dli", "#ircc-reel-etablissement-dli"], "Établissement visé"),
        ("programme_vise", ("formation", "programme", "specialite", "filiere", "cursus vise"), ["#champ-programme-vise", "#preconsulaire-etape3-formation", "#eef-intitule-formation-visee", "#ircc-programme-etudes", "#ircc-reel-programme-etudes"], "Formation / Programme visé"),
        ("niveau_actuel", ("niveau actuel", "niveau d'etudes", "dernier diplome"), ["#champ-niveau-actuel", "#activite-2-intitule", "#eef-dernier-niveau-etudes"], "Niveau d'études actuel"),
        ("nom", ("nom de famille", "nom"), ["#champ-nom-famille", "#inscr-nom", "#eef-nom-famille", "#ircc-nom-famille", "#ircc-reel-nom-famille"], "Nom de famille"),
        ("prenom", ("prenom",), ["#champ-prenom", "#inscr-prenom", "#eef-prenom-candidat", "#ircc-prenom", "#ircc-reel-prenom"], "Prénom"),
    ]

    for cle_c, synonymes, sels_c, lib_c in definitions_champs:
        for syn in synonymes:
            # Patron A : "change/modifie/mets/remplis (le/la/l'/mon/ma) <syn> (par/pour/avec/a/en/:) <valeur>"
            pat_a = re.compile(
                rf"(?:change|modifie|remplace|mets|met|ecris|tape|saisis|remplis|definis|fixe)?\s*(?:le|la|l'|mon|ma|votre)?\s*\b{re.escape(syn)}\b\s*(?:par|pour|avec|comme|a|en|est|c'est|:|=)\s*[\"«']?([^\"»'\n,;.]+)[\"»']?",
                flags=re.IGNORECASE,
            )
            m_a = pat_a.search(texte)
            if not m_a:
                # Sans accents : on cherche dans inst_norm puis on découpe la même tranche
                m_a_norm = pat_a.search(inst_norm)
                if m_a_norm:
                    val_extraite = m_a_norm.group(1).strip()
                else:
                    val_extraite = ""
            else:
                val_extraite = m_a.group(1).strip()

            # Patron B : "mets/ecris/saisis <valeur> (comme|dans|en tant que) (le|la|l'|mon|ma)? <syn>"
            if not val_extraite:
                pat_b = re.compile(
                    rf"(?:mets|met|ecris|tape|saisis|entre)\s+[\"«']?([^\"»'\n,;]+?)[\"»']?\s+(?:comme|dans|pour)\s+(?:le\s+|la\s+|l'|mon\s+|ma\s+|champ\s+)?\b{re.escape(syn)}\b",
                    flags=re.IGNORECASE,
                )
                m_b = pat_b.search(texte)
                if m_b:
                    val_extraite = m_b.group(1).strip()

            if val_extraite and len(val_extraite) >= 2:
                # Nettoyage des mots parasites de fin
                val_extraite = re.sub(r"\s+(?:et\s+enregistre.*|sans\s+soumettre.*|s'il\s+te\s+plait.*|stp.*)$", "", val_extraite, flags=re.IGNORECASE).strip()
                if val_extraite and not any(k == cle_c for k, _, _, _ in extractions):
                    candidat[cle_c] = val_extraite
                    extractions.append((cle_c, val_extraite, sels_c, f"{lib_c} ({val_extraite})"))
                    break

    return extractions


def _cliquer_element_par_intention_naturelle(
    page: Page,
    instruction: str,
    etapes_realisees: list[str],
) -> bool:
    """Si l'opérateur demande de cliquer ou d'ouvrir un élément précis de la page
    (ex: « clique sur S'inscrire », « appuie sur Enregistrer », « va sur l'onglet Scolarité »),
    recherche l'élément correspondant dans le DOM en direct, vérifie la Règle 1, l'anime et clique dessus."""
    inst_norm = _normaliser_sans_accents(instruction)
    m_clic = re.search(
        r"(?:clique|cliquer|appuie|appuyer|ouvre|ouvrir|selectionne|choisis|active)\s+(?:sur\s+)?(?:le\s+bouton\s+|l'onglet\s+|la\s+rubrique\s+|le\s+lien\s+|le\s+|la\s+|l')?[\"«']?([^\"»'\n.?!]{2,60})[\"»']?",
        inst_norm,
    )
    if not m_clic:
        return False

    cible_texte = m_clic.group(1).strip()
    for mot_fin in ("s'il te plait", "stp", "maintenant", "dans le navigateur", "sur la page"):
        if cible_texte.endswith(mot_fin):
            cible_texte = cible_texte[: -len(mot_fin)].strip()

    if not cible_texte or any(
        w in cible_texte
        for w in ("vrai site", "site officiel", "campus france", "ircc", "portail", "tout", "formulaire", "dossier")
    ):
        return False

    if _est_element_soumission_interdit_regle1(cible_texte, cible_texte, ""):
        return False

    # Recherche dans les éléments interactifs détectés sur la page
    elements = inspecter_elements_interactifs_page(page)
    for el in elements:
        if el["interdit_regle1"] == "oui":
            continue
        if el["type_element"] not in ("bouton", "lien"):
            continue
        lib_norm = _normaliser_sans_accents(el["libelle"])
        if cible_texte in lib_norm or lib_norm in cible_texte:
            if _cliquer_si_present(page, [el["selecteur"]], libelle_visuel=el["libelle"]):
                etapes_realisees.append(f"Clic direct dans le navigateur sur « {el['libelle']} »")
                return True

    # Recherche générique par texte Playwright
    for tag in ("button", "a", "[role='button']", "span[onclick]", "summary"):
        sel_cand = f"{tag}:has-text(\"{cible_texte}\")"
        if _cliquer_si_present(page, [sel_cand], libelle_visuel=cible_texte):
            etapes_realisees.append(f"Clic direct dans le navigateur sur « {cible_texte} »")
            return True

    return False


def _executer_commandes_navigation_et_defilement(
    page: Page,
    instruction: str,
    etapes_realisees: list[str],
) -> bool:
    """Exécute les commandes directes de défilement (scroll), retour arrière, page suivante ou actualisation."""
    inst_norm = _normaliser_sans_accents(instruction)
    action_faite = False

    if any(m in inst_norm for m in ("descends", "descendre", "scrolle en bas", "scroll en bas", "plus bas", "bas de la page", "bas de page")):
        try:
            if "bas de la page" in inst_norm or "tout en bas" in inst_norm:
                page.evaluate("window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })")
                etapes_realisees.append("Défilement fluide jusqu'en bas de la page")
            else:
                page.evaluate("window.scrollBy({ top: 550, behavior: 'smooth' })")
                etapes_realisees.append("Défilement de la page vers le bas")
            action_faite = True
        except Exception:
            pass

    elif any(m in inst_norm for m in ("monte", "monter", "scrolle en haut", "scroll en haut", "plus haut", "haut de la page", "haut de page")):
        try:
            if "haut de la page" in inst_norm or "tout en haut" in inst_norm:
                page.evaluate("window.scrollTo({ top: 0, behavior: 'smooth' })")
                etapes_realisees.append("Défilement fluide jusqu'en haut de la page")
            else:
                page.evaluate("window.scrollBy({ top: -550, behavior: 'smooth' })")
                etapes_realisees.append("Défilement de la page vers le haut")
            action_faite = True
        except Exception:
            pass

    if any(m in inst_norm for m in ("retourne en arriere", "page precedente", "reviens en arriere")):
        try:
            page.go_back(wait_until="domcontentloaded", timeout=8000)
            etapes_realisees.append(f"Retour à la page précédente ({page.url})")
            action_faite = True
        except Exception:
            pass

    elif "page suivante" in inst_norm:
        try:
            page.go_forward(wait_until="domcontentloaded", timeout=8000)
            etapes_realisees.append(f"Passage à la page suivante ({page.url})")
            action_faite = True
        except Exception:
            pass

    elif any(m in inst_norm for m in ("actualise la page", "rafraichis la page", "recharge la page")):
        try:
            page.reload(wait_until="domcontentloaded", timeout=10000)
            etapes_realisees.append(f"Page actualisée ({page.url})")
            action_faite = True
        except Exception:
            pass

    return action_faite


def _construire_analyse_contextuelle_et_reponse(
    page: Page,
    *,
    code_demarche: str,
    instruction_libre: str | None,
    candidat: dict[str, Any],
    etapes_realisees: list[str],
    champs_remplis: list[str],
    pieces_televersees: list[str],
    champs_manquants: list[str],
    elements_page: list[dict[str, str]],
) -> str:
    """Génère une réponse conversationnelle intelligente (style Perplexity Assistant / Claude Cowork)
    combinant l'état réel de la page ouverte dans le navigateur, les actions exécutées et la connaissance
    experte du Guide Études en France Septembre 2026 / IRCC Canada."""
    inst_norm = _normaliser_sans_accents(instruction_libre or "")
    titre = page.title() or "Portail actif"
    url = page.url or ""

    champs_dom = [e for e in elements_page if e["type_element"] in ("champ", "liste", "zone_texte")]
    champs_dom_remplis = [e for e in champs_dom if e.get("valeur", "").strip()]
    champs_dom_vides = [e for e in champs_dom if not e.get("valeur", "").strip()]
    boutons_dom = [e for e in elements_page if e["type_element"] in ("bouton", "lien") and e["interdit_regle1"] == "non"]

    lignes: list[str] = []

    # 1. Si l'utilisateur a posé une question sur le Guide Campus France Septembre 2026 ou IRCC
    if instruction_libre:
        reponses_guide = repondre_question_guide_campus_france(instruction_libre)
        if reponses_guide:
            lignes.extend(reponses_guide)

        if any(m in inst_norm for m in ("ircc", "canada", "20 635", "20635", "pal", "lap", "caq", "dli", "eed", "imm 5645", "imm5645")):
            fonds_cand = candidat.get("fonds_disponibles_eur")
            statut_fonds = (
                f"Votre candidat dispose de {fonds_cand} EUR (conforme au seuil de 14 500 EUR / 20 635 CAD)."
                if isinstance(fonds_cand, (int, float)) and fonds_cand >= 14500
                else f"Attention : les fonds du candidat ({fonds_cand or 'non renseignés'} EUR) sont sous le seuil recommandé de 14 500 EUR (20 635 $ CAD hors frais de scolarité)."
            )
            lignes.append(
                "Règles IRCC Canada (Permis d'études) :\n"
                f"  • Seuil financier exigé : 20 635 $ CAD (≈ 14 500 EUR) en plus des frais de scolarité de la 1re année. {statut_fonds}\n"
                "  • Pièces obligatoires : Passeport, Lettre d'admission EED/DLI, Lettre d'Attestation Provinciale (LAP/PAL) ou CAQ Québec, Preuve de fonds, Photo et Formulaire famille IMM 5645."
            )

    # 2. Si l'utilisateur demande d'analyser / expliquer la page ouverte (« qu'est-ce qu'il y a sur cette page ? », « que dois-je faire ? »)
    demande_analyse_page = any(
        m in inst_norm
        for m in (
            "sur cette page",
            "analyse",
            "explique",
            "que vois-tu",
            "qu'est-ce qu",
            "ou suis-je",
            "que dois-je faire",
            "prochaine etape",
            "aide-moi",
            "resume la page",
            "quels sont les champs",
        )
    )
    if demande_analyse_page or (not etapes_realisees and not champs_remplis and not lignes):
        exemples_vides = ", ".join(e["libelle"] for e in champs_dom_vides[:5])
        exemples_boutons = ", ".join(e["libelle"] for e in boutons_dom[:5])
        lignes.append(
            f"Analyse en direct de votre onglet actif (« {titre} » — {url}) :\n"
            f"  • Champs de formulaire détectés sur la page : {len(champs_dom)} au total ({len(champs_dom_remplis)} déjà remplis, {len(champs_dom_vides)} vides).\n"
            + (f"  • Principaux champs restant à remplir ici : {exemples_vides}.\n" if exemples_vides else "")
            + (f"  • Actions et rubriques cliquables sur cette page : {exemples_boutons}.\n" if exemples_boutons else "")
            + f"  • Dossier actif : {candidat.get('prenom') or ''} {candidat.get('nom') or ''} — Formation visée : {candidat.get('programme_vise') or 'Non précisée'} ({candidat.get('etablissement_vise') or 'Établissement non précisé'}).\n"
            "  • Dites-moi par exemple : « remplis cette page », « mets [valeur] dans [champ] » ou « clique sur [bouton] »."
        )

    # 3. Compte rendu naturel des actions qui viennent d'être exécutées en direct
    if champs_remplis or pieces_televersees or etapes_realisees:
        details_actions: list[str] = []
        if etapes_realisees:
            details_actions.append(" ; ".join(etapes_realisees))
        if champs_remplis:
            apercu_ch = ", ".join(champs_remplis[:8])
            suite = f" (+{len(champs_remplis) - 8} autres)" if len(champs_remplis) > 8 else ""
            details_actions.append(f"{len(champs_remplis)} champ(s) saisi(s) en direct ({apercu_ch}{suite})")
        if pieces_televersees:
            details_actions.append(f"{len(pieces_televersees)} pièce(s) jointe(s) ({', '.join(pieces_televersees)})")
        lignes.append("Exécution en direct dans votre navigateur : " + " — ".join(details_actions) + ".")

    if champs_manquants:
        lignes.append(
            f"Données non renseignées dans la fiche candidat (Règle 4 : aucune valeur inventée) : {', '.join(champs_manquants)}."
        )

    return "\n\n".join(lignes).strip()


class GestionnairePiloteNavigateur:
    """Gère un thread dédié unique pour Playwright afin d'éviter toute erreur de changement
    de thread (`Cannot switch to a different thread`) entre deux requêtes HTTP FastAPI,
    et maintient le pont temps réel avec la barre latérale Co-Pilote injectée dans le navigateur."""

    def __init__(
        self,
        *,
        mode_serveur: bool = False,
        politique_navigation: PolitiqueNavigation | None = None,
        url_serveur: str = "",
    ) -> None:
        """`mode_serveur` : headless forcé, jamais de rattachement CDP 9222 ni de canal chrome/msedge,
        toute navigation principale hors domaines officiels est bloquée. `politique_navigation` : Règle 6
        (domaines HTTPS officiels des YAML) ; None = pas de contrôle (usage local historique / tests
        directs). `url_serveur` : URL injectée dans le panneau du Co-Pilote (vide = pont désactivé)."""
        self._mode_serveur = mode_serveur
        self._politique_navigation = politique_navigation
        self._url_serveur = (url_serveur or "").rstrip("/")
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="pilote_playwright"
        )
        self._playwright: Playwright | None = None
        self._navigateur_cdp: Browser | None = None
        self._contexte: BrowserContext | None = None
        self._page: Page | None = None
        self._mode_headless_actif: bool | None = None
        self._jeton_bridge_local: str = secrets.token_urlsafe(24)
        self._dernier_candidat: dict[str, Any] = {}
        self._derniere_demarche: str = "campus_france"
        self._derniere_cible: str = "campus_france_officiel"
        self._dernier_dossier_profil: Path | None = None
        self._historique_actions: list[dict[str, str]] = []

    @property
    def jeton_bridge_local(self) -> str:
        return self._jeton_bridge_local

    def _configurer_contexte_et_page(self, page: Page) -> None:
        script_config = f"""
        window.__COWORK_URL_SERVEUR__ = {json.dumps(self._url_serveur)};
        window.__COWORK_JETON_BRIDGE__ = {json.dumps(self._jeton_bridge_local)};
        """
        try:
            if self._contexte is not None:
                self._contexte.add_init_script(script_config + "\n" + SCRIPT_COPILOTE_COWORK_INJECTE)
        except Exception:
            pass

        if self._mode_serveur and self._politique_navigation is not None and self._contexte is not None:
            # Défense en profondeur (Règle 6) : toute navigation du cadre principal (clic sur un lien,
            # redirection, window.open) vers un domaine non officiel est bloquée côté navigateur.
            politique = self._politique_navigation

            def _garde_navigation(route: Route) -> None:
                try:
                    req = route.request
                    if (
                        req.is_navigation_request()
                        and req.frame.parent_frame is None
                        and politique.motif_refus(req.url) is not None
                    ):
                        route.abort("blockedbyclient")
                        return
                    route.fallback()
                except Exception:
                    try:
                        route.abort("failed")
                    except Exception:
                        pass

            try:
                self._contexte.route("**/*", _garde_navigation)
            except Exception:
                pass

        def _servir_demo_local(route: Route) -> None:
            from urllib.parse import parse_qs, urlparse
            from app.demo.routeur_demo import page_demo_campus_france, page_demo_ircc

            u = urlparse(route.request.url)
            if u.path.startswith("/demo/eef-reel"):
                from app.demo.maquette_eef_reel import html_maquette_eef_reel

                route.fulfill(
                    status=200,
                    headers={"Content-Type": "text/html; charset=utf-8"},
                    body=html_maquette_eef_reel().encode("utf-8"),
                )
                return
            qs = parse_qs(u.query)
            sess = int(qs.get("session_ouverte", ["1"])[0])
            cap = int(qs.get("captcha", ["0"])[0])
            if "ircc" in u.path:
                rep_html = page_demo_ircc(session_ouverte=sess, captcha=cap)
            else:
                rep_html = page_demo_campus_france(session_ouverte=sess, captcha=cap)
            route.fulfill(
                status=200,
                headers={"Content-Type": "text/html; charset=utf-8"},
                body=bytes(rep_html.body),
            )

        try:
            page.route("http://portail.local/demo/**", _servir_demo_local)
        except Exception:
            pass

    def _injecter_overlay_page_courante(self, page: Page) -> None:
        try:
            page.evaluate(
                f"window.__COWORK_URL_SERVEUR__ = {json.dumps(self._url_serveur)}; "
                f"window.__COWORK_JETON_BRIDGE__ = {json.dumps(self._jeton_bridge_local)};"
            )
            page.evaluate(SCRIPT_COPILOTE_COWORK_INJECTE)
        except Exception:
            pass

    def _assurer_page(self, *, headless: bool, dossier_profil: Path) -> Page:
        if self._mode_serveur:
            # Mode serveur : headless forcé. Du coup, jamais de rattachement CDP 9222 (réservé au mode
            # visible) ni de canal chrome/msedge local (Chromium de Playwright uniquement).
            headless = True
        self._dernier_dossier_profil = dossier_profil
        if (
            self._page is not None
            and not self._page.is_closed()
            and self._mode_headless_actif == headless
        ):
            if not headless:
                try:
                    self._page.bring_to_front()
                except Exception:
                    pass
            self._injecter_overlay_page_courante(self._page)
            return self._page

        if self._contexte is not None:
            try:
                self._contexte.close()
            except Exception:
                pass
            self._contexte = None
            self._page = None

        if self._playwright is None:
            self._playwright = sync_playwright().start()

        dossier_profil.mkdir(parents=True, exist_ok=True)
        args_navigateur: list[str] = []
        if not self._mode_serveur:
            # Réglages de confort du poste local ; jamais en mode serveur (pas de contenu mixte toléré).
            args_navigateur = [
                "--allow-running-insecure-content",
                "--disable-features=BlockInsecurePrivateNetworkRequests,PrivateNetworkAccessRespectPreflightResults",
            ]
        if not headless:
            args_navigateur.append("--start-maximized")

        # 1. En mode visible, tenter d'abord de se greffer au vrai navigateur Chrome/Edge ouvert en CDP (port 9222)
        if not headless and not self._mode_serveur:
            try:
                self._navigateur_cdp = self._playwright.chromium.connect_over_cdp(
                    "http://127.0.0.1:9222", timeout=900
                )
                if self._navigateur_cdp.contexts:
                    self._contexte = self._navigateur_cdp.contexts[0]
                else:
                    self._contexte = self._navigateur_cdp.new_context(bypass_csp=True)
                self._mode_headless_actif = False
            except Exception:
                self._navigateur_cdp = None
                self._contexte = None

        # 2. Sinon, ouvrir le vrai Chrome ou Edge installé sur Windows (ou Chromium Playwright) en mode persistant
        if self._contexte is None:
            canaux_a_tester: list[str | None] = (
                ["chrome", "msedge", None]
                if not headless and not self._mode_serveur
                else [None]
            )
            for canal in canaux_a_tester:
                try:
                    kwargs_lancement: dict[str, Any] = {
                        "user_data_dir": str(dossier_profil),
                        "headless": headless,
                        "bypass_csp": True,
                        "args": args_navigateur,
                    }
                    if canal is not None:
                        kwargs_lancement["channel"] = canal
                    if self._mode_serveur:
                        kwargs_lancement["accept_downloads"] = False
                    if headless:
                        kwargs_lancement["viewport"] = {"width": 1280, "height": 900}
                    else:
                        kwargs_lancement["no_viewport"] = True

                    self._contexte = self._playwright.chromium.launch_persistent_context(
                        **kwargs_lancement
                    )
                    self._mode_headless_actif = headless
                    break
                except Exception:
                    continue

        # 3. Repli headless de sécurité si aucun affichage graphique n'est disponible
        if self._contexte is None:
            self._contexte = self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(dossier_profil),
                headless=True,
                bypass_csp=True,
                viewport={"width": 1280, "height": 900},
            )
            self._mode_headless_actif = True

        self._page = (
            self._contexte.pages[0]
            if self._contexte.pages
            else self._contexte.new_page()
        )
        self._configurer_contexte_et_page(self._page)
        if not self._mode_headless_actif:
            try:
                self._page.bring_to_front()
            except Exception:
                pass
        return self._page

    def _fermer_dans_thread(self) -> None:
        self._page = None
        if self._contexte is not None:
            try:
                self._contexte.close()
            except Exception:
                pass
            self._contexte = None
        if self._navigateur_cdp is not None:
            try:
                self._navigateur_cdp.close()
            except Exception:
                pass
            self._navigateur_cdp = None
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        self._mode_headless_actif = None

    def fermer(self) -> None:
        try:
            self._executor.submit(self._fermer_dans_thread).result(timeout=10)
        except Exception:
            pass

    def arreter(self) -> None:
        """Ferme le navigateur ET le thread dédié (instance non réutilisable ensuite)."""
        self.fermer()
        self._executor.shutdown(wait=False)

    def _refus_navigation(self, url: str) -> str | None:
        """Règle 6 : motif de refus si la politique de navigation interdit cette URL, sinon None."""
        if self._politique_navigation is None:
            return None
        return self._politique_navigation.motif_refus(url)

    # ---- Vue opérateur (capture, état, contrôle humain) : jamais utilisées par l'agent ----

    def capturer_jpeg(self, qualite: int = 70) -> bytes | None:
        """Capture JPEG de la page courante (viewport), ou None si aucune page n'est ouverte."""

        def _capture() -> bytes | None:
            page = self._page
            if page is None or page.is_closed():
                return None
            try:
                return page.screenshot(full_page=False, type="jpeg", quality=qualite)
            except Exception:
                return None

        return self._executor.submit(_capture).result(timeout=15)

    def etat_operateur(self) -> dict[str, Any]:
        """État minimal pour la vue opérateur : URL sans paramètres, titre, contrôle de sécurité détecté."""

        def _etat() -> dict[str, Any]:
            page = self._page
            if page is None or page.is_closed():
                return {"navigateur_ouvert": False, "url_courante": "", "titre_page": "", "controle_securite_detecte": False}
            analyse = urlparse(page.url or "")
            url_sans_parametres = (
                f"{analyse.scheme}://{analyse.netloc}{analyse.path}" if analyse.scheme else (page.url or "")
            )
            try:
                titre = page.title() or ""
            except Exception:
                titre = ""
            return {
                "navigateur_ouvert": True,
                "url_courante": url_sans_parametres,
                "titre_page": titre[:200],
                "controle_securite_detecte": _detecter_captcha_ou_2fa_sur_page(page),
            }

        return self._executor.submit(_etat).result(timeout=15)

    def executer_controle_humain(
        self,
        *,
        type_action: str,
        x: int | None = None,
        y: int | None = None,
        texte: str | None = None,
        touche: str | None = None,
        delta_y: int | None = None,
    ) -> bool:
        """Action d'un HUMAIN (résolution d'un CAPTCHA / 2FA, Règle 2) : souris et clavier réels de la page.
        Les paramètres sont déjà validés par la couche API. Retourne False si aucune page n'est ouverte."""

        def _agir() -> bool:
            page = self._page
            if page is None or page.is_closed():
                return False
            if type_action == "clic":
                page.mouse.click(x, y)
            elif type_action == "texte":
                page.keyboard.type(texte or "")
            elif type_action == "touche":
                page.keyboard.press(touche or "")
            elif type_action == "defilement":
                if x is not None and y is not None:
                    page.mouse.move(x, y)
                page.mouse.wheel(0, delta_y or 0)
            else:
                return False
            return True

        return self._executor.submit(_agir).result(timeout=15)

    def obtenir_etat_temps_reel(self) -> dict[str, Any]:
        """Retourne en moins de 25 ms l'état en direct du navigateur (sans capture d'écran)
        et exécute toute consigne éventuellement saisie dans la barre latérale du navigateur."""
        fut = self._executor.submit(self._obtenir_etat_dans_thread)
        return fut.result(timeout=10)

    def _obtenir_etat_dans_thread(self) -> dict[str, Any]:
        if self._page is None or self._page.is_closed():
            return {
                "navigateur_ouvert": False,
                "mode_fenetre_visible": False,
                "url_courante": "",
                "titre_page": "Navigateur en attente d'ouverture",
                "code_demarche": self._derniere_demarche,
                "cible": self._derniere_cible,
                "elements_interactifs_page": [],
                "historique_actions": self._historique_actions[-10:],
            }

        # Si l'opérateur a tapé une consigne directement dans le dock Co-Pilote du navigateur
        try:
            commandes_en_attente = self._page.evaluate(
                "() => { const q = window.__COWORK_FILE_COMMANDES__ || []; window.__COWORK_FILE_COMMANDES__ = []; return q; }"
            )
            if commandes_en_attente and isinstance(commandes_en_attente, list):
                for cmd in commandes_en_attente:
                    if isinstance(cmd, str) and cmd.strip() and self._dernier_dossier_profil:
                        self._executer_dans_thread_playwright(
                            code_demarche=self._derniere_demarche,
                            cible=self._derniere_cible,
                            action="instruction_libre",
                            instruction_libre=cmd.strip(),
                            candidat=dict(self._dernier_candidat),
                            documents_dechiffres=[],
                            dossier_profil=self._dernier_dossier_profil,
                            headless=bool(self._mode_headless_actif),
                            prendre_capture=False,
                        )
        except Exception:
            pass

        elements = inspecter_elements_interactifs_page(self._page)
        try:
            titre = self._page.title() or "Portail officiel"
        except Exception:
            titre = "Portail officiel"

        return {
            "navigateur_ouvert": True,
            "mode_fenetre_visible": not bool(self._mode_headless_actif),
            "url_courante": self._page.url,
            "titre_page": titre,
            "code_demarche": self._derniere_demarche,
            "cible": self._derniere_cible,
            "elements_interactifs_page": elements,
            "historique_actions": self._historique_actions[-10:],
        }

    def executer_action_dom_directe(
        self,
        *,
        type_operation: str,
        selecteur: str | None = None,
        valeur: str | None = None,
        url_destination: str | None = None,
        dossier_profil: Path,
        headless: bool = False,
    ) -> dict[str, Any]:
        """Exécute instantanément (< 50 ms) un clic, une saisie, un défilement ou une navigation
        directe dans le DOM du navigateur actif, sans capture d'écran."""
        fut = self._executor.submit(
            self._executer_action_dom_dans_thread,
            type_operation=type_operation,
            selecteur=selecteur,
            valeur=valeur,
            url_destination=url_destination,
            dossier_profil=dossier_profil,
            headless=headless,
        )
        return fut.result(timeout=20)

    def _executer_action_dom_dans_thread(
        self,
        *,
        type_operation: str,
        selecteur: str | None,
        valeur: str | None,
        url_destination: str | None,
        dossier_profil: Path,
        headless: bool,
    ) -> dict[str, Any]:
        page = self._assurer_page(headless=headless, dossier_profil=dossier_profil)
        op = type_operation.lower().strip()
        message = "Action directe exécutée."
        succes = True

        if op == "naviguer" and url_destination:
            url_nav = url_destination.strip()
            if not url_nav.startswith(("http://", "https://")):
                url_nav = URLS_CIBLES_OFFICIELS.get(url_nav, "https://" + url_nav)
            refus_r6 = self._refus_navigation(url_nav)
            if refus_r6:
                succes = False
                message = refus_r6
            else:
                try:
                    page.goto(url_nav, wait_until="domcontentloaded", timeout=15000)
                    self._injecter_overlay_page_courante(page)
                    message = f"Navigation directe vers {page.url}"
                except Exception as exc:
                    succes = False
                    message = f"Délai dépassé lors de l'ouverture de {url_nav} ({type(exc).__name__})."

        elif op == "cliquer" and selecteur:
            if _est_element_soumission_interdit_regle1(selecteur, valeur or "", ""):
                succes = False
                message = "Arrêt Règle 1 : ce bouton correspond à une soumission finale réservée à l'humain."
            elif _cliquer_si_present(page, [selecteur], libelle_visuel=valeur or selecteur):
                message = f"Clic direct effectué sur « {valeur or selecteur} »."
            else:
                succes = False
                message = f"Élément « {selecteur} » non visible sur la page actuelle."

        elif op == "remplir" and selecteur and valeur is not None:
            if (
                _remplir_si_present(page, [selecteur], valeur, type_champ="texte", libelle_visuel=selecteur)
                or _remplir_si_present(page, [selecteur], valeur, type_champ="liste", libelle_visuel=selecteur)
            ):
                message = f"Champ « {selecteur} » rempli en direct avec « {valeur} »."
            else:
                succes = False
                message = f"Impossible de remplir « {selecteur} »."

        elif op == "focus_fenetre":
            try:
                page.bring_to_front()
                message = "Fenêtre du navigateur mise au premier plan sur votre écran."
            except Exception:
                message = "Navigateur actif."

        elif op in ("scroll_bas", "scroll_haut", "retour", "suivant", "actualiser"):
            etapes_tmp: list[str] = []
            correspondance = {
                "scroll_bas": "descends",
                "scroll_haut": "monte",
                "retour": "retourne en arriere",
                "suivant": "page suivante",
                "actualiser": "actualise la page",
            }
            _executer_commandes_navigation_et_defilement(page, correspondance[op], etapes_tmp)
            message = etapes_tmp[0] if etapes_tmp else "Action navigateur exécutée."

        self._injecter_overlay_page_courante(page)
        elements = inspecter_elements_interactifs_page(page)
        self._historique_actions.append({"action": op, "message": message})
        return {
            "succes": succes,
            "message": message,
            "url_courante": page.url,
            "titre_page": page.title() or "Portail actif",
            "elements_interactifs_page": elements,
        }

    def executer_action(
        self,
        *,
        code_demarche: str,
        cible: str,
        action: str,
        instruction_libre: str | None,
        candidat: dict[str, Any],
        documents_dechiffres: list[tuple[str, str, str, bytes]],
        dossier_profil: Path,
        headless: bool = False,
        prendre_capture: bool = True,
        voeux: list[dict[str, Any]] | None = None,
        portail_homologue: bool = False,
        profil_panier: ProfilSelecteursPanier | None = None,
    ) -> ResultatActionNavigateur:
        """`voeux` : liste [{voeu_id, intitule, etablissement, niveau, motivation}] pour l'action
        « ajouter_voeux_panier ». `portail_homologue` : True uniquement si l'administrateur a validé
        le vrai portail (Règle 6) ; sinon l'ajout de vœux est refusé hors page de démonstration.
        `profil_panier` : profil de sélecteurs explicite, pris en compte UNIQUEMENT sur une page de
        démonstration (ex. le profil réel appliqué à la maquette `/demo/eef-reel/...`) ; sur le vrai
        portail le profil réel est toujours imposé."""
        fut = self._executor.submit(
            self._executer_dans_thread_playwright,
            code_demarche=code_demarche,
            cible=cible,
            action=action,
            instruction_libre=instruction_libre,
            candidat=candidat,
            documents_dechiffres=documents_dechiffres,
            dossier_profil=dossier_profil,
            headless=headless,
            prendre_capture=prendre_capture,
            voeux=voeux,
            portail_homologue=portail_homologue,
            profil_panier=profil_panier,
        )
        return fut.result(timeout=120 if action == ACTION_AJOUTER_VOEUX_PANIER else 45)

    def _executer_dans_thread_playwright(
        self,
        *,
        code_demarche: str,
        cible: str,
        action: str,
        instruction_libre: str | None,
        candidat: dict[str, Any],
        documents_dechiffres: list[tuple[str, str, str, bytes]],
        dossier_profil: Path,
        headless: bool,
        prendre_capture: bool = True,
        voeux: list[dict[str, Any]] | None = None,
        portail_homologue: bool = False,
        profil_panier: ProfilSelecteursPanier | None = None,
    ) -> ResultatActionNavigateur:
        etapes_realisees: list[str] = []
        champs_remplis: list[str] = []
        pieces_televersees: list[str] = []
        champs_manquants: list[str] = []
        avertissements: list[str] = []
        modifications_candidat: dict[str, Any] = {}

        # Mémorise le contexte courant pour la barre latérale Co-Pilote du navigateur
        candidat_travail = dict(candidat)
        self._dernier_candidat = candidat_travail
        self._derniere_demarche = code_demarche
        self._derniere_cible = cible

        # 1. Garde-fou Règle 1 immédiat sur l'instruction libre éventuelle
        if instruction_libre:
            alerte_regle1 = _verifier_instruction_non_interdite_regle1(instruction_libre)
            if alerte_regle1:
                avertissements.append(alerte_regle1)
                octets_png: bytes | None = None
                url_actuelle = URLS_CIBLES_OFFICIELS.get(cible, "")
                titre_actuel = "Garde-fou Règle 1 — Soumission finale bloquée"
                if self._page is not None and not self._page.is_closed():
                    try:
                        if prendre_capture:
                            octets_png = self._page.screenshot(full_page=False, type="png")
                        url_actuelle = self._page.url
                        titre_actuel = self._page.title() or titre_actuel
                    except Exception:
                        octets_png = None
                return ResultatActionNavigateur(
                    succes=False,
                    code_demarche=code_demarche,
                    cible=cible,
                    action_executee=action,
                    url_courante=url_actuelle,
                    titre_page=titre_actuel,
                    resume_francais=alerte_regle1,
                    reponse_agent=alerte_regle1,
                    etapes_realisees=etapes_realisees,
                    avertissements_securite=avertissements,
                    arret_regle1_avant_soumission=True,
                    capture_base64=(
                        base64.b64encode(octets_png).decode("ascii")
                        if octets_png
                        else None
                    ),
                    capture_png_octets=octets_png,
                )

        # 1bis. Ajout de vœux : réservé à campus_france et refusé sur le vrai portail non homologué (Règle 6)
        if action == ACTION_AJOUTER_VOEUX_PANIER:
            msg_refus: str | None = None
            if code_demarche != "campus_france":
                msg_refus = "L'action « ajouter_voeux_panier » concerne uniquement la démarche Campus France."
            elif not cible.startswith("demo_") and not portail_homologue:
                msg_refus = _MESSAGE_REFUS_PORTAIL_NON_HOMOLOGUE
            if msg_refus:
                return self._resultat_refus_action(
                    code_demarche=code_demarche,
                    cible=cible,
                    action=action,
                    message=msg_refus,
                    avertissements=avertissements,
                )

        page = self._assurer_page(headless=headless, dossier_profil=dossier_profil)

        # 2. Détermination intelligente de l'URL cible et de la navigation
        url_cible = URLS_CIBLES_OFFICIELS.get(cible)
        if not url_cible:
            url_cible = (
                URLS_CIBLES_OFFICIELS["demo_campus_france"]
                if code_demarche == "campus_france"
                else URLS_CIBLES_OFFICIELS["demo_ircc"]
            )

        inst_min = _normaliser_sans_accents(instruction_libre or "")
        navigation_explicite_demandee = False

        # Extraction d'une URL explicite dans l'instruction (ex: "va sur https://...")
        m_url_directe = re.search(r"(https?://[^\s\"'<>]+)", instruction_libre or "")
        if m_url_directe:
            url_cible = m_url_directe.group(1)
            navigation_explicite_demandee = True
        elif any(m in inst_min for m in ("vrai site", "site officiel", "etudesenfrance.diplomatie", "ouvre campus france", "aller sur campus france", "va sur campus france")):
            url_cible = (
                URLS_CIBLES_OFFICIELS["campus_france_officiel"]
                if code_demarche == "campus_france" and "ircc" not in inst_min
                else URLS_CIBLES_OFFICIELS["ircc_officiel"]
            )
            navigation_explicite_demandee = True
        elif any(m in inst_min for m in ("portal-portail.apps.cic", "portail officiel ircc", "ouvre ircc", "va sur ircc", "site de ircc", "site ircc")):
            url_cible = URLS_CIBLES_OFFICIELS["ircc_officiel"]
            code_demarche = "ircc_permis_etudes"
            navigation_explicite_demandee = True
        elif "paiement.if-algerie" in inst_min or ("site" in inst_min and "paiement" in inst_min):
            url_cible = URLS_CIBLES_OFFICIELS["paiement_ifa_algerie"]
            navigation_explicite_demandee = True
        elif "algerie.campusfrance" in inst_min or "horaires" in inst_min:
            url_cible = URLS_CIBLES_OFFICIELS["campus_france_algerie"]
            navigation_explicite_demandee = True
        elif any(m in inst_min for m in ("simulation", "page de demo", "mode demo")):
            url_cible = (
                URLS_CIBLES_OFFICIELS["demo_campus_france"]
                if code_demarche == "campus_france"
                else URLS_CIBLES_OFFICIELS["demo_ircc"]
            )
            navigation_explicite_demandee = True

        url_page_actuelle = (page.url or "").rstrip("/")
        url_cible_norm = url_cible.rstrip("/")

        # Vérifie si le navigateur est déjà sur une page de la même famille (pour ne JAMAIS recharger
        # la page d'accueil au milieu d'une interaction de l'opérateur !)
        famille_domaines = (
            DOMAINES_FAMILLE_CAMPUS_FRANCE
            if code_demarche == "campus_france"
            else DOMAINES_FAMILLE_IRCC
        )
        est_sur_demo = "/demo/" in url_page_actuelle
        cible_est_demo = "/demo/" in url_cible_norm
        meme_famille_active = (
            url_page_actuelle not in ("", "about:blank")
            and (est_sur_demo == cible_est_demo)
            and (
                url_page_actuelle == url_cible_norm
                or url_page_actuelle.startswith(url_cible_norm)
                or any(dom in url_page_actuelle.lower() for dom in famille_domaines)
            )
        )

        doit_naviguer = (
            action == "ouvrir_portail"
            or navigation_explicite_demandee
            or url_page_actuelle in {"about:blank", ""}
            or not meme_famille_active
        )
        if action == ACTION_CARTOGRAPHIER_PAGE:
            # Calibration : on cartographie la page COURANTE (celle où l'humain est connecté),
            # sans jamais naviguer sauf si aucune page n'est ouverte.
            doit_naviguer = url_page_actuelle in {"about:blank", ""}

        if doit_naviguer:
            refus_r6 = self._refus_navigation(url_cible)
            if refus_r6:
                return self._resultat_refus_action(
                    code_demarche=code_demarche,
                    cible=cible,
                    action=action,
                    message=refus_r6,
                    avertissements=avertissements,
                    page=page,
                    prendre_capture=prendre_capture,
                )
            try:
                page.goto(url_cible, wait_until="domcontentloaded", timeout=15000)
                etapes_realisees.append(f"Ouverture directe dans le navigateur : {page.url}")
            except Exception as exc:
                avertissements.append(
                    f"Le site distant ({url_cible}) n'a pas répondu dans le délai imparti ({type(exc).__name__}). "
                    "Basculez sur la page locale Études en France / IRCC ou vérifiez votre connexion."
                )

        self._injecter_overlay_page_courante(page)

        # 3. Contrôle Règle 2 : Détection CAPTCHA / 2FA
        if _detecter_captcha_ou_2fa_sur_page(page):
            msg_cap = (
                "Contrôle de sécurité (CAPTCHA ou double authentification 2FA) détecté sur la page (Règle 2). "
                "L'agent s'est mis en pause : veuillez résoudre le contrôle directement dans la fenêtre du navigateur."
            )
            avertissements.append(msg_cap)
            octets_png = page.screenshot(full_page=False, type="png") if prendre_capture else None
            return ResultatActionNavigateur(
                succes=False,
                code_demarche=code_demarche,
                cible=cible,
                action_executee=action,
                url_courante=page.url,
                titre_page=page.title() or "Portail",
                resume_francais=msg_cap,
                reponse_agent=msg_cap,
                etapes_realisees=etapes_realisees,
                avertissements_securite=avertissements,
                blocage_captcha_ou_2fa=True,
                capture_base64=base64.b64encode(octets_png).decode("ascii") if octets_png else None,
                capture_png_octets=octets_png,
            )

        # 3bis. Actions dédiées : cartographie de calibration (lecture seule) et ajout de vœux au panier.
        #       Elles court-circuitent la NLU générique : aucun clic ni saisie hors de leur périmètre.
        if action == ACTION_CARTOGRAPHIER_PAGE:
            return self._executer_cartographie_page(
                page,
                code_demarche=code_demarche,
                cible=cible,
                action=action,
                dossier_calibration=dossier_profil.parent / "calibration",
                etapes_realisees=etapes_realisees,
                avertissements=avertissements,
                prendre_capture=prendre_capture,
            )
        if action == ACTION_AJOUTER_VOEUX_PANIER:
            est_demo = "/demo/" in (page.url or "")
            if not est_demo:
                if not portail_homologue:
                    return self._resultat_refus_action(
                        code_demarche=code_demarche,
                        cible=cible,
                        action=action,
                        message=_MESSAGE_REFUS_PORTAIL_NON_HOMOLOGUE,
                        avertissements=avertissements,
                        page=page,
                        prendre_capture=prendre_capture,
                    )
                analyse_url = urlparse(page.url or "")
                if analyse_url.scheme != "https" or (analyse_url.hostname or "").lower() not in DOMAINES_OFFICIELS_CAMPUS_FRANCE_REEL:
                    return self._resultat_refus_action(
                        code_demarche=code_demarche,
                        cible=cible,
                        action=action,
                        message=(
                            "Action refusée (Règle 6) : la page courante n'est pas sur un domaine officiel "
                            "HTTPS du portail Études en France."
                        ),
                        avertissements=avertissements,
                        page=page,
                        prendre_capture=prendre_capture,
                    )
            return self._executer_ajout_voeux_panier(
                page,
                code_demarche=code_demarche,
                cible=cible,
                action=action,
                voeux=voeux or [],
                profil=(
                    (
                        profil_panier
                        or (
                            profil_maquette_eef()
                            if "/demo/eef-reel" in (page.url or "")
                            else PROFIL_PANIER_DEMO
                        )
                    )
                    if est_demo
                    else PROFIL_PANIER_REEL
                ),
                etapes_realisees=etapes_realisees,
                avertissements=avertissements,
                prendre_capture=prendre_capture,
            )

        # 4. Compréhension du langage naturel (NLU) : défilement, clics génériques, valeurs personnalisées
        attente_connexion_humaine = False
        action_specifique_nlu_executee = False

        if instruction_libre:
            # 4a. Défilement / retour / actualisation
            if _executer_commandes_navigation_et_defilement(page, instruction_libre, etapes_realisees):
                action_specifique_nlu_executee = True

            # 4b. Valeurs personnalisées dictées par l'opérateur (« mets Oran comme ville », « change l'établissement pour ... »)
            extractions = _extraire_modifications_depuis_instruction(instruction_libre, candidat_travail)
            for cle_cand, val_extraite, sels_connus, libelle_modif in extractions:
                modifications_candidat[cle_cand] = val_extraite
                self._dernier_candidat[cle_cand] = val_extraite
                rempli_direct = _remplir_si_present(
                    page,
                    sels_connus,
                    val_extraite,
                    type_champ="texte",
                    libelle_visuel=libelle_modif,
                )
                if not rempli_direct:
                    # Cherche dans le DOM tout champ correspondant au nom de la clé
                    elements_actuels = inspecter_elements_interactifs_page(page)
                    for el in elements_actuels:
                        if el["type_element"] in ("champ", "liste", "zone_texte"):
                            if cle_cand.split("_")[0] in _normaliser_sans_accents(f"{el['libelle']} {el['selecteur']}"):
                                rempli_direct = _remplir_si_present(
                                    page,
                                    [el["selecteur"]],
                                    val_extraite,
                                    type_champ="liste" if el["type_element"] == "liste" else "texte",
                                    libelle_visuel=libelle_modif,
                                )
                                if rempli_direct:
                                    break
                if cle_cand == "lieu_naissance":
                    ant = _determiner_antenne_algerie(val_extraite)
                    _remplir_si_present(page, ["#champ-antenne-ecf"], ant, type_champ="liste")
                    _remplir_si_present(page, ["#inscr-region", "#champ-adresse-postale"], val_extraite)
                champs_remplis.append(libelle_modif)
                etapes_realisees.append(f"Modification en direct appliquée : {libelle_modif}")
                action_specifique_nlu_executee = True

            # 4c. Clic générique sur un bouton/onglet/lien nommé par l'opérateur
            if _cliquer_element_par_intention_naturelle(page, instruction_libre, etapes_realisees):
                action_specifique_nlu_executee = True

        # 5. Exécution des actions structurées Campus France (Guide Septembre 2026) ou IRCC Canada
        if code_demarche == "campus_france":
            attente_connexion_humaine = self._executer_actions_campus_france(
                page,
                action=action,
                instruction_libre=instruction_libre,
                action_specifique_deja_faite=action_specifique_nlu_executee or navigation_explicite_demandee,
                candidat=candidat_travail,
                documents_dechiffres=documents_dechiffres,
                etapes_realisees=etapes_realisees,
                champs_remplis=champs_remplis,
                pieces_televersees=pieces_televersees,
                champs_manquants=champs_manquants,
                avertissements=avertissements,
            )
        else:
            attente_connexion_humaine = self._executer_actions_ircc(
                page,
                action=action,
                instruction_libre=instruction_libre,
                action_specifique_deja_faite=action_specifique_nlu_executee or navigation_explicite_demandee,
                candidat=candidat_travail,
                documents_dechiffres=documents_dechiffres,
                etapes_realisees=etapes_realisees,
                champs_remplis=champs_remplis,
                pieces_televersees=pieces_televersees,
                champs_manquants=champs_manquants,
                avertissements=avertissements,
            )

        avertissements.append(
            "Sécurité Règle 1 active : l'agent s'est arrêté avant le bouton final de soumission officielle."
        )

        # Inspection en direct des éléments interactifs présents sur la page
        elements_page = inspecter_elements_interactifs_page(page)

        # Génération de la réponse conversationnelle intelligente (Perplexity / Claude Cowork)
        reponse_agent = _construire_analyse_contextuelle_et_reponse(
            page,
            code_demarche=code_demarche,
            instruction_libre=instruction_libre,
            candidat=candidat_travail,
            etapes_realisees=etapes_realisees,
            champs_remplis=champs_remplis,
            pieces_televersees=pieces_televersees,
            champs_manquants=champs_manquants,
            elements_page=elements_page,
        )

        if champs_remplis or pieces_televersees:
            resume = (
                f"Action exécutée en direct sur {page.title() or page.url} : "
                f"{len(champs_remplis)} information(s) remplie(s) et {len(pieces_televersees)} pièce(s) jointe(s). "
                "Arrêt de sécurité effectué avant la soumission finale (Règle 1)."
            )
        elif etapes_realisees:
            resume = " — ".join(etapes_realisees)
        elif reponse_agent:
            premiere_ligne = reponse_agent.splitlines()[0]
            resume = premiere_ligne[:240]
        else:
            resume = f"Contrôle direct actif sur {page.url}."

        # Mise à jour du journal dans la barre latérale du navigateur
        try:
            page.evaluate(
                "(msg) => { if (window.__coworkAjouterMessage) window.__coworkAjouterMessage('Co-Pilote IA', msg); }",
                resume,
            )
        except Exception:
            pass

        self._historique_actions.append(
            {
                "action": instruction_libre or action,
                "message": resume,
                "url": page.url,
            }
        )

        octets_png: bytes | None = None
        b64_png: str | None = None
        if prendre_capture:
            try:
                octets_png = page.screenshot(full_page=False, type="png")
                b64_png = base64.b64encode(octets_png).decode("ascii")
            except Exception:
                octets_png = None
                b64_png = None

        # Succès réel uniquement si quelque chose a effectivement été fait sur la page (Règle 4)
        succes_reel = bool(
            champs_remplis
            or pieces_televersees
            or action_specifique_nlu_executee
            or navigation_explicite_demandee
            or action == "ouvrir_portail"
            or (attente_connexion_humaine and action in ("connexion_compte", "inscription_compte"))
        )

        return ResultatActionNavigateur(
            succes=succes_reel,
            code_demarche=code_demarche,
            cible=cible,
            action_executee=action,
            url_courante=page.url,
            titre_page=page.title() or "Portail officiel",
            resume_francais=resume,
            reponse_agent=reponse_agent,
            etapes_realisees=etapes_realisees,
            champs_remplis_libelles=champs_remplis,
            pieces_televersees_libelles=pieces_televersees,
            champs_manquants_libelles=champs_manquants,
            avertissements_securite=avertissements,
            elements_interactifs_page=elements_page,
            modifications_candidat_detectees=modifications_candidat,
            arret_regle1_avant_soumission=True,
            attente_connexion_humaine_regle3=attente_connexion_humaine,
            mode_controle_direct=True,
            capture_base64=b64_png,
            capture_png_octets=octets_png,
        )

    @staticmethod
    def _capturer_page(page: Page | None, prendre_capture: bool) -> bytes | None:
        if page is None or not prendre_capture:
            return None
        try:
            if page.is_closed():
                return None
            return page.screenshot(full_page=False, type="png")
        except Exception:
            return None

    def _resultat_refus_action(
        self,
        *,
        code_demarche: str,
        cible: str,
        action: str,
        message: str,
        avertissements: list[str],
        page: Page | None = None,
        prendre_capture: bool = False,
    ) -> ResultatActionNavigateur:
        """Refus d'une action dédiée (aucune interaction avec la page n'a eu lieu)."""
        avertissements.append(message)
        octets = self._capturer_page(page, prendre_capture)
        url = URLS_CIBLES_OFFICIELS.get(cible, "")
        titre = "Action refusée"
        if page is not None:
            try:
                url = page.url
                titre = page.title() or titre
            except Exception:
                pass
        return ResultatActionNavigateur(
            succes=False,
            code_demarche=code_demarche,
            cible=cible,
            action_executee=action,
            url_courante=url,
            titre_page=titre,
            resume_francais=message,
            reponse_agent=message,
            avertissements_securite=avertissements,
            arret_regle1_avant_soumission=True,
            capture_base64=base64.b64encode(octets).decode("ascii") if octets else None,
            capture_png_octets=octets,
        )

    def _executer_cartographie_page(
        self,
        page: Page,
        *,
        code_demarche: str,
        cible: str,
        action: str,
        dossier_calibration: Path,
        etapes_realisees: list[str],
        avertissements: list[str],
        prendre_capture: bool,
    ) -> ResultatActionNavigateur:
        """Calibration : enregistre la structure des éléments interactifs (sans valeurs, sans clic)."""
        try:
            fichier, nb = cartographier_page(page, dossier_calibration=dossier_calibration)
        except Exception as exc:
            msg = f"Cartographie impossible ({type(exc).__name__})."
            return self._resultat_refus_action(
                code_demarche=code_demarche,
                cible=cible,
                action=action,
                message=msg,
                avertissements=avertissements,
                page=page,
                prendre_capture=False,
            )
        resume = (
            f"Cartographie de calibration enregistrée : {nb} élément(s) interactif(s) "
            "(structure uniquement : aucune valeur saisie lue, aucun clic effectué)."
        )
        etapes_realisees.append(resume)
        avertissements.append(
            "Calibration : les sélecteurs du vrai portail restent « non testés » tant qu'une session "
            "supervisée n'a pas validé le résultat."
        )
        octets = self._capturer_page(page, prendre_capture)
        self._historique_actions.append({"action": action, "message": resume, "url": page.url})
        return ResultatActionNavigateur(
            succes=True,
            code_demarche=code_demarche,
            cible=cible,
            action_executee=action,
            url_courante=page.url,
            titre_page=page.title() or "Portail",
            resume_francais=resume,
            reponse_agent=resume,
            etapes_realisees=etapes_realisees,
            avertissements_securite=avertissements,
            arret_regle1_avant_soumission=True,
            capture_base64=base64.b64encode(octets).decode("ascii") if octets else None,
            capture_png_octets=octets,
            fichier_calibration=str(fichier),
        )

    def _executer_ajout_voeux_panier(
        self,
        page: Page,
        *,
        code_demarche: str,
        cible: str,
        action: str,
        voeux: list[dict[str, Any]],
        profil: ProfilSelecteursPanier,
        etapes_realisees: list[str],
        avertissements: list[str],
        prendre_capture: bool,
    ) -> ResultatActionNavigateur:
        """Ajoute des formations au panier + motivation par formation (jamais de certification ni de
        soumission : gardes Règle 1 et pause CAPTCHA/2FA Règle 2)."""
        if not profil.teste:
            avertissements.append(
                "Sélecteurs du vrai portail « non testés » : résultat à vérifier par l'opérateur."
            )
        resultats, notes, blocage = ajouter_voeux_au_panier(
            page,
            voeux,
            profil=profil,
            est_interdit=_est_element_soumission_interdit_regle1,
            detecteur_blocage=_detecter_captcha_ou_2fa_sur_page,
        )
        comptes: dict[str, int] = {}
        for r in resultats:
            comptes[r["statut"]] = comptes.get(r["statut"], 0) + 1
        nb_motiv = sum(1 for r in resultats if r["motivation_enregistree"])
        detail_statuts = ", ".join(f"{n} {s}" for s, n in sorted(comptes.items())) or "aucun vœu"
        resume = (
            f"Panier de vœux Campus France : {len(resultats)} vœu(x) traité(s) ({detail_statuts}) ; "
            f"{nb_motiv} motivation(s) enregistrée(s). Arrêt avant certification et soumission (Règle 1)."
        )
        etapes_realisees.append(resume)
        avertissements.extend(notes)
        avertissements.append(
            "Sécurité Règle 1 active : aucune case de certification cochée, bouton de soumission jamais cliqué."
        )
        if blocage:
            resume = (
                "Contrôle de sécurité (CAPTCHA ou double authentification 2FA) détecté (Règle 2) : "
                "l'agent s'est mis en pause. " + resume
            )
        succes = (not blocage) and all(r["statut"] != STATUT_ERREUR_VOEU for r in resultats)
        octets = self._capturer_page(page, prendre_capture)
        try:
            page.evaluate(
                "(msg) => { if (window.__coworkAjouterMessage) window.__coworkAjouterMessage('Co-Pilote IA', msg); }",
                resume,
            )
        except Exception:
            pass
        self._historique_actions.append({"action": action, "message": resume, "url": page.url})
        return ResultatActionNavigateur(
            succes=succes,
            code_demarche=code_demarche,
            cible=cible,
            action_executee=action,
            url_courante=page.url,
            titre_page=page.title() or "Portail",
            resume_francais=resume,
            reponse_agent=resume,
            etapes_realisees=etapes_realisees,
            avertissements_securite=avertissements,
            elements_interactifs_page=[],  # le contenu des zones de motivation ne doit pas fuiter (R5)
            arret_regle1_avant_soumission=True,
            blocage_captcha_ou_2fa=blocage,
            capture_base64=base64.b64encode(octets).decode("ascii") if octets else None,
            capture_png_octets=octets,
            resultats_voeux=resultats,
        )

    def _executer_actions_campus_france(
        self,
        page: Page,
        *,
        action: str,
        instruction_libre: str | None,
        action_specifique_deja_faite: bool = False,
        candidat: dict[str, Any],
        documents_dechiffres: list[tuple[str, str, str, bytes]],
        etapes_realisees: list[str],
        champs_remplis: list[str],
        pieces_televersees: list[str],
        champs_manquants: list[str],
        avertissements: list[str],
    ) -> bool:
        inst = _normaliser_sans_accents(instruction_libre or "")
        attente_mdp = False
        antenne = _determiner_antenne_algerie(candidat.get("lieu_naissance") or candidat.get("adresse"))

        if action == "ouvrir_portail":
            return False

        def _etape_section(libelle_ok: str, nb_avant: int, nom_rubrique: str) -> None:
            """N'annonce une rubrique « pré-remplie » que si au moins un champ a réellement été rempli
            (Règle 4 : ne jamais affirmer un résultat inexistant)."""
            if len(champs_remplis) > nb_avant:
                etapes_realisees.append(libelle_ok)
            else:
                etapes_realisees.append(
                    f"Rubrique « {nom_rubrique} » : aucun champ correspondant trouvé sur la page courante — rien n'a été rempli"
                )

        # Portail RÉEL non connecté : rien à remplir tant que l'opérateur ne s'est pas connecté lui-même (Règle 3)
        if (
            "/demo/" not in (page.url or "")
            and action not in ("connexion_compte", "inscription_compte")
            and not any(m in inst for m in ("connecter", "connexion", "login", "inscri", "creer un compte", "creer mon compte"))
            and _portail_reel_non_connecte(page)
        ):
            etapes_realisees.append(
                "Vous n'êtes pas connecté au portail Études en France : connectez-vous vous-même dans la fenêtre "
                "du navigateur (Règle 3 : aucun mot de passe n'est saisi ni stocké par l'agent), puis relancez l'action."
            )
            avertissements.append(
                "Règle 3 : connexion humaine requise sur le portail réel avant tout pré-remplissage."
            )
            return True

        # Déterminer quelles sous-sections exécuter selon `action` ou `instruction_libre`
        tout_remplir = action == "preremplissage_complet" or any(
            m in inst
            for m in (
                "tout remplir",
                "pre-remplir tout",
                "preremplir tout",
                "remplis tout",
                "remplir tout",
                "integralite",
                "complet",
                "dossier etudes en france",
                "remplis cette page",
                "remplis la page",
                "remplis le formulaire",
                "complete tout",
            )
        )

        # A0. Questionnaire d'éligibilité (« Dois-je candidater par Études en France ? » — Guide Section 3, p. 18-20)
        if (
            tout_remplir
            or action == "verifier_eligibilite"
            or any(m in inst for m in ("eligibilite", "dois-je candidater", "questionnaire"))
        ):
            _cliquer_si_present(page, ["#onglet-demo-compte", "a:has-text('Dois-je candidater')"])
            if _remplir_si_present(page, ["#elig-pays-residence"], candidat.get("pays_residence") or "Algérie"):
                champs_remplis.append("Pays de résidence (Questionnaire d'éligibilité)")
            if _remplir_si_present(page, ["#elig-nationalite"], candidat.get("nationalite") or "Algérienne"):
                champs_remplis.append("Nationalité (Questionnaire d'éligibilité)")
            _remplir_si_present(page, ["#elig-bac-europeen"], "Non", type_champ="liste")
            _remplir_si_present(page, ["#elig-filiere-selective"], "Non", type_champ="liste")
            if not tout_remplir:
                etapes_realisees.append("Questionnaire d'éligibilité « Dois-je candidater par Études en France ? » renseigné")

        # A. Création de compte (« S'inscrire » — Guide Section 3, p. 21-24)
        if action == "inscription_compte" or any(m in inst for m in ("inscrire", "inscription", "creer un compte", "creer mon compte")):
            _cliquer_si_present(
                page,
                [
                    "#onglet-demo-compte",
                    "a:has-text(\"S'inscrire\")",
                    "button:has-text(\"S'inscrire\")",
                    "[href*='inscription']",
                    "[href*='register']",
                ],
            )
            etapes_realisees.append("Ouverture de la rubrique « S'inscrire » (Création de compte Études en France)")
            if _remplir_si_present(page, ["#inscr-prenom", "#champ-prenom", "input[name*='prenom']"], candidat.get("prenom")):
                champs_remplis.append("Prénom (Inscription)")
            if _remplir_si_present(page, ["#inscr-nom", "#champ-nom-famille", "input[name*='nom']"], candidat.get("nom")):
                champs_remplis.append("Nom de famille (Inscription)")
            if _remplir_si_present(page, ["#inscr-email", "#champ-email", "input[type='email']"], candidat.get("email")):
                champs_remplis.append("Adresse e-mail (Inscription)")
            if _remplir_si_present(
                page,
                ["#inscr-espace-cf"],
                "Espace Campus France Algérie",
                type_champ="liste",
            ):
                champs_remplis.append("Espace Campus France de résidence (Espace Campus France Algérie)")
            if _remplir_si_present(page, ["#inscr-region"], antenne):
                champs_remplis.append(f"Région / Antenne de résidence ({antenne})")
            avertissements.append(
                "Règle 3 : définissez le mot de passe manuellement et validez le lien d'activation reçu par e-mail (valable 48h)."
            )
            attente_mdp = True

        # B. Connexion (« Se connecter » — Guide Section 3, p. 25-27)
        if action == "connexion_compte" or any(m in inst for m in ("connecter", "connexion", "login", "identifiant")):
            _cliquer_si_present(
                page,
                [
                    "#onglet-demo-compte",
                    "a:has-text('Se connecter')",
                    "button:has-text('Se connecter')",
                    "[href*='login']",
                    "[href*='connexion']",
                ],
            )
            if _remplir_si_present(
                page,
                ["#login-identifiant-eef", "#champ-email", "input[name='username']", "input[type='email']"],
                candidat.get("email"),
            ):
                champs_remplis.append("Identifiant / Adresse e-mail de connexion")
            etapes_realisees.append(
                "Ouverture de la page « Se connecter » (Saisie humaine du mot de passe requise — Règle 3)"
            )
            avertissements.append(
                "Attention (Guide Septembre 2026, p. 25) : le compte Études en France est bloqué pendant 30 minutes au bout de 5 tentatives de mot de passe erronées."
            )
            attente_mdp = True

        # C. Section 4 — Mon espace étudiant (Identité, Passeport, Coordonnées, Statut particulier)
        if (
            tout_remplir
            or action == "preremplir_espace_etudiant"
            or any(m in inst for m in ("espace etudiant", "informations personnelles", "mon identite", "identite", "passeport", "coordonnees", "statut particulier"))
        ):
            nb_avant_c = len(champs_remplis)
            _cliquer_si_present(
                page,
                [
                    "#onglet-demo-espace-etudiant",
                    "#onglet-informations-personnelles-eef",
                    "a:has-text('Mon espace étudiant')",
                    "button:has-text('Mes informations personnelles')",
                ],
            )
            correspondances_identite = [
                ("nom", ["#champ-nom-famille", "#eef-nom-famille", "input[name='nom_famille']"], "texte"),
                ("prenom", ["#champ-prenom", "#eef-prenom-candidat", "input[name='prenom_candidat']"], "texte"),
                ("sexe", ["#champ-sexe", "#eef-civilite-sexe", "select[name='sexe']"], "liste"),
                ("date_naissance", ["#champ-date-naissance", "#eef-date-naissance", "input[name='date_naissance']"], "texte"),
                ("lieu_naissance", ["#champ-lieu-naissance", "#eef-ville-naissance", "input[name='lieu_naissance']"], "texte"),
                ("nationalite", ["#champ-nationalite", "#eef-nationalite", "input[name='nationalite']"], "texte"),
                ("pays_residence", ["#champ-pays-residence", "#eef-pays-residence", "input[name='pays_residence']"], "texte"),
                ("email", ["#champ-email", "#eef-email-contact", "input[name='email']"], "texte"),
                ("telephone", ["#champ-telephone", "#eef-telephone-mobile", "input[name='telephone']"], "texte"),
                ("numero_passeport", ["#champ-numero-passeport", "#eef-numero-piece-identite", "input[name='numero_passeport']"], "texte"),
                ("date_expiration_passeport", ["#champ-date-expiration-passeport", "#eef-date-validite-piece", "input[name='date_expiration_passeport']"], "texte"),
            ]
            for cle_cand, sels, t_ch in correspondances_identite:
                val = candidat.get(cle_cand)
                lib_fr = LIBELLES_CHAMPS_CANDIDAT_FR.get(cle_cand, cle_cand)
                if not val:
                    champs_manquants.append(lib_fr)
                elif _remplir_si_present(page, sels, str(val), type_champ=t_ch, libelle_visuel=lib_fr):
                    if lib_fr not in champs_remplis:
                        champs_remplis.append(lib_fr)

            _remplir_si_present(page, ["#champ-antenne-ecf"], antenne, type_champ="liste", libelle_visuel="Antenne ECF")
            if _remplir_si_present(page, ["#champ-adresse-postale"], candidat.get("adresse") or candidat.get("lieu_naissance"), libelle_visuel="Adresse postale"):
                champs_remplis.append("Adresse postale / Wilaya (Coordonnées)")
            _etape_section(
                f"Rubrique « Mon espace étudiant — Informations personnelles, Passeport & Coordonnées (Antenne {antenne}) » pré-remplie",
                nb_avant_c,
                "Mon espace étudiant",
            )

        # D. Section 4 (Onglets 2 & 3) — Dossier de scolarité, CV, Parcours (min. 2 activités) & Compétences linguistiques
        if (
            tout_remplir
            or action == "preremplir_scolarite_et_langues"
            or any(m in inst for m in ("scolarite", "cursus", "diplome", "activite", "parcours", "cv", "langue", "francais", "anglais", "tcf", "delf", "piece"))
        ):
            nb_avant_d = len(champs_remplis)
            nb_pieces_avant_d = len(pieces_televersees)
            _cliquer_si_present(
                page,
                [
                    "#onglet-demo-scolarite-langues",
                    "#onglet-cursus-diplomes-eef",
                    "a:has-text('Mon dossier de scolarité')",
                    "button:has-text('Mon dossier de scolarité')",
                ],
            )
            niv = candidat.get("niveau_actuel")
            if niv:
                if _remplir_si_present(page, ["#champ-niveau-actuel", "#eef-dernier-niveau-etudes"], str(niv), libelle_visuel="Niveau actuel"):
                    champs_remplis.append("Niveau d'études actuel")
                _remplir_si_present(page, ["#activite-1-type"], "Un bac ou équivalent", type_champ="liste")
                _remplir_si_present(page, ["#activite-1-intitule"], f"Baccalauréat de l'enseignement secondaire ({candidat.get('lieu_naissance') or 'Algérie'})")
                _remplir_si_present(page, ["#activite-2-type"], "Une année d'études supérieures", type_champ="liste")
                if _remplir_si_present(page, ["#activite-2-intitule"], str(niv)):
                    champs_remplis.append("Parcours scolaire et professionnel (2 activités obligatoires)")
            else:
                champs_manquants.append("Niveau d'études actuel")

            _remplir_si_present(page, ["#champ-francais-etudie"], "Oui", type_champ="liste")
            _remplir_si_present(page, ["#champ-francais-volume-heures"], "Plus de 1000 heures", type_champ="liste")
            _remplir_si_present(page, ["#champ-francais-duree"], "4 ans et plus", type_champ="liste")
            if _remplir_si_present(page, ["#champ-francais-niveau-atteint"], "Avancé", type_champ="liste"):
                champs_remplis.append("Compétences linguistiques : Français (> 1000 heures, 4 ans et plus, Avancé)")
            _remplir_si_present(page, ["#champ-anglais-etudie"], "Oui", type_champ="liste")

            selecteurs_fichiers_cf: dict[str, tuple[str, list[str]]] = {
                "passeport": ("Passeport biométrique", ["#upload-passeport", "#eef-upload-passeport"]),
                "photo_identite": ("Photo d'identité", ["#upload-photo-identite", "#eef-upload-photo-identite"]),
                "releve_notes_bac": ("Relevé de notes du Baccalauréat", ["#upload-releve-notes-bac", "#eef-upload-releve-bac"]),
                "diplome_bac": ("Diplôme du Baccalauréat", ["#upload-diplome-bac", "#eef-upload-diplome-bac"]),
                "releves_notes_superieur": ("Relevés de notes supérieurs", ["#upload-releves-notes-superieur", "#eef-upload-releves-superieur"]),
                "cv": ("Curriculum Vitae (CV)", ["#upload-cv", "#eef-upload-cv"]),
                "attestation_langue_francaise": ("Attestation de test de français (TCF / DELF / DALF)", ["#upload-test-francais"]),
            }
            self._televerser_documents_disponibles(
                page,
                documents_dechiffres=documents_dechiffres,
                carte_selecteurs=selecteurs_fichiers_cf,
                pieces_televersees=pieces_televersees,
            )
            _etape_section(
                "Rubriques « Mon dossier de scolarité (CV + 2 activités obligatoires) » et « Mes compétences linguistiques (Français > 1000h, Avancé) » complétées",
                # une pièce téléversée compte aussi comme un résultat réel
                nb_avant_d - (len(pieces_televersees) - nb_pieces_avant_d),
                "Mon dossier de scolarité / Compétences linguistiques",
            )

        # E. Section 5 — Mon dossier de candidature (Panier de formations max 7 choix & Texte de motivation 4000 car.)
        if (
            tout_remplir
            or action == "preremplir_panier_formations_et_motivations"
            or any(m in inst for m in ("panier", "formation", "catalogue", "motivation", "candidature", "voeu"))
        ):
            nb_avant_e = len(champs_remplis)
            _cliquer_si_present(
                page,
                [
                    "#onglet-demo-candidature",
                    "#onglet-panier-formations-eef",
                    "a:has-text('Mon panier de formations')",
                    "button:has-text('Mon dossier de candidature')",
                ],
            )
            prog = candidat.get("programme_vise")
            etab = candidat.get("etablissement_vise")
            if prog:
                if _remplir_si_present(page, ["#champ-programme-vise", "#eef-intitule-formation-visee", "input[name*='formation']"], str(prog), libelle_visuel="Formation visée"):
                    if "Formation visée (Panier de formations)" not in champs_remplis:
                        champs_remplis.append("Formation visée (Panier de formations)")
            else:
                champs_manquants.append("Formation / Programme visé")

            if etab:
                if _remplir_si_present(page, ["#champ-etablissement-vise", "#eef-etablissement-accueil", "input[name*='etablissement']"], str(etab), libelle_visuel="Établissement visé"):
                    if "Établissement d'accueil visé" not in champs_remplis:
                        champs_remplis.append("Établissement d'accueil visé")
            else:
                champs_manquants.append("Établissement visé")

            motivation = _generer_motivation_personnalisee(candidat)
            if _remplir_si_present(page, ["#champ-texte-motivation", "textarea[name*='motivation']"], motivation, libelle_visuel="Texte de motivation"):
                champs_remplis.append("Texte de motivation personnalisé (conformité 4 000 caractères max)")

            _etape_section(
                "Rubrique « Mon panier de formations (max 7 choix) & Texte de motivation (max 4 000 caractères) » pré-remplie",
                nb_avant_e,
                "Mon panier de formations & Texte de motivation",
            )

        # F. Section 5 suite — Mes paiements (20 000 DZD / 10 000 DZD) & Mes rendez-vous (Antennes Algérie)
        if (
            tout_remplir
            or action == "preparer_paiement_et_rdv"
            or any(m in inst for m in ("paiement", "payer", "quittance", "rendez-vous", "rdv", "entretien", "20 000", "20000"))
        ):
            _cliquer_si_present(page, ["#onglet-demo-paiements-rdv", "a:has-text('Mes paiements')"])
            nb_avant_f = len(champs_remplis)
            nom_payeur = f"{candidat.get('nom') or ''} {candidat.get('prenom') or ''}".strip()
            if nom_payeur and _remplir_si_present(page, ["#champ-nom-payeur"], nom_payeur, libelle_visuel="Nom du payeur"):
                champs_remplis.append("Nom du payeur (Déclaration de paiement Campus France Algérie)")
            _remplir_si_present(page, ["#champ-lieu-rdv-ecf"], f"Espace Campus France {antenne}", type_champ="liste")
            _etape_section(
                f"Rubriques « Mes paiements (20 000 DZD / 10 000 DZD) » et « Mes rendez-vous ({antenne}) » préparées sans soumission finale",
                nb_avant_f,
                "Mes paiements / Mes rendez-vous",
            )

        # G. Section 6 — Mon dossier pré-consulaire (« Je suis accepté » — 4 étapes)
        if (
            tout_remplir
            or action == "preremplir_dossier_preconsulaire"
            or any(m in inst for m in ("pre-consulaire", "preconsulaire", "accepte", "acceptation papier", "programme d'echange", "programme d echange"))
        ):
            _cliquer_si_present(page, ["#onglet-demo-preconsulaire", "a:has-text('Mon dossier pré-consulaire')"])
            if _remplir_si_present(page, ["#preconsulaire-etape1-type"], "Acceptation papier", type_champ="liste"):
                champs_remplis.append("Dossier pré-consulaire — Étape 1/4 : Type de projet d'étude (Acceptation papier)")
            if _remplir_si_present(page, ["#preconsulaire-etape2-categorie"], "Formation diplômante", type_champ="liste"):
                champs_remplis.append("Dossier pré-consulaire — Étape 2/4 : Catégorie de formation (Formation diplômante)")
            if candidat.get("programme_vise"):
                if _remplir_si_present(page, ["#preconsulaire-etape3-formation"], str(candidat["programme_vise"])):
                    champs_remplis.append("Dossier pré-consulaire — Étape 3/4 : Formation et établissement d'accueil")
            if candidat.get("etablissement_vise"):
                _remplir_si_present(page, ["#preconsulaire-etape3-etablissement"], str(candidat["etablissement_vise"]))
            if _remplir_si_present(
                page,
                ["#preconsulaire-etape4-motivation"],
                _generer_motivation_personnalisee(candidat),
            ):
                champs_remplis.append("Dossier pré-consulaire — Étape 4/4 : Motivations et justificatif (max 4 000 caractères)")
            elif not tout_remplir:
                champs_remplis.append("Dossier pré-consulaire — Étape 3/4 : Formation et établissement d'accueil")
                champs_remplis.append("Dossier pré-consulaire — Étape 4/4 : Motivations et justificatif (max 4 000 caractères)")
            if not tout_remplir:
                etapes_realisees.append(
                    "Rubrique « Mon dossier pré-consulaire (Étapes 1 à 4) » pré-remplie — Arrêt avant soumission (Règle 1)"
                )

        # H. Auto-remplissage intelligent du DOM réel si l'utilisateur demande de remplir la page
        est_question_pure = any(
            m in inst
            for m in (
                "?",
                "combien",
                "quel ",
                "quelle ",
                "quels ",
                "quelles ",
                "comment ",
                "pourquoi ",
                "quand ",
                "explique",
                "analyse",
                "que vois-tu",
                "qu'est-ce",
                "ou suis-je",
            )
        ) and not any(m in inst for m in ("remplis", "preremplir", "pre-remplir", "complete", "mets", "ecris"))

        if (tout_remplir or any(m in inst for m in ("remplis", "complete", "formulaire"))) and not est_question_pure:
            _remplir_formulaire_intelligent_dom(page, candidat, champs_remplis)

        if (
            action == "instruction_libre"
            and not etapes_realisees
            and not champs_remplis
            and not action_specifique_deja_faite
            and not est_question_pure
        ):
            nb_dom = _remplir_formulaire_intelligent_dom(page, candidat, champs_remplis)
            if nb_dom > 0:
                etapes_realisees.append(f"{nb_dom} champ(s) détecté(s) sur la page active et rempli(s) en direct")
            else:
                return self._executer_actions_campus_france(
                    page,
                    action="preremplissage_complet",
                    instruction_libre=None,
                    action_specifique_deja_faite=True,
                    candidat=candidat,
                    documents_dechiffres=documents_dechiffres,
                    etapes_realisees=etapes_realisees,
                    champs_remplis=champs_remplis,
                    pieces_televersees=pieces_televersees,
                    champs_manquants=champs_manquants,
                    avertissements=avertissements,
                )

        # Enregistrement du brouillon si des champs ont été remplis (autorisé par Règle 1)
        if (champs_remplis or pieces_televersees or "brouillon" in inst or "enregistre" in inst) and _cliquer_si_present(
            page,
            ["#btn-enregistrer-brouillon", "#btn-enregistrer-rubrique-eef"],
            libelle_visuel="Enregistrer le brouillon",
        ):
            etapes_realisees.append("Brouillon enregistré avec succès (sans soumission officielle)")

        return attente_mdp

    def _executer_actions_ircc(
        self,
        page: Page,
        *,
        action: str,
        instruction_libre: str | None,
        action_specifique_deja_faite: bool = False,
        candidat: dict[str, Any],
        documents_dechiffres: list[tuple[str, str, str, bytes]],
        etapes_realisees: list[str],
        champs_remplis: list[str],
        pieces_televersees: list[str],
        champs_manquants: list[str],
        avertissements: list[str],
    ) -> bool:
        inst = _normaliser_sans_accents(instruction_libre or "")
        tout_remplir = action == "preremplissage_complet" or any(
            m in inst
            for m in (
                "tout remplir",
                "pre-remplir",
                "preremplir",
                "remplir le formulaire",
                "imm 1294",
                "imm1294",
                "formulaire ircc",
                "toute la demande",
                "complet",
                "tout",
                "remplis cette page",
                "remplis la page",
            )
        )

        if action == "connexion_compte" or any(m in inst for m in ("clegc", "connecter", "connexion")):
            avertissements.append(
                "Règle 3 : aucune CléGC ni mot de passe IRCC n'est stocké par l'agent. Authentifiez-vous manuellement et résolvez les questions de sécurité."
            )
            etapes_realisees.append("Attente d'authentification humaine CléGC / Partenaire de connexion sur le portail IRCC")
            return True

        if action == "ouvrir_portail":
            return False

        est_question_pure = any(
            m in inst
            for m in (
                "?",
                "combien",
                "quel ",
                "quelle ",
                "quels ",
                "quelles ",
                "comment ",
                "pourquoi ",
                "explique",
                "analyse",
                "que vois-tu",
                "qu'est-ce",
            )
        ) and not any(m in inst for m in ("remplis", "preremplir", "pre-remplir", "complete", "mets", "ecris"))

        if est_question_pure and not tout_remplir:
            return False

        remplir_identite = (
            tout_remplir
            or action == "preremplir_identite_ircc"
            or any(m in inst for m in ("identite", "passeport", "nom", "prenom", "demande"))
            or (action == "instruction_libre" and not action_specifique_deja_faite and not any(m in inst for m in ("dli", "fonds", "finan", "piece", "televerse")))
        )
        remplir_dli_fonds = (
            tout_remplir
            or action == "preremplir_dli_fonds_ircc"
            or any(m in inst for m in ("dli", "eed", "etablissement", "fonds", "finan", "demande"))
            or (action == "instruction_libre" and not action_specifique_deja_faite and not any(m in inst for m in ("identite", "passeport", "piece", "televerse")))
        )
        televerser_pieces = (
            tout_remplir
            or action == "televerser_pieces_ircc"
            or any(m in inst for m in ("piece", "justificatif", "televerse", "pal", "caq", "imm5645", "loa", "demande"))
            or (action == "instruction_libre" and not action_specifique_deja_faite and not any(m in inst for m in ("identite", "dli", "fonds")))
        )

        if remplir_identite:
            _cliquer_si_present(page, ["#etape-ircc-identite-passeport"])
            correspondances_identite_ircc = [
                ("nom", ["#ircc-nom-famille", "#ircc-reel-nom-famille"], "texte"),
                ("prenom", ["#ircc-prenom", "#ircc-reel-prenom"], "texte"),
                ("sexe", ["#ircc-sexe", "#ircc-reel-sexe"], "liste"),
                ("date_naissance", ["#ircc-date-naissance", "#ircc-reel-date-naissance"], "texte"),
                ("lieu_naissance", ["#ircc-lieu-naissance", "#ircc-reel-ville-naissance"], "texte"),
                ("nationalite", ["#ircc-nationalite", "#ircc-reel-citoyennete"], "texte"),
                ("pays_residence", ["#ircc-pays-residence", "#ircc-reel-pays-residence"], "texte"),
                ("email", ["#ircc-email", "#ircc-reel-courriel"], "texte"),
                ("telephone", ["#ircc-telephone", "#ircc-reel-telephone"], "texte"),
                ("numero_passeport", ["#ircc-numero-passeport", "#ircc-reel-numero-passeport"], "texte"),
                ("date_expiration_passeport", ["#ircc-date-expiration-passeport", "#ircc-reel-expiration-passeport"], "texte"),
            ]
            for cle_cand, sels, t_ch in correspondances_identite_ircc:
                val = candidat.get(cle_cand)
                lib_fr = LIBELLES_CHAMPS_CANDIDAT_FR.get(cle_cand, cle_cand)
                if val is None or (isinstance(val, str) and not val.strip()):
                    champs_manquants.append(lib_fr)
                elif _remplir_si_present(page, sels, str(val), type_champ=t_ch, libelle_visuel=lib_fr):
                    if lib_fr not in champs_remplis:
                        champs_remplis.append(lib_fr)

        if remplir_dli_fonds:
            _cliquer_si_present(page, ["#etape-ircc-etudes-dli-fonds"])
            correspondances_dli_ircc = [
                ("etablissement_vise", ["#ircc-etablissement-dli", "#ircc-reel-etablissement-dli"], "texte"),
                ("programme_vise", ["#ircc-programme-etudes", "#ircc-reel-programme-etudes"], "texte"),
                ("fonds_disponibles_eur", ["#ircc-fonds-disponibles-eur", "#ircc-reel-fonds-disponibles-eur"], "texte"),
            ]
            for cle_cand, sels, t_ch in correspondances_dli_ircc:
                val = candidat.get(cle_cand)
                lib_fr = LIBELLES_CHAMPS_CANDIDAT_FR.get(cle_cand, cle_cand)
                if val is None or (isinstance(val, str) and not val.strip()):
                    champs_manquants.append(lib_fr)
                elif _remplir_si_present(page, sels, str(val), type_champ=t_ch, libelle_visuel=lib_fr):
                    if lib_fr not in champs_remplis:
                        champs_remplis.append(lib_fr)

        if televerser_pieces:
            _cliquer_si_present(page, ["#etape-ircc-pieces-justificatives"])
            selecteurs_fichiers_ircc: dict[str, tuple[str, list[str]]] = {
                "passeport": ("Passeport valide", ["#ircc-upload-passeport", "#ircc-reel-upload-passeport"]),
                "lettre_admission_dli": ("Lettre d'admission EED / DLI", ["#ircc-upload-lettre-admission-dli", "#ircc-reel-upload-loa-dli"]),
                "attestation_provinciale_pal_caq": ("Lettre d'attestation provinciale (LAP / PAL) ou CAQ Québec", ["#ircc-upload-pal-caq", "#ircc-reel-upload-pal-caq"]),
                "preuve_financiere": ("Preuve de ressources financières (seuil 20 635 CAD)", ["#ircc-upload-preuve-financiere", "#ircc-reel-upload-preuve-fonds"]),
                "photo_identite": ("Photographie numérique aux normes IRCC", ["#ircc-upload-photo-identite", "#ircc-reel-upload-photo"]),
                "formulaire_imm5645": ("Formulaire d'informations sur la famille (IMM 5645)", ["#ircc-upload-imm5645", "#ircc-reel-upload-imm5645"]),
            }
            self._televerser_documents_disponibles(
                page,
                documents_dechiffres=documents_dechiffres,
                carte_selecteurs=selecteurs_fichiers_ircc,
                pieces_televersees=pieces_televersees,
            )

        if remplir_identite or remplir_dli_fonds or televerser_pieces:
            _remplir_formulaire_intelligent_dom(page, candidat, champs_remplis)
            etapes_realisees.append(
                "Pré-remplissage IRCC Canada (Identité, Passeport, Établissement désigné EED/DLI, Ressources financières & Pièces justificatives)"
            )
            if _cliquer_si_present(
                page,
                ["#btn-enregistrer-brouillon-ircc", "#btn-ircc-sauvegarder-demande"],
                libelle_visuel="Sauvegarder le brouillon IRCC",
            ):
                etapes_realisees.append("Demande IRCC sauvegardée en brouillon (sans signature ni transmission finale — Règle 1)")

        return False

    @staticmethod
    def _televerser_documents_disponibles(
        page: Page,
        *,
        documents_dechiffres: list[tuple[str, str, str, bytes]],
        carte_selecteurs: dict[str, tuple[str, list[str]]],
        pieces_televersees: list[str],
    ) -> None:
        if not documents_dechiffres:
            return
        par_type: dict[str, tuple[str, str, bytes]] = {}
        for type_piece, nom_orig, mime, octets in documents_dechiffres:
            par_type[type_piece] = (nom_orig, mime, octets)

        with tempfile.TemporaryDirectory(prefix="be_pilote_upload_") as tmp_dir:
            racine = Path(tmp_dir)
            for type_piece, (libelle_fr, selecteurs) in carte_selecteurs.items():
                info = par_type.get(type_piece)
                if info is None:
                    continue
                _nom_orig, mime, octets = info
                ext = ".pdf" if mime == "application/pdf" else ".png"
                fichier_tmp = racine / f"{type_piece}{ext}"
                fichier_tmp.write_bytes(octets)
                for sel in selecteurs:
                    try:
                        loc = page.locator(sel)
                        if loc.count() > 0:
                            _animer_element_dans_navigateur(page, loc.first, f"📎 Pièce : {libelle_fr}")
                            loc.first.set_input_files(str(fichier_tmp))
                            pieces_televersees.append(libelle_fr)
                            break
                    except Exception:
                        continue


# Alias de compatibilité (mode local / tests directs UNIQUEMENT). Plus aucune route de l'API ne l'utilise :
# chaque bureau a sa propre session dans `app.agent_local.sessions_navigateur.RegistreSessionsNavigateur`.
pilote_navigateur_global = GestionnairePiloteNavigateur()
