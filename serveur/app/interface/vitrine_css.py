"""Feuille de la vitrine publique (`/bienvenue`, `/inscription`, pages courriel).

S'ajoute à `CSS_DESIGN` : uniquement des tokens (`var(--...)`), aucune couleur littérale, aucun
antislash. Les durées et courbes reprennent le vocabulaire de mouvement (`--mo-dur-*`,
`--mo-ease-out`) avec une valeur de repli : la page n'en dépend pas.

Principes : tout le contenu est visible sans JavaScript et sans animation ; les animations sont
déclarées uniquement sous `prefers-reduced-motion: no-preference`, n'utilisent que transform et
opacity, et se mettent en pause hors écran (classe posée par le script).
"""

from __future__ import annotations

STYLE_BASE = """
    :root { --v-dur: var(--mo-dur-3, 360ms); --v-dur-long: var(--mo-dur-4, 560ms); --v-ease: var(--mo-ease-out, cubic-bezier(0.2, 0.7, 0.2, 1)); }
    [hidden] { display: none !important; }
    body.publique { display: block; background: var(--fond); }
    body.publique main { max-width: none; padding: 0; display: block; }
    section[id] { scroll-margin-top: 72px; }
    .v-cadre { max-width: 1200px; margin: 0 auto; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
    .v-section { padding-block: clamp(56px, 8vw, 112px); }
    .v-section-creuse { background: var(--surface-2); border-block: 1px solid var(--bord); }
    .v-entete { display: flex; flex-direction: column; gap: var(--e3); max-width: 60ch; margin-bottom: var(--e7); }
    .v-entete h2 { font-size: clamp(1.75rem, 3.4vw, 2.5rem); line-height: 1.1; letter-spacing: -0.03em; text-wrap: balance; }
    .v-entete p { margin: 0; color: var(--texte-doux); font-size: var(--t-md); line-height: 1.6; }
    .v-actions { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e3); }
    .v-actions .btn { margin: 0; }

    /* En-tête collant */
    .pub-entete { position: sticky; top: 0; z-index: 30; background: var(--fond); background: color-mix(in srgb, var(--fond) 86%, transparent); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border-bottom: 1px solid var(--bord); }
    .pub-entete-ligne { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--e2) var(--e4); padding-block: var(--e3); }
    .pub-entete .marque { padding: 0; text-decoration: none; color: var(--texte); }
    .pub-nav { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e1) var(--e1); }
    .pub-nav .btn { margin: 0 0 0 var(--e2); }
    .pub-lien-nav { padding: 6px var(--e3); border-radius: var(--r-pilule); color: var(--texte-doux); text-decoration: none; font-size: var(--t-sm); font-weight: 500; transition: color var(--d1) var(--courbe), background-color var(--d1) var(--courbe); }
    .pub-lien-nav:hover, .pub-lien-nav[aria-current="page"] { color: var(--accent-fort); background: var(--accent-doux); }
    .pub-lien-nav:focus-visible, .v-pied a:focus-visible, .v-faq summary:focus-visible, .v-rail a:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

    /* Accroche */
    .v-hero { position: relative; overflow: hidden; isolation: isolate; padding-block: clamp(36px, 6vw, 88px) clamp(48px, 7vw, 104px); }
    .v-hero-fond { position: absolute; inset: 0; z-index: -1; pointer-events: none; background: radial-gradient(60% 70% at 88% 8%, color-mix(in srgb, var(--accent) 16%, transparent), transparent 70%), radial-gradient(50% 60% at 0% 100%, color-mix(in srgb, var(--accent) 9%, transparent), transparent 70%); }
    .v-hero-fond::after { content: ""; position: absolute; inset: 0; background-image: radial-gradient(circle, color-mix(in srgb, var(--texte) 16%, transparent) 1px, transparent 1.6px); background-size: 28px 28px; -webkit-mask-image: linear-gradient(180deg, var(--texte), transparent 80%); mask-image: linear-gradient(180deg, var(--texte), transparent 80%); opacity: 0.55; }
    .v-hero-fond canvas { position: absolute; inset: 0; width: 100%; height: 100%; display: block; opacity: 0; transition: opacity 1.4s var(--v-ease); z-index: 1; }
    .v-hero-fond.pret canvas { opacity: 1; }
    .v-hero-grille { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 6fr); gap: var(--e7); align-items: center; }
    .v-hero-texte { display: flex; flex-direction: column; gap: var(--e5); min-width: 0; }
    .v-hero h1 { font-size: clamp(2.25rem, 4.6vw, 3.6rem); line-height: 1.04; letter-spacing: -0.04em; text-wrap: balance; }
    .v-lead { font-size: var(--t-md); color: var(--texte-doux); max-width: 52ch; margin: 0; line-height: 1.65; }
    .v-garanties { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: var(--e2) var(--e5); font-size: var(--t-sm); color: var(--texte-doux); }
    .v-garanties li { display: inline-flex; align-items: center; gap: 6px; }
    .v-garanties .ico { color: var(--bon); }

    /* Démonstration du flux */
    .flux { position: relative; padding: var(--e4); background: var(--surface); border: 1px solid var(--bord); border-radius: var(--r-xl); box-shadow: var(--ombre-2); min-width: 0; }
    .flux-tete { display: flex; align-items: center; justify-content: space-between; gap: var(--e3); margin-bottom: var(--e4); }
    .flux-legende { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--e3); flex: 1; min-width: 0; }
    .flux-legende li { position: relative; display: flex; align-items: center; gap: var(--e2); font-size: var(--t-sm); font-weight: 600; color: var(--texte); padding-bottom: var(--e2); min-width: 0; }
    .flux-legende b { width: 22px; height: 22px; flex: none; border-radius: 50%; display: grid; place-items: center; background: var(--accent-doux); color: var(--accent-fort); font-size: var(--t-xs); font-variant-numeric: tabular-nums; }
    .flux-legende li::after { content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 2px; border-radius: 2px; background: var(--accent); transform-origin: left; }
    .flux-exemple { font-size: var(--t-xs); color: var(--texte-faible); white-space: nowrap; }
    .flux-scene { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--e4); }
    .fx-col { position: relative; display: flex; flex-direction: column; gap: var(--e2); min-height: 244px; padding: var(--e3); background: var(--surface-2); border: 1px solid var(--bord); border-radius: var(--r-l); min-width: 0; }
    .fx-col:not(:last-child)::after { content: ""; position: absolute; top: 50%; right: calc(-1 * var(--e4) / 2 - 5px); width: 10px; height: 10px; border-top: 2px solid var(--accent); border-right: 2px solid var(--accent); transform: translateY(-50%) rotate(45deg); z-index: 2; }
    .fx-titre { font-size: var(--t-xs); font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--texte-faible); margin-bottom: var(--e1); }
    .fx-doc { display: flex; align-items: center; gap: var(--e2); padding: 8px 10px; background: var(--surface); border: 1px solid var(--bord); border-radius: var(--r-m); font-size: var(--t-xs); font-weight: 500; color: var(--texte); min-width: 0; }
    .fx-doc .ico { width: 14px; height: 14px; color: var(--accent); flex: none; }
    .fx-doc span { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .fx-doc .fx-ok { width: 16px; height: 16px; flex: none; border-radius: 50%; display: grid; place-items: center; background: var(--bon-doux); color: var(--bon-texte); }
    .fx-doc .fx-ok .ico { width: 10px; height: 10px; color: inherit; }
    .fx-champ { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
    .fx-champ small { font-size: 11px; color: var(--texte-faible); }
    .fx-champ strong { font-size: var(--t-sm); font-weight: 600; color: var(--texte); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .fx-verifier { align-self: flex-start; display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: var(--r-pilule); background: var(--alerte-doux); color: var(--alerte-texte); font-size: 11px; font-weight: 600; }
    .fx-ligne { display: flex; justify-content: space-between; gap: var(--e2); font-size: var(--t-xs); color: var(--texte-doux); }
    .fx-ligne b { color: var(--texte); font-variant-numeric: tabular-nums; }
    .fx-bouton { position: relative; margin-top: auto; height: 38px; border-radius: var(--r-m); font-size: var(--t-xs); font-weight: 600; }
    .fx-bouton > span { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; gap: 6px; border-radius: var(--r-m); text-align: center; }
    .fx-bouton .fx-b-attente { background: var(--surface); color: var(--accent-fort); box-shadow: inset 0 0 0 1.5px var(--accent); opacity: 0; }
    .fx-bouton .fx-b-ok { background: var(--accent-plein); color: var(--sur-accent); }
    .fx-bouton .ico { width: 12px; height: 12px; }
    .fx-curseur { position: absolute; right: 18%; bottom: 6px; width: 22px; height: 22px; color: var(--texte); z-index: 3; opacity: 0; pointer-events: none; }
    .flux-controle { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--e3); margin-top: var(--e3); font-size: var(--t-xs); color: var(--texte-faible); }
    .flux-controle .btn { margin: 0; }
    .flux-note { margin: 0; }

    /* Bande de faits */
    .v-faits { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); border-block: 1px solid var(--bord); }
    .v-faits li { display: flex; flex-direction: column; gap: 4px; padding: var(--e5) var(--e5); border-left: 1px solid var(--bord); font-size: var(--t-sm); color: var(--texte-doux); }
    .v-faits li:first-child { border-left: 0; padding-left: 0; }
    .v-faits strong { font-family: var(--police-titre); font-size: var(--t-lg); line-height: 1.2; letter-spacing: -0.02em; color: var(--texte); }

    /* Comment ça marche : rail collant + étapes */
    .v-etapes-zone { display: grid; grid-template-columns: minmax(0, 4fr) minmax(0, 8fr); gap: var(--e8); align-items: start; }
    .v-etapes-gauche { position: sticky; top: 96px; display: flex; flex-direction: column; gap: var(--e6); }
    .v-etapes-gauche .v-entete { margin: 0; }
    .v-rail { position: relative; padding-left: var(--e6); }
    .v-rail-liste { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--e4); }
    .v-rail::before, .v-rail-prog { content: ""; position: absolute; left: 7px; top: 8px; bottom: 8px; width: 2px; border-radius: 2px; background: var(--bord-fort); }
    .v-rail-prog { background: var(--accent); transform-origin: top; transform: scaleY(var(--p, 1)); }
    .v-rail a { position: relative; display: block; color: var(--texte-doux); text-decoration: none; font-weight: 500; transition: color var(--d2) var(--courbe); }
    .v-rail a::before { content: ""; position: absolute; left: calc(-1 * var(--e6) + 1px); top: 4px; width: 14px; height: 14px; border-radius: 50%; background: var(--fond); box-shadow: inset 0 0 0 2px var(--bord-fort); transition: background-color var(--d2) var(--courbe), box-shadow var(--d2) var(--courbe); z-index: 1; }
    .v-rail a:hover { color: var(--texte); }
    .v-rail a.actif { color: var(--accent-fort); font-weight: 600; }
    .v-rail a.actif::before { background: var(--accent-plein); box-shadow: 0 0 0 4px var(--accent-doux); }
    .v-etapes { display: flex; flex-direction: column; gap: clamp(48px, 9vw, 120px); }
    .v-etape { display: grid; gap: var(--e5); }
    .v-etape-texte { display: flex; flex-direction: column; gap: var(--e2); max-width: 54ch; }
    .v-etape-num { font-family: var(--police-titre); font-weight: 700; color: var(--accent); font-size: var(--t-sm); }
    .v-etape h3 { font-size: var(--t-xl); letter-spacing: -0.025em; line-height: 1.15; }
    .v-etape p { margin: 0; color: var(--texte-doux); line-height: 1.65; }
    .il { display: flex; flex-direction: column; gap: var(--e3); padding: var(--e5); min-height: 216px; background: var(--surface); border: 1px solid var(--bord); border-radius: var(--r-xl); box-shadow: var(--ombre-1); overflow: hidden; position: relative; }
    .il-zone { display: flex; flex-direction: column; gap: var(--e2); padding: var(--e4); border: 1.5px dashed var(--bord-fort); border-radius: var(--r-l); background: var(--surface-2); }
    .il-puce { display: flex; align-items: center; gap: var(--e2); padding: 8px 12px; background: var(--surface); border: 1px solid var(--bord); border-radius: var(--r-m); font-size: var(--t-sm); font-weight: 500; }
    .il-puce .ico { width: 16px; height: 16px; color: var(--accent); flex: none; }
    .il-puce em { margin-left: auto; font-style: normal; font-size: var(--t-xs); color: var(--texte-faible); }
    .il-page { position: relative; display: flex; flex-direction: column; gap: 8px; padding: var(--e4); border: 1px solid var(--bord); border-radius: var(--r-m); background: var(--surface-2); overflow: hidden; }
    .il-trait { height: 8px; border-radius: 4px; background: var(--surface-3); }
    .il-trait.l1 { width: 90%; } .il-trait.l2 { width: 72%; } .il-trait.l3 { width: 84%; } .il-trait.l4 { width: 55%; }
    .il-scan { position: absolute; left: 0; right: 0; top: 0; height: 36px; background: linear-gradient(180deg, transparent, color-mix(in srgb, var(--accent) 28%, transparent)); border-bottom: 2px solid var(--accent); opacity: 0; }
    .il-lus { display: flex; flex-wrap: wrap; gap: var(--e2); }
    .il-lu { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: var(--r-pilule); background: var(--accent-doux); color: var(--accent-fort); font-size: var(--t-xs); font-weight: 600; }
    .il-lu.verif { background: var(--alerte-doux); color: var(--alerte-texte); }
    .il-liste { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--e2); }
    .il-liste li { display: flex; align-items: center; justify-content: space-between; gap: var(--e3); padding: 10px 12px; background: var(--surface-2); border: 1px solid var(--bord); border-radius: var(--r-m); font-size: var(--t-sm); font-weight: 500; }
    .il-liste .badge { margin: 0; flex: none; }
    .il-valid { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--e3); margin-top: auto; }
    .il-valid small { color: var(--texte-faible); font-size: var(--t-xs); max-width: 30ch; }
    .il-bouton { position: relative; height: 40px; min-width: 210px; border-radius: var(--r-m); font-size: var(--t-sm); font-weight: 600; }
    .il-bouton > span { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; gap: 6px; border-radius: var(--r-m); }
    .il-bouton .il-b-a { background: var(--accent-plein); color: var(--sur-accent); }
    .il-bouton .il-b-b { background: var(--bon-doux); color: var(--bon-texte); opacity: 0; }
    .il-bouton .ico { width: 14px; height: 14px; }

    /* Ce que voit l'équipe : aperçu du tableau de bord */
    .v-suivi { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 7fr); gap: var(--e7); align-items: center; }
    .v-suivi .v-entete { margin: 0; }
    .apercu { padding: var(--e4); border-radius: var(--r-xl); background: var(--surface); border: 1px solid var(--bord); box-shadow: var(--ombre-2); min-width: 0; }
    .apercu-fenetre { background: var(--fond); border: 1px solid var(--bord); border-radius: var(--r-l); overflow: hidden; }
    .apercu-barre { display: flex; align-items: center; gap: 6px; padding: var(--e2) var(--e3); background: var(--surface); border-bottom: 1px solid var(--bord); font-size: var(--t-xs); color: var(--texte-faible); }
    .apercu-point { width: 8px; height: 8px; border-radius: 50%; background: var(--bord-fort); flex: none; }
    .apercu-barre span:last-child { margin-left: var(--e2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .apercu-corps { display: grid; grid-template-columns: 116px minmax(0, 1fr); }
    .apercu-nav { display: flex; flex-direction: column; gap: 4px; padding: var(--e3) var(--e2); background: var(--surface); border-right: 1px solid var(--bord); font-size: var(--t-xs); color: var(--texte-doux); }
    .apercu-nav span { display: flex; align-items: center; gap: 6px; padding: 5px 6px; border-radius: var(--r-s); white-space: nowrap; overflow: hidden; }
    .apercu-nav .ico { width: 13px; height: 13px; color: var(--texte-faible); }
    .apercu-nav .actif { background: var(--accent-doux); color: var(--accent-fort); font-weight: 600; }
    .apercu-nav .actif .ico { color: var(--accent); }
    .apercu-contenu { display: flex; flex-direction: column; gap: var(--e3); padding: var(--e3); min-width: 0; }
    .apercu-titre { font-family: var(--police-titre); font-weight: 700; font-size: var(--t-base); color: var(--texte); }
    .apercu-kpis { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--e2); }
    .apercu-kpi { display: flex; flex-direction: column; gap: 2px; padding: var(--e2) var(--e3); background: var(--surface); border: 1px solid var(--bord); border-radius: var(--r-m); min-width: 0; }
    .apercu-kpi span { font-size: 11px; color: var(--texte-faible); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .apercu-kpi b { font-family: var(--police-titre); font-size: var(--t-lg); line-height: 1.1; color: var(--texte); font-variant-numeric: tabular-nums; }
    .apercu-kpi.alerte b { color: var(--alerte-texte); }
    .apercu-dossiers { list-style: none; margin: 0; padding: 0; background: var(--surface); border: 1px solid var(--bord); border-radius: var(--r-m); }
    .apercu-dossiers li { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 6px var(--e3); padding: var(--e2) var(--e3); border-top: 1px solid var(--bord); }
    .apercu-dossiers li:first-child { border-top: 0; }
    .apercu-dossiers strong { display: block; font-size: var(--t-sm); font-weight: 600; color: var(--texte); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .apercu-dossiers small { display: block; font-size: 11px; color: var(--texte-faible); }
    .apercu-dossiers .barre-progression { grid-column: 1 / -1; height: 5px; margin: 0; }
    .apercu-note { margin: var(--e3) 0 0; font-size: var(--t-xs); color: var(--texte-faible); }

    /* Sécurité et confiance */
    .v-confiance { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 250px), 1fr)); gap: var(--e4); }
    .v-confiance li { display: flex; flex-direction: column; gap: var(--e2); padding: var(--e5); background: var(--surface); border: 1px solid var(--bord); border-radius: var(--r-xl); transition: transform var(--v-dur) var(--v-ease), box-shadow var(--v-dur) var(--v-ease); }
    .v-confiance li:hover { transform: translateY(-2px); box-shadow: var(--ombre-2); }
    .v-confiance h3 { font-size: var(--t-md); margin: var(--e2) 0 0; }
    .v-confiance p { margin: 0; color: var(--texte-doux); font-size: var(--t-sm); line-height: 1.6; }
    .v-icone { width: 40px; height: 40px; border-radius: var(--r-m); display: grid; place-items: center; background: var(--accent-doux); color: var(--accent); }
    .v-icone .ico { width: 20px; height: 20px; }
    .v-section-appel { padding-top: 0; }
    .fx-curseur path { fill: currentColor; stroke: var(--surface); stroke-width: 1.5; stroke-linejoin: round; }
    .v-limites { margin-top: var(--e6); padding: var(--e5); border: 1px dashed var(--bord-fort); border-radius: var(--r-l); display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 9fr); gap: var(--e4) var(--e6); }
    .v-limites h3 { font-size: var(--t-md); }
    .v-limites ul { margin: 0; padding-left: 1.1em; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--e2) var(--e6); color: var(--texte-doux); font-size: var(--t-sm); line-height: 1.55; }

    /* Tarifs */
    .v-forfaits { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr)); gap: var(--e4); align-items: stretch; }
    .v-forfaits li { display: flex; flex-direction: column; gap: var(--e4); padding: var(--e6) var(--e5); background: var(--surface); border: 1px solid var(--bord); border-radius: var(--r-xl); box-shadow: var(--ombre-1); transition: transform var(--v-dur) var(--v-ease), box-shadow var(--v-dur) var(--v-ease); }
    .v-forfaits li:hover { transform: translateY(-2px); box-shadow: var(--ombre-2); }
    .v-forfaits li.fort { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent), var(--ombre-2); }
    .v-forfaits h3 { font-size: var(--t-md); line-height: 1.3; }
    .v-prix { margin: 0; display: flex; align-items: baseline; gap: var(--e2); }
    .v-prix b { font-family: var(--police-titre); font-size: var(--t-3xl); line-height: 1; letter-spacing: -0.04em; font-variant-numeric: tabular-nums; color: var(--texte); }
    .v-prix span { font-size: var(--t-sm); color: var(--texte-faible); }
    .v-quota { margin: 0; display: flex; align-items: center; gap: var(--e2); padding-top: var(--e4); border-top: 1px solid var(--bord); color: var(--texte-doux); font-size: var(--t-sm); }
    .v-quota .ico { color: var(--accent); flex: none; }
    .v-forfaits .btn { margin: auto 0 0; }
    .v-tarif-note { margin: var(--e5) 0 0; font-size: var(--t-sm); color: var(--texte-faible); max-width: 70ch; }

    /* Questions fréquentes */
    .v-faq-zone { display: grid; grid-template-columns: minmax(0, 4fr) minmax(0, 8fr); gap: var(--e8); align-items: start; }
    .v-faq-zone .v-entete { margin: 0; position: sticky; top: 96px; }
    .v-faq-liste { display: flex; flex-direction: column; border-top: 1px solid var(--bord); }
    .v-faq { border-bottom: 1px solid var(--bord); }
    .v-faq summary { list-style: none; display: flex; align-items: center; justify-content: space-between; gap: var(--e4); padding: var(--e4) 0; cursor: pointer; font-weight: 600; font-size: var(--t-md); color: var(--texte); border-radius: var(--r-s); }
    .v-faq summary::-webkit-details-marker { display: none; }
    .v-faq summary::after { content: "+"; flex: none; width: 28px; height: 28px; display: grid; place-items: center; border-radius: 50%; background: var(--surface-2); color: var(--accent); font-size: var(--t-lg); line-height: 1; transition: transform var(--v-dur) var(--v-ease), background-color var(--d1) var(--courbe); }
    .v-faq summary:hover::after { background: var(--accent-doux); }
    .v-faq[open] summary::after { transform: rotate(45deg); }
    .v-faq p { margin: 0 0 var(--e4); color: var(--texte-doux); line-height: 1.65; max-width: 62ch; }

    /* Appel final */
    .v-appel { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--e5); padding: clamp(28px, 5vw, 56px); border-radius: var(--r-xl); color: var(--sur-marque); background: radial-gradient(120% 140% at 100% 0%, var(--marque-fond-2) 0%, var(--marque-fond) 60%); }
    .v-appel h2 { color: var(--sur-marque); font-size: clamp(1.6rem, 3vw, 2.25rem); letter-spacing: -0.03em; }
    .v-appel p { margin: var(--e2) 0 0; color: var(--sur-marque-doux); max-width: 52ch; }
    .v-appel .btn { margin: 0; background: var(--surface); color: var(--accent-fort); border-color: var(--surface); }
    .v-appel .btn:hover { background: var(--accent-doux); border-color: var(--accent-doux); }

    /* Pied de page */
    .v-pied { border-top: 1px solid var(--bord); background: var(--surface); }
    .v-pied-grille { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 2fr) minmax(0, 2fr); gap: var(--e6) var(--e7); padding-block: var(--e7); font-size: var(--t-sm); color: var(--texte-faible); }
    .v-pied p { margin: var(--e3) 0 0; max-width: 54ch; line-height: 1.6; }
    .v-pied h2 { font-family: var(--police-texte); font-size: var(--t-xs); font-weight: 600; letter-spacing: 0.07em; text-transform: uppercase; color: var(--texte-faible); margin: 0 0 var(--e3); }
    .v-pied ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--e2); }
    .v-pied a { color: var(--texte-doux); text-decoration: none; }
    .v-pied a:hover { color: var(--accent-fort); text-decoration: underline; }
    .v-pied .marque { padding: 0; }
"""

