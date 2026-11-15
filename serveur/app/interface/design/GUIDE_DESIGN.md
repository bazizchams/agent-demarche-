# Guide du système de design (interface web)

Source unique : `styles.py` (tokens + composants), `shell.py` (coquille, icônes `[[i:nom]]`).
Référence visuelle : écran de connexion et tableau de bord (`tableau_bord.py`).

## Règles pour refaire un écran

- Couleurs, rayons, ombres, espacements : **toujours `var(--token)`**, jamais de couleur littérale
  (le thème sombre ne redéfinit que les tokens). Aucun antislash dans les chaînes Python de l'interface.
- Espacer les frères avec `display:flex|grid` + `gap`, pas de marges par élément.
  Attention : `.btn` garde une marge héritée (`0 8px 8px 0`) ; dans un conteneur à `gap`, ajouter `.btn { margin: 0 }`
  (déjà fait pour `.page-actions`, `.pile-actions`, `.raccourcis`, `.carte-entete`, `.carte-pied`, `.modale-pied`, `.section-entete`).
- JS : nœuds DOM + `textContent` (jamais `innerHTML`), pas de `console.log`. Ne renommer aucun `id`, `data-*`, fonction.
- Navigation déclarative : `data-aller-vers="vue-x"` (+ `data-ouvrir="id-details"` facultatif) sur n'importe quel bouton.
- Masquer : classe `.cache`. Texte pour lecteur d'écran seulement : `.sr-only`.
- Icônes : `[[i:nom]]` (accueil, etudiants, pieces, conseiller, globe, envoi, procedures, validation, recaps, audit,
  moniteur, abonnement, menu, fermer, soleil, lune, retour, suivant, actualiser, haut, bas, micro, plus, externe,
  cadenas, utilisateur, dossier, calendrier, coche, alerte, pause, sortie). Nom inconnu = erreur Python.

## Tokens (`:root`, redéfinis en sombre)

| Rôle | Tokens |
|---|---|
| Fonds | `--fond` (page), `--fond-creux`, `--surface` (cartes), `--surface-2` (zones calmes, en-têtes de tableau), `--surface-3` (pistes, survol fort) |
| Bordures | `--bord`, `--bord-fort` (cartes, zone de dépôt en pointillés), `--bord-champ` (contour des champs de saisie, voir plus bas) |
| Texte | `--texte`, `--texte-doux` (secondaire), `--texte-faible` (aide, libellés ; AA garanti) |
| Accent indigo | `--accent` (liens, texte), `--accent-fort`, `--accent-doux` (fond teinté), `--accent-moyen`, `--accent-plein` + `--accent-plein-survol` (fond des boutons pleins), `--sur-accent` |
| Marque | `--marque-fond`, `--marque-fond-2`, `--sur-marque`, `--sur-marque-doux` (panneau indigo) |
| Sémantique | `--bon`, `--bon-doux`, `--bon-texte` ; `--alerte`, `--alerte-doux`, `--alerte-texte` ; `--critique`, `--critique-doux`, `--critique-texte` |
| Ombres | `--ombre-1` (cartes), `--ombre-2` (survol, panneaux), `--ombre-flottante` (toast, tiroir, modale), `--anneau` (focus champ), `--voile` (fond de modale) |
| Typo | `--police-titre` (Bricolage Grotesque), `--police-texte` (Inter), `--police-code` ; tailles `--t-xs` 12, `--t-sm` 13, `--t-base` 15, `--t-md` 17, `--t-lg` 21, `--t-xl` 28, `--t-2xl` 36, `--t-3xl` 44 px |
| Espaces | `--e1` 4, `--e2` 8, `--e3` 12, `--e4` 16, `--e5` 24, `--e6` 32, `--e7` 48, `--e8` 64 px |
| Rayons | `--r-s` 6, `--r-m` 10, `--r-l` 14, `--r-xl` 20, `--r-pilule` |
| Contrôles | `--h-ctrl-sm` 32, `--h-ctrl` 40, `--h-ctrl-lg` 48 px |
| Mouvement | `--d1` 150 ms, `--d2` 200 ms, `--d3` 320 ms, `--courbe` (réduit à 1 ms si `prefers-reduced-motion`) |

