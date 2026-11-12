"""Écrans « Dossiers » : étudiants et fiches, pièces (et coffre, inséré au marqueur), conseiller.

Gabarits HTML seuls : toute la logique est dans les modules `js_*`. Les identifiants des champs
et des boutons sont utilisés par ce JavaScript et par les tests : ne pas les renommer.
Les jetons [[i:nom]] sont remplacés par des icônes SVG à l'assemblage.
"""

from __future__ import annotations

HTML_ETUDIANTS = """
    <!-- Étudiants et fiches -->
    <section id="vue-etudiants" class="vue-ecran cache">
      <header class="page-entete">
        <div>
          <h2>Étudiants et fiches</h2>
          <p class="lead">Choisissez le dossier sur lequel vous travaillez, ou créez une nouvelle fiche. Les données sont chiffrées par bureau.</p>
        </div>
      </header>

      <div class="carte">
        <div class="carte-entete"><h3>Dossiers du bureau</h3></div>
        <div class="barre-saisie" style="margin-bottom:12px;">
          <input id="rech-candidat" type="search" placeholder="Rechercher par nom, prénom, e-mail ou passeport" aria-label="Rechercher un étudiant" />
          <button id="btn-rechercher-candidat" class="btn btn-secondaire" type="button" style="margin:0;">Rechercher</button>
        </div>
        <div class="table-wrap">
          <table id="table-candidats">
            <thead><tr><th>Étudiant</th><th>Passeport</th><th>Formation visée</th><th>Consentement (loi 18-07)</th><th>Actions</th></tr></thead>
            <tbody></tbody>
          </table>
        </div>
      </div>

      <details id="carte-nouvel-etudiant" class="carte">
        <summary>Nouvel étudiant</summary>
        <p class="aide">Seuls le nom et le prénom sont obligatoires. Ce que vous ne renseignez pas reste vide : l'agent n'invente jamais de valeur (règle 4).</p>
        <fieldset>
          <legend>Identité</legend>
          <div class="grille-form">
            <label>Nom de famille <span class="requis" aria-hidden="true">*</span><input id="cand-nom" type="text" value="BELAID" required aria-required="true" autocomplete="off" /></label>
            <label>Prénom <span class="requis" aria-hidden="true">*</span><input id="cand-prenom" type="text" value="Amine" required aria-required="true" autocomplete="off" /></label>
            <label>Sexe <select id="cand-sexe"><option value="M" selected>Masculin</option><option value="F">Féminin</option><option value="">Non renseigné</option></select></label>
            <label>Date de naissance <input id="cand-dn" type="date" value="2002-06-15" /></label>
            <label>Lieu de naissance (wilaya ou ville) <input id="cand-lieu" type="text" value="Alger" /></label>
            <label>Nationalité <input id="cand-nat" type="text" value="Algérienne" /></label>
          </div>
        </fieldset>
        <fieldset>
          <legend>Coordonnées</legend>
          <div class="grille-form">
            <label>Pays de résidence <input id="cand-pays" type="text" value="Algérie" /></label>
            <label>Adresse e-mail <input id="cand-email" type="email" value="amine.belaid@exemple.dz" autocomplete="off" /></label>
            <label>Téléphone <input id="cand-tel" type="text" value="+213555123456" autocomplete="off" /></label>
          </div>
        </fieldset>
        <fieldset>
          <legend>Passeport</legend>
          <div class="grille-form">
            <label>Numéro de passeport <input id="cand-pass" type="text" value="DZ9900112" autocomplete="off" /></label>
            <label>Date d'expiration du passeport <input id="cand-exp-pass" type="date" value="2031-05-20" /></label>
          </div>
        </fieldset>
        <fieldset>
          <legend>Projet d'études</legend>
          <div class="grille-form">
            <label>Niveau d'études actuel <input id="cand-niveau" type="text" value="Licence 3 Informatique" /></label>
            <label>Formation ou programme visé <input id="cand-prog" type="text" value="Master 1 Informatique et Intelligence Artificielle" /></label>
            <label>Établissement visé <input id="cand-etab" type="text" value="Université Paris-Saclay" /></label>
            <label>Ressources financières disponibles (EUR) <input id="cand-fonds" type="number" min="0" value="15000" /></label>
          </div>
        </fieldset>
        <button id="btn-creer-candidat" class="btn btn-primaire" type="button">Enregistrer l'étudiant</button>
      </details>
    </section>
"""

HTML_DOCUMENTS = """
    <!-- Pièces et identifiants -->
    <section id="vue-documents" class="vue-ecran cache">
      <header class="page-entete">
        <div>
          <h2>Pièces et identifiants</h2>
          <p class="lead">Déposez les pièces justificatives du dossier actif, vérifiez ce qui manque pour chaque démarche et gérez les identifiants des portails.</p>
        </div>
      </header>

      <div class="carte">
        <h3>Ajouter une pièce justificative</h3>
        <p class="aide">Le fichier est chiffré (AES-256-GCM) dès son dépôt.</p>
        <div class="grille-form">
          <label>Type de pièce
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
          <label>Date d'expiration (si la pièce en a une) <input id="doc-expiration" type="date" value="2031-05-20" /></label>
          <label>Fichier (PDF, PNG ou JPEG, 10 Mo maximum) <input id="doc-fichier" type="file" accept=".pdf,.png,.jpg,.jpeg" /></label>
        </div>
        <div class="pile-actions">
          <button id="btn-televerser-doc" class="btn btn-primaire" type="button">Déposer et chiffrer la pièce</button>
          <button id="btn-specimens-demo" class="btn btn-contour" type="button">Générer des pièces spécimens (démonstration)</button>
        </div>
      </div>

      <div class="carte">
        <div class="carte-entete">
          <h3>Pièces manquantes par démarche</h3>
          <button id="btn-verifier-completude" class="btn btn-secondaire btn-sm" type="button" style="margin:0;">[[i:actualiser]]Vérifier maintenant</button>
        </div>
        <div id="zone-completude" class="panneau-texte">
          Choisissez un dossier dans « Étudiants et fiches », puis cliquez sur « Vérifier maintenant » : vous verrez les pièces manquantes et celles déjà valides.
        </div>
      </div>

      <div class="carte">
        <h3>Pièces déposées dans le dossier</h3>
        <div class="table-wrap">
          <table id="table-documents-candidat">
            <thead><tr><th>Pièce</th><th>Fichier d'origine</th><th>Expiration</th><th>Taille</th><th>Actions</th></tr></thead>
            <tbody><tr><td colspan="5" class="etat-vide"><strong>Aucun dossier choisi.</strong>Choisissez un étudiant pour voir ses pièces déposées.</td></tr></tbody>
          </table>
        </div>
      </div>
      <!-- zone:coffre -->
    </section>
"""

