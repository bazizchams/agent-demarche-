"""Feuille de style unique de l'interface : tokens (clair et sombre), coquille, composants, écrans.

Direction : outil de bureau d'études, sobre et dense. Indigo profond comme accent unique, neutres
gris-bleu teintés vers cet indigo, cartes blanches arrondies à ombre très douce. La sémantique
(bon, alerte, critique) reste distincte de l'accent et s'exprime par la forme ET la couleur.
Le thème sombre est redessiné (surfaces bleu nuit étagées, indigo plus lumineux), pas inversé.

Les noms hérités (--bleu-primaire, --carte, --bordure...) restent définis comme alias, et les
classes des écrans existants sont conservées : la référence des composants est GUIDE_DESIGN.md.
Aucun antislash dans ces chaînes : les tests comptent les antislash de la page servie.
"""

from __future__ import annotations

from app.interface.design.motion import CSS_MOUVEMENT

LIEN_POLICES = (
    '<link rel="preconnect" href="https://fonts.googleapis.com" />\n'
    '  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />\n'
    '  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700"
    '&amp;family=Inter:wght@400;500;600;700&amp;display=swap" />'
)

# Couleurs du thème clair : neutres teintés indigo (teinte ~240), accent indigo profond.
TOKENS_CLAIR = """
      --fond: #f3f4f9;
      --fond-creux: #eceef6;
      --surface: #ffffff;
      --surface-2: #f2f3f9;
      --surface-3: #e5e7f2;
      --bord: #e2e4ef;
      --bord-fort: #c9cde0;
      --bord-champ: #7b82a3;
      --texte: #141831;
      --texte-doux: #454c6c;
      --texte-faible: #565c80;
      --accent: #3730a3;
      --accent-fort: #2a2384;
      --accent-doux: #ebeafc;
      --accent-moyen: #cfccf6;
      --accent-plein: #3730a3;
      --accent-plein-survol: #2c2589;
      --sur-accent: #ffffff;
      --marque-fond: #2f2994;
      --marque-fond-2: #3d36b4;
      --sur-marque: #ffffff;
      --sur-marque-doux: #d6d4fa;
      --bon: #177a46;
      --bon-doux: #e1f4e9;
      --bon-texte: #115f37;
      --alerte: #a65800;
      --alerte-doux: #fdf1db;
      --alerte-texte: #7a4100;
      --critique: #c0262d;
      --critique-doux: #fde9e9;
      --critique-texte: #961920;
      --voile: rgba(16, 18, 40, 0.48);
      --ombre-1: 0 1px 2px rgba(20, 24, 49, 0.05), 0 1px 1px rgba(20, 24, 49, 0.03);
      --ombre-2: 0 1px 2px rgba(20, 24, 49, 0.06), 0 6px 16px -4px rgba(20, 24, 49, 0.08);
      --ombre-flottante: 0 18px 40px -8px rgba(20, 24, 49, 0.22), 0 4px 10px rgba(20, 24, 49, 0.08);
      --anneau: 0 0 0 3px rgba(55, 48, 163, 0.25);
      --miroitement: rgba(255, 255, 255, 0.65);
"""

# Thème sombre : bleu nuit étagé (le plus clair = le plus proche), indigo éclairci pour le texte,
# indigo saturé pour les boutons pleins (texte blanc, contraste AA conservé).
TOKENS_SOMBRE = """
      --fond: #0c0e1d;
      --fond-creux: #090b17;
      --surface: #14172e;
      --surface-2: #1b1f3c;
      --surface-3: #262b50;
      --bord: #252a4b;
      --bord-fort: #3a406e;
      --bord-champ: #7a80ad;
      --texte: #e9eaf8;
      --texte-doux: #b1b5d6;
      --texte-faible: #8f94ba;
      --accent: #aba7ff;
      --accent-fort: #c9c6ff;
      --accent-doux: #232158;
      --accent-moyen: #36337a;
      --accent-plein: #4f46e5;
      --accent-plein-survol: #5b52ef;
      --sur-accent: #ffffff;
      --marque-fond: #1d1960;
      --marque-fond-2: #2a2584;
      --sur-marque: #ffffff;
      --sur-marque-doux: #c3c0f2;
      --bon: #6cba97;
      --bon-doux: rgba(108, 186, 151, 0.12);
      --bon-texte: #9ad9b8;
      --alerte: #e0a257;
      --alerte-doux: rgba(224, 162, 87, 0.12);
      --alerte-texte: #f2c98a;
      --critique: #f07a80;
      --critique-doux: rgba(240, 122, 128, 0.12);
      --critique-texte: #ffa8ab;
      --voile: rgba(3, 4, 12, 0.66);
      --ombre-1: 0 1px 2px rgba(0, 0, 0, 0.35);
      --ombre-2: 0 1px 2px rgba(0, 0, 0, 0.4), 0 8px 20px -6px rgba(0, 0, 0, 0.45);
      --ombre-flottante: 0 22px 48px -10px rgba(0, 0, 0, 0.7), 0 4px 12px rgba(0, 0, 0, 0.45);
      --anneau: 0 0 0 3px rgba(171, 167, 255, 0.32);
      --miroitement: rgba(255, 255, 255, 0.06);
"""

