"""Écran d'accueil : chiffres clés, puis ce qui demande une action humaine, puis les échéances.

Alimenté par les routes existantes (candidats, centre de validation, récapitulatifs, agents) via
`rafraichirTableauDeBord` qui appelle `accueilAfficher`. Tout l'affichage passe par des nœuds DOM
et `textContent` : aucune donnée n'est interprétée comme du HTML. Aucun antislash.
Les squelettes de chargement sont remplacés au premier affichage (ou par « — » si une route
n'a pas répondu). Les raccourcis utilisent `data-aller-vers` (géré par la coquille).
"""

from __future__ import annotations

_LIGNE_SQUELETTE_ACTION = (
    '<li class="ligne-squelette" aria-hidden="true"><span class="squelette squelette-pastille"></span>'
    '<span class="squelette-pile"><span class="squelette squelette-texte"></span>'
    '<span class="squelette squelette-texte court"></span></span></li>'
)
_LIGNE_SQUELETTE_ECHEANCE = (
    '<li class="ligne-squelette" aria-hidden="true"><span class="squelette squelette-carre"></span>'
    '<span class="squelette-pile"><span class="squelette squelette-texte"></span>'
    '<span class="squelette squelette-texte court"></span></span></li>'
)
_VALEUR_SQUELETTE = '<span class="squelette squelette-valeur" aria-hidden="true"></span>'


def _kpi(identifiant: str, libelle: str, nom_icone: str, aide: str) -> str:
    return (
        '<div class="kpi">'
        f'<div class="kpi-entete"><span>{libelle}</span><span class="kpi-icone">[[i:{nom_icone}]]</span></div>'
        f'<div id="{identifiant}" class="valeur">{_VALEUR_SQUELETTE}</div>'
        f'<p class="kpi-aide">{aide}</p></div>'
    )


def _raccourci(vue: str, nom_icone: str, titre: str, detail: str) -> str:
    return (
        f'<button class="raccourci" type="button" data-aller-vers="{vue}">'
        f'<span class="raccourci-icone">[[i:{nom_icone}]]</span>'
        f"<span><strong>{titre}</strong><small>{detail}</small></span>[[i:suivant]]</button>"
    )


