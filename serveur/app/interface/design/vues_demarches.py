"""Écrans « Démarches » (Campus France, IRCC, procédures) et « Validation et abonnement ».

Gabarits HTML seuls : la logique est dans les modules `js_*`. Les identifiants et les attributs
`onclick` sont consommés par ce JavaScript et par les tests : ne pas les renommer.
Les jetons [[i:nom]] sont remplacés par des icônes SVG à l'assemblage.
"""

from __future__ import annotations

_BARRE_NAV_CF = """
            <div class="barre-chrome-direct">
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('{D}', 'retour')" title="Page précédente" aria-label="Page précédente">[[i:retour]]</button>
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('{D}', 'suivant')" title="Page suivante" aria-label="Page suivante">[[i:suivant]]</button>
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('{D}', 'actualiser')" title="Actualiser la page" aria-label="Actualiser la page">[[i:actualiser]]</button>
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('{D}', 'scroll_haut')" title="Remonter" aria-label="Remonter dans la page">[[i:haut]]</button>
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('{D}', 'scroll_bas')" title="Descendre" aria-label="Descendre dans la page">[[i:bas]]</button>
              <input id="{P}-url-live" class="url-live-input" type="text" value="{U}" placeholder="Adresse à ouvrir" aria-label="Adresse du portail" />
              <button class="btn-nav-mini" type="button" onclick="naviguerUrlDirecte('{D}')">Aller</button>
              <button class="btn-nav-mini" type="button" onclick="basculerModeVueDirecte('{D}')" id="btn-mode-vue-{P}">Vue : contrôle DOM et fenêtre</button>
            </div>"""

_CADRE_NAVIGATEUR = """
          <div class="cadre-navigateur-direct">{BARRE}
            <div id="{P}-conteneur-iframe" class="cache">
              <iframe id="{P}-iframe-direct" class="iframe-navigateur-direct" src="{S}" title="{T}"></iframe>
            </div>
            <div id="{P}-panneau-dom-live" class="corps-navigateur-direct">
              <div class="entete-live">
                <div>
                  <strong id="{P}-titre-page-live">{TL}</strong>
                  <div class="aide">Agissez en temps réel sur les champs et boutons de la page ouverte dans votre navigateur.</div>
                </div>
                <button class="btn btn-contour btn-sm" type="button" style="margin:0;" onclick="synchroniserEtatNavigateurDirect('{D}')">[[i:actualiser]]Synchroniser</button>
              </div>
              <div id="{P}-elements-dom-live">
                <p class="aide">{AIDE}</p>
              </div>
            </div>
          </div>"""


def _cadre(prefixe: str, demarche: str, url: str, src: str, titre: str, titre_live: str, aide: str) -> str:
    barre = (
        _BARRE_NAV_CF.replace("{D}", demarche).replace("{P}", prefixe).replace("{U}", url)
    )
    return (
        _CADRE_NAVIGATEUR.replace("{BARRE}", barre)
        .replace("{D}", demarche)
        .replace("{P}", prefixe)
        .replace("{S}", src)
        .replace("{T}", titre)
        .replace("{TL}", titre_live)
        .replace("{AIDE}", aide)
    )


_CADRE_CF = _cadre(
    "cf", "campus_france", "https://etudesenfrance.diplomatie.gouv.fr/", "/demo/campus-france",
    "Portail interactif Études en France", "Contrôleur de page : Études en France",
    "Cliquez sur « 1. Ouvrir le site » ou donnez une consigne à droite (par exemple « remplis mon identité ») pour voir et manipuler les éléments de la page.",
)
_CADRE_IRCC = _cadre(
    "ircc", "ircc_permis_etudes", "https://portal-portail.apps.cic.gc.ca/signin?lang=fr", "/demo/ircc",
    "Portail interactif IRCC Canada", "Contrôleur de page : portail IRCC Canada",
    "Cliquez sur « 1. Ouvrir le portail IRCC » ou donnez une consigne à droite pour inspecter et remplir les champs.",
)

