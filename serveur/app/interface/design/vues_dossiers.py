"""Écrans « Dossiers » : étudiants et fiches, pièces (et coffre, inséré au marqueur), conseiller.

Gabarits HTML seuls : toute la logique est dans les modules `js_*`. Les identifiants des champs
et des boutons sont utilisés par ce JavaScript et par les tests : ne pas les renommer.
Les jetons [[i:nom]] sont remplacés par des icônes SVG à l'assemblage.

`CSS_DOSSIERS` : petits compléments propres à ces trois écrans (préfixe `.ecran-dossiers`),
uniquement à partir des tokens du système de design. Aucun antislash.
"""

from __future__ import annotations

from app.interface.design.vues_ouverture_pc import HTML_OUVERTURE_PC

CSS_DOSSIERS = """
    <style>
      /* Compléments locaux des écrans Étudiants, Pièces et Conseiller (tokens uniquement). */
      .ecran-dossiers .cellule-actions { display: flex; flex-wrap: wrap; gap: var(--e2); }
      .ecran-dossiers .cellule-actions .btn { margin: 0; }
      .ecran-dossiers .etu-identite { display: flex; align-items: center; gap: var(--e3); min-width: 0; }
      .ecran-dossiers .avatar-initiales { font-family: var(--police-titre); font-size: var(--t-xs); font-weight: 700; letter-spacing: 0.02em; }
      .ecran-dossiers tr.ligne-active .avatar-initiales { background: var(--accent-plein); color: var(--sur-accent); }
      .ecran-dossiers .etu-progression { min-width: 120px; }
      .ecran-dossiers tbody td:first-child { min-width: 250px; }
      .ecran-dossiers tbody td:last-child { min-width: 190px; }
      .ecran-dossiers .etu-identite > :first-child { flex-shrink: 0; }
      .ecran-dossiers .etu-identite > :last-child { flex: 1; overflow-wrap: anywhere; }
      .ecran-dossiers .cellule-actions .btn { white-space: nowrap; }
      .ecran-dossiers .table-wrap table { min-width: 900px; }
      .ecran-dossiers .barre-recherche { margin-bottom: var(--e4); }
      .ecran-dossiers .barre-recherche .btn, .ecran-dossiers .barre-saisie .btn { margin: 0; }
      .ecran-dossiers .ligne-formulaire { display: flex; flex-wrap: wrap; align-items: flex-end; gap: var(--e3); }
      .ecran-dossiers .ligne-formulaire .champ { flex: 1 1 280px; }
      .ecran-dossiers .ligne-formulaire .btn { margin: 0; }
      .ecran-dossiers .etat-vide-cellule { padding: 0; }
      .ecran-dossiers td .squelette { margin: var(--e1) 0; }
      .ecran-dossiers .espace-haut { margin-top: var(--e3); }
      .ecran-dossiers .score-zone { margin-top: var(--e4); padding-top: var(--e4); border-top: 1px solid var(--bord); }

      /* Fiche du dossier actif : sections regroupées, libellé au-dessus de la valeur */
      .ecran-dossiers .fiche-grille { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 240px), 1fr)); gap: var(--e5) var(--e4); }
      .ecran-dossiers .fiche-section { display: flex; flex-direction: column; gap: var(--e3); min-width: 0; }
      .ecran-dossiers .fiche-section h4 { margin: 0; padding-bottom: var(--e2); border-bottom: 1px solid var(--bord); }
      .ecran-dossiers .fiche-liste { display: flex; flex-direction: column; gap: var(--e3); margin: 0; }
      .ecran-dossiers .fiche-liste div { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
      .ecran-dossiers .fiche-liste dt { font-size: var(--t-xs); font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; color: var(--texte-faible); }
      .ecran-dossiers .fiche-liste dd { margin: 0; overflow-wrap: anywhere; }
      .ecran-dossiers .fiche-liste dd.fiche-vide { color: var(--texte-faible); font-style: italic; }
      .ecran-dossiers .formulaire-pied { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--e3); padding-top: var(--e4); border-top: 1px solid var(--bord); }
      .ecran-dossiers .formulaire-pied .btn { margin: 0; }
      .ecran-dossiers .champ-erreur.cache { display: none; }

      /* Zone de dépôt : le champ fichier natif couvre la zone (clic, clavier et glisser-déposer) */
      .ecran-dossiers .depot-zone { position: relative; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--e2); min-height: 150px; padding: var(--e5) var(--e4); text-align: center; background: var(--surface-2); border: 2px dashed var(--bord-fort); border-radius: var(--r-l); color: var(--texte-doux); font-weight: 400; transition: border-color var(--d1) var(--courbe), background-color var(--d1) var(--courbe); }
      .ecran-dossiers .depot-zone:hover, .ecran-dossiers .depot-zone.survol { border-color: var(--accent); background: var(--accent-doux); }
      .ecran-dossiers .depot-zone:focus-within { border-color: var(--accent); box-shadow: var(--anneau); }
      .ecran-dossiers .depot-zone input[type="file"] { position: absolute; inset: 0; width: 100%; height: 100%; min-height: 0; padding: 0; opacity: 0; cursor: pointer; }
      .ecran-dossiers .depot-icone { width: 44px; height: 44px; border-radius: var(--r-m); display: grid; place-items: center; background: var(--surface); color: var(--accent); box-shadow: var(--ombre-1); }
      .ecran-dossiers .depot-icone .ico { width: 22px; height: 22px; }
      .ecran-dossiers .depot-titre { font-weight: 600; color: var(--texte); font-size: var(--t-base); }
      .ecran-dossiers .depot-nom { font-weight: 600; color: var(--accent-fort); overflow-wrap: anywhere; }
      .ecran-dossiers .depot-grille { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr); gap: var(--e4); align-items: stretch; }
      .ecran-dossiers .depot-champs { display: flex; flex-direction: column; gap: var(--e4); }

      /* Pièces par démarche : pastille (forme + couleur) | texte | badge */
      .ecran-dossiers .completude-grille { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 340px), 1fr)); gap: var(--e4); }
      .ecran-dossiers .completude-carte { margin: 0; display: flex; flex-direction: column; gap: var(--e4); }
      .ecran-dossiers .completude-carte .carte-entete { margin: 0; align-items: flex-start; }
      .ecran-dossiers .completude-carte h4 { margin: 0; }
      .ecran-dossiers .completude-bloc { display: flex; flex-direction: column; gap: var(--e2); }
      .ecran-dossiers .completude-bloc .notif { margin: 0; }
      .ecran-dossiers .liste-pieces { list-style: none; margin: 0; padding: 0; }
      .ecran-dossiers .liste-pieces li { display: grid; grid-template-columns: 12px minmax(0, 1fr) auto; align-items: center; gap: var(--e3); padding: var(--e2) 0; border-top: 1px solid var(--bord); }
      .ecran-dossiers .liste-pieces li:first-child { border-top: 0; }
      .ecran-dossiers .liste-pieces.sans-badge li { grid-template-columns: 12px minmax(0, 1fr); }
      .ecran-dossiers .piece-pastille { width: 10px; height: 10px; border-radius: 50%; background: var(--surface-3); box-shadow: inset 0 0 0 2px var(--bord-fort); }
      .ecran-dossiers .piece-ok { background: var(--bon); box-shadow: none; }
      .ecran-dossiers .piece-manque { background: var(--critique); box-shadow: none; border-radius: 2px; transform: rotate(45deg); width: 9px; height: 9px; }
      .ecran-dossiers .piece-warn { background: var(--alerte); box-shadow: none; border-radius: 0; clip-path: polygon(50% 0, 100% 100%, 0 100%); }
      .ecran-dossiers .piece-info { background: var(--accent); box-shadow: none; border-radius: 0; clip-path: polygon(50% 0, 100% 50%, 50% 100%, 0 50%); }

      /* Score : jauge circulaire + lecture en listes */
      .ecran-dossiers .score-resultat { display: flex; flex-direction: column; gap: var(--e5); }
      .ecran-dossiers .score-entete { display: grid; grid-template-columns: auto minmax(0, 1fr); align-items: center; gap: var(--e5); }
      .ecran-dossiers .score-entete .banniere-regle { margin: 0; }
      .ecran-dossiers .score-infos { display: flex; flex-direction: column; gap: var(--e2); min-width: 0; align-items: flex-start; }
      .ecran-dossiers .score-infos h4 { margin: 0; }
      .ecran-dossiers .jauge-bloc { display: flex; flex-direction: column; align-items: center; gap: var(--e2); text-align: center; }
      .ecran-dossiers .jauge { position: relative; width: 136px; height: 136px; flex: none; }
      .ecran-dossiers .jauge svg { width: 100%; height: 100%; display: block; }
      .ecran-dossiers .jauge-piste { fill: none; stroke: var(--surface-3); stroke-width: 12; }
      .ecran-dossiers .jauge-valeur { fill: none; stroke: var(--accent-plein); stroke-width: 12; stroke-linecap: round; transition: stroke-dasharray var(--d3) var(--courbe); }
      .ecran-dossiers .jauge-valeur.jauge-bon { stroke: var(--bon); }
      .ecran-dossiers .jauge-valeur.jauge-alerte { stroke: var(--alerte); }
      .ecran-dossiers .jauge-valeur.jauge-critique { stroke: var(--critique); }
      .ecran-dossiers .jauge-centre { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; line-height: 1.1; }
      .ecran-dossiers .jauge-chiffre { font-family: var(--police-titre); font-size: var(--t-xl); font-weight: 700; color: var(--texte); font-variant-numeric: tabular-nums; }
      .ecran-dossiers .jauge-legende { font-size: var(--t-xs); color: var(--texte-faible); }
      .ecran-dossiers .score-bloc { display: flex; flex-direction: column; gap: var(--e2); min-width: 0; }
      .ecran-dossiers .score-bloc h4 { margin: 0; }
      .ecran-dossiers .score-bloc .liste-propre { margin: 0; }
      .ecran-dossiers .liste-criteres { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--e3); }
      .ecran-dossiers .liste-criteres li { display: flex; flex-direction: column; gap: 6px; }
      .ecran-dossiers .liste-criteres .barre-progression { margin: 0; height: 6px; }
      .ecran-dossiers .critere-entete { display: flex; justify-content: space-between; align-items: baseline; gap: var(--e3); }
      .ecran-dossiers .critere-entete strong { font-weight: 600; }
      .ecran-dossiers .critere-entete span { font-size: var(--t-sm); color: var(--texte-doux); font-variant-numeric: tabular-nums; white-space: nowrap; }
      .ecran-dossiers .critere-commentaire { font-size: var(--t-sm); color: var(--texte-doux); }
      .ecran-dossiers .score-resultat details.guide-bloc { margin: 0; }
      .ecran-dossiers .score-resultat .note { margin: 0; }

      /* Discussion */
      .ecran-dossiers .msg-entete { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e2); margin-bottom: var(--e1); }
      .ecran-dossiers .msg-entete strong { font-size: var(--t-sm); }
      .ecran-dossiers .fil-discussion .etat-vide { padding: var(--e4); }
      .ecran-dossiers .fil-discussion .ligne-squelette { padding: var(--e3); }

      @media (max-width: 760px) {
        .ecran-dossiers .depot-grille { grid-template-columns: minmax(0, 1fr); }
        .ecran-dossiers .score-entete { grid-template-columns: minmax(0, 1fr); justify-items: center; text-align: center; }
        .ecran-dossiers .score-infos { align-items: center; }
        .ecran-dossiers .score-entete .banniere-regle { text-align: left; }
      }
    </style>
"""

