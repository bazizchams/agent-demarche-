"""Composant « Discussion de l'agent » : le fil de la fenêtre du PC, en direct, dans l'interface web.

INTÉGRATION (écran Dossier automatique ou tout autre écran) :
    1. Inclure ce composant dans la page : `assembler_discussion_agent(html_base)` (insère le style puis le
       script), ou intégrer `CSS_DISCUSSION_AGENT` et `JS_DISCUSSION_AGENT` soi-même.
    2. Fournir un conteneur vide (un `div`) puis appeler :

           const discussion = monterDiscussionAgent(conteneur, tacheId);   // tacheId : UUID de la tâche
           // ... plus tard, par exemple au changement de dossier :
           discussion.demonter();

       `monterDiscussionAgent(conteneur, tacheId)` construit tout par nœuds DOM (jamais `innerHTML`), vide le
       conteneur, remplace une discussion déjà montée dans le même conteneur et retourne
       `{ demonter(), actualiser() }`. Dépend de `appelApi` (CSRF) ; `notifier` et `roleActif` sont facultatifs.

API consommée : `GET /api/v1/taches/{id}/evenements?depuis=` (repli par interrogation toutes les 3 s),
flux SSE `GET /api/v1/taches/{id}/evenements/flux` (EventSource, reconnexion automatique), `POST .../messages`,
`POST .../pause|reprise|arret|premier-plan`.

Règles : couleurs et espaces par `var(--token)` (thème indigo clair/sombre, voir GUIDE_DESIGN.md), aucun
antislash, aucun `innerHTML`, aucun `console.log`. Fil en `role="log"` + `aria-live`, alertes en `role="alert"`,
focus visible, mobile (colonne unique, contrôles de 40 px). Le rôle lecture seule voit le fil sans pouvoir
écrire. Une consigne qui contredirait les règles 1/2/3/6 est refusée par le serveur et l'agent répond poliment ;
l'écran ne propose jamais de valider ou d'envoyer à la place de l'humain.

Présence (même langage visuel que le panneau injecté `agent_local/panneau_discussion.py`) : bulles typées avec
icône, indicateur « l'agent agit » discret, apparition fluide, auto-défilement qui ne vole pas la lecture
(bouton « nouveaux messages »), pastille d'état qui respire. Mouvement : tokens `--d*` / `--courbe` du design,
rien ne bouge sous `prefers-reduced-motion` ; contrat de mouvement partagé (motion.py) non requis : le composant
reste autonome. Aucune animation ne suggère qu'une chose a été validée ou envoyée (pas de coche animée).
"""

from __future__ import annotations

_MARQUEUR_FIN_MAIN = "  </main>\n\n  <script>"
_MARQUEUR_JS = "    // Connexion automatique dès l'ouverture de l'interface"

