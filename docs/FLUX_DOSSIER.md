# Parcours d'un dossier : du dépôt à la validation humaine

Ce document décrit, étape par étape, le chemin d'un dossier étudiant dans la plateforme : du dépôt des pièces jusqu'à la validation humaine. Il sert de référence aux opérateurs et aux développeurs.

**Vérification** : les routes citées ont été relevées dans `serveur\app\api\v1\*.py` (préfixe du routeur et décorateur `@routeur.get/post/put/patch/delete`) et dans `serveur\app\api\v1\__init__.py` (inclusion sous `/api/v1`). Les écrans viennent de `serveur\app\interface\`. État au 2026-11-15. Un endpoint absent de ce document n'est pas garanti.

---

## 1. Vue d'ensemble

| # | Étape | Ce qui se passe | Qui décide | Où dans le menu |
|---|---|---|---|---|
| 1 | Dépôt des pièces | L'opérateur dépose des fichiers PDF, PNG ou JPG pour un étudiant | Humain | Pièces et identifiants (ou Dossier automatique, étape 1) |
| 2 | Lecture | La plateforme extrait le texte (PDF) ou fait un OCR (images) | Machine : valeurs « à valider » | Lecture des documents |
| 3 | Revue | L'opérateur valide, rejette ou corrige chaque valeur lue | Humain | Lecture des documents |
| 4 | Fiche | Seules les valeurs confirmées sont appliquées à la fiche | Humain | Étudiants et fiches |
| 5 | Points forts | Calcul par règles déterministes, chacun avec sa pièce | Machine propose, humain confirme ou rejette | Points forts et projet |
| 6 | Projet professionnel | Brouillon généré, modifiable, puis validé | Machine brouillon, humain valide | Points forts et projet |
| 7 | Vœux | Suggestions en lecture seule, puis création de vœux par un humain | Humain | Campus France (section vœux) |
| 8 | Lettres de motivation | Brouillon enregistré, à relire et à valider | Machine brouillon, humain relit | Campus France (section vœux) |
| 9 | Navigateur visible et discussion en direct | Pilotage du portail dans une fenêtre visible, fil de discussion en direct | Agent, sous surveillance humaine | Étudiants et fiches (« Ouvrir sur mon PC ») ou Navigateur de l'agent (« Vue en direct ») |
| 10 | Validation humaine | Récapitulatif validé par un employé ou un administrateur | Humain uniquement | Centre de validation, Récapitulatifs à valider |

Le menu **Dossier automatique** suit ces étapes sous leurs codes internes : `pieces`, `lecture`, `revue_valeurs`, `fiche`, `points_forts`, `projet_professionnel`, `voeux`, `lettres`, `navigateur` (`serveur\app\interface\design\js_flux_dossier.py`). L'orchestrateur ne valide jamais à la place d'un humain, ne crée ni ne soumet aucun vœu, et liste les pièces manquantes sans rien inventer (`serveur\app\services\dossier_automatique.py`).

---

## 2. Conventions

- Toutes les routes d'API sont sous `/api/v1` (`serveur\app\api\v1\__init__.py`). Les routes `/` et `/interface` (interface web), `/bienvenue`, `/inscription` et les pages de courriel (`/mot-de-passe-oublie`, `/nouveau-mot-de-passe`, `/verification-adresse`) ne sont pas sous `/api/v1`.
- Les pages de simulation `/demo/campus-france` et `/demo/ircc` ne sont montées que hors production.
- Connexion : `POST /api/v1/auth/connexion`. Déconnexion : `POST /api/v1/auth/deconnexion`. Utilisateur courant : `GET /api/v1/auth/moi`.
- Rôles : les écritures sur les dossiers, les tâches et les validations sont réservées à l'**administrateur** ou à l'**employé** du bureau. La création d'un agent local est réservée à l'administrateur.
- Les écritures de l'interface passent par `appelApi`, qui gère le jeton CSRF.
- Dans les chemins ci-dessous, `{candidat_id}`, `{tache_id}`, etc. sont des identifiants (UUID).

---

## 3. Les étapes en détail

### Étape 1 : Dépôt des pièces

**Écran** : « Pièces et identifiants » (bouton « Déposer et chiffrer la pièce ») ou étape 1 du « Dossier automatique ».

| Méthode | Chemin | Rôle |
|---|---|---|
| POST | `/api/v1/candidats` | Crée la fiche d'un étudiant (nom et prénom obligatoires) |
| GET | `/api/v1/candidats` | Liste paginée des étudiants, avec recherche |
| POST | `/api/v1/candidats/{candidat_id}/documents` | Dépose une pièce (formulaire : `type_piece`, `fichier` ; facultatifs : `date_expiration`, `date_expiration_piece`) |
| GET | `/api/v1/candidats/{candidat_id}/documents` | Liste les pièces du dossier |
| GET | `/api/v1/candidats/{candidat_id}/documents/{document_id}/telecharger` | Télécharge une pièce |
| DELETE | `/api/v1/candidats/{candidat_id}/documents/{document_id}` | Supprime une pièce |
| GET | `/api/v1/candidats/{candidat_id}/completude/{code_demarche}` | Indique les pièces manquantes pour une démarche |
| POST | `/api/v1/candidats/{candidat_id}/documents/specimens-demo` | Génère des pièces spécimens de démonstration (voir « Points à vérifier ») |

Formats acceptés par l'interface : `.pdf`, `.png`, `.jpg`, `.jpeg`. Taille maximale : 15 Mo par défaut (`taille_max_document_octets`). Les pièces sont chiffrées au repos.

### Étape 2 : Lecture des documents

**Écran** : « Lecture des documents » (suivi), ou étape 2 du « Dossier automatique ».

| Méthode | Chemin | Rôle |
|---|---|---|
| POST | `/api/v1/candidats/{candidat_id}/documents/{document_id}/extraire` | Lit une pièce (texte du PDF, puis OCR si besoin) |
| POST | `/api/v1/candidats/{candidat_id}/extractions/lot` | Lit toutes les pièces du dossier (paramètre facultatif `code_demarche`) |
| POST | `/api/v1/candidats/{candidat_id}/dossier-automatique/lancer` | Lance le parcours automatique |
| GET | `/api/v1/candidats/{candidat_id}/dossier-automatique/etat` | Progression (0 à 100), état des 9 étapes, pièces manquantes |

Chaque valeur lue reste « à valider ». Le lecteur automatique n'a aucun accès à la revue humaine.

### Étape 3 : Revue humaine des valeurs lues

**Écran** : « Lecture des documents ».

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/api/v1/candidats/{candidat_id}/extractions` | Liste les valeurs lues |
| POST | `/api/v1/candidats/{candidat_id}/extractions/{extraction_id}/valider` | Confirme une valeur |
| POST | `/api/v1/candidats/{candidat_id}/extractions/{extraction_id}/rejeter` | Rejette une valeur |
| POST | `/api/v1/candidats/{candidat_id}/extractions/{extraction_id}/corriger` | Corrige une valeur avant confirmation |
| POST | `/api/v1/candidats/{candidat_id}/extractions/appliquer` | Applique à la fiche les seules valeurs confirmées |

