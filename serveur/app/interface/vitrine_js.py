"""Scripts de la vitrine publique : thème, défilement animé, pause, scène Three.js paresseuse.

JavaScript sobre : nœuds DOM et `textContent`, aucune insertion de HTML, aucun `eval`, aucun
`console.log`, aucun antislash dans ces chaînes. La page est complète sans ces scripts : ils
n'ajoutent que du confort (apparition au défilement, rail d'étapes, pause, profondeur du fond).
"""

from __future__ import annotations

# Three.js r128 (2021, bien au-delà du délai de prudence), version exacte épinglée sur cdnjs
# avec empreinte d'intégrité. Chargé seulement sur poste de bureau, sans demande de réduction
# des animations, avec WebGL disponible ; sinon le fond CSS reste en place.
URL_THREE = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"
INTEGRITE_THREE = "sha384-CI3ELBVUz9XQO+97x6nwMDPosPR5XvsxW2ua7N1Xeygeh1IxtgqtCkGfQY9WWdHu"

SCRIPT_THEME_INITIAL = """<script>
(function(){var r=document.documentElement;r.classList.add("js");
try{var c=localStorage.getItem("theme-interface");
if(c==="dark"||c==="light")r.setAttribute("data-theme",c);}catch(e){}})();
</script>"""

SCRIPT_THEME = """<script>
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

SCRIPT_VITRINE = """<script>
(function(){
var racine=document.documentElement;
var reduit=window.matchMedia("(prefers-reduced-motion: reduce)").matches;
var aObservateur="IntersectionObserver" in window;

/* Pause manuelle de toutes les animations de la page */
var pause=document.querySelector("[data-pause-anim]");
if(pause){pause.addEventListener("click",function(){
 var actif=racine.classList.toggle("anim-pause");
 pause.setAttribute("aria-pressed",actif?"true":"false");
 pause.textContent=actif?"Reprendre l'animation":"Mettre l'animation en pause";});}

/* Apparition au défilement : sans observateur ou en mouvement réduit, tout est visible */
var cibles=[].slice.call(document.querySelectorAll("[data-reveal]"));
if(!aObservateur||reduit){cibles.forEach(function(e){e.classList.add("vu");});}
else{
 var io=new IntersectionObserver(function(es){es.forEach(function(e){
  if(e.isIntersecting){e.target.classList.add("vu");io.unobserve(e.target);}});},
  {rootMargin:"0px 0px -8% 0px",threshold:0.12});
 cibles.forEach(function(e){io.observe(e);});
}

/* Démonstration du flux : en pause tant qu'elle n'est pas à l'écran */
var flux=document.querySelector("[data-flux]");
if(flux&&aObservateur){
 flux.classList.add("hors-ecran");
 new IntersectionObserver(function(es){es.forEach(function(e){
  flux.classList.toggle("hors-ecran",!e.isIntersecting);});},{threshold:0.2}).observe(flux);
}

/* Rail des étapes : étape active et progression */
var zone=document.querySelector("[data-etapes-zone]");
if(zone&&aObservateur){
 var liens=[].slice.call(zone.querySelectorAll("[data-rail] a"));
 var etapes=[].slice.call(zone.querySelectorAll("[data-etape]"));
 var obs=new IntersectionObserver(function(es){es.forEach(function(e){
  if(!e.isIntersecting)return;
  liens.forEach(function(a){a.classList.toggle("actif",a.getAttribute("href")==="#"+e.target.id);});});},
  {rootMargin:"-40% 0px -40% 0px",threshold:0});
 etapes.forEach(function(e){obs.observe(e);});
 if(!reduit){
  var attente=false;
  var progression=function(){attente=false;var r=zone.getBoundingClientRect();
   var p=(window.innerHeight*0.5-r.top)/Math.max(r.height,1);
   zone.style.setProperty("--p",String(Math.max(0,Math.min(1,p))));};
  window.addEventListener("scroll",function(){if(!attente){attente=true;requestAnimationFrame(progression);}},{passive:true});
  window.addEventListener("resize",progression);
  progression();
 }
}
})();
</script>"""

SCRIPT_SCENE = (
    """<script>
