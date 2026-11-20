"""Pages publiques (sans session) : vitrine `/bienvenue` et formulaire `/inscription`.

HTML autonome servi sans session. Il reprend la feuille du système de design (`CSS_DESIGN`, tokens
clair et sombre) et ajoute la feuille de la vitrine (`vitrine_css`, tokens uniquement). Sections
dans `vitrine_html`, scripts dans `vitrine_js`. Tout le contenu est lisible sans JavaScript et sans
animation. Les forfaits sont lus dans le catalogue.
"""

from __future__ import annotations

from html import escape

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.interface import vitrine_html
from app.interface.design.shell import icone
from app.interface.design.styles import CSS_DESIGN, LIEN_POLICES
from app.interface.vitrine_css import STYLE_PUBLIC
from app.interface.vitrine_js import (
    SCRIPT_INSCRIPTION,
    SCRIPT_SCENE,
    SCRIPT_THEME,
    SCRIPT_THEME_INITIAL,
    SCRIPT_VITRINE,
)
from app.services.abonnements import lister_catalogue_forfaits

routeur_public = APIRouter(include_in_schema=False)

_LIENS_NAV = (
    ("/bienvenue#comment", "Comment ça marche", ""),
    ("/bienvenue#securite", "Sécurité", ""),
    ("/bienvenue#tarifs", "Tarifs", ""),
    ("/bienvenue#faq", "FAQ", ""),
)


def _entete() -> str:
    liens = "".join(
        f'<a class="pub-lien-nav optionnel" href="{href}">{libelle}</a>' for href, libelle, _ in _LIENS_NAV
    )
    return f"""<header class="pub-entete"><div class="v-cadre pub-entete-ligne">
<a class="marque" href="/bienvenue"><span class="marque-logo">{icone("dossier")}</span>
<span class="marque-nom">Agent Bureau d'Études<span class="marque-sous">Campus France · IRCC Canada · Algérie</span></span></a>
<nav class="pub-nav" aria-label="Navigation principale">{liens}
<a class="pub-lien-nav" href="/">Connexion</a>
<a class="btn btn-primaire btn-sm" href="/inscription">Créer mon bureau</a>
<button class="btn btn-fantome btn-icone btn-sm" type="button" data-bascule-theme aria-label="Passer en thème sombre"><span class="icone-lune">{icone("lune")}</span><span class="icone-soleil">{icone("soleil")}</span></button>
</nav></div></header>"""


_PIED = """<footer class="v-pied"><div class="v-cadre v-pied-grille">
<div><p>Plateforme destinée aux bureaux d'études et d'accompagnement. Aucun résultat de démarche
n'est garanti : les décisions appartiennent aux autorités compétentes.</p></div>
<nav aria-label="Produit"><h2>Produit</h2><ul><li><a href="/bienvenue#comment">Comment ça marche</a></li>
<li><a href="/bienvenue#securite">Sécurité</a></li><li><a href="/bienvenue#tarifs">Tarifs</a></li>
<li><a href="/bienvenue#faq">Questions fréquentes</a></li></ul></nav>
<nav aria-label="Compte"><h2>Compte</h2><ul><li><a href="/inscription">Créer mon bureau</a></li>
<li><a href="/">Connexion</a></li><li><a href="/mot-de-passe-oublie">Mot de passe oublié</a></li></ul></nav>
</div></footer>"""


def _page(
    titre: str,
    description: str,
    corps: str,
    script: str = "",
    courant: str = "",
    pleine_largeur: bool = False,
) -> HTMLResponse:
    """Coquille commune. `corps` est inséré tel quel (pleine largeur) ou dans un cadre centré."""
    contenu = corps if pleine_largeur else f'<div class="v-cadre v-courriel">{corps}</div>'
    html = f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<title>{escape(titre)}</title>
