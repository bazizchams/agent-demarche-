"""Carte « Ouvrir sur mon PC » de l'écran Étudiants et fiches (HTML statique, aucun contenu dynamique).

Le texte affiché ensuite (états, marche à suivre) est construit par nœuds DOM et `textContent` dans
`js_ouverture_pc.py`. Respecte GUIDE_DESIGN.md : tokens `var(--…)`, composants `.carte`, `.badge`, `.btn`.
"""

from __future__ import annotations

CSS_OUVERTURE_PC = """
    <style>
      #carte-ouverture-pc .ouverture-etat { display: flex; flex-direction: column; gap: var(--e2); margin: 0 0 var(--e3); }
      #carte-ouverture-pc .ouverture-etat p { margin: 0; }
      #carte-ouverture-pc .ouverture-actions { display: flex; flex-wrap: wrap; gap: var(--e2); margin-bottom: var(--e4); }
      #carte-ouverture-pc .ouverture-actions .btn { margin: 0; }
      #carte-ouverture-pc .ouverture-detail { margin: 0 0 var(--e3); }
      #carte-ouverture-pc details.ouverture-marche { background: var(--surface-2); border: 1px solid var(--bord); border-radius: var(--r-m); }
      #carte-ouverture-pc details.ouverture-marche > summary { cursor: pointer; padding: var(--e3) var(--e4); min-height: var(--h-ctrl); display: flex; align-items: center; justify-content: space-between; gap: var(--e3);
        font-weight: 600; font-size: var(--t-sm); list-style: none; border-radius: var(--r-m); }
      #carte-ouverture-pc details.ouverture-marche > summary::-webkit-details-marker { display: none; }
      #carte-ouverture-pc details.ouverture-marche > summary::after { content: ""; width: 8px; height: 8px; flex: none; border-right: 2px solid var(--texte-doux); border-bottom: 2px solid var(--texte-doux); transform: rotate(45deg); transition: transform var(--d2) var(--courbe); }
      #carte-ouverture-pc details.ouverture-marche[open] > summary::after { transform: rotate(-135deg); }
      #carte-ouverture-pc .ouverture-marche-corps { display: flex; flex-direction: column; gap: var(--e2); padding: 0 var(--e4) var(--e4); }
      #carte-ouverture-pc .ouverture-marche ol { margin: 0; padding-left: var(--e5); display: flex; flex-direction: column; gap: var(--e2); }
      #carte-ouverture-pc .ouverture-marche code { font-family: var(--police-code); font-size: var(--t-sm); background: var(--surface-3);
        padding: 1px var(--e2); border-radius: var(--r-s); overflow-wrap: anywhere; }
      #carte-ouverture-pc .ouverture-alerte { color: var(--alerte-texte); }
      @media (prefers-reduced-motion: reduce) { #carte-ouverture-pc details.ouverture-marche > summary::after { transition: none; } }
    </style>
"""

HTML_OUVERTURE_PC = (
    CSS_OUVERTURE_PC
    + """
      <section id="carte-ouverture-pc" class="carte" aria-labelledby="titre-ouverture-pc">
        <div class="carte-entete">
          <div>
            <span class="surtitre">Sur le PC du bureau</span>
            <h3 id="titre-ouverture-pc">Ouvrir sur mon PC</h3>
          </div>
          <span id="ouverture-pc-badge" class="badge badge-nu">—</span>
        </div>
        <div class="ouverture-actions">
          <button id="btn-ouvrir-sur-pc" class="btn btn-primaire btn-sm" type="button">[[i:globe]]Ouvrir sur mon PC</button>
          <button id="btn-reprendre-ouverture-pc" class="btn btn-secondaire btn-sm cache" type="button">[[i:actualiser]]Reprendre la tâche</button>
          <button id="btn-ouverture-vers-validation" class="btn btn-contour btn-sm cache" type="button" data-aller-vers="vue-validation-humaine">[[i:validation]]Centre de validation</button>
        </div>
        <div id="ouverture-pc-etat" class="ouverture-etat" aria-live="polite"></div>
        <details id="ouverture-pc-marche" class="ouverture-marche cache"></details>
        <div class="carte-pied">
          <span class="note">Règle 1 : rien n'est envoyé au portail sans votre validation. La page de démonstration s'ouvre dans une fenêtre visible sur votre PC : vous vous connectez vous-même et résolvez vous-même tout contrôle de sécurité.</span>
        </div>
      </section>
"""
)
