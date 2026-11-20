"""Écran « Points forts et projet professionnel » (phases P2 et P3).

- liste des points forts déduits, chacun avec la pièce citée (extrait littéral, page), son statut,
  ses alertes (certificat expiré, validité non vérifiable) et les boutons Confirmer / Rejeter ;
- application du niveau de langue à la fiche, seulement pour un point confirmé ;
- éditeur du projet professionnel : génération, enregistrement, validation. Les marqueurs
  « [À COMPLÉTER » et les éléments à vérifier sont affichés et bloquent la validation (règle 4).

Règles du guide de design : couleurs par `var(--token)` ; JavaScript en nœuds DOM + `textContent`
(jamais d'insertion de HTML), sans console ni stockage navigateur ; aucun antislash dans ce code.
"""

from __future__ import annotations

from app.interface.design.shell import bouton_nav, rendre_icones

_MARQUEUR_NAV = "<!-- nav:validation -->"
_MARQUEUR_FIN_MAIN = "  </main>\n\n  <script>"
_MARQUEUR_JS = "    // Connexion automatique dès l'ouverture de l'interface"

HTML_NAV = "\n      " + bouton_nav("vue-projet-pro", "Points forts et projet", "validation")

STYLE_PROJET = """
    <style>
      #vue-projet-pro .pp-section { display: flex; flex-direction: column; gap: var(--e4); margin: 0 0 var(--e6); }
      #vue-projet-pro .pp-section > h3 { margin: 0; }
      #vue-projet-pro .pp-liste { display: flex; flex-direction: column; gap: var(--e3); }
      #vue-projet-pro .pp-actions { display: flex; flex-wrap: wrap; gap: var(--e2); }
      #vue-projet-pro .pp-actions .btn, #vue-projet-pro .page-actions .btn { margin: 0; }
      #vue-projet-pro #pp-resume .btn { margin: var(--e2) 0 0; }

      /* Bilan : trois compteurs (forme + texte + chiffre) et une barre segmentée */
      #vue-projet-pro .pp-bilan { display: flex; flex-direction: column; gap: var(--e3); padding: var(--e4) var(--e5); background: var(--surface); border: 1px solid var(--bord); border-radius: var(--r-l); box-shadow: var(--ombre-1); }
      #vue-projet-pro .pp-bilan { margin-bottom: var(--e5); }
      #vue-projet-pro .pp-bilan.cache { display: none; }
      #vue-projet-pro .pp-editeur.cache { display: none; }
      #vue-projet-pro .pp-bilan-chiffres { display: flex; flex-wrap: wrap; gap: var(--e2) var(--e5); }
      #vue-projet-pro .pp-bilan-item { display: flex; align-items: center; gap: var(--e2); }
      #vue-projet-pro .pp-bilan-item b { font-family: var(--police-titre); font-size: var(--t-xl); font-weight: 700; line-height: 1; font-variant-numeric: tabular-nums; letter-spacing: -0.02em; }
      #vue-projet-pro .pp-bilan-barre { display: flex; gap: 2px; height: 10px; border-radius: var(--r-pilule); overflow: hidden; background: var(--surface-3); transform-origin: left center; animation: pp-barre var(--mo-dur-4, 600ms) var(--mo-ease-out, var(--courbe)) both; }
      #vue-projet-pro .pp-seg { min-width: 0; transition: flex-grow var(--mo-dur-3, var(--d3)) var(--mo-ease-out, var(--courbe)); }
      #vue-projet-pro .pp-seg-confirme { background: var(--bon); }
      #vue-projet-pro .pp-seg-a_verifier { background: var(--alerte); }
      #vue-projet-pro .pp-seg-rejete { background: var(--critique); }

      /* Carte d'un point fort : le rail et la bordure disent le statut en plus de la couleur */
      #vue-projet-pro .pp-carte { position: relative; display: flex; flex-direction: column; gap: var(--e3); margin: 0; padding: var(--e4) var(--e5); background: var(--surface); border: 1px solid var(--bord-fort); border-radius: var(--r-l); box-shadow: var(--ombre-1); transition: box-shadow var(--mo-dur-2, var(--d2)) var(--courbe), transform var(--mo-dur-2, var(--d2)) var(--courbe); animation: pp-entree var(--mo-dur-3, var(--d3)) var(--mo-ease-out, var(--courbe)) both; animation-delay: calc(var(--i, 0) * 55ms); }
      #vue-projet-pro .pp-carte:hover { box-shadow: var(--ombre-2); transform: translateY(-1px); }
      /* L'état est porté par le badge (forme + texte) ; en plus, le trait de la carte : pointillé = à vérifier, plein = confirmé, fond calme + titre barré = rejeté. */
      #vue-projet-pro .pp-s-a_verifier { border-style: dashed; }
      #vue-projet-pro .pp-s-confirme { border-style: solid; }
      #vue-projet-pro .pp-s-rejete { border-style: solid; border-color: var(--bord); background: var(--surface-2); box-shadow: none; }
      #vue-projet-pro .pp-s-rejete .pp-titre { text-decoration: line-through; text-decoration-thickness: 1px; color: var(--texte-doux); }
      #vue-projet-pro .pp-entete { display: flex; flex-wrap: wrap; align-items: flex-start; justify-content: space-between; gap: var(--e2) var(--e3); }
      #vue-projet-pro .pp-titre { margin: 0; font-size: var(--t-md); line-height: 1.3; overflow-wrap: anywhere; flex: 1 1 260px; }
      #vue-projet-pro .pp-source { display: flex; flex-direction: column; gap: var(--e2); padding: var(--e3); background: var(--surface-2); border: 1px solid var(--bord); border-radius: var(--r-m); }
      #vue-projet-pro .pp-source-tete { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e2); font-size: var(--t-xs); font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--texte-faible); }
      #vue-projet-pro .pp-source-tete .ico { width: 16px; height: 16px; color: var(--accent); }
      #vue-projet-pro .pp-source-nom { text-transform: none; letter-spacing: 0; font-size: var(--t-sm); color: var(--texte); font-weight: 600; overflow-wrap: anywhere; }
      #vue-projet-pro .pp-page { padding: 1px 8px; border-radius: var(--r-pilule); background: var(--surface); box-shadow: inset 0 0 0 1px var(--bord-fort); color: var(--texte-doux); text-transform: none; letter-spacing: 0; }
      #vue-projet-pro .pp-extrait { margin: 0; padding: 0 0 0 var(--e3); border-left: 3px solid var(--accent-moyen); font-family: var(--police-code); font-size: var(--t-sm); color: var(--texte); overflow-wrap: anywhere; white-space: pre-wrap; }
      #vue-projet-pro .pp-alerte { display: flex; gap: var(--e2); align-items: flex-start; margin: 0; padding: var(--e3); background: var(--alerte-doux); color: var(--alerte-texte); border-left: 4px solid var(--alerte); border-radius: var(--r-s) var(--r-m) var(--r-m) var(--r-s); font-size: var(--t-sm); }
      #vue-projet-pro .pp-alerte .ico { width: 18px; height: 18px; margin-top: 1px; flex: none; }
      #vue-projet-pro .pp-bloquant { background: var(--critique-doux); color: var(--critique-texte); border-left-color: var(--critique); }
      #vue-projet-pro .pp-bloquant ul { margin: var(--e1) 0 0; padding-left: var(--e5); }
      #vue-projet-pro .pp-bloquant p { margin: 0; }
      #vue-projet-pro .pp-bloquant .btn { margin: var(--e2) 0 0; }

      /* Éditeur : texte transparent par-dessus un miroir où les marqueurs sont surlignés */
      #vue-projet-pro .pp-editeur { position: relative; background: var(--surface); border-radius: var(--r-m); }
      #vue-projet-pro .pp-miroir, #vue-projet-pro #pp-texte { box-sizing: border-box; width: 100%; min-height: 260px; margin: 0; padding: var(--e3) var(--e4); font-family: var(--police-texte); font-size: var(--t-base); line-height: 1.6; letter-spacing: normal; white-space: pre-wrap; overflow-wrap: anywhere; word-break: normal; overflow-y: scroll; border: 1px solid transparent; }
      #vue-projet-pro .pp-miroir { position: absolute; top: 0; left: 0; right: 0; bottom: 0; height: 100%; color: transparent; pointer-events: none; overflow: hidden; }
      #vue-projet-pro #pp-texte { position: relative; display: block; resize: vertical; background: transparent; }
      #vue-projet-pro .pp-miroir mark { color: transparent; background: var(--alerte-doux); border-radius: 3px; box-shadow: 0 0 0 2px var(--alerte-doux), 0 2px 0 0 var(--alerte); }
      #vue-projet-pro .pp-marqueurs { display: flex; flex-direction: column; gap: var(--e2); }
      #vue-projet-pro .pp-statut-ligne { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e2); }
      #vue-projet-pro .pp-statut-ligne .note { margin: 0; }
      #vue-projet-pro .pp-statut-ligne .badge.cache { display: none; }
      #vue-projet-pro #pp-confirmation { flex-direction: column; }
      #vue-projet-pro #pp-confirmation.cache { display: none; }
      #vue-projet-pro .pp-vide.cache { display: none; }
      @keyframes pp-entree { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
      @keyframes pp-barre { from { transform: scaleX(0); } to { transform: scaleX(1); } }
      @media (max-width: 760px) {
        #vue-projet-pro .pp-carte { padding: var(--e4); }
        #vue-projet-pro .pp-bilan { padding: var(--e4); }
      }
      @media (prefers-reduced-motion: reduce) {
        #vue-projet-pro .pp-carte, #vue-projet-pro .pp-bilan-barre { animation: none; }
        #vue-projet-pro .pp-carte, #vue-projet-pro .pp-seg { transition: none; }
        #vue-projet-pro .pp-carte:hover { transform: none; }
      }
    </style>"""

