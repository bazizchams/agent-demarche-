"""Écrans « Démarches » (Campus France, IRCC, procédures) et « Validation et abonnement ».

Gabarits HTML seuls : la logique est dans les modules `js_*`. Les identifiants et les attributs
`onclick` sont consommés par ce JavaScript et par les tests : ne pas les renommer.
Les jetons [[i:nom]] sont remplacés par des icônes SVG à l'assemblage.
"""

from __future__ import annotations

# Styles propres aux écrans Démarches (Campus France, IRCC, procédures) : composants absents de
# styles.py (parcours numéroté, cartes de vœu, blocs numérotés de l'éditeur). Tokens uniquement,
# tout est préfixé par `.vue-demarche` ; aucun antislash.
_STYLE_DEMARCHES = """
    <style>
    .vue-demarche .carte-entete { align-items: flex-start; flex-wrap: wrap; }
    .vue-demarche .carte-entete p { margin: 2px 0 0; font-size: var(--t-sm); color: var(--texte-doux); max-width: 70ch; }
    .vue-demarche .surtitre { margin-bottom: 2px; }
    .vue-demarche .sous-titre-carte { margin: var(--e5) 0 var(--e3); padding-top: var(--e4); border-top: 1px solid var(--bord); font-size: var(--t-base); }
    .vue-demarche .note-regle { margin: var(--e2) 0 0; }
    .vue-demarche .form-voeu { display: flex; flex-direction: column; gap: var(--e3); }
    .vue-demarche .form-voeu .pile-actions { margin: 0; }
    .vue-demarche .champ input, .vue-demarche .champ select, .vue-demarche .champ textarea { width: 100%; }

    /* Cartes de vœu */
    .vue-demarche .liste-voeux { display: flex; flex-direction: column; gap: var(--e3); margin-top: var(--e4); }
    .vue-demarche .liste-voeux > .etat-vide { background: var(--surface-2); border: 1px dashed var(--bord-fort); border-radius: var(--r-l); }
    .vue-demarche .voeu { margin: 0; padding: var(--e4) var(--e5); border-radius: var(--r-l); display: flex; flex-direction: column; gap: var(--e3); box-shadow: var(--ombre-1); }
    .vue-demarche .voeu-entete { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: start; gap: var(--e3); margin: 0; }
    .vue-demarche .voeu-rang { width: 32px; height: 32px; border-radius: 50%; display: grid; place-items: center; background: var(--accent-doux); color: var(--accent-fort); font-family: var(--police-titre); font-weight: 700; font-variant-numeric: tabular-nums; }
    .vue-demarche .voeu-texte { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    .vue-demarche .voeu-titre { font-size: var(--t-md); line-height: 1.3; overflow-wrap: anywhere; }
    .vue-demarche .voeu-meta { font-size: var(--t-sm); color: var(--texte-doux); overflow-wrap: anywhere; }
    .vue-demarche .voeu-justif { font-size: var(--t-sm); color: var(--texte-faible); }
    .vue-demarche .voeu-alertes { margin: 0; padding: var(--e3) var(--e4) var(--e3) var(--e6); background: var(--alerte-doux); border-radius: var(--r-m); }
    .vue-demarche .voeu-compteur { margin: 0; text-align: right; font-weight: 400; font-variant-numeric: tabular-nums; }
    .vue-demarche .voeu > .note { margin: 0; }
    .vue-demarche .voeu-actions { display: flex; flex-wrap: wrap; gap: var(--e2); }
    .vue-demarche .voeu-actions .btn { margin: 0; }
    .vue-demarche .voeu-actions .btn-retirer { margin-left: auto; }
    .vue-demarche .voeu-squelette { display: flex; flex-direction: column; gap: var(--e3); padding: var(--e4) var(--e5); border: 1px solid var(--bord); border-radius: var(--r-l); background: var(--surface); }

    /* Parcours numéroté (étapes du portail en un clic) */
    .vue-demarche .demarche-raccourci { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--e3); padding: var(--e4); background: var(--accent-doux); border-radius: var(--r-m); }
    .vue-demarche .demarche-raccourci p { margin: 0; font-size: var(--t-sm); color: var(--texte); max-width: 52ch; }
    .vue-demarche .demarche-raccourci .pile-actions { margin: 0; }
    .vue-demarche .parcours { list-style: none; margin: 0; padding: 0; counter-reset: parcours; display: flex; flex-direction: column; }
    .vue-demarche .parcours > li { counter-increment: parcours; display: grid; grid-template-columns: 30px minmax(0, 1fr) auto; align-items: center; gap: var(--e2) var(--e3); padding: var(--e3) 0; border-top: 1px solid var(--bord); }
    .vue-demarche .parcours > li:first-child { border-top: 0; }
    .vue-demarche .parcours > li::before { content: counter(parcours); width: 30px; height: 30px; border-radius: 50%; display: grid; place-items: center; background: var(--surface); color: var(--texte-doux); box-shadow: inset 0 0 0 2px var(--bord-fort); font-weight: 700; font-size: var(--t-sm); font-variant-numeric: tabular-nums; }
    .vue-demarche .parcours-texte { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    .vue-demarche .parcours-texte strong { font-size: var(--t-base); }
    .vue-demarche .parcours-texte span { font-size: var(--t-sm); color: var(--texte-doux); }
    .vue-demarche .parcours-actions { display: flex; flex-wrap: wrap; gap: var(--e2); justify-content: flex-end; }
    .vue-demarche .parcours-actions .btn { margin: 0; }

    /* Compte rendu et suivi de tâche dans la zone de retour du co-pilote */
    .vue-demarche .zone-retour-demarche { display: flex; flex-direction: column; gap: var(--e3); min-width: 0; overflow-wrap: anywhere; }
    .vue-demarche .zone-retour-demarche > * { margin: 0; }
    .vue-demarche .retour-entete { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-start; gap: var(--e2); }
    .vue-demarche .retour-entete > div { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    .vue-demarche .retour-entete .badge, .vue-demarche .retour-statut .badge { white-space: normal; }
    .vue-demarche .retour-titre { margin: 0 0 var(--e1); font-size: var(--t-sm); font-weight: 600; color: var(--texte); }
    .vue-demarche .retour-titre.ok { color: var(--bon-texte); }
    .vue-demarche .retour-titre.alerte { color: var(--alerte-texte); }
    .vue-demarche .retour-titre.critique { color: var(--critique-texte); }
    .vue-demarche .retour-bloc .liste-propre { margin: 0; }
    .vue-demarche .retour-bloc .btn { margin: var(--e2) 0 0; white-space: normal; text-align: left; }
    .vue-demarche .zone-retour-demarche .etapes { grid-auto-flow: row; grid-auto-columns: auto; gap: var(--e4); margin: 0; }
    .vue-demarche .zone-retour-demarche .etape { padding: 4px 0 0 44px; min-height: 30px; }
    .vue-demarche .zone-retour-demarche .etape::after { top: 36px; left: 14px; right: auto; bottom: -14px; width: 2px; height: auto; }
    .vue-demarche .zone-retour-demarche .etape:last-child::after { display: none; }
    .vue-demarche .zone-retour-demarche .capture-apercu { margin-top: var(--e2); }

    /* Procédures : tableau et éditeur en blocs numérotés */
    .vue-demarche td.etat-vide .etat-vide-illu { display: block; margin: 0 auto var(--e2); }
    .vue-demarche td.etat-vide strong { margin-bottom: 2px; }
    .vue-demarche .proc-nom { display: flex; flex-direction: column; gap: 2px; }
    .vue-demarche .proc-nom code { font-size: var(--t-xs); color: var(--texte-faible); }
    .vue-demarche .proc-actions { display: flex; flex-wrap: wrap; gap: var(--e2); }
    .vue-demarche .proc-actions .btn { margin: 0; }
    .vue-demarche .proc-blocs { list-style: none; margin: 0; padding: 0; counter-reset: bloc; display: flex; flex-direction: column; gap: var(--e5); }
    .vue-demarche .proc-bloc { counter-increment: bloc; display: flex; flex-direction: column; gap: var(--e3); padding-top: var(--e5); border-top: 1px solid var(--bord); }
    .vue-demarche .proc-bloc:first-child { padding-top: 0; border-top: 0; }
    .vue-demarche .proc-bloc-entete { display: grid; grid-template-columns: 30px minmax(0, 1fr); gap: var(--e3); align-items: start; }
    .vue-demarche .proc-bloc-entete::before { content: counter(bloc); width: 30px; height: 30px; border-radius: 50%; display: grid; place-items: center; background: var(--accent-doux); color: var(--accent-fort); font-weight: 700; font-size: var(--t-sm); font-variant-numeric: tabular-nums; }
    .vue-demarche .proc-bloc-entete h4 { margin: 4px 0 0; }
    .vue-demarche .proc-bloc-entete p { margin: 2px 0 0; font-size: var(--t-sm); color: var(--texte-doux); max-width: 70ch; }
    .vue-demarche .proc-bloc > .btn { align-self: flex-start; margin: 0; }
    .vue-demarche .ligne-proc { align-items: flex-end; margin: 0 0 var(--e2); padding: var(--e3); }
    .vue-demarche .ligne-proc > label.champ { flex: 1 1 160px; min-width: min(100%, 140px); flex-direction: column; align-items: stretch; gap: 6px; font-size: var(--t-sm); font-weight: 600; }
    .vue-demarche .ligne-proc > label.champ.large { flex: 3 1 260px; }
    .vue-demarche .ligne-proc > label.champ input { flex: none; width: 100%; min-width: 0; }
    .vue-demarche .ligne-proc > label.case { flex: 0 1 auto; align-self: center; font-size: var(--t-sm); }
    .vue-demarche .ligne-proc > .btn { margin: 0 0 0 auto; }
    .vue-demarche #proc-etapes { counter-reset: etape-proc; }
    .vue-demarche #proc-etapes .ligne-proc { counter-increment: etape-proc; }
    .vue-demarche #proc-etapes .ligne-proc::before { content: counter(etape-proc); align-self: center; width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; background: var(--surface); box-shadow: inset 0 0 0 2px var(--bord-fort); color: var(--texte-doux); font-weight: 700; font-size: var(--t-xs); }
    .vue-demarche .editeur-pied { justify-content: flex-start; }

    @media (max-width: 640px) {
      .vue-demarche .voeu { padding: var(--e4); }
      .vue-demarche .voeu-entete { grid-template-columns: auto minmax(0, 1fr); }
      .vue-demarche .voeu-entete .badge { grid-column: 2; justify-self: start; }
      .vue-demarche .voeu-actions .btn-retirer { margin-left: 0; }
      .vue-demarche .parcours > li { grid-template-columns: 30px minmax(0, 1fr); }
      .vue-demarche .parcours-actions { grid-column: 2; justify-content: flex-start; }
      .vue-demarche .ligne-proc > .btn { margin: 0; }
    }
    </style>
"""

