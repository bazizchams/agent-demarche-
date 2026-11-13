"""Écrans web du coffre d'identifiants portail (Règle 3) et des récapitulatifs à valider (Règle 1).

Ce module fournit des fragments HTML/JS insérés dans la page unique de `routeur_interface.py`
par `assembler_interface`. Règles respectées par tout le code ci-dessous :

- aucune dépendance front nouvelle : classes du système de design (`design/styles.py`) et un
  petit bloc <style> local (`STYLE_COFFRE_VALIDATION`) qui n'utilise que les tokens `var(--…)`,
  préfixé par l'identifiant de l'écran ;
- tout contenu affiché passe par `textContent` / création de nœuds DOM (jamais `innerHTML`
  avec une donnée), donc un contenu piégé du type `<script>` reste du texte inerte ;
- les identifiants du coffre ne sont jamais écrits dans le HTML, ni relus, ni journalisés
  (pas de console, pas de stockage navigateur) ; les champs sont vidés dès la saisie capturée ;
- aucun antislash dans ce code : la page est servie depuis une chaîne Python.
"""

from __future__ import annotations

from app.interface.design.shell import bouton_nav, rendre_icones

PORTAILS_COFFRE: tuple[tuple[str, str], ...] = (
    ("etudes_en_france", "Études en France (Campus France)"),
    ("ircc", "IRCC Canada (permis d'études)"),
)

_MARQUEUR_NAV = "<!-- nav:validation -->"
_MARQUEUR_DOCUMENTS = "<!-- zone:coffre -->"
_MARQUEUR_CENTRE = "<!-- zone:lien-recaps -->"
_MARQUEUR_FIN_MAIN = "  </main>\n\n  <script>"
_MARQUEUR_JS = "    // Connexion automatique dès l'ouverture de l'interface"

HTML_NAV = "\n      " + bouton_nav("vue-recaps-valider", "Récapitulatifs à valider", "recaps")

