"""Écran d'accueil : chiffres clés animés, santé du portefeuille, actions humaines, échéances.

Alimenté par les routes existantes (candidats, centre de validation, récapitulatifs, agents, et le
journal d'audit pour les administrateurs) via `rafraichirTableauDeBord` qui appelle `accueilAfficher`.
Tout l'affichage passe par des nœuds DOM et `textContent` : aucune donnée n'est interprétée comme
du HTML. Aucun antislash. Tous les chiffres viennent de l'API : jamais de valeur inventée (sans
donnée, le visuel reste vide et affiche « — »).

Mouvement : animations CSS propres à l'écran (préfixe `.tb-`), qui reprennent les jetons du contrat
`--mo-*` s'ils existent (repli sur `--d*` / `--courbe`) ; `window.Mouvement.reduit` est consulté s'il
est présent. Sous `prefers-reduced-motion`, plus aucune animation : les valeurs s'affichent d'emblée.
Ce module apporte aussi l'enrichissement de la fiche du dossier actif (écran Étudiants), observé
sur `#fiche-active-corps`.
"""

from __future__ import annotations

_LIGNE_SQUELETTE_ACTION = (
    '<li class="ligne-squelette" aria-hidden="true"><span class="squelette squelette-pastille"></span>'
    '<span class="squelette-pile"><span class="squelette squelette-texte"></span>'
    '<span class="squelette squelette-texte court"></span></span></li>'
)
_LIGNE_SQUELETTE_ECHEANCE = (
    '<li class="ligne-squelette" aria-hidden="true"><span class="squelette squelette-carre"></span>'
    '<span class="squelette-pile"><span class="squelette squelette-texte"></span>'
    '<span class="squelette squelette-texte court"></span></span></li>'
)
_VALEUR_SQUELETTE = '<span class="squelette squelette-valeur" aria-hidden="true"></span>'

_RAYON_JAUGE = 50