HTML_CONSEILLER = """
    <!-- Conseiller et score -->
    <section id="vue-conseiller" class="vue-ecran cache">
      <header class="page-entete">
        <div>
          <h2>Conseiller et score d'acceptation</h2>
          <p class="lead">Évaluez la solidité du dossier actif (0 à 100 %) et posez vos questions à l'assistant.</p>
        </div>
      </header>
      <div id="ia-statut-discussion" class="ia-statut">Assistant IA : état en cours de vérification...</div>

      <div class="carte">
        <h3>Score d'acceptation et plan d'action</h3>
        <div class="barre-saisie" style="align-items:flex-end;">
          <label style="flex:1 1 280px;">Démarche à évaluer
            <select id="eval-demarche">
              <option value="campus_france">Campus France — Études en France (Guide septembre 2026)</option>
              <option value="ircc_permis_etudes">IRCC Canada — Demande de permis d'études</option>
            </select>
          </label>
          <button id="btn-calculer-score" class="btn btn-primaire" type="button" style="margin:0;">Calculer le score</button>
        </div>
        <div id="zone-score-acceptation" class="panneau-texte" style="margin-top:16px;">
          Cliquez sur « Calculer le score » pour afficher l'évaluation : score sur 100, pièces manquantes, points forts et plan d'action.
        </div>
      </div>

      <div class="carte">
        <h3>Discussion avec le conseiller sur ce dossier</h3>
        <p class="titre-mini" style="margin-top:0;">Questions rapides</p>
        <div class="chips">
          <button class="puce-cmd" type="button" onclick="poserQuestionRapide('Quelles sont les pièces manquantes et quelle est notre priorité sur ce dossier ?')">Pièces manquantes et priorité</button>
          <button class="puce-cmd" type="button" onclick="poserQuestionRapide('Quels sont les délais du calendrier Campus France Algérie 2026-2027 et les frais en DZD ?')">Calendrier et frais (20 000 DZD)</button>
          <button class="puce-cmd" type="button" onclick="poserQuestionRapide('Comment fonctionne le panier de 7 formations (DAP Blanche, DAP Jaune, Hors DAP) et la motivation de 4000 caractères ?')">Panier de 7 formations et motivation</button>
          <button class="puce-cmd" type="button" onclick="poserQuestionRapide('Comment déclarer un bac algérien en français (> 1000 heures) et remplir le dossier de scolarité (2 activités) ?')">Bac en français (+1000 h) et scolarité</button>
          <button class="puce-cmd" type="button" onclick="poserQuestionRapide('Comment fonctionne le dossier pré-consulaire en 4 étapes et la réduction visa CAPAGO de 50 % ?')">Dossier pré-consulaire et visa CAPAGO</button>
        </div>
        <div id="fil-discussion" class="fil-discussion" aria-live="polite">
          <div class="aide">Posez une question ci-dessous ou choisissez une question rapide pour obtenir l'analyse du conseiller.</div>
        </div>
        <div class="barre-saisie">
          <input id="msg-discussion" type="text" value="Quelle est notre priorité pour maximiser les chances d'acceptation de ce dossier ?" placeholder="Posez votre question au conseiller" aria-label="Votre question au conseiller" />
          <button id="btn-envoyer-discussion" class="btn btn-primaire" type="button" style="margin:0;">Envoyer au Conseiller</button>
        </div>
      </div>

      <div id="carte-assistant-ia" class="carte">
        <h3>Assistant IA du dossier</h3>
        <p class="aide">L'assistant ne reçoit aucune donnée personnelle du candidat : il répond à partir de la démarche choisie. Ses réponses sont indicatives et doivent être vérifiées par un conseiller.</p>
        <div class="grille-form" style="margin-bottom:12px;">
          <label>Démarche concernée
            <select id="ia-demarche-assistant">
              <option value="campus_france">Campus France — Études en France (Guide septembre 2026)</option>
              <option value="ircc_permis_etudes">IRCC Canada — Demande de permis d'études</option>
            </select>
          </label>
        </div>
        <div class="barre-saisie">
          <input id="ia-question-assistant" type="text" maxlength="2000" placeholder="Votre question sur la démarche" aria-label="Votre question pour l'assistant IA" />
          <button id="btn-demander-assistant-ia" class="btn btn-primaire" type="button" style="margin:0;">Demander</button>
        </div>
        <div id="zone-reponse-assistant-ia" class="panneau-texte cache" style="margin-top:12px;"></div>
      </div>
    </section>
"""
