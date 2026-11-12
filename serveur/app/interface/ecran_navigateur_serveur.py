"""Écran « Navigateur de l'agent » : vue opérateur du navigateur headless hébergé par le serveur.

Fragments HTML/JS insérés dans la page unique de `routeur_interface.py` par
`assembler_navigateur_serveur` (même principe que `ecrans_coffre_validation.assembler_interface`).
Contrat consommé (réservé aux humains ADMINISTRATEUR / EMPLOYE) :

- GET  /api/v1/navigateur/capture   -> image/jpeg 1280x900 (204/404 sans session) ;
- GET  /api/v1/navigateur/etat      -> JSON {navigateur_ouvert, url_courante, titre_page, ...} ;
- POST /api/v1/navigateur/controle  -> {type: clic|texte|touche|defilement, x, y, texte, touche, delta_y} ;
- POST /api/v1/navigateur/fermer.

Règles respectées par tout le code ci-dessous :

- aucune dépendance front : uniquement les classes du système de design (`design/styles.py`) ;
- tout affichage passe par `textContent` (jamais `innerHTML`, `eval`, `alert`) ;
- le texte tapé par l'opérateur (CAPTCHA, code de sécurité) n'est jamais écrit dans le DOM,
  ni relu, ni stocké (pas de localStorage/sessionStorage), ni journalisé (pas de console) ;
  le champ est vidé dès que la saisie est capturée ;
- la capture est une balise <img> à URL anti-cache ; aucun rafraîchissement si l'onglet est
  caché ou si l'écran n'est pas affiché ;
- aucun antislash dans ce code : la page est servie depuis une chaîne Python.
"""

from __future__ import annotations

from app.interface.design.shell import bouton_nav

ID_VUE = "vue-navigateur-serveur"
LARGEUR_VIEWPORT = 1280
HAUTEUR_VIEWPORT = 900

_MARQUEUR_NAV = "<!-- nav:navigateur -->"
_MARQUEUR_FIN_MAIN = "  </main>\n\n  <script>"
_MARQUEUR_JS = "    // Connexion automatique dès l'ouverture de l'interface"

HTML_NAV = "\n      " + bouton_nav("vue-navigateur-serveur", "Vue en direct", "moniteur")

HTML_VUE_NAVIGATEUR = """
    <!-- Navigateur de l'agent (vue et prise en main de l'opérateur) -->
    <section id="vue-navigateur-serveur" class="vue-ecran cache">
      <header class="page-entete">
        <div>
          <h2>Navigateur de l'agent</h2>
          <p class="lead">Suivez en direct ce que fait l'agent et reprenez la main quand le portail demande un CAPTCHA ou un code de sécurité.</p>
        </div>
      </header>
      <div class="banniere-regle">
        À utiliser pour un CAPTCHA ou un code de sécurité : l'agent ne les contourne jamais.
        Ce que vous tapez n'est ni enregistré ni affiché dans l'historique.
      </div>
      <div id="ns-lecture-seule" class="notif notif-err cache">
        Compte en lecture seule : la vue et la prise en main du navigateur sont réservées aux
        administrateurs et aux employés.
      </div>
      <div id="ns-bandeau" class="panneau-texte" style="margin-bottom:16px;">
        <div><strong>État :</strong> <span id="ns-etat">Chargement...</span></div>
        <div><strong>Adresse :</strong> <span id="ns-url">—</span></div>
        <div><strong>Titre de la page :</strong> <span id="ns-titre">—</span></div>
      </div>
      <div class="pile-actions" style="margin:0 0 16px;">
        <button id="ns-prendre-main" class="btn btn-primaire" type="button">Prendre la main</button>
        <button id="ns-rendre-main" class="btn btn-secondaire cache" type="button">Rendre la main à l'agent</button>
        <button id="ns-fermer" class="btn btn-danger" type="button">Fermer le navigateur</button>
      </div>
      <div id="ns-controles" class="carte carte-action cache">
        <h3>Vous avez la main</h3>
        <p class="aide">
          Cliquez directement sur l'image pour cliquer dans la page ; la molette fait défiler.
        </p>
        <div class="grille-form">
          <label>Texte à saisir dans la page
            <input id="ns-texte" type="password" autocomplete="off" autocapitalize="off" spellcheck="false" />
          </label>
          <label class="case" style="align-self:end;">
            <input id="ns-afficher" type="checkbox" /> <span>Afficher la saisie</span>
          </label>
        </div>
        <div class="pile-actions">
          <button id="ns-envoyer-texte" class="btn btn-primaire" type="button">Envoyer le texte</button>
          <button class="btn btn-contour ns-touche" type="button" data-touche="Enter">Entrée</button>
          <button class="btn btn-contour ns-touche" type="button" data-touche="Tab">Tab</button>
          <button class="btn btn-contour ns-touche" type="button" data-touche="Backspace">Retour</button>
          <button class="btn btn-contour ns-touche" type="button" data-touche="Escape">Échap</button>
        </div>
      </div>
      <p id="ns-message" class="note">Aucune capture pour le moment.</p>
      <div style="max-width:1280px;">
        <img id="ns-capture" class="capture-apercu cache" alt="Capture du navigateur de l'agent"
             draggable="false" style="width:100%; height:auto; display:block; margin:0;" />
      </div>
    </section>
"""

