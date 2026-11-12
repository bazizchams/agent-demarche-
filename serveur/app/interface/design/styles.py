"""Feuille de style unique de l'interface : tokens (clair et sombre) puis composants.

Direction : outil de bureau d'études, sobre et dense. Neutres teintés vers l'indigo de
l'accent ; la sémantique (bon, alerte, critique) reste distincte de l'accent. Les cartes n'ont
ni ombre ni double bordure : l'ombre est réservée aux éléments flottants (notification, menu).
Les noms hérités (--bleu-primaire, --carte, --bordure...) restent définis comme alias pour le
code d'écran existant, afin que tout suive automatiquement le thème.
"""

from __future__ import annotations

LIEN_POLICES = (
    '<link rel="preconnect" href="https://fonts.googleapis.com" />\n'
    '  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />\n'
    '  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700"
    '&amp;family=Inter:wght@400;500;600&amp;display=swap" />'
)

TOKENS_CLAIR = """
      --fond: #f5f6fa;
      --surface: #ffffff;
      --surface-2: #eef0f6;
      --surface-3: #e2e5f0;
      --bord: #dfe2ec;
      --bord-fort: #c5cadb;
      --texte: #161a2e;
      --texte-doux: #4b5370;
      --texte-faible: #5f6784;
      --accent: #3342c4;
      --accent-fort: #252f99;
      --accent-doux: #e6e9fb;
      --sur-accent: #ffffff;
      --bon: #187a45;
      --bon-doux: #e0f3e8;
      --bon-texte: #12603a;
      --alerte: #a85a00;
      --alerte-doux: #fdf0d8;
      --alerte-texte: #7d4300;
      --critique: #c1272d;
      --critique-doux: #fde8e8;
      --critique-texte: #98191f;
      --ombre-flottante: 0 14px 34px rgba(22, 26, 46, 0.18), 0 2px 6px rgba(22, 26, 46, 0.10);
      --anneau: 0 0 0 3px rgba(51, 66, 196, 0.28);
"""

TOKENS_SOMBRE = """
      --fond: #0e1120;
      --surface: #151a2e;
      --surface-2: #1c2238;
      --surface-3: #262d49;
      --bord: #2b3352;
      --bord-fort: #3d476c;
      --texte: #e8ebf7;
      --texte-doux: #aab1cc;
      --texte-faible: #8b93b2;
      --accent: #8f9bff;
      --accent-fort: #b3bbff;
      --accent-doux: #232b5c;
      --sur-accent: #0c1035;
      --bon: #4cc88a;
      --bon-doux: #173a2b;
      --bon-texte: #7fdcab;
      --alerte: #f0a64a;
      --alerte-doux: #40290c;
      --alerte-texte: #f5c27d;
      --critique: #ff7b80;
      --critique-doux: #45191d;
      --critique-texte: #ffa3a7;
      --ombre-flottante: 0 14px 34px rgba(0, 0, 0, 0.55), 0 2px 6px rgba(0, 0, 0, 0.4);
      --anneau: 0 0 0 3px rgba(143, 155, 255, 0.35);
"""

_RACINE = """
    :root {
      color-scheme: light;
      /* Typographie : titres caractérisés, texte courant très lisible, piles de secours */
      --police-titre: "Bricolage Grotesque", "Segoe UI Variable Display", "Segoe UI", system-ui, sans-serif;
      --police-texte: Inter, "Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, sans-serif;
      --police-code: ui-monospace, "Cascadia Mono", Consolas, monospace;
      /* Échelle typographique */
      --t-xs: 0.75rem; --t-sm: 0.8125rem; --t-base: 0.9375rem; --t-md: 1.0625rem;
      --t-lg: 1.3125rem; --t-xl: 1.75rem; --t-2xl: 2.25rem;
      /* Espacements */
      --e1: 4px; --e2: 8px; --e3: 12px; --e4: 16px; --e5: 24px; --e6: 32px; --e7: 48px;
      /* Rayons */
      --r-s: 6px; --r-m: 10px; --r-l: 14px; --r-pilule: 999px;
      /* Durées et courbe */
      --d1: 120ms; --d2: 200ms; --d3: 320ms;
      --courbe: cubic-bezier(0.2, 0.7, 0.2, 1);
      --largeur-nav: 268px;
      /* Alias hérités du code d'écran existant */
      --texte-secondaire: var(--texte-doux);
      --bleu-primaire: var(--accent);
      --bleu-clair: var(--accent-doux);
      --vert-succes: var(--bon);
      --vert-clair: var(--bon-doux);
      --orange-alerte: var(--alerte);
      --orange-clair: var(--alerte-doux);
      --rouge-danger: var(--critique);
      --rouge-clair: var(--critique-doux);
      --carte: var(--surface);
      --bordure: var(--bord);
      --rayon: var(--r-m);
"""