### Étape 4 : Fiche de l'étudiant

**Écran** : « Étudiants et fiches ».

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/api/v1/candidats/{candidat_id}` | Lit la fiche |
| PATCH | `/api/v1/candidats/{candidat_id}` | Modifie la fiche |
| POST | `/api/v1/candidats/{candidat_id}/archiver` | Archive le dossier |
| POST | `/api/v1/candidats/{candidat_id}/restaurer` | Restaure un dossier archivé |
| POST | `/api/v1/candidats/{candidat_id}/consentement` | Enregistre le consentement écrit de l'étudiant |
| POST | `/api/v1/candidats/{candidat_id}/consentement/revoquer` | Révoque le consentement |
| GET | `/api/v1/candidats/{candidat_id}/consentements` | Liste les consentements |

Pour information, le score d'acceptation (écran « Conseiller et score ») utilise `GET /api/v1/candidats/{candidat_id}/evaluation/{code_demarche}`.

### Étape 5 : Points forts

**Écran** : « Points forts et projet ».

| Méthode | Chemin | Rôle |
|---|---|---|
| POST | `/api/v1/candidats/{candidat_id}/deductions/calculer` | Calcule les points forts à partir des seules valeurs confirmées |
| GET | `/api/v1/candidats/{candidat_id}/points-forts` | Liste les points forts |
| POST | `/api/v1/candidats/{candidat_id}/points-forts/{point_id}/confirmer` | Confirme un point fort |
| POST | `/api/v1/candidats/{candidat_id}/points-forts/{point_id}/rejeter` | Rejette un point fort |
| POST | `/api/v1/candidats/{candidat_id}/points-forts/{point_id}/appliquer-niveau` | Applique le niveau (langue, etc.) à la fiche |

Le calcul est déterministe, sans IA. Chaque point fort renvoie à sa pièce justificative.

### Étape 6 : Projet professionnel

**Écran** : « Points forts et projet » (boutons « Générer un brouillon », « Enregistrer »).

| Méthode | Chemin | Rôle |
|---|---|---|
| POST | `/api/v1/candidats/{candidat_id}/projet-professionnel/generer` | Génère un brouillon à partir des points forts confirmés |
| GET | `/api/v1/candidats/{candidat_id}/projet-professionnel` | Lit le projet |
| PUT | `/api/v1/candidats/{candidat_id}/projet-professionnel` | Enregistre le texte modifié (avec numéro de version) |
| POST | `/api/v1/candidats/{candidat_id}/projet-professionnel/valider` | Validation humaine du projet |

### Étape 7 : Vœux de formation

**Écran** : « Campus France » (section vœux).

Catalogue et suggestions :

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/api/v1/catalogue-formations` | Liste les fiches de formation du bureau |
| POST | `/api/v1/catalogue-formations/import-ecoles` | Importe les écoles |
| POST | `/api/v1/catalogue-formations/fiches` | Crée une fiche de formation |
| POST | `/api/v1/voeux/suggestions` | Propose jusqu'à sept vœux selon les prérequis réels des fiches (lecture seule) |