# Composants manquants au système commun : bloc portail du coffre, « bon de commande » du
# récapitulatif (sections champ/valeur), encart des champs manquants, squelette de carte.
STYLE_COFFRE_VALIDATION = """
    <style>
      #carte-coffre-identifiants .coffre-grille { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 340px), 1fr)); gap: var(--e4); }
      #carte-coffre-identifiants .coffre-portail { display: flex; flex-direction: column; gap: var(--e3); min-width: 0; padding: var(--e4); background: var(--surface-2); border: 1px solid var(--bord); border-radius: var(--r-l); }
      #carte-coffre-identifiants .coffre-portail-entete { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--e2); }
      #carte-coffre-identifiants .coffre-portail-entete h4 { margin: 0; }
      #carte-coffre-identifiants .coffre-statut { margin: 0; font-size: var(--t-sm); color: var(--texte-doux); }
      #carte-coffre-identifiants .coffre-saisie { display: flex; flex-direction: column; gap: var(--e3); }
      #carte-coffre-identifiants .coffre-consentement { padding: var(--e3); background: var(--surface); border: 1px solid var(--bord); border-radius: var(--r-m); font-size: var(--t-sm); }
      #carte-coffre-identifiants .coffre-actions { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--e2); }
      #carte-coffre-identifiants .coffre-actions .btn, #carte-coffre-identifiants .coffre-revoquer .btn { margin: 0; }
      #carte-coffre-identifiants .coffre-revoquer { display: flex; justify-content: flex-end; }
      #carte-coffre-identifiants .coffre-revoquer:has(.btn.cache) { display: none; }
      #carte-coffre-identifiants #coffre-lecture-seule { margin: 0 0 var(--e4); }
      .cv-lien-centre { margin: 0 0 var(--e5); }
      #vue-recaps-valider .cv-resume { margin: 0 0 var(--e3); }
      #vue-recaps-valider .cv-squelette-carte { display: flex; flex-direction: column; gap: var(--e4); padding: var(--e5); margin-bottom: var(--e5); background: var(--surface); border: 1px solid var(--bord); border-radius: var(--r-l); }
      #vue-recaps-valider .cv-recap.cv-recap-bloque { border-color: var(--critique); }
      #vue-recaps-valider .cv-recap-entete { align-items: flex-start; flex-wrap: wrap; }
      #vue-recaps-valider .cv-recap-titres { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
      #vue-recaps-valider .cv-recap-titres h3 { margin: 0; overflow-wrap: anywhere; }
      #vue-recaps-valider .cv-recap-demarche { margin: 0; font-size: var(--t-sm); color: var(--texte-doux); overflow-wrap: anywhere; }
      #vue-recaps-valider .cv-recap-meta { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e1) var(--e4); margin: calc(var(--e2) * -1) 0 var(--e4); font-size: var(--t-sm); color: var(--texte-faible); }
      #vue-recaps-valider .cv-empreinte-code { font-family: var(--police-code); font-size: var(--t-xs); color: var(--texte-faible); background: var(--surface-2); letter-spacing: 0.02em; }
      #vue-recaps-valider .cv-manquants { display: flex; flex-direction: column; gap: var(--e2); margin: 0 0 var(--e4); padding: var(--e3) var(--e4); background: var(--critique-doux); color: var(--critique-texte); border-left: 4px solid var(--critique); border-radius: var(--r-s) var(--r-m) var(--r-m) var(--r-s); font-size: var(--t-sm); }
      #vue-recaps-valider .cv-manquants p { margin: 0; }
      #vue-recaps-valider .cv-manquants-liste { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: var(--e2); }
      #vue-recaps-valider .cv-manquants-liste .badge { white-space: normal; overflow-wrap: anywhere; background: var(--surface); }
      #vue-recaps-valider .cv-bon { display: flex; flex-direction: column; background: var(--surface); border: 1px solid var(--bord-fort); border-radius: var(--r-m); overflow: hidden; }
      #vue-recaps-valider .cv-bon-section { padding: var(--e3) var(--e4); border-top: 1px dashed var(--bord-fort); min-width: 0; }
      #vue-recaps-valider .cv-bon-section:first-child { border-top: 0; }
      #vue-recaps-valider .cv-bon-titre { margin: 0 0 var(--e2); font-family: var(--police-texte); font-size: var(--t-xs); font-weight: 600; letter-spacing: 0.07em; text-transform: uppercase; color: var(--texte-faible); }
      #vue-recaps-valider .cv-def { margin: 0; display: flex; flex-direction: column; }
      #vue-recaps-valider .cv-def-ligne { display: grid; grid-template-columns: minmax(120px, 34%) minmax(0, 1fr); gap: var(--e1) var(--e4); padding: 6px 0; border-top: 1px solid var(--bord); }
      #vue-recaps-valider .cv-def-ligne:first-child { border-top: 0; }
      #vue-recaps-valider .cv-def dt { font-size: var(--t-sm); color: var(--texte-doux); overflow-wrap: anywhere; }
      #vue-recaps-valider .cv-def dd { margin: 0; font-weight: 500; color: var(--texte); overflow-wrap: anywhere; min-width: 0; font-variant-numeric: tabular-nums; }
      #vue-recaps-valider .cv-def dd .cv-def { padding-left: var(--e3); border-left: 2px solid var(--bord); font-weight: 400; }
      #vue-recaps-valider .cv-def-manquante { background: var(--critique-doux); margin: 0 calc(var(--e2) * -1); padding-left: var(--e2); padding-right: var(--e2); border-radius: var(--r-s); }
      #vue-recaps-valider .cv-def-manquante dt { color: var(--critique-texte); font-weight: 600; }
      #vue-recaps-valider .cv-liste { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 2px; }
      #vue-recaps-valider .cv-non-renseigne { color: var(--alerte-texte); font-style: italic; font-weight: 400; }
      #vue-recaps-valider .cv-recap-pied { align-items: center; }
      #vue-recaps-valider .cv-recap-avert { margin: 0; flex: 1 1 260px; font-size: var(--t-sm); color: var(--texte-doux); }
      #vue-recaps-valider .cv-recap-actions { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e3); }
      #vue-recaps-valider .cv-recap-actions .btn { margin: 0; }
      #vue-recaps-valider .cv-separateur { width: 1px; align-self: stretch; background: var(--bord); }
      @media (max-width: 520px) {
        #vue-recaps-valider .cv-def-ligne { grid-template-columns: minmax(0, 1fr); gap: 0; }
        #vue-recaps-valider .cv-recap-actions { width: 100%; flex-direction: column-reverse; align-items: stretch; }
        #vue-recaps-valider .cv-separateur { display: none; }
      }
    </style>"""

