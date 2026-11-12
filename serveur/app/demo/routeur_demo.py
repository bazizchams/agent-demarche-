"""Routeur FastAPI servant les pages de simulation locales complètes :
1. Études en France — Campus France Algérie (conforme au Guide officiel Septembre 2026, 96 pages)
2. Portail IRCC Canada — Demande de permis d'études

Ces pages permettent à la fois :
- d'exécuter de bout en bout tous les tests automatisés Playwright (`config/portails/demo_*.yaml`) ;
- à l'opérateur du bureau de visualiser et tester en conditions réelles l'intégralité des rubriques
  Études en France (Mon compte, Mon espace étudiant, Scolarité & Langues, Panier max 7 formations &
  Motivations 4 000 caractères, Paiements 20 000 DZD / RDV antennes Algérie, Dossier pré-consulaire en 4 étapes)
  et IRCC Canada, avec arrêt strict de l'agent avant le bouton de soumission finale (Règle 1).
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

routeur_demo = APIRouter(prefix="/demo", tags=["pages de démonstration"])


@routeur_demo.get("/eef-reel", response_class=HTMLResponse)
@routeur_demo.get("/eef-reel/{chemin:path}", response_class=HTMLResponse)
def page_maquette_eef_reel(chemin: str = "") -> HTMLResponse:
    """Maquette fidèle du vrai portail Études en France (catalogue / fiche / panier) : tests uniquement."""
    from app.demo.maquette_eef_reel import html_maquette_eef_reel

    return HTMLResponse(content=html_maquette_eef_reel(), headers={"X-Frame-Options": "SAMEORIGIN"})

# Catalogue FICTIF de formations pour la page de démonstration (recherche + panier de vœux).
# Deux entrées « Licence 3 Informatique — Université de Lorraine » sont volontairement identiques
# (campus différents) pour tester la détection de correspondance ambiguë du Co-Pilote.
CATALOGUE_FORMATIONS_DEMO: list[dict[str, str]] = [
    {"id": "f-001", "intitule": "Master 1 Intelligence Artificielle", "etablissement": "Sorbonne Université", "niveau": "Master 1"},
    {"id": "f-002", "intitule": "Master 1 Informatique", "etablissement": "Université Paris-Saclay", "niveau": "Master 1"},
    {"id": "f-003", "intitule": "Master 2 Data Science", "etablissement": "Université de Lyon", "niveau": "Master 2"},
    {"id": "f-004", "intitule": "Licence 3 Informatique", "etablissement": "Université de Lorraine", "niveau": "Licence 3", "campus": "Nancy"},
    {"id": "f-005", "intitule": "Licence 3 Informatique", "etablissement": "Université de Lorraine", "niveau": "Licence 3", "campus": "Metz"},
    {"id": "f-006", "intitule": "Master 1 Informatique", "etablissement": "Université de Lorraine", "niveau": "Master 1"},
    {"id": "f-007", "intitule": "Master 2 Cybersécurité", "etablissement": "Université de Rennes", "niveau": "Master 2"},
    {"id": "f-008", "intitule": "Diplôme d'ingénieur Génie Logiciel", "etablissement": "INSA Lyon", "niveau": "Ingénieur"},
    {"id": "f-009", "intitule": "Master 1 Intelligence Artificielle", "etablissement": "Université Côte d'Azur", "niveau": "Master 1"},
    {"id": "f-010", "intitule": "Master 1 Mathématiques Appliquées", "etablissement": "Université de Bordeaux", "niveau": "Master 1"},
    {"id": "f-011", "intitule": "Master 1 Réseaux et Télécommunications", "etablissement": "Université de Limoges", "niveau": "Master 1"},
    {"id": "f-012", "intitule": "Master 1 Génie Électrique", "etablissement": "Université de Toulouse III", "niveau": "Master 1"},
    {"id": "f-013", "intitule": "Master 1 Management International", "etablissement": "Université de Strasbourg", "niveau": "Master 1"},
    {"id": "f-014", "intitule": "Master 1 Biologie Moléculaire", "etablissement": "Université de Montpellier", "niveau": "Master 1"},
    {"id": "f-015", "intitule": "Master 1 Droit des Affaires", "etablissement": "Université de Lille", "niveau": "Master 1"},
]


@routeur_demo.get("/campus-france", response_class=HTMLResponse)
def page_demo_campus_france(
    session_ouverte: int = Query(default=1),
    captcha: int = Query(default=0),
) -> HTMLResponse:
    banniere_session = (
        '<div id="bandeau-session-connectee" class="ok">'
        "Connecté sur Études en France — Espace Campus France Algérie (Identifiant : <strong>DZ26-00142</strong>) "
        "| Fil d'actualité | Messages (0)"
        "</div>"
        if session_ouverte == 1
        else '<div id="alerte-session-non-connectee" class="alerte">'
        "Session fermée : veuillez vous connecter manuellement au portail Études en France avant de lancer l'agent (Règle 3)."
        "</div>"
    )
    bloc_captcha = (
        '<div id="bloc-captcha-securite" class="alerte">'
        "Contrôle de sécurité CAPTCHA actif : résolution humaine obligatoire dans le navigateur (Règle 2)."
        "</div>"
        if captcha == 1
        else ""
    )

    catalogue_json = json.dumps(CATALOGUE_FORMATIONS_DEMO, ensure_ascii=False).replace("</", "<\\/")

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <title>Études en France — Plateforme des étudiants internationaux (Campus France Algérie — Guide Septembre 2026)</title>
  <style>
    body {{ font-family: Segoe UI, system-ui, Arial, sans-serif; margin: 0; padding: 20px 28px; background: #f1f5f9; color: #0f172a; }}
    header {{ background: linear-gradient(135deg, #002654 0%, #1e3a8a 100%); color: #fff; padding: 18px 24px; border-radius: 10px; margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; border-bottom: 4px solid #ed2939; }}
    header h1 {{ margin: 0; font-size: 1.25rem; }}
    header .meta-header {{ font-size: 0.85rem; color: #dbeafe; }}
    .barre-onglets {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }}
    .barre-onglets span {{ background: #e2e8f0; color: #1e293b; padding: 6px 12px; border-radius: 6px; font-size: 0.84rem; font-weight: 600; }}
    .ok {{ background: #dcfce7; border: 1px solid #16a34a; color: #14532d; padding: 11px 16px; border-radius: 8px; margin-bottom: 12px; font-weight: 500; }}
    .alerte {{ background: #fef3c7; border: 2px solid #d97706; color: #78350f; padding: 12px 16px; border-radius: 8px; margin-bottom: 12px; font-weight: 600; }}
    section {{ background: #ffffff; border: 1px solid #cbd5e1; border-radius: 10px; padding: 16px 20px; margin-bottom: 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.03); }}
    .entete-section {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px; }}
    h2 {{ margin: 0; font-size: 1.06rem; color: #002654; }}
    .badge-statut {{ padding: 4px 10px; border-radius: 999px; font-size: 0.76rem; font-weight: 700; text-transform: uppercase; }}
    .badge-a-completer {{ background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; }}
    .badge-complete {{ background: #dcfce7; color: #166534; border: 1px solid #86efac; }}
    .grille {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 12px; }}
    label {{ display: flex; flex-direction: column; font-size: 0.86rem; font-weight: 600; gap: 4px; color: #1e293b; }}
    input, select, textarea {{ padding: 8px 10px; border: 1px solid #94a3b8; border-radius: 6px; font-size: 0.92rem; font-family: inherit; }}
    textarea {{ min-height: 80px; resize: vertical; }}
    .note-guide {{ font-size: 0.82rem; color: #475569; background: #f8fafc; border-left: 3px solid #1d4ed8; padding: 8px 12px; margin: 10px 0; border-radius: 4px; }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 14px; align-items: center; margin-top: 16px; }}
    .btn-brouillon {{ background: #1d4ed8; color: #fff; border: none; padding: 11px 20px; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 0.93rem; }}
    .btn-officiel {{ background: #b91c1c; color: #fff; border: none; padding: 11px 20px; border-radius: 6px; cursor: pointer; font-weight: 700; font-size: 0.93rem; }}
    .cases-certification {{ background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px 16px; margin-top: 14px; }}
    .cases-certification label {{ flex-direction: row; align-items: center; gap: 8px; font-weight: 500; margin-bottom: 6px; }}
    .cache {{ display: none; }}
    .bloc-catalogue, .bloc-panier {{ margin-top: 16px; border-top: 1px dashed #cbd5e1; padding-top: 12px; }}
    .barre-recherche {{ display: flex; gap: 8px; align-items: flex-end; flex-wrap: wrap; }}
    .barre-recherche label {{ flex: 1 1 320px; }}
    #catalogue-resultats, #panier-liste {{ list-style: none; margin: 10px 0 0; padding: 0; display: grid; gap: 8px; }}
    .catalogue-item, .panier-item {{ border: 1px solid #cbd5e1; border-radius: 8px; padding: 10px 12px; background: #f8fafc; }}
    .catalogue-item {{ display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 8px; }}
    .btn-secondaire {{ background: #0f766e; color: #fff; border: none; padding: 8px 14px; border-radius: 6px; cursor: pointer; font-weight: 600; }}
    .btn-retirer-formation {{ background: #e2e8f0; color: #1e293b; border: none; padding: 8px 14px; border-radius: 6px; cursor: pointer; }}
    .panier-item-entete {{ display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }}
    .compteur-motivation {{ font-size: 0.78rem; color: #64748b; margin: 4px 0 8px; }}
    #panier-message {{ min-height: 1.2em; font-size: 0.86rem; color: #92400e; margin-top: 6px; }}
    footer {{ font-size: 0.8rem; color: #64748b; text-align: center; margin-top: 20px; padding-top: 12px; border-top: 1px solid #cbd5e1; }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>RÉPUBLIQUE FRANÇAISE — Études en France (Campus France Algérie)</h1>
      <div class="meta-header">Guide officiel Septembre 2026 | Portail : https://etudesenfrance.diplomatie.gouv.fr/</div>
    </div>
    <div class="meta-header">
      Langue : <strong>FR - Français</strong> | Affichage : <strong>Thème clair</strong>
    </div>
  </header>

  <div class="barre-onglets">
    <span id="onglet-demo-compte" style="cursor:pointer;" onclick="document.getElementById('section-compte-eligibilite').scrollIntoView({{behavior:'smooth'}})">3. Mon compte &amp; Éligibilité</span>
    <span id="onglet-demo-espace-etudiant" style="cursor:pointer;" onclick="document.getElementById('section-etat-civil').scrollIntoView({{behavior:'smooth'}})">4. Mon espace étudiant</span>
    <span id="onglet-demo-scolarite-langues" style="cursor:pointer;" onclick="document.getElementById('section-cursus-pieces').scrollIntoView({{behavior:'smooth'}})">4. Scolarité &amp; Compétences linguistiques</span>
    <span id="onglet-demo-candidature" style="cursor:pointer;" onclick="document.getElementById('section-formations').scrollIntoView({{behavior:'smooth'}})">5. Mon dossier de candidature (Panier max 7 choix)</span>
    <span id="onglet-demo-paiements-rdv" style="cursor:pointer;" onclick="document.getElementById('section-paiements-et-preconsulaire').scrollIntoView({{behavior:'smooth'}})">5. Mes paiements (20 000 DZD) &amp; Mes rendez-vous</span>
    <span id="onglet-demo-preconsulaire" style="cursor:pointer;" onclick="document.getElementById('section-paiements-et-preconsulaire').scrollIntoView({{behavior:'smooth'}})">6. Mon dossier pré-consulaire (« Je suis accepté »)</span>
  </div>

  {banniere_session}
  {bloc_captcha}

  <div id="bandeau-dossier-complet-eef" class="ok cache">
    <strong>Votre dossier de candidature est complété.</strong> Toutes les rubriques affichent le statut « COMPLÉTÉ ».
  </div>

  <!-- Section 3 : Questionnaire d'éligibilité, Création de compte (« S'inscrire ») & Connexion (« Se connecter ») -->
  <section id="section-compte-eligibilite">
    <div class="entete-section">
      <h2>0. Mon compte — Questionnaire d'éligibilité, Inscription &amp; Connexion (Guide p. 18–27)</h2>
      <span id="badge-statut-compte" class="badge-statut badge-complete">ACTIF</span>
    </div>
    <div class="note-guide">
      Guide Septembre 2026 (p. 18–27) : Questionnaire « Dois-je candidater par Études en France ? », formulaire « S'inscrire » (rattachement Espace Campus France Algérie, lien d'activation valable 48h) et connexion (attention : compte bloqué 30 minutes après 5 tentatives erronées).
    </div>
    <div class="grille">
      <label>Éligibilité — Pays de résidence *
        <input id="elig-pays-residence" type="text" value="Algérie" />
      </label>
      <label>Éligibilité — Nationalité *
        <input id="elig-nationalite" type="text" value="Algérienne" />
      </label>
      <label>Titulaire d'un bac français ou européen ?
        <select id="elig-bac-europeen">
          <option value="Non" selected>Non</option>
          <option value="Oui">Oui</option>
        </select>
      </label>
      <label>Filières sélectives non universitaires (CPGE/BTS/DCG) ?
        <select id="elig-filiere-selective">
          <option value="Non" selected>Non</option>
          <option value="Oui">Oui (Parcoursup)</option>
        </select>
      </label>
      <label>Inscription — Prénom *
        <input id="inscr-prenom" type="text" placeholder="Prénom de l'étudiant" />
      </label>
      <label>Inscription — Nom *
        <input id="inscr-nom" type="text" placeholder="Nom de famille" />
      </label>
      <label>Inscription — Espace Campus France de résidence *
        <select id="inscr-espace-cf">
          <option value="Espace Campus France Algérie" selected>Espace Campus France Algérie</option>
        </select>
      </label>
      <label>Inscription — Région / Antenne de résidence *
        <input id="inscr-region" type="text" placeholder="Alger, Oran, Constantine, Annaba, Tlemcen" />
      </label>
      <label>Inscription — Adresse e-mail *
        <input id="inscr-email" type="email" placeholder="etudiant@exemple.dz" />
      </label>
      <label>Connexion — Identifiant / Adresse e-mail
        <input id="login-identifiant-eef" type="text" placeholder="Identifiant ou adresse e-mail" />
      </label>
    </div>
  </section>

  <!-- Section 4.1 : Mes informations personnelles, Passeport, Coordonnées & Statut particulier -->
  <section id="section-etat-civil">
    <div class="entete-section">
      <h2>1. Mon espace étudiant — Mes informations personnelles, Passeport &amp; Coordonnées</h2>
      <span id="badge-statut-identite" class="badge-statut badge-a-completer">À COMPLÉTER</span>
    </div>
    <div class="note-guide">
      Guide Septembre 2026 (p. 28–36) : Photo d'identité au format passeport et copie du passeport (JPG, PNG ou PDF, max 10 Mo). L'adresse et le numéro de téléphone définissent votre Espace Campus France de rattachement (Alger, Annaba, Constantine, Oran ou Tlemcen).
    </div>
    <div class="grille">
      <label>Nom de famille *
        <input id="champ-nom-famille" name="nom_famille" type="text" placeholder="Ex. BELAID" />
      </label>
      <label>Prénom *
        <input id="champ-prenom" name="prenom_candidat" type="text" placeholder="Ex. Amine" />
      </label>
      <label>Sexe *
        <select id="champ-sexe" name="sexe">
          <option value="">-- Choisir --</option>
          <option value="M">Masculin (M)</option>
          <option value="F">Féminin (F)</option>
        </select>
      </label>
      <label>Date de naissance *
        <input id="champ-date-naissance" name="date_naissance" type="date" />
      </label>
      <label>Lieu de naissance *
        <input id="champ-lieu-naissance" name="lieu_naissance" type="text" placeholder="Ex. Alger" />
      </label>
      <label>Pays et territoire de nationalité *
        <input id="champ-nationalite" name="nationalite" type="text" placeholder="Ex. Algérienne" />
      </label>
      <label>Pays de résidence *
        <input id="champ-pays-residence" name="pays_residence" type="text" placeholder="Ex. Algérie" />
      </label>
      <label>Adresse e-mail *
        <input id="champ-email" name="email" type="email" />
      </label>
      <label>Numéro de téléphone *
        <input id="champ-telephone" name="telephone" type="tel" />
      </label>
      <label>Adresse postale &amp; Wilaya (Coordonnées)
        <input id="champ-adresse-postale" name="adresse_postale" type="text" placeholder="Adresse, Ville, Wilaya" />
      </label>
      <label>Numéro de pièce d'identité (Passeport) *
        <input id="champ-numero-passeport" name="numero_passeport" type="text" />
      </label>
      <label>Date limite de validité du passeport *
        <input id="champ-date-expiration-passeport" name="date_expiration_passeport" type="date" />
      </label>
      <label>Antenne Espace Campus France de rattachement (Algérie)
        <select id="champ-antenne-ecf" name="antenne_ecf">
          <option value="Alger">Alger (ecf.alger@if-algerie.com)</option>
          <option value="Oran">Oran (ecf.oran@if-algerie.com)</option>
          <option value="Constantine">Constantine (ecf.constantine@if-algerie.com)</option>
          <option value="Annaba">Annaba (ecf.annaba@if-algerie.com)</option>
          <option value="Tlemcen">Tlemcen (ecf.tlemcen@if-algerie.com)</option>
        </select>
      </label>
    </div>
    <p style="margin-top:10px; font-size:0.86rem;">
      <label style="flex-direction:row; align-items:center; gap:8px;">
        <input id="case-aucun-statut-particulier" type="checkbox" checked />
        Statut particulier : « Je ne suis concerné par aucun de ces statuts particuliers. »
      </label>
    </p>
  </section>

  <!-- Section 4.2 & 4.3 : Mon dossier de scolarité & Mes compétences linguistiques -->
  <section id="section-cursus-pieces">
    <div class="entete-section">
      <h2>2. Mon dossier de scolarité (CV + min. 2 activités) &amp; Mes compétences linguistiques</h2>
      <span id="badge-statut-scolarite" class="badge-statut badge-a-completer">À COMPLÉTER</span>
    </div>
    <div class="note-guide">
      Guide Septembre 2026 (p. 37–43) : Le parcours scolaire doit comporter au moins 2 activités (du baccalauréat jusqu'à la dernière année d'études supérieures). Si vous avez préparé un baccalauréat non européen en français : sélectionnez « Oui », Volume « Plus de 1000 heures », Durée « 4 ans et plus », Niveau « Avancé ».
    </div>
    <div class="grille">
      <label>Dernier niveau d'études / Activité principale *
        <input id="champ-niveau-actuel" name="niveau_actuel" type="text" placeholder="Ex. Licence 3 Informatique" />
      </label>
      <label>Activité obligatoire n°1 — Type d'activité *
        <select id="activite-1-type">
          <option value="Un bac ou équivalent" selected>Un bac ou équivalent</option>
          <option value="Une année de lycée">Une année de lycée</option>
          <option value="Un concours">Un concours</option>
        </select>
      </label>
      <label>Activité obligatoire n°1 — Détail / Établissement *
        <input id="activite-1-intitule" type="text" placeholder="Ex. Baccalauréat de l'enseignement secondaire" />
      </label>
      <label>Activité obligatoire n°2 — Type d'activité *
        <select id="activite-2-type">
          <option value="Une année d'études supérieures" selected>Une année d'études supérieures</option>
          <option value="Un diplôme d'études supérieures">Un diplôme d'études supérieures</option>
          <option value="Une autre activité">Une autre activité</option>
        </select>
      </label>
      <label>Activité obligatoire n°2 — Détail / Cursus supérieur *
        <input id="activite-2-intitule" type="text" placeholder="Ex. Licence 3 Informatique" />
      </label>
      <label>J'ai déjà étudié le français *
        <select id="champ-francais-etudie">
          <option value="Oui" selected>Oui (Bac non européen en français)</option>
          <option value="Langue maternelle">Langue maternelle</option>
          <option value="Non">Non</option>
        </select>
      </label>
      <label>Volume d'heures de français
        <select id="champ-francais-volume-heures">
          <option value="Plus de 1000 heures" selected>Plus de 1000 heures</option>
          <option value="500 à 1000 heures">500 à 1000 heures</option>
        </select>
      </label>
      <label>Sur une durée de (Français)
        <select id="champ-francais-duree">
          <option value="4 ans et plus" selected>4 ans et plus</option>
          <option value="1 à 3 ans">1 à 3 ans</option>
        </select>
      </label>
      <label>Niveau atteint en français
        <select id="champ-francais-niveau-atteint">
          <option value="Avancé" selected>Avancé</option>
          <option value="Intermédiaire">Intermédiaire</option>
          <option value="Débutant">Débutant</option>
        </select>
      </label>
      <label>J'ai déjà étudié l'anglais *
        <select id="champ-anglais-etudie">
          <option value="Oui" selected>Oui</option>
          <option value="Non">Non</option>
          <option value="Langue maternelle">Langue maternelle</option>
        </select>
      </label>
      <label>Copie du Passeport biométrique (PDF/PNG/JPG, max 10 Mo) *
        <input id="upload-passeport" type="file" />
      </label>
      <label>Photo d'identité au format passeport (max 10 Mo) *
        <input id="upload-photo-identite" type="file" />
      </label>
      <label>Relevé de notes du Baccalauréat *
        <input id="upload-releve-notes-bac" type="file" />
      </label>
      <label>Diplôme ou attestation du Baccalauréat *
        <input id="upload-diplome-bac" type="file" />
      </label>
      <label>Relevés de notes des études supérieures *
        <input id="upload-releves-notes-superieur" type="file" />
      </label>
      <label>Curriculum Vitæ (CV, max 10 Mo) *
        <input id="upload-cv" type="file" />
      </label>
      <label>Attestation de test de français (TCF / DELF / DALF)
        <input id="upload-test-francais" type="file" />
      </label>
    </div>
  </section>

  <!-- Section 5 : Mon dossier de candidature (Panier de formations & Motivations) -->
  <section id="section-formations">
    <div class="entete-section">
      <h2>3. Mon dossier de candidature — Mon panier de formations (max 7 vœux) &amp; Motivations</h2>
      <span id="badge-statut-panier" class="badge-statut badge-a-completer">À COMPLÉTER</span>
    </div>
    <div class="note-guide">
      Guide Septembre 2026 (p. 44–59) : Jusqu'à 7 formations au total (DAP Blanche L1 : max 3 choix | DAP Jaune Architecture ENSA : 2 choix + Portfolio | Hors DAP L2/L3/M1/M2/Ingénieur/Commerce : max 7 choix). Statut vérifié : <strong>OUVERT À LA CANDIDATURE</strong> — <strong>PROCÉDURE UNIQUEMENT SUR ÉTUDES EN FRANCE</strong>.
    </div>
    <div class="grille">
      <label>Intitulé de la formation sélectionnée dans le catalogue *
        <input id="champ-programme-vise" name="programme_vise" type="text" placeholder="Ex. Master 1 Informatique et Intelligence Artificielle" />
      </label>
      <label>Établissement d'accueil visé *
        <input id="champ-etablissement-vise" name="etablissement_vise" type="text" placeholder="Ex. Université Paris-Saclay" />
      </label>
    </div>
    <div style="margin-top: 12px;">
      <label>Texte de motivation (« Vos motivations » — limite officielle : 4 000 caractères)
        <textarea id="champ-texte-motivation" name="texte_motivation" maxlength="4000" placeholder="Rédigez ou laissez l'agent pré-remplir votre projet d'études personnalisé (max 4 000 caractères)..."></textarea>
      </label>
    </div>

    <!-- Catalogue de formations (recherche) -->
    <div class="bloc-catalogue" id="bloc-catalogue">
      <h3 style="margin:0 0 8px; font-size:0.98rem;">Catalogue des formations</h3>
      <div class="barre-recherche">
        <label>Rechercher une formation (intitulé ou établissement)
          <input id="catalogue-recherche" type="search" placeholder="Ex. Master 1 Informatique" autocomplete="off" />
        </label>
        <button id="btn-catalogue-rechercher" type="button" class="btn-brouillon">Rechercher</button>
      </div>
      <ul id="catalogue-resultats" aria-live="polite"></ul>
    </div>

    <!-- Panier de formations (max 7) avec un texte de motivation par formation -->
    <div class="bloc-panier" id="panier-formations">
      <h3 style="margin:0 0 8px; font-size:0.98rem;">Mon panier de formations — <span id="panier-compteur">0 / 7</span></h3>
      <div id="panier-message" role="status"></div>
      <ul id="panier-liste"></ul>
    </div>
  </section>

  <!-- Section 5 (suite) & 6 : Mes paiements (Algérie), Mes rendez-vous & Mon dossier pré-consulaire -->
  <section id="section-paiements-et-preconsulaire">
    <div class="entete-section">
      <h2>4. Mes paiements (Algérie), Entretien ECF &amp; Mon dossier pré-consulaire (« Je suis accepté » — 4 étapes)</h2>
      <span id="badge-statut-paiement" class="badge-statut badge-complete">PRÊT</span>
    </div>
    <div class="grille">
      <label>Déclaration de paiement — Nom du payeur (Tarif Algérie : 20 000 DZD / Demi-tarif : 10 000 DZD)
        <input id="champ-nom-payeur" type="text" placeholder="Nom et prénom du payeur (ou paiement.if-algerie.com)" />
      </label>
      <label>Lieu de l'entretien Campus France Algérie
        <select id="champ-lieu-rdv-ecf">
          <option value="Espace Campus France Alger">Espace Campus France Alger</option>
          <option value="Espace Campus France Oran">Espace Campus France Oran</option>
          <option value="Espace Campus France Constantine">Espace Campus France Constantine</option>
          <option value="Espace Campus France Annaba">Espace Campus France Annaba</option>
          <option value="Espace Campus France Tlemcen">Espace Campus France Tlemcen</option>
        </select>
      </label>
      <label>Dossier pré-consulaire — Étape 1/4 : Type de projet d'étude
        <select id="preconsulaire-etape1-type">
          <option value="Admission via Études en France">Admission obtenue via Études en France</option>
          <option value="Acceptation papier">Acceptation papier (hors Études en France)</option>
          <option value="Programme d'échange">Programme d'échange</option>
        </select>
      </label>
      <label>Dossier pré-consulaire — Étape 2/4 : Catégorie de formation
        <select id="preconsulaire-etape2-categorie">
          <option value="Formation diplômante">Formation diplômante</option>
          <option value="Formation professionnelle continue">Formation professionnelle continue</option>
          <option value="Formation français langue étrangère (FLE)">Formation français langue étrangère (FLE)</option>
          <option value="Doctorat">Doctorat</option>
          <option value="Concours">Concours</option>
          <option value="Autre">Autre</option>
        </select>
      </label>
      <label>Dossier pré-consulaire — Étape 3/4 : Nom de la formation retenue
        <input id="preconsulaire-etape3-formation" type="text" placeholder="Nom de la formation" />
      </label>
      <label>Dossier pré-consulaire — Étape 3/4 : Établissement d'accueil
        <input id="preconsulaire-etape3-etablissement" type="text" placeholder="Établissement d'accueil" />
      </label>
    </div>
    <div style="margin-top: 12px;">
      <label>Dossier pré-consulaire — Étape 4/4 : Motivations (max 4 000 caractères)
        <textarea id="preconsulaire-etape4-motivation" maxlength="4000" placeholder="Motivations pour le dossier pré-consulaire (0/4 000 caractères)..."></textarea>
      </label>
    </div>

    <div class="cases-certification">
      <strong>Vérification avant soumission officielle (Guide Septembre 2026, p. 58 — Règle 1) :</strong>
      <label>
        <input id="case-certif-exactitude" type="checkbox" checked />
        J'ai bien relu mon dossier et je certifie l'exactitude des informations qu'il contient. *
      </label>
      <label>
        <input id="case-certif-prerequis" type="checkbox" checked />
        Je certifie avoir pris connaissance des prérequis relatifs aux formations auxquelles je candidate. *
      </label>
    </div>

    <div class="actions">
      <button id="btn-enregistrer-brouillon" type="button" class="btn-brouillon">
        Enregistrer toutes les rubriques du dossier (Mode brouillon sécurisé)
      </button>
      <button
        id="btn-soumission-finale-officielle"
        type="button"
        class="btn-officiel"
        data-action-officielle="soumettre-definitivement"
      >
        Soumettre mon dossier de candidature (Validation finale par l'opérateur humain)
      </button>
    </div>

    <div id="banniere-brouillon-enregistre" class="ok cache" style="margin-top: 14px;">
      Brouillon Études en France pré-rempli et enregistré avec succès — Toutes les rubriques sont au statut « COMPLÉTÉ ». L'agent s'est arrêté avant la soumission finale (Règle 1).
    </div>
    <div id="banniere-soumission-finale-effectuee" class="ok cache" style="margin-top: 14px; border-color:#1d4ed8; background:#eff6ff; color:#1e3a8a;">
      Confirmation humaine enregistrée : le dossier Études en France a été soumis manuellement par l'opérateur. Vous pouvez maintenant télécharger la quittance de paiement et suivre l'instruction par l'Espace Campus France Algérie.
    </div>
  </section>

  <footer>
    Plateforme Études en France — Guide Septembre 2026 (Campus France Algérie : Alger, Annaba, Constantine, Oran, Tlemcen) | Réduction 50 % frais de visa long séjour CAPAGO avec l'attestation d'acceptation DZXX-XXXXX.
  </footer>

  <script>
    window.__SOUMISSION_FINALE_CLIQUEE__ = false;
    window.__BROUILLON_ENREGISTRE__ = false;
    window.__MOTIVATIONS_ENREGISTREES__ = 0;

    // ---- Catalogue de formations & panier de vœux (max 7) avec motivation par formation ----
    var CATALOGUE_FORMATIONS = {catalogue_json};
    var LIMITE_PANIER = 7;
    var LIMITE_MOTIVATION = 4000;

    function normaliserRecherche(t) {{
      return String(t || "").normalize("NFD").replace(/[\\u0300-\\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
    }}
    function messagePanier(texte) {{
      document.getElementById("panier-message").textContent = texte || "";
    }}
    function nbPanier() {{
      return document.querySelectorAll("#panier-liste .panier-item").length;
    }}
    function majCompteurPanier() {{
      document.getElementById("panier-compteur").textContent = nbPanier() + " / " + LIMITE_PANIER;
    }}
    function formationDansPanier(id) {{
      return Array.prototype.some.call(document.querySelectorAll("#panier-liste .panier-item"), function (li) {{
        return li.getAttribute("data-formation-id") === id;
      }});
    }}

    function lancerRechercheCatalogue() {{
      var q = normaliserRecherche(document.getElementById("catalogue-recherche").value);
      var liste = document.getElementById("catalogue-resultats");
      liste.innerHTML = "";
      CATALOGUE_FORMATIONS.forEach(function (f) {{
        var meule = normaliserRecherche(f.intitule + " " + f.etablissement + " " + f.niveau);
        if (q && meule.indexOf(q) === -1) return;
        var li = document.createElement("li");
        li.className = "catalogue-item";
        li.setAttribute("data-formation-id", f.id);
        li.setAttribute("data-intitule", f.intitule);
        li.setAttribute("data-etablissement", f.etablissement);
        li.setAttribute("data-niveau", f.niveau);
        if (f.campus) li.setAttribute("data-campus", f.campus);
        var info = document.createElement("span");
        info.className = "catalogue-info";
        info.textContent = f.intitule + " — " + f.etablissement + " — " + f.niveau + (f.campus ? " (campus " + f.campus + ")" : "");
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn-ajouter-formation btn-secondaire";
        btn.textContent = "+ Ajouter une formation";
        btn.addEventListener("click", function () {{ ajouterAuPanier(f); }});
        li.appendChild(info);
        li.appendChild(btn);
        liste.appendChild(li);
      }});
      if (!liste.children.length) {{
        var vide = document.createElement("li");
        vide.className = "catalogue-vide";
        vide.textContent = "Aucune formation ne correspond à votre recherche.";
        liste.appendChild(vide);
      }}
    }}

    function ajouterAuPanier(f) {{
      if (formationDansPanier(f.id)) {{ messagePanier("Cette formation est déjà dans votre panier."); return; }}
      if (nbPanier() >= LIMITE_PANIER) {{ messagePanier("Votre panier est plein : 7 formations maximum."); return; }}
      messagePanier("");
      var li = document.createElement("li");
      li.className = "panier-item";
      li.setAttribute("data-formation-id", f.id);
      li.setAttribute("data-intitule", f.intitule);
      li.setAttribute("data-etablissement", f.etablissement);
      li.setAttribute("data-niveau", f.niveau);
      li.setAttribute("data-statut", "motivation_a_rediger");

      var entete = document.createElement("div");
      entete.className = "panier-item-entete";
      var titre = document.createElement("strong");
      titre.textContent = f.intitule + " — " + f.etablissement + " (" + f.niveau + ")";
      var statut = document.createElement("span");
      statut.className = "panier-statut badge-statut badge-a-completer";
      statut.textContent = "Motivation à rédiger";
      entete.appendChild(titre);
      entete.appendChild(statut);

      var lbl = document.createElement("label");
      lbl.appendChild(document.createTextNode("Texte de motivation (limite officielle : 4 000 caractères)"));
      var zone = document.createElement("textarea");
      zone.className = "panier-motivation";
      zone.setAttribute("maxlength", String(LIMITE_MOTIVATION));
      zone.setAttribute("placeholder", "Motivation pour cette formation (max 4 000 caractères)...");
      lbl.appendChild(zone);

      var compteur = document.createElement("div");
      compteur.className = "compteur-motivation";
      compteur.textContent = "0 / 4 000 caractères";
      zone.addEventListener("input", function () {{
        compteur.textContent = zone.value.length + " / 4 000 caractères";
        if (li.getAttribute("data-statut") === "motivation_enregistree") {{
          li.setAttribute("data-statut", "motivation_a_rediger");
          statut.textContent = "Motivation modifiée — à enregistrer";
          statut.className = "panier-statut badge-statut badge-a-completer";
        }}
      }});

      var btnEnreg = document.createElement("button");
      btnEnreg.type = "button";
      btnEnreg.className = "btn-enregistrer-motivation btn-brouillon";
      btnEnreg.textContent = "Enregistrer";
      btnEnreg.addEventListener("click", function () {{
        var v = zone.value;
        if (!v.trim()) {{ messagePanier("La motivation est vide : rien à enregistrer."); return; }}
        if (v.length > LIMITE_MOTIVATION) {{ messagePanier("La motivation dépasse 4 000 caractères."); return; }}
        messagePanier("");
        li.setAttribute("data-statut", "motivation_enregistree");
        statut.textContent = "Motivation enregistrée";
        statut.className = "panier-statut badge-statut badge-complete";
        window.__MOTIVATIONS_ENREGISTREES__ += 1;
      }});

      var btnRetirer = document.createElement("button");
      btnRetirer.type = "button";
      btnRetirer.className = "btn-retirer-formation";
      btnRetirer.setAttribute("data-action", "retirer-formation");
      btnRetirer.textContent = "Retirer du panier";
      btnRetirer.addEventListener("click", function () {{
        li.remove();
        majCompteurPanier();
      }});

      li.appendChild(entete);
      li.appendChild(lbl);
      li.appendChild(compteur);
      li.appendChild(btnEnreg);
      li.appendChild(document.createTextNode(" "));
      li.appendChild(btnRetirer);
      document.getElementById("panier-liste").appendChild(li);
      majCompteurPanier();
    }}

    document.getElementById("btn-catalogue-rechercher").addEventListener("click", lancerRechercheCatalogue);
    document.getElementById("catalogue-recherche").addEventListener("keydown", function (ev) {{
      if (ev.key === "Enter") {{ ev.preventDefault(); lancerRechercheCatalogue(); }}
    }});

    function marquerRubriquesCompletes() {{
      ["badge-statut-identite", "badge-statut-scolarite", "badge-statut-panier"].forEach(function(id) {{
        var el = document.getElementById(id);
        if (el) {{
          el.textContent = "COMPLÉTÉ";
          el.className = "badge-statut badge-complete";
        }}
      }});
      var bandeau = document.getElementById("bandeau-dossier-complet-eef");
      if (bandeau) bandeau.classList.remove("cache");
    }}

    document.getElementById("btn-enregistrer-brouillon").addEventListener("click", function () {{
      window.__BROUILLON_ENREGISTRE__ = true;
      marquerRubriquesCompletes();
      document.getElementById("banniere-brouillon-enregistre").classList.remove("cache");
    }});

    document.getElementById("btn-soumission-finale-officielle").addEventListener("click", function () {{
      window.__SOUMISSION_FINALE_CLIQUEE__ = true;
      document.getElementById("banniere-soumission-finale-effectuee").classList.remove("cache");
    }});

    window.addEventListener("message", function (ev) {{
      var d = ev.data || {{}};
      if (d.type === "COWORK_SYNC_CANDIDAT" && d.candidat) {{
        var c = d.candidat;
        var mapChamps = {{
          "champ-nom-famille": c.nom,
          "inscr-nom": c.nom,
          "champ-prenom": c.prenom,
          "inscr-prenom": c.prenom,
          "champ-sexe": c.sexe,
          "champ-date-naissance": c.date_naissance,
          "champ-lieu-naissance": c.lieu_naissance,
          "champ-adresse-postale": c.lieu_naissance,
          "inscr-region": c.lieu_naissance,
          "champ-nationalite": c.nationalite,
          "elig-nationalite": c.nationalite,
          "champ-pays-residence": c.pays_residence,
          "elig-pays-residence": c.pays_residence,
          "champ-email": c.email,
          "inscr-email": c.email,
          "login-identifiant-eef": c.email,
          "champ-telephone": c.telephone,
          "champ-numero-passeport": c.numero_passeport,
          "champ-date-expiration-passeport": c.date_expiration_passeport,
          "champ-niveau-actuel": c.niveau_actuel,
          "activite-2-intitule": c.niveau_actuel,
          "champ-programme-vise": c.programme_vise,
          "preconsulaire-etape3-formation": c.programme_vise,
          "champ-etablissement-vise": c.etablissement_vise,
          "preconsulaire-etape3-etablissement": c.etablissement_vise,
          "champ-nom-payeur": ((c.nom || "") + " " + (c.prenom || "")).trim()
        }};
        if (d.motivation) {{
          mapChamps["champ-texte-motivation"] = d.motivation;
          mapChamps["preconsulaire-etape4-motivation"] = d.motivation;
        }}
        Object.keys(mapChamps).forEach(function (id) {{
          var el = document.getElementById(id);
          if (el && mapChamps[id]) {{
            el.value = mapChamps[id];
            el.style.outline = "2px solid #2563eb";
            setTimeout(function () {{ el.style.outline = ""; }}, 1200);
          }}
        }});
        if (d.marquerComplet) {{
          marquerRubriquesCompletes();
          document.getElementById("banniere-brouillon-enregistre").classList.remove("cache");
        }}
      }} else if (d.type === "COWORK_ACTION_DOM" && d.selecteur) {{
        var cible = document.querySelector(d.selecteur);
        if (cible) {{
          cible.scrollIntoView({{ behavior: "smooth", block: "center" }});
          cible.style.outline = "3px solid #16a34a";
          setTimeout(function () {{ cible.style.outline = ""; }}, 1500);
          if (d.operation === "remplir" && d.valeur !== undefined) {{
            cible.value = d.valeur;
          }} else if (d.operation === "cliquer" && !cible.getAttribute("data-action-officielle")) {{
            cible.click();
          }}
        }}
      }}
    }});
  </script>
</body>
</html>"""
    return HTMLResponse(content=html, headers={"X-Frame-Options": "SAMEORIGIN"})