_ILLU_DOSSIER = (
    '<svg class="etat-vide-illu" viewBox="0 0 96 72" aria-hidden="true" focusable="false">'
    '<rect class="illu-fond" x="6" y="18" width="72" height="48" rx="9"/>'
    '<rect class="illu-papier" x="18" y="6" width="48" height="40" rx="6"/>'
    '<path class="illu-trait" d="M27 17h24M27 25h30M27 33h16"/>'
    '<circle class="illu-accent" cx="72" cy="50" r="14"/>'
    '<path class="illu-coche" d="M72 44v12M66 50h12"/></svg>'
)

_ILLU_JAUGE = (
    '<svg class="etat-vide-illu" viewBox="0 0 96 72" aria-hidden="true" focusable="false">'
    '<rect class="illu-fond" x="8" y="10" width="80" height="56" rx="10"/>'
    '<path class="illu-trait" d="M24 52a24 24 0 0 1 48 0"/>'
    '<path class="illu-coche" d="M48 52l11-14"/>'
    '<circle class="illu-accent" cx="48" cy="52" r="5"/></svg>'
)

_LIGNE_SQUELETTE_TABLE = (
    '<tr aria-hidden="true">'
    '<td><span class="squelette squelette-texte"></span><span class="squelette squelette-texte court"></span></td>'
    '<td><span class="squelette squelette-texte"></span></td>'
    '<td><span class="squelette squelette-texte"></span><span class="squelette squelette-texte court"></span></td>'
    '<td><span class="squelette squelette-texte"></span></td>'
    '<td><span class="squelette squelette-pastille"></span></td>'
    '<td><span class="squelette squelette-texte court"></span></td></tr>'
)