Alias hérités encore valides : `--bleu-primaire`, `--bleu-clair`, `--carte`, `--bordure`, `--rayon`, `--vert-*`, `--orange-*`, `--rouge-*`.

## Composants

**En-tête d'écran**
```html
<header class="page-entete"><div><h2>Étudiants</h2><p class="lead">Une phrase d'objectif.</p></div>
  <div class="page-actions"><button class="btn btn-primaire" type="button">[[i:plus]]Nouvel étudiant</button></div></header>
```
**En-tête de section** (`.surtitre` = petit libellé majuscule)
```html
<div class="section-entete"><div><h3>Pièces</h3><p>Description courte.</p></div><button class="btn btn-fantome btn-sm" type="button">Tout voir</button></div>
```
**Boutons** : `.btn` + `.btn-primaire` | `.btn-secondaire` (indigo doux) | `.btn-contour` | `.btn-fantome` | `.btn-danger` | `.btn-lien` ;
tailles `.btn-sm`, `.btn-lg`, `.btn-icone` (+ `aria-label`), `.btn-bloc` (pleine largeur) ; `aria-busy="true"` = spinner (boutons primaires).
```html
<button class="btn btn-primaire" type="button">Valider</button> <button class="btn btn-danger btn-sm" type="button">Supprimer</button>
```
**Champs** (`label` = colonne libellé + champ ; erreur via `aria-invalid`)
```html
<label class="champ" for="f-nom">Nom de famille <span class="requis">*</span>
  <input id="f-nom" type="text" aria-invalid="true" aria-describedby="f-nom-err" />
  <span class="champ-aide">Comme sur le passeport.</span><span id="f-nom-err" class="champ-erreur">Champ obligatoire.</span></label>
```
Grilles de formulaire : `.grille-form` (auto 220 px), `.grille-2` (auto 340 px). Cases : `<label class="case"><input type="checkbox" /> Texte</label>`.

