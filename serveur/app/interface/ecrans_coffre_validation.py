"""Écrans web du coffre d'identifiants portail (Règle 3) et des récapitulatifs à valider (Règle 1).

Ce module fournit des fragments HTML/JS insérés dans la page unique de `routeur_interface.py`
par `assembler_interface`. Règles respectées par tout le code ci-dessous :

- aucune dépendance front nouvelle, aucun CSS nouveau (classes existantes de l'interface) ;
- tout contenu affiché passe par `textContent` / création de nœuds DOM (jamais `innerHTML`
  avec une donnée), donc un contenu piégé du type `<script>` reste du texte inerte ;
- les identifiants du coffre ne sont jamais écrits dans le HTML, ni relus, ni journalisés
  (pas de console, pas de stockage navigateur) ; les champs sont vidés dès la saisie capturée ;
- aucun antislash dans ce code : la page est servie depuis une chaîne Python.
"""

from __future__ import annotations

PORTAILS_COFFRE: tuple[tuple[str, str], ...] = (
    ("etudes_en_france", "Études en France (Campus France)"),
    ("ircc", "IRCC Canada (permis d'études)"),
)

_MARQUEUR_NAV = '<button class="nav-btn" data-vue="vue-procedures">10. Procédures (démarches)</button>'
_MARQUEUR_DOCUMENTS = "    </section>\n\n    <!-- 4. Discussion & Score d'acceptation -->"
_MARQUEUR_CENTRE = '<div id="liste-centre-validation" class="panneau-texte">Chargement des dossiers...</div>'
_MARQUEUR_FIN_MAIN = "  </main>\n\n  <script>"
_MARQUEUR_JS = "    // Connexion automatique dès l'ouverture de l'interface"

HTML_NAV = (
    '\n    <button class="nav-btn" data-vue="vue-recaps-valider">'
    "11. Récapitulatifs à valider</button>"
)

_MODELE_PORTAIL = """
        <div class="panneau-texte" id="coffre-bloc-{P}" style="margin-bottom:12px;">
          <h4 style="margin-top:0;">{L}</h4>
          <p id="coffre-statut-{P}">Sélectionnez un candidat pour voir l'état du coffre.</p>
          <div id="coffre-saisie-{P}">
            <label style="display:block; margin-bottom:10px;">
              <input id="coffre-consent-{P}" type="checkbox" />
              Je confirme avoir recueilli le consentement écrit du candidat pour conserver ses
              identifiants de ce portail dans le coffre du bureau.
            </label>
            <div class="grille-form">
              <label>Identifiant du portail
                <input id="coffre-id-{P}" type="text" autocomplete="off" autocapitalize="off" spellcheck="false" />
              </label>
              <label>Mot de passe du portail
                <input id="coffre-mdp-{P}" type="password" autocomplete="off" autocapitalize="off" spellcheck="false" />
              </label>
            </div>
            <p style="margin-top:10px;">
              <button id="coffre-enregistrer-{P}" class="btn btn-succes" type="button">Enregistrer dans le coffre</button>
            </p>
          </div>
          <p>
            <button id="coffre-supprimer-{P}" class="btn btn-danger cache" type="button">Supprimer du coffre (révoquer le consentement)</button>
          </p>
        </div>"""


def _html_portails() -> str:
    return "".join(
        _MODELE_PORTAIL.replace("{P}", code).replace("{L}", libelle)
        for code, libelle in PORTAILS_COFFRE
    )


def html_bloc_coffre() -> str:
    return (
        '      <div class="carte" id="carte-coffre-identifiants">\n'
        "        <h3>4. Identifiants portail (Études en France, IRCC) — coffre chiffré</h3>\n"
        '        <div class="banniere-regle">\n'
        "          Les identifiants sont chiffrés avec la clé du bureau et isolés par bureau. Ils ne sont\n"
        "          jamais réaffichés ni renvoyés après la saisie : seul leur statut est visible. Ils ne sont\n"
        "          lisibles que par l'agent, au moment de la connexion au portail. Le consentement écrit du\n"
        "          candidat est obligatoire et tracé ; la suppression est possible à tout moment.\n"
        "        </div>\n"
        '        <p id="coffre-lecture-seule" class="notif notif-err cache" style="margin:0 0 10px 0;">\n'
        "          Compte en lecture seule : l'enregistrement et la suppression des identifiants sont réservés\n"
        "          aux administrateurs et aux employés.\n"
        "        </p>"
        f"{_html_portails()}\n"
        "      </div>\n"
    )