HTML_ETUDIANTS = (
    CSS_DOSSIERS
    + """
    <!-- Étudiants et fiches -->
    <section id="vue-etudiants" class="vue-ecran ecran-dossiers cache">
      <header class="page-entete">
        <div>
          <h2>Étudiants et fiches</h2>
          <p class="lead">Choisissez le dossier sur lequel vous travaillez, ou créez une nouvelle fiche. Les données sont chiffrées par bureau.</p>
        </div>
        <div class="page-actions">
          <button class="btn btn-primaire" type="button" data-aller-vers="vue-etudiants" data-ouvrir="carte-nouvel-etudiant">[[i:plus]]Nouvel étudiant</button>
        </div>
      </header>

      <section class="carte" aria-labelledby="titre-dossiers-bureau">
        <div class="carte-entete">
          <h3 id="titre-dossiers-bureau">Dossiers du bureau</h3>
          <span id="etudiants-total" class="badge badge-nu">—</span>
        </div>
        <div class="barre-saisie barre-recherche" role="search">
          <input id="rech-candidat" type="search" placeholder="Rechercher par nom, prénom, e-mail ou passeport" aria-label="Rechercher un étudiant" />
          <button id="btn-rechercher-candidat" class="btn btn-secondaire" type="button">Rechercher</button>
        </div>
        <div class="table-wrap" tabindex="0" role="region" aria-label="Tableau des dossiers du bureau">
          <table id="table-candidats" aria-busy="true">
            <caption class="sr-only">Dossiers du bureau : étudiant, passeport, formation visée, fiche, consentement et actions</caption>
            <thead><tr><th scope="col">Étudiant</th><th scope="col">Passeport</th><th scope="col">Formation visée</th><th scope="col">Fiche</th><th scope="col">Consentement (loi 18-07)</th><th scope="col">Actions</th></tr></thead>
            <tbody>
              <tr class="sr-only"><td colspan="6">Chargement des dossiers</td></tr>
              """
    + _LIGNE_SQUELETTE_TABLE * 3
    + """
            </tbody>
          </table>
        </div>
      </section>

      <section id="carte-fiche-active" class="carte" aria-labelledby="titre-fiche-active">
        <div class="carte-entete">
          <div>
            <span class="surtitre">Dossier actif</span>
            <h3 id="titre-fiche-active">Fiche de l'étudiant</h3>
          </div>
          <span id="fiche-active-badge" class="badge badge-nu">—</span>
        </div>
        <div id="fiche-active-corps">
          <div class="etat-vide">"""
    + _ILLU_DOSSIER
    + """<strong>Aucun dossier choisi.</strong><span>Choisissez un étudiant dans la liste ci-dessus pour afficher sa fiche.</span></div>
        </div>
        <div class="carte-pied">
          <span class="note">Seules les informations saisies sont affichées : rien n'est déduit ni inventé.</span>
          <div class="cellule-actions">
            <button class="btn btn-secondaire btn-sm" type="button" data-aller-vers="vue-documents">[[i:pieces]]Vérifier les pièces</button>
            <button class="btn btn-contour btn-sm" type="button" data-aller-vers="vue-conseiller">[[i:conseiller]]Calculer le score</button>
          </div>
        </div>
      </section>

"""
    + HTML_OUVERTURE_PC
    + """
      <details id="carte-nouvel-etudiant" class="carte">
        <summary>Nouvel étudiant</summary>
        <p class="aide">Seuls le nom et le prénom sont obligatoires. Ce que vous ne renseignez pas reste vide : l'agent n'invente jamais de valeur (règle 4).</p>
        <fieldset>
          <legend>Identité</legend>
          <div class="grille-form">
            <label class="champ">Nom de famille <span class="requis" aria-hidden="true">*</span><input id="cand-nom" type="text" placeholder="Nom de famille" required aria-required="true" aria-describedby="cand-nom-err" autocomplete="off" /><span class="champ-aide">Comme sur le passeport.</span><span id="cand-nom-err" class="champ-erreur cache">Le nom de famille est obligatoire.</span></label>
            <label class="champ">Prénom <span class="requis" aria-hidden="true">*</span><input id="cand-prenom" type="text" placeholder="Prénom" required aria-required="true" aria-describedby="cand-prenom-err" autocomplete="off" /><span id="cand-prenom-err" class="champ-erreur cache">Le prénom est obligatoire.</span></label>
            <label class="champ">Sexe <select id="cand-sexe"><option value="">Non renseigné</option><option value="M">Masculin</option><option value="F">Féminin</option></select></label>
            <label class="champ">Date de naissance <input id="cand-dn" type="date" /></label>
            <label class="champ">Lieu de naissance <input id="cand-lieu" type="text" placeholder="Ville ou wilaya" /><span class="champ-aide">Wilaya ou ville.</span></label>
            <label class="champ">Nationalité <input id="cand-nat" type="text" placeholder="Nationalité" /></label>
          </div>
        </fieldset>
        <fieldset>
          <legend>Coordonnées</legend>
          <div class="grille-form">
            <label class="champ">Pays de résidence <input id="cand-pays" type="text" placeholder="Pays de résidence" /></label>
            <label class="champ">Adresse e-mail <input id="cand-email" type="email" placeholder="Adresse e-mail" autocomplete="off" /></label>
            <label class="champ">Téléphone <input id="cand-tel" type="text" placeholder="Numéro de téléphone" autocomplete="off" /><span class="champ-aide">Format international, avec l'indicatif du pays.</span></label>
          </div>
        </fieldset>
        <fieldset>
          <legend>Passeport</legend>
          <div class="grille-form">
            <label class="champ">Numéro de passeport <input id="cand-pass" type="text" placeholder="Numéro de passeport" autocomplete="off" /></label>
            <label class="champ">Date d'expiration du passeport <input id="cand-exp-pass" type="date" /><span class="champ-aide">Les démarches exigent souvent 6 mois de validité restante.</span></label>
          </div>
        </fieldset>
        <fieldset>
          <legend>Projet d'études</legend>
          <div class="grille-form">
            <label class="champ">Niveau d'études actuel <input id="cand-niveau" type="text" placeholder="Niveau d'études" /></label>
            <label class="champ">Formation ou programme visé <input id="cand-prog" type="text" placeholder="Formation ou programme" /></label>
            <label class="champ">Établissement visé <input id="cand-etab" type="text" placeholder="Établissement" /></label>
            <label class="champ">Ressources financières disponibles (EUR) <input id="cand-fonds" type="number" min="0" placeholder="Montant en euros" /><span class="champ-aide">Montant en euros, sans espace.</span></label>
          </div>
        </fieldset>
        <div class="formulaire-pied">
          <span class="note"><span class="requis" aria-hidden="true">*</span> Champ obligatoire</span>
          <button id="btn-creer-candidat" class="btn btn-primaire" type="button">Enregistrer l'étudiant</button>
        </div>
      </details>
    </section>
"""
)