_RACINE = """
    :root {
      color-scheme: light;
      /* Typographie : titres caractérisés, texte courant très lisible, piles de secours */
      --police-titre: "Bricolage Grotesque", "Segoe UI Variable Display", "Segoe UI", system-ui, sans-serif;
      --police-texte: Inter, "Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, sans-serif;
      --police-code: ui-monospace, "Cascadia Mono", Consolas, monospace;
      /* Échelle typographique (rapport ~1.2, base 15px) */
      --t-xs: 0.8125rem; --t-sm: 0.875rem; --t-base: 0.9375rem; --t-md: 1.0625rem;
      --t-lg: 1.3125rem; --t-xl: 1.75rem; --t-2xl: 2.25rem; --t-3xl: 2.75rem;
      /* Espacements (grille de 4px) */
      --e1: 4px; --e2: 8px; --e3: 12px; --e4: 16px; --e5: 24px; --e6: 32px; --e7: 48px; --e8: 64px;
      /* Rayons */
      --r-s: 6px; --r-m: 10px; --r-l: 14px; --r-xl: 20px; --r-pilule: 999px;
      /* Tailles de contrôle (cible tactile >= 40px) */
      --h-ctrl-sm: 32px; --h-ctrl: 40px; --h-ctrl-lg: 48px;
      /* Durées et courbe */
      --d1: 150ms; --d2: 200ms; --d3: 320ms;
      --courbe: cubic-bezier(0.2, 0.7, 0.2, 1);
      --largeur-nav: 264px;
      --largeur-contenu: 1280px;
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
    ::selection { background: var(--accent-moyen); color: var(--texte); }
    a { color: var(--accent); text-underline-offset: 2px; }
    a:hover { color: var(--accent-fort); }
    code { font-family: var(--police-code); font-size: 0.88em; background: var(--surface-2); padding: 1px 6px; border-radius: var(--r-s); }
    h1, h2, h3, h4 { font-family: var(--police-titre); color: var(--texte); margin: 0; font-weight: 700; letter-spacing: -0.015em; line-height: 1.2; text-wrap: balance; }
    h2 { font-size: var(--t-xl); }
    h3 { font-size: var(--t-md); letter-spacing: -0.005em; }
    h4 { font-size: var(--t-base); margin: var(--e5) 0 var(--e2); }
    p { margin: 0 0 var(--e3); }
    small { font-size: var(--t-sm); color: var(--texte-doux); }
    .cache { display: none !important; }
    .sr-only { position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; border: 0; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
    .sr-focus { position: absolute; left: -9999px; top: var(--e2); z-index: 100; padding: var(--e2) var(--e4); border-radius: var(--r-m); background: var(--accent-plein); color: var(--sur-accent); font-weight: 600; text-decoration: none; }
    .sr-focus:focus, .sr-focus:focus-visible { position: fixed; left: var(--e4); top: var(--e4); }
    main:focus, .vue-ecran h2[tabindex="-1"]:focus { outline: none; }
    :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: var(--r-s); }
    .ico { width: 1.15em; height: 1.15em; stroke: currentColor; fill: none; stroke-width: 1.75; stroke-linecap: round; stroke-linejoin: round; flex: none; }
    .surtitre { display: block; font-size: var(--t-sm); font-weight: 600; color: var(--texte-faible); }
    .chiffres { font-variant-numeric: tabular-nums; }

    /* ---------- Navigation latérale ---------- */
    aside#navigation-principale {
      position: sticky; top: 0; align-self: start; height: 100vh; height: 100dvh; overflow-y: auto;
      display: flex; flex-direction: column; gap: var(--e4); padding: var(--e4) var(--e3) 0;
      background: var(--surface); border-right: 1px solid var(--bord);
    }
    aside#navigation-principale nav { display: flex; flex-direction: column; gap: var(--e2); }
    .marque { display: flex; align-items: center; gap: var(--e3); padding: var(--e1) var(--e2) var(--e2); }
    .marque-logo { width: 36px; height: 36px; border-radius: var(--r-m); background: var(--accent-plein); color: var(--sur-accent); display: grid; place-items: center; flex: none; box-shadow: inset 0 -2px 0 rgba(0, 0, 0, 0.18); }
    .marque-logo .ico { width: 20px; height: 20px; }
    .marque-nom { font-family: var(--police-titre); font-weight: 700; font-size: 1rem; line-height: 1.15; letter-spacing: -0.015em; }
    .marque-sous { display: block; font-family: var(--police-texte); font-weight: 500; font-size: var(--t-xs); color: var(--texte-faible); letter-spacing: 0; margin-top: 2px; }
    .nav-groupe { display: flex; flex-direction: column; gap: 2px; }
    .nav-titre { margin: 0; padding: var(--e2) var(--e3) 2px; font-size: var(--t-xs); font-weight: 600; letter-spacing: 0.07em; text-transform: uppercase; color: var(--texte-faible); }
    aside button.nav-btn {
      position: relative; display: flex; align-items: center; gap: var(--e3); width: 100%; min-height: var(--h-ctrl); text-align: left;
      padding: 8px var(--e3); border: 0; border-radius: var(--r-m); background: transparent; color: var(--texte-doux);
      font: inherit; font-size: var(--t-base); font-weight: 500; line-height: 1.25; cursor: pointer;
      transition: background-color var(--d1) var(--courbe), color var(--d1) var(--courbe);
    }
    aside button.nav-btn .ico { width: 18px; height: 18px; color: var(--texte-faible); transition: color var(--d1) var(--courbe); }
    aside button.nav-btn:hover { background: var(--surface-2); color: var(--texte); }
    aside button.nav-btn:hover .ico { color: var(--texte-doux); }
    aside button.nav-btn.actif { background: var(--accent-doux); color: var(--accent-fort); font-weight: 600; }
    aside button.nav-btn.actif .ico { color: var(--accent); }
    aside button.nav-btn::before { content: ""; position: absolute; left: -12px; top: 9px; bottom: 9px; width: 3px; border-radius: 0 3px 3px 0; background: var(--accent); transform: scaleY(0); transition: transform var(--d2) var(--courbe); }
    aside button.nav-btn.actif::before { transform: scaleY(1); }
    .nav-compteur { margin-left: auto; min-width: 22px; padding: 1px 7px; border-radius: var(--r-pilule); background: var(--alerte-doux); color: var(--alerte-texte); font-size: var(--t-xs); font-weight: 700; text-align: center; font-variant-numeric: tabular-nums; }
    .nav-pied { margin-top: auto; position: sticky; bottom: 0; z-index: 2; display: flex; flex-direction: column; gap: var(--e2); padding: var(--e3) 0 max(var(--e3), env(safe-area-inset-bottom, 0px)); background: var(--surface); border-top: 1px solid var(--bord); }
    .session-carte { display: flex; align-items: center; gap: var(--e3); padding: var(--e2); border-radius: var(--r-m); background: var(--surface-2); }
    .avatar { width: 34px; height: 34px; border-radius: 50%; display: grid; place-items: center; flex: none; background: var(--accent-doux); color: var(--accent); }
    .avatar .ico { width: 18px; height: 18px; }
    .session-etat { display: flex; flex-direction: column; min-width: 0; font-size: var(--t-sm); color: var(--texte-doux); line-height: 1.3; }
    .session-etat .ico { color: var(--texte-faible); }
    #etat-utilisateur { font-weight: 600; color: var(--texte); overflow-wrap: anywhere; }
    .session-sous { font-size: var(--t-xs); color: var(--texte-faible); }
    #bloc-connexion { display: flex; flex-direction: column; gap: var(--e1); }
    #btn-se-deconnecter { justify-content: flex-start; width: 100%; }
    .session-form summary { cursor: pointer; font-size: var(--t-sm); color: var(--accent); padding: var(--e1) 0; }
    .session-form .grille-form { gap: var(--e2); }
    .session-actions { display: flex; gap: var(--e2); flex-wrap: wrap; align-items: center; }
    .session-actions .btn { margin: 0; }
    .bouton-theme { display: flex; align-items: center; gap: var(--e2); width: 100%; min-height: var(--h-ctrl); padding: 8px var(--e3); border: 1px solid var(--bord); border-radius: var(--r-m); background: transparent; color: var(--texte-doux); font: inherit; font-size: var(--t-sm); font-weight: 500; cursor: pointer; transition: background-color var(--d1) var(--courbe), color var(--d1) var(--courbe); }
    .bouton-theme:hover { background: var(--surface-2); color: var(--texte); }
    .icone-soleil { display: none; }
    .icone-lune, .icone-soleil { line-height: 0; }

    /* ---------- Zone principale et barre de contexte ---------- */
    main { min-width: 0; padding: var(--e5) var(--e6) var(--e8); max-width: var(--largeur-contenu); width: 100%; justify-self: center; }
    .barre-haute { display: none; }
    .scrim { display: none; }
    aside#navigation-principale .nav-fermer { display: none; }
    #banniere-etat {
      display: flex; flex-wrap: wrap; align-items: center; gap: var(--e2) var(--e4); margin: 0 0 var(--e5);
      padding: var(--e2) var(--e2) var(--e2) var(--e2); background: var(--surface); border: 1px solid var(--bord);
      border-radius: var(--r-l); box-shadow: var(--ombre-1); font-size: var(--t-sm); color: var(--texte-doux);
    }
    #banniere-etat strong { color: var(--texte); }
    #banniere-etat .btn { margin: 0; }
    .banniere-contexte { display: flex; align-items: center; gap: var(--e3); min-width: 0; padding-right: var(--e3); }
    .banniere-pastille { width: 34px; height: 34px; border-radius: var(--r-m); display: grid; place-items: center; flex: none; background: var(--accent-doux); color: var(--accent); }
    .banniere-pastille .ico { width: 18px; height: 18px; }
    .banniere-dossier { display: flex; flex-direction: column; line-height: 1.25; min-width: 0; }
    .banniere-dossier strong { font-size: var(--t-base); font-weight: 600; overflow-wrap: anywhere; }
    .banniere-regle-courte { margin-left: auto; display: flex; align-items: center; gap: var(--e2); padding: 6px var(--e3); border-radius: var(--r-pilule); background: var(--bon-doux); color: var(--bon-texte); font-weight: 500; }
    .banniere-regle-courte .ico { width: 16px; height: 16px; }
    .banniere-alerte, .banniere-regle.banniere-alerte { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e2) var(--e3); background: var(--alerte-doux); border-left-color: var(--alerte); color: var(--alerte-texte); }
    .banniere-alerte .btn { margin: 0; }
    .bandeau-fin { display: flex; align-items: center; gap: var(--e2) var(--e3); min-height: 40px; margin: 0 0 var(--e4); padding: 4px var(--e2) 4px var(--e3); border-radius: var(--r-m); background: var(--alerte-doux); color: var(--alerte-texte); font-size: var(--t-sm); }
    .bandeau-fin .ico { width: 18px; height: 18px; }
    .bandeau-fin > span { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .bandeau-fin .btn { margin: 0; flex: none; }
    .bandeau-fin .btn-lien { color: var(--alerte-texte); font-weight: 600; }
    .bandeau-fin .btn-fantome { color: var(--alerte-texte); }
    .page-entete { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: var(--e3) var(--e5); margin-bottom: var(--e5); }
    .page-entete h2 { margin: 0; }
    .page-entete .lead { margin: var(--e1) 0 0; color: var(--texte-doux); max-width: 62ch; }
    .page-actions { display: flex; flex-wrap: wrap; gap: var(--e2); }
    .page-actions .btn { margin: 0; }
    .titre-section { margin: var(--e6) 0 var(--e3); font-size: var(--t-md); }
    .note { font-size: var(--t-sm); color: var(--texte-faible); }
    .vue-ecran:not(.cache) { animation: entree-ecran var(--d3) var(--courbe) both; }
    @keyframes entree-ecran { from { opacity: 0.4; transform: translateY(4px); } to { opacity: 1; transform: none; } }
"""

