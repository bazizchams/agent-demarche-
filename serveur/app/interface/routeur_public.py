"""Pages publiques (sans session) : page de vente `/bienvenue` et formulaire `/inscription`.

HTML autonome servi sans session. Il reprend la feuille du système de design (`CSS_DESIGN`, tokens
clair et sombre) et n'ajoute qu'un bloc local écrit uniquement avec `var(--...)`. Les polices
viennent de Google Fonts, avec piles de secours système. Les forfaits sont lus dans le catalogue.
"""

from __future__ import annotations

from html import escape

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.interface.design.shell import icone
from app.interface.design.styles import CSS_DESIGN, LIEN_POLICES
from app.services.abonnements import lister_catalogue_forfaits

routeur_public = APIRouter(include_in_schema=False)

# Compléments propres aux pages publiques : uniquement des tokens, aucune couleur littérale.
_STYLE_PUBLIC = """
    [hidden] { display: none !important; }
    body.publique { display: block; }
    body.publique main { max-width: none; padding: 0; }
    .pub-cadre { max-width: 1160px; margin: 0 auto; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
    .pub-entete { position: sticky; top: 0; z-index: 30; background: var(--fond); background: color-mix(in srgb, var(--fond) 88%, transparent); backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px); border-bottom: 1px solid var(--bord); }
    .pub-entete-ligne { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--e2) var(--e4); padding-block: var(--e3); }
    .pub-entete .marque { padding: 0; text-decoration: none; color: var(--texte); }
    .pub-nav { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e1) var(--e2); }
    .pub-nav .btn { margin: 0; }
    .pub-lien-nav { padding: 6px var(--e2); border-radius: var(--r-s); color: var(--texte-doux); text-decoration: none; font-size: var(--t-sm); font-weight: 500; }
    .pub-lien-nav:hover, .pub-lien-nav[aria-current="page"] { color: var(--accent-fort); background: var(--accent-doux); }
    .pub-contenu { padding-block: var(--e7) var(--e8); display: flex; flex-direction: column; gap: var(--e8); }
    .pub-contenu h1 { font-size: clamp(2rem, 4.4vw, var(--t-3xl)); letter-spacing: -0.03em; line-height: 1.08; }
    .pub-lead { font-size: var(--t-md); color: var(--texte-doux); max-width: 58ch; margin: 0; line-height: 1.6; }
    .pub-actions { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e3); }
    .pub-actions .btn { margin: 0; }

    /* Accroche : texte à gauche, aperçu du tableau de bord à droite */
    .pub-hero { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.05fr); gap: var(--e7); align-items: center; }
    .pub-hero-texte { display: flex; flex-direction: column; gap: var(--e5); min-width: 0; }
    .pub-garanties { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: var(--e2) var(--e4); font-size: var(--t-sm); color: var(--texte-doux); }
    .pub-garanties li { display: inline-flex; align-items: center; gap: 6px; }
    .pub-garanties .ico { color: var(--bon); }

    .apercu { position: relative; padding: var(--e5); border-radius: var(--r-xl); background: radial-gradient(120% 90% at 100% 0%, var(--marque-fond-2) 0%, var(--marque-fond) 62%); box-shadow: var(--ombre-2); min-width: 0; }
    .apercu-etiquette { position: absolute; top: var(--e3); right: var(--e4); font-size: var(--t-xs); font-weight: 600; letter-spacing: 0.07em; text-transform: uppercase; color: var(--sur-marque-doux); }
    .apercu-fenetre { margin-top: var(--e4); background: var(--fond); border-radius: var(--r-l); overflow: hidden; box-shadow: var(--ombre-flottante); }
    .apercu-barre { display: flex; align-items: center; gap: 6px; padding: var(--e2) var(--e3); background: var(--surface); border-bottom: 1px solid var(--bord); font-size: var(--t-xs); color: var(--texte-faible); }
    .apercu-point { width: 8px; height: 8px; border-radius: 50%; background: var(--bord-fort); flex: none; }
    .apercu-barre span:last-child { margin-left: var(--e2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .apercu-corps { display: grid; grid-template-columns: 116px minmax(0, 1fr); }
    .apercu-nav { display: flex; flex-direction: column; gap: 4px; padding: var(--e3) var(--e2); background: var(--surface); border-right: 1px solid var(--bord); font-size: var(--t-xs); color: var(--texte-doux); }
    .apercu-nav span { display: flex; align-items: center; gap: 6px; padding: 5px 6px; border-radius: var(--r-s); white-space: nowrap; overflow: hidden; }
    .apercu-nav .ico { width: 13px; height: 13px; color: var(--texte-faible); }
    .apercu-nav .actif { background: var(--accent-doux); color: var(--accent-fort); font-weight: 600; }
    .apercu-nav .actif .ico { color: var(--accent); }
    .apercu-contenu { display: flex; flex-direction: column; gap: var(--e3); padding: var(--e3); min-width: 0; }
    .apercu-titre { font-family: var(--police-titre); font-weight: 700; font-size: var(--t-base); color: var(--texte); }
    .apercu-kpis { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--e2); }
    .apercu-kpi { display: flex; flex-direction: column; gap: 2px; padding: var(--e2) var(--e3); background: var(--surface); border: 1px solid var(--bord); border-radius: var(--r-m); min-width: 0; }
    .apercu-kpi span { font-size: 11px; color: var(--texte-faible); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .apercu-kpi b { font-family: var(--police-titre); font-size: var(--t-lg); line-height: 1.1; color: var(--texte); font-variant-numeric: tabular-nums; }
    .apercu-kpi.alerte b { color: var(--alerte-texte); }
    .apercu-dossiers { list-style: none; margin: 0; padding: 0; background: var(--surface); border: 1px solid var(--bord); border-radius: var(--r-m); }
    .apercu-dossiers li { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 6px var(--e3); padding: var(--e2) var(--e3); border-top: 1px solid var(--bord); }
    .apercu-dossiers li:first-child { border-top: 0; }
    .apercu-dossiers strong { display: block; font-size: var(--t-sm); font-weight: 600; color: var(--texte); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .apercu-dossiers small { display: block; font-size: 11px; color: var(--texte-faible); }
    .apercu-dossiers .barre-progression { grid-column: 1 / -1; height: 5px; margin: 0; }

    /* Sections */
    .pub-section { display: flex; flex-direction: column; gap: var(--e5); }
    .pub-section-entete { display: flex; flex-direction: column; gap: var(--e2); max-width: 62ch; }
    .pub-section-entete h2 { font-size: var(--t-xl); }
    .pub-section-entete p { margin: 0; color: var(--texte-doux); }
    .pub-arguments { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 240px), 1fr)); gap: var(--e4); }
    .pub-arguments .carte { margin: 0; display: flex; flex-direction: column; gap: var(--e2); }
    .pub-arguments h3 { margin: var(--e2) 0 0; }
    .pub-arguments p { margin: 0; color: var(--texte-doux); font-size: var(--t-sm); line-height: 1.6; }
    .pub-icone { width: 40px; height: 40px; border-radius: var(--r-m); display: grid; place-items: center; background: var(--accent-doux); color: var(--accent); }
    .pub-icone .ico { width: 20px; height: 20px; }
    .pub-etapes { margin: 0; padding: var(--e5); background: var(--surface); border: 1px solid var(--bord); border-radius: var(--r-l); box-shadow: var(--ombre-1); }
    .pub-forfaits { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 230px), 1fr)); gap: var(--e4); }
    .pub-forfaits .carte { margin: 0; display: flex; flex-direction: column; gap: var(--e3); }
    .pub-forfaits h3 { font-size: var(--t-md); }
    .pub-prix { margin: 0; display: flex; align-items: baseline; gap: var(--e2); }
    .pub-prix b { font-family: var(--police-titre); font-size: var(--t-2xl); line-height: 1; letter-spacing: -0.03em; font-variant-numeric: tabular-nums; color: var(--texte); }
    .pub-prix span { font-size: var(--t-sm); color: var(--texte-faible); }
    .pub-quota { margin: 0; display: flex; align-items: center; gap: var(--e2); padding-top: var(--e3); border-top: 1px solid var(--bord); color: var(--texte-doux); font-size: var(--t-sm); }
    .pub-quota .ico { color: var(--accent); }
    .pub-forfaits .btn { margin: auto 0 0; }
    .pub-appel { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--e4); padding: var(--e6); border-radius: var(--r-xl); color: var(--sur-marque); background: radial-gradient(120% 140% at 100% 0%, var(--marque-fond-2) 0%, var(--marque-fond) 60%); }
    .pub-appel h2 { color: var(--sur-marque); font-size: var(--t-xl); }
    .pub-appel p { margin: var(--e2) 0 0; color: var(--sur-marque-doux); max-width: 56ch; }
    .pub-appel .btn { margin: 0; background: var(--surface); color: var(--accent-fort); border-color: var(--surface); }
    .pub-appel .btn:hover { background: var(--accent-doux); border-color: var(--accent-doux); color: var(--accent-fort); }

    /* Pied de page */
    .pub-pied { border-top: 1px solid var(--bord); background: var(--surface); }
    .pub-pied-ligne { display: flex; flex-wrap: wrap; justify-content: space-between; gap: var(--e3) var(--e6); padding-block: var(--e5) var(--e6); font-size: var(--t-sm); color: var(--texte-faible); }
    .pub-pied-ligne p { margin: 0; max-width: 62ch; }
    .pub-pied-liens { display: flex; flex-wrap: wrap; gap: var(--e2) var(--e4); }
    .pub-pied-liens a { color: var(--texte-doux); }

    /* Inscription : même composition que l'écran de connexion */
    .pub-inscription { display: grid; }
    .connexion-entete h1 { font-size: var(--t-2xl); letter-spacing: -0.025em; }
    .pub-inscription .connexion-form { justify-content: flex-start; }
    .pub-inscription details summary { cursor: pointer; color: var(--accent); font-size: var(--t-sm); font-weight: 500; }
    pre.cgu { white-space: pre-wrap; font: inherit; font-size: var(--t-sm); line-height: 1.6; max-height: 18rem; overflow: auto; margin: var(--e2) 0 0; padding: var(--e3) var(--e4); border: 1px solid var(--bord); border-radius: var(--r-m); background: var(--surface-2); color: var(--texte-doux); }
    .piege { position: absolute; left: -10000px; width: 1px; height: 1px; overflow: hidden; }

    /* Pages courriel : carte centrée */
    .pub-centre { display: grid; place-items: start center; }
    .pub-carte { width: 100%; max-width: 460px; display: flex; flex-direction: column; gap: var(--e5); padding: var(--e6); background: var(--surface); border: 1px solid var(--bord); border-radius: var(--r-xl); box-shadow: var(--ombre-2); }
    .pub-carte-entete { display: flex; flex-direction: column; gap: var(--e3); }
    .pub-carte-entete h1 { font-size: var(--t-xl); letter-spacing: -0.02em; line-height: 1.15; }
    .pub-carte-entete p { margin: 0; color: var(--texte-doux); }
    .pub-pastille { width: 48px; height: 48px; border-radius: var(--r-l); display: grid; place-items: center; background: var(--accent-doux); color: var(--accent); }
    .pub-pastille .ico { width: 24px; height: 24px; }
    .pub-champs { display: flex; flex-direction: column; gap: var(--e4); }
    .pub-champs .btn, .pub-carte .btn { margin: 0; }
    .pub-carte-pied { margin: 0; padding-top: var(--e4); border-top: 1px solid var(--bord); font-size: var(--t-sm); display: flex; flex-wrap: wrap; justify-content: space-between; gap: var(--e2); }

    /* Retour d'action (classes posées par le JavaScript : message ok / message erreur) */
    .message { position: relative; padding: var(--e3) var(--e4) var(--e3) calc(var(--e4) + 20px); border-radius: var(--r-m); background: var(--surface-2); color: var(--texte); font-size: var(--t-sm); font-weight: 500; line-height: 1.5; }
    .message::before { content: ""; position: absolute; left: var(--e4); top: calc(var(--e3) + 5px); width: 10px; height: 10px; border-radius: 50%; background: var(--accent); }
    .message.ok { background: var(--bon-doux); color: var(--bon-texte); }
    .message.ok::before { background: var(--bon); box-shadow: 0 0 0 3px color-mix(in srgb, var(--bon) 25%, transparent); }
    .message.erreur { background: var(--critique-doux); color: var(--critique-texte); }
    .message.erreur::before { background: var(--critique); border-radius: 2px; transform: rotate(45deg); }
    .message a { color: inherit; font-weight: 700; }
    .message:focus { outline: none; }
    .message:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

    @media (max-width: 960px) {
      .pub-hero { grid-template-columns: minmax(0, 1fr); gap: var(--e6); }
    }
    @media (max-width: 720px) {
      .pub-contenu { padding-block: var(--e5) var(--e7); gap: var(--e7); }
      .pub-lien-nav.optionnel { display: none; }
      .pub-entete .marque-sous { display: none; }
      .apercu { padding: var(--e3); }
      .apercu-etiquette { position: static; display: block; }
      .apercu-fenetre { margin-top: var(--e2); }
      .apercu-corps { grid-template-columns: minmax(0, 1fr); }
      .apercu-nav { display: none; }
      .pub-etapes { padding: var(--e4); }
      .pub-appel { padding: var(--e5); }
      .pub-carte { padding: var(--e5); }
    }
"""