CSS_ACCUEIL = """
    <style>
      /* Accueil : mouvement et finitions (tokens uniquement ; repli sur les durées de la coquille). */
      #vue-tableau-bord { --tb-dur: var(--mo-dur-3, var(--d3)); --tb-ease: var(--mo-ease-out, var(--courbe)); }
      #vue-tableau-bord .tb-in { animation: tb-entree var(--tb-dur) var(--tb-ease) both; animation-delay: calc(var(--i, 0) * 60ms); }
      @keyframes tb-entree { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }

      #vue-tableau-bord .tb-date { margin: 0 0 var(--e1); font-size: var(--t-xs); font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--texte-faible); }
      #vue-tableau-bord .tb-date:empty { display: none; }

      /* Chiffres clés */
      #vue-tableau-bord .kpi { position: relative; overflow: hidden; transition: box-shadow var(--d2) var(--courbe), transform var(--d2) var(--courbe), border-color var(--d2) var(--courbe); }
      #vue-tableau-bord .kpi:hover { transform: translateY(-2px); box-shadow: var(--ombre-2); border-color: var(--bord-fort); }
      #vue-tableau-bord .kpi::after { content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 3px; background: var(--accent-moyen); transform: scaleX(0); transform-origin: left; transition: transform var(--tb-dur) var(--tb-ease); }
      #vue-tableau-bord .kpi:hover::after { transform: scaleX(1); }
      #vue-tableau-bord .kpi.kpi-alerte::after { background: var(--alerte); }
      #vue-tableau-bord .kpi .valeur { font-size: var(--t-3xl); }
      #vue-tableau-bord .kpi.kpi-zero .valeur { color: var(--texte-faible); }
      #vue-tableau-bord .kpi.kpi-zero { box-shadow: none; background: var(--surface-2); }
      #vue-tableau-bord .kpi.kpi-actif { border-color: var(--accent-moyen); }
      #vue-tableau-bord .kpi.kpi-actif .valeur { color: var(--accent-fort); }
      #vue-tableau-bord .kpi.kpi-actif.kpi-alerte { border-color: var(--alerte); }
      #vue-tableau-bord .kpi.kpi-actif.kpi-alerte .valeur { color: var(--alerte-texte); }

      /* Santé du portefeuille : jauges et activité */
      #vue-tableau-bord .tb-sante { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr); gap: var(--e4); margin-bottom: var(--e5); align-items: stretch; }
      #vue-tableau-bord .tb-sante .carte { margin: 0; display: flex; flex-direction: column; }
      #vue-tableau-bord .tb-sante-sous { margin: calc(var(--e2) * -1) 0 var(--e4); font-size: var(--t-sm); color: var(--texte-doux); }
      #vue-tableau-bord .tb-jauges { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 104px), 1fr)); gap: var(--e4); }
      #vue-tableau-bord .tb-jauge { display: flex; flex-direction: column; align-items: center; gap: var(--e1); text-align: center; min-width: 0; }
      #vue-tableau-bord .tb-jauge-visuel { position: relative; width: 112px; height: 112px; margin-bottom: var(--e2); }
      #vue-tableau-bord .tb-jauge-visuel svg { width: 100%; height: 100%; display: block; }
      #vue-tableau-bord .tb-jauge-piste { fill: none; stroke: var(--surface-3); stroke-width: 10; }
      #vue-tableau-bord .tb-jauge-valeur { fill: none; stroke: var(--accent-plein); stroke-width: 10; stroke-linecap: round; transition: stroke-dashoffset 900ms var(--tb-ease); }
      #vue-tableau-bord .tb-jauge.j-bon .tb-jauge-valeur { stroke: var(--bon); }
      #vue-tableau-bord .tb-jauge.j-alerte .tb-jauge-valeur { stroke: var(--alerte); }
      #vue-tableau-bord .tb-jauge.j-critique .tb-jauge-valeur { stroke: var(--critique); }
      #vue-tableau-bord .tb-jauge-centre { position: absolute; top: 0; left: 0; right: 0; bottom: 0; display: flex; align-items: center; justify-content: center; font-family: var(--police-titre); font-size: var(--t-xl); font-weight: 700; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; color: var(--texte); }
      #vue-tableau-bord .tb-jauge-centre small { font-size: var(--t-sm); font-weight: 600; color: var(--texte-faible); margin-left: 1px; }
      #vue-tableau-bord .tb-jauge strong { font-size: var(--t-sm); font-weight: 600; min-height: 2.6em; display: flex; align-items: flex-end; }
      #vue-tableau-bord .tb-jauge-detail { font-size: var(--t-xs); color: var(--texte-doux); min-height: 2.8em; }
      #vue-tableau-bord .tb-jauge .badge { margin-top: auto; }

      #vue-tableau-bord .tb-activite-tete { display: flex; align-items: baseline; justify-content: space-between; gap: var(--e3); flex-wrap: wrap; margin-bottom: var(--e2); }
      #vue-tableau-bord .tb-activite-total { font-family: var(--police-titre); font-size: var(--t-2xl); font-weight: 700; line-height: 1; letter-spacing: -0.03em; font-variant-numeric: tabular-nums; }
      #vue-tableau-bord .tb-activite-pic { font-size: var(--t-xs); color: var(--texte-doux); }
      #vue-tableau-bord .tb-spark { display: block; width: 100%; height: auto; overflow: visible; }
      #vue-tableau-bord .tb-spark-base { stroke: var(--bord); stroke-width: 1; }
      #vue-tableau-bord .tb-spark-aire { fill: var(--accent-doux); opacity: 0; transition: opacity 700ms var(--tb-ease) 250ms; }
      #vue-tableau-bord .tb-spark-ligne { fill: none; stroke: var(--accent-plein); stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; stroke-dasharray: 1; stroke-dashoffset: 1; transition: stroke-dashoffset 900ms var(--tb-ease); }
      #vue-tableau-bord .tb-spark-pt { fill: var(--accent-plein); stroke: var(--surface); stroke-width: 2; opacity: 0; transition: opacity var(--d2) var(--courbe) 800ms; }
      #vue-tableau-bord .tb-spark-zone { fill: transparent; }
      #vue-tableau-bord .tb-spark-zone:hover + .tb-spark-pt-survol, #vue-tableau-bord .tb-spark-zone:hover { fill: var(--accent-doux); }
      #vue-tableau-bord .tb-spark.tb-trace-ok .tb-spark-ligne { stroke-dashoffset: 0; }
      #vue-tableau-bord .tb-spark.tb-trace-ok .tb-spark-aire { opacity: 1; }
      #vue-tableau-bord .tb-spark.tb-trace-ok .tb-spark-pt { opacity: 1; }
      #vue-tableau-bord .tb-spark-axe { display: flex; justify-content: space-between; margin-top: var(--e1); font-size: var(--t-xs); color: var(--texte-faible); }
      #vue-tableau-bord .tb-activite-note { margin: var(--e3) 0 0; font-size: var(--t-xs); color: var(--texte-faible); }
      #vue-tableau-bord .tb-activite .etat-vide { padding: var(--e3); }

      #vue-tableau-bord .tb-colonne { display: flex; flex-direction: column; gap: var(--e5); min-width: 0; }
      #vue-tableau-bord .tb-colonne .section-entete { margin: 0; }
      #vue-tableau-bord .tb-colonne .grille-raccourcis { grid-template-columns: repeat(auto-fit, minmax(min(100%, 230px), 1fr)); }
      #vue-tableau-bord .tb-sites { margin-top: var(--e5); }

      /* Lignes d'actions et d'échéances : survol doux, cascade */
      #vue-tableau-bord .ligne-action, #vue-tableau-bord .echeance { margin: 0 calc(var(--e3) * -1); padding-left: var(--e3); padding-right: var(--e3); border-radius: var(--r-m); transition: background-color var(--d1) var(--courbe); }
      #vue-tableau-bord .ligne-action:first-child, #vue-tableau-bord .echeance:first-child { padding-top: var(--e3); }
      #vue-tableau-bord .ligne-action:last-child, #vue-tableau-bord .echeance:last-child { padding-bottom: var(--e3); }
      #vue-tableau-bord .ligne-action:hover, #vue-tableau-bord .echeance:hover { background: var(--surface-2); }
      #vue-tableau-bord .echeance-date.tb-urgent { background: var(--critique-doux); border-color: var(--critique); }
      #vue-tableau-bord .echeance-date.tb-proche { background: var(--alerte-doux); border-color: var(--alerte); }
      #vue-tableau-bord .raccourci:active, #vue-tableau-bord .kpi:active { transform: scale(0.985); }
      #vue-tableau-bord .raccourci { transition: border-color var(--d1) var(--courbe), box-shadow var(--d1) var(--courbe), transform var(--d1) var(--courbe); }

      @media (max-width: 900px) {
        #vue-tableau-bord .tb-sante { grid-template-columns: minmax(0, 1fr); }
      }
      @media (prefers-reduced-motion: reduce) {
        #vue-tableau-bord .tb-in { animation: none; }
        #vue-tableau-bord .kpi, #vue-tableau-bord .kpi::after, #vue-tableau-bord .raccourci, #vue-tableau-bord .tb-jauge-valeur,
        #vue-tableau-bord .tb-spark-ligne, #vue-tableau-bord .tb-spark-aire, #vue-tableau-bord .tb-spark-pt { transition: none; }
        #vue-tableau-bord .kpi:hover, #vue-tableau-bord .kpi:active, #vue-tableau-bord .raccourci:active { transform: none; }
      }
    </style>
"""


def _kpi(identifiant: str, libelle: str, aide: str, rang: int) -> str:
    return (
        f'<div class="kpi tb-in" style="--i:{rang}">'
        f'<div class="kpi-entete"><span>{libelle}</span></div>'
        f'<div id="{identifiant}" class="valeur">{_VALEUR_SQUELETTE}</div>'
        f'<p id="{identifiant}-aide" class="kpi-aide">{aide}</p></div>'
    )


def _jauge(identifiant: str, libelle: str) -> str:
    circonference = 2 * 3.14159265 * _RAYON_JAUGE
    return (
        f'<div id="{identifiant}" class="tb-jauge" role="group" aria-label="{libelle}">'
        '<div class="tb-jauge-visuel">'
        '<svg viewBox="0 0 120 120" aria-hidden="true" focusable="false">'
        f'<circle class="tb-jauge-piste" cx="60" cy="60" r="{_RAYON_JAUGE}"/>'
        f'<circle class="tb-jauge-valeur" cx="60" cy="60" r="{_RAYON_JAUGE}" transform="rotate(-90 60 60)" '
        f'style="stroke-dasharray:{circonference:.2f};stroke-dashoffset:{circonference:.2f}"/>'
        '</svg><div class="tb-jauge-centre">—</div></div>'
        f'<strong>{libelle}</strong><span class="tb-jauge-detail">En attente des données</span>'
        '<span class="badge badge-nu tb-jauge-etat">—</span></div>'
    )


