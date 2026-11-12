# Portail Études en France (espace Algérie) : relevé factuel du site réel

**Date d'observation :** 2026-11-11, en session connectée
**Destinataires :** développeurs du Co-Pilote
**Nature :** relevé de structure et de comportement observé. Aucune donnée personnelle n'est reprise dans ce document.

---

## 1. Adresses

**Connexion :**
`https://pastel.diplomatie.gouv.fr/etudesenfrance/dyn/public/authentification/login.html`

**Après connexion, domaine `etudesenfrance.diplomatie.gouv.fr` :**

| Chemin | Page |
|---|---|
| `/` | Accueil |
| `/catalogue-formations` | Catalogue des formations |
| `/catalogue-formations/formation/{idFormation}/site/{idSite}` | Fiche formation |
| `/mon-espace-etudiant` | Espace étudiant |
| `/mon-dossier-candidature` | Mon dossier de candidature |
| `/mon-dossier-candidature/panier-formations` | Panier de formations |
| `/mon-dossier-candidature/panier-formations/regles` | Règles de constitution du panier |
| `/mes-paiements` | Mes paiements |
| `/mes-rendez-vous` | Mes rendez-vous |

---

## 2. Interface

- Le site est une application React. Les identifiants d'éléments sont générés et ont la forme `input-:rc5:`. **Ne jamais s'appuyer sur ces id** : ils changent d'un rendu à l'autre.
- En largeur étroite (environ moins de 900 px), le site passe en affichage mobile. Les filtres du catalogue se cachent alors derrière un bouton « Filtrer les formations ».
- Le Co-Pilote doit fixer une largeur de **1280 px** pour travailler sur le catalogue.

---

## 3. API de lecture utilisée par le site

Ces appels utilisent la session du site (cookies). Ils sont observés, pas documentés officiellement.

### 3.1 Fiche formation (GET)

`GET /parcours-api/espace-etudiant/catalogue/formations/{idFormation}/site/{idSite}`

La réponse JSON contient :

- **`formationInformationGenerale`** : `libelleFormation`, `libelleGroupement`, `libelleEtablissement`, `libelleSite`, `valeurComNiveau`, `libelleCatalogue`, `libelleTypeDiplome`, `langueEnseignement`, `preRequis.value` (HTML), `UrlInfoSpecifique`, `niveauLabel`.
- **`formationsInformationsEntree[]`** : un élément par niveau d'entrée, avec `id`, `annee`, `dureeMois`, `ferme`, `connecte`, `coutFormation`, `processusCandidature`, `dateDebut`, `dateFin`, `procedureParallele`, `valeurComNiveau`, `procedureInscription.value`, `ajouteAuPanier`.

### 3.2 Recherche du catalogue (POST)

`POST /parcours-api/public/catalogue/formations`

- Le corps de la requête **n'est pas documenté**. Ne pas le deviner par essais.
- La réponse contient :
  - `pagination` : `page`, `size`, `nbResultats`, `nbPages` ;
  - `donnees[]` : `idFormation`, `idSite`, `libelleFormation`, `typeDiplome`, `procedureParallele`, `libelleCatalogue`, `libelleSite`, `libelleEtablissement`, `libelleGroupement`, `valeurComNiveau`, `niveauLabel`.

### 3.3 Autres appels

- `GET /parcours-api/public/catalogue/formations/filters/localisation`
- `GET /parcours-api/public/catalogue/formations/filters/formations`
- `GET /parcours-api/public/catalogue/formations/filters/domaines`
- `GET /parcours-api/utilisateurs/moi`
- `GET /parcours-api/public/fonctionnalites-actives`

---

## 4. Page catalogue (vue bureau)

**Champs et boutons :**

- Champ texte « Libellé de la formation ».
- Boutons « Type de diplôme » et « Groupement ».
- Filtres « Catalogue » : Français Langue Étrangère, Général, Taught In English.
- Filtres : Établissement, Domaine, Sous-domaine, Région, Département, Ville.
- Bouton « Rechercher » (type submit).
- Bouton « Réinitialiser les filtres ».
- Sélecteur du nombre de résultats : 10, 20, 50.
- Pagination : « Précédent / Page n sur N / Suivant ».

**Comportement de recherche :** la recherche par mots est large. Plusieurs mots élargissent les résultats.

**Résultats :** chaque résultat est un lien `a[href^="/catalogue-formations/formation/..."]` qui porte l'intitulé. Le lien affiche aussi le diplôme, l'établissement, le site, la mention « Niveau d'entrée : Bac +x ». Quand c'est le cas, la mention « PROCÉDURE UNIQUEMENT SUR ÉTUDES EN FRANCE » apparaît.

---

## 5. Page formation

