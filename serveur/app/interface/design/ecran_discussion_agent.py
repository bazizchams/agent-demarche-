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
"""

from __future__ import annotations

_MARQUEUR_FIN_MAIN = "  </main>\n\n  <script>"
_MARQUEUR_JS = "    // Connexion automatique dès l'ouverture de l'interface"

CSS_DISCUSSION_AGENT = """
    <style>
      .da { display: flex; flex-direction: column; gap: var(--e3); min-width: 0; }
      .da-entete { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--e2) var(--e3); }
      .da-entete h3 { margin: 0; font-family: var(--police-titre); font-size: var(--t-md); }
      .da-commandes { display: flex; flex-wrap: wrap; gap: var(--e2); }
      .da-commandes .btn { margin: 0; min-height: var(--h-ctrl); }
      .da-fil { list-style: none; margin: 0; padding: var(--e3); display: flex; flex-direction: column; gap: var(--e2); min-height: 160px; max-height: min(60vh, 520px); overflow-y: auto; background: var(--surface-2); border: 1px solid var(--bord); border-radius: var(--r-m); }
      .da-fil:focus-visible { outline: none; box-shadow: var(--anneau); }
      .da-msg { display: flex; flex-direction: column; gap: var(--e1); padding: var(--e2) var(--e3); border-radius: var(--r-m); background: var(--surface); border: 1px solid var(--bord); overflow-wrap: anywhere; max-width: 100%; }
      .da-msg-entete { display: flex; justify-content: space-between; gap: var(--e3); font-size: var(--t-xs); font-weight: 700; color: var(--texte-faible); text-transform: uppercase; letter-spacing: 0.04em; }
      .da-msg-texte { margin: 0; font-size: var(--t-base); color: var(--texte); }
      .da-msg-action { border-style: dashed; }
      .da-msg-utilisateur { background: var(--accent-doux); border-color: var(--accent-moyen); margin-left: var(--e5); }
      .da-msg-alerte { background: var(--alerte-doux); border-color: var(--alerte); }
      .da-msg-alerte .da-msg-texte, .da-msg-alerte .da-msg-entete { color: var(--alerte-texte); }
      .da-msg-demande_humaine { background: var(--accent-doux); border: 2px solid var(--accent); }
      .da-msg-demande_humaine .da-msg-texte { font-weight: 600; }
      .da-msg-commande { background: transparent; border-style: dotted; }
      .da-vide { margin: 0; color: var(--texte-faible); font-size: var(--t-sm); }
      .da-saisie { display: flex; flex-wrap: wrap; align-items: flex-end; gap: var(--e2); }
      .da-saisie .champ { flex: 1 1 220px; margin: 0; }
      .da-saisie textarea { min-height: var(--h-ctrl-lg); resize: vertical; }
      .da-saisie .btn { margin: 0; min-height: var(--h-ctrl); }
      .da-aide { margin: 0; font-size: var(--t-xs); color: var(--texte-faible); }
      @media (max-width: 600px) { .da-msg-utilisateur { margin-left: var(--e2); } .da-saisie .btn { flex: 1 1 100%; } }
    </style>
"""

JS_DISCUSSION_AGENT = """
    // ===== Discussion de l'agent (composant réutilisable) =====
    const DA_LIBELLES = { agent: "Agent", action: "Action", alerte: "Alerte", demande_humaine: "L'agent a besoin de vous", utilisateur: "Vous", commande: "Commande" };
    const DA_ETATS = { en_cours: ["Au travail", "badge badge-ok"], pause: ["En pause", "badge badge-warn"], arret: ["Arrêté", "badge badge-err"], attente: ["Attend votre aide", "badge badge-warn"], inactif: ["En attente", "badge badge-attente"] };
    const DA_INTERVALLE_MS = 3000;
    const DA_ERREURS_AVANT_REPLI = 3;
    const DA_MAX_MESSAGES = 300;

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
      racine.appendChild(commandes);

      const fil = daNoeud("ol", "da-fil");
      fil.setAttribute("role", "log");
      fil.setAttribute("aria-live", "polite");
      fil.setAttribute("aria-label", "Messages de l'agent");
      fil.tabIndex = 0;
      const vide = daNoeud("li", "da-vide", "L'agent n'a encore rien dit. Ses messages apparaîtront ici, en direct.");
      fil.appendChild(vide);
      racine.appendChild(fil);

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

      function majEtat() {
        const cle = (etat === "en_cours" && derniereDemande) ? "attente" : etat;
        const [texte, classe] = DA_ETATS[cle] || DA_ETATS.inactif;
        badge.textContent = texte;
        badge.className = classe;
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
        const li = daNoeud("li", "da-msg da-msg-" + e.type);
        if (e.type === "alerte" || e.type === "demande_humaine") li.setAttribute("role", "alert");
        const tete = daNoeud("div", "da-msg-entete");
        tete.appendChild(daNoeud("span", "", DA_LIBELLES[e.type] || "Agent"));
        tete.appendChild(daNoeud("span", "", heure(e.cree_le)));
        li.appendChild(tete);
        li.appendChild(daNoeud("p", "da-msg-texte", e.texte));
        fil.appendChild(li);
        while (fil.childNodes.length > DA_MAX_MESSAGES) fil.removeChild(fil.firstChild);
        fil.scrollTop = fil.scrollHeight;
        if (e.type === "demande_humaine") derniereDemande = true;
        else if (e.type === "agent" || e.type === "action") derniereDemande = false;
      }

      async function interroger() {
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
      interroger().then(demarrerFlux);
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