CSS_CONNEXION = """
    /* ---------- Écran de connexion (affiché tant qu'aucune session n'est ouverte) ---------- */
    #ecran-connexion { display: none; }
    body.hors-session #ecran-connexion { display: grid; }
    body.hors-session main:has(#vue-tableau-bord.cache) #ecran-connexion { display: none; }
    body.hors-session #vue-tableau-bord, body.hors-session #banniere-etat { display: none !important; }
    body.hors-session aside#navigation-principale nav { opacity: 0.28; user-select: none; }
    .connexion {
      grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr); min-height: min(720px, calc(100dvh - 72px));
      background: var(--surface); border: 1px solid var(--bord); border-radius: var(--r-xl); box-shadow: var(--ombre-2); overflow: hidden;
      animation: entree-ecran var(--d3) var(--courbe) both;
    }
    .connexion-form { display: flex; flex-direction: column; justify-content: center; gap: var(--e5); padding: var(--e7) clamp(24px, 5vw, 64px); }
    .connexion-form > * { width: 100%; max-width: 400px; }
    .connexion-entete { display: flex; flex-direction: column; gap: var(--e2); }
    .connexion-entete h2 { font-size: var(--t-2xl); letter-spacing: -0.025em; }
    .connexion-entete p { margin: 0; color: var(--texte-doux); }
    .connexion-champs { display: flex; flex-direction: column; gap: var(--e4); }
    .connexion-champs .btn { margin: 0; width: 100%; }
    .connexion-ligne { display: flex; justify-content: space-between; align-items: center; gap: var(--e3); flex-wrap: wrap; font-size: var(--t-sm); }
    .connexion-pied { display: flex; align-items: flex-start; gap: var(--e2); font-size: var(--t-sm); color: var(--texte-faible); padding-top: var(--e4); border-top: 1px solid var(--bord); }
    .connexion-pied .ico { margin-top: 2px; }
    .connexion-marque {
      position: relative; display: flex; flex-direction: column; justify-content: space-between; gap: var(--e6);
      padding: var(--e7) clamp(24px, 4vw, 56px); color: var(--sur-marque); overflow: hidden; isolation: isolate;
      background: radial-gradient(120% 90% at 100% 0%, var(--marque-fond-2) 0%, var(--marque-fond) 60%);
    }
    .connexion-marque::before {
      content: ""; position: absolute; inset: 0; z-index: -1; opacity: 0.5;
      background-image: linear-gradient(rgba(255, 255, 255, 0.07) 1px, transparent 1px), linear-gradient(90deg, rgba(255, 255, 255, 0.07) 1px, transparent 1px);
      background-size: 32px 32px; mask-image: linear-gradient(160deg, #000 10%, transparent 75%); -webkit-mask-image: linear-gradient(160deg, #000 10%, transparent 75%);
    }
    .connexion-marque .marque { padding: 0; }
    .connexion-marque .marque-logo { background: rgba(255, 255, 255, 0.14); color: var(--sur-marque); box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.22); }
    .connexion-marque .marque-sous { color: var(--sur-marque-doux); }
    .connexion-accroche { font-family: var(--police-titre); font-size: clamp(1.5rem, 2.4vw, 2.125rem); font-weight: 700; line-height: 1.15; letter-spacing: -0.02em; color: var(--sur-marque); max-width: 22ch; margin: 0; text-wrap: balance; }
    .connexion-arguments { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--e4); }
    .connexion-arguments li { display: grid; grid-template-columns: 40px minmax(0, 1fr); gap: var(--e3); align-items: start; }
    .connexion-arguments .argument-icone { width: 40px; height: 40px; border-radius: var(--r-m); display: grid; place-items: center; background: rgba(255, 255, 255, 0.12); box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.18); }
    .connexion-arguments strong { display: block; font-weight: 600; color: var(--sur-marque); }
    .connexion-arguments span { display: block; font-size: var(--t-sm); color: var(--sur-marque-doux); line-height: 1.5; }
    .puce-marque { display: inline-flex; align-items: center; gap: 6px; padding: 2px 10px; border-radius: var(--r-pilule); background: rgba(255, 255, 255, 0.16); color: var(--sur-marque); font-size: var(--t-xs); font-weight: 600; white-space: nowrap; }
"""

