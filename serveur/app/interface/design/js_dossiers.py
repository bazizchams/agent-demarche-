"""JavaScript de l'interface : Socle (état, appels API, session), étudiants, pièces, conseiller et score.

Socle extrait de l'ancien `routeur_interface.py` : chaîne Python non brute, les doubles
antislash y sont voulus (échappements Python) et leur nombre est verrouillé par les tests.
Les écrans Dossiers (listes, fiche, pièces, score, discussion) sont construits par nœuds DOM et
`textContent` (helpers `dos*`) : aucune donnée n'est interprétée comme du HTML.
"""

from __future__ import annotations

JS_DOSSIERS = """
    let roleActif = "";
    let jetonCsrf = "";
    let candidatActifId = null;
    let candidatActifObj = null;
    let dictionnaireCandidats = {};
    let listeDemarches = [
      { code: "campus_france", libelle: "Campus France — Études en France (Guide Septembre 2026)" },
      { code: "ircc_permis_etudes", libelle: "IRCC Canada — Demande de permis d'études" },
    ];

    const LIBELLES_PIECES_FR = {
      passeport: "Passeport biométrique en cours de validité",
      photo_identite: "Photo d'identité aux normes passeport",
      releve_notes_bac: "Relevé de notes du Baccalauréat",
      diplome_bac: "Diplôme ou attestation provisoire du Baccalauréat",
      releves_notes_superieur: "Relevés de notes des années d'études supérieures",
      cv: "Curriculum Vitæ (CV)",
      attestation_langue_francaise: "Attestation de test de français (TCF / DELF / DALF)",
      lettre_admission_dli: "Lettre d'admission d'un établissement désigné (EED / DLI)",
      attestation_provinciale_pal_caq: "Lettre d'attestation provinciale (LAP / PAL) ou CAQ Québec",
      preuve_financiere: "Preuve de ressources financières",
      formulaire_imm5645: "Formulaire d'informations sur la famille (IMM 5645)",
      lettre_explicative: "Lettre d'explication / Plan d'études"
    };

    const LIBELLES_CHAMPS_FR = {
      nom: "Nom de famille",
      prenom: "Prénom",
      sexe: "Sexe",
      date_naissance: "Date de naissance",
      lieu_naissance: "Lieu de naissance",
      nationalite: "Nationalité",
      pays_residence: "Pays de résidence",
      email: "Adresse e-mail",
      telephone: "Numéro de téléphone",
      numero_passeport: "Numéro de passeport",
      date_expiration_passeport: "Date d'expiration du passeport",
      niveau_actuel: "Niveau d'études actuel",
      programme_vise: "Formation / Programme visé",
      etablissement_vise: "Établissement visé",
      fonds_disponibles_eur: "Ressources financières disponibles (EUR)"
    };

    const LIBELLES_SOLIDITE_FR = {
      tres_solide: "Très solide",
      favorable: "Favorable",
      fragile: "Fragile (à consolider)",
      risque_eleve: "Risque élevé de refus",
      incomplet_ou_bloquant: "Dossier incomplet (pièces ou informations requises manquantes)"
    };

    const LIBELLES_STATUT_TACHE_FR = {
      en_attente: "En attente de lancement",
      en_cours: "En cours d'exécution par l'agent",
      suspendue: "En pause (intervention ou pièce requise)",
      a_valider: "Prêt pour validation humaine (arrêté avant soumission — Règle 1)",
      terminee: "Validé humainement et terminé",
      annulee: "Annulé",
      en_erreur: "En erreur"
    };

    // Statut de tâche -> badge (forme ET couleur) : neutre, info, ok, alerte, critique.
    function classeBadgeStatutTache(statut) {
      if (statut === "terminee") return "badge-ok";
      if (statut === "a_valider" || statut === "en_cours") return "badge-info";
      if (statut === "suspendue") return "badge-warn";
      if (statut === "en_erreur") return "badge-err";
      return "";
    }

    function echapperHtml(str) {
      if (str === null || str === undefined) return "";
      return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    let minuteurNotification = null;
    function notifier(msg, ok = true) {
      const el = document.getElementById("zone-notification");
      el.textContent = msg;
      el.className = "notif " + (ok ? "notif-ok" : "notif-err");
      el.setAttribute("role", ok ? "status" : "alert");
      // Relance l'animation d'apparition à chaque nouveau message
      el.style.animation = "none";
      void el.offsetWidth;
      el.style.animation = "";
      clearTimeout(minuteurNotification);
      // Un succès se retire seul ; une erreur reste jusqu'au prochain message
      if (ok) minuteurNotification = setTimeout(() => el.classList.add("cache"), 6000);
    }

    function allerVersVue(cible) {
      document.querySelectorAll("aside button.nav-btn").forEach((b) => {
        const courant = b.getAttribute("data-vue") === cible;
        b.classList.toggle("actif", courant);
        if (courant) b.setAttribute("aria-current", "page");
        else b.removeAttribute("aria-current");
      });
      document.querySelectorAll(".vue-ecran").forEach((s) => {
        s.classList.toggle("cache", s.id !== cible);
      });
      window.scrollTo(0, 0);
      fermerMenuMobile();
      if (cible === "vue-conseiller" || cible === "vue-documents") chargerListeDemarches();
      if (cible === "vue-conseiller" || cible === "vue-procedures") chargerStatutIA();
      if (cible === "vue-documents" && candidatActifId) {
        chargerDocumentsCandidat();
        verifierCompletudeDossier();
      } else if (cible === "vue-conseiller" && candidatActifId) {
        chargerHistoriqueDiscussion();
      } else if (cible === "vue-validation-humaine") {
        rafraichirValidationsHumaines();
      } else if (cible === "vue-historique-erreurs") {
        rafraichirJournalAudit();
      } else if (cible === "vue-procedures") {
        chargerProcedures();
      } else if (cible === "vue-campus-france") {
        chargerVoeux();
      }
    }

    document.querySelectorAll("aside button.nav-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        allerVersVue(btn.getAttribute("data-vue"));
      });
    });

    async function appelApi(url, options = {}) {
      const headers = Object.assign({}, options.headers || {});
      if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
        headers["Content-Type"] = "application/json";
      }
      if (jetonCsrf) headers["X-CSRF-Token"] = jetonCsrf;
      return fetch(url, Object.assign({}, options, { headers }));
    }

    async function connecterOperateur(silencieux = false) {
      const email = document.getElementById("login-email").value.trim();
      const mot_de_passe = document.getElementById("login-mdp").value;
      const rep = await appelApi("/api/v1/auth/connexion", {
        method: "POST",
        body: JSON.stringify({ email, mot_de_passe }),
      });
      if (rep.ok) {
        const data = await rep.json();
        jetonCsrf = data.jeton_csrf;
        roleActif = data.utilisateur.role;
        const roleFr = data.utilisateur.role === "administrateur" ? "Administrateur du bureau" : "Employé";
        document.getElementById("etat-utilisateur").textContent =
          data.utilisateur.nom_affiche + " (" + roleFr + ")";
        document.getElementById("btn-se-deconnecter").classList.remove("cache");
        majBandeauVerification(data.utilisateur);
        if (!silencieux) notifier("Session opérateur ouverte avec succès.", true);
        await chargerCandidats();
        await rafraichirTableauDeBord();
      } else {
        document.getElementById("etat-utilisateur").textContent = "Non connecté";
        document.querySelector(".session-form").open = true;
        afficherCandidatsHorsSession();
        if (!silencieux) {
          const err = await rep.json().catch(() => null);
          notifier(messageErreurApi(err, "Connexion impossible : vérifiez l'adresse e-mail et le mot de passe."), false);
        }
      }
    }

    document.getElementById("btn-se-connecter").addEventListener("click", () => connecterOperateur(false));

    document.getElementById("btn-se-deconnecter").addEventListener("click", async () => {
      await appelApi("/api/v1/auth/deconnexion", { method: "POST" });
      jetonCsrf = "";
      document.getElementById("etat-utilisateur").textContent = "Non connecté";
      document.getElementById("btn-se-deconnecter").classList.add("cache");
      majBandeauVerification(null);
      notifier("Session fermée.", true);
    });

    async function rafraichirTableauDeBord() {
      const [rCand, rVal, rAg] = await Promise.all([
        appelApi("/api/v1/candidats"),
        appelApi("/api/v1/validations/en-attente"),
        appelApi("/api/v1/agents-locaux"),
      ]);
      const etat = { candidats: [], validations: null, agents: null, recaps: null };
      if (rCand.ok) {
        const c = await rCand.json();
        document.getElementById("stat-nb-candidats").textContent = c.total;
        etat.candidats = c.elements || [];
        etat.candidats.forEach((cand) => {
          dictionnaireCandidats[cand.id] = cand;
        });
      }
      if (rVal.ok) {
        const v = await rVal.json();
        document.getElementById("stat-nb-a-valider").textContent = v.total_a_valider;
        document.getElementById("stat-nb-suspendues").textContent = v.total_suspendues;
        etat.validations = v;
      }
      if (rAg.ok) {
        const a = await rAg.json();
        document.getElementById("stat-nb-agents").textContent = a.length;
        etat.agents = a.length;
      }
      if (utilisateurHumainEcriture()) {
        const res = await chargerRecapitulatifsEnAttente().catch(() => null);
        if (res && res.ok) etat.recaps = res.liste.length;
      }
      accueilAfficher(etat);
    }

    // -----------------------------------------------------------------------
    // Outils d'affichage des écrans Dossiers : nœuds DOM et textContent uniquement.
    // -----------------------------------------------------------------------
    const DOS_ESPACE_SVG = "http://www.w3.org/2000/svg";
    const DOS_CHAMPS_FICHE = Object.keys(LIBELLES_CHAMPS_FR);
    const DOS_SEUIL_SCORE_BON = 75;
    const DOS_SEUIL_SCORE_ALERTE = 50;
    const DOS_RAYON_JAUGE = 52;

    function dosNoeud(balise, classe, texte) {
      const n = document.createElement(balise);
      if (classe) n.className = classe;
      if (texte !== undefined && texte !== null) n.textContent = texte;
      return n;
    }

    function dosSvg(nom, attributs) {
      const n = document.createElementNS(DOS_ESPACE_SVG, nom);
      Object.keys(attributs).forEach((cle) => n.setAttribute(cle, attributs[cle]));
      return n;
    }

    function dosIllustration(sorte) {
      const svg = dosSvg("svg", { viewBox: "0 0 96 72", class: "etat-vide-illu", "aria-hidden": "true", focusable: "false" });
      if (sorte === "recherche") {
        svg.appendChild(dosSvg("rect", { x: "6", y: "14", width: "60", height: "50", rx: "8", class: "illu-fond" }));
        svg.appendChild(dosSvg("path", { d: "M18 28h32M18 38h24M18 48h16", class: "illu-trait" }));
        svg.appendChild(dosSvg("circle", { cx: "66", cy: "40", r: "14", class: "illu-accent" }));
        svg.appendChild(dosSvg("path", { d: "M76 50l10 10", class: "illu-coche" }));
        return svg;
      }
      if (sorte === "piece") {
        svg.appendChild(dosSvg("rect", { x: "22", y: "6", width: "44", height: "56", rx: "6", class: "illu-papier" }));
        svg.appendChild(dosSvg("path", { d: "M31 20h26M31 28h26M31 36h14", class: "illu-trait" }));
        svg.appendChild(dosSvg("circle", { cx: "68", cy: "52", r: "14", class: "illu-accent" }));
        svg.appendChild(dosSvg("path", { d: "M68 58V46M63 51l5-5 5 5", class: "illu-coche" }));
        return svg;
      }
      svg.appendChild(dosSvg("rect", { x: "6", y: "18", width: "72", height: "48", rx: "9", class: "illu-fond" }));
      svg.appendChild(dosSvg("rect", { x: "18", y: "6", width: "48", height: "40", rx: "6", class: "illu-papier" }));
      svg.appendChild(dosSvg("path", { d: "M27 17h24M27 25h30M27 33h16", class: "illu-trait" }));
      svg.appendChild(dosSvg("circle", { cx: "72", cy: "50", r: "14", class: "illu-accent" }));
      svg.appendChild(dosSvg("path", { d: "M72 44v12M66 50h12", class: "illu-coche" }));
      return svg;
    }

    function dosEtatVide(titre, texte, sorte) {
      const bloc = dosNoeud("div", "etat-vide");
      if (sorte) bloc.appendChild(dosIllustration(sorte));
      bloc.appendChild(dosNoeud("strong", "", titre));
      if (texte) bloc.appendChild(dosNoeud("span", "", texte));
      return bloc;
    }

    function dosLigneVide(nbColonnes, titre, texte, sorte) {
      const tr = document.createElement("tr");
      const td = dosNoeud("td", "etat-vide-cellule");
      td.colSpan = nbColonnes;
      td.appendChild(dosEtatVide(titre, texte, sorte));
      tr.appendChild(td);
      return tr;
    }

    function dosSqueletteTable(tbody, nbColonnes, nbLignes) {
      tbody.replaceChildren();
      const table = tbody.closest("table");
      if (table) table.setAttribute("aria-busy", "true");
      const annonce = dosNoeud("tr", "sr-only");
      const tdAnnonce = dosNoeud("td", "", "Chargement");
      tdAnnonce.colSpan = nbColonnes;
      annonce.appendChild(tdAnnonce);
      tbody.appendChild(annonce);
      for (let i = 0; i < nbLignes; i += 1) {
        const tr = document.createElement("tr");
        tr.setAttribute("aria-hidden", "true");
        for (let j = 0; j < nbColonnes; j += 1) {
          const td = document.createElement("td");
          td.appendChild(dosNoeud("span", "squelette squelette-texte" + (j % 2 ? " court" : "")));
          tr.appendChild(td);
        }
        tbody.appendChild(tr);
      }
    }

    function dosFinChargementTable(tbody) {
      tbody.replaceChildren();
      const table = tbody.closest("table");
      if (table) table.setAttribute("aria-busy", "false");
    }

    function dosSqueletteListe(conteneur, nbLignes) {
      conteneur.replaceChildren();
      conteneur.setAttribute("aria-busy", "true");
      conteneur.appendChild(dosNoeud("div", "sr-only", "Chargement"));
      for (let i = 0; i < nbLignes; i += 1) {
        const ligne = dosNoeud("div", "ligne-squelette");
        ligne.setAttribute("aria-hidden", "true");
        ligne.appendChild(dosNoeud("span", "squelette squelette-pastille"));
        const pile = dosNoeud("span", "squelette-pile");
        pile.appendChild(dosNoeud("span", "squelette squelette-texte"));
        pile.appendChild(dosNoeud("span", "squelette squelette-texte court"));
        ligne.appendChild(pile);
        conteneur.appendChild(ligne);
      }
    }

    function dosBarreProgression(pourcent, classeEtat, libelleAccessible) {
      const valeur = Math.max(0, Math.min(100, Math.round(pourcent)));
      const barre = dosNoeud("div", "barre-progression" + (classeEtat ? " " + classeEtat : ""));
      barre.setAttribute("role", "progressbar");
      barre.setAttribute("aria-valuemin", "0");
      barre.setAttribute("aria-valuemax", "100");
      barre.setAttribute("aria-valuenow", String(valeur));
      if (libelleAccessible) barre.setAttribute("aria-label", libelleAccessible);
      const rempli = dosNoeud("div", "barre-progression-remplie");
      rempli.style.width = valeur + "%";
      barre.appendChild(rempli);
      return barre;
    }

    function dosProgression(libelle, faits, total, classeEtat) {
      const bloc = dosNoeud("div", "progression-dossier");
      const entete = dosNoeud("div", "progression-entete");
      entete.appendChild(dosNoeud("span", "", libelle));
      entete.appendChild(dosNoeud("strong", "", faits + " / " + total));
      bloc.appendChild(entete);
      bloc.appendChild(dosBarreProgression(total > 0 ? (faits * 100) / total : 0, classeEtat, libelle + " : " + faits + " sur " + total));
      return bloc;
    }

    function dosEstRenseigne(valeur) {
      return valeur !== null && valeur !== undefined && String(valeur).trim() !== "";
    }

    function dosInitiales(c) {
      const a = String(c.nom || "").trim().charAt(0);
      const b = String(c.prenom || "").trim().charAt(0);
      return (a + b).toUpperCase() || "?";
    }

    function dosChampsRenseignes(c) {
      return DOS_CHAMPS_FICHE.filter((ch) => dosEstRenseigne(c[ch])).length;
    }

    function dosBouton(classe, texte) {
      const b = dosNoeud("button", "btn " + classe, texte);
      b.type = "button";
      return b;
    }

    // -----------------------------------------------------------------------
    // Écran Étudiants : liste, fiche du dossier actif, création
    // -----------------------------------------------------------------------

    function majCompteurEtudiants(total) {
      const badge = document.getElementById("etudiants-total");
      badge.className = "badge badge-nu";
      badge.textContent = total + " " + (total > 1 ? "dossiers" : "dossier");
    }

    function celluleEtudiant(c) {
      const td = document.createElement("td");
      const identite = dosNoeud("div", "etu-identite");
      const avatar = dosNoeud("span", "avatar avatar-initiales", dosInitiales(c));
      avatar.setAttribute("aria-hidden", "true");
      identite.appendChild(avatar);
      const texte = dosNoeud("div", "ligne-texte");
      texte.appendChild(dosNoeud("strong", "", (c.nom || "") + " " + (c.prenom || "")));
      texte.appendChild(dosNoeud("span", "", c.email || "E-mail non renseigné"));
      identite.appendChild(texte);
      td.appendChild(identite);
      return td;
    }

    function celluleProgressionFiche(c) {
      const td = dosNoeud("td", "etu-progression");
      const faits = dosChampsRenseignes(c);
      const total = DOS_CHAMPS_FICHE.length;
      td.appendChild(dosProgression("Renseignée", faits, total, faits === total ? "ok" : faits < total / 2 ? "alerte" : ""));
      return td;
    }

    async function enregistrerConsentement(c) {
      const rCons = await appelApi(`/api/v1/candidats/${c.id}/consentement`, {
        method: "POST",
        body: JSON.stringify({ consentement_explicite: true, mode_recueil: "formulaire_signe_bureau" }),
      });
      if (rCons.ok) {
        notifier(`Consentement Loi 18-07 enregistré pour ${c.nom} ${c.prenom}.`, true);
        await chargerCandidats();
      }
    }

    function ligneCandidat(c) {
      const estActif = c.id === candidatActifId;
      const tr = document.createElement("tr");
      tr.classList.toggle("ligne-active", estActif);
      tr.appendChild(celluleEtudiant(c));

      const tdPass = document.createElement("td");
      if (c.numero_passeport) {
        tdPass.appendChild(dosNoeud("span", "chiffres", c.numero_passeport));
        if (c.date_expiration_passeport) tdPass.appendChild(dosNoeud("small", "", "Expire le " + c.date_expiration_passeport));
      } else {
        tdPass.appendChild(dosNoeud("span", "note", "Non renseigné"));
      }
      tr.appendChild(tdPass);

      const tdProg = document.createElement("td");
      tdProg.appendChild(dosNoeud("span", "", c.programme_vise || "-"));
      tdProg.appendChild(dosNoeud("small", "", c.etablissement_vise || "-"));
      tr.appendChild(tdProg);

      tr.appendChild(celluleProgressionFiche(c));

      const tdCons = document.createElement("td");
      tdCons.appendChild(dosNoeud("span", "badge " + (c.consentement_signe ? "badge-ok" : "badge-warn"),
        c.consentement_signe ? "Signé (Loi 18-07)" : "À recueillir"));
      tr.appendChild(tdCons);

      const tdActions = document.createElement("td");
      const actions = dosNoeud("div", "cellule-actions");
      const btnSel = dosBouton((estActif ? "btn-primaire" : "btn-secondaire") + " btn-sm", estActif ? "Dossier actif" : "Choisir ce dossier");
      btnSel.setAttribute("data-sel", c.id);
      if (estActif) btnSel.setAttribute("aria-current", "true");
      btnSel.addEventListener("click", () => {
        selectionnerCandidat(c, false);
        chargerCandidats();
      });
      const btnCons = dosBouton((c.consentement_signe ? "btn-fantome" : "btn-contour") + " btn-sm", "Enregistrer le consentement");
      btnCons.setAttribute("data-cons", c.id);
      btnCons.addEventListener("click", () => enregistrerConsentement(c));
      actions.appendChild(btnSel);
      actions.appendChild(btnCons);
      tdActions.appendChild(actions);
      tr.appendChild(tdActions);
      return tr;
    }

    // Sans session, la liste remplace ses squelettes par un état vide explicite.
    function afficherCandidatsHorsSession() {
      const tbody = document.querySelector("#table-candidats tbody");
      dosFinChargementTable(tbody);
      tbody.appendChild(dosLigneVide(6, "Connectez-vous pour voir vos dossiers.", "Ouvrez votre session pour afficher les étudiants de votre bureau.", "dossier"));
    }

    async function chargerCandidats() {
      const q = document.getElementById("rech-candidat").value.trim();
      const url = q ? "/api/v1/candidats?recherche=" + encodeURIComponent(q) : "/api/v1/candidats";
      const tbody = document.querySelector("#table-candidats tbody");
      const rep = await appelApi(url);
      if (!rep.ok) {
        dosFinChargementTable(tbody);
        tbody.appendChild(dosLigneVide(6, "Liste indisponible.", "Ouvrez votre session puis cliquez sur « Rechercher » pour afficher les dossiers.", "dossier"));
        return;
      }
      const data = await rep.json();
      dosFinChargementTable(tbody);
      majCompteurEtudiants(typeof data.total === "number" ? data.total : data.elements.length);
      if (data.elements.length === 0) {
        tbody.appendChild(q
          ? dosLigneVide(6, "Aucun étudiant ne correspond à « " + q + " ».", "Vérifiez l'orthographe ou cherchez par numéro de passeport.", "recherche")
          : dosLigneVide(6, "Aucun étudiant pour le moment.", "Ouvrez « Nouvel étudiant », remplissez la fiche puis enregistrez-la.", "dossier"));
        return;
      }
      data.elements.forEach((c) => {
        dictionnaireCandidats[c.id] = c;
        if (!candidatActifId) selectionnerCandidat(c, true);
        if (c.id === candidatActifId) {
          candidatActifObj = c;
          afficherFicheDossierActif(c);
        }
        tbody.appendChild(ligneCandidat(c));
      });
    }

    function valeurFiche(c, champ) {
      const v = c[champ];
      if (!dosEstRenseigne(v)) return null;
      if (champ === "sexe") return v === "M" ? "Masculin" : v === "F" ? "Féminin" : String(v);
      if (champ === "fonds_disponibles_eur") return Number(v).toLocaleString("fr-FR") + " EUR";
      return String(v);
    }

    function sectionFiche(c, titre, champs) {
      const section = dosNoeud("section", "fiche-section");
      section.appendChild(dosNoeud("h4", "", titre));
      const dl = dosNoeud("dl", "fiche-liste");
      champs.forEach((champ) => {
        const ligne = document.createElement("div");
        ligne.appendChild(dosNoeud("dt", "", LIBELLES_CHAMPS_FR[champ] || champ));
        const valeur = valeurFiche(c, champ);
        ligne.appendChild(dosNoeud("dd", valeur === null ? "fiche-vide" : "", valeur === null ? "Non renseigné" : valeur));
        dl.appendChild(ligne);
      });
      section.appendChild(dl);
      return section;
    }

    function afficherFicheDossierActif(c) {
      const corps = document.getElementById("fiche-active-corps");
      const badge = document.getElementById("fiche-active-badge");
      document.getElementById("titre-fiche-active").textContent = (c.nom || "") + " " + (c.prenom || "");
      const faits = dosChampsRenseignes(c);
      const total = DOS_CHAMPS_FICHE.length;
      badge.className = "badge " + (faits === total ? "badge-valide" : "badge-completer");
      badge.textContent = faits === total ? "Fiche complète" : "Fiche " + faits + " / " + total;
      const grille = dosNoeud("div", "fiche-grille");
      grille.appendChild(sectionFiche(c, "Identité", ["nom", "prenom", "sexe", "date_naissance", "lieu_naissance", "nationalite"]));
      grille.appendChild(sectionFiche(c, "Coordonnées", ["pays_residence", "email", "telephone"]));
      grille.appendChild(sectionFiche(c, "Passeport", ["numero_passeport", "date_expiration_passeport"]));
      grille.appendChild(sectionFiche(c, "Projet d'études", ["niveau_actuel", "programme_vise", "etablissement_vise", "fonds_disponibles_eur"]));
      corps.replaceChildren(grille);
    }

    function selectionnerCandidat(c, silencieux = false) {
      candidatActifId = c.id;
      candidatActifObj = c;
      dictionnaireCandidats[c.id] = c;
      document.getElementById("bandeau-candidat-actif").textContent =
        `${c.nom} ${c.prenom} (Passeport : ${c.numero_passeport || "non renseigné"})`;
      afficherFicheDossierActif(c);
      if (typeof ouvSurChangementCandidat === "function") ouvSurChangementCandidat(c);
      if (!silencieux) {
        notifier(`Dossier actif sélectionné : ${c.nom} ${c.prenom}`, true);
      }
    }

    function libelleCandidatParId(candId) {
      const c = dictionnaireCandidats[candId];
      if (!c) return "Candidat sélectionné";
      return `${c.nom} ${c.prenom} (Passeport : ${c.numero_passeport || "non renseigné"})`;
    }

    function rechercherCandidats() {
      dosSqueletteTable(document.querySelector("#table-candidats tbody"), 6, 3);
      chargerCandidats();
    }

    document.getElementById("btn-rechercher-candidat").addEventListener("click", rechercherCandidats);
    document.getElementById("rech-candidat").addEventListener("keydown", (e) => {
      if (e.key === "Enter") rechercherCandidats();
    });

    // Le formulaire « Nouvel étudiant » est en bas de l'écran : on l'amène à l'écran à l'ouverture.
    document.getElementById("carte-nouvel-etudiant").addEventListener("toggle", (e) => {
      if (e.target.open) e.target.scrollIntoView({ behavior: "smooth", block: "start" });
    });

    function signalerChampObligatoire(idChamp, vide) {
      document.getElementById(idChamp).setAttribute("aria-invalid", vide ? "true" : "false");
      document.getElementById(idChamp + "-err").classList.toggle("cache", !vide);
    }

    document.getElementById("btn-creer-candidat").addEventListener("click", async () => {
      const payload = {
        nom: document.getElementById("cand-nom").value.trim(),
        prenom: document.getElementById("cand-prenom").value.trim(),
        sexe: document.getElementById("cand-sexe").value || null,
        date_naissance: document.getElementById("cand-dn").value || null,
        lieu_naissance: document.getElementById("cand-lieu").value.trim() || null,
        nationalite: document.getElementById("cand-nat").value.trim() || null,
        pays_residence: document.getElementById("cand-pays").value.trim() || null,
        email: document.getElementById("cand-email").value.trim() || null,
        telephone: document.getElementById("cand-tel").value.trim() || null,
        numero_passeport: document.getElementById("cand-pass").value.trim() || null,
        date_expiration_passeport: document.getElementById("cand-exp-pass").value || null,
        niveau_actuel: document.getElementById("cand-niveau").value.trim() || null,
        programme_vise: document.getElementById("cand-prog").value.trim() || null,
        etablissement_vise: document.getElementById("cand-etab").value.trim() || null,
        fonds_disponibles_eur: document.getElementById("cand-fonds").value
          ? parseInt(document.getElementById("cand-fonds").value, 10)
          : null,
      };
      signalerChampObligatoire("cand-nom", !payload.nom);
      signalerChampObligatoire("cand-prenom", !payload.prenom);
      if (!payload.nom || !payload.prenom) {
        document.getElementById(!payload.nom ? "cand-nom" : "cand-prenom").focus();
        return notifier("Renseignez le nom et le prénom de l'étudiant avant d'enregistrer.", false);
      }
      const btn = document.getElementById("btn-creer-candidat");
      btn.setAttribute("aria-busy", "true");
      try {
        const rep = await appelApi("/api/v1/candidats", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        if (rep.ok) {
          const c = await rep.json();
          selectionnerCandidat(c, false);
          await chargerCandidats();
          await rafraichirTableauDeBord();
          notifier(`Fiche candidat ${c.nom} ${c.prenom} créée et chiffrée avec succès.`, true);
        } else {
          const err = await rep.json();
          notifier(messageErreurApi(err, "La fiche n'a pas pu être créée : vérifiez le nom et le prénom, puis réessayez."), false);
        }
      } finally {
        btn.removeAttribute("aria-busy");
      }
    });

    // -----------------------------------------------------------------------
    // Onglet 3 : Documents & Pièces manquantes (ZÉRO CODE / ZÉRO JSON)
    // -----------------------------------------------------------------------

    function dosEstPassee(iso) {
      const d = new Date(String(iso) + "T00:00:00");
      if (isNaN(d.getTime())) return false;
      const aujourdhui = new Date();
      aujourdhui.setHours(0, 0, 0, 0);
      return d.getTime() < aujourdhui.getTime();
    }

    async function supprimerDocument(d) {
      const rDel = await appelApi(`/api/v1/candidats/${candidatActifId}/documents/${d.id}`, { method: "DELETE" });
      if (rDel.ok) {
        notifier("Pièce supprimée du dossier.", true);
        await chargerDocumentsCandidat();
        await verifierCompletudeDossier();
      }
    }

    function ligneDocument(d) {
      const tr = document.createElement("tr");
      const tdPiece = document.createElement("td");
      tdPiece.appendChild(dosNoeud("strong", "", LIBELLES_PIECES_FR[d.type_piece] || d.type_piece));
      tr.appendChild(tdPiece);
      tr.appendChild(dosNoeud("td", "", d.nom_fichier_origine));
      const tdExp = document.createElement("td");
      if (!d.date_expiration) tdExp.appendChild(dosNoeud("span", "note", "Non requise"));
      else if (dosEstPassee(d.date_expiration)) tdExp.appendChild(dosNoeud("span", "badge badge-err", "Expirée le " + d.date_expiration));
      else tdExp.appendChild(dosNoeud("span", "chiffres", d.date_expiration));
      tr.appendChild(tdExp);
      tr.appendChild(dosNoeud("td", "num", Math.max(1, Math.round(d.taille_octets / 1024)) + " Ko"));
      const tdActions = document.createElement("td");
      const actions = dosNoeud("div", "cellule-actions");
      const lien = dosNoeud("a", "btn btn-contour btn-sm", "Télécharger");
      lien.href = `/api/v1/candidats/${candidatActifId}/documents/${d.id}/telecharger`;
      lien.target = "_blank";
      lien.rel = "noopener";
      const btnSuppr = dosBouton("btn-danger btn-sm", "Supprimer");
      btnSuppr.setAttribute("data-suppr", d.id);
      btnSuppr.addEventListener("click", () => supprimerDocument(d));
      actions.appendChild(lien);
      actions.appendChild(btnSuppr);
      tdActions.appendChild(actions);
      tr.appendChild(tdActions);
      return tr;
    }

    async function chargerDocumentsCandidat() {
      if (!candidatActifId) return;
      const tbody = document.querySelector("#table-documents-candidat tbody");
      dosSqueletteTable(tbody, 5, 2);
      const rep = await appelApi(`/api/v1/candidats/${candidatActifId}/documents`);
      if (!rep.ok) {
        dosFinChargementTable(tbody);
        tbody.appendChild(dosLigneVide(5, "Pièces indisponibles.", "La liste n'a pas pu être chargée : vérifiez votre session puis rouvrez cet écran.", "piece"));
        return;
      }
      const docs = await rep.json();
      dosFinChargementTable(tbody);
      if (docs.length === 0) {
        tbody.appendChild(dosLigneVide(5, "Aucune pièce déposée.", "Ajoutez un fichier ci-dessus ou générez les pièces spécimens de démonstration.", "piece"));
        return;
      }
      docs.forEach((d) => tbody.appendChild(ligneDocument(d)));
    }

    // Statut d'une pièce -> pastille (forme + couleur), badge et précision.
    function etatPiece(p) {
      if (p.statut === "valide") {
        return { pastille: "piece-ok", badge: "badge-valide", texte: "Reçue",
          detail: p.date_expiration ? "Valide jusqu'au " + p.date_expiration : "Déposée et valide" };
      }
      if (!p.obligatoire) return { pastille: "", badge: "badge-brouillon", texte: "Facultative", detail: "Recommandée, non exigée" };
      if (p.statut === "expiree") return { pastille: "piece-manque", badge: "badge-err", texte: "Expirée", detail: "Document expiré : déposez une version à jour" };
      if (p.statut === "validite_insuffisante") return { pastille: "piece-warn", badge: "badge-warn", texte: "À renouveler", detail: p.detail || "Validité restante insuffisante" };
      if (p.statut === "expiration_non_renseignee") return { pastille: "piece-warn", badge: "badge-warn", texte: "Date à renseigner", detail: "Date d'expiration à renseigner" };
      return { pastille: "piece-manque", badge: "badge-err", texte: "Manquante", detail: "Pièce obligatoire non déposée" };
    }

    function lignePiece(p) {
      const etat = etatPiece(p);
      const li = document.createElement("li");
      const pastille = dosNoeud("span", "piece-pastille " + etat.pastille);
      pastille.setAttribute("aria-hidden", "true");
      li.appendChild(pastille);
      const texte = dosNoeud("div", "ligne-texte");
      texte.appendChild(dosNoeud("strong", "", p.libelle));
      texte.appendChild(dosNoeud("span", "", etat.detail));
      li.appendChild(texte);
      li.appendChild(dosNoeud("span", "badge " + etat.badge, etat.texte));
      return li;
    }

    function blocCompletude(titre, elements) {
      const bloc = dosNoeud("div", "completude-bloc");
      bloc.appendChild(dosNoeud("span", "surtitre", titre));
      elements.forEach((e) => bloc.appendChild(e));
      return bloc;
    }

    function formaterCarteCompletude(comp) {
      if (!comp || !comp.pieces) return null;
      const obligatoires = comp.pieces.filter((p) => p.obligatoire);
      const piecesManquantes = obligatoires.filter((p) => p.statut !== "valide");
      const piecesValidesOblig = obligatoires.filter((p) => p.statut === "valide");
      const piecesFacultatives = comp.pieces.filter((p) => !p.obligatoire);
      const champsManquants = (comp.champs_candidat_manquants || []).map((ch) => LIBELLES_CHAMPS_FR[ch] || ch);

      const carte = dosNoeud("section", "carte completude-carte");
      const entete = dosNoeud("div", "carte-entete");
      entete.appendChild(dosNoeud("h4", "", comp.libelle_demarche));
      entete.appendChild(dosNoeud("span", "badge " + (comp.pret_pour_prerequis ? "badge-ok" : "badge-err"),
        comp.pret_pour_prerequis ? "Dossier complet" : "Pièces manquantes"));
      carte.appendChild(entete);

      const complet = piecesValidesOblig.length === obligatoires.length;
      carte.appendChild(dosProgression("Pièces obligatoires reçues", piecesValidesOblig.length, obligatoires.length, complet ? "ok" : "alerte"));

      if (piecesManquantes.length === 0 && champsManquants.length === 0) {
        carte.appendChild(dosNoeud("div", "notif notif-ok", "Toutes les pièces justificatives obligatoires et les informations du candidat sont complètes et valides."));
      }

      const listeOblig = dosNoeud("ul", "liste-pieces");
      piecesManquantes.concat(piecesValidesOblig).forEach((p) => listeOblig.appendChild(lignePiece(p)));
      if (obligatoires.length > 0) carte.appendChild(blocCompletude("Pièces obligatoires (" + obligatoires.length + ")", [listeOblig]));

      if (champsManquants.length > 0) {
        const listeChamps = dosNoeud("ul", "liste-pieces sans-badge");
        champsManquants.forEach((lib) => {
          const li = document.createElement("li");
          const pastille = dosNoeud("span", "piece-pastille piece-warn");
          pastille.setAttribute("aria-hidden", "true");
          li.appendChild(pastille);
          li.appendChild(dosNoeud("span", "", lib));
          listeChamps.appendChild(li);
        });
        carte.appendChild(blocCompletude("Informations à compléter dans la fiche (" + champsManquants.length + ")", [listeChamps]));
      }

      if (piecesFacultatives.length > 0) {
        const listeFac = dosNoeud("ul", "liste-pieces");
        piecesFacultatives.forEach((p) => listeFac.appendChild(lignePiece(p)));
        carte.appendChild(blocCompletude("Pièces complémentaires recommandées", [listeFac]));
      }
      return carte;
    }

    function squeletteCompletude(zone) {
      zone.replaceChildren();
      zone.setAttribute("aria-busy", "true");
      zone.appendChild(dosNoeud("div", "sr-only", "Vérification en cours"));
      const grille = dosNoeud("div", "completude-grille");
      for (let i = 0; i < 2; i += 1) {
        const carte = dosNoeud("div", "carte completude-carte");
        carte.setAttribute("aria-hidden", "true");
        carte.appendChild(dosNoeud("span", "squelette squelette-titre"));
        const liste = document.createElement("div");
        dosSqueletteListe(liste, 3);
        liste.removeAttribute("aria-busy");
        carte.appendChild(liste);
        grille.appendChild(carte);
      }
      zone.appendChild(grille);
    }

    async function verifierCompletudeDossier() {
      if (!candidatActifId) return notifier("Choisissez d'abord un dossier dans « Étudiants et fiches ».", false);
      const zone = document.getElementById("zone-completude");
      squeletteCompletude(zone);
      await chargerListeDemarches();
      const reponses = await Promise.all(
        listeDemarches.map((d) => appelApi(`/api/v1/candidats/${candidatActifId}/completude/${encodeURIComponent(d.code)}`))
      );
      const grille = dosNoeud("div", "completude-grille");
      for (const r of reponses) {
        const donnees = r.ok ? await r.json() : null;
        const carte = formaterCarteCompletude(donnees);
        if (carte) grille.appendChild(carte);
      }
      zone.replaceChildren();
      zone.setAttribute("aria-busy", "false");
      if (grille.children.length === 0) {
        const vide = dosEtatVide("Vérification impossible.", "Aucune démarche n'a répondu : vérifiez votre session puis réessayez.", "dossier");
        vide.classList.add("carte", "carte-sobre");
        zone.appendChild(vide);
        return;
      }
      zone.appendChild(grille);
    }

    // Zone de dépôt : nom du fichier choisi et surbrillance pendant le glisser-déposer.
    (function initialiserZoneDepot() {
      const champ = document.getElementById("doc-fichier");
      const zone = champ.closest(".depot-zone");
      const nom = document.getElementById("doc-fichier-nom");
      champ.addEventListener("change", () => {
        const f = champ.files.length ? champ.files[0] : null;
        nom.textContent = f ? "Fichier choisi : " + f.name + " (" + Math.max(1, Math.round(f.size / 1024)) + " Ko)" : "";
      });
      ["dragenter", "dragover"].forEach((t) => champ.addEventListener(t, () => zone.classList.add("survol")));
      ["dragleave", "drop"].forEach((t) => champ.addEventListener(t, () => zone.classList.remove("survol")));
    })();

    document.getElementById("btn-televerser-doc").addEventListener("click", async () => {
      if (!candidatActifId) return notifier("Choisissez d'abord un dossier dans « Étudiants et fiches ».", false);
      const fichierInput = document.getElementById("doc-fichier");
      if (!fichierInput.files.length) return notifier("Choisissez un fichier PDF, PNG ou JPEG à téléverser.", false);
      const typePiece = document.getElementById("doc-type-piece").value;
      const fd = new FormData();
      fd.append("type_piece", typePiece);
      const exp = document.getElementById("doc-expiration").value;
      if (exp) fd.append("date_expiration", exp);
      fd.append("fichier", fichierInput.files[0]);
      const btn = document.getElementById("btn-televerser-doc");
      btn.setAttribute("aria-busy", "true");
      try {
        const rep = await appelApi(`/api/v1/candidats/${candidatActifId}/documents`, {
          method: "POST",
          body: fd,
        });
        if (rep.ok) {
          const doc = await rep.json();
          const libellePiece = LIBELLES_PIECES_FR[doc.type_piece] || doc.type_piece;
          notifier(`Pièce « ${libellePiece} » chiffrée et enregistrée avec succès.`, true);
          fichierInput.value = "";
          document.getElementById("doc-fichier-nom").textContent = "";
          await chargerDocumentsCandidat();
          await verifierCompletudeDossier();
        } else {
          const err = await rep.json();
          notifier(messageErreurApi(err, "Le fichier a été refusé : utilisez un PDF, PNG ou JPEG de 10 Mo maximum."), false);
        }
      } finally {
        btn.removeAttribute("aria-busy");
      }
    });

    document.getElementById("btn-verifier-completude").addEventListener("click", verifierCompletudeDossier);

    document.getElementById("btn-specimens-demo").addEventListener("click", async () => {
      if (!candidatActifId) return notifier("Choisissez d'abord un dossier dans « Étudiants et fiches ».", false);
      const rep = await appelApi(`/api/v1/candidats/${candidatActifId}/documents/specimens-demo`, {
        method: "POST",
      });
      if (rep.ok) {
        const crees = await rep.json();
        notifier(
          crees.length > 0
            ? `${crees.length} pièce(s) justificative(s) spécimen(s) générée(s) et chiffrée(s) pour ce candidat.`
            : "Toutes les pièces justificatives sont déjà présentes dans ce dossier.",
          true
        );
        await chargerDocumentsCandidat();
        await verifierCompletudeDossier();
      }
    });

    // -----------------------------------------------------------------------
    // Onglet 4 : Score d'acceptation & Discussion Conseiller (ZÉRO CODE)
    // -----------------------------------------------------------------------

    function classeNiveauScore(score) {
      if (score >= DOS_SEUIL_SCORE_BON) return { jauge: "jauge-bon", badge: "badge-valide" };
      if (score >= DOS_SEUIL_SCORE_ALERTE) return { jauge: "jauge-alerte", badge: "badge-completer" };
      return { jauge: "jauge-critique", badge: "badge-refuse" };
    }

    function construireJauge(score) {
      const valeur = Math.max(0, Math.min(100, Number(score) || 0));
      const circonference = 2 * Math.PI * DOS_RAYON_JAUGE;
      const bloc = dosNoeud("div", "jauge");
      bloc.setAttribute("role", "img");
      bloc.setAttribute("aria-label", "Score d'acceptation estimé : " + valeur + " %");
      const svg = dosSvg("svg", { viewBox: "0 0 120 120", "aria-hidden": "true", focusable: "false" });
      svg.appendChild(dosSvg("circle", { cx: "60", cy: "60", r: String(DOS_RAYON_JAUGE), class: "jauge-piste" }));
      svg.appendChild(dosSvg("circle", {
        cx: "60", cy: "60", r: String(DOS_RAYON_JAUGE), class: "jauge-valeur " + classeNiveauScore(valeur).jauge,
        "stroke-dasharray": ((circonference * valeur) / 100).toFixed(1) + " " + circonference.toFixed(1),
        transform: "rotate(-90 60 60)",
      }));
      bloc.appendChild(svg);
      const centre = dosNoeud("div", "jauge-centre");
      centre.setAttribute("aria-hidden", "true");
      centre.appendChild(dosNoeud("span", "jauge-chiffre", valeur + " %"));
      centre.appendChild(dosNoeud("span", "jauge-legende", "sur 100"));
      bloc.appendChild(centre);
      return bloc;
    }

    function blocScore(titre, contenu) {
      const bloc = dosNoeud("section", "score-bloc");
      bloc.appendChild(dosNoeud("h4", "", titre));
      bloc.appendChild(contenu);
      return bloc;
    }

    function listeAPastilles(textes, classePastille) {
      const ul = dosNoeud("ul", "liste-pieces sans-badge");
      textes.forEach((t) => {
        const li = document.createElement("li");
        const pastille = dosNoeud("span", "piece-pastille " + classePastille);
        pastille.setAttribute("aria-hidden", "true");
        li.appendChild(pastille);
        li.appendChild(dosNoeud("span", "", t));
        ul.appendChild(li);
      });
      return ul;
    }

    function listeCriteres(criteres) {
      const ul = dosNoeud("ul", "liste-criteres");
      criteres.forEach((c) => {
        const li = document.createElement("li");
        const entete = dosNoeud("div", "critere-entete");
        entete.appendChild(dosNoeud("strong", "", c.libelle));
        entete.appendChild(dosNoeud("span", "", c.points_obtenus + " / " + c.points_max + " points"));
        li.appendChild(entete);
        const ratio = c.points_max > 0 ? (c.points_obtenus * 100) / c.points_max : 0;
        li.appendChild(dosBarreProgression(ratio, ratio >= 100 ? "ok" : ratio < 50 ? "alerte" : "", c.libelle));
        if (c.commentaire) li.appendChild(dosNoeud("span", "critere-commentaire", c.commentaire));
        ul.appendChild(li);
      });
      return ul;
    }

    function enteteScore(data, score) {
      const entete = dosNoeud("div", "score-entete");
      const blocJauge = dosNoeud("div", "jauge-bloc");
      blocJauge.appendChild(construireJauge(score));
      blocJauge.appendChild(dosNoeud("span", "jauge-legende", "Score d'acceptation estimé"));
      entete.appendChild(blocJauge);
      const infos = dosNoeud("div", "score-infos");
      infos.appendChild(dosNoeud("span", "surtitre", "Démarche évaluée"));
      infos.appendChild(dosNoeud("h4", "", data.libelle_demarche));
      infos.appendChild(dosNoeud("span", "badge " + classeNiveauScore(score).badge,
        "Niveau du dossier : " + (LIBELLES_SOLIDITE_FR[data.niveau_solidite] || data.niveau_solidite)));
      if (data.meilleure_action_recommandee) {
        const action = dosNoeud("div", "banniere-regle");
        action.appendChild(dosNoeud("strong", "", "Action prioritaire recommandée : "));
        action.appendChild(document.createTextNode(data.meilleure_action_recommandee));
        infos.appendChild(action);
      }
      entete.appendChild(infos);
      return entete;
    }

    function blocVeille(veille) {
      const details = dosNoeud("details", "guide-bloc");
      details.appendChild(dosNoeud("summary", "", "Règles officielles et prérequis applicables (" + veille.length + ")"));
      const ul = dosNoeud("ul", "liste-propre");
      veille.forEach((v) => {
        const li = document.createElement("li");
        li.appendChild(dosNoeud("strong", "", v.titre));
        li.appendChild(document.createTextNode(" (" + v.reference + ") : " + v.resume));
        ul.appendChild(li);
      });
      details.appendChild(ul);
      return details;
    }

    function afficherEvaluationEnTexte(data) {
      const score = data.pourcentage_acceptation_estime ?? 0;
      const resultat = dosNoeud("div", "score-resultat");
      resultat.appendChild(enteteScore(data, score));

      const risques = data.risques_et_blocages || [];
      const forces = data.points_forts || [];
      if (risques.length > 0 || forces.length > 0) {
        const grille = dosNoeud("div", "grille-2");
        if (risques.length > 0) grille.appendChild(blocScore("À corriger en priorité (" + risques.length + ")", listeAPastilles(risques, "piece-manque")));
        if (forces.length > 0) grille.appendChild(blocScore("Points forts du dossier (" + forces.length + ")", listeAPastilles(forces, "piece-ok")));
        resultat.appendChild(grille);
      }

      if (data.actions_prioritaires && data.actions_prioritaires.length > 0) {
        const ol = dosNoeud("ol", "liste-propre");
        data.actions_prioritaires.forEach((act) => ol.appendChild(dosNoeud("li", "", act)));
        resultat.appendChild(blocScore("Plan d'action recommandé", ol));
      }

      if (data.criteres && data.criteres.length > 0) {
        resultat.appendChild(blocScore("Détail du calcul sur 100 points", listeCriteres(data.criteres)));
      }

      if (data.veille_reglementaire && data.veille_reglementaire.length > 0) {
        resultat.appendChild(blocVeille(data.veille_reglementaire));
      }

      if (data.avertissement) resultat.appendChild(dosNoeud("p", "note", data.avertissement));
      document.getElementById("zone-score-acceptation").replaceChildren(resultat);
    }

    document.getElementById("btn-calculer-score").addEventListener("click", async () => {
      if (!candidatActifId) return notifier("Choisissez d'abord un dossier dans « Étudiants et fiches ».", false);
      const dem = document.getElementById("eval-demarche").value;
      const btn = document.getElementById("btn-calculer-score");
      btn.setAttribute("aria-busy", "true");
      try {
        const rep = await appelApi(`/api/v1/candidats/${candidatActifId}/evaluation/${dem}`);
        if (rep.ok) {
          const data = await rep.json();
          afficherEvaluationEnTexte(data);
          const libelleNiveau = LIBELLES_SOLIDITE_FR[data.niveau_solidite] || data.niveau_solidite;
          notifier(`Score d'acceptation calculé : ${data.pourcentage_acceptation_estime} % (${libelleNiveau})`, true);
        } else {
          const err = await rep.json();
          notifier(messageErreurApi(err, "Impossible de calculer le score : vérifiez que la fiche du candidat est enregistrée."), false);
        }
      } finally {
        btn.removeAttribute("aria-busy");
      }
    });

    // Texte brut du conseiller -> lignes nettoyées (titres, gras et code Markdown retirés).
    function lignesMessageDiscussion(texteBrut) {
      return String(texteBrut || "")
        .split("\\n")
        .map((l) => l.replace(/^#+\\s*/, "").replace(/\\*\\*/g, "").replace(/`/g, ""));
    }

    function bulleMessage(m) {
      const estUtilisateur = m.auteur === "utilisateur" || m.auteur === "operateur";
      const scoreMsg = m.score_solidite_pourcent ?? m.score_instantane ?? "-";
      const div = dosNoeud("div", "msg " + (estUtilisateur ? "msg-op" : "msg-ia"));
      const entete = dosNoeud("div", "msg-entete");
      entete.appendChild(dosNoeud("strong", "", estUtilisateur ? "Vous (Opérateur du bureau)" : "Assistant Conseiller Réglementaire"));
      entete.appendChild(dosNoeud("span", "badge badge-nu", scoreMsg + " % d'acceptation"));
      div.appendChild(entete);
      const corps = document.createElement("div");
      lignesMessageDiscussion(m.contenu || m.message || "").forEach((ligne, i) => {
        if (i > 0) corps.appendChild(document.createElement("br"));
        corps.appendChild(document.createTextNode(ligne));
      });
      div.appendChild(corps);
      return div;
    }

    function afficherListeMessagesDiscussion(messages) {
      const fil = document.getElementById("fil-discussion");
      fil.replaceChildren();
      fil.setAttribute("aria-busy", "false");
      if (!messages || messages.length === 0) {
        fil.appendChild(dosEtatVide("Aucun message dans cette discussion.", "Posez votre première question ci-dessous.", ""));
        return;
      }
      messages.forEach((m) => fil.appendChild(bulleMessage(m)));
      fil.scrollTop = fil.scrollHeight;
    }

    async function chargerHistoriqueDiscussion() {
      if (!candidatActifId) return;
      const code_demarche = document.getElementById("eval-demarche").value;
      const fil = document.getElementById("fil-discussion");
      if (!fil.querySelector(".msg")) dosSqueletteListe(fil, 2);
      const rHisto = await appelApi(
        `/api/v1/candidats/${candidatActifId}/discussion?code_demarche=${encodeURIComponent(code_demarche)}`
      );
      if (rHisto.ok) {
        const messages = await rHisto.json();
        afficherListeMessagesDiscussion(messages);
      } else {
        fil.replaceChildren(dosEtatVide("Historique indisponible.", "La discussion n'a pas pu être chargée : vérifiez votre session puis réessayez.", ""));
        fil.setAttribute("aria-busy", "false");
      }
    }

    async function envoyerQuestionConseiller() {
      if (!candidatActifId) return notifier("Choisissez d'abord un dossier dans « Étudiants et fiches ».", false);
      const champMsg = document.getElementById("msg-discussion");
      const message = champMsg.value.trim();
      const code_demarche = document.getElementById("eval-demarche").value;
      if (message.length < 2) {
        return notifier("Veuillez saisir une question d'au moins 2 caractères.", false);
      }
      const btn = document.getElementById("btn-envoyer-discussion");
      btn.disabled = true;
      btn.setAttribute("aria-busy", "true");
      try {
        const rep = await appelApi(`/api/v1/candidats/${candidatActifId}/discussion`, {
          method: "POST",
          body: JSON.stringify({ code_demarche, message }),
        });
        if (rep.ok) {
          const echange = await rep.json();
          if (echange.evaluation) {
            afficherEvaluationEnTexte(echange.evaluation);
          }
          await chargerHistoriqueDiscussion();
          notifier("Réponse du Conseiller ajoutée à la discussion.", true);
        } else {
          const err = await rep.json();
          notifier(err.detail || "Erreur lors de l'envoi de la question au Conseiller.", false);
        }
      } finally {
        btn.disabled = false;
        btn.removeAttribute("aria-busy");
      }
    }

    function poserQuestionRapide(texte) {
      document.getElementById("msg-discussion").value = texte;
      envoyerQuestionConseiller();
    }

    document.getElementById("btn-envoyer-discussion").addEventListener("click", envoyerQuestionConseiller);
    document.getElementById("eval-demarche").addEventListener("change", chargerHistoriqueDiscussion);

"""