_ILLU_PROJET = (
    '<svg class="etat-vide-illu" viewBox="0 0 96 72" aria-hidden="true" focusable="false">'
    '<rect class="illu-fond" x="6" y="12" width="84" height="54" rx="10"/>'
    '<rect class="illu-papier" x="18" y="6" width="52" height="46" rx="6"/>'
    '<path class="illu-trait" d="M26 18h36M26 26h36M26 34h20"/>'
    '<path class="illu-accent" d="M60 58l3-11 17-17a4 4 0 0 1 6 6L69 53z"/>'
    '<path class="illu-coche" d="M63 47l6 6"/></svg>'
)
_ILLU_ETUDIANT = (
    '<svg class="etat-vide-illu" viewBox="0 0 96 72" aria-hidden="true" focusable="false">'
    '<rect class="illu-fond" x="6" y="12" width="84" height="54" rx="10"/>'
    '<circle class="illu-papier" cx="48" cy="30" r="14"/>'
    '<path class="illu-papier" d="M22 62c0-12 11-20 26-20s26 8 26 20z"/>'
    '<circle class="illu-accent" cx="72" cy="22" r="10"/>'
    '<path class="illu-coche" d="M72 17v10M67 22h10"/></svg>'
)

HTML_VUE = rendre_icones(
    """
    <!-- Points forts et projet professionnel (phases P2 et P3) -->
    <section id="vue-projet-pro" class="vue-ecran cache">"""
    + STYLE_PROJET
    + """
      <header class="page-entete">
        <div>
          <h2>Points forts et projet professionnel</h2>
          <p class="lead">Chaque point fort cite la pièce d'où il vient. Confirmez-le avant qu'il serve au projet.</p>
        </div>
        <div class="page-actions">
          <button id="pp-btn-calculer" class="btn btn-primaire" type="button">[[i:actualiser]]Calculer les points forts</button>
        </div>
      </header>
      <div class="banniere-regle">
        Seules les valeurs lues que vous avez confirmées servent aux déductions. Rien n'est inventé : un
        projet avec un marqueur « À COMPLÉTER » ou un élément à vérifier ne peut pas être validé.
      </div>
      <div id="pp-resume" class="etat-vide carte carte-sobre cache">"""
    + _ILLU_ETUDIANT
    + """<strong>Aucun étudiant choisi.</strong><span>Choisissez d'abord un étudiant dans la liste des étudiants.</span>
        <button class="btn btn-secondaire btn-sm" type="button" data-aller-vers="vue-etudiants">[[i:etudiants]]Choisir un étudiant</button>
      </div>
      <div id="pp-bilan" class="pp-bilan cache" role="group" aria-label="Bilan des points forts"></div>
      <div class="pp-section"><h3>Points forts</h3><div id="pp-points" class="pp-liste"></div></div>
      <div class="pp-section">
        <h3>Projet professionnel</h3>
        <div class="pp-statut-ligne"><span id="pp-statut-badge" class="badge badge-nu cache"></span><p id="pp-statut" class="note"></p></div>
        <div id="pp-projet-vide" class="etat-vide carte carte-sobre pp-vide cache">"""
    + _ILLU_PROJET
    + """<strong>Aucun projet pour cet étudiant.</strong><span>Générez un brouillon : il reprend les points forts confirmés et marque en « À COMPLÉTER » ce que vous devez rédiger.</span></div>
        <div id="pp-alertes"></div>
        <div id="pp-marqueurs" class="pp-marqueurs"></div>
        <div id="pp-editeur" class="pp-editeur">
          <div id="pp-miroir" class="pp-miroir" aria-hidden="true"></div>
          <label class="sr-only" for="pp-texte">Texte du projet</label>
          <textarea id="pp-texte" maxlength="6000" placeholder="Le texte du projet apparaîtra ici."></textarea>
        </div>
        <div id="pp-confirmation" class="pp-alerte cache" role="alertdialog" aria-labelledby="pp-confirmation-titre">
          <p id="pp-confirmation-titre"></p>
          <div class="pp-actions">
            <button id="pp-btn-confirmer-remplacement" class="btn btn-danger" type="button">Remplacer le texte</button>
            <button id="pp-btn-annuler-remplacement" class="btn btn-contour" type="button">Annuler</button>
          </div>
        </div>
        <div class="pp-actions">
          <button id="pp-btn-generer" class="btn btn-secondaire" type="button">Générer un brouillon</button>
          <button id="pp-btn-enregistrer" class="btn btn-contour" type="button">Enregistrer</button>
          <button id="pp-btn-valider" class="btn btn-primaire" type="button">[[i:coche]]Valider le projet</button>
        </div>
      </div>
    </section>
"""
)

