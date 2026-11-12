"""Coquille de la page : en-tête HTML, navigation groupée par tâche, barre de contexte, thème.

Les écrans (`vues_*.py`) se placent entre `html_debut()` et `HTML_FIN`. Les modules coffre /
récapitulatifs et navigateur de l'agent insèrent leur entrée de navigation aux marqueurs
`<!-- nav:validation -->` et `<!-- nav:navigateur -->`.
"""

from __future__ import annotations

import re

from app.interface.design.styles import CSS_DESIGN, LIEN_POLICES

# Icônes au trait (viewBox 24), génériques et sans texte : jamais de caractère emoji.
_ICONES: dict[str, str] = {
    "accueil": '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
    "etudiants": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8"/><path d="M18.5 14.4c1.9.8 3 2.6 3 5.6"/>',
    "pieces": '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/><path d="M9 13h6M9 17h6"/>',
    "conseiller": '<path d="M4 5h16v11H9l-5 4z"/><path d="M8 9.5h8M8 12.5h5"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z"/>',
    "envoi": '<path d="M3 11l18-7-7 18-2.5-7.5z"/>',
    "procedures": '<path d="M9 6h11M9 12h11M9 18h11"/><path d="M3.5 6l1.3 1.3L7 5M3.5 12l1.3 1.3L7 11M3.5 18l1.3 1.3L7 17"/>',
    "validation": '<path d="M12 3l8 3v6c0 4.5-3.2 7.8-8 9-4.8-1.2-8-4.5-8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
    "recaps": '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V3h6v1"/><path d="M8.5 13l2.5 2.5 4.5-5"/>',
    "audit": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "moniteur": '<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8M12 17v4"/>',
    "abonnement": '<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10.5h18M7 15h4"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
    "fermer": '<path d="M6 6l12 12M18 6L6 18"/>',
    "soleil": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "lune": '<path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z"/>',
    "retour": '<path d="M15 5l-7 7 7 7"/>',
    "suivant": '<path d="M9 5l7 7-7 7"/>',
    "actualiser": '<path d="M20 11a8 8 0 0 0-14-4.5L4 9"/><path d="M4 4v5h5"/><path d="M4 13a8 8 0 0 0 14 4.5L20 15"/><path d="M20 20v-5h-5"/>',
    "haut": '<path d="M5 15l7-7 7 7"/>',
    "bas": '<path d="M5 9l7 7 7-7"/>',
    "micro": '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "externe": '<path d="M14 4h6v6"/><path d="M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    "cadenas": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    "utilisateur": '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 3.6-7 8-7s8 3 8 7"/>',
    "dossier": '<path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "calendrier": '<rect x="4" y="5" width="16" height="16" rx="2"/><path d="M4 10h16M9 3v4M15 3v4"/>',
    "coche": '<circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.7 2.7L16 9.5"/>',
}

_MOTIF_ICONE = re.compile(r"\[\[i:([a-z]+)\]\]")


def icone(nom: str) -> str:
    """Balise <svg> décorative (aria-hidden) pour une icône du système."""
    return (
        '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
        + _ICONES[nom]
        + "</svg>"
    )


def rendre_icones(html: str) -> str:
    """Remplace les jetons [[i:nom]] des gabarits par l'icône correspondante."""
    return _MOTIF_ICONE.sub(lambda m: icone(m.group(1)), html)


def bouton_nav(vue: str, libelle: str, nom_icone: str, *, actif: bool = False, extra: str = "") -> str:
    classe = "nav-btn actif" if actif else "nav-btn"
    courant = ' aria-current="page"' if actif else ""
    return (
        f'<button class="{classe}" type="button" data-vue="{vue}"{courant}>'
        f"{icone(nom_icone)}<span>{libelle}</span>{extra}</button>"
    )


def _groupe(identifiant: str, titre: str, contenu: str) -> str:
    entete = f'<p class="nav-titre" id="nav-titre-{identifiant}">{titre}</p>' if titre else ""
    labelle = f' role="group" aria-labelledby="nav-titre-{identifiant}"' if titre else ""
    return f'    <div class="nav-groupe"{labelle}>{entete}\n      {contenu}\n    </div>\n'


