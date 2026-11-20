"""Écran de revue des valeurs lues dans les documents (phase P1 « lecture des documents »).

Pour chaque valeur proposée : l'extrait du document (et l'image si le document en est une) à côté
de la valeur, avec les boutons Confirmer, Corriger et Rejeter. Rien n'atteint la fiche sans la
confirmation d'un humain (règles 1 et 4) ; les valeurs sont celles de l'API, jamais écrites dans
le HTML servi.

Règles du guide de design (`design/GUIDE_DESIGN.md`) respectées :
- couleurs, espaces, rayons : uniquement `var(--token)` ;
- JavaScript : nœuds DOM créés un à un et `textContent` (jamais d'insertion de HTML), pas de
  console, pas de stockage navigateur ; aucun antislash dans ce code (page servie depuis une
  chaîne Python) ;
- navigation déclarative par `data-vue`, bouton de menu `bouton_nav`.
"""

from __future__ import annotations

from app.interface.design.shell import bouton_nav, rendre_icones

_MARQUEUR_NAV = "<!-- nav:validation -->"
_MARQUEUR_FIN_MAIN = "  </main>\n\n  <script>"
_MARQUEUR_JS = "    // Connexion automatique dès l'ouverture de l'interface"

HTML_NAV = "\n      " + bouton_nav("vue-revue-extractions", "Lecture des documents", "pieces")