JS_NAVIGATEUR = """
    // =======================================================================
    // Navigateur de l'agent : capture ~1 image/s (onglet visible et écran actif uniquement),
    // prise en main de l'opérateur. Le texte saisi n'est jamais écrit dans le DOM, relu,
    // stocké ou journalisé ; tout affichage passe par textContent.
    // =======================================================================
    const NS_LARGEUR = 1280;
    const NS_HAUTEUR = 900;
    const NS_INTERVALLE_MS = 1000;
    const NS_DELAI_DEFILEMENT_MS = 120;
    const NS_ROUTE = "/api/v1/navigateur/";
    let nsMinuteur = null;
    let nsMinuteurDefilement = null;
    let nsEnCours = false;
    let nsBloque = false;
    let nsCompteur = 0;
    let nsMain = false;
    let nsDeltaEnAttente = 0;

    function nsHumain() {
      return roleActif === "administrateur" || roleActif === "employe";
    }

    function nsEcranVisible() {
      return !document.getElementById("vue-navigateur-serveur").classList.contains("cache");
    }

    function nsPeutInterroger() {
      return nsEcranVisible() && !document.hidden && nsHumain() && !nsBloque;
    }

    // Conversion affichage -> viewport 1280x900 (arrondie, bornée à la fenêtre).
    function nsConvertirClic(rect, clientX, clientY) {
      if (!rect || !(rect.width > 0) || !(rect.height > 0)) return null;
      const x = Math.round((clientX - rect.left) * NS_LARGEUR / rect.width);
      const y = Math.round((clientY - rect.top) * NS_HAUTEUR / rect.height);
      return {
        x: Math.min(NS_LARGEUR - 1, Math.max(0, x)),
        y: Math.min(NS_HAUTEUR - 1, Math.max(0, y)),
      };
    }

    // Adresse sans paramètres ni fragment (les jetons d'URL ne doivent pas s'afficher).
    function nsUrlSansParametres(brute) {
      if (!brute) return "—";
      try {
        const u = new URL(String(brute));
        return u.origin + u.pathname;
      } catch (e) {
        return "—";
      }
    }

    function nsTexte(id, valeur) {
      document.getElementById(id).textContent = valeur;
    }

    function nsMessage(texte) {
      nsTexte("ns-message", texte);
    }

    function nsEffacerCapture() {
      const img = document.getElementById("ns-capture");
      img.onload = null;
      img.onerror = null;
      img.removeAttribute("src");
      img.classList.add("cache");
    }

    function nsAppliquerMain() {
      const humain = nsHumain();
      document.getElementById("ns-lecture-seule").classList.toggle("cache", humain);
      document.getElementById("ns-prendre-main").classList.toggle("cache", nsMain);
      document.getElementById("ns-rendre-main").classList.toggle("cache", !nsMain);
      document.getElementById("ns-controles").classList.toggle("cache", !(nsMain && humain));
      document.getElementById("ns-capture").style.cursor = nsMain ? "crosshair" : "default";
      ["ns-prendre-main", "ns-rendre-main", "ns-fermer", "ns-texte", "ns-afficher",
        "ns-envoyer-texte"].forEach((id) => {
        document.getElementById(id).disabled = !humain;
      });
      document.querySelectorAll("#ns-controles .ns-touche").forEach((b) => { b.disabled = !humain; });
    }

    function nsRendreLaMain() {
      nsMain = false;
      nsDeltaEnAttente = 0;
      document.getElementById("ns-texte").value = "";
      nsAppliquerMain();
    }

    function nsAfficherEtat(etat) {
      const ouvert = !!(etat && etat.navigateur_ouvert);
      nsTexte("ns-etat", ouvert ? "Navigateur ouvert" : "Aucun navigateur ouvert");
      nsTexte("ns-url", ouvert ? nsUrlSansParametres(etat.url_courante) : "—");
      nsTexte("ns-titre", ouvert && etat.titre_page ? String(etat.titre_page) : "—");
      return ouvert;
    }

    function nsChargerCapture() {
      return new Promise((resolve) => {
        const img = document.getElementById("ns-capture");
        img.onload = () => {
          img.classList.remove("cache");
          nsMessage("Capture en direct, rafraîchie environ chaque seconde.");
          resolve();
        };
        img.onerror = () => {
          nsMessage("Capture indisponible pour le moment.");
          resolve();
        };
        nsCompteur += 1;
        img.src = NS_ROUTE + "capture?jeton=" + Date.now() + "-" + nsCompteur;
      });
    }

    async function nsRafraichir() {
      const rep = await appelApi(NS_ROUTE + "etat");
      if (!rep.ok) {
        if (rep.status === 401 || rep.status === 403) nsBloque = true;
        nsTexte("ns-etat", rep.status === 403 ? "Accès refusé" : "État indisponible");
        nsEffacerCapture();
        nsMessage(rep.status === 403
          ? "Droits insuffisants pour voir le navigateur de l'agent."
          : "Impossible de lire l'état du navigateur.");
        return;
      }
      const ouvert = nsAfficherEtat(await rep.json());
      if (ouvert) {
        await nsChargerCapture();
      } else {
        nsEffacerCapture();
        nsMessage("Aucun navigateur ouvert : l'agent n'a pas de session en cours.");
      }
    }

    function nsPlanifier(delai) {
      clearTimeout(nsMinuteur);
      nsMinuteur = null;
      if (!nsPeutInterroger()) return;
      nsMinuteur = setTimeout(nsCycle, delai);
    }

    async function nsCycle() {
      nsMinuteur = null;
      if (!nsPeutInterroger()) return;
      if (nsEnCours) {
        nsPlanifier(NS_INTERVALLE_MS);
        return;
      }
      nsEnCours = true;
      try {
        await nsRafraichir();
      } catch (e) {
        nsMessage("Connexion au serveur interrompue.");
      } finally {
        nsEnCours = false;
      }
      nsPlanifier(NS_INTERVALLE_MS);
    }

    async function nsEnvoyerControle(corps) {
      if (!nsMain || !nsHumain()) return false;
      let rep;
      try {
        rep = await appelApi(NS_ROUTE + "controle", { method: "POST", body: JSON.stringify(corps) });
      } catch (e) {
        notifier("Commande non envoyée (réseau).", false);
        return false;
      }
      if (!rep.ok) {
        notifier(rep.status === 403
          ? "Droits insuffisants pour piloter le navigateur."
          : "Commande refusée : aucun navigateur ouvert ou session expirée.", false);
        return false;
      }
      nsPlanifier(250);
      return true;
    }

    function nsEnvoyerDefilement() {
      nsMinuteurDefilement = null;
      const delta = Math.round(nsDeltaEnAttente);
      nsDeltaEnAttente = 0;
      if (delta !== 0) nsEnvoyerControle({ type: "defilement", delta_y: delta });
    }

    function nsEnvoyerTexte() {
      const champ = document.getElementById("ns-texte");
      const texte = champ.value;
      if (!texte) return;
      champ.value = ""; // vidé dès la saisie capturée, succès ou échec
      nsEnvoyerControle({ type: "texte", texte: texte });
    }

    async function nsFermerNavigateur() {
      if (!nsHumain()) return;
      if (!window.confirm("Fermer le navigateur de l'agent ? La session en cours sera perdue.")) return;
      const rep = await appelApi(NS_ROUTE + "fermer", { method: "POST" });
      nsRendreLaMain();
      if (rep.ok) {
        notifier("Navigateur de l'agent fermé.", true);
        nsEffacerCapture();
        nsPlanifier(0);
      } else {
        notifier(rep.status === 403
          ? "Droits insuffisants pour fermer le navigateur."
          : "Impossible de fermer le navigateur.", false);
      }
    }

    (function nsBrancher() {
      const img = document.getElementById("ns-capture");
      img.addEventListener("click", (e) => {
        if (!nsMain) return;
        const pos = nsConvertirClic(img.getBoundingClientRect(), e.clientX, e.clientY);
        if (pos) nsEnvoyerControle({ type: "clic", x: pos.x, y: pos.y });
      });
      img.addEventListener("wheel", (e) => {
        if (!nsMain) return;
        e.preventDefault();
        nsDeltaEnAttente += e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY;
        if (nsMinuteurDefilement === null) {
          nsMinuteurDefilement = setTimeout(nsEnvoyerDefilement, NS_DELAI_DEFILEMENT_MS);
        }
      }, { passive: false });
      document.getElementById("ns-prendre-main").addEventListener("click", () => {
        if (!nsHumain()) return;
        nsMain = true;
        nsAppliquerMain();
      });
      document.getElementById("ns-rendre-main").addEventListener("click", nsRendreLaMain);
      document.getElementById("ns-fermer").addEventListener("click", nsFermerNavigateur);
      document.getElementById("ns-envoyer-texte").addEventListener("click", nsEnvoyerTexte);
      document.getElementById("ns-texte").addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          nsEnvoyerTexte();
        }
      });
      document.getElementById("ns-afficher").addEventListener("change", (e) => {
        document.getElementById("ns-texte").type = e.target.checked ? "text" : "password";
      });
      document.querySelectorAll("#ns-controles .ns-touche").forEach((b) => {
        b.addEventListener("click", () => nsEnvoyerControle({ type: "touche", touche: b.getAttribute("data-touche") }));
      });
      document.addEventListener("visibilitychange", () => {
        if (document.hidden) {
          clearTimeout(nsMinuteur);
          nsMinuteur = null;
        } else {
          nsPlanifier(0);
        }
      });
      const allerVersVuePrecedent = allerVersVue;
      allerVersVue = function (cible) {
        const etaitVisible = nsEcranVisible();
        allerVersVuePrecedent(cible);
        if (cible === "vue-navigateur-serveur") {
          nsBloque = false;
          nsAppliquerMain();
          nsPlanifier(0);
        } else if (etaitVisible) {
          clearTimeout(nsMinuteur);
          nsMinuteur = null;
          nsRendreLaMain();
        }
      };
      nsAppliquerMain();
    })();

"""


def _inserer(html: str, marqueur: str, ajout: str, *, avant: bool) -> str:
    if html.count(marqueur) != 1:
        raise RuntimeError("Marqueur d'insertion introuvable ou ambigu : " + marqueur[:60])
    return html.replace(marqueur, ajout + marqueur if avant else marqueur + ajout)


def assembler_navigateur_serveur(html: str) -> str:
    """Insère l'écran « Navigateur de l'agent » (à appeler après `assembler_interface`)."""
    html = _inserer(html, _MARQUEUR_NAV, HTML_NAV, avant=False)
    html = _inserer(html, _MARQUEUR_FIN_MAIN, HTML_VUE_NAVIGATEUR + "\n", avant=True)
    return _inserer(html, _MARQUEUR_JS, JS_NAVIGATEUR, avant=True)