STYLE_FORMULAIRES = """
    /* Inscription : même composition que l'écran de connexion */
    .v-inscription { padding-block: clamp(24px, 5vw, 64px); }
    .pub-inscription { display: grid; }
    .connexion-entete h1 { font-size: var(--t-2xl); letter-spacing: -0.03em; }
    .pub-inscription .connexion-form { justify-content: flex-start; }
    .pub-inscription details summary { cursor: pointer; color: var(--accent); font-size: var(--t-sm); font-weight: 500; }
    .v-forfait-info { margin: 0; font-size: var(--t-sm); color: var(--texte-doux); }
    pre.cgu { white-space: pre-wrap; font: inherit; font-size: var(--t-sm); line-height: 1.6; max-height: 18rem; overflow: auto; margin: var(--e2) 0 0; padding: var(--e3) var(--e4); border: 1px solid var(--bord); border-radius: var(--r-m); background: var(--surface-2); color: var(--texte-doux); }
    .piege { position: absolute; left: -10000px; width: 1px; height: 1px; overflow: hidden; }
    .v-apres { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--e4); counter-reset: apres; }
    .v-apres li { display: grid; grid-template-columns: 32px minmax(0, 1fr); gap: var(--e3); align-items: start; counter-increment: apres; }
    .v-apres li::before { content: counter(apres); width: 32px; height: 32px; border-radius: 50%; display: grid; place-items: center; background: color-mix(in srgb, var(--sur-marque) 14%, transparent); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--sur-marque) 24%, transparent); color: var(--sur-marque); font-weight: 700; font-size: var(--t-sm); }
    .v-apres strong { display: block; color: var(--sur-marque); font-weight: 600; }
    .v-apres span { display: block; font-size: var(--t-sm); color: var(--sur-marque-doux); line-height: 1.5; }

    /* Pages courriel : carte centrée */
    .v-courriel { padding-block: clamp(32px, 6vw, 80px); }
    .pub-centre { display: grid; place-items: start center; }
    .pub-carte { width: 100%; max-width: 460px; display: flex; flex-direction: column; gap: var(--e5); padding: var(--e6); background: var(--surface); border: 1px solid var(--bord); border-radius: var(--r-xl); box-shadow: var(--ombre-2); }
    .pub-carte-entete { display: flex; flex-direction: column; gap: var(--e3); }
    .pub-carte-entete h1 { font-size: var(--t-xl); letter-spacing: -0.02em; line-height: 1.15; }
    .pub-carte-entete p { margin: 0; color: var(--texte-doux); }
    .pub-pastille { width: 48px; height: 48px; border-radius: var(--r-l); display: grid; place-items: center; background: var(--accent-doux); color: var(--accent); }
    .pub-pastille .ico { width: 24px; height: 24px; }
    .pub-champs { display: flex; flex-direction: column; gap: var(--e4); }
    .pub-champs .btn, .pub-carte .btn { margin: 0; }
    .pub-carte-pied { margin: 0; padding-top: var(--e4); border-top: 1px solid var(--bord); font-size: var(--t-sm); display: flex; flex-wrap: wrap; justify-content: space-between; gap: var(--e2); }

    /* Retour d'action (classes posées par le JavaScript : message ok / message erreur) */
    .message { position: relative; padding: var(--e3) var(--e4) var(--e3) calc(var(--e4) + 20px); border-radius: var(--r-m); background: var(--surface-2); color: var(--texte); font-size: var(--t-sm); font-weight: 500; line-height: 1.5; }
    .message::before { content: ""; position: absolute; left: var(--e4); top: calc(var(--e3) + 5px); width: 10px; height: 10px; border-radius: 50%; background: var(--accent); }
    .message.ok { background: var(--bon-doux); color: var(--bon-texte); }
    .message.ok::before { background: var(--bon); box-shadow: 0 0 0 3px color-mix(in srgb, var(--bon) 25%, transparent); }
    .message.erreur { background: var(--critique-doux); color: var(--critique-texte); }
    .message.erreur::before { background: var(--critique); border-radius: 2px; transform: rotate(45deg); }
    .message a { color: inherit; font-weight: 700; }
    .message:focus { outline: none; }
    .message:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
"""