def _raccourci(vue: str, nom_icone: str, titre: str, detail: str, rang: int) -> str:
    return (
        f'<button class="raccourci tb-in" style="--i:{rang}" type="button" data-aller-vers="{vue}">'
        f'<span class="raccourci-icone">[[i:{nom_icone}]]</span>'
        f"<span><strong>{titre}</strong><small>{detail}</small></span>[[i:suivant]]</button>"
    )


HTML_ACCUEIL = (
    CSS_ACCUEIL
    + f"""
    <!-- Tableau de bord : chiffres clés, santé du portefeuille, actions humaines, échéances -->
    <section id="vue-tableau-bord" class="vue-ecran">
      <header class="page-entete">
        <div>
          <p id="accueil-date" class="tb-date"></p>
          <h2>Tableau de bord</h2>
          <p class="lead">Ce qui attend une décision de votre part, puis l'état du bureau.</p>
        </div>
        <div class="page-actions">
          <button class="btn btn-primaire" type="button" data-aller-vers="vue-etudiants" data-ouvrir="carte-nouvel-etudiant">[[i:plus]]Nouvel étudiant</button>
        </div>
      </header>

      <div class="grille-kpi" role="group" aria-label="Chiffres clés du bureau">
        {_kpi("stat-nb-candidats", "Étudiants actifs", "Fiches enregistrées dans votre bureau", 0)}
        {_kpi("stat-nb-a-valider", "Prêts à valider", "Arrêtés avant l'envoi, en attente de votre contrôle", 1)}
        {_kpi("stat-nb-suspendues", "En pause", "Pièce manquante, session expirée ou CAPTCHA", 2)}
        {_kpi("stat-nb-agents", "Postes agents", "Postes de l'agent local enrôlés", 3)}
      </div>

      <div class="tb-sante">
        <section class="carte tb-in" style="--i:4" aria-labelledby="titre-sante">
          <div class="carte-entete">
            <h3 id="titre-sante">Santé du portefeuille</h3>
            <span id="sante-total" class="badge badge-nu">—</span>
          </div>
          <p class="tb-sante-sous">Calculée sur les fiches de votre bureau : rien n'est estimé.</p>
          <div class="tb-jauges">
            {_jauge("jauge-fiches", "Fiches renseignées")}
            {_jauge("jauge-consentements", "Consentements signés")}
            {_jauge("jauge-passeports", "Passeports valides")}
          </div>
        </section>
        <section id="accueil-activite" class="carte tb-activite tb-in" style="--i:5" aria-labelledby="titre-activite">
          <div class="carte-entete">
            <h3 id="titre-activite">Activité du bureau</h3>
          </div>
          <div id="accueil-activite-corps" aria-busy="true">
            <span class="squelette squelette-valeur" aria-hidden="true"></span>
            <span class="squelette squelette-texte" aria-hidden="true"></span>
            <span class="sr-only">Chargement de l'activité</span>
          </div>
        </section>
      </div>

      <div class="accueil-grille">
        <div class="tb-colonne">
        <section class="carte tb-in" style="--i:6" aria-labelledby="titre-a-traiter">
          <div class="carte-entete">
            <h3 id="titre-a-traiter">À traiter maintenant</h3>
            <span id="accueil-total-actions" class="badge badge-nu">—</span>
          </div>
          <ul id="accueil-actions" class="liste-actions" aria-busy="true">
            <li class="sr-only">Chargement de vos dossiers</li>
            {_LIGNE_SQUELETTE_ACTION}
            {_LIGNE_SQUELETTE_ACTION}
            {_LIGNE_SQUELETTE_ACTION}
          </ul>
        </section>

      <div class="section-entete">
        <div>
          <h3>Accès rapides</h3>
          <p>Les tâches les plus fréquentes du bureau.</p>
        </div>
      </div>
      <div class="grille-raccourcis">
        {_raccourci("vue-campus-france", "globe", "Piloter Campus France", "Vœux et pré-remplissage Études en France", 8)}
        {_raccourci("vue-ircc", "envoi", "Piloter IRCC Canada", "Demande de permis d'études", 9)}
        {_raccourci("vue-conseiller", "conseiller", "Calculer un score", "Solidité du dossier et conseils", 10)}
        {_raccourci("vue-documents", "pieces", "Vérifier les pièces", "Pièces manquantes et coffre chiffré", 11)}
      </div>
        </div>

        <section class="carte tb-in" style="--i:7" aria-labelledby="titre-echeances">
          <div class="carte-entete">
            <h3 id="titre-echeances">Échéances proches</h3>
          </div>
          <ul id="accueil-echeances" class="liste-echeances" aria-busy="true">
            <li class="sr-only">Chargement des échéances</li>
            {_LIGNE_SQUELETTE_ECHEANCE}
            {_LIGNE_SQUELETTE_ECHEANCE}
            {_LIGNE_SQUELETTE_ECHEANCE}
          </ul>
          <p class="note carte-pied">Calendrier Campus France Algérie 2026-2027 et passeports qui expirent dans les 6 mois.</p>
        </section>
      </div>


      <p class="titre-mini tb-sites">Sites officiels et pages de simulation (s'ouvrent dans un nouvel onglet)</p>
      <div class="raccourcis">
        <a class="btn btn-contour btn-sm" href="https://etudesenfrance.diplomatie.gouv.fr/" target="_blank" rel="noopener">Études en France [[i:externe]]</a>
        <a class="btn btn-contour btn-sm" href="https://portal-portail.apps.cic.gc.ca/signin?lang=fr" target="_blank" rel="noopener">Portail IRCC Canada [[i:externe]]</a>
        <a class="btn btn-fantome btn-sm" href="/demo/campus-france" target="_blank" rel="noopener">Simulation Études en France [[i:externe]]</a>
        <a class="btn btn-fantome btn-sm" href="/demo/ircc" target="_blank" rel="noopener">Simulation IRCC [[i:externe]]</a>
      </div>
    </section>
"""
)