# Illustration d'état vide (dossier + coche), mêmes classes que l'accueil.
_ILLU_DOSSIER = (
    '<svg class="etat-vide-illu" viewBox="0 0 96 72" aria-hidden="true" focusable="false">'
    '<rect class="illu-fond" x="6" y="18" width="72" height="48" rx="9"/>'
    '<rect class="illu-papier" x="18" y="6" width="48" height="40" rx="6"/>'
    '<path class="illu-trait" d="M27 17h24M27 25h30M27 33h16"/>'
    '<circle class="illu-accent" cx="72" cy="50" r="14"/>'
    '<path class="illu-coche" d="M65.5 50.5l4.5 4.5 8-9"/></svg>'
)

_CELLULE_SQUELETTE = '<td><span class="squelette squelette-texte"></span></td>'
_LIGNE_SQUELETTE_PROC = (
    '<tr aria-hidden="true"><td><span class="squelette-pile"><span class="squelette squelette-texte"></span>'
    '<span class="squelette squelette-texte court"></span></span></td>'
    '<td><span class="squelette squelette-pastille"></span></td>'
    + _CELLULE_SQUELETTE
    + _CELLULE_SQUELETTE
    + "</tr>"
)

_BARRE_NAV_CF = """
            <div class="barre-chrome-direct">
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('{D}', 'retour')" title="Page précédente" aria-label="Page précédente">[[i:retour]]</button>
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('{D}', 'suivant')" title="Page suivante" aria-label="Page suivante">[[i:suivant]]</button>
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('{D}', 'actualiser')" title="Actualiser la page" aria-label="Actualiser la page">[[i:actualiser]]</button>
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('{D}', 'scroll_haut')" title="Remonter" aria-label="Remonter dans la page">[[i:haut]]</button>
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('{D}', 'scroll_bas')" title="Descendre" aria-label="Descendre dans la page">[[i:bas]]</button>
              <input id="{P}-url-live" class="url-live-input" type="text" value="{U}" placeholder="Adresse à ouvrir" aria-label="Adresse du portail" />
              <button class="btn-nav-mini" type="button" onclick="naviguerUrlDirecte('{D}')">Aller</button>
              <button class="btn-nav-mini" type="button" onclick="basculerModeVueDirecte('{D}')" id="btn-mode-vue-{P}">Vue : contrôle DOM et fenêtre</button>
            </div>"""