_SCRIPT_THEME_INITIAL = """<script>
(function(){try{var c=localStorage.getItem("theme-interface");
if(c==="dark"||c==="light")document.documentElement.setAttribute("data-theme",c);}catch(e){}})();
</script>"""

_SCRIPT_THEME = """<script>
(function(){
function effectif(){var c=document.documentElement.getAttribute("data-theme");
 if(c==="dark"||c==="light")return c;
 return window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";}
function maj(){var s=effectif()==="dark";
 document.querySelectorAll("[data-bascule-theme]").forEach(function(b){
  b.setAttribute("aria-label",s?"Passer en thème clair":"Passer en thème sombre");});}
document.querySelectorAll("[data-bascule-theme]").forEach(function(b){
 b.addEventListener("click",function(){var n=effectif()==="dark"?"light":"dark";
  document.documentElement.setAttribute("data-theme",n);
  try{localStorage.setItem("theme-interface",n);}catch(e){}maj();});});
maj();
})();
</script>"""

_LIENS_NAV = (
    ("/bienvenue", "Présentation", "bienvenue"),
    ("/bienvenue#forfaits", "Forfaits", ""),
)


_ATTR_COURANT = ' aria-current="page"'


def _entete(courant: str) -> str:
    liens = "".join(
        f'<a class="pub-lien-nav optionnel" href="{href}"'
        f'{_ATTR_COURANT if cle and cle == courant else ""}>{libelle}</a>'
        for href, libelle, cle in _LIENS_NAV
    )
    return f"""<header class="pub-entete"><div class="pub-cadre pub-entete-ligne">
<a class="marque" href="/bienvenue"><span class="marque-logo">{icone("dossier")}</span>
<span class="marque-nom">Agent Bureau d'Études<span class="marque-sous">Campus France · IRCC Canada · Algérie</span></span></a>
<nav class="pub-nav" aria-label="Navigation principale">{liens}
<a class="pub-lien-nav" href="/">Connexion</a>
<a class="btn btn-primaire btn-sm" href="/inscription">Créer mon bureau</a>
<button class="btn btn-fantome btn-icone btn-sm" type="button" data-bascule-theme aria-label="Passer en thème sombre"><span class="icone-lune">{icone("lune")}</span><span class="icone-soleil">{icone("soleil")}</span></button>
</nav></div></header>"""


