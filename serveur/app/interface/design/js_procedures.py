"""JavaScript de l'interface : Procédures du bureau, assistant IA et liste des démarches.

Extrait tel quel de l'ancien `routeur_interface.py` : chaîne Python non brute, les doubles
antislash y sont voulus (échappements Python) et leur nombre est verrouillé par les tests.
"""

from __future__ import annotations

JS_PROCEDURES = """
    // ===== Procédures (démarches) du bureau : liste + éditeur =====
    let procedureEditee = null; // code de la procédure modifiée, ou null en création
    let definitionOriginaleProcedure = null; // définition complète telle que reçue (pour ne rien perdre à l'enregistrement)
    const CLES_GEREES_PROCEDURE = ["code", "libelle", "description", "seuil_fonds_recommande_eur", "champs_candidat_requis", "pieces_requises", "etapes_tache", "veille_reglementaire"];

    function clesAvanceesProcedure(def) {
      return Object.keys(def || {}).filter((k) => !CLES_GEREES_PROCEDURE.includes(k));
    }

    function afficherChampsAvances(def) {
      const cles = clesAvanceesProcedure(def);
      const liste = document.getElementById("liste-champs-avances");
      liste.innerHTML = "";
      cles.forEach((k) => {
        const li = document.createElement("li");
        const fort = document.createElement("strong");
        fort.textContent = k;
        let apercu = "";
        try { apercu = JSON.stringify(def[k]); } catch (e) { apercu = ""; }
        if (apercu && apercu.length > 160) apercu = apercu.slice(0, 160) + "...";
        li.appendChild(fort);
        li.appendChild(document.createTextNode(apercu ? " : " + apercu : ""));
        liste.appendChild(li);
      });
      document.getElementById("encart-champs-avances").classList.toggle("cache", cles.length === 0);
    }

    function masquerBlocIaEditeur() {
      document.getElementById("bloc-ia-editeur").classList.add("cache");
      document.getElementById("liste-avertissements-ia").innerHTML = "";
    }

    function estAdministrateur() {
      return roleActif === "administrateur";
    }

    function messageErreurApi(err, defaut) {
      if (!err) return defaut;
      if (typeof err.detail === "string") return err.detail;
      if (Array.isArray(err.detail)) {
        return err.detail.map((e) => (e.loc ? e.loc.slice(1).join(" > ") + " : " : "") + e.msg).join(" ; ");
      }
      return err.message || defaut;
    }

    function retourProcedure(msg, ok) {
      const z = document.getElementById("zone-retour-procedure");
      z.textContent = msg;
      z.style.borderColor = ok ? "var(--bon)" : "var(--critique)";
      z.classList.remove("cache");
    }

    async function chargerProcedures() {
      const tbody = document.querySelector("#table-procedures tbody");
      document.getElementById("btn-nouvelle-procedure").classList.toggle("cache", !estAdministrateur());
      document.getElementById("carte-generation-ia").classList.toggle("cache", !estAdministrateur());
      const rep = await appelApi("/api/v1/demarches/gestion");
      if (!rep.ok) {
        tbody.innerHTML = `<tr><td colspan="5" class="etat-vide">Connectez-vous (menu de gauche) pour afficher les procédures.</td></tr>`;
        return;
      }
      const liste = await rep.json();
      tbody.innerHTML = "";
      if (liste.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="etat-vide">Aucune procédure disponible pour votre bureau.</td></tr>`;
        return;
      }
      liste.forEach((d) => {
        const tr = document.createElement("tr");
        const origine = d.source === "bureau"
          ? `<span class="badge badge-ok">Votre bureau</span>`
          : `<span class="badge">Base commune</span>`;
        tr.innerHTML = `
          <td><code>${echapperHtml(d.code)}</code></td>
          <td>${echapperHtml(d.libelle)}</td>
          <td>${origine}</td>
          <td>${d.source === "bureau" ? d.version : "-"}</td>
          <td></td>`;
        const cellule = tr.lastElementChild;
        const btnOuvrir = document.createElement("button");
        btnOuvrir.type = "button";
        btnOuvrir.className = "btn btn-secondaire btn-sm";
        btnOuvrir.textContent = estAdministrateur() ? "Modifier" : "Consulter";
        btnOuvrir.addEventListener("click", () => ouvrirEditeurProcedure(d.code));
        cellule.appendChild(btnOuvrir);
        if (estAdministrateur()) {
          const btnMasquer = document.createElement("button");
          btnMasquer.type = "button";
          btnMasquer.className = "btn btn-danger btn-sm";
          btnMasquer.textContent = "Masquer";
          btnMasquer.addEventListener("click", () => masquerProcedure(d.code, d.libelle));
          cellule.appendChild(btnMasquer);
        }
        tbody.appendChild(tr);
      });
    }

    async function masquerProcedure(code, libelle) {
      if (!window.confirm("Masquer la procédure « " + libelle + " » pour votre bureau ? Les autres bureaux ne sont pas concernés. Vous pourrez la réactiver en la modifiant.")) return;
      const rep = await appelApi("/api/v1/demarches/" + encodeURIComponent(code), { method: "DELETE" });
      if (rep.ok) {
        notifier("Procédure masquée pour votre bureau.", true);
        fermerEditeurProcedure();
        await chargerProcedures();
      } else {
        const err = await rep.json().catch(() => null);
        notifier(messageErreurApi(err, "Impossible de masquer la procédure."), false);
      }
    }

    function creerLigne(contenuHtml) {
      const div = document.createElement("div");
      div.className = "ligne-proc";
      div.innerHTML = contenuHtml + `<button type="button" class="btn btn-danger btn-sm" style="margin:0;" data-retirer="1">Retirer</button>`;
      div.querySelector("[data-retirer]").addEventListener("click", () => div.remove());
      return div;
    }

    function ajouterLignePiece(p) {
      const v = Object.assign({ type_piece: "", libelle: "", obligatoire: true, exige_date_expiration: false, validite_minimale_jours: 0 }, p || {});
      const div = creerLigne(`
        <input type="text" class="p-type" list="liste-types-pieces" placeholder="type (ex: passeport)" value="${echapperHtml(v.type_piece)}" />
        <input type="text" class="p-libelle large" placeholder="Libellé affiché (ex: Passeport en cours de validité)" value="${echapperHtml(v.libelle)}" />
        <label style="font-weight:400;"><input type="checkbox" class="p-oblig" ${v.obligatoire ? "checked" : ""} /> Obligatoire</label>
        <label style="font-weight:400;"><input type="checkbox" class="p-exp" ${v.exige_date_expiration ? "checked" : ""} /> Date d'expiration exigée</label>
        <input type="number" class="p-valid" min="0" style="max-width:150px;" title="Validité minimale restante (jours)" placeholder="Validité min. (jours)" value="${Number(v.validite_minimale_jours) || 0}" />`);
      document.getElementById("proc-pieces").appendChild(div);
    }

    function ajouterLigneEtape(e) {
      const v = Object.assign({ code: "", libelle: "" }, e || {});
      const div = creerLigne(`
        <input type="text" class="e-code" placeholder="code (ex: verification_prerequis)" value="${echapperHtml(v.code)}" />
        <input type="text" class="e-libelle large" placeholder="Libellé de l'étape" value="${echapperHtml(v.libelle)}" />`);
      document.getElementById("proc-etapes").appendChild(div);
    }

    function ajouterLigneVeille(p) {
      const v = Object.assign({ titre: "", resume: "", reference: "" }, p || {});
      const div = creerLigne(`
        <input type="text" class="v-titre" placeholder="Titre" value="${echapperHtml(v.titre)}" />
        <input type="text" class="v-resume large" placeholder="Résumé de la règle (1000 caractères max)" value="${echapperHtml(v.resume)}" />
        <input type="text" class="v-ref" placeholder="Référence officielle" value="${echapperHtml(v.reference)}" />`);
      document.getElementById("proc-veille").appendChild(div);
    }

    function construireCasesChamps(coches) {
      const zone = document.getElementById("proc-champs");
      zone.innerHTML = "";
      const tous = Object.keys(LIBELLES_CHAMPS_FR);
      coches.forEach((c) => { if (!tous.includes(c)) tous.push(c); });
      tous.forEach((cle) => {
        const lab = document.createElement("label");
        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.value = cle;
        cb.checked = coches.includes(cle);
        lab.appendChild(cb);
        lab.appendChild(document.createTextNode(" " + (LIBELLES_CHAMPS_FR[cle] || cle)));
        zone.appendChild(lab);
      });
    }

    function remplirEditeurProcedure(def) {
      definitionOriginaleProcedure = JSON.parse(JSON.stringify(def || {}));
      afficherChampsAvances(definitionOriginaleProcedure);
      document.getElementById("proc-code").value = def.code || "";
      document.getElementById("proc-code").disabled = procedureEditee !== null;
      document.getElementById("proc-libelle").value = def.libelle || "";
      document.getElementById("proc-description").value = def.description || "";
      document.getElementById("proc-seuil").value = def.seuil_fonds_recommande_eur === null || def.seuil_fonds_recommande_eur === undefined ? "" : def.seuil_fonds_recommande_eur;
      construireCasesChamps(def.champs_candidat_requis || []);
      const dl = document.getElementById("liste-types-pieces");
      dl.innerHTML = Object.keys(LIBELLES_PIECES_FR).map((k) => `<option value="${echapperHtml(k)}">${echapperHtml(LIBELLES_PIECES_FR[k])}</option>`).join("");
      document.getElementById("proc-pieces").innerHTML = "";
      (def.pieces_requises || []).forEach(ajouterLignePiece);
      document.getElementById("proc-etapes").innerHTML = "";
      (def.etapes_tache || []).forEach(ajouterLigneEtape);
      document.getElementById("proc-veille").innerHTML = "";
      (def.veille_reglementaire || []).forEach(ajouterLigneVeille);
    }

    function configurerEditeurSelonRole() {
      const admin = estAdministrateur();
      document.getElementById("fs-editeur").disabled = !admin;
      document.getElementById("btn-enregistrer-procedure").classList.toggle("cache", !admin);
      ["btn-ajouter-piece", "btn-ajouter-etape", "btn-ajouter-veille"].forEach((id) => {
        document.getElementById(id).classList.toggle("cache", !admin);
      });
    }

    async function ouvrirEditeurProcedure(code) {
      const rep = await appelApi("/api/v1/demarches/" + encodeURIComponent(code));
      if (!rep.ok) {
        const err = await rep.json().catch(() => null);
        notifier(messageErreurApi(err, "Procédure introuvable."), false);
        return;
      }
      const data = await rep.json();
      procedureEditee = code;
      masquerBlocIaEditeur();
      remplirEditeurProcedure(data.definition);
      configurerEditeurSelonRole();
      document.getElementById("titre-editeur-procedure").textContent =
        (estAdministrateur() ? "Modifier la procédure : " : "Consulter la procédure : ") + data.definition.libelle +
        (data.source === "base" ? " (base commune : l'enregistrement créera la version de votre bureau)" : " (version " + data.version + ")");
      document.getElementById("zone-retour-procedure").classList.add("cache");
      document.getElementById("carte-editeur-procedure").classList.remove("cache");
      document.getElementById("carte-editeur-procedure").scrollIntoView({ behavior: "smooth" });
    }

    function nouvelleProcedure() {
      procedureEditee = null;
      masquerBlocIaEditeur();
      remplirEditeurProcedure({ code: "", libelle: "", champs_candidat_requis: ["nom", "prenom", "numero_passeport"], pieces_requises: [{ type_piece: "passeport", libelle: "Passeport en cours de validité", obligatoire: true, exige_date_expiration: true, validite_minimale_jours: 180 }] });
      configurerEditeurSelonRole();
      document.getElementById("titre-editeur-procedure").textContent = "Nouvelle procédure";
      document.getElementById("zone-retour-procedure").classList.add("cache");
      document.getElementById("carte-editeur-procedure").classList.remove("cache");
      document.getElementById("carte-editeur-procedure").scrollIntoView({ behavior: "smooth" });
    }

    function fermerEditeurProcedure() {
      procedureEditee = null;
      definitionOriginaleProcedure = null;
      masquerBlocIaEditeur();
      document.getElementById("carte-editeur-procedure").classList.add("cache");
    }

    function collecterDefinitionProcedure() {
      const texte = (el, sel) => el.querySelector(sel).value.trim();
      const def = {
        code: document.getElementById("proc-code").value.trim().toLowerCase(),
        libelle: document.getElementById("proc-libelle").value.trim(),
        description: document.getElementById("proc-description").value.trim(),
        champs_candidat_requis: Array.from(document.querySelectorAll("#proc-champs input:checked")).map((c) => c.value),
        pieces_requises: Array.from(document.querySelectorAll("#proc-pieces .ligne-proc")).map((l) => ({
          type_piece: texte(l, ".p-type").toLowerCase(),
          libelle: texte(l, ".p-libelle"),
          obligatoire: l.querySelector(".p-oblig").checked,
          exige_date_expiration: l.querySelector(".p-exp").checked,
          validite_minimale_jours: parseInt(l.querySelector(".p-valid").value || "0", 10) || 0,
        })),
        veille_reglementaire: Array.from(document.querySelectorAll("#proc-veille .ligne-proc")).map((l) => ({
          titre: texte(l, ".v-titre"),
          resume: texte(l, ".v-resume"),
          reference: texte(l, ".v-ref"),
        })),
      };
      const seuil = document.getElementById("proc-seuil").value.trim();
      if (seuil !== "") def.seuil_fonds_recommande_eur = parseInt(seuil, 10);
      const etapes = Array.from(document.querySelectorAll("#proc-etapes .ligne-proc")).map((l) => ({
        code: texte(l, ".e-code").toLowerCase(),
        libelle: texte(l, ".e-libelle"),
      }));
      if (etapes.length > 0) def.etapes_tache = etapes;
      // Champs avancés non gérés par l'éditeur : conservés tels quels (jamais perdus à l'enregistrement)
      clesAvanceesProcedure(definitionOriginaleProcedure).forEach((k) => {
        if (!(k in def)) def[k] = JSON.parse(JSON.stringify(definitionOriginaleProcedure[k]));
      });
      return def;
    }

    async function enregistrerProcedure() {
      const def = collecterDefinitionProcedure();
      const enCreation = procedureEditee === null;
      const rep = await appelApi(
        enCreation ? "/api/v1/demarches" : "/api/v1/demarches/" + encodeURIComponent(procedureEditee),
        { method: enCreation ? "POST" : "PUT", body: JSON.stringify(def) }
      );
      if (rep.ok) {
        const data = await rep.json();
        procedureEditee = data.definition.code;
        definitionOriginaleProcedure = JSON.parse(JSON.stringify(data.definition));
        afficherChampsAvances(definitionOriginaleProcedure);
        masquerBlocIaEditeur();
        document.getElementById("proc-code").disabled = true;
        document.getElementById("titre-editeur-procedure").textContent =
          "Modifier la procédure : " + data.definition.libelle + " (version " + data.version + ")";
        retourProcedure("Procédure enregistrée (version " + data.version + "). Elle est utilisable immédiatement par votre bureau.", true);
        notifier("Procédure « " + data.definition.libelle + " » enregistrée.", true);
        await chargerProcedures();
      } else {
        const err = await rep.json().catch(() => null);
        retourProcedure(messageErreurApi(err, "Enregistrement refusé."), false);
      }
    }

    document.getElementById("btn-rafraichir-procedures").addEventListener("click", chargerProcedures);
    document.getElementById("btn-nouvelle-procedure").addEventListener("click", nouvelleProcedure);
    document.getElementById("btn-fermer-editeur-procedure").addEventListener("click", fermerEditeurProcedure);
    document.getElementById("btn-enregistrer-procedure").addEventListener("click", enregistrerProcedure);
    document.getElementById("btn-ajouter-piece").addEventListener("click", () => ajouterLignePiece());
    document.getElementById("btn-ajouter-etape").addEventListener("click", () => ajouterLigneEtape());
    document.getElementById("btn-ajouter-veille").addEventListener("click", () => ajouterLigneVeille());

    // ===== Assistant IA : état, génération de procédure, assistant du dossier, liste des démarches =====
    const TAILLE_MIN_TEXTE_IA = 80;
    const TAILLE_MAX_TEXTE_IA = 30000;

    function messageErreurIA(statut, err) {
      if (statut === 503) return "L'assistant IA n'est pas activé sur cette plateforme.";
      if (statut === 429) return "Le plafond mensuel de demandes à l'assistant IA est atteint pour votre bureau.";
      return messageErreurApi(err, "La demande à l'assistant IA a échoué.");
    }

    async function chargerStatutIA() {
      let texte = "Assistant IA : état indisponible";
      try {
        const rep = await appelApi("/api/v1/ia/statut");
        if (rep.ok) {
          const s = await rep.json();
          texte = s.active
            ? "Assistant IA : activé — " + s.appels_ce_mois + " / " + s.plafond_mensuel + " demandes ce mois"
            : "Assistant IA : non activé";
        }
      } catch (e) { /* état laissé à « indisponible » */ }
      ["ia-statut-procedures", "ia-statut-discussion"].forEach((id) => {
        document.getElementById(id).textContent = texte;
      });
    }

    function remplirSelectDemarches(idSelect) {
      const sel = document.getElementById(idSelect);
      const valeur = sel.value;
      sel.innerHTML = "";
      listeDemarches.forEach((d) => {
        const opt = document.createElement("option");
        opt.value = d.code;
        opt.textContent = d.libelle;
        sel.appendChild(opt);
      });
      if (listeDemarches.some((d) => d.code === valeur)) sel.value = valeur;
    }

    async function chargerListeDemarches() {
      try {
        const rep = await appelApi("/api/v1/demarches");
        if (rep.ok) {
          const liste = await rep.json();
          if (Array.isArray(liste) && liste.length > 0) {
            listeDemarches = liste.map((d) => ({ code: d.code, libelle: d.libelle || d.code }));
          }
        }
      } catch (e) { /* on garde la liste par défaut (Campus France, IRCC) */ }
      remplirSelectDemarches("eval-demarche");
      remplirSelectDemarches("ia-demarche-assistant");
    }

    function majCompteurTexteIA() {
      const n = document.getElementById("ia-texte-source").value.trim().length;
      const c = document.getElementById("ia-compteur-texte");
      c.textContent = n + " / 30 000 caractères (minimum 80)";
      c.classList.toggle("depasse", n > 0 && (n < TAILLE_MIN_TEXTE_IA || n > TAILLE_MAX_TEXTE_IA));
    }

    function retourGenerationIA(msg, ok) {
      const z = document.getElementById("zone-retour-generation-ia");
      z.textContent = msg;
      z.style.borderColor = ok ? "var(--bon)" : "var(--critique)";
      z.classList.remove("cache");
    }

    async function genererProcedureIA() {
      if (!estAdministrateur()) return notifier("Réservé aux administrateurs du bureau.", false);
      const texte = document.getElementById("ia-texte-source").value.trim();
      if (texte.length < TAILLE_MIN_TEXTE_IA || texte.length > TAILLE_MAX_TEXTE_IA) {
        return retourGenerationIA("Le texte doit contenir entre 80 et 30 000 caractères (actuellement " + texte.length + ").", false);
      }
      const btn = document.getElementById("btn-generer-procedure-ia");
      btn.disabled = true;
      btn.textContent = "Génération en cours...";
      try {
        const rep = await appelApi("/api/v1/ia/procedures/generer", { method: "POST", body: JSON.stringify({ texte }) });
        if (!rep.ok) {
          const err = await rep.json().catch(() => null);
          return retourGenerationIA(messageErreurIA(rep.status, err), false);
        }
        const data = await rep.json();
        procedureEditee = null;
        remplirEditeurProcedure(data.brouillon);
        configurerEditeurSelonRole();
        const liste = document.getElementById("liste-avertissements-ia");
        liste.innerHTML = "";
        (data.avertissements || []).forEach((a) => {
          const li = document.createElement("li");
          li.textContent = a;
          liste.appendChild(li);
        });
        document.getElementById("titre-avertissements-ia").classList.toggle("cache", liste.children.length === 0);
        document.getElementById("bloc-ia-editeur").classList.remove("cache");
        document.getElementById("titre-editeur-procedure").textContent = "Nouvelle procédure (brouillon généré par IA, non enregistré)";
        document.getElementById("zone-retour-procedure").classList.add("cache");
        document.getElementById("carte-editeur-procedure").classList.remove("cache");
        document.getElementById("carte-editeur-procedure").scrollIntoView({ behavior: "smooth" });
        retourGenerationIA("Brouillon généré. Relisez-le dans l'éditeur ci-dessous : rien n'est enregistré avant votre clic sur « Enregistrer la procédure ».", true);
        chargerStatutIA();
      } finally {
        btn.disabled = false;
        btn.textContent = "Générer un brouillon";
      }
    }

    function retourAssistantIA(msg, ok) {
      const z = document.getElementById("zone-reponse-assistant-ia");
      z.innerHTML = "";
      const p = document.createElement("div");
      p.textContent = msg;
      z.appendChild(p);
      z.style.borderColor = ok ? "var(--bon)" : "var(--critique)";
      z.classList.remove("cache");
    }

    async function demanderAssistantDossier() {
      if (!candidatActifId) {
        return retourAssistantIA("Aucun candidat n'est sélectionné. Choisissez d'abord un dossier dans « Étudiants et fiches » : l'assistant répond dans le contexte de ce dossier.", false);
      }
      const question = document.getElementById("ia-question-assistant").value.trim();
      const code_demarche = document.getElementById("ia-demarche-assistant").value;
      if (question.length < 1) return retourAssistantIA("Saisissez votre question.", false);
      const btn = document.getElementById("btn-demander-assistant-ia");
      btn.disabled = true;
      btn.textContent = "Analyse en cours...";
      try {
        const rep = await appelApi("/api/v1/ia/dossiers/" + encodeURIComponent(candidatActifId) + "/assistant", {
          method: "POST",
          body: JSON.stringify({ code_demarche, question }),
        });
        if (!rep.ok) {
          const err = await rep.json().catch(() => null);
          return retourAssistantIA(messageErreurIA(rep.status, err), false);
        }
        const data = await rep.json();
        const z = document.getElementById("zone-reponse-assistant-ia");
        z.innerHTML = "";
        const texte = document.createElement("div");
        texte.className = "ia-reponse";
        texte.textContent = data.reponse;
        const mention = document.createElement("div");
        mention.className = "ia-mention";
        mention.textContent = data.mention || "";
        z.appendChild(texte);
        z.appendChild(mention);
        z.style.borderColor = "var(--bon)";
        z.classList.remove("cache");
        chargerStatutIA();
      } finally {
        btn.disabled = false;
        btn.textContent = "Demander";
      }
    }

    document.getElementById("ia-texte-source").addEventListener("input", majCompteurTexteIA);
    document.getElementById("btn-generer-procedure-ia").addEventListener("click", genererProcedureIA);
    document.getElementById("btn-demander-assistant-ia").addEventListener("click", demanderAssistantDossier);

"""
