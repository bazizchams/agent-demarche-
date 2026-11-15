# Plateforme Agent Bureau d'Études — Algérie (Campus France & IRCC Canada)

Plateforme multi-bureaux (SaaS) avec **Co-Pilote Navigateur en direct** (Playwright) pour l'accompagnement supervisé des dossiers étudiants vers la France (**Études en France — Guide officiel Septembre 2026**) et le Canada (**IRCC — Permis d'études IMM 1294**).

---

## Fonctionnalités principales

- **Chiffrement de bout en bout par bureau (`AES-256-GCM` + `HKDF-SHA256`)** : toutes les données personnelles (état civil, passeport, e-mail, téléphone) et toutes les pièces justificatives téléversées sont chiffrées au repos avec une clé dérivée par bureau (`tenant_id`) et par candidat. Recherche rapide via index aveugle `HMAC-SHA256`.
- **Conformité Loi algérienne 18-07 & RGPD** : recueil du consentement explicite horodaté, registre des activités de traitement, droit d'accès/portabilité et suppression définitive.
- **Vérification des pièces manquantes & Génération de spécimens de test en 1 clic** : affichage clair en français des pièces requises par démarche (Campus France / IRCC).
- **Assistant Conseiller & Score d'acceptation (0–100 %)** :
  - Évaluation pondérée sur 100 % (complétude documentaire, passeport, solidité financière, cohérence académique, conformité réglementaire).
  - Référentiel officiel **Campus France Algérie — Septembre 2026** intégré (calendrier 2026–2027 DAP / Hors DAP, frais `20 000 DZD` / `10 000 DZD` sur `paiement.if-algerie.com`, 5 antennes : Alger, Annaba, Constantine, Oran, Tlemcen, réduction visa CAPAGO `-50 %` avec identifiant `DZXX-XXXXX`).
  - Seuil financier **IRCC Canada** relevé (`20 635 CAD` hors frais de scolarité + Lettre d'Attestation Provinciale LAP/PAL ou CAQ Québec).
- **Co-Pilote Navigateur en direct (style Perplexity Assistant / Claude Cowork)** :
  - Pilote directement une fenêtre Chromium visible avec barre latérale Co-Pilote injectée dans la page.
  - Exécute les instructions en langage naturel ou à la voix en temps réel sur les portails officiels (`https://etudesenfrance.diplomatie.gouv.fr/`, `https://portal-portail.apps.cic.gc.ca/`) ou sur les pages de simulation locales (`/demo/campus-france`, `/demo/ircc`).
- **Lecture des documents avec revue humaine** : texte natif des PDF (pypdf) puis OCR local (RapidOCR, français et anglais) ; un modèle de vision local est facultatif et désactivé par défaut. Chaque valeur lue reste « à valider » jusqu'à une décision d'un employé ou administrateur (valider, rejeter, corriger). Seules les valeurs confirmées sont appliquées à la fiche du candidat. L'agent local n'a aucun accès à cette revue.
- **Points forts et projet professionnel** : points forts calculés par des règles déterministes (sans IA) à partir des seules valeurs confirmées, chacun avec sa pièce justificative ; confirmation ou rejet humain ; brouillon de projet professionnel généré à partir des points forts confirmés, modifiable puis validé par un humain.
- **Catalogue de formations et suggestions de vœux** : catalogue des fiches de formation du bureau (écoles privées, fiches relevées sur les portails officiels) ; suggestions de sept vœux au maximum selon les prérequis réels des fiches (diplôme, moyenne, langue, date limite). Les suggestions sont en lecture seule : un vœu n'est créé que par une action humaine. Une exigence inconnue ou une donnée absente ne produit jamais un « ok ».
- **Lettres de motivation des vœux** : rédaction d'un brouillon enregistré à relire ; sans clé d'IA, un modèle avec des repères « [À COMPLÉTER] » qui bloquent la validation.
- **Agent Local à l'écoute (navigateur visible sur le PC du bureau)** : sur un PC Windows du bureau, l'agent attend les tâches « Ouvrir sur mon PC », ouvre une fenêtre Chrome ou Edge visible et ajoute les vœux **validés** au panier de la page de démonstration. Il s'arrête avant tout envoi, se met en pause sur CAPTCHA ou 2FA et ne reçoit jamais le mot de passe du coffre. Voir [docs/AGENT_LOCAL.md](docs/AGENT_LOCAL.md).
- **Rappels d'échéance par courriel** : rappels des échéances des démarches envoyés aux membres du bureau, idempotents (un seul envoi par échéance et par seuil), déclenchables par un administrateur ou par une tâche planifiée.
- **6 Règles de sécurité immuables** :
  - **Règle 1** : Arrêt obligatoire avant le bouton de soumission finale officielle — validation humaine explicite requise dans le Centre de validation.
  - **Règle 2** : Aucun contournement de CAPTCHA ou 2FA (pause automatique avec alerte opérateur).
  - **Règle 3** : Aucun stockage des mots de passe des portails officiels (Études en France / CléGC IRCC).
  - **Règle 4** : Zéro valeur par défaut inventée si une donnée candidat est absente.
  - **Règle 5** : Journal d'audit immuable chaîné SHA-256 sans aucune donnée personnelle (PII).
  - **Règle 6** : Vérification stricte des domaines HTTPS officiels et des sélecteurs YAML versionnés.

---

## Structure du dépôt

```text
plateforme/
├── config/
│   ├── demarches/          # Règles métier YAML (campus_france.yaml, ircc_permis_etudes.yaml)
│   └── portails/           # Sélecteurs et étapes Playwright (campus_france.yaml, ircc_permis_etudes.yaml)
├── agent_local/
│   └── lanceur.py          # Lanceur de l'agent local sur le poste Windows de l'opérateur
├── deploiement/
│   ├── Dockerfile
│   ├── docker-compose.production.yml
│   └── Caddyfile
└── serveur/
    ├── alembic/            # Migrations de base de données
    ├── app/
    │   ├── agent_local/    # Exécuteur Playwright, Co-Pilote temps réel & Guide Septembre 2026
    │   ├── api/v1/         # Routes FastAPI (auth, candidats, documents, taches, portails, audit...)
    │   ├── core/           # Configuration, sécurité Argon2id/CSRF, chiffrement AES-256-GCM
    │   ├── demo/           # Pages de simulation locales Études en France & IRCC
    │   ├── interface/      # Interface web complète en français + Co-Pilote temps réel
    │   ├── modeles/        # Modèles SQLAlchemy 2.0
    │   ├── schemas/        # Schémas Pydantic v2
    │   └── services/       # Logique métier (candidats, documents, conseiller, tâches, conformité...)
    └── tests/              # Suite complète de tests automatisés (pytest + Playwright)
```

---

## Démarrage rapide en local (Windows / Linux / macOS)

```bash
cd serveur
python -m venv .venv
# Windows PowerShell :
.\.venv\Scripts\pip install -e ".[dev]"
.\.venv\Scripts\playwright install chromium

# Copier et adapter la configuration :
copy .env.exemple .env

# Lancer les migrations et démarrer le serveur :
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Ouvrez ensuite **`http://127.0.0.1:8000`** dans votre navigateur.

> `alembic upgrade head` est recommandé même en local lorsque la base existe déjà : en environnement `LOCAL`, le démarrage ne crée que les tables manquantes (`create_all`) et ne met pas à jour le schéma d'une base ancienne.

### Options de lancement

```powershell
# Lecture des documents (PDF, images) : pypdf, RapidOCR, onnxruntime (facultatif)
cd serveur
.\.venv\Scripts\pip install -e ".[lecture]"

# Rappels d'échéance par courriel (idempotent : à planifier, par exemple avec une tâche planifiée Windows)
cd serveur
.\.venv\Scripts\python.exe -m app.cli envoyer-rappels-echeances

# Agent Local sur un PC Windows du bureau : double-cliquer sur agent_local\installer_agent.bat (une fois),
# puis sur agent_local\lancer_agent.bat (laisser la fenêtre ouverte ; -Oublier efface l'adresse et la clé mémorisées)

# Agent Local en mode développeur (clé dans la variable d'environnement BE_JETON_AGENT)
.\agent_local\.venv-agent\Scripts\python.exe agent_local\lanceur.py --mode ecouter --url-serveur http://127.0.0.1:8000
```

**Production** : `BE_ENVIRONNEMENT=production` et `BE_COOKIE_SECURISE=true` sont obligatoires. Hors Windows, `BE_CLE_MAITRESSE_BASE64` (32 octets en base64) est également obligatoire, sinon le serveur refuse de démarrer. Voir [docs/DEPLOIEMENT.md](docs/DEPLOIEMENT.md).

Parcours complet d'un dossier, endpoint par endpoint : [docs/FLUX_DOSSIER.md](docs/FLUX_DOSSIER.md).

---

## Exécuter les tests automatisés

```bash
cd serveur
.\.venv\Scripts\pytest -q
```
