"""JavaScript du parcours « Créer la fiche depuis le passeport » (écran Dossier automatique).

Chaîne Python non brute : AUCUN antislash. Nœuds DOM + `textContent`, aucun `console.log`.
Assemblé par `js_flux_dossier.py` ; utilise ses fonctions `fdEl`, `fdEcriture`, `fdMessageHttp`,
`fdChargerEtudiants`, `fdChoisirEtudiant`, `fdExtensionValide`.
Contrat : `POST /api/v1/depots-passeport`, `POST .../{id}/creer-fiche` (confirme:true), `DELETE .../{id}`.
Rien n'est créé sans le clic de confirmation (R4).
"""

from __future__ import annotations

JS_FLUX_DOSSIER_PASSEPORT = """
    // ----- Fiche depuis le passeport : dépôt, propositions « à confirmer », confirmation (R4) -----
    // Rien n'est envoyé à la création sans le clic « Confirmer et créer la fiche » (valeurs affichées, modifiables).
    const FD_PP_CHAMPS = [
      ["nom", "Nom de famille", true],
      ["prenom", "Prénom", true],
      ["date_naissance", "Date de naissance (AAAA-MM-JJ)", false],
      ["sexe", "Sexe", false],
      ["nationalite", "Nationalité", false],
      ["numero_passeport", "Numéro de passeport", false],
      ["date_expiration_passeport", "Date d'expiration du passeport (AAAA-MM-JJ)", false]
    ];
    let fdPpDepot = null;
    let fdPpOccupe = false;

    function fdPpStatut(message, genre, candidatId) {
      const classes = { ok: "fd-pp-ok", alerte: "fd-pp-alerte", erreur: "fd-pp-erreur" };
      const enfants = [dosNoeud("p", "fd-pp-msg " + (classes[genre] || ""), message)];
      if (candidatId) {
        const lien = dosNoeud("button", "mo-press btn btn-lien btn-sm", "Voir la fiche existante");
        lien.type = "button";
        lien.addEventListener("click", () => fdOuvrirFiche(candidatId));
        enfants.push(lien);
      }
      fdEl("fd-pp-statut").replaceChildren(...enfants);
    }
    async function fdOuvrirFiche(id) {
      if (!dictionnaireCandidats[id]) await fdChargerEtudiants();
      if (dictionnaireCandidats[id]) selectionnerCandidat(dictionnaireCandidats[id], true);
      allerVersVue("vue-etudiants");
    }
    function fdPpActiver() {
      fdEl("fd-pp-fichier").disabled = !fdEcriture() || fdPpOccupe;
    }
    function fdPpReinitialiser(message, genre) {
      fdPpDepot = null;
      fdEl("fd-pp-zone").replaceChildren();
      fdEl("fd-pp-zone").removeAttribute("aria-busy");
      fdEl("fd-pp-fichier").value = "";
      if (message) fdPpStatut(message, genre); else fdEl("fd-pp-statut").replaceChildren();
    }
    function fdPpSquelette() {
      const bloc = dosNoeud("div", "fd-pp-squelette");
      bloc.setAttribute("aria-hidden", "true");
      bloc.append(dosNoeud("span", "mo-skel squelette squelette-texte"), dosNoeud("span", "mo-skel squelette squelette-texte"), dosNoeud("span", "mo-skel squelette squelette-texte court"));
      return bloc;
    }
    function fdPpChamp(def, proposition, manuel) {
      const id = "fd-pp-champ-" + def[0];
      const label = dosNoeud("label", "champ");
      label.setAttribute("for", id);
      const entete = dosNoeud("span", "fd-pp-libelle", def[1]);
      if (def[2]) entete.appendChild(dosNoeud("span", "requis", "*"));
      if (proposition) entete.appendChild(dosNoeud("span", "badge badge-completer", "À confirmer"));
      let champ;
      if (def[0] === "sexe") {
        champ = document.createElement("select");
        [["", "Non renseigné"], ["M", "Masculin"], ["F", "Féminin"]].forEach((o) => {
          const opt = dosNoeud("option", "", o[1]);
          opt.value = o[0];
          champ.appendChild(opt);
        });
        champ.value = proposition ? String(proposition.valeur).trim().toUpperCase().charAt(0) : "";
      } else {
        champ = document.createElement("input");
        champ.type = "text";
        champ.autocomplete = "off";
        champ.value = proposition ? proposition.valeur : "";
      }
      champ.id = id;
      champ.setAttribute("data-champ", def[0]);
      const aideId = id + "-aide";
      champ.setAttribute("aria-describedby", aideId);
      let aide = "À remplir vous-même.";
      if (proposition) aide = "Extrait du passeport : « " + proposition.extrait + " ». Vérifiez et corrigez si besoin.";
      else if (!manuel) aide = "Non lu dans le passeport : à remplir si vous le connaissez.";
      const aideNoeud = dosNoeud("span", "champ-aide fd-pp-extrait", aide);
      aideNoeud.id = aideId;
      label.append(entete, champ, aideNoeud);
      return label;
    }
    function fdPpRendre(depot) {
      const manuel = depot.statut === "saisie_manuelle" || depot.saisie_manuelle_requise === true;
      const parChamp = {};
      (depot.propositions || []).forEach((p) => { if (!parChamp[p.champ]) parChamp[p.champ] = p; });
      if (depot.candidat_existant_id) {
        fdPpStatut("Attention : un étudiant du bureau a déjà ce numéro de passeport. Consultez sa fiche avant de confirmer, pour ne pas créer de doublon.", "alerte", depot.candidat_existant_id);
      } else if (manuel) {
        fdPpStatut("Le passeport n'a pas pu être lu automatiquement : remplissez les champs vous-même à partir du document.", "alerte");
      } else {
        fdPpStatut("Passeport lu : les valeurs ci-dessous sont des propositions à confirmer. Aucune fiche n'est créée pour l'instant.", "ok");
      }
      const statut = fdEl("fd-pp-statut");
      (depot.avertissements || []).forEach((a) => statut.appendChild(dosNoeud("p", "fd-pp-msg", String(a))));
      const form = document.createElement("form");
      form.className = "fd-pp-form";
      form.noValidate = true;
      const groupe = document.createElement("fieldset");
      groupe.className = "fd-pp-form";
      groupe.appendChild(dosNoeud("legend", "", manuel ? "Valeurs à saisir" : "Valeurs proposées (à confirmer)"));
      const grille = dosNoeud("div", "fd-pp-grille");
      FD_PP_CHAMPS.forEach((def) => grille.appendChild(fdPpChamp(def, manuel ? null : parChamp[def[0]], manuel)));
      const confirmer = dosNoeud("button", "mo-press btn btn-primaire", "Confirmer et créer la fiche");
      confirmer.type = "submit";
      confirmer.id = "fd-pp-confirmer";
      const annuler = dosNoeud("button", "mo-press btn btn-contour", "Annuler");
      annuler.type = "button";
      annuler.id = "fd-pp-annuler";
      annuler.addEventListener("click", fdPpAnnuler);
      const actions = dosNoeud("div", "fd-pp-actions");
      actions.append(confirmer, annuler);
      groupe.append(grille, actions);
      form.appendChild(groupe);
      form.addEventListener("submit", (ev) => { ev.preventDefault(); fdPpConfirmer(form); });
      fdEl("fd-pp-zone").removeAttribute("aria-busy");
      fdEl("fd-pp-zone").replaceChildren(form);
      const premier = form.querySelector("input, select");
      if (premier) premier.focus();
    }

    async function fdPpDeposer(fichier) {
      if (!fdEcriture()) { fdPpStatut("Ce compte ne peut pas créer de fiche.", "erreur"); return; }
      if (!fdExtensionValide(fichier.name)) { fdPpStatut("Format refusé : utilisez un passeport au format PDF, PNG ou JPEG.", "erreur"); return; }
      const ancien = fdPpDepot;
      if (ancien) appelApi("/api/v1/depots-passeport/" + encodeURIComponent(ancien.id), { method: "DELETE" }).catch(() => null);
      fdPpDepot = null;
      fdPpOccupe = true;
      fdPpActiver();
      fdEl("fd-pp-zone").setAttribute("aria-busy", "true");
      fdEl("fd-pp-zone").replaceChildren(fdPpSquelette());
      fdPpStatut("Lecture du passeport en cours…", "");
      try {
        const formulaire = new FormData();
        formulaire.append("fichier", fichier);
        const rep = await appelApi("/api/v1/depots-passeport", { method: "POST", body: formulaire });
        const corps = await rep.json().catch(() => null);
        if (!rep.ok) {
          fdPpReinitialiser(fdMessageHttp(rep.status, corps, "Le passeport a été refusé : utilisez un PDF, PNG ou JPEG lisible de 10 Mo maximum."), "erreur");
          return;
        }
        fdPpDepot = corps;
        fdPpRendre(corps);
      } catch (e) {
        fdPpReinitialiser(FD_MESSAGE_RESEAU, "erreur");
      } finally {
        fdPpOccupe = false;
        fdPpActiver();
        fdEl("fd-pp-fichier").value = "";
      }
    }

    async function fdPpConfirmer(form) {
      if (!fdPpDepot || fdPpOccupe) return;
      const valeurs = {};
      form.querySelectorAll("[data-champ]").forEach((c) => { valeurs[c.getAttribute("data-champ")] = c.value.trim(); });
      let manque = null;
      ["nom", "prenom"].forEach((k) => {
        const c = document.getElementById("fd-pp-champ-" + k);
        c.setAttribute("aria-invalid", valeurs[k] ? "false" : "true");
        if (!valeurs[k] && !manque) manque = c;
      });
      if (manque) {
        manque.focus();
        fdPpStatut("Le nom et le prénom sont obligatoires pour créer la fiche.", "erreur");
        return;
      }
      const corpsEnvoi = { confirme: true };
      Object.keys(valeurs).forEach((k) => { if (valeurs[k]) corpsEnvoi[k] = valeurs[k]; });
      const depot = fdPpDepot;
      const bouton = form.querySelector("#fd-pp-confirmer");
      fdPpOccupe = true;
      bouton.setAttribute("aria-busy", "true");
      bouton.disabled = true;
      try {
        const rep = await appelApi("/api/v1/depots-passeport/" + encodeURIComponent(depot.id) + "/creer-fiche", { method: "POST", body: JSON.stringify(corpsEnvoi) });
        const corps = await rep.json().catch(() => null);
        if (rep.status === 409 && corps && corps.code === "passeport_deja_utilise") {
          fdPpStatut("Ce passeport est déjà utilisé par une fiche existante : aucune fiche n'a été créée.", "erreur", corps.candidat_id);
          return;
        }
        if (!rep.ok) {
          fdPpStatut(rep.status === 409 ? messageErreurApi(corps, "La fiche n'a pas pu être créée : conflit avec une fiche existante.") : fdMessageHttp(rep.status, corps, "La fiche n'a pas pu être créée : vérifiez les valeurs."), "erreur");
          return;
        }
        const candidat = corps.candidat;
        dictionnaireCandidats[candidat.id] = candidat;
        fdPpReinitialiser("Fiche créée pour " + (candidat.nom || "") + " " + (candidat.prenom || "") + ". Déposez maintenant ses documents.", "ok");
        await fdChargerEtudiants();
        fdEl("fd-etudiant").value = candidat.id;
        fdChoisirEtudiant(candidat.id);
        notifier("Fiche créée depuis le passeport : déposez maintenant les documents de l'étudiant.", true);
        fdEl("fd-fichiers").focus();
      } catch (e) {
        fdPpStatut(FD_MESSAGE_RESEAU, "erreur");
      } finally {
        fdPpOccupe = false;
        bouton.removeAttribute("aria-busy");
        bouton.disabled = false;
      }
    }

    async function fdPpAnnuler() {
      if (!fdPpDepot || fdPpOccupe) return;
      fdPpOccupe = true;
      try {
        const rep = await appelApi("/api/v1/depots-passeport/" + encodeURIComponent(fdPpDepot.id), { method: "DELETE" });
        if (rep.ok || rep.status === 404) {
          fdPpReinitialiser("Dépôt annulé : le passeport a été retiré et aucune fiche n'a été créée.", "ok");
        } else {
          const corps = await rep.json().catch(() => null);
          fdPpStatut(fdMessageHttp(rep.status, corps, "Le dépôt n'a pas pu être annulé."), "erreur");
        }
      } catch (e) {
        fdPpStatut(FD_MESSAGE_RESEAU, "erreur");
      } finally {
        fdPpOccupe = false;
      }
    }

"""
