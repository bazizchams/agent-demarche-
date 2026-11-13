# Déploiement en ligne de la Plateforme Agent Bureau d'Études

## À lire d'abord : ce qui n'a PAS été vérifié

Ce guide a été rédigé en relisant le code (`Dockerfile`, `docker-compose.production.yml`, `Caddyfile`,
`serveur/app/core/config.py`, `serveur/app/core/chiffrement.py`, `serveur/app/cli.py`, `serveur/app/main.py`).
Un audit statique complémentaire (variables `BE_*`, chemins lus à l'exécution, migrations, compose, Caddy) a corrigé plusieurs écarts. **Rien n'a été lancé** : ni `docker build`, ni `docker compose`, ni migration sur PostgreSQL, ni obtention
de certificat HTTPS, ni test du point de contrôle de santé, ni sauvegarde ou restauration réelle.
Les points à valider lors du premier déploiement sur un serveur de test sont signalés par **(à valider)**.

---

## 1. Prérequis

- **Un serveur Linux** (Ubuntu 22.04 ou 24.04 recommandé), 2 cœurs et 4 Go de mémoire minimum, avec une adresse IP publique fixe.
- **Un nom de domaine** (par exemple `app.votre-bureau.dz`) dont vous contrôlez les DNS.
- **Docker Engine et le plugin Docker Compose** (voir la documentation officielle de Docker pour Ubuntu).
- **Un accès SSH** au serveur avec un utilisateur qui peut lancer Docker.
- **Un ordinateur de confiance** avec Python 3.11 ou plus, pour générer les secrets.

### 1.1 Pare-feu et DNS

1. Ouvrez uniquement les ports **22** (SSH, idéalement restreint à votre IP), **80** et **443** (HTTP/HTTPS).
2. Créez chez votre hébergeur DNS un enregistrement **A** : `app.votre-bureau.dz` pointe vers l'adresse IP du serveur.
3. Vérifiez la propagation avant de continuer : depuis votre ordinateur, `nslookup app.votre-bureau.dz` doit afficher l'IP du serveur.

Caddy obtient le certificat HTTPS automatiquement. Le port 80 doit donc être joignable depuis Internet.

### 1.2 Installation de Docker (Ubuntu)

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
# Installer Docker Engine et le plugin compose en suivant la documentation officielle :
# https://docs.docker.com/engine/install/ubuntu/
sudo usermod -aG docker "$USER"   # puis se reconnecter en SSH
docker compose version            # doit afficher une version 2.x
```

---

## 2. Récupérer le code sur le serveur

```bash
sudo mkdir -p /opt/agent-bureau && sudo chown "$USER" /opt/agent-bureau
cd /opt/agent-bureau
git clone <adresse-du-depot> plateforme      # ou copier le dossier "plateforme" par un moyen sûr
cd plateforme/deploiement
```

Le dossier `plateforme/serveur/donnees/` **ne doit jamais** être copié depuis un poste de développement :
il contient la base et les données de test.

---

## 3. Générer les secrets

Trois secrets sont nécessaires. Générez-les **sur votre ordinateur de confiance**, pas dans un outil en ligne.

### 3.1 Clé maîtresse de chiffrement (la plus importante)

Toutes les données personnelles et les pièces justificatives sont chiffrées avec une clé dérivée de cette clé maîtresse
(AES-256-GCM, voir `serveur/app/core/chiffrement.py`). Elle doit faire **exactement 32 octets** encodés en Base64 *urlsafe*.

```bash
python3 -c "import secrets,base64;print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

Le résultat (une chaîne d'environ 44 caractères se terminant souvent par `=`) est la valeur de `BE_CLE_MAITRESSE_BASE64`.

> **Attention.** Si cette clé est perdue, **toutes les données chiffrées deviennent irrécupérables**, y compris les
> sauvegardes. Conservez-la en deux exemplaires séparés (par exemple gestionnaire de mots de passe chiffré et copie papier
> dans un coffre). Ne la mettez jamais dans Git, dans un e-mail ou dans une conversation. Ne la changez jamais après la mise en service :
> une nouvelle clé ne déchiffre pas les données existantes.

### 3.2 Mot de passe de la base PostgreSQL

```bash
python3 -c "import secrets;print(secrets.token_urlsafe(32))"
```

Si le mot de passe contient `@`, `:`, `/`, `?`, `#` ou `%`, il doit être encodé en URL dans `BE_URL_BASE_DONNEES`.
Le plus simple est de choisir uniquement des caractères alphanumériques et `-` `_`, ce que produit la commande ci-dessus.

### 3.3 Secret du webhook Stripe

Stripe n'est activé qu'après les étapes de la section 9.2. Le fichier de production exige néanmoins une valeur qui n'est **pas** celle
de développement. Générez une valeur provisoire de la forme attendue :

```bash
python3 -c "import secrets;print('whsec_'+secrets.token_urlsafe(32))"
```

Remplacez-la plus tard par le vrai secret fourni par Stripe lors de l'activation.

---

## 4. Configuration

```bash
cd /opt/agent-bureau/plateforme/deploiement
cp .env.production.exemple .env.production
chmod 600 .env.production
nano .env.production
```

Renseignez au minimum :

| Variable | Valeur à mettre |
|---|---|
| `DOMAINE_PLATEFORME` | Votre domaine, sans `https://` (ex. `app.votre-bureau.dz`) |
| `EMAIL_CERTIFICAT_TLS` | Adresse e-mail pour les avis Let's Encrypt |
| `POSTGRES_PASSWORD` | Le mot de passe généré en 3.2 |
| `BE_CLE_MAITRESSE_BASE64` | La clé générée en 3.1 |
| `BE_STRIPE_SECRET_WEBHOOK` | La valeur provisoire générée en 3.3 |
| `BE_SMTP_HOTE`, `BE_SMTP_EXPEDITEUR` (+ `BE_SMTP_UTILISATEUR`, `BE_SMTP_MOT_DE_PASSE`) | Serveur d'envoi de courriels. **Sans eux, rien n'est envoyé** (mot de passe oublié, vérification d'adresse) et, en production, la validation humaine d'un récapitulatif est refusée tant que l'adresse n'est pas vérifiée. |

L'URL publique (`BE_URL_PUBLIQUE_PLATEFORME`) est déduite de `DOMAINE_PLATEFORME` par le compose. Toute variable `BE_*` doit figurer dans la
section `environment` du compose pour atteindre le conteneur ; l'audit statique a vérifié que celles de `serveur/app/core/config.py` y sont, sauf
`BE_EXIGER_ADRESSE_VERIFIEE`, `BE_BLOCAGE_ABONNEMENT_EXPIRE` et les limites de débit / durées de jetons (défauts du code, adaptés à la production).
Les autres variables ont des valeurs par défaut sûres. Ne modifiez pas `BE_ENVIRONNEMENT` ni `BE_COOKIE_SECURISE` :
ils sont fixés par `docker-compose.production.yml`.

Le fichier `.env.production` est ignoré par Git et par Docker. Ne le partagez jamais.

---

## 5. Lancement

```bash
cd /opt/agent-bureau/plateforme/deploiement
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
```

La première construction de l'image prend plusieurs minutes. Vérifiez ensuite :

```bash
docker compose --env-file .env.production -f docker-compose.production.yml ps
# postgres doit être "healthy", serveur et caddy "running" (le serveur passe "healthy" après 1 minute environ)

docker compose --env-file .env.production -f docker-compose.production.yml logs -f serveur
# Les migrations doivent se terminer par "Running upgrade ..." puis "Uvicorn running on http://0.0.0.0:8000"
```

Le démarrage du serveur exécute `alembic upgrade head` (migrations de base, sans risque si elles sont déjà appliquées) avant
de lancer l'application. Si les migrations échouent, le conteneur s'arrête et les journaux indiquent la cause.

Testez depuis votre ordinateur :

```bash
curl -I https://app.votre-bureau.dz            # doit répondre en HTTPS avec un certificat valide (à valider)
curl https://app.votre-bureau.dz/api/v1/sante  # réponse JSON de contrôle (à valider)
```

Ouvrez ensuite `https://app.votre-bureau.dz` dans un navigateur. Aucun compte de démonstration n'existe en production.

---

## 6. Création du premier bureau et de son administrateur

En production, aucun bureau n'est créé automatiquement. Utilisez l'outil d'administration (`serveur/app/cli.py`) dans le conteneur :

```bash
cd /opt/agent-bureau/plateforme/deploiement
docker compose --env-file .env.production -f docker-compose.production.yml exec serveur \
  python -m app.cli creer-bureau \
  --nom "Bureau d'Études Alger Centre" \
  --slug bureau-alger \
  --email-admin admin@votre-bureau.dz \
  --nom-admin "Responsable du bureau" \
  --temporaire
```

- Le mot de passe est demandé deux fois, sans affichage. **Ne pas** utiliser l'option `--mot-de-passe` : elle laisse la valeur dans l'historique du shell.
- `--temporaire` impose à l'administrateur de changer son mot de passe à la première connexion.
- Le mot de passe doit comporter au moins 12 caractères (`BE_LONGUEUR_MIN_MOT_DE_PASSE`).

Pour lister les bureaux existants :

```bash
docker compose --env-file .env.production -f docker-compose.production.yml exec serveur \
  python -m app.cli lister-bureaux
```

Pour un nouveau bureau, répétez la commande `creer-bureau` avec un autre `--slug`.

---

## 7. Sauvegardes et restauration

### 7.1 Ce qui doit être sauvegardé

| Élément | Où il se trouve | Pourquoi |
|---|---|---|
| Base PostgreSQL | volume `postgres` | Dossiers, comptes, journal d'audit |
| Documents chiffrés | volume `documents_chiffres` | Pièces justificatives des candidats |
| Clé maîtresse | `.env.production` et copie hors serveur | Sans elle, rien n'est lisible |
| Fichier `.env.production` | serveur | Configuration et secrets (sauvegardé hors serveur, jamais avec les dumps) |

> **Limite importante.** Les archives produites par l'application (`POST /api/v1/sauvegardes`, fichiers `.be.enc`) ne contiennent que
> des **métadonnées** (fiches et index des documents), pas les fichiers documents eux-mêmes et pas la base complète.
> Elles ne suffisent **pas** à restaurer le service. Il faut donc faire les sauvegardes décrites ci-dessous.
> L'application ne fournit pas non plus de commande de restauration automatique (voir section 11).

### 7.2 Sauvegarde quotidienne automatique (`deploiement/sauvegarde.sh`)

Le script fait un `pg_dump` (format custom, compressé) de la base et une archive des documents chiffrés, vérifie que les deux fichiers sont lisibles,
écrit des sommes de contrôle SHA-256, purge les copies de plus de `RETENTION_JOURS` jours et, si `COPIE_DISTANTE_RSYNC` est renseigné, les copie hors serveur.
Variables (dans `.env.production`) : `DEST_SAUVEGARDES` (défaut `/opt/sauvegardes`), `RETENTION_JOURS` (défaut 14), `COPIE_DISTANTE_RSYNC` (facultatif).

```bash
cd /opt/agent-bureau/plateforme/deploiement
bash sauvegarde.sh                      # premier essai à la main
sudo crontab -e                         # puis ajouter, pour une exécution chaque nuit à 02h30 :
# 30 2 * * * /bin/bash /opt/agent-bureau/plateforme/deploiement/sauvegarde.sh >> /var/log/agent-bureau-sauvegarde.log 2>&1
```

Limites assumées : base et documents ne sont pas copiés dans un instantané atomique ; les profils de navigateur (cookies des portails) ne sont **pas**
sauvegardés (secrets) ; la clé maîtresse n'est **pas** dans la sauvegarde (7.3). Une sauvegarde laissée sur le même disque ne protège pas de la perte du
serveur : configurez la copie distante et chiffrez le stockage distant. **(à valider : scripts jamais exécutés, seulement relus et vérifiés par `bash -n`)**

### 7.3 Copie de la clé de secours

```bash
docker compose --env-file .env.production -f docker-compose.production.yml exec serveur \
  python -m app.cli exporter-cle-secours
```

La commande affiche la clé en groupes lisibles, avec une somme de contrôle. Notez-la sur papier et rangez-la hors du serveur.
Elle correspond à `BE_CLE_MAITRESSE_BASE64`.

### 7.4 Règles

- Les sauvegardes contiennent des données personnelles : protégez-les comme la base elle-même (droits `600`, stockage distant chiffré).
- Surveillez `/var/log/agent-bureau-sauvegarde.log` : une sauvegarde silencieusement en échec est la panne la plus courante.
- **Testez la restauration** (7.5) avant la mise en service, puis au moins chaque trimestre.

### 7.5 Test de restauration sans risque (`restauration.sh verifier`)

Restaure la sauvegarde dans une base temporaire `restauration_test` du PostgreSQL en marche (la production n'est pas touchée), vérifie le nombre de
tables et la version Alembic, contrôle l'archive de documents, puis supprime la base temporaire :

```bash
cd /opt/agent-bureau/plateforme/deploiement
bash restauration.sh verifier /opt/sauvegardes/base_AAAA-MM-JJ_HHMM.dump /opt/sauvegardes/documents_AAAA-MM-JJ_HHMM.tar.gz
# Attendu : « OK : la sauvegarde est restaurable (base temporaire supprimée). »
```

Ce test ne prouve pas que l'application démarre avec la base restaurée : faites la restauration complète (7.6) une fois sur un serveur de test.

### 7.6 Restauration complète (`restauration.sh appliquer`)

Sur un serveur neuf ou après incident : installez le dépôt, recréez `.env.production` avec **la même** `BE_CLE_MAITRESSE_BASE64`, copiez les deux fichiers
de sauvegarde, puis :

```bash
cd /opt/agent-bureau/plateforme/deploiement
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build postgres   # base vide + volumes
bash restauration.sh appliquer /chemin/base_AAAA-MM-JJ_HHMM.dump /chemin/documents_AAAA-MM-JJ_HHMM.tar.gz
```

Le script demande de taper `RESTAURER`, arrête `serveur` et `caddy`, recrée la base, y restaure le dump, remplace les documents, puis relance l'ensemble ;
les migrations s'exécutent sans effet si elles sont déjà appliquées. N'utilisez **jamais** `docker compose down -v` (supprime les volumes).
Les volumes s'appellent `agent-bureau_volume_*` (nom de projet fixé dans le compose).

---

## 8. Mise à jour

```bash
cd /opt/agent-bureau/plateforme
git pull                                   # ou remplacer le dossier par la nouvelle version
cd deploiement

# 1. Sauvegarder d'abord : bash sauvegarde.sh (section 7.2)
# 2. Reconstruire et relancer
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
docker compose --env-file .env.production -f docker-compose.production.yml logs -f serveur
```

Les migrations de base sont appliquées automatiquement au démarrage. Une migration ne se défait pas automatiquement :
en cas de problème, revenez à la version précédente du code **et** restaurez la sauvegarde faite juste avant la mise à jour.

---

## 9. Activation de l'assistant IA et de Stripe

### 9.1 Assistant IA (Claude)

1. Créez une clé API auprès d'Anthropic (réservée à la plateforme, jamais partagée entre bureaux).
2. Dans `.env.production`, renseignez `BE_CLE_API_ANTHROPIC=<votre clé>` et, si besoin, `BE_MODELE_LLM`.
3. Relancez : `docker compose ... up -d` (le conteneur est recréé avec la nouvelle variable).
4. Vérifiez : `GET /api/v1/ia/statut` doit indiquer que l'assistant est actif. Sans clé, les fonctions IA répondent 503 et le reste fonctionne.

Sans clé payante : IA locale (Ollama) ou niveau gratuit hébergé via `BE_IA_FOURNISSEUR=openai_compatible`, `BE_IA_URL_BASE`, `BE_IA_MODELE`, `BE_IA_CLE` : voir `docs/IA_GRATUITE.md` (risques RGPD / loi 18-07 inclus).

### 9.2 Stripe : à tester en mode test avant tout encaissement

Le code appelle désormais l'API Stripe pour `POST /api/v1/abonnement/checkout-stripe` lorsque `BE_STRIPE_CLE_SECRETE` est renseignée
(`serveur/app/services/paiement_stripe.py`) ; sans clé, il répond « Paiement en ligne non configuré » en production. Ce comportement a été relu dans le code,
**jamais exécuté contre Stripe**. Les webhooks sont vérifiés par signature et refusés si le secret est celui de développement.

1. Dans Stripe (mode test d'abord), créer un produit et un prix par forfait ; reporter les `price_...` dans `BE_STRIPE_PRIX_STARTER`,
   `BE_STRIPE_PRIX_PROFESSIONNEL`, `BE_STRIPE_PRIX_ENTREPRISE`.
2. Renseigner `BE_STRIPE_CLE_SECRETE` (`sk_test_...` puis `sk_live_...`, jamais dans Git).
3. Créer un webhook vers `https://app.votre-bureau.dz/api/v1/webhooks/stripe` avec les événements `checkout.session.completed`,
   `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_succeeded` et `invoice.payment_failed`.
4. Renseigner `BE_STRIPE_SECRET_WEBHOOK` avec le secret `whsec_...` fourni par Stripe, puis `docker compose ... up -d`.
5. Dérouler un paiement complet en mode test (carte de test Stripe) sur un serveur de test avant de passer en `sk_live_...`.

L'ouverture d'un compte Stripe pour une activité établie en Algérie peut être restreinte : **à vérifier** auprès de Stripe avant de compter dessus.

---

### 9.3 Rappels d'échéance par e-mail (cron)

Prérequis : SMTP configuré (sinon rien n'est envoyé ni marqué). Destinataires : administrateurs et employés actifs, adresse vérifiée, par bureau.
La commande est idempotente (table `rappels_echeances_envoyes`) : on peut la relancer sans doublon. Code retour 1 si un envoi a échoué.
```bash
# crontab (sudo crontab -e) : chaque jour à 07h00
0 7 * * * cd /opt/agent-bureau/plateforme/deploiement && docker compose --env-file .env.production -f docker-compose.production.yml exec -T serveur python -m app.cli envoyer-rappels-echeances >> /var/log/agent-bureau-rappels.log 2>&1
```
Options : `--slug <bureau>`, `--date-rentree AAAA-MM-JJ`. Lancement manuel par un administrateur : `POST /api/v1/demarches/rappels-echeances` (jeton CSRF requis).
Le courriel ne contient que le libellé, la date, les jours restants et le lien. Les échéances relatives à la rentrée ou au dépôt ne sont calculées que si la date est fournie.

## 10. Liste de contrôle de sécurité avant ouverture au public

Cochez chaque point. Un point non coché bloque la mise en service.

- [ ] Le site répond uniquement en HTTPS, le certificat est valide et `http://` redirige vers `https://`.
- [ ] `BE_ENVIRONNEMENT=production`, `BE_COOKIE_SECURISE=true`, `BE_DOCS_API_ACTIVES=false` (vérifier `https://.../docs` : 404).
- [ ] `BE_CLE_MAITRESSE_BASE64` est une clé neuve de 32 octets, générée pour cette installation, et sa copie de secours est rangée hors du serveur.
- [ ] `POSTGRES_PASSWORD` est long et aléatoire, et PostgreSQL n'est pas publié sur Internet (aucun port 5432 ouvert).
- [ ] Le webhook Stripe n'utilise pas la valeur de développement `whsec_dev_local_secret_change_me`.
- [ ] Les comptes de démonstration (`admin@bureau-alger.dz`, etc.) n'existent pas sur le serveur (ils ne sont créés qu'en local).
- [ ] Le mot de passe administrateur initial a été changé à la première connexion.
- [ ] Seuls les ports 22 (restreint), 80 et 443 sont ouverts sur le pare-feu.
- [ ] L'accès SSH se fait par clé, le mot de passe SSH est désactivé.
- [ ] `.env.production` a les droits `600` et n'est pas dans Git (`git status` ne le montre pas).
- [ ] Une sauvegarde complète (base + documents + clé) a été faite **et restaurée avec succès** sur un serveur de test.
- [ ] Les mises à jour de sécurité du système (`apt upgrade`) sont programmées.
- [ ] Les conditions d'utilisation et le consentement (loi 18-07 et RGPD) ont été validés juridiquement pour le bureau.
- [ ] Le bureau sait qu'aucune soumission officielle n'est faite automatiquement : la validation humaine est obligatoire (règle 1).

---

## 11. Limites connues (ce qui n'est pas encore prêt)

1. **Co-Pilote en ligne : livré, mais non éprouvé en production.** Le Co-Pilote historique (`agent_local/`) tourne toujours sur
   le poste Windows de l'opérateur. Le **Co-Pilote en ligne** (section 12) est livré : une session Chromium headless par bureau,
   pont sécurisé, vue opérateur pour résoudre CAPTCHA et double authentification (l'agent ne les contourne jamais), et garde
   Règle 6 limitée aux domaines HTTPS officiels des YAML. Il est **désactivé par défaut** : les routes qui lancent un navigateur
   sur le serveur échouent tant que `BE_NAVIGATEUR_SERVEUR_ACTIF` n'est pas à `true`. Restent à faire :
   - l'image n'a **pas été construite ni testée en conteneur** ;
   - la liste des **domaines officiels** est incomplète : un domaine d'authentification absent des YAML (CléGC, Connexion
     partenaire IRCC, fournisseur d'identité ou CDN d'Études en France) bloque la redirection ; ils sont à vérifier sur le vrai
     portail (`docs/sources_demarches.md`), jamais à deviner ;
   - les **profils de navigateur** (cookies de session des portails) sont à persister sur un volume dédié et à **chiffrer**
     (disque chiffré ou volume chiffré) ; leur sauvegarde est un choix à assumer, ce sont des secrets ;
   - les sélecteurs des portails réels restent « non testés » tant que l'administrateur n'a pas attesté la validation (Règle 6).
2. **Stripe non éprouvé** : appel à l'API présent dans le code mais jamais testé contre Stripe (section 9.2).
3. **Sauvegardes** : l'application ne crée que des archives de métadonnées et n'a pas de commande de restauration.
   La sauvegarde complète passe par `deploiement/sauvegarde.sh` et `restauration.sh` (section 7), **jamais exécutés** à ce jour.
4. **Pas de haute disponibilité** : un seul conteneur serveur, une seule base PostgreSQL, pas de réplication.
   Une panne de l'hôte interrompt le service jusqu'au redémarrage.
5. **Pilote PostgreSQL absent de `pyproject.toml`.** `psycopg[binary]` est installé dans le `Dockerfile`. Pour le développement local
   sur PostgreSQL, installez-le aussi à la main. Ajouter la dépendance à `pyproject.toml` est recommandé mais n'a pas été fait ici.
6. **Clé API IA unique pour toute la plateforme** : la consommation est mutualisée entre bureaux. Surveillez la facturation Anthropic.
7. **Pas de Content-Security-Policy** : les en-têtes de sécurité sont présents (HSTS, nosniff, X-Frame-Options, Referrer-Policy),
   mais une politique CSP n'est pas définie, car l'interface utilise du JavaScript intégré.
8. **Journaux** : envoyés sur la sortie standard du conteneur (`docker compose logs`). Aucune rotation ni centralisation n'est configurée.
   Aucun outil de supervision ou d'alerte n'est fourni.
9. **Limitation de débit** : seule la protection par verrouillage après échecs de connexion existe. Pas de limitation globale de requêtes.
10. **Base SQLite interdite en production** : le code la supporte pour le développement, mais la production utilise PostgreSQL uniquement.
11. **Expiration des archives** : la purge des dossiers archivés expirés (`POST /api/v1/conformite/purger-archives-expirees`) est manuelle.
12. **Aucun test de bout en bout du déploiement n'a été exécuté** (voir la première section de ce document).

---

## 11 bis. Liste de contrôle « avant ouverture au public »

À cocher en plus de la section 10. Un point non coché bloque l'ouverture.

- [ ] **Mode serveur** : `BE_ENVIRONNEMENT=production`, PostgreSQL uniquement, pages de démonstration `/demo/` refusées par la garde Règle 6.
- [ ] **URL publique** : nom de domaine définitif, DNS et HTTPS valides, `BE_URL_PUBLIQUE_PLATEFORME` est déduite de `DOMAINE_PLATEFORME` par le compose (liens des e-mails, retours de paiement, pont du Co-Pilote).
- [ ] **SMTP** : serveur d'envoi configuré et testé (réinitialisation de mot de passe, invitations), expéditeur authentifié (SPF, DKIM, DMARC) pour éviter le dossier spam.
- [ ] **SATIM non intégré** : le paiement local par carte CIB/Edahabia n'est pas branché ; ne pas l'annoncer. Stripe : seulement après le test de la section 9.2. Prévoir un encaissement manuel hors plateforme tant que ce n'est pas fait.
- [ ] **Sauvegardes** : sauvegarde complète (`pg_dump` + documents + clé) programmée, **restauration testée** sur un serveur de test, copie hors serveur.
- [ ] **Clé de secours** : copie de `BE_CLE_MAITRESSE_BASE64` rangée hors du serveur et hors Git (sans elle, documents et identifiants chiffrés sont perdus).
- [ ] **RGPD / loi 18-07** : conditions d'utilisation, consentement des candidats, durées de conservation et purge des archives, registre des traitements et contact de protection des données validés juridiquement.
- [ ] **Co-Pilote en ligne** (si activé) : `BE_NAVIGATEUR_SERVEUR_ACTIF=true` après un essai concluant sur serveur de test, volume de profils chiffré, domaines officiels vérifiés (section 12.5), mémoire dimensionnée (12.3), procédure CAPTCHA/2FA expliquée aux opérateurs (12.4).
- [ ] **Validation humaine** : les opérateurs savent qu'aucune soumission officielle n'est automatique (Règle 1).

---

## 12. Navigateur de l'agent en ligne

> **Non validé en conteneur** : le `Dockerfile` et `docker-compose.production.yml` ont été modifiés et relus, mais l'image
> n'a pas été construite ni lancée (pas de Docker sur le poste de développement). Faites un premier essai sur un serveur de test.

### 12.1 Principe

Le serveur héberge un Chromium headless (Playwright) par bureau. Les opérateurs (administrateur, employé) le voient dans l'écran
**« 12. Navigateur de l'agent »** de l'interface : capture rafraîchie environ une fois par seconde, uniquement quand l'onglet est
visible et l'écran affiché. Le bouton **« Prendre la main »** permet de cliquer sur l'image, de faire défiler, de taper du texte
(champ masqué, vidé après envoi, jamais enregistré ni affiché dans l'historique) et d'envoyer Entrée, Tab, Retour, Échap.
Un compte en lecture seule voit l'écran désactivé et n'envoie aucune requête.

### 12.2 Variables à activer

Dans `.env.production` (valeurs par défaut du modèle) :

| Variable | Défaut | Rôle |
|---|---|---|
| `BE_NAVIGATEUR_SERVEUR_ACTIF` | `false` | Active le navigateur serveur. |
| `BE_NAVIGATEUR_SERVEUR_SESSIONS_MAX` | `3` | Sessions simultanées (une par bureau). |
| `BE_NAVIGATEUR_SERVEUR_INACTIVITE_MINUTES` | `15` | Fermeture automatique d'une session inactive. |
| `BE_DOSSIER_PROFILS_NAVIGATEUR` | `/srv/plateforme/donnees/profils_navigateur` | Profils de navigateur (volume dédié). |
| `SERVEUR_LIMITE_MEMOIRE` / `SERVEUR_LIMITE_CPU` | `3g` / `2.0` | Limites du conteneur `serveur`. |

Ces noms ont été **vérifiés** dans `serveur/app/core/config.py` (alias `BE_NAVIGATEUR_SERVEUR_*`). Piège : si `BE_NAVIGATEUR_SERVEUR_ACTIF` est absente,
le code active le navigateur serveur **par défaut en production** ; le compose force donc `false`. Une variable absente de la section `environment`
du compose n'est pas transmise au conteneur.

### 12.3 Dimensionnement

- Comptez **environ 500 Mo de mémoire par session** de navigateur, plus environ 1 Go pour l'API : 3 sessions simultanées demandent
  donc environ 2,5 Go ; la limite par défaut (`3g`) laisse une marge. Pour N sessions : `1 Go + N x 500 Mo`, arrondi au-dessus.
- Le serveur doit avoir cette mémoire libre en plus de PostgreSQL (environ 512 Mo) et Caddy. Un hôte de 4 Go convient pour 3 sessions.
- 1 à 2 CPU suffisent pour quelques sessions ; les pages lourdes des portails consomment un CPU entier en pointe.
- `shm_size: 1gb`, `init: true` et un `/tmp` en mémoire (512 Mo) sont posés dans le compose : sans eux Chromium plante (`/dev/shm` de 64 Mo).
- Si le conteneur est tué (code 137), c'est la limite mémoire : baissez `BE_NAVIGATEUR_SERVEUR_SESSIONS_MAX` ou augmentez `SERVEUR_LIMITE_MEMOIRE`.
- Disque : prévoir environ 600 Mo pour Chromium dans l'image, et quelques dizaines de Mo par profil de bureau.

### 12.4 Pause CAPTCHA / double authentification

L'agent **ne contourne jamais** un CAPTCHA ni une double authentification (règle 2). Lorsqu'il en détecte un, la tâche passe en pause
(motif `action_utilisateur_portail`) et le Centre de validation humaine affiche un bouton **« Ouvrir le navigateur de l'agent »**.
Marche à suivre pour l'opérateur : ouvrir l'écran, cliquer **« Prendre la main »**, résoudre le CAPTCHA ou saisir le code reçu,
cliquer **« Rendre la main à l'agent »**, puis **« Reprendre la tâche »** dans le Centre de validation. Ce que l'opérateur tape n'est ni
enregistré, ni journalisé, ni affiché dans l'historique.

### 12.5 Sécurité

- **Domaines officiels uniquement** (règle 6) : le navigateur n'ouvre que les domaines HTTPS autorisés par les fichiers `config/portails/*.yaml`.
  N'ajoutez un domaine qu'après vérification qu'il est officiel.
- **Profil isolé par bureau** : un sous-dossier distinct par bureau, jamais partagé ; il contient les cookies de session du portail et se
  traite comme un secret. Il vit dans un **volume séparé** (`volume_profils_navigateur`), à inclure dans les sauvegardes chiffrées seulement
  si vous acceptez de conserver ces sessions, et à ne jamais exposer.
- Conteneur non-root, `no-new-privileges`, limites mémoire/CPU/processus. Playwright lance Chromium sans bac à sable interne : l'isolation
  repose sur le conteneur. N'ajoutez pas `SYS_ADMIN` ni `--privileged`.
- Réservé aux humains administrateur et employé ; actions authentifiées avec jeton CSRF. L'opérateur voit exactement ce que l'agent voit :
  pas d'accès à d'autres onglets du serveur ni au système de fichiers.
- Les captures contiennent des données personnelles de candidats : elles ne sont pas conservées par l'interface (une image remplace la précédente).

---

## 13. Choix de l'hébergeur (comparatif honnête, non vérifié en ligne)

> **Aucun tarif ni aucune fonctionnalité n'a été vérifié en ligne** pour ce comparatif : il repose sur des connaissances générales. Tout prix est « à vérifier »
> sur le site de l'hébergeur le jour de la commande. Aucun compte n'a été créé. Les points juridiques sont à valider par un juriste.

**Contraintes du projet.** Utilisateurs en Algérie ; données personnelles de candidats (passeports, pièces justificatives) soumises à la loi 18-07 (elle
encadre les transferts de données hors d'Algérie et crée une autorité de protection des données : **à valider juridiquement**, notamment pour savoir si une
autorisation est requise pour un hébergement à l'étranger) et, pour les candidats européens, au RGPD. Taille minimale : 2 vCPU, 4 Go de mémoire
(Chromium : environ 500 Mo par session), 40 Go de disque, adresse IP publique fixe, sauvegardes hors serveur.

| Critère | OVHcloud (France) | Hetzner (Allemagne / Finlande) | Hébergeur en Algérie (centres de données locaux) |
|---|---|---|---|
| Juridiction / RGPD | UE, société française ; accord de traitement (DPA) normalement disponible : à vérifier | UE, société allemande ; DPA normalement disponible : à vérifier | Droit algérien : pas de transfert hors du pays ; RGPD des candidats européens à examiner |
| Latence vers l'Algérie | Bonne attendue (France) : à mesurer | Un peu plus élevée attendue : à mesurer | La meilleure attendue : à mesurer |
| Support en français | Oui attendu : à vérifier | Principalement anglais / allemand : à vérifier | Oui attendu |
| Paiement depuis l'Algérie | Carte internationale ou virement : **blocage possible**, à vérifier | Idem ; vérification d'identité fréquente : à vérifier | Paiement local (dinar) probable : à vérifier |
| VPS Linux avec Docker | Oui attendu | Oui attendu | **Souvent incertain** (Docker, IP fixe, ports 80/443, sauvegardes, niveau de service) : à vérifier |
| Stockage de sauvegardes hors serveur | Stockage objet : à vérifier | Stockage dédié aux sauvegardes : à vérifier | Rarement bien outillé : à vérifier |
| Prix d'un serveur 2 vCPU / 4 Go | à vérifier | à vérifier | à vérifier |

**Recommandation : OVHcloud, région France, sur un VPS ou une instance de 4 Go ou plus.** Justification :
1. l'hébergement reste dans l'UE sous RGPD, avec contrat et support en français ;
2. la proximité réseau avec l'Algérie est a priori meilleure que celle du nord de l'Europe (à mesurer avec un serveur d'essai) ;
3. il évite l'incertitude technique d'un hébergeur local sur Docker, les sauvegardes et le niveau de service.

**Réserves.** (a) Si le paiement par carte internationale depuis l'Algérie n'est pas possible, il faudra un tiers payeur ou un revendeur : à examiner avant de s'engager.
(b) Si un avis juridique impose de garder les données en Algérie, l'hébergeur local devient obligatoire : exigez alors, avant signature, Docker (ou accès root),
IP fixe, instantanés et sauvegarde distante. (c) Hetzner est une alternative sérieuse si son tarif et le paiement sont meilleurs. (d) Quel que soit le choix : ne rangez jamais
la clé maîtresse chez le fournisseur qui héberge les sauvegardes, et chiffrez disque et sauvegardes.