JS_PROJET = """
    // =======================================================================
    // Points forts (pièce citée) et projet professionnel. Tout contenu passe par textContent.
    // =======================================================================
    const PP_STATUTS = {
      a_verifier: ["À vérifier", "badge-completer"],
      confirme: ["Confirmé", "badge-valide"],
      rejete: ["Rejeté", "badge-refuse"]
    };
    const PP_ORDRE_STATUTS = ["confirme", "a_verifier", "rejete"];
    const PP_ALERTES = {
      certificat_expire: "Certificat expiré : ce point ne peut pas être confirmé.",
      validite_non_verifiable: "Validité non vérifiable pour ce type de certificat.",
      date_absente: "Date de passation non lue : validité non vérifiable.",
      date_incoherente: "Date de passation incohérente.",
      type_absent: "Type de certificat non lu : validité non vérifiable.",
      preuve_invalidee: "La pièce n'est plus confirmée : point retiré."
    };
    const PP_MARQUEUR_DEBUT = "[à compléter";
    const PP_MARQUEUR_FIN = "]";
    const PP_LONGUEUR_CHIP = 56;
    const PP_ESPACE_SVG = "http://www.w3.org/2000/svg";
    let ppVersion = null;
    let ppStatut = null;
    let ppTexteCharge = "";
    let ppPieces = {};
    let ppElementsAVerifier = [];

    function ppEcriture() {
      return roleActif === "administrateur" || roleActif === "employe";
    }
    function ppEl(balise, classe, texte) {
      const el = document.createElement(balise);
      if (classe) el.className = classe;
      if (texte !== undefined) el.textContent = texte;
      return el;
    }
    function ppVider(el) {
      while (el.firstChild) el.removeChild(el.firstChild);
    }
    function ppIconeDocument() {
      const svg = document.createElementNS(PP_ESPACE_SVG, "svg");
      svg.setAttribute("class", "ico");
      svg.setAttribute("viewBox", "0 0 24 24");
      svg.setAttribute("aria-hidden", "true");
      svg.setAttribute("focusable", "false");
      ["M6 3h8l4 4v14H6z", "M14 3v4h4", "M9 13h6M9 17h6"].forEach((d) => {
        const chemin = document.createElementNS(PP_ESPACE_SVG, "path");
        chemin.setAttribute("d", d);
        svg.appendChild(chemin);
      });
      return svg;
    }
    function ppUrl(suite) {
      return "/api/v1/candidats/" + encodeURIComponent(candidatActifId) + suite;
    }
    async function ppDetail(rep) {
      try {
        const corps = await rep.json();
        return corps && typeof corps.detail === "string" ? corps.detail : null;
      } catch (e) {
        return null;
      }
    }
    function ppBouton(texte, classe, auClic) {
      const b = ppEl("button", "btn btn-sm " + classe, texte);
      b.type = "button";
      b.addEventListener("click", auClic);
      return b;
    }
    async function ppAction(suite, options, messageOk) {
      const rep = await appelApi(ppUrl(suite), options);
      if (rep.ok) {
        notifier(messageOk, true);
      } else {
        notifier((await ppDetail(rep)) || "Action impossible.", false);
      }
      await ppActualiser();
    }

    // Pièces du dossier : sert seulement à nommer la pièce source (repli : « Pièce du dossier »).
    async function ppChargerPieces() {
      ppPieces = {};
      try {
        const rep = await appelApi(ppUrl("/documents"));
        if (!rep.ok) return;
        (await rep.json()).forEach((d) => { ppPieces[d.id] = d; });
      } catch (e) {
        ppPieces = {};
      }
    }
    function ppNomPiece(documentId) {
      const d = ppPieces[documentId];
      if (!d) return "Pièce du dossier";
      const type = typeof LIBELLES_PIECES_FR !== "undefined" && LIBELLES_PIECES_FR[d.type_piece] ? LIBELLES_PIECES_FR[d.type_piece] : d.type_piece;
      return type + " · " + d.nom_fichier_origine;
    }

    function ppCarte(p, rang) {
      const [libelle, classe] = PP_STATUTS[p.statut] || [p.statut, ""];
      const carte = ppEl("section", "pp-carte pp-s-" + p.statut);
      carte.style.setProperty("--i", String(Math.min(rang, 8)));
      const entete = ppEl("div", "pp-entete");
      entete.appendChild(ppEl("h4", "pp-titre", p.texte));
      entete.appendChild(ppEl("span", "badge " + classe, libelle));
      carte.appendChild(entete);
      const source = ppEl("div", "pp-source");
      const tete = ppEl("div", "pp-source-tete");
      tete.appendChild(ppIconeDocument());
      tete.appendChild(ppEl("span", "", "Pièce source"));
      tete.appendChild(ppEl("span", "pp-source-nom", ppNomPiece(p.document_id)));
      if (p.page) tete.appendChild(ppEl("span", "pp-page", "page " + p.page));
      source.appendChild(tete);
      source.appendChild(ppEl("p", "pp-extrait", p.extrait));
      carte.appendChild(source);
      if (p.alerte) carte.appendChild(ppEl("p", "pp-alerte", PP_ALERTES[p.alerte] || "Alerte : " + p.alerte));
      if (p.applique_le) carte.appendChild(ppEl("p", "note", "Niveau appliqué à la fiche."));
      if (ppEcriture()) {
        const actions = ppEl("div", "pp-actions");
        if (p.statut !== "confirme") {
          actions.appendChild(ppBouton("Confirmer", "btn-primaire", () =>
            ppAction("/points-forts/" + encodeURIComponent(p.id) + "/confirmer", { method: "POST" }, "Point fort confirmé.")));
        }
        if (p.statut !== "rejete") {
          actions.appendChild(ppBouton("Rejeter", "btn-danger", () =>
            ppAction("/points-forts/" + encodeURIComponent(p.id) + "/rejeter", { method: "POST" }, "Point fort rejeté.")));
        }
        if (p.statut === "confirme" && p.champ_fiche && !p.applique_le) {
          actions.appendChild(ppBouton("Appliquer le niveau à la fiche", "btn-contour", () =>
            ppAction("/points-forts/" + encodeURIComponent(p.id) + "/appliquer-niveau", { method: "POST" }, "Niveau appliqué à la fiche.")));
        }
        carte.appendChild(actions);
      }
      return carte;
    }

    // Bilan chiffré (données réelles de la liste) : compteurs avec forme et texte, barre segmentée.
    function ppAfficherBilan(liste) {
      const zone = document.getElementById("pp-bilan");
      ppVider(zone);
      if (!liste.length) { zone.classList.add("cache"); return; }
      zone.classList.remove("cache");
      const chiffres = ppEl("div", "pp-bilan-chiffres");
      const barre = ppEl("div", "pp-bilan-barre");
      barre.setAttribute("aria-hidden", "true");
      PP_ORDRE_STATUTS.forEach((statut) => {
        const n = liste.filter((p) => p.statut === statut).length;
        const [libelle, classe] = PP_STATUTS[statut];
        const item = ppEl("div", "pp-bilan-item");
        item.appendChild(ppEl("b", "", String(n)));
        item.appendChild(ppEl("span", "badge " + classe, libelle));
        chiffres.appendChild(item);
        const seg = ppEl("span", "pp-seg pp-seg-" + statut);
        seg.style.flexGrow = String(n);
        seg.style.flexBasis = "0";
        barre.appendChild(seg);
      });
      zone.appendChild(chiffres);
      zone.appendChild(barre);
    }

    function ppSqueletteCartes(zone) {
      ppVider(zone);
      zone.setAttribute("aria-busy", "true");
      for (let i = 0; i < 2; i += 1) {
        const c = ppEl("div", "pp-carte");
        c.setAttribute("aria-hidden", "true");
        c.appendChild(ppEl("span", "squelette squelette-titre"));
        c.appendChild(ppEl("span", "squelette squelette-texte"));
        c.appendChild(ppEl("span", "squelette squelette-texte court"));
        zone.appendChild(c);
      }
    }

    function ppEtatVidePoints() {
      const vide = ppEl("div", "etat-vide carte carte-sobre");
      const svg = document.createElementNS(PP_ESPACE_SVG, "svg");
      svg.setAttribute("class", "etat-vide-illu");
      svg.setAttribute("viewBox", "0 0 96 72");
      svg.setAttribute("aria-hidden", "true");
      svg.setAttribute("focusable", "false");
      [["rect", { class: "illu-fond", x: "6", y: "14", width: "84", height: "52", rx: "10" }],
        ["rect", { class: "illu-papier", x: "20", y: "6", width: "44", height: "42", rx: "6" }],
        ["path", { class: "illu-trait", d: "M28 18h22M28 26h28M28 34h14" }],
        ["circle", { class: "illu-accent", cx: "68", cy: "48", r: "15" }],
        ["path", { class: "illu-coche", d: "M68 41l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.8-5.2 2.8 1-5.8-4.3-4.1 5.9-.9z" }]
      ].forEach((def) => {
        const n = document.createElementNS(PP_ESPACE_SVG, def[0]);
        Object.keys(def[1]).forEach((k) => n.setAttribute(k, def[1][k]));
        svg.appendChild(n);
      });
      vide.appendChild(svg);
      vide.appendChild(ppEl("strong", "", "Aucun point fort pour l'instant."));
      vide.appendChild(ppEl("span", "", "Confirmez d'abord les valeurs lues dans les pièces, puis calculez : chaque point fort apparaîtra ici avec sa pièce source."));
      if (ppEcriture()) {
        vide.appendChild(ppBouton("Calculer les points forts", "btn-secondaire", () => document.getElementById("pp-btn-calculer").click()));
      }
      return vide;
    }

    // Marqueurs « [À COMPLÉTER ... ] » : positions dans le texte (comparaison sans casse).
    function ppTrouverMarqueurs(texte) {
      const bas = texte.toLowerCase();
      const trouves = [];
      let depart = 0;
      while (depart < bas.length) {
        const debut = bas.indexOf(PP_MARQUEUR_DEBUT, depart);
        if (debut === -1) break;
        const fermeture = bas.indexOf(PP_MARQUEUR_FIN, debut);
        const fin = fermeture === -1 ? bas.length : fermeture + 1;
        trouves.push({ debut: debut, fin: fin });
        depart = fin;
      }
      return trouves;
    }

    function ppMajMiroir() {
      const texte = document.getElementById("pp-texte").value;
      const miroir = document.getElementById("pp-miroir");
      ppVider(miroir);
      let curseur = 0;
      ppTrouverMarqueurs(texte).forEach((m) => {
        if (m.debut > curseur) miroir.appendChild(document.createTextNode(texte.slice(curseur, m.debut)));
        miroir.appendChild(ppEl("mark", "", texte.slice(m.debut, m.fin)));
        curseur = m.fin;
      });
      miroir.appendChild(document.createTextNode(texte.slice(curseur) + " "));
      miroir.scrollTop = document.getElementById("pp-texte").scrollTop;
    }

    function ppSelectionner(m) {
      const zone = document.getElementById("pp-texte");
      zone.focus();
      zone.setSelectionRange(m.debut, m.fin);
    }

    function ppAccorder(n, singulier, pluriel) {
      return n + " " + (n > 1 ? pluriel : singulier);
    }

    // Un seul bloc d'alerte : passages « À COMPLÉTER » (surlignés dans le texte) et autres éléments à vérifier.
    function ppMajMarqueurs() {
      const zone = document.getElementById("pp-marqueurs");
      ppVider(zone);
      const texte = document.getElementById("pp-texte").value;
      const marqueurs = ppTrouverMarqueurs(texte);
      ppMajMiroir();
      if (!texte.trim()) return;
      const autres = ppElementsAVerifier.filter((e) => e.toLowerCase().indexOf("marqueur") === -1);
      if (!marqueurs.length && !autres.length) {
        zone.appendChild(ppEl("p", "note", "Aucun passage à compléter : le texte est prêt à être relu."));
        return;
      }
      const bloc = ppEl("div", "pp-alerte pp-bloquant");
      const contenu = ppEl("div");
      const titre = marqueurs.length
        ? ppAccorder(marqueurs.length, "passage à compléter", "passages à compléter")
        : "À corriger ou vérifier";
      contenu.appendChild(ppEl("p", "", titre + " : la validation est bloquée tant qu'il en reste."));
      if (marqueurs.length) contenu.appendChild(ppEl("p", "note", "Ils sont surlignés dans le texte ci-dessous."));
      if (autres.length) {
        const liste = ppEl("ul");
        autres.forEach((e) => liste.appendChild(ppEl("li", "", e)));
        contenu.appendChild(liste);
      }
      if (marqueurs.length) {
        const aller = ppEl("button", "btn btn-contour btn-sm", "Aller au premier passage");
        aller.type = "button";
        aller.addEventListener("click", () => ppSelectionner(marqueurs[0]));
        contenu.appendChild(aller);
      }
      bloc.appendChild(contenu);
      zone.appendChild(bloc);
    }

    function ppAfficherProjet(projet) {
      const zone = document.getElementById("pp-alertes");
      ppVider(zone);
      const texte = document.getElementById("pp-texte");
      const statut = document.getElementById("pp-statut");
      const badge = document.getElementById("pp-statut-badge");
      const vide = document.getElementById("pp-projet-vide");
      if (!projet) {
        ppVersion = null;
        ppStatut = null;
        ppTexteCharge = "";
        ppElementsAVerifier = [];
        texte.value = "";
        statut.textContent = "";
        badge.classList.add("cache");
        vide.classList.remove("cache");
        document.getElementById("pp-editeur").classList.add("cache");
        ppMajMarqueurs();
        return;
      }
      vide.classList.add("cache");
      document.getElementById("pp-editeur").classList.remove("cache");
      ppVersion = projet.version;
      ppStatut = projet.statut;
      ppTexteCharge = projet.texte;
      texte.value = projet.texte;
      const valide = projet.statut === "valide";
      badge.className = "badge " + (valide ? "badge-valide" : "badge-brouillon");
      badge.textContent = valide ? "Validé" : "Brouillon";
      statut.textContent = "Version " + projet.version + " : " + (valide ? "validé" : "brouillon") +
        " (" + (projet.nb_points_forts_utilises === 0 ? "aucun point fort confirmé utilisé" : projet.nb_points_forts_utilises === 1 ? "1 point fort confirmé utilisé" : projet.nb_points_forts_utilises + " points forts confirmés utilisés") + ").";
      ppElementsAVerifier = projet.elements_a_verifier || [];
      ppMajMarqueurs();
    }

    async function ppActualiser() {
      const points = document.getElementById("pp-points");
      const resume = document.getElementById("pp-resume");
      ppVider(points);
      if (!candidatActifId) {
        document.getElementById("pp-bilan").classList.add("cache");
        resume.classList.remove("cache");
        return;
      }
      resume.classList.add("cache");
      ppSqueletteCartes(points);
      const [repPoints, repProjet] = await Promise.all([appelApi(ppUrl("/points-forts")), appelApi(ppUrl("/projet-professionnel")), ppChargerPieces()]);
      ppVider(points);
      points.setAttribute("aria-busy", "false");
      if (repPoints.ok) {
        const liste = await repPoints.json();
        ppAfficherBilan(liste);
        if (!liste.length) points.appendChild(ppEtatVidePoints());
        liste.forEach((p, rang) => points.appendChild(ppCarte(p, rang)));
      } else {
        ppAfficherBilan([]);
        notifier((await ppDetail(repPoints)) || "Impossible de charger les points forts.", false);
      }
      if (repProjet.ok) {
        ppAfficherProjet(await repProjet.json());
      } else if (repProjet.status === 404) {
        ppAfficherProjet(null);
      } else {
        notifier((await ppDetail(repProjet)) || "Impossible de charger le projet professionnel.", false);
      }
    }

    function ppCorps(objet) {
      return { method: "POST", body: JSON.stringify(objet) };
    }
    document.getElementById("pp-texte").addEventListener("input", ppMajMarqueurs);
    document.getElementById("pp-texte").addEventListener("scroll", () => {
      document.getElementById("pp-miroir").scrollTop = document.getElementById("pp-texte").scrollTop;
    });
    document.getElementById("pp-btn-calculer").addEventListener("click", () => {
      if (!candidatActifId) { notifier("Choisissez d'abord un étudiant.", false); return; }
      ppAction("/deductions/calculer", { method: "POST" }, "Points forts calculés : confirmez-les un par un.");
    });
    function ppMasquerConfirmation() {
      document.getElementById("pp-confirmation").classList.add("cache");
    }
    function ppGenerer(remplacerValide) {
      ppMasquerConfirmation();
      const existe = ppVersion !== null;
      ppAction("/projet-professionnel/generer",
        ppCorps({ remplacer: existe, remplacer_valide: remplacerValide }), "Brouillon généré : relisez-le.");
    }
    document.getElementById("pp-btn-generer").addEventListener("click", () => {
      if (!candidatActifId) { notifier("Choisissez d'abord un étudiant.", false); return; }
      if (ppVersion === null) { ppGenerer(false); return; }
      const valide = ppStatut === "valide";
      const edite = document.getElementById("pp-texte").value.trim() !== ppTexteCharge.trim();
      const message = valide
        ? "Ce projet est VALIDÉ. Générer un nouveau brouillon le remplace et annule la validation."
        : edite
          ? "Le texte contient des modifications non enregistrées. Générer un brouillon les écrase."
          : "Générer un nouveau brouillon remplace le texte actuel.";
      document.getElementById("pp-confirmation-titre").textContent = message;
      document.getElementById("pp-btn-confirmer-remplacement").onclick = () => ppGenerer(valide);
      document.getElementById("pp-confirmation").classList.remove("cache");
    });
    document.getElementById("pp-btn-annuler-remplacement").addEventListener("click", ppMasquerConfirmation);
    document.getElementById("pp-btn-enregistrer").addEventListener("click", () => {
      const texte = document.getElementById("pp-texte").value.trim();
      if (!candidatActifId || ppVersion === null || !texte) { notifier("Rien à enregistrer.", false); return; }
      ppAction("/projet-professionnel", { method: "PUT", body: JSON.stringify({ texte: texte, version: ppVersion }) }, "Projet enregistré.");
    });
    document.getElementById("pp-btn-valider").addEventListener("click", async () => {
      if (!candidatActifId || ppVersion === null) { notifier("Aucun projet à valider.", false); return; }
      let version = ppVersion;
      const texte = document.getElementById("pp-texte").value.trim();
      if (texte !== ppTexteCharge.trim()) {
        if (!texte) { notifier("Le texte est vide : rien à valider.", false); return; }
        const rep = await appelApi(ppUrl("/projet-professionnel"), { method: "PUT", body: JSON.stringify({ texte: texte, version: version }) });
        if (!rep.ok) {
          notifier((await ppDetail(rep)) || "Enregistrement impossible : projet non validé.", false);
          await ppActualiser();
          return;
        }
        version = (await rep.json()).version;
      }
      ppAction("/projet-professionnel/valider", ppCorps({ version: version }), "Projet validé.");
    });
    const allerVersVuePrecedentePp = allerVersVue;
    allerVersVue = function (cible) {
      allerVersVuePrecedentePp(cible);
      if (cible === "vue-projet-pro") ppActualiser();
    };

"""
def _inserer(html: str, marqueur: str, ajout: str, *, avant: bool) -> str:
    if html.count(marqueur) != 1:
        raise RuntimeError("Marqueur d'insertion introuvable ou ambigu : " + marqueur[:60])
    return html.replace(marqueur, ajout + marqueur if avant else marqueur + ajout)


def assembler_projet(html_base: str) -> str:
    """Insère l'écran dans la page : bouton de menu, section, puis script."""
    html = _inserer(html_base, _MARQUEUR_NAV, HTML_NAV, avant=False)
    html = _inserer(html, _MARQUEUR_FIN_MAIN, HTML_VUE + "\n", avant=True)
    return _inserer(html, _MARQUEUR_JS, JS_PROJET, avant=True)
