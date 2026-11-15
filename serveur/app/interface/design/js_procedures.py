"""JavaScript de l'interface : Procédures du bureau, assistant IA et liste des démarches.

Chaîne Python non brute : aucun antislash (leur nombre dans la page est verrouillé par les tests).
Tableau et éditeur construits par nœuds DOM et textContent, avec les aides `dem*` de `js_demarches`.
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
      liste.replaceChildren();
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
      document.getElementById("liste-avertissements-ia").replaceChildren();
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
      annoncer(msg);
      z.textContent = msg;
      z.style.borderColor = ok ? "var(--bon)" : "var(--critique)";
      z.classList.remove("cache");
    }

    const NB_COLONNES_PROCEDURES = 4;

    function ligneEtatProcedures(titre, texte, sorte) {
      const tr = document.createElement("tr");
      const td = demNoeud("td", "etat-vide");
      td.colSpan = NB_COLONNES_PROCEDURES;
      td.appendChild(demIllustration(sorte));
      td.appendChild(demNoeud("strong", "", titre));
      td.appendChild(demNoeud("span", "", texte));
      tr.appendChild(td);
      return tr;
    }

    function ligneSqueletteProcedure() {
      const tr = document.createElement("tr");
      tr.setAttribute("aria-hidden", "true");
      ["squelette squelette-texte", "squelette squelette-pastille", "squelette squelette-valeur", "squelette squelette-texte court"].forEach((classe) => {
        const td = document.createElement("td");
        td.appendChild(demNoeud("span", classe));
        tr.appendChild(td);
      });
      return tr;
    }

    function ligneProcedure(d) {
      const tr = document.createElement("tr");
      const nom = demNoeud("td");
      const pile = demNoeud("div", "proc-nom");
      pile.appendChild(demNoeud("strong", "", d.libelle));
      pile.appendChild(demNoeud("code", "", d.code));
      nom.appendChild(pile);
      tr.appendChild(nom);
      const origine = demNoeud("td");
      origine.appendChild(d.source === "bureau"
        ? demNoeud("span", "badge badge-ok", "Votre bureau")
        : demNoeud("span", "badge badge-nu", "Base commune"));
      tr.appendChild(origine);
      tr.appendChild(demNoeud("td", "num", d.source === "bureau" ? String(d.version) : "—"));
      const cellule = demNoeud("td");
      const actions = demNoeud("div", "proc-actions");
      const btnOuvrir = demNoeud("button", "btn btn-secondaire btn-sm", estAdministrateur() ? "Modifier" : "Consulter");
      btnOuvrir.type = "button";
      btnOuvrir.addEventListener("click", () => ouvrirEditeurProcedure(d.code));
      actions.appendChild(btnOuvrir);
      if (estAdministrateur()) {
        const btnMasquer = demNoeud("button", "btn btn-fantome btn-sm", "Masquer");
        btnMasquer.type = "button";
        btnMasquer.addEventListener("click", () => masquerProcedure(d.code, d.libelle));
        actions.appendChild(btnMasquer);
      }
      cellule.appendChild(actions);
      tr.appendChild(cellule);
      return tr;
    }

    async function chargerProcedures() {
      const tbody = document.querySelector("#table-procedures tbody");
      document.getElementById("btn-nouvelle-procedure").classList.toggle("cache", !estAdministrateur());
      document.getElementById("carte-generation-ia").classList.toggle("cache", !estAdministrateur());
      tbody.setAttribute("aria-busy", "true");
      tbody.replaceChildren(ligneSqueletteProcedure(), ligneSqueletteProcedure(), ligneSqueletteProcedure());
      const rep = await appelApi("/api/v1/demarches/gestion");
      tbody.setAttribute("aria-busy", "false");
      if (!rep.ok) {
        tbody.replaceChildren(ligneEtatProcedures("Procédures indisponibles.", "Connectez-vous (menu de gauche) pour afficher les procédures de votre bureau.", "alerte"));
        return;
      }
      const liste = await rep.json();
      if (liste.length === 0) {
        tbody.replaceChildren(ligneEtatProcedures("Aucune procédure disponible.", "Votre bureau n'a encore aucune procédure. Un administrateur peut en créer une avec « Nouvelle procédure ».", "dossier"));
        return;
      }
      tbody.replaceChildren(...liste.map(ligneProcedure));
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

    // Ligne éditable (pièce, étape, point de veille) : champs libellés + bouton « Retirer ».
    function creerLigne(enfants) {
      const div = demNoeud("div", "ligne-proc");
      enfants.forEach((e) => div.appendChild(e));
      const retirer = demNoeud("button", "btn btn-fantome btn-sm", "Retirer");
      retirer.type = "button";
      retirer.setAttribute("data-retirer", "1");
      retirer.addEventListener("click", () => div.remove());
      div.appendChild(retirer);
      return div;
    }

    function champLigne(libelle, classeInput, valeur, options) {
      const opts = options || {};
      const label = demNoeud("label", "champ" + (opts.large ? " large" : ""), libelle);
      const input = document.createElement("input");
      input.type = opts.type || "text";
      input.className = classeInput;
      input.value = valeur;
      if (opts.placeholder) input.placeholder = opts.placeholder;
      if (opts.liste) input.setAttribute("list", opts.liste);
      if (opts.min !== undefined) input.min = String(opts.min);
      label.appendChild(input);
      return label;
    }

    function caseLigne(libelle, classeInput, coche) {
      const label = demNoeud("label", "case");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.className = classeInput;
      cb.checked = coche;
      label.appendChild(cb);
      label.appendChild(document.createTextNode(" " + libelle));
      return label;
    }

    function ajouterLignePiece(p) {
      const v = Object.assign({ type_piece: "", libelle: "", obligatoire: true, exige_date_expiration: false, validite_minimale_jours: 0 }, p || {});
      const div = creerLigne([
        champLigne("Type", "p-type", v.type_piece, { placeholder: "ex : passeport", liste: "liste-types-pieces" }),
        champLigne("Libellé affiché", "p-libelle", v.libelle, { large: true, placeholder: "ex : Passeport en cours de validité" }),
        champLigne("Validité min. (jours)", "p-valid", String(Number(v.validite_minimale_jours) || 0), { type: "number", min: 0 }),
        caseLigne("Obligatoire", "p-oblig", !!v.obligatoire),
        caseLigne("Date d'expiration exigée", "p-exp", !!v.exige_date_expiration),
      ]);
      document.getElementById("proc-pieces").appendChild(div);
    }

    function ajouterLigneEtape(e) {
      const v = Object.assign({ code: "", libelle: "" }, e || {});
      const div = creerLigne([
        champLigne("Code", "e-code", v.code, { placeholder: "ex : verification_prerequis" }),
        champLigne("Libellé de l'étape", "e-libelle", v.libelle, { large: true }),
      ]);
      document.getElementById("proc-etapes").appendChild(div);
    }

    function ajouterLigneVeille(p) {
      const v = Object.assign({ titre: "", resume: "", reference: "" }, p || {});
      const div = creerLigne([
        champLigne("Titre", "v-titre", v.titre),
        champLigne("Résumé de la règle", "v-resume", v.resume, { large: true, placeholder: "1000 caractères maximum" }),
        champLigne("Référence officielle", "v-ref", v.reference),
      ]);
      document.getElementById("proc-veille").appendChild(div);
    }

    function construireCasesChamps(coches) {
      const zone = document.getElementById("proc-champs");
      zone.replaceChildren();
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
      dl.replaceChildren(...Object.keys(LIBELLES_PIECES_FR).map((k) => {
        const opt = document.createElement("option");
        opt.value = k;
        opt.textContent = LIBELLES_PIECES_FR[k];
        return opt;
      }));
      document.getElementById("proc-pieces").replaceChildren();
      (def.pieces_requises || []).forEach((p) => ajouterLignePiece(p));
      document.getElementById("proc-etapes").replaceChildren();
      (def.etapes_tache || []).forEach((e) => ajouterLigneEtape(e));
      document.getElementById("proc-veille").replaceChildren();
      (def.veille_reglementaire || []).forEach((p) => ajouterLigneVeille(p));
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
      annoncer(msg);
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
      btn.setAttribute("aria-busy", "true");
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
        liste.replaceChildren();
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
        btn.removeAttribute("aria-busy");
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