_PIED = """<footer class="pub-pied"><div class="pub-cadre pub-pied-ligne">
<p>Plateforme destinée aux bureaux d'études et d'accompagnement. Aucun résultat de démarche n'est
garanti : les décisions appartiennent aux autorités compétentes.</p>
<nav class="pub-pied-liens" aria-label="Liens utiles"><a href="/bienvenue">Présentation</a>
<a href="/inscription">Créer mon bureau</a><a href="/">Connexion</a>
<a href="/mot-de-passe-oublie">Mot de passe oublié</a></nav>
</div></footer>"""


def _page(titre: str, description: str, corps: str, script: str = "", courant: str = "") -> HTMLResponse:
    html = f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<title>{escape(titre)}</title>
<meta name="description" content="{escape(description)}">
{LIEN_POLICES}
{_SCRIPT_THEME_INITIAL}
<style>{CSS_DESIGN}{_STYLE_PUBLIC}</style>
</head>
<body class="publique">
{_entete(courant)}
<main id="contenu"><div class="pub-cadre pub-contenu">
{corps}
</div></main>
{_PIED}
{_SCRIPT_THEME}
{script}
</body>
</html>"""
    return HTMLResponse(html)


def _cartes_forfaits() -> str:
    morceaux = []
    for f in lister_catalogue_forfaits():
        morceaux.append(
            '<li class="carte">'
            f"<h3>{escape(f.libelle)}</h3>"
            f'<p class="pub-prix"><b>{f.prix_mensuel_eur}&nbsp;&euro;</b><span>par mois</span></p>'
            f'<p class="pub-quota">{icone("dossier")}'
            f"<span>Jusqu'à {f.quota_dossiers_mensuels} dossiers actifs par mois</span></p>"
            """<a class="btn btn-contour btn-bloc" href="/inscription">Commencer l'essai</a>"""
            "</li>"
        )
    return '<ul class="pub-forfaits">' + "".join(morceaux) + "</ul>"


