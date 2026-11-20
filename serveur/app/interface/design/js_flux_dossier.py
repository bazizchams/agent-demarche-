"""JavaScript de l'écran « Dossier automatique » (parcours : étudiant, dépôt, analyse, suivi des 9 étapes).

Chaîne Python non brute : AUCUN antislash (leur nombre dans la page est verrouillé par les tests).
Tout l'affichage est construit par nœuds DOM et `textContent` (jamais `innerHTML`), aucun `console.log`.
Utilise `appelApi`, `notifier`, `messageErreurApi`, `selectionnerCandidat`, `candidatActifId`,
`dictionnaireCandidats`, `roleActif`, `dosNoeud`, `dosSvg`, `dosEtatVide` (socle) et, pour l'étape
navigateur, `ouvDemanderOuverture` (js_ouverture_pc) : la logique d'API de « Ouvrir sur mon PC » n'est
pas recopiée ici.

Contrat d'API :
- `POST /api/v1/candidats/{id}/dossier-automatique/lancer` ;
- `GET  /api/v1/candidats/{id}/dossier-automatique/etat` -> progression 0-100, étapes, pièces manquantes ;
- dépôt : `POST /api/v1/candidats/{id}/documents` (formulaire `type_piece` + `fichier`, jeton CSRF via appelApi) ;
- fiche depuis le passeport : `POST /api/v1/depots-passeport` (fichier), `POST .../{id}/creer-fiche`
  (`confirme: true` + valeurs affichées), `DELETE .../{id}` (annulation).
"""

from __future__ import annotations

from app.interface.design.js_flux_dossier_mouvement import JS_FLUX_DOSSIER_MOUVEMENT
from app.interface.design.js_flux_dossier_passeport import JS_FLUX_DOSSIER_PASSEPORT