Vœux du candidat :

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/api/v1/candidats/{candidat_id}/voeux` | Liste les vœux |
| POST | `/api/v1/candidats/{candidat_id}/voeux` | Crée un vœu (action humaine) |
| PATCH | `/api/v1/candidats/{candidat_id}/voeux/{voeu_id}` | Modifie un vœu |
| POST | `/api/v1/candidats/{candidat_id}/voeux/{voeu_id}/valider` | Valide un vœu |
| POST | `/api/v1/candidats/{candidat_id}/voeux/{voeu_id}/marquer-ajoute` | Marque le vœu comme ajouté au panier du portail |
| DELETE | `/api/v1/candidats/{candidat_id}/voeux/{voeu_id}` | Supprime un vœu |

Une suggestion ne devient un vœu que par une action humaine. Une exigence inconnue n'est jamais présentée comme « ok ».

### Étape 8 : Lettres de motivation

**Écran** : « Campus France » (bouton « Rédiger la lettre », sur chaque vœu).

| Méthode | Chemin | Rôle |
|---|---|---|
| POST | `/api/v1/candidats/{candidat_id}/voeux/{voeu_id}/lettre/generer` | Rédige la lettre du vœu et l'enregistre en brouillon |

La réponse indique l'origine du texte : `ia` (modèle IA) ou `modele` (lettre type). Sans IA, la lettre contient des repères `[À COMPLÉTER ...]`, qui bloquent la validation tant qu'ils restent (`serveur\app\services\lettres_voeux.py`). Le brouillon se relit ensuite, puis le vœu se valide (étape 7).

### Étape 9 : Navigateur visible et discussion en direct

Deux modes existent. Le premier est le mode recommandé pour un poste du bureau.

**A. « Ouvrir sur mon PC » (agent local sur un PC Windows du bureau)**

Écran : « Étudiants et fiches », carte « Ouvrir sur mon PC ». Le dossier automatique (étape 9) affiche le même bouton.

Côté humain (interface) :

| Méthode | Chemin | Rôle |
|---|---|---|
| POST | `/api/v1/taches` | Crée la tâche « Ouvrir sur mon PC » |
| GET | `/api/v1/taches/{tache_id}` | Suit l'état de la tâche |
| POST | `/api/v1/taches/{tache_id}/reprendre` | Reprend une tâche suspendue |
| POST | `/api/v1/taches/{tache_id}/capture-controle` | Prise de contrôle humaine de la fenêtre |

Côté agent local (appels faits par le programme sur le PC, pas par l'interface) :

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/api/v1/agents-locaux/moi` | Identité de l'agent |
| POST | `/api/v1/taches/reserver-suivante` | Réserve la tâche suivante |
| POST | `/api/v1/taches/{tache_id}/demarrer` | Démarre la tâche |
| POST | `/api/v1/taches/{tache_id}/battement-coeur` | Signale que l'agent est vivant |
| GET | `/api/v1/taches/{tache_id}/contexte-execution` | Lit le contexte d'exécution |
| GET | `/api/v1/taches/{tache_id}/voeux-a-ajouter` | Lit les vœux validés à ajouter au panier |
| POST | `/api/v1/taches/{tache_id}/etapes/{code_etape}/terminer` | Signale une étape terminée |
| POST | `/api/v1/taches/{tache_id}/suspendre` | Suspend la tâche : l'agent s'arrête et attend une décision humaine |
| POST | `/api/v1/taches/{tache_id}/erreur` | Signale une erreur |
| POST | `/api/v1/taches/{tache_id}/soumettre-validation` | Demande une validation humaine (étape 10) |