def _navigation() -> str:
    compteur = '<span id="nav-compteur-validation" class="nav-compteur cache" title="Dossiers à traiter"></span>'
    return (
        _groupe("accueil", "", bouton_nav("vue-tableau-bord", "Tableau de bord", "accueil", actif=True))
        + _groupe(
            "dossiers",
            "Dossiers",
            "\n      ".join(
                (
                    bouton_nav("vue-etudiants", "Étudiants et fiches", "etudiants"),
                    bouton_nav("vue-documents", "Pièces et identifiants", "pieces"),
                    bouton_nav("vue-conseiller", "Conseiller et score", "conseiller"),
                )
            ),
        )
        + _groupe(
            "demarches",
            "Démarches",
            "\n      ".join(
                (
                    bouton_nav("vue-campus-france", "Campus France", "globe"),
                    bouton_nav("vue-ircc", "IRCC Canada", "envoi"),
                    bouton_nav("vue-procedures", "Procédures du bureau", "procedures"),
                )
            ),
        )
        + _groupe(
            "validation",
            "Validation &amp; sécurité",
            "\n      ".join(
                (
                    bouton_nav("vue-validation-humaine", "Centre de validation", "validation", extra=compteur),
                    "<!-- nav:validation -->",
                    bouton_nav("vue-historique-erreurs", "Journal d'audit", "audit"),
                )
            ),
        )
        + _groupe("navigateur", "Navigateur de l'agent", "<!-- nav:navigateur -->")
        + _groupe(
            "abonnement",
            "Abonnement",
            bouton_nav("vue-parametres", "Abonnement et sauvegardes", "abonnement"),
        )
    )


_SCRIPT_THEME_INITIAL = """  <script>
    (function () {
      try {
        var choix = localStorage.getItem("theme-interface");
        if (choix === "dark" || choix === "light") document.documentElement.setAttribute("data-theme", choix);
      } catch (e) { /* stockage indisponible : on suit le thème du système */ }
    })();
  </script>"""


