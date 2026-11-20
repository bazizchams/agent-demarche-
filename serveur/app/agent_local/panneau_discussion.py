"""Panneau de DISCUSSION de l'agent, injecté dans la fenêtre visible de l'utilisateur (style Claude Cowork).

L'utilisateur voit l'agent agir EN DIRECT dans sa propre fenêtre (élément surligné, petit curseur animé,
saisie qui apparaît), pas des captures d'écran. À droite, un panneau repliable affiche ce que l'agent
annonce (ce qu'il va faire, fait, a fait, problèmes, demandes d'aide) et permet d'écrire à l'agent et de
le mettre en Pause / Reprendre / Arrêter.

Sécurité et accessibilité du script injecté (`JS_PANNEAU_DISCUSSION`) :
- DOM uniquement par `createElement` / `textContent` ; aucun `innerHTML`, aucun `eval` ;
- Shadow DOM FERMÉ : le style du portail n'affecte pas le panneau et inversement, et les sélecteurs de l'agent
  (`textarea`, `button`, texte…) ne risquent pas de tomber sur le panneau ;
- `role="log"` + `aria-live` pour le fil, `role="alert"` pour les alertes et demandes d'aide, focus visible,
  `prefers-reduced-motion` respecté (curseur et défilement sans animation) ;
- le surlignage ne lit JAMAIS la valeur d'un champ ; un champ sensible (mot de passe, identifiant,
  passeport, identité) est signalé à Python (`sensible`) pour que son libellé ne soit pas transmis ;
- jamais dans un iframe.

Pont Python <-> page (`expose_function`) : `agent_envoyer_message(texte)` et `agent_commande(code)`.
Les callbacks s'exécutent dans le fil Playwright : ils ne font qu'enregistrer / relayer, sans toucher à la page.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any
from weakref import WeakKeyDictionary

journal = logging.getLogger("app.agent_local.panneau_discussion")

NOM_PONT_MESSAGE = "agent_envoyer_message"
NOM_PONT_COMMANDE = "agent_commande"
TYPES_MESSAGE = ("agent", "action", "alerte", "demande_humaine", "utilisateur")
ETATS_PANNEAU = ("inactif", "travaille", "pause", "attente_humain", "arrete", "termine")
NB_MESSAGES_REJOUES = 200

JS_PANNEAU_DISCUSSION = """
(function () {
  "use strict";
  if (window.top !== window || window.__agentPanneau) return;
  var MAX_MESSAGES = 200;
  var MAX_SAISIE = 1000;
  var LARGEUR_PANNEAU = 360;
  var LARGEUR_MIN_ECRAN = 700;
  var DUREE_SURLIGNAGE_MS = 2200;
  var DUREE_CURSEUR_MS = 2400;
  var DUREE_MAX_TRAJET_MS = 480;
  var SEUIL_BAS_PX = 48;
  var NS_SVG = "http://www.w3.org/2000/svg";
  var margeAvant = null;
  var LIBELLES = {
    agent: "Agent", action: "Action", alerte: "Alerte",
    demande_humaine: "J'ai besoin de vous", utilisateur: "Vous"
  };
  var ETATS = {
    inactif: "Inactif", travaille: "Au travail", pause: "En pause",
    attente_humain: "Attend votre aide", arrete: "Arrêté", termine: "Terminé"
  };
  var ICONES = {
    agent: ["M3 4h10v7H8l-3 2.5V11H3z"],
    action: ["M3 2l9 4-4 1.5L6.5 12z"],
    alerte: ["M8 2l6.5 11.5h-13z", "M8 6.5v3", "M8 11.5v.1"],
    demande_humaine: ["M8 3.2a1.8 1.8 0 100 3.6 1.8 1.8 0 000-3.6z", "M3.5 13c.4-2.6 2.2-4 4.5-4s4.1 1.4 4.5 4"],
    pause: ["M5 3v10", "M11 3v10"],
    reprise: ["M5 3l8 5-8 5z"],
    arret: ["M4 4h8v8H4z"],
    replier: ["M6 3l5 5-5 5"],
    bas: ["M3 6l5 5 5-5"]
  };
  var RE_SENSIBLE = /pass(word|wd)|pwd|mot.?de.?passe|mdp|identifiant|login|user.?name|passeport|passport|otp|secret|token|iban|card|carte|cvv|e-?mail|courriel|naissance|birth|phone|telephone|^nom$|prenom|first.?name|last.?name/i;

  var messages = [];
  var etat = "inactif";
  var replie = false;
  var nonLus = 0;
  var nonVus = 0;
  var racine = null;
  var ui = {};
  var minuteurs = new WeakMap();
  var minuteurCurseur = null;
  var minuteurHalo = null;
  var animationCurseur = null;
  var curseurPlace = false;
  var curX = 0;
  var curY = 0;
  var colle = true;
  var defilementAutoJusqua = 0;
  var cibleHalo = null;
  var dernierRectHalo = "";
  var nbMessagesAffiches = 0;

  function reduit() {
    try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) { return false; }
  }
  function noeud(balise, classe, texte) {
    var n = document.createElement(balise);
    if (classe) n.className = classe;
    if (texte !== undefined && texte !== null) n.textContent = texte;
    return n;
  }
  function icone(nom, taille) {
    var s = document.createElementNS(NS_SVG, "svg");
    s.setAttribute("viewBox", "0 0 16 16");
    s.setAttribute("width", String(taille || 14));
    s.setAttribute("height", String(taille || 14));
    s.setAttribute("aria-hidden", "true");
    s.setAttribute("focusable", "false");
    s.setAttribute("class", "ico");
    (ICONES[nom] || []).forEach(function (d) {
      var p = document.createElementNS(NS_SVG, "path");
      p.setAttribute("d", d);
      s.appendChild(p);
    });
    return s;
  }
  function heure(d) {
    var h = d.getHours(), m = d.getMinutes();
    return (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m;
  }

  var STYLE = [
    ":host{all:initial;position:fixed;inset:0;z-index:2147483647;pointer-events:none;",
    "--fond:#ffffff;--surface:#f6f6ff;--surface2:#eceafd;--texte:#1e1b4b;--doux:#4b4a6b;--bord:#d4d6f3;--accent:#4f46e5;--sur-accent:#ffffff;",
    "--accent-doux:#e8e6ff;--alerte-fond:#fff4e0;--alerte-texte:#7a3e00;--alerte-bord:#f0c27a;--crit:#b91c1c;--crit-fond:#fdecec;",
    "--bon:#16a34a;--pause:#d97706;--ombre:0 12px 36px rgba(30,27,75,.22),0 2px 6px rgba(30,27,75,.10);",
    "--sortie:cubic-bezier(.2,.7,.2,1);",
    "font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;font-size:14px;line-height:1.45;color:var(--texte)}",
    "@media (prefers-color-scheme:dark){:host{--fond:#16152e;--surface:#1f1d3f;--surface2:#2a2760;--texte:#eceaff;--doux:#b9b7de;--bord:#3b3a6e;",
    "--accent:#8b87ff;--sur-accent:#14123a;--accent-doux:#2a2760;--alerte-fond:#3a2a10;--alerte-texte:#ffd8a0;--alerte-bord:#6b4a1a;",
    "--crit:#ff9a9a;--crit-fond:#3a1620;--bon:#4ade80;--pause:#fbbf24;--ombre:0 12px 36px rgba(0,0,0,.5),0 2px 6px rgba(0,0,0,.3)}}",
    "*{box-sizing:border-box}",
    ".ico{flex:none;fill:none;stroke:currentColor;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}",
    /* panneau : glisse depuis la droite ; replié = invisible et sans aucune prise sur les clics du portail */
    ".panneau{pointer-events:auto;position:absolute;top:0;right:0;bottom:0;width:min(360px,100vw);display:flex;flex-direction:column;",
    "background:var(--fond);border-left:1px solid var(--bord);box-shadow:var(--ombre);color:var(--texte);",
    "visibility:visible;transform:none;opacity:1;transition:transform 200ms var(--sortie),opacity 200ms var(--sortie),visibility 0s}",
    ".panneau.replie{visibility:hidden;pointer-events:none;transform:translateX(24px);opacity:0;",
    "transition:transform 200ms var(--sortie),opacity 150ms ease,visibility 0s linear 200ms}",
    ".entete{display:flex;align-items:center;gap:8px;padding:10px 12px;border-bottom:1px solid var(--bord);background:var(--surface)}",
    ".titre{margin:0;font-weight:700;font-size:15px;letter-spacing:-.01em}",
    ".espace{flex:1}",
    ".pastille{position:relative;display:inline-flex;align-items:center;gap:7px;padding:2px 10px 2px 8px;border-radius:999px;border:1px solid var(--bord);background:var(--fond);font-size:12px;color:var(--doux)}",
    ".point{position:relative;width:9px;height:9px;border-radius:50%;background:var(--doux);transition:background-color 200ms ease}",
    ".point::after{content:'';position:absolute;inset:0;border-radius:50%;background:inherit;opacity:0}",
    ".etat-travaille .point,.pilule.etat-travaille .point{background:var(--bon)}",
    ".etat-travaille .point::after{animation:vie 1800ms ease-out infinite}",
    ".etat-pause .point{background:var(--pause)}",
    ".etat-attente_humain .point{background:var(--crit)}.etat-attente_humain .point::after{animation:vie 2400ms ease-out infinite}",
    ".etat-arret .point,.etat-arrete .point{background:#6b7280}.etat-termine .point{background:var(--accent)}",
    "@keyframes vie{0%{transform:scale(1);opacity:.55}80%,100%{transform:scale(2.6);opacity:0}}",
    "button{font:inherit;color:inherit;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;gap:6px;min-height:32px;padding:4px 12px;",
    "border-radius:8px;border:1px solid var(--bord);background:var(--fond);",
    "transition:background-color 150ms ease,border-color 150ms ease,transform 100ms ease,opacity 150ms ease}",
    "button:hover:not(:disabled){background:var(--accent-doux)}button:active:not(:disabled){transform:scale(.97)}",
    "button:disabled{opacity:.45;cursor:not-allowed}",
    "button.primaire,button.accent:not(:disabled){background:var(--accent);color:var(--sur-accent);border-color:var(--accent);font-weight:600}",
    "button.primaire:hover:not(:disabled),button.accent:hover:not(:disabled){background:var(--accent);filter:brightness(1.08)}",
    "button.danger:not(:disabled){color:var(--crit);border-color:var(--crit)}",
    "button.danger:hover:not(:disabled){background:var(--crit-fond)}",
    "button.discret{border-color:transparent;background:transparent;color:var(--doux)}",
    "button:focus-visible,textarea:focus-visible,.fil:focus-visible{outline:3px solid var(--accent);outline-offset:2px}",
    ".commandes{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;padding:8px 12px;border-bottom:1px solid var(--bord)}",
    ".zone-fil{position:relative;flex:1;min-height:0;display:flex}",
    ".fil{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:10px;overscroll-behavior:contain}",
    /* bulles typées */
    ".msg{position:relative;max-width:92%;padding:8px 12px 9px;border-radius:14px 14px 14px 4px;background:var(--surface);border:1px solid var(--bord);overflow-wrap:anywhere}",
    ".msg.entree{animation:entree 200ms var(--sortie) both}",
    "@keyframes entree{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}",
    ".tete{display:flex;align-items:center;gap:6px;margin:0 0 2px;font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--doux)}",
    ".tete .etiquette{flex:1}.tete .heure{font-weight:500;letter-spacing:0;text-transform:none;font-variant-numeric:tabular-nums}",
    ".msg .texte{display:block}",
    ".msg.t-agent{align-self:flex-start}",
    ".msg.t-action{align-self:stretch;max-width:100%;border:0;border-left:3px solid var(--accent);border-radius:4px 10px 10px 4px;background:transparent;padding:3px 10px;color:var(--doux);font-size:13px}",
    ".msg.t-action .tete{color:var(--accent)}",
    ".msg.t-utilisateur{align-self:flex-end;border-radius:14px 14px 4px 14px;background:var(--accent);color:var(--sur-accent);border-color:var(--accent)}",
    ".msg.t-utilisateur .tete{color:inherit;opacity:.85}",
    ".msg.t-alerte{align-self:stretch;max-width:100%;border-radius:10px;background:var(--alerte-fond);color:var(--alerte-texte);border-color:var(--alerte-bord);border-left:4px solid var(--alerte-texte)}",
    ".msg.t-alerte .tete{color:inherit}",
    ".msg.t-demande_humaine{align-self:stretch;max-width:100%;border-radius:12px;background:var(--accent-doux);border:2px solid var(--accent);font-weight:600}",
    ".msg.t-demande_humaine .tete{color:var(--accent)}",
    ".msg.t-demande_humaine.entree::after{content:'';position:absolute;inset:-2px;border-radius:inherit;border:2px solid var(--accent);pointer-events:none;animation:anneau 480ms ease-out both}",
    "@keyframes anneau{from{opacity:.7;transform:scale(1)}to{opacity:0;transform:scale(1.04)}}",
    /* indicateur « l'agent agit » */
    ".ecrit{align-self:flex-start;display:none;align-items:center;gap:4px;padding:7px 11px;border-radius:12px 12px 12px 4px;background:var(--surface);border:1px solid var(--bord)}",
    ".ecrit.visible{display:inline-flex}",
    ".ecrit i{width:5px;height:5px;border-radius:50%;background:var(--doux);opacity:.55;animation:saut 1200ms ease-in-out infinite}",
    ".ecrit i:nth-child(2){animation-delay:150ms}.ecrit i:nth-child(3){animation-delay:300ms}",
    "@keyframes saut{0%,60%,100%{transform:none;opacity:.4}30%{transform:translateY(-3px);opacity:1}}",
    ".nouveaux{position:absolute;left:50%;bottom:10px;transform:translateX(-50%);visibility:hidden;opacity:0;box-shadow:var(--ombre);",
    "background:var(--accent);color:var(--sur-accent);border-color:var(--accent);font-weight:600;border-radius:999px;min-height:30px;font-size:12px;",
    "transition:opacity 150ms ease,visibility 0s linear 150ms,transform 100ms ease}",
    ".nouveaux.visible{visibility:visible;opacity:1;transition:opacity 150ms ease,visibility 0s}",
    ".nouveaux:hover:not(:disabled){background:var(--accent);filter:brightness(1.08)}.nouveaux:active:not(:disabled){transform:translateX(-50%) scale(.97)}",
    ".saisie{display:flex;gap:8px;padding:10px 12px 4px;border-top:1px solid var(--bord);align-items:flex-end}",
    "textarea{flex:1;min-height:40px;max-height:120px;resize:none;font:inherit;padding:7px 9px;color:var(--texte);background:var(--fond);border:1px solid var(--bord);border-radius:10px}",
    ".note{margin:0;padding:0 12px 10px;font-size:11px;color:var(--doux)}",
    /* repli : pastille flottante */
    ".pilule{pointer-events:auto;position:absolute;right:12px;bottom:12px;display:inline-flex;align-items:center;gap:8px;padding:8px 14px;border-radius:999px;",
    "background:var(--accent);color:var(--sur-accent);border:0;font-weight:600;box-shadow:var(--ombre);visibility:hidden;opacity:0;transform:translateY(6px) scale(.96);",
    "transition:opacity 150ms ease,transform 200ms var(--sortie),visibility 0s linear 200ms}",
    ".pilule.visible{visibility:visible;opacity:1;transform:none;transition:opacity 150ms ease,transform 200ms var(--sortie),visibility 0s}",
    ".pilule:hover:not(:disabled){background:var(--accent);filter:brightness(1.08)}",
    ".pilule:not(.visible){pointer-events:none}",
    ".pilule .point{background:var(--sur-accent);opacity:.9}.pilule.etat-travaille .point{background:var(--bon)}",
    ".pilule.etat-pause .point{background:var(--pause)}.pilule.etat-attente_humain .point{background:var(--crit)}",
    ".badge{min-width:18px;padding:0 5px;border-radius:999px;background:#dc2626;color:#fff;font-size:12px;text-align:center}",
    ".badge.cache{display:none}",
    /* curseur et halo de l'agent : jamais de prise sur la souris, uniquement transform / opacity */
    ".curseur{position:fixed;left:0;top:0;pointer-events:none;opacity:0;transition:opacity 150ms ease;will-change:transform;filter:drop-shadow(0 2px 3px rgba(0,0,0,.35))}",
    ".curseur.visible{opacity:1}",
    ".curseur .tag{position:absolute;left:20px;top:20px;padding:1px 8px;border-radius:999px;background:var(--accent);color:var(--sur-accent);font-size:11px;font-weight:600;white-space:nowrap;box-shadow:0 1px 3px rgba(0,0,0,.3)}",
    ".halo{position:fixed;left:0;top:0;pointer-events:none;opacity:0;border-radius:8px;will-change:transform;",
    "box-shadow:0 0 0 5px color-mix(in srgb,var(--accent) 22%,transparent),0 0 22px 2px color-mix(in srgb,var(--accent) 38%,transparent);transition:opacity 300ms ease}",
    ".halo.visible{opacity:1;transition:opacity 150ms ease}",
    ".halo::after{content:'';position:absolute;inset:-2px;border-radius:inherit;border:2px solid var(--accent);opacity:0}",
    ".halo.ping::after{animation:ping 450ms ease-out both}",
    "@keyframes ping{from{opacity:.6;transform:scale(1)}to{opacity:0;transform:scale(1.12)}}",
    ".sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}",
    "@media (prefers-reduced-motion:reduce){*,*::before,*::after{transition:none !important;animation:none !important;scroll-behavior:auto !important}}",
    "@media (max-width:480px){.panneau{width:100vw}}"
  ].join("");

  function appeler(nom, argument) {
    var f = window[nom];
    if (typeof f !== "function") return Promise.reject(new Error("pont indisponible"));
    return Promise.resolve(f(argument));
  }

  function rendreMessage(m, anime) {
    var type = LIBELLES[m.type] ? m.type : "agent";
    var el = noeud("div", "msg t-" + m.type + (anime && !reduit() ? " entree" : ""));
    if (m.type === "alerte" || m.type === "demande_humaine") el.setAttribute("role", "alert");
    var tete = noeud("div", "tete");
    if (ICONES[type]) tete.appendChild(icone(type, 12));
    tete.appendChild(noeud("span", "etiquette", LIBELLES[m.type] || "Agent"));
    tete.appendChild(noeud("span", "heure", heure(new Date(m.t))));
    el.appendChild(tete);
    el.appendChild(noeud("span", "texte", m.texte));
    return el;
  }

  function majBadge() {
    if (!ui.badge) return;
    ui.badge.textContent = String(nonLus);
    ui.badge.className = "badge" + (nonLus > 0 ? "" : " cache");
  }

  function majNouveaux() {
    if (!ui.nouveaux) return;
    var visible = nonVus > 0 && !colle;
    ui.nouveaux.className = "nouveaux" + (visible ? " visible" : "");
    ui.nouveaux.tabIndex = visible ? 0 : -1;
    ui.nouveauxTexte.textContent = nonVus + (nonVus > 1 ? " nouveaux messages" : " nouveau message");
  }

  function reserverPlace() {
    // Déplié sur un écran large : on réduit la page de la largeur du panneau pour qu'il ne masque (et ne
    // bloque) aucun élément du portail ; replié ou écran étroit : la marge d'origine est rétablie.
    var el = document.documentElement;
    if (!el) return;
    if (!replie && window.innerWidth >= LARGEUR_MIN_ECRAN) {
      if (margeAvant === null) {
        margeAvant = [el.style.getPropertyValue("margin-right"), el.style.getPropertyPriority("margin-right")];
      }
      el.style.setProperty("margin-right", LARGEUR_PANNEAU + "px", "important");
    } else if (margeAvant !== null) {
      el.style.removeProperty("margin-right");
      if (margeAvant[0]) el.style.setProperty("margin-right", margeAvant[0], margeAvant[1]);
      margeAvant = null;
    }
  }

  function definirReplie(valeur, focaliser) {
    replie = !!valeur;
    reserverPlace();
    if (!ui.panneau) return;
    ui.panneau.className = "panneau" + (replie ? " replie" : "");
    ui.pilule.className = "pilule etat-" + etat + (replie ? " visible" : "");
    ui.bascule.setAttribute("aria-expanded", replie ? "false" : "true");
    ui.pilule.setAttribute("aria-expanded", replie ? "false" : "true");
    if (!replie) {
      nonLus = 0;
      majBadge();
      if (focaliser) ui.saisie.focus();
    } else if (focaliser) {
      ui.pilule.focus();
    }
  }

  function majEtat() {
    if (!ui.pastille) return;
    ui.pastille.className = "pastille etat-" + etat;
    ui.pilule.className = "pilule etat-" + etat + (replie ? " visible" : "");
    ui.etatTexte.textContent = ETATS[etat] || etat;
    ui.btnPause.disabled = !(etat === "travaille" || etat === "attente_humain");
    ui.btnReprise.disabled = etat !== "pause";
    ui.btnArret.disabled = !(etat === "travaille" || etat === "pause" || etat === "attente_humain");
    placerIndicateur();
  }

  function placerIndicateur() {
    if (!ui.ecrit) return;
    var actif = etat === "travaille";
    ui.ecrit.className = "ecrit" + (actif ? " visible" : "");
    if (actif) ui.fil.appendChild(ui.ecrit);
  }

  function pres() {
    return ui.fil.scrollHeight - ui.fil.scrollTop - ui.fil.clientHeight < SEUIL_BAS_PX;
  }

  function descendre(doux) {
    if (!ui.fil) return;
    defilementAutoJusqua = Date.now() + 450;
    colle = true;
    nonVus = 0;
    majNouveaux();
    try {
      ui.fil.scrollTo({ top: ui.fil.scrollHeight, behavior: doux && !reduit() ? "smooth" : "auto" });
    } catch (e) { ui.fil.scrollTop = ui.fil.scrollHeight; }
  }

  function surDefilement() {
    if (Date.now() < defilementAutoJusqua) { defilementAutoJusqua = Date.now() + 150; return; }  // défilement animé en cours
    colle = pres();
    if (colle) { nonVus = 0; }
    majNouveaux();
  }

  function monter() {
    if (racine || !document.documentElement) return;
    var hote = document.createElement("div");
    hote.id = "agent-panneau-hote";
    // Racine FERMÉE : les sélecteurs Playwright de l'agent (textarea, button, texte…) ne traversent pas un
    // shadow root fermé, donc le panneau ne peut jamais être pris pour un champ du portail. Les tests
    // posent `window.__AGENT_PANNEAU_OUVERT__ = true` pour l'inspecter.
    racine = hote.attachShadow({ mode: window.__AGENT_PANNEAU_OUVERT__ === true ? "open" : "closed" });
    var style = document.createElement("style");
    style.textContent = STYLE;
    racine.appendChild(style);

    var panneau = noeud("section", "panneau");
    panneau.setAttribute("aria-label", "Discussion avec l'agent");
    panneau.id = "panneau";
    var entete = noeud("div", "entete");
    entete.appendChild(noeud("h2", "titre", "Agent"));
    var pastille = noeud("span", "pastille");
    pastille.setAttribute("role", "status");
    pastille.appendChild(noeud("span", "point"));
    var etatTexte = noeud("span", "", "");
    pastille.appendChild(etatTexte);
    entete.appendChild(pastille);
    entete.appendChild(noeud("span", "espace"));
    var bascule = noeud("button", "discret", "");
    bascule.appendChild(document.createTextNode("Replier"));
    bascule.appendChild(icone("replier", 14));
    bascule.type = "button";
    bascule.setAttribute("aria-controls", "panneau");
    bascule.setAttribute("aria-expanded", "true");
    bascule.addEventListener("click", function () { definirReplie(true, true); });
    entete.appendChild(bascule);
    panneau.appendChild(entete);

    var commandes = noeud("div", "commandes");
    commandes.setAttribute("role", "group");
    commandes.setAttribute("aria-label", "Commandes de l'agent");
    function boutonCommande(libelle, nomIcone, classe) {
      var b = noeud("button", classe || "", "");
      b.type = "button";
      b.appendChild(icone(nomIcone, 14));
      b.appendChild(document.createTextNode(libelle));
      commandes.appendChild(b);
      return b;
    }
    var btnPause = boutonCommande("Pause", "pause", "");
    var btnReprise = boutonCommande("Reprendre", "reprise", "accent");
    var btnArret = boutonCommande("Arrêter", "arret", "danger");
    btnPause.addEventListener("click", function () { commande("pause", "pause"); });
    btnReprise.addEventListener("click", function () { commande("reprise", "travaille"); });
    btnArret.addEventListener("click", function () { commande("arret", "arrete"); });
    panneau.appendChild(commandes);

    var zoneFil = noeud("div", "zone-fil");
    var fil = noeud("div", "fil");
    fil.setAttribute("role", "log");
    fil.setAttribute("aria-live", "polite");
    fil.setAttribute("aria-relevant", "additions");
    fil.setAttribute("aria-label", "Messages de l'agent");
    fil.tabIndex = 0;
    fil.addEventListener("scroll", surDefilement);
    fil.addEventListener("wheel", function (ev) {
      if (ev.deltaY < 0) { defilementAutoJusqua = 0; colle = false; }
    }, { passive: true });
    var ecrit = noeud("div", "ecrit");
    ecrit.setAttribute("aria-hidden", "true");
    ecrit.appendChild(noeud("i"));
    ecrit.appendChild(noeud("i"));
    ecrit.appendChild(noeud("i"));
    fil.appendChild(ecrit);
    zoneFil.appendChild(fil);
    var nouveaux = noeud("button", "nouveaux", "");
    nouveaux.type = "button";
    nouveaux.tabIndex = -1;
    var nouveauxTexte = noeud("span", "", "");
    nouveaux.appendChild(nouveauxTexte);
    nouveaux.appendChild(icone("bas", 12));
    nouveaux.addEventListener("click", function () { descendre(true); });
    zoneFil.appendChild(nouveaux);
    panneau.appendChild(zoneFil);

    var zone = noeud("div", "saisie");
    var saisie = document.createElement("textarea");
    saisie.rows = 2;
    saisie.maxLength = MAX_SAISIE;
    saisie.placeholder = "Écrire à l'agent (Entrée pour envoyer)";
    saisie.setAttribute("aria-label", "Écrire à l'agent");
    saisie.setAttribute("aria-describedby", "note-agent");
    var envoyer = noeud("button", "primaire", "Envoyer");
    envoyer.type = "button";
    zone.appendChild(saisie);
    zone.appendChild(envoyer);
    panneau.appendChild(zone);
    var note = noeud("p", "note", "L'agent ne valide et n'envoie rien à votre place.");
    note.id = "note-agent";
    panneau.appendChild(note);
    function soumettre() { var t = saisie.value; saisie.value = ""; envoyerMessage(t); }
    envoyer.addEventListener("click", soumettre);
    saisie.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); soumettre(); }
    });
    panneau.addEventListener("keydown", function (ev) { if (ev.key === "Escape") definirReplie(true, true); });

    var pilule = noeud("button", "pilule", "");
    pilule.type = "button";
    pilule.setAttribute("aria-controls", "panneau");
    pilule.setAttribute("aria-expanded", "false");
    pilule.setAttribute("aria-label", "Ouvrir la discussion avec l'agent");
    pilule.appendChild(noeud("span", "point"));
    pilule.appendChild(noeud("span", "", "Agent"));
    var badge = noeud("span", "badge cache", "0");
    pilule.appendChild(badge);
    pilule.addEventListener("click", function () { definirReplie(false, true); });

    var curseur = noeud("div", "curseur");
    curseur.setAttribute("aria-hidden", "true");
    var svg = document.createElementNS(NS_SVG, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("width", "22");
    svg.setAttribute("height", "22");
    var chemin = document.createElementNS(NS_SVG, "path");
    chemin.setAttribute("d", "M3 2 L3 19 L8 14.5 L11.5 22 L14.5 20.7 L11 13.3 L18 13 Z");
    chemin.setAttribute("fill", "#4f46e5");
    chemin.setAttribute("stroke", "#ffffff");
    chemin.setAttribute("stroke-width", "1.5");
    svg.appendChild(chemin);
    curseur.appendChild(svg);
    curseur.appendChild(noeud("span", "tag", "Agent"));

    var halo = noeud("div", "halo");
    halo.setAttribute("aria-hidden", "true");

    racine.appendChild(panneau);
    racine.appendChild(pilule);
    racine.appendChild(halo);
    racine.appendChild(curseur);
    ui = { panneau: panneau, fil: fil, saisie: saisie, pastille: pastille, etatTexte: etatTexte, bascule: bascule,
           pilule: pilule, badge: badge, curseur: curseur, halo: halo, ecrit: ecrit, nouveaux: nouveaux,
           nouveauxTexte: nouveauxTexte, btnPause: btnPause, btnReprise: btnReprise, btnArret: btnArret };
    document.documentElement.appendChild(hote);
    messages.forEach(function (m) { insererMessage(rendreMessage(m, false)); });
    descendre(false);
    majEtat();
    majNouveaux();
    window.addEventListener("resize", reserverPlace);
    definirReplie(replie, false);
  }

  function insererMessage(el) {
    ui.fil.insertBefore(el, ui.ecrit);
    nbMessagesAffiches += 1;
    while (nbMessagesAffiches > MAX_MESSAGES && ui.fil.firstChild && ui.fil.firstChild !== ui.ecrit) {
      ui.fil.removeChild(ui.fil.firstChild);
      nbMessagesAffiches -= 1;
    }
  }

  function ajouter(type, texte) {
    var m = { type: String(type), texte: String(texte), t: Date.now() };
    messages.push(m);
    while (messages.length > MAX_MESSAGES) messages.shift();
    if (ui.fil) {
      // Auto-défilement qui ne vole pas la lecture : on ne suit le fil que si l'utilisateur est déjà en bas
      // (ou s'il vient d'écrire, ou si l'agent a besoin de lui) ; sinon on propose « nouveaux messages ».
      var suivre = colle || pres();
      insererMessage(rendreMessage(m, true));
      placerIndicateur();
      if (suivre || m.type === "utilisateur" || m.type === "demande_humaine") descendre(true);
      else { nonVus += 1; majNouveaux(); }
    }
    if (replie && m.type !== "utilisateur") {
      nonLus += 1;
      majBadge();
      if (m.type === "alerte" || m.type === "demande_humaine") definirReplie(false, false);
    }
  }

  function envoyerMessage(texte) {
    var t = String(texte || "").trim().slice(0, MAX_SAISIE);
    if (!t) return;
    ajouter("utilisateur", t);
    appeler("agent_envoyer_message", t).catch(function () {
      ajouter("alerte", "Votre message n'a pas pu être transmis à l'agent.");
    });
  }

  function commande(code, nouvelEtat) {
    appeler("agent_commande", code).then(function () {
      definirEtat(nouvelEtat);
    }).catch(function () {
      ajouter("alerte", "La commande n'a pas pu être transmise à l'agent.");
    });
  }

  function definirEtat(e) {
    if (!ETATS[e]) return;
    etat = e;
    majEtat();
  }

  function estSensible(el) {
    if (!el || !el.getAttribute) return false;
    var type = (el.getAttribute("type") || "").toLowerCase();
    if (type === "password" || type === "email" || type === "tel") return true;
    var attrs = ["name", "id", "autocomplete", "aria-label", "placeholder"];
    for (var i = 0; i < attrs.length; i++) {
      var v = el.getAttribute(attrs[i]);
      if (v && RE_SENSIBLE.test(v)) return true;
    }
    return false;
  }

  function surlignerElement(el) {
    var ancien = minuteurs.get(el);
    var valeurs = ancien ? ancien.valeurs : {
      outline: [el.style.getPropertyValue("outline"), el.style.getPropertyPriority("outline")],
      offset: [el.style.getPropertyValue("outline-offset"), el.style.getPropertyPriority("outline-offset")]
    };
    if (ancien) clearTimeout(ancien.id);
    el.style.setProperty("outline", "2px solid #4f46e5", "important");
    el.style.setProperty("outline-offset", "2px", "important");
    var id = setTimeout(function () {
      el.style.removeProperty("outline");
      el.style.removeProperty("outline-offset");
      if (valeurs.outline[0]) el.style.setProperty("outline", valeurs.outline[0], valeurs.outline[1]);
      if (valeurs.offset[0]) el.style.setProperty("outline-offset", valeurs.offset[0], valeurs.offset[1]);
      minuteurs.delete(el);
    }, DUREE_SURLIGNAGE_MS);
    minuteurs.set(el, { id: id, valeurs: valeurs });
  }

  function poserHalo() {
    if (!cibleHalo || !ui.halo) return;
    var r = cibleHalo.getBoundingClientRect();
    var cle = Math.round(r.left) + "," + Math.round(r.top) + "," + Math.round(r.width) + "," + Math.round(r.height);
    if (cle !== dernierRectHalo) {
      dernierRectHalo = cle;
      var h = ui.halo;
      h.style.width = Math.round(r.width + 4) + "px";
      h.style.height = Math.round(r.height + 4) + "px";
      h.style.transform = "translate(" + Math.round(r.left - 2) + "px," + Math.round(r.top - 2) + "px)";
    }
    window.requestAnimationFrame(poserHalo);
  }

  function montrerHalo(el) {
    var h = ui.halo;
    if (!h) return;
    var rayon = "8px";
    try {
      var br = window.getComputedStyle(el).borderRadius;
      if (br && br !== "0px") rayon = br;
    } catch (e) { }
    h.style.borderRadius = rayon;
    var etaitActif = !!cibleHalo;
    cibleHalo = el;
    dernierRectHalo = "";
    if (!etaitActif) poserHalo();
    h.className = "halo visible";
    if (!reduit()) {
      void h.offsetWidth;
      h.className = "halo visible ping";
    }
    if (minuteurHalo) clearTimeout(minuteurHalo);
    minuteurHalo = setTimeout(function () {
      cibleHalo = null;
      h.className = "halo";
    }, DUREE_SURLIGNAGE_MS);
  }

  function trajectoire(x0, y0, x1, y1) {
    // Courbe de Bézier quadratique courte (arc léger, côté perpendiculaire), échantillonnée en 8 pas avec
    // décélération en fin de course : le curseur « glisse » au lieu de se téléporter en ligne droite.
    var dx = x1 - x0, dy = y1 - y0;
    var d = Math.sqrt(dx * dx + dy * dy) || 1;
    var arc = Math.min(48, d * 0.2);
    var cx = (x0 + x1) / 2 + (-dy / d) * arc;
    var cy = (y0 + y1) / 2 + (dx / d) * arc;
    var pas = 8, pts = [];
    for (var i = 0; i <= pas; i++) {
      var s = i / pas;
      var t = 1 - Math.pow(1 - s, 3);
      var u = 1 - t;
      var x = u * u * x0 + 2 * u * t * cx + t * t * x1;
      var y = u * u * y0 + 2 * u * t * cy + t * t * y1;
      pts.push({ transform: "translate(" + x.toFixed(1) + "px," + y.toFixed(1) + "px)", offset: s });
    }
    return { pts: pts, duree: Math.round(Math.min(DUREE_MAX_TRAJET_MS, 160 + d * 0.35)) };
  }

  function deplacerCurseur(el) {
    if (!ui.curseur) return;
    var r = el.getBoundingClientRect();
    var x = Math.max(0, Math.min(window.innerWidth - 26, r.left + Math.min(r.width / 2, 40)));
    var y = Math.max(0, Math.min(window.innerHeight - 26, r.top + r.height / 2));
    x = Math.round(x);
    y = Math.round(y);
    var c = ui.curseur;
    if (animationCurseur) { try { animationCurseur.cancel(); } catch (e) { } animationCurseur = null; }
    var anime = curseurPlace && !reduit() && typeof c.animate === "function";
    if (anime) {
      var t = trajectoire(curX, curY, x, y);
      c.style.transform = "translate(" + x + "px," + y + "px)";
      animationCurseur = c.animate(t.pts, { duration: t.duree, easing: "linear" });
    } else {
      c.style.transform = "translate(" + x + "px," + y + "px)";
    }
    curX = x;
    curY = y;
    curseurPlace = true;
    c.className = "curseur visible";
    if (minuteurCurseur) clearTimeout(minuteurCurseur);
    minuteurCurseur = setTimeout(function () { c.className = "curseur"; }, DUREE_CURSEUR_MS);
  }

  function dansLaFenetre(el) {
    var r = el.getBoundingClientRect();
    return r.top >= 0 && r.bottom <= window.innerHeight && r.left >= 0 && r.right <= window.innerWidth;
  }

  function surligner(cible) {
    var el = null;
    try {
      el = typeof cible === "string" ? document.querySelector(cible) : cible;
    } catch (e) { el = null; }
    if (!el || !el.getBoundingClientRect) return { trouve: false, sensible: false };
    // Défilement uniquement si l'élément est hors champ, et instantané : les coordonnées du curseur et du halo
    // restent exactes et la page du portail n'est pas animée à sa place.
    try { if (!dansLaFenetre(el)) el.scrollIntoView({ block: "center", inline: "nearest", behavior: "auto" }); } catch (e) { }
    surlignerElement(el);
    montrerHalo(el);
    deplacerCurseur(el);
    return { trouve: true, sensible: estSensible(el) };
  }

  function restaurer(liste, etatInitial) {
    messages = [];
    (liste || []).slice(-MAX_MESSAGES).forEach(function (m) {
      messages.push({ type: String(m.type), texte: String(m.texte), t: Number(m.t) || Date.now() });
    });
    if (ui.fil) {
      while (ui.fil.firstChild) ui.fil.removeChild(ui.fil.firstChild);
      ui.fil.appendChild(ui.ecrit);
      nbMessagesAffiches = 0;
      messages.forEach(function (m) { insererMessage(rendreMessage(m, false)); });
      descendre(false);
    }
    if (etatInitial) definirEtat(etatInitial);
  }

  window.__agentPanneau = {
    ajouter: ajouter, definirEtat: definirEtat, surligner: surligner, restaurer: restaurer,
    replier: definirReplie, estSensible: estSensible,
    etat: function () { return etat; }, nombreMessages: function () { return messages.length; }
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", monter);
  else monter();
  if (!racine) document.addEventListener("DOMContentLoaded", monter);
})();
"""


class PontPanneau:
    """Pont entre une page (ou un contexte) Playwright et un `JournalAgent`.

    Un pont par contexte (voir `pont_pour`) : les fonctions exposées ne peuvent être enregistrées qu'une
    fois. Le journal courant (`lier`) change à chaque tâche.
    """

    def __init__(self, cible: Any, page: Any) -> None:
        self._cible = cible
        self._page = page
        self._recepteur: Any = None
        self._historique: list[dict[str, Any]] = []
        self._etat = "inactif"
        self._a_restaurer = False
        self._installe = False

    # ------------------------------------------------------------------ installation
    def installer(self) -> None:
        if self._installe:
            return
        self._cible.expose_function(NOM_PONT_MESSAGE, self._recevoir_message)
        self._cible.expose_function(NOM_PONT_COMMANDE, self._recevoir_commande)
        self._cible.add_init_script(JS_PANNEAU_DISCUSSION)
        self._page.on("domcontentloaded", self._marquer_a_restaurer)
        self._installe = True
        self._injecter_dans_page_courante()

    def _injecter_dans_page_courante(self) -> None:
        try:
            self._page.evaluate(JS_PANNEAU_DISCUSSION)
            self._restaurer()
        except Exception as exc:
            journal.info("Panneau non injecté dans la page courante : %s", type(exc).__name__)

    def lier(self, recepteur: Any) -> None:
        self._recepteur = recepteur

    # ------------------------------------------------------------------ callbacks de la page
    def _recevoir_message(self, texte: Any) -> None:
        if self._recepteur is not None and isinstance(texte, str):
            self._recepteur.sur_message_panneau(texte[:1000])

    def _recevoir_commande(self, code: Any) -> None:
        if self._recepteur is not None and isinstance(code, str):
            self._recepteur.sur_commande_panneau(code)

    def _marquer_a_restaurer(self, *_: Any) -> None:
        self._a_restaurer = True

    # ------------------------------------------------------------------ vers la page
    def _restaurer(self) -> None:
        self._a_restaurer = False
        self._page.evaluate(
            "([liste, etat]) => window.__agentPanneau && window.__agentPanneau.restaurer(liste, etat)",
            [self._historique[-NB_MESSAGES_REJOUES:], self._etat],
        )

    def _synchroniser(self) -> None:
        if self._a_restaurer:
            try:
                self._restaurer()
            except Exception as exc:
                journal.info("Panneau non restauré : %s", type(exc).__name__)

    def ajouter(self, type_: str, texte: str) -> None:
        """Ajoute un message au fil (le texte doit déjà être masqué par l'appelant)."""
        if type_ not in TYPES_MESSAGE:
            raise ValueError(f"type de message inconnu : {type_}")
        self._synchroniser()  # d'abord rejouer l'historique après une navigation, puis ajouter le nouveau
        self._historique.append({"type": type_, "texte": texte, "t": int(time.time() * 1000)})
        del self._historique[:-NB_MESSAGES_REJOUES]
        try:
            self._page.evaluate(
                "([t, x]) => window.__agentPanneau && window.__agentPanneau.ajouter(t, x)", [type_, texte]
            )
        except Exception as exc:
            journal.info("Message non affiché dans le panneau : %s", type(exc).__name__)

    def definir_etat(self, etat: str) -> None:
        if etat not in ETATS_PANNEAU:
            raise ValueError(f"état inconnu : {etat}")
        self._etat = etat
        self._synchroniser()
        try:
            self._page.evaluate("(e) => window.__agentPanneau && window.__agentPanneau.definirEtat(e)", etat)
        except Exception as exc:
            journal.info("État non affiché dans le panneau : %s", type(exc).__name__)

    def surligner(self, cible: Any, *, delai_ms: int = 1500) -> dict[str, bool]:
        """Surligne l'élément (sélecteur CSS ou `Locator`) et y déplace le curseur de l'agent.
        Ne lit jamais la valeur. Retourne `{trouve, sensible}` ; ne lève jamais."""
        self._synchroniser()
        try:
            if isinstance(cible, str):
                resultat = self._page.evaluate(
                    "(s) => window.__agentPanneau ? window.__agentPanneau.surligner(s) : null", cible
                )
            else:
                resultat = cible.first.evaluate(
                    "(el) => window.__agentPanneau ? window.__agentPanneau.surligner(el) : null",
                    timeout=delai_ms,
                )
        except Exception as exc:
            journal.info("Surlignage impossible : %s", type(exc).__name__)
            return {"trouve": False, "sensible": False}
        if not isinstance(resultat, dict):
            return {"trouve": False, "sensible": False}
        return {"trouve": bool(resultat.get("trouve")), "sensible": bool(resultat.get("sensible"))}

    def attendre(self, duree_ms: int) -> None:
        """Pause qui laisse Playwright traiter les callbacks de la page (messages, boutons)."""
        try:
            self._page.wait_for_timeout(duree_ms)
        except Exception:
            time.sleep(duree_ms / 1000)


_PONTS: WeakKeyDictionary[Any, PontPanneau] = WeakKeyDictionary()


def pont_pour(page: Any, *, fabrique: Callable[[Any, Any], PontPanneau] = PontPanneau) -> PontPanneau:
    """Pont du contexte de `page` (un par contexte ; `page` sert au repli si le contexte est inaccessible)."""
    try:
        cible = page.context
    except Exception:
        cible = page
    pont = _PONTS.get(cible)
    if pont is not None:
        pont._page = page
    else:
        pont = fabrique(cible, page)
        _PONTS[cible] = pont
    return pont