_APERCU = f"""<div class="apercu" role="img" aria-label="Aperçu du tableau de bord avec des dossiers d'exemple">
<span class="apercu-etiquette" aria-hidden="true">Aperçu · données d'exemple</span>
<div class="apercu-fenetre" aria-hidden="true">
<div class="apercu-barre"><span class="apercu-point"></span><span class="apercu-point"></span><span class="apercu-point"></span><span>Tableau de bord · Bureau Horizon</span></div>
<div class="apercu-corps">
<div class="apercu-nav"><span class="actif">{icone("accueil")}Accueil</span><span>{icone("etudiants")}Étudiants</span>
<span>{icone("globe")}Campus France</span><span>{icone("envoi")}IRCC</span><span>{icone("validation")}Validation</span></div>
<div class="apercu-contenu">
<span class="apercu-titre">Dossiers de la semaine</span>
<div class="apercu-kpis"><div class="apercu-kpi"><span>Dossiers actifs</span><b>24</b></div>
<div class="apercu-kpi"><span>À valider</span><b>3</b></div>
<div class="apercu-kpi alerte"><span>En pause</span><b>2</b></div></div>
<ul class="apercu-dossiers">
<li><div><strong>Études en France · Licence 3 Informatique</strong><small>Pièces 11 sur 11 · récapitulatif prêt</small></div>
<span class="badge badge-valide">Prêt à valider</span>
<div class="barre-progression ok"><div class="barre-progression-remplie" style="width:100%"></div></div></li>
<li><div><strong>IRCC · Permis d'études, Montréal</strong><small>Pièces 7 sur 11</small></div>
<span class="badge badge-completer">À compléter</span>
<div class="barre-progression"><div class="barre-progression-remplie" style="width:64%"></div></div></li>
<li><div><strong>Études en France · Master 1 Gestion</strong><small>CAPTCHA sur le portail : à vous</small></div>
<span class="badge badge-attente">En pause</span>
<div class="barre-progression alerte"><div class="barre-progression-remplie" style="width:82%"></div></div></li>
</ul></div></div></div></div>"""