(function(){
var fond=document.querySelector("[data-scene]");
if(!fond||!window.matchMedia)return;
if(!window.matchMedia("(min-width: 960px) and (hover: hover) and (pointer: fine)").matches)return;
if(window.matchMedia("(prefers-reduced-motion: reduce)").matches)return;
var racine=document.documentElement;

function attendre(){
 if("requestIdleCallback" in window)requestIdleCallback(charger,{timeout:2500});
 else setTimeout(charger,1200);}
function charger(){
 var s=document.createElement("script");
 s.src=\""""
    + URL_THREE
    + """\";
 s.integrity=\""""
    + INTEGRITE_THREE
    + """\";
 s.crossOrigin="anonymous";s.async=true;
 s.onload=function(){try{demarrer();}catch(e){fond.classList.remove("pret");}};
 s.onerror=function(){};
 document.head.appendChild(s);}
if(document.readyState==="complete")attendre();else window.addEventListener("load",attendre);

function demarrer(){
 var T=window.THREE;if(!T)return;
 var rendu=new T.WebGLRenderer({antialias:true,alpha:true,powerPreference:"low-power"});
 rendu.setPixelRatio(Math.min(window.devicePixelRatio||1,1.5));
 var cv=rendu.domElement;cv.setAttribute("aria-hidden","true");fond.appendChild(cv);
 var scene=new T.Scene();
 var cam=new T.PerspectiveCamera(45,1,0.1,60);cam.position.set(0,0,14);
 function teinte(){var v=getComputedStyle(racine).getPropertyValue("--accent").trim();
  return new T.Color(v||"#3730a3");}
 var matFace=new T.MeshBasicMaterial({color:teinte(),transparent:true,opacity:0.07,side:T.DoubleSide,depthWrite:false});
 var matBord=new T.LineBasicMaterial({color:teinte(),transparent:true,opacity:0.3});
 var plan=new T.PlaneGeometry(1.6,2.1);
 var bords=new T.EdgesGeometry(plan);
 var traits=new T.BufferGeometry();
 var pts=[];[0.55,0.25,-0.05,-0.35,-0.65].forEach(function(y,i){
  var l=i===4?0.55:1.0;pts.push(-0.55,y,0.001,-0.55+l*1.1,y,0.001);});
 traits.setAttribute("position",new T.Float32BufferAttribute(pts,3));
 var feuilles=[];var graine=7;
 function hasard(){graine=(graine*16807)%2147483647;return (graine-1)/2147483646;}
 for(var i=0;i<18;i++){
  var g=new T.Group();
  g.add(new T.Mesh(plan,matFace));
  g.add(new T.LineSegments(bords,matBord));
  g.add(new T.LineSegments(traits,matBord));
  var echelle=0.7+hasard()*0.9;g.scale.set(echelle,echelle,echelle);
  var bx=(hasard()-0.1)*17,by=(hasard()-0.5)*9;
  g.position.set(bx,by,(hasard()-0.7)*9);
  g.rotation.set((hasard()-0.5)*0.5,(hasard()-0.5)*1.1,(hasard()-0.5)*0.6);
  scene.add(g);
  feuilles.push({g:g,by:by,ry:g.rotation.y,rz:g.rotation.z,ph:hasard()*6.28,v:0.25+hasard()*0.35});
 }
 var cible={x:0,y:0};
 window.addEventListener("pointermove",function(e){
  cible.x=(e.clientX/window.innerWidth-0.5)*2;cible.y=(e.clientY/window.innerHeight-0.5)*2;},{passive:true});
 function taille(){var r=fond.getBoundingClientRect();
  if(r.width<2||r.height<2)return;
  rendu.setSize(r.width,r.height,false);cam.aspect=r.width/r.height;cam.updateProjectionMatrix();}
 taille();
 if("ResizeObserver" in window)new ResizeObserver(taille).observe(fond);
 var visible=true,raf=0,premier=true;
 function dessiner(ms){
  var t=ms/1000;
  feuilles.forEach(function(f){
   f.g.position.y=f.by+Math.sin(t*f.v+f.ph)*0.4;
   f.g.rotation.y=f.ry+Math.sin(t*0.3+f.ph)*0.22;
   f.g.rotation.z=f.rz+Math.sin(t*0.2+f.ph)*0.06;});
  cam.position.x+=(cible.x*1.1-cam.position.x)*0.04;
  cam.position.y+=(-cible.y*0.6-cam.position.y)*0.04;
  cam.lookAt(0,0,0);
  rendu.render(scene,cam);
  if(premier){premier=false;fond.classList.add("pret");}
  raf=requestAnimationFrame(dessiner);}
 function maj(){
  var doit=visible&&!document.hidden&&!racine.classList.contains("anim-pause");
  if(doit&&!raf)raf=requestAnimationFrame(dessiner);
  if(!doit&&raf){cancelAnimationFrame(raf);raf=0;}}
 function recolorer(){matFace.color=teinte();matBord.color=teinte();}
 if("IntersectionObserver" in window)new IntersectionObserver(function(es){
  visible=es[0].isIntersecting;maj();}).observe(fond);
 document.addEventListener("visibilitychange",maj);
 new MutationObserver(function(){recolorer();maj();}).observe(racine,{attributes:true,attributeFilter:["class","data-theme"]});
 window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change",recolorer);
 cv.addEventListener("webglcontextlost",function(e){e.preventDefault();
  if(raf){cancelAnimationFrame(raf);raf=0;}fond.classList.remove("pret");});
 window.addEventListener("pagehide",function(){
  if(raf)cancelAnimationFrame(raf);
  plan.dispose();bords.dispose();traits.dispose();matFace.dispose();matBord.dispose();rendu.dispose();});
 maj();
}
})();
</script>"""
)

SCRIPT_INSCRIPTION = """
<script>
(function(){
var form=document.getElementById('formulaire');
var zone=document.getElementById('retour');
var bouton=document.getElementById('envoyer');
var choix=form.elements.forfait;
var info=document.getElementById('info-forfait');
function afficher(texte,type){zone.className='message '+type;zone.textContent=texte;
zone.hidden=false;zone.focus();}
function majForfait(){var o=choix.options[choix.selectedIndex];
 if(o&&info&&o.dataset.quota){info.textContent="Jusqu'à "+o.dataset.quota+" dossiers actifs par mois, après 30 jours d'essai.";}}
try{var voulu=new URLSearchParams(location.search).get('forfait');
 if(voulu){for(var i=0;i<choix.options.length;i++){if(choix.options[i].value===voulu){choix.selectedIndex=i;}}}}catch(e){}
choix.addEventListener('change',majForfait);majForfait();
document.getElementById('voir-cgu').addEventListener('toggle',function(e){
 var pre=document.getElementById('texte-cgu');
 if(e.target.open&&!pre.dataset.charge){
  fetch('/api/v1/inscription/cgu').then(function(r){return r.json();}).then(function(j){
   pre.textContent=j.texte_complet+String.fromCharCode(10,10)+'(Version '+j.version_cgu+')';pre.dataset.charge='1';
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
  var champEnCause=null;
  var m={403:'Les inscriptions sont fermées pour le moment.',
   409:(x.j.detail||'Impossible de créer le compte avec ces informations.'),
   429:'Trop de tentatives. Réessayez plus tard.'}[x.s];
  if(!m&&x.s===422){
   var MSG={nom_bureau:'Nom du bureau : 2 à 120 caractères attendus.',
    nom_admin:'Votre nom : champ obligatoire, 120 caractères au maximum.',
    email_admin:'Adresse e-mail : format invalide (exemple : prenom.nom@votre-bureau.dz).',
    mot_de_passe:'Mot de passe : 12 caractères minimum, avec au moins 3 types parmi minuscules, majuscules, chiffres, symboles.',
    forfait:'Forfait : choisissez un forfait de la liste.',
    accepte_cgu:'Vous devez accepter les CGU.'};
   var noms=(x.j.champs||[]).map(function(c){return String(c.champ||'').split('.').pop();});
   var fautif=Object.keys(MSG).filter(function(k){return noms.indexOf(k)>=0;})[0];
   if(fautif){m=MSG[fautif];
    champEnCause=form.elements[fautif];}
   else m=x.j.detail||'Données invalides : vérifiez les champs du formulaire.';
  }
  afficher(m||'Une erreur est survenue. Réessayez.','erreur');
  if(champEnCause&&champEnCause.focus)champEnCause.focus();
 }).catch(function(){bouton.disabled=false;
  afficher('Connexion au serveur impossible. Réessayez.','erreur');});
});
})();
</script>
"""