**Cartes** : `.carte` (+ `.carte-entete`, `.carte-pied`), `.carte-sobre` (pointillés), `.carte-cliquable`, `.carte-action` (liseré), `details.carte` (repliable).
```html
<section class="carte"><div class="carte-entete"><h3>Titre</h3><span class="badge badge-ok">À jour</span></div>…<div class="carte-pied">…</div></section>
```
**Chiffres clés** : `.grille-kpi > .kpi` (`.kpi-alerte` / `.kpi-ok` colorent l'icône).
```html
<div class="kpi"><div class="kpi-entete"><span>En pause</span><span class="kpi-icone">[[i:pause]]</span></div>
  <div class="valeur">3</div><p class="kpi-aide">Pièce manquante ou CAPTCHA</p></div>
```
**Badges de statut** (forme + couleur) : `.badge` neutre, `.badge-attente` (en attente), `.badge-valide` / `.badge-ok`,
`.badge-refuse` / `.badge-err`, `.badge-envoye`, `.badge-completer` / `.badge-warn` (à compléter), `.badge-info`, `.badge-brouillon`, `.badge-nu` (sans pastille).
```html
<span class="badge badge-completer">À compléter</span>
```
**Tableaux** : toujours dans `.table-wrap` (défilement horizontal interne) ; `td.num` chiffres alignés ; `tr.ligne-active` ; `.table-compacte`.
```html
<div class="table-wrap"><table><thead><tr><th>Étudiant</th><th class="num">Pièces</th></tr></thead><tbody><tr><td>…</td><td class="num">9/11</td></tr></tbody></table></div>
```
**Listes** : `.liste-actions > li.ligne-action` (badge | `.ligne-texte` strong+span | bouton) ; `.liste-echeances > li.echeance` ;
tâches :
```html
<ul class="liste-taches"><li class="tache faite"><input type="checkbox" checked aria-label="Fait" /><div><span class="tache-titre">Relevé du bac</span><span class="tache-meta">Reçu le 2026-11-02</span></div><span class="badge badge-valide">Validé</span></li></ul>
```
**Raccourcis** : `.grille-raccourcis > button.raccourci[data-aller-vers]` (`.raccourci-icone`, strong, small, `[[i:suivant]]`).

**État vide** (illustration SVG : classes `illu-fond`, `illu-papier`, `illu-trait`, `illu-accent`, `illu-coche` ; en JS, `createElementNS`, voir `accueilIllustration`)
```html
<div class="etat-vide"><svg class="etat-vide-illu" viewBox="0 0 96 72" aria-hidden="true"><rect class="illu-papier" x="18" y="6" width="48" height="40" rx="6"/><circle class="illu-accent" cx="72" cy="50" r="14"/></svg>
  <strong>Aucun étudiant.</strong><span>Ajoutez une première fiche.</span></div>
```
**Squelettes** (remplacent « Chargement… » ; `aria-busy="true"` sur le conteneur + texte `.sr-only`)
```html
<ul aria-busy="true"><li class="sr-only">Chargement</li><li class="ligne-squelette" aria-hidden="true"><span class="squelette squelette-pastille"></span>
  <span class="squelette-pile"><span class="squelette squelette-texte"></span><span class="squelette squelette-texte court"></span></span></li></ul>
```
Variantes : `.squelette-titre`, `.squelette-valeur`, `.squelette-carre`.

**Toasts** : appeler `notifier(message, ok)` (zone `#zone-notification`), voir « Toasts à deux régions » plus bas. Classe statique : `.toast.toast-ok` / `.toast-err`.
Encart de règle : `.banniere-regle` (+ `.banniere-alerte`).

**Onglets**
```html
<div class="onglets" role="tablist"><button class="onglet" role="tab" aria-selected="true" type="button">Pièces</button><button class="onglet" role="tab" aria-selected="false" type="button">Historique</button></div>
```
**Étapes d'une procédure** (`.etape-faite`, `.etape-courante`, `.etape-bloquee` ; vertical sous 900 px)
```html
<ol class="etapes"><li class="etape etape-faite"><span class="etape-titre">Fiche</span>Complète</li><li class="etape etape-courante"><span class="etape-titre">Pièces</span>9 sur 11</li><li class="etape"><span class="etape-titre">Validation</span></li></ol>
```
**Progression de dossier** (`.barre-progression.ok` / `.alerte`)
```html
<div class="progression-dossier"><div class="progression-entete"><span>Pièces reçues</span><strong>9 / 11</strong></div>
  <div class="barre-progression" role="progressbar" aria-valuenow="82" aria-valuemin="0" aria-valuemax="100"><div class="barre-progression-remplie" style="width:82%"></div></div></div>
```
**Modale** (`<dialog>` natif, `showModal()` / `close()`)
```html
<dialog id="modale-x" class="modale" aria-labelledby="modale-x-titre"><div class="modale-entete"><h3 id="modale-x-titre">Confirmer</h3>
  <button class="btn btn-fantome btn-icone" type="button" aria-label="Fermer">[[i:fermer]]</button></div>
  <div class="modale-corps">Texte.</div><div class="modale-pied"><button class="btn btn-contour" type="button">Annuler</button><button class="btn btn-primaire" type="button">Confirmer</button></div></dialog>
```

## Contour des champs : `--bord-champ`

- Token de contour des champs de saisie (`input`, `select`, `textarea`). Valeurs : `#7b82a3` en thème clair, `#7a80ad` en thème sombre (`TOKENS_CLAIR` et `TOKENS_SOMBRE` dans `styles.py`).
- Il est présent dans `:root`, dans `:root:not([data-theme="light"])` sous `prefers-color-scheme: dark`, et dans `:root[data-theme="dark"]`.
- Il n'est utilisé qu'à un endroit : la règle `input, select, textarea` de `styles.py` (`border: 1px solid var(--bord-champ)`).
- Pour un nouveau champ, ne rien écrire : le style vient de la règle globale. Pour une carte ou un séparateur, utiliser `--bord` ou `--bord-fort`, pas `--bord-champ`.

## Lien d'évitement : `.sr-focus`

- Lien « Aller au contenu », premier élément du `<body>` (`shell.py`) : `<a class="sr-focus" href="#contenu">Aller au contenu</a>`. Cible : `<main id="contenu" tabindex="-1">`.
- Règle CSS dans `styles.py` : hors écran (`left: -9999px`) tant qu'il n'a pas le focus. Au focus (`:focus` ou `:focus-visible`), il passe en `position: fixed` à `var(--e4)` du bord haut-gauche.
- Ne pas le déplacer après la barre haute, et ne pas renommer l'id `contenu`.
- Ne pas confondre avec `.sr-only` (même fichier) : `.sr-only` cache un texte à l'écran tout en le laissant aux lecteurs d'écran ; `.sr-focus` est un lien invisible qui apparaît au clavier.

## Annonces : `annoncer(msg)`

- Fonction JS définie dans `js_dossiers.py` : `function annoncer(msg)` écrit `msg` dans `#annonce-statut`.
- `#annonce-statut` (`shell.py`) : `<div id="annonce-statut" class="sr-only" role="status" aria-live="polite" aria-atomic="true">`. Rien ne s'affiche à l'écran.
- Usage : un résumé court pour lecteur d'écran, par exemple « Score d'acceptation calculé. » ou « 2 vœux dans le panier. ».
- Ne pas l'utiliser pour un message visible ni pour une erreur : utiliser `notifier`.

## Toasts à deux régions

- `shell.py`, dans `#zone-notification` : `#notif-statut` (`role="status"`, `aria-live="polite"`) pour les succès, et `#notif-alerte` (`role="alert"`) pour les erreurs. Ces deux régions existent dès le chargement et ne sont jamais retirées du DOM.
- `notifier(msg, ok = true)` (`js_dossiers.py`) : `ok` vrai écrit dans `#notif-statut`, sinon dans `#notif-alerte`. Chaque appel remplace le contenu de la région (`replaceChildren`) : un seul toast par région à la fois.
- Succès (`.toast-ok`) : retiré automatiquement après 6 000 ms.
- Erreur (`.toast-err`) : reste affichée jusqu'au bouton « Fermer », créé par `notifier`.
- Le message est inséré avec `textContent`, jamais en `innerHTML`.
- Sur mobile (≤ 900 px), la zone passe en bas de l'écran (`styles.py`).
- Ne pas créer ces régions à la volée : un rôle ajouté après coup n'est pas toujours annoncé.

## Coquille (ne pas casser)

- `body.hors-session` : l'écran `#ecran-connexion` remplace `#vue-tableau-bord` ; suit l'état de `#btn-se-deconnecter`.
- Thème : tout bouton `[data-bascule-theme]` bascule `data-theme` sur `<html>` (mémorisé dans `localStorage["theme-interface"]`).
- Mobile (≤ 900 px) : tiroir `body.nav-ouverte`, gouttière 16 px, toasts en bas ; aucun défilement horizontal de la page à 375 px.

## Composant « Discussion de l'agent » (`ecran_discussion_agent.py`)

Fil en direct (SSE, repli par interrogation) de la fenêtre de l'agent, avec saisie, Pause / Reprendre / Arrêter et lien
« Voir la fenêtre sur mon PC ». Intégration : `monterDiscussionAgent(conteneur, tacheId)` (voir l'en-tête du fichier) ;
`assembler_discussion_agent(html)` insère le style et le script. Classes préfixées `.da-`, tokens uniquement.