HTML_CAMPUS_FRANCE = (
    """
    <!-- Campus France -->
    <section id="vue-campus-france" class="vue-ecran cache">
      <header class="page-entete">
        <div>
          <h2>Campus France — Études en France</h2>
          <p class="lead">Préparez les vœux et les lettres de motivation, puis laissez le co-pilote pré-remplir le portail. Il s'arrête toujours avant la certification et l'envoi.</p>
        </div>
        <div class="page-actions">
          <button class="btn btn-secondaire" type="button" onclick="executerActionDomRapide('campus_france', 'focus_fenetre')">[[i:moniteur]]Fenêtre du navigateur au premier plan</button>
          <button id="btn-creer-tache-cf" class="btn btn-secondaire" type="button">Suivi de la tâche</button>
        </div>
      </header>

      <div class="carte" id="carte-voeux">
        <h3>Vœux de formation et lettres de motivation (7 maximum)</h3>
        <p class="aide">Dossier actif : <strong id="voeux-candidat-actif">Aucun</strong>. Chaque lettre est rédigée en brouillon, relue par vous, puis validée. Seuls les vœux validés peuvent être ajoutés au panier.</p>

        <details class="guide-bloc" open>
          <summary>Faits du parcours utilisés pour rédiger les lettres (aucune identité n'est transmise à l'IA)</summary>
          <div class="grille-form">
            <label>Parcours (une ligne par étape)
              <textarea id="faits-parcours" rows="4" placeholder="Ex : 2023-2025 : Master Linguistique et didactique, Université de Béjaïa, moyenne 13,16/20"></textarea>
            </label>
            <label>Points forts vérifiables (une ligne chacun)
              <textarea id="faits-points" rows="4" placeholder="Ex : Mémoire de master noté 16/20"></textarea>
            </label>
            <label>Langues et certificats (une ligne chacun)
              <textarea id="faits-langues" rows="3" placeholder="Ex : Anglais 17/20 en M1 ; TCF B2 (si disponible)"></textarea>
            </label>
            <label>Projet professionnel ou de recherche
              <textarea id="faits-projet" rows="3" placeholder="Ce que le candidat veut faire après la formation"></textarea>
            </label>
          </div>
          <p class="aide" style="margin:8px 0 0;">N'écrivez ici ni nom, ni date de naissance, ni numéro de passeport, ni e-mail, ni téléphone. Ce que vous ne renseignez pas apparaît comme « À COMPLÉTER » dans la lettre.</p>
        </details>

        <h4>Ajouter un vœu</h4>
        <div class="grille-form">
          <label>Intitulé exact de la formation
            <input id="voeu-intitule" type="text" placeholder="Ex : Master Traitement automatique des langues" />
          </label>
          <label>Établissement
            <input id="voeu-etablissement" type="text" placeholder="Ex : Université de Lorraine" />
          </label>
          <label>Niveau
            <select id="voeu-niveau">
              <option>Master 1</option><option>Master 2</option><option>Licence 3</option><option>Licence 2</option>
              <option>Licence 1</option><option>Ingénieur</option><option>Autre</option>
            </select>
          </label>
          <label>Voie
            <select id="voeu-voie">
              <option value="hors_dap" selected>Hors DAP (L2, L3, Master, Ingénieur…)</option>
              <option value="dap_blanche">DAP Blanche (Licence 1)</option>
              <option value="dap_jaune">DAP Jaune (Architecture)</option>
            </select>
          </label>
          <label>Pourquoi cette formation ? <span class="aide">(facultatif, personnalise la lettre)</span>
            <input id="voeu-justification" type="text" placeholder="Ex : cours de TAL pour langues peu dotées" />
          </label>
        </div>
        <div class="pile-actions" style="margin-bottom:16px;">
          <button id="btn-ajouter-voeu" class="btn btn-primaire" type="button">[[i:plus]]Ajouter ce vœu</button>
          <button id="btn-actualiser-voeux" class="btn btn-secondaire" type="button">Actualiser la liste</button>
        </div>

        <div id="liste-voeux"><div class="panneau-texte">Choisissez un dossier dans « Étudiants et fiches » pour gérer ses vœux.</div></div>

        <div class="pile-actions">
          <button id="btn-panier-voeux" class="btn btn-contour" type="button" onclick="lancerActionNavigateur('campus_france', 'ajouter_voeux_panier')">Ajouter les vœux validés au panier (co-pilote)</button>
        </div>
      </div>

      <div class="carte">
        <div class="carte-entete">
          <h3><span class="point-vert-pulsant"></span>Co-pilote navigateur</h3>
          <span class="badge badge-ok">Temps réel</span>
        </div>
        <p class="aide">Pilotage direct de votre navigateur, sans capture d'écran : barre latérale IA dans la page, curseur animé et consignes en langage naturel.</p>

        <div class="grille-form">
          <label>Portail cible dans le navigateur
            <select id="cf-cible-navigateur" onchange="changerCibleNavigateurDirect('campus_france')">
              <option value="campus_france_officiel" selected>Site officiel Études en France (etudesenfrance.diplomatie.gouv.fr)</option>
              <option value="demo_campus_france">Portail interactif Études en France (mode direct intégré)</option>
              <option value="campus_france_algerie">Site Campus France Algérie (algerie.campusfrance.org)</option>
              <option value="paiement_ifa_algerie">Portail de paiement IFA Algérie (paiement.if-algerie.com)</option>
            </select>
          </label>
          <label class="case" style="align-self:end;">
            <input id="cf-fenetre-visible" type="checkbox" checked />
            <span>Piloter ma vraie fenêtre Chrome, Edge ou Chromium (avec barre latérale du co-pilote)</span>
          </label>
        </div>

        <p class="titre-mini">Étapes en un clic (guide Études en France, septembre 2026)</p>
        <div class="etapes-actions">
          <button class="btn btn-secondaire" type="button" onclick="lancerActionNavigateur('campus_france', 'ouvrir_portail')">1. Ouvrir le site</button>
          <button class="btn btn-primaire" type="button" onclick="lancerActionNavigateur('campus_france', 'preremplissage_complet')">2. Tout remplir, joindre les pièces et s'arrêter (règle 1)</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('campus_france', 'inscription_compte')">3. S'inscrire (créer le compte)</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('campus_france', 'connexion_compte')">3. Se connecter (règle 3)</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('campus_france', 'preremplir_espace_etudiant')">4. Identité, passeport et antenne ECF</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('campus_france', 'preremplir_scolarite_et_langues')">4. Scolarité (2 activités) et français &gt; 1000 h</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('campus_france', 'preremplir_panier_formations_et_motivations')">5. Panier (7 max.) et motivation (4 000 car.)</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('campus_france', 'preparer_paiement_et_rdv')">5. Paiement (20 000 DZD) et rendez-vous</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('campus_france', 'preremplir_dossier_preconsulaire')">6. Dossier pré-consulaire (4 étapes)</button>
        </div>

        <div class="workspace-cowork">"""
    + _CADRE_CF
    + """

          <div class="panneau-copilote-chat">
            <div class="entete-chat"><strong>Assistant co-pilote</strong><span class="aide">Langage naturel et voix</span></div>
            <div>
              <span class="aide">Exemples de demandes (cliquez pour les envoyer) :</span>
              <div class="chips">
                <button class="puce-cmd" type="button" onclick="envoyerConsigneRapideCopilote('campus_france', 'Ouvre le vrai site Études en France dans mon navigateur')">Ouvrir le vrai site</button>
                <button class="puce-cmd" type="button" onclick="envoyerConsigneRapideCopilote('campus_france', 'Clique sur S’inscrire et pré-remplis mon compte')">Aller sur « S'inscrire »</button>
                <button class="puce-cmd" type="button" onclick="envoyerConsigneRapideCopilote('campus_france', 'Analyse cette page et explique-moi ce qu’il faut faire')">Analyser cette page</button>
                <button class="puce-cmd" type="button" onclick="envoyerConsigneRapideCopilote('campus_france', 'Mets Oran comme ville et Université Paris-Saclay comme établissement')">Changer ville et université</button>
                <button class="puce-cmd" type="button" onclick="envoyerConsigneRapideCopilote('campus_france', 'Remplis mes motivations pour ma formation')">Rédiger les motivations</button>
                <button class="puce-cmd" type="button" onclick="envoyerConsigneRapideCopilote('campus_france', 'Quels sont les frais en DZD et les dates limites 2026-2027 ?')">Frais et dates limites</button>
              </div>
            </div>
            <div id="fil-copilote-cf" class="fil-copilote" aria-live="polite">
              <div class="bulle-copilote-ia">
                <strong>Co-pilote prêt.</strong> Dites-moi en français ce que je dois faire dans votre navigateur (par exemple <em>« remplis mon identité »</em>, <em>« clique sur Se connecter »</em>, <em>« descends en bas de la page »</em> ou <em>« remplis tout sans soumettre »</em>).
              </div>
            </div>
            <div class="barre-saisie">
              <input id="cf-instruction-agent" type="text" value="Pré-remplir tout le dossier Études en France du candidat (identité, passeport, scolarité, langues, panier de formations et motivation) et enregistrer le brouillon" placeholder="Parlez naturellement à l'agent" aria-label="Consigne pour le co-pilote" />
              <button class="btn btn-secondaire btn-icone" type="button" style="margin:0;" onclick="demarrerDicteeVocale('campus_france')" title="Dicter la consigne à la voix" aria-label="Dicter la consigne à la voix">[[i:micro]]</button>
              <button id="btn-piloter-cf-instruction" class="btn btn-primaire" type="button" style="margin:0;">Exécuter</button>
            </div>
            <div id="zone-retour-cf" class="panneau-texte">
              Choisissez un dossier, puis donnez une consigne ci-dessus ou lancez une étape en un clic.
            </div>
          </div>
        </div>
      </div>

      <div class="carte">
        <h3>Guide officiel « Études en France — septembre 2026 » (Campus France Algérie)</h3>
        <details class="guide-bloc" open>
          <summary>Calendrier de la session 2026–2027 et frais de dossier (DZD)</summary>
          <ul class="liste-propre">
            <li><strong>Hors DAP (L2, L3, Master 1 et 2, écoles d'ingénieurs et de commerce) :</strong> ouverture le <strong>1er octobre 2026</strong> ; date limite de dépôt et de paiement le <strong>30 novembre 2026</strong> ; entretiens jusqu'au <strong>15 mars 2027</strong> ; choix définitif avant le <strong>31 mai 2027</strong>.</li>
            <li><strong>DAP (L1 université, écoles d'architecture ENSA, BUT, licence professionnelle) :</strong> ouverture le <strong>1er octobre 2026</strong> ; date limite le <strong>15 décembre 2026</strong> ; entretiens jusqu'au <strong>15 mars 2027</strong> ; choix définitif avant le <strong>31 mai 2027</strong>.</li>
            <li><strong>CPGE, BTS, DCG :</strong> à partir de <strong>janvier 2027</strong> sur Parcoursup.</li>
            <li><strong>Dossier pré-consulaire (« Je suis accepté » ou établissements privés non connectés) :</strong> dès la réception de l'acceptation, au minimum <strong>45 jours avant la rentrée</strong>.</li>
            <li><strong>Frais de dossier Algérie :</strong> plein tarif <strong>20 000 DZD</strong> ; demi-tarif <strong>10 000 DZD</strong> (bac français depuis moins de 4 ans et candidat de moins de 22 ans, ou acceptation Campus Art) ; <strong>gratuité</strong> pour les boursiers du gouvernement français, les bacheliers du LIAD de l'année en cours et les agents de l'Institut français d'Algérie. Paiement sur <code>paiement.if-algerie.com</code>.</li>
            <li><strong>5 antennes Espace Campus France Algérie :</strong> Alger (<code>ecf.alger@if-algerie.com</code>), Annaba (<code>ecf.annaba@if-algerie.com</code>), Constantine (<code>ecf.constantine@if-algerie.com</code>), Oran (<code>ecf.oran@if-algerie.com</code>), Tlemcen (<code>ecf.tlemcen@if-algerie.com</code>).</li>
          </ul>
        </details>
        <details class="guide-bloc">
          <summary>Mon compte et mon espace étudiant (identité, scolarité, compétences linguistiques)</summary>
          <ul class="liste-propre">
            <li><strong>Inscription et connexion :</strong> bouton « S'inscrire » sur <code>https://etudesenfrance.diplomatie.gouv.fr/</code> (Espace Campus France Algérie, activation par e-mail sous 48 h). Le compte est bloqué <strong>30 minutes après 5 mots de passe erronés</strong>.</li>
            <li><strong>Informations personnelles :</strong> identité, photo d'identité au format passeport (JPG, PNG ou PDF, 10 Mo maximum), passeport valide (numéro, date limite, copie), coordonnées (l'adresse et le téléphone déterminent l'antenne ECF) et statut particulier (« Je ne suis concerné par aucun de ces statuts particuliers »).</li>
            <li><strong>Dossier de scolarité :</strong> CV obligatoire et <strong>au moins 2 activités</strong> dans « Parcours scolaire et professionnel » (du lycée au bac pour Bac+1 ; du bac à la dernière année d'études supérieures pour Bac+2 et plus ; commentaire limité à 1 000 caractères).</li>
            <li><strong>Compétences linguistiques :</strong> pour un baccalauréat algérien ou non européen suivi en français, choisir « Oui », volume « Plus de 1000 heures », durée « 4 ans et plus », niveau atteint « Avancé ». Ajouter le test TCF ou DELF/DALF avec « + Ajouter un test », puis renseigner le niveau d'anglais.</li>
          </ul>
        </details>
        <details class="guide-bloc">
          <summary>Dossier de candidature (panier de 7 choix maximum) et dossier pré-consulaire</summary>
          <ul class="liste-propre">
            <li><strong>Règles du panier (7 formations maximum) :</strong> DAP Blanche (L1 : jusqu'à 3 choix), DAP Jaune (architecture ENSA : 2 choix obligatoires et portfolio), Hors DAP (L2, L3, M1, M2, ingénieur, commerce : jusqu'à 7 choix). Vérifier le badge « OUVERT À LA CANDIDATURE ».</li>
            <li><strong>Texte de motivation :</strong> obligatoire pour chaque formation du panier (jusqu'à <strong>4 000 caractères</strong>), puis « Enregistrer ».</li>
            <li><strong>Envoi (règle 1) :</strong> l'agent s'arrête toujours avant les 2 cases de certification et le bouton « Soumettre mon dossier de candidature ».</li>
            <li><strong>Dossier pré-consulaire (« Je suis accepté ») :</strong> sélection de la formation acceptée via Études en France, ou ajout d'une acceptation papier ou d'un programme d'échange en <strong>4 étapes</strong>. Il donne l'attestation d'acceptation (identifiant <code>DZXX-XXXXX</code>) et <strong>-50 % sur les frais de visa long séjour</strong> chez CAPAGO.</li>
          </ul>
        </details>
      </div>
    </section>
"""
)