def html_debut() -> str:
    """De <!DOCTYPE> jusqu'à l'ouverture de <main> (barre de contexte et notification incluses)."""
    return rendre_icones(f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="color-scheme" content="light dark" />
  <title>Agent Bureau d'Études — Dossiers Campus France et IRCC</title>
  {LIEN_POLICES}
{_SCRIPT_THEME_INITIAL}
  <style>{CSS_DESIGN}  </style>
</head>
<body>
  <header class="barre-haute">
    <button id="btn-menu" class="btn btn-contour btn-icone" type="button" aria-controls="navigation-principale" aria-expanded="false" aria-label="Ouvrir le menu">[[i:menu]]</button>
    <div class="marque"><span class="marque-logo">[[i:dossier]]</span><span class="marque-nom">Agent Bureau d'Études</span></div>
  </header>
  <button id="scrim-menu" class="scrim" type="button" aria-label="Fermer le menu" tabindex="-1"></button>
  <aside id="navigation-principale" aria-label="Navigation principale">
    <div class="marque">
      <span class="marque-logo">[[i:dossier]]</span>
      <span class="marque-nom">Agent Bureau d'Études<span class="marque-sous">Plateforme Algérie</span></span>
    </div>
    <nav aria-label="Écrans">
{_navigation()}    </nav>
    <div class="nav-pied">
      <section id="bloc-connexion" aria-label="Session de l'opérateur">
        <div class="session-etat">[[i:utilisateur]]<span id="etat-utilisateur">Connexion en cours...</span></div>
        <details class="session-form">
          <summary>Se connecter ou changer de compte</summary>
          <div class="grille-form">
            <label><span class="sr-only">Adresse e-mail de connexion</span>
              <input id="login-email" type="email" placeholder="employe@bureau.dz" autocomplete="username" /></label>
            <label><span class="sr-only">Mot de passe</span>
              <input id="login-mdp" type="password" autocomplete="current-password" /></label>
          </div>
          <div class="session-actions" style="margin-top:8px;">
            <button id="btn-se-connecter" class="btn btn-primaire btn-sm" type="button">Se connecter</button>
            <a class="btn-lien" href="/mot-de-passe-oublie">Mot de passe oublié ?</a>
          </div>
        </details>
        <div class="session-actions" style="margin-top:8px;">
          <button id="btn-se-deconnecter" class="btn btn-contour btn-sm cache" type="button">Se déconnecter</button>
        </div>
      </section>
      <button id="btn-theme" class="bouton-theme" type="button" aria-label="Passer en thème sombre">
        <span class="icone-lune">[[i:lune]]</span><span class="icone-soleil">[[i:soleil]]</span>
        <span id="libelle-theme">Thème sombre</span>
      </button>
    </div>
  </aside>

  <main id="contenu">
    <div id="banniere-etat">
      <span class="banniere-contexte">[[i:dossier]]<span>Dossier actif : <strong id="bandeau-candidat-actif">Aucun</strong></span></span>
      <span class="banniere-regle-courte">Données chiffrées par bureau. L'agent s'arrête toujours avant l'envoi officiel.</span>
    </div>
    <div id="bandeau-email-non-verifie" class="banniere-regle banniere-alerte cache" role="status">
      <strong>Adresse e-mail non vérifiée.</strong>
      <span>Confirmez votre adresse pour sécuriser votre compte et recevoir les messages de la plateforme.</span>
      <button id="btn-renvoyer-verification" class="btn btn-secondaire btn-sm" type="button">Renvoyer l'e-mail de vérification</button>
    </div>
    <div id="zone-notification" class="notif cache" role="status" aria-live="polite"></div>
""")


JS_COQUILLE = """
    // ===== Coquille : thème clair/sombre mémorisé, menu repliable sur téléphone =====
    function themeEffectif() {
      const choix = document.documentElement.getAttribute("data-theme");
      if (choix === "dark" || choix === "light") return choix;
      return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }

    function majBoutonTheme() {
      const sombre = themeEffectif() === "dark";
      const bouton = document.getElementById("btn-theme");
      bouton.setAttribute("aria-label", sombre ? "Passer en thème clair" : "Passer en thème sombre");
      document.getElementById("libelle-theme").textContent = sombre ? "Thème clair" : "Thème sombre";
    }

    document.getElementById("btn-theme").addEventListener("click", () => {
      const suivant = themeEffectif() === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", suivant);
      try { localStorage.setItem("theme-interface", suivant); } catch (e) { /* mémorisation facultative */ }
      majBoutonTheme();
    });
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", majBoutonTheme);
    majBoutonTheme();

    function majBandeauVerification(utilisateur) {
      const non_verifie = !!utilisateur && utilisateur.email_verifie === false;
      document.getElementById("bandeau-email-non-verifie").classList.toggle("cache", !non_verifie);
    }

    document.getElementById("btn-renvoyer-verification").addEventListener("click", async () => {
      const bouton = document.getElementById("btn-renvoyer-verification");
      bouton.disabled = true;
      try {
        const rep = await appelApi("/api/v1/auth/verification-adresse/renvoyer", { method: "POST" });
        const data = await rep.json().catch(() => null);
        if (rep.ok) notifier((data && data.message) || "E-mail de vérification envoyé : consultez votre boîte de réception.", true);
        else notifier(messageErreurApi(data, "Envoi impossible pour le moment : réessayez dans quelques minutes."), false);
      } catch (e) {
        notifier("Envoi impossible : vérifiez votre connexion puis réessayez.", false);
      } finally {
        bouton.disabled = false;
      }
    });

    function fermerMenuMobile() {
      document.body.classList.remove("nav-ouverte");
      document.getElementById("btn-menu").setAttribute("aria-expanded", "false");
    }

    document.getElementById("btn-menu").addEventListener("click", () => {
      const ouvert = document.body.classList.toggle("nav-ouverte");
      document.getElementById("btn-menu").setAttribute("aria-expanded", ouvert ? "true" : "false");
    });
    document.getElementById("scrim-menu").addEventListener("click", fermerMenuMobile);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") fermerMenuMobile();
    });

"""