HTML_DOCUMENTS = (
    """
    <!-- Pièces et identifiants -->
    <section id="vue-documents" class="vue-ecran ecran-dossiers cache">
      <header class="page-entete">
        <div>
          <h2>Pièces et identifiants</h2>
          <p class="lead">Déposez les pièces justificatives du dossier actif, vérifiez ce qui manque pour chaque démarche et gérez les identifiants des portails.</p>
        </div>
      </header>

      <section class="carte" aria-labelledby="titre-ajout-piece">
        <div class="carte-entete">
          <h3 id="titre-ajout-piece">Ajouter une pièce justificative</h3>
          <span class="badge badge-nu">[[i:cadenas]]Chiffrée AES-256-GCM</span>
        </div>
        <div class="depot-grille">
          <label class="depot-zone" for="doc-fichier">
            <span class="depot-icone">[[i:pieces]]</span>
            <span class="depot-titre">Glissez le fichier ici ou cliquez pour le choisir</span>
            <span class="aide">PDF, PNG ou JPEG, 10 Mo maximum. Le fichier est chiffré dès son dépôt.</span>
            <span id="doc-fichier-nom" class="depot-nom" aria-live="polite"></span>
            <input id="doc-fichier" type="file" accept=".pdf,.png,.jpg,.jpeg" />
          </label>
          <div class="depot-champs">
            <label class="champ">Type de pièce
              <select id="doc-type-piece">
                <option value="passeport">Passeport biométrique en cours de validité</option>
                <option value="photo_identite">Photo d'identité aux normes passeport</option>
                <option value="releve_notes_bac">Relevé de notes du baccalauréat</option>
                <option value="diplome_bac">Diplôme ou attestation provisoire du baccalauréat</option>
                <option value="releves_notes_superieur">Relevés de notes des années d'études supérieures</option>
                <option value="cv">Curriculum Vitæ (CV)</option>
                <option value="attestation_langue_francaise">Attestation de test de français (TCF, DELF ou DALF)</option>
                <option value="lettre_admission_dli">IRCC : lettre d'admission d'un établissement désigné (EED ou DLI)</option>
                <option value="attestation_provinciale_pal_caq">IRCC : attestation provinciale (LAP ou PAL) ou CAQ Québec</option>
                <option value="preuve_financiere">IRCC : preuve de ressources financières (relevés, CPG ou GIC, garant)</option>
                <option value="formulaire_imm5645">IRCC : formulaire d'informations sur la famille (IMM 5645)</option>
                <option value="lettre_explicative">IRCC : lettre d'explication ou plan d'études</option>
              </select>
            </label>
            <label class="champ">Date d'expiration <input id="doc-expiration" type="date" value="2031-05-20" /><span class="champ-aide">Seulement si la pièce en a une (passeport, attestation de langue…).</span></label>
          </div>
        </div>
        <div class="carte-pied">
          <button id="btn-specimens-demo" class="btn btn-fantome" type="button">Générer des pièces spécimens (démonstration)</button>
          <button id="btn-televerser-doc" class="btn btn-primaire" type="button">Déposer et chiffrer la pièce</button>
        </div>
      </section>

      <div class="section-entete">
        <div>
          <h3>Pièces par démarche</h3>
          <p>Ce qui est reçu, ce qui manque et ce qui est à corriger, pour chaque démarche.</p>
        </div>
        <button id="btn-verifier-completude" class="btn btn-secondaire btn-sm" type="button">[[i:actualiser]]Vérifier maintenant</button>
      </div>
      <div id="zone-completude">
        <div class="carte carte-sobre etat-vide">"""
    + _ILLU_DOSSIER
    + """<strong>Aucune vérification pour l'instant.</strong><span>Choisissez un dossier dans « Étudiants et fiches », puis cliquez sur « Vérifier maintenant ».</span></div>
      </div>

      <div class="section-entete">
        <div>
          <h3>Pièces déposées dans le dossier</h3>
          <p>Fichiers chiffrés du dossier actif. Le téléchargement les déchiffre pour vous seul.</p>
        </div>
      </div>
      <div class="table-wrap" tabindex="0" role="region" aria-label="Tableau des pièces déposées dans le dossier">
        <table id="table-documents-candidat">
          <caption class="sr-only">Pièces déposées dans le dossier actif : pièce, fichier d'origine, expiration, taille et actions</caption>
          <thead><tr><th scope="col">Pièce</th><th scope="col">Fichier d'origine</th><th scope="col">Expiration</th><th scope="col" class="num">Taille</th><th scope="col">Actions</th></tr></thead>
          <tbody><tr><td colspan="5" class="etat-vide-cellule"><div class="etat-vide">"""
    + _ILLU_DOSSIER
    + """<strong>Aucun dossier choisi.</strong><span>Choisissez un étudiant pour voir ses pièces déposées.</span></div></td></tr></tbody>
        </table>
      </div>
      <!-- zone:coffre -->
    </section>
"""
)