def _argument(nom_icone: str, titre: str, texte: str) -> str:
    return (
        f'<li class="carte"><span class="pub-icone">{icone(nom_icone)}</span>'
        f"<h3>{titre}</h3><p>{texte}</p></li>"
    )


_ARGUMENTS = "".join(
    (
        _argument(
            "validation",
            "Arrêt avant l'envoi officiel",
            "Le co-pilote pré-remplit les formulaires des portails officiels, s'arrête avant toute "
            "soumission et attend la validation d'un membre de votre équipe.",
        ),
        _argument(
            "pause",
            "CAPTCHA et double authentification",
            "Ils restent entre vos mains : l'agent ne les contourne jamais, il met le dossier en "
            "pause et vous alerte.",
        ),
        _argument(
            "cadenas",
            "Dossiers chiffrés par bureau",
            "Les données et documents de chaque candidat sont chiffrés, et chaque bureau ne voit que "
            "ses propres dossiers.",
        ),
        _argument(
            "procedures",
            "Vos procédures, sans redéploiement",
            "Les démarches sont décrites dans des fichiers de configuration que vous adaptez. "
            "L'assistant IA vous aide sans recevoir de nom, d'e-mail ni de numéro de passeport.",
        ),
    )
)


@routeur_public.get("/bienvenue", response_class=HTMLResponse)
def page_bienvenue() -> HTMLResponse:
    corps = f"""
<section class="pub-hero" aria-labelledby="titre-accroche">
<div class="pub-hero-texte">
<span class="surtitre">Pour les bureaux d'études et d'accompagnement</span>
<h1 id="titre-accroche">Vos dossiers Campus France et IRCC préparés, jamais envoyés sans vous.</h1>
<p class="pub-lead">L'agent prépare les dossiers Études en France et les demandes de permis
d'études au Canada, pré-remplit les portails officiels puis s'arrête avant l'envoi. Un membre de
votre bureau relit et valide.</p>
<div class="pub-actions"><a class="btn btn-primaire btn-lg" href="/inscription">Créer mon bureau</a>
<a class="btn btn-contour btn-lg" href="#forfaits">Voir les forfaits</a></div>
<ul class="pub-garanties"><li>{icone("coche")}30 jours d'essai</li>
<li>{icone("coche")}Validation humaine obligatoire</li><li>{icone("coche")}Loi 18-07 et RGPD</li></ul>
</div>
{_APERCU}
</section>

<section class="pub-section" aria-labelledby="titre-arguments">
<div class="pub-section-entete"><span class="surtitre">Ce que fait la plateforme</span>
<h2 id="titre-arguments">Un co-pilote qui prépare, votre équipe qui décide</h2>
<p>De la petite structure à l'équipe de plusieurs conseillers : candidats, pièces et démarches
suivis au même endroit.</p></div>
<ul class="pub-arguments">{_ARGUMENTS}</ul>
</section>

<section class="pub-section" aria-labelledby="titre-etapes">
<div class="pub-section-entete"><span class="surtitre">Déroulé d'un dossier</span>
<h2 id="titre-etapes">De la fiche du candidat à la validation</h2></div>
<ol class="etapes pub-etapes">
<li class="etape"><span class="etape-titre">Fiche et pièces</span>Vous créez la fiche et rassemblez les pièces du candidat.</li>
<li class="etape"><span class="etape-titre">Pré-remplissage</span>L'agent remplit Études en France ou IRCC selon votre procédure.</li>
<li class="etape"><span class="etape-titre">Récapitulatif</span>Il s'arrête avant le bouton final et montre ce qui sera transmis.</li>
<li class="etape"><span class="etape-titre">Validation humaine</span>Rien n'est soumis sans l'accord d'un membre de l'équipe.</li>
</ol>
<p class="note">Consentement explicite du candidat, journal d'audit sans donnée personnelle,
suppression à la demande : la plateforme est conçue pour accompagner le respect de la loi
algérienne n° 18-07 et du RGPD.</p>
</section>

<section class="pub-section" id="forfaits" aria-labelledby="titre-forfaits">
<div class="pub-section-entete"><span class="surtitre">Forfaits mensuels</span>
<h2 id="titre-forfaits">Un prix selon le nombre de dossiers actifs</h2>
<p>Chaque nouveau bureau démarre par une période d'essai de 30 jours.</p></div>
{_cartes_forfaits()}
</section>

<section class="pub-appel" aria-labelledby="titre-appel">
<div><h2 id="titre-appel">Créer mon bureau</h2>
<p>Vous devenez administrateur de votre bureau. L'essai de 30 jours commence tout de suite.</p></div>
<a class="btn btn-lg" href="/inscription">Commencer l'essai</a>
</section>
"""
    return _page(
        "Bienvenue - Agent Bureau d'Études",
        "Plateforme de gestion de dossiers pour bureaux d'études : Campus France et IRCC.",
        corps,
        courant="bienvenue",
    )


