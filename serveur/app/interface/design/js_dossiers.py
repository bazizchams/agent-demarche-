"""JavaScript de l'interface : Socle (état, appels API, session), étudiants, pièces, conseiller et score.

Extrait tel quel de l'ancien `routeur_interface.py` : chaîne Python non brute, les doubles
antislash y sont voulus (échappements Python) et leur nombre est verrouillé par les tests.
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

    async function chargerCandidats() {
      const q = document.getElementById("rech-candidat").value.trim();
      const url = q ? "/api/v1/candidats?recherche=" + encodeURIComponent(q) : "/api/v1/candidats";
      const rep = await appelApi(url);
      if (!rep.ok) return;
      const data = await rep.json();
      const tbody = document.querySelector("#table-candidats tbody");
      tbody.innerHTML = "";
      if (data.elements.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="etat-vide"><strong>Aucun étudiant pour le moment.</strong>Ouvrez « Nouvel étudiant » ci-dessus, remplissez la fiche puis enregistrez-la.</td></tr>`;
        return;
      }
      data.elements.forEach((c) => {
        dictionnaireCandidats[c.id] = c;
        if (!candidatActifId) selectionnerCandidat(c, true);
        const tr = document.createElement("tr");
        const estActif = c.id === candidatActifId;
        tr.classList.toggle("ligne-active", estActif);
        tr.innerHTML = `
          <td><strong>${echapperHtml(c.nom)} ${echapperHtml(c.prenom)}</strong><br/><small>${echapperHtml(c.email || "")}</small></td>
          <td>${echapperHtml(c.numero_passeport || "Non renseigné")}</td>
          <td>${echapperHtml(c.programme_vise || "-")}<br/><small>${echapperHtml(c.etablissement_vise || "-")}</small></td>
          <td><span class="badge ${c.consentement_signe ? 'badge-ok' : 'badge-warn'}">${c.consentement_signe ? "Signé (Loi 18-07)" : "À recueillir"}</span></td>
          <td>
            <button class="btn ${estActif ? "btn-primaire" : "btn-secondaire"} btn-sm" type="button" data-sel="${c.id}">${estActif ? "Dossier actif" : "Choisir ce dossier"}</button>
            <button class="btn btn-contour btn-sm" type="button" data-cons="${c.id}">Enregistrer le consentement</button>
          </td>
        `;
        tr.querySelector("[data-sel]").addEventListener("click", () => {
          selectionnerCandidat(c, false);
          chargerCandidats();
        });
        tr.querySelector("[data-cons]").addEventListener("click", async () => {
          const rCons = await appelApi(`/api/v1/candidats/${c.id}/consentement`, {
            method: "POST",
            body: JSON.stringify({ consentement_explicite: true, mode_recueil: "formulaire_signe_bureau" }),
          });
          if (rCons.ok) {
            notifier(`Consentement Loi 18-07 enregistré pour ${c.nom} ${c.prenom}.`, true);
            await chargerCandidats();
          }
        });
        tbody.appendChild(tr);
      });
    }

    function selectionnerCandidat(c, silencieux = false) {
      candidatActifId = c.id;
      candidatActifObj = c;
      dictionnaireCandidats[c.id] = c;
      document.getElementById("bandeau-candidat-actif").textContent =
        `${c.nom} ${c.prenom} (Passeport : ${c.numero_passeport || "non renseigné"})`;
      if (!silencieux) {
        notifier(`Dossier actif sélectionné : ${c.nom} ${c.prenom}`, true);
      }
    }

    function libelleCandidatParId(candId) {
      const c = dictionnaireCandidats[candId];
      if (!c) return "Candidat sélectionné";
      return `${c.nom} ${c.prenom} (Passeport : ${c.numero_passeport || "non renseigné"})`;
    }

    document.getElementById("btn-rechercher-candidat").addEventListener("click", chargerCandidats);

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
    });

    // -----------------------------------------------------------------------
    // Onglet 3 : Documents & Pièces manquantes (ZÉRO CODE / ZÉRO JSON)
    // -----------------------------------------------------------------------

    async function chargerDocumentsCandidat() {
      if (!candidatActifId) return;
      const rep = await appelApi(`/api/v1/candidats/${candidatActifId}/documents`);
      if (!rep.ok) return;
      const docs = await rep.json();
      const tbody = document.querySelector("#table-documents-candidat tbody");
      tbody.innerHTML = "";
      if (docs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="etat-vide"><strong>Aucune pièce déposée.</strong>Ajoutez un fichier ci-dessus ou générez les pièces spécimens de démonstration.</td></tr>`;
        return;
      }
      docs.forEach((d) => {
        const libellePiece = LIBELLES_PIECES_FR[d.type_piece] || d.type_piece;
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><strong>${echapperHtml(libellePiece)}</strong></td>
          <td>${echapperHtml(d.nom_fichier_origine)}</td>
          <td>${echapperHtml(d.date_expiration || "Non requise")}</td>
          <td>${Math.max(1, Math.round(d.taille_octets / 1024))} Ko</td>
          <td>
            <a class="btn btn-contour btn-sm" href="/api/v1/candidats/${candidatActifId}/documents/${d.id}/telecharger" target="_blank" rel="noopener">Télécharger</a>
            <button class="btn btn-danger btn-sm" type="button" data-suppr="${d.id}">Supprimer</button>
          </td>
        `;
        tr.querySelector("[data-suppr]").addEventListener("click", async () => {
          const rDel = await appelApi(`/api/v1/candidats/${candidatActifId}/documents/${d.id}`, { method: "DELETE" });
          if (rDel.ok) {
            notifier("Pièce supprimée du dossier.", true);
            await chargerDocumentsCandidat();
            await verifierCompletudeDossier();
          }
        });
        tbody.appendChild(tr);
      });
    }

    function formaterCarteCompletude(comp) {
      if (!comp || !comp.pieces) return "";
      const piecesManquantes = comp.pieces.filter((p) => p.statut !== "valide" && p.obligatoire);
      const piecesFacultativesManquantes = comp.pieces.filter((p) => p.statut !== "valide" && !p.obligatoire);
      const piecesValides = comp.pieces.filter((p) => p.statut === "valide");
      const champsManquants = (comp.champs_candidat_manquants || []).map((ch) => LIBELLES_CHAMPS_FR[ch] || ch);

      let html = `<div class="carte" style="margin-bottom:0;">`;
      html += `<div style="display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:10px;">
        <h4 style="margin:0; font-size:1.02rem;">${echapperHtml(comp.libelle_demarche)}</h4>
        <span class="badge ${comp.pret_pour_prerequis ? 'badge-ok' : 'badge-err'}">
          ${comp.pret_pour_prerequis ? "Dossier complet" : "Pièces manquantes"}
        </span>
      </div>`;

      if (piecesManquantes.length === 0 && champsManquants.length === 0) {
        html += `<div class="notif notif-ok" style="margin-bottom:10px;">Toutes les pièces justificatives obligatoires et les informations du candidat sont complètes et valides.</div>`;
      } else {
        if (piecesManquantes.length > 0) {
          html += `<p style="margin:6px 0 4px 0; color:var(--rouge-danger); font-weight:700;">Pièces obligatoires manquantes ou à corriger (${piecesManquantes.length}) :</p><ul class="liste-propre">`;
          piecesManquantes.forEach((p) => {
            let precision = "";
            if (p.statut === "expiree") precision = " — Document expiré";
            else if (p.statut === "validite_insuffisante") precision = " — " + (p.detail || "Validité restante insuffisante");
            else if (p.statut === "expiration_non_renseignee") precision = " — Date d'expiration à renseigner";
            html += `<li><strong>${echapperHtml(p.libelle)}</strong>${echapperHtml(precision)}</li>`;
          });
          html += `</ul>`;
        }
        if (champsManquants.length > 0) {
          html += `<p style="margin:6px 0 4px 0; color:var(--orange-alerte); font-weight:700;">Informations à compléter dans la fiche candidat :</p><ul class="liste-propre">`;
          champsManquants.forEach((lib) => {
            html += `<li>${echapperHtml(lib)}</li>`;
          });
          html += `</ul>`;
        }
      }

      if (piecesValides.length > 0) {
        html += `<p style="margin:8px 0 4px 0; color:var(--vert-succes); font-weight:700;">Pièces déjà déposées et valides (${piecesValides.length}) :</p><ul class="liste-propre">`;
        piecesValides.forEach((p) => {
          const expTxt = p.date_expiration ? ` (valide jusqu'au ${p.date_expiration})` : "";
          html += `<li class="ok">${echapperHtml(p.libelle)}${echapperHtml(expTxt)}</li>`;
        });
        html += `</ul>`;
      }

      if (piecesFacultativesManquantes.length > 0) {
        html += `<p style="margin:8px 0 4px 0; color:var(--texte-secondaire); font-weight:600;">Pièces complémentaires recommandées (facultatives) :</p><ul class="liste-propre">`;
        piecesFacultativesManquantes.forEach((p) => {
          html += `<li>${echapperHtml(p.libelle)}</li>`;
        });
        html += `</ul>`;
      }

      html += `</div>`;
      return html;
    }

    async function verifierCompletudeDossier() {
      if (!candidatActifId) return notifier("Choisissez d'abord un dossier dans « Étudiants et fiches ».", false);
      await chargerListeDemarches();
      const reponses = await Promise.all(
        listeDemarches.map((d) => appelApi(`/api/v1/candidats/${candidatActifId}/completude/${encodeURIComponent(d.code)}`))
      );
      let cartes = "";
      for (const r of reponses) {
        const donnees = r.ok ? await r.json() : null;
        cartes += formaterCarteCompletude(donnees);
      }
      const zone = document.getElementById("zone-completude");
      zone.innerHTML = `<div class="grille-2">${cartes}</div>`;
    }

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
      const rep = await appelApi(`/api/v1/candidats/${candidatActifId}/documents`, {
        method: "POST",
        body: fd,
      });
      if (rep.ok) {
        const doc = await rep.json();
        const libellePiece = LIBELLES_PIECES_FR[doc.type_piece] || doc.type_piece;
        notifier(`Pièce « ${libellePiece} » chiffrée et enregistrée avec succès.`, true);
        await chargerDocumentsCandidat();
        await verifierCompletudeDossier();
      } else {
        const err = await rep.json();
        notifier(messageErreurApi(err, "Le fichier a été refusé : utilisez un PDF, PNG ou JPEG de 10 Mo maximum."), false);
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

    function afficherEvaluationEnTexte(data) {
      const score = data.pourcentage_acceptation_estime ?? 0;
      const libelleNiveau = LIBELLES_SOLIDITE_FR[data.niveau_solidite] || data.niveau_solidite;
      const couleurBarre = score >= 75 ? "var(--bon)" : score >= 50 ? "var(--alerte)" : "var(--critique)";

      let html = `
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:10px;">
          <div>
            <h4 style="margin:0; font-size:1.1rem;">${echapperHtml(data.libelle_demarche)}</h4>
            <div style="color:var(--texte-secondaire); font-size:0.9rem; margin-top:2px;">
              Niveau du dossier : <strong>${echapperHtml(libelleNiveau)}</strong>
            </div>
          </div>
          <div style="text-align:right;">
            <span style="font-size:2rem; font-weight:800; color:${couleurBarre};">${score} %</span>
            <div style="font-size:0.8rem; color:var(--texte-secondaire);">Score d'acceptation estimé</div>
          </div>
        </div>
        <div class="barre-progression">
          <div class="barre-progression-remplie" style="width:${score}%; background:${couleurBarre};"></div>
        </div>
        <div class="banniere-regle" style="margin-top:12px;">
          <strong>Action prioritaire recommandée :</strong> ${echapperHtml(data.meilleure_action_recommandee)}
        </div>
      `;

      if (data.criteres && data.criteres.length > 0) {
        html += `<h4 style="margin:14px 0 8px 0;">Détail du calcul sur 100 points :</h4><ul class="liste-propre">`;
        data.criteres.forEach((c) => {
          html += `<li><strong>${echapperHtml(c.libelle)} : ${c.points_obtenus} / ${c.points_max} points</strong> — ${echapperHtml(c.commentaire)}</li>`;
        });
        html += `</ul>`;
      }

      if (data.risques_et_blocages && data.risques_et_blocages.length > 0) {
        html += `<h4 style="margin:14px 0 6px 0; color:var(--rouge-danger);">Points bloquants ou pièces manquantes à corriger :</h4><ul class="liste-propre">`;
        data.risques_et_blocages.forEach((r) => {
          html += `<li>${echapperHtml(r)}</li>`;
        });
        html += `</ul>`;
      }

      if (data.points_forts && data.points_forts.length > 0) {
        html += `<h4 style="margin:14px 0 6px 0; color:var(--vert-succes);">Points forts du dossier :</h4><ul class="liste-propre">`;
        data.points_forts.forEach((pf) => {
          html += `<li class="ok">${echapperHtml(pf)}</li>`;
        });
        html += `</ul>`;
      }

      if (data.actions_prioritaires && data.actions_prioritaires.length > 0) {
        html += `<h4 style="margin:14px 0 6px 0;">Plan d'action recommandé :</h4><ol class="liste-propre">`;
        data.actions_prioritaires.forEach((act) => {
          html += `<li>${echapperHtml(act)}</li>`;
        });
        html += `</ol>`;
      }

      if (data.veille_reglementaire && data.veille_reglementaire.length > 0) {
        html += `<h4 style="margin:14px 0 6px 0;">Règles officielles et prérequis applicables :</h4><ul class="liste-propre">`;
        data.veille_reglementaire.forEach((v) => {
          html += `<li><strong>${echapperHtml(v.titre)}</strong> (${echapperHtml(v.reference)}) : ${echapperHtml(v.resume)}</li>`;
        });
        html += `</ul>`;
      }

      html += `<p style="font-size:0.82rem; color:var(--texte-secondaire); margin-top:12px; margin-bottom:0;"><em>${echapperHtml(data.avertissement)}</em></p>`;
      document.getElementById("zone-score-acceptation").innerHTML = html;
    }

    document.getElementById("btn-calculer-score").addEventListener("click", async () => {
      if (!candidatActifId) return notifier("Choisissez d'abord un dossier dans « Étudiants et fiches ».", false);
      const dem = document.getElementById("eval-demarche").value;
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
    });

    function formaterMessageDiscussionHtml(texteBrut) {
      const lignes = String(texteBrut || "").split("\\n");
      return lignes
        .map((l) => echapperHtml(l.replace(/^#+\\s*/, "").replace(/\\*\\*/g, "").replace(/`/g, "")))
        .join("<br/>");
    }

    function afficherListeMessagesDiscussion(messages) {
      const fil = document.getElementById("fil-discussion");
      if (!messages || messages.length === 0) {
        fil.innerHTML = `<div style="color:var(--texte-secondaire); font-size:0.9rem;">Aucun message dans cette discussion. Posez votre première question ci-dessous.</div>`;
        return;
      }
      fil.innerHTML = "";
      messages.forEach((m) => {
        const estUtilisateur = m.auteur === "utilisateur" || m.auteur === "operateur";
        const texteMsg = m.contenu || m.message || "";
        const scoreMsg = m.score_solidite_pourcent ?? m.score_instantane ?? "-";
        const div = document.createElement("div");
        div.className = "msg " + (estUtilisateur ? "msg-op" : "msg-ia");
        div.innerHTML =
          `<div style="margin-bottom:4px;"><strong>${estUtilisateur ? "Vous (Opérateur du bureau)" : "Assistant Conseiller Réglementaire"}</strong> ` +
          `<span class="badge">${scoreMsg} % d'acceptation</span></div>` +
          `<div>${formaterMessageDiscussionHtml(texteMsg)}</div>`;
        fil.appendChild(div);
      });
      fil.scrollTop = fil.scrollHeight;
    }

    async function chargerHistoriqueDiscussion() {
      if (!candidatActifId) return;
      const code_demarche = document.getElementById("eval-demarche").value;
      const rHisto = await appelApi(
        `/api/v1/candidats/${candidatActifId}/discussion?code_demarche=${encodeURIComponent(code_demarche)}`
      );
      if (rHisto.ok) {
        const messages = await rHisto.json();
        afficherListeMessagesDiscussion(messages);
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
      btn.textContent = "Analyse en cours...";
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
        btn.textContent = "Envoyer au Conseiller";
      }
    }

    function poserQuestionRapide(texte) {
      document.getElementById("msg-discussion").value = texte;
      envoyerQuestionConseiller();
    }

    document.getElementById("btn-envoyer-discussion").addEventListener("click", envoyerQuestionConseiller);
    document.getElementById("eval-demarche").addEventListener("change", chargerHistoriqueDiscussion);

"""
