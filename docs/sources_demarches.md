# Sources des démarches de base (vérification au 2026-11-11)

## Sources officielles consultées (contenu récupéré)
- https://www.service-public.gouv.fr/particuliers/vosdroits/F2230 (visa court séjour Schengen)
- https://www.justice.fr/fiche/visa-court-sejour-schengen-etranger-france-3-mois-maximum (mise à jour 2025-10-12)
- https://www.justice.fr/fiche/etudiant-etranger-france-visa-long-sejour-titre-sejour (mise à jour 2026-05-01)
- https://www.quebec.ca/education/etudier-quebec/demande-selection-temporaire
- https://www.quebec.ca/education/etudier-quebec/documents
- https://www.quebec.ca/education/etudier-quebec/conditions-requises
- https://www.canada.ca/fr/immigration-refugies-citoyennete/organisation/publications-guides/bulletins-guides-operationnels/residents-temporaires/permis-etudes/etudiants-rendent-quebec.html
- https://www.canada.ca/en/immigration-refugees-citizenship/services/study-canada/study-permit/apply.html
- https://www.canada.ca/fr/immigration-refugies-citoyennete/services/immigrer-canada/entree-express/documents.html
- https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry/documents/education-assessment.html
- https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry/documents/language-test.html
- https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry/documents/proof-funds.html
- https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry/create-profile.html
- Recherche (extraits) : canada.ca « Présenter une demande de résidence permanente » (60 jours après invitation)

## À vérifier (non confirmé sur source officielle, absent des YAML)

### Visa Schengen (France, Algérie)
- Montant des droits de visa court séjour en DZD : france-visas.gouv.fr (page Algérie et Tarifs) renvoie HTTP 403 à l'outil. Un article de presse (lesafriques.com, 2026-09) cite 90 EUR + environ 29 EUR de frais de service ; non confirmé.
- Prestataire de dépôt : sources secondaires indiquent que Capago International remplace VFS/TLScontact depuis le 2025-04-08 ; à confirmer sur france-visas.gouv.fr/fr/algerie et le site Capago.
- Délai de traitement (environ 15 jours, 45 maximum) : source secondaire uniquement.
- Liste exacte des pièces (photo, justificatifs d'emploi, relevés bancaires, montant de ressources journalier) : l'assistant France-Visas n'a pas pu être consulté.

### Écoles privées en France
- Règles exactes de la procédure « Je suis accepté » pour une acceptation papier d'une école non connectée en Algérie (calendrier, frais, pièces, dispense éventuelle de certification de langue) : FAQ Campus France Algérie « acceptation papier / établissement non connecté » (https://www.algerie.campusfrance.org/faq/public/etudiants-4?page=5) dont le texte n'a pas été récupéré ; calendrier 2026-2027 (https://www.algerie.campusfrance.org/system/files/medias/documents/2025-09/Calendrier_2026-2027.pdf) illisible par l'outil (PDF).
- Réduction de 50 % sur les frais de visa avec l'attestation d'acceptation (indiquée dans campus_france.yaml, non revérifiée ici).
- Pièces du dossier de visa long séjour sur france-visas.gouv.fr (inaccessible, HTTP 403) ; seuil de ressources annuel non figé dans le YAML (615 EUR/mois vérifié, durée d'études variable).
- Justice.fr indique 150 EUR de taxe à la validation du VLS-TS ; des sources commerciales citent d'autres montants : confirmer sur le portail ANEF.

### Québec DEP / DEC
- Montant de capacité financière exigé pour le CAQ (page « Coût des études et de la vie » non retrouvée : URL en 404) : non renseigné.
- Processus d'admission collégiale (SRAM, dates limites) et plafonds par établissement : non vérifiés.
- Frais de traitement du permis d'études IRCC (hors biométrie 85 CAD) et montant de preuve de fonds IRCC pour le Québec : non trouvés sur les pages consultées.
- Exigences de LAP pour le Québec, examen médical, certificat de police : non confirmés.

### Résidence permanente (Entrée express)
- Montants de fonds minimaux : la page indiquait une mise à jour du 2025-07-07 (1 personne : 15 263 CAD) ; à revérifier car ces montants sont révisés chaque année.
- Frais de traitement de la demande de RP, grille SCG, catégories de sélection et seuils d'invitations : non repris dans le YAML.
- Conditions d'admissibilité par programme (TQF, CEC, métiers) : non détaillées.
