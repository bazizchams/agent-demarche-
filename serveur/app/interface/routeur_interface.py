"""Routeur servant l'interface web complète en français de la plateforme :
1. Tableau de bord
2. Étudiants & Fiche candidat
3. Documents & Pièces requises (affichage en français clair sans code technique)
4. Discussion & Score d'acceptation (évaluation détaillée en texte lisible + Assistant Conseiller fonctionnel)
5. Campus France (Études en France — Guide officiel Septembre 2026 Algérie + Agent Navigateur Playwright)
6. IRCC Canada (Permis d'études + Agent Navigateur Playwright)
7. Centre de validation humaine (Règle 1 — cartes interactives + aperçu de la capture de contrôle)
8. Historique & Erreurs (Audit sans donnée personnelle — Règle 5)
9. Paramètres & Sauvegardes (Agents locaux, sauvegardes chiffrées, abonnement et statut des portails)
10. Procédures (démarches) : ajout et modification par le bureau, sans redéploiement
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.interface.ecran_navigateur_serveur import assembler_navigateur_serveur
from app.interface.ecrans_coffre_validation import assembler_interface

routeur_interface = APIRouter(tags=["interface web en français"])

_HTML_INTERFACE_BASE = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Plateforme Agent Bureau d'Études — Algérie (Campus France Septembre 2026 &amp; IRCC)</title>
  <style>
    :root {
      --bleu-nuit: #0f172a;
      --bleu-primaire: #1d4ed8;
      --bleu-clair: #eff6ff;
      --vert-succes: #15803d;
      --vert-clair: #dcfce7;
      --orange-alerte: #b45309;
      --orange-clair: #fef3c7;
      --rouge-danger: #b91c1c;
      --rouge-clair: #fee2e2;
      --fond: #f1f5f9;
      --carte: #ffffff;
      --bordure: #cbd5e1;
      --texte: #0f172a;
      --texte-secondaire: #475569;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: Segoe UI, system-ui, -apple-system, sans-serif; background: var(--fond); color: var(--texte); display: flex; min-height: 100vh; }
    aside { width: 285px; background: var(--bleu-nuit); color: #fff; padding: 20px 14px; display: flex; flex-direction: column; gap: 6px; flex-shrink: 0; }
    aside h1 { font-size: 1.08rem; margin: 0 0 12px 8px; color: #93c5fd; }
    aside button.nav-btn { background: transparent; color: #e2e8f0; border: none; text-align: left; padding: 10px 12px; border-radius: 6px; cursor: pointer; font-size: 0.9rem; font-weight: 500; transition: background 0.15s; }
    aside button.nav-btn.actif, aside button.nav-btn:hover { background: #1e293b; color: #fff; }
    main { flex: 1; padding: 22px 30px; overflow-y: auto; max-width: 1400px; }
    .carte { background: var(--carte); border: 1px solid var(--bordure); border-radius: 10px; padding: 18px 22px; margin-bottom: 18px; box-shadow: 0 1px 2px rgba(0,0,0,0.03); }
    .grille-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 18px; }
    .stat { background: var(--carte); border: 1px solid var(--bordure); border-radius: 8px; padding: 14px 16px; }
    .stat .valeur { font-size: 1.7rem; font-weight: 700; color: var(--bleu-primaire); }
    .stat .libelle { font-size: 0.85rem; color: var(--texte-secondaire); }
    .cache { display: none !important; }
    .grille-form { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
    .grille-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px; }
    label { display: flex; flex-direction: column; gap: 4px; font-size: 0.86rem; font-weight: 600; }
    input, select, textarea { padding: 8px 10px; border: 1px solid var(--bordure); border-radius: 6px; font-size: 0.92rem; font-family: inherit; }
    button.btn { background: var(--bleu-primaire); color: #fff; border: none; padding: 9px 15px; border-radius: 6px; cursor: pointer; font-weight: 600; margin-right: 6px; margin-bottom: 6px; font-size: 0.88rem; }
    button.btn:hover { opacity: 0.93; }
    button.btn-succes { background: var(--vert-succes); }
    button.btn-danger { background: var(--rouge-danger); }
    button.btn-secondaire { background: #475569; }
    button.btn-contour { background: #f8fafc; color: #1e293b; border: 1px solid var(--bordure); }
    table { width: 100%; border-collapse: collapse; font-size: 0.9rem; margin-top: 10px; }
    th, td { border-bottom: 1px solid var(--bordure); padding: 9px 10px; text-align: left; vertical-align: top; }
    th { background: #f8fafc; font-weight: 700; color: #334155; }
    .badge { display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 0.78rem; font-weight: 700; background: #e2e8f0; color: #1e293b; }
    .badge-ok { background: var(--vert-clair); color: #166534; }
    .badge-warn { background: var(--orange-clair); color: #92400e; }
    .badge-err { background: var(--rouge-clair); color: #991b1b; }
    .banniere-regle { background: var(--bleu-clair); border-left: 4px solid var(--bleu-primaire); padding: 11px 15px; font-size: 0.89rem; margin-bottom: 14px; border-radius: 4px; }
    .notif { padding: 11px 15px; border-radius: 6px; margin-bottom: 14px; font-weight: 600; font-size: 0.9rem; }
    .notif-ok { background: var(--vert-clair); color: #166534; border: 1px solid #86efac; }
    .notif-err { background: var(--rouge-clair); color: #991b1b; border: 1px solid #fca5a5; }
    .panneau-texte { background: #f8fafc; border: 1px solid var(--bordure); border-radius: 8px; padding: 16px 18px; font-size: 0.92rem; line-height: 1.55; }
    .fil-discussion { max-height: 380px; overflow-y: auto; border: 1px solid var(--bordure); border-radius: 8px; padding: 14px; background: #f8fafc; margin-bottom: 12px; }
    .msg { padding: 12px 14px; border-radius: 8px; margin-bottom: 10px; font-size: 0.91rem; line-height: 1.5; }
    .msg-op { background: #dbeafe; margin-left: 12%; border: 1px solid #93c5fd; }
    .msg-ia { background: #ffffff; border: 1px solid var(--bordure); margin-right: 6%; }
    .barre-progression { width: 100%; height: 14px; background: #e2e8f0; border-radius: 999px; overflow: hidden; margin: 8px 0; }
    .barre-progression-remplie { height: 100%; background: var(--bleu-primaire); transition: width 0.3s; }
    .liste-propre { margin: 6px 0 12px 0; padding-left: 20px; }
    .liste-propre li { margin-bottom: 5px; }
    .capture-apercu { max-width: 100%; border: 2px solid var(--bordure); border-radius: 8px; margin-top: 10px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }
    details.guide-bloc { border: 1px solid var(--bordure); border-radius: 8px; padding: 10px 14px; margin-bottom: 10px; background: #f8fafc; }
    details.guide-bloc summary { font-weight: 700; cursor: pointer; color: #1e3a8a; font-size: 0.95rem; }
    .workspace-cowork { display: grid; grid-template-columns: 1.15fr 0.95fr; gap: 16px; align-items: start; margin-top: 12px; }
    @media (max-width: 1100px) { .workspace-cowork { grid-template-columns: 1fr; } }
    .cadre-navigateur-direct { border: 2px solid #3b82f6; border-radius: 12px; background: #0f172a; overflow: hidden; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12); }
    .barre-chrome-direct { background: #1e293b; color: #f8fafc; padding: 8px 12px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; border-bottom: 1px solid #334155; }
    .barre-chrome-direct button.btn-nav-mini { background: #334155; color: #f8fafc; border: 1px solid #475569; border-radius: 6px; padding: 5px 9px; cursor: pointer; font-size: 0.82rem; font-weight: 600; }
    .barre-chrome-direct button.btn-nav-mini:hover { background: #2563eb; border-color: #60a5fa; }
    .url-live-input { flex: 1; min-width: 180px; background: #0f172a; color: #93c5fd; border: 1px solid #475569; border-radius: 6px; padding: 6px 10px; font-size: 0.84rem; font-family: Consolas, monospace; }
    .corps-navigateur-direct { background: #ffffff; color: #0f172a; min-height: 460px; max-height: 620px; overflow-y: auto; padding: 14px; }
    .iframe-navigateur-direct { width: 100%; height: 540px; border: none; background: #ffffff; display: block; }
    .panneau-copilote-chat { border: 2px solid #cbd5e1; border-radius: 12px; background: #ffffff; padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; }
    .fil-copilote { max-height: 340px; min-height: 180px; overflow-y: auto; background: #f8fafc; border: 1px solid var(--bordure); border-radius: 8px; padding: 12px; display: flex; flex-direction: column; gap: 8px; }
    .bulle-copilote-user { align-self: flex-end; background: #dbeafe; color: #1e3a8a; border: 1px solid #93c5fd; padding: 8px 12px; border-radius: 10px 10px 2px 10px; font-size: 0.88rem; max-width: 88%; }
    .bulle-copilote-ia { align-self: flex-start; background: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; border-left: 4px solid #2563eb; padding: 10px 12px; border-radius: 2px 10px 10px 10px; font-size: 0.88rem; max-width: 95%; line-height: 1.5; }
    .grille-dom-live { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px; margin-top: 8px; }
    .carte-dom-item { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 7px; padding: 8px 10px; font-size: 0.82rem; display: flex; flex-direction: column; gap: 5px; }
    .puce-cmd { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; border-radius: 999px; padding: 4px 10px; font-size: 0.79rem; font-weight: 600; cursor: pointer; display: inline-block; margin: 2px 3px 2px 0; }
    .puce-cmd:hover { background: #dbeafe; }
    .point-vert-pulsant { display: inline-block; width: 9px; height: 9px; border-radius: 50%; background: #22c55e; box-shadow: 0 0 8px #22c55e; margin-right: 5px; }

    /* ===================================================================
       Couche design « Apple » (skill apple-design) :
       réponse instantanée, matériaux translucides, typographie à pistage
       adaptatif, mouvement amorti sans rebond, respect de reduced-motion,
       reduced-transparency et prefers-contrast. Pas d'antislash ici.
       =================================================================== */
    :root {
      color-scheme: light dark;
      --fond: #f5f5f7;
      --carte: #ffffff;
      --surface-2: #f5f5f7;
      --bordure: rgba(60, 60, 67, 0.18);
      --texte: #1d1d1f;
      --texte-secondaire: #6e6e73;
      --bleu-primaire: #0071e3;
      --bleu-clair: #eaf3fe;
      --vert-succes: #248a3d;
      --vert-clair: #e3f5e8;
      --orange-clair: #fff4e0;
      --rouge-danger: #d70015;
      --rouge-clair: #ffe9eb;
      --rayon: 14px;
      --amorti: cubic-bezier(0.22, 1, 0.36, 1);
      --ombre-carte: 0 1px 2px rgba(0, 0, 0, 0.04), 0 8px 24px rgba(0, 0, 0, 0.05);
      --matiere: rgba(255, 255, 255, 0.72);
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --fond: #000000;
        --carte: #1c1c1e;
        --surface-2: #2c2c2e;
        --bordure: rgba(235, 235, 245, 0.18);
        --texte: #f5f5f7;
        --texte-secondaire: #a1a1a6;
        --bleu-primaire: #0a84ff;
        --bleu-clair: rgba(10, 132, 255, 0.16);
        --vert-succes: #30d158;
        --vert-clair: rgba(48, 209, 88, 0.16);
        --orange-clair: rgba(255, 159, 10, 0.16);
        --rouge-danger: #ff453a;
        --rouge-clair: rgba(255, 69, 58, 0.16);
        --ombre-carte: 0 1px 2px rgba(0, 0, 0, 0.4), 0 8px 24px rgba(0, 0, 0, 0.35);
        --matiere: rgba(44, 44, 46, 0.72);
      }
    }
    html { -webkit-text-size-adjust: 100%; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif;
      font-size: 100%;
      line-height: 1.5;
      -webkit-font-smoothing: antialiased;
      font-optical-sizing: auto;
      -webkit-tap-highlight-color: transparent;
    }
    h2 { font-size: 1.85rem; line-height: 1.1; letter-spacing: -0.024em; font-weight: 700; margin: 4px 0 16px; }
    h3 { font-size: 1.2rem; line-height: 1.2; letter-spacing: -0.014em; font-weight: 650; margin: 0 0 10px; }
    h4 { font-size: 1rem; line-height: 1.3; letter-spacing: -0.006em; font-weight: 650; margin: 18px 0 8px; }
    small, .libelle, th, label { letter-spacing: 0.004em; }

    /* Navigation : matière sombre translucide, structure du site */
    aside {
      position: sticky; top: 0; align-self: flex-start; height: 100vh; overflow-y: auto;
      width: 280px; padding: 22px 12px;
      background: rgba(28, 28, 30, 0.86);
      -webkit-backdrop-filter: blur(24px) saturate(180%);
      backdrop-filter: blur(24px) saturate(180%);
      border-right: 1px solid rgba(255, 255, 255, 0.08);
    }
    aside h1 { font-size: 1.05rem; letter-spacing: -0.012em; font-weight: 700; color: #f5f5f7; margin: 0 0 16px 10px; }
    aside button.nav-btn {
      color: rgba(245, 245, 247, 0.82); padding: 10px 12px; border-radius: 10px; font-size: 0.92rem; font-weight: 500;
      letter-spacing: 0; line-height: 1.3;
      transition: background-color 160ms var(--amorti), color 160ms var(--amorti), transform 90ms var(--amorti);
    }
    aside button.nav-btn:hover { background: rgba(255, 255, 255, 0.08); color: #fff; }
    aside button.nav-btn.actif { background: rgba(255, 255, 255, 0.16); color: #fff; font-weight: 600; }
    aside button.nav-btn:active { transform: scale(0.98); transition-duration: 40ms; }

    main { overflow: visible; padding: 20px 40px 64px; max-width: 1360px; min-width: 0; }

    /* Barre d'état flottante : le contenu défile dessous (pas de trait dur) */
    #banniere-etat {
      position: sticky; top: 12px; z-index: 20; margin: 0 0 18px;
      background: var(--matiere);
      -webkit-backdrop-filter: blur(20px) saturate(180%);
      backdrop-filter: blur(20px) saturate(180%);
      border: 1px solid var(--bordure); border-top-color: rgba(255, 255, 255, 0.5);
      border-radius: var(--rayon); box-shadow: var(--ombre-carte);
      font-size: 0.86rem; color: var(--texte-secondaire);
    }
    #banniere-etat strong { color: var(--texte); }
    .banniere-regle { background: var(--bleu-clair); border: 1px solid rgba(0, 113, 227, 0.2); border-left-width: 1px; border-radius: 12px; padding: 12px 16px; color: var(--texte); line-height: 1.5; }

    /* Surfaces */
    .carte, .stat, .panneau-copilote-chat {
      background: var(--carte); border: 1px solid var(--bordure); border-radius: var(--rayon);
      box-shadow: var(--ombre-carte);
    }
    .carte { padding: 20px 24px; margin-bottom: 20px; }
    .stat { padding: 16px 18px; }
    .stat .valeur { font-size: 2.1rem; line-height: 1.1; letter-spacing: -0.03em; font-weight: 700; color: var(--bleu-primaire); }
    .stat .libelle { font-size: 0.84rem; color: var(--texte-secondaire); margin-top: 4px; line-height: 1.35; }
    .panneau-texte, .fil-discussion, .fil-copilote, details.guide-bloc, .carte-dom-item {
      background: var(--surface-2); border: 1px solid var(--bordure); border-radius: 12px; color: var(--texte);
    }
    details.guide-bloc summary { color: var(--bleu-primaire); letter-spacing: -0.006em; }

    /* Formulaires : retour immédiat au focus */
    input, select, textarea {
      padding: 9px 12px; border: 1px solid var(--bordure); border-radius: 10px; font-size: 0.94rem;
      background: var(--carte); color: var(--texte);
      transition: border-color 140ms var(--amorti), box-shadow 140ms var(--amorti);
    }
    input:focus, select:focus, textarea:focus { outline: none; border-color: var(--bleu-primaire); box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.22); }
    input:disabled, select:disabled, textarea:disabled { opacity: 0.6; }
    label { font-size: 0.84rem; font-weight: 600; color: var(--texte); gap: 6px; }

    /* Boutons : la réponse commence à l'appui (pointerdown), pas au relâchement */
    button.btn {
      background: var(--bleu-primaire); color: #fff; border: 1px solid transparent; border-radius: 10px;
      padding: 9px 16px; font-size: 0.9rem; font-weight: 600; letter-spacing: -0.003em;
      touch-action: manipulation;
      transition: transform 120ms var(--amorti), filter 140ms var(--amorti), background-color 140ms var(--amorti);
    }
    button.btn:hover { opacity: 1; filter: brightness(1.08); }
    button.btn:active { transform: scale(0.97); filter: brightness(0.94); transition-duration: 50ms; }
    button.btn-succes { background: var(--vert-succes); }
    button.btn-danger { background: var(--rouge-danger); }
    button.btn-secondaire { background: rgba(120, 120, 128, 0.16); color: var(--texte); }
    button.btn-contour { background: transparent; color: var(--bleu-primaire); border: 1px solid var(--bordure); }
    button:focus-visible, .nav-btn:focus-visible, .puce-cmd:focus-visible, summary:focus-visible {
      outline: 3px solid rgba(0, 113, 227, 0.5); outline-offset: 2px;
    }

    /* Tableaux : hiérarchie par l'espacement et le contraste */
    table { font-size: 0.92rem; }
    th { background: transparent; color: var(--texte-secondaire); font-size: 0.74rem; font-weight: 650; text-transform: uppercase; letter-spacing: 0.05em; }
    th, td { border-bottom: 1px solid var(--bordure); padding: 11px 12px; }
    tbody tr { transition: background-color 120ms var(--amorti); }
    tbody tr:hover { background: var(--surface-2); }

    .badge { background: rgba(120, 120, 128, 0.16); color: var(--texte); font-weight: 650; letter-spacing: 0.01em; }
    .badge-ok { background: var(--vert-clair); color: var(--vert-succes); }
    .badge-warn { background: var(--orange-clair); color: var(--orange-alerte); }
    .badge-err { background: var(--rouge-clair); color: var(--rouge-danger); }

    /* Notifications : matière flottante qui se matérialise (flou + échelle) */
    .notif {
      position: fixed; top: 20px; right: 24px; z-index: 60; margin: 0;
      max-width: min(440px, calc(100vw - 48px)); padding: 12px 16px; border-radius: 14px;
      background: var(--matiere);
      -webkit-backdrop-filter: blur(24px) saturate(180%);
      backdrop-filter: blur(24px) saturate(180%);
      box-shadow: 0 12px 40px rgba(0, 0, 0, 0.18);
      font-weight: 600; line-height: 1.4; letter-spacing: 0.002em;
      animation: materialiser 420ms var(--amorti) both;
    }
    .notif-ok { color: var(--vert-succes); border: 1px solid rgba(36, 138, 61, 0.35); }
    .notif-err { color: var(--rouge-danger); border: 1px solid rgba(215, 0, 21, 0.35); }
    @keyframes materialiser {
      from { opacity: 0; transform: translateY(-10px) scale(0.96); filter: blur(8px); }
      to { opacity: 1; transform: none; filter: none; }
    }

    /* Changement d'écran : l'écran arrive depuis le bas, sans rebond */
    .vue-ecran:not(.cache) { animation: entree-ecran 380ms var(--amorti) both; }
    @keyframes entree-ecran {
      from { opacity: 0; transform: translateY(10px); }
      to { opacity: 1; transform: none; }
    }
    .barre-progression { height: 10px; background: rgba(120, 120, 128, 0.18); }
    .barre-progression-remplie { transition: width 450ms var(--amorti); }

    /* Co-Pilote : conversation façon messagerie, cadres adoucis */
    .cadre-navigateur-direct { border: 1px solid var(--bordure); border-radius: 16px; box-shadow: var(--ombre-carte); }
    .panneau-copilote-chat { border-radius: 16px; }
    .bulle-copilote-user { background: var(--bleu-primaire); color: #fff; border: none; border-radius: 18px 18px 6px 18px; padding: 9px 14px; line-height: 1.45; }
    .bulle-copilote-ia { background: rgba(120, 120, 128, 0.14); color: var(--texte); border: none; border-radius: 18px 18px 18px 6px; padding: 10px 14px; }
    .msg-op { background: var(--bleu-clair); border: 1px solid rgba(0, 113, 227, 0.2); border-radius: 14px; }
    .msg-ia { background: var(--carte); border: 1px solid var(--bordure); border-radius: 14px; }
    .puce-cmd { background: var(--bleu-clair); color: var(--bleu-primaire); border: 1px solid transparent; transition: transform 90ms var(--amorti), background-color 140ms var(--amorti); }
    .puce-cmd:hover { background: rgba(0, 113, 227, 0.2); }
    .puce-cmd:active { transform: scale(0.96); }

    /* Étroit : la navigation devient une barre horizontale */
    @media (max-width: 860px) {
      body { flex-direction: column; }
      aside { position: static; width: 100%; height: auto; flex-direction: row; overflow-x: auto; padding: 10px; gap: 4px; }
      aside h1 { display: none; }
      aside button.nav-btn { white-space: nowrap; }
      main { padding: 14px 16px 48px; }
    }

    /* Accessibilité : mouvement réduit = fondu simple, sans glissement ni flou animé */
    @media (prefers-reduced-motion: reduce) {
      .vue-ecran:not(.cache) { animation: entree-reduite 200ms ease both; }
      .notif { animation: entree-reduite 200ms ease both; }
      button.btn:active, aside button.nav-btn:active, .puce-cmd:active { transform: none; }
      * { scroll-behavior: auto !important; }
    }
    @keyframes entree-reduite { from { opacity: 0; } to { opacity: 1; } }
    /* Transparence réduite : matières pleines, sans flou */
    @media (prefers-reduced-transparency: reduce) {
      aside { background: #1c1c1e; -webkit-backdrop-filter: none; backdrop-filter: none; }
      #banniere-etat, .notif { background: var(--carte); -webkit-backdrop-filter: none; backdrop-filter: none; }
    }
    /* Contraste renforcé : bordures nettes */
    @media (prefers-contrast: more) {
      :root { --bordure: rgba(0, 0, 0, 0.6); --texte-secondaire: #3a3a3c; }
      .carte, .stat, input, select, textarea, button.btn-contour { border-color: var(--bordure); }
    }
  </style>
</head>
<body>
  <aside id="navigation-principale">
    <h1>Agent Bureau d'Études</h1>
    <button class="nav-btn actif" data-vue="vue-tableau-bord">1. Tableau de bord</button>
    <button class="nav-btn" data-vue="vue-etudiants">2. Étudiants &amp; Fiche candidat</button>
    <button class="nav-btn" data-vue="vue-documents">3. Documents &amp; Pièces requises</button>
    <button class="nav-btn" data-vue="vue-conseiller">4. Discussion &amp; Score d'acceptation</button>
    <button class="nav-btn" data-vue="vue-campus-france">5. Campus France (Études en France)</button>
    <button class="nav-btn" data-vue="vue-ircc">6. IRCC Canada (Permis d'études)</button>
    <button class="nav-btn" data-vue="vue-validation-humaine">7. Centre de validation humaine</button>
    <button class="nav-btn" data-vue="vue-historique-erreurs">8. Historique &amp; Erreurs (Audit)</button>
    <button class="nav-btn" data-vue="vue-parametres">9. Paramètres &amp; Sauvegardes</button>
    <button class="nav-btn" data-vue="vue-procedures">10. Procédures (démarches)</button>
  </aside>

  <main>
    <div id="banniere-etat" class="banniere-regle">
      Sécurité active : chiffrement AES-256-GCM par bureau, zéro valeur par défaut inventée (Règle 4), arrêt obligatoire avant soumission officielle (Règle 1).
      | Candidat sélectionné : <strong id="bandeau-candidat-actif">Aucun</strong>
    </div>
    <div id="zone-notification" class="notif cache"></div>

    <!-- Connexion -->
    <section id="bloc-connexion" class="carte">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
        <div>
          <strong>Session Opérateur du Bureau :</strong>
          <span id="etat-utilisateur">Connexion en cours...</span>
        </div>
        <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
          <input id="login-email" type="email" value="admin@bureau-alger.dz" placeholder="employe@bureau.dz" style="width:210px;" />
          <input id="login-mdp" type="password" value="BureauAlger!2026" style="width:160px;" />
          <button id="btn-se-connecter" class="btn" type="button">Se connecter</button>
          <button id="btn-se-deconnecter" class="btn btn-secondaire cache" type="button">Se déconnecter</button>
        </div>
      </div>
    </section>

    <!-- 1. Tableau de bord -->
    <section id="vue-tableau-bord" class="vue-ecran">
      <h2>Tableau de bord du Bureau</h2>
      <div class="grille-stats">
        <div class="stat"><div id="stat-nb-candidats" class="valeur">0</div><div class="libelle">Étudiants actifs</div></div>
        <div class="stat"><div id="stat-nb-a-valider" class="valeur">0</div><div class="libelle">Dossiers prêts à valider humainement (Règle 1)</div></div>
        <div class="stat"><div id="stat-nb-suspendues" class="valeur">0</div><div class="libelle">Dossiers en pause (Pièces / Session / CAPTCHA)</div></div>
        <div class="stat"><div id="stat-nb-agents" class="valeur">0</div><div class="libelle">Postes Agents locaux enrôlés</div></div>
      </div>
      <div class="carte">
        <h3>Accès rapides aux démarches et portails</h3>
        <p>
          <button class="btn btn-succes" type="button" onclick="allerVersVue('vue-campus-france')">Piloter un dossier Campus France (Guide Septembre 2026)</button>
          <button class="btn btn-succes" type="button" onclick="allerVersVue('vue-ircc')">Piloter un dossier IRCC Canada (Permis d'études)</button>
          <button class="btn" type="button" onclick="allerVersVue('vue-conseiller')">Calculer le score d'acceptation &amp; interroger le Conseiller</button>
          <button class="btn btn-secondaire" type="button" onclick="allerVersVue('vue-documents')">Vérifier les pièces manquantes</button>
        </p>
        <p style="margin-top:8px;">
          <a href="https://etudesenfrance.diplomatie.gouv.fr/" target="_blank" rel="noopener"><button class="btn btn-contour" type="button">Site officiel Études en France</button></a>
          <a href="https://portal-portail.apps.cic.gc.ca/signin?lang=fr" target="_blank" rel="noopener"><button class="btn btn-contour" type="button">Portail officiel IRCC Canada</button></a>
          <a href="/demo/campus-france" target="_blank"><button class="btn btn-contour" type="button">Page de simulation Études en France</button></a>
          <a href="/demo/ircc" target="_blank"><button class="btn btn-contour" type="button">Page de simulation IRCC Canada</button></a>
        </p>
      </div>
    </section>

    <!-- 2. Étudiants & Fiche candidat -->
    <section id="vue-etudiants" class="vue-ecran cache">
      <h2>Étudiants &amp; Fiche candidat (Chiffrement AES-256-GCM)</h2>
      <div class="carte">
        <h3>Créer une fiche candidat (Règle 4 : aucune donnée inventée)</h3>
        <div class="grille-form">
          <label>Nom de famille * <input id="cand-nom" type="text" value="BELAID" /></label>
          <label>Prénom * <input id="cand-prenom" type="text" value="Amine" /></label>
          <label>Sexe <select id="cand-sexe"><option value="M" selected>Masculin (M)</option><option value="F">Féminin (F)</option><option value="">Non renseigné</option></select></label>
          <label>Date de naissance <input id="cand-dn" type="date" value="2002-06-15" /></label>
          <label>Lieu de naissance (Wilaya / Ville) <input id="cand-lieu" type="text" value="Alger" /></label>
          <label>Nationalité <input id="cand-nat" type="text" value="Algérienne" /></label>
          <label>Pays de résidence <input id="cand-pays" type="text" value="Algérie" /></label>
          <label>Adresse e-mail <input id="cand-email" type="email" value="amine.belaid@exemple.dz" /></label>
          <label>Téléphone <input id="cand-tel" type="text" value="+213555123456" /></label>
          <label>Numéro de passeport <input id="cand-pass" type="text" value="DZ9900112" /></label>
          <label>Date d'expiration du passeport <input id="cand-exp-pass" type="date" value="2031-05-20" /></label>
          <label>Niveau d'études actuel <input id="cand-niveau" type="text" value="Licence 3 Informatique" /></label>
          <label>Formation / Programme visé <input id="cand-prog" type="text" value="Master 1 Informatique et Intelligence Artificielle" /></label>
          <label>Établissement visé <input id="cand-etab" type="text" value="Université Paris-Saclay" /></label>
          <label>Ressources financières disponibles (EUR) <input id="cand-fonds" type="number" min="0" value="15000" /></label>
        </div>
        <p style="margin-top:12px;">
          <button id="btn-creer-candidat" class="btn btn-succes" type="button">Enregistrer le candidat</button>
        </p>
      </div>
      <div class="carte">
        <h3>Dossiers candidats du bureau &amp; Sélection du candidat actif</h3>
        <div style="display:flex; gap:8px; margin-bottom:10px;">
          <input id="rech-candidat" type="text" placeholder="Rechercher par nom, prénom, e-mail ou numéro de passeport..." style="flex:1;" />
          <button id="btn-rechercher-candidat" class="btn btn-secondaire" type="button">Rechercher / Actualiser</button>
        </div>
        <table id="table-candidats">
          <thead><tr><th>Nom &amp; Prénom</th><th>Passeport</th><th>Formation / Établissement</th><th>Consentement Loi 18-07</th><th>Actions</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </section>

    <!-- 3. Documents & Pièces requises -->
    <section id="vue-documents" class="vue-ecran cache">
      <h2>Documents justificatifs &amp; Vérification des pièces manquantes</h2>
      <div class="carte">
        <h3>1. Téléverser une pièce justificative (chiffrée en AES-256-GCM)</h3>
        <div class="grille-form">
          <label>Type de pièce justificative
            <select id="doc-type-piece">
              <option value="passeport">Passeport biométrique en cours de validité</option>
              <option value="photo_identite">Photo d'identité aux normes passeport</option>
              <option value="releve_notes_bac">Relevé de notes du Baccalauréat</option>
              <option value="diplome_bac">Diplôme ou attestation provisoire du Baccalauréat</option>
              <option value="releves_notes_superieur">Relevés de notes des années d'études supérieures</option>
              <option value="cv">Curriculum Vitæ (CV)</option>
              <option value="attestation_langue_francaise">Attestation de test de français (TCF / DELF / DALF)</option>
              <option value="lettre_admission_dli">IRCC Canada : Lettre d'admission d'un établissement désigné (EED / DLI)</option>
              <option value="attestation_provinciale_pal_caq">IRCC Canada : Lettre d'attestation provinciale (LAP / PAL) ou CAQ Québec</option>
              <option value="preuve_financiere">IRCC Canada : Preuve de ressources financières (relevés, CPG/GIC, garant)</option>
              <option value="formulaire_imm5645">IRCC Canada : Formulaire d'informations sur la famille (IMM 5645)</option>
              <option value="lettre_explicative">IRCC Canada : Lettre d'explication / Plan d'études</option>
            </select>
          </label>
          <label>Date d'expiration du document (si applicable) <input id="doc-expiration" type="date" value="2031-05-20" /></label>
          <label>Fichier justificatif (PDF, PNG ou JPEG — max 10 Mo) <input id="doc-fichier" type="file" accept=".pdf,.png,.jpg,.jpeg" /></label>
        </div>
        <p style="margin-top:12px;">
          <button id="btn-televerser-doc" class="btn btn-succes" type="button">Téléverser et chiffrer la pièce</button>
          <button id="btn-verifier-completude" class="btn" type="button">Vérifier les pièces manquantes (Campus France &amp; IRCC)</button>
          <button id="btn-specimens-demo" class="btn btn-secondaire" type="button">Générer les pièces spécimens de démonstration pour ce candidat</button>
        </p>
      </div>

      <div class="carte">
        <h3>2. État des pièces justificatives par démarche</h3>
        <div id="zone-completude" class="panneau-texte">
          Sélectionnez un candidat puis cliquez sur « Vérifier les pièces manquantes » pour afficher la liste claire des pièces manquantes et des pièces déposées.
        </div>
      </div>

      <div class="carte">
        <h3>3. Pièces déjà déposées dans le dossier du candidat</h3>
        <table id="table-documents-candidat">
          <thead><tr><th>Pièce justificative</th><th>Fichier d'origine</th><th>Date d'expiration</th><th>Taille</th><th>Actions</th></tr></thead>
          <tbody><tr><td colspan="5">Sélectionnez un candidat pour voir ses pièces déposées.</td></tr></tbody>
        </table>
      </div>
    </section>

    <!-- 4. Discussion & Score d'acceptation -->
    <section id="vue-conseiller" class="vue-ecran cache">
      <h2>Espace Discussion Conseiller &amp; Score d'acceptation (0 à 100 %)</h2>
      <div id="ia-statut-discussion" class="ia-statut">Assistant IA : état en cours de vérification...</div>

      <div id="carte-assistant-ia" class="carte">
        <h3>Assistant IA du dossier (sans donnée personnelle)</h3>
        <p style="font-size:0.86rem; color:var(--texte-secondaire); margin-top:0;">
          L'assistant ne reçoit aucune donnée personnelle du candidat : il répond à partir de la démarche choisie. Ses réponses sont indicatives et doivent être vérifiées par un conseiller.
        </p>
        <div class="grille-form">
          <label>Démarche concernée
            <select id="ia-demarche-assistant">
              <option value="campus_france">Campus France — Études en France (Guide Septembre 2026)</option>
              <option value="ircc_permis_etudes">IRCC Canada — Demande de permis d'études</option>
            </select>
          </label>
        </div>
        <div style="display:flex; gap:10px; align-items:center; margin-top:10px;">
          <input id="ia-question-assistant" type="text" style="flex:1;" maxlength="2000" placeholder="Votre question sur la démarche..." />
          <button id="btn-demander-assistant-ia" class="btn btn-succes" type="button" style="margin:0;">Demander</button>
        </div>
        <div id="zone-reponse-assistant-ia" class="panneau-texte cache" style="margin-top:12px;"></div>
      </div>

      <div class="carte">
        <h3>1. Évaluation détaillée des chances d'acceptation et de la solidité du dossier</h3>
        <div class="grille-form">
          <label>Démarche à évaluer
            <select id="eval-demarche">
              <option value="campus_france">Campus France — Études en France (Guide Septembre 2026)</option>
              <option value="ircc_permis_etudes">IRCC Canada — Demande de permis d'études</option>
            </select>
          </label>
        </div>
        <p style="margin-top:12px;">
          <button id="btn-calculer-score" class="btn" type="button">Calculer le score d'acceptation (0–100 %)</button>
        </p>
        <div id="zone-score-acceptation" class="panneau-texte">
          Cliquez sur « Calculer le score d'acceptation » pour afficher l'évaluation complète en français (score sur 100 %, pièces manquantes éventuelles, points forts et plan d'action).
        </div>
      </div>

      <div class="carte">
        <h3>2. Poser une question à l'Assistant Conseiller sur ce dossier</h3>
        <p style="font-size:0.86rem; color:var(--texte-secondaire); margin-top:0;">
          Questions rapides :
          <button class="btn btn-contour" type="button" onclick="poserQuestionRapide('Quelles sont les pièces manquantes et quelle est notre priorité sur ce dossier ?')">Pièces manquantes &amp; Priorité</button>
          <button class="btn btn-contour" type="button" onclick="poserQuestionRapide('Quels sont les délais du calendrier Campus France Algérie 2026-2027 et les frais en DZD ?')">Calendrier &amp; Frais Algérie (20 000 DZD)</button>
          <button class="btn btn-contour" type="button" onclick="poserQuestionRapide('Comment fonctionne le panier de 7 formations (DAP Blanche, DAP Jaune, Hors DAP) et la motivation de 4000 caractères ?')">Panier 7 formations &amp; Motivation</button>
          <button class="btn btn-contour" type="button" onclick="poserQuestionRapide('Comment déclarer un bac algérien en français (> 1000 heures) et remplir le dossier de scolarité (2 activités) ?')">Bac en français &gt; 1000h &amp; Scolarité</button>
          <button class="btn btn-contour" type="button" onclick="poserQuestionRapide('Comment fonctionne le dossier pré-consulaire en 4 étapes et la réduction visa CAPAGO de 50 % ?')">Dossier pré-consulaire &amp; Visa CAPAGO</button>
        </p>
        <div id="fil-discussion" class="fil-discussion">
          <div style="color:var(--texte-secondaire); font-size:0.9rem;">Posez une question ci-dessous ou cliquez sur l'un des boutons de question rapide pour obtenir l'analyse du Conseiller.</div>
        </div>
        <div style="display:flex; gap:10px; align-items:center;">
          <input id="msg-discussion" type="text" style="flex:1;" value="Quelle est notre priorité pour maximiser les chances d'acceptation de ce dossier ?" placeholder="Posez votre question au conseiller..." />
          <button id="btn-envoyer-discussion" class="btn btn-succes" type="button" style="margin:0;">Envoyer au Conseiller</button>
        </div>
      </div>
    </section>

    <!-- 5. Campus France (Études en France — Guide Septembre 2026 & Co-Pilote Navigateur Direct) -->
    <section id="vue-campus-france" class="vue-ecran cache">
      <h2>Démarche Campus France — Études en France (Co-Pilote Navigateur Direct — Guide Septembre 2026)</h2>

      <!-- Vœux de formation et lettres de motivation -->
      <div class="carte" id="carte-voeux">
        <style>
          .voeu { border: 1px solid var(--bordure); border-radius: 12px; padding: 14px 16px; margin-bottom: 12px; background: var(--surface-2); }
          .voeu-entete { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; flex-wrap: wrap; margin-bottom: 8px; }
          .voeu textarea { width: 100%; min-height: 180px; line-height: 1.5; resize: vertical; }
          .voeu-compteur { font-size: 0.8rem; color: var(--texte-secondaire); margin: 4px 0 8px; }
          .voeu-compteur.depasse { color: var(--rouge-danger); font-weight: 650; }
          .voeu-alertes { font-size: 0.86rem; margin: 6px 0 8px; padding-left: 18px; color: var(--orange-alerte); }
        </style>
        <h3>Vœux de formation et lettres de motivation (panier, 7 maximum)</h3>
        <div style="font-size:0.86rem; color:var(--texte-secondaire); margin-bottom:12px; line-height:1.5;">
          Candidat actif : <strong id="voeux-candidat-actif">Aucun</strong>. Chaque lettre est rédigée en brouillon, relue par vous, puis validée. Seuls les vœux validés peuvent être ajoutés au panier, et le Co-Pilote s'arrête toujours avant la certification et la soumission (Règle 1).
        </div>

        <details class="guide-bloc" open>
          <summary>Faits du parcours utilisés pour rédiger les lettres (aucune identité n'est transmise à l'IA)</summary>
          <div class="grille-form" style="margin-top:10px;">
            <label>Parcours (une ligne par étape)
              <textarea id="faits-parcours" rows="4" placeholder="Ex : 2023-2025 : Master Linguistique et didactique, Université de Béjaïa, moyenne 13,16/20"></textarea>
            </label>
            <label>Points forts vérifiables (une ligne chacun)
              <textarea id="faits-points" rows="4" placeholder="Ex : Mémoire de master noté 16/20"></textarea>
            </label>
            <label>Langues et certificats (une ligne chacun)
              <textarea id="faits-langues" rows="3" placeholder="Ex : Anglais 17/20 en M1 ; TCF B2 (si disponible)"></textarea>
            </label>
            <label>Projet professionnel ou de recherche
              <textarea id="faits-projet" rows="3" placeholder="Ce que la candidate veut faire après la formation"></textarea>
            </label>
          </div>
          <div style="font-size:0.82rem; color:var(--texte-secondaire); margin-top:6px;">
            N'écrivez ici ni nom, ni date de naissance, ni numéro de passeport, ni e-mail, ni téléphone. Rien d'inventé : ce que vous ne renseignez pas apparaît comme « À COMPLÉTER » dans la lettre.
          </div>
        </details>

        <h4>Ajouter un vœu</h4>
        <div class="grille-form">
          <label>Intitulé exact de la formation
            <input id="voeu-intitule" type="text" placeholder="Ex : Master Traitement automatique des langues" />
          </label>
          <label>Établissement
            <input id="voeu-etablissement" type="text" placeholder="Ex : Université de Lorraine" />
          </label>
          <label>Niveau
            <select id="voeu-niveau">
              <option>Master 1</option><option>Master 2</option><option>Licence 3</option><option>Licence 2</option>
              <option>Licence 1</option><option>Ingénieur</option><option>Autre</option>
            </select>
          </label>
          <label>Voie
            <select id="voeu-voie">
              <option value="hors_dap" selected>Hors DAP (L2, L3, Master, Ingénieur…)</option>
              <option value="dap_blanche">DAP Blanche (Licence 1)</option>
              <option value="dap_jaune">DAP Jaune (Architecture)</option>
            </select>
          </label>
          <label>Pourquoi cette formation ? (facultatif, sert à personnaliser la lettre)
            <input id="voeu-justification" type="text" placeholder="Ex : cours de TAL pour langues peu dotées" />
          </label>
        </div>
        <p style="margin-top:10px;">
          <button id="btn-ajouter-voeu" class="btn" type="button">+ Ajouter ce vœu</button>
          <button id="btn-actualiser-voeux" class="btn btn-secondaire" type="button">Actualiser la liste</button>
        </p>

        <div id="liste-voeux"><div class="panneau-texte">Sélectionnez un candidat (onglet 2) pour gérer ses vœux.</div></div>

        <p>
          <button id="btn-panier-voeux" class="btn btn-succes" type="button" onclick="lancerActionNavigateur('campus_france', 'ajouter_voeux_panier')">Ajouter les vœux validés au panier (Co-Pilote)</button>
        </p>
      </div>

      <div class="carte">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:10px;">
          <div>
            <h3 style="margin:0;"><span class="point-vert-pulsant"></span>Co-Pilote Navigateur IA en Direct (Style Perplexity Assistant / Claude Cowork)</h3>
            <div style="font-size:0.86rem; color:var(--texte-secondaire); margin-top:3px;">
              Contrôle direct et temps réel de votre navigateur (sans capture d'écran) : barre latérale IA injectée dans la page, curseur animé en direct et compréhension du langage naturel.
            </div>
          </div>
          <div>
            <button class="btn" type="button" onclick="executerActionDomRapide('campus_france', 'focus_fenetre')">🖥️ Mettre la fenêtre du navigateur au 1er plan</button>
            <button id="btn-creer-tache-cf" class="btn btn-secondaire" type="button">Suivi de la tâche Campus France</button>
          </div>
        </div>

        <div class="grille-form">
          <label>Portail cible dans le navigateur
            <select id="cf-cible-navigateur" onchange="changerCibleNavigateurDirect('campus_france')">
              <option value="campus_france_officiel" selected>Vrai site officiel Études en France (https://etudesenfrance.diplomatie.gouv.fr/)</option>
              <option value="demo_campus_france">Portail interactif Études en France — Mode direct intégré (Guide Septembre 2026)</option>
              <option value="campus_france_algerie">Site Campus France Algérie (https://www.algerie.campusfrance.org)</option>
              <option value="paiement_ifa_algerie">Portail de paiement IFA Algérie (https://paiement.if-algerie.com)</option>
            </select>
          </label>
          <label style="justify-content:center;">
            <span>Mode de contrôle du navigateur</span>
            <span style="font-weight:400; margin-top:6px;">
              <input id="cf-fenetre-visible" type="checkbox" checked /> Piloter directement ma vraie fenêtre Chrome / Edge / Chromium (avec barre latérale Co-Pilote intégrée)
            </span>
          </label>
        </div>

        <p style="margin-top:10px; margin-bottom:4px;"><strong>Actions directes en 1 clic dans le navigateur (Guide Études en France — Septembre 2026) :</strong></p>
        <div>
          <button class="btn" type="button" onclick="lancerActionNavigateur('campus_france', 'ouvrir_portail')">1. Ouvrir le site en direct</button>
          <button class="btn btn-succes" type="button" onclick="lancerActionNavigateur('campus_france', 'preremplissage_complet')">2. ⚡ Tout remplir en direct + Pièces + Arrêt Règle 1</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('campus_france', 'inscription_compte')">3. S'inscrire (Créer compte)</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('campus_france', 'connexion_compte')">3. Se connecter (Règle 3)</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('campus_france', 'preremplir_espace_etudiant')">4. Identité, Passeport &amp; Antenne ECF</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('campus_france', 'preremplir_scolarite_et_langues')">4. Scolarité (2 activités) &amp; Français &gt; 1000h</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('campus_france', 'preremplir_panier_formations_et_motivations')">5. Panier (max 7) &amp; Motivation (4 000 car.)</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('campus_france', 'preparer_paiement_et_rdv')">5. Paiement (20 000 DZD) &amp; RDV</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('campus_france', 'preremplir_dossier_preconsulaire')">6. Dossier pré-consulaire (4 étapes)</button>
        </div>

        <div class="workspace-cowork">
          <!-- Colonne Gauche : Navigateur en Direct & Inspecteur DOM Temps Réel (Zéro Capture d'Écran) -->
          <div class="cadre-navigateur-direct">
            <div class="barre-chrome-direct">
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('campus_france', 'retour')" title="Page précédente">⬅</button>
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('campus_france', 'suivant')" title="Page suivante">➡</button>
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('campus_france', 'actualiser')" title="Actualiser la page">↻</button>
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('campus_france', 'scroll_haut')" title="Monter">⬆️</button>
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('campus_france', 'scroll_bas')" title="Descendre">⬇️</button>
              <input id="cf-url-live" class="url-live-input" type="text" value="https://etudesenfrance.diplomatie.gouv.fr/" placeholder="Entrez une URL et appuyez sur Aller..." />
              <button class="btn-nav-mini" type="button" onclick="naviguerUrlDirecte('campus_france')">Aller</button>
              <button class="btn-nav-mini" type="button" onclick="basculerModeVueDirecte('campus_france')" id="btn-mode-vue-cf">Vue : Contrôle DOM &amp; Fenêtre</button>
            </div>
            <div id="cf-conteneur-iframe" class="cache">
              <iframe id="cf-iframe-direct" class="iframe-navigateur-direct" src="/demo/campus-france" title="Portail interactif Études en France en direct"></iframe>
            </div>
            <div id="cf-panneau-dom-live" class="corps-navigateur-direct">
              <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #e2e8f0; padding-bottom:8px; margin-bottom:10px;">
                <div>
                  <strong id="cf-titre-page-live">Contrôleur DOM en Direct — Études en France</strong>
                  <div style="font-size:0.8rem; color:var(--texte-secondaire);">Interagissez en temps réel avec les champs et boutons de la page ouverte dans votre navigateur (sans capture d'écran).</div>
                </div>
                <button class="btn btn-contour" type="button" style="margin:0; padding:5px 10px; font-size:0.8rem;" onclick="synchroniserEtatNavigateurDirect('campus_france')">🔄 Synchroniser DOM</button>
              </div>
              <div id="cf-elements-dom-live">
                <p style="color:var(--texte-secondaire); font-size:0.88rem;">
                  Cliquez sur <strong>« 1. Ouvrir le site en direct »</strong> ou tapez une consigne à droite (ex: <em>« ouvre le vrai site Campus France »</em>, <em>« remplis mon identité »</em>) pour voir et manipuler en direct tous les éléments de la page.
                </p>
              </div>
            </div>
          </div>

          <!-- Colonne Droite : Conversation Co-Pilote Temps Réel (Compréhension Naturelle & Voix) -->
          <div class="panneau-copilote-chat">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <strong>💬 Assistant Co-Pilote Navigateur (Langage naturel &amp; Voix)</strong>
              <span class="badge badge-ok">Temps réel</span>
            </div>
            <div style="font-size:0.8rem; color:var(--texte-secondaire);">
              Exemples de demandes naturelles (cliquez pour tester) :
              <div style="margin-top:4px;">
                <span class="puce-cmd" onclick="envoyerConsigneRapideCopilote('campus_france', 'Ouvre le vrai site Études en France dans mon navigateur')">🌐 Vrai site Études en France</span>
                <span class="puce-cmd" onclick="envoyerConsigneRapideCopilote('campus_france', 'Clique sur S\'inscrire et pré-remplis mon compte')">📝 Aller sur S'inscrire</span>
                <span class="puce-cmd" onclick="envoyerConsigneRapideCopilote('campus_france', 'Analyse cette page et explique-moi ce qu\'il faut faire')">🔍 Analyser cette page</span>
                <span class="puce-cmd" onclick="envoyerConsigneRapideCopilote('campus_france', 'Mets Oran comme ville et Université Paris-Saclay comme établissement')">✏️ Changer ville &amp; université</span>
                <span class="puce-cmd" onclick="envoyerConsigneRapideCopilote('campus_france', 'Remplis mes motivations pour ma formation')">✍️ Rédiger motivations</span>
                <span class="puce-cmd" onclick="envoyerConsigneRapideCopilote('campus_france', 'Quels sont les frais en DZD et les dates limites 2026-2027 ?')">📅 Frais 20 000 DZD &amp; Dates</span>
              </div>
            </div>

            <div id="fil-copilote-cf" class="fil-copilote">
              <div class="bulle-copilote-ia">
                <strong>Co-Pilote prêt.</strong> Dites-moi en français naturel ce que je dois faire dans votre navigateur (ex: <em>« remplis mon identité »</em>, <em>« clique sur Se connecter »</em>, <em>« mets Constantine comme ville »</em>, <em>« descends en bas de la page »</em>, <em>« remplis tout sans soumettre »</em>).
              </div>
            </div>

            <div style="display:flex; gap:6px; align-items:center;">
              <input id="cf-instruction-agent" type="text" style="flex:1;" value="Pré-remplir tout le dossier Études en France du candidat (identité, passeport, scolarité, langues, panier de formations et motivation) et enregistrer le brouillon" placeholder="Parlez naturellement à l'agent (ex: clique sur S'inscrire, mets Oran comme ville, remplis cette page...)" />
              <button class="btn btn-secondaire" type="button" style="margin:0; padding:9px 11px;" onclick="demarrerDicteeVocale('campus_france')" title="Dicter votre consigne à la voix">🎤</button>
              <button id="btn-piloter-cf-instruction" class="btn btn-succes" type="button" style="margin:0;">Exécuter en direct</button>
            </div>

            <div id="zone-retour-cf" class="panneau-texte" style="padding:12px 14px; font-size:0.88rem;">
              Sélectionnez un candidat puis donnez une instruction en langage naturel ci-dessus ou cliquez sur une action directe.
            </div>
          </div>
        </div>
      </div>

      <div class="carte">
        <h3>2. Guide officiel complet « Études en France — Septembre 2026 » (Campus France Algérie — 96 pages)</h3>
        <details class="guide-bloc" open>
          <summary>Calendrier officiel Campus France Algérie (Session 2026–2027) &amp; Frais de dossier (DZD)</summary>
          <div style="margin-top:8px; font-size:0.9rem;">
            <ul class="liste-propre">
              <li><strong>Hors DAP (L2, L3, Master 1, Master 2, Écoles d'ingénieurs et de commerce) :</strong> Ouverture le <strong>1er octobre 2026</strong> — Date limite de soumission et de paiement : <strong>30 novembre 2026</strong> — Entretiens jusqu'au <strong>15 mars 2027</strong> — Choix définitif avant le <strong>31 mai 2027</strong>.</li>
              <li><strong>DAP (L1 Université, Écoles d'architecture ENSA, BUT, Licence professionnelle) :</strong> Ouverture le <strong>1er octobre 2026</strong> — Date limite de soumission et de paiement : <strong>15 décembre 2026</strong> — Entretiens jusqu'au <strong>15 mars 2027</strong> — Choix définitif avant le <strong>31 mai 2027</strong>.</li>
              <li><strong>CPGE, BTS, DCG :</strong> À partir de <strong>janvier 2027</strong> sur Parcoursup.</li>
              <li><strong>Dossier pré-consulaire (« Je suis accepté » / Établissements privés non-connectés) :</strong> Dès réception de l'acceptation, au minimum <strong>45 jours avant la rentrée</strong>.</li>
              <li><strong>Frais de dossier Algérie :</strong> Plein tarif : <strong>20 000 DZD</strong> | Demi-tarif : <strong>10 000 DZD</strong> (Bac français &lt; 4 ans et candidat &lt; 22 ans, ou acceptation Campus Art) | <strong>Gratuité :</strong> Boursier du gouvernement français, bachelier du LIAD de l'année en cours, agent de l'Institut français d'Algérie. Paiement sur <code>paiement.if-algerie.com</code>.</li>
              <li><strong>5 Antennes Espace Campus France Algérie :</strong> Alger (<code>ecf.alger@if-algerie.com</code>), Annaba (<code>ecf.annaba@if-algerie.com</code>), Constantine (<code>ecf.constantine@if-algerie.com</code>), Oran (<code>ecf.oran@if-algerie.com</code>), Tlemcen (<code>ecf.tlemcen@if-algerie.com</code>).</li>
            </ul>
          </div>
        </details>

        <details class="guide-bloc">
          <summary>Sections 3 &amp; 4 : Mon compte &amp; Mon espace étudiant (Identité, Scolarité, Compétences linguistiques)</summary>
          <div style="margin-top:8px; font-size:0.9rem;">
            <ul class="liste-propre">
              <li><strong>Inscription &amp; Connexion :</strong> Bouton « S'inscrire » sur <code>https://etudesenfrance.diplomatie.gouv.fr/</code> (Espace Campus France Algérie, activation par mail sous 48h). Attention : compte bloqué <strong>30 minutes après 5 tentatives</strong> de mot de passe erronées.</li>
              <li><strong>Mes informations personnelles :</strong> Identité, Photo d'identité au format passeport (JPG/PNG/PDF, max 10 Mo), Passeport valide (numéro, date limite de validité, copie), Coordonnées (adresse et téléphone déterminant l'antenne ECF), et Statut particulier (« Je ne suis concerné par aucun de ces statuts particuliers »).</li>
              <li><strong>Mon dossier de scolarité :</strong> CV obligatoire + <strong>au moins 2 activités obligatoires</strong> dans « Parcours scolaire et professionnel » (années de lycée jusqu'au bac pour Bac+1 ; du bac jusqu'à la dernière année d'études supérieures pour Bac+2 et plus ; commentaire limité à 1 000 caractères).</li>
              <li><strong>Mes compétences linguistiques :</strong> Pour un baccalauréat algérien/non européen en français : sélectionner « Oui », Volume « Plus de 1000 heures », Durée « 4 ans et plus », Niveau atteint « Avancé ». Ajouter le test TCF ou DELF/DALF dans « + Ajouter un test », puis renseigner le niveau d'anglais.</li>
            </ul>
          </div>
        </details>

        <details class="guide-bloc">
          <summary>Sections 5 &amp; 6 : Mon dossier de candidature (Panier max 7 choix) &amp; Mon dossier pré-consulaire</summary>
          <div style="margin-top:8px; font-size:0.9rem;">
            <ul class="liste-propre">
              <li><strong>Règles du panier (max 7 formations) :</strong> DAP Blanche (L1 : jusqu'à 3 choix), DAP Jaune (Architecture ENSA : 2 choix obligatoires + Portfolio), Hors DAP (L2, L3, M1, M2, Ingénieur, Commerce : jusqu'à 7 choix). Vérifier le badge « OUVERT À LA CANDIDATURE ».</li>
              <li><strong>Texte de motivation :</strong> Obligatoire pour chaque formation du panier (jusqu'à <strong>4 000 caractères</strong>) puis cliquer sur « Enregistrer ».</li>
              <li><strong>Soumission (Règle 1) :</strong> L'agent s'arrête toujours avant les 2 cases de certification et le bouton « Soumettre mon dossier de candidature ».</li>
              <li><strong>Dossier pré-consulaire (« Je suis accepté ») :</strong> Sélection de la formation acceptée via Études en France, ou ajout d'une acceptation papier / programme d'échange en <strong>4 étapes</strong>. Permet d'obtenir l'Attestation d'acceptation (identifiant <code>DZXX-XXXXX</code>) donnant droit à <strong>-50 % sur les frais de visa long séjour</strong> chez CAPAGO.</li>
            </ul>
          </div>
        </details>
      </div>
    </section>

    <!-- 6. IRCC Canada (Co-Pilote Navigateur Direct) -->
    <section id="vue-ircc" class="vue-ecran cache">
      <h2>Démarche IRCC Canada — Demande de permis d'études (Co-Pilote Navigateur Direct)</h2>
      <div class="carte">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:10px;">
          <div>
            <h3 style="margin:0;"><span class="point-vert-pulsant"></span>Co-Pilote Navigateur IRCC Canada en Direct (Style Perplexity / Claude Cowork)</h3>
            <div style="font-size:0.86rem; color:var(--texte-secondaire); margin-top:3px;">
              Contrôle automatique du seuil financier (<strong>20 635 $ CAD</strong> ≈ <strong>14 500 EUR</strong>), de la LAP/PAL ou CAQ Québec et de l'admission EED/DLI. Arrêt garanti avant signature/transmission (Règle 1).
            </div>
          </div>
          <div>
            <button class="btn" type="button" onclick="executerActionDomRapide('ircc_permis_etudes', 'focus_fenetre')">🖥️ Mettre la fenêtre du navigateur au 1er plan</button>
            <button id="btn-creer-tache-ircc" class="btn btn-secondaire" type="button">Suivi de la tâche IRCC</button>
          </div>
        </div>

        <div class="grille-form">
          <label>Portail cible dans le navigateur
            <select id="ircc-cible-navigateur" onchange="changerCibleNavigateurDirect('ircc_permis_etudes')">
              <option value="ircc_officiel" selected>Vrai portail officiel IRCC Canada (https://portal-portail.apps.cic.gc.ca/signin?lang=fr)</option>
              <option value="demo_ircc">Portail interactif IRCC — Mode direct intégré</option>
              <option value="ircc_canada_info">Page officielle Permis d'études Canada.ca</option>
            </select>
          </label>
          <label style="justify-content:center;">
            <span>Mode de contrôle du navigateur</span>
            <span style="font-weight:400; margin-top:6px;">
              <input id="ircc-fenetre-visible" type="checkbox" checked /> Piloter directement ma vraie fenêtre Chrome / Edge / Chromium (avec barre latérale Co-Pilote intégrée)
            </span>
          </label>
        </div>

        <p style="margin-top:10px;">
          <button class="btn" type="button" onclick="lancerActionNavigateur('ircc_permis_etudes', 'ouvrir_portail')">1. Ouvrir le portail IRCC en direct</button>
          <button class="btn btn-succes" type="button" onclick="lancerActionNavigateur('ircc_permis_etudes', 'preremplissage_complet')">2. ⚡ Tout pré-remplir + Joindre pièces IRCC + Arrêt Règle 1</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('ircc_permis_etudes', 'preremplir_identite_ircc')">3. Identité &amp; Passeport IRCC</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('ircc_permis_etudes', 'preremplir_dli_fonds_ircc')">4. Établissement DLI &amp; Fonds (20 635 CAD)</button>
          <button class="btn btn-contour" type="button" onclick="lancerActionNavigateur('ircc_permis_etudes', 'televerser_pieces_ircc')">5. Téléverser les 6 pièces IRCC (PAL/CAQ, IMM 5645...)</button>
        </p>

        <div class="workspace-cowork">
          <!-- Colonne Gauche : Navigateur IRCC en Direct & Inspecteur DOM -->
          <div class="cadre-navigateur-direct">
            <div class="barre-chrome-direct">
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('ircc_permis_etudes', 'retour')" title="Page précédente">⬅</button>
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('ircc_permis_etudes', 'suivant')" title="Page suivante">➡</button>
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('ircc_permis_etudes', 'actualiser')" title="Actualiser">↻</button>
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('ircc_permis_etudes', 'scroll_haut')" title="Monter">⬆️</button>
              <button class="btn-nav-mini" type="button" onclick="executerActionDomRapide('ircc_permis_etudes', 'scroll_bas')" title="Descendre">⬇️</button>
              <input id="ircc-url-live" class="url-live-input" type="text" value="https://portal-portail.apps.cic.gc.ca/signin?lang=fr" placeholder="URL IRCC..." />
              <button class="btn-nav-mini" type="button" onclick="naviguerUrlDirecte('ircc_permis_etudes')">Aller</button>
              <button class="btn-nav-mini" type="button" onclick="basculerModeVueDirecte('ircc_permis_etudes')" id="btn-mode-vue-ircc">Vue : Contrôle DOM &amp; Fenêtre</button>
            </div>
            <div id="ircc-conteneur-iframe" class="cache">
              <iframe id="ircc-iframe-direct" class="iframe-navigateur-direct" src="/demo/ircc" title="Portail interactif IRCC Canada en direct"></iframe>
            </div>
            <div id="ircc-panneau-dom-live" class="corps-navigateur-direct">
              <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #e2e8f0; padding-bottom:8px; margin-bottom:10px;">
                <div>
                  <strong id="ircc-titre-page-live">Contrôleur DOM en Direct — Portail IRCC Canada</strong>
                  <div style="font-size:0.8rem; color:var(--texte-secondaire);">Manipulez en temps réel les champs et boutons de votre navigateur sans capture d'écran.</div>
                </div>
                <button class="btn btn-contour" type="button" style="margin:0; padding:5px 10px; font-size:0.8rem;" onclick="synchroniserEtatNavigateurDirect('ircc_permis_etudes')">🔄 Synchroniser DOM</button>
              </div>
              <div id="ircc-elements-dom-live">
                <p style="color:var(--texte-secondaire); font-size:0.88rem;">
                  Cliquez sur <strong>« 1. Ouvrir le portail IRCC en direct »</strong> ou donnez une consigne à droite pour inspecter et remplir les champs en direct.
                </p>
              </div>
            </div>
          </div>

          <!-- Colonne Droite : Conversation Co-Pilote IRCC Temps Réel -->
          <div class="panneau-copilote-chat">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <strong>💬 Assistant Co-Pilote IRCC (Langage naturel &amp; Voix)</strong>
              <span class="badge badge-ok">Temps réel</span>
            </div>
            <div style="font-size:0.8rem; color:var(--texte-secondaire);">
              Exemples de demandes naturelles :
              <div style="margin-top:4px;">
                <span class="puce-cmd" onclick="envoyerConsigneRapideCopilote('ircc_permis_etudes', 'Ouvre le vrai portail officiel IRCC Canada')">🌐 Vrai portail IRCC</span>
                <span class="puce-cmd" onclick="envoyerConsigneRapideCopilote('ircc_permis_etudes', 'Analyse cette page IRCC et dis-moi quoi remplir')">🔍 Analyser la page</span>
                <span class="puce-cmd" onclick="envoyerConsigneRapideCopilote('ircc_permis_etudes', 'Mets Université Laval comme établissement et 21000 euros comme fonds')">✏️ Changer DLI &amp; Fonds</span>
                <span class="puce-cmd" onclick="envoyerConsigneRapideCopilote('ircc_permis_etudes', 'Remplis tout le formulaire IRCC et téléverse les pièces sans transmettre')">⚡ Tout remplir IRCC</span>
              </div>
            </div>

            <div id="fil-copilote-ircc" class="fil-copilote">
              <div class="bulle-copilote-ia">
                <strong>Co-Pilote IRCC prêt.</strong> Demandez-moi n'importe quelle action en français (ex: <em>« remplis mon identité et le DLI »</em>, <em>« mets 19000 euros comme fonds »</em>, <em>« quelles sont les règles PAL/CAQ ? »</em>).
              </div>
            </div>

            <div style="display:flex; gap:6px; align-items:center;">
              <input id="ircc-instruction-agent" type="text" style="flex:1;" value="Pré-remplir toute la demande de permis d'études IRCC (identité, passeport, établissement DLI, ressources financières et pièces justificatives) et sauvegarder le brouillon" placeholder="Parlez naturellement à l'agent IRCC..." />
              <button class="btn btn-secondaire" type="button" style="margin:0; padding:9px 11px;" onclick="demarrerDicteeVocale('ircc_permis_etudes')" title="Dicter votre consigne à la voix">🎤</button>
              <button id="btn-piloter-ircc-instruction" class="btn btn-succes" type="button" style="margin:0;">Exécuter en direct</button>
            </div>

            <div id="zone-retour-ircc" class="panneau-texte" style="padding:12px 14px; font-size:0.88rem;">
              Sélectionnez un candidat puis donnez une instruction en langage naturel ci-dessus ou cliquez sur une action directe.
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 7. Centre de validation humaine -->
    <section id="vue-validation-humaine" class="vue-ecran cache">
      <h2>Centre de validation humaine (Règle 1 — Option A)</h2>
      <div class="banniere-regle">
        Aucune demande officielle n'est jamais soumise par l'agent. Vérifiez la capture d'écran de contrôle et le récapitulatif en français ci-dessous avant d'approuver humainement.
      </div>
      <p><button id="btn-rafraichir-validations" class="btn" type="button">Actualiser les dossiers en attente de validation ou en pause</button></p>
      <div id="liste-centre-validation" class="panneau-texte">Chargement des dossiers...</div>
    </section>

    <!-- 8. Historique & Erreurs -->
    <section id="vue-historique-erreurs" class="vue-ecran cache">
      <h2>Historique d'audit immuable &amp; Journal des opérations (Règle 5)</h2>
      <div class="carte">
        <p><button id="btn-rafraichir-audit" class="btn btn-secondaire" type="button">Actualiser le journal d'audit</button></p>
        <table id="table-audit">
          <thead><tr><th>Date &amp; Heure (UTC)</th><th>Opération</th><th>Statut</th><th>Ressource</th><th>Résumé (sans donnée personnelle — Règle 5)</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </section>

    <!-- 9. Paramètres & Sauvegardes -->
    <section id="vue-parametres" class="vue-ecran cache">
      <h2>Paramètres du Bureau, Abonnement SaaS, Agents Locaux &amp; Sauvegardes chiffrées</h2>
      <div class="carte">
        <h3>1. Enrôler un poste Agent Local Playwright dans le bureau</h3>
        <div class="grille-form">
          <label>Nom du poste Windows du bureau <input id="nom-machine-agent" type="text" value="PC-BUREAU-ALGER-01" /></label>
        </div>
        <p style="margin-top:12px;"><button id="btn-enroler-agent" class="btn" type="button">Enrôler ce poste et générer sa clé d'accès</button></p>
        <div id="zone-jeton-agent" class="panneau-texte cache"></div>
      </div>
      <div class="carte">
        <h3>2. Sauvegardes chiffrées AES-256-GCM du bureau &amp; Statut Abonnement / Portails</h3>
        <p>
          <button id="btn-creer-sauvegarde" class="btn btn-succes" type="button">Créer une sauvegarde chiffrée (.be.enc)</button>
          <button id="btn-voir-abonnement" class="btn btn-secondaire" type="button">Afficher mon abonnement &amp; le statut d'homologation des portails (Règle 6)</button>
        </p>
        <div id="zone-sauvegardes-abo" class="panneau-texte">Cliquez sur l'un des boutons ci-dessus.</div>
      </div>
    </section>

    <!-- 10. Procédures (démarches) : ajout et modification par le bureau -->
    <section id="vue-procedures" class="vue-ecran cache">
      <style>
        .ligne-proc { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; background: #f8fafc; border: 1px solid var(--bordure); border-radius: 8px; padding: 8px 10px; margin-bottom: 8px; }
        .ligne-proc input[type="text"], .ligne-proc input[type="number"] { flex: 1 1 160px; min-width: 120px; }
        .ligne-proc .large { flex: 3 1 260px; }
        .liste-cases { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 6px; }
        .liste-cases label, .ligne-proc label { font-weight: 400; display: flex; flex-direction: row; gap: 6px; align-items: center; }
        .liste-cases input[type="checkbox"], .ligne-proc input[type="checkbox"] { width: auto; margin: 0; }
        fieldset#fs-editeur { border: none; padding: 0; margin: 0; min-width: 0; }
        .ia-statut { display: inline-block; font-size: 0.85rem; color: var(--texte-secondaire); background: var(--surface-2); border: 1px solid var(--bordure); border-radius: 999px; padding: 4px 12px; margin: 0 0 12px 0; }
        .ia-texte-source { width: 100%; min-height: 200px; line-height: 1.5; resize: vertical; }
        .ia-compteur { font-size: 0.8rem; color: var(--texte-secondaire); margin: 4px 0 8px; }
        .ia-compteur.depasse { color: var(--rouge-danger); font-weight: 650; }
        .ia-reponse { white-space: pre-wrap; line-height: 1.55; }
        .ia-mention { font-size: 0.82rem; color: var(--texte-secondaire); margin-top: 8px; }
      </style>
      <h2>Procédures (démarches) de votre bureau</h2>
      <div class="banniere-regle">
        Les procédures de base (Campus France, IRCC…) sont communes à tous les bureaux. Vous pouvez en ajouter de nouvelles ou personnaliser une procédure de base : vos changements ne concernent que votre bureau et s'appliquent immédiatement, sans redéploiement. Réservé aux administrateurs du bureau pour la modification.
      </div>

      <div id="ia-statut-procedures" class="ia-statut">Assistant IA : état en cours de vérification...</div>

      <div id="carte-generation-ia" class="carte cache">
        <h3>Créer une procédure à partir d'un texte officiel (IA)</h3>
        <p style="font-size:0.86rem; color:var(--texte-secondaire); margin-top:0;">
          Collez le guide ou la page officielle de la démarche (80 à 30 000 caractères). L'assistant prépare un brouillon de procédure ; rien n'est enregistré tant que vous n'avez pas relu l'éditeur et cliqué sur « Enregistrer la procédure ».
        </p>
        <textarea id="ia-texte-source" class="ia-texte-source" placeholder="Collez ici le texte officiel de la démarche..."></textarea>
        <div id="ia-compteur-texte" class="ia-compteur">0 / 30 000 caractères (minimum 80)</div>
        <p>
          <button id="btn-generer-procedure-ia" class="btn btn-succes" type="button">Générer un brouillon</button>
        </p>
        <div id="zone-retour-generation-ia" class="panneau-texte cache"></div>
      </div>

      <div class="carte">
        <p>
          <button id="btn-rafraichir-procedures"class="btn btn-secondaire" type="button">Actualiser la liste</button>
          <button id="btn-nouvelle-procedure" class="btn btn-succes cache" type="button">+ Nouvelle procédure</button>
        </p>
        <table id="table-procedures">
          <thead><tr><th>Code</th><th>Libellé</th><th>Origine</th><th>Version</th><th>Actions</th></tr></thead>
          <tbody><tr><td colspan="5">Chargement...</td></tr></tbody>
        </table>
      </div>

      <div id="carte-editeur-procedure" class="carte cache">
        <h3 id="titre-editeur-procedure">Éditeur de procédure</h3>
        <div id="bloc-ia-editeur" class="panneau-texte cache">
          <strong>Brouillon généré par IA : relisez chaque point avant d'enregistrer</strong>
          <div id="titre-avertissements-ia" style="margin-top:8px;">Points signalés par l'assistant :</div>
          <ul id="liste-avertissements-ia" class="liste-propre"></ul>
        </div>
        <div id="encart-champs-avances" class="panneau-texte cache">
          <strong>Champs avancés présents dans cette procédure</strong>
          <div style="font-size:0.85rem; color:var(--texte-secondaire); margin:4px 0;">
            Lecture seule pour l'instant : l'éditeur ne sait pas encore les modifier, mais ils sont conservés tels quels à l'enregistrement.
          </div>
          <ul id="liste-champs-avances" class="liste-propre"></ul>
        </div>
        <fieldset id="fs-editeur">
          <div class="grille-form">
            <label>Code technique (minuscules, chiffres, underscores)
              <input id="proc-code" type="text" placeholder="ex: visa_touristique" />
            </label>
            <label>Libellé affiché
              <input id="proc-libelle" type="text" placeholder="ex: Visa touristique Schengen" />
            </label>
            <label>Seuil de fonds recommandé (EUR, facultatif)
              <input id="proc-seuil" type="number" min="0" />
            </label>
          </div>
          <label style="display:block; margin-top:10px;">Description (facultatif)
            <input id="proc-description" type="text" style="width:100%;" />
          </label>

          <h4>Informations du candidat obligatoires avant tout pré-remplissage</h4>
          <div id="proc-champs" class="liste-cases"></div>

          <h4>Pièces requises</h4>
          <datalist id="liste-types-pieces"></datalist>
          <div id="proc-pieces"></div>
          <p><button id="btn-ajouter-piece" class="btn btn-contour" type="button">+ Ajouter une pièce</button></p>

          <h4>Étapes de la tâche (facultatif)</h4>
          <div style="font-size:0.85rem; color:var(--texte-secondaire); margin-bottom:6px;">
            Laissez vide pour garder les 4 étapes standard (vérification, session portail, pré-remplissage, arrêt avant validation humaine).
          </div>
          <div id="proc-etapes"></div>
          <p><button id="btn-ajouter-etape" class="btn btn-contour" type="button">+ Ajouter une étape</button></p>

          <h4>Veille réglementaire (points à connaître)</h4>
          <div id="proc-veille"></div>
          <p><button id="btn-ajouter-veille" class="btn btn-contour" type="button">+ Ajouter un point de veille</button></p>
        </fieldset>
        <p>
          <button id="btn-enregistrer-procedure" class="btn btn-succes" type="button">Enregistrer la procédure</button>
          <button id="btn-fermer-editeur-procedure" class="btn btn-secondaire" type="button">Fermer l'éditeur</button>
        </p>
        <div id="zone-retour-procedure" class="panneau-texte cache"></div>
      </div>
    </section>
  </main>

  <script>
    let roleActif = "";
    let jetonCsrf = "";
    let candidatActifId = null;
    let candidatActifObj = null;
    let dictionnaireCandidats = {};
    let listeDemarches = [
      { code: "campus_france", libelle: "Campus France — Études en France (Guide Septembre 2026)" },
      { code: "ircc_permis_etudes", libelle: "IRCC Canada — Demande de permis d'études" },
    ];

    const LIBELLES_PIECES_FR = {
      passeport: "Passeport biométrique en cours de validité",
      photo_identite: "Photo d'identité aux normes passeport",
      releve_notes_bac: "Relevé de notes du Baccalauréat",
      diplome_bac: "Diplôme ou attestation provisoire du Baccalauréat",
      releves_notes_superieur: "Relevés de notes des années d'études supérieures",
      cv: "Curriculum Vitæ (CV)",
      attestation_langue_francaise: "Attestation de test de français (TCF / DELF / DALF)",
      lettre_admission_dli: "Lettre d'admission d'un établissement désigné (EED / DLI)",
      attestation_provinciale_pal_caq: "Lettre d'attestation provinciale (LAP / PAL) ou CAQ Québec",
      preuve_financiere: "Preuve de ressources financières",
      formulaire_imm5645: "Formulaire d'informations sur la famille (IMM 5645)",
      lettre_explicative: "Lettre d'explication / Plan d'études"
    };

    const LIBELLES_CHAMPS_FR = {
      nom: "Nom de famille",
      prenom: "Prénom",
      sexe: "Sexe",
      date_naissance: "Date de naissance",
      lieu_naissance: "Lieu de naissance",
      nationalite: "Nationalité",
      pays_residence: "Pays de résidence",
      email: "Adresse e-mail",
      telephone: "Numéro de téléphone",
      numero_passeport: "Numéro de passeport",
      date_expiration_passeport: "Date d'expiration du passeport",
      niveau_actuel: "Niveau d'études actuel",
      programme_vise: "Formation / Programme visé",
      etablissement_vise: "Établissement visé",
      fonds_disponibles_eur: "Ressources financières disponibles (EUR)"
    };

    const LIBELLES_SOLIDITE_FR = {
      tres_solide: "Très solide",
      favorable: "Favorable",
      fragile: "Fragile (à consolider)",
      risque_eleve: "Risque élevé de refus",
      incomplet_ou_bloquant: "Dossier incomplet (pièces ou informations requises manquantes)"
    };

    const LIBELLES_STATUT_TACHE_FR = {
      en_attente: "En attente de lancement",
      en_cours: "En cours d'exécution par l'agent",
      suspendue: "En pause (intervention ou pièce requise)",
      a_valider: "Prêt pour validation humaine (arrêté avant soumission — Règle 1)",
      terminee: "Validé humainement et terminé",
      annulee: "Annulé",
      en_erreur: "En erreur"
    };

    function echapperHtml(str) {
      if (str === null || str === undefined) return "";
      return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    let minuteurNotification = null;
    function notifier(msg, ok = true) {
      const el = document.getElementById("zone-notification");
      el.textContent = msg;
      el.className = "notif " + (ok ? "notif-ok" : "notif-err");
      // Relance l'animation d'apparition à chaque nouveau message
      el.style.animation = "none";
      void el.offsetWidth;
      el.style.animation = "";
      clearTimeout(minuteurNotification);
      // Un succès se retire seul ; une erreur reste jusqu'au prochain message
      if (ok) minuteurNotification = setTimeout(() => el.classList.add("cache"), 6000);
    }

    function allerVersVue(cible) {
      document.querySelectorAll("aside button.nav-btn").forEach((b) => {
        b.classList.toggle("actif", b.getAttribute("data-vue") === cible);
      });
      document.querySelectorAll(".vue-ecran").forEach((s) => {
        s.classList.toggle("cache", s.id !== cible);
      });
      if (cible === "vue-conseiller" || cible === "vue-documents") chargerListeDemarches();
      if (cible === "vue-conseiller" || cible === "vue-procedures") chargerStatutIA();
      if (cible === "vue-documents" && candidatActifId) {
        chargerDocumentsCandidat();
        verifierCompletudeDossier();
      } else if (cible === "vue-conseiller" && candidatActifId) {
        chargerHistoriqueDiscussion();
      } else if (cible === "vue-validation-humaine") {
        rafraichirValidationsHumaines();
      } else if (cible === "vue-historique-erreurs") {
        rafraichirJournalAudit();
      } else if (cible === "vue-procedures") {
        chargerProcedures();
      } else if (cible === "vue-campus-france") {
        chargerVoeux();
      }
    }

    document.querySelectorAll("aside button.nav-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        allerVersVue(btn.getAttribute("data-vue"));
      });
    });

    async function appelApi(url, options = {}) {
      const headers = Object.assign({}, options.headers || {});
      if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
        headers["Content-Type"] = "application/json";
      }
      if (jetonCsrf) headers["X-CSRF-Token"] = jetonCsrf;
      return fetch(url, Object.assign({}, options, { headers }));
    }

    async function connecterOperateur(silencieux = false) {
      const email = document.getElementById("login-email").value.trim();
      const mot_de_passe = document.getElementById("login-mdp").value;
      const rep = await appelApi("/api/v1/auth/connexion", {
        method: "POST",
        body: JSON.stringify({ email, mot_de_passe }),
      });
      if (rep.ok) {
        const data = await rep.json();
        jetonCsrf = data.jeton_csrf;
        roleActif = data.utilisateur.role;
        const roleFr = data.utilisateur.role === "administrateur" ? "Administrateur du bureau" : "Employé";
        document.getElementById("etat-utilisateur").textContent =
          data.utilisateur.nom_affiche + " (" + roleFr + ")";
        document.getElementById("btn-se-deconnecter").classList.remove("cache");
        if (!silencieux) notifier("Session opérateur ouverte avec succès.", true);
        await chargerCandidats();
        await rafraichirTableauDeBord();
      } else {
        document.getElementById("etat-utilisateur").textContent = "Non connecté — cliquez sur Se connecter";
        if (!silencieux) {
          const err = await rep.json();
          notifier(err.detail || "Échec de connexion", false);
        }
      }
    }

    document.getElementById("btn-se-connecter").addEventListener("click", () => connecterOperateur(false));

    document.getElementById("btn-se-deconnecter").addEventListener("click", async () => {
      await appelApi("/api/v1/auth/deconnexion", { method: "POST" });
      jetonCsrf = "";
      document.getElementById("etat-utilisateur").textContent = "Non connecté";
      document.getElementById("btn-se-deconnecter").classList.add("cache");
      notifier("Session fermée.", true);
    });

    async function rafraichirTableauDeBord() {
      const [rCand, rVal, rAg] = await Promise.all([
        appelApi("/api/v1/candidats"),
        appelApi("/api/v1/validations/en-attente"),
        appelApi("/api/v1/agents-locaux"),
      ]);
      if (rCand.ok) {
        const c = await rCand.json();
        document.getElementById("stat-nb-candidats").textContent = c.total;
        (c.elements || []).forEach((cand) => {
          dictionnaireCandidats[cand.id] = cand;
        });
      }
      if (rVal.ok) {
        const v = await rVal.json();
        document.getElementById("stat-nb-a-valider").textContent = v.total_a_valider;
        document.getElementById("stat-nb-suspendues").textContent = v.total_suspendues;
      }
      if (rAg.ok) {
        const a = await rAg.json();
        document.getElementById("stat-nb-agents").textContent = a.length;
      }
    }

    async function chargerCandidats() {
      const q = document.getElementById("rech-candidat").value.trim();
      const url = q ? "/api/v1/candidats?recherche=" + encodeURIComponent(q) : "/api/v1/candidats";
      const rep = await appelApi(url);
      if (!rep.ok) return;
      const data = await rep.json();
      const tbody = document.querySelector("#table-candidats tbody");
      tbody.innerHTML = "";
      if (data.elements.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5">Aucun candidat enregistré pour le moment. Cliquez sur « Enregistrer le candidat » ci-dessus pour créer la première fiche.</td></tr>`;
        return;
      }
      data.elements.forEach((c) => {
        dictionnaireCandidats[c.id] = c;
        if (!candidatActifId) selectionnerCandidat(c, true);
        const tr = document.createElement("tr");
        const estActif = c.id === candidatActifId;
        tr.style.background = estActif ? "#eff6ff" : "";
        tr.innerHTML = `
          <td><strong>${echapperHtml(c.nom)} ${echapperHtml(c.prenom)}</strong><br/><small>${echapperHtml(c.email || "")}</small></td>
          <td>${echapperHtml(c.numero_passeport || "Non renseigné")}</td>
          <td>${echapperHtml(c.programme_vise || "-")}<br/><small>${echapperHtml(c.etablissement_vise || "-")}</small></td>
          <td><span class="badge ${c.consentement_signe ? 'badge-ok' : 'badge-warn'}">${c.consentement_signe ? "Signé (Loi 18-07)" : "À recueillir"}</span></td>
          <td>
            <button class="btn" type="button" data-sel="${c.id}">${estActif ? "Candidat actif" : "Sélectionner"}</button>
            <button class="btn btn-succes" type="button" data-cons="${c.id}">Valider Consentement</button>
          </td>
        `;
        tr.querySelector("[data-sel]").addEventListener("click", () => {
          selectionnerCandidat(c, false);
          chargerCandidats();
        });
        tr.querySelector("[data-cons]").addEventListener("click", async () => {
          const rCons = await appelApi(`/api/v1/candidats/${c.id}/consentement`, {
            method: "POST",
            body: JSON.stringify({ consentement_explicite: true, mode_recueil: "formulaire_signe_bureau" }),
          });
          if (rCons.ok) {
            notifier(`Consentement Loi 18-07 enregistré pour ${c.nom} ${c.prenom}.`, true);
            await chargerCandidats();
          }
        });
        tbody.appendChild(tr);
      });
    }

    function selectionnerCandidat(c, silencieux = false) {
      candidatActifId = c.id;
      candidatActifObj = c;
      dictionnaireCandidats[c.id] = c;
      document.getElementById("bandeau-candidat-actif").textContent =
        `${c.nom} ${c.prenom} (Passeport : ${c.numero_passeport || "non renseigné"})`;
      if (!silencieux) {
        notifier(`Dossier actif sélectionné : ${c.nom} ${c.prenom}`, true);
      }
    }

    function libelleCandidatParId(candId) {
      const c = dictionnaireCandidats[candId];
      if (!c) return "Candidat sélectionné";
      return `${c.nom} ${c.prenom} (Passeport : ${c.numero_passeport || "non renseigné"})`;
    }

    document.getElementById("btn-rechercher-candidat").addEventListener("click", chargerCandidats);

    document.getElementById("btn-creer-candidat").addEventListener("click", async () => {
      const payload = {
        nom: document.getElementById("cand-nom").value.trim(),
        prenom: document.getElementById("cand-prenom").value.trim(),
        sexe: document.getElementById("cand-sexe").value || null,
        date_naissance: document.getElementById("cand-dn").value || null,
        lieu_naissance: document.getElementById("cand-lieu").value.trim() || null,
        nationalite: document.getElementById("cand-nat").value.trim() || null,
        pays_residence: document.getElementById("cand-pays").value.trim() || null,
        email: document.getElementById("cand-email").value.trim() || null,
        telephone: document.getElementById("cand-tel").value.trim() || null,
        numero_passeport: document.getElementById("cand-pass").value.trim() || null,
        date_expiration_passeport: document.getElementById("cand-exp-pass").value || null,
        niveau_actuel: document.getElementById("cand-niveau").value.trim() || null,
        programme_vise: document.getElementById("cand-prog").value.trim() || null,
        etablissement_vise: document.getElementById("cand-etab").value.trim() || null,
        fonds_disponibles_eur: document.getElementById("cand-fonds").value
          ? parseInt(document.getElementById("cand-fonds").value, 10)
          : null,
      };
      const rep = await appelApi("/api/v1/candidats", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (rep.ok) {
        const c = await rep.json();
        selectionnerCandidat(c, false);
        await chargerCandidats();
        await rafraichirTableauDeBord();
        notifier(`Fiche candidat ${c.nom} ${c.prenom} créée et chiffrée avec succès.`, true);
      } else {
        const err = await rep.json();
        notifier(err.detail || "Erreur lors de la création du candidat", false);
      }
    });

    // -----------------------------------------------------------------------
    // Onglet 3 : Documents & Pièces manquantes (ZÉRO CODE / ZÉRO JSON)
    // -----------------------------------------------------------------------

    async function chargerDocumentsCandidat() {
      if (!candidatActifId) return;
      const rep = await appelApi(`/api/v1/candidats/${candidatActifId}/documents`);
      if (!rep.ok) return;
      const docs = await rep.json();
      const tbody = document.querySelector("#table-documents-candidat tbody");
      tbody.innerHTML = "";
      if (docs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5">Aucune pièce déposée pour ce candidat. Téléversez un fichier ci-dessus ou cliquez sur « Générer les pièces spécimens de démonstration ».</td></tr>`;
        return;
      }
      docs.forEach((d) => {
        const libellePiece = LIBELLES_PIECES_FR[d.type_piece] || d.type_piece;
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><strong>${echapperHtml(libellePiece)}</strong></td>
          <td>${echapperHtml(d.nom_fichier_origine)}</td>
          <td>${echapperHtml(d.date_expiration || "Non requise")}</td>
          <td>${Math.max(1, Math.round(d.taille_octets / 1024))} Ko</td>
          <td>
            <a href="/api/v1/candidats/${candidatActifId}/documents/${d.id}/telecharger" target="_blank"><button class="btn btn-contour" type="button">Télécharger</button></a>
            <button class="btn btn-danger" type="button" data-suppr="${d.id}">Supprimer</button>
          </td>
        `;
        tr.querySelector("[data-suppr]").addEventListener("click", async () => {
          const rDel = await appelApi(`/api/v1/candidats/${candidatActifId}/documents/${d.id}`, { method: "DELETE" });
          if (rDel.ok) {
            notifier("Pièce supprimée du dossier.", true);
            await chargerDocumentsCandidat();
            await verifierCompletudeDossier();
          }
        });
        tbody.appendChild(tr);
      });
    }

    function formaterCarteCompletude(comp) {
      if (!comp || !comp.pieces) return "";
      const piecesManquantes = comp.pieces.filter((p) => p.statut !== "valide" && p.obligatoire);
      const piecesFacultativesManquantes = comp.pieces.filter((p) => p.statut !== "valide" && !p.obligatoire);
      const piecesValides = comp.pieces.filter((p) => p.statut === "valide");
      const champsManquants = (comp.champs_candidat_manquants || []).map((ch) => LIBELLES_CHAMPS_FR[ch] || ch);

      let html = `<div class="carte" style="margin-bottom:0;">`;
      html += `<div style="display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:10px;">
        <h4 style="margin:0; font-size:1.02rem;">${echapperHtml(comp.libelle_demarche)}</h4>
        <span class="badge ${comp.pret_pour_prerequis ? 'badge-ok' : 'badge-err'}">
          ${comp.pret_pour_prerequis ? "Dossier complet" : "Pièces manquantes"}
        </span>
      </div>`;

      if (piecesManquantes.length === 0 && champsManquants.length === 0) {
        html += `<div class="notif notif-ok" style="margin-bottom:10px;">Toutes les pièces justificatives obligatoires et les informations du candidat sont complètes et valides.</div>`;
      } else {
        if (piecesManquantes.length > 0) {
          html += `<p style="margin:6px 0 4px 0; color:var(--rouge-danger); font-weight:700;">Pièces obligatoires manquantes ou à corriger (${piecesManquantes.length}) :</p><ul class="liste-propre">`;
          piecesManquantes.forEach((p) => {
            let precision = "";
            if (p.statut === "expiree") precision = " — Document expiré";
            else if (p.statut === "validite_insuffisante") precision = " — " + (p.detail || "Validité restante insuffisante");
            else if (p.statut === "expiration_non_renseignee") precision = " — Date d'expiration à renseigner";
            html += `<li><strong>${echapperHtml(p.libelle)}</strong>${echapperHtml(precision)}</li>`;
          });
          html += `</ul>`;
        }
        if (champsManquants.length > 0) {
          html += `<p style="margin:6px 0 4px 0; color:var(--orange-alerte); font-weight:700;">Informations à compléter dans la fiche candidat :</p><ul class="liste-propre">`;
          champsManquants.forEach((lib) => {
            html += `<li>${echapperHtml(lib)}</li>`;
          });
          html += `</ul>`;
        }
      }

      if (piecesValides.length > 0) {
        html += `<p style="margin:8px 0 4px 0; color:var(--vert-succes); font-weight:700;">Pièces déjà déposées et valides (${piecesValides.length}) :</p><ul class="liste-propre">`;
        piecesValides.forEach((p) => {
          const expTxt = p.date_expiration ? ` (valide jusqu'au ${p.date_expiration})` : "";
          html += `<li>✓ ${echapperHtml(p.libelle)}${echapperHtml(expTxt)}</li>`;
        });
        html += `</ul>`;
      }

      if (piecesFacultativesManquantes.length > 0) {
        html += `<p style="margin:8px 0 4px 0; color:var(--texte-secondaire); font-weight:600;">Pièces complémentaires recommandées (facultatives) :</p><ul class="liste-propre">`;
        piecesFacultativesManquantes.forEach((p) => {
          html += `<li>${echapperHtml(p.libelle)}</li>`;
        });
        html += `</ul>`;
      }

      html += `</div>`;
      return html;
    }

    async function verifierCompletudeDossier() {
      if (!candidatActifId) return notifier("Sélectionnez d'abord un candidat dans l'onglet 2.", false);
      await chargerListeDemarches();
      const reponses = await Promise.all(
        listeDemarches.map((d) => appelApi(`/api/v1/candidats/${candidatActifId}/completude/${encodeURIComponent(d.code)}`))
      );
      let cartes = "";
      for (const r of reponses) {
        const donnees = r.ok ? await r.json() : null;
        cartes += formaterCarteCompletude(donnees);
      }
      const zone = document.getElementById("zone-completude");
      zone.innerHTML = `<div class="grille-2">${cartes}</div>`;
    }

    document.getElementById("btn-televerser-doc").addEventListener("click", async () => {
      if (!candidatActifId) return notifier("Sélectionnez d'abord un candidat dans l'onglet 2.", false);
      const fichierInput = document.getElementById("doc-fichier");
      if (!fichierInput.files.length) return notifier("Choisissez un fichier PDF, PNG ou JPEG à téléverser.", false);
      const typePiece = document.getElementById("doc-type-piece").value;
      const fd = new FormData();
      fd.append("type_piece", typePiece);
      const exp = document.getElementById("doc-expiration").value;
      if (exp) fd.append("date_expiration", exp);
      fd.append("fichier", fichierInput.files[0]);
      const rep = await appelApi(`/api/v1/candidats/${candidatActifId}/documents`, {
        method: "POST",
        body: fd,
      });
      if (rep.ok) {
        const doc = await rep.json();
        const libellePiece = LIBELLES_PIECES_FR[doc.type_piece] || doc.type_piece;
        notifier(`Pièce « ${libellePiece} » chiffrée et enregistrée avec succès.`, true);
        await chargerDocumentsCandidat();
        await verifierCompletudeDossier();
      } else {
        const err = await rep.json();
        notifier(err.detail || "Refus lors du téléversement", false);
      }
    });

    document.getElementById("btn-verifier-completude").addEventListener("click", verifierCompletudeDossier);

    document.getElementById("btn-specimens-demo").addEventListener("click", async () => {
      if (!candidatActifId) return notifier("Sélectionnez d'abord un candidat dans l'onglet 2.", false);
      const rep = await appelApi(`/api/v1/candidats/${candidatActifId}/documents/specimens-demo`, {
        method: "POST",
      });
      if (rep.ok) {
        const crees = await rep.json();
        notifier(
          crees.length > 0
            ? `${crees.length} pièce(s) justificative(s) spécimen(s) générée(s) et chiffrée(s) pour ce candidat.`
            : "Toutes les pièces justificatives sont déjà présentes dans ce dossier.",
          true
        );
        await chargerDocumentsCandidat();
        await verifierCompletudeDossier();
      }
    });

    // -----------------------------------------------------------------------
    // Onglet 4 : Score d'acceptation & Discussion Conseiller (ZÉRO CODE)
    // -----------------------------------------------------------------------

    function afficherEvaluationEnTexte(data) {
      const score = data.pourcentage_acceptation_estime ?? 0;
      const libelleNiveau = LIBELLES_SOLIDITE_FR[data.niveau_solidite] || data.niveau_solidite;
      const couleurBarre = score >= 75 ? "#15803d" : score >= 50 ? "#d97706" : "#b91c1c";

      let html = `
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:10px;">
          <div>
            <h4 style="margin:0; font-size:1.1rem;">${echapperHtml(data.libelle_demarche)}</h4>
            <div style="color:var(--texte-secondaire); font-size:0.9rem; margin-top:2px;">
              Niveau du dossier : <strong>${echapperHtml(libelleNiveau)}</strong>
            </div>
          </div>
          <div style="text-align:right;">
            <span style="font-size:2rem; font-weight:800; color:${couleurBarre};">${score} %</span>
            <div style="font-size:0.8rem; color:var(--texte-secondaire);">Score d'acceptation estimé</div>
          </div>
        </div>
        <div class="barre-progression">
          <div class="barre-progression-remplie" style="width:${score}%; background:${couleurBarre};"></div>
        </div>
        <div class="banniere-regle" style="margin-top:12px;">
          <strong>Action prioritaire recommandée :</strong> ${echapperHtml(data.meilleure_action_recommandee)}
        </div>
      `;

      if (data.criteres && data.criteres.length > 0) {
        html += `<h4 style="margin:14px 0 8px 0;">Détail du calcul sur 100 points :</h4><ul class="liste-propre">`;
        data.criteres.forEach((c) => {
          html += `<li><strong>${echapperHtml(c.libelle)} : ${c.points_obtenus} / ${c.points_max} points</strong> — ${echapperHtml(c.commentaire)}</li>`;
        });
        html += `</ul>`;
      }

      if (data.risques_et_blocages && data.risques_et_blocages.length > 0) {
        html += `<h4 style="margin:14px 0 6px 0; color:var(--rouge-danger);">Points bloquants ou pièces manquantes à corriger :</h4><ul class="liste-propre">`;
        data.risques_et_blocages.forEach((r) => {
          html += `<li>${echapperHtml(r)}</li>`;
        });
        html += `</ul>`;
      }

      if (data.points_forts && data.points_forts.length > 0) {
        html += `<h4 style="margin:14px 0 6px 0; color:var(--vert-succes);">Points forts du dossier :</h4><ul class="liste-propre">`;
        data.points_forts.forEach((pf) => {
          html += `<li>✓ ${echapperHtml(pf)}</li>`;
        });
        html += `</ul>`;
      }

      if (data.actions_prioritaires && data.actions_prioritaires.length > 0) {
        html += `<h4 style="margin:14px 0 6px 0;">Plan d'action recommandé :</h4><ol class="liste-propre">`;
        data.actions_prioritaires.forEach((act) => {
          html += `<li>${echapperHtml(act)}</li>`;
        });
        html += `</ol>`;
      }

      if (data.veille_reglementaire && data.veille_reglementaire.length > 0) {
        html += `<h4 style="margin:14px 0 6px 0;">Règles officielles et prérequis applicables :</h4><ul class="liste-propre">`;
        data.veille_reglementaire.forEach((v) => {
          html += `<li><strong>${echapperHtml(v.titre)}</strong> (${echapperHtml(v.reference)}) : ${echapperHtml(v.resume)}</li>`;
        });
        html += `</ul>`;
      }

      html += `<p style="font-size:0.82rem; color:var(--texte-secondaire); margin-top:12px; margin-bottom:0;"><em>${echapperHtml(data.avertissement)}</em></p>`;
      document.getElementById("zone-score-acceptation").innerHTML = html;
    }

    document.getElementById("btn-calculer-score").addEventListener("click", async () => {
      if (!candidatActifId) return notifier("Sélectionnez d'abord un candidat dans l'onglet 2.", false);
      const dem = document.getElementById("eval-demarche").value;
      const rep = await appelApi(`/api/v1/candidats/${candidatActifId}/evaluation/${dem}`);
      if (rep.ok) {
        const data = await rep.json();
        afficherEvaluationEnTexte(data);
        const libelleNiveau = LIBELLES_SOLIDITE_FR[data.niveau_solidite] || data.niveau_solidite;
        notifier(`Score d'acceptation calculé : ${data.pourcentage_acceptation_estime} % (${libelleNiveau})`, true);
      } else {
        const err = await rep.json();
        notifier(err.detail || "Impossible de calculer le score", false);
      }
    });

    function formaterMessageDiscussionHtml(texteBrut) {
      const lignes = String(texteBrut || "").split("\\n");
      return lignes
        .map((l) => echapperHtml(l.replace(/^#+\\s*/, "").replace(/\\*\\*/g, "").replace(/`/g, "")))
        .join("<br/>");
    }

    function afficherListeMessagesDiscussion(messages) {
      const fil = document.getElementById("fil-discussion");
      if (!messages || messages.length === 0) {
        fil.innerHTML = `<div style="color:var(--texte-secondaire); font-size:0.9rem;">Aucun message dans cette discussion. Posez votre première question ci-dessous.</div>`;
        return;
      }
      fil.innerHTML = "";
      messages.forEach((m) => {
        const estUtilisateur = m.auteur === "utilisateur" || m.auteur === "operateur";
        const texteMsg = m.contenu || m.message || "";
        const scoreMsg = m.score_solidite_pourcent ?? m.score_instantane ?? "-";
        const div = document.createElement("div");
        div.className = "msg " + (estUtilisateur ? "msg-op" : "msg-ia");
        div.innerHTML =
          `<div style="margin-bottom:4px;"><strong>${estUtilisateur ? "Vous (Opérateur du bureau)" : "Assistant Conseiller Réglementaire"}</strong> ` +
          `<span class="badge">${scoreMsg} % d'acceptation</span></div>` +
          `<div>${formaterMessageDiscussionHtml(texteMsg)}</div>`;
        fil.appendChild(div);
      });
      fil.scrollTop = fil.scrollHeight;
    }

    async function chargerHistoriqueDiscussion() {
      if (!candidatActifId) return;
      const code_demarche = document.getElementById("eval-demarche").value;
      const rHisto = await appelApi(
        `/api/v1/candidats/${candidatActifId}/discussion?code_demarche=${encodeURIComponent(code_demarche)}`
      );
      if (rHisto.ok) {
        const messages = await rHisto.json();
        afficherListeMessagesDiscussion(messages);
      }
    }

    async function envoyerQuestionConseiller() {
      if (!candidatActifId) return notifier("Sélectionnez d'abord un candidat dans l'onglet 2.", false);
      const champMsg = document.getElementById("msg-discussion");
      const message = champMsg.value.trim();
      const code_demarche = document.getElementById("eval-demarche").value;
      if (message.length < 2) {
        return notifier("Veuillez saisir une question d'au moins 2 caractères.", false);
      }
      const btn = document.getElementById("btn-envoyer-discussion");
      btn.disabled = true;
      btn.textContent = "Analyse en cours...";
      try {
        const rep = await appelApi(`/api/v1/candidats/${candidatActifId}/discussion`, {
          method: "POST",
          body: JSON.stringify({ code_demarche, message }),
        });
        if (rep.ok) {
          const echange = await rep.json();
          if (echange.evaluation) {
            afficherEvaluationEnTexte(echange.evaluation);
          }
          await chargerHistoriqueDiscussion();
          notifier("Réponse du Conseiller ajoutée à la discussion.", true);
        } else {
          const err = await rep.json();
          notifier(err.detail || "Erreur lors de l'envoi de la question au Conseiller.", false);
        }
      } finally {
        btn.disabled = false;
        btn.textContent = "Envoyer au Conseiller";
      }
    }

    function poserQuestionRapide(texte) {
      document.getElementById("msg-discussion").value = texte;
      envoyerQuestionConseiller();
    }

    document.getElementById("btn-envoyer-discussion").addEventListener("click", envoyerQuestionConseiller);
    document.getElementById("eval-demarche").addEventListener("change", chargerHistoriqueDiscussion);

    // -----------------------------------------------------------------------
    // Onglets 5 & 6 : Campus France & IRCC — Pilotage Navigateur & Tâches
    // -----------------------------------------------------------------------

    function formaterCompteRenduPilotageHtml(res) {
      let html = `
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:10px;">
          <div>
            <strong style="font-size:1.05rem;">${echapperHtml(res.titre_page || "Navigateur de l'Agent")}</strong>
            <div style="font-size:0.84rem; color:var(--texte-secondaire);">Adresse ouverte : ${echapperHtml(res.url_courante)}</div>
          </div>
          <span class="badge ${res.succes ? 'badge-ok' : 'badge-warn'}">
            ${res.succes ? "Action exécutée par l'Agent" : "Intervention humaine requise"}
          </span>
        </div>
        <div class="notif ${res.succes ? 'notif-ok' : 'notif-err'}" style="margin-bottom:10px;">
          ${echapperHtml(res.resume_francais)}
        </div>
      `;

      if (res.statut_tache) {
        const libStatut = LIBELLES_STATUT_TACHE_FR[res.statut_tache] || res.statut_tache;
        const classeBadgeStatut = (res.statut_tache === "a_valider" || res.statut_tache === "terminee")
          ? "badge-ok"
          : (res.statut_tache === "suspendue" || res.statut_tache === "en_attente")
            ? "badge-warn"
            : "badge";
        html += `<p style="margin:6px 0;"><strong>Statut du dossier :</strong> <span class="badge ${classeBadgeStatut}">${echapperHtml(libStatut)}</span></p>`;
      }

      if (res.pieces_manquantes_tache && res.pieces_manquantes_tache.length > 0) {
        html += `<div class="banniere-regle" style="margin:8px 0;">
          <strong>Dossier en pause (pièces justificatives à téléverser avant passage au Centre de validation humaine) :</strong>
          <ul class="liste-propre" style="margin:6px 0;">
            ${res.pieces_manquantes_tache.map((tp) => `<li>${echapperHtml(LIBELLES_PIECES_FR[tp] || tp)}</li>`).join("")}
          </ul>
          <button class="btn btn-succes" type="button" onclick="completerPiecesSpecimensEtRelancer('${echapperHtml(res.code_demarche)}')">
            Déposer automatiquement les pièces spécimens de démo et lancer le pré-remplissage complet
          </button>
        </div>`;
      }

      if (res.etapes_realisees && res.etapes_realisees.length > 0) {
        html += `<p style="margin:8px 0 4px 0; font-weight:700;">Actions réalisées dans le navigateur :</p><ul class="liste-propre">`;
        res.etapes_realisees.forEach((et) => {
          html += `<li>✓ ${echapperHtml(et)}</li>`;
        });
        html += `</ul>`;
      }

      if (res.champs_remplis_libelles && res.champs_remplis_libelles.length > 0) {
        html += `<p style="margin:8px 0 4px 0; font-weight:700; color:var(--vert-succes);">Champs pré-remplis automatiquement (${res.champs_remplis_libelles.length}) :</p><ul class="liste-propre">`;
        res.champs_remplis_libelles.forEach((ch) => {
          html += `<li>✓ ${echapperHtml(ch)}</li>`;
        });
        html += `</ul>`;
      }

      if (res.pieces_televersees_libelles && res.pieces_televersees_libelles.length > 0) {
        html += `<p style="margin:8px 0 4px 0; font-weight:700; color:var(--vert-succes);">Pièces justificatives téléversées sur la page (${res.pieces_televersees_libelles.length}) :</p><ul class="liste-propre">`;
        res.pieces_televersees_libelles.forEach((p) => {
          html += `<li>✓ ${echapperHtml(p)}</li>`;
        });
        html += `</ul>`;
      }

      if (res.champs_manquants_libelles && res.champs_manquants_libelles.length > 0) {
        html += `<p style="margin:8px 0 4px 0; font-weight:700; color:var(--orange-alerte);">Informations non renseignées dans la fiche candidat (Règle 4 : aucune valeur inventée) :</p><ul class="liste-propre">`;
        res.champs_manquants_libelles.forEach((m) => {
          html += `<li>${echapperHtml(m)}</li>`;
        });
        html += `</ul>`;
      }

      if (res.avertissements_securite && res.avertissements_securite.length > 0) {
        html += `<p style="margin:8px 0 4px 0; font-weight:700;">Garde-fous de sécurité actifs :</p><ul class="liste-propre">`;
        res.avertissements_securite.forEach((av) => {
          html += `<li>${echapperHtml(av)}</li>`;
        });
        html += `</ul>`;
      }

      if (res.capture_base64) {
        html += `
          <div style="margin-top:12px;">
            <strong>Capture d'écran en direct du navigateur piloté par l'agent :</strong><br/>
            <img class="capture-apercu" src="data:image/png;base64,${res.capture_base64}" alt="Capture d'écran du navigateur" />
          </div>
        `;
      }
      return html;
    }

    async function lancerActionNavigateur(codeDemarche, action, instructionLibre = null) {
      if (!candidatActifId) {
        notifier("Sélectionnez d'abord un candidat dans l'onglet 2.", false);
        return;
      }
      const estCf = codeDemarche === "campus_france";
      const cible = document.getElementById(estCf ? "cf-cible-navigateur" : "ircc-cible-navigateur").value;
      const ouvrirVisible = document.getElementById(estCf ? "cf-fenetre-visible" : "ircc-fenetre-visible").checked;
      const zoneId = estCf ? "zone-retour-cf" : "zone-retour-ircc";
      const zone = document.getElementById(zoneId);

      zone.innerHTML = `<div style="font-weight:600; color:var(--bleu-primaire);">L'Agent Navigateur exécute votre demande dans Chromium... Veuillez patienter quelques secondes.</div>`;

      const rep = await appelApi("/api/v1/portails/piloter-navigateur", {
        method: "POST",
        body: JSON.stringify({
          candidat_id: candidatActifId,
          code_demarche: codeDemarche,
          cible: cible,
          action: action,
          instruction_libre: instructionLibre,
          ouvrir_fenetre_visible: ouvrirVisible,
          synchroniser_tache: true,
        }),
      });

      if (rep.ok) {
        const res = await rep.json();
        zone.innerHTML = formaterCompteRenduPilotageHtml(res);
        await rafraichirTableauDeBord();
        notifier(res.resume_francais, res.succes);
      } else {
        const err = await rep.json();
        zone.innerHTML = `<div class="notif notif-err">${echapperHtml(err.detail || "Erreur lors du pilotage du navigateur.")}</div>`;
        notifier(err.detail || "Erreur lors du pilotage du navigateur", false);
      }
    }

    document.getElementById("btn-piloter-cf-instruction").addEventListener("click", () => {
      const inst = document.getElementById("cf-instruction-agent").value.trim();
      lancerActionNavigateur("campus_france", "instruction_libre", inst);
    });

    document.getElementById("btn-piloter-ircc-instruction").addEventListener("click", () => {
      const inst = document.getElementById("ircc-instruction-agent").value.trim();
      lancerActionNavigateur("ircc_permis_etudes", "instruction_libre", inst);
    });

    function formaterTacheEnTexteHtml(tache, codeDemarche) {
      const libStatut = LIBELLES_STATUT_TACHE_FR[tache.statut] || tache.statut;
      const estSuspendue = tache.statut === "suspendue";
      const estAValider = tache.statut === "a_valider";

      let html = `
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:10px;">
          <div>
            <strong>Suivi de la tâche ${codeDemarche === "campus_france" ? "Campus France — Études en France" : "IRCC Canada — Permis d'études"}</strong>
          </div>
          <span class="badge ${estAValider ? 'badge-ok' : estSuspendue ? 'badge-warn' : 'badge'}">${echapperHtml(libStatut)}</span>
        </div>
      `;

      if (tache.message_alerte) {
        html += `<div class="banniere-regle">${echapperHtml(tache.message_alerte)}</div>`;
      }

      if (tache.pieces_manquantes && tache.pieces_manquantes.length > 0) {
        html += `<p style="margin:6px 0; color:var(--rouge-danger); font-weight:700;">Pièces justificatives obligatoires à fournir avant l'envoi officiel :</p><ul class="liste-propre">`;
        tache.pieces_manquantes.forEach((tp) => {
          html += `<li>${echapperHtml(LIBELLES_PIECES_FR[tp] || tp)}</li>`;
        });
        html += `</ul>`;
        html += `<p><button class="btn btn-succes" type="button" onclick="completerPiecesSpecimensEtRelancer('${codeDemarche}')">Déposer automatiquement les pièces spécimens de démo et lancer le pré-remplissage par l'Agent</button></p>`;
      }

      if (tache.champs_manquants && tache.champs_manquants.length > 0) {
        html += `<p style="margin:6px 0; color:var(--orange-alerte); font-weight:700;">Informations à compléter dans la fiche candidat :</p><ul class="liste-propre">`;
        tache.champs_manquants.forEach((ch) => {
          html += `<li>${echapperHtml(LIBELLES_CHAMPS_FR[ch] || ch)}</li>`;
        });
        html += `</ul>`;
      }

      if (tache.etapes && tache.etapes.length > 0) {
        html += `<p style="margin:10px 0 4px 0; font-weight:700;">Progression des étapes de la démarche :</p><ol class="liste-propre">`;
        tache.etapes.forEach((e) => {
          const icone = e.statut === "terminee" ? "✓" : e.statut === "en_cours" ? "⏳" : e.statut === "suspendue" ? "⏸" : "•";
          const stTxt = e.statut === "terminee" ? "Terminée" : e.statut === "en_cours" ? "En cours" : e.statut === "suspendue" ? "En attente de complétion" : "À faire";
          html += `<li>${icone} <strong>${echapperHtml(e.libelle)}</strong> — <em>${stTxt}</em></li>`;
        });
        html += `</ol>`;
      }

      return html;
    }

    async function completerPiecesSpecimensEtRelancer(codeDemarche) {
      if (!candidatActifId) return;
      await appelApi(`/api/v1/candidats/${candidatActifId}/documents/specimens-demo?code_demarche=${encodeURIComponent(codeDemarche)}`, {
        method: "POST",
      });
      await lancerActionNavigateur(codeDemarche, "preremplissage_complet");
    }

    async function creerOuAfficherTacheDemarche(codeDemarche) {
      if (!candidatActifId) return notifier("Sélectionnez d'abord un candidat dans l'onglet 2.", false);
      const zoneId = codeDemarche === "campus_france" ? "zone-retour-cf" : "zone-retour-ircc";
      const rep = await appelApi("/api/v1/taches", {
        method: "POST",
        body: JSON.stringify({ candidat_id: candidatActifId, code_demarche: codeDemarche }),
      });
      if (rep.ok) {
        const tache = await rep.json();
        document.getElementById(zoneId).innerHTML = formaterTacheEnTexteHtml(tache, codeDemarche);
        await rafraichirTableauDeBord();
        const libStatut = LIBELLES_STATUT_TACHE_FR[tache.statut] || tache.statut;
        notifier(`Tâche créée : ${libStatut}`, true);
      } else {
        // Si une tâche est déjà ouverte pour ce candidat, on la récupère et on l'affiche clairement
        const rListe = await appelApi(`/api/v1/taches?candidat_id=${candidatActifId}&code_demarche=${codeDemarche}`);
        if (rListe.ok) {
          const pageTaches = await rListe.json();
          if (pageTaches.elements && pageTaches.elements.length > 0) {
            const tacheExistante = pageTaches.elements[0];
            document.getElementById(zoneId).innerHTML = formaterTacheEnTexteHtml(tacheExistante, codeDemarche);
            notifier("Affichage de la tâche en cours pour ce candidat.", true);
            return;
          }
        }
        const err = await rep.json();
        notifier(err.detail || "Impossible de créer la tâche", false);
      }
    }

    document.getElementById("btn-creer-tache-cf").addEventListener("click", () => creerOuAfficherTacheDemarche("campus_france"));
    document.getElementById("btn-creer-tache-ircc").addEventListener("click", () => creerOuAfficherTacheDemarche("ircc_permis_etudes"));

    // -----------------------------------------------------------------------
    // Onglet 7 : Centre de validation humaine (Règle 1 — Cartes interactives)
    // -----------------------------------------------------------------------

    function formaterRecapitulatifValidationHtml(recap) {
      if (!recap || typeof recap !== "object") return "";
      let bloc = `<div class="panneau-texte" style="margin:8px 0;">`;
      if (recap.url_courante) {
        bloc += `<div style="font-size:0.86rem; color:var(--texte-secondaire); margin-bottom:6px;"><strong>Portail contrôlé :</strong> ${echapperHtml(recap.url_courante)}</div>`;
      }
      if (recap.champs_remplis && recap.champs_remplis.length > 0) {
        bloc += `<div style="margin:4px 0;"><strong style="color:var(--vert-succes);">Champs pré-remplis vérifiés (${recap.champs_remplis.length}) :</strong> ${recap.champs_remplis.map((c) => echapperHtml(c)).join(" • ")}</div>`;
      }
      if (recap.pieces_televersees && recap.pieces_televersees.length > 0) {
        bloc += `<div style="margin:4px 0;"><strong style="color:var(--vert-succes);">Pièces téléversées (${recap.pieces_televersees.length}) :</strong> ${recap.pieces_televersees.map((p) => echapperHtml(p)).join(" • ")}</div>`;
      }
      bloc += `</div>`;
      return bloc;
    }

    async function rafraichirValidationsHumaines() {
      if (Object.keys(dictionnaireCandidats).length === 0) {
        await chargerCandidats();
      }
      const rep = await appelApi("/api/v1/validations/en-attente");
      if (!rep.ok) return;
      const data = await rep.json();
      const zone = document.getElementById("liste-centre-validation");

      if (data.total_a_valider === 0 && data.total_suspendues === 0) {
        zone.innerHTML = `<div class="notif notif-ok" style="margin:0;">Aucun dossier en attente de validation ni en pause pour le moment.</div>`;
        return;
      }

      let html = "";

      if (data.taches_a_valider && data.taches_a_valider.length > 0) {
        html += `<h3 style="margin-top:0; color:var(--vert-succes);">Dossiers pré-remplis prêts pour validation humaine (${data.total_a_valider})</h3>`;
        data.taches_a_valider.forEach((t) => {
          const nomDem = t.code_demarche === "campus_france" ? "Campus France — Études en France" : "IRCC Canada — Permis d'études";
          const nomCand = libelleCandidatParId(t.candidat_id);
          html += `
            <div class="carte">
              <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                <div>
                  <strong>${echapperHtml(nomDem)}</strong>
                  <div style="font-size:0.86rem; color:var(--texte-secondaire);">Candidat : ${echapperHtml(nomCand)}</div>
                </div>
                <span class="badge badge-ok">En attente de validation humaine (Règle 1)</span>
              </div>
              <p style="margin:8px 0;">${echapperHtml(t.message_alerte || "Pré-remplissage terminé et arrêté avant le bouton final.")}</p>
              ${formaterRecapitulatifValidationHtml(t.recapitulatif_remplissage)}
              ${t.capture_controle_disponible ? `
                <div style="margin:10px 0;">
                  <div style="margin-bottom:6px;">
                    <a href="/api/v1/taches/${t.id}/capture-controle" target="_blank"><button class="btn btn-contour" type="button">Voir la capture d'écran de contrôle en plein écran</button></a>
                  </div>
                  <img class="capture-apercu" src="/api/v1/taches/${t.id}/capture-controle" alt="Capture d'écran de contrôle avant soumission" />
                </div>
              ` : ""}
              <div style="display:flex; gap:8px; flex-wrap:wrap; margin-top:8px;">
                <button class="btn btn-succes" type="button" onclick="validerDossierHumainement('${t.id}')">Confirmer et valider humainement ce dossier (Règle 1)</button>
                <button class="btn" type="button" onclick="rejeterValidationHumaine('${t.id}')">Demander une correction avant validation</button>
                <button class="btn btn-danger" type="button" onclick="annulerTacheDossier('${t.id}')">Annuler la tâche</button>
              </div>
            </div>
          `;
        });
      }

      if (data.taches_suspendues && data.taches_suspendues.length > 0) {
        html += `<h3 style="margin-top:14px; color:var(--orange-alerte);">Dossiers en pause (${data.total_suspendues})</h3>`;
        data.taches_suspendues.forEach((t) => {
          const nomDem = t.code_demarche === "campus_france" ? "Campus France — Études en France" : "IRCC Canada — Permis d'études";
          const nomCand = libelleCandidatParId(t.candidat_id);
          const piecesTxt = (t.pieces_manquantes || []).map((p) => LIBELLES_PIECES_FR[p] || p).join(", ");
          html += `
            <div class="carte">
              <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                <div>
                  <strong>${echapperHtml(nomDem)}</strong>
                  <div style="font-size:0.86rem; color:var(--texte-secondaire);">Candidat : ${echapperHtml(nomCand)}</div>
                </div>
                <span class="badge badge-warn">En pause</span>
              </div>
              <p style="margin:8px 0;">${echapperHtml(t.message_alerte || "")}</p>
              ${piecesTxt ? `<p style="margin:4px 0; color:var(--rouge-danger);"><strong>Pièces manquantes :</strong> ${echapperHtml(piecesTxt)}</p>` : ""}
              <div style="display:flex; gap:8px; flex-wrap:wrap; margin-top:8px;">
                ${piecesTxt ? `<button class="btn btn-succes" type="button" onclick="completerPiecesEtRelancerDepuisValidation('${t.id}', '${t.candidat_id}', '${t.code_demarche}')">Déposer les pièces spécimens de démo &amp; Pré-remplir par l'Agent</button>` : ""}
                ${t.motif_suspension === "action_utilisateur_portail" ? `<button class="btn btn-contour" type="button" onclick="allerVersVue('vue-navigateur-serveur')">Ouvrir le navigateur de l'agent (CAPTCHA / code de sécurité)</button>` : ""}
                <button class="btn" type="button" onclick="reprendreTacheDossier('${t.id}')">Reprendre la tâche</button>
                <button class="btn btn-danger" type="button" onclick="annulerTacheDossier('${t.id}')">Annuler la tâche</button>
              </div>
            </div>
          `;
        });
      }

      zone.innerHTML = html;
    }

    async function validerDossierHumainement(tacheId) {
      const rep = await appelApi(`/api/v1/taches/${tacheId}/valider`, {
        method: "POST",
        body: JSON.stringify({
          confirmation_humaine_explicite: true,
          commentaire: "Vérifié et validé par l'opérateur humain au Centre de validation.",
        }),
      });
      if (rep.ok) {
        notifier("Dossier validé humainement avec succès (Règle 1).", true);
        await rafraichirValidationsHumaines();
        await rafraichirTableauDeBord();
      } else {
        const err = await rep.json();
        notifier(err.detail || "Erreur lors de la validation", false);
      }
    }

    async function rejeterValidationHumaine(tacheId) {
      const rep = await appelApi(`/api/v1/taches/${tacheId}/rejeter`, {
        method: "POST",
        body: JSON.stringify({
          motif_rejet: "Correction demandée par l'opérateur humain avant la soumission finale.",
        }),
      });
      if (rep.ok) {
        notifier("Dossier remis en pause pour correction avant validation finale.", true);
        await rafraichirValidationsHumaines();
        await rafraichirTableauDeBord();
      } else {
        const err = await rep.json();
        notifier(err.detail || "Erreur lors du renvoi en correction", false);
      }
    }

    async function completerPiecesEtRelancerDepuisValidation(tacheId, candId, codeDemarche) {
      await appelApi(`/api/v1/candidats/${candId}/documents/specimens-demo?code_demarche=${encodeURIComponent(codeDemarche)}`, {
        method: "POST",
      });
      await appelApi(`/api/v1/portails/piloter-navigateur`, {
        method: "POST",
        body: JSON.stringify({
          candidat_id: candId,
          code_demarche: codeDemarche,
          cible: codeDemarche === "campus_france" ? "demo_campus_france" : "demo_ircc",
          action: "preremplissage_complet",
          ouvrir_fenetre_visible: false,
          synchroniser_tache: true,
        }),
      });
      notifier("Pièces spécimens déposées et dossier pré-rempli par l'Agent — prêt pour validation humaine !", true);
      await rafraichirValidationsHumaines();
      await rafraichirTableauDeBord();
    }

    async function reprendreTacheDossier(tacheId) {
      const rep = await appelApi(`/api/v1/taches/${tacheId}/reprendre`, { method: "POST" });
      if (rep.ok) {
        notifier("Tâche remise en file d'attente.", true);
        await rafraichirValidationsHumaines();
        await rafraichirTableauDeBord();
      } else {
        const err = await rep.json();
        notifier(err.detail || "Complétez d'abord les pièces manquantes avant de reprendre la tâche.", false);
      }
    }

    async function annulerTacheDossier(tacheId) {
      const rep = await appelApi(`/api/v1/taches/${tacheId}/annuler`, { method: "POST" });
      if (rep.ok) {
        notifier("Tâche annulée.", true);
        await rafraichirValidationsHumaines();
        await rafraichirTableauDeBord();
      }
    }

    document.getElementById("btn-rafraichir-validations").addEventListener("click", rafraichirValidationsHumaines);

    // -----------------------------------------------------------------------
    // Onglet 8 : Historique d'audit (ZÉRO CODE BRUT)
    // -----------------------------------------------------------------------

    async function rafraichirJournalAudit() {
      const rep = await appelApi("/api/v1/audit?taille=30");
      if (!rep.ok) return;
      const data = await rep.json();
      const tbody = document.querySelector("#table-audit tbody");
      tbody.innerHTML = "";
      data.elements.forEach((e) => {
        const detailsObj = e.details || {};
        const resumeDetails = Object.entries(detailsObj)
          .map(([k, v]) => `${k.replace(/_/g, " ")} : ${v}`)
          .join(" | ") || "Opération standard";
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><small>${echapperHtml(e.horodatage)}</small></td>
          <td><strong>${echapperHtml(e.action)}</strong></td>
          <td><span class="badge ${e.resultat === 'succes' ? 'badge-ok' : 'badge-err'}">${echapperHtml(e.resultat)}</span></td>
          <td>${echapperHtml(e.ressource_type || "-")}</td>
          <td>${echapperHtml(resumeDetails)}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    document.getElementById("btn-rafraichir-audit").addEventListener("click", rafraichirJournalAudit);

    // -----------------------------------------------------------------------
    // Onglet 9 : Paramètres, Agents locaux & Sauvegardes (ZÉRO CODE BRUT)
    // -----------------------------------------------------------------------

    document.getElementById("btn-enroler-agent").addEventListener("click", async () => {
      const nom_machine = document.getElementById("nom-machine-agent").value.trim();
      const rep = await appelApi("/api/v1/agents-locaux", {
        method: "POST",
        body: JSON.stringify({ nom_machine }),
      });
      if (rep.ok) {
        const data = await rep.json();
        const zone = document.getElementById("zone-jeton-agent");
        zone.innerHTML = `
          <div class="notif notif-ok" style="margin-bottom:8px;">Poste Agent Local « ${echapperHtml(data.agent.nom_machine)} » enrôlé avec succès.</div>
          <p style="margin:4px 0;"><strong>Clé d'authentification de l'Agent Local (à conserver précieusement) :</strong><br/>
          <input type="text" readonly value="${echapperHtml(data.jeton_secret)}" style="width:100%; margin-top:4px; font-weight:600;" /></p>
        `;
        zone.classList.remove("cache");
        await rafraichirTableauDeBord();
        notifier("Poste Agent Local enrôlé avec succès.", true);
      }
    });

    document.getElementById("btn-creer-sauvegarde").addEventListener("click", async () => {
      const rep = await appelApi("/api/v1/sauvegardes", { method: "POST" });
      const data = await rep.json();
      const zone = document.getElementById("zone-sauvegardes-abo");
      if (rep.ok) {
        zone.innerHTML = `
          <div class="notif notif-ok" style="margin-bottom:8px;">Sauvegarde chiffrée AES-256-GCM créée avec succès.</div>
          <ul class="liste-propre">
            <li><strong>Nom de l'archive chiffrée :</strong> ${echapperHtml(data.nom_fichier)}</li>
            <li><strong>Nombre de dossiers candidats sauvegardés :</strong> ${data.nb_candidats}</li>
            <li><strong>Nombre de pièces justificatives sauvegardées :</strong> ${data.nb_documents}</li>
            <li><strong>Taille de l'archive :</strong> ${Math.max(1, Math.round(data.taille_octets / 1024))} Ko</li>
          </ul>
        `;
        notifier(`Sauvegarde chiffrée créée : ${data.nom_fichier}`, true);
      } else {
        zone.innerHTML = `<div class="notif notif-err">${echapperHtml(data.detail || "Erreur lors de la sauvegarde")}</div>`;
      }
    });

    document.getElementById("btn-voir-abonnement").addEventListener("click", async () => {
      const [rAbo, rPort] = await Promise.all([
        appelApi("/api/v1/abonnement"),
        appelApi("/api/v1/portails"),
      ]);
      const abo = rAbo.ok ? await rAbo.json() : {};
      const portails = rPort.ok ? await rPort.json() : [];
      let html = `
        <h4 style="margin-top:0;">Abonnement SaaS du Bureau</h4>
        <ul class="liste-propre">
          <li><strong>Forfait actif :</strong> ${echapperHtml(abo.forfait || "Starter")}</li>
          <li><strong>Quota mensuel de dossiers :</strong> ${abo.nb_dossiers_actifs ?? 0} / ${abo.quota_dossiers_mensuels ?? 25} dossiers actifs</li>
          <li><strong>Durée de conservation RGPD / Loi 18-07 :</strong> ${abo.duree_conservation_jours ?? 365} jours</li>
        </ul>
        <h4>Statut des modules portails (Règle 6 &amp; Règle 7)</h4>
        <ul class="liste-propre">
      `;
      portails.forEach((p) => {
        html += `<li><strong>${echapperHtml(p.nom_portail)}</strong> — Statut d'homologation : <span class="badge">${echapperHtml(p.statut_test_regle6)}</span> (${p.nb_etapes_automatisation} étapes automatisées)</li>`;
      });
      html += `</ul>`;
      document.getElementById("zone-sauvegardes-abo").innerHTML = html;
    });

    // ===== Procédures (démarches) du bureau : liste + éditeur =====
    let procedureEditee = null; // code de la procédure modifiée, ou null en création
    let definitionOriginaleProcedure = null; // définition complète telle que reçue (pour ne rien perdre à l'enregistrement)
    const CLES_GEREES_PROCEDURE = ["code", "libelle", "description", "seuil_fonds_recommande_eur", "champs_candidat_requis", "pieces_requises", "etapes_tache", "veille_reglementaire"];

    function clesAvanceesProcedure(def) {
      return Object.keys(def || {}).filter((k) => !CLES_GEREES_PROCEDURE.includes(k));
    }

    function afficherChampsAvances(def) {
      const cles = clesAvanceesProcedure(def);
      const liste = document.getElementById("liste-champs-avances");
      liste.innerHTML = "";
      cles.forEach((k) => {
        const li = document.createElement("li");
        const fort = document.createElement("strong");
        fort.textContent = k;
        let apercu = "";
        try { apercu = JSON.stringify(def[k]); } catch (e) { apercu = ""; }
        if (apercu && apercu.length > 160) apercu = apercu.slice(0, 160) + "...";
        li.appendChild(fort);
        li.appendChild(document.createTextNode(apercu ? " : " + apercu : ""));
        liste.appendChild(li);
      });
      document.getElementById("encart-champs-avances").classList.toggle("cache", cles.length === 0);
    }

    function masquerBlocIaEditeur() {
      document.getElementById("bloc-ia-editeur").classList.add("cache");
      document.getElementById("liste-avertissements-ia").innerHTML = "";
    }

    function estAdministrateur() {
      return roleActif === "administrateur";
    }

    function messageErreurApi(err, defaut) {
      if (!err) return defaut;
      if (typeof err.detail === "string") return err.detail;
      if (Array.isArray(err.detail)) {
        return err.detail.map((e) => (e.loc ? e.loc.slice(1).join(" > ") + " : " : "") + e.msg).join(" ; ");
      }
      return err.message || defaut;
    }

    function retourProcedure(msg, ok) {
      const z = document.getElementById("zone-retour-procedure");
      z.textContent = msg;
      z.style.borderColor = ok ? "#16a34a" : "#dc2626";
      z.classList.remove("cache");
    }

    async function chargerProcedures() {
      const tbody = document.querySelector("#table-procedures tbody");
      document.getElementById("btn-nouvelle-procedure").classList.toggle("cache", !estAdministrateur());
      document.getElementById("carte-generation-ia").classList.toggle("cache", !estAdministrateur());
      const rep = await appelApi("/api/v1/demarches/gestion");
      if (!rep.ok) {
        tbody.innerHTML = `<tr><td colspan="5">Connectez-vous pour afficher les procédures.</td></tr>`;
        return;
      }
      const liste = await rep.json();
      tbody.innerHTML = "";
      if (liste.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5">Aucune procédure disponible.</td></tr>`;
        return;
      }
      liste.forEach((d) => {
        const tr = document.createElement("tr");
        const origine = d.source === "bureau"
          ? `<span class="badge badge-ok">Votre bureau</span>`
          : `<span class="badge">Base commune</span>`;
        tr.innerHTML = `
          <td><code>${echapperHtml(d.code)}</code></td>
          <td>${echapperHtml(d.libelle)}</td>
          <td>${origine}</td>
          <td>${d.source === "bureau" ? d.version : "-"}</td>
          <td></td>`;
        const cellule = tr.lastElementChild;
        const btnOuvrir = document.createElement("button");
        btnOuvrir.type = "button";
        btnOuvrir.className = "btn";
        btnOuvrir.textContent = estAdministrateur() ? "Modifier" : "Consulter";
        btnOuvrir.addEventListener("click", () => ouvrirEditeurProcedure(d.code));
        cellule.appendChild(btnOuvrir);
        if (estAdministrateur()) {
          const btnMasquer = document.createElement("button");
          btnMasquer.type = "button";
          btnMasquer.className = "btn btn-danger";
          btnMasquer.textContent = "Masquer";
          btnMasquer.addEventListener("click", () => masquerProcedure(d.code, d.libelle));
          cellule.appendChild(btnMasquer);
        }
        tbody.appendChild(tr);
      });
    }

    async function masquerProcedure(code, libelle) {
      if (!window.confirm("Masquer la procédure « " + libelle + " » pour votre bureau ? Les autres bureaux ne sont pas concernés. Vous pourrez la réactiver en la modifiant.")) return;
      const rep = await appelApi("/api/v1/demarches/" + encodeURIComponent(code), { method: "DELETE" });
      if (rep.ok) {
        notifier("Procédure masquée pour votre bureau.", true);
        fermerEditeurProcedure();
        await chargerProcedures();
      } else {
        const err = await rep.json().catch(() => null);
        notifier(messageErreurApi(err, "Impossible de masquer la procédure."), false);
      }
    }

    function creerLigne(contenuHtml) {
      const div = document.createElement("div");
      div.className = "ligne-proc";
      div.innerHTML = contenuHtml + `<button type="button" class="btn btn-danger" style="margin:0;" data-retirer="1">Retirer</button>`;
      div.querySelector("[data-retirer]").addEventListener("click", () => div.remove());
      return div;
    }

    function ajouterLignePiece(p) {
      const v = Object.assign({ type_piece: "", libelle: "", obligatoire: true, exige_date_expiration: false, validite_minimale_jours: 0 }, p || {});
      const div = creerLigne(`
        <input type="text" class="p-type" list="liste-types-pieces" placeholder="type (ex: passeport)" value="${echapperHtml(v.type_piece)}" />
        <input type="text" class="p-libelle large" placeholder="Libellé affiché (ex: Passeport en cours de validité)" value="${echapperHtml(v.libelle)}" />
        <label style="font-weight:400;"><input type="checkbox" class="p-oblig" ${v.obligatoire ? "checked" : ""} /> Obligatoire</label>
        <label style="font-weight:400;"><input type="checkbox" class="p-exp" ${v.exige_date_expiration ? "checked" : ""} /> Date d'expiration exigée</label>
        <input type="number" class="p-valid" min="0" style="max-width:150px;" title="Validité minimale restante (jours)" placeholder="Validité min. (jours)" value="${Number(v.validite_minimale_jours) || 0}" />`);
      document.getElementById("proc-pieces").appendChild(div);
    }

    function ajouterLigneEtape(e) {
      const v = Object.assign({ code: "", libelle: "" }, e || {});
      const div = creerLigne(`
        <input type="text" class="e-code" placeholder="code (ex: verification_prerequis)" value="${echapperHtml(v.code)}" />
        <input type="text" class="e-libelle large" placeholder="Libellé de l'étape" value="${echapperHtml(v.libelle)}" />`);
      document.getElementById("proc-etapes").appendChild(div);
    }

    function ajouterLigneVeille(p) {
      const v = Object.assign({ titre: "", resume: "", reference: "" }, p || {});
      const div = creerLigne(`
        <input type="text" class="v-titre" placeholder="Titre" value="${echapperHtml(v.titre)}" />
        <input type="text" class="v-resume large" placeholder="Résumé de la règle (1000 caractères max)" value="${echapperHtml(v.resume)}" />
        <input type="text" class="v-ref" placeholder="Référence officielle" value="${echapperHtml(v.reference)}" />`);
      document.getElementById("proc-veille").appendChild(div);
    }

    function construireCasesChamps(coches) {
      const zone = document.getElementById("proc-champs");
      zone.innerHTML = "";
      const tous = Object.keys(LIBELLES_CHAMPS_FR);
      coches.forEach((c) => { if (!tous.includes(c)) tous.push(c); });
      tous.forEach((cle) => {
        const lab = document.createElement("label");
        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.value = cle;
        cb.checked = coches.includes(cle);
        lab.appendChild(cb);
        lab.appendChild(document.createTextNode(" " + (LIBELLES_CHAMPS_FR[cle] || cle)));
        zone.appendChild(lab);
      });
    }

    function remplirEditeurProcedure(def) {
      definitionOriginaleProcedure = JSON.parse(JSON.stringify(def || {}));
      afficherChampsAvances(definitionOriginaleProcedure);
      document.getElementById("proc-code").value = def.code || "";
      document.getElementById("proc-code").disabled = procedureEditee !== null;
      document.getElementById("proc-libelle").value = def.libelle || "";
      document.getElementById("proc-description").value = def.description || "";
      document.getElementById("proc-seuil").value = def.seuil_fonds_recommande_eur === null || def.seuil_fonds_recommande_eur === undefined ? "" : def.seuil_fonds_recommande_eur;
      construireCasesChamps(def.champs_candidat_requis || []);
      const dl = document.getElementById("liste-types-pieces");
      dl.innerHTML = Object.keys(LIBELLES_PIECES_FR).map((k) => `<option value="${echapperHtml(k)}">${echapperHtml(LIBELLES_PIECES_FR[k])}</option>`).join("");
      document.getElementById("proc-pieces").innerHTML = "";
      (def.pieces_requises || []).forEach(ajouterLignePiece);
      document.getElementById("proc-etapes").innerHTML = "";
      (def.etapes_tache || []).forEach(ajouterLigneEtape);
      document.getElementById("proc-veille").innerHTML = "";
      (def.veille_reglementaire || []).forEach(ajouterLigneVeille);
    }

    function configurerEditeurSelonRole() {
      const admin = estAdministrateur();
      document.getElementById("fs-editeur").disabled = !admin;
      document.getElementById("btn-enregistrer-procedure").classList.toggle("cache", !admin);
      ["btn-ajouter-piece", "btn-ajouter-etape", "btn-ajouter-veille"].forEach((id) => {
        document.getElementById(id).classList.toggle("cache", !admin);
      });
    }

    async function ouvrirEditeurProcedure(code) {
      const rep = await appelApi("/api/v1/demarches/" + encodeURIComponent(code));
      if (!rep.ok) {
        const err = await rep.json().catch(() => null);
        notifier(messageErreurApi(err, "Procédure introuvable."), false);
        return;
      }
      const data = await rep.json();
      procedureEditee = code;
      masquerBlocIaEditeur();
      remplirEditeurProcedure(data.definition);
      configurerEditeurSelonRole();
      document.getElementById("titre-editeur-procedure").textContent =
        (estAdministrateur() ? "Modifier la procédure : " : "Consulter la procédure : ") + data.definition.libelle +
        (data.source === "base" ? " (base commune : l'enregistrement créera la version de votre bureau)" : " (version " + data.version + ")");
      document.getElementById("zone-retour-procedure").classList.add("cache");
      document.getElementById("carte-editeur-procedure").classList.remove("cache");
      document.getElementById("carte-editeur-procedure").scrollIntoView({ behavior: "smooth" });
    }

    function nouvelleProcedure() {
      procedureEditee = null;
      masquerBlocIaEditeur();
      remplirEditeurProcedure({ code: "", libelle: "", champs_candidat_requis: ["nom", "prenom", "numero_passeport"], pieces_requises: [{ type_piece: "passeport", libelle: "Passeport en cours de validité", obligatoire: true, exige_date_expiration: true, validite_minimale_jours: 180 }] });
      configurerEditeurSelonRole();
      document.getElementById("titre-editeur-procedure").textContent = "Nouvelle procédure";
      document.getElementById("zone-retour-procedure").classList.add("cache");
      document.getElementById("carte-editeur-procedure").classList.remove("cache");
      document.getElementById("carte-editeur-procedure").scrollIntoView({ behavior: "smooth" });
    }

    function fermerEditeurProcedure() {
      procedureEditee = null;
      definitionOriginaleProcedure = null;
      masquerBlocIaEditeur();
      document.getElementById("carte-editeur-procedure").classList.add("cache");
    }

    function collecterDefinitionProcedure() {
      const texte = (el, sel) => el.querySelector(sel).value.trim();
      const def = {
        code: document.getElementById("proc-code").value.trim().toLowerCase(),
        libelle: document.getElementById("proc-libelle").value.trim(),
        description: document.getElementById("proc-description").value.trim(),
        champs_candidat_requis: Array.from(document.querySelectorAll("#proc-champs input:checked")).map((c) => c.value),
        pieces_requises: Array.from(document.querySelectorAll("#proc-pieces .ligne-proc")).map((l) => ({
          type_piece: texte(l, ".p-type").toLowerCase(),
          libelle: texte(l, ".p-libelle"),
          obligatoire: l.querySelector(".p-oblig").checked,
          exige_date_expiration: l.querySelector(".p-exp").checked,
          validite_minimale_jours: parseInt(l.querySelector(".p-valid").value || "0", 10) || 0,
        })),
        veille_reglementaire: Array.from(document.querySelectorAll("#proc-veille .ligne-proc")).map((l) => ({
          titre: texte(l, ".v-titre"),
          resume: texte(l, ".v-resume"),
          reference: texte(l, ".v-ref"),
        })),
      };
      const seuil = document.getElementById("proc-seuil").value.trim();
      if (seuil !== "") def.seuil_fonds_recommande_eur = parseInt(seuil, 10);
      const etapes = Array.from(document.querySelectorAll("#proc-etapes .ligne-proc")).map((l) => ({
        code: texte(l, ".e-code").toLowerCase(),
        libelle: texte(l, ".e-libelle"),
      }));
      if (etapes.length > 0) def.etapes_tache = etapes;
      // Champs avancés non gérés par l'éditeur : conservés tels quels (jamais perdus à l'enregistrement)
      clesAvanceesProcedure(definitionOriginaleProcedure).forEach((k) => {
        if (!(k in def)) def[k] = JSON.parse(JSON.stringify(definitionOriginaleProcedure[k]));
      });
      return def;
    }

    async function enregistrerProcedure() {
      const def = collecterDefinitionProcedure();
      const enCreation = procedureEditee === null;
      const rep = await appelApi(
        enCreation ? "/api/v1/demarches" : "/api/v1/demarches/" + encodeURIComponent(procedureEditee),
        { method: enCreation ? "POST" : "PUT", body: JSON.stringify(def) }
      );
      if (rep.ok) {
        const data = await rep.json();
        procedureEditee = data.definition.code;
        definitionOriginaleProcedure = JSON.parse(JSON.stringify(data.definition));
        afficherChampsAvances(definitionOriginaleProcedure);
        masquerBlocIaEditeur();
        document.getElementById("proc-code").disabled = true;
        document.getElementById("titre-editeur-procedure").textContent =
          "Modifier la procédure : " + data.definition.libelle + " (version " + data.version + ")";
        retourProcedure("Procédure enregistrée (version " + data.version + "). Elle est utilisable immédiatement par votre bureau.", true);
        notifier("Procédure « " + data.definition.libelle + " » enregistrée.", true);
        await chargerProcedures();
      } else {
        const err = await rep.json().catch(() => null);
        retourProcedure(messageErreurApi(err, "Enregistrement refusé."), false);
      }
    }

    document.getElementById("btn-rafraichir-procedures").addEventListener("click", chargerProcedures);
    document.getElementById("btn-nouvelle-procedure").addEventListener("click", nouvelleProcedure);
    document.getElementById("btn-fermer-editeur-procedure").addEventListener("click", fermerEditeurProcedure);
    document.getElementById("btn-enregistrer-procedure").addEventListener("click", enregistrerProcedure);
    document.getElementById("btn-ajouter-piece").addEventListener("click", () => ajouterLignePiece());
    document.getElementById("btn-ajouter-etape").addEventListener("click", () => ajouterLigneEtape());
    document.getElementById("btn-ajouter-veille").addEventListener("click", () => ajouterLigneVeille());

    // ===== Assistant IA : état, génération de procédure, assistant du dossier, liste des démarches =====
    const TAILLE_MIN_TEXTE_IA = 80;
    const TAILLE_MAX_TEXTE_IA = 30000;

    function messageErreurIA(statut, err) {
      if (statut === 503) return "L'assistant IA n'est pas activé sur cette plateforme.";
      if (statut === 429) return "Le plafond mensuel de demandes à l'assistant IA est atteint pour votre bureau.";
      return messageErreurApi(err, "La demande à l'assistant IA a échoué.");
    }

    async function chargerStatutIA() {
      let texte = "Assistant IA : état indisponible";
      try {
        const rep = await appelApi("/api/v1/ia/statut");
        if (rep.ok) {
          const s = await rep.json();
          texte = s.active
            ? "Assistant IA : activé — " + s.appels_ce_mois + " / " + s.plafond_mensuel + " demandes ce mois"
            : "Assistant IA : non activé";
        }
      } catch (e) { /* état laissé à « indisponible » */ }
      ["ia-statut-procedures", "ia-statut-discussion"].forEach((id) => {
        document.getElementById(id).textContent = texte;
      });
    }

    function remplirSelectDemarches(idSelect) {
      const sel = document.getElementById(idSelect);
      const valeur = sel.value;
      sel.innerHTML = "";
      listeDemarches.forEach((d) => {
        const opt = document.createElement("option");
        opt.value = d.code;
        opt.textContent = d.libelle;
        sel.appendChild(opt);
      });
      if (listeDemarches.some((d) => d.code === valeur)) sel.value = valeur;
    }

    async function chargerListeDemarches() {
      try {
        const rep = await appelApi("/api/v1/demarches");
        if (rep.ok) {
          const liste = await rep.json();
          if (Array.isArray(liste) && liste.length > 0) {
            listeDemarches = liste.map((d) => ({ code: d.code, libelle: d.libelle || d.code }));
          }
        }
      } catch (e) { /* on garde la liste par défaut (Campus France, IRCC) */ }
      remplirSelectDemarches("eval-demarche");
      remplirSelectDemarches("ia-demarche-assistant");
    }

    function majCompteurTexteIA() {
      const n = document.getElementById("ia-texte-source").value.trim().length;
      const c = document.getElementById("ia-compteur-texte");
      c.textContent = n + " / 30 000 caractères (minimum 80)";
      c.classList.toggle("depasse", n > 0 && (n < TAILLE_MIN_TEXTE_IA || n > TAILLE_MAX_TEXTE_IA));
    }

    function retourGenerationIA(msg, ok) {
      const z = document.getElementById("zone-retour-generation-ia");
      z.textContent = msg;
      z.style.borderColor = ok ? "#16a34a" : "#dc2626";
      z.classList.remove("cache");
    }

    async function genererProcedureIA() {
      if (!estAdministrateur()) return notifier("Réservé aux administrateurs du bureau.", false);
      const texte = document.getElementById("ia-texte-source").value.trim();
      if (texte.length < TAILLE_MIN_TEXTE_IA || texte.length > TAILLE_MAX_TEXTE_IA) {
        return retourGenerationIA("Le texte doit contenir entre 80 et 30 000 caractères (actuellement " + texte.length + ").", false);
      }
      const btn = document.getElementById("btn-generer-procedure-ia");
      btn.disabled = true;
      btn.textContent = "Génération en cours...";
      try {
        const rep = await appelApi("/api/v1/ia/procedures/generer", { method: "POST", body: JSON.stringify({ texte }) });
        if (!rep.ok) {
          const err = await rep.json().catch(() => null);
          return retourGenerationIA(messageErreurIA(rep.status, err), false);
        }
        const data = await rep.json();
        procedureEditee = null;
        remplirEditeurProcedure(data.brouillon);
        configurerEditeurSelonRole();
        const liste = document.getElementById("liste-avertissements-ia");
        liste.innerHTML = "";
        (data.avertissements || []).forEach((a) => {
          const li = document.createElement("li");
          li.textContent = a;
          liste.appendChild(li);
        });
        document.getElementById("titre-avertissements-ia").classList.toggle("cache", liste.children.length === 0);
        document.getElementById("bloc-ia-editeur").classList.remove("cache");
        document.getElementById("titre-editeur-procedure").textContent = "Nouvelle procédure (brouillon généré par IA, non enregistré)";
        document.getElementById("zone-retour-procedure").classList.add("cache");
        document.getElementById("carte-editeur-procedure").classList.remove("cache");
        document.getElementById("carte-editeur-procedure").scrollIntoView({ behavior: "smooth" });
        retourGenerationIA("Brouillon généré. Relisez-le dans l'éditeur ci-dessous : rien n'est enregistré avant votre clic sur « Enregistrer la procédure ».", true);
        chargerStatutIA();
      } finally {
        btn.disabled = false;
        btn.textContent = "Générer un brouillon";
      }
    }

    function retourAssistantIA(msg, ok) {
      const z = document.getElementById("zone-reponse-assistant-ia");
      z.innerHTML = "";
      const p = document.createElement("div");
      p.textContent = msg;
      z.appendChild(p);
      z.style.borderColor = ok ? "#16a34a" : "#dc2626";
      z.classList.remove("cache");
    }

    async function demanderAssistantDossier() {
      if (!candidatActifId) {
        return retourAssistantIA("Aucun candidat n'est sélectionné. Choisissez d'abord un candidat dans l'onglet 2 : l'assistant répond dans le contexte de son dossier.", false);
      }
      const question = document.getElementById("ia-question-assistant").value.trim();
      const code_demarche = document.getElementById("ia-demarche-assistant").value;
      if (question.length < 1) return retourAssistantIA("Saisissez votre question.", false);
      const btn = document.getElementById("btn-demander-assistant-ia");
      btn.disabled = true;
      btn.textContent = "Analyse en cours...";
      try {
        const rep = await appelApi("/api/v1/ia/dossiers/" + encodeURIComponent(candidatActifId) + "/assistant", {
          method: "POST",
          body: JSON.stringify({ code_demarche, question }),
        });
        if (!rep.ok) {
          const err = await rep.json().catch(() => null);
          return retourAssistantIA(messageErreurIA(rep.status, err), false);
        }
        const data = await rep.json();
        const z = document.getElementById("zone-reponse-assistant-ia");
        z.innerHTML = "";
        const texte = document.createElement("div");
        texte.className = "ia-reponse";
        texte.textContent = data.reponse;
        const mention = document.createElement("div");
        mention.className = "ia-mention";
        mention.textContent = data.mention || "";
        z.appendChild(texte);
        z.appendChild(mention);
        z.style.borderColor = "#16a34a";
        z.classList.remove("cache");
        chargerStatutIA();
      } finally {
        btn.disabled = false;
        btn.textContent = "Demander";
      }
    }

    document.getElementById("ia-texte-source").addEventListener("input", majCompteurTexteIA);
    document.getElementById("btn-generer-procedure-ia").addEventListener("click", genererProcedureIA);
    document.getElementById("btn-demander-assistant-ia").addEventListener("click", demanderAssistantDossier);

    // ===== Vœux de formation et lettres de motivation =====
    const NL = String.fromCharCode(10);
    const MAX_MOTIVATION = 4000;
    const LIBELLES_STATUT_VOEU = { brouillon: "Brouillon à relire", valide: "Validé", ajoute_au_panier: "Dans le panier" };
    let alertesVoeux = {}; // points à vérifier renvoyés à la rédaction, par vœu

    function lignesDepuis(id) {
      return document.getElementById(id).value.split(NL).map((s) => s.trim()).filter((s) => s.length > 0);
    }

    function faitsDuParcours() {
      const projet = document.getElementById("faits-projet").value.trim();
      return {
        parcours: lignesDepuis("faits-parcours"),
        points_forts: lignesDepuis("faits-points"),
        langues: lignesDepuis("faits-langues"),
        projet: projet || null,
      };
    }

    function baseVoeux() {
      return "/api/v1/candidats/" + candidatActifId + "/voeux";
    }

    async function chargerVoeux() {
      const zone = document.getElementById("liste-voeux");
      document.getElementById("voeux-candidat-actif").textContent =
        candidatActifObj ? candidatActifObj.nom + " " + candidatActifObj.prenom : "Aucun";
      if (!candidatActifId) {
        zone.innerHTML = `<div class="panneau-texte">Sélectionnez un candidat (onglet 2) pour gérer ses vœux.</div>`;
        return;
      }
      const rep = await appelApi(baseVoeux());
      if (!rep.ok) {
        zone.innerHTML = `<div class="panneau-texte">Impossible de charger les vœux de ce candidat.</div>`;
        return;
      }
      const liste = await rep.json();
      document.getElementById("btn-ajouter-voeu").disabled = liste.length >= 7;
      zone.innerHTML = "";
      if (liste.length === 0) {
        zone.innerHTML = `<div class="panneau-texte">Aucun vœu pour le moment. Ajoutez une formation ci-dessus.</div>`;
        return;
      }
      liste.forEach((v) => zone.appendChild(construireCarteVoeu(v)));
    }

    function construireCarteVoeu(v) {
      const div = document.createElement("div");
      div.className = "voeu";
      const base = baseVoeux() + "/" + v.id;
      const enPanier = v.statut === "ajoute_au_panier";

      const entete = document.createElement("div");
      entete.className = "voeu-entete";
      const titre = document.createElement("div");
      const t = document.createElement("strong");
      t.textContent = v.rang + ". " + v.intitule;
      const sous = document.createElement("div");
      sous.style.fontSize = "0.86rem";
      sous.style.color = "var(--texte-secondaire)";
      sous.textContent = v.etablissement + " · " + v.niveau + (v.justification ? " · " + v.justification : "");
      titre.appendChild(t);
      titre.appendChild(sous);
      const badge = document.createElement("span");
      badge.className = "badge " + (v.statut === "brouillon" ? "badge-warn" : "badge-ok");
      badge.textContent = LIBELLES_STATUT_VOEU[v.statut] || v.statut;
      entete.appendChild(titre);
      entete.appendChild(badge);
      div.appendChild(entete);

      const alertes = alertesVoeux[v.id] || [];
      if (alertes.length > 0) {
        const ul = document.createElement("ul");
        ul.className = "voeu-alertes";
        alertes.forEach((a) => {
          const li = document.createElement("li");
          li.textContent = a;
          ul.appendChild(li);
        });
        div.appendChild(ul);
      }

      const ta = document.createElement("textarea");
      ta.value = v.motivation || "";
      ta.placeholder = "Rédigez la lettre ici, ou cliquez sur « Rédiger la lettre ».";
      ta.disabled = enPanier;
      const compteur = document.createElement("div");
      compteur.className = "voeu-compteur";
      const majCompteur = () => {
        const n = ta.value.length;
        compteur.textContent = n + " / " + MAX_MOTIVATION + " caractères";
        compteur.classList.toggle("depasse", n > MAX_MOTIVATION);
      };
      ta.addEventListener("input", majCompteur);
      majCompteur();
      div.appendChild(ta);
      div.appendChild(compteur);

      const ajouterBouton = (texte, classe, action) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "btn " + classe;
        b.textContent = texte;
        b.addEventListener("click", action);
        div.appendChild(b);
        return b;
      };

      if (!enPanier) {
        ajouterBouton("Rédiger la lettre", "", async () => {
          const rep = await appelApi(base + "/lettre/generer", { method: "POST", body: JSON.stringify(faitsDuParcours()) });
          const data = await rep.json().catch(() => null);
          if (!rep.ok) {
            notifier(messageErreurApi(data, "Rédaction impossible."), false);
            return;
          }
          alertesVoeux[v.id] = data.elements_a_verifier || [];
          notifier(
            data.origine === "ia"
              ? "Lettre rédigée par l'IA : relisez-la avant de valider."
              : "Lettre type générée (sans IA) : complétez les repères « À COMPLÉTER ».",
            true
          );
          await chargerVoeux();
        });
        ajouterBouton("Enregistrer mon texte", "btn-contour", async () => {
          const rep = await appelApi(base, { method: "PATCH", body: JSON.stringify({ motivation: ta.value }) });
          const data = await rep.json().catch(() => null);
          if (!rep.ok) {
            notifier(messageErreurApi(data, "Enregistrement refusé."), false);
            return;
          }
          notifier("Texte enregistré en brouillon.", true);
          await chargerVoeux();
        });
        if (v.statut === "brouillon") {
          ajouterBouton("Valider ce vœu", "btn-succes", async () => {
            const rep = await appelApi(base + "/valider", { method: "POST" });
            const data = await rep.json().catch(() => null);
            if (!rep.ok) {
              notifier(messageErreurApi(data, "Validation refusée."), false);
              return;
            }
            delete alertesVoeux[v.id];
            notifier("Vœu validé : il peut être ajouté au panier.", true);
            await chargerVoeux();
          });
        }
        ajouterBouton("Retirer", "btn-danger", async () => {
          if (!window.confirm("Retirer ce vœu de la liste ?")) return;
          const rep = await appelApi(base, { method: "DELETE" });
          if (!rep.ok) {
            const data = await rep.json().catch(() => null);
            notifier(messageErreurApi(data, "Suppression impossible."), false);
            return;
          }
          notifier("Vœu retiré.", true);
          await chargerVoeux();
        });
      }
      return div;
    }

    document.getElementById("btn-ajouter-voeu").addEventListener("click", async () => {
      if (!candidatActifId) {
        notifier("Sélectionnez d'abord un candidat dans l'onglet 2.", false);
        return;
      }
      const justification = document.getElementById("voeu-justification").value.trim();
      const corps = {
        intitule: document.getElementById("voeu-intitule").value.trim(),
        etablissement: document.getElementById("voeu-etablissement").value.trim(),
        niveau: document.getElementById("voeu-niveau").value,
        voie: document.getElementById("voeu-voie").value,
      };
      if (justification) corps.justification = justification;
      const rep = await appelApi(baseVoeux(), { method: "POST", body: JSON.stringify(corps) });
      const data = await rep.json().catch(() => null);
      if (!rep.ok) {
        notifier(messageErreurApi(data, "Ajout du vœu impossible."), false);
        return;
      }
      ["voeu-intitule", "voeu-etablissement", "voeu-justification"].forEach((id) => {
        document.getElementById(id).value = "";
      });
      notifier("Vœu ajouté. Rédigez maintenant sa lettre.", true);
      await chargerVoeux();
    });
    document.getElementById("btn-actualiser-voeux").addEventListener("click", chargerVoeux);

    // Connexion automatique dès l'ouverture de l'interface pour une prise en main immédiate
    window.addEventListener("DOMContentLoaded", () => {
      connecterOperateur(true);
    });
  </script>
</body>
</html>"""

# Ajoute le coffre d'identifiants (Règle 3) et les récapitulatifs à valider (Règle 1).
HTML_INTERFACE_FR = assembler_navigateur_serveur(assembler_interface(_HTML_INTERFACE_BASE))


@routeur_interface.get("/", response_class=HTMLResponse)
@routeur_interface.get("/interface", response_class=HTMLResponse)
def afficher_interface_francaise() -> HTMLResponse:
    return HTMLResponse(content=HTML_INTERFACE_FR)