_SCRIPT_INSCRIPTION = """
<script>
(function(){
var form=document.getElementById('formulaire');
var zone=document.getElementById('retour');
var bouton=document.getElementById('envoyer');
function afficher(texte,type){zone.className='message '+type;zone.textContent=texte;
zone.hidden=false;zone.focus();}
document.getElementById('voir-cgu').addEventListener('toggle',function(e){
 var pre=document.getElementById('texte-cgu');
 if(e.target.open&&!pre.dataset.charge){
  fetch('/api/v1/inscription/cgu').then(function(r){return r.json();}).then(function(j){
   pre.textContent=j.texte_complet+'\\n\\n(Version '+j.version_cgu+')';pre.dataset.charge='1';
  }).catch(function(){pre.textContent='Impossible de charger les CGU pour le moment.';});
 }
});
form.addEventListener('submit',function(ev){
 ev.preventDefault();zone.hidden=true;
 var d=new FormData(form);
 var corps={nom_bureau:d.get('nom_bureau'),email_admin:d.get('email_admin'),
  nom_admin:d.get('nom_admin'),mot_de_passe:d.get('mot_de_passe'),
  accepte_cgu:form.elements.accepte_cgu.checked,forfait:d.get('forfait'),
  site_web:d.get('site_web')||''};
 bouton.disabled=true;
 fetch('/api/v1/inscription',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify(corps)}).then(function(r){
  return r.json().catch(function(){return {};}).then(function(j){return {s:r.status,j:j};});
 }).then(function(x){
  bouton.disabled=false;
  if(x.s===201){form.hidden=true;
   zone.className='message ok';zone.hidden=false;
   zone.textContent='';
   zone.appendChild(document.createTextNode((x.j.message||'Bureau créé.')+' '));
   var a=document.createElement('a');a.href='/';a.textContent='Aller à la connexion';
   zone.appendChild(a);zone.focus();return;}
  var m={403:'Les inscriptions sont fermées pour le moment.',
   409:(x.j.detail||'Impossible de créer le compte avec ces informations.'),
   429:'Trop de tentatives. Réessayez plus tard.'}[x.s];
  if(!m&&x.s===422){
   var champs=(x.j.champs||[]).map(function(c){return c.champ;}).join(' ');
   m=x.j.detail||'Données invalides.';
   if(champs.indexOf('accepte_cgu')>=0)m='Vous devez accepter les CGU.';
   else if(champs.indexOf('email_admin')>=0)m='Adresse e-mail invalide.';
   else if(!x.j.champs)m=x.j.detail;
  }
  afficher(m||'Une erreur est survenue. Réessayez.','erreur');
 }).catch(function(){bouton.disabled=false;
  afficher('Connexion au serveur impossible. Réessayez.','erreur');});
});
})();
</script>
"""


