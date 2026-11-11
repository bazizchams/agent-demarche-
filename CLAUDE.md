# CLAUDE.md — Guide du projet pour Claude Code

Ce dossier contient la **Plateforme Agent Bureau d'Études — Algérie (Campus France & IRCC Canada)** avec son **Co-Pilote Navigateur en direct** (Playwright).

## 1. Emplacement et structure du code

- Racine du dépôt : `C:\Users\HP\Desktop\agentbureau\plateforme`
- Backend FastAPI + Interface Web + Agent Navigateur : `serveur/`
  - `serveur/app/main.py` : point d'entrée FastAPI
  - `serveur/app/interface/routeur_interface.py` : interface web complète en français + Co-Pilote temps réel (style Perplexity Assistant / Claude Cowork)
  - `serveur/app/agent_local/pilote_navigateur.py` : pilote Playwright temps réel avec panneau Co-Pilote injecté dans le navigateur Chromium, compréhension du langage naturel et garde-fous
  - `serveur/app/agent_local/guide_campus_france_2026.py` : référentiel complet du Guide Études en France — Septembre 2026 (96 pages, Campus France Algérie)
  - `serveur/app/demo/routeur_demo.py` : pages de simulation locales (`/demo/campus-france` et `/demo/ircc`)
  - `serveur/app/services/` : logique métier (`candidats.py`, `documents.py`, `conseiller_dossier.py`, `taches.py`, `abonnements.py`, `conformite.py`, `sauvegardes.py`)
  - `serveur/app/api/v1/` : routes REST (`/api/v1/auth`, `/api/v1/candidats`, `/api/v1/taches`, `/api/v1/portails`, `/api/v1/validations`, `/api/v1/audit`, etc.)
- Configurations YAML :
  - `config/demarches/campus_france.yaml` & `config/demarches/ircc_permis_etudes.yaml`
  - `config/portails/`

## 2. Commandes utiles (Windows PowerShell)

```powershell
# Se placer dans le dossier serveur
cd C:\Users\HP\Desktop\agentbureau\plateforme\serveur

# Lancer le serveur FastAPI en local sur http://127.0.0.1:8000
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000

# Lancer toute la suite de tests (34 tests pytest + Playwright)
.\.venv\Scripts\pytest.exe -q
```

Identifiants opérateur de démonstration par défaut :
- **E-mail** : `admin@bureau-alger.dz`
- **Mot de passe** : `BureauAlger!2026`

## 3. Règles de sécurité immuables (à toujours respecter)

1. **Règle 1 (Arrêt obligatoire avant soumission officielle)** : L'agent ne doit JAMAIS cliquer sur le bouton final de soumission officielle sur Études en France ou IRCC. Il s'arrête en mode brouillon et demande une validation humaine.
2. **Règle 2 (Zéro contournement CAPTCHA / 2FA)** : Si un CAPTCHA ou une double authentification apparaît, l'agent se met en pause et alerte l'opérateur humain.
3. **Règle 3 (Aucun mot de passe portail stocké)** : L'agent ne stocke jamais les mots de passe des comptes Études en France ou CléGC IRCC.
4. **Règle 4 (Zéro valeur par défaut inventée)** : Si un champ ou document candidat manque, l'agent ne l'invente jamais et le signale clairement.
5. **Règle 5 (Zéro donnée personnelle dans les logs/audit)** : Le journal d'audit SHA-256 ne contient jamais de nom, prénom, e-mail ou numéro de passeport en clair.
6. **Règle 6 (Vérification des domaines HTTPS officiels)** : Seuls les domaines officiels autorisés dans les fichiers YAML sont acceptés en mode réel.
