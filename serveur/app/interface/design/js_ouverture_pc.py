"""JavaScript de la carte « Ouvrir sur mon PC » (écran Étudiants et fiches).

Chaîne Python non brute : AUCUN antislash (leur nombre dans la page est verrouillé par les tests).
Tout l'affichage est construit par nœuds DOM et `textContent` (jamais `innerHTML`), aucun `console.log`.
Utilise `appelApi`, `notifier`, `candidatActifId` et `dosNoeud` définis dans `js_dossiers`.

Parcours : le bouton crée une tâche (`POST /api/v1/taches`, action `ajouter_voeux_panier`) ; l'écran affiche
« en attente de l'agent » puis l'état réel (en cours, en pause, à valider, erreur) en interrogeant la tâche.
S'il n'y a aucun agent enrôlé ou en ligne, la marche à suivre est affichée (enrôlement, lancement).
Règle 3 : aucun mot de passe n'est demandé ici ; la connexion se fait dans la fenêtre sur le PC.
"""

from __future__ import annotations

JS_OUVERTURE_PC = """
    // ===== Ouvrir sur mon PC =====
    const OUV_ACTION = "ajouter_voeux_panier";
    const OUV_DEMARCHE = "campus_france";
    const OUV_INTERVALLE_MS = 3000;
    const OUV_STATUTS_FINAUX = ["a_valider", "terminee", "annulee", "en_erreur", "suspendue"];
    const OUV_LIBELLES = {
      en_attente: "En attente de l'agent : il prendra la tâche dès qu'il est lancé sur votre PC.",
      en_cours: "L'agent travaille dans la fenêtre ouverte sur votre PC.",
      suspendue: "En pause : une intervention de votre part est nécessaire dans la fenêtre ouverte sur votre PC.",
      a_valider: "Terminé côté agent, arrêté avant tout envoi : contrôlez la fenêtre ouverte sur votre PC, puis validez dans le Centre de validation.",
      terminee: "Validé et terminé.",
      annulee: "Tâche annulée.",
      en_erreur: "L'agent a rencontré une erreur."
    };
    const OUV_CLASSES_BADGE = {
      en_attente: "badge-attente", en_cours: "badge-info", suspendue: "badge-warn",
      a_valider: "badge-info", terminee: "badge-ok", annulee: "", en_erreur: "badge-err"
    };
    let ouvMinuteur = null;
    let ouvTacheId = null;
    let ouvCandidat = null;

    function ouvArreterSuivi() {
      if (ouvMinuteur !== null) {
        clearInterval(ouvMinuteur);
        ouvMinuteur = null;
      }
    }

    function ouvAdresseServeur() {
      return window.location.origin;
    }

    function ouvAfficherEtat(statut, message) {
      const badge = document.getElementById("ouverture-pc-badge");
      badge.className = "badge " + (OUV_CLASSES_BADGE[statut] || "badge-nu");
      badge.textContent = statut ? statut.replace("_", " ") : "—";
      const zone = document.getElementById("ouverture-pc-etat");
      const lignes = [];
      if (statut) lignes.push(dosNoeud("p", "", OUV_LIBELLES[statut] || statut));
      if (message) lignes.push(dosNoeud("p", statut === "suspendue" || statut === "en_erreur" ? "ouverture-alerte" : "aide", message));
      zone.replaceChildren(...lignes);
      document.getElementById("btn-reprendre-ouverture-pc").classList.toggle("cache", statut !== "suspendue" && statut !== "en_erreur");
      document.getElementById("btn-ouverture-vers-validation").classList.toggle("cache", statut !== "a_valider");
    }

    function ouvEtapeMarche(texte, commande) {
      const li = dosNoeud("li", "", texte);
      if (commande) {
        li.appendChild(document.createTextNode(" "));
        li.appendChild(dosNoeud("code", "", commande));
      }
      return li;
    }

    // La marche à suivre est un bloc repliable (details) : seul son résumé reste visible par défaut.
    function ouvMarcheContenu(zone, titre, etapes) {
      const corps = dosNoeud("div", "ouverture-marche-corps");
      corps.appendChild(dosNoeud("strong", "", titre));
      corps.appendChild(etapes);
      zone.replaceChildren(dosNoeud("summary", "", "Marche à suivre pour installer et lancer l'agent sur le PC"), corps);
    }

    function ouvAfficherMarche(agents) {
      const zone = document.getElementById("ouverture-pc-marche");
      const actifs = agents.filter((a) => a.actif);
      const enLigne = actifs.filter((a) => a.en_ligne);
      if (enLigne.length > 0) {
        zone.classList.add("cache");
        zone.replaceChildren();
        return;
      }
      const etapes = dosNoeud("ol", "");
      if (actifs.length === 0) {
        ouvMarcheContenu(zone, "Aucun poste agent n'est enrôlé pour votre bureau.", etapes);
        etapes.appendChild(ouvEtapeMarche("Un administrateur ouvre « Abonnement et sauvegardes », puis « Enrôler un poste agent local », et copie la clé affichée (elle ne s'affiche qu'une fois)."));
        etapes.appendChild(ouvEtapeMarche("Sur le PC Windows du bureau : installer Python 3.11 ou plus récent, puis double-cliquer sur", "agent_local" + String.fromCharCode(92) + "installer_agent.bat"));
      } else {
        const dernier = actifs.map((a) => a.derniere_activite_le).filter((d) => d).sort().pop();
        const quand = dernier ? "Dernier signe de vie : " + new Date(dernier).toLocaleString("fr-FR") + "." : "Aucun poste ne s'est encore connecté.";
        ouvMarcheContenu(zone, "Aucun agent n'est en ligne pour l'instant. " + quand, etapes);
      }
      etapes.appendChild(ouvEtapeMarche("Lancer l'agent en double-cliquant sur", "agent_local" + String.fromCharCode(92) + "lancer_agent.bat"));
      etapes.appendChild(ouvEtapeMarche("Quand le script le demande, saisir l'adresse du serveur", ouvAdresseServeur()));
      etapes.appendChild(ouvEtapeMarche("Puis coller la clé de l'agent (rien ne s'affiche pendant la saisie) et laisser la fenêtre noire ouverte."));
      etapes.appendChild(ouvEtapeMarche("Cette page détecte l'agent en quelques secondes. Guide complet : docs/AGENT_LOCAL.md."));
      zone.classList.remove("cache");
    }

    async function ouvLireAgents() {
      const rep = await appelApi("/api/v1/agents-locaux");
      return rep.ok ? await rep.json() : [];
    }

    async function ouvDerniereTache(candidatId) {
      const rep = await appelApi("/api/v1/taches?candidat_id=" + encodeURIComponent(candidatId) + "&code_demarche=" + OUV_DEMARCHE + "&taille=50");
      if (!rep.ok) return null;
      const page = await rep.json();
      const liste = (page.elements || []).filter((t) => t.action === OUV_ACTION);
      return liste.length > 0 ? liste[0] : null;
    }

    function ouvAfficherTache(tache) {
      ouvTacheId = tache.id;
      ouvAfficherEtat(tache.statut, tache.message_alerte);
      if (typeof fdSynchroniserDiscussion === "function") fdSynchroniserDiscussion();
      if (typeof fdCopierEtatPc === "function") fdCopierEtatPc();
      if (OUV_STATUTS_FINAUX.indexOf(tache.statut) !== -1) ouvArreterSuivi();
    }

    async function ouvActualiser() {
      if (document.hidden) return; // onglet caché : on économise le réseau, la reprise se fait au retour
      if (!ouvTacheId || !ouvCandidat || ouvCandidat !== candidatActifId) {
        ouvArreterSuivi();
        return;
      }
      const [rep, agents] = await Promise.all([appelApi("/api/v1/taches/" + ouvTacheId), ouvLireAgents()]);
      if (!rep.ok) {
        ouvArreterSuivi();
        return;
      }
      const tache = await rep.json();
      ouvAfficherTache(tache);
      ouvAfficherMarche(agents);
    }

    function ouvSuivre() {
      ouvArreterSuivi();
      ouvMinuteur = setInterval(ouvActualiser, OUV_INTERVALLE_MS);
    }

    async function ouvSurChangementCandidat(c) {
      ouvArreterSuivi();
      ouvTacheId = null;
      ouvCandidat = c ? c.id : null;
      cnxSurChangementCandidat(c);
      if (typeof fdSynchroniserDiscussion === "function") fdSynchroniserDiscussion();
      const bouton = document.getElementById("btn-ouvrir-sur-pc");
      if (!ouvCandidat) {
        bouton.disabled = true;
        ouvAfficherEtat("", "Choisissez d'abord un dossier.");
        return;
      }
      const [agents, tache] = await Promise.all([ouvLireAgents(), ouvDerniereTache(ouvCandidat)]);
      if (ouvCandidat !== c.id) return;
      bouton.disabled = agents.filter((a) => a.actif).length === 0;
      ouvAfficherMarche(agents);
      if (tache) {
        ouvAfficherTache(tache);
        if (OUV_STATUTS_FINAUX.indexOf(tache.statut) === -1) ouvSuivre();
      } else {
        ouvAfficherEtat("", "Aucune ouverture sur le PC pour ce dossier.");
      }
    }

    async function ouvDemanderOuverture() {
      if (!candidatActifId) {
        notifier("Choisissez d'abord un dossier dans la liste.", false);
        return;
      }
      ouvCandidat = candidatActifId;
      const bouton = document.getElementById("btn-ouvrir-sur-pc");
      bouton.setAttribute("aria-busy", "true");
      try {
        const rep = await appelApi("/api/v1/taches", {
          method: "POST",
          body: JSON.stringify({ candidat_id: candidatActifId, code_demarche: OUV_DEMARCHE, action: OUV_ACTION }),
        });
        const data = await rep.json().catch(() => ({}));
        if (!rep.ok) {
          const detail = typeof data.detail === "string" ? data.detail : "La demande n'a pas pu être créée.";
          ouvAfficherEtat("", detail);
          notifier(detail, false);
          return;
        }
        ouvAfficherTache(data);
        ouvAfficherMarche(await ouvLireAgents());
        ouvSuivre();
        notifier("Demande envoyée : en attente de l'agent sur votre PC.", true);
      } finally {
        bouton.removeAttribute("aria-busy");
      }
    }

    async function ouvReprendre() {
      if (!ouvTacheId) return;
      const rep = await appelApi("/api/v1/taches/" + ouvTacheId + "/reprendre", { method: "POST" });
      const data = await rep.json().catch(() => ({}));
      if (!rep.ok) {
        const detail = typeof data.detail === "string" ? data.detail : "La reprise a échoué.";
        notifier(detail, false);
        return;
      }
      ouvAfficherTache(data);
      ouvSuivre();
      notifier("Tâche remise en attente : l'agent va la reprendre.", true);
    }

    // ===== Connexion au portail et création de compte (R3 : aucun mot de passe ici, jamais) =====
    const CNX_ACTIONS = ["connexion_portail", "creation_compte_eef"];
    const CNX_FINAUX = ["terminee", "annulee", "en_erreur"];
    const CNX_LIBELLES = {
      en_attente: "Demande envoyée : en attente de l'agent sur votre PC.",
      en_cours: "L'agent travaille dans la fenêtre ouverte sur votre PC.",
      suspendue: "En pause : une intervention de votre part est nécessaire dans la fenêtre ouverte sur votre PC (CAPTCHA, code, fiche incomplète…), puis reprenez la tâche.",
      a_valider: "Terminé côté agent, arrêté avant tout envoi : contrôlez la fenêtre sur votre PC, puis clôturez dans le Centre de validation.",
      terminee: "Validé et terminé.", annulee: "Tâche annulée.", en_erreur: "L'agent a rencontré une erreur."
    };
    let cnxMinuteur = null;
    let cnxTacheId = null;
    let cnxAction = null;
    let cnxCandidat = null;

    function cnxArreter() {
      if (cnxMinuteur !== null) { clearInterval(cnxMinuteur); cnxMinuteur = null; }
    }

    function cnxAfficher(tache) {
      const zone = document.getElementById("connexion-pc-etat");
      if (!tache) { zone.replaceChildren(); }
      else {
        const lignes = [dosNoeud("p", "", CNX_LIBELLES[tache.statut] || tache.statut)];
        if (tache.message_alerte && (tache.statut === "suspendue" || tache.statut === "en_erreur")) lignes.push(dosNoeud("p", "ouverture-alerte", tache.message_alerte));
        zone.replaceChildren(...lignes);
      }
      const attendConsentement = !!tache && tache.action === "connexion_portail" && tache.statut === "en_cours";
      document.getElementById("btn-autoriser-agent").classList.toggle("cache", !attendConsentement);
    }

    async function cnxActualiserDepot() {
      const bloc = document.getElementById("depot-identifiants-bloc");
      if (!cnxTacheId || cnxAction !== "connexion_portail") { bloc.classList.add("cache"); return; }
      const rep = await appelApi("/api/v1/taches/" + cnxTacheId + "/depot-identifiants");
      const etat = rep.ok ? await rep.json() : { present: false };
      bloc.classList.toggle("cache", !etat.present);
    }

    async function cnxActualiser() {
      if (!cnxTacheId || !cnxCandidat || cnxCandidat !== candidatActifId) { cnxArreter(); return; }
      const rep = await appelApi("/api/v1/taches/" + cnxTacheId);
      if (!rep.ok) { cnxArreter(); return; }
      const tache = await rep.json();
      cnxAfficher(tache);
      await cnxActualiserDepot();
      if (CNX_FINAUX.indexOf(tache.statut) !== -1) cnxArreter();
    }

    function cnxSuivre() {
      cnxArreter();
      cnxMinuteur = setInterval(cnxActualiser, OUV_INTERVALLE_MS);
    }

    async function cnxSurChangementCandidat(c) {
      cnxArreter();
      cnxTacheId = null;
      cnxAction = null;
      cnxCandidat = c ? c.id : null;
      cnxAfficher(null);
      document.getElementById("depot-identifiants-bloc").classList.add("cache");
      const actif = !!cnxCandidat;
      ["btn-se-connecter-portail", "btn-creer-compte-eef"].forEach((id) => { document.getElementById(id).disabled = !actif; });
      if (!actif) return;
      const rep = await appelApi("/api/v1/taches?candidat_id=" + encodeURIComponent(cnxCandidat) + "&taille=50");
      if (!rep.ok || cnxCandidat !== c.id) return;
      const page = await rep.json();
      const liste = (page.elements || []).filter((t) => CNX_ACTIONS.indexOf(t.action) !== -1);
      if (liste.length === 0) return;
      cnxTacheId = liste[0].id;
      cnxAction = liste[0].action;
      cnxAfficher(liste[0]);
      await cnxActualiserDepot();
      if (CNX_FINAUX.indexOf(liste[0].statut) === -1) cnxSuivre();
    }

    async function cnxCreer(action, demarche, portail) {
      if (!candidatActifId) { notifier("Choisissez d'abord un dossier dans la liste.", false); return; }
      cnxCandidat = candidatActifId;
      const corps = { candidat_id: candidatActifId, code_demarche: demarche, action: action };
      if (portail) corps.portail = portail;
      const rep = await appelApi("/api/v1/taches", { method: "POST", body: JSON.stringify(corps) });
      const data = await rep.json().catch(() => ({}));
      if (!rep.ok) {
        const detail = typeof data.detail === "string" ? data.detail : "La demande n'a pas pu être créée.";
        cnxAfficher(null);
        document.getElementById("connexion-pc-etat").replaceChildren(dosNoeud("p", "ouverture-alerte", detail));
        notifier(detail, false);
        return;
      }
      cnxTacheId = data.id;
      cnxAction = data.action;
      cnxAfficher(data);
      cnxSuivre();
      notifier("Demande envoyée : en attente de l'agent sur votre PC.", true);
    }

    async function cnxAutoriser() {
      if (!cnxTacheId) return;
      const rep = await appelApi("/api/v1/taches/" + cnxTacheId + "/autoriser-connexion", { method: "POST" });
      const data = await rep.json().catch(() => ({}));
      if (!rep.ok) {
        notifier(typeof data.detail === "string" ? data.detail : "L'autorisation a échoué.", false);
        return;
      }
      notifier("Autorisation donnée pour 60 secondes, une seule fois : l'agent se connecte.", true);
    }

    async function cnxEnregistrerDepot() {
      if (!cnxTacheId) return;
      const consentement = document.getElementById("depot-consentement").checked;
      const rep = await appelApi("/api/v1/taches/" + cnxTacheId + "/depot-identifiants/enregistrer", {
        method: "POST", body: JSON.stringify({ consentement: consentement })
      });
      const data = await rep.json().catch(() => ({}));
      if (!rep.ok) {
        notifier(typeof data.detail === "string" ? data.detail : "L'enregistrement a échoué.", false);
        return;
      }
      document.getElementById("depot-consentement").checked = false;
      document.getElementById("depot-identifiants-bloc").classList.add("cache");
      notifier("Identifiants enregistrés dans le coffre chiffré.", true);
    }

    async function cnxRefuserDepot() {
      if (!cnxTacheId) return;
      await appelApi("/api/v1/taches/" + cnxTacheId + "/depot-identifiants", { method: "DELETE" });
      document.getElementById("depot-consentement").checked = false;
      document.getElementById("depot-identifiants-bloc").classList.add("cache");
      notifier("Identifiants non enregistrés : ils ont été effacés.", true);
    }

    document.getElementById("btn-se-connecter-portail").addEventListener("click", () => {
      const portail = document.getElementById("select-portail-connexion").value;
      cnxCreer("connexion_portail", portail === "ircc" ? "ircc_permis_etudes" : "compte_etudes_en_france", portail);
    });
    document.getElementById("btn-creer-compte-eef").addEventListener("click", () => cnxCreer("creation_compte_eef", "compte_etudes_en_france", null));
    document.getElementById("btn-autoriser-agent").addEventListener("click", cnxAutoriser);
    document.getElementById("btn-depot-enregistrer").addEventListener("click", cnxEnregistrerDepot);
    document.getElementById("btn-depot-refuser").addEventListener("click", cnxRefuserDepot);

    document.getElementById("btn-ouvrir-sur-pc").addEventListener("click", ouvDemanderOuverture);
    document.getElementById("btn-reprendre-ouverture-pc").addEventListener("click", ouvReprendre);
"""