CSS_DISCUSSION_AGENT = """
    <style>
      .da { display: flex; flex-direction: column; gap: var(--e3); min-width: 0; }
      .da-entete { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--e2) var(--e3); }
      .da-entete h3 { margin: 0; font-family: var(--police-titre); font-size: var(--t-md); }
      .da-etat-travail .da-entete .badge::before { animation: da-vie 1600ms ease-in-out infinite; }
      .da-commandes { display: flex; flex-wrap: wrap; gap: var(--e2); }
      .da-commandes .btn { margin: 0; min-height: var(--h-ctrl); }
      .da-commandes .btn .da-ico { margin-right: var(--e1); }
      .da-zone { position: relative; display: flex; flex-direction: column; min-width: 0; }
      .da-fil { list-style: none; margin: 0; padding: var(--e3); display: flex; flex-direction: column; gap: var(--e3); min-height: 160px; max-height: min(60vh, 520px); overflow-y: auto; overscroll-behavior: contain; background: var(--surface-2); border: 1px solid var(--bord); border-radius: var(--r-m); }
      .da-fil:focus-visible { outline: none; box-shadow: var(--anneau); }
      .da-ico { flex: none; fill: none; stroke: currentColor; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }
      .da-msg { position: relative; display: flex; flex-direction: column; gap: var(--e1); max-width: 88%; padding: var(--e2) var(--e3); border-radius: var(--r-l) var(--r-l) var(--r-l) var(--r-s); background: var(--surface); border: 1px solid var(--bord); overflow-wrap: anywhere; align-self: flex-start; box-shadow: var(--ombre-1); }
      .da-msg-entree { animation: da-entree var(--d3) var(--courbe) both; }
      .da-msg-entete { display: flex; align-items: center; gap: var(--e2); font-size: var(--t-xs); font-weight: 700; color: var(--texte-faible); text-transform: uppercase; letter-spacing: 0.04em; }
      .da-msg-entete span:first-of-type { flex: 1; }
      .da-msg-entete span:last-child { font-weight: 500; text-transform: none; letter-spacing: 0; font-variant-numeric: tabular-nums; }
      .da-msg-texte { margin: 0; font-size: var(--t-base); color: var(--texte); }
      .da-msg-action { align-self: stretch; max-width: 100%; gap: 0; padding: var(--e1) var(--e3); background: transparent; box-shadow: none; border: 0; border-left: 3px solid var(--accent); border-radius: var(--r-s) var(--r-m) var(--r-m) var(--r-s); }
      .da-msg-action .da-msg-entete { color: var(--accent); }
      .da-msg-action .da-msg-texte { font-size: var(--t-sm); color: var(--texte-doux); }
      .da-msg-utilisateur { align-self: flex-end; background: var(--accent-plein); border-color: var(--accent-plein); border-radius: var(--r-l) var(--r-l) var(--r-s) var(--r-l); box-shadow: none; }
      .da-msg-utilisateur .da-msg-texte, .da-msg-utilisateur .da-msg-entete { color: var(--sur-accent); }
      .da-msg-alerte { align-self: stretch; max-width: 100%; background: var(--alerte-doux); border-color: var(--alerte); border-left: 4px solid var(--alerte); border-radius: var(--r-m); box-shadow: none; }
      .da-msg-alerte .da-msg-texte, .da-msg-alerte .da-msg-entete { color: var(--alerte-texte); }
      .da-msg-demande_humaine { align-self: stretch; max-width: 100%; background: var(--accent-doux); border: 2px solid var(--accent); border-radius: var(--r-m); box-shadow: none; }
      .da-msg-demande_humaine .da-msg-entete { color: var(--accent); }
      .da-msg-demande_humaine .da-msg-texte { font-weight: 600; }
      .da-msg-demande_humaine.da-msg-entree::after { content: ""; position: absolute; inset: -2px; border: 2px solid var(--accent); border-radius: inherit; pointer-events: none; animation: da-anneau var(--d3) ease-out both; }
      .da-msg-commande { background: transparent; border-style: dotted; box-shadow: none; align-self: center; max-width: 100%; }
      .da-ecrit { align-self: flex-start; display: inline-flex; align-items: center; gap: var(--e1); padding: var(--e2) var(--e3); border-radius: var(--r-l) var(--r-l) var(--r-l) var(--r-s); background: var(--surface); border: 1px solid var(--bord); }
      .da-ecrit i { width: 6px; height: 6px; border-radius: 50%; background: var(--texte-faible); animation: da-saut 1200ms ease-in-out infinite; }
      .da-ecrit i:nth-child(2) { animation-delay: 150ms; }
      .da-ecrit i:nth-child(3) { animation-delay: 300ms; }
      .da-nouveaux { position: absolute; left: 50%; bottom: var(--e3); transform: translateX(-50%); margin: 0; box-shadow: var(--ombre-2); animation: da-apparait var(--d2) var(--courbe) both; }
      .da-nouveaux[hidden] { display: none; }
      .da-vide { margin: 0; color: var(--texte-faible); font-size: var(--t-sm); }
      .da-saisie { display: flex; flex-wrap: wrap; align-items: flex-end; gap: var(--e2); }
      .da-saisie .champ { flex: 1 1 220px; margin: 0; }
      .da-saisie textarea { min-height: var(--h-ctrl-lg); resize: vertical; }
      .da-saisie .btn { margin: 0; min-height: var(--h-ctrl); }
      .da-aide { margin: 0; font-size: var(--t-xs); color: var(--texte-faible); }
      @keyframes da-entree { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
      @keyframes da-apparait { from { opacity: 0; transform: translate(-50%, 6px); } to { opacity: 1; transform: translateX(-50%); } }
      @keyframes da-anneau { from { opacity: 0.7; transform: scale(1); } to { opacity: 0; transform: scale(1.03); } }
      @keyframes da-vie { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(0.75); } }
      @keyframes da-saut { 0%, 60%, 100% { opacity: 0.4; transform: none; } 30% { opacity: 1; transform: translateY(-3px); } }
      @media (max-width: 600px) { .da-msg-utilisateur { margin-left: var(--e2); } .da-saisie .btn { flex: 1 1 100%; } }
      @media (prefers-reduced-motion: reduce) {
        .da-msg-entree, .da-msg-entree::after, .da-nouveaux, .da-ecrit i, .da-etat-travail .da-entete .badge::before { animation: none !important; }
        .da-nouveaux { transform: translateX(-50%); }
      }
    </style>
"""