JS_ACCUEIL = """
    // =======================================================================
    // Accueil : ce qui demande une action humaine, puis les échéances proches.
    // Affichage par nœuds DOM et textContent uniquement (aucune donnée interprétée en HTML).
    // =======================================================================
    const CALENDRIER_CAMPUS_FRANCE = [
      { date: "2026-11-30", libelle: "Campus France : date limite de dépôt et de paiement (hors DAP)" },
      { date: "2026-12-15", libelle: "Campus France : date limite de dépôt et de paiement (DAP)" },
      { date: "2027-03-15", libelle: "Campus France : fin des entretiens" },
      { date: "2027-05-31", libelle: "Campus France : choix définitif des formations" },
    ];
    const SEUIL_PASSEPORT_JOURS = 180;
    const SEUIL_ECHEANCE_CRITIQUE_JOURS = 14;
    const SEUIL_ECHEANCE_ALERTE_JOURS = 45;
    const MAX_LIGNES_ACTIONS = 8;
    const MAX_ECHEANCES = 4;
    const MS_PAR_JOUR = 86400000;
    const MOIS_COURTS_FR = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
    const ESPACE_SVG = "http://www.w3.org/2000/svg";
    const IDS_CHIFFRES_ACCUEIL = ["stat-nb-candidats", "stat-nb-a-valider", "stat-nb-suspendues", "stat-nb-agents"];
    const ACCUEIL_SEUIL_BON = 75;
    const ACCUEIL_SEUIL_ALERTE = 50;
    const ACCUEIL_CIRCONFERENCE = 2 * Math.PI * 50;
    const ACCUEIL_DUREE_COMPTEUR_MS = 800;
    const ACCUEIL_JOURS_ACTIVITE = 14;
    const ACCUEIL_TAILLE_AUDIT = 200;
    const ACCUEIL_SPARK_L = 320;
    const ACCUEIL_SPARK_H = 120;
    const ACCUEIL_SPARK_MARGE = 6;
    // Chiffres clés : texte d'aide quand la valeur est nulle (état vide expliqué) ou non.
    const ACCUEIL_AIDES_CHIFFRES = {
      "stat-nb-candidats": ["Aucun étudiant : ajoutez une première fiche.", "Fiches enregistrées dans votre bureau"],
      "stat-nb-a-valider": ["Aucun dossier prêt : rien n'attend votre contrôle.", "Arrêtés avant l'envoi, en attente de votre contrôle"],
      "stat-nb-suspendues": ["Aucun dossier en pause.", "Pièce manquante, session expirée ou CAPTCHA"],
      "stat-nb-agents": ["Aucun poste enrôlé : l'agent local n'est pas installé.", "Postes de l'agent local enrôlés"],
    };

    function accueilNoeud(balise, classe, texte) {
      const n = document.createElement(balise);
      if (classe) n.className = classe;
      if (texte !== undefined) n.textContent = texte;
      return n;
    }

    function accueilSvg(nom, attributs) {
      const n = document.createElementNS(ESPACE_SVG, nom);
      Object.keys(attributs).forEach((cle) => n.setAttribute(cle, attributs[cle]));
      return n;
    }

    // Mouvement réduit : préférence système, ou indication du module partagé s'il est présent.
    function accueilMouvementReduit() {
      const partage = window.Mouvement;
      if (partage && partage.reduit !== undefined) {
        return typeof partage.reduit === "function" ? !!partage.reduit() : !!partage.reduit;
      }
      return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    }

    // Petites illustrations d'état vide, construites nœud par nœud (aucun HTML interprété).
    function accueilIllustration(sorte) {
      const svg = accueilSvg("svg", { viewBox: "0 0 96 72", class: "etat-vide-illu", "aria-hidden": "true", focusable: "false" });
      if (sorte === "calendrier") {
        svg.appendChild(accueilSvg("rect", { x: "14", y: "10", width: "60", height: "52", rx: "8", class: "illu-papier" }));
        svg.appendChild(accueilSvg("path", { d: "M14 24h60M28 6v8M60 6v8", class: "illu-trait" }));
        svg.appendChild(accueilSvg("path", { d: "M26 36h8M40 36h8M26 48h8", class: "illu-trait" }));
        svg.appendChild(accueilSvg("circle", { cx: "70", cy: "50", r: "14", class: "illu-accent" }));
        svg.appendChild(accueilSvg("path", { d: "M70 43v7l5 3", class: "illu-coche" }));
        return svg;
      }
      if (sorte === "activite") {
        svg.appendChild(accueilSvg("rect", { x: "6", y: "10", width: "84", height: "52", rx: "10", class: "illu-fond" }));
        svg.appendChild(accueilSvg("path", { d: "M16 50h64", class: "illu-trait" }));
        svg.appendChild(accueilSvg("path", { d: "M18 44l14-10 12 6 16-18 18 12", class: "illu-coche" }));
        svg.appendChild(accueilSvg("circle", { cx: "78", cy: "34", r: "5", class: "illu-accent" }));
        return svg;
      }
      svg.appendChild(accueilSvg("rect", { x: "6", y: "18", width: "72", height: "48", rx: "9", class: "illu-fond" }));
      svg.appendChild(accueilSvg("rect", { x: "18", y: "6", width: "48", height: "40", rx: "6", class: "illu-papier" }));
      svg.appendChild(accueilSvg("path", { d: "M27 17h24M27 25h30M27 33h16", class: "illu-trait" }));
      svg.appendChild(accueilSvg("circle", { cx: "72", cy: "50", r: "14", class: "illu-accent" }));
      svg.appendChild(accueilSvg("path", { d: "M65.5 50.5l4.5 4.5 8-9", class: "illu-coche" }));
      return svg;
    }

    function accueilJoursAvant(iso) {
      const cible = new Date(String(iso) + "T00:00:00");
      if (isNaN(cible.getTime())) return null;
      const aujourdhui = new Date();
      aujourdhui.setHours(0, 0, 0, 0);
      return Math.round((cible.getTime() - aujourdhui.getTime()) / MS_PAR_JOUR);
    }

    function accueilNomDemarche(code) {
      if (code === "campus_france") return "Campus France";
      if (code === "ircc_permis_etudes") return "IRCC Canada";
      const connue = listeDemarches.find((d) => d.code === code);
      return connue ? connue.libelle : String(code);
    }

    function accueilEtatVide(titre, texte, illustration) {
      const li = accueilNoeud("li", "etat-vide");
      li.appendChild(accueilIllustration(illustration));
      li.appendChild(accueilNoeud("strong", "", titre));
      li.appendChild(accueilNoeud("span", "", texte));
      return li;
    }

    function accueilLigneAction(classeBadge, texteBadge, titre, detail, libelleBouton, vue) {
      const li = accueilNoeud("li", "ligne-action");
      li.appendChild(accueilNoeud("span", "badge " + classeBadge, texteBadge));
      const texte = accueilNoeud("div", "ligne-texte");
      texte.appendChild(accueilNoeud("strong", "", titre));
      if (detail) texte.appendChild(accueilNoeud("span", "", detail));
      li.appendChild(texte);
      const bouton = accueilNoeud("button", "btn btn-secondaire btn-sm", libelleBouton);
      bouton.type = "button";
      bouton.addEventListener("click", () => allerVersVue(vue));
      li.appendChild(bouton);
      return li;
    }

    function accueilPluriel(n, singulier, pluriel) {
      return n + " " + (n > 1 ? pluriel : singulier);
    }

    // Apparition en cascade des lignes d'une liste (retard par --i, plafonné).
    function accueilCascade(elements) {
      elements.forEach((el, i) => {
        el.classList.add("tb-in");
        el.style.setProperty("--i", String(Math.min(i, 8)));
      });
    }

    function accueilConstruireActions(etat) {
      const lignes = [];
      if (etat.recaps) {
        lignes.push(accueilLigneAction(
          "badge-info", "À valider",
          accueilPluriel(etat.recaps, "récapitulatif attend", "récapitulatifs attendent") + " votre validation",
          "L'agent n'enverra rien tant que vous n'avez pas validé le contenu exact.",
          "Examiner", "vue-recaps-valider"));
      }
      const synthese = etat.validations;
      if (synthese) {
        (synthese.taches_a_valider || []).forEach((t) => {
          lignes.push(accueilLigneAction(
            "badge-info", "Validation en attente",
            accueilNomDemarche(t.code_demarche) + " : " + libelleCandidatParId(t.candidat_id),
            t.message_alerte || "Pré-remplissage terminé, arrêté avant l'envoi officiel.",
            "Contrôler", "vue-validation-humaine"));
        });
        (synthese.taches_suspendues || []).forEach((t) => {
          const actionHumaine = t.motif_suspension === "action_utilisateur_portail";
          lignes.push(accueilLigneAction(
            "badge-warn", actionHumaine ? "CAPTCHA ou code" : "En pause",
            accueilNomDemarche(t.code_demarche) + " : " + libelleCandidatParId(t.candidat_id),
            t.message_alerte || (actionHumaine
              ? "Le portail demande une action de votre part."
              : "Des pièces ou des informations sont à compléter."),
            actionHumaine ? "Prendre la main" : "Compléter",
            actionHumaine ? "vue-navigateur-serveur" : "vue-validation-humaine"));
        });
      }
      const sansConsentement = etat.candidats.filter((c) => c.consentement_signe === false).length;
      if (sansConsentement > 0) {
        lignes.push(accueilLigneAction(
          "badge-warn", "Consentement",
          accueilPluriel(sansConsentement, "fiche sans consentement", "fiches sans consentement") + " (loi 18-07)",
          "Recueillez le consentement du candidat avant de traiter son dossier.",
          "Ouvrir les fiches", "vue-etudiants"));
      }
      return lignes;
    }

    function accueilAfficherActions(etat) {
      const liste = document.getElementById("accueil-actions");
      const badge = document.getElementById("accueil-total-actions");
      liste.replaceChildren();
      liste.setAttribute("aria-busy", "false");
      const connecte = etat.validations !== null || etat.candidats.length > 0 || etat.recaps !== null;
      if (!connecte) {
        badge.className = "badge badge-nu";
        badge.textContent = "—";
        liste.appendChild(accueilEtatVide("Connectez-vous pour voir vos dossiers.", "Ouvrez votre session pour afficher les dossiers de votre bureau.", "dossier"));
        return;
      }
      const lignes = accueilConstruireActions(etat);
      badge.className = "badge " + (lignes.length > 0 ? "badge-warn" : "badge-ok");
      badge.textContent = lignes.length > 0 ? accueilPluriel(lignes.length, "action", "actions") : "À jour";
      if (lignes.length === 0) {
        liste.appendChild(accueilEtatVide("Tout est à jour.", "Aucun dossier n'attend de décision. Ajoutez un étudiant ou lancez une démarche pour avancer.", "dossier"));
        return;
      }
      const visibles = lignes.slice(0, MAX_LIGNES_ACTIONS);
      accueilCascade(visibles);
      visibles.forEach((l) => liste.appendChild(l));
      if (lignes.length > MAX_LIGNES_ACTIONS) {
        const reste = accueilNoeud("li", "note", "Et " + accueilPluriel(lignes.length - MAX_LIGNES_ACTIONS, "autre", "autres") + " : ouvrez le centre de validation pour tout voir.");
        liste.appendChild(reste);
      }
    }

    function accueilConstruireEcheances(candidats) {
      const items = CALENDRIER_CAMPUS_FRANCE.map((e) => ({ iso: e.date, libelle: e.libelle, passeport: false }));
      candidats.forEach((c) => {
        if (!c.date_expiration_passeport) return;
        const jours = accueilJoursAvant(c.date_expiration_passeport);
        if (jours === null || jours > SEUIL_PASSEPORT_JOURS) return;
        items.push({
          iso: c.date_expiration_passeport,
          libelle: "Passeport de " + c.nom + " " + c.prenom + (jours < 0 ? " expiré" : " : expiration"),
          passeport: true,
        });
      });
      return items
        .map((i) => Object.assign({}, i, { jours: accueilJoursAvant(i.iso) }))
        .filter((i) => i.jours !== null && (i.jours >= 0 || i.passeport))
        .sort((a, b) => a.jours - b.jours)
        .slice(0, MAX_ECHEANCES);
    }

    function accueilTexteDelai(jours) {
      if (jours < 0) return "Dépassée de " + Math.abs(jours) + " j";
      if (jours === 0) return "Aujourd'hui";
      if (jours === 1) return "Demain";
      return "Dans " + jours + " j";
    }

    function accueilAfficherEcheances(candidats) {
      const liste = document.getElementById("accueil-echeances");
      liste.replaceChildren();
      liste.setAttribute("aria-busy", "false");
      const items = accueilConstruireEcheances(candidats);
      if (items.length === 0) {
        liste.appendChild(accueilEtatVide("Aucune échéance proche.", "Les prochaines dates apparaîtront ici.", "calendrier"));
        return;
      }
      const lignes = [];
      items.forEach((i) => {
        const date = new Date(i.iso + "T00:00:00");
        const li = accueilNoeud("li", "echeance");
        const urgence = i.jours <= SEUIL_ECHEANCE_CRITIQUE_JOURS ? " tb-urgent" : i.jours <= SEUIL_ECHEANCE_ALERTE_JOURS ? " tb-proche" : "";
        const bloc = accueilNoeud("div", "echeance-date" + urgence);
        bloc.appendChild(accueilNoeud("b", "", String(date.getDate())));
        bloc.appendChild(accueilNoeud("span", "", MOIS_COURTS_FR[date.getMonth()]));
        li.appendChild(bloc);
        const texte = accueilNoeud("div", "ligne-texte");
        texte.appendChild(accueilNoeud("strong", "", i.libelle));
        texte.appendChild(accueilNoeud("span", "", i.passeport ? "Pièce d'identité du candidat" : "Calendrier officiel"));
        li.appendChild(texte);
        const classe = i.jours <= SEUIL_ECHEANCE_CRITIQUE_JOURS ? "badge-err"
          : i.jours <= SEUIL_ECHEANCE_ALERTE_JOURS ? "badge-warn" : "";
        li.appendChild(accueilNoeud("span", "badge " + classe, accueilTexteDelai(i.jours)));
        lignes.push(li);
      });
      accueilCascade(lignes);
      lignes.forEach((l) => liste.appendChild(l));
    }

    function accueilMajCompteurNav(synthese) {
      const compteur = document.getElementById("nav-compteur-validation");
      const total = synthese ? (synthese.total_a_valider || 0) + (synthese.total_suspendues || 0) : 0;
      compteur.textContent = String(total);
      compteur.setAttribute("aria-label", total + (total > 1 ? " dossiers à traiter" : " dossier à traiter"));
      compteur.classList.toggle("cache", total === 0);
    }

    // Compteur : de 0 à la valeur réelle (sortie ralentie). Sans animation : valeur d'emblée.
    function accueilAnimerCompteur(el, cible, suffixe, duree) {
      if (el.dataset.valeurAffichee === String(cible)) return;
      el.dataset.valeurAffichee = String(cible);
      const fin = String(cible) + (suffixe || "");
      const partage = window.Mouvement;
      if (!suffixe && partage && typeof partage.compteur === "function") {
        try { partage.compteur(el, cible, duree || ACCUEIL_DUREE_COMPTEUR_MS); return; } catch (e) { /* repli ci-dessous */ }
      }
      if (accueilMouvementReduit() || cible === 0) {
        el.textContent = fin;
        return;
      }
      const debut = performance.now();
      const total = duree || ACCUEIL_DUREE_COMPTEUR_MS;
      function image(maintenant) {
        const t = Math.min(1, (maintenant - debut) / total);
        const doux = 1 - Math.pow(1 - t, 3);
        el.textContent = String(Math.round(cible * doux)) + (suffixe || "");
        if (t < 1 && el.dataset.valeurAffichee === String(cible)) requestAnimationFrame(image);
        else el.textContent = fin;
      }
      requestAnimationFrame(image);
    }

    // Chiffres clés : un squelette encore présent signifie que la route n'a pas répondu.
    function accueilFinaliserChiffres(synthese) {
      IDS_CHIFFRES_ACCUEIL.forEach((id) => {
        const el = document.getElementById(id);
        if (!el) return;
        if (el.querySelector(".squelette")) { el.textContent = "—"; return; }
        const n = parseInt(el.textContent, 10);
        if (!isNaN(n) && String(n) === el.textContent.trim()) {
          const carte = el.parentElement;
          const aide = document.getElementById(id + "-aide");
          const textes = ACCUEIL_AIDES_CHIFFRES[id];
          carte.classList.toggle("kpi-zero", n === 0);
          carte.classList.toggle("kpi-actif", n > 0);
          if (aide && textes) aide.textContent = textes[n === 0 ? 0 : 1];
          // Remet à zéro puis anime vers la valeur réelle déjà posée par le chargement.
          el.dataset.valeurAffichee = "";
          accueilAnimerCompteur(el, n);
        }
      });
      const enPause = synthese ? synthese.total_suspendues || 0 : 0;
      document.getElementById("stat-nb-suspendues").parentElement.classList.toggle("kpi-alerte", enPause > 0);
    }

    // ---- Jauges de santé du portefeuille (ratios calculés sur les fiches réelles) ----
    function accueilClasseJauge(pct) {
      if (pct === null) return ["", "Sans donnée", "badge-nu"];
      if (pct >= ACCUEIL_SEUIL_BON) return ["j-bon", "Solide", "badge-ok"];
      if (pct >= ACCUEIL_SEUIL_ALERTE) return ["j-alerte", "À renforcer", "badge-warn"];
      return ["j-critique", "Fragile", "badge-err"];
    }

    function accueilPoserJauge(id, faits, total, detail) {
      const racine = document.getElementById(id);
      if (!racine) return;
      const pct = total > 0 ? Math.round((faits * 100) / total) : null;
      const [classe, mot, classeBadge] = accueilClasseJauge(pct);
      racine.classList.remove("j-bon", "j-alerte", "j-critique");
      if (classe) racine.classList.add(classe);
      const centre = racine.querySelector(".tb-jauge-centre");
      const arc = racine.querySelector(".tb-jauge-valeur");
      const etat = racine.querySelector(".tb-jauge-etat");
      racine.querySelector(".tb-jauge-detail").textContent = detail;
      etat.className = "badge tb-jauge-etat " + classeBadge;
      etat.textContent = mot;
      const decalage = pct === null ? ACCUEIL_CIRCONFERENCE : ACCUEIL_CIRCONFERENCE * (1 - pct / 100);
      if (pct === null) {
        centre.textContent = "—";
        arc.style.strokeDashoffset = String(decalage);
        return;
      }
      centre.textContent = "";
      const nombre = accueilNoeud("span", "", "0");
      centre.appendChild(nombre);
      centre.appendChild(accueilNoeud("small", "", "%"));
      racine.setAttribute("aria-label", racine.querySelector("strong").textContent + " : " + pct + " pour cent, " + mot);
      nombre.dataset.valeurAffichee = "";
      accueilAnimerCompteur(nombre, pct, "", 900);
      if (accueilMouvementReduit()) {
        arc.style.strokeDashoffset = String(decalage);
      } else {
        requestAnimationFrame(() => requestAnimationFrame(() => { arc.style.strokeDashoffset = String(decalage); }));
      }
    }

    function accueilAfficherSante(candidats) {
      const total = candidats.length;
      const badge = document.getElementById("sante-total");
      badge.textContent = total > 0 ? accueilPluriel(total, "dossier", "dossiers") : "Aucun dossier";
      const champs = DOS_CHAMPS_FICHE.length;
      const renseignes = candidats.reduce((somme, c) => somme + dosChampsRenseignes(c), 0);
      const completes = candidats.filter((c) => dosChampsRenseignes(c) === champs).length;
      accueilPoserJauge("jauge-fiches", renseignes, total * champs,
        total > 0 ? accueilPluriel(completes, "fiche complète", "fiches complètes") + " sur " + total : "Aucune fiche");
      const signes = candidats.filter((c) => c.consentement_signe === true).length;
      accueilPoserJauge("jauge-consentements", signes, total,
        total > 0 ? signes + " sur " + total + " (loi 18-07)" : "Aucune fiche");
      const avecDate = candidats.filter((c) => c.date_expiration_passeport && accueilJoursAvant(c.date_expiration_passeport) !== null);
      const valides = avecDate.filter((c) => accueilJoursAvant(c.date_expiration_passeport) > SEUIL_PASSEPORT_JOURS).length;
      accueilPoserJauge("jauge-passeports", valides, avecDate.length,
        avecDate.length > 0 ? valides + " sur " + avecDate.length + " (plus de 6 mois)" : "Aucune date renseignée");
    }

    // ---- Activité du bureau : opérations du journal d'audit par jour (administrateurs) ----
    function accueilCleJour(date) {
      return date.getFullYear() + "-" + String(date.getMonth() + 1).padStart(2, "0") + "-" + String(date.getDate()).padStart(2, "0");
    }

    function accueilCompterParJour(entrees) {
      const jours = [];
      const index = {};
      const aujourdhui = new Date();
      aujourdhui.setHours(0, 0, 0, 0);
      for (let i = ACCUEIL_JOURS_ACTIVITE - 1; i >= 0; i -= 1) {
        const d = new Date(aujourdhui.getTime() - i * MS_PAR_JOUR);
        const jour = { date: d, cle: accueilCleJour(d), n: 0 };
        index[jour.cle] = jour;
        jours.push(jour);
      }
      entrees.forEach((e) => {
        const quand = new Date(e.horodatage);
        if (isNaN(quand.getTime())) return;
        const jour = index[accueilCleJour(quand)];
        if (jour) jour.n += 1;
      });
      return jours;
    }

    function accueilLibelleJour(date) {
      return date.getDate() + " " + MOIS_COURTS_FR[date.getMonth()];
    }

    function accueilConstruireSpark(jours) {
      const maxi = Math.max.apply(null, jours.map((j) => j.n).concat([1]));
      const haut = ACCUEIL_SPARK_H - ACCUEIL_SPARK_MARGE * 2;
      const pas = (ACCUEIL_SPARK_L - ACCUEIL_SPARK_MARGE * 2) / (jours.length - 1);
      const points = jours.map((j, i) => ({
        x: ACCUEIL_SPARK_MARGE + i * pas,
        y: ACCUEIL_SPARK_H - ACCUEIL_SPARK_MARGE - (j.n / maxi) * haut,
      }));
      const trace = points.map((p, i) => (i === 0 ? "M" : "L") + p.x.toFixed(1) + " " + p.y.toFixed(1)).join(" ");
      const bas = (ACCUEIL_SPARK_H - ACCUEIL_SPARK_MARGE).toFixed(1);
      const aire = trace + " L" + points[points.length - 1].x.toFixed(1) + " " + bas + " L" + points[0].x.toFixed(1) + " " + bas + " Z";
      const svg = accueilSvg("svg", { viewBox: "0 0 " + ACCUEIL_SPARK_L + " " + ACCUEIL_SPARK_H, class: "tb-spark", "aria-hidden": "true", focusable: "false" });
      svg.appendChild(accueilSvg("line", { x1: String(ACCUEIL_SPARK_MARGE), x2: String(ACCUEIL_SPARK_L - ACCUEIL_SPARK_MARGE), y1: bas, y2: bas, class: "tb-spark-base" }));
      svg.appendChild(accueilSvg("path", { d: aire, class: "tb-spark-aire" }));
      svg.appendChild(accueilSvg("path", { d: trace, class: "tb-spark-ligne", pathLength: "1" }));
      const dernier = points[points.length - 1];
      svg.appendChild(accueilSvg("circle", { cx: dernier.x.toFixed(1), cy: dernier.y.toFixed(1), r: "4", class: "tb-spark-pt" }));
      points.forEach((p, i) => {
        const zone = accueilSvg("circle", { cx: p.x.toFixed(1), cy: p.y.toFixed(1), r: "9", class: "tb-spark-zone" });
        zone.appendChild(accueilNoeud("title", "", accueilLibelleJour(jours[i].date) + " : " + accueilPluriel(jours[i].n, "opération", "opérations")));
        svg.appendChild(zone);
      });
      return svg;
    }

    function accueilAfficherActivite(entrees) {
      const corps = document.getElementById("accueil-activite-corps");
      corps.replaceChildren();
      corps.setAttribute("aria-busy", "false");
      const jours = accueilCompterParJour(entrees);
      const total = jours.reduce((s, j) => s + j.n, 0);
      if (total === 0) {
        const vide = accueilNoeud("div", "etat-vide");
        vide.appendChild(accueilIllustration("activite"));
        vide.appendChild(accueilNoeud("strong", "", "Aucune opération sur 14 jours."));
        vide.appendChild(accueilNoeud("span", "", "Les envois, validations et connexions du bureau tracent leur activité ici."));
        corps.appendChild(vide);
        return;
      }
      const pic = jours.reduce((m, j) => (j.n > m.n ? j : m), jours[0]);
      const tete = accueilNoeud("div", "tb-activite-tete");
      const chiffre = accueilNoeud("span", "tb-activite-total", "0");
      tete.appendChild(chiffre);
      tete.appendChild(accueilNoeud("span", "tb-activite-pic", "opérations sur 14 jours · pic : " + pic.n + " le " + accueilLibelleJour(pic.date)));
      corps.appendChild(tete);
      const svg = accueilConstruireSpark(jours);
      corps.appendChild(svg);
      const axe = accueilNoeud("div", "tb-spark-axe");
      axe.appendChild(accueilNoeud("span", "", accueilLibelleJour(jours[0].date)));
      axe.appendChild(accueilNoeud("span", "", "Aujourd'hui"));
      corps.appendChild(axe);
      corps.appendChild(accueilNoeud("p", "sr-only", total + " opérations sur 14 jours, pic de " + pic.n + " le " + accueilLibelleJour(pic.date) + "."));
      corps.appendChild(accueilNoeud("p", "tb-activite-note", "Calculé sur les " + ACCUEIL_TAILLE_AUDIT + " dernières entrées du journal d'audit."));
      accueilAnimerCompteur(chiffre, total, "", 900);
      if (accueilMouvementReduit()) svg.classList.add("tb-trace-ok");
      else requestAnimationFrame(() => requestAnimationFrame(() => svg.classList.add("tb-trace-ok")));
    }

    function accueilActiviteIndisponible(titre, texte) {
      const corps = document.getElementById("accueil-activite-corps");
      corps.replaceChildren();
      corps.setAttribute("aria-busy", "false");
      const vide = accueilNoeud("div", "etat-vide");
      vide.appendChild(accueilIllustration("activite"));
      vide.appendChild(accueilNoeud("strong", "", titre));
      vide.appendChild(accueilNoeud("span", "", texte));
      corps.appendChild(vide);
    }

    async function accueilChargerActivite() {
      if (roleActif !== "administrateur") {
        accueilActiviteIndisponible("Réservé aux administrateurs.", "Le journal d'audit du bureau n'est visible que par un administrateur.");
        return;
      }
      try {
        const rep = await appelApi("/api/v1/audit?taille=" + ACCUEIL_TAILLE_AUDIT);
        if (!rep.ok) throw new Error("audit");
        const data = await rep.json();
        accueilAfficherActivite(data.elements || []);
      } catch (e) {
        accueilActiviteIndisponible("Activité indisponible.", "Le journal d'audit n'a pas répondu. Actualisez la page dans un instant.");
      }
    }

    function accueilAfficherDate() {
      const el = document.getElementById("accueil-date");
      if (!el) return;
      el.textContent = new Date().toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
    }

    function accueilAfficher(etat) {
      accueilAfficherDate();
      accueilFinaliserChiffres(etat.validations);
      accueilAfficherActions(etat);
      accueilAfficherEcheances(etat.candidats);
      accueilAfficherSante(etat.candidats);
      accueilMajCompteurNav(etat.validations);
      accueilChargerActivite();
    }

    // =======================================================================
    // Écran Étudiants : en-tête de la fiche du dossier actif (avatar, jauge de complétude).
    // La fiche est reconstruite par js_dossiers : on la complète dès qu'elle change.
    // =======================================================================
    function accueilJaugeFiche(pct) {
      const svg = accueilSvg("svg", { viewBox: "0 0 120 120", class: "fiche-jauge-svg", "aria-hidden": "true", focusable: "false" });
      svg.appendChild(accueilSvg("circle", { cx: "60", cy: "60", r: "50", class: "fiche-jauge-piste" }));
      const arc = accueilSvg("circle", { cx: "60", cy: "60", r: "50", transform: "rotate(-90 60 60)", class: "fiche-jauge-valeur" });
      arc.style.strokeDasharray = ACCUEIL_CIRCONFERENCE.toFixed(2);
      arc.style.strokeDashoffset = ACCUEIL_CIRCONFERENCE.toFixed(2);
      svg.appendChild(arc);
      const decalage = ACCUEIL_CIRCONFERENCE * (1 - pct / 100);
      if (accueilMouvementReduit()) arc.style.strokeDashoffset = String(decalage);
      else requestAnimationFrame(() => requestAnimationFrame(() => { arc.style.strokeDashoffset = String(decalage); }));
      return svg;
    }

    function accueilEnteteFiche(c) {
      const faits = dosChampsRenseignes(c);
      const total = DOS_CHAMPS_FICHE.length;
      const pct = total > 0 ? Math.round((faits * 100) / total) : 0;
      const hero = accueilNoeud("div", "fiche-hero");
      hero.appendChild(accueilNoeud("span", "fiche-hero-avatar", dosInitiales(c)));
      hero.lastChild.setAttribute("aria-hidden", "true");
      const texte = accueilNoeud("div", "fiche-hero-texte");
      texte.appendChild(accueilNoeud("strong", "", (c.nom || "") + " " + (c.prenom || "")));
      const visee = [c.programme_vise, c.etablissement_vise].filter((v) => dosEstRenseigne(v)).join(" · ");
      texte.appendChild(accueilNoeud("span", "", visee || "Formation visée non renseignée"));
      const puces = accueilNoeud("div", "fiche-hero-puces");
      puces.appendChild(accueilNoeud("span", "badge " + (c.consentement_signe ? "badge-ok" : "badge-warn"),
        c.consentement_signe ? "Consentement signé" : "Consentement à recueillir"));
      puces.appendChild(accueilNoeud("span", "badge " + (faits === total ? "badge-ok" : "badge-warn"),
        faits === total ? "Fiche complète" : accueilPluriel(total - faits, "champ à compléter", "champs à compléter")));
      texte.appendChild(puces);
      hero.appendChild(texte);
      const jauge = accueilNoeud("div", "fiche-hero-jauge");
      jauge.setAttribute("role", "img");
      jauge.setAttribute("aria-label", "Fiche renseignée à " + pct + " pour cent (" + faits + " champs sur " + total + ")");
      jauge.appendChild(accueilJaugeFiche(pct));
      jauge.appendChild(accueilNoeud("span", "fiche-hero-pct", pct + " %"));
      hero.appendChild(jauge);
      return hero;
    }

    function accueilSurveillerFiche() {
      const corps = document.getElementById("fiche-active-corps");
      if (!corps || typeof MutationObserver === "undefined") return;
      new MutationObserver(() => {
        const premier = corps.firstElementChild;
        if (!premier || !premier.classList.contains("fiche-grille")) return;
        if (typeof candidatActifObj === "undefined" || !candidatActifObj) return;
        corps.insertBefore(accueilEnteteFiche(candidatActifObj), premier);
      }).observe(corps, { childList: true });
    }
    accueilSurveillerFiche();

"""