CSS_BASE = """
    * { box-sizing: border-box; }
    html { -webkit-text-size-adjust: 100%; }
    body {
      margin: 0; min-height: 100vh; background: var(--fond); color: var(--texte);
      font-family: var(--police-texte); font-size: var(--t-base); line-height: 1.55;
      -webkit-font-smoothing: antialiased; display: grid; grid-template-columns: var(--largeur-nav) minmax(0, 1fr);
    }
    ::selection { background: var(--accent-doux); color: var(--texte); }
    a { color: var(--accent); text-underline-offset: 2px; }
    a:hover { color: var(--accent-fort); }
    code { font-family: var(--police-code); font-size: 0.88em; background: var(--surface-2); padding: 1px 6px; border-radius: var(--r-s); }
    h1, h2, h3, h4 { font-family: var(--police-titre); color: var(--texte); margin: 0; font-weight: 700; letter-spacing: -0.012em; line-height: 1.2; }
    h2 { font-size: var(--t-xl); }
    h3 { font-size: var(--t-md); letter-spacing: -0.005em; }
    h4 { font-size: var(--t-base); margin: var(--e5) 0 var(--e2); }
    p { margin: 0 0 var(--e3); }
    small { font-size: var(--t-sm); color: var(--texte-doux); }
    .cache { display: none !important; }
    .sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
    :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: var(--r-s); }
    .ico { width: 1.15em; height: 1.15em; stroke: currentColor; fill: none; stroke-width: 1.75; stroke-linecap: round; stroke-linejoin: round; flex: none; }

    /* ---------- Navigation latérale ---------- */
    aside#navigation-principale {
      position: sticky; top: 0; align-self: start; height: 100vh; height: 100dvh; overflow-y: auto;
      display: flex; flex-direction: column; gap: var(--e4); padding: var(--e4) var(--e3) var(--e3);
      background: var(--surface); border-right: 1px solid var(--bord);
    }
    .marque { display: flex; align-items: center; gap: var(--e3); padding: var(--e1) var(--e2) var(--e2); }
    .marque-logo { width: 34px; height: 34px; border-radius: var(--r-m); background: var(--accent); color: var(--sur-accent); display: grid; place-items: center; flex: none; }
    .marque-logo .ico { width: 20px; height: 20px; }
    .marque-nom { font-family: var(--police-titre); font-weight: 700; font-size: var(--t-md); line-height: 1.15; letter-spacing: -0.01em; }
    .marque-sous { display: block; font-family: var(--police-texte); font-weight: 500; font-size: var(--t-xs); color: var(--texte-faible); letter-spacing: 0; }
    .nav-groupe { display: flex; flex-direction: column; gap: 2px; }
    .nav-titre { margin: 0; padding: var(--e2) var(--e3) var(--e1); font-size: var(--t-xs); font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--texte-faible); }
    aside button.nav-btn {
      position: relative; display: flex; align-items: center; gap: var(--e3); width: 100%; text-align: left;
      padding: 9px var(--e3); border: 0; border-radius: var(--r-m); background: transparent; color: var(--texte-doux);
      font: inherit; font-size: var(--t-base); font-weight: 500; line-height: 1.25; cursor: pointer;
      transition: background-color var(--d1) var(--courbe), color var(--d1) var(--courbe);
    }
    aside button.nav-btn:hover { background: var(--surface-2); color: var(--texte); }
    aside button.nav-btn.actif { background: var(--accent-doux); color: var(--accent-fort); font-weight: 600; }
    aside button.nav-btn.actif::before { content: ""; position: absolute; left: -12px; top: 8px; bottom: 8px; width: 3px; border-radius: 0 3px 3px 0; background: var(--accent); }
    .nav-compteur { margin-left: auto; min-width: 22px; padding: 1px 7px; border-radius: var(--r-pilule); background: var(--alerte-doux); color: var(--alerte-texte); font-size: var(--t-xs); font-weight: 600; text-align: center; }
    .nav-pied { margin-top: auto; display: flex; flex-direction: column; gap: var(--e3); padding-top: var(--e3); border-top: 1px solid var(--bord); }
    .session-etat { display: flex; align-items: center; gap: var(--e2); font-size: var(--t-sm); color: var(--texte-doux); }
    .session-etat .ico { color: var(--texte-faible); }
    #etat-utilisateur { font-weight: 600; color: var(--texte); overflow-wrap: anywhere; }
    .session-form summary { cursor: pointer; font-size: var(--t-sm); color: var(--accent); padding: var(--e1) 0; }
    .session-form[open] summary { margin-bottom: var(--e2); }
    .session-form .grille-form { gap: var(--e2); }
    .session-actions { display: flex; gap: var(--e2); flex-wrap: wrap; }
    .bouton-theme { display: flex; align-items: center; gap: var(--e2); width: 100%; padding: 8px var(--e3); border: 1px solid var(--bord); border-radius: var(--r-m); background: transparent; color: var(--texte-doux); font: inherit; font-size: var(--t-sm); font-weight: 500; cursor: pointer; }
    .bouton-theme:hover { background: var(--surface-2); color: var(--texte); }
    .icone-soleil { display: none; }

    /* ---------- Zone principale ---------- */
    main { min-width: 0; padding: var(--e5) var(--e6) 64px; max-width: 1280px; width: 100%; }
    .barre-haute { display: none; }
    .scrim { display: none; }
    #banniere-etat { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e2) var(--e4); margin: 0 0 var(--e5); padding: var(--e2) var(--e4); background: var(--surface); border: 1px solid var(--bord); border-radius: var(--r-m); font-size: var(--t-sm); color: var(--texte-doux); }
    #banniere-etat .ico { color: var(--accent); }
    #banniere-etat strong { color: var(--texte); }
    .banniere-contexte { display: flex; align-items: center; gap: var(--e2); }
    .banniere-regle-courte { margin-left: auto; color: var(--texte-faible); }
    .banniere-alerte { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e2) var(--e3); background: var(--alerte-doux); border-left-color: var(--alerte); color: var(--alerte-texte); }
    .banniere-alerte .btn { margin: 0; }
    .page-entete { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: var(--e3) var(--e5); margin-bottom: var(--e5); }
    .page-entete h2 { margin: 0; }
    .page-entete .lead { margin: var(--e1) 0 0; color: var(--texte-doux); max-width: 62ch; }
    .page-actions { display: flex; flex-wrap: wrap; gap: var(--e2); }
    .titre-section { margin: var(--e6) 0 var(--e3); font-size: var(--t-md); }
    .note { font-size: var(--t-sm); color: var(--texte-faible); }
    .vue-ecran:not(.cache) { animation: entree-ecran var(--d3) var(--courbe) both; }
    @keyframes entree-ecran { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }

    /* ---------- Surfaces, par rôle ---------- */
    .carte { background: var(--surface); border: 1px solid var(--bord); border-radius: var(--r-l); padding: var(--e5); margin-bottom: var(--e5); }
    .carte > h3:first-child, .carte-entete h3 { margin-bottom: var(--e3); }
    .carte-entete { display: flex; align-items: center; justify-content: space-between; gap: var(--e3); margin-bottom: var(--e3); }
    .carte-entete h3 { margin: 0; }
    .carte-action { border-left: 4px solid var(--accent); }
    .carte-action.attente { border-left-color: var(--alerte); }
    .carte-sobre { background: transparent; border-style: dashed; }
    .panneau-texte { background: var(--surface-2); border: 1px solid var(--bord); border-radius: var(--r-m); padding: var(--e4) var(--e5); line-height: 1.6; }
    .panneau-texte > :last-child { margin-bottom: 0; }
    .banniere-regle { display: block; background: var(--accent-doux); color: var(--texte); border-left: 4px solid var(--accent); border-radius: var(--r-s) var(--r-m) var(--r-m) var(--r-s); padding: var(--e3) var(--e4); margin-bottom: var(--e4); font-size: var(--t-sm); line-height: 1.55; }
    .notif { padding: var(--e3) var(--e4); border-radius: var(--r-m); margin-bottom: var(--e3); font-size: var(--t-sm); font-weight: 600; border: 1px solid var(--bord); background: var(--surface-2); }
    .notif-ok { background: var(--bon-doux); color: var(--bon-texte); border-color: transparent; }
    .notif-err { background: var(--critique-doux); color: var(--critique-texte); border-color: transparent; }
    #zone-notification.notif {
      position: fixed; top: var(--e4); right: var(--e4); z-index: 80; margin: 0; max-width: min(440px, calc(100vw - 32px));
      background: var(--surface); color: var(--texte); border: 1px solid var(--bord); border-left-width: 4px; box-shadow: var(--ombre-flottante);
      animation: apparition var(--d3) var(--courbe) both;
    }
    #zone-notification.notif-ok { border-left-color: var(--bon); }
    #zone-notification.notif-err { border-left-color: var(--critique); }
    @keyframes apparition { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: none; } }
    .grille-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 190px), 1fr)); gap: var(--e3); margin-bottom: var(--e5); }
    .stat { background: var(--surface-2); border-radius: var(--r-l); padding: var(--e4) var(--e5); }
    .stat .valeur { font-family: var(--police-titre); font-size: var(--t-2xl); font-weight: 700; line-height: 1.1; letter-spacing: -0.02em; color: var(--texte); font-variant-numeric: tabular-nums; }
    .stat .libelle { margin-top: var(--e1); font-size: var(--t-sm); color: var(--texte-doux); line-height: 1.35; }
    .grille-form { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr)); gap: var(--e4); }
    .grille-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 340px), 1fr)); gap: var(--e4); }
    .accueil-grille { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: var(--e5); align-items: start; }
    .accueil-grille .carte { margin-bottom: 0; }
    .pile > .carte:last-child { margin-bottom: 0; }

    /* ---------- Listes d'actions et d'échéances (accueil) ---------- */
    .liste-actions, .liste-echeances { list-style: none; margin: 0; padding: 0; }
    .ligne-action { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: var(--e3); padding: var(--e3) 0; border-top: 1px solid var(--bord); }
    .ligne-action:first-child { border-top: 0; padding-top: 0; }
    .ligne-texte strong { display: block; font-weight: 600; overflow-wrap: anywhere; }
    .ligne-texte span { display: block; font-size: var(--t-sm); color: var(--texte-doux); overflow-wrap: anywhere; }
    .echeance { display: grid; grid-template-columns: 52px minmax(0, 1fr) auto; align-items: center; gap: var(--e3); padding: var(--e3) 0; border-top: 1px solid var(--bord); }
    .echeance:first-child { border-top: 0; padding-top: 0; }
    .echeance-date { text-align: center; background: var(--surface-2); border-radius: var(--r-m); padding: 6px 0; line-height: 1.1; }
    .echeance-date b { display: block; font-family: var(--police-titre); font-size: var(--t-md); }
    .echeance-date span { font-size: var(--t-xs); text-transform: uppercase; letter-spacing: 0.05em; color: var(--texte-doux); }
    .etat-vide { text-align: center; color: var(--texte-doux); padding: var(--e5) var(--e4); }
    .etat-vide .ico { width: 28px; height: 28px; color: var(--texte-faible); display: block; margin: 0 auto var(--e2); }
    .etat-vide strong { display: block; color: var(--texte); margin-bottom: var(--e1); }
    td.etat-vide { padding: var(--e6) var(--e4); }
    .pile > .etat-vide, .carte.etat-vide { background: var(--surface); border: 1px dashed var(--bord-fort); border-radius: var(--r-l); }
    .raccourcis { display: flex; flex-wrap: wrap; gap: var(--e2); }

    /* ---------- Formulaires ---------- */
    label { display: flex; flex-direction: column; gap: 6px; font-size: var(--t-sm); font-weight: 600; color: var(--texte); }
    label .requis { color: var(--critique); }
    label.case, .liste-cases label, .ligne-proc label { flex-direction: row; align-items: flex-start; gap: var(--e2); font-weight: 400; font-size: var(--t-base); }
    label.case input[type="checkbox"], .liste-cases input[type="checkbox"], .ligne-proc input[type="checkbox"], label.case input[type="radio"] { width: 18px; height: 18px; margin: 2px 0 0; padding: 0; flex: none; accent-color: var(--accent); }
    input[type="checkbox"] { accent-color: var(--accent); }
    input, select, textarea {
      width: 100%; min-height: 40px; padding: 8px var(--e3); border: 1px solid var(--bord-fort); border-radius: var(--r-m);
      background: var(--surface); color: var(--texte); font: inherit; font-size: var(--t-base); font-weight: 400;
      transition: border-color var(--d1) var(--courbe), box-shadow var(--d1) var(--courbe);
    }
    textarea { line-height: 1.5; resize: vertical; }
    input::placeholder, textarea::placeholder { color: var(--texte-faible); }
    input:hover, select:hover, textarea:hover { border-color: var(--texte-faible); }
    input:focus, select:focus, textarea:focus { outline: none; border-color: var(--accent); box-shadow: var(--anneau); }
    input:disabled, select:disabled, textarea:disabled { background: var(--surface-2); color: var(--texte-faible); cursor: not-allowed; }
    input[type="file"] { padding: 6px var(--e2); }
    fieldset { border: 0; padding: 0; margin: 0 0 var(--e5); min-width: 0; }
    fieldset legend { padding: 0; margin-bottom: var(--e3); font-family: var(--police-titre); font-weight: 700; font-size: var(--t-base); }
    .aide { font-size: var(--t-sm); color: var(--texte-faible); font-weight: 400; }
    .barre-saisie { display: flex; gap: var(--e2); align-items: stretch; flex-wrap: wrap; }
    .barre-saisie > input[type="text"], .barre-saisie > input[type="search"] { flex: 1 1 240px; width: auto; }
    details.carte > summary { cursor: pointer; font-family: var(--police-titre); font-weight: 700; font-size: var(--t-md); list-style: none; display: flex; align-items: center; justify-content: space-between; gap: var(--e3); }
    details.carte > summary::-webkit-details-marker { display: none; }
    details.carte > summary::after { content: ""; width: 8px; height: 8px; border-right: 2px solid var(--texte-doux); border-bottom: 2px solid var(--texte-doux); transform: rotate(45deg); transition: transform var(--d2) var(--courbe); }
    details.carte[open] > summary::after { transform: rotate(-135deg); }
    details.carte[open] > summary { margin-bottom: var(--e4); }

    /* ---------- Boutons : primaire, secondaire, contour, danger ---------- */
    .btn, a.btn {
      display: inline-flex; align-items: center; justify-content: center; gap: var(--e2); min-height: 40px; padding: 8px var(--e4);
      margin: 0 var(--e2) var(--e2) 0; border: 1px solid var(--bord-fort); border-radius: var(--r-m); background: var(--surface); color: var(--texte);
      font: inherit; font-size: var(--t-base); font-weight: 600; line-height: 1.2; text-decoration: none; cursor: pointer; touch-action: manipulation;
      transition: background-color var(--d1) var(--courbe), border-color var(--d1) var(--courbe), color var(--d1) var(--courbe), transform var(--d1) var(--courbe);
    }
    .btn:hover, a.btn:hover { background: var(--surface-2); color: var(--texte); border-color: var(--texte-faible); }
    .btn:active { transform: translateY(1px); }
    .btn:disabled { opacity: 0.55; cursor: not-allowed; transform: none; }
    .btn-primaire, .btn-succes, a.btn-primaire { background: var(--accent); border-color: var(--accent); color: var(--sur-accent); }
    .btn-primaire:hover, .btn-succes:hover, a.btn-primaire:hover { background: var(--accent-fort); border-color: var(--accent-fort); color: var(--sur-accent); }
    .btn-secondaire { background: var(--surface-2); border-color: transparent; }
    .btn-secondaire:hover { background: var(--surface-3); border-color: transparent; }
    .btn-contour { background: transparent; }
    .btn-danger { background: var(--critique-doux); border-color: transparent; color: var(--critique-texte); }
    .btn-danger:hover { background: var(--critique); border-color: var(--critique); color: var(--sur-accent); }
    .btn-sm { min-height: 32px; padding: 4px var(--e3); font-size: var(--t-sm); }
    .btn-icone { min-width: 40px; padding: 8px; }
    .btn-sm.btn-icone { min-width: 32px; padding: 4px; }
    .pile-actions { display: flex; flex-wrap: wrap; gap: var(--e2); margin-top: var(--e3); }
    .pile-actions .btn { margin: 0; }
    .btn-lien { background: none; border: 0; min-height: 0; padding: 0; margin: 0; color: var(--accent); font-weight: 500; text-decoration: underline; }
    .btn-lien:hover { background: none; color: var(--accent-fort); }

    /* ---------- Badges d'état : forme ET couleur ---------- */
    .badge { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px 3px 8px; border-radius: var(--r-pilule); font-size: var(--t-xs); font-weight: 600; line-height: 1.4; background: var(--surface-2); color: var(--texte-doux); white-space: nowrap; }
    .badge::before { content: ""; width: 9px; height: 9px; flex: none; border: 2px solid currentColor; border-radius: 50%; }
    .badge-ok { background: var(--bon-doux); color: var(--bon-texte); }
    .badge-ok::before { border: 0; background: currentColor; border-radius: 50%; }
    .badge-warn { background: var(--alerte-doux); color: var(--alerte-texte); }
    .badge-warn::before { border: 0; background: currentColor; border-radius: 0; clip-path: polygon(50% 0, 100% 100%, 0 100%); }
    .badge-err { background: var(--critique-doux); color: var(--critique-texte); }
    .badge-err::before { border: 0; background: currentColor; border-radius: 0; clip-path: polygon(30% 0, 70% 0, 100% 30%, 100% 70%, 70% 100%, 30% 100%, 0 70%, 0 30%); }
    .badge-info { background: var(--accent-doux); color: var(--accent-fort); }
    .badge-info::before { border: 0; background: currentColor; border-radius: 0; clip-path: polygon(50% 0, 100% 50%, 50% 100%, 0 50%); }

    /* ---------- Tableaux denses ---------- */
    .table-wrap { overflow-x: auto; border: 1px solid var(--bord); border-radius: var(--r-m); background: var(--surface); -webkit-overflow-scrolling: touch; }
    table { width: 100%; border-collapse: collapse; font-size: var(--t-base); }
    .table-wrap table { min-width: 620px; }
    th { position: sticky; top: 0; background: var(--surface-2); color: var(--texte-doux); font-size: var(--t-xs); font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase; text-align: left; padding: 10px var(--e3); border-bottom: 1px solid var(--bord); white-space: nowrap; }
    td { padding: 10px var(--e3); border-bottom: 1px solid var(--bord); vertical-align: top; }
    tbody tr:last-child td { border-bottom: 0; }
    tbody tr:hover { background: var(--surface-2); }
    tbody tr.ligne-active { background: var(--accent-doux); }
    td small { display: block; }
    td .btn { margin: 2px 4px 2px 0; }

    /* ---------- Fils de discussion, listes, détails ---------- */
    .liste-propre { margin: var(--e2) 0 var(--e3); padding-left: 20px; }
    .liste-propre li { margin-bottom: 5px; }
    li.ok { list-style: none; position: relative; margin-left: -20px; padding-left: 22px; }
    li.ok::before { content: ""; position: absolute; left: 2px; top: 0.5em; width: 5px; height: 9px; border-right: 2px solid var(--bon); border-bottom: 2px solid var(--bon); transform: rotate(40deg); }
    li.etape-terminee strong { color: var(--bon-texte); }
    li.etape-en_cours strong { color: var(--accent-fort); }
    li.etape-suspendue strong { color: var(--alerte-texte); }
    .fil-discussion, .fil-copilote { background: var(--surface-2); border: 1px solid var(--bord); border-radius: var(--r-m); padding: var(--e3); overflow-y: auto; }
    .fil-discussion { max-height: 380px; margin-bottom: var(--e3); }
    .msg { padding: var(--e3) var(--e4); border-radius: var(--r-m); margin-bottom: var(--e2); font-size: var(--t-base); line-height: 1.5; }
    .msg-op { background: var(--accent-doux); margin-left: 10%; }
    .msg-ia { background: var(--surface); border: 1px solid var(--bord); margin-right: 6%; }
    .barre-progression { width: 100%; height: 10px; background: var(--surface-3); border-radius: var(--r-pilule); overflow: hidden; margin: var(--e2) 0; }
    .barre-progression-remplie { height: 100%; background: var(--accent); border-radius: var(--r-pilule); transition: width var(--d3) var(--courbe); }
    .capture-apercu { max-width: 100%; border: 1px solid var(--bord); border-radius: var(--r-m); margin-top: var(--e3); }
    details.guide-bloc { border: 1px solid var(--bord); border-radius: var(--r-m); padding: var(--e3) var(--e4); margin-bottom: var(--e2); background: var(--surface); }
    details.guide-bloc summary { font-weight: 600; cursor: pointer; }
    details.guide-bloc[open] summary { margin-bottom: var(--e2); color: var(--accent-fort); }
    .chips { display: flex; flex-wrap: wrap; gap: var(--e2); margin: var(--e2) 0 var(--e3); }
    .puce-cmd { display: inline-flex; align-items: center; gap: 6px; background: var(--accent-doux); color: var(--accent-fort); border: 0; border-radius: var(--r-pilule); padding: 5px 12px; font: inherit; font-size: var(--t-sm); font-weight: 500; cursor: pointer; transition: background-color var(--d1) var(--courbe); }
    .puce-cmd:hover { background: var(--surface-3); }
    .point-vert-pulsant { display: inline-block; width: 9px; height: 9px; border-radius: 50%; background: var(--bon); margin-right: 8px; box-shadow: 0 0 0 0 var(--bon); animation: pouls 2s ease-out infinite; }
    @keyframes pouls { 0% { box-shadow: 0 0 0 0 rgba(76, 200, 138, 0.55); } 100% { box-shadow: 0 0 0 9px rgba(76, 200, 138, 0); } }

    /* ---------- Co-pilote navigateur ---------- */
    .workspace-cowork { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.95fr); gap: var(--e4); align-items: start; margin-top: var(--e4); }
    .cadre-navigateur-direct { border: 1px solid var(--bord-fort); border-radius: var(--r-l); background: var(--surface); overflow: hidden; }
    .barre-chrome-direct { background: var(--surface-2); padding: var(--e2) var(--e3); display: flex; align-items: center; gap: var(--e1); flex-wrap: wrap; border-bottom: 1px solid var(--bord); }
    .barre-chrome-direct .btn-nav-mini { display: inline-flex; align-items: center; justify-content: center; min-width: 32px; height: 32px; padding: 0 var(--e2); border: 1px solid var(--bord); border-radius: var(--r-s); background: var(--surface); color: var(--texte); font: inherit; font-size: var(--t-sm); font-weight: 600; cursor: pointer; }
    .barre-chrome-direct .btn-nav-mini:hover { background: var(--accent-doux); color: var(--accent-fort); }
    .url-live-input { flex: 1 1 180px; width: auto; min-height: 32px; padding: 4px var(--e3); font-family: var(--police-code); font-size: var(--t-sm); border-radius: var(--r-pilule); }
    .corps-navigateur-direct { min-height: 380px; max-height: 620px; overflow-y: auto; padding: var(--e4); }
    .corps-navigateur-direct .entete-live { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--e3); border-bottom: 1px solid var(--bord); padding-bottom: var(--e3); margin-bottom: var(--e3); }
    .iframe-navigateur-direct { width: 100%; height: 540px; border: 0; background: #ffffff; display: block; }
    .panneau-copilote-chat { background: var(--surface); border: 1px solid var(--bord-fort); border-radius: var(--r-l); padding: var(--e4); display: flex; flex-direction: column; gap: var(--e3); min-width: 0; }
    .panneau-copilote-chat .entete-chat { display: flex; justify-content: space-between; align-items: center; gap: var(--e2); }
    .fil-copilote { max-height: 340px; min-height: 160px; display: flex; flex-direction: column; gap: var(--e2); }
    .bulle-copilote-user { align-self: flex-end; background: var(--accent); color: var(--sur-accent); padding: 8px var(--e3); border-radius: var(--r-l) var(--r-l) var(--r-s) var(--r-l); font-size: var(--t-sm); max-width: 88%; }
    .bulle-copilote-ia { align-self: flex-start; background: var(--surface); color: var(--texte); border: 1px solid var(--bord); padding: 10px var(--e3); border-radius: var(--r-l) var(--r-l) var(--r-l) var(--r-s); font-size: var(--t-sm); max-width: 95%; line-height: 1.5; }
    .grille-dom-live { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 220px), 1fr)); gap: var(--e2); margin-top: var(--e2); }
    .carte-dom-item { background: var(--surface-2); border: 1px solid var(--bord); border-radius: var(--r-m); padding: var(--e2) var(--e3); font-size: var(--t-sm); display: flex; flex-direction: column; gap: 5px; }
    .etapes-actions { display: flex; flex-wrap: wrap; gap: var(--e2); margin: var(--e3) 0 0; }
    .etapes-actions .btn { margin: 0; }
    .titre-mini { margin: var(--e4) 0 var(--e1); font-size: var(--t-sm); font-weight: 600; color: var(--texte-doux); }

    /* ---------- Vœux, procédures, assistant IA ---------- */
    .voeu { border: 1px solid var(--bord); border-radius: var(--r-m); padding: var(--e4); margin-bottom: var(--e3); background: var(--surface); }
    .voeu-entete { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--e3); flex-wrap: wrap; margin-bottom: var(--e2); }
    .voeu textarea { min-height: 180px; }
    .voeu-compteur, .ia-compteur { font-size: var(--t-sm); color: var(--texte-faible); margin: var(--e1) 0 var(--e2); }
    .voeu-compteur.depasse, .ia-compteur.depasse { color: var(--critique); font-weight: 600; }
    .voeu-alertes { font-size: var(--t-sm); margin: var(--e2) 0; padding-left: 18px; color: var(--alerte-texte); }
    .ligne-proc { display: flex; flex-wrap: wrap; gap: var(--e2); align-items: center; background: var(--surface-2); border: 1px solid var(--bord); border-radius: var(--r-m); padding: var(--e2) var(--e3); margin-bottom: var(--e2); }
    .ligne-proc input[type="text"], .ligne-proc input[type="number"] { flex: 1 1 160px; width: auto; min-width: 120px; }
    .ligne-proc .large { flex: 3 1 260px; }
    .liste-cases { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 260px), 1fr)); gap: var(--e2); }
    fieldset#fs-editeur { margin: 0; }
    .ia-statut { display: inline-block; font-size: var(--t-sm); color: var(--texte-doux); background: var(--surface); border: 1px solid var(--bord); border-radius: var(--r-pilule); padding: 4px var(--e3); margin: 0 0 var(--e4); }
    .ia-texte-source { min-height: 200px; }
    .ia-reponse { white-space: pre-wrap; line-height: 1.55; }
    .ia-mention { font-size: var(--t-sm); color: var(--texte-faible); margin-top: var(--e2); }

    /* ---------- Étroit : navigation repliable, gouttière de 16px ---------- */
    @media (max-width: 1100px) {
      .workspace-cowork { grid-template-columns: minmax(0, 1fr); }
      .accueil-grille { grid-template-columns: minmax(0, 1fr); }
    }
    @media (max-width: 900px) {
      body { display: block; }
      .barre-haute { display: flex; align-items: center; gap: var(--e3); position: sticky; top: 0; z-index: 40; padding: var(--e2) var(--e4); background: var(--surface); border-bottom: 1px solid var(--bord); }
      .barre-haute .marque { padding: 0; flex: 1; }
      .barre-haute .btn { margin: 0; }
      aside#navigation-principale {
        position: fixed; z-index: 60; left: 0; top: 0; bottom: 0; width: min(300px, 86vw); height: auto;
        transform: translateX(-102%); visibility: hidden; box-shadow: var(--ombre-flottante);
        transition: transform var(--d2) var(--courbe), visibility 0s linear var(--d2);
      }
      aside#navigation-principale .marque { display: none; }
      body.nav-ouverte aside#navigation-principale { transform: none; visibility: visible; transition: transform var(--d2) var(--courbe), visibility 0s; }
      body.nav-ouverte .scrim { display: block; position: fixed; inset: 0; z-index: 50; background: rgba(10, 12, 26, 0.5); border: 0; }
      main { padding: var(--e4) var(--e4) var(--e7); }
      #banniere-etat { margin-bottom: var(--e4); }
      .banniere-regle-courte { margin-left: 0; }
      #zone-notification.notif { left: var(--e4); right: var(--e4); top: auto; bottom: var(--e4); max-width: none; }
      .carte { padding: var(--e4); }
      h2 { font-size: var(--t-lg); }
      .stat .valeur { font-size: var(--t-xl); }
      .ligne-action { grid-template-columns: minmax(0, 1fr); gap: var(--e2); }
      .ligne-action .btn { justify-self: start; margin: 0; }
      .echeance { grid-template-columns: 52px minmax(0, 1fr); }
      .echeance .badge { grid-column: 2; justify-self: start; }
      .iframe-navigateur-direct { height: 420px; }
    }
    @media (prefers-color-scheme: dark) {
      :root:not([data-theme="light"]) .icone-lune { display: none; }
      :root:not([data-theme="light"]) .icone-soleil { display: inline; }
    }
    :root[data-theme="dark"] .icone-lune { display: none; }
    :root[data-theme="dark"] .icone-soleil { display: inline; }
    :root[data-theme="light"] .icone-lune { display: inline; }
    :root[data-theme="light"] .icone-soleil { display: none; }

    /* ---------- Accessibilité ---------- */
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { animation-duration: 1ms !important; animation-iteration-count: 1 !important; transition-duration: 1ms !important; scroll-behavior: auto !important; }
      .point-vert-pulsant { animation: none; }
    }
    @media (prefers-contrast: more) {
      :root { --bord: #6b7390; --bord-fort: #4b5370; }
    }
"""


def construire_css() -> str:
    """Assemble : tokens clairs, redéfinition sombre (système puis choix explicite), composants."""
    return (
        _RACINE
        + TOKENS_CLAIR
        + "    }\n"
        + "    @media (prefers-color-scheme: dark) {\n"
        + '      :root:not([data-theme="light"]) {\n        color-scheme: dark;'
        + TOKENS_SOMBRE
        + "      }\n    }\n"
        + '    :root[data-theme="dark"] {\n      color-scheme: dark;'
        + TOKENS_SOMBRE
        + "    }\n"
        + CSS_BASE
    )


CSS_DESIGN = construire_css()