HTML_ACCUEIL = f"""
    <!-- Tableau de bord : chiffres clés, actions humaines, échéances -->
    <section id="vue-tableau-bord" class="vue-ecran">
      <header class="page-entete">
        <div>
          <h2>Tableau de bord</h2>
          <p class="lead">Ce qui attend une décision de votre part, puis l'état du bureau.</p>
        </div>
        <div class="page-actions">
          <button class="btn btn-primaire" type="button" data-aller-vers="vue-etudiants" data-ouvrir="carte-nouvel-etudiant">[[i:plus]]Nouvel étudiant</button>
        </div>
      </header>

      <div class="grille-kpi" aria-label="Chiffres clés du bureau">
        {_kpi("stat-nb-candidats", "Étudiants actifs", "etudiants", "Fiches enregistrées dans votre bureau")}
        {_kpi("stat-nb-a-valider", "Prêts à valider", "validation", "Arrêtés avant l'envoi, en attente de votre contrôle")}
        {_kpi("stat-nb-suspendues", "En pause", "pause", "Pièce manquante, session expirée ou CAPTCHA")}
        {_kpi("stat-nb-agents", "Postes agents", "moniteur", "Postes de l'agent local enrôlés")}
      </div>

      <div class="accueil-grille">
        <section class="carte" aria-labelledby="titre-a-traiter">
          <div class="carte-entete">
            <h3 id="titre-a-traiter">À traiter maintenant</h3>
            <span id="accueil-total-actions" class="badge badge-nu">—</span>
          </div>
          <ul id="accueil-actions" class="liste-actions" aria-busy="true">
            <li class="sr-only">Chargement de vos dossiers</li>
            {_LIGNE_SQUELETTE_ACTION}
            {_LIGNE_SQUELETTE_ACTION}
            {_LIGNE_SQUELETTE_ACTION}
          </ul>
        </section>

        <section class="carte" aria-labelledby="titre-echeances">
          <div class="carte-entete">
            <h3 id="titre-echeances">Échéances proches</h3>
            <span class="kpi-icone">[[i:calendrier]]</span>
          </div>
          <ul id="accueil-echeances" class="liste-echeances" aria-busy="true">
            <li class="sr-only">Chargement des échéances</li>
            {_LIGNE_SQUELETTE_ECHEANCE}
            {_LIGNE_SQUELETTE_ECHEANCE}
            {_LIGNE_SQUELETTE_ECHEANCE}
          </ul>
          <p class="note carte-pied">Calendrier Campus France Algérie 2026-2027 et passeports qui expirent dans les 6 mois.</p>
        </section>
      </div>

      <div class="section-entete">
        <div>
          <h3>Accès rapides</h3>
          <p>Les tâches les plus fréquentes du bureau.</p>
        </div>
      </div>
      <div class="grille-raccourcis">
        {_raccourci("vue-campus-france", "globe", "Piloter Campus France", "Vœux et pré-remplissage Études en France")}
        {_raccourci("vue-ircc", "envoi", "Piloter IRCC Canada", "Demande de permis d'études")}
        {_raccourci("vue-conseiller", "conseiller", "Calculer un score", "Solidité du dossier et conseils")}
        {_raccourci("vue-documents", "pieces", "Vérifier les pièces", "Pièces manquantes et coffre chiffré")}
      </div>

      <p class="titre-mini">Sites officiels et pages de simulation (s'ouvrent dans un nouvel onglet)</p>
      <div class="raccourcis">
        <a class="btn btn-contour btn-sm" href="https://etudesenfrance.diplomatie.gouv.fr/" target="_blank" rel="noopener">Études en France [[i:externe]]</a>
        <a class="btn btn-contour btn-sm" href="https://portal-portail.apps.cic.gc.ca/signin?lang=fr" target="_blank" rel="noopener">Portail IRCC Canada [[i:externe]]</a>
        <a class="btn btn-fantome btn-sm" href="/demo/campus-france" target="_blank" rel="noopener">Simulation Études en France [[i:externe]]</a>
        <a class="btn btn-fantome btn-sm" href="/demo/ircc" target="_blank" rel="noopener">Simulation IRCC [[i:externe]]</a>
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
    const ESPACE_SVG = "http://www.w3.org/2000/svg";
    const IDS_CHIFFRES_ACCUEIL = ["stat-nb-candidats", "stat-nb-a-valider", "stat-nb-suspendues", "stat-nb-agents"];

    function accueilNoeud(balise, classe, texte) {
      const n = document.createElement(balise);
      if (classe) n.className = classe;
      if (texte !== undefined) n.textContent = texte;
      return n;
    }

    function accueilSvg(nom, attributs) {
      const n = document.createElementNS(ESPACE_SVG, nom);
      Object.keys(attributs).forEach((cle) => n.setAttribute(cle, attributs[cle]));
      return n;
    }

    // Petites illustrations d'état vide, construites nœud par nœud (aucun HTML interprété).
    function accueilIllustration(sorte) {
      const svg = accueilSvg("svg", { viewBox: "0 0 96 72", class: "etat-vide-illu", "aria-hidden": "true", focusable: "false" });
      if (sorte === "calendrier") {
        svg.appendChild(accueilSvg("rect", { x: "14", y: "10", width: "60", height: "52", rx: "8", class: "illu-papier" }));
        svg.appendChild(accueilSvg("path", { d: "M14 24h60M28 6v8M60 6v8", class: "illu-trait" }));
        svg.appendChild(accueilSvg("path", { d: "M26 36h8M40 36h8M26 48h8", class: "illu-trait" }));
        svg.appendChild(accueilSvg("circle", { cx: "70", cy: "50", r: "14", class: "illu-accent" }));
        svg.appendChild(accueilSvg("path", { d: "M70 43v7l5 3", class: "illu-coche" }));
        return svg;
      }
      svg.appendChild(accueilSvg("rect", { x: "6", y: "18", width: "72", height: "48", rx: "9", class: "illu-fond" }));
      svg.appendChild(accueilSvg("rect", { x: "18", y: "6", width: "48", height: "40", rx: "6", class: "illu-papier" }));
      svg.appendChild(accueilSvg("path", { d: "M27 17h24M27 25h30M27 33h16", class: "illu-trait" }));
      svg.appendChild(accueilSvg("circle", { cx: "72", cy: "50", r: "14", class: "illu-accent" }));
      svg.appendChild(accueilSvg("path", { d: "M65.5 50.5l4.5 4.5 8-9", class: "illu-coche" }));
      return svg;
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

    function accueilEtatVide(titre, texte, illustration) {
      const li = accueilNoeud("li", "etat-vide");
      li.appendChild(accueilIllustration(illustration));
      li.appendChild(accueilNoeud("strong", "", titre));
      li.appendChild(accueilNoeud("span", "", texte));
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
            "badge-warn", actionHumaine ? "CAPTCHA ou code" : "En pause",
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
      liste.setAttribute("aria-busy", "false");
      const connecte = etat.validations !== null || etat.candidats.length > 0 || etat.recaps !== null;
      if (!connecte) {
        badge.className = "badge badge-nu";
        badge.textContent = "—";
        liste.appendChild(accueilEtatVide("Connectez-vous pour voir vos dossiers.", "Ouvrez votre session pour afficher les dossiers de votre bureau.", "dossier"));
        return;
      }
      const lignes = accueilConstruireActions(etat);
      badge.className = "badge " + (lignes.length > 0 ? "badge-warn" : "badge-ok");
      badge.textContent = lignes.length > 0 ? accueilPluriel(lignes.length, "action", "actions") : "À jour";
      if (lignes.length === 0) {
        liste.appendChild(accueilEtatVide("Tout est à jour.", "Aucun dossier n'attend de décision. Ajoutez un étudiant ou lancez une démarche pour avancer.", "dossier"));
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
      liste.setAttribute("aria-busy", "false");
      const items = accueilConstruireEcheances(candidats);
      if (items.length === 0) {
        liste.appendChild(accueilEtatVide("Aucune échéance proche.", "Les prochaines dates apparaîtront ici.", "calendrier"));
        return;
      }
      items.forEach((i) => {
        const date = new Date(i.iso + "T00:00:00");
        const li = accueilNoeud("li", "echeance");
        const bloc = accueilNoeud("div", "echeance-date");
        bloc.appendChild(accueilNoeud("b", "", String(date.getDate())));
        bloc.appendChild(accueilNoeud("span", "", MOIS_COURTS_FR[date.getMonth()]));
        li.appendChild(bloc);
        const texte = accueilNoeud("div", "ligne-texte");
        texte.appendChild(accueilNoeud("strong", "", i.libelle));
        texte.appendChild(accueilNoeud("span", "", i.passeport ? "Pièce d'identité du candidat" : "Calendrier officiel"));
        li.appendChild(texte);
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
      compteur.setAttribute("aria-label", total + (total > 1 ? " dossiers à traiter" : " dossier à traiter"));
      compteur.classList.toggle("cache", total === 0);
    }

    // Chiffres clés : un squelette encore présent signifie que la route n'a pas répondu.
    function accueilFinaliserChiffres(synthese) {
      IDS_CHIFFRES_ACCUEIL.forEach((id) => {
        const el = document.getElementById(id);
        if (el && el.querySelector(".squelette")) el.textContent = "—";
      });
      const enPause = synthese ? synthese.total_suspendues || 0 : 0;
      document.getElementById("stat-nb-suspendues").parentElement.classList.toggle("kpi-alerte", enPause > 0);
    }

    function accueilAfficher(etat) {
      accueilFinaliserChiffres(etat.validations);
      accueilAfficherActions(etat);
      accueilAfficherEcheances(etat.candidats);
      accueilMajCompteurNav(etat.validations);
    }

"""
