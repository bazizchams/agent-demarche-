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
  - Lecture des documents : `services/lecture_documents.py` (texte PDF, OCR local), `lecture_vision.py` (vision locale, désactivée par défaut), `extractions.py`, `application_extractions.py` ; routes `api/v1/extractions.py`
  - Points forts et projet professionnel : `services/deductions_dossier.py`, `projet_professionnel.py` ; routes `api/v1/deductions.py`, `api/v1/projet_professionnel.py`
  - Catalogue et vœux : `services/catalogue_formations.py`, `fiche_formation.py`, `prerequis_formation.py`, `selection_voeux.py` (suggestions, lecture seule), `lettres_voeux.py` (brouillons) ; routes `api/v1/catalogue_formations.py`, `api/v1/voeux_suggestions.py`, `api/v1/voeux.py`
  - Rappels d'échéance : `services/rappels_echeances.py`, `echeances_demarche.py` ; commande `python -m app.cli envoyer-rappels-echeances`
  - Agent local à l'écoute (navigateur visible) : `services/reservation_taches.py`, `taches_ouverture_pc.py`, `serveur/app/agent_local/demon_ecoute.py`, `ouverture_visible.py`, `action_voeux_demo.py`, `agent_local/lanceur.py` ; routes `api/v1/agents_locaux.py`, `api/v1/taches.py`
  - Parcours complet d'un dossier et endpoints : `docs/FLUX_DOSSIER.md`
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

1. **Règle 1 (Validation humaine obligatoire avant soumission officielle)** *(modifiée le 2026-11-12 par décision du propriétaire du projet)* : L'agent ne soumet JAMAIS une demande officielle (Études en France, IRCC, école) sans validation humaine préalable. Il prépare le dossier en brouillon, produit un récapitulatif précis, et s'arrête. Seul un employé ou administrateur de l'agence, authentifié, peut valider ce récapitulatif. L'agent n'est autorisé à envoyer que ce contenu exact (empreinte du récapitulatif vérifiée juste avant l'envoi : toute modification invalide la validation). La validation est tracée dans l'audit (qui, quand, empreinte, sans donnée personnelle). Un agent ne peut pas valider lui-même. **Mise en œuvre dans le code : service, API, écran de validation, garde d'envoi (`soumission_validee.py`) branchée sur l'exécuteur en option, tests livrés (2026-11-12)** ; par défaut (aucune validation fournie) le comportement reste l'arrêt avant le bouton final. Aucun appelant de production ne fournit encore de validation.
2. **Règle 2 (Zéro contournement CAPTCHA / 2FA)** : Si un CAPTCHA ou une double authentification apparaît, l'agent se met en pause et alerte l'opérateur humain.
3. **Règle 3 (Mots de passe portail : coffre chiffré uniquement)** *(modifiée le 2026-11-12 par décision du propriétaire du projet)* : Les identifiants des comptes Études en France ou IRCC d'un candidat ne sont stockés que dans le coffre chiffré du bureau (chiffrement par la clé maîtresse, isolation par bureau), avec le consentement écrit du candidat tracé. Ils ne sont JAMAIS écrits en clair (base, fichiers, journaux, audit, messages d'erreur, captures, réponses d'API), jamais renvoyés par l'API après leur saisie, et ne sont lisibles que par l'agent au moment de la connexion. Leur suppression est possible à tout moment (révocation du consentement, suppression du candidat). **Mise en œuvre dans le code : coffre, API, écran de saisie et connexion (`connexion_portail.py`) livrés et testés (2026-11-12)** ; la connexion automatique n'est active que pour un portail dont le YAML définit les sélecteurs de connexion (aucun pour l'instant : connexion manuelle) et qu'un appelant la demande.
4. **Règle 4 (Zéro valeur par défaut inventée)** : Si un champ ou document candidat manque, l'agent ne l'invente jamais et le signale clairement.
5. **Règle 5 (Zéro donnée personnelle dans les logs/audit)** : Le journal d'audit SHA-256 ne contient jamais de nom, prénom, e-mail ou numéro de passeport en clair.
6. **Règle 6 (Vérification des domaines HTTPS officiels)** : Seuls les domaines officiels autorisés dans les fichiers YAML sont acceptés en mode réel.
