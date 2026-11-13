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
- Connexion à Études en France des écoles du catalogue (13 sur 15 non confirmées) : liste officielle uniquement en PDF Campus France (non lu), pages HTML campusfrance.org en 404 ; pages admissions des écoles relues le 2026-11-13 sans mention explicite. Langues/frais restants (EM Normandie, Rennes SB, EPITA, Efrei, ESILV, Strate, ECV, Vatel, Penninghen, Lyfe, MBS score) non publiés en HTML ; seule la langue de PSB a été levée.
- Règles exactes de la procédure « Je suis accepté » pour une acceptation papier d'une école non connectée en Algérie (calendrier, frais, pièces, dispense éventuelle de certification de langue) : FAQ Campus France Algérie « acceptation papier / établissement non connecté » (https://www.algerie.campusfrance.org/faq/public/etudiants-4?page=5) dont le texte n'a pas été récupéré ; calendrier 2026-2027 (https://www.algerie.campusfrance.org/system/files/medias/documents/2025-09/Calendrier_2026-2027.pdf) illisible par l'outil (PDF).
- Réduction de 50 % sur les frais de visa avec l'attestation d'acceptation (indiquée dans campus_france.yaml, non revérifiée ici).
- Pièces du dossier de visa long séjour sur france-visas.gouv.fr (inaccessible, HTTP 403) ; seuil de ressources annuel non figé dans le YAML (615 EUR/mois vérifié, durée d'études variable).
- Justice.fr indique 150 EUR de taxe à la validation du VLS-TS ; des sources commerciales citent d'autres montants : confirmer sur le portail ANEF.

### Québec DEP / DEC
- Montant de capacité financière exigé pour le CAQ (page « Coût des études et de la vie » non retrouvée : URL en 404) : non renseigné.
- Processus d'admission collégiale (SRAM, dates limites) et plafonds par établissement : non vérifiés.
- Frais de traitement du permis d'études IRCC (hors biométrie 85 CAD) et montant de preuve de fonds IRCC pour le Québec : non trouvés sur les pages consultées.
- Exigences de LAP pour le Québec, examen médical, certificat de police : non confirmés.

### Domaines d'authentification des portails réels (Règle 6) : tentative de vérification du 2026-11-12
Les outils de recherche et de lecture web étaient indisponibles lors de cette passe (erreur modèle de WebSearch/WebFetch,
connexion refusée par algerie.campusfrance.org). Aucun nouveau domaine n'a donc pu être confirmé sur une page officielle
gouvernementale : **aucun domaine n'a été ajouté aux YAML**. Domaines déjà présents, d'origine connue : URL officielle IRCC
(`portal-portail.apps.cic.gc.ca`, YAML), relevé de connexion Études en France (`pastel.diplomatie.gouv.fr`,
`etudesenfrance.diplomatie.gouv.fr`, voir docs/portail_etudes_en_france_reel.md, observé le 2026-11-11).

#### IRCC : domaines de connexion vérifiés le 2026-11-13 (navigateur, lecture seule, sans connexion)
Relevé des `href` des boutons sur la page officielle puis suivi des redirections jusqu'à la page de connexion
(aucun identifiant saisi). Ajoutés à `config/portails/ircc_reel.yaml` (`domaines_autorises`) :
- `onlineservices-servicesenligne-cic.fjgc-gccf.gc.ca` : cible des boutons « GCKey Sign-In »
  (`/mycic/gccf?lang=eng&idp=gckey&svc=/mycic/start`) et « Sign-In Partner » (`...&idp=securekey...`), versions EN et FR
  (`lang=fra`). Source : https://www.canada.ca/en/immigration-refugees-citizenship/services/application/account.html et
  https://www.canada.ca/fr/immigration-refugies-citoyennete/services/demande/compte.html
- `clegc-gckey.gc.ca` : page de connexion CléGC (`/j/eng/l`) après redirection depuis « GCKey Sign-In ». **La page charge un
  hCaptcha** (`div.h-captcha`, iframes `newassets.hcaptcha.com`) : règle 2, pause et alerte opérateur (sélecteur `.h-captcha`
  déjà présent dans `detecteurs_blocage_securite`). `hcaptcha.com` n'est volontairement pas autorisé en navigation.
- `services.signin.interac-id.ca` : service de connexion Interac (choix de la banque, `/cbs/saml/login`) après redirection
  depuis « Sign-In Partner ». Les hôtes des banques partenaires ne sont **pas** ajoutés (non relevés).
- `portal-portail.apps.cic.gc.ca` : « Sign in to the IRCC Portal » (redirige vers `/portal/signin`), confirmé sur
  https://www.canada.ca/en/immigration-refugees-citizenship/services/visit-canada/portal-application-process.html
- `ircc-services.canada.ca` : « IRCC Portal – New version » (`/cxp/s/login/`, `/cxp/s/eligibilitycheck`), sur
  https://www.canada.ca/en/immigration-refugees-citizenship/services/application/online-account.html

Restent à vérifier (IRCC) :
- `onlineservices-servicesenligne.cic.gc.ca` (déjà dans le YAML) : aucun lien vers cet hôte vu sur les pages consultées ;
  il s'agit peut-être de l'hôte du compte après connexion : à confirmer dans une session supervisée.
- Hôtes des banques partenaires (Sign-In Partner) et hôtes éventuels après connexion CléGC.
- Sélecteurs CSS des champs de connexion et du formulaire : non relevés (nécessitent un compte) ; ceux du YAML restent
  ceux de la maquette.

À vérifier sur le vrai portail (ouvrir une session supervisée, relever les redirections réellement bloquées dans les journaux
« Navigation refusée (Règle 6) », puis confirmer chaque hôte sur une page officielle canada.ca, diplomatie.gouv.fr ou
campusfrance.org avant de l'ajouter à `domaines_autorises`, avec la source citée ici) :
- Études en France : vérifié le 2026-11-13 (voir section suivante) : pas de fournisseur d'identité externe.
- Règle : hôtes exacts uniquement, jamais de joker ; refuser tout hôte tiers non gouvernemental (CDN publics, services
  de mesure) sauf s'il est indispensable et documenté.

### Études en France : connexion et création de compte (vérifié le 2026-11-13, navigateur intégré, lecture seule)
Aucune connexion, aucun compte créé, aucun champ rempli. Relevé :
- `https://pastel.diplomatie.gouv.fr/etudesenfrance` redirige vers
  `https://pastel.diplomatie.gouv.fr/etudesenfrance/dyn/public/authentification/login.html` (ancienne page, v4.0.20) :
  liens « Se connecter au portail étudiant » → `https://etudesenfrance.diplomatie.gouv.fr/connexion` et « Je m'inscris »
  → `https://etudesenfrance.diplomatie.gouv.fr/inscription`. Le lien du site Campus France Algérie
  `https://pastel.diplomatie.gouv.fr/etudesenfrance/dyn/public/login.html?ecf=DZ&locale=fr_DZ` mène à la même page.
  Ses scripts viennent aussi de `cdn.diplomatie.gouv.fr` (ressources seulement : la garde Règle 6 ne filtre que les
  navigations du cadre principal, ce domaine n'a donc pas été ajouté).
- Connexion : `https://etudesenfrance.diplomatie.gouv.fr/connexion` ; formulaire envoyé au même hôte ; champs
  « Identifiant » (une adresse mail) et « Mot de passe ». Aucune redirection vers un fournisseur d'identité ; toutes les
  ressources chargées viennent de `etudesenfrance.diplomatie.gouv.fr`.
- Mot de passe oublié : `https://etudesenfrance.diplomatie.gouv.fr/connexion/mot-de-passe-oublie` (adresse mail, puis
  « Envoyer le lien de réinitialisation »).
- Création de compte : `https://etudesenfrance.diplomatie.gouv.fr/inscription` (route de l'application : un chargement
  direct a renvoyé une page 404, l'accès passe par le lien « S'inscrire » de l'accueil). Champs : Prénom, Nom, Espace
  Campus France de résidence (« Espace Campus France Algérie »), Région de résidence (liste dépendante de l'espace, non
  ouverte), Adresse mail, Mot de passe et confirmation (12 caractères minimum, 1 minuscule, 1 majuscule, 1 chiffre,
  1 caractère spécial), case de consentement obligatoire, case facultative France Alumni.
- `https://www.algerie.campusfrance.org/utilisation-de-la-plateforme-etudes-en-france` : « Vous avez déjà un compte ?
  Vous ne devez pas en créer un nouveau » (données rapatriées sur la nouvelle plateforme) ; le site demande de ne pas
  communiquer ses identifiants à un tiers.
- `https://www.algerie.campusfrance.org/campagne-etudes-en-france-2027` : 5 actions (projet, candidature, paiement des
  frais en ligne dans les 48 h après soumission sur `https://paiement.if-algerie.com/`, entretien sur rendez-vous pris
  depuis le compte, choix définitif avant le 2027-05-31) ; « Je crée et je remplis moi-même mon dossier ».
- `https://www.algerie.campusfrance.org/le-calendrier-de-la-procedure` : campagne ouverte le 2026-10-01 (rentrée 2027) ;
  DAP : 2026-12-15 ; Hors DAP : 2026-12-22 (nouvelle date limite) ; entretiens : 2027-03-15.
- `https://www.algerie.campusfrance.org/horaires-d-attention-au-public-septembre-2026` : 5 espaces (Alger, Annaba,
  Constantine, Oran, Tlemcen) ; `https://paiement.if-algerie.com/verifier-statut` propose les mêmes 5 espaces.
- `https://algerie.campusfrance.org/` redirige vers `https://www.algerie.campusfrance.org/`.

Domaines retenus dans `config/portails/campus_france_reel.yaml` : `etudesenfrance.diplomatie.gouv.fr`,
`pastel.diplomatie.gouv.fr`, `www.algerie.campusfrance.org`, `algerie.campusfrance.org` (ajouté), `paiement.if-algerie.com`.

Encore à vérifier : page d'activation du compte (lien reçu par courriel ?) et son hôte ; procédure en cas de compte
bloqué ; libellés exacts des régions de résidence pour l'Algérie ; grille des frais (FAQ en erreur 503 le 2026-11-13) ;
passage d'un compte d'une campagne à la suivante (réactivation).

### Résidence permanente (Entrée express)
- Montants de fonds minimaux : toujours affichés le 2026-11-13 avec la mention « Updated July 7, 2025 » (1 personne : 15 263 CAD) ; repris dans `ircc_entree_express_rp.yaml`, à revérifier à la prochaine révision annuelle.
- Frais de RP, conditions par programme (TQF, CEC, TMF), rondes d'invitations et changements SCG du 2026-11-03 : vérifiés le 2026-11-13, voir section suivante.
- Grille SCG détaillée (hors facteur « intégration au marché du travail ») et délais de traitement : non repris.

## Procédures IRCC ajoutées le 2026-11-13 (navigateur intégré, pages canada.ca / ircc.canada.ca)
Fichiers : `config/demarches/ircc_visa_visiteur.yaml`, `config/demarches/ircc_visite_famille_super_visa.yaml`,
`config/demarches/ircc_entree_express_rp.yaml`. Toutes s'arrêtent avant paiement et soumission (règle 1).

Sources consultées :
- https://www.canada.ca/en/immigration-refugees-citizenship/services/visit-canada/apply-visitor-visa.html (motifs tourisme et visite familiale, Algérie : « There are no local visa office instructions for your country »)
- https://www.canada.ca/en/immigration-refugees-citizenship/services/visit-canada/eligibility.html
- https://www.canada.ca/en/immigration-refugees-citizenship/services/visit-canada/after-apply-next-steps.html
- https://www.canada.ca/en/immigration-refugees-citizenship/services/visit-canada/parent-grandparent-super-visa.html (+ eligibility, forms-documents, apply)
- https://www.canada.ca/en/immigration-refugees-citizenship/services/biometrics/how-to-give.html et where-to-give.html (CRDV « Algiers, Algeria » : https://visa.vfsglobal.com/dza/en/can)
- https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry.html (+ changes, who-can-apply, check-score, documents/proof-funds, rounds-invitations, apply-permanent-residence, after-apply)
- https://ircc.canada.ca/english/information/fees/fees.asp (« Date modified: 2026-11-10 ») : visa de visiteur / super visa 100 CAD par personne, 500 CAD par famille de 5+ ; biométrie 85 CAD (170 CAD par famille de 2+) ; immigration économique 990 CAD + DRP 600 CAD (1 590 CAD), conjoint idem, enfant à charge 270 CAD.

À vérifier :
- Délais de traitement (visiteur, super visa pour l'Algérie ; RP Entrée express) : outil « Check processing times » non consulté.
- Super visa : barème du revenu minimal nécessaire de l'hôte (page « Proof of financial support » non lue).
- Visa de visiteur : aucun montant de fonds chiffré par IRCC (« depends on how long you will stay »).
- Entrée express : contenu exact exigé des lettres d'employeur ; grille SCG complète.
