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

---

## Exécuter les tests automatisés

```bash
cd serveur
.\.venv\Scripts\pytest -q
```
