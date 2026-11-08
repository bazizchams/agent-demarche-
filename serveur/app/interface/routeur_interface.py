"""Routeur servant l'interface web complète en français de la plateforme :
1. Tableau de bord
2. Étudiants & Fiche candidat
3. Documents & Pièces requises (affichage en français clair sans code technique)
4. Discussion & Score d'acceptation (évaluation détaillée en texte lisible + Assistant Conseiller fonctionnel)
5. Campus France (Études en France — Guide officiel Septembre 2026 Algérie + Agent Navigateur Playwright)
6. IRCC Canada (Permis d'études + Agent Navigateur Playwright)
7. Centre de validation humaine (Règle 1 — cartes interactives + aperçu de la capture de contrôle)
8. Historique & Erreurs (Audit sans donnée personnelle — Règle 5)
9. Paramètres & Sauvegardes (Agents locaux, sauvegardes chiffrées, abonnement et statut des portails)
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

routeur_interface = APIRouter(tags=["interface web en français"])

HTML_INTERFACE_FR = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Plateforme Agent Bureau d'Études — Algérie (Campus France Septembre 2026 &amp; IRCC)</title>
  <style>
    :root {
      --bleu-nuit: #0f172a;
      --bleu-primaire: #1d4ed8;
      --bleu-clair: #eff6ff;
      --vert-succes: #15803d;
      --vert-clair: #dcfce7;
      --orange-alerte: #b45309;
      --orange-clair: #fef3c7;
      --rouge-danger: #b91c1c;
      --rouge-clair: #fee2e2;
      --fond: #f1f5f9;
      --carte: #ffffff;
      --bordure: #cbd5e1;
      --texte: #0f172a;
      --texte-secondaire: #475569;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: Segoe UI, system-ui, -apple-system, sans-serif; background: var(--fond); color: var(--texte); display: flex; min-height: 100vh; }
    aside { width: 285px; background: var(--bleu-nuit); color: #fff; padding: 20px 14px; display: flex; flex-direction: column; gap: 6px; flex-shrink: 0; }
    aside h1 { font-size: 1.08rem; margin: 0 0 12px 8px; color: #93c5fd; }
    aside button.nav-btn { background: transparent; color: #e2e8f0; border: none; text-align: left; padding: 10px 12px; border-radius: 6px; cursor: pointer; font-size: 0.9rem; font-weight: 500; transition: background 0.15s; }
    aside button.nav-btn.actif, aside button.nav-btn:hover { background: #1e293b; color: #fff; }
    main { flex: 1; padding: 22px 30px; overflow-y: auto; max-width: 1400px; }
    .carte { background: var(--carte); border: 1px solid var(--bordure); border-radius: 10px; padding: 18px 22px; margin-bottom: 18px; box-shadow: 0 1px 2px rgba(0,0,0,0.03); }
    .grille-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 18px; }
    .stat { background: var(--carte); border: 1px solid var(--bordure); border-radius: 8px; padding: 14px 16px; }
    .stat .valeur { font-size: 1.7rem; font-weight: 700; color: var(--bleu-primaire); }
    .stat .libelle { font-size: 0.85rem; color: var(--texte-secondaire); }
    .cache { display: none !important; }
    .grille-form { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
    .grille-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px; }
    label { display: flex; flex-direction: column; gap: 4px; font-size: 0.86rem; font-weight: 600; }
    input, select, textarea { padding: 8px 10px; border: 1px solid var(--bordure); border-radius: 6px; font-size: 0.92rem; font-family: inherit; }
    button.btn { background: var(--bleu-primaire); color: #fff; border: none; padding: 9px 15px; border-radius: 6px; cursor: pointer; font-weight: 600; margin-right: 6px; margin-bottom: 6px; font-size: 0.88rem; }
    button.btn:hover { opacity: 0.93; }
    button.btn-succes { background: var(--vert-succes); }
    button.btn-danger { background: var(--rouge-danger); }
    button.btn-secondaire { background: #475569; }
    button.btn-contour { background: #f8fafc; color: #1e293b; border: 1px solid var(--bordure); }
    table { width: 100%; border-collapse: collapse; font-size: 0.9rem; margin-top: 10px; }
    th, td { border-bottom: 1px solid var(--bordure); padding: 9px 10px; text-align: left; vertical-align: top; }
    th { background: #f8fafc; font-weight: 700; color: #334155; }
    .badge { display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 0.78rem; font-weight: 700; background: #e2e8f0; color: #1e293b; }
    .badge-ok { background: var(--vert-clair); color: #166534; }
    .badge-warn { background: var(--orange-clair); color: #92400e; }
    .badge-err { background: var(--rouge-clair); color: #991b1b; }
    .banniere-regle { background: var(--bleu-clair); border-left: 4px solid var(--bleu-primaire); padding: 11px 15px; font-size: 0.89rem; margin-bottom: 14px; border-radius: 4px; }
    .notif { padding: 11px 15px; border-radius: 6px; margin-bottom: 14px; font-weight: 600; font-size: 0.9rem; }
    .notif-ok { background: var(--vert-clair); color: #166534; border: 1px solid #86efac; }
    .notif-err { background: var(--rouge-clair); color: #991b1b; border: 1px solid #fca5a5; }
    .panneau-texte { background: #f8fafc; border: 1px solid var(--bordure); border-radius: 8px; padding: 16px 18px; font-size: 0.92rem; line-height: 1.55; }
    .fil-discussion { max-height: 380px; overflow-y: auto; border: 1px solid var(--bordure); border-radius: 8px; padding: 14px; background: #f8fafc; margin-bottom: 12px; }
    .msg { padding: 12px 14px; border-radius: 8px; margin-bottom: 10px; font-size: 0.91rem; line-height: 1.5; }
    .msg-op { background: #dbeafe; margin-left: 12%; border: 1px solid #93c5fd; }
    .msg-ia { background: #ffffff; border: 1px solid var(--bordure); margin-right: 6%; }
    .barre-progression { width: 100%; height: 14px; background: #e2e8f0; border-radius: 999px; overflow: hidden; margin: 8px 0; }
    .barre-progression-remplie { height: 100%; background: var(--bleu-primaire); transition: width 0.3s; }
    .liste-propre { margin: 6px 0 12px 0; padding-left: 20px; }
    .liste-propre li { margin-bottom: 5px; }
    .capture-apercu { max-width: 100%; border: 2px solid var(--bordure); border-radius: 8px; margin-top: 10px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }
    details.guide-bloc { border: 1px solid var(--bordure); border-radius: 8px; padding: 10px 14px; margin-bottom: 10px; background: #f8fafc; }
    details.guide-bloc summary { font-weight: 700; cursor: pointer; color: #1e3a8a; font-size: 0.95rem; }
    .workspace-cowork { display: grid; grid-template-columns: 1.15fr 0.95fr; gap: 16px; align-items: start; margin-top: 12px; }
    @media (max-width: 1100px) { .workspace-cowork { grid-template-columns: 1fr; } }
    .cadre-navigateur-direct { border: 2px solid #3b82f6; border-radius: 12px; background: #0f172a; overflow: hidden; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12); }
    .barre-chrome-direct { background: #1e293b; color: #f8fafc; padding: 8px 12px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; border-bottom: 1px solid #334155; }
    .barre-chrome-direct button.btn-nav-mini { background: #334155; color: #f8fafc; border: 1px solid #475569; border-radius: 6px; padding: 5px 9px; cursor: pointer; font-size: 0.82rem; font-weight: 600; }
    .barre-chrome-direct button.btn-nav-mini:hover { background: #2563eb; border-color: #60a5fa; }
    .url-live-input { flex: 1; min-width: 180px; background: #0f172a; color: #93c5fd; border: 1px solid #475569; border-radius: 6px; padding: 6px 10px; font-size: 0.84rem; font-family: Consolas, monospace; }
    .corps-navigateur-direct { background: #ffffff; color: #0f172a; min-height: 460px; max-height: 620px; overflow-y: auto; padding: 14px; }
    .iframe-navigateur-direct { width: 100%; height: 540px; border: none; background: #ffffff; display: block; }
    .panneau-copilote-chat { border: 2px solid #cbd5e1; border-radius: 12px; background: #ffffff; padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; }
    .fil-copilote { max-height: 340px; min-height: 180px; overflow-y: auto; background: #f8fafc; border: 1px solid var(--bordure); border-radius: 8px; padding: 12px; display: flex; flex-direction: column; gap: 8px; }
    .bulle-copilote-user { align-self: flex-end; background: #dbeafe; color: #1e3a8a; border: 1px solid #93c5fd; padding: 8px 12px; border-radius: 10px 10px 2px 10px; font-size: 0.88rem; max-width: 88%; }
    .bulle-copilote-ia { align-self: flex-start; background: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; border-left: 4px solid #2563eb; padding: 10px 12px; border-radius: 2px 10px 10px 10px; font-size: 0.88rem; max-width: 95%; line-height: 1.5; }
    .grille-dom-live { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px; margin-top: 8px; }
    .carte-dom-item { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 7px; padding: 8px 10px; font-size: 0.82rem; display: flex; flex-direction: column; gap: 5px; }
    .puce-cmd { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; border-radius: 999px; padding: 4px 10px; font-size: 0.79rem; font-weight: 600; cursor: pointer; display: inline-block; margin: 2px 3px 2px 0; }
    .puce-cmd:hover { background: #dbeafe; }
    .point-vert-pulsant { display: inline-block; width: 9px; height: 9px; border-radius: 50%; background: #22c55e; box-shadow: 0 0 8px #22c55e; margin-right: 5px; }
  </style>
</head>
<body>
  <aside id="navigation-principale">
    <h1>Agent Bureau d'Études</h1>
    <button class="nav-btn actif" data-vue="vue-tableau-bord">1. Tableau de bord</button>
    <button class="nav-btn" data-vue="vue-etudiants">2. Étudiants &amp; Fiche candidat</button>
    <button class="nav-btn" data-vue="vue-documents">3. Documents &amp; Pièces requises</button>
    <button class="nav-btn" data-vue="vue-conseiller">4. Discussion &amp; Score d'acceptation</button>
    <button class="nav-btn" data-vue="vue-campus-france">5. Campus France (Études en France)</button>
    <button class="nav-btn" data-vue="vue-ircc">6. IRCC Canada (Permis d'études)</button>
    <button class="nav-btn" data-vue="vue-validation-humaine">7. Centre de validation humaine</button>
    <button class="nav-btn" data-vue="vue-historique-erreurs">8. Historique &amp; Erreurs (Audit)</button>
    <button class="nav-btn" data-vue="vue-parametres">9. Paramètres &amp; Sauvegardes</button>
  </aside>

  <main>
    <div id="banniere-etat" class="banniere-regle">
      Sécurité active : chiffrement AES-256-GCM par bureau, zéro valeur par défaut inventée (Règle 4), arrêt obligatoire avant soumission officielle (Règle 1).
      | Candidat sélectionné : <strong id="bandeau-candidat-actif">Aucun</strong>
    </div>
    <div id="zone-notification" class="notif cache"></div>

    <!-- Connexion -->
    <section id="bloc-connexion" class="carte">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
        <div>
          <strong>Session Opérateur du Bureau :</strong>
          <span id="etat-utilisateur">Connexion en cours...</span>
        </div>
        <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
          <input id="login-email" type="email" value="admin@bureau-alger.dz" placeholder="employe@bureau.dz" style="width:210px;" />
          <input id="login-mdp" type="password" value="BureauAlger!2026" style="width:160px;" />
          <button id="btn-se-connecter" class="btn" type="button">Se connecter</button>
          <button id="btn-se-deconnecter" class="btn btn-secondaire cache" type="button">Se déconnecter</button>
        </div>
      </div>
    </section>

    <!-- 1. Tableau de bord -->
    <section id="vue-tableau-bord" class="vue-ecran">
      <h2>Tableau de bord du Bureau</h2>
      <div class="grille-stats">
        <div class="stat"><div id="stat-nb-candidats" class="valeur">0</div><div class="libelle">Étudiants actifs</div></div>
        <div class="stat"><div id="stat-nb-a-valider" class="valeur">0</div><div class="libelle">Dossiers prêts à valider humainement (Règle 1)</div></div>
        <div class="stat"><div id="stat-nb-suspendues" class="valeur">0</div><div class="libelle">Dossiers en pause (Pièces / Session / CAPTCHA)</div></div>
        <div class="stat"><div id="stat-nb-agents" class="valeur">0</div><div class="libelle">Postes Agents locaux enrôlés</div></div>
      </div>
      <div class="carte">
        <h3>Accès rapides aux démarches et portails</h3>
        <p>
          <button class="btn btn-succes" type="button" onclick="allerVersVue('vue-campus-france')">Piloter un dossier Campus France (Guide Septembre 2026)</button>
          <button class="btn btn-succes" type="button" onclick="allerVersVue('vue-ircc')">Piloter un dossier IRCC Canada (Permis d'études)</button>
          <button class="btn" type="button" onclick="allerVersVue('vue-conseiller')">Calculer le score d'acceptation &amp; interroger le Conseiller</button>
          <button class="btn btn-secondaire" type="button" onclick="allerVersVue('vue-documents')">Vérifier les pièces manquantes</button>
        </p>
        <p style="margin-top:8px;">
          <a href="https://etudesenfrance.diplomatie.gouv.fr/" target="_blank" rel="noopener"><button class="btn btn-contour" type="button">Site officiel Études en France</button></a>
          <a href="https://portal-portail.apps.cic.gc.ca/signin?lang=fr" target="_blank" rel="noopener"><button class="btn btn-contour" type="button">Portail officiel IRCC Canada</button></a>
          <a href="/demo/campus-france" target="_blank"><button class="btn btn-contour" type="button">Page de simulation Études en France</button></a>
          <a href="/demo/ircc" target="_blank"><button class="btn btn-contour" type="button">Page de simulation IRCC Canada</button></a>
        </p>
      </div>
    </section>

    <!-- 2. Étudiants & Fiche candidat -->
    <section id="vue-etudiants" class="vue-ecran cache">
      <h2>Étudiants &amp; Fiche candidat (Chiffrement AES-256-GCM)</h2>
      <div class="carte">
        <h3>Créer une fiche candidat (Règle 4 : aucune donnée inventée)</h3>
        <div class="grille-form">
          <label>Nom de famille * <input id="cand-nom" type="text" value="BELAID" /></label>
          <label>Prénom * <input id="cand-prenom" type="text" value="Amine" /></label>
          <label>Sexe <select id="cand-sexe"><option value="M" selected>Masculin (M)</option><option value="F">Féminin (F)</option><option value="">Non renseigné</option></select></label>
          <label>Date de naissance <input id="cand-dn" type="date" value="2002-06-15" /></label>
          <label>Lieu de naissance (Wilaya / Ville) <input id="cand-lieu" type="text" value="Alger" /></label>
          <label>Nationalité <input id="cand-nat" type="text" value="Algérienne" /></label>
          <label>Pays de résidence <input id="cand-pays" type="text" value="Algérie" /></label>
          <label>Adresse e-mail <input id="cand-email" type="email" value="amine.belaid@exemple.dz" /></label>
          <label>Téléphone <input id="cand-tel" type="text" value="+213555123456" /></label>
          <label>Numéro de passeport <input id="cand-pass" type="text" value="DZ9900112" /></label>
          <label>Date d'expiration du passeport <input id="cand-exp-pass" type="date" value="2031-05-20" /></label>
          <label>Niveau d'études actuel <input id="cand-niveau" type="text" value="Licence 3 Informatique" /></label>
          <label>Formation / Programme visé <input id="cand-prog" type="text" value="Master 1 Informatique et Intelligence Artificielle" /></label>
          <label>Établissement visé <input id="cand-etab" type="text" value="Université Paris-Saclay" /></label>
          <label>Ressources financières disponibles (EUR) <input id="cand-fonds" type="number" min="0" value="15000" /></label>
        </div>
        <p style="margin-top:12px;">
          <button id="btn-creer-candidat" class="btn btn-succes" type="button">Enregistrer le candidat</button>
        </p>
      </div>
      <div class="carte">
        <h3>Dossiers candidats du bureau &amp; Sélection du candidat actif</h3>
        <div style="display:flex; gap:8px; margin-bottom:10px;">
          <input id="rech-candidat" type="text" placeholder="Rechercher par nom, prénom, e-mail ou numéro de passeport..." style="flex:1;" />
          <button id="btn-rechercher-candidat" class="btn btn-secondaire" type="button">Rechercher / Actualiser</button>
        </div>
        <table id="table-candidats">
          <thead><tr><th>Nom &amp; Prénom</th><th>Passeport</th><th>Formation / Établissement</th><th>Consentement Loi 18-07</th><th>Actions</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </section>

    <!-- 3. Documents & Pièces requises -->
    <section id="vue-documents" class="vue-ecran cache">
      <h2>Documents justificatifs &amp; Vérification des pièces manquantes</h2>
      <div class="carte">
        <h3>1. Téléverser une pièce justificative (chiffrée en AES-256-GCM)</h3>
        <div class="grille-form">
          <label>Type de pièce justificative
            <select id="doc-type-piece">
              <option value="passeport">Passeport biométrique en cours de validité</option>
              <option value="photo_identite">Photo d'identité aux normes passeport</option>
              <option value="releve_notes_bac">Relevé de notes du Baccalauréat</option>
              <option value="diplome_bac">Diplôme ou attestation provisoire du Baccalauréat</option>
              <option value="releves_notes_superieur">Relevés de notes des années d'études supérieures</option>
              <option value="cv">Curriculum Vitæ (CV)</option>
              <option value="attestation_langue_francaise">Attestation de test de français (TCF / DELF / DALF)</option>
              <option value="lettre_admission_dli">IRCC Canada : Lettre d'admission d'un établissement désigné (EED / DLI)</option>
              <option value="attestation_provinciale_pal_caq">IRCC Canada : Lettre d'attestation provinciale (LAP / PAL) ou CAQ Québec</option>
              <option value="preuve_financiere">IRCC Canada : Preuve de ressources financières (relevés, CPG/GIC, garant)</option>
              <option value="formulaire_imm5645">IRCC Canada : Formulaire d'informations sur la famille (IMM 5645)</option>
              <option value="lettre_explicative">IRCC Canada : Lettre d'explication / Plan d'études</option>
            </select>
          </label>
          <label>Date d'expiration du document (si applicable) <input id="doc-expiration" type="date" value="2031-05-20" /></label>
          <label>Fichier justificatif (PDF, PNG ou JPEG — max 10 Mo) <input id="doc-fichier" type="file" accept=".pdf,.png,.jpg,.jpeg" /></label>
        </div>
        <p style="margin-top:12px;">
          <button id="btn-televerser-doc" class="btn btn-succes" type="button">Téléverser et chiffrer la pièce</button>
          <button id="btn-verifier-completude" class="btn" type="button">Vérifier les pièces manquantes (Campus France &amp; IRCC)</button>
          <button id="btn-specimens-demo" class="btn btn-secondaire" type="button">Générer les pièces spécimens de démonstration pour ce candidat</button>
        </p>
      </div>

      <div class="carte">
        <h3>2. État des pièces justificatives par démarche</h3>
        <div id="zone-completude" class="panneau-texte">
          Sélectionnez un candidat puis cliquez sur « Vérifier les pièces manquantes » pour afficher la liste claire des pièces manquantes et des pièces déposées.
        </div>
      </div>

      <div class="carte">
        <h3>3. Pièces déjà déposées dans le dossier du candidat</h3>
        <table id="table-documents-candidat">
          <thead><tr><th>Pièce justificative</th><th>Fichier d'origine</th><th>Date d'expiration</th><th>Taille</th><th>Actions</th></tr></thead>
          <tbody><tr><td colspan="5">Sélectionnez un candidat pour voir ses pièces déposées.</td></tr></tbody>
        </table>
      </div>
    </section>

    <!-- 4. Discussion & Score d'acceptation -->
    <section id="vue-conseiller" class="vue-ecran cache">
      <h2>Espace Discussion Conseiller &amp; Score d'acceptation (0 à 100 %)</h2>
      <div class="carte">
        <h3>1. Évaluation détaillée des chances d'acceptation et de la solidité du dossier</h3>
        <div class="grille-form">
          <label>Démarche à évaluer
            <select id="eval-demarche">
              <option value="campus_france">Campus France — Études en France (Guide Septembre 2026)</option>
              <option value="ircc_permis_etudes">IRCC Canada — Demande de permis d'études</option>
            </select>
          </label>
        </div>
        <p style="margin-top:12px;">
          <button id="btn-calculer-score" class="btn" type="button">Calculer le score d'acceptation (0–100 %)</button>
        </p>
        <div id="zone-score-acceptation" class="panneau-texte">
          Cliquez sur « Calculer le score d'acceptation » pour afficher l'évaluation complète en français (score sur 100 %, pièces manquantes éventuelles, points forts et plan d'action).
        </div>
      </div>

      <div class="carte">
        <h3>2. Poser une question à l'Assistant Conseiller sur ce dossier</h3>
        <p style="font-size:0.86rem; color:var(--texte-secondaire); margin-top:0;">
          Questions rapides :
          <button class="btn btn-contour" type="button" onclick="poserQuestionRapide('Quelles sont les pièces manquantes et quelle est notre priorité sur ce dossier ?')">Pièces manquantes &amp; Priorité</button>
          <button class="btn btn-contour" type="button" onclick="poserQuestionRapide('Quels sont les délais du calendrier Campus France Algérie 2026-2027 et les frais en DZD ?')">Calendrier &amp; Frais Algérie (20 000 DZD)</button>
          <button class="btn btn-contour" type="button" onclick="poserQuestionRapide('Comment fonctionne le panier de 7 formations (DAP Blanche, DAP Jaune, Hors DAP) et la motivation de 4000 caractères ?')">Panier 7 formations &amp; Motivation</button>
          <button class="btn btn-contour" type="button" onclick="poserQuestionRapide('Comment déclarer un bac algérien en français (> 1000 heures) et remplir le dossier de scolarité (2 activités) ?')">Bac en français &gt; 1000h &amp; Scolarité</button>
          <button class="btn btn-contour" type="button" onclick="poserQuestionRapide('Comment fonctionne le dossier pré-consulaire en 4 étapes et la réduction visa CAPAGO de 50 % ?')">Dossier pré-consulaire &amp; Visa CAPAGO</button>
        </p>
        <div id="fil-discussion" class="fil-discussion">
          <div style="color:var(--texte-secondaire); font-size:0.9rem;">Posez une question ci-dessous ou cliquez sur l'un des boutons de question rapide pour obtenir l'analyse du Conseiller.</div>
        </div>
        <div style="display:flex; gap:10px; align-items:center;">
          <input id="msg-discussion" type="text" style="flex:1;" value="Quelle est notre priorité pour maximiser les chances d'acceptation de ce dossier ?" placeholder="Posez votre question au conseiller..." />
          <button id="btn-envoyer-discussion" class="btn btn-succes" type="button" style="margin:0;">Envoyer au Conseiller</button>
        </div>
      </div>
    </section>

    <!-- 5. Campus France (Études en France — Guide Septembre 2026 & Co-Pilote Navigateur Direct) -->
    <section id="vue-campus-france" class="vue-ecran cache">
      <h2>Démarche Campus France — Études en France (Co-Pilote Navigateur Direct — Guide Septembre 2026)</h2>

      <div class="carte">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:10px;">
          <div>
            <h3 style="margin:0;"><span class="point-vert-pulsant"></span>Co-Pilote Navigateur IA en Direct (Style Perplexity Assistant / Claude Cowork)</h3>
            <div style="font-size:0.86rem; color:var(--texte-secondaire); margin-top:3px;">
              Contrôle direct et temps réel de votre navigateur (sans capture d'écran) : barre latérale IA injectée dans la page, curseur animé en direct et compréhension du langage naturel.
            </div>
          </div>
          <div>
            <button class="btn" type="button" onclick="executerActionDomRapide('campus_france', 'focus_fenetre')">🖥️ Mettre la fenêtre du navigateur au 1er plan</button>
            <button id="btn-creer-tache-cf" class="btn btn-secondaire" type="button">Suivi de la tâche Campus France</button>
          </div>
        </div>

        <div class="grille-form">
          <label>Portail cible dans le navigateur
            <select id="cf-cible-navigateur" onchange="changerCibleNavigateurDirect('campus_france')">
              <option value="campus_france_officiel" selected>Vrai site officiel Études en France (https://etudesenfrance.diplomatie.gouv.fr/)</option>
              <option value="demo_campus_france">Portail interactif Études en France — Mode direct intégré (Guide Septembre 2026)</option>
              <option value="campus_france_algerie">Site Campus France Algérie (https://www.algerie.campusfrance.org)</option>
              <option value="paiement_ifa_algerie">Portail de paiement IFA Algérie (https://paiement.if-algerie.com)</option>
            </select>
          </label>
          <label style="justify-content:center;">
            <span>Mode de contrôle du navigateur</span>
            <span style="font-weight:400; margin-top:6px;">
              <input id="cf-fenetre-visible" type="checkbox" checked /> Piloter directement ma vraie fenêtre Chrome / Edge / Chromium (avec barre latérale Co-Pilote intégrée)
            </span>
          </label>
        </div>

        <p style="margin-top:10px; margin-bottom:4px;"><strong>Actions directes en 1 clic dans le navigateur (Guide Études en France — Septembre 2026) :</strong></p>
        <div>
          <button class="btn" type="button" onclick="lancerActionNavigateur('campus_france', 'ouvrir_portail')">1. Ouvrir le site en direct</button>
          <button class="btn btn-succes" type="button" onclick="lancerActionNavigateur('campus_france', 'preremplissage_complet')">2. ⚡ Tout remplir en direct + Pièces + Arrêt Règle 1</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('campus_france', 'inscription_compte')">3. S'inscrire (Créer compte)</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('campus_france', 'connexion_compte')">3. Se connecter (Règle 3)</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('campus_france', 'preremplir_espace_etudiant')">4. Identité, Passeport &amp; Antenne ECF</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('campus_france', 'preremplir_scolarite_et_langues')">4. Scolarité (2 activités) &amp; Français &gt; 1000h</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('campus_france', 'preremplir_panier_formations_et_motivations')">5. Panier (max 7) &amp; Motivation (4 000 car.)</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('campus_france', 'preparer_paiement_et_rdv')">5. Paiement (20 000 DZD) &amp; RDV</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('campus_france', 'preremplir_dossier_preconsulaire')">6. Dossier pré-consulaire (4 étapes)</button>
        </div>

        <div class="workspace-cowork">
          <!-- Colonne Gauche : Navigateur en Direct & Inspecteur DOM Temps Réel (Zéro Capture d'Écran) -->
          <div class="cadre-navigateur-direct">
            <div class="barre-chrome-direct">
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('campus_france', 'retour')" title="Page précédente">⬅</button>
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('campus_france', 'suivant')" title="Page suivante">➡</button>
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('campus_france', 'actualiser')" title="Actualiser la page">↻</button>
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('campus_france', 'scroll_haut')" title="Monter">⬆️</button>
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('campus_france', 'scroll_bas')" title="Descendre">⬇️</button>
              <input id="cf-url-live" class="url-live-input" type="text" value="https://etudesenfrance.diplomatie.gouv.fr/" placeholder="Entrez une URL et appuyez sur Aller..." />
              <button class="btn-nav-mini" type="button" onclick="naviguerUrlDirecte('campus_france')">Aller</button>
              <button class="btn-nav-mini" type="button" onclick="basculerModeVueDirecte('campus_france')" id="btn-mode-vue-cf">Vue : Contrôle DOM &amp; Fenêtre</button>
            </div>
            <div id="cf-conteneur-iframe" class="cache">
              <iframe id="cf-iframe-direct" class="iframe-navigateur-direct" src="/demo/campus-france" title="Portail interactif Études en France en direct"></iframe>
            </div>
            <div id="cf-panneau-dom-live" class="corps-navigateur-direct">
              <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #e2e8f0; padding-bottom:8px; margin-bottom:10px;">
                <div>
                  <strong id="cf-titre-page-live">Contrôleur DOM en Direct — Études en France</strong>
                  <div style="font-size:0.8rem; color:var(--texte-secondaire);">Interagissez en temps réel avec les champs et boutons de la page ouverte dans votre navigateur (sans capture d'écran).</div>
                </div>
                <button class="btn btn-contour" type="button" style="margin:0; padding:5px 10px; font-size:0.8rem;" onclick="synchroniserEtatNavigateurDirect('campus_france')">🔄 Synchroniser DOM</button>
              </div>
              <div id="cf-elements-dom-live">
                <p style="color:var(--texte-secondaire); font-size:0.88rem;">
                  Cliquez sur <strong>« 1. Ouvrir le site en direct »</strong> ou tapez une consigne à droite (ex: <em>« ouvre le vrai site Campus France »</em>, <em>« remplis mon identité »</em>) pour voir et manipuler en direct tous les éléments de la page.
                </p>
              </div>
            </div>
          </div>

          <!-- Colonne Droite : Conversation Co-Pilote Temps Réel (Compréhension Naturelle & Voix) -->
          <div class="panneau-copilote-chat">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <strong>💬 Assistant Co-Pilote Navigateur (Langage naturel &amp; Voix)</strong>
              <span class="badge badge-ok">Temps réel</span>
            </div>
            <div style="font-size:0.8rem; color:var(--texte-secondaire);">
              Exemples de demandes naturelles (cliquez pour tester) :
              <div style="margin-top:4px;">
                <span class="puce-cmd" onclick="envoyerConsigneRapideCopilote('campus_france', 'Ouvre le vrai site Études en France dans mon navigateur')">🌐 Vrai site Études en France</span>
                <span class="puce-cmd" onclick="envoyerConsigneRapideCopilote('campus_france', 'Clique sur S\'inscrire et pré-remplis mon compte')">📝 Aller sur S'inscrire</span>
                <span class="puce-cmd" onclick="envoyerConsigneRapideCopilote('campus_france', 'Analyse cette page et explique-moi ce qu\'il faut faire')">🔍 Analyser cette page</span>
                <span class="puce-cmd" onclick="envoyerConsigneRapideCopilote('campus_france', 'Mets Oran comme ville et Université Paris-Saclay comme établissement')">✏️ Changer ville &amp; université</span>
                <span class="puce-cmd" onclick="envoyerConsigneRapideCopilote('campus_france', 'Remplis mes motivations pour ma formation')">✍️ Rédiger motivations</span>
                <span class="puce-cmd" onclick="envoyerConsigneRapideCopilote('campus_france', 'Quels sont les frais en DZD et les dates limites 2026-2027 ?')">📅 Frais 20 000 DZD &amp; Dates</span>
              </div>
            </div>

            <div id="fil-copilote-cf" class="fil-copilote">
              <div class="bulle-copilote-ia">
                <strong>Co-Pilote prêt.</strong> Dites-moi en français naturel ce que je dois faire dans votre navigateur (ex: <em>« remplis mon identité »</em>, <em>« clique sur Se connecter »</em>, <em>« mets Constantine comme ville »</em>, <em>« descends en bas de la page »</em>, <em>« remplis tout sans soumettre »</em>).
              </div>
            </div>

            <div style="display:flex; gap:6px; align-items:center;">
              <input id="cf-instruction-agent" type="text" style="flex:1;" value="Pré-remplir tout le dossier Études en France du candidat (identité, passeport, scolarité, langues, panier de formations et motivation) et enregistrer le brouillon" placeholder="Parlez naturellement à l'agent (ex: clique sur S'inscrire, mets Oran comme ville, remplis cette page...)" />
              <button class="btn btn-secondaire" type="button" style="margin:0; padding:9px 11px;" onclick="demarrerDicteeVocale('campus_france')" title="Dicter votre consigne à la voix">🎤</button>
              <button id="btn-piloter-cf-instruction" class="btn btn-succes" type="button" style="margin:0;">Exécuter en direct</button>
            </div>

            <div id="zone-retour-cf" class="panneau-texte" style="padding:12px 14px; font-size:0.88rem;">
              Sélectionnez un candidat puis donnez une instruction en langage naturel ci-dessus ou cliquez sur une action directe.
            </div>
          </div>
        </div>
      </div>

      <div class="carte">
        <h3>2. Guide officiel complet « Études en France — Septembre 2026 » (Campus France Algérie — 96 pages)</h3>
        <details class="guide-bloc" open>
          <summary>Calendrier officiel Campus France Algérie (Session 2026–2027) &amp; Frais de dossier (DZD)</summary>
          <div style="margin-top:8px; font-size:0.9rem;">
            <ul class="liste-propre">
              <li><strong>Hors DAP (L2, L3, Master 1, Master 2, Écoles d'ingénieurs et de commerce) :</strong> Ouverture le <strong>1er octobre 2026</strong> — Date limite de soumission et de paiement : <strong>30 novembre 2026</strong> — Entretiens jusqu'au <strong>15 mars 2027</strong> — Choix définitif avant le <strong>31 mai 2027</strong>.</li>
              <li><strong>DAP (L1 Université, Écoles d'architecture ENSA, BUT, Licence professionnelle) :</strong> Ouverture le <strong>1er octobre 2026</strong> — Date limite de soumission et de paiement : <strong>15 décembre 2026</strong> — Entretiens jusqu'au <strong>15 mars 2027</strong> — Choix définitif avant le <strong>31 mai 2027</strong>.</li>
              <li><strong>CPGE, BTS, DCG :</strong> À partir de <strong>janvier 2027</strong> sur Parcoursup.</li>
              <li><strong>Dossier pré-consulaire (« Je suis accepté » / Établissements privés non-connectés) :</strong> Dès réception de l'acceptation, au minimum <strong>45 jours avant la rentrée</strong>.</li>
              <li><strong>Frais de dossier Algérie :</strong> Plein tarif : <strong>20 000 DZD</strong> | Demi-tarif : <strong>10 000 DZD</strong> (Bac français &lt; 4 ans et candidat &lt; 22 ans, ou acceptation Campus Art) | <strong>Gratuité :</strong> Boursier du gouvernement français, bachelier du LIAD de l'année en cours, agent de l'Institut français d'Algérie. Paiement sur <code>paiement.if-algerie.com</code>.</li>
              <li><strong>5 Antennes Espace Campus France Algérie :</strong> Alger (<code>ecf.alger@if-algerie.com</code>), Annaba (<code>ecf.annaba@if-algerie.com</code>), Constantine (<code>ecf.constantine@if-algerie.com</code>), Oran (<code>ecf.oran@if-algerie.com</code>), Tlemcen (<code>ecf.tlemcen@if-algerie.com</code>).</li>
            </ul>
          </div>
        </details>

        <details class="guide-bloc">
          <summary>Sections 3 &amp; 4 : Mon compte &amp; Mon espace étudiant (Identité, Scolarité, Compétences linguistiques)</summary>
          <div style="margin-top:8px; font-size:0.9rem;">
            <ul class="liste-propre">
              <li><strong>Inscription &amp; Connexion :</strong> Bouton « S'inscrire » sur <code>https://etudesenfrance.diplomatie.gouv.fr/</code> (Espace Campus France Algérie, activation par mail sous 48h). Attention : compte bloqué <strong>30 minutes après 5 tentatives</strong> de mot de passe erronées.</li>
              <li><strong>Mes informations personnelles :</strong> Identité, Photo d'identité au format passeport (JPG/PNG/PDF, max 10 Mo), Passeport valide (numéro, date limite de validité, copie), Coordonnées (adresse et téléphone déterminant l'antenne ECF), et Statut particulier (« Je ne suis concerné par aucun de ces statuts particuliers »).</li>
              <li><strong>Mon dossier de scolarité :</strong> CV obligatoire + <strong>au moins 2 activités obligatoires</strong> dans « Parcours scolaire et professionnel » (années de lycée jusqu'au bac pour Bac+1 ; du bac jusqu'à la dernière année d'études supérieures pour Bac+2 et plus ; commentaire limité à 1 000 caractères).</li>
              <li><strong>Mes compétences linguistiques :</strong> Pour un baccalauréat algérien/non européen en français : sélectionner « Oui », Volume « Plus de 1000 heures », Durée « 4 ans et plus », Niveau atteint « Avancé ». Ajouter le test TCF ou DELF/DALF dans « + Ajouter un test », puis renseigner le niveau d'anglais.</li>
            </ul>
          </div>
        </details>

        <details class="guide-bloc">
          <summary>Sections 5 &amp; 6 : Mon dossier de candidature (Panier max 7 choix) &amp; Mon dossier pré-consulaire</summary>
          <div style="margin-top:8px; font-size:0.9rem;">
            <ul class="liste-propre">
              <li><strong>Règles du panier (max 7 formations) :</strong> DAP Blanche (L1 : jusqu'à 3 choix), DAP Jaune (Architecture ENSA : 2 choix obligatoires + Portfolio), Hors DAP (L2, L3, M1, M2, Ingénieur, Commerce : jusqu'à 7 choix). Vérifier le badge « OUVERT À LA CANDIDATURE ».</li>
              <li><strong>Texte de motivation :</strong> Obligatoire pour chaque formation du panier (jusqu'à <strong>4 000 caractères</strong>) puis cliquer sur « Enregistrer ».</li>
              <li><strong>Soumission (Règle 1) :</strong> L'agent s'arrête toujours avant les 2 cases de certification et le bouton « Soumettre mon dossier de candidature ».</li>
              <li><strong>Dossier pré-consulaire (« Je suis accepté ») :</strong> Sélection de la formation acceptée via Études en France, ou ajout d'une acceptation papier / programme d'échange en <strong>4 étapes</strong>. Permet d'obtenir l'Attestation d'acceptation (identifiant <code>DZXX-XXXXX</code>) donnant droit à <strong>-50 % sur les frais de visa long séjour</strong> chez CAPAGO.</li>
            </ul>
          </div>
        </details>
      </div>
    </section>

    <!-- 6. IRCC Canada (Co-Pilote Navigateur Direct) -->
    <section id="vue-ircc" class="vue-ecran cache">
      <h2>Démarche IRCC Canada — Demande de permis d'études (Co-Pilote Navigateur Direct)</h2>
      <div class="carte">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:10px;">
          <div>
            <h3 style="margin:0;"><span class="point-vert-pulsant"></span>Co-Pilote Navigateur IRCC Canada en Direct (Style Perplexity / Claude Cowork)</h3>
            <div style="font-size:0.86rem; color:var(--texte-secondaire); margin-top:3px;">
              Contrôle automatique du seuil financier (<strong>20 635 $ CAD</strong> ≈ <strong>14 500 EUR</strong>), de la LAP/PAL ou CAQ Québec et de l'admission EED/DLI. Arrêt garanti avant signature/transmission (Règle 1).
            </div>
          </div>
          <div>
            <button class="btn" type="button" onclick="executerActionDomRapide('ircc_permis_etudes', 'focus_fenetre')">🖥️ Mettre la fenêtre du navigateur au 1er plan</button>
            <button id="btn-creer-tache-ircc" class="btn btn-secondaire" type="button">Suivi de la tâche IRCC</button>
          </div>
        </div>

        <div class="grille-form">
          <label>Portail cible dans le navigateur
            <select id="ircc-cible-navigateur" onchange="changerCibleNavigateurDirect('ircc_permis_etudes')">
              <option value="ircc_officiel" selected>Vrai portail officiel IRCC Canada (https://portal-portail.apps.cic.gc.ca/signin?lang=fr)</option>
              <option value="demo_ircc">Portail interactif IRCC — Mode direct intégré</option>
              <option value="ircc_canada_info">Page officielle Permis d'études Canada.ca</option>
            </select>
          </label>
          <label style="justify-content:center;">
            <span>Mode de contrôle du navigateur</span>
            <span style="font-weight:400; margin-top:6px;">
              <input id="ircc-fenetre-visible" type="checkbox" checked /> Piloter directement ma vraie fenêtre Chrome / Edge / Chromium (avec barre latérale Co-Pilote intégrée)
            </span>
          </label>
        </div>

        <p style="margin-top:10px;">
          <button class="btn" type="button" onclick="lancerActionNavigateur('ircc_permis_etudes', 'ouvrir_portail')">1. Ouvrir le portail IRCC en direct</button>
          <button class="btn btn-succes" type="button" onclick="lancerActionNavigateur('ircc_permis_etudes', 'preremplissage_complet')">2. ⚡ Tout pré-remplir + Joindre pièces IRCC + Arrêt Règle 1</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('ircc_permis_etudes', 'preremplir_identite_ircc')">3. Identité &amp; Passeport IRCC</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('ircc_permis_etudes', 'preremplir_dli_fonds_ircc')">4. Établissement DLI &amp; Fonds (20 635 CAD)</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('ircc_permis_etudes', 'televerser_pieces_ircc')">5. Téléverser les 6 pièces IRCC (PAL/CAQ, IMM 5645...)</button>
        </p>

        <div class="workspace-cowork">
          <!-- Colonne Gauche : Navigateur IRCC en Direct & Inspecteur DOM -->
          <div class="cadre-navigateur-direct">
            <div class="barre-chrome-direct">
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('ircc_permis_etudes', 'retour')" title="Page précédente">⬅</button>
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('ircc_permis_etudes', 'suivant')" title="Page suivante">➡</button>
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('ircc_permis_etudes', 'actualiser')" title="Actualiser">↻</button>
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('ircc_permis_etudes', 'scroll_haut')" title="Monter">⬆️</button>
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('ircc_permis_etudes', 'scroll_bas')" title="Descendre">⬇️</button>
              <input id="ircc-url-live" class="url-live-input" type="text" value="https://portal-portail.apps.cic.gc.ca/signin?lang=fr" placeholder="URL IRCC..." />
              <button class="btn-nav-mini" type="button" onclick="naviguerUrlDirecte('ircc_permis_etudes')">Aller</button>
              <button class="btn-nav-mini" type="button" onclick="basculerModeVueDirecte('ircc_permis_etudes')" id="btn-mode-vue-ircc">Vue : Contrôle DOM &amp; Fenêtre</button>
            </div>
            <div id="ircc-conteneur-iframe" class="cache">
              <iframe id="ircc-iframe-direct" class="iframe-navigateur-direct" src="/demo/ircc" title="Portail interactif IRCC Canada en direct"></iframe>
            </div>
            <div id="ircc-panneau-dom-live" class="corps-navigateur-direct">
              <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #e2e8f0; padding-bottom:8px; margin-bottom:10px;">
                <div>
                  <strong id="ircc-titre-page-live">Contrôleur DOM en Direct — Portail IRCC Canada</strong>
                  <div style="font-size:0.8rem; color:var(--texte-secondaire);">Manipulez en temps réel les champs et boutons de votre navigateur sans capture d'écran.</div>
                </div>
                <button class="btn btn-contour" type="button" style="margin:0; padding:5px 10px; font-size:0.8rem;" onclick="synchroniserEtatNavigateurDirect('ircc_permis_etudes')">🔄 Synchroniser DOM</button>
              </div>
              <div id="ircc-elements-dom-live">
                <p style="color:var(--texte-secondaire); font-size:0.88rem;">
                  Cliquez sur <strong>« 1. Ouvrir le portail IRCC en direct »</strong> ou donnez une consigne à droite pour inspecter et remplir les champs en direct.
                </p>
              </div>
            </div>
          </div>

          <!-- Colonne Droite : Conversation Co-Pilote IRCC Temps Réel -->
          <div class="panneau-copilote-chat">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <strong>💬 Assistant Co-Pilote IRCC (Langage naturel &amp; Voix)</strong>
              <span class="badge badge-ok">Temps réel</span>
            </div>
            <div style="font-size:0.8rem; color:var(--texte-secondaire);">
              Exemples de demandes naturelles :
              <div style="margin-top:4px;">
                <span class="puce-cmd" onclick="envoyerConsigneRapideCopilote('ircc_permis_etudes', 'Ouvre le vrai portail officiel IRCC Canada')">🌐 Vrai portail IRCC</span>
                <span class="puce-cmd" onclick="envoyerConsigneRapideCopilote('ircc_permis_etudes', 'Analyse cette page IRCC et dis-moi quoi remplir')">🔍 Analyser la page</span>
                <span class="puce-cmd" onclick="envoyerConsigneRapideCopilote('ircc_permis_etudes', 'Mets Université Laval comme établissement et 21000 euros comme fonds')">✏️ Changer DLI &amp; Fonds</span>
                <span class="puce-cmd" onclick="envoyerConsigneRapideCopilote('ircc_permis_etudes', 'Remplis tout le formulaire IRCC et téléverse les pièces sans transmettre')">⚡ Tout remplir IRCC</span>
              </div>
            </div>

            <div id="fil-copilote-ircc" class="fil-copilote">
              <div class="bulle-copilote-ia">
                <strong>Co-Pilote IRCC prêt.</strong> Demandez-moi n'importe quelle action en français (ex: <em>« remplis mon identité et le DLI »</em>, <em>« mets 19000 euros comme fonds »</em>, <em>« quelles sont les règles PAL/CAQ ? »</em>).
              </div>
            </div>

            <div style="display:flex; gap:6px; align-items:center;">
              <input id="ircc-instruction-agent" type="text" style="flex:1;" value="Pré-remplir toute la demande de permis d'études IRCC (identité, passeport, établissement DLI, ressources financières et pièces justificatives) et sauvegarder le brouillon" placeholder="Parlez naturellement à l'agent IRCC..." />
              <button class="btn btn-secondaire" type="button" style="margin:0; padding:9px 11px;" onclick="demarrerDicteeVocale('ircc_permis_etudes')" title="Dicter votre consigne à la voix">🎤</button>
              <button id="btn-piloter-ircc-instruction" class="btn btn-succes" type="button" style="margin:0;">Exécuter en direct</button>
            </div>

            <div id="zone-retour-ircc" class="panneau-texte" style="padding:12px 14px; font-size:0.88rem;">
              Sélectionnez un candidat puis donnez une instruction en langage naturel ci-dessus ou cliquez sur une action directe.
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 7. Centre de validation humaine -->
    <section id="vue-validation-humaine" class="vue-ecran cache">
      <h2>Centre de validation humaine (Règle 1 — Option A)</h2>
      <div class="banniere-regle">
        Aucune demande officielle n'est jamais soumise par l'agent. Vérifiez la capture d'écran de contrôle et le récapitulatif en français ci-dessous avant d'approuver humainement.
      </div>
      <p><button id="btn-rafraichir-validations" class="btn" type="button">Actualiser les dossiers en attente de validation ou en pause</button></p>
      <div id="liste-centre-validation" class="panneau-texte">Chargement des dossiers...</div>
    </section>

    <!-- 8. Historique & Erreurs -->
    <section id="vue-historique-erreurs" class="vue-ecran cache">
      <h2>Historique d'audit immuable &amp; Journal des opérations (Règle 5)</h2>
      <div class="carte">
        <p><button id="btn-rafraichir-audit" class="btn btn-secondaire" type="button">Actualiser le journal d'audit</button></p>
        <table id="table-audit">
          <thead><tr><th>Date &amp; Heure (UTC)</th><th>Opération</th><th>Statut</th><th>Ressource</th><th>Résumé (sans donnée personnelle — Règle 5)</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </section>

    <!-- 9. Paramètres & Sauvegardes -->
    <section id="vue-parametres" class="vue-ecran cache">
      <h2>Paramètres du Bureau, Abonnement SaaS, Agents Locaux &amp; Sauvegardes chiffrées</h2>
      <div class="carte">
        <h3>1. Enrôler un poste Agent Local Playwright dans le bureau</h3>
        <div class="grille-form">
          <label>Nom du poste Windows du bureau <input id="nom-machine-agent" type="text" value="PC-BUREAU-ALGER-01" /></label>
        </div>
        <p style="margin-top:12px;"><button id="btn-enroler-agent" class="btn" type="button">Enrôler ce poste et générer sa clé d'accès</button></p>
        <div id="zone-jeton-agent" class="panneau-texte cache"></div>
      </div>
      <div class="carte">
        <h3>2. Sauvegardes chiffrées AES-256-GCM du bureau &amp; Statut Abonnement / Portails</h3>
        <p>
          <button id="btn-creer-sauvegarde" class="btn btn-succes" type="button">Créer une sauvegarde chiffrée (.be.enc)</button>
          <button id="btn-voir-abonnement" class="btn btn-secondaire" type="button">Afficher mon abonnement &amp; le statut d'homologation des portails (Règle 6)</button>
        </p>
        <div id="zone-sauvegardes-abo" class="panneau-texte">Cliquez sur l'un des boutons ci-dessus.</div>
      </div>
    </section>
  </main>

  <script>
    let jetonCsrf = "";
    let candidatActifId = null;
    let candidatActifObj = null;
    let dictionnaireCandidats = {};

    const LIBELLES_PIECES_FR = {
      passeport: "Passeport biométrique en cours de validité",
      photo_identite: "Photo d'identité aux normes passeport",
      releve_notes_bac: "Relevé de notes du Baccalauréat",
      diplome_bac: "Diplôme ou attestation provisoire du Baccalauréat",
      releves_notes_superieur: "Relevés de notes des années d'études supérieures",
      cv: "Curriculum Vitæ (CV)",
      attestation_langue_francaise: "Attestation de test de français (TCF / DELF / DALF)",
      lettre_admission_dli: "Lettre d'admission d'un établissement désigné (EED / DLI)",
      attestation_provinciale_pal_caq: "Lettre d'attestation provinciale (LAP / PAL) ou CAQ Québec",
      preuve_financiere: "Preuve de ressources financières",
      formulaire_imm5645: "Formulaire d'informations sur la famille (IMM 5645)",
      lettre_explicative: "Lettre d'explication / Plan d'études"
    };

    const LIBELLES_CHAMPS_FR = {
      nom: "Nom de famille",
      prenom: "Prénom",
      sexe: "Sexe",
      date_naissance: "Date de naissance",
      lieu_naissance: "Lieu de naissance",
      nationalite: "Nationalité",
      pays_residence: "Pays de résidence",
      email: "Adresse e-mail",
      telephone: "Numéro de téléphone",
      numero_passeport: "Numéro de passeport",
      date_expiration_passeport: "Date d'expiration du passeport",
      niveau_actuel: "Niveau d'études actuel",
      programme_vise: "Formation / Programme visé",
      etablissement_vise: "Établissement visé",
      fonds_disponibles_eur: "Ressources financières disponibles (EUR)"
    };

    const LIBELLES_SOLIDITE_FR = {
      tres_solide: "Très solide",
      favorable: "Favorable",
      fragile: "Fragile (à consolider)",
      risque_eleve: "Risque élevé de refus",
      incomplet_ou_bloquant: "Dossier incomplet (pièces ou informations requises manquantes)"
    };

    const LIBELLES_STATUT_TACHE_FR = {
      en_attente: "En attente de lancement",
      en_cours: "En cours d'exécution par l'agent",
      suspendue: "En pause (intervention ou pièce requise)",
      a_valider: "Prêt pour validation humaine (arrêté avant soumission — Règle 1)",
      terminee: "Validé humainement et terminé",
      annulee: "Annulé",
      en_erreur: "En erreur"
    };

    function echapperHtml(str) {
      if (str === null || str === undefined) return "";
      return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function notifier(msg, ok = true) {
      const el = document.getElementById("zone-notification");
      el.textContent = msg;
      el.className = "notif " + (ok ? "notif-ok" : "notif-err");
      el.classList.remove("cache");
    }

    function allerVersVue(cible) {
      document.querySelectorAll("aside button.nav-btn").forEach((b) => {
        b.classList.toggle("actif", b.getAttribute("data-vue") === cible);
      });
      document.querySelectorAll(".vue-ecran").forEach((s) => {
        s.classList.toggle("cache", s.id !== cible);
      });
      if (cible === "vue-documents" && candidatActifId) {
        chargerDocumentsCandidat();
        verifierCompletudeDossier();
      } else if (cible === "vue-conseiller" && candidatActifId) {
        chargerHistoriqueDiscussion();
      } else if (cible === "vue-validation-humaine") {
        rafraichirValidationsHumaines();
      } else if (cible === "vue-historique-erreurs") {
        rafraichirJournalAudit();
      }
    }

    document.querySelectorAll("aside button.nav-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        allerVersVue(btn.getAttribute("data-vue"));
      });
    });

    async function appelApi(url, options = {}) {
      const headers = Object.assign({}, options.headers || {});
      if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
        headers["Content-Type"] = "application/json";
      }
      if (jetonCsrf) headers["X-CSRF-Token"] = jetonCsrf;
      return fetch(url, Object.assign({}, options, { headers }));
    }

    async function connecterOperateur(silencieux = false) {
      const email = document.getElementById("login-email").value.trim();
      const mot_de_passe = document.getElementById("login-mdp").value;
      const rep = await appelApi("/api/v1/auth/connexion", {
        method: "POST",
        body: JSON.stringify({ email, mot_de_passe }),
      });
      if (rep.ok) {
        const data = await rep.json();
        jetonCsrf = data.jeton_csrf;
        const roleFr = data.utilisateur.role === "administrateur" ? "Administrateur du bureau" : "Employé";
        document.getElementById("etat-utilisateur").textContent =
          data.utilisateur.nom_affiche + " (" + roleFr + ")";
        document.getElementById("btn-se-deconnecter").classList.remove("cache");
        if (!silencieux) notifier("Session opérateur ouverte avec succès.", true);
        await chargerCandidats();
        await rafraichirTableauDeBord();
      } else {
        document.getElementById("etat-utilisateur").textContent = "Non connecté — cliquez sur Se connecter";
        if (!silencieux) {
          const err = await rep.json();
          notifier(err.detail || "Échec de connexion", false);
        }
      }
    }

    document.getElementById("btn-se-connecter").addEventListener("click", () => connecterOperateur(false));

    document.getElementById("btn-se-deconnecter").addEventListener("click", async () => {
      await appelApi("/api/v1/auth/deconnexion", { method: "POST" });
      jetonCsrf = "";
      document.getElementById("etat-utilisateur").textContent = "Non connecté";
      document.getElementById("btn-se-deconnecter").classList.add("cache");
      notifier("Session fermée.", true);
    });

    async function rafraichirTableauDeBord() {
      const [rCand, rVal, rAg] = await Promise.all([
        appelApi("/api/v1/candidats"),
        appelApi("/api/v1/validations/en-attente"),
        appelApi("/api/v1/agents-locaux"),
      ]);
      if (rCand.ok) {
        const c = await rCand.json();
        document.getElementById("stat-nb-candidats").textContent = c.total;
        (c.elements || []).forEach((cand) => {
          dictionnaireCandidats[cand.id] = cand;
        });
      }
      if (rVal.ok) {
        const v = await rVal.json();
        document.getElementById("stat-nb-a-valider").textContent = v.total_a_valider;
        document.getElementById("stat-nb-suspendues").textContent = v.total_suspendues;
      }
      if (rAg.ok) {
        const a = await rAg.json();
        document.getElementById("stat-nb-agents").textContent = a.length;
      }
    }

    async function chargerCandidats() {
      const q = document.getElementById("rech-candidat").value.trim();
      const url = q ? "/api/v1/candidats?recherche=" + encodeURIComponent(q) : "/api/v1/candidats";
      const rep = await appelApi(url);
      if (!rep.ok) return;
      const data = await rep.json();
      const tbody = document.querySelector("#table-candidats tbody");
      tbody.innerHTML = "";
      if (data.elements.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5">Aucun candidat enregistré pour le moment. Cliquez sur « Enregistrer le candidat » ci-dessus pour créer la première fiche.</td></tr>`;
        return;
      }
      data.elements.forEach((c) => {
        dictionnaireCandidats[c.id] = c;
        if (!candidatActifId) selectionnerCandidat(c, true);
        const tr = document.createElement("tr");
        const estActif = c.id === candidatActifId;
        tr.style.background = estActif ? "#eff6ff" : "";
        tr.innerHTML = `
          <td><strong>${echapperHtml(c.nom)} ${echapperHtml(c.prenom)}</strong><br/><small>${echapperHtml(c.email || "")}</small></td>
          <td>${echapperHtml(c.numero_passeport || "Non renseigné")}</td>
          <td>${echapperHtml(c.programme_vise || "-")}<br/><small>${echapperHtml(c.etablissement_vise || "-")}</small></td>
          <td><span class="badge ${c.consentement_signe ? 'badge-ok' : 'badge-warn'}">${c.consentement_signe ? "Signé (Loi 18-07)" : "À recueillir"}</span></td>
          <td>
            <button class="btn" type="button" data-sel="${c.id}">${estActif ? "Candidat actif" : "Sélectionner"}</button>
            <button class="btn btn-succes" type="button" data-cons="${c.id}">Valider Consentement</button>
          </td>
        `;
        tr.querySelector("[data-sel]").addEventListener("click", () => {
          selectionnerCandidat(c, false);
          chargerCandidats();
        });
        tr.querySelector("[data-cons]").addEventListener("click", async () => {
          const rCons = await appelApi(`/api/v1/candidats/${c.id}/consentement`, {
            method: "POST",
            body: JSON.stringify({ consentement_explicite: true, mode_recueil: "formulaire_signe_bureau" }),
          });
          if (rCons.ok) {
            notifier(`Consentement Loi 18-07 enregistré pour ${c.nom} ${c.prenom}.`, true);
            await chargerCandidats();
          }
        });
        tbody.appendChild(tr);
      });
    }

    function selectionnerCandidat(c, silencieux = false) {
      candidatActifId = c.id;
      candidatActifObj = c;
      dictionnaireCandidats[c.id] = c;
      document.getElementById("bandeau-candidat-actif").textContent =
        `${c.nom} ${c.prenom} (Passeport : ${c.numero_passeport || "non renseigné"})`;
      if (!silencieux) {
        notifier(`Dossier actif sélectionné : ${c.nom} ${c.prenom}`, true);
      }
    }

    function libelleCandidatParId(candId) {
      const c = dictionnaireCandidats[candId];
      if (!c) return "Candidat sélectionné";
      return `${c.nom} ${c.prenom} (Passeport : ${c.numero_passeport || "non renseigné"})`;
    }

    document.getElementById("btn-rechercher-candidat").addEventListener("click", chargerCandidats);

    document.getElementById("btn-creer-candidat").addEventListener("click", async () => {
      const payload = {
        nom: document.getElementById("cand-nom").value.trim(),
        prenom: document.getElementById("cand-prenom").value.trim(),
        sexe: document.getElementById("cand-sexe").value || null,
        date_naissance: document.getElementById("cand-dn").value || null,
        lieu_naissance: document.getElementById("cand-lieu").value.trim() || null,
        nationalite: document.getElementById("cand-nat").value.trim() || null,
        pays_residence: document.getElementById("cand-pays").value.trim() || null,
        email: document.getElementById("cand-email").value.trim() || null,
        telephone: document.getElementById("cand-tel").value.trim() || null,
        numero_passeport: document.getElementById("cand-pass").value.trim() || null,
        date_expiration_passeport: document.getElementById("cand-exp-pass").value || null,
        niveau_actuel: document.getElementById("cand-niveau").value.trim() || null,
        programme_vise: document.getElementById("cand-prog").value.trim() || null,
        etablissement_vise: document.getElementById("cand-etab").value.trim() || null,
        fonds_disponibles_eur: document.getElementById("cand-fonds").value
          ? parseInt(document.getElementById("cand-fonds").value, 10)
          : null,
      };
      const rep = await appelApi("/api/v1/candidats", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (rep.ok) {
        const c = await rep.json();
        selectionnerCandidat(c, false);
        await chargerCandidats();
        await rafraichirTableauDeBord();
        notifier(`Fiche candidat ${c.nom} ${c.prenom} créée et chiffrée avec succès.`, true);
      } else {
        const err = await rep.json();
        notifier(err.detail || "Erreur lors de la création du candidat", false);
      }
    });

    // -----------------------------------------------------------------------
    // Onglet 3 : Documents & Pièces manquantes (ZÉRO CODE / ZÉRO JSON)
    // -----------------------------------------------------------------------

    async function chargerDocumentsCandidat() {
      if (!candidatActifId) return;
      const rep = await appelApi(`/api/v1/candidats/${candidatActifId}/documents`);
      if (!rep.ok) return;
      const docs = await rep.json();
      const tbody = document.querySelector("#table-documents-candidat tbody");
      tbody.innerHTML = "";
      if (docs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5">Aucune pièce déposée pour ce candidat. Téléversez un fichier ci-dessus ou cliquez sur « Générer les pièces spécimens de démonstration ».</td></tr>`;
        return;
      }
      docs.forEach((d) => {
        const libellePiece = LIBELLES_PIECES_FR[d.type_piece] || d.type_piece;
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><strong>${echapperHtml(libellePiece)}</strong></td>
          <td>${echapperHtml(d.nom_fichier_origine)}</td>
          <td>${echapperHtml(d.date_expiration || "Non requise")}</td>
          <td>${Math.max(1, Math.round(d.taille_octets / 1024))} Ko</td>
          <td>
            <a href="/api/v1/candidats/${candidatActifId}/documents/${d.id}/telecharger" target="_blank"><button class="btn btn-contour" type="button">Télécharger</button></a>
            <button class="btn btn-danger" type="button" data-suppr="${d.id}">Supprimer</button>
          </td>
        `;
        tr.querySelector("[data-suppr]").addEventListener("click", async () => {
          const rDel = await appelApi(`/api/v1/candidats/${candidatActifId}/documents/${d.id}`, { method: "DELETE" });
          if (rDel.ok) {
            notifier("Pièce supprimée du dossier.", true);
            await chargerDocumentsCandidat();
            await verifierCompletudeDossier();
          }
        });
        tbody.appendChild(tr);
      });
    }

    function formaterCarteCompletude(comp) {
      if (!comp || !comp.pieces) return "";
      const piecesManquantes = comp.pieces.filter((p) => p.statut !== "valide" && p.obligatoire);
      const piecesFacultativesManquantes = comp.pieces.filter((p) => p.statut !== "valide" && !p.obligatoire);
      const piecesValides = comp.pieces.filter((p) => p.statut === "valide");
      const champsManquants = (comp.champs_candidat_manquants || []).map((ch) => LIBELLES_CHAMPS_FR[ch] || ch);

      let html = `<div class="carte" style="margin-bottom:0;">`;
      html += `<div style="display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:10px;">
        <h4 style="margin:0; font-size:1.02rem;">${echapperHtml(comp.libelle_demarche)}</h4>
        <span class="badge ${comp.pret_pour_prerequis ? 'badge-ok' : 'badge-err'}">
          ${comp.pret_pour_prerequis ? "Dossier complet" : "Pièces manquantes"}
        </span>
      </div>`;

      if (piecesManquantes.length === 0 && champsManquants.length === 0) {
        html += `<div class="notif notif-ok" style="margin-bottom:10px;">Toutes les pièces justificatives obligatoires et les informations du candidat sont complètes et valides.</div>`;
      } else {
        if (piecesManquantes.length > 0) {
          html += `<p style="margin:6px 0 4px 0; color:var(--rouge-danger); font-weight:700;">Pièces obligatoires manquantes ou à corriger (${piecesManquantes.length}) :</p><ul class="liste-propre">`;
          piecesManquantes.forEach((p) => {
            let precision = "";
            if (p.statut === "expiree") precision = " — Document expiré";
            else if (p.statut === "validite_insuffisante") precision = " — " + (p.detail || "Validité restante insuffisante");
            else if (p.statut === "expiration_non_renseignee") precision = " — Date d'expiration à renseigner";
            html += `<li><strong>${echapperHtml(p.libelle)}</strong>${echapperHtml(precision)}</li>`;
          });
          html += `</ul>`;
        }
        if (champsManquants.length > 0) {
          html += `<p style="margin:6px 0 4px 0; color:var(--orange-alerte); font-weight:700;">Informations à compléter dans la fiche candidat :</p><ul class="liste-propre">`;
          champsManquants.forEach((lib) => {
            html += `<li>${echapperHtml(lib)}</li>`;
          });
          html += `</ul>`;
        }
      }

      if (piecesValides.length > 0) {
        html += `<p style="margin:8px 0 4px 0; color:var(--vert-succes); font-weight:700;">Pièces déjà déposées et valides (${piecesValides.length}) :</p><ul class="liste-propre">`;
        piecesValides.forEach((p) => {
          const expTxt = p.date_expiration ? ` (valide jusqu'au ${p.date_expiration})` : "";
          html += `<li>✓ ${echapperHtml(p.libelle)}${echapperHtml(expTxt)}</li>`;
        });
        html += `</ul>`;
      }

      if (piecesFacultativesManquantes.length > 0) {
        html += `<p style="margin:8px 0 4px 0; color:var(--texte-secondaire); font-weight:600;">Pièces complémentaires recommandées (facultatives) :</p><ul class="liste-propre">`;
        piecesFacultativesManquantes.forEach((p) => {
          html += `<li>${echapperHtml(p.libelle)}</li>`;
        });
        html += `</ul>`;
      }

      html += `</div>`;
      return html;
    }

    async function verifierCompletudeDossier() {
      if (!candidatActifId) return notifier("Sélectionnez d'abord un candidat dans l'onglet 2.", false);
      const [rCf, rIrcc] = await Promise.all([
        appelApi(`/api/v1/candidats/${candidatActifId}/completude/campus_france`),
        appelApi(`/api/v1/candidats/${candidatActifId}/completude/ircc_permis_etudes`),
      ]);
      const cf = rCf.ok ? await rCf.json() : null;
      const ircc = rIrcc.ok ? await rIrcc.json() : null;
      const zone = document.getElementById("zone-completude");
      zone.innerHTML = `<div class="grille-2">${formaterCarteCompletude(cf)}${formaterCarteCompletude(ircc)}</div>`;
    }

    document.getElementById("btn-televerser-doc").addEventListener("click", async () => {
      if (!candidatActifId) return notifier("Sélectionnez d'abord un candidat dans l'onglet 2.", false);
      const fichierInput = document.getElementById("doc-fichier");
      if (!fichierInput.files.length) return notifier("Choisissez un fichier PDF, PNG ou JPEG à téléverser.", false);
      const typePiece = document.getElementById("doc-type-piece").value;
      const fd = new FormData();
      fd.append("type_piece", typePiece);
      const exp = document.getElementById("doc-expiration").value;
      if (exp) fd.append("date_expiration", exp);
      fd.append("fichier", fichierInput.files[0]);
      const rep = await appelApi(`/api/v1/candidats/${candidatActifId}/documents`, {
        method: "POST",
        body: fd,
      });
      if (rep.ok) {
        const doc = await rep.json();
        const libellePiece = LIBELLES_PIECES_FR[doc.type_piece] || doc.type_piece;
        notifier(`Pièce « ${libellePiece} » chiffrée et enregistrée avec succès.`, true);
        await chargerDocumentsCandidat();
        await verifierCompletudeDossier();
      } else {
        const err = await rep.json();
        notifier(err.detail || "Refus lors du téléversement", false);
      }
    });

    document.getElementById("btn-verifier-completude").addEventListener("click", verifierCompletudeDossier);

    document.getElementById("btn-specimens-demo").addEventListener("click", async () => {
      if (!candidatActifId) return notifier("Sélectionnez d'abord un candidat dans l'onglet 2.", false);
      const rep = await appelApi(`/api/v1/candidats/${candidatActifId}/documents/specimens-demo`, {
        method: "POST",
      });
      if (rep.ok) {
        const crees = await rep.json();
        notifier(
          crees.length > 0
            ? `${crees.length} pièce(s) justificative(s) spécimen(s) générée(s) et chiffrée(s) pour ce candidat.`
            : "Toutes les pièces justificatives sont déjà présentes dans ce dossier.",
          true
        );
        await chargerDocumentsCandidat();
        await verifierCompletudeDossier();
      }
    });

    // -----------------------------------------------------------------------
    // Onglet 4 : Score d'acceptation & Discussion Conseiller (ZÉRO CODE)
    // -----------------------------------------------------------------------

    function afficherEvaluationEnTexte(data) {
      const score = data.pourcentage_acceptation_estime ?? 0;
      const libelleNiveau = LIBELLES_SOLIDITE_FR[data.niveau_solidite] || data.niveau_solidite;
      const couleurBarre = score >= 75 ? "#15803d" : score >= 50 ? "#d97706" : "#b91c1c";

      let html = `
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:10px;">
          <div>
            <h4 style="margin:0; font-size:1.1rem;">${echapperHtml(data.libelle_demarche)}</h4>
            <div style="color:var(--texte-secondaire); font-size:0.9rem; margin-top:2px;">
              Niveau du dossier : <strong>${echapperHtml(libelleNiveau)}</strong>
            </div>
          </div>
          <div style="text-align:right;">
            <span style="font-size:2rem; font-weight:800; color:${couleurBarre};">${score} %</span>
            <div style="font-size:0.8rem; color:var(--texte-secondaire);">Score d'acceptation estimé</div>
          </div>
        </div>
        <div class="barre-progression">
          <div class="barre-progression-remplie" style="width:${score}%; background:${couleurBarre};"></div>
        </div>
        <div class="banniere-regle" style="margin-top:12px;">
          <strong>Action prioritaire recommandée :</strong> ${echapperHtml(data.meilleure_action_recommandee)}
        </div>
      `;

      if (data.criteres && data.criteres.length > 0) {
        html += `<h4 style="margin:14px 0 8px 0;">Détail du calcul sur 100 points :</h4><ul class="liste-propre">`;
        data.criteres.forEach((c) => {
          html += `<li><strong>${echapperHtml(c.libelle)} : ${c.points_obtenus} / ${c.points_max} points</strong> — ${echapperHtml(c.commentaire)}</li>`;
        });
        html += `</ul>`;
      }

      if (data.risques_et_blocages && data.risques_et_blocages.length > 0) {
        html += `<h4 style="margin:14px 0 6px 0; color:var(--rouge-danger);">Points bloquants ou pièces manquantes à corriger :</h4><ul class="liste-propre">`;
        data.risques_et_blocages.forEach((r) => {
          html += `<li>${echapperHtml(r)}</li>`;
        });
        html += `</ul>`;
      }

      if (data.points_forts && data.points_forts.length > 0) {
        html += `<h4 style="margin:14px 0 6px 0; color:var(--vert-succes);">Points forts du dossier :</h4><ul class="liste-propre">`;
        data.points_forts.forEach((pf) => {
          html += `<li>✓ ${echapperHtml(pf)}</li>`;
        });
        html += `</ul>`;
      }

      if (data.actions_prioritaires && data.actions_prioritaires.length > 0) {
        html += `<h4 style="margin:14px 0 6px 0;">Plan d'action recommandé :</h4><ol class="liste-propre">`;
        data.actions_prioritaires.forEach((act) => {
          html += `<li>${echapperHtml(act)}</li>`;
        });
        html += `</ol>`;
      }

      if (data.veille_reglementaire && data.veille_reglementaire.length > 0) {
        html += `<h4 style="margin:14px 0 6px 0;">Règles officielles et prérequis applicables :</h4><ul class="liste-propre">`;
        data.veille_reglementaire.forEach((v) => {
          html += `<li><strong>${echapperHtml(v.titre)}</strong> (${echapperHtml(v.reference)}) : ${echapperHtml(v.resume)}</li>`;
        });
        html += `</ul>`;
      }

      html += `<p style="font-size:0.82rem; color:var(--texte-secondaire); margin-top:12px; margin-bottom:0;"><em>${echapperHtml(data.avertissement)}</em></p>`;
      document.getElementById("zone-score-acceptation").innerHTML = html;
    }

    document.getElementById("btn-calculer-score").addEventListener("click", async () => {
      if (!candidatActifId) return notifier("Sélectionnez d'abord un candidat dans l'onglet 2.", false);
      const dem = document.getElementById("eval-demarche").value;
      const rep = await appelApi(`/api/v1/candidats/${candidatActifId}/evaluation/${dem}`);
      if (rep.ok) {
        const data = await rep.json();
        afficherEvaluationEnTexte(data);
        const libelleNiveau = LIBELLES_SOLIDITE_FR[data.niveau_solidite] || data.niveau_solidite;
        notifier(`Score d'acceptation calculé : ${data.pourcentage_acceptation_estime} % (${libelleNiveau})`, true);
      } else {
        const err = await rep.json();
        notifier(err.detail || "Impossible de calculer le score", false);
      }
    });

    function formaterMessageDiscussionHtml(texteBrut) {
      const lignes = String(texteBrut || "").split("\\n");
      return lignes
        .map((l) => echapperHtml(l.replace(/^#+\\s*/, "").replace(/\\*\\*/g, "").replace(/`/g, "")))
        .join("<br/>");
    }

    function afficherListeMessagesDiscussion(messages) {
      const fil = document.getElementById("fil-discussion");
      if (!messages || messages.length === 0) {
        fil.innerHTML = `<div style="color:var(--texte-secondaire); font-size:0.9rem;">Aucun message dans cette discussion. Posez votre première question ci-dessous.</div>`;
        return;
      }
      fil.innerHTML = "";
      messages.forEach((m) => {
        const estUtilisateur = m.auteur === "utilisateur" || m.auteur === "operateur";
        const texteMsg = m.contenu || m.message || "";
        const scoreMsg = m.score_solidite_pourcent ?? m.score_instantane ?? "-";
        const div = document.createElement("div");
        div.className = "msg " + (estUtilisateur ? "msg-op" : "msg-ia");
        div.innerHTML =
          `<div style="margin-bottom:4px;"><strong>${estUtilisateur ? "Vous (Opérateur du bureau)" : "Assistant Conseiller Réglementaire"}</strong> ` +
          `<span class="badge">${scoreMsg} % d'acceptation</span></div>` +
          `<div>${formaterMessageDiscussionHtml(texteMsg)}</div>`;
        fil.appendChild(div);
      });
      fil.scrollTop = fil.scrollHeight;
    }

    async function chargerHistoriqueDiscussion() {
      if (!candidatActifId) return;
      const code_demarche = document.getElementById("eval-demarche").value;
      const rHisto = await appelApi(
        `/api/v1/candidats/${candidatActifId}/discussion?code_demarche=${encodeURIComponent(code_demarche)}`
      );
      if (rHisto.ok) {
        const messages = await rHisto.json();
        afficherListeMessagesDiscussion(messages);
      }
    }

    async function envoyerQuestionConseiller() {
      if (!candidatActifId) return notifier("Sélectionnez d'abord un candidat dans l'onglet 2.", false);
      const champMsg = document.getElementById("msg-discussion");
      const message = champMsg.value.trim();
      const code_demarche = document.getElementById("eval-demarche").value;
      if (message.length < 2) {
        return notifier("Veuillez saisir une question d'au moins 2 caractères.", false);
      }
      const btn = document.getElementById("btn-envoyer-discussion");
      btn.disabled = true;
      btn.textContent = "Analyse en cours...";
      try {
        const rep = await appelApi(`/api/v1/candidats/${candidatActifId}/discussion`, {
          method: "POST",
          body: JSON.stringify({ code_demarche, message }),
        });
        if (rep.ok) {
          const echange = await rep.json();
          if (echange.evaluation) {
            afficherEvaluationEnTexte(echange.evaluation);
          }
          await chargerHistoriqueDiscussion();
          notifier("Réponse du Conseiller ajoutée à la discussion.", true);
        } else {
          const err = await rep.json();
          notifier(err.detail || "Erreur lors de l'envoi de la question au Conseiller.", false);
        }
      } finally {
        btn.disabled = false;
        btn.textContent = "Envoyer au Conseiller";
      }
    }

    function poserQuestionRapide(texte) {
      document.getElementById("msg-discussion").value = texte;
      envoyerQuestionConseiller();
    }

    document.getElementById("btn-envoyer-discussion").addEventListener("click", envoyerQuestionConseiller);
    document.getElementById("eval-demarche").addEventListener("change", chargerHistoriqueDiscussion);

    // -----------------------------------------------------------------------
    // Onglets 5 & 6 : Campus France & IRCC — Pilotage Navigateur & Tâches
    // -----------------------------------------------------------------------

    function formaterCompteRenduPilotageHtml(res) {
      let html = `
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:10px;">
          <div>
            <strong style="font-size:1.05rem;">${echapperHtml(res.titre_page || "Navigateur de l'Agent")}</strong>
            <div style="font-size:0.84rem; color:var(--texte-secondaire);">Adresse ouverte : ${echapperHtml(res.url_courante)}</div>
          </div>
          <span class="badge ${res.succes ? 'badge-ok' : 'badge-warn'}">
            ${res.succes ? "Action exécutée par l'Agent" : "Intervention humaine requise"}
          </span>
        </div>
        <div class="notif ${res.succes ? 'notif-ok' : 'notif-err'}" style="margin-bottom:10px;">
          ${echapperHtml(res.resume_francais)}
        </div>
      `;

      if (res.statut_tache) {
        const libStatut = LIBELLES_STATUT_TACHE_FR[res.statut_tache] || res.statut_tache;
        const classeBadgeStatut = (res.statut_tache === "a_valider" || res.statut_tache === "terminee")
          ? "badge-ok"
          : (res.statut_tache === "suspendue" || res.statut_tache === "en_attente")
            ? "badge-warn"
            : "badge";
        html += `<p style="margin:6px 0;"><strong>Statut du dossier :</strong> <span class="badge ${classeBadgeStatut}">${echapperHtml(libStatut)}</span></p>`;
      }

      if (res.pieces_manquantes_tache && res.pieces_manquantes_tache.length > 0) {
        html += `<div class="banniere-regle" style="margin:8px 0;">
          <strong>Dossier en pause (pièces justificatives à téléverser avant passage au Centre de validation humaine) :</strong>
          <ul class="liste-propre" style="margin:6px 0;">
            ${res.pieces_manquantes_tache.map((tp) => `<li>${echapperHtml(LIBELLES_PIECES_FR[tp] || tp)}</li>`).join("")}
          </ul>
          <button class="btn btn-succes" type="button" onclick="completerPiecesSpecimensEtRelancer('${echapperHtml(res.code_demarche)}')">
            Déposer automatiquement les pièces spécimens de démo et lancer le pré-remplissage complet
          </button>
        </div>`;
      }

      if (res.etapes_realisees && res.etapes_realisees.length > 0) {
        html += `<p style="margin:8px 0 4px 0; font-weight:700;">Actions réalisées dans le navigateur :</p><ul class="liste-propre">`;
        res.etapes_realisees.forEach((et) => {
          html += `<li>✓ ${echapperHtml(et)}</li>`;
        });
        html += `</ul>`;
      }

      if (res.champs_remplis_libelles && res.champs_remplis_libelles.length > 0) {
        html += `<p style="margin:8px 0 4px 0; font-weight:700; color:var(--vert-succes);">Champs pré-remplis automatiquement (${res.champs_remplis_libelles.length}) :</p><ul class="liste-propre">`;
        res.champs_remplis_libelles.forEach((ch) => {
          html += `<li>✓ ${echapperHtml(ch)}</li>`;
        });
        html += `</ul>`;
      }

      if (res.pieces_televersees_libelles && res.pieces_televersees_libelles.length > 0) {
        html += `<p style="margin:8px 0 4px 0; font-weight:700; color:var(--vert-succes);">Pièces justificatives téléversées sur la page (${res.pieces_televersees_libelles.length}) :</p><ul class="liste-propre">`;
        res.pieces_televersees_libelles.forEach((p) => {
          html += `<li>✓ ${echapperHtml(p)}</li>`;
        });
        html += `</ul>`;
      }

      if (res.champs_manquants_libelles && res.champs_manquants_libelles.length > 0) {
        html += `<p style="margin:8px 0 4px 0; font-weight:700; color:var(--orange-alerte);">Informations non renseignées dans la fiche candidat (Règle 4 : aucune valeur inventée) :</p><ul class="liste-propre">`;
        res.champs_manquants_libelles.forEach((m) => {
          html += `<li>${echapperHtml(m)}</li>`;
        });
        html += `</ul>`;
      }

      if (res.avertissements_securite && res.avertissements_securite.length > 0) {
        html += `<p style="margin:8px 0 4px 0; font-weight:700;">Garde-fous de sécurité actifs :</p><ul class="liste-propre">`;
        res.avertissements_securite.forEach((av) => {
          html += `<li>${echapperHtml(av)}</li>`;
        });
        html += `</ul>`;
      }

      if (res.capture_base64) {
        html += `
          <div style="margin-top:12px;">
            <strong>Capture d'écran en direct du navigateur piloté par l'agent :</strong><br/>
            <img class="capture-apercu" src="data:image/png;base64,${res.capture_base64}" alt="Capture d'écran du navigateur" />
          </div>
        `;
      }
      return html;
    }

    async function lancerActionNavigateur(codeDemarche, action, instructionLibre = null) {
      if (!candidatActifId) {
        notifier("Sélectionnez d'abord un candidat dans l'onglet 2.", false);
        return;
      }
      const estCf = codeDemarche === "campus_france";
      const cible = document.getElementById(estCf ? "cf-cible-navigateur" : "ircc-cible-navigateur").value;
      const ouvrirVisible = document.getElementById(estCf ? "cf-fenetre-visible" : "ircc-fenetre-visible").checked;
      const zoneId = estCf ? "zone-retour-cf" : "zone-retour-ircc";
      const zone = document.getElementById(zoneId);

      zone.innerHTML = `<div style="font-weight:600; color:var(--bleu-primaire);">L'Agent Navigateur exécute votre demande dans Chromium... Veuillez patienter quelques secondes.</div>`;

      const rep = await appelApi("/api/v1/portails/piloter-navigateur", {
        method: "POST",
        body: JSON.stringify({
          candidat_id: candidatActifId,
          code_demarche: codeDemarche,
          cible: cible,
          action: action,
          instruction_libre: instructionLibre,
          ouvrir_fenetre_visible: ouvrirVisible,
          synchroniser_tache: true,
        }),
      });

      if (rep.ok) {
        const res = await rep.json();
        zone.innerHTML = formaterCompteRenduPilotageHtml(res);
        await rafraichirTableauDeBord();
        notifier(res.resume_francais, res.succes);
      } else {
        const err = await rep.json();
        zone.innerHTML = `<div class="notif notif-err">${echapperHtml(err.detail || "Erreur lors du pilotage du navigateur.")}</div>`;
        notifier(err.detail || "Erreur lors du pilotage du navigateur", false);
      }
    }

    document.getElementById("btn-piloter-cf-instruction").addEventListener("click", () => {
      const inst = document.getElementById("cf-instruction-agent").value.trim();
      lancerActionNavigateur("campus_france", "instruction_libre", inst);
    });

    document.getElementById("btn-piloter-ircc-instruction").addEventListener("click", () => {
      const inst = document.getElementById("ircc-instruction-agent").value.trim();
      lancerActionNavigateur("ircc_permis_etudes", "instruction_libre", inst);
    });

    function formaterTacheEnTexteHtml(tache, codeDemarche) {
      const libStatut = LIBELLES_STATUT_TACHE_FR[tache.statut] || tache.statut;
      const estSuspendue = tache.statut === "suspendue";
      const estAValider = tache.statut === "a_valider";

      let html = `
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:10px;">
          <div>
            <strong>Suivi de la tâche ${codeDemarche === "campus_france" ? "Campus France — Études en France" : "IRCC Canada — Permis d'études"}</strong>
          </div>
          <span class="badge ${estAValider ? 'badge-ok' : estSuspendue ? 'badge-warn' : 'badge'}">${echapperHtml(libStatut)}</span>
        </div>
      `;

      if (tache.message_alerte) {
        html += `<div class="banniere-regle">${echapperHtml(tache.message_alerte)}</div>`;
      }

      if (tache.pieces_manquantes && tache.pieces_manquantes.length > 0) {
        html += `<p style="margin:6px 0; color:var(--rouge-danger); font-weight:700;">Pièces justificatives obligatoires à fournir avant l'envoi officiel :</p><ul class="liste-propre">`;
        tache.pieces_manquantes.forEach((tp) => {
          html += `<li>${echapperHtml(LIBELLES_PIECES_FR[tp] || tp)}</li>`;
        });
        html += `</ul>`;
        html += `<p><button class="btn btn-succes" type="button" onclick="completerPiecesSpecimensEtRelancer('${codeDemarche}')">Déposer automatiquement les pièces spécimens de démo et lancer le pré-remplissage par l'Agent</button></p>`;
      }

      if (tache.champs_manquants && tache.champs_manquants.length > 0) {
        html += `<p style="margin:6px 0; color:var(--orange-alerte); font-weight:700;">Informations à compléter dans la fiche candidat :</p><ul class="liste-propre">`;
        tache.champs_manquants.forEach((ch) => {
          html += `<li>${echapperHtml(LIBELLES_CHAMPS_FR[ch] || ch)}</li>`;
        });
        html += `</ul>`;
      }

      if (tache.etapes && tache.etapes.length > 0) {
        html += `<p style="margin:10px 0 4px 0; font-weight:700;">Progression des étapes de la démarche :</p><ol class="liste-propre">`;
        tache.etapes.forEach((e) => {
          const icone = e.statut === "terminee" ? "✓" : e.statut === "en_cours" ? "⏳" : e.statut === "suspendue" ? "⏸" : "•";
          const stTxt = e.statut === "terminee" ? "Terminée" : e.statut === "en_cours" ? "En cours" : e.statut === "suspendue" ? "En attente de complétion" : "À faire";
          html += `<li>${icone} <strong>${echapperHtml(e.libelle)}</strong> — <em>${stTxt}</em></li>`;
        });
        html += `</ol>`;
      }

      return html;
    }

    async function completerPiecesSpecimensEtRelancer(codeDemarche) {
      if (!candidatActifId) return;
      await appelApi(`/api/v1/candidats/${candidatActifId}/documents/specimens-demo?code_demarche=${encodeURIComponent(codeDemarche)}`, {
        method: "POST",
      });
      await lancerActionNavigateur(codeDemarche, "preremplissage_complet");
    }

    async function creerOuAfficherTacheDemarche(codeDemarche) {
      if (!candidatActifId) return notifier("Sélectionnez d'abord un candidat dans l'onglet 2.", false);
      const zoneId = codeDemarche === "campus_france" ? "zone-retour-cf" : "zone-retour-ircc";
      const rep = await appelApi("/api/v1/taches", {
        method: "POST",
        body: JSON.stringify({ candidat_id: candidatActifId, code_demarche: codeDemarche }),
      });
      if (rep.ok) {
        const tache = await rep.json();
        document.getElementById(zoneId).innerHTML = formaterTacheEnTexteHtml(tache, codeDemarche);
        await rafraichirTableauDeBord();
        const libStatut = LIBELLES_STATUT_TACHE_FR[tache.statut] || tache.statut;
        notifier(`Tâche créée : ${libStatut}`, true);
      } else {
        // Si une tâche est déjà ouverte pour ce candidat, on la récupère et on l'affiche clairement
        const rListe = await appelApi(`/api/v1/taches?candidat_id=${candidatActifId}&code_demarche=${codeDemarche}`);
        if (rListe.ok) {
          const pageTaches = await rListe.json();
          if (pageTaches.elements && pageTaches.elements.length > 0) {
            const tacheExistante = pageTaches.elements[0];
            document.getElementById(zoneId).innerHTML = formaterTacheEnTexteHtml(tacheExistante, codeDemarche);
            notifier("Affichage de la tâche en cours pour ce candidat.", true);
            return;
          }
        }
        const err = await rep.json();
        notifier(err.detail || "Impossible de créer la tâche", false);
      }
    }

    document.getElementById("btn-creer-tache-cf").addEventListener("click", () => creerOuAfficherTacheDemarche("campus_france"));
    document.getElementById("btn-creer-tache-ircc").addEventListener("click", () => creerOuAfficherTacheDemarche("ircc_permis_etudes"));

    // -----------------------------------------------------------------------
    // Onglet 7 : Centre de validation humaine (Règle 1 — Cartes interactives)
    // -----------------------------------------------------------------------

    function formaterRecapitulatifValidationHtml(recap) {
      if (!recap || typeof recap !== "object") return "";
      let bloc = `<div class="panneau-texte" style="margin:8px 0;">`;
      if (recap.url_courante) {
        bloc += `<div style="font-size:0.86rem; color:var(--texte-secondaire); margin-bottom:6px;"><strong>Portail contrôlé :</strong> ${echapperHtml(recap.url_courante)}</div>`;
      }
      if (recap.champs_remplis && recap.champs_remplis.length > 0) {
        bloc += `<div style="margin:4px 0;"><strong style="color:var(--vert-succes);">Champs pré-remplis vérifiés (${recap.champs_remplis.length}) :</strong> ${recap.champs_remplis.map((c) => echapperHtml(c)).join(" • ")}</div>`;
      }
      if (recap.pieces_televersees && recap.pieces_televersees.length > 0) {
        bloc += `<div style="margin:4px 0;"><strong style="color:var(--vert-succes);">Pièces téléversées (${recap.pieces_televersees.length}) :</strong> ${recap.pieces_televersees.map((p) => echapperHtml(p)).join(" • ")}</div>`;
      }
      bloc += `</div>`;
      return bloc;
    }

    async function rafraichirValidationsHumaines() {
      if (Object.keys(dictionnaireCandidats).length === 0) {
        await chargerCandidats();
      }
      const rep = await appelApi("/api/v1/validations/en-attente");
      if (!rep.ok) return;
      const data = await rep.json();
      const zone = document.getElementById("liste-centre-validation");

      if (data.total_a_valider === 0 && data.total_suspendues === 0) {
        zone.innerHTML = `<div class="notif notif-ok" style="margin:0;">Aucun dossier en attente de validation ni en pause pour le moment.</div>`;
        return;
      }

      let html = "";

      if (data.taches_a_valider && data.taches_a_valider.length > 0) {
        html += `<h3 style="margin-top:0; color:var(--vert-succes);">Dossiers pré-remplis prêts pour validation humaine (${data.total_a_valider})</h3>`;
        data.taches_a_valider.forEach((t) => {
          const nomDem = t.code_demarche === "campus_france" ? "Campus France — Études en France" : "IRCC Canada — Permis d'études";
          const nomCand = libelleCandidatParId(t.candidat_id);
          html += `
            <div class="carte">
              <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                <div>
                  <strong>${echapperHtml(nomDem)}</strong>
                  <div style="font-size:0.86rem; color:var(--texte-secondaire);">Candidat : ${echapperHtml(nomCand)}</div>
                </div>
                <span class="badge badge-ok">En attente de validation humaine (Règle 1)</span>
              </div>
              <p style="margin:8px 0;">${echapperHtml(t.message_alerte || "Pré-remplissage terminé et arrêté avant le bouton final.")}</p>
              ${formaterRecapitulatifValidationHtml(t.recapitulatif_remplissage)}
              ${t.capture_controle_disponible ? `
                <div style="margin:10px 0;">
                  <div style="margin-bottom:6px;">
                    <a href="/api/v1/taches/${t.id}/capture-controle" target="_blank"><button class="btn btn-contour" type="button">Voir la capture d'écran de contrôle en plein écran</button></a>
                  </div>
                  <img class="capture-apercu" src="/api/v1/taches/${t.id}/capture-controle" alt="Capture d'écran de contrôle avant soumission" />
                </div>
              ` : ""}
              <div style="display:flex; gap:8px; flex-wrap:wrap; margin-top:8px;">
                <button class="btn btn-succes" type="button" onclick="validerDossierHumainement('${t.id}')">Confirmer et valider humainement ce dossier (Règle 1)</button>
                <button class="btn" type="button" onclick="rejeterValidationHumaine('${t.id}')">Demander une correction avant validation</button>
                <button class="btn btn-danger" type="button" onclick="annulerTacheDossier('${t.id}')">Annuler la tâche</button>
              </div>
            </div>
          `;
        });
      }

      if (data.taches_suspendues && data.taches_suspendues.length > 0) {
        html += `<h3 style="margin-top:14px; color:var(--orange-alerte);">Dossiers en pause (${data.total_suspendues})</h3>`;
        data.taches_suspendues.forEach((t) => {
          const nomDem = t.code_demarche === "campus_france" ? "Campus France — Études en France" : "IRCC Canada — Permis d'études";
          const nomCand = libelleCandidatParId(t.candidat_id);
          const piecesTxt = (t.pieces_manquantes || []).map((p) => LIBELLES_PIECES_FR[p] || p).join(", ");
          html += `
            <div class="carte">
              <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                <div>
                  <strong>${echapperHtml(nomDem)}</strong>
                  <div style="font-size:0.86rem; color:var(--texte-secondaire);">Candidat : ${echapperHtml(nomCand)}</div>
                </div>
                <span class="badge badge-warn">En pause</span>
              </div>
              <p style="margin:8px 0;">${echapperHtml(t.message_alerte || "")}</p>
              ${piecesTxt ? `<p style="margin:4px 0; color:var(--rouge-danger);"><strong>Pièces manquantes :</strong> ${echapperHtml(piecesTxt)}</p>` : ""}
              <div style="display:flex; gap:8px; flex-wrap:wrap; margin-top:8px;">
                ${piecesTxt ? `<button class="btn btn-succes" type="button" onclick="completerPiecesEtRelancerDepuisValidation('${t.id}', '${t.candidat_id}', '${t.code_demarche}')">Déposer les pièces spécimens de démo &amp; Pré-remplir par l'Agent</button>` : ""}
                <button class="btn" type="button" onclick="reprendreTacheDossier('${t.id}')">Reprendre la tâche</button>
                <button class="btn btn-danger" type="button" onclick="annulerTacheDossier('${t.id}')">Annuler la tâche</button>
              </div>
            </div>
          `;
        });
      }

      zone.innerHTML = html;
    }

    async function validerDossierHumainement(tacheId) {
      const rep = await appelApi(`/api/v1/taches/${tacheId}/valider`, {
        method: "POST",
        body: JSON.stringify({
          confirmation_humaine_explicite: true,
          commentaire: "Vérifié et validé par l'opérateur humain au Centre de validation.",
        }),
      });
      if (rep.ok) {
        notifier("Dossier validé humainement avec succès (Règle 1).", true);
        await rafraichirValidationsHumaines();
        await rafraichirTableauDeBord();
      } else {
        const err = await rep.json();
        notifier(err.detail || "Erreur lors de la validation", false);
      }
    }

    async function rejeterValidationHumaine(tacheId) {
      const rep = await appelApi(`/api/v1/taches/${tacheId}/rejeter`, {
        method: "POST",
        body: JSON.stringify({
          motif_rejet: "Correction demandée par l'opérateur humain avant la soumission finale.",
        }),
      });
      if (rep.ok) {
        notifier("Dossier remis en pause pour correction avant validation finale.", true);
        await rafraichirValidationsHumaines();
        await rafraichirTableauDeBord();
      } else {
        const err = await rep.json();
        notifier(err.detail || "Erreur lors du renvoi en correction", false);
      }
    }

    async function completerPiecesEtRelancerDepuisValidation(tacheId, candId, codeDemarche) {
      await appelApi(`/api/v1/candidats/${candId}/documents/specimens-demo?code_demarche=${encodeURIComponent(codeDemarche)}`, {
        method: "POST",
      });
      await appelApi(`/api/v1/portails/piloter-navigateur`, {
        method: "POST",
        body: JSON.stringify({
          candidat_id: candId,
          code_demarche: codeDemarche,
          cible: codeDemarche === "campus_france" ? "demo_campus_france" : "demo_ircc",
          action: "preremplissage_complet",
          ouvrir_fenetre_visible: false,
          synchroniser_tache: true,
        }),
      });
      notifier("Pièces spécimens déposées et dossier pré-rempli par l'Agent — prêt pour validation humaine !", true);
      await rafraichirValidationsHumaines();
      await rafraichirTableauDeBord();
    }

    async function reprendreTacheDossier(tacheId) {
      const rep = await appelApi(`/api/v1/taches/${tacheId}/reprendre`, { method: "POST" });
      if (rep.ok) {
        notifier("Tâche remise en file d'attente.", true);
        await rafraichirValidationsHumaines();
        await rafraichirTableauDeBord();
      } else {
        const err = await rep.json();
        notifier(err.detail || "Complétez d'abord les pièces manquantes avant de reprendre la tâche.", false);
      }
    }

    async function annulerTacheDossier(tacheId) {
      const rep = await appelApi(`/api/v1/taches/${tacheId}/annuler`, { method: "POST" });
      if (rep.ok) {
        notifier("Tâche annulée.", true);
        await rafraichirValidationsHumaines();
        await rafraichirTableauDeBord();
      }
    }

    document.getElementById("btn-rafraichir-validations").addEventListener("click", rafraichirValidationsHumaines);

    // -----------------------------------------------------------------------
    // Onglet 8 : Historique d'audit (ZÉRO CODE BRUT)
    // -----------------------------------------------------------------------

    async function rafraichirJournalAudit() {
      const rep = await appelApi("/api/v1/audit?taille=30");
      if (!rep.ok) return;
      const data = await rep.json();
      const tbody = document.querySelector("#table-audit tbody");
      tbody.innerHTML = "";
      data.elements.forEach((e) => {
        const detailsObj = e.details || {};
        const resumeDetails = Object.entries(detailsObj)
          .map(([k, v]) => `${k.replace(/_/g, " ")} : ${v}`)
          .join(" | ") || "Opération standard";
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><small>${echapperHtml(e.horodatage)}</small></td>
          <td><strong>${echapperHtml(e.action)}</strong></td>
          <td><span class="badge ${e.resultat === 'succes' ? 'badge-ok' : 'badge-err'}">${echapperHtml(e.resultat)}</span></td>
          <td>${echapperHtml(e.ressource_type || "-")}</td>
          <td>${echapperHtml(resumeDetails)}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    document.getElementById("btn-rafraichir-audit").addEventListener("click", rafraichirJournalAudit);

    // -----------------------------------------------------------------------
    // Onglet 9 : Paramètres, Agents locaux & Sauvegardes (ZÉRO CODE BRUT)
    // -----------------------------------------------------------------------

    document.getElementById("btn-enroler-agent").addEventListener("click", async () => {
      const nom_machine = document.getElementById("nom-machine-agent").value.trim();
      const rep = await appelApi("/api/v1/agents-locaux", {
        method: "POST",
        body: JSON.stringify({ nom_machine }),
      });
      if (rep.ok) {
        const data = await rep.json();
        const zone = document.getElementById("zone-jeton-agent");
        zone.innerHTML = `
          <div class="notif notif-ok" style="margin-bottom:8px;">Poste Agent Local « ${echapperHtml(data.agent.nom_machine)} » enrôlé avec succès.</div>
          <p style="margin:4px 0;"><strong>Clé d'authentification de l'Agent Local (à conserver précieusement) :</strong><br/>
          <input type="text" readonly value="${echapperHtml(data.jeton_secret)}" style="width:100%; margin-top:4px; font-weight:600;" /></p>
        `;
        zone.classList.remove("cache");
        await rafraichirTableauDeBord();
        notifier("Poste Agent Local enrôlé avec succès.", true);
      }
    });

    document.getElementById("btn-creer-sauvegarde").addEventListener("click", async () => {
      const rep = await appelApi("/api/v1/sauvegardes", { method: "POST" });
      const data = await rep.json();
      const zone = document.getElementById("zone-sauvegardes-abo");
      if (rep.ok) {
        zone.innerHTML = `
          <div class="notif notif-ok" style="margin-bottom:8px;">Sauvegarde chiffrée AES-256-GCM créée avec succès.</div>
          <ul class="liste-propre">
            <li><strong>Nom de l'archive chiffrée :</strong> ${echapperHtml(data.nom_fichier)}</li>
            <li><strong>Nombre de dossiers candidats sauvegardés :</strong> ${data.nb_candidats}</li>
            <li><strong>Nombre de pièces justificatives sauvegardées :</strong> ${data.nb_documents}</li>
            <li><strong>Taille de l'archive :</strong> ${Math.max(1, Math.round(data.taille_octets / 1024))} Ko</li>
          </ul>
        `;
        notifier(`Sauvegarde chiffrée créée : ${data.nom_fichier}`, true);
      } else {
        zone.innerHTML = `<div class="notif notif-err">${echapperHtml(data.detail || "Erreur lors de la sauvegarde")}</div>`;
      }
    });

    document.getElementById("btn-voir-abonnement").addEventListener("click", async () => {
      const [rAbo, rPort] = await Promise.all([
        appelApi("/api/v1/abonnement"),
        appelApi("/api/v1/portails"),
      ]);
      const abo = rAbo.ok ? await rAbo.json() : {};
      const portails = rPort.ok ? await rPort.json() : [];
      let html = `
        <h4 style="margin-top:0;">Abonnement SaaS du Bureau</h4>
        <ul class="liste-propre">
          <li><strong>Forfait actif :</strong> ${echapperHtml(abo.forfait || "Starter")}</li>
          <li><strong>Quota mensuel de dossiers :</strong> ${abo.nb_dossiers_actifs ?? 0} / ${abo.quota_dossiers_mensuels ?? 25} dossiers actifs</li>
          <li><strong>Durée de conservation RGPD / Loi 18-07 :</strong> ${abo.duree_conservation_jours ?? 365} jours</li>
        </ul>
        <h4>Statut des modules portails (Règle 6 &amp; Règle 7)</h4>
        <ul class="liste-propre">
      `;
      portails.forEach((p) => {
        html += `<li><strong>${echapperHtml(p.nom_portail)}</strong> — Statut d'homologation : <span class="badge">${echapperHtml(p.statut_test_regle6)}</span> (${p.nb_etapes_automatisation} étapes automatisées)</li>`;
      });
      html += `</ul>`;
      document.getElementById("zone-sauvegardes-abo").innerHTML = html;
    });

    // Connexion automatique dès l'ouverture de l'interface pour une prise en main immédiate
    window.addEventListener("DOMContentLoaded", () => {
      connecterOperateur(true);
    });
  </script>
</body>
</html>"""


@routeur_interface.get("/", response_class=HTMLResponse)
@routeur_interface.get("/interface", response_class=HTMLResponse)
def afficher_interface_francaise() -> HTMLResponse:
    return HTMLResponse(content=HTML_INTERFACE_FR)