STYLE_REVUE = """
    <style>
      #vue-revue-extractions .rx-barre { display: flex; flex-wrap: wrap; align-items: flex-end; gap: var(--e3); margin: 0 0 var(--e4); }
      #vue-revue-extractions .rx-barre .btn { margin: 0; }
      #vue-revue-extractions .rx-barre .champ { min-width: 220px; margin: 0; }
      #vue-revue-extractions .rx-resume { margin: 0 0 var(--e3); }
      #vue-revue-extractions .rx-liste { display: flex; flex-direction: column; gap: var(--e4); }
      #vue-revue-extractions .rx-bloc { display: flex; flex-direction: column; gap: var(--e2); margin: 0 0 var(--e4); padding: var(--e3) var(--e4); background: var(--alerte-doux); color: var(--alerte-texte); border-left: 4px solid var(--alerte); border-radius: var(--r-s) var(--r-m) var(--r-m) var(--r-s); font-size: var(--t-sm); }
      #vue-revue-extractions .rx-bloc.rx-critique { background: var(--critique-doux); color: var(--critique-texte); border-left-color: var(--critique); }
      #vue-revue-extractions .rx-bloc p, #vue-revue-extractions .rx-bloc ul { margin: 0; }
      #vue-revue-extractions .rx-bloc ul { padding-left: var(--e5); }
      #vue-revue-extractions .rx-carte-entete { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--e2); }
      #vue-revue-extractions .rx-carte-entete h4 { margin: 0; }
      #vue-revue-extractions .rx-grille { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr)); gap: var(--e4); }
      #vue-revue-extractions .rx-colonne { display: flex; flex-direction: column; gap: var(--e2); min-width: 0; }
      #vue-revue-extractions .rx-etiquette { margin: 0; font-size: var(--t-xs); font-weight: 600; letter-spacing: 0.07em; text-transform: uppercase; color: var(--texte-faible); }
      #vue-revue-extractions .rx-extrait { margin: 0; padding: var(--e3); background: var(--surface-2); border: 1px solid var(--bord); border-radius: var(--r-m); font-family: var(--police-code); font-size: var(--t-sm); overflow-wrap: anywhere; white-space: pre-wrap; }
      #vue-revue-extractions .rx-zoom { position: relative; display: block; width: 100%; height: 260px; padding: 0; margin: 0; overflow: hidden; border: 1px solid var(--bord); border-radius: var(--r-m); background: var(--surface-2); cursor: zoom-in; }
      #vue-revue-extractions .rx-zoom:focus-visible { outline: none; box-shadow: var(--anneau); }
      #vue-revue-extractions .rx-zoom.rx-zoom-actif { cursor: zoom-out; }
      #vue-revue-extractions .rx-image { display: block; width: 100%; height: 100%; object-fit: contain; transform-origin: 50% 50%; transition: transform var(--d2) var(--courbe); will-change: transform; }
      #vue-revue-extractions .rx-zoom:hover .rx-image, #vue-revue-extractions .rx-zoom.rx-zoom-actif .rx-image { transform: scale(2); }
      #vue-revue-extractions .rx-aide { margin: 0; font-size: var(--t-xs); color: var(--texte-faible); }
      #vue-revue-extractions .rx-carte { position: relative; border-left: 4px solid var(--bord-fort); transition: border-color var(--d2) var(--courbe), background-color var(--d2) var(--courbe); }
      #vue-revue-extractions .rx-carte.rx-st-auto { border-left-color: var(--accent); }
      #vue-revue-extractions .rx-carte.rx-st-a_verifier { border-left-color: var(--alerte); }
      #vue-revue-extractions .rx-carte.rx-st-valide_humain { border-left-color: var(--bon); }
      #vue-revue-extractions .rx-carte.rx-st-rejete { border-left-color: var(--critique); }
      #vue-revue-extractions .rx-carte.rx-st-rejete .rx-valeur { color: var(--texte-faible); text-decoration: line-through; }
      #vue-revue-extractions .rx-carte.rx-change::after { content: ""; position: absolute; inset: 0; border-radius: inherit; background: var(--accent-doux); pointer-events: none; animation: rx-flash var(--d3) var(--courbe) both; }
      #vue-revue-extractions .rx-carte.rx-change .badge { animation: rx-pop var(--d3) var(--courbe) both; }
      #vue-revue-extractions .rx-transition { margin: 0; font-size: var(--t-xs); color: var(--texte-faible); }
      #vue-revue-extractions button[aria-busy="true"] { cursor: progress; }
      @keyframes rx-flash { from { opacity: 0.8; } to { opacity: 0; } }
      @keyframes rx-pop { from { opacity: 0.4; transform: scale(0.85); } to { opacity: 1; transform: none; } }
      @media (prefers-reduced-motion: reduce) {
        #vue-revue-extractions .rx-carte.rx-change::after, #vue-revue-extractions .rx-carte.rx-change .badge { animation: none !important; }
        #vue-revue-extractions .rx-image, #vue-revue-extractions .rx-carte { transition: none !important; }
      }
      #vue-revue-extractions .rx-valeur { margin: 0; font-size: var(--t-lg); font-weight: 600; color: var(--texte); overflow-wrap: anywhere; font-variant-numeric: tabular-nums; }
      #vue-revue-extractions .rx-note { margin: 0; font-size: var(--t-sm); color: var(--texte-doux); overflow-wrap: anywhere; }
      #vue-revue-extractions .rx-actions { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e2); }
      #vue-revue-extractions .rx-actions .btn { margin: 0; }
      #vue-revue-extractions .rx-correction { display: flex; flex-wrap: wrap; align-items: flex-end; gap: var(--e2); }
      #vue-revue-extractions .rx-correction .btn { margin: 0; }
      #vue-revue-extractions .rx-lot { display: flex; flex-direction: column; gap: var(--e3); margin: 0 0 var(--e4); padding: var(--e4); background: var(--accent-doux); border: 1px solid var(--bord); border-left: 4px solid var(--accent); border-radius: var(--r-m); }
      #vue-revue-extractions .rx-lot p, #vue-revue-extractions .rx-lot ul { margin: 0; }
      #vue-revue-extractions .rx-lot ul { padding-left: var(--e5); font-size: var(--t-sm); }
      #vue-revue-extractions .rx-lot .btn { align-self: flex-start; margin: 0; }
      #vue-revue-extractions .rx-carte.rx-douteuse { background: var(--alerte-doux); border-left-color: var(--alerte); box-shadow: inset 0 0 0 1px var(--alerte); }
    </style>"""

