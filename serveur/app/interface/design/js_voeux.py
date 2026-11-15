"""JavaScript de l'interface : Vœux de formation et lettres de motivation.

Chaîne Python non brute : aucun antislash (leur nombre dans la page est verrouillé par les tests).
Chaque vœu est une carte construite par nœuds DOM et textContent (rang, formation, établissement,
statut, lettre, actions). Utilise les aides `dem*` définies dans `js_demarches`.
"""

from __future__ import annotations

JS_VOEUX = """
    // ===== Vœux de formation et lettres de motivation =====
    const NL = String.fromCharCode(10);
    const MAX_MOTIVATION = 4000;
    const MAX_VOEUX_PANIER = 7;
    const LIBELLES_STATUT_VOEU = { brouillon: "Brouillon à relire", valide: "Validé", ajoute_au_panier: "Dans le panier" };
    const CLASSES_STATUT_VOEU = { brouillon: "badge-completer", valide: "badge-valide", ajoute_au_panier: "badge-envoye" };
    const LIBELLES_VOIE_VOEU = { hors_dap: "Hors DAP", dap_blanche: "DAP Blanche", dap_jaune: "DAP Jaune" };
    let alertesVoeux = {}; // points à vérifier renvoyés à la rédaction, par vœu

    function lignesDepuis(id) {
      return document.getElementById(id).value.split(NL).map((s) => s.trim()).filter((s) => s.length > 0);
    }

    function faitsDuParcours() {
      const projet = document.getElementById("faits-projet").value.trim();
      return {
        parcours: lignesDepuis("faits-parcours"),
        points_forts: lignesDepuis("faits-points"),
        langues: lignesDepuis("faits-langues"),
        projet: projet || null,
      };
    }

    function baseVoeux() {
      return "/api/v1/candidats/" + candidatActifId + "/voeux";
    }

    function majCompteurVoeux(nombre) {
      const badge = document.getElementById("voeux-compteur");
      if (nombre === null) {
        badge.className = "badge badge-nu";
        badge.textContent = "— / " + MAX_VOEUX_PANIER;
        return;
      }
      badge.className = "badge " + (nombre >= MAX_VOEUX_PANIER ? "badge-warn" : "badge-nu");
      badge.textContent = nombre + " / " + MAX_VOEUX_PANIER + " vœux";
    }

    function squeletteVoeux() {
      const frag = document.createDocumentFragment();
      frag.appendChild(demNoeud("span", "sr-only", "Chargement des vœux"));
      for (let i = 0; i < 2; i += 1) {
        const carte = demNoeud("div", "voeu-squelette");
        carte.setAttribute("aria-hidden", "true");
        carte.appendChild(demNoeud("span", "squelette squelette-titre"));
        carte.appendChild(demNoeud("span", "squelette squelette-texte court"));
        const zone = demNoeud("span", "squelette squelette-texte");
        zone.style.height = "6em";
        carte.appendChild(zone);
        frag.appendChild(carte);
      }
      return frag;
    }

    async function chargerVoeux() {
      const zone = document.getElementById("liste-voeux");
      document.getElementById("voeux-candidat-actif").textContent =
        candidatActifObj ? candidatActifObj.nom + " " + candidatActifObj.prenom : "Aucun";
      if (!candidatActifId) {
        majCompteurVoeux(null);
        zone.replaceChildren(demEtatVide("Aucun dossier choisi.", "Choisissez un dossier dans « Étudiants et fiches » pour gérer ses vœux.", "dossier"));
        return;
      }
      zone.setAttribute("aria-busy", "true");
      zone.replaceChildren(squeletteVoeux());
      const rep = await appelApi(baseVoeux());
      zone.setAttribute("aria-busy", "false");
      if (!rep.ok) {
        majCompteurVoeux(null);
        zone.replaceChildren(demEtatVide("Vœux indisponibles.", "Impossible de charger les vœux de ce candidat. Réessayez avec « Actualiser la liste ».", "alerte"));
        return;
      }
      const liste = await rep.json();
      majCompteurVoeux(liste.length);
      annoncer(liste.length + (liste.length > 1 ? " vœux dans le panier." : " vœu dans le panier."));
      document.getElementById("btn-ajouter-voeu").disabled = liste.length >= MAX_VOEUX_PANIER;
      if (liste.length === 0) {
        zone.replaceChildren(demEtatVide("Aucun vœu pour le moment.", "Ajoutez une première formation ci-dessus : sa lettre de motivation se rédige ensuite ici.", "dossier"));
        return;
      }
      zone.replaceChildren(...liste.map((v) => construireCarteVoeu(v)));
    }

    function enteteCarteVoeu(v) {
      const entete = demNoeud("div", "voeu-entete");
      const rang = demNoeud("span", "voeu-rang", String(v.rang));
      rang.setAttribute("aria-label", "Vœu numéro " + v.rang);
      entete.appendChild(rang);
      const texte = demNoeud("div", "voeu-texte");
      texte.appendChild(demNoeud("strong", "voeu-titre", v.intitule));
      const meta = [v.etablissement, v.niveau, LIBELLES_VOIE_VOEU[v.voie]].filter((x) => x);
      texte.appendChild(demNoeud("span", "voeu-meta", meta.join(" · ")));
      if (v.justification) texte.appendChild(demNoeud("span", "voeu-justif", "Motif : " + v.justification));
      entete.appendChild(texte);
      entete.appendChild(demNoeud("span", "badge " + (CLASSES_STATUT_VOEU[v.statut] || ""), LIBELLES_STATUT_VOEU[v.statut] || v.statut));
      return entete;
    }

    function champLettreVoeu(v, enPanier) {
      const id = "voeu-motivation-" + v.id;
      const label = demNoeud("label", "champ", "Lettre de motivation");
      label.htmlFor = id;
      const ta = document.createElement("textarea");
      ta.id = id;
      ta.value = v.motivation || "";
      ta.placeholder = "Rédigez la lettre ici, ou cliquez sur « Rédiger la lettre ».";
      ta.disabled = enPanier;
      const compteur = demNoeud("span", "voeu-compteur");
      const majCompteur = () => {
        const n = ta.value.length;
        compteur.textContent = n + " / " + MAX_MOTIVATION + " caractères";
        compteur.classList.toggle("depasse", n > MAX_MOTIVATION);
      };
      ta.addEventListener("input", majCompteur);
      majCompteur();
      label.appendChild(ta);
      label.appendChild(compteur);
      return { label, ta };
    }

    function construireCarteVoeu(v) {
      const div = demNoeud("article", "voeu");
      const base = baseVoeux() + "/" + v.id;
      const enPanier = v.statut === "ajoute_au_panier";
      div.appendChild(enteteCarteVoeu(v));

      const alertes = alertesVoeux[v.id] || [];
      if (alertes.length > 0) {
        const ul = demNoeud("ul", "voeu-alertes");
        ul.setAttribute("aria-label", "Points à vérifier dans la lettre");
        alertes.forEach((a) => ul.appendChild(demNoeud("li", "", a)));
        div.appendChild(ul);
      }

      const { label, ta } = champLettreVoeu(v, enPanier);
      div.appendChild(label);

      if (enPanier) {
        div.appendChild(demNoeud("p", "note", "Ce vœu est dans le panier du portail : sa lettre n'est plus modifiable ici."));
        return div;
      }

      const actions = demNoeud("div", "voeu-actions");
      const ajouterBouton = (texte, classe, action) => {
        const b = demNoeud("button", "btn " + classe, texte);
        b.type = "button";
        b.addEventListener("click", action);
        actions.appendChild(b);
        return b;
      };

      ajouterBouton("Rédiger la lettre", "btn-secondaire", async () => {
        const rep = await appelApi(base + "/lettre/generer", { method: "POST", body: JSON.stringify(faitsDuParcours()) });
        const data = await rep.json().catch(() => null);
        if (!rep.ok) {
          notifier(messageErreurApi(data, "Rédaction impossible."), false);
          return;
        }
        alertesVoeux[v.id] = data.elements_a_verifier || [];
        notifier(
          data.origine === "ia"
            ? "Lettre rédigée par l'IA : relisez-la avant de valider."
            : "Lettre type générée (sans IA) : complétez les repères « À COMPLÉTER ».",
          true
        );
        await chargerVoeux();
      });
      ajouterBouton("Enregistrer mon texte", "btn-contour", async () => {
        const rep = await appelApi(base, { method: "PATCH", body: JSON.stringify({ motivation: ta.value }) });
        const data = await rep.json().catch(() => null);
        if (!rep.ok) {
          notifier(messageErreurApi(data, "Enregistrement refusé."), false);
          return;
        }
        notifier("Texte enregistré en brouillon.", true);
        await chargerVoeux();
      });
      if (v.statut === "brouillon") {
        ajouterBouton("Valider ce vœu", "btn-primaire", async () => {
          const rep = await appelApi(base + "/valider", { method: "POST" });
          const data = await rep.json().catch(() => null);
          if (!rep.ok) {
            notifier(messageErreurApi(data, "Validation refusée."), false);
            return;
          }
          delete alertesVoeux[v.id];
          notifier("Vœu validé : il peut être ajouté au panier.", true);
          await chargerVoeux();
        });
      }
      ajouterBouton("Retirer", "btn-danger btn-sm btn-retirer", async () => {
        if (!window.confirm("Retirer ce vœu de la liste ?")) return;
        const rep = await appelApi(base, { method: "DELETE" });
        if (!rep.ok) {
          const data = await rep.json().catch(() => null);
          notifier(messageErreurApi(data, "Suppression impossible."), false);
          return;
        }
        notifier("Vœu retiré.", true);
        await chargerVoeux();
      });
      div.appendChild(actions);
      return div;
    }

    document.getElementById("btn-ajouter-voeu").addEventListener("click", async () => {
      if (!candidatActifId) {
        notifier("Choisissez d'abord un dossier dans « Étudiants et fiches ».", false);
        return;
      }
      const justification = document.getElementById("voeu-justification").value.trim();
      const corps = {
        intitule: document.getElementById("voeu-intitule").value.trim(),
        etablissement: document.getElementById("voeu-etablissement").value.trim(),
        niveau: document.getElementById("voeu-niveau").value,
        voie: document.getElementById("voeu-voie").value,
      };
      if (justification) corps.justification = justification;
      const rep = await appelApi(baseVoeux(), { method: "POST", body: JSON.stringify(corps) });
      const data = await rep.json().catch(() => null);
      if (!rep.ok) {
        notifier(messageErreurApi(data, "Ajout du vœu impossible."), false);
        return;
      }
      ["voeu-intitule", "voeu-etablissement", "voeu-justification"].forEach((id) => {
        document.getElementById(id).value = "";
      });
      notifier("Vœu ajouté. Rédigez maintenant sa lettre.", true);
      await chargerVoeux();
    });
    document.getElementById("btn-actualiser-voeux").addEventListener("click", chargerVoeux);

"""