_CADRE_NAVIGATEUR = """
          <div class="cadre-navigateur-direct">{BARRE}
            <div id="{P}-conteneur-iframe" class="cache">
              <iframe id="{P}-iframe-direct" class="iframe-navigateur-direct" src="{S}" title="{T}"></iframe>
            </div>
            <div id="{P}-vue-capture" class="corps-navigateur-direct cache">
              <p id="{P}-capture-message" class="aide">Capture de la page ouverte dans le navigateur du bureau.</p>
              <img id="{P}-capture-direct" class="capture-apercu cache" alt="Capture de la page ouverte dans le navigateur du bureau" />
            </div>
            <div id="{P}-panneau-dom-live" class="corps-navigateur-direct">
              <div class="entete-live">
                <div>
                  <strong id="{P}-titre-page-live">{TL}</strong>
                  <div class="aide">Agissez en temps réel sur les champs et boutons de la page ouverte dans votre navigateur.</div>
                </div>
                <button class="btn btn-contour btn-sm" type="button" style="margin:0;" onclick="synchroniserEtatNavigateurDirect('{D}')">[[i:actualiser]]Synchroniser</button>
              </div>
              <div id="{P}-elements-dom-live">
                <p class="aide">{AIDE}</p>
              </div>
            </div>
          </div>"""


def _cadre(prefixe: str, demarche: str, url: str, src: str, titre: str, titre_live: str, aide: str) -> str:
    barre = (
        _BARRE_NAV_CF.replace("{D}", demarche).replace("{P}", prefixe).replace("{U}", url)
    )
    return (
        _CADRE_NAVIGATEUR.replace("{BARRE}", barre)
        .replace("{D}", demarche)
        .replace("{P}", prefixe)
        .replace("{S}", src)
        .replace("{T}", titre)
        .replace("{TL}", titre_live)
        .replace("{AIDE}", aide)
    )


_CADRE_CF = _cadre(
    "cf", "campus_france", "https://etudesenfrance.diplomatie.gouv.fr/", "/demo/campus-france",
    "Portail interactif Études en France", "Contrôleur de page : Études en France",
    "Cliquez sur « 1. Ouvrir le site » ou donnez une consigne à droite (par exemple « remplis mon identité ») pour voir et manipuler les éléments de la page.",
)
_CADRE_IRCC = _cadre(
    "ircc", "ircc_permis_etudes", "https://portal-portail.apps.cic.gc.ca/signin?lang=fr", "/demo/ircc",
    "Portail interactif IRCC Canada", "Contrôleur de page : portail IRCC Canada",
    "Cliquez sur « 1. Ouvrir le portail IRCC » ou donnez une consigne à droite pour inspecter et remplir les champs.",
)

