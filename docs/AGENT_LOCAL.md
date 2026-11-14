# Agent Local : ouvrir le navigateur sur le PC du bureau

L'**Agent Local** est un petit programme qui tourne sur un PC Windows du bureau. Quand vous cliquez sur
**« Ouvrir sur mon PC »** dans l'interface, il ouvre **une vraie fenêtre de navigateur sur ce PC** (Chrome,
sinon Edge) et y travaille sous vos yeux. Vous voyez tout ce qu'il fait, et vous gardez la main.

> Pour l'instant, l'agent travaille sur la **page de démonstration** du portail Campus France (adresse
> `…/demo/campus-france` de votre serveur) : il y ajoute au panier les **vœux validés** du dossier actif.
> Le vrai portail Études en France reste fermé à l'agent tant que l'administrateur ne l'a pas homologué
> (règle 6).

## Ce que l'agent fait et ne fait jamais

| Règle | Concrètement |
|---|---|
| **R1 : validation humaine** | L'agent s'arrête **toujours avant tout envoi officiel**. Il ne valide jamais lui-même : la tâche passe à « à valider » et c'est **vous** qui validez dans le Centre de validation. |
| **R2 : pas de contournement** | Si un CAPTCHA ou une double authentification (2FA) apparaît, l'agent se **met en pause**. Vous le résolvez **vous-même dans la fenêtre**, puis vous cliquez sur « Reprendre la tâche ». |
| **R3 : mots de passe** | La plateforme **n'envoie jamais** le mot de passe du coffre à un PC. Si le portail demande de se connecter, **vous tapez vous-même** votre identifiant et votre mot de passe dans la fenêtre. L'agent attend. |
| **R6 : domaines officiels** | L'agent n'ouvre que la page de démonstration de **votre** serveur. Aucune autre adresse. |
| **R4 : rien d'inventé** | Sans vœu validé, l'agent s'arrête et le dit. Seuls les vœux **validés** lui sont transmis (jamais un brouillon). |

## Ce qu'il vous faut

- Un PC **Windows 10 ou 11**.
- **Python 3.11 ou plus récent** (gratuit).
- **Google Chrome** ou **Microsoft Edge** (Edge est déjà installé sous Windows).
- Le **dossier `plateforme`** copié sur ce PC (le même que celui du serveur, par exemple sur une clé USB
  ou par le partage du bureau).
- Un accès au serveur du bureau (son adresse, par exemple `http://127.0.0.1:8000` si le serveur est sur le
  même PC).

## Étape 1. Installer Python (une seule fois)

1. Allez sur <https://www.python.org/downloads/> et téléchargez Python 3.11 ou plus récent.
2. Lancez l'installateur. **Cochez la case « Add python.exe to PATH »** en bas de la première fenêtre,
   puis cliquez sur « Install Now ».

## Étape 2. Installer l'agent (une seule fois)

1. Ouvrez le dossier `plateforme\agent_local`.
2. Double-cliquez sur **`installer_agent.bat`**.
3. Une fenêtre noire s'ouvre et installe les composants (quelques minutes, internet nécessaire).
4. À la question « Installer aussi le Chromium de secours ? », répondez **N** (non) si vous avez Chrome ou
   Edge. Appuyez sur Entrée.
5. Quand « Installation terminée » s'affiche, appuyez sur une touche.

## Étape 3. Enrôler ce PC (une seule fois par PC)

L'enrôlement donne à ce PC sa propre **clé d'accès**. Il se fait dans l'interface, par un **administrateur**.

1. Ouvrez l'interface du bureau dans le navigateur.
2. Allez dans **« Abonnement et sauvegardes »**.
3. Dans la carte **« Enrôler un poste agent local »**, donnez un nom au PC (par exemple `PC-ACCUEIL`) puis
   cliquez sur **« Enrôler ce poste et générer sa clé »**.
