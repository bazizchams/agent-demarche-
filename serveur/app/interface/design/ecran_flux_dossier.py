"""Écran « Dossier automatique » : le parcours complet d'un étudiant, du dépôt des pièces au navigateur.

L'opérateur choisit (ou crée) un étudiant, dépose ses documents, lance l'analyse puis suit les 9 étapes.
Quand une étape attend un humain (confirmer les valeurs lues, valider un projet…), elle affiche le bouton
qui mène à l'écran concerné. L'agent s'arrête toujours avant l'envoi officiel (règle 1).

Ce module contient le gabarit HTML, le CSS et l'insertion dans la page (entrée de menu en tête de
navigation, section, script). Le JavaScript est dans `js_flux_dossier.py`.

Règles du guide de design : couleurs et espaces par `var(--token)`, aucun antislash, aucun `innerHTML`.
API consommée : `POST /api/v1/candidats/{id}/dossier-automatique/lancer`, `GET .../etat`, et le dépôt
existant `POST /api/v1/candidats/{id}/documents` (formulaire : `type_piece`, `fichier`).
"""

from __future__ import annotations

from app.interface.design.js_flux_dossier import JS_FLUX_DOSSIER
from app.interface.design.shell import bouton_nav, rendre_icones

_MARQUEUR_NAV = "<!-- nav:flux -->"
_MARQUEUR_FIN_MAIN = "  </main>\n\n  <script>"
_MARQUEUR_JS = "    // Connexion automatique dès l'ouverture de l'interface"

HTML_NAV = bouton_nav("vue-flux-dossier", "Dossier automatique", "envoi")