HTML_CAMPUS_FRANCE = (
    _STYLE_DEMARCHES
    + """
    <!-- Campus France -->
    <section id="vue-campus-france" class="vue-ecran vue-demarche cache">
      <header class="page-entete">
        <div>
          <h2>Campus France — Études en France</h2>
          <p class="lead">Préparez les vœux et les lettres de motivation, puis laissez le co-pilote pré-remplir le portail. Il s'arrête toujours avant la certification et l'envoi.</p>
        </div>
        <div class="page-actions">
          <button class="btn btn-contour" type="button" onclick="executerActionDomRapide('campus_france', 'focus_fenetre')">[[i:moniteur]]Fenêtre du navigateur au premier plan</button>
          <button id="btn-creer-tache-cf" class="btn btn-secondaire" type="button">[[i:validation]]Suivi de la tâche</button>
        </div>
      </header>

      <section class="carte" id="carte-voeux" aria-labelledby="titre-voeux">
        <div class="carte-entete">
          <div>
            <span class="surtitre">Étape préalable</span>
            <h3 id="titre-voeux">Vœux de formation et lettres de motivation</h3>
            <p>Dossier actif : <strong id="voeux-candidat-actif">Aucun</strong>. Chaque lettre est rédigée en brouillon, relue par vous, puis validée. Seuls les vœux validés vont au panier.</p>
          </div>
          <span id="voeux-compteur" class="badge badge-nu" title="Vœux enregistrés sur 7 possibles">— / 7</span>
        </div>

        <details class="guide-bloc" open>
          <summary>Faits du parcours utilisés pour rédiger les lettres (aucune identité n'est transmise à l'IA)</summary>
          <div class="grille-2">
            <label class="champ" for="faits-parcours">Parcours
              <textarea id="faits-parcours" rows="4" placeholder="Ex : 2023-2025 : Master Linguistique et didactique, Université de Béjaïa, moyenne 13,16/20"></textarea>
              <span class="champ-aide">Une ligne par étape, du plus ancien au plus récent.</span>
            </label>
            <label class="champ" for="faits-points">Points forts vérifiables
              <textarea id="faits-points" rows="4" placeholder="Ex : Mémoire de master noté 16/20"></textarea>
              <span class="champ-aide">Une ligne par point, avec la note ou la preuve.</span>
            </label>
            <label class="champ" for="faits-langues">Langues et certificats
              <textarea id="faits-langues" rows="3" placeholder="Ex : Anglais 17/20 en M1 ; TCF B2 (si disponible)"></textarea>
              <span class="champ-aide">Une ligne par langue ou par test.</span>
            </label>
            <label class="champ" for="faits-projet">Projet professionnel ou de recherche
              <textarea id="faits-projet" rows="3" placeholder="Ce que le candidat veut faire après la formation"></textarea>
            </label>
          </div>
          <p class="banniere-regle note-regle">N'écrivez ici ni nom, ni date de naissance, ni numéro de passeport, ni e-mail, ni téléphone. Ce que vous ne renseignez pas apparaît comme « À COMPLÉTER » dans la lettre.</p>
        </details>

        <h4 class="sous-titre-carte">Ajouter un vœu</h4>
        <div class="form-voeu">
          <div class="grille-form">
            <label class="champ" for="voeu-intitule">Intitulé exact de la formation <span class="requis" aria-hidden="true">*</span>
              <input id="voeu-intitule" type="text" placeholder="Ex : Master Traitement automatique des langues" />
              <span class="champ-aide">Tel qu'il apparaît dans le catalogue Études en France.</span>
            </label>
            <label class="champ" for="voeu-etablissement">Établissement <span class="requis" aria-hidden="true">*</span>
              <input id="voeu-etablissement" type="text" placeholder="Ex : Université de Lorraine" />
            </label>
            <label class="champ" for="voeu-niveau">Niveau
              <select id="voeu-niveau">
                <option>Master 1</option><option>Master 2</option><option>Licence 3</option><option>Licence 2</option>
                <option>Licence 1</option><option>Ingénieur</option><option>Autre</option>
              </select>
            </label>
            <label class="champ" for="voeu-voie">Voie
              <select id="voeu-voie">
                <option value="hors_dap" selected>Hors DAP (L2, L3, Master, Ingénieur…)</option>
                <option value="dap_blanche">DAP Blanche (Licence 1)</option>
                <option value="dap_jaune">DAP Jaune (Architecture)</option>
              </select>
              <span class="champ-aide">DAP Blanche : 3 choix ; DAP Jaune : 2 choix et portfolio.</span>
            </label>
            <label class="champ" for="voeu-justification">Pourquoi cette formation ?
              <input id="voeu-justification" type="text" placeholder="Ex : cours de TAL pour langues peu dotées" />
              <span class="champ-aide">Facultatif : personnalise la lettre.</span>
            </label>
          </div>
          <div class="pile-actions">
            <button id="btn-ajouter-voeu" class="btn btn-primaire" type="button">[[i:plus]]Ajouter ce vœu</button>
            <button id="btn-actualiser-voeux" class="btn btn-fantome" type="button">[[i:actualiser]]Actualiser la liste</button>
          </div>
        </div>

        <div id="liste-voeux" class="liste-voeux">
          <div class="etat-vide">"""
    + _ILLU_DOSSIER
    + """<strong>Aucun dossier choisi.</strong><span>Choisissez un dossier dans « Étudiants et fiches » pour gérer ses vœux.</span></div>
        </div>

        <div class="carte-pied">
          <p class="note">Le co-pilote reporte dans le panier du portail les vœux validés et leur lettre, sans rien soumettre.</p>
          <button id="btn-panier-voeux" class="btn btn-secondaire" type="button" onclick="lancerActionNavigateur('campus_france', 'ajouter_voeux_panier')">Ajouter les vœux validés au panier (co-pilote)</button>
        </div>
      </section>

      <section class="carte" aria-labelledby="titre-copilote-cf">
        <div class="carte-entete">
          <div>
            <span class="surtitre">Pré-remplissage du portail</span>
            <h3 id="titre-copilote-cf"><span class="point-vert-pulsant" aria-hidden="true"></span>Co-pilote navigateur</h3>
            <p>Pilotage direct de votre navigateur, sans capture d'écran : barre latérale dans la page, curseur animé et consignes en langage naturel.</p>
          </div>
          <span class="badge badge-ok">Temps réel</span>
        </div>

        <div class="grille-2">
          <label class="champ" for="cf-cible-navigateur">Portail cible dans le navigateur
            <select id="cf-cible-navigateur" onchange="changerCibleNavigateurDirect('campus_france')">
              <option value="campus_france_officiel" data-url="https://etudesenfrance.diplomatie.gouv.fr/" selected>Site officiel Études en France (etudesenfrance.diplomatie.gouv.fr)</option>
              <option value="demo_campus_france" data-url="http://portail.local/demo/campus-france">Portail interactif Études en France (mode direct intégré)</option>
              <option value="campus_france_algerie" data-url="https://www.algerie.campusfrance.org/horaires-d-attention-au-public">Site Campus France Algérie (algerie.campusfrance.org)</option>
              <option value="paiement_ifa_algerie" data-url="https://paiement.if-algerie.com">Portail de paiement IFA Algérie (paiement.if-algerie.com)</option>
            </select>
          </label>
          <label class="case" style="align-self:end;">
            <input id="cf-fenetre-visible" type="checkbox" checked />
            <span>Piloter ma vraie fenêtre Chrome, Edge ou Chromium (avec barre latérale du co-pilote)</span>
          </label>
        </div>

        <h4 class="sous-titre-carte">Étapes en un clic</h4>
        <div class="demarche-raccourci">
          <p><strong>Le plus rapide :</strong> le co-pilote remplit tout le dossier, joint les pièces et s'arrête avant les cases de certification et l'envoi (règle 1).</p>
          <div class="pile-actions">
            <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('campus_france', 'ouvrir_portail')">[[i:externe]]Ouvrir le site</button>
            <button class="btn btn-primaire" type="button" onclick="lancerActionNavigateur('campus_france', 'preremplissage_complet')">Tout remplir et s'arrêter avant l'envoi</button>
          </div>
        </div>
        <p class="titre-mini">Ou étape par étape (guide Études en France, septembre 2026)</p>
        <ol class="parcours" aria-label="Étapes du portail Études en France">
          <li><div class="parcours-texte"><strong>Compte Études en France</strong><span>Créer le compte, ou se connecter avec les identifiants du coffre (règle 3).</span></div>
            <div class="parcours-actions">
              <button class="btn btn-contour btn-sm" type="button" onclick="lancerActionNavigateur('campus_france', 'inscription_compte')">S'inscrire</button>
              <button class="btn btn-contour btn-sm" type="button" onclick="lancerActionNavigateur('campus_france', 'connexion_compte')">Se connecter</button>
            </div></li>
          <li><div class="parcours-texte"><strong>Espace étudiant</strong><span>Identité, passeport et antenne Espace Campus France.</span></div>
            <div class="parcours-actions"><button class="btn btn-contour btn-sm" type="button" onclick="lancerActionNavigateur('campus_france', 'preremplir_espace_etudiant')">Pré-remplir l'identité</button></div></li>
          <li><div class="parcours-texte"><strong>Scolarité et langues</strong><span>Au moins 2 activités ; français : plus de 1000 h.</span></div>
            <div class="parcours-actions"><button class="btn btn-contour btn-sm" type="button" onclick="lancerActionNavigateur('campus_france', 'preremplir_scolarite_et_langues')">Pré-remplir la scolarité</button></div></li>
          <li><div class="parcours-texte"><strong>Panier et motivations</strong><span>7 formations au maximum ; 4 000 caractères par lettre.</span></div>
            <div class="parcours-actions"><button class="btn btn-contour btn-sm" type="button" onclick="lancerActionNavigateur('campus_france', 'preremplir_panier_formations_et_motivations')">Remplir le panier</button></div></li>
          <li><div class="parcours-texte"><strong>Paiement et rendez-vous</strong><span>Frais de dossier : 20 000 DZD plein tarif, puis entretien.</span></div>
            <div class="parcours-actions"><button class="btn btn-contour btn-sm" type="button" onclick="lancerActionNavigateur('campus_france', 'preparer_paiement_et_rdv')">Préparer le paiement</button></div></li>
          <li><div class="parcours-texte"><strong>Dossier pré-consulaire</strong><span>Après l'acceptation, en 4 étapes.</span></div>
            <div class="parcours-actions"><button class="btn btn-contour btn-sm" type="button" onclick="lancerActionNavigateur('campus_france', 'preremplir_dossier_preconsulaire')">Préparer le dossier</button></div></li>
        </ol>

        <h4 class="sous-titre-carte">Navigateur et assistant</h4>
        <div class="workspace-cowork">"""
    + _CADRE_CF
    + """

          <div class="panneau-copilote-chat">
            <div class="entete-chat"><strong>Assistant co-pilote</strong><span class="aide">Langage naturel et voix</span></div>
            <div>
              <span class="aide">Exemples de demandes (cliquez pour les envoyer) :</span>
              <div class="chips">
                <button class="puce-cmd" type="button" onclick="envoyerConsigneRapideCopilote('campus_france', 'Ouvre le vrai site Études en France dans mon navigateur')">Ouvrir le vrai site</button>
                <button class="puce-cmd" type="button" onclick="envoyerConsigneRapideCopilote('campus_france', 'Clique sur S’inscrire et pré-remplis mon compte')">Aller sur « S'inscrire »</button>
                <button class="puce-cmd" type="button" onclick="envoyerConsigneRapideCopilote('campus_france', 'Analyse cette page et explique-moi ce qu’il faut faire')">Analyser cette page</button>
                <button class="puce-cmd" type="button" onclick="envoyerConsigneRapideCopilote('campus_france', 'Mets Oran comme ville et Université Paris-Saclay comme établissement')">Changer ville et université</button>
                <button class="puce-cmd" type="button" onclick="envoyerConsigneRapideCopilote('campus_france', 'Remplis mes motivations pour ma formation')">Rédiger les motivations</button>
                <button class="puce-cmd" type="button" onclick="envoyerConsigneRapideCopilote('campus_france', 'Quels sont les frais en DZD et les dates limites 2026-2027 ?')">Frais et dates limites</button>
              </div>
            </div>
            <div id="fil-copilote-cf" class="fil-copilote" role="log">
              <div class="bulle-copilote-ia">
                <strong>Co-pilote prêt.</strong> Dites-moi en français ce que je dois faire dans votre navigateur (par exemple <em>« remplis mon identité »</em>, <em>« clique sur Se connecter »</em>, <em>« descends en bas de la page »</em> ou <em>« remplis tout sans soumettre »</em>).
              </div>
            </div>
            <div class="barre-saisie">
              <input id="cf-instruction-agent" type="text" value="Pré-remplir tout le dossier Études en France du candidat (identité, passeport, scolarité, langues, panier de formations et motivation) et enregistrer le brouillon" placeholder="Parlez naturellement à l'agent" aria-label="Consigne pour le co-pilote" />
              <button id="btn-dictee-cf" class="btn btn-secondaire btn-icone" type="button" style="margin:0;" onclick="demarrerDicteeVocale('campus_france')" title="Dicter la consigne à la voix" aria-label="Dicter la consigne à la voix">[[i:micro]]</button>
              <button id="btn-piloter-cf-instruction" class="btn btn-primaire" type="button" style="margin:0;">Exécuter</button>
            </div>
            <div id="zone-retour-cf" class="panneau-texte zone-retour-demarche">
              <p class="note">Choisissez un dossier, puis donnez une consigne ci-dessus ou lancez une étape en un clic. Le compte rendu et le suivi de la tâche s'affichent ici.</p>
            </div>
          </div>
        </div>
      </section>

      <section class="carte" aria-labelledby="titre-guide-cf">
        <div class="carte-entete">
          <div>
            <span class="surtitre">Référence</span>
            <h3 id="titre-guide-cf">Guide officiel « Études en France — septembre 2026 »</h3>
            <p>Campus France Algérie : calendrier, frais, comptes et règles du panier.</p>
          </div>
        </div>
        <details class="guide-bloc" open>
          <summary>Calendrier de la session 2026–2027 et frais de dossier (DZD)</summary>
          <ul class="liste-propre">
            <li><strong>Hors DAP (L2, L3, Master 1 et 2, écoles d'ingénieurs et de commerce) :</strong> ouverture le <strong>1er octobre 2026</strong> ; date limite de dépôt et de paiement le <strong>30 novembre 2026</strong> ; entretiens jusqu'au <strong>15 mars 2027</strong> ; choix définitif avant le <strong>31 mai 2027</strong>.</li>
            <li><strong>DAP (L1 université, écoles d'architecture ENSA, BUT, licence professionnelle) :</strong> ouverture le <strong>1er octobre 2026</strong> ; date limite le <strong>15 décembre 2026</strong> ; entretiens jusqu'au <strong>15 mars 2027</strong> ; choix définitif avant le <strong>31 mai 2027</strong>.</li>
            <li><strong>CPGE, BTS, DCG :</strong> à partir de <strong>janvier 2027</strong> sur Parcoursup.</li>
            <li><strong>Dossier pré-consulaire (« Je suis accepté » ou établissements privés non connectés) :</strong> dès la réception de l'acceptation, au minimum <strong>45 jours avant la rentrée</strong>.</li>
            <li><strong>Frais de dossier Algérie :</strong> plein tarif <strong>20 000 DZD</strong> ; demi-tarif <strong>10 000 DZD</strong> (bac français depuis moins de 4 ans et candidat de moins de 22 ans, ou acceptation Campus Art) ; <strong>gratuité</strong> pour les boursiers du gouvernement français, les bacheliers du LIAD de l'année en cours et les agents de l'Institut français d'Algérie. Paiement sur <code>paiement.if-algerie.com</code>.</li>
            <li><strong>5 antennes Espace Campus France Algérie :</strong> Alger (<code>ecf.alger@if-algerie.com</code>), Annaba (<code>ecf.annaba@if-algerie.com</code>), Constantine (<code>ecf.constantine@if-algerie.com</code>), Oran (<code>ecf.oran@if-algerie.com</code>), Tlemcen (<code>ecf.tlemcen@if-algerie.com</code>).</li>
          </ul>
        </details>
        <details class="guide-bloc">
          <summary>Mon compte et mon espace étudiant (identité, scolarité, compétences linguistiques)</summary>
          <ul class="liste-propre">
            <li><strong>Inscription et connexion :</strong> bouton « S'inscrire » sur <code>https://etudesenfrance.diplomatie.gouv.fr/</code> (Espace Campus France Algérie, activation par e-mail sous 48 h). Le compte est bloqué <strong>30 minutes après 5 mots de passe erronés</strong>.</li>
            <li><strong>Informations personnelles :</strong> identité, photo d'identité au format passeport (JPG, PNG ou PDF, 10 Mo maximum), passeport valide (numéro, date limite, copie), coordonnées (l'adresse et le téléphone déterminent l'antenne ECF) et statut particulier (« Je ne suis concerné par aucun de ces statuts particuliers »).</li>
            <li><strong>Dossier de scolarité :</strong> CV obligatoire et <strong>au moins 2 activités</strong> dans « Parcours scolaire et professionnel » (du lycée au bac pour Bac+1 ; du bac à la dernière année d'études supérieures pour Bac+2 et plus ; commentaire limité à 1 000 caractères).</li>
            <li><strong>Compétences linguistiques :</strong> pour un baccalauréat algérien ou non européen suivi en français, choisir « Oui », volume « Plus de 1000 heures », durée « 4 ans et plus », niveau atteint « Avancé ». Ajouter le test TCF ou DELF/DALF avec « + Ajouter un test », puis renseigner le niveau d'anglais.</li>
          </ul>
        </details>
        <details class="guide-bloc">
          <summary>Dossier de candidature (panier de 7 choix maximum) et dossier pré-consulaire</summary>
          <ul class="liste-propre">
            <li><strong>Règles du panier (7 formations maximum) :</strong> DAP Blanche (L1 : jusqu'à 3 choix), DAP Jaune (architecture ENSA : 2 choix obligatoires et portfolio), Hors DAP (L2, L3, M1, M2, ingénieur, commerce : jusqu'à 7 choix). Vérifier le badge « OUVERT À LA CANDIDATURE ».</li>
            <li><strong>Texte de motivation :</strong> obligatoire pour chaque formation du panier (jusqu'à <strong>4 000 caractères</strong>), puis « Enregistrer ».</li>
            <li><strong>Envoi (règle 1) :</strong> l'agent s'arrête toujours avant les 2 cases de certification et le bouton « Soumettre mon dossier de candidature ».</li>
            <li><strong>Dossier pré-consulaire (« Je suis accepté ») :</strong> sélection de la formation acceptée via Études en France, ou ajout d'une acceptation papier ou d'un programme d'échange en <strong>4 étapes</strong>. Il donne l'attestation d'acceptation (identifiant <code>DZXX-XXXXX</code>) et <strong>-50 % sur les frais de visa long séjour</strong> chez CAPAGO.</li>
          </ul>
        </details>
      </section>
    </section>
"""
)