Gestion des agents (administrateur) :

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/api/v1/agents-locaux` | Liste les agents locaux |
| POST | `/api/v1/agents-locaux` | Enrôle un agent local |
| POST | `/api/v1/agents-locaux/{agent_id}/revoquer` | Révoque un agent |
| POST | `/api/v1/agents-locaux/{agent_id}/activer` | Réactive un agent |

**Discussion en direct** (dans l'interface, dès qu'une tâche existe pour l'étudiant affiché) :

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/api/v1/taches/{tache_id}/evenements?depuis=` | Historique des événements |
| GET | `/api/v1/taches/{tache_id}/evenements/flux` | Flux en direct (`text/event-stream`), reconnexion automatique |
| POST | `/api/v1/taches/{tache_id}/messages` | Envoie une consigne à l'agent |
| POST | `/api/v1/taches/{tache_id}/pause` | Met l'agent en pause |
| POST | `/api/v1/taches/{tache_id}/reprise` | Reprend l'agent |
| POST | `/api/v1/taches/{tache_id}/arret` | Arrête l'agent |
| POST | `/api/v1/taches/{tache_id}/premier-plan` | Met la fenêtre de l'agent au premier plan |
| GET | `/api/v1/taches/{tache_id}/messages-en-attente` | (agent) Consignes en attente |
| POST | `/api/v1/taches/{tache_id}/evenements` | (agent) Publie un événement dans le fil |

Une consigne qui contredirait les règles 1, 2, 3 ou 6 est refusée par le serveur, et l'agent répond poliment.

**B. Navigateur côté serveur (écran « Vue en direct »)**