CSS_FLUX = """
    <style>
      #vue-flux-dossier .fd-grille { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 6fr); gap: var(--e4); align-items: start; }
      #vue-flux-dossier .fd-colonne { display: flex; flex-direction: column; gap: var(--e4); min-width: 0; }
      #vue-flux-dossier .carte { margin: 0; }
      #vue-flux-dossier .btn { margin: 0; }
      #vue-flux-dossier .fd-numero { display: inline-grid; place-items: center; width: 28px; height: 28px; margin-right: var(--e2); border-radius: 50%; background: var(--accent-doux); color: var(--accent-fort); font-family: var(--police-titre); font-size: var(--t-sm); font-weight: 700; vertical-align: middle; }
      #vue-flux-dossier .fd-choix { display: flex; flex-wrap: wrap; align-items: flex-end; gap: var(--e3); }
      #vue-flux-dossier .fd-choix .champ { flex: 1 1 240px; }
      #vue-flux-dossier .fd-nouveau { margin-top: var(--e3); border-top: 1px solid var(--bord); padding-top: var(--e3); }
      #vue-flux-dossier .fd-nouveau summary { cursor: pointer; font-weight: 600; color: var(--accent); min-height: var(--h-ctrl-sm); display: flex; align-items: center; gap: var(--e2); }
      #vue-flux-dossier .fd-nouveau-corps { display: flex; flex-wrap: wrap; align-items: flex-end; gap: var(--e3); margin-top: var(--e3); }
      #vue-flux-dossier .fd-nouveau-corps .champ { flex: 1 1 160px; }
      #vue-flux-dossier .fd-pp-corps { display: flex; flex-direction: column; gap: var(--e3); margin-top: var(--e3); min-width: 0; }
      #vue-flux-dossier .fd-pp-corps .champ { margin: 0; }
      #vue-flux-dossier .fd-pp-grille { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr)); gap: var(--e3); }
      #vue-flux-dossier .fd-pp-form { display: flex; flex-direction: column; gap: var(--e3); min-width: 0; margin: 0; padding: 0; border: 0; }
      #vue-flux-dossier .fd-pp-form legend { padding: 0; font-weight: 600; font-size: var(--t-sm); color: var(--texte-doux); }
      #vue-flux-dossier .fd-pp-libelle { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e1) var(--e2); }
      #vue-flux-dossier .fd-pp-extrait { overflow-wrap: anywhere; }
      #vue-flux-dossier .fd-pp-statut:empty { display: none; }
      #vue-flux-dossier .fd-pp-statut { display: flex; flex-direction: column; align-items: flex-start; gap: var(--e2); margin-top: var(--e3); min-width: 0; }
      #vue-flux-dossier .fd-pp-msg { margin: 0; padding: var(--e2) var(--e3); border-radius: var(--r-m); font-size: var(--t-sm); background: var(--surface-2); color: var(--texte); overflow-wrap: anywhere; }
      #vue-flux-dossier .fd-pp-ok { background: var(--bon-doux); color: var(--bon-texte); }
      #vue-flux-dossier .fd-pp-alerte { background: var(--alerte-doux); color: var(--alerte-texte); border-left: 4px solid var(--alerte); }
      #vue-flux-dossier .fd-pp-erreur { background: var(--critique-doux); color: var(--critique-texte); border-left: 4px solid var(--critique); }
      #vue-flux-dossier .fd-pp-actions { display: flex; flex-wrap: wrap; gap: var(--e2); }
      #vue-flux-dossier .fd-pp-squelette { display: flex; flex-direction: column; gap: var(--e2); }

      /* Zone de dépôt : le champ fichier natif couvre toute la zone (clic, clavier, glisser-déposer) */
      #vue-flux-dossier .fd-depot { position: relative; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--e2); min-height: 190px; padding: var(--e5) var(--e4); text-align: center; background: var(--surface-2); border: 2px dashed var(--bord-fort); border-radius: var(--r-l); transition: border-color var(--mo-dur-2) var(--mo-ease-out), background var(--mo-dur-2) var(--mo-ease-out), transform var(--mo-dur-2) var(--mo-ease-out); }
      #vue-flux-dossier .fd-depot:hover, #vue-flux-dossier .fd-depot.survol { border-color: var(--accent); background: var(--accent-doux); }
      #vue-flux-dossier .fd-depot.survol { border-style: solid; transform: scale(1.01); }
      #vue-flux-dossier .fd-depot-icone { transition: transform var(--mo-dur-3) var(--mo-ease-out), color var(--mo-dur-2) var(--mo-ease-out); }
      #vue-flux-dossier .fd-depot:hover .fd-depot-icone, #vue-flux-dossier .fd-depot.survol .fd-depot-icone { transform: translateY(-4px); }
      #vue-flux-dossier .fd-depot.survol .fd-depot-icone { animation: fd-flotte 900ms var(--mo-ease-inout) infinite; }
      @keyframes fd-flotte { 0%, 100% { transform: translateY(-2px); } 50% { transform: translateY(-8px); } }
      #vue-flux-dossier .fd-depot:focus-within { border-color: var(--accent); box-shadow: var(--anneau); }
      #vue-flux-dossier .fd-depot.inactif { opacity: 0.6; }
      #vue-flux-dossier .fd-depot input[type="file"] { position: absolute; inset: 0; width: 100%; height: 100%; min-height: 0; padding: 0; opacity: 0; cursor: pointer; }
      #vue-flux-dossier .fd-depot input[type="file"]:disabled { cursor: not-allowed; }
      #vue-flux-dossier .fd-depot-icone { display: grid; place-items: center; width: 52px; height: 52px; border-radius: var(--r-l); background: var(--surface); color: var(--accent); box-shadow: var(--ombre-1); }
      #vue-flux-dossier .fd-depot-icone .ico { width: 26px; height: 26px; }
      #vue-flux-dossier .fd-depot-titre { font-family: var(--police-titre); font-size: var(--t-md); font-weight: 600; color: var(--texte); }
      #vue-flux-dossier .fd-depot-aide { font-size: var(--t-sm); color: var(--texte-doux); max-width: 38ch; }

      #vue-flux-dossier .fd-fichiers { list-style: none; margin: var(--e3) 0 0; padding: 0; display: flex; flex-direction: column; gap: var(--e2); }
      #vue-flux-dossier .fd-fichier { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--e2) var(--e3); align-items: center; padding: var(--e3); border: 1px solid var(--bord); border-radius: var(--r-m); background: var(--surface); }
      #vue-flux-dossier .fd-fichier-nom { font-weight: 600; font-size: var(--t-sm); overflow-wrap: anywhere; }
      #vue-flux-dossier .fd-fichier-meta:empty { display: none; }
      #vue-flux-dossier .fd-fichier-meta { grid-column: 1 / -1; display: flex; flex-wrap: wrap; align-items: center; gap: var(--e2) var(--e3); }
      #vue-flux-dossier .fd-fichier-meta select { flex: 1 1 200px; min-width: 0; min-height: var(--h-ctrl-sm); font-size: var(--t-sm); }
      #vue-flux-dossier .fd-fichier-barre { grid-column: 1 / -1; position: relative; height: 4px; border-radius: var(--r-pilule); background: var(--surface-3); overflow: hidden; }
      #vue-flux-dossier .fd-fichier-remplie { height: 100%; width: 0; border-radius: var(--r-pilule); background: var(--accent-plein); transition: width var(--mo-dur-3) var(--mo-ease-out), background-color var(--mo-dur-2) var(--mo-ease-out); }
      #vue-flux-dossier .fd-barre-ok .fd-fichier-remplie { background: var(--bon); }
      #vue-flux-dossier .fd-barre-erreur .fd-fichier-remplie { background: var(--critique); }
      #vue-flux-dossier .fd-barre-envoi .fd-fichier-remplie { width: 40%; animation: fd-va-vient 1.2s var(--mo-ease-inout) infinite; }
      @keyframes fd-va-vient { 0% { transform: translateX(-100%); } 100% { transform: translateX(250%); } }
      #vue-flux-dossier .fd-fichier-message { grid-column: 1 / -1; }
      #vue-flux-dossier .fd-fichier-message:empty { display: none; }
      #vue-flux-dossier .fd-fichier-erreur { margin: 0; padding: var(--e2) var(--e3); border-radius: var(--r-s); background: var(--critique-doux); font-size: var(--t-sm); color: var(--critique-texte); }
      #vue-flux-dossier .fd-suggestion { font-size: var(--t-xs); color: var(--texte-faible); }
      #vue-flux-dossier .fd-depot-pied { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--e3); margin-top: var(--e3); }

      #vue-flux-dossier .fd-manquantes { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--e2); }
      #vue-flux-dossier .fd-manquantes li { display: flex; align-items: flex-start; gap: var(--e2); padding: var(--e2) var(--e3); border-radius: var(--r-m); background: var(--alerte-doux); color: var(--alerte-texte); font-size: var(--t-sm); }
      #vue-flux-dossier .fd-manquantes .ico { width: 18px; height: 18px; flex: none; margin-top: 1px; }
      #vue-flux-dossier .fd-complet { display: flex; align-items: center; gap: var(--e2); margin: 0; padding: var(--e2) var(--e3); border-radius: var(--r-m); background: var(--bon-doux); color: var(--bon-texte); font-size: var(--t-sm); font-weight: 600; }
      #vue-flux-dossier .fd-complet .ico { width: 18px; height: 18px; flex: none; }

      /* Progression et lancement */
      #vue-flux-dossier .fd-lancement { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e3); margin-top: var(--e4); }
      #vue-flux-dossier .fd-lancement .btn-lg { flex: 1 1 240px; }
      #vue-flux-dossier .fd-progres-chiffre { font-family: var(--police-titre); font-size: min(var(--t-2xl), 28px); font-weight: 700; line-height: 1; color: var(--accent-fort); }
      #vue-flux-dossier .fd-progres-tete { display: flex; align-items: baseline; justify-content: space-between; gap: var(--e3); margin-bottom: var(--e2); }
      #vue-flux-dossier .barre-progression-remplie { position: relative; overflow: hidden; }
      #vue-flux-dossier .barre-progression.fd-actif .barre-progression-remplie::after { content: ""; position: absolute; inset: 0; background-image: linear-gradient(90deg, transparent 0, var(--miroitement) 50%, transparent 100%); background-size: 60% 100%; background-repeat: no-repeat; animation: fd-glisse 1.6s linear infinite; }
      #vue-flux-dossier .fd-lancer[data-etat="cours"]::before { content: ""; width: 14px; height: 14px; margin-right: var(--e2); border-radius: 50%; border: 2px solid currentColor; border-right-color: transparent; animation: rotation 0.8s linear infinite; }
      #vue-flux-dossier .fd-lancer[data-etat="cours"] .ico { display: none; }
      #vue-flux-dossier .btn { transition: transform var(--mo-dur-2) var(--mo-ease-spring), background-color var(--mo-dur-1) var(--mo-ease-out), border-color var(--mo-dur-1) var(--mo-ease-out), box-shadow var(--mo-dur-1) var(--mo-ease-out); }
      #vue-flux-dossier .fd-pret { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e3); margin: var(--e4) 0 0; padding: var(--e3) var(--e4); border-radius: var(--r-m); border: 1px solid var(--bon); background: var(--bon-doux); color: var(--bon-texte); }
      #vue-flux-dossier .fd-pret > div { flex: 1 1 220px; display: flex; flex-direction: column; gap: 2px; font-size: var(--t-sm); }
      #vue-flux-dossier .fd-pret strong { font-size: var(--t-base); }
      #vue-flux-dossier .badge-ok { background: color-mix(in srgb, var(--bon) 12%, transparent); color: var(--bon-texte); }
      :root[data-theme="dark"] #vue-flux-dossier .badge-ok { color: color-mix(in srgb, var(--bon-texte) 85%, var(--texte-doux)); }
      @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) #vue-flux-dossier .badge-ok { color: color-mix(in srgb, var(--bon-texte) 85%, var(--texte-doux)); } }
      #vue-flux-dossier .fd-pret .btn-primaire { flex: none; }
      #vue-flux-dossier .fd-pret-icone { width: 28px; height: 28px; flex: none; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
      #vue-flux-dossier .fd-pret-rond, #vue-flux-dossier .fd-pret-coche { stroke-dasharray: 1; stroke-dashoffset: 0; }
      #vue-flux-dossier .fd-pret-anime { animation: mo-entree var(--mo-dur-3) var(--mo-ease-out) both; }
      #vue-flux-dossier .fd-pret-anime .fd-pret-rond { animation: fd-trace var(--mo-dur-4) var(--mo-ease-out) both; }
      #vue-flux-dossier .fd-pret-anime .fd-pret-coche { animation: fd-trace var(--mo-dur-3) var(--mo-ease-out) 500ms both; }
      #vue-flux-dossier .fd-halo { animation: fd-halo var(--mo-dur-4) var(--mo-ease-out) 1; }
      @keyframes fd-halo { 0% { box-shadow: var(--ombre-1), 0 0 0 0 var(--bon); } 100% { box-shadow: var(--ombre-1), 0 0 0 10px transparent; } }
      #vue-flux-dossier .fd-vide-bloc { display: flex; flex-direction: column; align-items: center; gap: var(--e2); }
      #vue-flux-dossier .fd-vide-bloc .btn { margin-top: var(--e2); }
      #vue-flux-dossier .fd-illu-lien { stroke: var(--bord-fort); stroke-width: 1.5; stroke-dasharray: 2 4; stroke-linecap: round; }
      #vue-flux-dossier .fd-illu { width: 168px; max-width: 60%; height: auto; margin-bottom: var(--e2); }
      #vue-flux-dossier .fd-grille:not(.cache) .carte { animation: mo-entree var(--mo-dur-3) var(--mo-ease-out) both; }
      #vue-flux-dossier .fd-grille:not(.cache) .fd-colonne > :nth-child(2) { animation-delay: var(--mo-pas); }
      #vue-flux-dossier .fd-grille:not(.cache) .fd-colonne > :nth-child(3) { animation-delay: calc(var(--mo-pas) * 2); }
      #vue-flux-dossier .fd-grille:not(.cache) .fd-colonne + .fd-colonne > :nth-child(1) { animation-delay: var(--mo-pas); }
      #vue-flux-dossier .fd-erreur:not(.cache) { animation: mo-entree var(--mo-dur-2) var(--mo-ease-out) both; }
      #vue-flux-dossier .fd-progres-texte { margin: var(--e2) 0 0; font-size: var(--t-sm); color: var(--texte-doux); }
      #vue-flux-dossier .fd-erreur { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e2) var(--e3); margin: 0 0 var(--e4); padding: var(--e3) var(--e4); border-radius: var(--r-m); border-left: 4px solid var(--critique); background: var(--critique-doux); color: var(--critique-texte); font-size: var(--t-sm); }
      #vue-flux-dossier .fd-erreur .ico { width: 18px; height: 18px; flex: none; }
      #vue-flux-dossier .fd-erreur span { flex: 1 1 200px; }

      /* Les 9 étapes */
      #vue-flux-dossier .fd-etapes { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
      #vue-flux-dossier .fd-etape { position: relative; display: grid; grid-template-columns: 34px minmax(0, 1fr); gap: 0 var(--e3); padding-bottom: var(--e4); }
      #vue-flux-dossier .fd-etape:last-child { padding-bottom: 0; }
      #vue-flux-dossier .fd-etape::before { content: ""; position: absolute; left: 16px; top: 36px; bottom: 2px; width: 2px; background: var(--bord); border-radius: 2px; }
      #vue-flux-dossier .fd-etape::after { content: ""; position: absolute; left: 16px; top: 36px; bottom: 2px; width: 2px; background: var(--bon); border-radius: 2px; transform: scaleY(0); transform-origin: top; transition: transform var(--mo-dur-3) var(--mo-ease-out); }
      #vue-flux-dossier .fd-etape:last-child::before, #vue-flux-dossier .fd-etape:last-child::after { display: none; }
      #vue-flux-dossier .fd-etape-termine::after { transform: scaleY(1); }
      #vue-flux-dossier .fd-marqueur { position: relative; z-index: 1; display: grid; place-items: center; width: 34px; height: 34px; border-radius: 50%; background: var(--surface); border: 2px solid var(--bord-fort); color: var(--texte-doux); font-family: var(--police-titre); font-size: var(--t-sm); font-weight: 700; transition: background-color var(--mo-dur-3) var(--mo-ease-out), border-color var(--mo-dur-3) var(--mo-ease-out), color var(--mo-dur-3) var(--mo-ease-out), border-radius var(--mo-dur-3) var(--mo-ease-out); }
      #vue-flux-dossier .fd-marqueur .ico { width: 18px; height: 18px; }
      #vue-flux-dossier .fd-etape-termine .fd-marqueur { background: var(--bon-doux); border-color: var(--bon); color: var(--bon-texte); }
      #vue-flux-dossier .fd-etape-en_cours .fd-marqueur { background: var(--accent-doux); border-color: var(--accent); color: var(--accent-fort); }
      #vue-flux-dossier .fd-etape-en_cours .fd-marqueur::after { content: ""; position: absolute; inset: -5px; border-radius: 50%; border: 2px solid var(--accent); opacity: 0; animation: fd-respire 2.4s var(--mo-ease-inout) infinite; }
      /* À vérifier et bloqué se lisent sans la couleur : forme (cercle pointillé / carré arrondi), icône et libellé du badge */
      #vue-flux-dossier .fd-etape-a_verifier .fd-marqueur { background: var(--alerte-doux); border: 2px dashed var(--alerte); color: var(--alerte-texte); }
      #vue-flux-dossier .fd-etape-bloque .fd-marqueur { background: var(--critique-doux); border-color: var(--critique); border-radius: var(--r-m); color: var(--critique-texte); }
      #vue-flux-dossier .fd-coche { stroke-dasharray: 1; stroke-dashoffset: 0; }
      #vue-flux-dossier .fd-coche-trace { stroke-dashoffset: 1; animation: fd-trace var(--mo-dur-3) var(--mo-ease-out) 120ms forwards; }
      #vue-flux-dossier .fd-marqueur-pop { animation: fd-pop var(--mo-dur-3) var(--mo-ease-out); }
      #vue-flux-dossier .fd-entree { animation: mo-entree var(--mo-dur-3) var(--mo-ease-out) both; }
      @keyframes fd-respire { 0%, 100% { opacity: 0; transform: scale(0.9); } 50% { opacity: 0.55; transform: scale(1.12); } }
      @keyframes fd-trace { from { stroke-dashoffset: 1; } to { stroke-dashoffset: 0; } }
      @keyframes fd-pop { 0% { transform: scale(0.82); } 60% { transform: scale(1.1); } 100% { transform: scale(1); } }
      @keyframes fd-glisse { from { background-position: 200% 0; } to { background-position: -100% 0; } }
      #vue-flux-dossier .fd-corps { display: flex; flex-direction: column; gap: var(--e2); min-width: 0; padding-top: 2px; }
      #vue-flux-dossier .fd-ligne { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--e1) var(--e3); }
      #vue-flux-dossier .fd-titre { margin: 0; font-size: var(--t-base); font-weight: 600; color: var(--texte); line-height: 1.3; }
      #vue-flux-dossier .fd-detail { margin: 0; font-size: var(--t-sm); color: var(--texte-doux); overflow-wrap: anywhere; }
      #vue-flux-dossier .fd-compteurs { display: flex; flex-wrap: wrap; gap: var(--e1) var(--e2); margin: 0; padding: 0; list-style: none; }
      #vue-flux-dossier .fd-compteurs li { padding: 2px var(--e2); border-radius: var(--r-pilule); background: var(--surface-2); border: 1px solid var(--bord); color: var(--texte-doux); font-size: var(--t-xs); }
      #vue-flux-dossier .fd-actions { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e2); margin-top: var(--e1); }
      #vue-flux-dossier .fd-etat-pc { margin: 0; font-size: var(--t-sm); color: var(--texte-doux); }
      #vue-flux-dossier .fd-regle { margin: var(--e3) 0 0; }
      #vue-flux-dossier .fd-vide { padding: var(--e6) var(--e4); }
      #vue-flux-dossier .fd-squelette { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--e4); }
      #vue-flux-dossier .fd-squelette li { display: grid; grid-template-columns: 34px minmax(0, 1fr); gap: var(--e3); align-items: center; }
      #vue-flux-dossier .fd-squelette .squelette-rond { width: 34px; height: 34px; border-radius: 50%; }

      #vue-flux-dossier .fd-illu { display: block; overflow: visible; }
      #vue-flux-dossier .fd-illu-fond {
        fill: var(--surface-2);
        stroke: var(--bord-fort);
        stroke-width: 1.5;
        stroke-linejoin: round;
      }
      #vue-flux-dossier .fd-illu-papier {
        fill: var(--surface);
        stroke: var(--bord-fort);
        stroke-width: 1.5;
        stroke-linejoin: round;
      }
      #vue-flux-dossier .fd-illu-trait {
        fill: none;
        stroke: var(--texte-faible);
        stroke-width: 1.5;
        stroke-linecap: round;
      }
      #vue-flux-dossier .fd-illu-accent {
        fill: var(--accent-doux);
        stroke: var(--accent);
        stroke-width: 1.5;
        stroke-linejoin: round;
      }
      #vue-flux-dossier .fd-illu-point {
        fill: var(--surface);
        stroke: var(--bord-fort);
        stroke-width: 1.5;
      }
      #vue-flux-dossier .fd-illu-coche {
        fill: none;
        stroke: var(--bon);
        stroke-width: 2.5;
        stroke-linecap: round;
        stroke-linejoin: round;
      }
      @keyframes fd-illu-entree {
        from { opacity: 0; }
        to { opacity: 1; }
      }
      @keyframes fd-illu-trace {
        from { stroke-dashoffset: 1; }
        to { stroke-dashoffset: 0; }
      }
      #vue-flux-dossier .fd-illu-pas {
        animation: fd-illu-entree var(--mo-dur-3) var(--mo-ease-out) both;
      }
      #vue-flux-dossier circle.fd-illu-pas:nth-of-type(2) {
        animation-delay: calc(var(--mo-pas) * 3);
      }
      #vue-flux-dossier circle.fd-illu-pas:nth-of-type(3) {
        animation-delay: calc(var(--mo-pas) * 5);
      }
      #vue-flux-dossier .fd-illu-coche-trace {
        stroke-dasharray: 1;
        stroke-dashoffset: 1;
        animation: fd-illu-trace var(--mo-dur-4) var(--mo-ease-inout) 500ms both;
      }
      @media (max-width: 1100px) { #vue-flux-dossier .fd-grille { grid-template-columns: minmax(0, 1fr); } }
      @media (max-width: 600px) {
        #vue-flux-dossier .fd-depot { min-height: 160px; padding: var(--e4) var(--e3); }
        #vue-flux-dossier .fd-progres-chiffre { font-size: var(--t-xl); }
        #vue-flux-dossier .fd-lancement .btn-lg { flex-basis: 100%; }
        #vue-flux-dossier .fd-actions .btn { flex: 1 1 100%; justify-content: center; }
      }
      @media (prefers-reduced-motion: reduce) {
        #vue-flux-dossier *, #vue-flux-dossier *::before, #vue-flux-dossier *::after { animation: none !important; transition: none !important; }
        #vue-flux-dossier .fd-coche-trace, #vue-flux-dossier .fd-illu-coche-trace { stroke-dashoffset: 0; }
        #vue-flux-dossier .fd-etape-en_cours .fd-marqueur::after { opacity: 0.55; }
        #vue-flux-dossier .fd-barre-envoi .fd-fichier-remplie { width: 100%; }
        #vue-flux-dossier .fd-lancer[data-etat="cours"]::before { border-right-color: currentColor; }
      }
    </style>"""