HTML_IRCC = (
    """
    <!-- IRCC Canada -->
    <section id="vue-ircc" class="vue-ecran vue-demarche cache">
      <header class="page-entete">
        <div>
          <h2>IRCC Canada — Permis d'études</h2>
          <p class="lead">Le co-pilote contrôle le seuil financier (<strong>20 635 $ CAD</strong>, soit environ <strong>14 500 EUR</strong>), la LAP/PAL ou le CAQ et l'admission EED/DLI. Il s'arrête avant la signature et la transmission (règle 1).</p>
        </div>
        <div class="page-actions">
          <button class="btn btn-contour" type="button" onclick="executerActionDomRapide('ircc_permis_etudes', 'focus_fenetre')">[[i:moniteur]]Fenêtre du navigateur au premier plan</button>
          <button id="btn-creer-tache-ircc" class="btn btn-secondaire" type="button">[[i:validation]]Suivi de la tâche</button>
        </div>
      </header>

      <section class="carte" aria-labelledby="titre-copilote-ircc">
        <div class="carte-entete">
          <div>
            <span class="surtitre">Pré-remplissage du portail</span>
            <h3 id="titre-copilote-ircc"><span class="point-vert-pulsant" aria-hidden="true"></span>Co-pilote navigateur</h3>
            <p>Demande de permis d'études : identité, établissement désigné (EED/DLI), preuve de fonds et pièces justificatives.</p>
          </div>
          <span class="badge badge-ok">Temps réel</span>
        </div>
        <div class="grille-2">
          <label class="champ" for="ircc-cible-navigateur">Portail cible dans le navigateur
            <select id="ircc-cible-navigateur" onchange="changerCibleNavigateurDirect('ircc_permis_etudes')">
              <option value="ircc_officiel" data-url="https://portal-portail.apps.cic.gc.ca/signin?lang=fr" selected>Portail officiel IRCC Canada (portal-portail.apps.cic.gc.ca)</option>
              <option value="demo_ircc" data-url="http://portail.local/demo/ircc">Portail interactif IRCC (mode direct intégré)</option>
              <option value="ircc_canada_info" data-url="https://www.canada.ca/fr/immigration-refugies-citoyennete/services/etudier-canada/permis-etudes.html">Page officielle Permis d'études sur Canada.ca</option>
            </select>
          </label>
          <label class="case" style="align-self:end;">
            <input id="ircc-fenetre-visible" type="checkbox" checked />
            <span>Piloter ma vraie fenêtre Chrome, Edge ou Chromium (avec barre latérale du co-pilote)</span>
          </label>
        </div>

        <h4 class="sous-titre-carte">Étapes en un clic</h4>
        <div class="demarche-raccourci">
          <p><strong>Le plus rapide :</strong> le co-pilote pré-remplit toute la demande, joint les pièces et s'arrête avant la signature et la transmission (règle 1).</p>
          <div class="pile-actions">
            <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('ircc_permis_etudes', 'ouvrir_portail')">[[i:externe]]Ouvrir le portail IRCC</button>
            <button class="btn btn-primaire" type="button" onclick="lancerActionNavigateur('ircc_permis_etudes', 'preremplissage_complet')">Tout pré-remplir et s'arrêter avant l'envoi</button>
          </div>
        </div>
        <p class="titre-mini">Ou étape par étape</p>
        <ol class="parcours" aria-label="Étapes du portail IRCC">
          <li><div class="parcours-texte"><strong>Identité et passeport</strong><span>État civil, passeport et coordonnées du candidat.</span></div>
            <div class="parcours-actions"><button class="btn btn-contour btn-sm" type="button" onclick="lancerActionNavigateur('ircc_permis_etudes', 'preremplir_identite_ircc')">Pré-remplir l'identité</button></div></li>
          <li><div class="parcours-texte"><strong>Établissement et fonds</strong><span>Établissement désigné (DLI) et preuve de fonds : 20 635 CAD au minimum.</span></div>
            <div class="parcours-actions"><button class="btn btn-contour btn-sm" type="button" onclick="lancerActionNavigateur('ircc_permis_etudes', 'preremplir_dli_fonds_ircc')">Pré-remplir DLI et fonds</button></div></li>
          <li><div class="parcours-texte"><strong>Pièces justificatives</strong><span>Les 6 pièces : PAL ou CAQ, IMM 5645, etc.</span></div>
            <div class="parcours-actions"><button class="btn btn-contour btn-sm" type="button" onclick="lancerActionNavigateur('ircc_permis_etudes', 'televerser_pieces_ircc')">Téléverser les pièces</button></div></li>
        </ol>

        <h4 class="sous-titre-carte">Navigateur et assistant</h4>
        <div class="workspace-cowork">"""
    + _CADRE_IRCC
    + """

          <div class="panneau-copilote-chat">
            <div class="entete-chat"><strong>Assistant co-pilote IRCC</strong><span class="aide">Langage naturel et voix</span></div>
            <div>
              <span class="aide">Exemples de demandes :</span>
              <div class="chips">
                <button class="puce-cmd" type="button" onclick="envoyerConsigneRapideCopilote('ircc_permis_etudes', 'Ouvre le vrai portail officiel IRCC Canada')">Ouvrir le vrai portail</button>
                <button class="puce-cmd" type="button" onclick="envoyerConsigneRapideCopilote('ircc_permis_etudes', 'Analyse cette page IRCC et dis-moi quoi remplir')">Analyser la page</button>
                <button class="puce-cmd" type="button" onclick="envoyerConsigneRapideCopilote('ircc_permis_etudes', 'Mets Université Laval comme établissement et 21000 euros comme fonds')">Changer DLI et fonds</button>
                <button class="puce-cmd" type="button" onclick="envoyerConsigneRapideCopilote('ircc_permis_etudes', 'Remplis tout le formulaire IRCC et téléverse les pièces sans transmettre')">Tout remplir sans transmettre</button>
              </div>
            </div>
            <div id="fil-copilote-ircc" class="fil-copilote" role="log">
              <div class="bulle-copilote-ia">
                <strong>Co-pilote IRCC prêt.</strong> Demandez-moi une action en français (par exemple <em>« remplis mon identité et le DLI »</em>, <em>« mets 19000 euros comme fonds »</em> ou <em>« quelles sont les règles PAL/CAQ ? »</em>).
              </div>
            </div>
            <div class="barre-saisie">
              <input id="ircc-instruction-agent" type="text" value="Pré-remplir toute la demande de permis d'études IRCC (identité, passeport, établissement DLI, ressources financières et pièces justificatives) et sauvegarder le brouillon" placeholder="Parlez naturellement à l'agent IRCC" aria-label="Consigne pour le co-pilote IRCC" />
              <button id="btn-dictee-ircc" class="btn btn-secondaire btn-icone" type="button" style="margin:0;" onclick="demarrerDicteeVocale('ircc_permis_etudes')" title="Dicter la consigne à la voix" aria-label="Dicter la consigne à la voix">[[i:micro]]</button>
              <button id="btn-piloter-ircc-instruction" class="btn btn-primaire" type="button" style="margin:0;">Exécuter</button>
            </div>
            <div id="zone-retour-ircc" class="panneau-texte zone-retour-demarche">
              <p class="note">Choisissez un dossier, puis donnez une consigne ci-dessus ou lancez une étape en un clic. Le compte rendu et le suivi de la tâche s'affichent ici.</p>
            </div>
          </div>
        </div>
      </section>
    </section>
"""
)