def _panneau_inscription() -> str:
    return f"""<div class="connexion-marque">
<div class="marque"><span class="marque-logo">{icone("dossier")}</span>
<span class="marque-nom">Agent Bureau d'Études<span class="marque-sous">Campus France · IRCC Canada · Algérie</span></span></div>
<p class="connexion-accroche">Un espace isolé pour les dossiers de votre bureau, prêt dès aujourd'hui.</p>
<ul class="connexion-arguments">
<li><span class="argument-icone">{icone("calendrier")}</span><div><strong>30 jours d'essai</strong><span>Chaque nouveau bureau démarre par une période d'essai de 30 jours.</span></div></li>
<li><span class="argument-icone">{icone("utilisateur")}</span><div><strong>Vous administrez le bureau</strong><span>Le compte créé ici devient l'administrateur de votre bureau.</span></div></li>
<li><span class="argument-icone">{icone("validation")}</span><div><strong>Rien n'est envoyé sans vous</strong><span>L'agent s'arrête avant toute soumission officielle et attend la validation d'un humain.</span></div></li>
</ul>
</div>"""


@routeur_public.get("/inscription", response_class=HTMLResponse)
def page_inscription() -> HTMLResponse:
    options = "".join(
        f'<option value="{escape(f.forfait.value)}">'
        f"{escape(f.libelle)} - {f.prix_mensuel_eur} EUR/mois</option>"
        for f in lister_catalogue_forfaits()
    )
    corps = f"""
<section class="connexion pub-inscription" aria-labelledby="titre-inscription">
<div class="connexion-form">
<div class="connexion-entete"><span class="surtitre">Essai de 30 jours</span>
<h1 id="titre-inscription">Créer mon bureau</h1>
<p>Vous deviendrez administrateur de votre bureau.</p></div>
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
<span id="aide-mdp" class="champ-aide">12 caractères minimum, avec au moins 3 types parmi :
minuscules, majuscules, chiffres, symboles.</span></label>
<label>Forfait
<select name="forfait">{options}</select></label>
<div class="piege" aria-hidden="true"><label>Site web
<input name="site_web" tabindex="-1" autocomplete="off"></label></div>
<details id="voir-cgu"><summary>Lire les Conditions Générales d'Utilisation</summary>
<pre class="cgu" id="texte-cgu">Chargement...</pre></details>
<label class="case"><input type="checkbox" name="accepte_cgu" required>
<span>J'ai lu et j'accepte les Conditions Générales d'Utilisation.</span></label>
<button class="btn btn-primaire btn-lg" id="envoyer" type="submit">Créer mon bureau</button>
</form>
<p class="connexion-pied">Déjà un compte ?&nbsp;<a href="/">Se connecter</a></p>
</div>
{_panneau_inscription()}
</section>
"""
    return _page(
        "Créer mon bureau - Agent Bureau d'Études",
        "Inscription d'une agence à la plateforme.",
        corps,
        _SCRIPT_INSCRIPTION,
    )


from app.api.pages_courriel import enregistrer_pages_courriel  # noqa: E402

enregistrer_pages_courriel(routeur_public, _page)