HTML_IRCC = (
    """
    <!-- IRCC Canada -->
    <section id="vue-ircc" class="vue-ecran cache">
      <header class="page-entete">
        <div>
          <h2>IRCC Canada — Permis d'études</h2>
          <p class="lead">Le co-pilote contrôle le seuil financier (<strong>20 635 $ CAD</strong>, soit environ <strong>14 500 EUR</strong>), la LAP/PAL ou le CAQ et l'admission EED/DLI. Il s'arrête avant la signature et la transmission (règle 1).</p>
        </div>
        <div class="page-actions">
          <button class="btn btn-secondaire" type="button" onclick="executerActionDomRapide('ircc_permis_etudes', 'focus_fenetre')">[[i:moniteur]]Fenêtre du navigateur au premier plan</button>
          <button id="btn-creer-tache-ircc" class="btn btn-secondaire" type="button">Suivi de la tâche</button>
        </div>
      </header>

      <div class="carte">
        <div class="carte-entete">
          <h3><span class="point-vert-pulsant"></span>Co-pilote navigateur</h3>
          <span class="badge badge-ok">Temps réel</span>
        </div>
        <div class="grille-form">
          <label>Portail cible dans le navigateur
            <select id="ircc-cible-navigateur" onchange="changerCibleNavigateurDirect('ircc_permis_etudes')">
              <option value="ircc_officiel" selected>Portail officiel IRCC Canada (portal-portail.apps.cic.gc.ca)</option>
              <option value="demo_ircc">Portail interactif IRCC (mode direct intégré)</option>
              <option value="ircc_canada_info">Page officielle Permis d'études sur Canada.ca</option>
            </select>
          </label>
          <label class="case" style="align-self:end;">
            <input id="ircc-fenetre-visible" type="checkbox" checked />
            <span>Piloter ma vraie fenêtre Chrome, Edge ou Chromium (avec barre latérale du co-pilote)</span>
          </label>
        </div>

        <p class="titre-mini">Étapes en un clic</p>
        <div class="etapes-actions">
          <button class="btn btn-secondaire" type="button" onclick="lancerActionNavigateur('ircc_permis_etudes', 'ouvrir_portail')">1. Ouvrir le portail IRCC</button>
          <button class="btn btn-primaire" type="button" onclick="lancerActionNavigateur('ircc_permis_etudes', 'preremplissage_complet')">2. Tout pré-remplir, joindre les pièces et s'arrêter (règle 1)</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('ircc_permis_etudes', 'preremplir_identite_ircc')">3. Identité et passeport</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('ircc_permis_etudes', 'preremplir_dli_fonds_ircc')">4. Établissement DLI et fonds (20 635 CAD)</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('ircc_permis_etudes', 'televerser_pieces_ircc')">5. Téléverser les 6 pièces (PAL/CAQ, IMM 5645…)</button>
        </div>

        <div class="workspace-cowork">"""
    + _CADRE_IRCC
    + """

          <div class="panneau-copilote-chat">
            <div class="entete-chat"><strong>Assistant co-pilote IRCC</strong><span class="aide">Langage naturel et voix</span></div>
            <div>
              <span class="aide">Exemples de demandes :</span>
              <div class="chips">
                <button class="puce-cmd" type="button" onclick="envoyerConsigneRapideCopilote('ircc_permis_etudes', 'Ouvre le vrai portail officiel IRCC Canada')">Ouvrir le vrai portail</button>
                <button class="puce-cmd" type="button" onclick="envoyerConsigneRapideCopilote('ircc_permis_etudes', 'Analyse cette page IRCC et dis-moi quoi remplir')">Analyser la page</button>
                <button class="puce-cmd" type="button" onclick="envoyerConsigneRapideCopilote('ircc_permis_etudes', 'Mets Université Laval comme établissement et 21000 euros comme fonds')">Changer DLI et fonds</button>
                <button class="puce-cmd" type="button" onclick="envoyerConsigneRapideCopilote('ircc_permis_etudes', 'Remplis tout le formulaire IRCC et téléverse les pièces sans transmettre')">Tout remplir sans transmettre</button>
              </div>
            </div>
            <div id="fil-copilote-ircc" class="fil-copilote" aria-live="polite">
              <div class="bulle-copilote-ia">
                <strong>Co-pilote IRCC prêt.</strong> Demandez-moi une action en français (par exemple <em>« remplis mon identité et le DLI »</em>, <em>« mets 19000 euros comme fonds »</em> ou <em>« quelles sont les règles PAL/CAQ ? »</em>).
              </div>
            </div>
            <div class="barre-saisie">
              <input id="ircc-instruction-agent" type="text" value="Pré-remplir toute la demande de permis d'études IRCC (identité, passeport, établissement DLI, ressources financières et pièces justificatives) et sauvegarder le brouillon" placeholder="Parlez naturellement à l'agent IRCC" aria-label="Consigne pour le co-pilote IRCC" />
              <button class="btn btn-secondaire btn-icone" type="button" style="margin:0;" onclick="demarrerDicteeVocale('ircc_permis_etudes')" title="Dicter la consigne à la voix" aria-label="Dicter la consigne à la voix">[[i:micro]]</button>
              <button id="btn-piloter-ircc-instruction" class="btn btn-primaire" type="button" style="margin:0;">Exécuter</button>
            </div>
            <div id="zone-retour-ircc" class="panneau-texte">
              Choisissez un dossier, puis donnez une consigne ci-dessus ou lancez une étape en un clic.
            </div>
          </div>
        </div>
      </div>
    </section>
"""
)

