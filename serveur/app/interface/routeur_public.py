"""Pages publiques (sans session) : page de vente `/bienvenue` et formulaire `/inscription`.
HTML autonome, sans dépendance externe. Les forfaits sont lus dans le catalogue existant."""

from __future__ import annotations

from html import escape

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.services.abonnements import lister_catalogue_forfaits

routeur_public = APIRouter(include_in_schema=False)

_STYLE = """
:root{color-scheme:light dark;--fond:#f7f8fa;--carte:#fff;--texte:#1b2430;--doux:#566274;
--accent:#0b5cad;--accent-texte:#fff;--bord:#d5dae1;--erreur:#b3261e;--ok:#1b6e3a}
@media (prefers-color-scheme:dark){:root{--fond:#12161c;--carte:#1a2029;--texte:#e8ecf2;
--doux:#a3adbb;--accent:#6ab0f3;--accent-texte:#0b1522;--bord:#323c4a;--erreur:#ff8a80;--ok:#7fd99a}}
*{box-sizing:border-box}
[hidden]{display:none!important}
body{margin:0;font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
background:var(--fond);color:var(--texte)}
a{color:var(--accent)}
.page{max-width:60rem;margin:0 auto;padding:0 1rem 3rem}
header.haut{display:flex;justify-content:space-between;align-items:center;gap:1rem;
flex-wrap:wrap;padding:1rem 0}
header.haut strong{font-size:1.1rem}
h1{font-size:clamp(1.7rem,4vw,2.5rem);line-height:1.2;margin:1.5rem 0 .75rem}
h2{font-size:1.4rem;margin:2.5rem 0 .75rem}
p.intro{font-size:1.1rem;color:var(--doux);max-width:42rem}
.bouton{display:inline-block;background:var(--accent);color:var(--accent-texte);
padding:.75rem 1.4rem;border-radius:.5rem;text-decoration:none;font-weight:600;border:0;
font:inherit;font-weight:600;cursor:pointer;transition:filter .15s ease}
.bouton:hover{filter:brightness(1.08)}
.bouton:disabled{opacity:.6;cursor:not-allowed}
:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
.grille{display:grid;gap:1rem;grid-template-columns:repeat(auto-fit,minmax(15rem,1fr));
padding:0;list-style:none;margin:0}
.carte{background:var(--carte);border:1px solid var(--bord);border-radius:.6rem;padding:1rem 1.1rem}
.carte h3{margin:.1rem 0 .4rem;font-size:1.05rem}
.carte p{margin:0;color:var(--doux)}
.prix{font-size:1.8rem;font-weight:700;margin:.3rem 0}
.note{color:var(--doux);font-size:.92rem}
form{background:var(--carte);border:1px solid var(--bord);border-radius:.6rem;
padding:1.2rem;display:grid;gap:1rem;max-width:34rem}
label{display:grid;gap:.3rem;font-weight:600}
input,select{font:inherit;padding:.6rem;border:1px solid var(--bord);border-radius:.4rem;
background:var(--fond);color:var(--texte)}
label.case{display:flex;gap:.6rem;align-items:flex-start;font-weight:400}
label.case input{margin-top:.35rem}
.piege{position:absolute;left:-10000px;width:1px;height:1px;overflow:hidden}
.message{padding:.8rem 1rem;border-radius:.5rem;border:1px solid var(--bord)}
.message.erreur{border-color:var(--erreur);color:var(--erreur)}
.message.ok{border-color:var(--ok);color:var(--ok)}
details{margin:.2rem 0}
pre.cgu{white-space:pre-wrap;font:inherit;max-height:18rem;overflow:auto;
border:1px solid var(--bord);border-radius:.4rem;padding:.8rem;background:var(--fond)}
footer{margin-top:3rem;color:var(--doux);font-size:.9rem}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important;
scroll-behavior:auto!important}}
"""


def _page(titre: str, description: str, corps: str, script: str = "") -> HTMLResponse:
    html = f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(titre)}</title>
<meta name="description" content="{escape(description)}">
<style>{_STYLE}</style>
</head>
<body>
<div class="page">
<header class="haut">
<strong>Agent Bureau d'Études</strong>
<nav aria-label="Navigation principale"><a href="/bienvenue">Présentation</a> &middot;
<a href="/inscription">Créer mon bureau</a> &middot; <a href="/">Connexion</a></nav>
</header>
<main id="contenu">
{corps}
</main>
<footer>Plateforme destinée aux bureaux d'études et d'accompagnement. Aucun résultat de
démarche n'est garanti : les décisions appartiennent aux autorités compétentes.</footer>
</div>
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
            f'<p class="prix">{f.prix_mensuel_eur}&nbsp;&euro;<span class="note"> / mois</span></p>'
            f"<p>Jusqu'à {f.quota_dossiers_mensuels} dossiers actifs par mois.</p>"
            "</li>"
        )
    return '<ul class="grille">' + "".join(morceaux) + "</ul>"