_JS_PRINCIPAL = """
    // =======================================================================
    // Dossier automatique : dépôt des pièces, lancement, suivi des 9 étapes.
    // =======================================================================
    const FD_INTERVALLE_MS = 3000;
    const FD_ECHECS_MAX = 5;
    const FD_SUIVIS_MAX = 20;
    const FD_VUE = "vue-flux-dossier";
    const FD_ETAPES_PREVUES = [
      ["pieces", "Pièces reçues"],
      ["lecture", "Lecture des pièces"],
      ["revue_valeurs", "Revue des valeurs"],
      ["fiche", "Fiche de l'étudiant"],
      ["points_forts", "Points forts"],
      ["projet_professionnel", "Projet professionnel"],
      ["voeux", "Vœux"],
      ["lettres", "Lettres de motivation"],
      ["navigateur", "Navigateur et validation"]
    ];
    // Libellé lisible d'une étape : celui du serveur, sans préfixe « Étape », sauf s'il est absent ou égal au code.
    function fdLibelleEtape(etape) {
      let brut = String(etape.libelle || "").trim();
      if (brut.toLowerCase().indexOf("étape ") === 0) brut = brut.slice(6).trim();
      if (brut && brut !== etape.code) return brut;
      const prevue = FD_ETAPES_PREVUES.find((e) => e[0] === etape.code);
      return prevue ? prevue[1] : (brut || String(etape.code || ""));
    }
    // Détail utile seulement : vide ou « Détail <code> » = rien à afficher.
    function fdDetailEtape(etape) {
      const d = String(etape.detail || "").trim();
      return d && d !== "Détail " + etape.code ? d : "";
    }
    const FD_STATUTS = {
      a_faire: ["À faire", "badge-attente"],
      en_cours: ["En cours", "badge-info"],
      termine: ["Terminé", "badge-ok"],
      a_verifier: ["À vérifier", "badge-warn"],
      bloque: ["Bloqué", "badge-err"]
    };
    const FD_LIENS_ECRANS = {
      pieces: "vue-documents",
      documents: "vue-documents",
      lecture: "vue-revue-extractions",
      revue_valeurs: "vue-revue-extractions",
      revue_extractions: "vue-revue-extractions",
      fiche: "vue-etudiants",
      etudiants: "vue-etudiants",
      points_forts: "vue-projet-pro",
      projet_professionnel: "vue-projet-pro",
      projet_pro: "vue-projet-pro",
      voeux: "vue-campus-france",
      lettres: "vue-campus-france",
      campus_france: "vue-campus-france",
      validation: "vue-validation-humaine",
      recaps: "vue-recaps-valider"
    };
    const FD_SUGGESTIONS_TYPE = [
      ["passeport", "passeport"], ["passport", "passeport"],
      ["photo", "photo_identite"],
      ["bac", "releve_notes_bac"],
      ["releve", "releves_notes_superieur"],
      ["cv", "cv"],
      ["tcf", "attestation_langue_francaise"], ["delf", "attestation_langue_francaise"], ["dalf", "attestation_langue_francaise"]
    ];
    const FD_EXTENSIONS = ["pdf", "png", "jpg", "jpeg"];

    let fdMinuteur = null;
    let fdCandidat = null;
    let fdEtat = null;
    let fdEchecs = 0;
    let fdSuivis = 0;
    let fdEnRequete = false;
    let fdFichiers = [];
    let fdSequence = 0;
    let fdEnvoi = false;
    let fdLancement = false;

    function fdEcriture() {
      return roleActif === "administrateur" || roleActif === "employe";
    }
    function fdEl(id) {
      return document.getElementById(id);
    }
    function fdVisible() {
      return !fdEl(FD_VUE).classList.contains("cache");
    }
    function fdUrl(suite) {
      return "/api/v1/candidats/" + encodeURIComponent(fdCandidat) + suite;
    }

    // ----- Messages d'erreur en français clair -----
    function fdMessageHttp(statut, corps, defaut) {
      if (statut === 401 || statut === 403) return "Votre session a expiré ou ce compte ne peut pas modifier les dossiers. Reconnectez-vous puis réessayez.";
      if (statut === 404) return "Le suivi automatique n'est pas disponible pour ce dossier : le dossier est introuvable ou la fonction n'est pas encore activée sur ce serveur.";
      if (statut === 413) return "Ce fichier est trop volumineux (10 Mo maximum). Réduisez-le ou scannez-le en plus basse résolution.";
      if (statut === 415 || statut === 422) return messageErreurApi(corps, "Ce fichier n'a pas pu être accepté : utilisez un PDF, PNG ou JPEG lisible.");
      if (statut === 429) return "Trop de demandes en peu de temps. Patientez quelques secondes puis réessayez.";
      if (statut === 409) return "Une analyse est déjà en cours pour ce dossier. Patientez : la page se met à jour toute seule.";
      if (statut >= 500) return "Le serveur a rencontré un problème. Réessayez dans un instant ; si cela continue, prévenez l'administrateur.";
      return messageErreurApi(corps, defaut);
    }
    const FD_MESSAGE_RESEAU = "Connexion au serveur impossible : vérifiez votre connexion internet puis réessayez.";

    function fdMontrerErreur(texte) {
      fdEl("fd-erreur-texte").textContent = texte;
      fdEl("fd-erreur").classList.remove("cache");
    }
    function fdCacherErreur() {
      fdEl("fd-erreur").classList.add("cache");
    }

    // ----- Étudiant : sélection et création rapide -----
    function fdRemplirEtudiants(liste) {
      const select = fdEl("fd-etudiant");
      select.replaceChildren();
      const vide = document.createElement("option");
      vide.value = "";
      vide.textContent = liste.length ? "Choisir un étudiant" : "Aucun étudiant : créez une fiche ci-dessous";
      select.appendChild(vide);
      liste.forEach((c) => {
        dictionnaireCandidats[c.id] = c;
        const o = document.createElement("option");
        o.value = c.id;
        o.textContent = (c.nom || "") + " " + (c.prenom || "");
        select.appendChild(o);
      });
      select.value = candidatActifId && dictionnaireCandidats[candidatActifId] ? candidatActifId : "";
    }

    async function fdChargerEtudiants() {
      try {
        const rep = await appelApi("/api/v1/candidats");
        if (!rep.ok) {
          fdRemplirEtudiants([]);
          fdMontrerErreur(fdMessageHttp(rep.status, null, "La liste des étudiants n'a pas pu être chargée."));
          return;
        }
        const data = await rep.json();
        fdRemplirEtudiants(data.elements || []);
      } catch (e) {
        fdRemplirEtudiants([]);
        fdMontrerErreur(FD_MESSAGE_RESEAU);
      }
    }

    function fdChoisirEtudiant(id) {
      fdArreterSuivi();
      fdFichiers = [];
      fdEtat = null;
      fdEchecs = 0;
      fdSuivis = 0;
      fdCompletVu = null;
      fdCandidat = id || null;
      fdSynchroniserDiscussion();
      fdCacherErreur();
      if (id && dictionnaireCandidats[id]) selectionnerCandidat(dictionnaireCandidats[id], true);
      fdAfficherSelection();
      if (fdCandidat) fdActualiser(true);
    }

    function fdAfficherSelection() {
      const aucun = !fdCandidat;
      fdEl("fd-vide").classList.toggle("cache", !aucun);
      fdEl("fd-contenu").classList.toggle("cache", aucun);
      if (aucun) {
        const vide = fdEl("fd-vide");
        const action = dosNoeud("button", "mo-press btn btn-secondaire btn-sm", "Créer la fiche d'un nouvel étudiant");
        action.type = "button";
        action.addEventListener("click", () => { fdEl("fd-nouveau").open = true; fdEl("fd-nom").focus(); });
        const bloc = dosNoeud("div", "fd-vide-bloc");
        bloc.append(fdIllustrationVide(), dosNoeud("strong", "", "Choisissez l'étudiant à traiter."),
          dosNoeud("span", "", "Sélectionnez un dossier dans la liste, ou créez la fiche d'un nouvel étudiant, puis déposez ses documents."), action);
        vide.replaceChildren(bloc);
      }
      fdRendreFichiers();
      fdRendreAnalyse();
    }

    async function fdCreerEtudiant() {
      const nom = fdEl("fd-nom").value.trim();
      const prenom = fdEl("fd-prenom").value.trim();
      fdEl("fd-nom").setAttribute("aria-invalid", nom ? "false" : "true");
      fdEl("fd-prenom").setAttribute("aria-invalid", prenom ? "false" : "true");
      if (!nom || !prenom) {
        fdEl(nom ? "fd-prenom" : "fd-nom").focus();
        notifier("Renseignez le nom et le prénom de l'étudiant.", false);
        return;
      }
      const bouton = fdEl("fd-btn-creer");
      bouton.setAttribute("aria-busy", "true");
      try {
        const rep = await appelApi("/api/v1/candidats", { method: "POST", body: JSON.stringify({ nom: nom, prenom: prenom }) });
        const corps = await rep.json().catch(() => null);
        if (!rep.ok) {
          notifier(fdMessageHttp(rep.status, corps, "La fiche n'a pas pu être créée : vérifiez le nom et le prénom."), false);
          return;
        }
        fdEl("fd-nom").value = "";
        fdEl("fd-prenom").value = "";
        fdEl("fd-nouveau").open = false;
        dictionnaireCandidats[corps.id] = corps;
        await fdChargerEtudiants();
        fdEl("fd-etudiant").value = corps.id;
        fdChoisirEtudiant(corps.id);
        notifier("Fiche créée : déposez maintenant les documents de l'étudiant.", true);
      } catch (e) {
        notifier(FD_MESSAGE_RESEAU, false);
      } finally {
        bouton.removeAttribute("aria-busy");
      }
    }

    // ----- Dépôt des documents -----
    function fdSuggererType(nom) {
      const bas = nom.toLowerCase();
      for (let i = 0; i < FD_SUGGESTIONS_TYPE.length; i++) {
        if (bas.indexOf(FD_SUGGESTIONS_TYPE[i][0]) !== -1) return FD_SUGGESTIONS_TYPE[i][1];
      }
      return "";
    }
    function fdExtensionValide(nom) {
      const point = nom.lastIndexOf(".");
      return point !== -1 && FD_EXTENSIONS.indexOf(nom.slice(point + 1).toLowerCase()) !== -1;
    }
    function fdTaille(octets) {
      return octets >= 1048576 ? (octets / 1048576).toFixed(1).replace(".", ",") + " Mo" : Math.max(1, Math.round(octets / 1024)) + " Ko";
    }

    function fdAjouterFichiers(fichiers) {
      const refuses = [];
      Array.prototype.forEach.call(fichiers, (f) => {
        if (!fdExtensionValide(f.name)) { refuses.push(f.name); return; }
        const suggestion = fdSuggererType(f.name);
        fdSequence += 1;
        fdFichiers.push({ cle: "f" + fdSequence, fichier: f, type: suggestion, suggere: suggestion !== "", statut: "attente", message: "" });
      });
      if (refuses.length) {
        notifier("Format refusé : " + refuses.join(", ") + ". Utilisez des fichiers PDF, PNG ou JPEG.", false);
      }
      fdRendreFichiers();
    }

    function fdOptionsTypes(select, valeur) {
      const vide = document.createElement("option");
      vide.value = "";
      vide.textContent = "Choisir le type de pièce";
      select.appendChild(vide);
      const source = document.getElementById("doc-type-piece");
      if (source) {
        Array.prototype.forEach.call(source.options, (o) => {
          const copie = document.createElement("option");
          copie.value = o.value;
          copie.textContent = o.textContent;
          select.appendChild(copie);
        });
      }
      select.value = valeur;
    }

    const FD_LIBELLES_ENVOI = { attente: ["À envoyer", "badge-attente"], envoi: ["Envoi…", "badge-info"], ok: ["Envoyé", "badge-ok"], erreur: ["Refusé", "badge-err"] };

    function fdLibelleType(code) {
      const source = document.getElementById("doc-type-piece");
      if (source) {
        for (let i = 0; i < source.options.length; i++) {
          if (source.options[i].value === code) return source.options[i].textContent;
        }
      }
      return code;
    }

    function fdRendreFichiers() {
      const liste = fdEl("fd-liste-fichiers");
      fdRendreListeFichiers(liste);
      const aEnvoyer = fdFichiers.filter((x) => x.statut === "attente" || x.statut === "erreur");
      fdEl("fd-depot-pied").classList.toggle("cache", fdFichiers.length === 0);
      const bouton = fdEl("fd-btn-envoyer");
      bouton.disabled = fdEnvoi || aEnvoyer.length === 0 || !fdEcriture();
      bouton.lastChild.textContent = aEnvoyer.length > 1 ? "Envoyer les " + aEnvoyer.length + " documents" : "Envoyer le document";
      const faits = fdFichiers.filter((x) => x.statut === "ok").length;
      fdEl("fd-depot-resume").textContent = faits ? faits + " sur " + fdFichiers.length + " document(s) déposé(s) et chiffré(s)." : "Choisissez le type de chaque pièce avant l'envoi.";
      const zone = fdEl("fd-zone-depot");
      zone.classList.toggle("inactif", !fdEcriture());
      fdEl("fd-fichiers").disabled = !fdEcriture() || fdEnvoi;
    }

    async function fdEnvoyerUn(entree) {
      const formulaire = new FormData();
      formulaire.append("type_piece", entree.type);
      formulaire.append("fichier", entree.fichier);
      entree.statut = "envoi";
      entree.message = "";
      fdRendreFichiers();
      try {
        const rep = await appelApi(fdUrl("/documents"), { method: "POST", body: formulaire });
        if (rep.ok) {
          entree.statut = "ok";
        } else {
          const corps = await rep.json().catch(() => null);
          entree.statut = "erreur";
          entree.message = fdMessageHttp(rep.status, corps, "Ce fichier a été refusé : utilisez un PDF, PNG ou JPEG de 10 Mo maximum.");
        }
      } catch (e) {
        entree.statut = "erreur";
        entree.message = FD_MESSAGE_RESEAU;
      }
    }

    async function fdEnvoyerTout() {
      if (!fdCandidat) return;
      const aEnvoyer = fdFichiers.filter((x) => x.statut === "attente" || x.statut === "erreur");
      const sansType = aEnvoyer.filter((x) => !x.type);
      sansType.forEach((x) => { x.message = "Choisissez le type de cette pièce avant de l'envoyer."; });
      if (sansType.length) {
        fdRendreFichiers();
        notifier("Choisissez le type de chaque pièce : l'agent n'en devine aucun à votre place.", false);
        return;
      }
      fdEnvoi = true;
      fdEl("fd-btn-envoyer").setAttribute("aria-busy", "true");
      const candidat = fdCandidat;
      for (let i = 0; i < aEnvoyer.length; i++) {
        if (fdCandidat !== candidat) return;
        await fdEnvoyerUn(aEnvoyer[i]);
      }
      fdEnvoi = false;
      fdEl("fd-btn-envoyer").removeAttribute("aria-busy");
      fdRendreFichiers();
      const ok = aEnvoyer.filter((x) => x.statut === "ok").length;
      if (ok === aEnvoyer.length) notifier(ok + " document(s) déposé(s). Vous pouvez lancer l'analyse.", true);
      else notifier(ok + " document(s) déposé(s), " + (aEnvoyer.length - ok) + " refusé(s) : corrigez-les puis renvoyez.", false);
      if (ok > 0) fdActualiser(false);
    }

    // ----- État du dossier automatique -----
    function fdVueDepuisLien(lien) {
      if (!lien || typeof lien !== "string") return null;
      let cle = lien;
      if (cle.charAt(0) === "#" || cle.charAt(0) === "/") cle = cle.slice(1);
      if (cle.indexOf("vue-") === 0) return document.getElementById(cle) ? cle : null;
      return FD_LIENS_ECRANS[cle] || null;
    }

    const FD_LIBELLES_COMPTEURS = {
      documents: "Documents", pieces_requises: "Pièces requises", pieces_manquantes: "Pièces manquantes",
      champs_fiche_manquants: "Champs de la fiche manquants", champs_manquants: "Champs manquants",
      lus: "Lus", a_lire: "À lire", illisibles: "Illisibles", auto: "Lues automatiquement",
      a_verifier: "À vérifier", a_confirmer: "À confirmer", confirmees: "Confirmées", rejetees: "Rejetées",
      confirmes: "Confirmés", rejetes: "Rejetés", valeurs_a_reporter: "Valeurs à reporter", conflits: "Conflits",
      points_forts_confirmes: "Points forts confirmés", version: "Version", elements_a_verifier: "Éléments à vérifier",
      voeux: "Vœux", propositions: "Propositions", sans_lettre: "Sans lettre", brouillons: "Brouillons",
      validees: "Validées", voeux_ajoutes: "Vœux ajoutés"
    };

    function fdLibelleCompteur(cle) {
      if (FD_LIBELLES_COMPTEURS[cle]) return FD_LIBELLES_COMPTEURS[cle];
      const texte = String(cle).split("_").join(" ");
      return texte.charAt(0).toUpperCase() + texte.slice(1);
    }

    function fdCompteurs(compteurs) {
      if (!compteurs || typeof compteurs !== "object") return null;
      const cles = Object.keys(compteurs).filter((k) => typeof compteurs[k] === "number" || typeof compteurs[k] === "string");
      if (!cles.length) return null;
      const ul = dosNoeud("ul", "fd-compteurs");
      cles.forEach((k) => ul.appendChild(dosNoeud("li", "", fdLibelleCompteur(k) + " : " + compteurs[k])));
      return ul;
    }

    function fdActionsEtape(etape) {
      const zone = dosNoeud("div", "fd-actions");
      const vue = fdVueDepuisLien(etape.lien_ecran);
      if (etape.action_humaine && vue) {
        const b = dosNoeud("button", etape.statut === "a_verifier" ? "mo-press btn btn-primaire btn-sm" : "mo-press btn btn-secondaire btn-sm", etape.action_humaine);
        b.type = "button";
        b.setAttribute("data-aller-vers", vue);
        zone.appendChild(b);
      } else if (etape.action_humaine) {
        zone.appendChild(dosNoeud("span", "badge badge-completer", etape.action_humaine));
      } else if (vue && etape.statut !== "a_faire") {
        const b = dosNoeud("button", "mo-press btn btn-fantome btn-sm", "Voir le détail");
        b.type = "button";
        b.setAttribute("data-aller-vers", vue);
        zone.appendChild(b);
      }
      if (etape.code === "navigateur" && etape.statut !== "bloque") {
        const pc = dosNoeud("button", "mo-press btn btn-contour btn-sm", "Ouvrir sur mon PC");
        pc.type = "button";
        pc.id = "fd-btn-ouvrir-pc";
        pc.addEventListener("click", fdOuvrirSurPc);
        zone.appendChild(pc);
        const etat = dosNoeud("p", "fd-etat-pc");
        etat.id = "fd-etat-pc";
        etat.setAttribute("role", "status");
        zone.appendChild(etat);
        fdCopierEtatPc();
      }
      return zone.children.length ? zone : null;
    }

    async function fdOuvrirSurPc() {
      if (typeof ouvDemanderOuverture !== "function") {
        notifier("L'ouverture sur le PC n'est pas disponible dans cette version de l'interface.", false);
        return;
      }
      await ouvDemanderOuverture();
      fdCopierEtatPc();
      fdSynchroniserDiscussion();
    }

    // Discussion en direct : montée dès qu'une tâche « Ouvrir sur mon PC » existe pour l'étudiant affiché
    // (identifiant réutilisé depuis js_ouverture_pc), démontée quand il n'y en a plus.
    let fdDiscussion = null;
    let fdDiscussionTache = null;

    function fdSynchroniserDiscussion() {
      const carte = document.getElementById("fd-carte-discussion");
      const conteneur = document.getElementById("fd-discussion");
      if (!carte || !conteneur || typeof monterDiscussionAgent !== "function") return;
      const tacheId = (typeof ouvTacheId !== "undefined" && ouvCandidat === fdCandidat) ? ouvTacheId : null;
      if (!tacheId || !fdCandidat) {
        if (fdDiscussion) fdDiscussion.demonter();
        fdDiscussion = null;
        fdDiscussionTache = null;
        conteneur.replaceChildren();
        carte.classList.add("cache");
        return;
      }
      carte.classList.remove("cache");
      if (fdDiscussionTache === tacheId) return;
      fdDiscussionTache = tacheId;
      fdDiscussion = monterDiscussionAgent(conteneur, tacheId);
    }

    function fdCopierEtatPc() {
      const cible = document.querySelector("#fd-etat-pc");
      const source = document.getElementById("ouverture-pc-etat");
      if (!cible || !source) return;
      const texte = source.textContent.trim();
      if (cible.textContent !== texte) cible.textContent = texte;
    }

    function fdSqueletteEtapes() {
      const ul = dosNoeud("ul", "fd-squelette");
      ul.setAttribute("aria-busy", "true");
      ul.appendChild(dosNoeud("li", "sr-only", "Chargement des étapes"));
      for (let i = 0; i < FD_ETAPES_PREVUES.length; i++) {
        const li = dosNoeud("li");
        li.setAttribute("aria-hidden", "true");
        li.appendChild(dosNoeud("span", "mo-skel squelette squelette-rond"));
        const pile = dosNoeud("span", "squelette-pile");
        pile.appendChild(dosNoeud("span", "mo-skel squelette squelette-texte"));
        pile.appendChild(dosNoeud("span", "mo-skel squelette squelette-texte court"));
        li.appendChild(pile);
        ul.appendChild(li);
      }
      return ul;
    }

    function fdEtapesAffichees() {
      if (fdEtat && fdEtat.etapes && fdEtat.etapes.length) return fdEtat.etapes;
      return FD_ETAPES_PREVUES.map((e) => ({ code: e[0], libelle: e[1], statut: "a_faire", detail: "", action_humaine: null, lien_ecran: null, compteurs: {} }));
    }

    function fdTextesProgression(etapes, progression) {
      const faites = etapes.filter((e) => e.statut === "termine").length;
      const enCours = etapes.filter((e) => e.statut === "en_cours");
      const attente = etapes.filter((e) => e.statut === "a_verifier");
      const bloquees = etapes.filter((e) => e.statut === "bloque");
      if (enCours.length) return (fdLancement ? "Analyse en cours : " : "Étape en cours : ") + fdLibelleEtape(enCours[0]) + ". " + faites + " étape(s) sur " + etapes.length + " terminée(s).";
      if (bloquees.length) return "L'analyse est bloquée à l'étape « " + fdLibelleEtape(bloquees[0]) + " ». " + faites + " étape(s) sur " + etapes.length + " terminée(s).";
      if (attente.length) return "À vous de jouer : « " + fdLibelleEtape(attente[0]) + " » attend votre vérification. " + faites + " étape(s) sur " + etapes.length + " terminée(s).";
      if (faites === etapes.length && etapes.length) return "Toutes les étapes sont terminées. Le dossier est prêt pour votre validation : rien n'a été envoyé.";
      if (progression > 0) return faites + " étape(s) sur " + etapes.length + " terminée(s).";
      return "Pas encore d'analyse : déposez les documents de l'étudiant, puis cliquez sur « Lancer l'analyse ».";
    }

    function fdRendrePiecesManquantes() {
      const zone = fdEl("fd-manquantes");
      const badge = fdEl("fd-badge-manquantes");
      if (!fdEtat) {
        zone.replaceChildren(dosNoeud("p", "note", "Les pièces manquantes s'afficheront après le premier état du dossier."));
        badge.className = "badge badge-nu";
        badge.textContent = "—";
        return;
      }
      const manquantes = Array.isArray(fdEtat.pieces_manquantes) ? fdEtat.pieces_manquantes : [];
      if (!manquantes.length) {
        const bloc = dosNoeud("p", "fd-complet");
        const svg = dosSvg("svg", { viewBox: "0 0 24 24", class: "ico", "aria-hidden": "true", focusable: "false" });
        svg.appendChild(dosSvg("circle", { cx: "12", cy: "12", r: "9", fill: "none", stroke: "currentColor", "stroke-width": "2" }));
        svg.appendChild(dosSvg("path", { d: "M8 12.5l2.7 2.7L16 9.5", fill: "none", stroke: "currentColor", "stroke-width": "2", "stroke-linecap": "round", "stroke-linejoin": "round" }));
        bloc.appendChild(svg);
        bloc.appendChild(dosNoeud("span", "", "Aucune pièce manquante."));
        zone.replaceChildren(bloc);
        badge.className = "badge badge-ok";
        badge.textContent = "Complet";
        return;
      }
      const ul = dosNoeud("ul", "fd-manquantes");
      manquantes.forEach((p) => {
        const li = document.createElement("li");
        const svg = dosSvg("svg", { viewBox: "0 0 24 24", class: "ico", "aria-hidden": "true", focusable: "false" });
        svg.appendChild(dosSvg("path", { d: "M12 4l9 16H3zM12 10v4M12 17v.5", fill: "none", stroke: "currentColor", "stroke-width": "2", "stroke-linecap": "round", "stroke-linejoin": "round" }));
        li.appendChild(svg);
        li.appendChild(dosNoeud("span", "", (typeof LIBELLES_PIECES_FR !== "undefined" && LIBELLES_PIECES_FR[p]) || String(p)));
        ul.appendChild(li);
      });
      zone.replaceChildren(ul);
      badge.className = "badge badge-warn";
      badge.textContent = manquantes.length + " à fournir";
    }

    function fdRendreAnalyse() {
      const etapes = fdEtapesAffichees();
      const progression = fdEtat && typeof fdEtat.progression === "number" ? Math.max(0, Math.min(100, Math.round(fdEtat.progression))) : 0;
      fdAnimerChiffre(fdEl("fd-progres-chiffre"), progression);
      fdEl("fd-barre").setAttribute("aria-valuenow", String(progression));
      fdEl("fd-barre").setAttribute("aria-valuetext", progression + " pour cent");
      fdEl("fd-barre-remplie").style.width = progression + "%";
      const barre = fdEl("fd-barre");
      barre.classList.toggle("ok", progression === 100);
      const reelles = fdEtat && Array.isArray(fdEtat.etapes) ? fdEtat.etapes : [];
      barre.classList.toggle("fd-actif", reelles.some((e) => e.statut === "en_cours"));
      const complet = fdMajPret(reelles);
      const texte = fdTextesProgression(etapes, progression);
      const zoneTexte = fdEl("fd-progres-texte");
      if (zoneTexte.textContent !== texte) zoneTexte.textContent = texte;
      const zone = fdEl("fd-etapes-zone");
      if (fdEtat === null && fdCandidat) {
        zone.replaceChildren(fdSqueletteEtapes());
      } else {
        fdMajEtapes(zone, etapes);
      }
      fdRendrePiecesManquantes();
      fdSynchroniserDiscussion();
      const bouton = fdEl("fd-btn-lancer");
      // L'analyse est synchrone côté serveur : « en cours » (étape partielle) ne doit jamais bloquer la relance.
      bouton.disabled = !fdCandidat || !fdEcriture() || fdLancement;
      const etat = fdLancement ? "cours" : (complet ? "termine" : "pret");
      bouton.setAttribute("data-etat", etat);
      bouton.classList.toggle("btn-primaire", etat !== "termine");
      bouton.classList.toggle("btn-contour", etat === "termine");
      bouton.lastChild.textContent = etat === "cours" ? "Analyse en cours…" : (etat === "termine" ? "Analyse terminée : relancer" : (progression > 0 ? "Relancer l'analyse" : "Lancer l'analyse"));
    }

    function fdArreterSuivi() {
      if (fdMinuteur !== null) {
        clearTimeout(fdMinuteur);
        fdMinuteur = null;
      }
    }

    function fdProgrammerSuivi() {
      fdArreterSuivi();
      const enCours = fdEtat && fdEtat.etapes && fdEtat.etapes.some((e) => e.statut === "en_cours");
      fdSuivis += 1;
      if (enCours && fdEchecs < FD_ECHECS_MAX && fdSuivis <= FD_SUIVIS_MAX && fdVisible()) {
        fdMinuteur = setTimeout(() => fdActualiser(false), FD_INTERVALLE_MS);
      }
    }

    async function fdActualiser(initial) {
      if (!fdCandidat || fdEnRequete) return;
      const candidat = fdCandidat;
      fdEnRequete = true;
      try {
        const rep = await appelApi(fdUrl("/dossier-automatique/etat"));
        if (candidat !== fdCandidat) return;
        if (rep.ok) {
          fdEtat = await rep.json();
          fdEchecs = 0;
          fdCacherErreur();
        } else {
          const corps = await rep.json().catch(() => null);
          fdEchecs += 1;
          if (fdEtat === null) fdEtat = { candidat_id: candidat, progression: 0, etapes: [], pieces_manquantes: [] };
          fdMontrerErreur(fdMessageHttp(rep.status, corps, "L'état du dossier n'a pas pu être lu."));
        }
      } catch (e) {
        if (candidat !== fdCandidat) return;
        fdEchecs += 1;
        if (fdEtat === null) fdEtat = { candidat_id: candidat, progression: 0, etapes: [], pieces_manquantes: [] };
        fdMontrerErreur(FD_MESSAGE_RESEAU);
      } finally {
        fdEnRequete = false;
      }
      fdRendreAnalyse();
      fdProgrammerSuivi();
    }

    async function fdLancer() {
      if (!fdCandidat) { notifier("Choisissez d'abord un étudiant.", false); return; }
      const enAttente = fdFichiers.filter((x) => x.statut === "attente" || x.statut === "erreur").length;
      const candidat = fdCandidat;
      fdLancement = true;
      fdRendreAnalyse();
      if (enAttente) {
        // Un seul clic : les documents choisis sont d'abord déposés (le type de chaque pièce reste à confirmer).
        await fdEnvoyerTout();
        if (fdFichiers.some((x) => x.statut === "attente" || x.statut === "erreur") || candidat !== fdCandidat) {
          fdLancement = false;
          fdRendreAnalyse();
          return;
        }
      }
      try {
        const rep = await appelApi(fdUrl("/dossier-automatique/lancer"), { method: "POST" });
        const corps = await rep.json().catch(() => null);
        if (!rep.ok) {
          const message = fdMessageHttp(rep.status, corps, "L'analyse n'a pas pu démarrer.");
          fdMontrerErreur(message);
          notifier(message, false);
          return;
        }
        fdCacherErreur();
        notifier("Analyse lancée : suivez la progression ci-dessous.", true);
        if (corps && Array.isArray(corps.etapes) && candidat === fdCandidat) fdEtat = corps;
      } catch (e) {
        fdMontrerErreur(FD_MESSAGE_RESEAU);
        notifier(FD_MESSAGE_RESEAU, false);
        return;
      } finally {
        fdLancement = false;
      }
      fdEchecs = 0;
      fdSuivis = 0;
      fdEnRequete = false;
      await fdActualiser(false);
    }

"""