STYLE_MOUVEMENT = """
    /* ---------- Mouvement : déclaré uniquement si la personne n'a pas demandé de le réduire ---------- */
    @media (prefers-reduced-motion: no-preference) {
      /* Entrée de l'accroche : une seule fois ; le h1 reste visible d'emblée (LCP) */
      .v-hero-texte > :not(h1), .flux { animation: v-entree var(--v-dur-long) var(--v-ease) both; }
      .v-hero-texte > .v-lead { animation-delay: 120ms; }
      .v-hero-texte > .v-actions { animation-delay: 220ms; }
      .v-hero-texte > .v-garanties { animation-delay: 320ms; }
      .flux { animation-delay: 160ms; }
      @keyframes v-entree { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } }

      /* Apparition au défilement (uniquement si le script a posé html.js ; sinon tout est visible) */
      .js [data-reveal] { transition: opacity var(--v-dur-long) var(--v-ease), transform var(--v-dur-long) var(--v-ease); transition-delay: calc(var(--i, 0) * 70ms); }
      .js [data-reveal]:not(.vu) { opacity: 0; transform: translateY(18px); }

      /* Démonstration du flux : boucle de 12 s, transform et opacité seulement */
      .flux .fx-doc { animation: fx-doc 12s var(--v-ease) infinite both; animation-delay: calc(var(--i, 0) * 0.35s); }
      .flux .fx-ok { animation: fx-ok 12s var(--v-ease) infinite both; animation-delay: calc(var(--i, 0) * 0.35s); }
      .flux .fx-champ, .flux .fx-ligne { animation: fx-val 12s var(--v-ease) infinite both; animation-delay: calc(var(--i, 0) * 0.3s); }
      .flux .fx-verifier { animation: fx-verifier 12s var(--v-ease) infinite both; }
      .flux .fx-b-attente { animation: fx-attente 12s var(--v-ease) infinite both; }
      .flux .fx-b-ok { animation: fx-ok-bouton 12s var(--v-ease) infinite both; }
      .flux .fx-curseur { animation: fx-curseur 12s var(--v-ease) infinite both; }
      .flux .fl-1::after { animation: fx-l1 12s linear infinite both; }
      .flux .fl-2::after { animation: fx-l2 12s linear infinite both; }
      .flux .fl-3::after { animation: fx-l3 12s linear infinite both; }
      .flux.hors-ecran *, .flux.hors-ecran *::before, .flux.hors-ecran *::after, html.anim-pause .flux *, html.anim-pause .flux *::before, html.anim-pause .flux *::after { animation-play-state: paused !important; }
      @keyframes fx-doc { 0% { opacity: 0; transform: translateY(-14px); } 5% { opacity: 1; transform: none; } 92% { opacity: 1; transform: none; } 97%, 100% { opacity: 0; transform: none; } }
      @keyframes fx-ok { 0%, 22% { opacity: 0; transform: scale(0.4); } 27% { opacity: 1; transform: scale(1); } 92% { opacity: 1; transform: scale(1); } 97%, 100% { opacity: 0; transform: scale(1); } }
      @keyframes fx-val { 0%, 30% { opacity: 0; transform: translateX(-8px); } 36% { opacity: 1; transform: none; } 92% { opacity: 1; transform: none; } 97%, 100% { opacity: 0; transform: none; } }
      @keyframes fx-verifier { 0%, 46% { opacity: 0; transform: scale(0.85); } 50% { opacity: 1; transform: scale(1); } 92% { opacity: 1; transform: scale(1); } 97%, 100% { opacity: 0; transform: scale(1); } }
      @keyframes fx-attente { 0%, 56% { opacity: 0; } 60% { opacity: 1; } 69% { opacity: 1; transform: scale(1); } 71% { opacity: 1; transform: scale(0.95); } 74% { opacity: 0; transform: scale(1); } 100% { opacity: 0; } }
      @keyframes fx-ok-bouton { 0%, 72% { opacity: 0; transform: scale(0.96); } 76% { opacity: 1; transform: scale(1); } 92% { opacity: 1; transform: scale(1); } 97%, 100% { opacity: 0; transform: scale(1); } }
      @keyframes fx-curseur { 0%, 54% { opacity: 0; transform: translate(70px, 54px); } 58% { opacity: 1; transform: translate(70px, 54px); } 68% { opacity: 1; transform: translate(0, 0); } 71% { opacity: 1; transform: translate(0, 0) scale(0.86); } 74% { opacity: 1; transform: translate(0, 0) scale(1); } 80%, 100% { opacity: 0; transform: translate(0, 0); } }
      @keyframes fx-l1 { 0%, 28% { opacity: 1; } 32%, 96% { opacity: 0; } 100% { opacity: 1; } }
      @keyframes fx-l2 { 0%, 28% { opacity: 0; } 32%, 58% { opacity: 1; } 62%, 100% { opacity: 0; } }
      @keyframes fx-l3 { 0%, 58% { opacity: 0; } 62%, 94% { opacity: 1; } 97%, 100% { opacity: 0; } }

      /* Illustrations des étapes : jouées une fois quand l'étape entre à l'écran */
      .js .v-etape:not(.vu) .il-anim { opacity: 0; }
      .v-etape.vu .il-anim { animation: il-entree var(--v-dur-long) var(--v-ease) both; animation-delay: calc(var(--i, 0) * 140ms + 200ms); }
      .v-etape.vu .il-scan { animation: il-scan 2.4s ease-in-out 700ms 2 both; }
      .v-etape.vu .il-b-a { animation: il-b-a 4.2s var(--v-ease) 1s both; }
      .v-etape.vu .il-b-b { animation: il-b-b 4.2s var(--v-ease) 1s both; }
      @keyframes il-entree { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: none; } }
      @keyframes il-scan { 0% { opacity: 0; transform: translateY(-40px); } 15% { opacity: 1; } 85% { opacity: 1; } 100% { opacity: 0; transform: translateY(150px); } }
      @keyframes il-b-a { 0%, 30% { opacity: 1; transform: scale(1); } 38% { opacity: 1; transform: scale(0.96); } 45%, 100% { opacity: 0; transform: scale(1); } }
      @keyframes il-b-b { 0%, 38% { opacity: 0; transform: scale(0.96); } 48%, 100% { opacity: 1; transform: scale(1); } }
    }
    @media (prefers-reduced-motion: reduce) {
      .flux-controle .btn { display: none; }
      .v-rail-prog { transform: none; }
    }
    /* Etat de repos : la fin de chaque démonstration est le contenu complet */
    .il-bouton .il-b-b { opacity: 1; }
    .il-bouton .il-b-a { opacity: 0; }
"""