@routeur_public.get("/bienvenue", response_class=HTMLResponse)
def page_bienvenue() -> HTMLResponse:
    corps = f"""
<h1>Gérez vos dossiers d'études à l'étranger, avec un co-pilote qui s'arrête avant l'envoi</h1>
<p class="intro">Pour les bureaux d'études et d'accompagnement qui préparent des dossiers
Campus France (Études en France) et IRCC (permis d'études au Canada).</p>
<p><a class="bouton" href="/inscription">Créer mon bureau</a></p>

<h2>À qui ça s'adresse</h2>
<p>Aux agences et bureaux d'accompagnement, de la petite structure à l'équipe de plusieurs
conseillers, qui veulent suivre leurs candidats, leurs pièces et leurs démarches au même endroit.</p>

<h2>Ce que fait la plateforme</h2>
<ul class="grille">
<li class="carte"><h3>Dossiers chiffrés par bureau</h3><p>Les données et documents de chaque
candidat sont chiffrés, et chaque bureau ne voit que ses propres dossiers.</p></li>
<li class="carte"><h3>Procédures personnalisables</h3><p>Les démarches sont décrites dans des
fichiers de configuration : vous les adaptez sans redéployer la plateforme.</p></li>
<li class="carte"><h3>Co-pilote navigateur</h3><p>Il pré-remplit les formulaires des portails
officiels, s'arrête avant toute soumission officielle et attend la validation d'un humain.
CAPTCHA et double authentification restent entre vos mains.</p></li>
<li class="carte"><h3>Assistant IA sans donnée personnelle</h3><p>L'assistant vous aide à
organiser le travail sans recevoir de nom, d'e-mail ni de numéro de passeport.</p></li>
<li class="carte"><h3>Conformité</h3><p>Conçue pour accompagner le respect de la loi
algérienne n° 18-07 et du RGPD : consentement explicite du candidat, journal d'audit sans
donnée personnelle, suppression à la demande.</p></li>
</ul>

<h2>Forfaits</h2>
{_cartes_forfaits()}
<p class="note">Chaque nouveau bureau démarre par une période d'essai de 30 jours.</p>
<p><a class="bouton" href="/inscription">Créer mon bureau</a></p>
"""
    return _page(
        "Bienvenue - Agent Bureau d'Études",
        "Plateforme de gestion de dossiers pour bureaux d'études : Campus France et IRCC.",
        corps,
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
   zone.innerHTML='';
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


@routeur_public.get("/inscription", response_class=HTMLResponse)
def page_inscription() -> HTMLResponse:
    options = "".join(
        f'<option value="{escape(f.forfait.value)}">'
        f"{escape(f.libelle)} - {f.prix_mensuel_eur} EUR/mois</option>"
        for f in lister_catalogue_forfaits()
    )
    corps = f"""
<h1>Créer mon bureau</h1>
<p class="intro">Essai de 30 jours. Vous deviendrez administrateur de votre bureau.</p>
<div id="retour" role="alert" tabindex="-1" hidden></div>
<form id="formulaire" novalidate>
<label>Nom du bureau
<input name="nom_bureau" required minlength="2" maxlength="120" autocomplete="organization"></label>
<label>Votre nom
<input name="nom_admin" required maxlength="120" autocomplete="name"></label>
<label>Adresse e-mail
<input name="email_admin" type="email" required autocomplete="email"></label>
<label>Mot de passe
<input name="mot_de_passe" type="password" required minlength="12" autocomplete="new-password"
aria-describedby="aide-mdp"></label>
<p id="aide-mdp" class="note">12 caractères minimum, avec au moins 3 types parmi :
minuscules, majuscules, chiffres, symboles.</p>
<label>Forfait
<select name="forfait">{options}</select></label>
<div class="piege" aria-hidden="true"><label>Site web
<input name="site_web" tabindex="-1" autocomplete="off"></label></div>
<details id="voir-cgu"><summary>Lire les Conditions Générales d'Utilisation</summary>
<pre class="cgu" id="texte-cgu">Chargement...</pre></details>
<label class="case"><input type="checkbox" name="accepte_cgu" required>
<span>J'ai lu et j'accepte les Conditions Générales d'Utilisation.</span></label>
<button class="bouton" id="envoyer" type="submit">Créer mon bureau</button>
</form>
<p class="note">Déjà un compte ? <a href="/">Se connecter</a></p>
"""
    return _page(
        "Créer mon bureau - Agent Bureau d'Études",
        "Inscription d'une agence à la plateforme.",
        corps,
        _SCRIPT_INSCRIPTION,
    )