CSS_COMPOSANTS = """
    /* ---------- Surfaces, par rôle ---------- */
    .carte { background: var(--surface); border: 1px solid var(--bord); border-radius: var(--r-l); padding: var(--e5); margin-bottom: var(--e5); box-shadow: var(--ombre-1); }
    .carte > h3:first-child, .carte-entete h3 { margin-bottom: var(--e3); }
    .carte-entete { display: flex; align-items: center; justify-content: space-between; gap: var(--e3); margin-bottom: var(--e4); }
    .carte-entete h3 { margin: 0; }
    .carte-entete .btn { margin: 0; }
    .carte-pied { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: var(--e3); margin-top: var(--e4); padding-top: var(--e4); border-top: 1px solid var(--bord); }
    .carte-pied .btn { margin: 0; }
    .carte-action { border-left: 4px solid var(--accent); }
    .carte-action.attente { border-left-color: var(--alerte); }
    .carte-sobre { background: transparent; border-style: dashed; box-shadow: none; }
    .carte-cliquable { cursor: pointer; transition: border-color var(--d1) var(--courbe), box-shadow var(--d1) var(--courbe), transform var(--d1) var(--courbe); }
    .carte-cliquable:hover { border-color: var(--accent-moyen); box-shadow: var(--ombre-2); transform: translateY(-1px); }
    .panneau-texte { background: var(--surface-2); border: 1px solid var(--bord); border-radius: var(--r-m); padding: var(--e4) var(--e5); line-height: 1.6; }
    .panneau-texte > :last-child { margin-bottom: 0; }
    .banniere-regle { display: block; background: var(--accent-doux); color: var(--texte); border-left: 4px solid var(--accent); border-radius: var(--r-s) var(--r-m) var(--r-m) var(--r-s); padding: var(--e3) var(--e4); margin-bottom: var(--e4); font-size: var(--t-sm); line-height: 1.55; }

    /* ---------- En-têtes de section ---------- */
    .section-entete { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: var(--e2) var(--e4); margin: var(--e6) 0 var(--e3); }
    .section-entete h3 { font-size: var(--t-md); margin: 0; }
    .section-entete p { margin: 2px 0 0; font-size: var(--t-sm); color: var(--texte-doux); max-width: 65ch; }
    .section-entete .btn { margin: 0; }

    /* ---------- Notifications et toasts ---------- */
    .notif { padding: var(--e3) var(--e4); border-radius: var(--r-m); margin-bottom: var(--e3); font-size: var(--t-sm); font-weight: 600; border: 1px solid var(--bord); background: var(--surface-2); }
    .notif-ok { background: var(--bon-doux); color: var(--bon-texte); border-color: transparent; }
    .notif-err { background: var(--critique-doux); color: var(--critique-texte); border-color: transparent; }
    #zone-notification { position: fixed; bottom: calc(var(--e4) + env(safe-area-inset-bottom, 0px)); right: var(--e4); z-index: 35; display: flex; flex-direction: column; gap: var(--e2); max-width: min(420px, calc(100vw - 32px)); pointer-events: none; }
    #zone-notification > div { display: flex; flex-direction: column; gap: var(--e2); }
    #zone-notification .toast { position: relative; inset: auto; max-width: none; pointer-events: auto; align-items: center; }
    #zone-notification .toast .notif-texte { flex: 1 1 auto; min-width: 0; overflow-wrap: anywhere; }
    #zone-notification .toast .btn { margin: -4px 0; flex: none; }
    .toast {
      position: fixed; top: var(--e4); right: var(--e4); z-index: 80; margin: 0; max-width: min(420px, calc(100vw - 32px));
      display: flex; align-items: flex-start; gap: var(--e3); padding: var(--e3) var(--e4) var(--e3) var(--e3);
      background: var(--surface); color: var(--texte); border: 1px solid var(--bord); border-radius: var(--r-l); box-shadow: var(--ombre-flottante);
      font-weight: 500; line-height: 1.45; animation: apparition var(--d3) var(--courbe) both;
    }
    .toast::before { content: ""; width: 10px; height: 10px; margin-top: 5px; flex: none; border-radius: 50%; background: var(--accent); box-shadow: 0 0 0 4px var(--accent-doux); }
    .toast-ok::before { background: var(--bon); box-shadow: 0 0 0 4px var(--bon-doux); }
    .toast-err::before { background: var(--critique); box-shadow: 0 0 0 4px var(--critique-doux); border-radius: 2px; transform: rotate(45deg); }
    @keyframes apparition { from { opacity: 0; transform: translateY(-8px) scale(0.98); } to { opacity: 1; transform: none; } }

    /* ---------- Chiffres clés ---------- */
    .grille-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 190px), 1fr)); gap: var(--e3); margin-bottom: var(--e5); }
    .stat { background: var(--surface-2); border-radius: var(--r-l); padding: var(--e4) var(--e5); }
    .stat .valeur, .kpi .valeur { font-family: var(--police-titre); font-size: var(--t-2xl); font-weight: 700; line-height: 1.05; letter-spacing: -0.03em; color: var(--texte); font-variant-numeric: tabular-nums; }
    .stat .libelle { margin-top: var(--e1); font-size: var(--t-sm); color: var(--texte-doux); line-height: 1.35; }
    .grille-kpi { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 150px), 1fr)); gap: var(--e3); margin-bottom: var(--e5); }
    .kpi { display: flex; flex-direction: column; gap: var(--e3); padding: var(--e4) var(--e5) var(--e5); background: var(--surface); border: 1px solid var(--bord); border-radius: var(--r-l); box-shadow: var(--ombre-1); min-width: 0; }
    .kpi-entete { display: flex; align-items: center; justify-content: space-between; gap: var(--e2); font-size: var(--t-sm); font-weight: 500; color: var(--texte-doux); }
    .kpi-icone { width: 32px; height: 32px; border-radius: var(--r-m); display: grid; place-items: center; flex: none; background: var(--accent-doux); color: var(--accent); }
    .kpi-icone .ico { width: 17px; height: 17px; }
    .kpi-alerte .kpi-icone { background: var(--alerte-doux); color: var(--alerte-texte); }
    .kpi-ok .kpi-icone { background: var(--bon-doux); color: var(--bon-texte); }
    .kpi .valeur { min-height: 1.05em; }
    .kpi-aide { margin: 0; font-size: var(--t-xs); color: var(--texte-faible); line-height: 1.4; }

    /* ---------- Grilles ---------- */
    .grille-form { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr)); gap: var(--e4); }
    .grille-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 340px), 1fr)); gap: var(--e4); }
    .accueil-grille { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr); gap: var(--e4); align-items: start; }
    .accueil-grille .carte { margin-bottom: 0; }
    .pile > .carte:last-child { margin-bottom: 0; }

    /* ---------- Listes d'actions, d'échéances et de tâches ---------- */
    .liste-actions, .liste-echeances, .liste-taches { list-style: none; margin: 0; padding: 0; }
    .ligne-action { display: grid; grid-template-columns: minmax(118px, auto) minmax(0, 1fr) auto; align-items: center; gap: var(--e3); padding: var(--e3) 0; border-top: 1px solid var(--bord); }
    .ligne-action:first-child { border-top: 0; padding-top: 0; }
    .ligne-action:last-child { padding-bottom: 0; }
    .ligne-action .badge { justify-self: start; }
    .ligne-action .btn { margin: 0; }
    .ligne-texte { min-width: 0; }
    .ligne-texte strong { display: block; font-weight: 600; overflow-wrap: anywhere; }
    .ligne-texte span { display: block; font-size: var(--t-sm); color: var(--texte-doux); overflow-wrap: anywhere; }
    .echeance { display: grid; grid-template-columns: 52px minmax(0, 1fr) auto; align-items: center; gap: var(--e3); padding: var(--e3) 0; border-top: 1px solid var(--bord); }
    .echeance:first-child { border-top: 0; padding-top: 0; }
    .echeance:last-child { padding-bottom: 0; }
    .echeance-date { text-align: center; background: var(--surface-2); border: 1px solid var(--bord); border-radius: var(--r-m); padding: 6px 0 5px; line-height: 1.05; }
    .echeance-date b { display: block; font-family: var(--police-titre); font-size: var(--t-lg); font-variant-numeric: tabular-nums; }
    .echeance-date span { font-size: var(--t-xs); color: var(--texte-doux); }
    .tache { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: var(--e3); padding: var(--e3) 0; border-top: 1px solid var(--bord); }
    .tache:first-child { border-top: 0; }
    .tache input[type="checkbox"] { width: 20px; height: 20px; min-height: 0; margin: 0; padding: 0; }
    .tache-titre { display: block; font-weight: 600; overflow-wrap: anywhere; }
    .tache-meta { display: block; font-size: var(--t-sm); color: var(--texte-doux); }
    .tache.faite .tache-titre { color: var(--texte-faible); text-decoration: line-through; text-decoration-thickness: 1px; }
    .raccourcis { display: flex; flex-wrap: wrap; gap: var(--e2); }
    .raccourcis .btn { margin: 0; }
    .grille-raccourcis { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 210px), 1fr)); gap: var(--e3); }
    .raccourci {
      display: grid; grid-template-columns: 40px minmax(0, 1fr) auto; align-items: center; gap: var(--e3); width: 100%; min-height: 72px; text-align: left;
      padding: var(--e3) var(--e4) var(--e3) var(--e3); background: var(--surface); border: 1px solid var(--bord); border-radius: var(--r-l); box-shadow: var(--ombre-1);
      color: var(--texte); font: inherit; cursor: pointer; text-decoration: none;
      transition: border-color var(--d1) var(--courbe), box-shadow var(--d1) var(--courbe), transform var(--d1) var(--courbe);
    }
    .raccourci:hover { border-color: var(--accent-moyen); box-shadow: var(--ombre-2); transform: translateY(-1px); color: var(--texte); }
    .raccourci-icone { width: 40px; height: 40px; border-radius: var(--r-m); display: grid; place-items: center; background: var(--accent-doux); color: var(--accent); }
    .raccourci-icone .ico { width: 20px; height: 20px; }
    .raccourci strong { display: block; font-weight: 600; line-height: 1.3; }
    .raccourci small { display: block; color: var(--texte-doux); line-height: 1.35; }
    .raccourci > .ico { color: var(--texte-faible); transition: transform var(--d1) var(--courbe), color var(--d1) var(--courbe); }
    .raccourci:hover > .ico { color: var(--accent); transform: translateX(2px); }

    /* ---------- États vides illustrés ---------- */
    .etat-vide { display: flex; flex-direction: column; align-items: center; text-align: center; gap: var(--e1); color: var(--texte-doux); padding: var(--e5) var(--e4); font-size: var(--t-sm); }
    .etat-vide .ico { width: 28px; height: 28px; color: var(--texte-faible); display: block; margin: 0 auto var(--e2); }
    .etat-vide strong { display: block; color: var(--texte); font-size: var(--t-base); }
    .etat-vide-illu { width: 96px; height: 72px; margin-bottom: var(--e2); flex: none; }
    .etat-vide-illu .illu-fond { fill: var(--surface-2); stroke: var(--bord-fort); stroke-width: 1.5; }
    .etat-vide-illu .illu-papier { fill: var(--surface); stroke: var(--bord-fort); stroke-width: 1.5; }
    .etat-vide-illu .illu-trait { stroke: var(--bord-fort); stroke-width: 2; stroke-linecap: round; fill: none; }
    .etat-vide-illu .illu-accent { fill: var(--accent-doux); stroke: var(--accent); stroke-width: 1.75; }
    .etat-vide-illu .illu-coche { fill: none; stroke: var(--accent); stroke-width: 2.25; stroke-linecap: round; stroke-linejoin: round; }
    td.etat-vide { display: table-cell; padding: var(--e6) var(--e4); }
    .pile > .etat-vide, .carte.etat-vide { background: var(--surface); border: 1px dashed var(--bord-fort); border-radius: var(--r-l); }

    /* ---------- Squelettes de chargement ---------- */
    .squelette {
      display: block; height: 0.85em; border-radius: var(--r-s); background-color: var(--surface-3);
      background-image: linear-gradient(90deg, transparent 0, var(--miroitement) 50%, transparent 100%);
      background-size: 200% 100%; background-repeat: no-repeat; animation: miroitement 1.4s linear infinite;
    }
    .squelette-texte { width: 100%; }
    .squelette-texte.court { width: 55%; }
    .squelette-titre { height: 1.25em; width: 40%; }
    .squelette-valeur { height: 1em; width: 2.2ch; border-radius: var(--r-s); }
    .squelette-pastille { width: 96px; height: 22px; border-radius: var(--r-pilule); }
    .squelette-carre { width: 52px; height: 46px; border-radius: var(--r-m); }
    .squelette-pile { display: flex; flex-direction: column; gap: var(--e2); min-width: 0; }
    .ligne-squelette { display: grid; grid-template-columns: auto minmax(0, 1fr); align-items: center; gap: var(--e3); padding: var(--e3) 0; border-top: 1px solid var(--bord); }
    .ligne-squelette:first-child { border-top: 0; padding-top: 0; }
    @keyframes miroitement { from { background-position: 150% 0; } to { background-position: -50% 0; } }

    /* ---------- Formulaires ---------- */
    label { display: flex; flex-direction: column; gap: 6px; font-size: var(--t-sm); font-weight: 600; color: var(--texte); }
    label .requis { color: var(--critique); }
    label.case, .liste-cases label, .ligne-proc label { flex-direction: row; align-items: flex-start; gap: var(--e2); font-weight: 400; font-size: var(--t-base); }
    label.case input[type="checkbox"], .liste-cases input[type="checkbox"], .ligne-proc input[type="checkbox"], label.case input[type="radio"] { width: 18px; height: 18px; min-height: 0; margin: 2px 0 0; padding: 0; flex: none; accent-color: var(--accent-plein); }
    input[type="checkbox"], input[type="radio"] { accent-color: var(--accent-plein); }
    input, select, textarea {
      width: 100%; min-height: var(--h-ctrl); padding: 8px var(--e3); border: 1px solid var(--bord-champ); border-radius: var(--r-m);
      background: var(--surface); color: var(--texte); font: inherit; font-size: var(--t-base); font-weight: 400;
      transition: border-color var(--d1) var(--courbe), box-shadow var(--d1) var(--courbe), background-color var(--d1) var(--courbe);
    }
    textarea { line-height: 1.5; resize: vertical; }
    select { cursor: pointer; }
    input::placeholder, textarea::placeholder { color: var(--texte-faible); opacity: 1; }
    input:hover, select:hover, textarea:hover { border-color: var(--texte-faible); }
    input:focus, select:focus, textarea:focus { border-color: var(--accent); }
    input:focus-visible, select:focus-visible, textarea:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: var(--r-m); }
    input[aria-invalid="true"], select[aria-invalid="true"], textarea[aria-invalid="true"] { border-color: var(--critique); }
    input[aria-invalid="true"]:focus-visible, select[aria-invalid="true"]:focus-visible, textarea[aria-invalid="true"]:focus-visible { outline-color: var(--critique); }
    input:disabled, select:disabled, textarea:disabled { background: var(--surface-2); color: var(--texte-faible); cursor: not-allowed; }
    input[type="file"] { padding: 6px var(--e2); }
    fieldset { border: 0; padding: 0; margin: 0 0 var(--e5); min-width: 0; }
    fieldset legend { padding: 0; margin-bottom: var(--e3); font-family: var(--police-titre); font-weight: 700; font-size: var(--t-base); }
    .champ { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
    .champ-libelle { font-size: var(--t-sm); font-weight: 600; color: var(--texte); }
    .champ-aide, .aide { font-size: var(--t-sm); color: var(--texte-faible); font-weight: 400; }
    .champ-erreur { display: flex; align-items: center; gap: 6px; font-size: var(--t-sm); font-weight: 500; color: var(--critique-texte); }
    .champ-erreur::before { content: ""; width: 8px; height: 8px; flex: none; background: var(--critique); transform: rotate(45deg); border-radius: 1px; }
    .barre-saisie { display: flex; gap: var(--e2); align-items: stretch; flex-wrap: wrap; }
    .barre-saisie > input[type="text"], .barre-saisie > input[type="search"] { flex: 1 1 240px; width: auto; }
    details.carte > summary { cursor: pointer; font-family: var(--police-titre); font-weight: 700; font-size: var(--t-md); list-style: none; display: flex; align-items: center; justify-content: space-between; gap: var(--e3); }
    details.carte > summary::-webkit-details-marker { display: none; }
    details.carte > summary::after { content: ""; width: 8px; height: 8px; border-right: 2px solid var(--texte-doux); border-bottom: 2px solid var(--texte-doux); transform: rotate(45deg); transition: transform var(--d2) var(--courbe); }
    details.carte[open] > summary::after { transform: rotate(-135deg); }
    details.carte[open] > summary { margin-bottom: var(--e4); }

    /* ---------- Boutons : primaire, secondaire, contour, fantôme, danger ; tailles ---------- */
    .btn {
      display: inline-flex; align-items: center; justify-content: center; gap: var(--e2); min-height: var(--h-ctrl); padding: 8px var(--e4);
      margin: 0 var(--e2) var(--e2) 0; border: 1px solid var(--bord-fort); border-radius: var(--r-m); background: var(--surface); color: var(--texte);
      font: inherit; font-size: var(--t-base); font-weight: 600; line-height: 1.2; text-decoration: none; white-space: nowrap; cursor: pointer; touch-action: manipulation;
      transition: background-color var(--d1) var(--courbe), border-color var(--d1) var(--courbe), color var(--d1) var(--courbe), box-shadow var(--d1) var(--courbe), transform var(--d1) var(--courbe);
    }
    .btn .ico { width: 1.1em; height: 1.1em; }
    @media (max-width: 640px) {
      .btn { max-width: 100%; white-space: normal; text-align: center; }
      main code { overflow-wrap: anywhere; }
    }
    .btn:hover { background: var(--surface-2); color: var(--texte); border-color: var(--texte-faible); }
    .btn:active { transform: translateY(1px); }
    .btn:disabled, .btn[aria-disabled="true"] { opacity: 0.5; cursor: not-allowed; transform: none; }
    .btn-primaire, .btn-succes, a.btn-primaire { background: var(--accent-plein); border-color: var(--accent-plein); color: var(--sur-accent); box-shadow: 0 1px 2px rgba(20, 24, 49, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.12); }
    .btn-primaire:hover, .btn-succes:hover, a.btn-primaire:hover { background: var(--accent-plein-survol); border-color: var(--accent-plein-survol); color: var(--sur-accent); }
    .btn-secondaire { background: var(--accent-doux); border-color: transparent; color: var(--accent-fort); }
    .btn-secondaire:hover { background: var(--accent-moyen); border-color: transparent; color: var(--accent-fort); }
    .btn-contour { background: var(--surface); }
    .btn-fantome { background: transparent; border-color: transparent; color: var(--texte-doux); }
    .btn-fantome:hover { background: var(--surface-2); border-color: transparent; color: var(--texte); }
    .btn-danger { background: var(--critique-doux); border-color: transparent; color: var(--critique-texte); }
    .btn-danger:hover { background: var(--critique); border-color: var(--critique); color: #ffffff; }
    .btn-sm { min-height: var(--h-ctrl-sm); padding: 4px var(--e3); font-size: var(--t-sm); }
    .btn-lg { min-height: var(--h-ctrl-lg); padding: 10px var(--e5); font-size: var(--t-md); border-radius: var(--r-l); }
    .btn-bloc { display: flex; width: 100%; }
    .btn-icone { min-width: var(--h-ctrl); padding: 8px; }
    .btn-sm.btn-icone { min-width: var(--h-ctrl-sm); padding: 4px; }
    .btn[aria-busy="true"] { position: relative; color: transparent; pointer-events: none; }
    .btn[aria-busy="true"]::after { content: ""; position: absolute; width: 16px; height: 16px; border-radius: 50%; border: 2px solid currentColor; border-color: var(--sur-accent) transparent var(--sur-accent) var(--sur-accent); animation: rotation 0.8s linear infinite; }
    @keyframes rotation { to { transform: rotate(360deg); } }
    .pile-actions { display: flex; flex-wrap: wrap; gap: var(--e2); margin-top: var(--e3); }
    .pile-actions .btn { margin: 0; }
    .btn-lien { background: none; border: 0; min-height: 0; padding: 0; margin: 0; color: var(--accent); font: inherit; font-weight: 500; text-decoration: underline; text-underline-offset: 2px; cursor: pointer; }
    .btn-lien:hover { background: none; color: var(--accent-fort); }

    /* ---------- Badges d'état : forme ET couleur ---------- */
    .badge { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px 3px 8px; border-radius: var(--r-pilule); font-size: var(--t-xs); font-weight: 600; line-height: 1.4; background: var(--surface-2); color: var(--texte-doux); white-space: nowrap; box-shadow: inset 0 0 0 1px var(--bord); font-variant-numeric: tabular-nums; }
    .badge::before { content: ""; width: 9px; height: 9px; flex: none; border: 2px solid currentColor; border-radius: 50%; }
    .badge-ok, .badge-valide { background: var(--bon-doux); color: var(--bon-texte); box-shadow: none; }
    .badge-ok::before, .badge-valide::before { border: 0; background: currentColor; border-radius: 50%; }
    .badge-warn, .badge-completer { background: var(--alerte-doux); color: var(--alerte-texte); box-shadow: none; }
    .badge-warn::before, .badge-completer::before { border: 0; background: currentColor; border-radius: 0; clip-path: polygon(50% 0, 100% 100%, 0 100%); }
    .badge-err, .badge-refuse { background: var(--critique-doux); color: var(--critique-texte); box-shadow: none; }
    .badge-err::before, .badge-refuse::before { border: 0; background: currentColor; border-radius: 0; clip-path: polygon(30% 0, 70% 0, 100% 30%, 100% 70%, 70% 100%, 30% 100%, 0 70%, 0 30%); }
    .badge-info, .badge-attente { background: var(--accent-doux); color: var(--accent-fort); box-shadow: none; }
    .badge-info::before { border: 0; background: currentColor; border-radius: 0; clip-path: polygon(50% 0, 100% 50%, 50% 100%, 0 50%); }
    .badge-attente::before { border: 2px solid currentColor; border-right-color: transparent; background: none; }
    .badge-envoye { background: var(--accent-plein); color: var(--sur-accent); box-shadow: none; }
    .badge-envoye::before { border: 0; width: 10px; background: currentColor; border-radius: 0; clip-path: polygon(0 0, 100% 50%, 0 100%, 25% 50%); }
    .badge-brouillon { background: transparent; color: var(--texte-doux); box-shadow: inset 0 0 0 1px var(--bord-fort); }
    .badge-brouillon::before { border-style: dashed; }
    .badge-nu::before { display: none; }

    /* ---------- Onglets ---------- */
    .onglets { display: flex; gap: var(--e1); border-bottom: 1px solid var(--bord); margin-bottom: var(--e4); overflow-x: auto; scrollbar-width: none; }
    .onglet { position: relative; min-height: var(--h-ctrl); padding: 8px var(--e3); border: 0; background: none; color: var(--texte-doux); font: inherit; font-size: var(--t-base); font-weight: 500; white-space: nowrap; cursor: pointer; border-radius: var(--r-m) var(--r-m) 0 0; transition: color var(--d1) var(--courbe), background-color var(--d1) var(--courbe); }
    .onglet:hover { color: var(--texte); background: var(--surface-2); }
    .onglet::after { content: ""; position: absolute; left: var(--e3); right: var(--e3); bottom: -1px; height: 2px; border-radius: 2px 2px 0 0; background: var(--accent); transform: scaleX(0); transition: transform var(--d2) var(--courbe); }
    .onglet[aria-selected="true"] { color: var(--accent-fort); font-weight: 600; }
    .onglet[aria-selected="true"]::after { transform: scaleX(1); }

    /* ---------- Étapes d'une procédure (stepper) ---------- */
    .etapes { list-style: none; margin: 0 0 var(--e5); padding: 0; display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr); gap: var(--e2); counter-reset: etape; }
    .etape { position: relative; display: flex; flex-direction: column; gap: 2px; padding-top: 40px; counter-increment: etape; font-size: var(--t-sm); color: var(--texte-doux); min-width: 0; }
    .etape::before { content: counter(etape); position: absolute; top: 0; left: 0; width: 30px; height: 30px; border-radius: 50%; display: grid; place-items: center; background: var(--surface); color: var(--texte-doux); box-shadow: inset 0 0 0 2px var(--bord-fort); font-weight: 700; font-size: var(--t-sm); font-variant-numeric: tabular-nums; z-index: 1; }
    .etape::after { content: ""; position: absolute; top: 14px; left: 38px; right: 0; height: 2px; border-radius: 2px; background: var(--bord); }
    .etape:last-child::after { display: none; }
    .etape-titre { font-weight: 600; color: var(--texte); font-size: var(--t-base); line-height: 1.3; }
    .etape-faite::before { content: ""; background: var(--accent-plein); box-shadow: none; }
    .etape-faite::after { background: var(--accent); }
    .etape-faite .etape-titre::before { content: ""; position: absolute; top: 9px; left: 11px; width: 6px; height: 10px; border-right: 2px solid var(--sur-accent); border-bottom: 2px solid var(--sur-accent); transform: rotate(40deg); z-index: 2; }
    .etape-courante::before { background: var(--accent-doux); color: var(--accent-fort); box-shadow: inset 0 0 0 2px var(--accent), 0 0 0 4px var(--accent-doux); }
    .etape-courante .etape-titre { color: var(--accent-fort); }
    .etape-bloquee::before { background: var(--alerte-doux); color: var(--alerte-texte); box-shadow: inset 0 0 0 2px var(--alerte); }

    /* ---------- Progression d'un dossier ---------- */
    .progression-dossier { display: flex; flex-direction: column; gap: 6px; }
    .progression-entete { display: flex; justify-content: space-between; align-items: baseline; gap: var(--e3); font-size: var(--t-sm); color: var(--texte-doux); }
    .progression-entete strong { color: var(--texte); font-variant-numeric: tabular-nums; }
    .barre-progression { width: 100%; height: 8px; background: var(--surface-3); border-radius: var(--r-pilule); overflow: hidden; margin: var(--e2) 0; }
    .progression-dossier .barre-progression { margin: 0; }
    .barre-progression-remplie { height: 100%; background: var(--accent-plein); border-radius: var(--r-pilule); transition: width var(--d3) var(--courbe); }
    .barre-progression.ok .barre-progression-remplie { background: var(--bon); }
    .barre-progression.alerte .barre-progression-remplie { background: var(--alerte); }

    /* ---------- Modales (élément <dialog>) ---------- */
    dialog.modale { width: min(560px, calc(100vw - 32px)); max-height: calc(100dvh - 48px); padding: 0; border: 1px solid var(--bord); border-radius: var(--r-xl); background: var(--surface); color: var(--texte); box-shadow: var(--ombre-flottante); overflow: auto; }
    dialog.modale[open] { animation: apparition var(--d2) var(--courbe) both; }
    dialog.modale::backdrop { background: var(--voile); }
    .modale-entete { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--e3); padding: var(--e5) var(--e5) 0; }
    .modale-entete h3 { font-size: var(--t-lg); }
    .modale-entete .btn { margin: -6px -6px 0 0; }
    .modale-corps { padding: var(--e4) var(--e5); color: var(--texte-doux); }
    .modale-pied { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: var(--e2); padding: var(--e4) var(--e5); background: var(--surface-2); border-top: 1px solid var(--bord); }
    .modale-pied .btn { margin: 0; }

    /* ---------- Tableaux lisibles ---------- */
    .table-wrap { overflow-x: auto; border: 1px solid var(--bord); border-radius: var(--r-l); background: var(--surface); box-shadow: var(--ombre-1); -webkit-overflow-scrolling: touch; }
    table { width: 100%; border-collapse: collapse; font-size: var(--t-base); }
    .table-wrap table { min-width: 620px; }
    th { position: sticky; top: 0; background: var(--surface-2); color: var(--texte-doux); font-size: var(--t-sm); font-weight: 600; text-align: left; padding: 10px var(--e4); border-bottom: 1px solid var(--bord); white-space: nowrap; }
    td { padding: var(--e3) var(--e4); border-bottom: 1px solid var(--bord); vertical-align: top; }
    tbody tr:last-child td { border-bottom: 0; }
    tbody tr { transition: background-color var(--d1) var(--courbe); }
    tbody tr:hover { background: var(--surface-2); }
    tbody tr.ligne-active { background: var(--accent-doux); }
    tbody tr.ligne-active td:first-child { box-shadow: inset 3px 0 0 var(--accent); }
    td small { display: block; }
    td .btn { margin: 2px 4px 2px 0; }
    td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
    .table-compacte td { padding: var(--e2) var(--e3); }
"""