HTML_VUE = rendre_icones(
    """
    <!-- Lecture des documents (phase P1) -->
    <section id="vue-revue-extractions" class="vue-ecran cache">"""
    + STYLE_REVUE
    + """
      <header class="page-entete">
        <div>
          <h2>Lecture des documents</h2>
          <p class="lead">Relisez chaque valeur lue dans les pièces de l'étudiant : confirmez, corrigez ou rejetez.</p>
        </div>
        <div class="page-actions">
          <button id="rx-btn-actualiser" class="btn btn-secondaire" type="button">[[i:actualiser]]Actualiser</button>
        </div>
      </header>
      <div class="banniere-regle">
        Rien n'est écrit sur la fiche sans votre confirmation : un seul clic sur « Tout confirmer et
        remplir la fiche » valide les valeurs fiables (passeport contrôlé, deux lectures concordantes
        ou même valeur sur deux pièces). Les valeurs douteuses se confirment une par une. Une valeur douteuse reste « à vérifier » et n'est
        jamais appliquée ; un champ illisible reste vide (Règle 4). Une valeur déjà saisie sur la
        fiche n'est jamais écrasée.
      </div>
      <div class="rx-barre">
        <label class="champ" for="rx-demarche">Pièces à contrôler avant la lecture
          <select id="rx-demarche">
            <option value="">Aucune démarche</option>
            <option value="campus_france">Campus France</option>
            <option value="ircc_permis_etudes">IRCC permis d'études</option>
          </select>
        </label>
        <button id="rx-btn-lire" class="btn btn-primaire" type="button">[[i:pieces]]Lire les documents</button>
        <button id="rx-btn-appliquer" class="btn btn-contour" type="button">[[i:coche]]Appliquer à la fiche</button>
      </div>
      <p id="rx-resume" class="note rx-resume cache"></p>
      <div id="rx-lot" class="rx-lot cache">
        <p id="rx-lot-texte"></p>
        <button id="rx-btn-lot" class="btn btn-primaire" type="button">[[i:coche]]Tout confirmer et remplir la fiche</button>
        <div id="rx-lot-details"></div>
      </div>
      <div id="rx-alertes"></div>
      <div id="rx-liste" class="rx-liste"></div>
    </section>
"""
)