HTML_VALIDATION = """
    <!-- Centre de validation -->
    <section id="vue-validation-humaine" class="vue-ecran cache">
      <header class="page-entete">
        <div>
          <h2>Centre de validation</h2>
          <p class="lead">Aucune demande officielle n'est jamais envoyée par l'agent. Contrôlez la capture et le récapitulatif de chaque dossier avant de valider.</p>
        </div>
        <div class="page-actions">
          <button id="btn-rafraichir-validations" class="btn btn-secondaire" type="button">[[i:actualiser]]Actualiser</button>
        </div>
      </header>
      <!-- zone:lien-recaps -->
      <div id="liste-centre-validation" class="pile">Chargement des dossiers...</div>
    </section>
"""

HTML_AUDIT = """
    <!-- Journal d'audit -->
    <section id="vue-historique-erreurs" class="vue-ecran cache">
      <header class="page-entete">
        <div>
          <h2>Journal d'audit</h2>
          <p class="lead">Historique immuable des opérations du bureau. Il ne contient aucune donnée personnelle (règle 5).</p>
        </div>
        <div class="page-actions">
          <button id="btn-rafraichir-audit" class="btn btn-secondaire" type="button">[[i:actualiser]]Actualiser</button>
        </div>
      </header>
      <div class="table-wrap">
        <table id="table-audit">
          <thead><tr><th>Date et heure (UTC)</th><th>Opération</th><th>Résultat</th><th>Ressource</th><th>Résumé</th></tr></thead>
          <tbody><tr><td colspan="5" class="etat-vide">Cliquez sur « Actualiser » pour charger le journal.</td></tr></tbody>
        </table>
      </div>
    </section>
"""

