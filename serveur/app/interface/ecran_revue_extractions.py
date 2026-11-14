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
      #vue-revue-extractions .rx-image { max-width: 100%; max-height: 260px; object-fit: contain; border: 1px solid var(--bord); border-radius: var(--r-m); background: var(--surface-2); }
      #vue-revue-extractions .rx-valeur { margin: 0; font-size: var(--t-lg); font-weight: 600; color: var(--texte); overflow-wrap: anywhere; font-variant-numeric: tabular-nums; }
      #vue-revue-extractions .rx-note { margin: 0; font-size: var(--t-sm); color: var(--texte-doux); overflow-wrap: anywhere; }
      #vue-revue-extractions .rx-actions { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e2); }
      #vue-revue-extractions .rx-actions .btn { margin: 0; }
      #vue-revue-extractions .rx-correction { display: flex; flex-wrap: wrap; align-items: flex-end; gap: var(--e2); }
      #vue-revue-extractions .rx-correction .btn { margin: 0; }
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
        Rien n'est écrit sur la fiche sans votre confirmation. Une valeur douteuse reste « à vérifier »
        et n'est jamais appliquée ; un champ illisible reste vide (Règle 4). Une valeur déjà saisie sur
        la fiche n'est jamais écrasée.
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
      niveau_francais: "Niveau de français", niveau_anglais: "Niveau d'anglais", ielts_bande: "Note IELTS"
    };
    const RX_STATUTS = {
      auto: ["Lu automatiquement", "badge-info"],
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
      img.alt = "Image du document source";
      conteneur.appendChild(img);
    }

    function rxLibelleMotif(motif) {
      return motif ? (RX_MOTIFS[motif] || "Motif : " + motif) : "";
    }

    async function rxDecider(extraction, action, valeur) {
      const options = { method: "POST" };
      if (action === "corriger") options.body = JSON.stringify({ valeur: valeur });
      const rep = await appelApi(rxUrlCandidat("/extractions/" + encodeURIComponent(extraction.id) + "/" + action), options);
      if (rep.ok) {
        notifier(action === "rejeter" ? "Valeur rejetée." : "Valeur confirmée : elle pourra être appliquée à la fiche.", true);
      } else {
        notifier((await rxLireDetail(rep)) || "Action impossible sur cette valeur.", false);
      }
      await rxActualiser();
    }

    function rxBoutonAction(texte, classe, auClic) {
      const b = rxEl("button", "btn btn-sm " + classe, texte);
      b.type = "button";
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
      const carte = rxEl("section", "carte");
      const entete = rxEl("div", "rx-carte-entete");
      entete.appendChild(rxEl("h4", "", RX_CHAMPS[extraction.champ] || extraction.champ));
      entete.appendChild(rxEl("span", "badge " + classeStatut, libelleStatut));
      carte.appendChild(entete);

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
      const zoneCorrection = rxEl("div", "rx-correction");
      if (rxEcriture()) {
        const actions = rxEl("div", "rx-actions");
        if (extraction.statut !== "valide_humain") {
          actions.appendChild(rxBoutonAction("Confirmer", "btn-primaire", () => rxDecider(extraction, "valider")));
        }
        actions.appendChild(rxBoutonAction("Corriger", "btn-contour", () => rxAfficherCorrection(zoneCorrection, extraction)));
        if (extraction.statut !== "rejete") {
          actions.appendChild(rxBoutonAction("Rejeter", "btn-danger", () => rxDecider(extraction, "rejeter")));
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

    async function rxActualiser() {
      const liste = document.getElementById("rx-liste");
      const resume = document.getElementById("rx-resume");
      rxVider(liste);
      if (!candidatActifId) {
        resume.textContent = "Choisissez d'abord un étudiant dans la liste des étudiants.";
        resume.classList.remove("cache");
        return;
      }
      const [repDocs, repExtr] = await Promise.all([
        appelApi(rxUrlCandidat("/documents")), appelApi(rxUrlCandidat("/extractions"))
      ]);
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