_JS_BRANCHEMENT = """
    // ----- Branchement -----
    function fdInitialiserDepot() {
      const champ = fdEl("fd-fichiers");
      const zone = fdEl("fd-zone-depot");
      champ.addEventListener("change", () => {
        fdAjouterFichiers(champ.files);
        champ.value = "";
      });
      const titre = zone.querySelector(".fd-depot-titre");
      const titreRepos = titre.textContent;
      ["dragenter", "dragover"].forEach((t) => champ.addEventListener(t, () => {
        zone.classList.add("survol");
        titre.textContent = "Relâchez pour déposer";
      }));
      ["dragleave", "drop"].forEach((t) => champ.addEventListener(t, () => {
        zone.classList.remove("survol");
        titre.textContent = titreRepos;
      }));
    }

    fdInitialiserDepot();
    fdEl("fd-etudiant").addEventListener("change", (e) => fdChoisirEtudiant(e.target.value));
    fdEl("fd-btn-creer").addEventListener("click", fdCreerEtudiant);
    fdEl("fd-pp-fichier").addEventListener("change", (e) => { if (e.target.files.length) fdPpDeposer(e.target.files[0]); });
    fdEl("fd-btn-envoyer").addEventListener("click", fdEnvoyerTout);
    fdEl("fd-btn-lancer").addEventListener("click", fdLancer);
    fdEl("fd-btn-actualiser").addEventListener("click", () => { fdEchecs = 0; fdSuivis = 0; fdActualiser(false); });
    fdEl("fd-btn-reessayer").addEventListener("click", () => {
      fdEchecs = 0;
      fdCacherErreur();
      fdChargerEtudiants();
      if (fdCandidat) fdActualiser(false);
    });

    async function fdEntrer() {
      fdPpActiver();
      await fdChargerEtudiants();
      if (candidatActifId && dictionnaireCandidats[candidatActifId] && candidatActifId !== fdCandidat) {
        fdChoisirEtudiant(candidatActifId);
      } else {
        fdAfficherSelection();
        if (fdCandidat) fdActualiser(false);
      }
    }

    const allerVersVuePrecedenteFd = allerVersVue;
    allerVersVue = function (cible) {
      allerVersVuePrecedenteFd(cible);
      if (cible === FD_VUE) fdEntrer();
      else fdArreterSuivi();
    };
    fdAfficherSelection();

"""

JS_FLUX_DOSSIER = JS_FLUX_DOSSIER_MOUVEMENT + _JS_PRINCIPAL + JS_FLUX_DOSSIER_PASSEPORT + _JS_BRANCHEMENT