HTML_VALIDATION = """
    <!-- Centre de validation -->
    <section id="vue-validation-humaine" class="vue-ecran cache">
      <header class="page-entete">
        <div>
          <h2>Centre de validation</h2>
          <p class="lead">Aucune demande officielle n'est jamais envoyée par l'agent. Contrôlez la capture et le récapitulatif de chaque dossier avant de valider.</p>
        </div>
        <div class="page-actions">
          <button id="btn-rafraichir-validations" class="btn btn-secondaire" type="button">[[i:actualiser]]Actualiser</button>
        </div>
      </header>
      <!-- zone:lien-recaps -->
      <div id="liste-centre-validation" class="pile">Chargement des dossiers...</div>
    </section>
"""

HTML_AUDIT = """
    <!-- Journal d'audit -->
    <section id="vue-historique-erreurs" class="vue-ecran cache">
      <header class="page-entete">
        <div>
          <h2>Journal d'audit</h2>
          <p class="lead">Historique immuable des opérations du bureau. Il ne contient aucune donnée personnelle (règle 5).</p>
        </div>
        <div class="page-actions">
          <button id="btn-rafraichir-audit" class="btn btn-secondaire" type="button">[[i:actualiser]]Actualiser</button>
        </div>
      </header>
      <div class="table-wrap" tabindex="0" role="region" aria-label="Tableau du journal d'audit">
        <table id="table-audit">
          <caption class="sr-only">Journal d'audit : date et heure, opération, résultat, ressource et résumé</caption>
          <thead><tr><th scope="col">Date et heure (UTC)</th><th scope="col">Opération</th><th scope="col">Résultat</th><th scope="col">Ressource</th><th scope="col">Résumé</th></tr></thead>
          <tbody><tr><td colspan="5" class="etat-vide">Cliquez sur « Actualiser » pour charger le journal.</td></tr></tbody>
        </table>
      </div>
    </section>
"""

