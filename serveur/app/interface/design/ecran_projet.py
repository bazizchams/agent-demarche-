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
      #vue-projet-pro .pp-section { display: flex; flex-direction: column; gap: var(--e3); margin: 0 0 var(--e5); }
      #vue-projet-pro .pp-liste { display: flex; flex-direction: column; gap: var(--e3); }
      #vue-projet-pro .pp-entete { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--e2); }
      #vue-projet-pro .pp-entete h4 { margin: 0; overflow-wrap: anywhere; }
      #vue-projet-pro .pp-etiquette { margin: 0; font-size: var(--t-xs); font-weight: 600; letter-spacing: 0.07em; text-transform: uppercase; color: var(--texte-faible); }
      #vue-projet-pro .pp-extrait { margin: 0; padding: var(--e3); background: var(--surface-2); border: 1px solid var(--bord); border-radius: var(--r-m); font-family: var(--police-code); font-size: var(--t-sm); overflow-wrap: anywhere; white-space: pre-wrap; }
      #vue-projet-pro .pp-actions { display: flex; flex-wrap: wrap; gap: var(--e2); }
      #vue-projet-pro .pp-actions .btn, #vue-projet-pro .page-actions .btn { margin: 0; }
      #vue-projet-pro .pp-alerte { margin: 0; padding: var(--e3); background: var(--alerte-doux); color: var(--alerte-texte); border-left: 4px solid var(--alerte); border-radius: var(--r-s) var(--r-m) var(--r-m) var(--r-s); font-size: var(--t-sm); }
      #vue-projet-pro .pp-bloquant { background: var(--critique-doux); color: var(--critique-texte); border-left-color: var(--critique); }
      #vue-projet-pro .pp-bloquant ul { margin: 0; padding-left: var(--e5); }
      #vue-projet-pro #pp-texte { width: 100%; min-height: 220px; resize: vertical; }
    </style>"""

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
      <p id="pp-resume" class="note cache"></p>
      <div class="pp-section"><h3>Points forts</h3><div id="pp-points" class="pp-liste"></div></div>
      <div class="pp-section">
        <h3>Projet professionnel</h3>
        <p id="pp-statut" class="note"></p>
        <div id="pp-alertes"></div>
        <label class="champ" for="pp-texte">Texte du projet
          <textarea id="pp-texte" maxlength="6000"></textarea>
        </label>
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
      a_verifier: ["À confirmer", "badge-completer"],
      confirme: ["Confirmé", "badge-valide"],
      rejete: ["Rejeté", "badge-refuse"]
    };
    const PP_ALERTES = {
      certificat_expire: "Certificat expiré : ce point ne peut pas être confirmé.",
      validite_non_verifiable: "Validité non vérifiable pour ce type de certificat.",
      date_absente: "Date de passation non lue : validité non vérifiable.",
      date_incoherente: "Date de passation incohérente.",
      type_absent: "Type de certificat non lu : validité non vérifiable.",
      preuve_invalidee: "La pièce n'est plus confirmée : point retiré."
    };
    let ppVersion = null;
    let ppStatut = null;
    let ppTexteCharge = "";

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

    function ppCarte(p) {
      const [libelle, classe] = PP_STATUTS[p.statut] || [p.statut, ""];
      const carte = ppEl("section", "carte");
      const entete = ppEl("div", "pp-entete");
      entete.appendChild(ppEl("h4", "", p.texte));
      entete.appendChild(ppEl("span", "badge " + classe, libelle));
      carte.appendChild(entete);
      carte.appendChild(ppEl("p", "pp-etiquette", "Pièce citée" + (p.page ? " (page " + p.page + ")" : "")));
      carte.appendChild(ppEl("p", "pp-extrait", p.extrait));
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

    function ppAfficherProjet(projet) {
      const zone = document.getElementById("pp-alertes");
      ppVider(zone);
      const texte = document.getElementById("pp-texte");
      const statut = document.getElementById("pp-statut");
      if (!projet) {
        ppVersion = null;
        ppStatut = null;
        ppTexteCharge = "";
        texte.value = "";
        statut.textContent = "Aucun projet pour cet étudiant. Générez un brouillon.";
        return;
      }
      ppVersion = projet.version;
      ppStatut = projet.statut;
      ppTexteCharge = projet.texte;
      texte.value = projet.texte;
      statut.textContent = "Version " + projet.version + " : " + (projet.statut === "valide" ? "validé" : "brouillon") +
        " (" + projet.nb_points_forts_utilises + " point(s) fort(s) confirmé(s) utilisé(s)).";
      if (projet.elements_a_verifier.length) {
        const bloc = ppEl("div", "pp-alerte pp-bloquant");
        bloc.appendChild(ppEl("p", "", "Validation bloquée : à corriger ou vérifier."));
        const liste = ppEl("ul");
        projet.elements_a_verifier.forEach((e) => liste.appendChild(ppEl("li", "", e)));
        bloc.appendChild(liste);
        zone.appendChild(bloc);
      }
    }

    async function ppActualiser() {
      const points = document.getElementById("pp-points");
      const resume = document.getElementById("pp-resume");
      ppVider(points);
      if (!candidatActifId) {
        resume.textContent = "Choisissez d'abord un étudiant dans la liste des étudiants.";
        resume.classList.remove("cache");
        return;
      }
      resume.classList.add("cache");
      const [repPoints, repProjet] = await Promise.all([appelApi(ppUrl("/points-forts")), appelApi(ppUrl("/projet-professionnel"))]);
      if (repPoints.ok) {
        const liste = await repPoints.json();
        if (!liste.length) points.appendChild(ppEl("p", "note", "Aucun point fort. Confirmez des valeurs lues puis calculez."));
        liste.forEach((p) => points.appendChild(ppCarte(p)));
      } else {
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