HTML_LIEN_CENTRE = """
      <p>
        <button id="btn-aller-recaps" class="btn btn-contour" type="button" onclick="allerVersVue('vue-recaps-valider')">
          Récapitulatifs à valider avant envoi officiel (<span id="compteur-recaps-centre">…</span>)
        </button>
      </p>"""

HTML_VUE_RECAPS = """
    <!-- 11. Récapitulatifs à valider (Règle 1) -->
    <section id="vue-recaps-valider" class="vue-ecran cache">
      <h2>Récapitulatifs à valider avant envoi officiel (Règle 1)</h2>
      <div class="banniere-regle">
        L'agent enverra exactement ce contenu ; toute modification annule la validation. Seul un
        administrateur ou un employé peut valider ou refuser. Un récapitulatif dont des champs
        sont manquants ne peut pas être validé : l'agent n'invente jamais de valeur (Règle 4).
      </div>
      <p><button id="btn-actualiser-recaps" class="btn" type="button">Actualiser les récapitulatifs en attente</button></p>
      <div id="liste-recaps" class="panneau-texte">Chargement des récapitulatifs...</div>
    </section>
"""

JS_COFFRE_VALIDATION = """
    // =======================================================================
    // Coffre d'identifiants portail (Règle 3) et récapitulatifs à valider (Règle 1)
    // Aucune donnée secrète n'est écrite dans le HTML, la console ou le stockage navigateur.
    // Tout contenu affiché passe par textContent ou des nœuds DOM créés un à un.
    // =======================================================================
    const PORTAILS_COFFRE = [
      { code: "etudes_en_france", libelle: "Études en France" },
      { code: "ircc", libelle: "IRCC Canada" },
    ];
    const LIBELLES_PORTAIL_RECAP = { etudes_en_france: "Études en France", ircc: "IRCC Canada" };

    function utilisateurHumainEcriture() {
      return roleActif === "administrateur" || roleActif === "employe";
    }

    function messageErreurSure(statutHttp, detail, parDefaut) {
      // Un 422 peut reprendre la saisie dans son détail : on ne l'affiche jamais.
      if (statutHttp === 403) return "Droits insuffisants pour cette action.";
      if (statutHttp === 422) return "Saisie invalide : vérifiez les champs et le consentement.";
      return typeof detail === "string" && detail ? detail : parDefaut;
    }

    async function lireDetailErreur(rep) {
      try {
        const corps = await rep.json();
        return corps && corps.detail;
      } catch (e) {
        return null;
      }
    }

    function dateFrLisible(iso) {
      if (!iso) return "";
      const d = new Date(iso);
      return isNaN(d.getTime()) ? "" : d.toLocaleString("fr-FR");
    }

    function afficherStatutCoffre(code, statutCoffre) {
      const zone = document.getElementById("coffre-statut-" + code);
      const boutonSupprimer = document.getElementById("coffre-supprimer-" + code);
      const humain = utilisateurHumainEcriture();
      if (statutCoffre && statutCoffre.existe) {
        const quand = dateFrLisible(statutCoffre.mis_a_jour_le || statutCoffre.cree_le);
        const cons = dateFrLisible(statutCoffre.consentement_recueilli_le);
        zone.textContent = "Identifiants enregistrés" + (quand ? " le " + quand : "") +
          (cons ? " (consentement écrit recueilli le " + cons + ")" : "") +
          ". Les valeurs ne sont jamais affichées.";
        boutonSupprimer.classList.toggle("cache", !humain);
      } else {
        zone.textContent = "Aucun identifiant enregistré pour ce portail.";
        boutonSupprimer.classList.add("cache");
      }
    }

    function viderChampsCoffre(code) {
      document.getElementById("coffre-id-" + code).value = "";
      document.getElementById("coffre-mdp-" + code).value = "";
      document.getElementById("coffre-consent-" + code).checked = false;
    }

    function adapterBlocCoffreAuRole() {
      const humain = utilisateurHumainEcriture();
      document.getElementById("coffre-lecture-seule").classList.toggle("cache", humain);
      PORTAILS_COFFRE.forEach((p) => {
        const saisie = document.getElementById("coffre-saisie-" + p.code);
        saisie.classList.toggle("cache", !humain || !candidatActifId);
        ["coffre-id-", "coffre-mdp-", "coffre-consent-", "coffre-enregistrer-"].forEach((pref) => {
          document.getElementById(pref + p.code).disabled = !humain;
        });
      });
    }

    async function chargerCoffreCandidat() {
      adapterBlocCoffreAuRole();
      for (const p of PORTAILS_COFFRE) {
        viderChampsCoffre(p.code);
        if (!candidatActifId) {
          document.getElementById("coffre-statut-" + p.code).textContent =
            "Sélectionnez un candidat pour voir l'état du coffre.";
          document.getElementById("coffre-supprimer-" + p.code).classList.add("cache");
          continue;
        }
        const rep = await appelApi("/api/v1/candidats/" + encodeURIComponent(candidatActifId) +
          "/coffre/" + p.code);
        if (rep.ok) {
          afficherStatutCoffre(p.code, await rep.json());
        } else {
          document.getElementById("coffre-statut-" + p.code).textContent =
            "État du coffre indisponible.";
        }
      }
    }

    async function enregistrerCoffre(code) {
      if (!candidatActifId || !utilisateurHumainEcriture()) return;
      const champId = document.getElementById("coffre-id-" + code);
      const champMdp = document.getElementById("coffre-mdp-" + code);
      const caseConsent = document.getElementById("coffre-consent-" + code);
      if (!caseConsent.checked) {
        notifier("Le consentement écrit du candidat est obligatoire.", false);
        return;
      }
      if (!champId.value || !champMdp.value) {
        notifier("Renseignez l'identifiant et le mot de passe du portail.", false);
        return;
      }
      const corps = JSON.stringify({
        identifiant: champId.value,
        mot_de_passe: champMdp.value,
        consentement: true,
      });
      viderChampsCoffre(code); // vidés dès la saisie capturée, succès ou échec
      let rep;
      try {
        rep = await appelApi("/api/v1/candidats/" + encodeURIComponent(candidatActifId) +
          "/coffre/" + code, { method: "PUT", body: corps });
      } catch (e) {
        notifier("Échec de l'enregistrement dans le coffre (réseau).", false);
        return;
      }
      if (rep.ok) {
        notifier("Identifiants enregistrés dans le coffre chiffré.", true);
        afficherStatutCoffre(code, await rep.json());
      } else {
        notifier(messageErreurSure(rep.status, await lireDetailErreur(rep),
          "Échec de l'enregistrement dans le coffre."), false);
      }
    }

    async function supprimerCoffre(code) {
      if (!candidatActifId || !utilisateurHumainEcriture()) return;
      if (!window.confirm("Supprimer définitivement les identifiants de ce portail du coffre ? " +
        "Le consentement sera révoqué.")) return;
      const rep = await appelApi("/api/v1/candidats/" + encodeURIComponent(candidatActifId) +
        "/coffre/" + code, { method: "DELETE" });
      if (rep.ok) {
        notifier("Identifiants supprimés du coffre.", true);
        afficherStatutCoffre(code, { existe: false });
      } else {
        notifier(messageErreurSure(rep.status, await lireDetailErreur(rep),
          "Échec de la suppression."), false);
      }
    }

    PORTAILS_COFFRE.forEach((p) => {
      document.getElementById("coffre-enregistrer-" + p.code)
        .addEventListener("click", () => enregistrerCoffre(p.code));
      document.getElementById("coffre-supprimer-" + p.code)
        .addEventListener("click", () => supprimerCoffre(p.code));
    });

    // ----- Récapitulatifs à valider -----

    function libelleChampRecap(cle) {
      return (typeof LIBELLES_CHAMPS_FR !== "undefined" && LIBELLES_CHAMPS_FR[cle]) ||
        String(cle).replace(/_/g, " ");
    }

    function rendreValeurRecap(valeur, parent, profondeur) {
      if (valeur === null || valeur === undefined || valeur === "") {
        parent.appendChild(document.createTextNode("— (non renseigné)"));
        return;
      }
      if (profondeur > 6) {
        parent.appendChild(document.createTextNode("…"));
        return;
      }
      if (Array.isArray(valeur) || typeof valeur === "object") {
        const ul = document.createElement("ul");
        ul.style.margin = "2px 0";
        const entrees = Array.isArray(valeur) ? valeur.map((v) => [null, v]) : Object.entries(valeur);
        entrees.forEach(([cle, v]) => {
          const li = document.createElement("li");
          if (cle !== null) {
            const fort = document.createElement("strong");
            fort.textContent = libelleChampRecap(cle) + " : ";
            li.appendChild(fort);
          }
          rendreValeurRecap(v, li, profondeur + 1);
          ul.appendChild(li);
        });
        parent.appendChild(ul);
        return;
      }
      parent.appendChild(document.createTextNode(String(valeur)));
    }

    function carteRecapitulatif(v) {
      const manquants = Array.isArray(v.champs_manquants) ? v.champs_manquants : [];
      const carte = document.createElement("div");
      carte.className = "carte";
      carte.setAttribute("data-validation-id", String(v.id));

      const titre = document.createElement("h3");
      titre.style.marginTop = "0";
      titre.textContent = (LIBELLES_PORTAIL_RECAP[v.portail] || String(v.portail)) +
        " — " + String(v.type_demarche) + " — " + libelleCandidatParId(v.candidat_id);
      carte.appendChild(titre);

      const meta = document.createElement("p");
      meta.style.fontSize = "0.86rem";
      meta.textContent = "Proposé le " + dateFrLisible(v.cree_le) + " — empreinte " +
        String(v.empreinte || "").slice(0, 12) + "…";
      carte.appendChild(meta);

      if (manquants.length > 0) {
        const alerte = document.createElement("div");
        alerte.className = "notif notif-err recap-manquants";
        alerte.style.margin = "0 0 10px 0";
        alerte.textContent = "Non validable (Règle 4) : champs manquants — " +
          manquants.map((c) => libelleChampRecap(c)).join(", ") +
          ". Complétez le dossier puis faites proposer un nouveau récapitulatif.";
        carte.appendChild(alerte);
      }

      const contenu = document.createElement("div");
      contenu.className = "panneau-texte";
      const aAfficher = Object.assign({}, v.contenu || {});
      delete aAfficher.champs_manquants;
      rendreValeurRecap(aAfficher, contenu, 0);
      carte.appendChild(contenu);

      const avert = document.createElement("p");
      avert.style.fontSize = "0.86rem";
      avert.textContent = "L'agent enverra exactement ce contenu ; toute modification annule la validation.";
      carte.appendChild(avert);

      const actions = document.createElement("p");
      const btnValider = document.createElement("button");
      btnValider.type = "button";
      btnValider.className = "btn btn-succes btn-valider-recap";
      btnValider.textContent = "Valider ce récapitulatif";
      btnValider.disabled = manquants.length > 0;
      btnValider.addEventListener("click", () => decisionRecapitulatif(v.id, "valider"));
      const btnRefuser = document.createElement("button");
      btnRefuser.type = "button";
      btnRefuser.className = "btn btn-danger btn-refuser-recap";
      btnRefuser.textContent = "Refuser";
      btnRefuser.addEventListener("click", () => decisionRecapitulatif(v.id, "refuser"));
      actions.appendChild(btnValider);
      actions.appendChild(document.createTextNode(" "));
      actions.appendChild(btnRefuser);
      carte.appendChild(actions);
      return carte;
    }

    async function chargerRecapitulatifsEnAttente() {
      const r = await appelApi("/api/v1/validations-recapitulatif?statut=en_attente");
      return r.ok ? { ok: true, liste: await r.json() } : { ok: false, statut: r.status };
    }

    async function rafraichirRecapitulatifs() {
      const zone = document.getElementById("liste-recaps");
      zone.textContent = "";
      if (!utilisateurHumainEcriture()) {
        zone.textContent = "Accès réservé aux administrateurs et aux employés du bureau.";
        return;
      }
      if (Object.keys(dictionnaireCandidats).length === 0) await chargerCandidats();
      const res = await chargerRecapitulatifsEnAttente();
      if (!res.ok) {
        zone.textContent = "Impossible de charger les récapitulatifs (session expirée ou droits insuffisants).";
        return;
      }
      if (res.liste.length === 0) {
        zone.textContent = "Aucun récapitulatif en attente de validation.";
        return;
      }
      res.liste.forEach((v) => zone.appendChild(carteRecapitulatif(v)));
    }

    async function decisionRecapitulatif(id, action) {
      if (!utilisateurHumainEcriture()) return;
      const rep = await appelApi("/api/v1/validations-recapitulatif/" + encodeURIComponent(id) +
        "/" + action, { method: "POST" });
      if (rep.ok) {
        notifier(action === "valider"
          ? "Récapitulatif validé : l'agent pourra envoyer exactement ce contenu."
          : "Récapitulatif refusé.", true);
      } else {
        notifier(messageErreurSure(rep.status, await lireDetailErreur(rep),
          "Action impossible sur ce récapitulatif."), false);
      }
      await rafraichirRecapitulatifs();
    }

    async function actualiserCompteurRecapsCentre() {
      const el = document.getElementById("compteur-recaps-centre");
      if (!utilisateurHumainEcriture()) {
        el.textContent = "réservé aux humains";
        return;
      }
      const res = await chargerRecapitulatifsEnAttente();
      el.textContent = res.ok ? String(res.liste.length) + " en attente" : "indisponible";
    }

    document.getElementById("btn-actualiser-recaps").addEventListener("click", rafraichirRecapitulatifs);

    // Branchement sur la navigation et la sélection de candidat existantes (sans toucher leur code).
    const allerVersVueInitial = allerVersVue;
    allerVersVue = function (cible) {
      allerVersVueInitial(cible);
      if (cible === "vue-documents") chargerCoffreCandidat();
      else if (cible === "vue-recaps-valider") rafraichirRecapitulatifs();
      else if (cible === "vue-validation-humaine") actualiserCompteurRecapsCentre();
    };
    const selectionnerCandidatInitial = selectionnerCandidat;
    selectionnerCandidat = function (c, silencieux) {
      selectionnerCandidatInitial(c, silencieux);
      if (!document.getElementById("vue-documents").classList.contains("cache")) chargerCoffreCandidat();
    };
    adapterBlocCoffreAuRole();

"""


def _inserer(html: str, marqueur: str, ajout: str, *, avant: bool) -> str:
    if html.count(marqueur) != 1:
        raise RuntimeError("Marqueur d'insertion introuvable ou ambigu : " + marqueur[:60])
    return html.replace(marqueur, ajout + marqueur if avant else marqueur + ajout)


def assembler_interface(html_base: str) -> str:
    """Insère les écrans coffre/validation dans la page de base."""
    html = _inserer(html_base, _MARQUEUR_NAV, HTML_NAV, avant=False)
    html = _inserer(html, _MARQUEUR_DOCUMENTS, html_bloc_coffre(), avant=True)
    html = _inserer(html, _MARQUEUR_CENTRE, HTML_LIEN_CENTRE, avant=False)
    html = _inserer(html, _MARQUEUR_FIN_MAIN, HTML_VUE_RECAPS + "\n", avant=True)
    return _inserer(html, _MARQUEUR_JS, JS_COFFRE_VALIDATION, avant=True)