HTML_PARAMETRES = """
    <!-- Abonnement et sauvegardes -->
    <section id="vue-parametres" class="vue-ecran cache">
      <header class="page-entete">
        <div>
          <h2>Abonnement et sauvegardes</h2>
          <p class="lead">Votre forfait, l'état des portails, les postes agents locaux et les sauvegardes chiffrées du bureau.</p>
        </div>
      </header>
      <div class="accueil-grille" style="align-items:start;">
        <div class="carte">
          <h3>Sauvegardes et abonnement</h3>
          <div class="pile-actions" style="margin:0 0 16px;">
            <button id="btn-voir-abonnement" class="btn btn-primaire" type="button">Afficher mon abonnement et l'état des portails</button>
            <button id="btn-creer-sauvegarde" class="btn btn-secondaire" type="button">Créer une sauvegarde chiffrée (.be.enc)</button>
          </div>
          <div id="zone-sauvegardes-abo" class="panneau-texte">Choisissez une action ci-dessus : la sauvegarde est chiffrée en AES-256-GCM, l'abonnement affiche votre quota et l'homologation des portails (règles 6 et 7).</div>
        </div>
        <div class="carte">
          <h3>Enrôler un poste agent local</h3>
          <p class="aide">Chaque poste Windows du bureau qui exécute l'agent reçoit sa propre clé d'accès.</p>
          <label>Nom du poste Windows <input id="nom-machine-agent" type="text" value="PC-BUREAU-ALGER-01" /></label>
          <div class="pile-actions"><button id="btn-enroler-agent" class="btn btn-primaire" type="button">Enrôler ce poste et générer sa clé</button></div>
          <div id="zone-jeton-agent" class="panneau-texte cache" style="margin-top:12px;"></div>
        </div>
      </div>
    </section>
"""