Écran : « Navigateur de l'agent » > « Vue en direct ».

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/api/v1/navigateur/etat` | État de la session du navigateur |
| GET | `/api/v1/navigateur/capture` | Capture de la page courante |
| POST | `/api/v1/navigateur/controle` | Prise de contrôle humaine |
| POST | `/api/v1/navigateur/fermer` | Ferme la session |
| POST | `/api/v1/portails/piloter-navigateur` | Instruction en langage naturel (Campus France, IRCC) |
| POST | `/api/v1/portails/action-dom-directe` | Action directe sur la page |
| GET | `/api/v1/portails/etat-navigateur` | État du pilotage |
| POST | `/api/v1/portails/copilote-bridge` | Pont du Co-Pilote (méthode OPTIONS également) |
| GET | `/api/v1/portails` | Synthèse des portails |
| GET | `/api/v1/portails/{code_portail}/verifier-url` | Vérifie qu'une URL appartient à un domaine officiel |
| GET | `/api/v1/portails/campus-france/guide-2026` | Référentiel du guide Campus France 2026 |

Le navigateur ne va jamais au bout d'une demande officielle : l'audit enregistre `bouton_soumission_finale_clique: false` (`serveur\app\api\v1\portails.py`).

**Identifiants des portails** : ils sont stockés uniquement dans le coffre chiffré du bureau, avec consentement écrit (règle 3). Les routes sont `PUT`, `GET` et `DELETE` sur `/api/v1/candidats/{candidat_id}/coffre/{portail}`. L'API renvoie un statut, jamais le mot de passe.

### Étape 10 : Validation humaine

**Écrans** : « Centre de validation » et « Récapitulatifs à valider ».

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/api/v1/validations/en-attente` | Synthèse des éléments à valider |
| POST | `/api/v1/taches/{tache_id}/valider` | Valide une tâche (humain) |
| POST | `/api/v1/taches/{tache_id}/rejeter-validation` | Rejette une demande de validation (humain) |
| POST | `/api/v1/validations-recapitulatif` | Propose un récapitulatif (agent local ou employé). Ce n'est jamais une validation |
| GET | `/api/v1/validations-recapitulatif` | Liste les récapitulatifs (filtre `statut`) |
| GET | `/api/v1/validations-recapitulatif/{validation_id}` | Lit un récapitulatif |
| POST | `/api/v1/validations-recapitulatif/{validation_id}/valider` | Valide le récapitulatif (employé ou administrateur) |
| POST | `/api/v1/validations-recapitulatif/{validation_id}/refuser` | Refuse le récapitulatif |
| POST | `/api/v1/portails/{code_portail}/valider-portail-reel` | Validation humaine du parcours sur le portail réel (règle 6) |
| GET | `/api/v1/audit` | Journal d'audit (écran « Journal d'audit ») |

Un agent ne peut pas valider lui-même : les routes de validation n'acceptent que l'administrateur ou l'employé. Le journal d'audit enregistre qui a validé, quand, et une empreinte, sans donnée personnelle.

---

## 4. Limites connues

- **Lecture des documents (OCR)** : elle demande l'extra `lecture`. Depuis `serveur\`, lancez `.\.venv\Scripts\pip install -e ".[lecture]"`. Cet extra installe `pypdf` (texte des PDF), `rapidocr` (OCR français et anglais), `onnxruntime` et `pillow`. Sans cet extra, l'application démarre et ses tests passent, mais la lecture d'un document répond par une erreur claire.
- **Vision locale** : désactivée par défaut (`BE_VISION_ACTIVE=false`).
- **IA facultative** : la plateforme fonctionne sans clé d'IA. Sans IA, le score, les points forts, les suggestions de vœux, le projet professionnel et les lettres (modèle à compléter) restent disponibles. Deux routes exigent une IA configurée et répondent sinon « L'assistant IA n'est pas activé » : `POST /api/v1/ia/procedures/generer` et `POST /api/v1/ia/dossiers/{candidat_id}/assistant`. L'état se lit sur `GET /api/v1/ia/statut`. La clé se configure par `BE_CLE_API_ANTHROPIC` ou par `BE_IA_*` (voir `serveur\.env.exemple`).
- **Jamais de soumission officielle sans validation humaine (règle 1)** : l'agent prépare le dossier en brouillon, produit un récapitulatif et s'arrête. Le garde d'envoi `serveur\app\agent_local\soumission_validee.py` existe et est testé, mais **aucun appelant de production ne lui fournit encore de validation** : aujourd'hui, l'agent s'arrête toujours avant le bouton final.
- **CAPTCHA et double authentification (règle 2)** : l'agent se met en pause et alerte l'opérateur. Rien n'est contourné.
- **Connexion aux portails (règle 3)** : la connexion automatique n'est active que pour un portail dont le YAML définit les sélecteurs de connexion. Aucun ne les définit pour l'instant : la connexion est manuelle.
- **Domaines (règle 6)** : seuls les domaines HTTPS officiels listés dans les YAML sont acceptés en mode réel.
- **Navigateur serveur** : en production, il tourne en mode sans fenêtre (headless). La fenêtre visible se trouve sur le PC de l'agent local.
- **« Ouvrir sur mon PC »** : suppose qu'un agent local tourne sur un PC Windows du bureau.
- **Données de démonstration** : le jeu de démonstration (une fiche fictive et deux comptes de bureau) n'est créé qu'en environnement `LOCAL`, qui est la valeur par défaut (`serveur\app\main.py`).
- **Production** : `BE_ENVIRONNEMENT=production` et `BE_COOKIE_SECURISE=true` sont obligatoires. Hors Windows, `BE_CLE_MAITRESSE_BASE64` l'est aussi. Voir `docs\DEPLOIEMENT.md`.

