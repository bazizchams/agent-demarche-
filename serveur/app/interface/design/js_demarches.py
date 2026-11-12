"""JavaScript de l'interface : Pilotage du navigateur (Campus France, IRCC), centre de validation, audit, paramètres.

Extrait tel quel de l'ancien `routeur_interface.py` : chaîne Python non brute, les doubles
antislash y sont voulus (échappements Python) et leur nombre est verrouillé par les tests.
"""

from __future__ import annotations

JS_DEMARCHES = """
    // -----------------------------------------------------------------------
    // Onglets 5 & 6 : Campus France & IRCC — Pilotage Navigateur & Tâches
    // -----------------------------------------------------------------------

    function formaterCompteRenduPilotageHtml(res) {
      let html = `
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:10px;">
          <div>
            <strong style="font-size:1.05rem;">${echapperHtml(res.titre_page || "Navigateur de l'Agent")}</strong>
            <div style="font-size:0.84rem; color:var(--texte-secondaire);">Adresse ouverte : ${echapperHtml(res.url_courante)}</div>
          </div>
          <span class="badge ${res.succes ? 'badge-ok' : 'badge-warn'}">
            ${res.succes ? "Action exécutée par l'Agent" : "Intervention humaine requise"}
          </span>
        </div>
        <div class="notif ${res.succes ? 'notif-ok' : 'notif-err'}" style="margin-bottom:10px;">
          ${echapperHtml(res.resume_francais)}
        </div>
      `;

      if (res.statut_tache) {
        const libStatut = LIBELLES_STATUT_TACHE_FR[res.statut_tache] || res.statut_tache;
        const classeBadgeStatut = classeBadgeStatutTache(res.statut_tache);
        html += `<p style="margin:6px 0;"><strong>Statut du dossier :</strong> <span class="badge ${classeBadgeStatut}">${echapperHtml(libStatut)}</span></p>`;
      }

      if (res.pieces_manquantes_tache && res.pieces_manquantes_tache.length > 0) {
        html += `<div class="banniere-regle" style="margin:8px 0;">
          <strong>Dossier en pause (pièces justificatives à téléverser avant passage au Centre de validation humaine) :</strong>
          <ul class="liste-propre" style="margin:6px 0;">
            ${res.pieces_manquantes_tache.map((tp) => `<li>${echapperHtml(LIBELLES_PIECES_FR[tp] || tp)}</li>`).join("")}
          </ul>
          <button class="btn btn-succes" type="button" onclick="completerPiecesSpecimensEtRelancer('${echapperHtml(res.code_demarche)}')">
            Déposer automatiquement les pièces spécimens de démo et lancer le pré-remplissage complet
          </button>
        </div>`;
      }

      if (res.etapes_realisees && res.etapes_realisees.length > 0) {
        html += `<p style="margin:8px 0 4px 0; font-weight:700;">Actions réalisées dans le navigateur :</p><ul class="liste-propre">`;
        res.etapes_realisees.forEach((et) => {
          html += `<li class="ok">${echapperHtml(et)}</li>`;
        });
        html += `</ul>`;
      }

      if (res.champs_remplis_libelles && res.champs_remplis_libelles.length > 0) {
        html += `<p style="margin:8px 0 4px 0; font-weight:700; color:var(--vert-succes);">Champs pré-remplis automatiquement (${res.champs_remplis_libelles.length}) :</p><ul class="liste-propre">`;
        res.champs_remplis_libelles.forEach((ch) => {
          html += `<li class="ok">${echapperHtml(ch)}</li>`;
        });
        html += `</ul>`;
      }

      if (res.pieces_televersees_libelles && res.pieces_televersees_libelles.length > 0) {
        html += `<p style="margin:8px 0 4px 0; font-weight:700; color:var(--vert-succes);">Pièces justificatives téléversées sur la page (${res.pieces_televersees_libelles.length}) :</p><ul class="liste-propre">`;
        res.pieces_televersees_libelles.forEach((p) => {
          html += `<li class="ok">${echapperHtml(p)}</li>`;
        });
        html += `</ul>`;
      }

      if (res.champs_manquants_libelles && res.champs_manquants_libelles.length > 0) {
        html += `<p style="margin:8px 0 4px 0; font-weight:700; color:var(--orange-alerte);">Informations non renseignées dans la fiche candidat (Règle 4 : aucune valeur inventée) :</p><ul class="liste-propre">`;
        res.champs_manquants_libelles.forEach((m) => {
          html += `<li>${echapperHtml(m)}</li>`;
        });
        html += `</ul>`;
      }

      if (res.avertissements_securite && res.avertissements_securite.length > 0) {
        html += `<p style="margin:8px 0 4px 0; font-weight:700;">Garde-fous de sécurité actifs :</p><ul class="liste-propre">`;
        res.avertissements_securite.forEach((av) => {
          html += `<li>${echapperHtml(av)}</li>`;
        });
        html += `</ul>`;
      }

      if (res.capture_base64) {
        html += `
          <div style="margin-top:12px;">
            <strong>Capture d'écran en direct du navigateur piloté par l'agent :</strong><br/>
            <img class="capture-apercu" src="data:image/png;base64,${res.capture_base64}" alt="Capture d'écran du navigateur" />
          </div>
        `;
      }
      return html;
    }

    async function lancerActionNavigateur(codeDemarche, action, instructionLibre = null) {
      if (!candidatActifId) {
        notifier("Choisissez d'abord un dossier dans « Étudiants et fiches ».", false);
        return;
      }
      const estCf = codeDemarche === "campus_france";
      const cible = document.getElementById(estCf ? "cf-cible-navigateur" : "ircc-cible-navigateur").value;
      const ouvrirVisible = document.getElementById(estCf ? "cf-fenetre-visible" : "ircc-fenetre-visible").checked;
      const zoneId = estCf ? "zone-retour-cf" : "zone-retour-ircc";
      const zone = document.getElementById(zoneId);

      zone.innerHTML = `<div style="font-weight:600; color:var(--bleu-primaire);">L'Agent Navigateur exécute votre demande dans Chromium... Veuillez patienter quelques secondes.</div>`;

      const rep = await appelApi("/api/v1/portails/piloter-navigateur", {
        method: "POST",
        body: JSON.stringify({
          candidat_id: candidatActifId,
          code_demarche: codeDemarche,
          cible: cible,
          action: action,
          instruction_libre: instructionLibre,
          ouvrir_fenetre_visible: ouvrirVisible,
          synchroniser_tache: true,
        }),
      });

      if (rep.ok) {
        const res = await rep.json();
        zone.innerHTML = formaterCompteRenduPilotageHtml(res);
        await rafraichirTableauDeBord();
        notifier(res.resume_francais, res.succes);
      } else {
        const err = await rep.json();
        zone.innerHTML = `<div class="notif notif-err">${echapperHtml(err.detail || "Erreur lors du pilotage du navigateur.")}</div>`;
        notifier(err.detail || "Erreur lors du pilotage du navigateur", false);
      }
    }

    document.getElementById("btn-piloter-cf-instruction").addEventListener("click", () => {
      const inst = document.getElementById("cf-instruction-agent").value.trim();
      lancerActionNavigateur("campus_france", "instruction_libre", inst);
    });

    document.getElementById("btn-piloter-ircc-instruction").addEventListener("click", () => {
      const inst = document.getElementById("ircc-instruction-agent").value.trim();
      lancerActionNavigateur("ircc_permis_etudes", "instruction_libre", inst);
    });

    function formaterTacheEnTexteHtml(tache, codeDemarche) {
      const libStatut = LIBELLES_STATUT_TACHE_FR[tache.statut] || tache.statut;
      const estSuspendue = tache.statut === "suspendue";
      const estAValider = tache.statut === "a_valider";

      let html = `
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:10px;">
          <div>
            <strong>Suivi de la tâche ${codeDemarche === "campus_france" ? "Campus France — Études en France" : "IRCC Canada — Permis d'études"}</strong>
          </div>
          <span class="badge ${classeBadgeStatutTache(tache.statut)}">${echapperHtml(libStatut)}</span>
        </div>
      `;

      if (tache.message_alerte) {
        html += `<div class="banniere-regle">${echapperHtml(tache.message_alerte)}</div>`;
      }

      if (tache.pieces_manquantes && tache.pieces_manquantes.length > 0) {
        html += `<p style="margin:6px 0; color:var(--rouge-danger); font-weight:700;">Pièces justificatives obligatoires à fournir avant l'envoi officiel :</p><ul class="liste-propre">`;
        tache.pieces_manquantes.forEach((tp) => {
          html += `<li>${echapperHtml(LIBELLES_PIECES_FR[tp] || tp)}</li>`;
        });
        html += `</ul>`;
        html += `<p><button class="btn btn-succes" type="button" onclick="completerPiecesSpecimensEtRelancer('${codeDemarche}')">Déposer automatiquement les pièces spécimens de démo et lancer le pré-remplissage par l'Agent</button></p>`;
      }

      if (tache.champs_manquants && tache.champs_manquants.length > 0) {
        html += `<p style="margin:6px 0; color:var(--orange-alerte); font-weight:700;">Informations à compléter dans la fiche candidat :</p><ul class="liste-propre">`;
        tache.champs_manquants.forEach((ch) => {
          html += `<li>${echapperHtml(LIBELLES_CHAMPS_FR[ch] || ch)}</li>`;
        });
        html += `</ul>`;
      }

      if (tache.etapes && tache.etapes.length > 0) {
        html += `<p style="margin:10px 0 4px 0; font-weight:700;">Progression des étapes de la démarche :</p><ol class="liste-propre">`;
        tache.etapes.forEach((e) => {
          const stTxt = e.statut === "terminee" ? "Terminée" : e.statut === "en_cours" ? "En cours" : e.statut === "suspendue" ? "En attente de complétion" : "À faire";
          html += `<li class="etape etape-${echapperHtml(e.statut)}"><strong>${echapperHtml(e.libelle)}</strong> — <em>${stTxt}</em></li>`;
        });
        html += `</ol>`;
      }

      return html;
    }

    async function completerPiecesSpecimensEtRelancer(codeDemarche) {
      if (!candidatActifId) return;
      await appelApi(`/api/v1/candidats/${candidatActifId}/documents/specimens-demo?code_demarche=${encodeURIComponent(codeDemarche)}`, {
        method: "POST",
      });
      await lancerActionNavigateur(codeDemarche, "preremplissage_complet");
    }

    async function creerOuAfficherTacheDemarche(codeDemarche) {
      if (!candidatActifId) return notifier("Choisissez d'abord un dossier dans « Étudiants et fiches ».", false);
      const zoneId = codeDemarche === "campus_france" ? "zone-retour-cf" : "zone-retour-ircc";
      const rep = await appelApi("/api/v1/taches", {
        method: "POST",
        body: JSON.stringify({ candidat_id: candidatActifId, code_demarche: codeDemarche }),
      });
      if (rep.ok) {
        const tache = await rep.json();
        document.getElementById(zoneId).innerHTML = formaterTacheEnTexteHtml(tache, codeDemarche);
        await rafraichirTableauDeBord();
        const libStatut = LIBELLES_STATUT_TACHE_FR[tache.statut] || tache.statut;
        notifier(`Tâche créée : ${libStatut}`, true);
      } else {
        // Si une tâche est déjà ouverte pour ce candidat, on la récupère et on l'affiche clairement
        const rListe = await appelApi(`/api/v1/taches?candidat_id=${candidatActifId}&code_demarche=${codeDemarche}`);
        if (rListe.ok) {
          const pageTaches = await rListe.json();
          if (pageTaches.elements && pageTaches.elements.length > 0) {
            const tacheExistante = pageTaches.elements[0];
            document.getElementById(zoneId).innerHTML = formaterTacheEnTexteHtml(tacheExistante, codeDemarche);
            notifier("Affichage de la tâche en cours pour ce candidat.", true);
            return;
          }
        }
        const err = await rep.json();
        notifier(err.detail || "Impossible de créer la tâche", false);
      }
    }

    document.getElementById("btn-creer-tache-cf").addEventListener("click", () => creerOuAfficherTacheDemarche("campus_france"));
    document.getElementById("btn-creer-tache-ircc").addEventListener("click", () => creerOuAfficherTacheDemarche("ircc_permis_etudes"));

    // -----------------------------------------------------------------------
    // Onglet 7 : Centre de validation humaine (Règle 1 — Cartes interactives)
    // -----------------------------------------------------------------------

    function formaterRecapitulatifValidationHtml(recap) {
      if (!recap || typeof recap !== "object") return "";
      let bloc = `<div class="panneau-texte" style="margin:8px 0;">`;
      if (recap.url_courante) {
        bloc += `<div style="font-size:0.86rem; color:var(--texte-secondaire); margin-bottom:6px;"><strong>Portail contrôlé :</strong> ${echapperHtml(recap.url_courante)}</div>`;
      }
      if (recap.champs_remplis && recap.champs_remplis.length > 0) {
        bloc += `<div style="margin:4px 0;"><strong style="color:var(--vert-succes);">Champs pré-remplis vérifiés (${recap.champs_remplis.length}) :</strong> ${recap.champs_remplis.map((c) => echapperHtml(c)).join(" • ")}</div>`;
      }
      if (recap.pieces_televersees && recap.pieces_televersees.length > 0) {
        bloc += `<div style="margin:4px 0;"><strong style="color:var(--vert-succes);">Pièces téléversées (${recap.pieces_televersees.length}) :</strong> ${recap.pieces_televersees.map((p) => echapperHtml(p)).join(" • ")}</div>`;
      }
      bloc += `</div>`;
      return bloc;
    }

    async function rafraichirValidationsHumaines() {
      if (Object.keys(dictionnaireCandidats).length === 0) {
        await chargerCandidats();
      }
      const rep = await appelApi("/api/v1/validations/en-attente");
      if (!rep.ok) return;
      const data = await rep.json();
      const zone = document.getElementById("liste-centre-validation");

      if (data.total_a_valider === 0 && data.total_suspendues === 0) {
        zone.innerHTML = `<div class="carte etat-vide"><strong>Rien à valider pour le moment.</strong>Les dossiers pré-remplis par l'agent apparaîtront ici avant tout envoi officiel.</div>`;
        return;
      }

      let html = "";

      if (data.taches_a_valider && data.taches_a_valider.length > 0) {
        html += `<h3 style="margin-top:0; color:var(--vert-succes);">Dossiers pré-remplis prêts pour validation humaine (${data.total_a_valider})</h3>`;
        data.taches_a_valider.forEach((t) => {
          const nomDem = t.code_demarche === "campus_france" ? "Campus France — Études en France" : "IRCC Canada — Permis d'études";
          const nomCand = libelleCandidatParId(t.candidat_id);
          html += `
            <div class="carte carte-action">
              <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                <div>
                  <strong>${echapperHtml(nomDem)}</strong>
                  <div style="font-size:0.86rem; color:var(--texte-secondaire);">Candidat : ${echapperHtml(nomCand)}</div>
                </div>
                <span class="badge badge-info">Validation en attente</span>
              </div>
              <p style="margin:8px 0;">${echapperHtml(t.message_alerte || "Pré-remplissage terminé et arrêté avant le bouton final.")}</p>
              ${formaterRecapitulatifValidationHtml(t.recapitulatif_remplissage)}
              ${t.capture_controle_disponible ? `
                <div style="margin:10px 0;">
                  <div style="margin-bottom:6px;">
                    <a class="btn btn-contour btn-sm" href="/api/v1/taches/${t.id}/capture-controle" target="_blank" rel="noopener">Ouvrir la capture de contrôle en plein écran</a>
                  </div>
                  <img class="capture-apercu" src="/api/v1/taches/${t.id}/capture-controle" alt="Capture d'écran de contrôle avant soumission" />
                </div>
              ` : ""}
              <div style="display:flex; gap:8px; flex-wrap:wrap; margin-top:8px;">
                <button class="btn btn-primaire" type="button" onclick="validerDossierHumainement('${t.id}')">Valider ce dossier (règle 1)</button>
                <button class="btn btn-secondaire" type="button" onclick="rejeterValidationHumaine('${t.id}')">Demander une correction avant validation</button>
                <button class="btn btn-danger" type="button" onclick="annulerTacheDossier('${t.id}')">Annuler la tâche</button>
              </div>
            </div>
          `;
        });
      }

      if (data.taches_suspendues && data.taches_suspendues.length > 0) {
        html += `<h3 style="margin-top:14px; color:var(--orange-alerte);">Dossiers en pause (${data.total_suspendues})</h3>`;
        data.taches_suspendues.forEach((t) => {
          const nomDem = t.code_demarche === "campus_france" ? "Campus France — Études en France" : "IRCC Canada — Permis d'études";
          const nomCand = libelleCandidatParId(t.candidat_id);
          const piecesTxt = (t.pieces_manquantes || []).map((p) => LIBELLES_PIECES_FR[p] || p).join(", ");
          html += `
            <div class="carte carte-action attente">
              <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                <div>
                  <strong>${echapperHtml(nomDem)}</strong>
                  <div style="font-size:0.86rem; color:var(--texte-secondaire);">Candidat : ${echapperHtml(nomCand)}</div>
                </div>
                <span class="badge badge-warn">En pause</span>${t.motif_suspension === "action_utilisateur_portail" ? ' <span class="badge badge-warn">CAPTCHA ou code de sécurité</span>' : ""}
              </div>
              <p style="margin:8px 0;">${echapperHtml(t.message_alerte || "")}</p>
              ${piecesTxt ? `<p style="margin:4px 0; color:var(--rouge-danger);"><strong>Pièces manquantes :</strong> ${echapperHtml(piecesTxt)}</p>` : ""}
              <div style="display:flex; gap:8px; flex-wrap:wrap; margin-top:8px;">
                ${piecesTxt ? `<button class="btn btn-succes" type="button" onclick="completerPiecesEtRelancerDepuisValidation('${t.id}', '${t.candidat_id}', '${t.code_demarche}')">Déposer les pièces spécimens de démo &amp; Pré-remplir par l'Agent</button>` : ""}
                ${t.motif_suspension === "action_utilisateur_portail" ? `<button class="btn btn-contour" type="button" onclick="allerVersVue('vue-navigateur-serveur')">Ouvrir le navigateur de l'agent (CAPTCHA / code de sécurité)</button>` : ""}
                <button class="btn btn-secondaire" type="button" onclick="reprendreTacheDossier('${t.id}')">Reprendre la tâche</button>
                <button class="btn btn-danger" type="button" onclick="annulerTacheDossier('${t.id}')">Annuler la tâche</button>
              </div>
            </div>
          `;
        });
      }

      zone.innerHTML = html;
    }

    async function validerDossierHumainement(tacheId) {
      const rep = await appelApi(`/api/v1/taches/${tacheId}/valider`, {
        method: "POST",
        body: JSON.stringify({
          confirmation_humaine_explicite: true,
          commentaire: "Vérifié et validé par l'opérateur humain au Centre de validation.",
        }),
      });
      if (rep.ok) {
        notifier("Dossier validé humainement avec succès (Règle 1).", true);
        await rafraichirValidationsHumaines();
        await rafraichirTableauDeBord();
      } else {
        const err = await rep.json();
        notifier(err.detail || "Erreur lors de la validation", false);
      }
    }

    async function rejeterValidationHumaine(tacheId) {
      const rep = await appelApi(`/api/v1/taches/${tacheId}/rejeter`, {
        method: "POST",
        body: JSON.stringify({
          motif_rejet: "Correction demandée par l'opérateur humain avant la soumission finale.",
        }),
      });
      if (rep.ok) {
        notifier("Dossier remis en pause pour correction avant validation finale.", true);
        await rafraichirValidationsHumaines();
        await rafraichirTableauDeBord();
      } else {
        const err = await rep.json();
        notifier(err.detail || "Erreur lors du renvoi en correction", false);
      }
    }

    async function completerPiecesEtRelancerDepuisValidation(tacheId, candId, codeDemarche) {
      await appelApi(`/api/v1/candidats/${candId}/documents/specimens-demo?code_demarche=${encodeURIComponent(codeDemarche)}`, {
        method: "POST",
      });
      await appelApi(`/api/v1/portails/piloter-navigateur`, {
        method: "POST",
        body: JSON.stringify({
          candidat_id: candId,
          code_demarche: codeDemarche,
          cible: codeDemarche === "campus_france" ? "demo_campus_france" : "demo_ircc",
          action: "preremplissage_complet",
          ouvrir_fenetre_visible: false,
          synchroniser_tache: true,
        }),
      });
      notifier("Pièces spécimens déposées et dossier pré-rempli par l'Agent — prêt pour validation humaine !", true);
      await rafraichirValidationsHumaines();
      await rafraichirTableauDeBord();
    }

    async function reprendreTacheDossier(tacheId) {
      const rep = await appelApi(`/api/v1/taches/${tacheId}/reprendre`, { method: "POST" });
      if (rep.ok) {
        notifier("Tâche remise en file d'attente.", true);
        await rafraichirValidationsHumaines();
        await rafraichirTableauDeBord();
      } else {
        const err = await rep.json();
        notifier(err.detail || "Complétez d'abord les pièces manquantes avant de reprendre la tâche.", false);
      }
    }

    async function annulerTacheDossier(tacheId) {
      const rep = await appelApi(`/api/v1/taches/${tacheId}/annuler`, { method: "POST" });
      if (rep.ok) {
        notifier("Tâche annulée.", true);
        await rafraichirValidationsHumaines();
        await rafraichirTableauDeBord();
      }
    }

    document.getElementById("btn-rafraichir-validations").addEventListener("click", rafraichirValidationsHumaines);

    // -----------------------------------------------------------------------
    // Onglet 8 : Historique d'audit (ZÉRO CODE BRUT)
    // -----------------------------------------------------------------------

    async function rafraichirJournalAudit() {
      const rep = await appelApi("/api/v1/audit?taille=30");
      if (!rep.ok) return;
      const data = await rep.json();
      const tbody = document.querySelector("#table-audit tbody");
      tbody.innerHTML = "";
      if (data.elements.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="etat-vide"><strong>Aucune opération enregistrée.</strong>Le journal se remplit au fil des actions du bureau.</td></tr>`;
        return;
      }
      data.elements.forEach((e) => {
        const detailsObj = e.details || {};
        const resumeDetails = Object.entries(detailsObj)
          .map(([k, v]) => `${k.replace(/_/g, " ")} : ${v}`)
          .join(" | ") || "Opération standard";
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><small>${echapperHtml(e.horodatage)}</small></td>
          <td><strong>${echapperHtml(e.action)}</strong></td>
          <td><span class="badge ${e.resultat === 'succes' ? 'badge-ok' : 'badge-err'}">${echapperHtml(e.resultat)}</span></td>
          <td>${echapperHtml(e.ressource_type || "-")}</td>
          <td>${echapperHtml(resumeDetails)}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    document.getElementById("btn-rafraichir-audit").addEventListener("click", rafraichirJournalAudit);

    // -----------------------------------------------------------------------
    // Onglet 9 : Paramètres, Agents locaux & Sauvegardes (ZÉRO CODE BRUT)
    // -----------------------------------------------------------------------

    document.getElementById("btn-enroler-agent").addEventListener("click", async () => {
      const nom_machine = document.getElementById("nom-machine-agent").value.trim();
      const rep = await appelApi("/api/v1/agents-locaux", {
        method: "POST",
        body: JSON.stringify({ nom_machine }),
      });
      if (rep.ok) {
        const data = await rep.json();
        const zone = document.getElementById("zone-jeton-agent");
        zone.innerHTML = `
          <div class="notif notif-ok" style="margin-bottom:8px;">Poste Agent Local « ${echapperHtml(data.agent.nom_machine)} » enrôlé avec succès.</div>
          <p style="margin:4px 0;"><strong>Clé d'authentification de l'Agent Local (à conserver précieusement) :</strong><br/>
          <input type="text" readonly value="${echapperHtml(data.jeton_secret)}" style="width:100%; margin-top:4px; font-weight:600;" /></p>
        `;
        zone.classList.remove("cache");
        await rafraichirTableauDeBord();
        notifier("Poste Agent Local enrôlé avec succès.", true);
      }
    });

    document.getElementById("btn-creer-sauvegarde").addEventListener("click", async () => {
      const rep = await appelApi("/api/v1/sauvegardes", { method: "POST" });
      const data = await rep.json();
      const zone = document.getElementById("zone-sauvegardes-abo");
      if (rep.ok) {
        zone.innerHTML = `
          <div class="notif notif-ok" style="margin-bottom:8px;">Sauvegarde chiffrée AES-256-GCM créée avec succès.</div>
          <ul class="liste-propre">
            <li><strong>Nom de l'archive chiffrée :</strong> ${echapperHtml(data.nom_fichier)}</li>
            <li><strong>Nombre de dossiers candidats sauvegardés :</strong> ${data.nb_candidats}</li>
            <li><strong>Nombre de pièces justificatives sauvegardées :</strong> ${data.nb_documents}</li>
            <li><strong>Taille de l'archive :</strong> ${Math.max(1, Math.round(data.taille_octets / 1024))} Ko</li>
          </ul>
        `;
        notifier(`Sauvegarde chiffrée créée : ${data.nom_fichier}`, true);
      } else {
        zone.innerHTML = `<div class="notif notif-err">${echapperHtml(data.detail || "Erreur lors de la sauvegarde")}</div>`;
      }
    });

    document.getElementById("btn-voir-abonnement").addEventListener("click", async () => {
      const [rAbo, rPort] = await Promise.all([
        appelApi("/api/v1/abonnement"),
        appelApi("/api/v1/portails"),
      ]);
      const abo = rAbo.ok ? await rAbo.json() : {};
      const portails = rPort.ok ? await rPort.json() : [];
      let html = `
        <h4 style="margin-top:0;">Abonnement SaaS du Bureau</h4>
        <ul class="liste-propre">
          <li><strong>Forfait actif :</strong> ${echapperHtml(abo.forfait || "Starter")}</li>
          <li><strong>Quota mensuel de dossiers :</strong> ${abo.nb_dossiers_actifs ?? 0} / ${abo.quota_dossiers_mensuels ?? 25} dossiers actifs</li>
          <li><strong>Durée de conservation RGPD / Loi 18-07 :</strong> ${abo.duree_conservation_jours ?? 365} jours</li>
        </ul>
        <h4>Statut des modules portails (Règle 6 &amp; Règle 7)</h4>
        <ul class="liste-propre">
      `;
      portails.forEach((p) => {
        html += `<li><strong>${echapperHtml(p.nom_portail)}</strong> — Statut d'homologation : <span class="badge">${echapperHtml(p.statut_test_regle6)}</span> (${p.nb_etapes_automatisation} étapes automatisées)</li>`;
      });
      html += `</ul>`;
      document.getElementById("zone-sauvegardes-abo").innerHTML = html;
    });

"""
