"""Référentiel structuré du Guide officiel « Études en France — Septembre 2026 »
(Spécifique à Campus France Algérie, 96 pages).

Ce module alimente :
1. L'Assistant Conseiller Dossier (réponses précises aux questions sur la procédure, les dates,
   les frais en DZD, le panier de formations DAP/Hors DAP, le dossier pré-consulaire, les antennes).
2. Le Pilote Navigateur Playwright (séquence de navigation pas-à-pas, détection des boutons et
   des rubriques officielles sur `https://etudesenfrance.diplomatie.gouv.fr/`, et garde-fous Règle 1).
3. L'interface web opérateur (guide interactif complet consultable sans quitter la plateforme).
"""

from __future__ import annotations

from typing import Any

GUIDE_CAMPUS_FRANCE_SEPTEMBRE_2026: dict[str, Any] = {
    "titre": "Guide de la plateforme des étudiants internationaux — Études en France (Septembre 2026)",
    "pays": "Algérie",
    "identifiant_format": "DZXX-XXXXX",
    "urls_officielles": {
        "plateforme_etudes_en_france": "https://etudesenfrance.diplomatie.gouv.fr/",
        "portail_historique_pastel": "https://pastel.diplomatie.gouv.fr/etudesenfrance",
        "campus_france_algerie": "https://www.algerie.campusfrance.org/horaires-d-attention-au-public",
        "paiement_ifa_algerie": "https://paiement.if-algerie.com",
    },
    "antennes_algerie": [
        {"ville": "Alger", "email": "ecf.alger@if-algerie.com"},
        {"ville": "Annaba", "email": "ecf.annaba@if-algerie.com"},
        {"ville": "Constantine", "email": "ecf.constantine@if-algerie.com"},
        {"ville": "Oran", "email": "ecf.oran@if-algerie.com"},
        {"ville": "Tlemcen", "email": "ecf.tlemcen@if-algerie.com"},
    ],
    "calendrier_2026_2027": [
        {
            "categorie": "DAP (L1, Écoles d'architecture ENSA, BUT, Licence professionnelle)",
            "ouverture": "1er octobre 2026",
            "date_limite_soumission_et_paiement": "15 décembre 2026",
            "date_limite_entretiens": "15 mars 2027",
            "date_limite_choix_definitif": "31 mai 2027",
        },
        {
            "categorie": "Hors DAP (L2, L3, Master 1, Master 2, Écoles d'ingénieurs et de commerce)",
            "ouverture": "1er octobre 2026",
            "date_limite_soumission_et_paiement": "30 novembre 2026",
            "date_limite_entretiens": "15 mars 2027",
            "date_limite_choix_definitif": "31 mai 2027",
        },
        {
            "categorie": "CPGE, BTS, DCG (Filières sélectives)",
            "ouverture": "À partir de janvier 2027 sur Parcoursup",
            "date_limite_soumission_et_paiement": "Selon calendrier Parcoursup puis dossier pré-consulaire",
            "date_limite_entretiens": "Après admission Parcoursup",
            "date_limite_choix_definitif": "Au minimum 45 jours avant la rentrée",
        },
        {
            "categorie": "Établissements privés non-connectés / Acceptation papier (Dossier pré-consulaire)",
            "ouverture": "Dès réception de l'acceptation (onglet 'Je suis accepté')",
            "date_limite_soumission_et_paiement": "Au minimum 45 jours avant le début de la formation",
            "date_limite_entretiens": "Selon convocation ECF",
            "date_limite_choix_definitif": "Avant demande de visa long séjour (> 90 jours)",
        },
    ],
    "frais_dossier_algerie": {
        "plein_tarif": {
            "montant_dzd": 20000,
            "libelle": "20 000 DZD",
            "conditions": "Dossier de candidature, dossier pré-consulaire ou convocation concours/examen.",
        },
        "demi_tarif": {
            "montant_dzd": 10000,
            "libelle": "10 000 DZD",
            "conditions": "Titulaire d'un Bac français de moins de 4 ans et âgé de moins de 22 ans, ou titulaire d'une acceptation Campus Art.",
        },
        "gratuite": {
            "montant_dzd": 0,
            "libelle": "Gratuit (0 DZD)",
            "conditions": "Boursier du gouvernement français (BGF), bachelier du LIAD de l'année en cours, ou agent de l'Institut français d'Algérie (IFA).",
        },
        "avantage_visa_capago": "L'attestation d'acceptation Études en France donne droit à une réduction de 50 % sur les frais de visa long séjour pour études (France-Visas + centre CAPAGO).",
    },
    "sections_navigation": [
        {
            "numero": 1,
            "code": "accueil_et_eligibilite",
            "titre": "1 & 2. Accueil, Paramètres et Questionnaire d'éligibilité",
            "pages_guide": "Pages 1 à 20",
            "description": (
                "Accès sur https://etudesenfrance.diplomatie.gouv.fr/. Choix de la langue (FR / EN) en haut "
                "et des paramètres d'affichage en pied de page (Thème clair / sombre / système). "
                "Questionnaire 'Dois-je candidater par Études en France ?' : Pays de résidence (Algérie), "
                "nationalité, bac français/européen (Oui/Non), filières sélectives non universitaires (Oui/Non)."
            ),
            "actions_agent": [
                "Ouvrir https://etudesenfrance.diplomatie.gouv.fr/",
                "Sélectionner la langue Française (FR)",
                "Vérifier le questionnaire d'éligibilité pour un résident en Algérie",
            ],
        },
        {
            "numero": 2,
            "code": "creation_compte_et_connexion",
            "titre": "3. Mon compte (Inscription, Connexion et Messagerie)",
            "pages_guide": "Pages 18 à 27",
            "description": (
                "Création de compte : bouton 'S'inscrire' en haut à droite -> Formulaire 'Vous êtes étudiant ? "
                "Inscrivez-vous à Études en France' : Prénom*, Nom*, Espace Campus France de résidence* "
                "(Espace Campus France Algérie), Région de résidence*, Adresse mail*, Mot de passe*, "
                "case obligatoire d'exploitation des données*, case France Alumni -> bouton 'S'inscrire' "
                "(lien d'activation par mail valable 48h). "
                "Connexion : bouton 'Se connecter' (Attention : compte bloqué 30 minutes au bout de 5 tentatives erronées). "
                "Messagerie accessible via l'onglet 'Messages (0)' à côté du 'Fil d'actualité'."
            ),
            "actions_agent": [
                "Cliquer sur 'S'inscrire' et pré-remplir Nom, Prénom, E-mail et Espace Campus France Algérie",
                "Ou ouvrir la page 'Se connecter' et laisser l'opérateur saisir le mot de passe (Règle 3)",
            ],
        },
        {
            "numero": 3,
            "code": "mon_espace_etudiant",
            "titre": "4. Mon espace étudiant (Identité, Scolarité, Compétences linguistiques)",
            "pages_guide": "Pages 28 à 43",
            "description": (
                "Menu 'Mes dossiers' -> 'Mon dossier de candidature' (ou pré-consulaire) -> ligne 'Mon espace étudiant' -> 'Modifier'.\n"
                "• Onglet 1 'Mes informations personnelles' : Identité (Nom*, Prénom*, Sexe, Date et lieu de naissance, Nationalité, Handicap Oui/Non), "
                "Photo d'identité* (JPG/PNG/PDF, max 10 Mo, format passeport), Pièce d'identité* (Passeport, numéro*, pays de délivrance*, date limite de validité*, copie*), "
                "Coordonnées (Adresse, Code postal, Ville, Wilaya/Région, Pays, Numéro de téléphone définissant l'antenne ECF).\n"
                "• Section 'Statut particulier' : Bourse / Autre statut ou cocher 'Je ne suis concerné par aucun de ces statuts particuliers.' -> 'Enregistrer'.\n"
                "• Onglet 2 'Mon dossier de scolarité' : Curriculum Vitæ* (max 10 Mo) + 'Parcours scolaire et professionnel' (minimum 2 activités obligatoires : "
                "années de lycée jusqu'au bac pour Bac+1 ; du bac jusqu'à la dernière année d'études supérieures pour Bac+2 et +) via '+ Ajouter une activité' "
                "(Types : 'Une année de lycée', 'Un bac ou équivalent', 'Un concours', 'Un diplôme d'études supérieures', 'Une année d'études supérieures', 'Une autre activité' + justificatifs et commentaire 0/1000 caractères).\n"
                "• Onglet 3 'Mes compétences linguistiques' : Français ('J'ai déjà étudié le français*' : si bac non européen en français -> Oui, 'Plus de 1000 heures', '4 ans et plus', niveau 'Avancé'), "
                "Test de français ('+ Ajouter un test' : TCF, DELF/DALF, date session, score, justificatif), Niveau d'anglais, Séjour en France optionnel ('+ Ajouter un séjour')."
            ),
            "actions_agent": [
                "Pré-remplir 'Mes informations personnelles' (Identité, Passeport, Coordonnées)",
                "Valider 'Statut particulier'",
                "Téléverser le CV et renseigner les activités du 'Parcours scolaire et professionnel'",
                "Renseigner 'Mes compétences linguistiques' (Français > 1000h / TCF / DELF et Anglais)",
            ],
        },
        {
            "numero": 4,
            "code": "mon_dossier_candidature",
            "titre": "5. Mon dossier de candidature (Panier max 7 formations, Motivations, Paiement, Entretien)",
            "pages_guide": "Pages 44 à 70",
            "description": (
                "• 'Mon panier de formations' -> '+ Ajouter une formation' : jusqu'à 7 formations au total "
                "(DAP Blanche : jusqu'à 3 choix L1 ; DAP Jaune : 2 choix obligatoires ENSA architecture + Portfolio ; "
                "Hors DAP : jusqu'à 7 choix L2, L3, M1, M2, Ingénieur, Commerce).\n"
                "• Recherche dans le Catalogue : filtres par libellé, type de diplôme, établissement, domaine, région, ville. "
                "Vérifier les badges 'OUVERT À LA CANDIDATURE' et 'PROCÉDURE UNIQUEMENT SUR ÉTUDES EN FRANCE'.\n"
                "• Pour chaque formation du panier : cliquer sur 'Texte de motivation' -> rédiger dans 'Vos motivations' (max 4 000 caractères) -> 'Enregistrer'.\n"
                "• Vérifier le bandeau 'Votre dossier de candidature est complété.' et tous les badges 'COMPLÉTÉ'.\n"
                "• RÈGLE 1 (ARRÊT OBLIGATOIRE DE L'AGENT) : l'agent s'arrête strictement avant les 2 cases de certification et le bouton 'Soumettre mon dossier de candidature'.\n"
                "• Paiement : Onglet 'Mes paiements' -> 'Déclarer un paiement - Candidature' (Nom du payeur*, Date*, Virement, Référence*, Banque/agence/ville*) et téléchargement de la Quittance.\n"
                "• Entretien : Onglet 'Mes rendez-vous' -> 'Prendre un rendez-vous' (choix antenne, date et créneau) -> Télécharger la Convocation."
            ),
            "actions_agent": [
                "Rechercher les formations dans le Catalogue et les ajouter au panier (max 7)",
                "Saisir et enregistrer le 'Texte de motivation' (jusqu'à 4 000 caractères)",
                "Prendre la capture de contrôle et s'arrêter AVANT 'Soumettre mon dossier de candidature' (Règle 1)",
            ],
        },
        {
            "numero": 5,
            "code": "mon_dossier_preconsulaire",
            "titre": "6. Mon dossier pré-consulaire ('Je suis accepté' — Visa long séjour > 90 jours)",
            "pages_guide": "Pages 71 à 91",
            "description": (
                "Menu 'Mes dossiers' -> 'Mon dossier pré-consulaire' (sections : 'Mon espace étudiant', 'Statut particulier', 'Mon projet d'étude').\n"
                "• Cas 1 — Admission obtenue via Études en France : dans 'Mon projet d'étude' -> 'Modifier' -> sélectionner l'unique formation acceptée retenue.\n"
                "• Cas 2 — Acceptation papier hors Études en France ou Programme d'échange : '+ Ajouter un projet d'étude' en 4 étapes :\n"
                "  - Étape 1/4 : 'Acceptation papier' ou 'Programme d'échange' -> 'Étape suivante'\n"
                "  - Étape 2/4 : 'Formation diplômante', 'Formation professionnelle continue', 'Concours', 'Formation français langue étrangère (FLE)', 'Doctorat' ou 'Autre'\n"
                "  - Étape 3/4 : Recherche dans la liste ou cocher 'Je n'ai pas trouvé la formation dans la liste des formations' (Nom*, Niveau d'entrée*, Domaine*, Type de diplôme*, Établissement*, Site*, Date de début*, Date de fin*)\n"
                "  - Étape 4/4 : 'Motivations' (0/4 000 caractères) + 'Justificatif' (copie de l'acceptation papier) -> 'Enregistrer'.\n"
                "• RÈGLE 1 (ARRÊT OBLIGATOIRE DE L'AGENT) : arrêt avant les 2 cases de certification et 'Soumettre mon dossier pré-consulaire'.\n"
                "• Fin de procédure : téléchargement de l'Attestation d'acceptation (identifiant DZXX-XXXXX), puis demande de visa sur France-Visas et dépôt chez CAPAGO (-50 % sur les frais de visa)."
            ),
            "actions_agent": [
                "Ouvrir 'Mon dossier pré-consulaire' et configurer 'Mon projet d'étude' (Étapes 1 à 4)",
                "Saisir les motivations et téléverser l'acceptation papier",
                "S'arrêter AVANT 'Soumettre mon dossier pré-consulaire' (Règle 1)",
            ],
        },
    ],
    "selecteurs_et_libelles_soumission_interdits_regle1": [
        "#btn-soumettre-dossier-eef",
        "#btn-soumission-finale-officielle",
        "button[data-action-officielle='soumettre-dossier-eef']",
        "button[data-action-officielle='soumettre-definitivement']",
        "Soumettre mon dossier de candidature",
        "Soumettre mon dossier pré-consulaire",
        "Soumettre ma déclaration",
        "Confirmer mon rendez-vous",
    ],
}