JS_DISCUSSION_AGENT = """
    // ===== Discussion de l'agent (composant réutilisable) =====
    const DA_LIBELLES = { agent: "Agent", action: "Action", alerte: "Alerte", demande_humaine: "L'agent a besoin de vous", utilisateur: "Vous", commande: "Commande" };
    const DA_ETATS = { en_cours: ["Au travail", "badge badge-ok"], pause: ["En pause", "badge badge-warn"], arret: ["Arrêté", "badge badge-err"], attente: ["Attend votre aide", "badge badge-warn"], inactif: ["En attente", "badge badge-attente"] };
    const DA_INTERVALLE_MS = 3000;
    const DA_ERREURS_AVANT_REPLI = 3;
    const DA_MAX_MESSAGES = 300;
    const DA_SEUIL_BAS_PX = 48;
    const DA_ICONES = {
      agent: ["M3 4h10v7H8l-3 2.5V11H3z"], action: ["M3 2l9 4-4 1.5L6.5 12z"],
      alerte: ["M8 2l6.5 11.5h-13z", "M8 6.5v3", "M8 11.5v.1"],
      demande_humaine: ["M8 3.2a1.8 1.8 0 100 3.6 1.8 1.8 0 000-3.6z", "M3.5 13c.4-2.6 2.2-4 4.5-4s4.1 1.4 4.5 4"],
      pause: ["M5 3v10", "M11 3v10"], reprise: ["M5 3l8 5-8 5z"], arret: ["M4 4h8v8H4z"], bas: ["M3 6l5 5 5-5"]
    };

    function daIcone(nom, taille) {
      const ns = "http://www.w3.org/2000/svg";
      const s = document.createElementNS(ns, "svg");
      s.setAttribute("viewBox", "0 0 16 16");
      s.setAttribute("width", String(taille || 14));
      s.setAttribute("height", String(taille || 14));
      s.setAttribute("class", "da-ico");
      s.setAttribute("aria-hidden", "true");
      s.setAttribute("focusable", "false");
      (DA_ICONES[nom] || []).forEach(function (d) {
        const p = document.createElementNS(ns, "path");
        p.setAttribute("d", d);
        s.appendChild(p);
      });
      return s;
    }

    function daReduit() {
      try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (err) { return false; }
    }

    function daNoeud(balise, classe, texte) {
      const n = document.createElement(balise);
      if (classe) n.className = classe;
      if (texte !== undefined && texte !== null) n.textContent = texte;
      return n;
    }

    function monterDiscussionAgent(conteneur, tacheId) {
      if (conteneur.__discussionAgent) conteneur.__discussionAgent.demonter();
      while (conteneur.firstChild) conteneur.removeChild(conteneur.firstChild);
      const base = "/api/v1/taches/" + encodeURIComponent(tacheId);
      const lectureSeule = (typeof roleActif !== "undefined") && roleActif === "lecture_seule";
      const vus = new Set();
      let dernier = 0;
      let etat = "en_cours";
      let derniereDemande = false;
      let flux = null;
      let minuteur = null;
      let erreurs = 0;
      let actif = true;
      let colle = true;
      let nbMessages = 0;
      let nonVus = 0;
      let chargementInitial = true;
      let auto = 0;

      const racine = daNoeud("div", "da");
      const entete = daNoeud("div", "da-entete");
      entete.appendChild(daNoeud("h3", "", "Discussion de l'agent"));
      const badge = daNoeud("span", "badge");
      badge.setAttribute("role", "status");
      entete.appendChild(badge);
      racine.appendChild(entete);

      const commandes = daNoeud("div", "da-commandes");
      commandes.setAttribute("role", "group");
      commandes.setAttribute("aria-label", "Commandes de l'agent");
      const btnPause = daNoeud("button", "btn btn-contour btn-sm", "Pause");
      const btnReprise = daNoeud("button", "btn btn-contour btn-sm", "Reprendre");
      const btnArret = daNoeud("button", "btn btn-danger btn-sm", "Arrêter");
      const btnFenetre = daNoeud("button", "btn btn-lien btn-sm", "Voir la fenêtre sur mon PC");
      [btnPause, btnReprise, btnArret, btnFenetre].forEach(function (b) { b.type = "button"; commandes.appendChild(b); });
      [[btnPause, "pause"], [btnReprise, "reprise"], [btnArret, "arret"]].forEach(function (c) { c[0].insertBefore(daIcone(c[1], 14), c[0].firstChild); });
      racine.appendChild(commandes);

      const fil = daNoeud("ol", "da-fil");
      fil.setAttribute("role", "log");
      fil.setAttribute("aria-live", "polite");
      fil.setAttribute("aria-label", "Messages de l'agent");
      fil.tabIndex = 0;
      const vide = daNoeud("li", "da-vide", "L'agent n'a encore rien dit. Ses messages apparaîtront ici, en direct.");
      fil.appendChild(vide);
      const ecrit = daNoeud("li", "da-ecrit");
      ecrit.setAttribute("aria-hidden", "true");
      ecrit.hidden = true;
      ecrit.appendChild(daNoeud("i"));
      ecrit.appendChild(daNoeud("i"));
      ecrit.appendChild(daNoeud("i"));
      fil.appendChild(ecrit);
      const zone = daNoeud("div", "da-zone");
      zone.appendChild(fil);
      const nouveaux = daNoeud("button", "btn btn-secondaire btn-sm da-nouveaux", "");
      nouveaux.type = "button";
      nouveaux.hidden = true;
      const nouveauxTexte = daNoeud("span", "", "");
      nouveaux.appendChild(nouveauxTexte);
      nouveaux.appendChild(daIcone("bas", 12));
      zone.appendChild(nouveaux);
      racine.appendChild(zone);

      const formulaire = daNoeud("form", "da-saisie");
      const etiquette = daNoeud("label", "champ", "Écrire à l'agent");
      const saisie = document.createElement("textarea");
      saisie.id = "da-saisie-" + Math.random().toString(36).slice(2, 8);
      etiquette.setAttribute("for", saisie.id);
      saisie.maxLength = 1000;
      saisie.rows = 2;
      saisie.setAttribute("aria-describedby", saisie.id + "-aide");
      etiquette.appendChild(saisie);
      const envoyer = daNoeud("button", "btn btn-primaire", "Envoyer");
      envoyer.type = "submit";
      formulaire.appendChild(etiquette);
      formulaire.appendChild(envoyer);
      racine.appendChild(formulaire);
      const aide = daNoeud("p", "da-aide", "L'agent ne valide, n'envoie rien et ne contourne aucun contrôle à votre place : cela reste à vous. Ne saisissez jamais de mot de passe ici.");
      aide.id = saisie.id + "-aide";
      racine.appendChild(aide);
      conteneur.appendChild(racine);

      function pres() { return fil.scrollHeight - fil.scrollTop - fil.clientHeight < DA_SEUIL_BAS_PX; }
      function majNouveaux() {
        nouveaux.hidden = !(nonVus > 0 && !colle);
        nouveauxTexte.textContent = nonVus + (nonVus > 1 ? " nouveaux messages" : " nouveau message");
      }
      function descendre(doux) {
        auto = Date.now() + 450;
        colle = true;
        nonVus = 0;
        majNouveaux();
        try { fil.scrollTo({ top: fil.scrollHeight, behavior: doux && !daReduit() ? "smooth" : "auto" }); } catch (err) { fil.scrollTop = fil.scrollHeight; }
      }
      fil.addEventListener("scroll", function () {
        if (Date.now() < auto) { auto = Date.now() + 150; return; }
        colle = pres();
        if (colle) nonVus = 0;
        majNouveaux();
      });
      fil.addEventListener("wheel", function (ev) { if (ev.deltaY < 0) { auto = 0; colle = false; } }, { passive: true });
      nouveaux.addEventListener("click", function () { fil.focus({ preventScroll: true }); descendre(true); });

      function majEtat() {
        const cle = (etat === "en_cours" && derniereDemande) ? "attente" : etat;
        const [texte, classe] = DA_ETATS[cle] || DA_ETATS.inactif;
        badge.textContent = texte;
        badge.className = classe;
        racine.className = "da" + (etat === "en_cours" && !derniereDemande ? " da-etat-travail" : "");
        ecrit.hidden = !(etat === "en_cours" && !derniereDemande);
        if (!ecrit.hidden) fil.appendChild(ecrit);
        btnPause.disabled = lectureSeule || etat !== "en_cours";
        btnReprise.disabled = lectureSeule || etat !== "pause";
        btnArret.disabled = lectureSeule || etat === "arret";
        btnFenetre.disabled = lectureSeule;
        saisie.disabled = lectureSeule;
        envoyer.disabled = lectureSeule;
      }

      function heure(iso) {
        const d = new Date(iso);
        if (isNaN(d.getTime())) return "";
        return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
      }

      function ajouter(e) {
        if (!e || vus.has(e.seq)) return;
        vus.add(e.seq);
        dernier = Math.max(dernier, e.seq);
        if (vide.parentNode) fil.removeChild(vide);
        const suivre = colle || pres();
        const li = daNoeud("li", "da-msg da-msg-" + e.type + (chargementInitial || daReduit() ? "" : " da-msg-entree"));
        if (e.type === "alerte" || e.type === "demande_humaine") li.setAttribute("role", "alert");
        const tete = daNoeud("div", "da-msg-entete");
        if (DA_ICONES[e.type]) tete.appendChild(daIcone(e.type, 12));
        tete.appendChild(daNoeud("span", "", DA_LIBELLES[e.type] || "Agent"));
        tete.appendChild(daNoeud("span", "", heure(e.cree_le)));
        li.appendChild(tete);
        li.appendChild(daNoeud("p", "da-msg-texte", e.texte));
        fil.insertBefore(li, ecrit);
        nbMessages += 1;
        while (nbMessages > DA_MAX_MESSAGES && fil.firstChild && fil.firstChild !== ecrit) { fil.removeChild(fil.firstChild); nbMessages -= 1; }
        // Auto-défilement qui ne vole pas la lecture : on suit le fil seulement si l'on est déjà en bas
        // (ou si l'humain vient d'écrire / si l'agent a besoin de lui) ; sinon bouton « nouveaux messages ».
        if (suivre || e.type === "utilisateur" || e.type === "demande_humaine") descendre(!chargementInitial);
        else { nonVus += 1; majNouveaux(); }
        if (e.type === "demande_humaine") derniereDemande = true;
        else if (e.type === "agent" || e.type === "action") derniereDemande = false;
      }

      async function interroger() {
        if (document.hidden) return;
        try {
          const rep = await appelApi(base + "/evenements?depuis=" + dernier);
          if (!rep.ok) return;
          const d = await rep.json();
          d.elements.forEach(ajouter);
          etat = d.etat || etat;
          majEtat();
        } catch (err) { /* réseau coupé : nouvel essai au prochain tour */ }
      }

      function demarrerRepli() {
        if (flux) { flux.close(); flux = null; }
        if (!minuteur && actif) minuteur = setInterval(interroger, DA_INTERVALLE_MS);
      }

      function demarrerFlux() {
        if (typeof EventSource === "undefined") { demarrerRepli(); return; }
        flux = new EventSource(base + "/evenements/flux?depuis=" + dernier);
        flux.addEventListener("evenement", function (ev) {
          erreurs = 0;
          try { ajouter(JSON.parse(ev.data)); majEtat(); } catch (err) { /* message illisible ignoré */ }
        });
        flux.addEventListener("etat", function (ev) {
          try { etat = JSON.parse(ev.data).etat || etat; majEtat(); } catch (err) { /* ignoré */ }
        });
        flux.onerror = function () {
          erreurs += 1;
          if (erreurs >= DA_ERREURS_AVANT_REPLI) demarrerRepli();
        };
      }

      async function commande(chemin, libelleOk) {
        const rep = await appelApi(base + "/" + chemin, { method: "POST" });
        if (rep.ok) {
          const d = await rep.json();
          ajouter(d.evenement);
          etat = d.etat || etat;
          majEtat();
          if (typeof notifier === "function" && libelleOk) notifier(libelleOk, true);
        } else if (typeof notifier === "function") {
          let detail = "Commande impossible.";
          try { detail = (await rep.json()).detail || detail; } catch (err) { /* corps vide */ }
          notifier(detail, false);
        }
      }

      btnPause.addEventListener("click", function () { commande("pause"); });
      btnReprise.addEventListener("click", function () { commande("reprise"); });
      btnArret.addEventListener("click", function () { commande("arret"); });
      btnFenetre.addEventListener("click", function () {
        commande("premier-plan", "La fenêtre de l'agent passe au premier plan sur le PC du bureau (pas dans ce navigateur).");
      });
      formulaire.addEventListener("submit", async function (ev) {
        ev.preventDefault();
        const texte = saisie.value.trim();
        if (!texte || lectureSeule) return;
        envoyer.disabled = true;
        try {
          const rep = await appelApi(base + "/messages", { method: "POST", body: JSON.stringify({ texte: texte }) });
          if (rep.ok) {
            const d = await rep.json();
            ajouter(d.message);
            if (d.reponse) ajouter(d.reponse);
            saisie.value = "";
          } else if (typeof notifier === "function") {
            notifier("Message non envoyé.", false);
          }
        } finally {
          envoyer.disabled = lectureSeule;
          saisie.focus();
        }
      });
      saisie.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); formulaire.requestSubmit(); }
      });

      function demonter() {
        actif = false;
        if (flux) { flux.close(); flux = null; }
        if (minuteur) { clearInterval(minuteur); minuteur = null; }
        while (conteneur.firstChild) conteneur.removeChild(conteneur.firstChild);
        conteneur.__discussionAgent = null;
      }

      majEtat();
      interroger().then(function () { chargementInitial = false; demarrerFlux(); });
      const poignee = { demonter: demonter, actualiser: interroger };
      conteneur.__discussionAgent = poignee;
      return poignee;
    }
"""


def _inserer(html: str, marqueur: str, contenu: str) -> str:
    if marqueur not in html:
        raise ValueError(f"Repère introuvable dans la page de base : {marqueur!r}")
    return html.replace(marqueur, contenu + marqueur, 1)


def assembler_discussion_agent(html_base: str) -> str:
    """Insère le style (avant la fin de `main`) puis le script (avant l'ouverture automatique de session)."""
    html = _inserer(html_base, _MARQUEUR_FIN_MAIN, CSS_DISCUSSION_AGENT + "\n")
    return _inserer(html, _MARQUEUR_JS, JS_DISCUSSION_AGENT)