JS_REVUE = """
    // =======================================================================
    // Lecture des documents : revue des valeurs lues (extrait à côté de la valeur proposée).
    // Tout contenu affiché passe par textContent ou des nœuds DOM créés un à un.
    // =======================================================================
    const RX_CHAMPS = {
      nom: "Nom", prenom: "Prénom", date_naissance: "Date de naissance", sexe: "Sexe",
      nationalite_code: "Nationalité (code)", numero_passeport: "Numéro de passeport",
      date_expiration_passeport: "Expiration du passeport", moyenne_generale: "Moyenne générale",
      certificat_langue_type: "Test de langue", certificat_langue_date: "Date du test de langue",
      niveau_francais: "Niveau de français", niveau_anglais: "Niveau d'anglais", ielts_bande: "Note IELTS",
      lieu_naissance: "Lieu de naissance", diplome_intitule: "Diplôme", diplome_etablissement: "Établissement",
      diplome_annee: "Année du diplôme", annee_universitaire: "Année universitaire", moyenne_annuelle: "Moyenne annuelle",
      mention: "Mention", rang: "Rang", session: "Session", decision_jury: "Décision du jury",
      diplome_filiere: "Filière", diplome_specialite: "Spécialité", numero_bac: "Numéro du baccalauréat", bac_serie: "Série du bac"
    };
    const RX_RAISONS = {
      mrz_valide: "Fiable : chiffres de contrôle du passeport valides.",
      double_lecture_concordante: "Fiable : les deux lectures concordent.",
      concordance_deux_pieces: "Fiable : même valeur lue sur deux pièces.",
      valeurs_differentes_entre_pieces: "Douteuse : les pièces ne donnent pas la même valeur."
    };
    let rxSynthese = null;
    const RX_STATUTS = {
      auto: ["Lu automatiquement : à confirmer", "badge-info"],
      a_verifier: ["À vérifier", "badge-completer"],
      valide_humain: ["Confirmé", "badge-valide"],
      rejete: ["Rejeté", "badge-refuse"]
    };
    const RX_MOTIFS = {
      discordance_ab: "Les deux lectures ne concordent pas.",
      double_lecture_absente: "Une seule lecture : à confirmer.",
      lecteur_b_sans_valeur: "Le second lecteur n'a pas vu ce champ.",
      lecteur_a_absent: "Vu seulement par le second lecteur.",
      b_non_ancre: "Le second lecteur n'a pas cité d'extrait vérifiable.",
      non_ancree: "Valeur introuvable dans le document.",
      controle_icao: "Contrôlée par les chiffres de contrôle du passeport.",
      discordance_inter_pieces: "Différent d'une autre pièce du dossier.",
      moyenne_hors_bornes: "Moyenne hors de l'intervalle 0 à 20.",
      moyenne_ambigue: "Plusieurs moyennes différentes dans le document.",
      bareme_different: "Barème différent de /20.",
      mrz_controle_invalide: "Zone lisible par machine : chiffre de contrôle faux.",
      mrz_date_invalide: "Zone lisible par machine : date impossible.",
      niveau_ambigu: "Plusieurs niveaux différents dans le document.",
      niveau_incoherent_avec_diplome: "Niveau incompatible avec ce diplôme.",
      bande_hors_bornes: "Note hors de l'intervalle 0 à 9.",
      valeurs_multiples: "Valeurs différentes selon les pages.",
      corrige_humain: "Corrigée par un humain.",
      rejete_humain: "Rejetée par un humain."
    };
    const RX_ALERTES = {
      passeport_expire: "Passeport expiré.",
      passeport_expiration_proche: "Passeport expirant dans moins de six mois."
    };
    const rxImagesDocuments = {};

    function rxEcriture() {
      return roleActif === "administrateur" || roleActif === "employe";
    }

    function rxEl(balise, classe, texte) {
      const el = document.createElement(balise);
      if (classe) el.className = classe;
      if (texte !== undefined) el.textContent = texte;
      return el;
    }

    function rxVider(el) {
      while (el.firstChild) el.removeChild(el.firstChild);
    }

    function rxUrlCandidat(suite) {
      return "/api/v1/candidats/" + encodeURIComponent(candidatActifId) + suite;
    }

    async function rxLireDetail(rep) {
      try {
        const corps = await rep.json();
        return corps && typeof corps.detail === "string" ? corps.detail : null;
      } catch (e) {
        return null;
      }
    }

    async function rxChargerImage(doc, conteneur) {
      if (!doc || doc.type_mime.indexOf("image/") !== 0) return;
      if (!rxImagesDocuments[doc.id]) {
        const rep = await appelApi(rxUrlCandidat("/documents/" + encodeURIComponent(doc.id) + "/telecharger"));
        if (!rep.ok) return;
        rxImagesDocuments[doc.id] = URL.createObjectURL(await rep.blob());
      }
      const img = rxEl("img", "rx-image");
      img.src = rxImagesDocuments[doc.id];
      img.alt = "";
      const zone = rxEl("button", "rx-zoom");
      zone.type = "button";
      zone.setAttribute("aria-pressed", "false");
      zone.setAttribute("aria-label", "Agrandir l'aperçu du document : " + (doc.nom_fichier_origine || "pièce du dossier"));
      zone.appendChild(img);
      function rxOrigine(x, y) {
        img.style.transformOrigin = Math.max(0, Math.min(100, x)) + "% " + Math.max(0, Math.min(100, y)) + "%";
      }
      zone.addEventListener("pointermove", (ev) => {
        const r = zone.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) rxOrigine(((ev.clientX - r.left) / r.width) * 100, ((ev.clientY - r.top) / r.height) * 100);
      });
      zone.addEventListener("click", () => {
        const actif = zone.classList.toggle("rx-zoom-actif");
        zone.setAttribute("aria-pressed", actif ? "true" : "false");
        if (!actif) rxOrigine(50, 50);
      });
      let ox = 50, oy = 50;
      zone.addEventListener("keydown", (ev) => {
        if (!zone.classList.contains("rx-zoom-actif")) return;
        const pas = { ArrowLeft: [-12, 0], ArrowRight: [12, 0], ArrowUp: [0, -12], ArrowDown: [0, 12] }[ev.key];
        if (pas) { ev.preventDefault(); ox += pas[0]; oy += pas[1]; rxOrigine(ox, oy); }
        else if (ev.key === "Escape") { zone.classList.remove("rx-zoom-actif"); zone.setAttribute("aria-pressed", "false"); rxOrigine(50, 50); }
      });
      conteneur.appendChild(zone);
      conteneur.appendChild(rxEl("p", "rx-aide", "Survolez ou appuyez sur Entrée pour agrandir ; flèches pour se déplacer, Échap pour revenir."));
    }

    function rxLibelleMotif(motif) {
      return motif ? (RX_MOTIFS[motif] || "Motif : " + motif) : "";
    }

    // Focus conservé : après Confirmer/Rejeter la liste est reconstruite ; on refocalise le bouton de la même
    // valeur (même action, sinon un autre bouton de la carte), sinon celui de la valeur suivante.
    let rxFocus = null;
    function rxBoutonsDecision() {
      return Array.from(document.querySelectorAll("#rx-liste button[data-rx-extraction]"));
    }
    function rxMemoriserFocus(extraction, action) {
      const ids = [];
      rxBoutonsDecision().forEach((b) => {
        const id = b.getAttribute("data-rx-extraction");
        if (ids.indexOf(id) < 0) ids.push(id);
      });
      const rang = ids.indexOf(extraction.id);
      rxFocus = { id: extraction.id, action: action, suivant: rang >= 0 && rang + 1 < ids.length ? ids[rang + 1] : null };
    }
    function rxRefocaliser() {
      if (!rxFocus) return;
      const cible = rxFocus;
      rxFocus = null;
      const boutons = rxBoutonsDecision();
      const deCarte = boutons.filter((b) => b.getAttribute("data-rx-extraction") === cible.id);
      const trouve = deCarte.find((b) => b.getAttribute("data-rx-action") === cible.action) || deCarte[0] ||
        boutons.find((b) => b.getAttribute("data-rx-extraction") === cible.suivant) || boutons[0];
      if (trouve) trouve.focus();
    }

    let rxChangement = null;
    function rxOccuper(extraction, action, occupe) {
      document.querySelectorAll("#rx-liste button[data-rx-extraction]").forEach((b) => {
        if (b.getAttribute("data-rx-extraction") !== extraction.id) return;
        b.disabled = occupe;
        if (b.getAttribute("data-rx-action") === action && occupe) b.setAttribute("aria-busy", "true");
        else b.removeAttribute("aria-busy");
      });
    }

    async function rxDecider(extraction, action, valeur) {
      rxMemoriserFocus(extraction, action);
      rxOccuper(extraction, action, true);
      const options = { method: "POST" };
      if (action === "corriger") options.body = JSON.stringify({ valeur: valeur });
      const rep = await appelApi(rxUrlCandidat("/extractions/" + encodeURIComponent(extraction.id) + "/" + action), options);
      if (rep.ok) {
        rxChangement = { id: extraction.id, avant: extraction.statut };
        notifier(action === "rejeter" ? "Valeur rejetée." : "Valeur confirmée : elle pourra être appliquée à la fiche.", true);
      } else {
        notifier((await rxLireDetail(rep)) || "Action impossible sur cette valeur.", false);
      }
      await rxActualiser();
      rxOccuper(extraction, action, false);
      rxChangement = null;
      rxRefocaliser();
    }

    function rxBoutonAction(texte, classe, auClic, extraction, action) {
      const b = rxEl("button", "btn btn-sm " + classe, texte);
      b.type = "button";
      if (extraction) {
        b.setAttribute("data-rx-extraction", extraction.id);
        b.setAttribute("data-rx-action", action);
      }
      b.addEventListener("click", auClic);
      return b;
    }

    function rxAfficherCorrection(zone, extraction) {
      rxVider(zone);
      const champ = rxEl("label", "champ", "Valeur corrigée");
      const entree = rxEl("input");
      entree.type = "text";
      entree.maxLength = 200;
      entree.setAttribute("aria-label", "Valeur corrigée");
      champ.appendChild(entree);
      zone.appendChild(champ);
      zone.appendChild(rxBoutonAction("Enregistrer", "btn-primaire", () => {
        if (entree.value.trim()) rxDecider(extraction, "corriger", entree.value.trim());
      }));
      zone.appendChild(rxBoutonAction("Annuler", "btn-fantome", () => rxVider(zone)));
      entree.focus();
    }

    function rxCarte(extraction, doc) {
      const [libelleStatut, classeStatut] = RX_STATUTS[extraction.statut] || [extraction.statut, ""];
      const carte = rxEl("section", "carte rx-carte rx-st-" + extraction.statut);
      const entete = rxEl("div", "rx-carte-entete");
      entete.appendChild(rxEl("h4", "", RX_CHAMPS[extraction.champ] || extraction.champ));
      entete.appendChild(rxEl("span", "badge " + classeStatut, libelleStatut));
      carte.appendChild(entete);
      if (rxChangement && rxChangement.id === extraction.id && rxChangement.avant !== extraction.statut) {
        const ancien = (RX_STATUTS[rxChangement.avant] || [rxChangement.avant])[0];
        carte.appendChild(rxEl("p", "rx-transition", "Avant : " + ancien + ". Maintenant : " + libelleStatut + "."));
        if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) carte.classList.add("rx-change");
      }

      const grille = rxEl("div", "rx-grille");
      const source = rxEl("div", "rx-colonne");
      source.appendChild(rxEl("p", "rx-etiquette", "Dans le document" + (extraction.page ? " (page " + extraction.page + ")" : "")));
      source.appendChild(rxEl("p", "rx-extrait", extraction.extrait));
      rxChargerImage(doc, source);
      grille.appendChild(source);

      const proposition = rxEl("div", "rx-colonne");
      proposition.appendChild(rxEl("p", "rx-etiquette", "Valeur proposée"));
      proposition.appendChild(rxEl("p", "rx-valeur", extraction.valeur));
      if (extraction.valeur_alternative) {
        proposition.appendChild(rxEl("p", "rx-note", "Autre lecture : " + extraction.valeur_alternative));
      }
      const motif = rxLibelleMotif(extraction.motif);
      if (motif) proposition.appendChild(rxEl("p", "rx-note", motif));
      if (extraction.applique_le) proposition.appendChild(rxEl("p", "rx-note", "Appliquée à la fiche."));
      const fiab = rxSynthese && rxSynthese[extraction.id];
      if (fiab) {
        proposition.appendChild(rxEl("p", "rx-note", RX_RAISONS[fiab.raison] || (fiab.niveau === "fiable" ? "Fiable." : "Douteuse : confirmez-la individuellement.")));
        if (fiab.conflit_fiche) proposition.appendChild(rxEl("p", "rx-note", "La fiche contient déjà une autre valeur : elle ne sera pas écrasée."));
        if (fiab.niveau === "douteuse") carte.classList.add("rx-douteuse");
      }
      const zoneCorrection = rxEl("div", "rx-correction");
      if (rxEcriture()) {
        const actions = rxEl("div", "rx-actions");
        if (extraction.statut !== "valide_humain") {
          actions.appendChild(rxBoutonAction("Confirmer", "btn-primaire", () => rxDecider(extraction, "valider"), extraction, "valider"));
        }
        actions.appendChild(rxBoutonAction("Corriger", "btn-contour", () => rxAfficherCorrection(zoneCorrection, extraction), extraction, "corriger"));
        if (extraction.statut !== "rejete") {
          actions.appendChild(rxBoutonAction("Rejeter", "btn-danger", () => rxDecider(extraction, "rejeter"), extraction, "rejeter"));
        }
        proposition.appendChild(actions);
        proposition.appendChild(zoneCorrection);
      }
      grille.appendChild(proposition);
      carte.appendChild(grille);
      return carte;
    }

    function rxAfficherAlertes(alertes, completude, erreurs) {
      const zone = document.getElementById("rx-alertes");
      rxVider(zone);
      if (completude && completude.pieces_manquantes_ou_invalides.length) {
        const bloc = rxEl("div", "rx-bloc rx-critique");
        bloc.appendChild(rxEl("p", "", "Pièces manquantes ou invalides pour cette démarche :"));
        const liste = rxEl("ul");
        completude.pieces_manquantes_ou_invalides.forEach((p) => liste.appendChild(rxEl("li", "", p)));
        bloc.appendChild(liste);
        zone.appendChild(bloc);
      }
      const messages = (alertes || []).map((a) => RX_ALERTES[a.code] || a.message);
      (erreurs || []).forEach((e) => messages.push("Un document n'a pas pu être lu : " + e.detail));
      if (messages.length) {
        const bloc = rxEl("div", "rx-bloc");
        const liste = rxEl("ul");
        messages.forEach((m) => liste.appendChild(rxEl("li", "", m)));
        bloc.appendChild(liste);
        zone.appendChild(bloc);
      }
    }

    function rxLibererImages() {
      Object.keys(rxImagesDocuments).forEach((id) => {
        URL.revokeObjectURL(rxImagesDocuments[id]);
        delete rxImagesDocuments[id];
      });
    }

    async function rxActualiser() {
      const liste = document.getElementById("rx-liste");
      const resume = document.getElementById("rx-resume");
      rxVider(liste);
      rxLibererImages();
      if (!candidatActifId) {
        resume.textContent = "Choisissez d'abord un étudiant dans la liste des étudiants.";
        resume.classList.remove("cache");
        return;
      }
      const [repDocs, repExtr, repSyn] = await Promise.all([
        appelApi(rxUrlCandidat("/documents")), appelApi(rxUrlCandidat("/extractions")),
        appelApi(rxUrlCandidat("/extractions/synthese"))
      ]);
      rxSynthese = null;
      const synthese = repSyn.ok ? await repSyn.json() : null;
      if (synthese) {
        rxSynthese = {};
        synthese.items.forEach((i) => { rxSynthese[i.extraction_id] = i; });
      }
      rxAfficherLot(synthese);
      if (!repExtr.ok) {
        resume.textContent = "Lecture des documents indisponible.";
        resume.classList.remove("cache");
        return;
      }
      const documents = repDocs.ok ? await repDocs.json() : [];
      const extractions = await repExtr.json();
      const parId = {};
      documents.forEach((d) => { parId[d.id] = d; });
      const aVerifier = extractions.filter((e) => e.statut === "a_verifier").length;
      resume.textContent = extractions.length
        ? extractions.length + " valeur(s) lue(s), dont " + aVerifier + " à vérifier."
        : "Aucune valeur lue pour l'instant. Lancez « Lire les documents ».";
      resume.classList.remove("cache");
      extractions.forEach((e) => liste.appendChild(rxCarte(e, parId[e.document_id])));
    }

    function rxIdsFiables() {
      return rxSynthese ? Object.keys(rxSynthese).filter((id) => rxSynthese[id].niveau === "fiable") : [];
    }

    function rxAfficherLot(synthese) {
      const zone = document.getElementById("rx-lot");
      const texte = document.getElementById("rx-lot-texte");
      const details = document.getElementById("rx-lot-details");
      rxVider(details);
      if (!synthese || (!synthese.items.length && !synthese.nb_deja_confirmees)) { zone.classList.add("cache"); return; }
      zone.classList.remove("cache");
      texte.textContent = synthese.nb_fiables + " valeur(s) fiable(s) prête(s) à être confirmées et reportées sur la fiche ; " +
        synthese.nb_douteuses + " valeur(s) douteuse(s) à confirmer une par une (surlignées ci-dessous).";
      const bouton = document.getElementById("rx-btn-lot");
      bouton.disabled = !rxEcriture() || synthese.nb_fiables === 0;
      if (synthese.a_completer.length) {
        details.appendChild(rxEl("p", "rx-note", "À compléter (non lisible dans les documents) :"));
        const liste = rxEl("ul");
        synthese.a_completer.forEach((c) => liste.appendChild(rxEl("li", "", RX_CHAMPS[c] || c)));
        details.appendChild(liste);
      }
    }

    async function rxToutConfirmer() {
      if (!candidatActifId) { notifier("Choisissez d'abord un étudiant.", false); return; }
      const bouton = document.getElementById("rx-btn-lot");
      bouton.disabled = true;
      bouton.setAttribute("aria-busy", "true");
      const rep = await appelApi(rxUrlCandidat("/extractions/valider-lot"), {
        method: "POST", body: JSON.stringify({ extraction_ids: rxIdsFiables() })
      });
      bouton.removeAttribute("aria-busy");
      if (!rep.ok) {
        notifier((await rxLireDetail(rep)) || "La confirmation en lot a échoué.", false);
        await rxActualiser();
        return;
      }
      const r = await rep.json();
      notifier(r.nb_valides + " valeur(s) confirmée(s), " + r.rapport.appliques.length + " champ(s) de la fiche rempli(s), " +
        r.rapport.conflits.length + " conflit(s) (valeurs déjà saisies conservées), " + r.nb_douteuses_restantes + " à confirmer une par une.", true);
      await rxActualiser();
    }

    async function rxLire() {
      if (!candidatActifId) { notifier("Choisissez d'abord un étudiant.", false); return; }
      const code = document.getElementById("rx-demarche").value;
      const suite = "/extractions/lot" + (code ? "?code_demarche=" + encodeURIComponent(code) : "");
      const rep = await appelApi(rxUrlCandidat(suite), { method: "POST" });
      if (!rep.ok) {
        notifier((await rxLireDetail(rep)) || "La lecture des documents a échoué.", false);
        return;
      }
      const lot = await rep.json();
      rxAfficherAlertes(lot.alertes, lot.completude, lot.erreurs);
      notifier("Lecture terminée : relisez les valeurs proposées.", true);
      await rxActualiser();
    }

    async function rxAppliquer() {
      if (!candidatActifId) { notifier("Choisissez d'abord un étudiant.", false); return; }
      const rep = await appelApi(rxUrlCandidat("/extractions/appliquer"), { method: "POST" });
      if (!rep.ok) {
        notifier((await rxLireDetail(rep)) || "L'application à la fiche a échoué.", false);
        return;
      }
      const r = await rep.json();
      notifier(r.appliques.length + " champ(s) appliqué(s), " + r.conflits.length + " conflit(s) avec la fiche, " +
        r.a_verifier_restants + " valeur(s) encore à vérifier.", true);
      await rxActualiser();
    }

    document.getElementById("rx-btn-actualiser").addEventListener("click", rxActualiser);
    document.getElementById("rx-btn-lire").addEventListener("click", rxLire);
    document.getElementById("rx-btn-appliquer").addEventListener("click", rxAppliquer);
    document.getElementById("rx-btn-lot").addEventListener("click", rxToutConfirmer);
    const allerVersVuePrecedenteRx = allerVersVue;
    allerVersVue = function (cible) {
      allerVersVuePrecedenteRx(cible);
      if (cible === "vue-revue-extractions") rxActualiser();
    };

"""


def _inserer(html: str, marqueur: str, ajout: str, *, avant: bool) -> str:
    if html.count(marqueur) != 1:
        raise RuntimeError("Marqueur d'insertion introuvable ou ambigu : " + marqueur[:60])
    return html.replace(marqueur, ajout + marqueur if avant else marqueur + ajout)


def assembler_revue_extractions(html_base: str) -> str:
    """Insère l'écran de revue dans la page : bouton de menu, section, puis script."""
    html = _inserer(html_base, _MARQUEUR_NAV, HTML_NAV, avant=False)
    html = _inserer(html, _MARQUEUR_FIN_MAIN, HTML_VUE + "\n", avant=True)
    return _inserer(html, _MARQUEUR_JS, JS_REVUE, avant=True)