_MODELE_PORTAIL = """
          <div class="coffre-portail" id="coffre-bloc-{P}">
            <div class="coffre-portail-entete">
              <h4>{L}</h4>
              <span id="coffre-badge-{P}" class="badge badge-brouillon">Aucun dossier</span>
            </div>
            <p id="coffre-statut-{P}" class="coffre-statut">Choisissez un dossier pour voir l'état du coffre.</p>
            <div id="coffre-saisie-{P}" class="coffre-saisie">
              <label class="case coffre-consentement">
                <input id="coffre-consent-{P}" type="checkbox" />
                <span>Je confirme avoir recueilli le consentement écrit du candidat pour conserver ses
                identifiants de ce portail dans le coffre du bureau.</span>
              </label>
              <div class="grille-form">
                <label class="champ">Identifiant du portail
                  <input id="coffre-id-{P}" type="text" autocomplete="off" autocapitalize="off" spellcheck="false" />
                </label>
                <label class="champ">Mot de passe du portail
                  <input id="coffre-mdp-{P}" type="password" autocomplete="off" autocapitalize="off" spellcheck="false" />
                  <span class="champ-aide">Jamais réaffiché ni renvoyé après l'enregistrement.</span>
                </label>
              </div>
              <div class="coffre-actions">
                <button id="coffre-enregistrer-{P}" class="btn btn-primaire" type="button">[[i:cadenas]]Enregistrer dans le coffre</button>
              </div>
            </div>
            <div class="coffre-revoquer">
              <button id="coffre-supprimer-{P}" class="btn btn-danger btn-sm cache" type="button">Supprimer du coffre (révoquer le consentement)</button>
            </div>
          </div>"""


def _html_portails() -> str:
    return "".join(
        _MODELE_PORTAIL.replace("{P}", code).replace("{L}", libelle)
        for code, libelle in PORTAILS_COFFRE
    )


def html_bloc_coffre() -> str:
    return rendre_icones(
        '      <section class="carte" id="carte-coffre-identifiants">\n'
        '        <div class="carte-entete">\n'
        "          <div><span class=\"surtitre\">Coffre chiffré</span>"
        "<h3>Identifiants portail (Études en France, IRCC)</h3></div>\n"
        '          <span class="badge badge-info badge-nu">[[i:cadenas]]Chiffré par bureau</span>\n'
        "        </div>\n"
        '        <div class="banniere-regle">\n'
        "          Les identifiants sont chiffrés avec la clé du bureau et isolés par bureau. Ils ne sont\n"
        "          jamais réaffichés ni renvoyés après la saisie : seul leur statut est visible. Ils ne sont\n"
        "          lisibles que par l'agent, au moment de la connexion au portail. Le consentement écrit du\n"
        "          candidat est obligatoire et tracé ; la suppression est possible à tout moment.\n"
        "        </div>\n"
        '        <p id="coffre-lecture-seule" class="notif notif-err cache">\n'
        "          Compte en lecture seule : l'enregistrement et la suppression des identifiants sont réservés\n"
        "          aux administrateurs et aux employés.\n"
        "        </p>\n"
        '        <div class="coffre-grille">'
        f"{_html_portails()}\n"
        "        </div>\n"
        "      </section>\n"
    )