HTML_CONSEILLER = (
    """
    <!-- Conseiller et score -->
    <section id="vue-conseiller" class="vue-ecran ecran-dossiers cache">
      <header class="page-entete">
        <div>
          <h2>Conseiller et score d'acceptation</h2>
          <p class="lead">Évaluez la solidité du dossier actif (0 à 100 %) et posez vos questions à l'assistant.</p>
        </div>
      </header>
      <div id="ia-statut-discussion" class="ia-statut">Assistant IA : état en cours de vérification...</div>

      <section class="carte" aria-labelledby="titre-score">
        <div class="carte-entete"><h3 id="titre-score">Score d'acceptation et plan d'action</h3></div>
        <div class="ligne-formulaire">
          <label class="champ">Démarche à évaluer
            <select id="eval-demarche">
              <option value="campus_france">Campus France — Études en France (Guide septembre 2026)</option>
              <option value="ircc_permis_etudes">IRCC Canada — Demande de permis d'études</option>
            </select>
          </label>
          <button id="btn-calculer-score" class="btn btn-primaire" type="button">Calculer le score</button>
        </div>
        <div id="zone-score-acceptation" class="score-zone">
          <div class="etat-vide">"""
    + _ILLU_JAUGE
    + """<strong>Pas encore de score.</strong><span>Cliquez sur « Calculer le score » : score sur 100, pièces manquantes, points forts et plan d'action.</span></div>
        </div>
      </section>

      <section class="carte" aria-labelledby="titre-discussion">
        <div class="carte-entete"><h3 id="titre-discussion">Discussion avec le conseiller sur ce dossier</h3></div>
        <span class="surtitre">Questions rapides</span>
        <div class="chips">
          <button class="puce-cmd" type="button" onclick="poserQuestionRapide('Quelles sont les pièces manquantes et quelle est notre priorité sur ce dossier ?')">Pièces manquantes et priorité</button>
          <button class="puce-cmd" type="button" onclick="poserQuestionRapide('Quels sont les délais du calendrier Campus France Algérie 2026-2027 et les frais en DZD ?')">Calendrier et frais (20 000 DZD)</button>
          <button class="puce-cmd" type="button" onclick="poserQuestionRapide('Comment fonctionne le panier de 7 formations (DAP Blanche, DAP Jaune, Hors DAP) et la motivation de 4000 caractères ?')">Panier de 7 formations et motivation</button>
          <button class="puce-cmd" type="button" onclick="poserQuestionRapide('Comment déclarer un bac algérien en français (> 1000 heures) et remplir le dossier de scolarité (2 activités) ?')">Bac en français (+1000 h) et scolarité</button>
          <button class="puce-cmd" type="button" onclick="poserQuestionRapide('Comment fonctionne le dossier pré-consulaire en 4 étapes et la réduction visa CAPAGO de 50 % ?')">Dossier pré-consulaire et visa CAPAGO</button>
        </div>
        <div id="fil-discussion" class="fil-discussion" role="log">
          <div class="etat-vide"><strong>Aucune question pour l'instant.</strong><span>Posez une question ci-dessous ou choisissez une question rapide pour obtenir l'analyse du conseiller.</span></div>
        </div>
        <div class="barre-saisie">
          <input id="msg-discussion" type="text" value="Quelle est notre priorité pour maximiser les chances d'acceptation de ce dossier ?" placeholder="Posez votre question au conseiller" aria-label="Votre question au conseiller" />
          <button id="btn-envoyer-discussion" class="btn btn-primaire" type="button">Envoyer au Conseiller</button>
        </div>
      </section>

      <section id="carte-assistant-ia" class="carte" aria-labelledby="titre-assistant-ia">
        <div class="carte-entete"><h3 id="titre-assistant-ia">Assistant IA du dossier</h3><span class="badge badge-info">Indicatif</span></div>
        <p class="aide">L'assistant ne reçoit aucune donnée personnelle du candidat : il répond à partir de la démarche choisie. Ses réponses sont indicatives et doivent être vérifiées par un conseiller.</p>
        <div class="ligne-formulaire">
          <label class="champ">Démarche concernée
            <select id="ia-demarche-assistant">
              <option value="campus_france">Campus France — Études en France (Guide septembre 2026)</option>
              <option value="ircc_permis_etudes">IRCC Canada — Demande de permis d'études</option>
            </select>
          </label>
        </div>
        <div class="barre-saisie espace-haut">
          <input id="ia-question-assistant" type="text" maxlength="2000" placeholder="Votre question sur la démarche" aria-label="Votre question pour l'assistant IA" />
          <button id="btn-demander-assistant-ia" class="btn btn-primaire" type="button">Demander</button>
        </div>
        <div id="zone-reponse-assistant-ia" class="panneau-texte espace-haut cache"></div>
      </section>
    </section>
"""
)
