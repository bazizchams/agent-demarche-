"""JavaScript du mouvement de l'écran « Dossier automatique » (stepper, compteur, fichiers, célébration).

Chaîne Python non brute : AUCUN antislash. Nœuds DOM + `textContent` uniquement, aucun `console.log`.
Rien ici n'envoie ni ne valide quoi que ce soit : ce sont des effets d'affichage (règle 1).
Les animations fonctionnent sans le module de mouvement partagé (`window.Mouvement`) ; sous
`prefers-reduced-motion`, aucune animation n'est lancée et toutes les informations restent affichées.
"""

from __future__ import annotations

JS_FLUX_DOSSIER_MOUVEMENT = """
    // -----------------------------------------------------------------------
    // Mouvement : mouvement réduit, compteur animé, stepper en place, fichiers, illustration.
    // -----------------------------------------------------------------------
    // Langage commun (window.Mouvement) quand il est présent ; repli local sinon.
    const FD_REDUIT = window.matchMedia("(prefers-reduced-motion: reduce)");
    function fdMv() {
      return window.Mouvement || null;
    }
    function fdReduit() {
      const mv = fdMv();
      return mv && typeof mv.reduit === "function" ? !!mv.reduit() : FD_REDUIT.matches;
    }

    let fdRaf = 0;
    function fdDureeChiffre(de, vers) {
      return 250 + Math.min(450, Math.abs(vers - de) * 12);
    }
    // Repli local : la valeur est dans `.fd-progres-valeur` si présent, sinon le texte entier porte « N % ».
    function fdAnimerChiffre(el, vers) {
      const valeur = el.querySelector(".fd-progres-valeur");
      const cible = valeur || el;
      const suffixe = valeur ? "" : " %";
      const de = parseInt(el.getAttribute("data-valeur") || "0", 10);
      el.setAttribute("data-valeur", String(vers));
      if (fdRaf) cancelAnimationFrame(fdRaf);
      fdRaf = 0;
      const mv = fdMv();
      if (valeur && mv && typeof mv.compteur === "function") {
        mv.compteur(valeur, vers, fdDureeChiffre(de, vers));
        return;
      }
      if (fdReduit() || de === vers) {
        cible.textContent = vers + suffixe;
        return;
      }
      const debut = performance.now();
      const duree = fdDureeChiffre(de, vers);
      const pas = (t) => {
        const k = Math.min(1, (t - debut) / duree);
        cible.textContent = Math.round(de + (vers - de) * (1 - Math.pow(1 - k, 3))) + suffixe;
        fdRaf = k < 1 ? requestAnimationFrame(pas) : 0;
      };
      fdRaf = requestAnimationFrame(pas);
    }

    // ----- Illustration de l'état vide -----
    function fdIllustrationVide() {
      const svg = dosSvg("svg", { viewBox: "0 0 168 112", class: "fd-illu", "aria-hidden": "true", focusable: "false" });
      const ajouter = (nom, attributs) => svg.appendChild(dosSvg(nom, attributs));
      ajouter("line", { class: "fd-illu-trait", x1: "14", y1: "100", x2: "154", y2: "100" });
      ajouter("rect", { class: "fd-illu-fond", x: "46", y: "40", width: "76", height: "52", rx: "6" });
      ajouter("path", { class: "fd-illu-accent", d: "M46 48 Q46 40 54 40 L72 40 Q76 40 78 44 L81 48 Z" });
      ajouter("path", { class: "fd-illu-papier", d: "M64 24 L92 24 L100 32 L100 62 L64 62 Z" });
      ajouter("line", { class: "fd-illu-trait", x1: "70", y1: "34", x2: "90", y2: "34" });
      ajouter("line", { class: "fd-illu-trait", x1: "70", y1: "42", x2: "94", y2: "42" });
      ajouter("line", { class: "fd-illu-trait", x1: "70", y1: "50", x2: "86", y2: "50" });
      ajouter("path", { class: "fd-illu-papier", d: "M84 30 L112 30 L118 36 L118 64 L84 64 Z" });
      ajouter("line", { class: "fd-illu-trait", x1: "90", y1: "44", x2: "110", y2: "44" });
      ajouter("line", { class: "fd-illu-trait", x1: "90", y1: "52", x2: "106", y2: "52" });
      ajouter("path", { class: "fd-illu-fond", d: "M42 58 L52 96 L116 96 L124 58 Z" });
      ajouter("line", { class: "fd-illu-lien", x1: "146", y1: "28", x2: "146", y2: "84" });
      ajouter("circle", { class: "fd-illu-point fd-illu-pas", cx: "146", cy: "28", r: "6" });
      ajouter("circle", { class: "fd-illu-point fd-illu-pas", cx: "146", cy: "56", r: "6" });
      ajouter("circle", { class: "fd-illu-accent fd-illu-pas", cx: "146", cy: "84", r: "6" });
      ajouter("path", { class: "fd-illu-coche fd-illu-coche-trace", d: "M143 84.2 L145.4 86.6 L150 81.6", pathLength: "1" });
      return svg;
    }

    // ----- Stepper : mise à jour en place (les transitions CSS jouent, rien n'est reconstruit sans changement) -----
    function fdIconeEtape(statut, animer) {
      const svg = dosSvg("svg", { viewBox: "0 0 24 24", class: "ico", focusable: "false", "aria-hidden": "true" });
      const trait = { fill: "none", stroke: "currentColor", "stroke-linecap": "round", "stroke-linejoin": "round" };
      if (statut === "termine") {
        svg.appendChild(dosSvg("path", Object.assign({ d: "M5 12.5l4.5 4.5L19 7.5", "stroke-width": "2.5", pathLength: "1", class: animer ? "fd-coche fd-coche-trace" : "fd-coche" }, trait)));
      } else if (statut === "a_verifier") {
        svg.appendChild(dosSvg("path", Object.assign({ d: "M12 4l9 16H3zM12 10v4M12 17v.5", "stroke-width": "2" }, trait)));
      } else if (statut === "bloque") {
        svg.appendChild(dosSvg("path", Object.assign({ d: "M8 8l8 8M16 8l-8 8", "stroke-width": "2.5" }, trait)));
      } else {
        return null;
      }
      return svg;
    }

    function fdRemplirMarqueur(marqueur, statut, rang, animer) {
      const icone = fdIconeEtape(statut, animer);
      if (icone) marqueur.replaceChildren(icone);
      else marqueur.textContent = String(rang);
      marqueur.classList.remove("fd-marqueur-pop");
      if (animer && !fdReduit() && statut !== "a_faire") {
        void marqueur.offsetWidth;
        marqueur.classList.add("fd-marqueur-pop");
      }
    }

    function fdRemplirCorps(corps, etape, statut) {
      const [libelleStatut, classeBadge] = FD_STATUTS[statut];
      const ligne = dosNoeud("div", "fd-ligne");
      ligne.appendChild(dosNoeud("h4", "fd-titre", fdLibelleEtape(etape)));
      ligne.appendChild(dosNoeud("span", "badge " + classeBadge, libelleStatut));
      const enfants = [ligne];
      const detail = fdDetailEtape(etape);
      if (detail) enfants.push(dosNoeud("p", "fd-detail", detail));
      const compteurs = fdCompteurs(etape.compteurs);
      if (compteurs) enfants.push(compteurs);
      const actions = fdActionsEtape(Object.assign({}, etape, { statut: statut }));
      if (actions) enfants.push(actions);
      corps.replaceChildren(...enfants);
    }

    function fdSignature(etape, statut) {
      return [statut, etape.libelle, etape.detail, etape.action_humaine, etape.lien_ecran, JSON.stringify(etape.compteurs || {})].join("|");
    }

    function fdNouvelleEtape(etape, rang, entree) {
      const li = dosNoeud("li", "fd-etape");
      li.setAttribute("data-code", etape.code);
      li.appendChild(dosNoeud("span", "fd-marqueur"));
      li.lastChild.setAttribute("aria-hidden", "true");
      li.appendChild(dosNoeud("div", "fd-corps"));
      if (entree && !fdReduit() && !fdMv()) {
        li.classList.add("fd-entree");
        li.style.animationDelay = (rang - 1) * 45 + "ms";
        li.addEventListener("animationend", (ev) => { if (ev.target === li) li.classList.remove("fd-entree"); });
      }
      return li;
    }

    function fdMajEtape(li, etape, rang, animer) {
      const statut = FD_STATUTS[etape.statut] ? etape.statut : "a_faire";
      const signature = fdSignature(etape, statut);
      if (li.getAttribute("data-sig") === signature) return;
      const ancien = li.getAttribute("data-statut");
      li.setAttribute("data-sig", signature);
      li.setAttribute("data-statut", statut);
      li.setAttribute("data-code", etape.code);
      li.classList.remove("fd-etape-a_faire", "fd-etape-en_cours", "fd-etape-termine", "fd-etape-a_verifier", "fd-etape-bloque");
      li.classList.add("fd-etape-" + statut);
      if (ancien !== statut) fdRemplirMarqueur(li.firstChild, statut, rang, animer && ancien !== null);
      fdRemplirCorps(li.lastChild, etape, statut);
    }

    function fdMajEtapes(zone, etapes) {
      let ol = zone.querySelector("ol.fd-etapes");
      const neuf = !ol;
      if (neuf) {
        ol = dosNoeud("ol", "fd-etapes");
        ol.setAttribute("aria-label", "Étapes du dossier automatique");
        zone.replaceChildren(ol);
      }
      etapes.forEach((etape, i) => {
        let li = ol.children[i];
        if (!li) {
          li = fdNouvelleEtape(etape, i + 1, neuf);
          ol.appendChild(li);
        }
        fdMajEtape(li, etape, i + 1, true);
      });
      while (ol.children.length > etapes.length) ol.removeChild(ol.lastChild);
      // Premier affichage seulement (le sondage périodique met à jour en place, sans re-rendre) : entrée décalée commune.
      if (neuf && fdMv() && typeof fdMv().cascade === "function") fdMv().cascade(ol.children);
    }

    // ----- Fichiers : une ligne persistante par fichier (barre, état, message) -----
    let fdLignes = {};

    function fdCreerLigne(entree) {
      const li = dosNoeud("li", "fd-fichier");
      const nom = dosNoeud("span", "fd-fichier-nom", entree.fichier.name + " (" + fdTaille(entree.fichier.size) + ")");
      const badge = dosNoeud("span", "badge");
      const barre = dosNoeud("div", "fd-fichier-barre");
      barre.setAttribute("role", "progressbar");
      barre.setAttribute("aria-valuemin", "0");
      barre.setAttribute("aria-valuemax", "100");
      barre.setAttribute("aria-label", "Envoi de " + entree.fichier.name);
      const remplie = dosNoeud("div", "fd-fichier-remplie");
      barre.appendChild(remplie);
      const meta = dosNoeud("div", "fd-fichier-meta");
      const message = dosNoeud("div", "fd-fichier-message");
      li.append(nom, badge, barre, meta, message);
      if (fdMv() && typeof fdMv().cascade === "function") {
        fdMv().cascade([li]);
      } else if (!fdReduit()) {
        li.classList.add("fd-entree");
        li.addEventListener("animationend", (ev) => { if (ev.target === li) li.classList.remove("fd-entree"); });
      }
      return { li: li, badge: badge, barre: barre, remplie: remplie, meta: meta, message: message };
    }

    function fdMajLigne(ligne, entree) {
      const [libelle, classe] = FD_LIBELLES_ENVOI[entree.statut];
      ligne.badge.className = "badge " + classe;
      ligne.badge.textContent = libelle;
      ligne.li.setAttribute("data-statut", entree.statut);
      ligne.barre.className = "fd-fichier-barre fd-barre-" + entree.statut;
      if (entree.statut === "envoi") {
        ligne.barre.removeAttribute("aria-valuenow");
        ligne.barre.setAttribute("aria-valuetext", "Envoi en cours");
      } else {
        const valeur = entree.statut === "ok" ? 100 : 0;
        ligne.barre.setAttribute("aria-valuenow", String(valeur));
        ligne.barre.setAttribute("aria-valuetext", entree.statut === "ok" ? "Envoyé" : (entree.statut === "erreur" ? "Refusé" : "En attente d'envoi"));
        ligne.remplie.style.width = entree.statut === "ok" ? "100%" : (entree.statut === "erreur" ? "100%" : "0%");
      }
      const enfants = [];
      if (entree.statut === "ok") {
        enfants.push(dosNoeud("span", "fd-suggestion", "Type : " + fdLibelleType(entree.type)));
      } else {
        const select = document.createElement("select");
        select.setAttribute("aria-label", "Type de la pièce " + entree.fichier.name);
        select.disabled = fdEnvoi;
        fdOptionsTypes(select, entree.type);
        select.addEventListener("change", () => {
          entree.type = select.value;
          entree.suggere = false;
          entree.message = "";
          fdRendreFichiers();
        });
        enfants.push(select);
        if (entree.suggere) enfants.push(dosNoeud("span", "fd-suggestion", "Suggéré d'après le nom : vérifiez"));
        const retirer = dosNoeud("button", "btn btn-fantome btn-sm", "Retirer");
        retirer.type = "button";
        retirer.disabled = fdEnvoi;
        retirer.setAttribute("aria-label", "Retirer " + entree.fichier.name);
        retirer.addEventListener("click", () => {
          fdFichiers = fdFichiers.filter((x) => x.cle !== entree.cle);
          fdRendreFichiers();
        });
        enfants.push(retirer);
      }
      ligne.meta.replaceChildren(...enfants);
      if (entree.message) {
        const p = dosNoeud("p", "fd-fichier-erreur", entree.message);
        p.setAttribute("role", "alert");
        ligne.message.replaceChildren(p);
      } else {
        ligne.message.replaceChildren();
      }
    }

    function fdRendreListeFichiers(liste) {
      const vivantes = {};
      fdFichiers.forEach((entree) => {
        const ligne = fdLignes[entree.cle] || fdCreerLigne(entree);
        fdMajLigne(ligne, entree);
        vivantes[entree.cle] = ligne;
      });
      Object.keys(fdLignes).forEach((cle) => { if (!vivantes[cle]) fdLignes[cle].li.remove(); });
      fdLignes = vivantes;
      fdFichiers.forEach((entree, i) => {
        const li = fdLignes[entree.cle].li;
        if (liste.children[i] !== li) liste.insertBefore(li, liste.children[i] || null);
      });
    }

    // ----- Célébration discrète : dossier prêt pour VALIDATION (rien n'est envoyé) -----
    let fdCompletVu = null;
    function fdMajPret(etapes) {
      if (!etapes.length) { fdEl("fd-pret").classList.add("cache"); return false; }
      const complet = etapes.every((e) => e.statut === "termine");
      const bandeau = fdEl("fd-pret");
      bandeau.classList.toggle("cache", !complet);
      const carte = fdEl("fd-carte-analyse");
      if (complet && fdCompletVu === false && !fdReduit()) {
        bandeau.classList.remove("fd-pret-anime");
        void bandeau.offsetWidth;
        bandeau.classList.add("fd-pret-anime");
        carte.classList.remove("fd-halo");
        void carte.offsetWidth;
        carte.classList.add("fd-halo");
      }
      if (!complet) {
        bandeau.classList.remove("fd-pret-anime");
        carte.classList.remove("fd-halo");
      }
      fdCompletVu = complet;
      return complet;
    }
"""