- Une section par niveau d'entrée, avec un titre du type « Bac +4 », « Bac +5 », etc.
- Chaque section contient :
  - « CANDIDATURES OUVERTES JUSQU'AU jj/mm/aaaa » ;
  - le coût ;
  - la durée ;
  - la « Procédure d'inscription » ;
  - un bouton « Ajouter au panier ».
- Boutons de navigation : « Retour à la recherche » et « Accéder à mon panier de formations ».
- Le texte des prérequis indique le niveau de français exigé.

---

## 6. Page panier de formations

**Liens et en-têtes :**

- « Ajouter une formation » (vers le catalogue).
- « Mon dossier de candidature ».
- « Règles de constitution du panier de formations ».
- Compteur « N formations ajoutées ».

**Par formation (un `article` par formation) :**

- Titre (heading) et mention de procédure.
- Bouton « Consulter la page de détails de la formation … ».
- **Bouton « Supprimer »** : il ouvre une boîte de dialogue « Supprimer la formation » avec les boutons Annuler et Supprimer. **Le Co-Pilote ne doit JAMAIS cliquer sur ce bouton.**
- Établissement, niveau (par exemple « Bac +4 »), site.
- Une région « Texte de motivation » avec un bouton de dépliage. Ce bouton n'a pas de nom accessible et son état est « À compléter ».

**Une fois la région dépliée :**

- Un formulaire « Vos motivations ».
- Un compteur « 0/5000 caractères maximum ». La limite affichée est 5000 ; le guide parlait de 4000.
- Une barre d'outils : Gras, Italique, Souligné, Barré, Liste ordonnée, Liste à puces.
- Un éditeur de texte riche. La structure interne exacte (iframe ou contenteditable) n'est **pas encore confirmée**.
- Boutons « Annuler » et « Enregistrer » (type submit).

**Règle du panier :** jusqu'à 7 formations, dont au maximum 3 « Bac+1 Licence » et/ou 2 formations d'architecture.

---

## 7. Page « Mon dossier de candidature »

**Sections :** Mon espace étudiant, Statut particulier, Mon panier de formations.

**Certifications (deux cases) :**

- « J'ai bien relu mon dossier et je certifie l'exactitude des informations qu'il contient ».
- « Je certifie avoir pris connaissance des prérequis relatifs aux formations auxquelles je candidate ».

**Bouton « Soumettre mon dossier de candidature ».**

**Règle 1 :** le Co-Pilote ne doit jamais cocher ces cases et ne doit jamais cliquer sur « Soumettre ».

---

## 8. Accueil : messages officiels et bugs connus

**Calendrier 2026-2027 (message officiel) :**

- Ouverture : 1er octobre 2026.
- Date limite hors DAP : 22 décembre 2026.
- DAP : 15 décembre 2026.

**Paiement :** les frais de dossier se paient dans les 48 h après la soumission, sur `paiement.if-algerie.com`.

**Consigne :** ne jamais créer un deuxième compte.

**Bugs connus signalés sur la page d'accueil :**

- L'ajout d'activités est difficile.
- La prise de rendez-vous d'entretien est en panne.
- La messagerie a été supprimée.

---

## 9. Exigences observées sur les fiches

- La plupart des masters de sciences du langage, de TAL et les masters berbère de l'Inalco exigent un **français C1 minimum** (TCF complet ou DALF).
- Certaines formations demandent en plus :
  - un certificat d'anglais B2 ;
  - une lettre de motivation d'une page ;
  - un projet de recherche de 2 à 5 pages ;
  - un avis signé d'un enseignant-chercheur (Inalco M2).
- Droits d'inscription différenciés : environ **3 900 € par an** pour les non-européens.

**Exceptions repérées au B2 :**

- Université d'Orléans : Sciences du langage, parcours Analyses et Traitements Linguistiques, mention « priorité aux C1 ».
- Université de Lille : Master MEEF, B2.

---

## 10. Règles de sécurité pour le Co-Pilote

1. **Jamais de clic** sur « Supprimer » (panier), sur les cases de certification, ni sur « Soumettre ».
2. **Ne pas créer de second compte.**
3. **Arrêt** en cas de CAPTCHA ou de double authentification.
4. **Pas de mot de passe stocké.**
5. **Aucune donnée personnelle** dans l'audit.

---

## À valider lors de la cartographie

Points incertains, à confirmer sur le site réel avant de les coder :

1. **Structure exacte de l'éditeur de texte riche** (iframe ou contenteditable) sur la région « Texte de motivation ».
2. **Structure des sections par niveau** sur la page formation : comment relier chaque bouton « Ajouter au panier » à son niveau d'entrée.
3. **Comportement après un ajout réussi** au panier : message affiché, redirection éventuelle.
4. **Corps de la requête** `POST /parcours-api/public/catalogue/formations` (non documenté).
