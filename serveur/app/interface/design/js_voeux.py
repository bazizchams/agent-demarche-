"""JavaScript de l'interface : Vœux de formation et lettres de motivation.

Extrait tel quel de l'ancien `routeur_interface.py` : chaîne Python non brute, les doubles
antislash y sont voulus (échappements Python) et leur nombre est verrouillé par les tests.
"""

from __future__ import annotations

JS_VOEUX = """
    // ===== Vœux de formation et lettres de motivation =====
    const NL = String.fromCharCode(10);
    const MAX_MOTIVATION = 4000;
    const LIBELLES_STATUT_VOEU = { brouillon: "Brouillon à relire", valide: "Validé", ajoute_au_panier: "Dans le panier" };
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

    async function chargerVoeux() {
      const zone = document.getElementById("liste-voeux");
      document.getElementById("voeux-candidat-actif").textContent =
        candidatActifObj ? candidatActifObj.nom + " " + candidatActifObj.prenom : "Aucun";
      if (!candidatActifId) {
        zone.innerHTML = `<div class="panneau-texte">Choisissez un dossier dans « Étudiants et fiches » pour gérer ses vœux.</div>`;
        return;
      }
      const rep = await appelApi(baseVoeux());
      if (!rep.ok) {
        zone.innerHTML = `<div class="panneau-texte">Impossible de charger les vœux de ce candidat.</div>`;
        return;
      }
      const liste = await rep.json();
      document.getElementById("btn-ajouter-voeu").disabled = liste.length >= 7;
      zone.innerHTML = "";
      if (liste.length === 0) {
        zone.innerHTML = `<div class="panneau-texte">Aucun vœu pour le moment. Ajoutez une formation ci-dessus.</div>`;
        return;
      }
      liste.forEach((v) => zone.appendChild(construireCarteVoeu(v)));
    }

    function construireCarteVoeu(v) {
      const div = document.createElement("div");
      div.className = "voeu";
      const base = baseVoeux() + "/" + v.id;
      const enPanier = v.statut === "ajoute_au_panier";

      const entete = document.createElement("div");
      entete.className = "voeu-entete";
      const titre = document.createElement("div");
      const t = document.createElement("strong");
      t.textContent = v.rang + ". " + v.intitule;
      const sous = document.createElement("div");
      sous.style.fontSize = "0.86rem";
      sous.style.color = "var(--texte-secondaire)";
      sous.textContent = v.etablissement + " · " + v.niveau + (v.justification ? " · " + v.justification : "");
      titre.appendChild(t);
      titre.appendChild(sous);
      const badge = document.createElement("span");
      badge.className = "badge " + (v.statut === "brouillon" ? "badge-warn" : "badge-ok");
      badge.textContent = LIBELLES_STATUT_VOEU[v.statut] || v.statut;
      entete.appendChild(titre);
      entete.appendChild(badge);
      div.appendChild(entete);

      const alertes = alertesVoeux[v.id] || [];
      if (alertes.length > 0) {
        const ul = document.createElement("ul");
        ul.className = "voeu-alertes";
        alertes.forEach((a) => {
          const li = document.createElement("li");
          li.textContent = a;
          ul.appendChild(li);
        });
        div.appendChild(ul);
      }

      const ta = document.createElement("textarea");
      ta.value = v.motivation || "";
      ta.placeholder = "Rédigez la lettre ici, ou cliquez sur « Rédiger la lettre ».";
      ta.disabled = enPanier;
      const compteur = document.createElement("div");
      compteur.className = "voeu-compteur";
      const majCompteur = () => {
        const n = ta.value.length;
        compteur.textContent = n + " / " + MAX_MOTIVATION + " caractères";
        compteur.classList.toggle("depasse", n > MAX_MOTIVATION);
      };
      ta.addEventListener("input", majCompteur);
      majCompteur();
      div.appendChild(ta);
      div.appendChild(compteur);

      const ajouterBouton = (texte, classe, action) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "btn " + classe;
        b.textContent = texte;
        b.addEventListener("click", action);
        div.appendChild(b);
        return b;
      };

      if (!enPanier) {
        ajouterBouton("Rédiger la lettre", "btn-primaire", async () => {
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
        ajouterBouton("Enregistrer mon texte", "btn-secondaire", async () => {
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
          ajouterBouton("Valider ce vœu", "btn-succes", async () => {
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
        ajouterBouton("Retirer", "btn-danger", async () => {
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
      }
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