HTML_PROCEDURES = (
    """
    <!-- Procédures du bureau -->
    <section id="vue-procedures" class="vue-ecran vue-demarche cache">
      <header class="page-entete">
        <div>
          <h2>Procédures du bureau</h2>
          <p class="lead">Les procédures de base (Campus France, IRCC…) sont communes. Ajoutez-en ou personnalisez-les : vos changements ne concernent que votre bureau et s'appliquent aussitôt. Modification réservée aux administrateurs.</p>
        </div>
        <div class="page-actions">
          <button id="btn-nouvelle-procedure" class="btn btn-primaire cache" type="button">[[i:plus]]Nouvelle procédure</button>
        </div>
      </header>

      <div id="ia-statut-procedures" class="ia-statut">Assistant IA : état en cours de vérification...</div>

      <section id="carte-generation-ia" class="carte cache" aria-labelledby="titre-generation-ia">
        <div class="carte-entete">
          <div>
            <span class="surtitre">Assistant IA</span>
            <h3 id="titre-generation-ia">Créer une procédure à partir d'un texte officiel</h3>
            <p>L'assistant prépare un brouillon : rien n'est enregistré tant que vous n'avez pas relu l'éditeur et cliqué sur « Enregistrer la procédure ».</p>
          </div>
        </div>
        <label class="champ" for="ia-texte-source">Texte officiel de la démarche
          <textarea id="ia-texte-source" class="ia-texte-source" placeholder="Collez ici le guide ou la page officielle de la démarche"></textarea>
          <span id="ia-compteur-texte" class="ia-compteur champ-aide">0 / 30 000 caractères (minimum 80)</span>
        </label>
        <div class="pile-actions">
          <button id="btn-generer-procedure-ia" class="btn btn-primaire" type="button">Générer un brouillon</button>
        </div>
        <div id="zone-retour-generation-ia" class="panneau-texte cache" style="margin-top:12px;"></div>
      </section>

      <section class="carte" aria-labelledby="titre-liste-procedures">
        <div class="carte-entete">
          <div>
            <h3 id="titre-liste-procedures">Procédures disponibles</h3>
            <p>Ouvrez une procédure pour voir ses pièces, ses étapes et sa veille réglementaire.</p>
          </div>
          <button id="btn-rafraichir-procedures" class="btn btn-fantome btn-sm" type="button">[[i:actualiser]]Actualiser</button>
        </div>
        <div class="table-wrap" tabindex="0" role="region" aria-label="Tableau des procédures disponibles">
          <table id="table-procedures">
            <caption class="sr-only">Procédures disponibles : procédure, origine, version et actions</caption>
            <thead><tr><th scope="col">Procédure</th><th scope="col">Origine</th><th scope="col" class="num">Version</th><th scope="col">Actions</th></tr></thead>
            <tbody aria-busy="true"><tr class="sr-only"><td colspan="4">Chargement des procédures</td></tr>"""
    + _LIGNE_SQUELETTE_PROC * 3
    + """</tbody>
          </table>
        </div>
      </section>

      <section id="carte-editeur-procedure" class="carte cache" aria-labelledby="titre-editeur-procedure">
        <div class="carte-entete">
          <h3 id="titre-editeur-procedure">Éditeur de procédure</h3>
        </div>
        <div id="bloc-ia-editeur" class="banniere-regle cache">
          <strong>Brouillon généré par l'IA : relisez chaque point avant d'enregistrer.</strong>
          <div id="titre-avertissements-ia" style="margin-top:8px;">Points signalés par l'assistant :</div>
          <ul id="liste-avertissements-ia" class="liste-propre"></ul>
        </div>
        <div id="encart-champs-avances" class="panneau-texte cache" style="margin-bottom:16px;">
          <strong>Champs avancés présents dans cette procédure</strong>
          <div class="aide" style="margin:4px 0;">Lecture seule pour l'instant : l'éditeur ne sait pas encore les modifier, mais ils sont conservés tels quels à l'enregistrement.</div>
          <ul id="liste-champs-avances" class="liste-propre"></ul>
        </div>
        <fieldset id="fs-editeur">
          <legend class="sr-only">Définition de la procédure</legend>
          <ol class="proc-blocs">
            <li class="proc-bloc">
              <div class="proc-bloc-entete"><div><h4>Identité de la procédure</h4><p>Le code sert aux échanges techniques ; le libellé est celui que voient les conseillers.</p></div></div>
              <div class="grille-form">
                <label class="champ" for="proc-code">Code technique <span class="requis" aria-hidden="true">*</span>
                  <input id="proc-code" type="text" placeholder="ex : visa_touristique" />
                  <span class="champ-aide">Minuscules, chiffres et tirets bas. Non modifiable après création.</span>
                </label>
                <label class="champ" for="proc-libelle">Libellé affiché <span class="requis" aria-hidden="true">*</span>
                  <input id="proc-libelle" type="text" placeholder="ex : Visa touristique Schengen" />
                </label>
                <label class="champ" for="proc-seuil">Seuil de fonds recommandé (EUR)
                  <input id="proc-seuil" type="number" min="0" />
                  <span class="champ-aide">Facultatif.</span>
                </label>
              </div>
              <label class="champ" for="proc-description">Description
                <input id="proc-description" type="text" />
                <span class="champ-aide">Facultatif : une phrase sur l'objet de la démarche.</span>
              </label>
            </li>
            <li class="proc-bloc">
              <div class="proc-bloc-entete"><div><h4>Informations du candidat</h4><p>Champs de la fiche obligatoires avant tout pré-remplissage.</p></div></div>
              <div id="proc-champs" class="liste-cases"></div>
            </li>
            <li class="proc-bloc">
              <div class="proc-bloc-entete"><div><h4>Pièces requises</h4><p>Chaque pièce peut exiger une date d'expiration et une validité minimale restante.</p></div></div>
              <datalist id="liste-types-pieces"></datalist>
              <div id="proc-pieces"></div>
              <button id="btn-ajouter-piece" class="btn btn-contour btn-sm" type="button">[[i:plus]]Ajouter une pièce</button>
            </li>
            <li class="proc-bloc">
              <div class="proc-bloc-entete"><div><h4>Étapes de la tâche</h4><p>Facultatif. Laissez vide pour garder les 4 étapes standard : vérification, session portail, pré-remplissage, arrêt avant validation humaine.</p></div></div>
              <div id="proc-etapes"></div>
              <button id="btn-ajouter-etape" class="btn btn-contour btn-sm" type="button">[[i:plus]]Ajouter une étape</button>
            </li>
            <li class="proc-bloc">
              <div class="proc-bloc-entete"><div><h4>Veille réglementaire</h4><p>Points à connaître, avec leur référence officielle.</p></div></div>
              <div id="proc-veille"></div>
              <button id="btn-ajouter-veille" class="btn btn-contour btn-sm" type="button">[[i:plus]]Ajouter un point de veille</button>
            </li>
          </ol>
        </fieldset>
        <div class="carte-pied editeur-pied">
          <button id="btn-enregistrer-procedure" class="btn btn-primaire" type="button">Enregistrer la procédure</button>
          <button id="btn-fermer-editeur-procedure" class="btn btn-contour" type="button">Fermer l'éditeur</button>
        </div>
        <div id="zone-retour-procedure" class="panneau-texte cache" style="margin-top:12px;"></div>
      </section>
    </section>
"""
)
