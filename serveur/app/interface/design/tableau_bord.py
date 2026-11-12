"""Écran d'accueil : ce qui demande une action humaine d'abord, puis l'état du bureau.

Alimenté par les routes existantes (candidats, centre de validation, récapitulatifs, agents) via
`rafraichirTableauDeBord` qui appelle `accueilAfficher`. Tout l'affichage passe par des nœuds DOM
et `textContent` : aucune donnée n'est interprétée comme du HTML. Aucun antislash.
"""

from __future__ import annotations

HTML_ACCUEIL = """
    <!-- Tableau de bord : actions humaines en tête -->
    <section id="vue-tableau-bord" class="vue-ecran">
      <header class="page-entete">
        <div>
          <h2>Tableau de bord</h2>
          <p class="lead">Ce qui attend une décision de votre part, puis l'état du bureau.</p>
        </div>
        <div class="page-actions">
          <button class="btn btn-primaire" type="button" onclick="allerVersVue('vue-etudiants'); document.getElementById('carte-nouvel-etudiant').open = true;">[[i:plus]]Nouvel étudiant</button>
        </div>
      </header>

      <div class="accueil-grille">
        <section class="carte" aria-labelledby="titre-a-traiter">
          <div class="carte-entete">
            <h3 id="titre-a-traiter">À traiter maintenant</h3>
            <span id="accueil-total-actions" class="badge">0</span>
          </div>
          <ul id="accueil-actions" class="liste-actions">
            <li class="etat-vide">Chargement de vos dossiers...</li>
          </ul>
        </section>

        <section class="carte" aria-labelledby="titre-echeances">
          <div class="carte-entete">
            <h3 id="titre-echeances">Échéances proches</h3>
          </div>
          <ul id="accueil-echeances" class="liste-echeances">
            <li class="etat-vide">Chargement...</li>
          </ul>
          <p class="note" style="margin:12px 0 0;">Dates du calendrier Campus France Algérie 2026-2027 et passeports qui expirent dans les 6 mois.</p>
        </section>
      </div>

      <h3 class="titre-section">Vue d'ensemble</h3>
      <div class="grille-stats">
        <div class="stat"><div id="stat-nb-candidats" class="valeur">0</div><div class="libelle">Étudiants actifs</div></div>
        <div class="stat"><div id="stat-nb-a-valider" class="valeur">0</div><div class="libelle">Dossiers prêts à valider</div></div>
        <div class="stat"><div id="stat-nb-suspendues" class="valeur">0</div><div class="libelle">Dossiers en pause (pièce, session ou CAPTCHA)</div></div>
        <div class="stat"><div id="stat-nb-agents" class="valeur">0</div><div class="libelle">Postes agents enrôlés</div></div>
      </div>

      <h3 class="titre-section">Accès rapides</h3>
      <div class="raccourcis">
        <button class="btn btn-secondaire" type="button" onclick="allerVersVue('vue-campus-france')">[[i:globe]]Piloter Campus France</button>
        <button class="btn btn-secondaire" type="button" onclick="allerVersVue('vue-ircc')">[[i:envoi]]Piloter IRCC Canada</button>
        <button class="btn btn-secondaire" type="button" onclick="allerVersVue('vue-conseiller')">[[i:conseiller]]Calculer un score d'acceptation</button>
        <button class="btn btn-secondaire" type="button" onclick="allerVersVue('vue-documents')">[[i:pieces]]Vérifier les pièces manquantes</button>
      </div>
      <p class="titre-mini">Sites officiels et pages de simulation (s'ouvrent dans un nouvel onglet)</p>
      <div class="raccourcis">
        <a class="btn btn-contour btn-sm" href="https://etudesenfrance.diplomatie.gouv.fr/" target="_blank" rel="noopener">Études en France [[i:externe]]</a>
        <a class="btn btn-contour btn-sm" href="https://portal-portail.apps.cic.gc.ca/signin?lang=fr" target="_blank" rel="noopener">Portail IRCC Canada [[i:externe]]</a>
        <a class="btn btn-contour btn-sm" href="/demo/campus-france" target="_blank" rel="noopener">Simulation Études en France [[i:externe]]</a>
        <a class="btn btn-contour btn-sm" href="/demo/ircc" target="_blank" rel="noopener">Simulation IRCC [[i:externe]]</a>
      </div>
    </section>
"""