HTML_VUE = rendre_icones(
    """
    <!-- Dossier automatique : dépôt des pièces, lancement, suivi des 9 étapes -->
    <section id="vue-flux-dossier" class="vue-ecran cache" aria-labelledby="fd-titre-page">"""
    + CSS_FLUX
    + """
      <header class="page-entete">
        <div>
          <h2 id="fd-titre-page">Dossier automatique</h2>
          <p class="lead">Déposez les documents d'un étudiant : l'agent lit les pièces, prépare le dossier et s'arrête avant tout envoi officiel.</p>
        </div>
      </header>

      <div id="fd-erreur" class="fd-erreur cache" role="alert">
        [[i:alerte]]<span id="fd-erreur-texte"></span>
        <button id="fd-btn-reessayer" class="mo-press btn btn-contour btn-sm" type="button">[[i:actualiser]]Réessayer</button>
      </div>

      <section class="carte" aria-labelledby="fd-titre-etudiant">
        <div class="carte-entete"><h3 id="fd-titre-etudiant"><span class="fd-numero" aria-hidden="true">1</span>Étudiant</h3></div>
        <div class="fd-choix">
          <label class="champ" for="fd-etudiant">Dossier à traiter
            <select id="fd-etudiant"><option value="">Chargement des étudiants…</option></select>
          </label>
        </div>
        <details id="fd-nouveau" class="fd-nouveau">
          <summary>[[i:plus]]Nouvel étudiant</summary>
          <div class="fd-nouveau-corps">
            <label class="champ" for="fd-nom">Nom de famille <span class="requis">*</span>
              <input id="fd-nom" type="text" autocomplete="off" aria-describedby="fd-nouveau-aide" /></label>
            <label class="champ" for="fd-prenom">Prénom <span class="requis">*</span>
              <input id="fd-prenom" type="text" autocomplete="off" /></label>
            <button id="fd-btn-creer" class="mo-press btn btn-secondaire" type="button">Créer la fiche</button>
          </div>
          <p id="fd-nouveau-aide" class="champ-aide">Le reste de la fiche (passeport, projet d'études) sera lu dans les documents, ou se complète dans « Étudiants et fiches ».</p>
        </details>
        <details id="fd-passeport" class="fd-nouveau">
          <summary>[[i:haut]]Créer la fiche depuis le passeport</summary>
          <div class="fd-pp-corps">
            <label class="champ" for="fd-pp-fichier">Passeport (PDF, PNG ou JPEG)
              <input id="fd-pp-fichier" type="file" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" aria-describedby="fd-pp-aide" />
              <span id="fd-pp-aide" class="champ-aide">L'agent lit le passeport et vous propose des valeurs. Rien n'est enregistré avant votre confirmation.</span>
            </label>
            <div id="fd-pp-zone"></div>
          </div>
          <div id="fd-pp-statut" class="fd-pp-statut" role="status" aria-live="polite" aria-atomic="false"></div>
        </details>
      </section>

      <div id="fd-vide" class="carte etat-vide fd-vide cache"></div>

      <div id="fd-contenu" class="fd-grille cache">
        <div class="fd-colonne">
          <section class="carte" aria-labelledby="fd-titre-depot">
            <div class="carte-entete"><h3 id="fd-titre-depot"><span class="fd-numero" aria-hidden="true">2</span>Documents de l'étudiant</h3></div>
            <div id="fd-zone-depot" class="fd-depot">
              <span class="fd-depot-icone">[[i:haut]]</span>
              <span class="fd-depot-titre">Glissez les documents ici</span>
              <span class="fd-depot-aide">ou cliquez pour les choisir (plusieurs à la fois). PDF, PNG ou JPEG.</span>
              <input id="fd-fichiers" type="file" multiple accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" aria-label="Choisir les documents à déposer" />
            </div>
            <ul id="fd-liste-fichiers" class="fd-fichiers" aria-label="Documents à envoyer"></ul>
            <div id="fd-depot-pied" class="fd-depot-pied cache">
              <span id="fd-depot-resume" class="note" aria-live="polite"></span>
              <button id="fd-btn-envoyer" class="mo-press btn btn-primaire" type="button">[[i:haut]]Envoyer les documents</button>
            </div>
          </section>
          <section class="carte" aria-labelledby="fd-titre-manquantes">
            <div class="carte-entete"><h3 id="fd-titre-manquantes">Pièces manquantes</h3><span id="fd-badge-manquantes" class="badge badge-nu">—</span></div>
            <div id="fd-manquantes" aria-live="polite"></div>
          </section>
        </div>

        <div class="fd-colonne">
          <section id="fd-carte-analyse" class="carte" aria-labelledby="fd-titre-analyse">
            <div class="carte-entete"><h3 id="fd-titre-analyse"><span class="fd-numero" aria-hidden="true">3</span>Analyse du dossier</h3></div>
            <div class="fd-progres-tete">
              <span id="fd-progres-libelle" class="surtitre">Progression</span>
              <span id="fd-progres-chiffre" class="fd-progres-chiffre"><span class="fd-progres-valeur">0</span> %</span>
            </div>
            <div id="fd-barre" class="barre-progression" role="progressbar" aria-labelledby="fd-progres-libelle" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100"><div id="fd-barre-remplie" class="barre-progression-remplie" style="width:0%"></div></div>
            <div id="fd-pret" class="fd-pret cache">
              <svg class="fd-pret-icone" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle class="fd-pret-rond" cx="12" cy="12" r="10" pathLength="1" /><path class="fd-pret-coche" d="M7.5 12.5l3 3 6-6.5" pathLength="1" /></svg>
              <div><strong>Dossier prêt pour votre validation</strong><span>L'agent a préparé le dossier. Rien n'a été envoyé : l'envoi officiel attend la validation d'un employé.</span></div>
              <button class="mo-press btn btn-primaire btn-sm" type="button" data-aller-vers="vue-validation-humaine">Passer à la validation</button>
            </div>
            <p id="fd-progres-texte" class="fd-progres-texte" role="status" aria-live="polite">Aucune analyse lancée.</p>
            <div class="fd-lancement">
              <button id="fd-btn-lancer" class="mo-press btn btn-primaire btn-lg fd-lancer" type="button">[[i:envoi]]Lancer l'analyse</button>
              <button id="fd-btn-actualiser" class="mo-press btn btn-fantome" type="button">[[i:actualiser]]Actualiser</button>
            </div>
            <p class="note fd-regle">L'agent s'arrête avant l'envoi officiel : rien n'part sans votre validation (règle 1).</p>
          </section>
          <section id="fd-carte-discussion" class="carte cache" aria-labelledby="fd-titre-discussion">
            <div class="carte-entete"><h3 id="fd-titre-discussion">Discussion en direct avec l'agent</h3></div>
            <div id="fd-discussion"></div>
          </section>
          <section class="carte" aria-labelledby="fd-titre-etapes">
            <div class="carte-entete"><h3 id="fd-titre-etapes">Les 9 étapes</h3></div>
            <div id="fd-etapes-zone" aria-live="off"></div>
          </section>
        </div>
      </div>
    </section>
"""
)


def _inserer(html: str, marqueur: str, ajout: str, *, avant: bool) -> str:
    if html.count(marqueur) != 1:
        raise RuntimeError("Marqueur d'insertion introuvable ou ambigu : " + marqueur[:60])
    return html.replace(marqueur, ajout + marqueur if avant else marqueur + ajout)


def assembler_flux_dossier(html_base: str) -> str:
    """Insère l'écran dans la page : entrée de menu en tête, section, puis script."""
    html = _inserer(html_base, _MARQUEUR_NAV, HTML_NAV, avant=True)
    html = _inserer(html, _MARQUEUR_FIN_MAIN, HTML_VUE + "\n", avant=True)
    return _inserer(html, _MARQUEUR_JS, JS_FLUX_DOSSIER, avant=True)
