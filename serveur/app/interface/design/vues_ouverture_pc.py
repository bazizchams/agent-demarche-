"""Carte « Ouvrir sur mon PC » de l'écran Étudiants et fiches (HTML statique, aucun contenu dynamique).

Le texte affiché ensuite (états, marche à suivre) est construit par nœuds DOM et `textContent` dans
`js_ouverture_pc.py`. Respecte GUIDE_DESIGN.md : tokens `var(--…)`, composants `.carte`, `.badge`, `.btn`.
"""

from __future__ import annotations

CSS_OUVERTURE_PC = """
    <style>
      #carte-ouverture-pc .ouverture-etat { display: flex; flex-direction: column; gap: var(--e2); margin: 0; }
      #carte-ouverture-pc .ouverture-etat p { margin: 0; }
      #carte-ouverture-pc .ouverture-marche { display: flex; flex-direction: column; gap: var(--e2); padding: var(--e3) var(--e4);
        background: var(--surface-2); border: 1px solid var(--bord); border-radius: var(--r-m); }
      #carte-ouverture-pc .ouverture-marche ol { margin: 0; padding-left: var(--e5); display: flex; flex-direction: column; gap: var(--e2); }
      #carte-ouverture-pc .ouverture-marche code { font-family: var(--police-code); font-size: var(--t-sm); background: var(--surface-3);
        padding: 1px var(--e2); border-radius: var(--r-s); }
      #carte-ouverture-pc .ouverture-alerte { color: var(--alerte-texte); }
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
        <p class="aide">Le navigateur s'ouvre dans une fenêtre visible sur votre PC et y ajoute les vœux validés du dossier actif (page de démonstration). L'agent s'arrête avant tout envoi officiel : vous vous connectez vous-même et vous résolvez vous-même tout contrôle de sécurité dans cette fenêtre.</p>
        <div id="ouverture-pc-etat" class="ouverture-etat" aria-live="polite"></div>
        <div id="ouverture-pc-marche" class="ouverture-marche cache"></div>
        <div class="carte-pied">
          <span class="note">Règle 1 : rien n'est envoyé au portail sans votre validation.</span>
          <div class="cellule-actions">
            <button id="btn-ouvrir-sur-pc" class="btn btn-primaire btn-sm" type="button">[[i:globe]]Ouvrir sur mon PC</button>
            <button id="btn-reprendre-ouverture-pc" class="btn btn-secondaire btn-sm cache" type="button">[[i:actualiser]]Reprendre la tâche</button>
            <button id="btn-ouverture-vers-validation" class="btn btn-contour btn-sm cache" type="button" data-aller-vers="vue-validation-humaine">[[i:validation]]Centre de validation</button>
          </div>
        </div>
      </section>
"""
)