@routeur_demo.get("/ircc", response_class=HTMLResponse)
def page_demo_ircc(
    session_ouverte: int = Query(default=1),
    captcha: int = Query(default=0),
) -> HTMLResponse:
    banniere_session = (
        '<div id="bandeau-session-ircc-connectee" class="ok">'
        "Session Portail IRCC Canada active (ouverte par l'opérateur — aucune CléGC ni mot de passe stocké par l'agent — Règle 3)"
        "</div>"
        if session_ouverte == 1
        else '<div id="alerte-session-ircc-fermee" class="alerte">'
        "Session IRCC non ouverte : veuillez vous authentifier manuellement (CléGC / Partenaire de connexion) avant de lancer l'agent."
        "</div>"
    )
    bloc_captcha = (
        '<div id="bloc-captcha-ircc" class="alerte">'
        "Vérification de sécurité IRCC / 2FA active : intervention humaine requise dans le navigateur (Règle 2)."
        "</div>"
        if captcha == 1
        else ""
    )

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <title>Gouvernement du Canada — Portail IRCC Demande de permis d'études</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 24px; background: #f8f9fa; color: #1f2933; }}
    header {{ background: #26374a; color: #fff; padding: 16px 20px; border-radius: 8px; margin-bottom: 16px; border-bottom: 4px solid #af3c43; }}
    .ok {{ background: #e6f6ec; border: 1px solid #2b8a3e; color: #1b5e20; padding: 10px 14px; border-radius: 6px; margin-bottom: 12px; }}
    .alerte {{ background: #fff3cd; border: 2px solid #d9480f; color: #7f2704; padding: 12px 14px; border-radius: 6px; margin-bottom: 12px; font-weight: 600; }}
    section {{ background: #fff; border: 1px solid #d8dee9; border-radius: 8px; padding: 16px 20px; margin-bottom: 16px; }}
    h2 {{ margin-top: 0; font-size: 1.1rem; color: #26374a; }}
    .grille {{ display: grid; grid-template-columns: repeat(2, minmax(240px, 1fr)); gap: 12px; }}
    label {{ display: flex; flex-direction: column; font-size: 0.9rem; font-weight: 600; gap: 4px; }}
    input, select {{ padding: 8px; border: 1px solid #b0bec5; border-radius: 4px; font-size: 0.95rem; }}
    .actions {{ display: flex; gap: 16px; align-items: center; margin-top: 16px; flex-wrap: wrap; }}
    .btn-brouillon {{ background: #26374a; color: #fff; border: none; padding: 10px 18px; border-radius: 6px; cursor: pointer; font-weight: 600; }}
    .btn-officiel {{ background: #af3c43; color: #fff; border: none; padding: 10px 18px; border-radius: 6px; cursor: pointer; font-weight: 700; }}
    .cache {{ display: none; }}
  </style>
</head>
<body>
  <header>
    <h1>Immigration, Réfugiés et Citoyenneté Canada (IRCC) — Demande de permis d'études</h1>
  </header>

  {banniere_session}
  {bloc_captcha}

  <section id="section-ircc-identite">
    <h2>1. Identité du demandeur et document de voyage (Passeport)</h2>
    <div class="grille">
      <label>Nom de famille (tel qu'indiqué sur le passeport)
        <input id="ircc-nom-famille" type="text" />
      </label>
      <label>Prénom(s)
        <input id="ircc-prenom" type="text" />
      </label>
      <label>Sexe
        <select id="ircc-sexe">
          <option value="">-- Sélectionner --</option>
          <option value="M">M</option>
          <option value="F">F</option>
        </select>
      </label>
      <label>Date de naissance
        <input id="ircc-date-naissance" type="date" />
      </label>
      <label>Ville / Lieu de naissance
        <input id="ircc-lieu-naissance" type="text" />
      </label>
      <label>Citoyenneté / Nationalité
        <input id="ircc-nationalite" type="text" />
      </label>
      <label>Pays de résidence actuel
        <input id="ircc-pays-residence" type="text" />
      </label>
      <label>Courriel de contact
        <input id="ircc-email" type="email" />
      </label>
      <label>Numéro de téléphone
        <input id="ircc-telephone" type="tel" />
      </label>
      <label>Numéro du passeport
        <input id="ircc-numero-passeport" type="text" />
      </label>
      <label>Date d'expiration du passeport
        <input id="ircc-date-expiration-passeport" type="date" />
      </label>
    </div>
  </section>

  <section id="section-ircc-dli">
    <h2>2. Établissement d'enseignement désigné (EED / DLI) et ressources financières (Seuil 20 635 $ CAD)</h2>
    <div class="grille">
      <label>Établissement d'enseignement désigné (EED / DLI)
        <input id="ircc-etablissement-dli" type="text" />
      </label>
      <label>Programme d'études visé
        <input id="ircc-programme-etudes" type="text" />
      </label>
      <label>Fonds disponibles pour le séjour (équivalent EUR — min. recommandé 14 500 EUR / 20 635 CAD)
        <input id="ircc-fonds-disponibles-eur" type="number" />
      </label>
    </div>
  </section>

  <section id="section-ircc-pieces">
    <h2>3. Téléversement des pièces justificatives obligatoires IRCC</h2>
    <div class="grille">
      <label>Passeport valide (page biographique et tampons)
        <input id="ircc-upload-passeport" type="file" />
      </label>
      <label>Lettre d'admission d'un établissement d'enseignement désigné (EED / DLI)
        <input id="ircc-upload-lettre-admission-dli" type="file" />
      </label>
      <label>Lettre d'attestation provinciale (LAP / PAL) ou CAQ (Québec)
        <input id="ircc-upload-pal-caq" type="file" />
      </label>
      <label>Preuve de ressources financières (seuil 20 635 CAD hors frais de scolarité)
        <input id="ircc-upload-preuve-financiere" type="file" />
      </label>
      <label>Photographie numérique aux normes IRCC
        <input id="ircc-upload-photo-identite" type="file" />
      </label>
      <label>Formulaire IMM 5645 (Informations sur la famille)
        <input id="ircc-upload-imm5645" type="file" />
      </label>
    </div>

    <div class="actions">
      <button id="btn-enregistrer-brouillon-ircc" type="button" class="btn-brouillon">
        Sauvegarder la demande pré-remplie en brouillon (sans transmettre)
      </button>
      <button
        id="btn-soumission-finale-ircc"
        type="button"
        class="btn-officiel"
        data-action-officielle="transmettre-demande-ircc"
      >
        Signer et transmettre la demande officielle à IRCC (Validation finale par l'opérateur humain)
      </button>
    </div>

    <div id="banniere-brouillon-ircc-enregistre" class="ok cache" style="margin-top: 14px;">
      Demande de permis d'études IRCC sauvegardée en brouillon — Arrêt de sécurité de l'agent effectué avant la signature et la transmission finale (Règle 1).
    </div>
    <div id="banniere-soumission-ircc-effectuee" class="ok cache" style="margin-top: 14px; border-color:#26374a; background:#eef2ff; color:#1e293b;">
      Confirmation humaine enregistrée : la demande de permis d'études IRCC a été signée et transmise manuellement par l'opérateur.
    </div>
  </section>

  <script>
    window.__SOUMISSION_FINALE_CLIQUEE__ = false;
    window.__BROUILLON_ENREGISTRE__ = false;

    document.getElementById("btn-enregistrer-brouillon-ircc").addEventListener("click", function () {{
      window.__BROUILLON_ENREGISTRE__ = true;
      document.getElementById("banniere-brouillon-ircc-enregistre").classList.remove("cache");
    }});

    document.getElementById("btn-soumission-finale-ircc").addEventListener("click", function () {{
      window.__SOUMISSION_FINALE_CLIQUEE__ = true;
      document.getElementById("banniere-soumission-ircc-effectuee").classList.remove("cache");
    }});

    window.addEventListener("message", function (ev) {{
      var d = ev.data || {{}};
      if (d.type === "COWORK_SYNC_CANDIDAT" && d.candidat) {{
        var c = d.candidat;
        var mapIrcc = {{
          "ircc-nom-famille": c.nom,
          "ircc-prenom": c.prenom,
          "ircc-sexe": c.sexe,
          "ircc-date-naissance": c.date_naissance,
          "ircc-lieu-naissance": c.lieu_naissance,
          "ircc-nationalite": c.nationalite,
          "ircc-pays-residence": c.pays_residence,
          "ircc-email": c.email,
          "ircc-telephone": c.telephone,
          "ircc-numero-passeport": c.numero_passeport,
          "ircc-date-expiration-passeport": c.date_expiration_passeport,
          "ircc-etablissement-dli": c.etablissement_vise,
          "ircc-programme-etudes": c.programme_vise,
          "ircc-fonds-disponibles-eur": c.fonds_disponibles_eur
        }};
        Object.keys(mapIrcc).forEach(function (id) {{
          var el = document.getElementById(id);
          if (el && mapIrcc[id] !== undefined && mapIrcc[id] !== null) {{
            el.value = mapIrcc[id];
            el.style.outline = "2px solid #2563eb";
            setTimeout(function () {{ el.style.outline = ""; }}, 1200);
          }}
        }});
        if (d.marquerComplet) {{
          document.getElementById("banniere-brouillon-ircc-enregistre").classList.remove("cache");
        }}
      }} else if (d.type === "COWORK_ACTION_DOM" && d.selecteur) {{
        var cible = document.querySelector(d.selecteur);
        if (cible) {{
          cible.scrollIntoView({{ behavior: "smooth", block: "center" }});
          cible.style.outline = "3px solid #16a34a";
          setTimeout(function () {{ cible.style.outline = ""; }}, 1500);
          if (d.operation === "remplir" && d.valeur !== undefined) {{
            cible.value = d.valeur;
          }} else if (d.operation === "cliquer" && !cible.getAttribute("data-action-officielle")) {{
            cible.click();
          }}
        }}
      }}
    }});
  </script>
</body>
</html>"""
    return HTMLResponse(content=html, headers={"X-Frame-Options": "SAMEORIGIN"})