---

## 5. Premier essai (pas à pas, pour un non-développeur)

Ce parcours utilise uniquement les écrans existants. Pour un premier essai sans risque, n'ouvrez que des pages de simulation locales et n'actionnez jamais une action sur un portail officiel réel.

**Étape 0 : prérequis**
- Python 3.11 ou plus récent, et le dossier `serveur\.venv` créé. S'il n'existe pas, suivez la section « Démarrage rapide » du `README.md` (`python -m venv .venv`, puis `pip install -e ".[dev]"`).
- Pour la lecture des pièces : `.\.venv\Scripts\pip install -e ".[lecture]"` (une seule fois).

**Étape 1 : lancer le serveur**
1. Ouvrez PowerShell.
2. Tapez `cd C:\Users\HP\Desktop\agentbureau\plateforme\serveur` puis Entrée.
3. Tapez `.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000` puis Entrée.
4. Laissez cette fenêtre ouverte. Pour arrêter le serveur plus tard : Ctrl+C.

**Étape 2 : ouvrir l'interface**
1. Ouvrez Chrome ou Edge.
2. Tapez `http://127.0.0.1:8000` dans la barre d'adresse.

**Étape 3 : se connecter**
- E-mail : `admin@bureau-alger.dz`
- Mot de passe : `BureauAlger!2026`

Ces identifiants sont ceux de démonstration de `CLAUDE.md`. Ils ne doivent jamais être utilisés en production. Un second bureau de démonstration existe aussi en environnement local (voir « Points à vérifier »).

**Étape 4 : repérer le menu**
- À gauche : « Tableau de bord », « Dossier automatique », « Étudiants et fiches », « Pièces et identifiants », « Conseiller et score », « Campus France », « IRCC Canada », « Procédures du bureau », « Points forts et projet », « Lecture des documents », « Récapitulatifs à valider », « Centre de validation », « Journal d'audit », « Vue en direct », « Abonnement et sauvegardes ».
- Le menu est replié sur téléphone : bouton « Menu » en haut à gauche.

**Étape 5 : créer un étudiant**
1. Cliquez sur « Étudiants et fiches ».
2. Ouvrez le bloc « Nouvel étudiant ».
3. **Remplacez toutes les valeurs déjà écrites dans les champs** (elles sont pré-remplies avec des exemples). Seuls le nom et le prénom sont obligatoires ; ce que vous ne remplissez pas reste vide.
4. Cliquez sur « Enregistrer l'étudiant ».

**Étape 6 : déposer une pièce**
1. Cliquez sur « Pièces et identifiants ».
2. Dans « Ajouter une pièce justificative », choisissez le type de pièce.
3. Choisissez un fichier PDF, PNG ou JPG (15 Mo maximum).
4. Si la pièce a une date d'expiration (passeport), renseignez-la.
5. Cliquez sur « Déposer et chiffrer la pièce ».

