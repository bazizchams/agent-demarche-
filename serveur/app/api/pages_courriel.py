"""Pages publiques minimales des parcours par courriel (sans session) :
`/mot-de-passe-oublie`, `/nouveau-mot-de-passe` et `/verification-adresse`.

Le jeton est lu dans le FRAGMENT de l'URL (`#jeton=...`) par JavaScript : il n'est donc jamais
envoyé au serveur dans l'URL (absent des journaux d'accès et des en-têtes Referer) et n'est
consommé que par un clic explicite de la personne (pas par un robot qui précharge le lien).
Le HTML autonome est fabriqué par la fonction `page` fournie par `routeur_public`.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

PageBuilder = Callable[..., HTMLResponse]

_JS_COMMUN = """
function jetonDuFragment(){var m=/[#&]jeton=([A-Za-z0-9_\\-]+)/.exec(location.hash);return m?m[1]:'';}
function afficher(zone,texte,type){zone.className='message '+type;zone.textContent=texte;
zone.hidden=false;zone.focus();}
function appeler(url,corps){return fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify(corps)}).then(function(r){return r.json().catch(function(){return {};})
.then(function(j){return {s:r.status,j:j};});});}
"""

_SCRIPT_OUBLI = "<script>" + _JS_COMMUN + """
(function(){
var f=document.getElementById('formulaire'),z=document.getElementById('retour'),
b=document.getElementById('envoyer');
f.addEventListener('submit',function(ev){ev.preventDefault();z.hidden=true;b.disabled=true;
appeler('/api/v1/auth/mot-de-passe-oublie',{email:f.elements.email.value}).then(function(x){
b.disabled=false;
if(x.s===202){afficher(z,x.j.message||'Demande enregistrée.','ok');}
else if(x.s===429){afficher(z,'Trop de demandes. Réessayez plus tard.','erreur');}
else{afficher(z,'Adresse e-mail invalide.','erreur');}
}).catch(function(){b.disabled=false;afficher(z,'Connexion au serveur impossible.','erreur');});});
})();
</script>"""

_SCRIPT_NOUVEAU = "<script>" + _JS_COMMUN + """
(function(){
var f=document.getElementById('formulaire'),z=document.getElementById('retour'),
b=document.getElementById('envoyer'),jeton=jetonDuFragment();
if(!jeton){afficher(z,'Lien incomplet : ouvrez le lien reçu par courriel.','erreur');b.disabled=true;}
f.addEventListener('submit',function(ev){ev.preventDefault();z.hidden=true;
var a=f.elements.nouveau.value;
if(a!==f.elements.confirmation.value){afficher(z,'Les deux mots de passe ne correspondent pas.','erreur');return;}
b.disabled=true;
appeler('/api/v1/auth/reinitialisation-mot-de-passe',{jeton:jeton,nouveau_mot_de_passe:a})
.then(function(x){
if(x.s===204){history.replaceState(null,'',location.pathname);f.hidden=true;
 z.className='message ok';z.hidden=false;z.textContent='Mot de passe modifié. Vous pouvez vous connecter. ';
 var l=document.createElement('a');l.href='/';l.textContent='Aller à la connexion';z.appendChild(l);z.focus();return;}
b.disabled=false;
afficher(z,(x.s===422&&x.j.detail)?x.j.detail:(x.s===429?'Trop de tentatives. Réessayez plus tard.':
 'Ce lien est invalide ou a expiré. Demandez-en un nouveau.'),'erreur');
}).catch(function(){b.disabled=false;afficher(z,'Connexion au serveur impossible.','erreur');});});
})();
</script>"""

_SCRIPT_VERIFICATION = "<script>" + _JS_COMMUN + """
(function(){
var z=document.getElementById('retour'),b=document.getElementById('envoyer'),jeton=jetonDuFragment();
if(!jeton){afficher(z,'Lien incomplet : ouvrez le lien reçu par courriel.','erreur');b.hidden=true;}
b.addEventListener('click',function(){z.hidden=true;b.disabled=true;
appeler('/api/v1/auth/verification-adresse',{jeton:jeton}).then(function(x){
if(x.s===204){history.replaceState(null,'',location.pathname);b.hidden=true;
 z.className='message ok';z.hidden=false;z.textContent='Adresse confirmée. Merci ! ';
 var l=document.createElement('a');l.href='/';l.textContent='Aller à la plateforme';z.appendChild(l);z.focus();return;}
b.disabled=false;
afficher(z,x.s===429?'Trop de tentatives. Réessayez plus tard.':
 'Ce lien est invalide ou a expiré. Connectez-vous pour en demander un nouveau.','erreur');
}).catch(function(){b.disabled=false;afficher(z,'Connexion au serveur impossible.','erreur');});});
})();
</script>"""

_CORPS_OUBLI = """
<h1>Mot de passe oublié</h1>
<p class="intro">Indiquez l'adresse e-mail de votre compte : si elle existe, vous recevrez un lien
valable une heure.</p>
<div id="retour" role="alert" tabindex="-1" hidden></div>
<form id="formulaire" novalidate>
<label>Adresse e-mail
<input name="email" type="email" required autocomplete="email"></label>
<button class="bouton" id="envoyer" type="submit">Envoyer le lien</button>
</form>
<p class="note"><a href="/">Retour à la connexion</a></p>
"""

_CORPS_NOUVEAU = """
<h1>Définir un nouveau mot de passe</h1>
<div id="retour" role="alert" tabindex="-1" hidden></div>
<form id="formulaire" novalidate>
<label>Nouveau mot de passe
<input name="nouveau" type="password" required minlength="12" autocomplete="new-password"
aria-describedby="aide-mdp"></label>
<label>Confirmer le mot de passe
<input name="confirmation" type="password" required autocomplete="new-password"></label>
<p id="aide-mdp" class="note">12 caractères minimum, avec au moins 3 types parmi :
minuscules, majuscules, chiffres, symboles. Toutes vos sessions ouvertes seront fermées.</p>
<button class="bouton" id="envoyer" type="submit">Enregistrer</button>
</form>
"""

_CORPS_VERIFICATION = """
<h1>Confirmer mon adresse e-mail</h1>
<p class="intro">Cliquez sur le bouton pour confirmer que cette adresse est bien la vôtre.</p>
<div id="retour" role="alert" tabindex="-1" hidden></div>
<p><button class="bouton" id="envoyer" type="button">Confirmer mon adresse</button></p>
"""


def enregistrer_pages_courriel(routeur: APIRouter, page: PageBuilder) -> None:
    @routeur.get("/mot-de-passe-oublie", response_class=HTMLResponse)
    def page_mot_de_passe_oublie() -> HTMLResponse:
        return page(
            "Mot de passe oublié - Agent Bureau d'Études",
            "Demande d'un lien de réinitialisation du mot de passe.",
            _CORPS_OUBLI, _SCRIPT_OUBLI,
        )

    @routeur.get("/nouveau-mot-de-passe", response_class=HTMLResponse)
    def page_nouveau_mot_de_passe() -> HTMLResponse:
        return page(
            "Nouveau mot de passe - Agent Bureau d'Études",
            "Définir un nouveau mot de passe.",
            _CORPS_NOUVEAU, _SCRIPT_NOUVEAU,
        )

    @routeur.get("/verification-adresse", response_class=HTMLResponse)
    def page_verification_adresse() -> HTMLResponse:
        return page(
            "Adresse e-mail - Agent Bureau d'Études",
            "Confirmation de l'adresse e-mail.",
            _CORPS_VERIFICATION, _SCRIPT_VERIFICATION,
        )