HTML_LIEN_CENTRE = rendre_icones("""
      <div class="cv-lien-centre">
        <button id="btn-aller-recaps" class="raccourci" type="button" onclick="allerVersVue('vue-recaps-valider')">
          <span class="raccourci-icone">[[i:recaps]]</span>
          <span><strong>Récapitulatifs à valider avant envoi officiel</strong>
          <small><span id="compteur-recaps-centre"><span class="squelette squelette-valeur" aria-hidden="true"></span></span></small></span>
          [[i:suivant]]
        </button>
      </div>""")

_SQUELETTE_CARTE = (
    '        <div class="cv-squelette-carte" aria-hidden="true">'
    '<span class="squelette squelette-titre"></span>'
    '<span class="squelette-pile"><span class="squelette squelette-texte"></span>'
    '<span class="squelette squelette-texte"></span>'
    '<span class="squelette squelette-texte court"></span></span></div>\n'
)

HTML_VUE_RECAPS = rendre_icones(
    """
    <!-- Récapitulatifs à valider (Règle 1) -->
    <section id="vue-recaps-valider" class="vue-ecran cache">"""
    + STYLE_COFFRE_VALIDATION
    + """
      <header class="page-entete">
        <div>
          <h2>Récapitulatifs à valider</h2>
          <p class="lead">Dernier contrôle avant l'envoi officiel : relisez chaque récapitulatif, puis validez-le ou refusez-le.</p>
        </div>
        <div class="page-actions">
          <button id="btn-actualiser-recaps" class="btn btn-secondaire" type="button">[[i:actualiser]]Actualiser</button>
        </div>
      </header>
      <div class="banniere-regle">
        L'agent enverra exactement ce contenu ; toute modification annule la validation. Seul un
        administrateur ou un employé peut valider ou refuser. Un récapitulatif dont des champs
        sont manquants ne peut pas être validé : l'agent n'invente jamais de valeur (Règle 4).
      </div>
      <p id="recaps-resume" class="note cv-resume cache"></p>
      <div id="liste-recaps" class="pile" aria-busy="true">
        <span class="sr-only">Chargement des récapitulatifs</span>
"""
    + _SQUELETTE_CARTE
    + _SQUELETTE_CARTE
    + """      </div>
    </section>
"""
)

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
    const CV_ESPACE_SVG = "http://www.w3.org/2000/svg";

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

    function cvElement(balise, classe, texte) {
      const el = document.createElement(balise);
      if (classe) el.className = classe;
      if (texte !== undefined) el.textContent = texte;
      return el;
    }

    function cvBadgeCoffre(code, classe, texte) {
      const badge = document.getElementById("coffre-badge-" + code);
      badge.className = "badge " + classe;
      badge.textContent = texte;
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
        cvBadgeCoffre(code, "badge-ok", "Enregistré");
        boutonSupprimer.classList.toggle("cache", !humain);
      } else {
        zone.textContent = "Aucun identifiant enregistré pour ce portail.";
        cvBadgeCoffre(code, "badge-brouillon", "Vide");
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
          cvBadgeCoffre(p.code, "badge-brouillon", "Aucun dossier");
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
          cvBadgeCoffre(p.code, "badge-err", "Indisponible");
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

    function cvValeurVide(parent) {
      parent.appendChild(cvElement("span", "cv-non-renseigne", "— (non renseigné)"));
    }

    function rendreValeurRecap(valeur, parent, profondeur) {
      if (valeur === null || valeur === undefined || valeur === "") {
        cvValeurVide(parent);
        return;
      }
      if (profondeur > 6) {
        parent.appendChild(document.createTextNode("…"));
        return;
      }
      if (Array.isArray(valeur)) {
        if (valeur.length === 0) {
          cvValeurVide(parent);
          return;
        }
        const ul = cvElement("ul", "cv-liste");
        valeur.forEach((v) => {
          const li = document.createElement("li");
          rendreValeurRecap(v, li, profondeur + 1);
          ul.appendChild(li);
        });
        parent.appendChild(ul);
        return;
      }
      if (typeof valeur === "object") {
        parent.appendChild(cvListeDefinitions(Object.entries(valeur), profondeur + 1, []));
        return;
      }
      parent.appendChild(document.createTextNode(String(valeur)));
    }

    // Lignes champ / valeur alignées ; les champs manquants absents du contenu sont ajoutés en rouge.
    function cvListeDefinitions(entrees, profondeur, absents) {
      const dl = cvElement("dl", "cv-def");
      entrees.forEach(([cle, v]) => {
        const ligne = cvElement("div", "cv-def-ligne");
        ligne.appendChild(cvElement("dt", "", libelleChampRecap(cle)));
        const dd = document.createElement("dd");
        rendreValeurRecap(v, dd, profondeur);
        ligne.appendChild(dd);
        dl.appendChild(ligne);
      });
      absents.forEach((cle) => {
        const ligne = cvElement("div", "cv-def-ligne cv-def-manquante");
        ligne.appendChild(cvElement("dt", "", libelleChampRecap(cle)));
        const dd = document.createElement("dd");
        dd.appendChild(cvElement("span", "badge badge-err", "Manquant"));
        ligne.appendChild(dd);
        dl.appendChild(ligne);
      });
      return dl;
    }

    function cvSectionBon(titre, corps) {
      const section = cvElement("section", "cv-bon-section");
      section.appendChild(cvElement("h4", "cv-bon-titre", titre));
      section.appendChild(corps);
      return section;
    }

    // Lecture type « bon de commande » : champs simples d'abord, puis une section par bloc composé.
    function cvBonDeCommande(contenu, manquants) {
      const bon = cvElement("div", "cv-bon");
      const entrees = Object.entries(contenu);
      const simples = entrees.filter(([, v]) => v === null || typeof v !== "object");
      const composes = entrees.filter(([, v]) => v !== null && typeof v === "object");
      const absents = manquants.map((c) => String(c))
        .filter((c) => !Object.prototype.hasOwnProperty.call(contenu, c));
      if (simples.length > 0 || absents.length > 0) {
        bon.appendChild(cvSectionBon("Informations du dossier", cvListeDefinitions(simples, 1, absents)));
      }
      composes.forEach(([cle, v]) => {
        const corps = document.createElement("div");
        rendreValeurRecap(v, corps, 1);
        bon.appendChild(cvSectionBon(libelleChampRecap(cle), corps));
      });
      if (!bon.firstChild) {
        const vide = cvElement("div", "cv-bon-section");
        cvValeurVide(vide);
        bon.appendChild(vide);
      }
      return bon;
    }

    function cvEncartManquants(manquants) {
      const alerte = cvElement("div", "cv-manquants recap-manquants");
      alerte.appendChild(cvElement("strong", "", "Non validable (Règle 4) : champs manquants"));
      const liste = cvElement("ul", "cv-manquants-liste");
      manquants.forEach((c) => {
        const li = cvElement("li", "badge badge-err", libelleChampRecap(c));
        liste.appendChild(li);
      });
      alerte.appendChild(liste);
      alerte.appendChild(cvElement("p", "",
        "Complétez le dossier puis faites proposer un nouveau récapitulatif."));
      return alerte;
    }

    function carteRecapitulatif(v) {
      const manquants = Array.isArray(v.champs_manquants) ? v.champs_manquants : [];
      const bloque = manquants.length > 0;
      const carte = cvElement("article", "carte cv-recap" + (bloque ? " cv-recap-bloque" : ""));
      carte.setAttribute("data-validation-id", String(v.id));

      const entete = cvElement("div", "carte-entete cv-recap-entete");
      const titres = cvElement("div", "cv-recap-titres");
      titres.appendChild(cvElement("span", "surtitre",
        LIBELLES_PORTAIL_RECAP[v.portail] || String(v.portail)));
      titres.appendChild(cvElement("h3", "", libelleCandidatParId(v.candidat_id)));
      titres.appendChild(cvElement("p", "cv-recap-demarche", String(v.type_demarche)));
      entete.appendChild(titres);
      entete.appendChild(bloque
        ? cvElement("span", "badge badge-completer", "À compléter")
        : cvElement("span", "badge badge-attente", "En attente de validation"));
      carte.appendChild(entete);

      const meta = cvElement("div", "cv-recap-meta");
      meta.appendChild(cvElement("span", "", "Proposé le " + dateFrLisible(v.cree_le)));
      const empreinte = cvElement("span", "");
      empreinte.appendChild(document.createTextNode("Empreinte "));
      const code = cvElement("code", "cv-empreinte-code", String(v.empreinte || "").slice(0, 12) + "…");
      code.title = String(v.empreinte || "");
      empreinte.appendChild(code);
      meta.appendChild(empreinte);
      carte.appendChild(meta);

      if (bloque) carte.appendChild(cvEncartManquants(manquants));

      const aAfficher = Object.assign({}, v.contenu || {});
      delete aAfficher.champs_manquants;
      carte.appendChild(cvBonDeCommande(aAfficher, manquants));

      const pied = cvElement("div", "carte-pied cv-recap-pied");
      pied.appendChild(cvElement("p", "cv-recap-avert",
        "L'agent enverra exactement ce contenu ; toute modification annule la validation."));
      const actions = cvElement("div", "cv-recap-actions");
      const btnRefuser = cvElement("button", "btn btn-danger btn-refuser-recap", "Refuser");
      btnRefuser.type = "button";
      btnRefuser.addEventListener("click", () => decisionRecapitulatif(v.id, "refuser"));
      const btnValider = cvElement("button", "btn btn-primaire btn-valider-recap", "Valider ce récapitulatif");
      btnValider.type = "button";
      btnValider.disabled = bloque;
      if (bloque) btnValider.title = "Impossible : des champs sont manquants.";
      btnValider.addEventListener("click", () => decisionRecapitulatif(v.id, "valider"));
      actions.appendChild(btnRefuser);
      actions.appendChild(cvElement("span", "cv-separateur"));
      actions.appendChild(btnValider);
      pied.appendChild(actions);
      carte.appendChild(pied);
      return carte;
    }

    async function chargerRecapitulatifsEnAttente() {
      const r = await appelApi("/api/v1/validations-recapitulatif?statut=en_attente");
      return r.ok ? { ok: true, liste: await r.json() } : { ok: false, statut: r.status };
    }

    function cvSvg(nom, attributs) {
      const n = document.createElementNS(CV_ESPACE_SVG, nom);
      Object.keys(attributs).forEach((cle) => n.setAttribute(cle, attributs[cle]));
      return n;
    }

    function cvIllustration(sorte) {
      const svg = cvSvg("svg", { viewBox: "0 0 96 72", class: "etat-vide-illu", "aria-hidden": "true", focusable: "false" });
      svg.appendChild(cvSvg("rect", { x: "16", y: "6", width: "50", height: "58", rx: "6", class: "illu-papier" }));
      svg.appendChild(cvSvg("path", { d: "M26 20 H56", class: "illu-trait" }));
      svg.appendChild(cvSvg("path", { d: "M26 30 H56", class: "illu-trait" }));
      svg.appendChild(cvSvg("path", { d: "M26 40 H44", class: "illu-trait" }));
      svg.appendChild(cvSvg("circle", { cx: "70", cy: "50", r: "15", class: "illu-accent" }));
      if (sorte === "verrou") {
        svg.appendChild(cvSvg("rect", { x: "63", y: "49", width: "14", height: "10", rx: "2", class: "illu-coche" }));
        svg.appendChild(cvSvg("path", { d: "M66 49 V46 A4 4 0 0 1 74 46 V49", class: "illu-coche" }));
      } else if (sorte === "erreur") {
        svg.appendChild(cvSvg("path", { d: "M70 42 V51", class: "illu-coche" }));
        svg.appendChild(cvSvg("path", { d: "M70 57 V57.5", class: "illu-coche" }));
      } else {
        svg.appendChild(cvSvg("path", { d: "M63 50 L68 55 L77 45", class: "illu-coche" }));
      }
      return svg;
    }

    function etatVideRecaps(zone, titre, detail, sorte) {
      const bloc = cvElement("div", "etat-vide");
      bloc.appendChild(cvIllustration(sorte));
      bloc.appendChild(cvElement("strong", "", titre));
      bloc.appendChild(cvElement("span", "", detail));
      zone.appendChild(bloc);
    }

    function cvSqueletteRecaps(zone) {
      zone.textContent = "";
      zone.setAttribute("aria-busy", "true");
      zone.appendChild(cvElement("span", "sr-only", "Chargement des récapitulatifs"));
      for (let i = 0; i < 2; i += 1) {
        const carte = cvElement("div", "cv-squelette-carte");
        carte.setAttribute("aria-hidden", "true");
        carte.appendChild(cvElement("span", "squelette squelette-titre"));
        const pile = cvElement("span", "squelette-pile");
        ["squelette squelette-texte", "squelette squelette-texte", "squelette squelette-texte court"]
          .forEach((c) => pile.appendChild(cvElement("span", c)));
        carte.appendChild(pile);
        zone.appendChild(carte);
      }
    }

    function cvViderZone(zone) {
      zone.textContent = "";
      zone.removeAttribute("aria-busy");
    }

    function cvResumeRecaps(liste) {
      const resume = document.getElementById("recaps-resume");
      if (!liste) {
        resume.classList.add("cache");
        return;
      }
      const aCompleter = liste.filter((v) => Array.isArray(v.champs_manquants) && v.champs_manquants.length > 0).length;
      resume.textContent = liste.length + (liste.length > 1 ? " récapitulatifs en attente" : " récapitulatif en attente") +
        (aCompleter > 0 ? ", dont " + aCompleter + " à compléter avant validation." : ".");
      resume.classList.toggle("cache", liste.length === 0);
    }

    async function rafraichirRecapitulatifs() {
      const zone = document.getElementById("liste-recaps");
      if (!utilisateurHumainEcriture()) {
        cvViderZone(zone);
        cvResumeRecaps(null);
        etatVideRecaps(zone, "Accès réservé.", "Seuls les administrateurs et les employés du bureau peuvent valider un récapitulatif.", "verrou");
        return;
      }
      cvSqueletteRecaps(zone);
      if (Object.keys(dictionnaireCandidats).length === 0) await chargerCandidats();
      const res = await chargerRecapitulatifsEnAttente();
      cvViderZone(zone);
      if (!res.ok) {
        cvResumeRecaps(null);
        etatVideRecaps(zone, "Chargement impossible.", "Votre session a peut-être expiré : reconnectez-vous (menu de gauche), puis actualisez.", "erreur");
        return;
      }
      cvResumeRecaps(res.liste);
      if (res.liste.length === 0) {
        etatVideRecaps(zone, "Aucun récapitulatif en attente.", "Quand l'agent proposera un contenu à envoyer, il apparaîtra ici pour validation.", "vide");
        return;
      }
      res.liste.forEach((v) => zone.appendChild(carteRecapitulatif(v)));
    }

    function cvVerrouillerCarte(id) {
      document.querySelectorAll("#liste-recaps [data-validation-id]").forEach((carte) => {
        if (carte.getAttribute("data-validation-id") !== String(id)) return;
        carte.querySelectorAll("button").forEach((b) => { b.disabled = true; });
      });
    }

    async function decisionRecapitulatif(id, action) {
      if (!utilisateurHumainEcriture()) return;
      cvVerrouillerCarte(id); // évite un double envoi pendant la requête
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