**Étape 7 : lancer l'analyse**
1. Cliquez sur « Dossier automatique » (tout en haut du menu).
2. Choisissez l'étudiant, puis cliquez sur « Lancer l'analyse ».
3. Suivez les étapes à l'écran. Une étape « à vérifier » affiche un bouton qui vous mène à l'écran concerné.

**Étape 8 : revoir les valeurs lues**
1. Cliquez sur « Lecture des documents ».
2. Pour chaque valeur : « Valider », « Rejeter » ou « Corriger ». Rien n'est appliqué à la fiche tant que vous ne l'avez pas confirmé.
3. Cliquez ensuite sur l'action qui applique les valeurs confirmées à la fiche.

**Étape 9 : points forts et projet**
1. Cliquez sur « Points forts et projet ».
2. Confirmez ou rejetez chaque point fort (chacun renvoie à sa pièce).
3. Cliquez sur « Générer un brouillon », relisez, modifiez si besoin, puis « Enregistrer » et valider.

**Étape 10 : vœux et lettres**
1. Cliquez sur « Campus France », puis allez à la section vœux.
2. Ajoutez un vœu. Un vœu n'est créé que par votre action.
3. Cliquez sur « Rédiger la lettre ». Le texte est un brouillon : complétez tous les repères `[À COMPLÉTER]` avant de valider.

**Étape 11 : essayer la simulation (sans risque)**
- Ouvrez dans un nouvel onglet `http://127.0.0.1:8000/demo/campus-france` ou `http://127.0.0.1:8000/demo/ircc`. Ce sont des pages de simulation locales.
- Ne lancez pas une action de pilotage sur un portail officiel réel.

**Étape 12 : valider (dernière étape humaine)**
1. Cliquez sur « Récapitulatifs à valider » ou « Centre de validation ».
2. Lisez le récapitulatif, puis « Valider ce récapitulatif » ou « Refuser ». Seul un employé ou un administrateur peut valider. Le bouton « Valider ce récapitulatif » reste désactivé si des éléments bloquants subsistent.
3. Contrôlez le « Journal d'audit » : chaque validation y figure, sans donnée personnelle.

**Étape 13 : fermer**
- Dans la fenêtre PowerShell du serveur, appuyez sur Ctrl+C.

---

## 6. Points à vérifier

Ces points sont constatés dans le code et ne sont pas encore corrigés. Ils ne sont pas des bugs confirmés par un test.

- **Corrigé : valeurs pré-remplies dans « Nouvel étudiant »** : le formulaire de `serveur\app\interface\design\vues_dossiers.py` n'a plus aucune valeur pré-remplie (placeholders neutres seulement) ; test `test_interface_nouvel_etudiant_vide.py`.
- **Corrigé : spécimens de démonstration en production** : `POST /api/v1/candidats/{candidat_id}/documents/specimens-demo` renvoie 404 en environnement `PRODUCTION` ; test `test_documents_specimens_production.py`. Les boutons de démonstration de l'interface affichent alors une erreur en production.
- **Corrigé : paramètre `jeton` dans l'URL de capture** : ce paramètre n'était pas un secret mais un horodatage anti-cache (l'authentification passe par le cookie de session) ; il est renommé `t` dans `GET /api/v1/navigateur/capture?t=...`. Voir `docs\DEPLOIEMENT.md` § 12.5.
- **Second bureau de démonstration** : `serveur\app\main.py` crée aussi un bureau « Démo Algérie » avec un autre compte, absent de `CLAUDE.md`.
- **Procédure de démarrage** : le `README.md` demande `alembic upgrade head` avant le démarrage. En environnement `LOCAL`, `main.py` crée aussi les tables au démarrage (`create_all`). Les deux approches coexistent ; vérifier la procédure en production dans `docs\DEPLOIEMENT.md`.