CSS_ECRANS = """
    /* ---------- Fils de discussion, listes, détails (écrans existants) ---------- */
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
    .capture-apercu { max-width: 100%; border: 1px solid var(--bord); border-radius: var(--r-m); margin-top: var(--e3); }
    details.guide-bloc { border: 1px solid var(--bord); border-radius: var(--r-m); padding: var(--e3) var(--e4); margin-bottom: var(--e2); background: var(--surface); }
    details.guide-bloc summary { font-weight: 600; cursor: pointer; }
    details.guide-bloc[open] summary { margin-bottom: var(--e2); color: var(--accent-fort); }
    .chips { display: flex; flex-wrap: wrap; gap: var(--e2); margin: var(--e2) 0 var(--e3); }
    .puce-cmd { display: inline-flex; align-items: center; gap: 6px; min-height: var(--h-ctrl-sm); background: var(--accent-doux); color: var(--accent-fort); border: 0; border-radius: var(--r-pilule); padding: 5px 12px; font: inherit; font-size: var(--t-sm); font-weight: 500; cursor: pointer; transition: background-color var(--d1) var(--courbe); }
    .puce-cmd:hover { background: var(--accent-moyen); }
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
    .bulle-copilote-user { align-self: flex-end; background: var(--accent-plein); color: var(--sur-accent); padding: 8px var(--e3); border-radius: var(--r-l) var(--r-l) var(--r-s) var(--r-l); font-size: var(--t-sm); max-width: 88%; }
    .bulle-copilote-ia { align-self: flex-start; background: var(--surface); color: var(--texte); border: 1px solid var(--bord); padding: 10px var(--e3); border-radius: var(--r-l) var(--r-l) var(--r-l) var(--r-s); font-size: var(--t-sm); max-width: 95%; line-height: 1.5; }
    .grille-dom-live { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 220px), 1fr)); gap: var(--e2); margin-top: var(--e2); }
    .carte-dom-item { background: var(--surface-2); border: 1px solid var(--bord); border-radius: var(--r-m); padding: var(--e2) var(--e3); font-size: var(--t-sm); display: flex; flex-direction: column; gap: 5px; }
    .etapes-actions { display: flex; flex-wrap: wrap; gap: var(--e2); margin: var(--e3) 0 0; }
    .etapes-actions .btn { margin: 0; }
    .titre-mini { margin: var(--e4) 0 var(--e2); font-size: var(--t-sm); font-weight: 600; color: var(--texte-doux); }

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
"""