HTML_PARAMETRES = """
    <!-- Abonnement et sauvegardes -->
    <section id="vue-parametres" class="vue-ecran cache">
      <header class="page-entete">
        <div>
          <h2>Abonnement et sauvegardes</h2>
          <p class="lead">Votre forfait, l'état des portails, les postes agents locaux et les sauvegardes chiffrées du bureau.</p>
        </div>
      </header>
      <div class="accueil-grille" style="align-items:start;">
        <div class="carte">
          <h3>Sauvegardes et abonnement</h3>
          <div class="pile-actions" style="margin:0 0 16px;">
            <button id="btn-voir-abonnement" class="btn btn-primaire" type="button">Afficher mon abonnement et l'état des portails</button>
            <button id="btn-creer-sauvegarde" class="btn btn-secondaire" type="button">Créer une sauvegarde chiffrée (.be.enc)</button>
          </div>
          <div id="zone-sauvegardes-abo" class="panneau-texte">Choisissez une action ci-dessus : la sauvegarde est chiffrée en AES-256-GCM, l'abonnement affiche votre quota et l'homologation des portails (règles 6 et 7).</div>
        </div>
        <div class="carte">
          <h3>Enrôler un poste agent local</h3>
          <p class="aide">Chaque poste Windows du bureau qui exécute l'agent reçoit sa propre clé d'accès.</p>
          <label>Nom du poste Windows <input id="nom-machine-agent" type="text" value="PC-BUREAU-ALGER-01" /></label>
          <div class="pile-actions"><button id="btn-enroler-agent" class="btn btn-primaire" type="button">Enrôler ce poste et générer sa clé</button></div>
          <div id="zone-jeton-agent" class="panneau-texte cache" style="margin-top:12px;"></div>
        </div>
      </div>
    </section>
"""