4. **Copiez la clé** qui s'affiche. **Elle ne s'affiche qu'une seule fois.** Gardez-la pour l'étape suivante
   (si vous la perdez, enrôlez le poste à nouveau et révoquez l'ancien).

## Étape 4. Lancer l'agent

1. Dans `plateforme\agent_local`, double-cliquez sur **`lancer_agent.bat`**.
2. Au premier lancement, la fenêtre noire demande :
   - **l'adresse du serveur** (par exemple `http://127.0.0.1:8000`) : celle que vous voyez dans la barre
     d'adresse du navigateur quand vous ouvrez l'interface ;
   - **la clé de l'agent** : collez-la (clic droit dans la fenêtre noire). **Rien ne s'affiche pendant la
     saisie, c'est normal.** Terminez par Entrée ;
   - « Mémoriser… ? » : répondez **O** pour ne pas la ressaisir à chaque fois. L'adresse et la clé sont alors
     enregistrées **chiffrées par Windows**, lisibles uniquement par votre compte Windows sur ce PC.
3. Le message **« Agent Local à l'écoute »** s'affiche. **Laissez cette fenêtre noire ouverte** : c'est
   l'agent. Pour l'arrêter proprement, appuyez sur **Ctrl+C** (l'agent termine la tâche en cours puis
   s'arrête).

Dans l'interface, la carte « Ouvrir sur mon PC » détecte l'agent en quelques secondes.

## Utiliser « Ouvrir sur mon PC »

1. Dans **« Étudiants et fiches »**, choisissez le dossier.
2. Assurez-vous que le dossier a **au moins un vœu validé** (écran Campus France, « Vœux et lettres de
   motivation »).
3. Cliquez sur **« Ouvrir sur mon PC »**. L'écran affiche d'abord **« En attente de l'agent »**.
4. Sur le PC, **la fenêtre du navigateur s'ouvre et passe au premier plan** : vous voyez les vœux s'ajouter
   au panier de démonstration.
5. L'écran indique ensuite l'état :
   - **En cours** : l'agent travaille ;
   - **En pause** : une action de votre part est nécessaire (connexion, CAPTCHA, 2FA…). Faites-la dans la
     fenêtre, puis cliquez sur **« Reprendre la tâche »** ;
   - **À valider** : l'agent s'est arrêté avant tout envoi. **Contrôlez la fenêtre**, puis allez dans le
     **Centre de validation** pour valider ou rejeter ;
   - **En erreur** : lisez le message affiché ; vous pouvez reprendre la tâche.
6. La fenêtre **reste ouverte** après la fin de la tâche, pour que vous puissiez contrôler. Elle se ferme
   quand vous arrêtez l'agent (Ctrl+C). Si vous la fermez vous-même, l'agent la rouvre à la tâche suivante.

Votre connexion au portail est conservée dans le **profil du navigateur de l'agent** (un profil par bureau,
dossier `agent_local\profil_chromium`). Ce profil est distinct de votre navigateur habituel.

## Si ça ne marche pas

| Symptôme | À faire |
|---|---|
| `installer_agent.bat` dit « Python est introuvable » | Refaites l'étape 1 en cochant **« Add python.exe to PATH »**, puis relancez. |
| L'interface affiche « Aucun agent n'est enrôlé » | Faites l'étape 3 (enrôlement par un administrateur). |
| L'interface affiche « Aucun agent n'est en ligne » | Lancez `lancer_agent.bat` (étape 4) et laissez la fenêtre noire ouverte. Vérifiez que le PC joint le serveur. |
| « Jeton refusé » / « La clé a été refusée » | La clé est fausse ou a été **révoquée**. Demandez-en une nouvelle à l'administrateur, puis lancez `lancer_agent.bat -Oublier` pour effacer l'ancienne, et relancez. |
| « Serveur injoignable » | Vérifiez l'adresse du serveur et que le serveur est démarré. L'agent réessaie tout seul. |
| « Aucun navigateur n'a pu être ouvert » | Installez Google Chrome, ou relancez `installer_agent.bat` en répondant **O** pour le Chromium de secours. |
| La tâche reste « En attente de l'agent » | L'agent n'est pas lancé, ou il a été arrêté. Lancez-le : il prend la tâche aussitôt. Une tâche prise par un agent qui s'éteint est automatiquement remise en attente. |
| La page de démonstration est indisponible | Elle n'existe pas sur un serveur en production : l'agent signale une erreur et n'essaie aucune autre adresse. |

Pour effacer la clé mémorisée sur un PC : double-cliquez sur `lancer_agent.bat` avec l'option `-Oublier`
(par exemple depuis une invite de commandes : `lancer_agent.bat -Oublier`). Pour retirer un PC du bureau :
dans l'interface, **révoquez** son agent ; sa clé cesse immédiatement de fonctionner.

## Pour les développeurs

- Démon : `python agent_local\lanceur.py --mode ecouter --url-serveur http://127.0.0.1:8000`
  (clé dans la variable d'environnement `BE_JETON_AGENT` ; options `--canal-navigateur auto|chrome|msedge|chromium`,
  `--intervalle-sondage`, `--profil-navigateur`, `--headless` pour les tests seulement).
- Code : `serveur/app/agent_local/demon_ecoute.py` (boucle, battement de cœur, arrêt propre),
  `ouverture_visible.py` (Chrome > Edge > Chromium, profil par bureau, premier plan), `action_voeux_demo.py`
  (action `ajouter_voeux_panier` sur la page de démonstration), `lanceur_ecoute.py` (assemblage).
- Serveur : `POST /api/v1/taches/reserver-suivante` (réservation atomique par compare-and-swap, jeton
  `X-Agent-Token` obligatoire), `GET /api/v1/taches/{id}/voeux-a-ajouter` (vœux au statut `valide`
  uniquement, tâche détenue par l'agent appelant), `GET /api/v1/agents-locaux/moi`.
- Aucune route ne transmet le mot de passe du coffre à un PC. Une future connexion automatique exigerait un
  endpoint à usage unique, à durée courte et avec consentement explicite : il n'existe pas aujourd'hui.
