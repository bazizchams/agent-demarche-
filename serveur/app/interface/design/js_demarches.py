"""JavaScript de l'interface : Pilotage du navigateur (Campus France, IRCC), centre de validation, audit, paramètres.

Chaîne Python non brute : aucun antislash (leur nombre dans la page est verrouillé par les tests).
La partie Campus France / IRCC construit l'affichage par nœuds DOM et textContent ; ses aides
`dem*` (nœud, illustration, état vide, squelette) sont réutilisées par les vœux et les procédures.
La partie validation, audit et paramètres est restée telle qu'extraite de `routeur_interface.py`.
"""

from __future__ import annotations

JS_DEMARCHES = """
    // -----------------------------------------------------------------------
    // Campus France et IRCC : pilotage du navigateur et suivi des tâches.
    // Affichage par nœuds DOM et textContent (aucune donnée interprétée en HTML).
    // Les aides dem* servent aussi aux vœux et aux procédures.
    // -----------------------------------------------------------------------

    function demNoeud(balise, classe, texte) {
      const n = document.createElement(balise);
      if (classe) n.className = classe;
      if (texte !== undefined && texte !== null) n.textContent = texte;
      return n;
    }

    function demSvg(nom, attributs) {
      const n = document.createElementNS("http://www.w3.org/2000/svg", nom);
      Object.keys(attributs).forEach((cle) => n.setAttribute(cle, attributs[cle]));
      return n;
    }

    // Illustration d'état vide : « dossier » (feuille + coche) ou « alerte » (feuille + point d'exclamation).
    function demIllustration(sorte) {
      const svg = demSvg("svg", { viewBox: "0 0 96 72", class: "etat-vide-illu", "aria-hidden": "true", focusable: "false" });
      svg.appendChild(demSvg("rect", { x: "6", y: "18", width: "72", height: "48", rx: "9", class: "illu-fond" }));
      svg.appendChild(demSvg("rect", { x: "18", y: "6", width: "48", height: "40", rx: "6", class: "illu-papier" }));
      svg.appendChild(demSvg("path", { d: "M27 17h24M27 25h30M27 33h16", class: "illu-trait" }));
      svg.appendChild(demSvg("circle", { cx: "72", cy: "50", r: "14", class: "illu-accent" }));
      svg.appendChild(demSvg("path", { d: sorte === "alerte" ? "M72 43v8M72 56v1" : "M65.5 50.5l4.5 4.5 8-9", class: "illu-coche" }));
      return svg;
    }

    function demEtatVide(titre, texte, sorte, balise) {
      const bloc = demNoeud(balise || "div", "etat-vide");
      bloc.appendChild(demIllustration(sorte || "dossier"));
      bloc.appendChild(demNoeud("strong", "", titre));
      if (texte) bloc.appendChild(demNoeud("span", "", texte));
      return bloc;
    }

    // Lignes de squelette (remplacent « Chargement… ») ; le conteneur porte aria-busy.
    function demSquelette(nbLignes) {
      const frag = document.createDocumentFragment();
      frag.appendChild(demNoeud("span", "sr-only", "Chargement en cours"));
      for (let i = 0; i < nbLignes; i += 1) {
        const ligne = demNoeud("div", "ligne-squelette");
        ligne.setAttribute("aria-hidden", "true");
        ligne.appendChild(demNoeud("span", "squelette squelette-pastille"));
        const pile = demNoeud("span", "squelette-pile");
        pile.appendChild(demNoeud("span", "squelette squelette-texte"));
        pile.appendChild(demNoeud("span", "squelette squelette-texte court"));
        ligne.appendChild(pile);
        frag.appendChild(ligne);
      }
      return frag;
    }

    function demBlocListe(titre, elements, ton, coche) {
      const bloc = demNoeud("div", "retour-bloc");
      bloc.appendChild(demNoeud("p", "retour-titre" + (ton ? " " + ton : ""), titre));
      const ul = demNoeud("ul", "liste-propre");
      elements.forEach((e) => ul.appendChild(demNoeud("li", coche ? "ok" : "", e)));
      bloc.appendChild(ul);
      return bloc;
    }

    function demBoutonSpecimens(codeDemarche, libelle) {
      const b = demNoeud("button", "btn btn-secondaire btn-sm", libelle);
      b.type = "button";
      b.addEventListener("click", () => completerPiecesSpecimensEtRelancer(codeDemarche));
      return b;
    }

    function demNomDemarche(codeDemarche) {
      return codeDemarche === "campus_france" ? "Campus France — Études en France" : "IRCC Canada — Permis d'études";
    }

    // Compte rendu d'une action du co-pilote : renvoie un fragment DOM.
    function formaterCompteRenduPilotageHtml(res) {
      const frag = document.createDocumentFragment();
      const entete = demNoeud("div", "retour-entete");
      const titres = demNoeud("div");
      titres.appendChild(demNoeud("strong", "", res.titre_page || "Navigateur de l'agent"));
      titres.appendChild(demNoeud("span", "note", "Adresse ouverte : " + (res.url_courante || "—")));
      entete.appendChild(titres);
      entete.appendChild(demNoeud("span", "badge " + (res.succes ? "badge-ok" : "badge-warn"),
        res.succes ? "Action exécutée par l'agent" : "Intervention humaine requise"));
      frag.appendChild(entete);
      frag.appendChild(demNoeud("div", "notif " + (res.succes ? "notif-ok" : "notif-err"), res.resume_francais || ""));

      if (res.statut_tache) {
        const statut = demNoeud("p", "retour-statut");
        statut.appendChild(demNoeud("strong", "", "Statut du dossier : "));
        statut.appendChild(demNoeud("span", "badge " + classeBadgeStatutTache(res.statut_tache),
          LIBELLES_STATUT_TACHE_FR[res.statut_tache] || res.statut_tache));
        frag.appendChild(statut);
      }

      const manquantes = res.pieces_manquantes_tache || [];
      if (manquantes.length > 0) {
        const banniere = demNoeud("div", "banniere-regle banniere-alerte retour-bloc");
        const contenu = demNoeud("div");
        contenu.appendChild(demNoeud("strong", "", "Dossier en pause : pièces à téléverser avant le passage au Centre de validation."));
        const ul = demNoeud("ul", "liste-propre");
        manquantes.forEach((tp) => ul.appendChild(demNoeud("li", "", LIBELLES_PIECES_FR[tp] || tp)));
        contenu.appendChild(ul);
        contenu.appendChild(demBoutonSpecimens(res.code_demarche,
          "Déposer les pièces spécimens de démo et lancer le pré-remplissage complet"));
        banniere.appendChild(contenu);
        frag.appendChild(banniere);
      }

      const blocs = [
        [res.etapes_realisees, "Actions réalisées dans le navigateur", "", true],
        [res.champs_remplis_libelles, "Champs pré-remplis automatiquement", "ok", true],
        [res.pieces_televersees_libelles, "Pièces justificatives téléversées sur la page", "ok", true],
        [res.champs_manquants_libelles, "Informations absentes de la fiche candidat (règle 4 : aucune valeur inventée)", "alerte", false],
        [res.avertissements_securite, "Garde-fous de sécurité actifs", "", false],
      ];
      blocs.forEach(([liste, titre, ton, coche]) => {
        if (liste && liste.length > 0) {
          const compte = ton === "ok" ? " (" + liste.length + ")" : "";
          frag.appendChild(demBlocListe(titre + compte, liste, ton, coche));
        }
      });

      if (res.capture_base64) {
        const bloc = demNoeud("div", "retour-bloc");
        bloc.appendChild(demNoeud("p", "retour-titre", "Capture d'écran du navigateur piloté par l'agent"));
        const img = demNoeud("img", "capture-apercu");
        img.alt = "Capture d'écran du navigateur";
        img.src = "data:image/png;base64," + res.capture_base64;
        bloc.appendChild(img);
        frag.appendChild(bloc);
      }
      return frag;
    }

    function demAfficherChargementPilotage(zone) {
      zone.setAttribute("aria-busy", "true");
      zone.replaceChildren(
        demNoeud("p", "retour-titre", "Le co-pilote exécute votre demande dans le navigateur. Cela prend quelques secondes."),
        demSquelette(3)
      );
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

      demAfficherChargementPilotage(zone);

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

      zone.setAttribute("aria-busy", "false");
      if (rep.ok) {
        const res = await rep.json();
        zone.replaceChildren(formaterCompteRenduPilotageHtml(res));
        annoncer("Compte rendu du pilotage disponible.");
        await rafraichirTableauDeBord();
        notifier(res.resume_francais, res.succes);
      } else {
        const err = await rep.json().catch(() => ({}));
        const message = err.detail || "Erreur lors du pilotage du navigateur.";
        zone.replaceChildren(demNoeud("div", "notif notif-err", message));
        notifier(message, false);
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

    // -----------------------------------------------------------------------
    // Cadre « Navigateur et assistant » : barre d'adresse, actions rapides, synchronisation,
    // vue capture, puces d'exemples et dictée vocale. Tout passe par les routes existantes
    // (/api/v1/portails/action-dom-directe, /api/v1/portails/etat-navigateur,
    // /api/v1/navigateur/etat et /capture) via appelApi (en-tête CSRF).
    // Règle 6 : contrôle du domaine côté client (domaines des YAML via /api/v1/portails),
    // puis contrôle définitif côté serveur. Règle 1 : aucune de ces actions ne clique un bouton.
    // -----------------------------------------------------------------------

    const PREFIXES_DIRECT = { campus_france: "cf", ircc_permis_etudes: "ircc" };
    const ACTIONS_DOM_RAPIDES = ["retour", "suivant", "actualiser", "scroll_haut", "scroll_bas", "focus_fenetre"];
    const LIBELLES_TYPE_ELEMENT = {
      champ: "Champ", liste: "Liste", zone_texte: "Zone de texte", bouton: "Bouton", lien: "Lien", fichier: "Fichier",
    };
    let etatsDirects = {
      campus_france: { cible: "campus_france_officiel", mode: "dom" },
      ircc_permis_etudes: { cible: "ircc_officiel", mode: "dom" },
    };
    let domainesAutorisesParDemarche = null;
    let dicteeEnCours = null;

    function dirPrefixe(codeDemarche) {
      return PREFIXES_DIRECT[codeDemarche] || null;
    }

    function dirElement(codeDemarche, suffixe) {
      const p = dirPrefixe(codeDemarche);
      return p ? document.getElementById(p + "-" + suffixe) : null;
    }

    function dirMettreAJourEtat(codeDemarche, changements) {
      etatsDirects = Object.assign({}, etatsDirects, {
        [codeDemarche]: Object.assign({}, etatsDirects[codeDemarche], changements),
      });
    }

    function dirRetour(codeDemarche, message, ok) {
      const zone = document.getElementById("zone-retour-" + dirPrefixe(codeDemarche));
      if (zone) zone.replaceChildren(demNoeud("div", "notif " + (ok ? "notif-ok" : "notif-err"), message));
      notifier(message, ok);
    }

    async function dirLireErreur(rep, defaut) {
      const err = await rep.json().catch(() => ({}));
      return typeof err.detail === "string" ? err.detail : defaut;
    }

    function dirAfficherElements(codeDemarche, titre, url, elements) {
      const titreEl = dirElement(codeDemarche, "titre-page-live");
      if (titreEl && titre) titreEl.textContent = titre;
      const urlEl = dirElement(codeDemarche, "url-live");
      if (urlEl && url) urlEl.value = url;
      const conteneur = dirElement(codeDemarche, "elements-dom-live");
      if (!conteneur) return;
      const liste = Array.isArray(elements) ? elements : [];
      if (liste.length === 0) {
        conteneur.replaceChildren(demNoeud("p", "aide", "Aucun champ ni bouton visible sur la page ouverte."));
        return;
      }
      const ul = demNoeud("ul", "liste-propre");
      liste.forEach((e) => {
        const li = demNoeud("li");
        li.appendChild(demNoeud("strong", "", (LIBELLES_TYPE_ELEMENT[e.type_element] || "Élément") + " : "));
        li.appendChild(document.createTextNode(String(e.libelle || "")));
        ul.appendChild(li);
      });
      conteneur.replaceChildren(
        demNoeud("p", "aide", liste.length + " élément(s) interactif(s) visible(s) sur la page."), ul);
    }

    function dirChargerCapture(codeDemarche) {
      const img = dirElement(codeDemarche, "capture-direct");
      const message = dirElement(codeDemarche, "capture-message");
      if (!img || !message) return;
      message.textContent = "Chargement de la capture…";
      img.onload = () => {
        img.classList.remove("cache");
        message.textContent = "Capture de la page ouverte dans le navigateur du bureau.";
      };
      img.onerror = () => {
        img.classList.add("cache");
        message.textContent = "Aucune capture disponible : ouvrez d'abord le site avec « Ouvrir le site ».";
      };
      img.src = "/api/v1/navigateur/capture?jeton=" + Date.now();
    }

    async function dirNavigateurOuvert() {
      const rep = await appelApi("/api/v1/navigateur/etat");
      if (!rep.ok) return { ok: false, message: await dirLireErreur(rep, "État du navigateur indisponible.") };
      const etat = await rep.json();
      return { ok: true, ouvert: Boolean(etat.navigateur_ouvert), etat: etat };
    }

    async function dirEnvoyerActionDom(codeDemarche, corps) {
      const visible = dirElement(codeDemarche, "fenetre-visible");
      const rep = await appelApi("/api/v1/portails/action-dom-directe", {
        method: "POST",
        body: JSON.stringify(Object.assign({}, corps, { ouvrir_fenetre_visible: visible ? visible.checked : true })),
      });
      if (!rep.ok) {
        dirRetour(codeDemarche, await dirLireErreur(rep, "Action refusée par le serveur."), false);
        return;
      }
      const res = await rep.json();
      dirAfficherElements(codeDemarche, res.titre_page, res.url_courante, res.elements_interactifs_page);
      if (etatsDirects[codeDemarche].mode === "capture") dirChargerCapture(codeDemarche);
      dirRetour(codeDemarche, res.message || "Action exécutée.", Boolean(res.succes));
    }

    // Actions rapides de la barre (précédent, suivant, actualiser, haut, bas, premier plan) :
    // toutes existent côté serveur (type_operation de /portails/action-dom-directe).
    async function executerActionDomRapide(codeDemarche, action) {
      if (!dirPrefixe(codeDemarche) || !ACTIONS_DOM_RAPIDES.includes(action)) {
        notifier("Action de navigation inconnue.", false);
        return;
      }
      const etat = await dirNavigateurOuvert();
      if (!etat.ok) {
        dirRetour(codeDemarche, etat.message, false);
        return;
      }
      if (!etat.ouvert) {
        dirRetour(codeDemarche, "Aucun navigateur ouvert pour votre bureau : cliquez d'abord sur « Ouvrir le site ».", false);
        return;
      }
      await dirEnvoyerActionDom(codeDemarche, { type_operation: action });
    }

    async function dirChargerDomainesAutorises() {
      if (domainesAutorisesParDemarche) return domainesAutorisesParDemarche;
      const rep = await appelApi("/api/v1/portails");
      if (!rep.ok) return null;
      const portails = await rep.json();
      const table = {};
      portails.forEach((p) => {
        const liste = table[p.code_demarche] || [];
        table[p.code_demarche] = liste.concat((p.domaines_autorises || []).map((d) => String(d).toLowerCase()));
      });
      domainesAutorisesParDemarche = table;
      return table;
    }

    // Règle 6 côté client : HTTPS et hôte exact parmi les domaines du portail ; pages de démonstration
    // locales acceptées ici, le serveur les refuse en production.
    function dirMotifRefusUrl(texte, domaines) {
      let analyse;
      try {
        analyse = new URL(texte);
      } catch (e) {
        return "Adresse invalide : saisissez une adresse complète commençant par https://.";
      }
      if (analyse.username || analyse.password) return "Navigation refusée (règle 6) : adresse avec identifiants intégrés.";
      const hote = analyse.hostname.toLowerCase();
      if (hote === "portail.local" && analyse.pathname.startsWith("/demo/")) return null;
      if (analyse.protocol !== "https:") return "Navigation refusée (règle 6) : seules les adresses HTTPS officielles sont acceptées.";
      if (!domaines.includes(hote)) return "Navigation refusée (règle 6) : le domaine « " + hote + " » n'est pas un domaine officiel de ce portail.";
      return null;
    }

    async function naviguerUrlDirecte(codeDemarche) {
      const champ = dirElement(codeDemarche, "url-live");
      if (!champ) return;
      const texte = champ.value.trim();
      if (!texte) {
        dirRetour(codeDemarche, "Saisissez l'adresse à ouvrir.", false);
        return;
      }
      const table = await dirChargerDomainesAutorises();
      if (!table) {
        dirRetour(codeDemarche, "Navigation annulée (règle 6) : impossible de vérifier les domaines officiels du portail.", false);
        return;
      }
      const refus = dirMotifRefusUrl(texte, table[codeDemarche] || []);
      if (refus) {
        dirRetour(codeDemarche, refus, false);
        return;
      }
      await dirEnvoyerActionDom(codeDemarche, { type_operation: "naviguer", url_destination: texte });
    }

    function basculerModeVueDirecte(codeDemarche) {
      const p = dirPrefixe(codeDemarche);
      if (!p) return;
      const versCapture = etatsDirects[codeDemarche].mode !== "capture";
      dirMettreAJourEtat(codeDemarche, { mode: versCapture ? "capture" : "dom" });
      dirElement(codeDemarche, "panneau-dom-live").classList.toggle("cache", versCapture);
      dirElement(codeDemarche, "vue-capture").classList.toggle("cache", !versCapture);
      const bouton = document.getElementById("btn-mode-vue-" + p);
      if (bouton) bouton.textContent = versCapture ? "Vue : capture de la page" : "Vue : contrôle DOM et fenêtre";
      if (versCapture) dirChargerCapture(codeDemarche);
    }

    async function synchroniserEtatNavigateurDirect(codeDemarche) {
      if (!dirPrefixe(codeDemarche)) return;
      const etat = await dirNavigateurOuvert();
      if (!etat.ok) {
        dirRetour(codeDemarche, etat.message, false);
        return;
      }
      if (!etat.ouvert) {
        dirAfficherElements(codeDemarche, "Aucun navigateur ouvert", "", []);
        dirRetour(codeDemarche, "Aucun navigateur ouvert pour votre bureau : cliquez d'abord sur « Ouvrir le site ».", false);
        return;
      }
      const rep = await appelApi("/api/v1/portails/etat-navigateur");
      if (!rep.ok) {
        dirRetour(codeDemarche, await dirLireErreur(rep, "Synchronisation impossible."), false);
        return;
      }
      const detail = await rep.json();
      dirAfficherElements(codeDemarche, detail.titre_page || etat.etat.titre_page, detail.url_courante || etat.etat.url_courante,
        detail.elements_interactifs_page);
      if (etatsDirects[codeDemarche].mode === "capture") dirChargerCapture(codeDemarche);
      if (etat.etat.controle_securite_detecte) {
        dirRetour(codeDemarche, "CAPTCHA ou code de sécurité détecté : à résoudre par vous (règle 2).", false);
        return;
      }
      notifier("Navigateur synchronisé.", true);
    }

    // Portail choisi : mémorisé et reporté dans la barre d'adresse. « Ouvrir le site » lit déjà ce choix.
    function changerCibleNavigateurDirect(codeDemarche) {
      const liste = dirElement(codeDemarche, "cible-navigateur");
      if (!liste) return;
      dirMettreAJourEtat(codeDemarche, { cible: liste.value });
      const option = liste.options[liste.selectedIndex];
      const url = option ? option.getAttribute("data-url") : "";
      const champ = dirElement(codeDemarche, "url-live");
      if (champ && url) champ.value = url;
    }

    // Puce d'exemple : même chemin que le bouton « Exécuter ».
    function envoyerConsigneRapideCopilote(codeDemarche, texte) {
      const p = dirPrefixe(codeDemarche);
      const champ = dirElement(codeDemarche, "instruction-agent");
      const bouton = p ? document.getElementById("btn-piloter-" + p + "-instruction") : null;
      if (!champ || !bouton) return;
      champ.value = String(texte || "");
      bouton.click();
    }

    function dirReconnaissanceVocale() {
      return window.SpeechRecognition || window.webkitSpeechRecognition || null;
    }

    // Dictée (Web Speech API du navigateur, fr-FR) : remplit le champ de consigne, sans rien
    // envoyer à notre serveur ; l'opérateur relit puis clique sur « Exécuter ».
    function demarrerDicteeVocale(codeDemarche) {
      const p = dirPrefixe(codeDemarche);
      const champ = dirElement(codeDemarche, "instruction-agent");
      const bouton = p ? document.getElementById("btn-dictee-" + p) : null;
      if (!champ || !bouton) return;
      const Reconnaissance = dirReconnaissanceVocale();
      if (!Reconnaissance) {
        bouton.disabled = true;
        dirRetour(codeDemarche, "La dictée vocale n'est pas disponible dans ce navigateur : saisissez la consigne au clavier.", false);
        return;
      }
      if (dicteeEnCours) {
        dicteeEnCours.stop();
        return;
      }
      const rec = new Reconnaissance();
      rec.lang = "fr-FR";
      rec.interimResults = false;
      rec.maxAlternatives = 1;
      rec.onresult = (ev) => {
        const resultat = ev.results && ev.results[0] && ev.results[0][0];
        if (resultat && resultat.transcript) {
          champ.value = resultat.transcript.trim();
          dirRetour(codeDemarche, "Consigne dictée. Relisez-la puis cliquez sur « Exécuter ».", true);
        }
      };
      rec.onerror = (ev) => {
        const refus = ev.error === "not-allowed" || ev.error === "service-not-allowed";
        dirRetour(codeDemarche, refus ? "Micro refusé : autorisez le micro pour cette page ou saisissez la consigne."
          : "Dictée interrompue : aucune parole reconnue.", false);
      };
      rec.onend = () => {
        dicteeEnCours = null;
        bouton.setAttribute("aria-pressed", "false");
      };
      dicteeEnCours = rec;
      bouton.setAttribute("aria-pressed", "true");
      try {
        rec.start();
        notifier("Dictée en cours : parlez, puis cliquez à nouveau sur le micro pour arrêter.", true);
      } catch (e) {
        dicteeEnCours = null;
        bouton.setAttribute("aria-pressed", "false");
        dirRetour(codeDemarche, "Impossible de démarrer la dictée vocale.", false);
      }
    }

    (function dirBrancherCadres() {
      const dicteeDispo = Boolean(dirReconnaissanceVocale());
      Object.keys(PREFIXES_DIRECT).forEach((codeDemarche) => {
        const p = PREFIXES_DIRECT[codeDemarche];
        const micro = document.getElementById("btn-dictee-" + p);
        if (micro && !dicteeDispo) {
          micro.disabled = true;
          micro.title = "Dictée vocale indisponible dans ce navigateur (Web Speech API absente)";
          const zone = document.getElementById("zone-retour-" + p);
          if (zone) zone.appendChild(demNoeud("p", "note",
            "La dictée vocale n'est pas disponible dans ce navigateur : saisissez la consigne au clavier."));
        }
        const champUrl = dirElement(codeDemarche, "url-live");
        if (champUrl) {
          champUrl.addEventListener("keydown", (ev) => {
            if (ev.key === "Enter") naviguerUrlDirecte(codeDemarche);
          });
        }
      });
    })();

    // Statut d'une étape de tâche -> composant « étapes » du guide.
    const ETAPE_TACHE_AFFICHAGE = {
      terminee: { classe: "etape-faite", texte: "Terminée" },
      en_cours: { classe: "etape-courante", texte: "En cours" },
      suspendue: { classe: "etape-bloquee", texte: "En attente de complétion" },
      en_erreur: { classe: "etape-bloquee", texte: "En erreur" },
    };

    function demConstruireEtapes(etapes) {
      const ol = demNoeud("ol", "etapes");
      ol.setAttribute("aria-label", "Progression des étapes de la démarche");
      etapes.forEach((e) => {
        const aff = ETAPE_TACHE_AFFICHAGE[e.statut] || { classe: "", texte: "À faire" };
        const li = demNoeud("li", "etape " + aff.classe);
        if (e.statut === "en_cours") li.setAttribute("aria-current", "step");
        li.appendChild(demNoeud("span", "etape-titre", e.libelle));
        li.appendChild(document.createTextNode(aff.texte));
        ol.appendChild(li);
      });
      return ol;
    }

    // Suivi d'une tâche : renvoie un fragment DOM (en-tête, alertes, étapes).
    function formaterTacheEnTexteHtml(tache, codeDemarche) {
      const frag = document.createDocumentFragment();
      const entete = demNoeud("div", "retour-entete");
      const titres = demNoeud("div");
      titres.appendChild(demNoeud("span", "surtitre", "Suivi de la démarche"));
      titres.appendChild(demNoeud("strong", "", "Suivi de la tâche " + demNomDemarche(codeDemarche)));
      entete.appendChild(titres);
      entete.appendChild(demNoeud("span", "badge " + classeBadgeStatutTache(tache.statut),
        LIBELLES_STATUT_TACHE_FR[tache.statut] || tache.statut));
      frag.appendChild(entete);

      if (tache.etapes && tache.etapes.length > 0) {
        frag.appendChild(demConstruireEtapes(tache.etapes));
      }

      if (tache.message_alerte) {
        frag.appendChild(demNoeud("div", "banniere-regle", tache.message_alerte));
      }

      const pieces = tache.pieces_manquantes || [];
      if (pieces.length > 0) {
        const bloc = demBlocListe("Pièces obligatoires à fournir avant l'envoi officiel",
          pieces.map((tp) => LIBELLES_PIECES_FR[tp] || tp), "critique", false);
        bloc.appendChild(demBoutonSpecimens(codeDemarche,
          "Déposer les pièces spécimens de démo et lancer le pré-remplissage par l'agent"));
        frag.appendChild(bloc);
      }

      const champs = tache.champs_manquants || [];
      if (champs.length > 0) {
        frag.appendChild(demBlocListe("Informations à compléter dans la fiche candidat",
          champs.map((ch) => LIBELLES_CHAMPS_FR[ch] || ch), "alerte", false));
      }
      return frag;
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
      const zone = document.getElementById(zoneId);
      const rep = await appelApi("/api/v1/taches", {
        method: "POST",
        body: JSON.stringify({ candidat_id: candidatActifId, code_demarche: codeDemarche }),
      });
      if (rep.ok) {
        const tache = await rep.json();
        zone.replaceChildren(formaterTacheEnTexteHtml(tache, codeDemarche));
        annoncer("Suivi de la tâche mis à jour.");
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
            zone.replaceChildren(formaterTacheEnTexteHtml(tacheExistante, codeDemarche));
            notifier("Affichage de la tâche en cours pour ce candidat.", true);
            return;
          }
        }
        const err = await rep.json().catch(() => ({}));
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