<meta name="description" content="{escape(description)}">
{LIEN_POLICES}
{SCRIPT_THEME_INITIAL}
<style>{CSS_DESIGN}{STYLE_PUBLIC}</style>
</head>
<body class="publique">
<a class="sr-focus" href="#contenu">Aller au contenu</a>
{_entete()}
<main id="contenu" tabindex="-1">
{contenu}
</main>
{_PIED}
{SCRIPT_THEME}
{script}
</body>
</html>"""
    return HTMLResponse(html)


@routeur_public.get("/bienvenue", response_class=HTMLResponse)
def page_bienvenue() -> HTMLResponse:
    return _page(
        "Agent Bureau d'Études : dossiers Campus France et IRCC préparés, validés par vous",
        "Plateforme pour bureaux d'études : préparation des dossiers Campus France et IRCC, "
        "validation humaine avant tout envoi, essai de 30 jours.",
        vitrine_html.corps_bienvenue(),
        SCRIPT_VITRINE + SCRIPT_SCENE,
        courant="bienvenue",
        pleine_largeur=True,
    )


def _panneau_inscription() -> str:
    return f"""<div class="connexion-marque">
<div class="marque"><span class="marque-logo">{icone("dossier")}</span>
<span class="marque-nom">Agent Bureau d'Études<span class="marque-sous">Campus France · IRCC Canada · Algérie</span></span></div>
<p class="connexion-accroche">Un espace isolé pour les dossiers de votre bureau, prêt dès aujourd'hui.</p>
<ol class="v-apres">
<li><div><strong>Vous administrez le bureau</strong><span>Le compte créé ici devient l'administrateur de votre bureau.</span></div></li>
<li><div><strong>Vous créez les fiches et déposez les pièces</strong><span>La plateforme lit les documents et prépare chaque dossier.</span></div></li>
<li><div><strong>Rien n'est envoyé sans vous</strong><span>L'agent s'arrête avant toute soumission officielle et attend la validation d'un humain.</span></div></li>
</ol>
</div>"""


@routeur_public.get("/inscription", response_class=HTMLResponse)
def page_inscription() -> HTMLResponse:
    options = "".join(
        f'<option value="{escape(f.forfait.value)}" data-quota="{f.quota_dossiers_mensuels}">'
        f"{escape(f.libelle)} - {f.prix_mensuel_eur} EUR/mois</option>"
        for f in lister_catalogue_forfaits()
    )
    corps = f"""
<div class="v-cadre v-inscription">
<section class="connexion pub-inscription" aria-labelledby="titre-inscription">
<div class="connexion-form">
<div class="connexion-entete"><span class="surtitre">Essai de 30 jours</span>
<h1 id="titre-inscription">Créer mon bureau</h1>
<p>Vous deviendrez administrateur de votre bureau. Aucun paiement n'est demandé.</p></div>
<div id="retour" role="alert" tabindex="-1" hidden></div>
<form id="formulaire" class="connexion-champs" novalidate>
<label>Nom du bureau
<input name="nom_bureau" required minlength="2" maxlength="120" autocomplete="organization"></label>
<label>Votre nom
<input name="nom_admin" required maxlength="120" autocomplete="name"></label>
<label>Adresse e-mail
<input name="email_admin" type="email" required autocomplete="email"></label>
<label>Mot de passe
<input name="mot_de_passe" type="password" required minlength="12" autocomplete="new-password"
aria-describedby="aide-mdp">
<span id="aide-mdp" class="champ-aide">12 caractères minimum, avec au moins 3 types parmi :
minuscules, majuscules, chiffres, symboles.</span></label>
<label>Forfait
<select name="forfait" aria-describedby="info-forfait">{options}</select>
<span id="info-forfait" class="champ-aide"></span></label>
<div class="piege" aria-hidden="true"><label>Site web
<input name="site_web" tabindex="-1" autocomplete="off"></label></div>
<details id="voir-cgu"><summary>Lire les Conditions Générales d'Utilisation</summary>
<pre class="cgu" id="texte-cgu">Chargement...</pre></details>
<label class="case"><input type="checkbox" name="accepte_cgu" required>
<span>J'ai lu et j'accepte les Conditions Générales d'Utilisation.</span></label>
<button class="btn btn-primaire btn-lg" id="envoyer" type="submit">Créer mon bureau</button>
</form>
<p class="connexion-pied">Déjà un compte ?&nbsp;<a href="/">Se connecter</a></p>
</div>
{_panneau_inscription()}
</section>
</div>
"""
    return _page(
        "Créer mon bureau - Agent Bureau d'Études",
        "Inscription d'une agence à la plateforme : essai de 30 jours.",
        corps,
        SCRIPT_INSCRIPTION,
        pleine_largeur=True,
    )


from app.api.pages_courriel import enregistrer_pages_courriel  # noqa: E402

enregistrer_pages_courriel(routeur_public, _page)