HTML_PROCEDURES = """
    <!-- Procédures du bureau -->
    <section id="vue-procedures" class="vue-ecran cache">
      <header class="page-entete">
        <div>
          <h2>Procédures du bureau</h2>
          <p class="lead">Les procédures de base (Campus France, IRCC…) sont communes. Ajoutez-en ou personnalisez-les : vos changements ne concernent que votre bureau et s'appliquent aussitôt. Modification réservée aux administrateurs.</p>
        </div>
        <div class="page-actions">
          <button id="btn-nouvelle-procedure" class="btn btn-primaire cache" type="button">[[i:plus]]Nouvelle procédure</button>
        </div>
      </header>

      <div id="ia-statut-procedures" class="ia-statut">Assistant IA : état en cours de vérification...</div>

      <div id="carte-generation-ia" class="carte cache">
        <h3>Créer une procédure à partir d'un texte officiel (IA)</h3>
        <p class="aide">Collez le guide ou la page officielle de la démarche (de 80 à 30 000 caractères). L'assistant prépare un brouillon : rien n'est enregistré tant que vous n'avez pas relu l'éditeur et cliqué sur « Enregistrer la procédure ».</p>
        <textarea id="ia-texte-source" class="ia-texte-source" placeholder="Collez ici le texte officiel de la démarche" aria-label="Texte officiel de la démarche"></textarea>
        <div id="ia-compteur-texte" class="ia-compteur">0 / 30 000 caractères (minimum 80)</div>
        <button id="btn-generer-procedure-ia" class="btn btn-primaire" type="button">Générer un brouillon</button>
        <div id="zone-retour-generation-ia" class="panneau-texte cache" style="margin-top:12px;"></div>
      </div>

      <div class="carte">
        <div class="carte-entete">
          <h3>Procédures disponibles</h3>
          <button id="btn-rafraichir-procedures" class="btn btn-secondaire btn-sm" type="button" style="margin:0;">[[i:actualiser]]Actualiser</button>
        </div>
        <div class="table-wrap">
          <table id="table-procedures">
            <thead><tr><th>Code</th><th>Libellé</th><th>Origine</th><th>Version</th><th>Actions</th></tr></thead>
            <tbody><tr><td colspan="5" class="etat-vide">Chargement...</td></tr></tbody>
          </table>
        </div>
      </div>

      <div id="carte-editeur-procedure" class="carte cache">
        <h3 id="titre-editeur-procedure">Éditeur de procédure</h3>
        <div id="bloc-ia-editeur" class="banniere-regle cache">
          <strong>Brouillon généré par l'IA : relisez chaque point avant d'enregistrer.</strong>
          <div id="titre-avertissements-ia" style="margin-top:8px;">Points signalés par l'assistant :</div>
          <ul id="liste-avertissements-ia" class="liste-propre"></ul>
        </div>
        <div id="encart-champs-avances" class="panneau-texte cache" style="margin-bottom:16px;">
          <strong>Champs avancés présents dans cette procédure</strong>
          <div class="aide" style="margin:4px 0;">Lecture seule pour l'instant : l'éditeur ne sait pas encore les modifier, mais ils sont conservés tels quels à l'enregistrement.</div>
          <ul id="liste-champs-avances" class="liste-propre"></ul>
        </div>
        <fieldset id="fs-editeur">
          <div class="grille-form">
            <label>Code technique <span class="aide">(minuscules, chiffres, tirets bas)</span>
              <input id="proc-code" type="text" placeholder="ex : visa_touristique" />
            </label>
            <label>Libellé affiché
              <input id="proc-libelle" type="text" placeholder="ex : Visa touristique Schengen" />
            </label>
            <label>Seuil de fonds recommandé (EUR) <span class="aide">(facultatif)</span>
              <input id="proc-seuil" type="number" min="0" />
            </label>
          </div>
          <label style="margin-top:16px;">Description <span class="aide">(facultatif)</span>
            <input id="proc-description" type="text" />
          </label>

          <h4>Informations du candidat obligatoires avant tout pré-remplissage</h4>
          <div id="proc-champs" class="liste-cases"></div>

          <h4>Pièces requises</h4>
          <datalist id="liste-types-pieces"></datalist>
          <div id="proc-pieces"></div>
          <button id="btn-ajouter-piece" class="btn btn-contour btn-sm" type="button">[[i:plus]]Ajouter une pièce</button>

          <h4>Étapes de la tâche <span class="aide">(facultatif)</span></h4>
          <p class="aide">Laissez vide pour garder les 4 étapes standard : vérification, session portail, pré-remplissage, arrêt avant validation humaine.</p>
          <div id="proc-etapes"></div>
          <button id="btn-ajouter-etape" class="btn btn-contour btn-sm" type="button">[[i:plus]]Ajouter une étape</button>

          <h4>Veille réglementaire (points à connaître)</h4>
          <div id="proc-veille"></div>
          <button id="btn-ajouter-veille" class="btn btn-contour btn-sm" type="button">[[i:plus]]Ajouter un point de veille</button>
        </fieldset>
        <div class="pile-actions" style="margin-top:24px;">
          <button id="btn-enregistrer-procedure" class="btn btn-primaire" type="button">Enregistrer la procédure</button>
          <button id="btn-fermer-editeur-procedure" class="btn btn-secondaire" type="button">Fermer l'éditeur</button>
        </div>
        <div id="zone-retour-procedure" class="panneau-texte cache" style="margin-top:12px;"></div>
      </div>
    </section>
"""
