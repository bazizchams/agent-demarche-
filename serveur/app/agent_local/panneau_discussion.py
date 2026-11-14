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
  var margeAvant = null;
  var LIBELLES = {
    agent: "Agent", action: "Action", alerte: "Alerte",
    demande_humaine: "J'ai besoin de vous", utilisateur: "Vous"
  };
  var ETATS = {
    inactif: "Inactif", travaille: "Au travail", pause: "En pause",
    attente_humain: "Attend votre aide", arrete: "Arrêté", termine: "Terminé"
  };
  var RE_SENSIBLE = /pass(word|wd)|pwd|mot.?de.?passe|mdp|identifiant|login|user.?name|passeport|passport|otp|secret|token|iban|card|carte|cvv|e-?mail|courriel|naissance|birth|phone|telephone|^nom$|prenom|first.?name|last.?name/i;

  var messages = [];
  var etat = "inactif";
  var replie = false;
  var nonLus = 0;
  var racine = null;
  var ui = {};
  var minuteurs = new WeakMap();
  var minuteurCurseur = null;
  var curseurPlace = false;

  function reduit() {
    try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) { return false; }
  }
  function noeud(balise, classe, texte) {
    var n = document.createElement(balise);
    if (classe) n.className = classe;
    if (texte !== undefined && texte !== null) n.textContent = texte;
    return n;
  }
  function heure(d) {
    var h = d.getHours(), m = d.getMinutes();
    return (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m;
  }

  var STYLE = [
    ":host{all:initial;position:fixed;inset:0;z-index:2147483647;pointer-events:none;",
    "--fond:#ffffff;--surface:#f5f5ff;--texte:#1e1b4b;--doux:#4b4a6b;--bord:#c7c9f0;--accent:#4f46e5;--sur-accent:#ffffff;",
    "--alerte-fond:#fff4e0;--alerte-texte:#7a3e00;--aide-fond:#e8e6ff;--ombre:0 8px 30px rgba(30,27,75,.25);",
    "font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;font-size:14px;line-height:1.45;color:var(--texte)}",
    "@media (prefers-color-scheme:dark){:host{--fond:#16152e;--surface:#1f1d3f;--texte:#eceaff;--doux:#b9b7de;--bord:#3b3a6e;",
    "--accent:#8b87ff;--sur-accent:#14123a;--alerte-fond:#3a2a10;--alerte-texte:#ffd8a0;--aide-fond:#2a2760}}",
    "*{box-sizing:border-box}",
    ".panneau{pointer-events:auto;position:absolute;top:0;right:0;bottom:0;width:min(360px,100vw);display:flex;flex-direction:column;",
    "background:var(--fond);border-left:1px solid var(--bord);box-shadow:var(--ombre);color:var(--texte);",
    "font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;font-size:14px;line-height:1.45}",
    ".panneau.replie{display:none}",
    ".entete{display:flex;align-items:center;gap:8px;padding:10px 12px;border-bottom:1px solid var(--bord);background:var(--surface)}",
    ".titre{flex:1;font-weight:700;font-size:15px;margin:0}",
    ".pastille{display:inline-flex;align-items:center;gap:6px;padding:2px 10px;border-radius:999px;border:1px solid var(--bord);font-size:12px;color:var(--doux)}",
    ".point{width:9px;height:9px;border-radius:50%;background:var(--doux)}",
    ".etat-travaille .point{background:#16a34a}.etat-pause .point{background:#d97706}",
    ".etat-attente_humain .point{background:#dc2626}.etat-arrete .point{background:#6b7280}.etat-termine .point{background:#4f46e5}",
    "button{font:inherit;color:inherit;cursor:pointer;min-height:32px;padding:4px 12px;border-radius:8px;border:1px solid var(--bord);background:var(--fond)}",
    "button:hover:not(:disabled){background:var(--aide-fond)}button:disabled{opacity:.5;cursor:not-allowed}",
    "button.primaire{background:var(--accent);color:var(--sur-accent);border-color:var(--accent);font-weight:600}",
    "button:focus-visible,textarea:focus-visible{outline:3px solid var(--accent);outline-offset:2px}",
    ".commandes{display:flex;gap:8px;padding:8px 12px;border-bottom:1px solid var(--bord)}",
    ".fil{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:8px;scroll-behavior:smooth}",
    ".msg{padding:8px 10px;border-radius:10px;background:var(--surface);border:1px solid var(--bord);overflow-wrap:anywhere}",
    ".msg .etiquette{display:block;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:var(--doux)}",
    ".msg .heure{float:right;font-size:11px;color:var(--doux)}",
    ".msg.t-action{border-style:dashed}.msg.t-utilisateur{background:var(--accent);color:var(--sur-accent);border-color:var(--accent);margin-left:24px}",
    ".msg.t-utilisateur .etiquette,.msg.t-utilisateur .heure{color:inherit}",
    ".msg.t-alerte{background:var(--alerte-fond);color:var(--alerte-texte);border-color:var(--alerte-texte)}",
    ".msg.t-demande_humaine{background:var(--aide-fond);border:2px solid var(--accent);font-weight:600}",
    ".saisie{display:flex;gap:8px;padding:10px 12px;border-top:1px solid var(--bord);align-items:flex-end}",
    "textarea{flex:1;min-height:40px;max-height:120px;resize:vertical;font:inherit;padding:6px 8px;color:var(--texte);background:var(--fond);border:1px solid var(--bord);border-radius:8px}",
    ".pilule{pointer-events:auto;position:absolute;right:12px;bottom:12px;display:none;align-items:center;gap:8px;padding:8px 14px;border-radius:999px;",
    "background:var(--accent);color:var(--sur-accent);border:0;font-weight:600;box-shadow:var(--ombre)}",
    ".pilule.visible{display:inline-flex}.badge{min-width:18px;padding:0 5px;border-radius:999px;background:#dc2626;color:#fff;font-size:12px;text-align:center}",
    ".badge.cache{display:none}",
    ".curseur{position:fixed;left:0;top:0;width:26px;height:26px;pointer-events:none;opacity:0;transition:transform 550ms ease,opacity 200ms ease;filter:drop-shadow(0 2px 3px rgba(0,0,0,.4))}",
    ".curseur.visible{opacity:1}.curseur.instantane{transition:none}",
    ".sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}",
    "@media (prefers-reduced-motion:reduce){*{transition:none !important;animation:none !important;scroll-behavior:auto !important}}",
    "@media (max-width:480px){.panneau{width:100vw}}"
  ].join("");

  function appeler(nom, argument) {
    var f = window[nom];
    if (typeof f !== "function") return Promise.reject(new Error("pont indisponible"));
    return Promise.resolve(f(argument));
  }

  function rendreMessage(m) {
    var el = noeud("div", "msg t-" + m.type);
    if (m.type === "alerte" || m.type === "demande_humaine") el.setAttribute("role", "alert");
    el.appendChild(noeud("span", "heure", heure(new Date(m.t))));
    el.appendChild(noeud("span", "etiquette", LIBELLES[m.type] || "Agent"));
    el.appendChild(noeud("span", "texte", m.texte));
    return el;
  }

  function majBadge() {
    if (!ui.badge) return;
    ui.badge.textContent = String(nonLus);
    ui.badge.className = "badge" + (nonLus > 0 ? "" : " cache");
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

  function definirReplie(valeur) {
    replie = !!valeur;
    reserverPlace();
    if (!ui.panneau) return;
    ui.panneau.className = "panneau" + (replie ? " replie" : "");
    ui.pilule.className = "pilule" + (replie ? " visible" : "");
    ui.bascule.setAttribute("aria-expanded", replie ? "false" : "true");
    ui.pilule.setAttribute("aria-expanded", replie ? "false" : "true");
    if (!replie) { nonLus = 0; majBadge(); ui.saisie.focus(); }
    else { ui.pilule.focus(); }
  }

  function majEtat() {
    if (!ui.pastille) return;
    ui.pastille.className = "pastille etat-" + etat;
    ui.etatTexte.textContent = ETATS[etat] || etat;
    ui.btnPause.disabled = !(etat === "travaille" || etat === "attente_humain");
    ui.btnReprise.disabled = etat !== "pause";
    ui.btnArret.disabled = !(etat === "travaille" || etat === "pause" || etat === "attente_humain");
  }

  function descendre() {
    if (ui.fil) ui.fil.scrollTop = ui.fil.scrollHeight;
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
    var bascule = noeud("button", "", "Replier");
    bascule.type = "button";
    bascule.setAttribute("aria-controls", "panneau");
    bascule.setAttribute("aria-expanded", "true");
    bascule.addEventListener("click", function () { definirReplie(true); });
    entete.appendChild(bascule);
    panneau.appendChild(entete);

    var commandes = noeud("div", "commandes");
    commandes.setAttribute("role", "group");
    commandes.setAttribute("aria-label", "Commandes de l'agent");
    var btnPause = noeud("button", "", "Pause");
    var btnReprise = noeud("button", "", "Reprendre");
    var btnArret = noeud("button", "", "Arrêter");
    [btnPause, btnReprise, btnArret].forEach(function (b) { b.type = "button"; commandes.appendChild(b); });
    btnPause.addEventListener("click", function () { commande("pause", "pause"); });
    btnReprise.addEventListener("click", function () { commande("reprise", "travaille"); });
    btnArret.addEventListener("click", function () { commande("arret", "arrete"); });
    panneau.appendChild(commandes);

    var fil = noeud("div", "fil");
    fil.setAttribute("role", "log");
    fil.setAttribute("aria-live", "polite");
    fil.setAttribute("aria-relevant", "additions");
    fil.setAttribute("aria-label", "Messages de l'agent");
    fil.tabIndex = 0;
    panneau.appendChild(fil);

    var zone = noeud("div", "saisie");
    var saisie = document.createElement("textarea");
    saisie.rows = 2;
    saisie.maxLength = MAX_SAISIE;
    saisie.placeholder = "Écrire à l'agent (Entrée pour envoyer)";
    saisie.setAttribute("aria-label", "Écrire à l'agent");
    var envoyer = noeud("button", "primaire", "Envoyer");
    envoyer.type = "button";
    zone.appendChild(saisie);
    zone.appendChild(envoyer);
    panneau.appendChild(zone);
    function soumettre() { var t = saisie.value; saisie.value = ""; envoyerMessage(t); }
    envoyer.addEventListener("click", soumettre);
    saisie.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); soumettre(); }
    });
    panneau.addEventListener("keydown", function (ev) { if (ev.key === "Escape") definirReplie(true); });

    var pilule = noeud("button", "pilule", "Agent");
    pilule.type = "button";
    pilule.setAttribute("aria-controls", "panneau");
    pilule.setAttribute("aria-expanded", "false");
    pilule.setAttribute("aria-label", "Ouvrir la discussion avec l'agent");
    var badge = noeud("span", "badge cache", "0");
    pilule.appendChild(badge);
    pilule.addEventListener("click", function () { definirReplie(false); });

    var curseur = noeud("div", "curseur");
    curseur.setAttribute("aria-hidden", "true");
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("width", "26");
    svg.setAttribute("height", "26");
    var chemin = document.createElementNS("http://www.w3.org/2000/svg", "path");
    chemin.setAttribute("d", "M3 2 L3 19 L8 14.5 L11.5 22 L14.5 20.7 L11 13.3 L18 13 Z");
    chemin.setAttribute("fill", "#4f46e5");
    chemin.setAttribute("stroke", "#ffffff");
    chemin.setAttribute("stroke-width", "1.5");
    svg.appendChild(chemin);
    curseur.appendChild(svg);

    racine.appendChild(panneau);
    racine.appendChild(pilule);
    racine.appendChild(curseur);
    ui = { panneau: panneau, fil: fil, saisie: saisie, pastille: pastille, etatTexte: etatTexte, bascule: bascule,
           pilule: pilule, badge: badge, curseur: curseur, btnPause: btnPause, btnReprise: btnReprise, btnArret: btnArret };
    document.documentElement.appendChild(hote);
    messages.forEach(function (m) { fil.appendChild(rendreMessage(m)); });
    descendre();
    majEtat();
    window.addEventListener("resize", reserverPlace);
    definirReplie(replie);
  }

  function ajouter(type, texte) {
    var m = { type: String(type), texte: String(texte), t: Date.now() };
    messages.push(m);
    while (messages.length > MAX_MESSAGES) messages.shift();
    if (ui.fil) {
      ui.fil.appendChild(rendreMessage(m));
      while (ui.fil.childNodes.length > MAX_MESSAGES) ui.fil.removeChild(ui.fil.firstChild);
      descendre();
    }
    if (replie && m.type !== "utilisateur") {
      nonLus += 1;
      majBadge();
      if (m.type === "alerte" || m.type === "demande_humaine") definirReplie(false);
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
    el.style.setProperty("outline", "3px solid #4f46e5", "important");
    el.style.setProperty("outline-offset", "2px", "important");
    var id = setTimeout(function () {
      el.style.removeProperty("outline");
      el.style.removeProperty("outline-offset");
      if (valeurs.outline[0]) el.style.setProperty("outline", valeurs.outline[0], valeurs.outline[1]);
      if (valeurs.offset[0]) el.style.setProperty("outline-offset", valeurs.offset[0], valeurs.offset[1]);
      minuteurs.delete(el);
    }, 2200);
    minuteurs.set(el, { id: id, valeurs: valeurs });
  }

  function deplacerCurseur(el) {
    if (!ui.curseur) return;
    var r = el.getBoundingClientRect();
    var x = Math.max(0, Math.min(window.innerWidth - 26, r.left + Math.min(r.width / 2, 40)));
    var y = Math.max(0, Math.min(window.innerHeight - 26, r.top + r.height / 2));
    var c = ui.curseur;
    if (!curseurPlace || reduit()) {
      c.className = "curseur instantane";
      c.style.transform = "translate(" + Math.round(x) + "px," + Math.round(y) + "px)";
      void c.offsetWidth;
      curseurPlace = true;
    } else {
      c.className = "curseur";
      c.style.transform = "translate(" + Math.round(x) + "px," + Math.round(y) + "px)";
    }
    c.className = c.className + " visible";
    if (minuteurCurseur) clearTimeout(minuteurCurseur);
    minuteurCurseur = setTimeout(function () { c.className = "curseur"; }, 2400);
  }

  function surligner(cible) {
    var el = null;
    try {
      el = typeof cible === "string" ? document.querySelector(cible) : cible;
    } catch (e) { el = null; }
    if (!el || !el.getBoundingClientRect) return { trouve: false, sensible: false };
    try { el.scrollIntoView({ block: "center", inline: "nearest", behavior: reduit() ? "auto" : "smooth" }); } catch (e) { }
    surlignerElement(el);
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
      messages.forEach(function (m) { ui.fil.appendChild(rendreMessage(m)); });
      descendre();
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