CSS_ADAPTATIF = """
    /* ---------- Étroit : navigation en tiroir, gouttière de 16px ---------- */
    @media (max-width: 1100px) {
      .workspace-cowork { grid-template-columns: minmax(0, 1fr); }
      .accueil-grille { grid-template-columns: minmax(0, 1fr); }
    }
    @media (max-width: 900px) {
      body { display: block; }
      .barre-haute {
        display: flex; align-items: center; gap: var(--e2); position: sticky; top: 0; z-index: 40;
        padding: var(--e2) max(16px, env(safe-area-inset-right, 0px)) var(--e2) max(16px, env(safe-area-inset-left, 0px));
        background: var(--surface); border-bottom: 1px solid var(--bord);
      }
      .barre-haute .marque { padding: 0; flex: 1; min-width: 0; }
      .barre-haute .marque-nom { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .barre-haute .marque-logo { width: 32px; height: 32px; }
      .barre-haute .btn { margin: 0; }
      aside#navigation-principale {
        position: fixed; z-index: 60; left: 0; top: 0; bottom: 0; width: min(300px, 86vw); height: 100vh; height: 100dvh;
        padding-left: max(12px, env(safe-area-inset-left, 0px));
        transform: translateX(-102%); visibility: hidden; box-shadow: var(--ombre-flottante);
        transition: transform var(--d2) var(--courbe), visibility 0s linear var(--d2);
      }
      aside#navigation-principale .marque { display: none; }
      aside#navigation-principale .nav-fermer { display: inline-flex; align-self: flex-end; margin: 0; min-width: 44px; min-height: 44px; }
      body.nav-ouverte { overflow: hidden; }
      body.nav-ouverte aside#navigation-principale { transform: none; visibility: visible; transition: transform var(--d2) var(--courbe), visibility 0s; }
      body.nav-ouverte .scrim { display: block; position: fixed; inset: 0; z-index: 50; background: var(--voile); border: 0; animation: fondu var(--d2) var(--courbe) both; }
      main { padding: var(--e4) max(16px, env(safe-area-inset-right, 0px)) var(--e7) max(16px, env(safe-area-inset-left, 0px)); }
      #banniere-etat { margin-bottom: var(--e4); flex-wrap: nowrap; gap: var(--e2); padding: 6px; }
      .banniere-contexte { flex: 1 1 0; padding-right: 0; gap: var(--e2); }
      .banniere-dossier { flex: 1 1 auto; }
      .banniere-dossier .surtitre { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
      .banniere-dossier strong { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; overflow-wrap: normal; }
      #banniere-etat .btn { flex: none; padding-left: var(--e2); padding-right: var(--e2); font-size: var(--t-xs); min-height: var(--h-ctrl-sm); }
      .banniere-regle-courte { margin-left: 0; flex: none; width: 34px; height: 34px; padding: 0; justify-content: center; }
      .banniere-regle-courte > span { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
      .bandeau-suite { display: none; }
      #zone-notification { left: max(16px, env(safe-area-inset-left, 0px)); right: max(16px, env(safe-area-inset-right, 0px)); top: auto; bottom: calc(var(--e4) + env(safe-area-inset-bottom, 0px)); max-width: none; }
      .carte { padding: var(--e4); }
      h2 { font-size: var(--t-lg); }
      .stat .valeur, .kpi .valeur { font-size: var(--t-xl); }
      .ligne-action { grid-template-columns: minmax(0, 1fr); gap: var(--e2); }
      .ligne-action .btn { justify-self: start; }
      .echeance { grid-template-columns: 52px minmax(0, 1fr); }
      .echeance .badge { grid-column: 2; justify-self: start; }
      .iframe-navigateur-direct { height: 420px; }
      .connexion { grid-template-columns: minmax(0, 1fr); min-height: 0; border-radius: var(--r-l); }
      .connexion-form { padding: var(--e6) var(--e5); }
      .connexion-entete h2 { font-size: var(--t-xl); }
      .connexion-marque { padding: var(--e5); gap: var(--e5); }
        .etapes { grid-auto-flow: row; grid-auto-columns: auto; gap: var(--e4); }
      .etape { padding: 4px 0 0 44px; min-height: 30px; }
      .etape::after { top: 36px; left: 14px; right: auto; bottom: -14px; width: 2px; height: auto; }
      .etape-faite .etape-titre::before { top: 9px; left: 11px; }
    }
    @media (max-width: 520px) {
      .kpi { padding: var(--e3) var(--e4) var(--e4); gap: var(--e2); }
      .kpi-aide { display: none; }
      .kpi-icone { width: 28px; height: 28px; }
    }
    @media (max-width: 900px) and (pointer: coarse) {
      .btn-sm, .btn-sm.btn-icone { min-height: var(--h-ctrl); min-width: var(--h-ctrl); }
    }
    /* Cibles tactiles : 44 px au minimum quand le pointeur est grossier (doigt) */
    @media (pointer: coarse) {
      .btn, .btn-sm, .btn-lg, aside button.nav-btn, .onglet, .puce-cmd, .bouton-theme, input, select, textarea { min-height: 44px; }
      .btn-icone, .btn-sm.btn-icone { min-width: 44px; }
      .barre-chrome-direct .btn-nav-mini { min-width: 44px; height: auto; min-height: 44px; }
      label.case, .liste-cases label { min-height: 44px; align-items: center; }
    }
    @media (min-width: 901px) {
      .barre-haute .bouton-theme-mobile { display: none; }
    }
    @keyframes fondu { from { opacity: 0; } to { opacity: 1; } }

    /* ---------- Icône du bouton de thème selon le thème effectif ---------- */
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
      .point-vert-pulsant, .squelette { animation: none; }
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
        + CSS_CONNEXION
        + CSS_COMPOSANTS
        + CSS_ECRANS
        + CSS_ADAPTATIF
        + CSS_MOUVEMENT
    )


CSS_DESIGN = construire_css()