JS_ACCUEIL = """
    // =======================================================================
    // Accueil : ce qui demande une action humaine, puis les échéances proches.
    // Affichage par nœuds DOM et textContent uniquement (aucune donnée interprétée en HTML).
    // =======================================================================
    const CALENDRIER_CAMPUS_FRANCE = [
      { date: "2026-11-30", libelle: "Campus France : date limite de dépôt et de paiement (hors DAP)" },
      { date: "2026-12-15", libelle: "Campus France : date limite de dépôt et de paiement (DAP)" },
      { date: "2027-03-15", libelle: "Campus France : fin des entretiens" },
      { date: "2027-05-31", libelle: "Campus France : choix définitif des formations" },
    ];
    const SEUIL_PASSEPORT_JOURS = 180;
    const SEUIL_ECHEANCE_CRITIQUE_JOURS = 14;
    const SEUIL_ECHEANCE_ALERTE_JOURS = 45;
    const MAX_LIGNES_ACTIONS = 8;
    const MAX_ECHEANCES = 6;
    const MS_PAR_JOUR = 86400000;
    const MOIS_COURTS_FR = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];

    function accueilNoeud(balise, classe, texte) {
      const n = document.createElement(balise);
      if (classe) n.className = classe;
      if (texte !== undefined) n.textContent = texte;
      return n;
    }

    function accueilJoursAvant(iso) {
      const cible = new Date(String(iso) + "T00:00:00");
      if (isNaN(cible.getTime())) return null;
      const aujourdhui = new Date();
      aujourdhui.setHours(0, 0, 0, 0);
      return Math.round((cible.getTime() - aujourdhui.getTime()) / MS_PAR_JOUR);
    }

    function accueilNomDemarche(code) {
      if (code === "campus_france") return "Campus France";
      if (code === "ircc_permis_etudes") return "IRCC Canada";
      const connue = listeDemarches.find((d) => d.code === code);
      return connue ? connue.libelle : String(code);
    }

    function accueilEtatVide(titre, texte) {
      const li = accueilNoeud("li", "etat-vide");
      li.appendChild(accueilNoeud("strong", "", titre));
      li.appendChild(document.createTextNode(texte));
      return li;
    }

    function accueilLigneAction(classeBadge, texteBadge, titre, detail, libelleBouton, vue) {
      const li = accueilNoeud("li", "ligne-action");
      li.appendChild(accueilNoeud("span", "badge " + classeBadge, texteBadge));
      const texte = accueilNoeud("div", "ligne-texte");
      texte.appendChild(accueilNoeud("strong", "", titre));
      if (detail) texte.appendChild(accueilNoeud("span", "", detail));
      li.appendChild(texte);
      const bouton = accueilNoeud("button", "btn btn-secondaire btn-sm", libelleBouton);
      bouton.type = "button";
      bouton.addEventListener("click", () => allerVersVue(vue));
      li.appendChild(bouton);
      return li;
    }

    function accueilPluriel(n, singulier, pluriel) {
      return n + " " + (n > 1 ? pluriel : singulier);
    }

    function accueilConstruireActions(etat) {
      const lignes = [];
      if (etat.recaps) {
        lignes.push(accueilLigneAction(
          "badge-info", "À valider",
          accueilPluriel(etat.recaps, "récapitulatif attend", "récapitulatifs attendent") + " votre validation",
          "L'agent n'enverra rien tant que vous n'avez pas validé le contenu exact.",
          "Examiner", "vue-recaps-valider"));
      }
      const synthese = etat.validations;
      if (synthese) {
        (synthese.taches_a_valider || []).forEach((t) => {
          lignes.push(accueilLigneAction(
            "badge-info", "Validation en attente",
            accueilNomDemarche(t.code_demarche) + " : " + libelleCandidatParId(t.candidat_id),
            t.message_alerte || "Pré-remplissage terminé, arrêté avant l'envoi officiel.",
            "Contrôler", "vue-validation-humaine"));
        });
        (synthese.taches_suspendues || []).forEach((t) => {
          const actionHumaine = t.motif_suspension === "action_utilisateur_portail";
          lignes.push(accueilLigneAction(
            "badge-warn", actionHumaine ? "CAPTCHA ou code de sécurité" : "En pause",
            accueilNomDemarche(t.code_demarche) + " : " + libelleCandidatParId(t.candidat_id),
            t.message_alerte || (actionHumaine
              ? "Le portail demande une action de votre part."
              : "Des pièces ou des informations sont à compléter."),
            actionHumaine ? "Prendre la main" : "Compléter",
            actionHumaine ? "vue-navigateur-serveur" : "vue-validation-humaine"));
        });
      }
      const sansConsentement = etat.candidats.filter((c) => c.consentement_signe === false).length;
      if (sansConsentement > 0) {
        lignes.push(accueilLigneAction(
          "badge-warn", "Consentement",
          accueilPluriel(sansConsentement, "fiche sans consentement", "fiches sans consentement") + " (loi 18-07)",
          "Recueillez le consentement du candidat avant de traiter son dossier.",
          "Ouvrir les fiches", "vue-etudiants"));
      }
      return lignes;
    }

    function accueilAfficherActions(etat) {
      const liste = document.getElementById("accueil-actions");
      const badge = document.getElementById("accueil-total-actions");
      liste.replaceChildren();
      const connecte = etat.validations !== null || etat.candidats.length > 0 || etat.recaps !== null;
      if (!connecte) {
        badge.className = "badge";
        badge.textContent = "—";
        liste.appendChild(accueilEtatVide("Connectez-vous pour voir vos dossiers.", "Utilisez le menu de gauche pour ouvrir votre session."));
        return;
      }
      const lignes = accueilConstruireActions(etat);
      badge.className = "badge " + (lignes.length > 0 ? "badge-warn" : "badge-ok");
      badge.textContent = lignes.length > 0 ? String(lignes.length) : "À jour";
      if (lignes.length === 0) {
        liste.appendChild(accueilEtatVide("Tout est à jour.", "Aucun dossier n'attend de décision. Ajoutez un étudiant ou lancez une démarche pour avancer."));
        return;
      }
      lignes.slice(0, MAX_LIGNES_ACTIONS).forEach((l) => liste.appendChild(l));
      if (lignes.length > MAX_LIGNES_ACTIONS) {
        const reste = accueilNoeud("li", "note", "Et " + (lignes.length - MAX_LIGNES_ACTIONS) + " autre(s) : ouvrez le centre de validation pour tout voir.");
        liste.appendChild(reste);
      }
    }

    function accueilConstruireEcheances(candidats) {
      const items = CALENDRIER_CAMPUS_FRANCE.map((e) => ({ iso: e.date, libelle: e.libelle, passeport: false }));
      candidats.forEach((c) => {
        if (!c.date_expiration_passeport) return;
        const jours = accueilJoursAvant(c.date_expiration_passeport);
        if (jours === null || jours > SEUIL_PASSEPORT_JOURS) return;
        items.push({
          iso: c.date_expiration_passeport,
          libelle: "Passeport de " + c.nom + " " + c.prenom + (jours < 0 ? " expiré" : " : expiration"),
          passeport: true,
        });
      });
      return items
        .map((i) => Object.assign({}, i, { jours: accueilJoursAvant(i.iso) }))
        .filter((i) => i.jours !== null && (i.jours >= 0 || i.passeport))
        .sort((a, b) => a.jours - b.jours)
        .slice(0, MAX_ECHEANCES);
    }

    function accueilTexteDelai(jours) {
      if (jours < 0) return "Dépassée de " + Math.abs(jours) + " j";
      if (jours === 0) return "Aujourd'hui";
      if (jours === 1) return "Demain";
      return "Dans " + jours + " j";
    }

    function accueilAfficherEcheances(candidats) {
      const liste = document.getElementById("accueil-echeances");
      liste.replaceChildren();
      const items = accueilConstruireEcheances(candidats);
      if (items.length === 0) {
        liste.appendChild(accueilEtatVide("Aucune échéance proche.", "Les prochaines dates apparaîtront ici."));
        return;
      }
      items.forEach((i) => {
        const date = new Date(i.iso + "T00:00:00");
        const li = accueilNoeud("li", "echeance");
        const bloc = accueilNoeud("div", "echeance-date");
        bloc.appendChild(accueilNoeud("b", "", String(date.getDate())));
        bloc.appendChild(accueilNoeud("span", "", MOIS_COURTS_FR[date.getMonth()]));
        li.appendChild(bloc);
        li.appendChild(accueilNoeud("div", "ligne-texte"));
        li.lastChild.appendChild(accueilNoeud("strong", "", i.libelle));
        const classe = i.jours <= SEUIL_ECHEANCE_CRITIQUE_JOURS ? "badge-err"
          : i.jours <= SEUIL_ECHEANCE_ALERTE_JOURS ? "badge-warn" : "";
        li.appendChild(accueilNoeud("span", "badge " + classe, accueilTexteDelai(i.jours)));
        liste.appendChild(li);
      });
    }

    function accueilMajCompteurNav(synthese) {
      const compteur = document.getElementById("nav-compteur-validation");
      const total = synthese ? (synthese.total_a_valider || 0) + (synthese.total_suspendues || 0) : 0;
      compteur.textContent = String(total);
      compteur.classList.toggle("cache", total === 0);
    }

    function accueilAfficher(etat) {
      accueilAfficherActions(etat);
      accueilAfficherEcheances(etat.candidats);
      accueilMajCompteurNav(etat.validations);
    }

"""