def repondre_question_guide_campus_france(question: str) -> list[str]:
    """Retourne les points précis du Guide Études en France Septembre 2026 (Algérie)
    pertinents pour la question posée par l'opérateur."""
    q = question.lower()
    reponses: list[str] = []

    if any(m in q for m in ("frais", "tarif", "payer", "paiement", "dzd", "dinar", "20 000", "20000", "quittance", "capago")):
        reponses.append(
            "Frais de dossier Campus France Algérie et paiement (Guide Septembre 2026) :\n"
            "  • Plein tarif : 20 000 DZD (dossier de candidature, pré-consulaire ou concours).\n"
            "  • Demi-tarif : 10 000 DZD (Bac français de moins de 4 ans et candidat < 22 ans, ou acceptation Campus Art).\n"
            "  • Gratuité : boursier du gouvernement français, bachelier du LIAD de l'année en cours, agent de l'Institut français d'Algérie.\n"
            "  • Paiement en ligne sur paiement.if-algerie.com ou déclaration dans l'onglet 'Mes paiements' -> 'Déclarer un paiement - Candidature' (Nom du payeur, Date, Virement, Référence, Banque/Agence/Ville).\n"
            "  • Avantage visa : l'Attestation d'acceptation finale (identifiant DZXX-XXXXX) donne droit à -50 % sur les frais de visa long séjour chez CAPAGO."
        )

    if any(m in q for m in ("date", "calendrier", "délai", "delai", "quand", "ouverture", "limite", "novembre", "décembre", "decembre", "mars", "mai")):
        reponses.append(
            "Calendrier officiel Campus France Algérie (Session 2026–2027) :\n"
            "  • Hors DAP (L2, L3, Master 1, Master 2, Ingénieur, Commerce) : ouverture le 1er octobre 2026, soumission et paiement jusqu'au 30 novembre 2026.\n"
            "  • DAP (L1, Écoles d'architecture ENSA, BUT, Licence pro) : ouverture le 1er octobre 2026, soumission et paiement jusqu'au 15 décembre 2026.\n"
            "  • Entretiens Campus France : jusqu'au 15 mars 2027 ; choix définitif d'établissement avant le 31 mai 2027.\n"
            "  • CPGE, BTS, DCG : à partir de janvier 2027 sur Parcoursup.\n"
            "  • Dossier pré-consulaire ('Je suis accepté') : au minimum 45 jours avant la rentrée."
        )

    if any(m in q for m in ("panier", "formation", "voeu", "vœu", "dap", "architecture", "ensa", "catalogue", "motivation", "4000", "7")):
        reponses.append(
            "Règles du Panier de formations et Motivations (Section 5 du Guide Septembre 2026) :\n"
            "  • Maximum 7 formations au total dans 'Mon panier de formations'.\n"
            "  • DAP Blanche (1re année de Licence L1 à l'université) : jusqu'à 3 choix maximum.\n"
            "  • DAP Jaune (Écoles nationales supérieures d'architecture — ENSA) : 2 choix obligatoires + téléversement obligatoire d'un Portfolio.\n"
            "  • Hors DAP (L2, L3, Master 1, Master 2, écoles d'ingénieurs et de commerce) : jusqu'à 7 choix.\n"
            "  • Vérifier dans le Catalogue que la formation affiche 'OUVERT À LA CANDIDATURE' et 'PROCÉDURE UNIQUEMENT SUR ÉTUDES EN FRANCE'.\n"
            "  • Pour chaque formation, rédiger un 'Texte de motivation' personnalisé (maximum 4 000 caractères) et cliquer sur 'Enregistrer'."
        )

    if any(m in q for m in ("langue", "tcf", "delf", "dalf", "français", "francais", "anglais", "1000", "bac")):
        reponses.append(
            "Compétences linguistiques et règle du Baccalauréat (Section 4 — Onglet 3 du Guide Septembre 2026) :\n"
            "  • Si le candidat a préparé un baccalauréat non européen en français : dans 'Niveau de langue : français', sélectionner 'Oui', Volume d'heures : 'Plus de 1000 heures', Durée : '4 ans et plus', Niveau atteint : 'Avancé', puis renseigner le lycée et joindre le justificatif.\n"
            "  • Dans 'Test de langue : français' -> '+ Ajouter un test' : sélectionner TCF ou DELF/DALF, indiquer la date de session (validité TCF : 2 ans), le lieu, le score obtenu et téléverser l'attestation.\n"
            "  • Renseigner également le niveau d'anglais (et les éventuels séjours en France)."
        )

    if any(m in q for m in ("scolarité", "scolarite", "activité", "activite", "cv", "parcours", "lycée", "lycee", "releve", "relevé", "diplome", "diplôme")):
        reponses.append(
            "Dossier de scolarité et activités obligatoires (Section 4 — Onglet 2 du Guide Septembre 2026) :\n"
            "  • Téléverser le Curriculum Vitæ (JPG, PNG ou PDF, max 10 Mo).\n"
            "  • La section 'Parcours scolaire et professionnel' doit comporter AU MOINS 2 ACTIVITÉS :\n"
            "    - Candidature en Bac+1 : saisir les années de lycée jusqu'au baccalauréat.\n"
            "    - Candidature en Bac+2 et plus : saisir du baccalauréat jusqu'à la dernière année d'études supérieures.\n"
            "  • Types d'activités disponibles : 'Une année de lycée', 'Un bac ou équivalent', 'Un concours', 'Un diplôme d'études supérieures', 'Une année d'études supérieures', 'Une autre activité' (avec justificatifs et commentaire jusqu'à 1 000 caractères)."
        )

    if any(m in q for m in ("pré-consulaire", "pre-consulaire", "preconsulaire", "accepté", "accepte", "papier", "échange", "echange", "visa", "attestation")):
        reponses.append(
            "Procédure 'Mon dossier pré-consulaire' (Section 6 du Guide Septembre 2026) :\n"
            "  • Pour une admission via Études en France : ouvrir 'Mon projet d'étude' -> 'Modifier' -> sélectionner l'unique formation acceptée.\n"
            "  • Pour une acceptation papier hors Études en France ou un programme d'échange : cliquer sur '+ Ajouter un projet d'étude' et suivre les 4 étapes (1. Type de projet -> 2. Type d'acceptation -> 3. Détails et dates de la formation -> 4. Motivations 4 000 car. + copie de l'acceptation papier).\n"
            "  • Après validation par Campus France, télécharger l'Attestation d'acceptation (identifiant DZXX-XXXXX) pour déposer la demande de visa sur France-Visas et au centre CAPAGO (-50 % sur les frais de visa)."
        )

    if any(m in q for m in ("antenne", "contact", "alger", "oran", "constantine", "annaba", "tlemcen", "entretien", "rendez-vous", "rdv")):
        reponses.append(
            "Antennes Espace Campus France Algérie et Entretien :\n"
            "  • L'antenne de rattachement est déterminée automatiquement par l'adresse et le numéro de téléphone saisis dans 'Coordonnées' :\n"
            "    - Alger : ecf.alger@if-algerie.com\n"
            "    - Annaba : ecf.annaba@if-algerie.com\n"
            "    - Constantine : ecf.constantine@if-algerie.com\n"
            "    - Oran : ecf.oran@if-algerie.com\n"
            "    - Tlemcen : ecf.tlemcen@if-algerie.com\n"
            "  • Une fois le dossier 'DÉCLARÉ COMPLET', prendre rendez-vous dans l'onglet 'Mes rendez-vous' et télécharger la Convocation."
        )

    if any(m in q for m in ("compte", "inscri", "connect", "bloqué", "bloque", "mot de passe", "tentative", "photo", "passeport")):
        reponses.append(
            "Création de compte, Connexion et Pièces d'identité (Sections 3 & 4 du Guide Septembre 2026) :\n"
            "  • Inscription sur https://etudesenfrance.diplomatie.gouv.fr/ via le bouton 'S'inscrire' (rattachement : Espace Campus France Algérie, lien d'activation valable 48h).\n"
            "  • Attention à la connexion : le compte est bloqué pendant 30 minutes après 5 tentatives de mot de passe infructueuses.\n"
            "  • Photo d'identité obligatoire au format passeport (JPG, PNG ou PDF, max 10 Mo) et copie du passeport valide."
        )

    return reponses
