"""Pages de DEMONSTRATION imitant les formulaires de connexion et d'inscription d'Etudes en France et de connexion
CleGC (GCKey) : TESTS UNIQUEMENT. Les libelles reprennent le releve du 2026-11-20 (config/portails/formulaires/).
Aucune donnee n'est envoyee nulle part : tout se passe dans la page. `window.__SOUMISSIONS__` journalise les
soumissions pour que les tests verifient qu'aucune inscription n'a ete envoyee. Variantes : `?captcha=1`, `?echec=1`,
`?connecte=1`.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

routeur_compte = APIRouter()

_STYLE = "<style>body{font-family:sans-serif;max-width:640px;margin:2rem auto}label{display:block;margin-top:.8rem}</style>"
_JOURNAL = "<script>window.__SOUMISSIONS__ = [];</script>"
_CAPTCHA = '<div class="g-recaptcha" data-sitekey="demo" style="border:1px solid #888;padding:1rem">Contrôle CAPTCHA (démo)</div>'
_CONNECTE = (
    '<div id="bandeau-identite-candidat"><p>Bienvenue sur votre espace (démo).</p>'
    '<button type="button">Se déconnecter</button></div>'
)


def _page(titre: str, corps: str) -> HTMLResponse:
    html = (
        f'<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><title>{titre}</title>{_STYLE}</head>'
        f"<body>{_JOURNAL}{corps}</body></html>"
    )
    return HTMLResponse(html, headers={"X-Frame-Options": "SAMEORIGIN"})


def _connexion(titre: str, libelle_id: str, captcha: int, echec: int, connecte: int) -> HTMLResponse:
    if connecte:
        return _page(titre, _CONNECTE)
    corps = f"""
<h1>{titre}</h1><p>Tous les champs sont obligatoires.</p>
{_CAPTCHA if captcha else ""}
<div id="zone-erreur" role="alert"></div>
<form id="f" autocomplete="off">
  <label for="i1">{libelle_id}</label><input id="i1" type="text">
  <label for="i2">Mot de passe</label><input id="i2" type="password">
  <label><input type="checkbox" aria-label="Afficher le mot de passe"> Afficher</label>
  <button type="submit">Se connecter</button>
</form>
<p><a href="/demo/eef-compte/mot-de-passe-oublie">Mot de passe oublié ?</a></p>
<script>
document.getElementById("f").addEventListener("submit", (e) => {{
  e.preventDefault();
  window.__SOUMISSIONS__.push("connexion");
  const echec = {echec};
  if (echec || !document.getElementById("i1").value || !document.getElementById("i2").value) {{
    document.getElementById("zone-erreur").textContent = "Identifiant ou mot de passe incorrect.";
    return;
  }}
  document.body.replaceChildren();
  document.body.insertAdjacentHTML("beforeend", {_CONNECTE!r});
}});
</script>"""
    return _page(titre, corps)


@routeur_compte.get("/eef-compte/connexion", response_class=HTMLResponse)
def connexion_eef(captcha: int = Query(0), echec: int = Query(0), connecte: int = Query(0)) -> HTMLResponse:
    return _connexion("Se connecter | Études en France", "Identifiant", captcha, echec, connecte)


@routeur_compte.get("/gckey/connexion", response_class=HTMLResponse)
def connexion_gckey(captcha: int = Query(0), echec: int = Query(0), connecte: int = Query(0)) -> HTMLResponse:
    return _connexion("CléGC (démo)", "Nom d'utilisateur", captcha, echec, connecte)


@routeur_compte.get("/eef-compte/inscription", response_class=HTMLResponse)
def inscription_eef(captcha: int = Query(0)) -> HTMLResponse:
    corps = f"""
<h1>Inscrivez-vous à Études en France</h1><p>Tous les champs dotés d'un * sont obligatoires.</p>
{_CAPTCHA if captcha else ""}
<form id="f" autocomplete="off">
  <label for="a1">Prénom*</label><input id="a1" type="text">
  <label for="a2">Nom*</label><input id="a2" type="text">
  <label for="a3">Espace Campus France de résidence*</label>
  <select id="a3"><option value="">Sélectionner une option</option>
    <option>Espace Campus France Algérie</option><option>Espace Campus France Tunisie</option></select>
  <label for="a4">Région de résidence*</label>
  <select id="a4"><option value="">Sélectionner une option</option></select>
  <label for="a5">Adresse mail*</label><input id="a5" type="text">
  <label for="a6">Mot de passe*</label><input id="a6" type="password">
  <label for="a7">Confirmer le mot de passe*</label><input id="a7" type="password">
  <p>Votre mot de passe doit contenir : 12 caractères minimum, 1 minuscule, 1 majuscule, 1 chiffre, 1 caractère spécial</p>
  <label><input type="checkbox" id="c1"> J'accepte que les informations saisies soient exploitées dans le cadre de la procédure de candidature aux études en France.*</label>
  <label><input type="checkbox" id="c2"> Je souhaite m'inscrire au réseau France Alumni. Les données suivantes seront transmises à France Alumni.</label>
  <button type="submit" id="envoi">S'inscrire</button>
</form>
<script>
document.getElementById("a3").addEventListener("change", (e) => {{
  const r = document.getElementById("a4");
  r.replaceChildren(new Option("Sélectionner une option", ""));
  if (e.target.value.endsWith("Algérie")) ["Alger", "Oran", "Constantine"].forEach((v) => r.add(new Option(v)));
}});
document.getElementById("f").addEventListener("submit", (e) => {{
  e.preventDefault();
  window.__SOUMISSIONS__.push("inscription");
}});
</script>"""
    return _page("S'inscrire | Études en France", corps)