STYLE_ADAPTATIF = """
    @media (max-width: 1024px) {
      .v-etapes-zone, .v-faq-zone, .v-suivi { grid-template-columns: minmax(0, 1fr); gap: var(--e6); }
      .v-etapes-gauche, .v-faq-zone .v-entete { position: static; }
      .v-rail { display: none; }
      .v-pied-grille { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
      .v-pied-grille > :first-child { grid-column: 1 / -1; }
    }
    @media (max-width: 960px) {
      .v-hero-grille { grid-template-columns: minmax(0, 1fr); gap: var(--e6); }
      .v-limites { grid-template-columns: minmax(0, 1fr); }
    }
    @media (max-width: 720px) {
      .pub-lien-nav.optionnel { display: none; }
      .pub-entete .marque-sous { display: none; }
      .v-entete { margin-bottom: var(--e6); }
      .v-faits { grid-template-columns: minmax(0, 1fr); }
      .v-faits li { border-left: 0; border-top: 1px solid var(--bord); padding-inline: 0; }
      .v-faits li:first-child { border-top: 0; }
      .v-limites ul { grid-template-columns: minmax(0, 1fr); }
      .flux { padding: var(--e3); }
      .flux-legende li { font-size: var(--t-xs); }
      .flux-legende li b { display: none; }
      .flux-exemple { display: none; }
      .flux-scene { grid-template-columns: minmax(0, 1fr); gap: var(--e4); }
      .fx-col { min-height: 0; }
      .fx-col:not(:last-child)::after { top: auto; right: auto; left: 50%; bottom: calc(-1 * var(--e4) / 2 - 5px); transform: translateX(-50%) rotate(135deg); }
      .fx-curseur { right: 24%; }
      .apercu-corps { grid-template-columns: minmax(0, 1fr); }
      .apercu-nav { display: none; }
      .il { padding: var(--e4); }
      .v-appel { padding: var(--e5); }
      .v-pied-grille { grid-template-columns: minmax(0, 1fr); padding-block: var(--e6); }
      .pub-carte { padding: var(--e5); }
      .il-bouton { min-width: 0; width: 100%; }
    }
"""

STYLE_PUBLIC = STYLE_BASE + STYLE_FORMULAIRES + STYLE_MOUVEMENT + STYLE_ADAPTATIF
