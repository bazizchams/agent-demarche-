"""Système de mouvement de l'interface : tokens, classes utilitaires et API JavaScript `Mouvement`.

Principes : sobre, premium, jamais gadget. Seuls `transform` et `opacity` s'animent (exceptions
documentées dans GUIDE_DESIGN.md : bascule de thème, compteur chiffré). Durées <= 700 ms, aucune
animation ne bloque la saisie, tout est no-op sous `prefers-reduced-motion: reduce`.

Amélioration progressive : `.mo-reveal` et les enfants de `.mo-stagger` ne sont masqués que si
`html.mo-actif` est posée (amorce `SCRIPT_MOUVEMENT_AMORCE` en <head>, puis `JS_MOUVEMENT`).
Sans JavaScript, ou en mouvement réduit, tout reste affiché.

Exports :
- `CSS_MOUVEMENT`  : déjà inclus dans `styles.CSS_DESIGN` (la coque et les pages publiques l'héritent) ;
- `SCRIPT_MOUVEMENT_AMORCE` : mini-script de <head> (pose `html.mo-actif` avant le premier rendu) ;
- `JS_MOUVEMENT`   : définit `window.Mouvement` (à placer avant tout autre script de la page).

Aucun antislash dans ces chaînes : les tests comptent les antislash de la page servie.
"""

from __future__ import annotations

SCRIPT_MOUVEMENT_AMORCE = """  <script>
    (function () {
      try {
        if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) document.documentElement.classList.add("mo-actif");
      } catch (e) { /* sans matchMedia : aucun masquage initial */ }
    })();
  </script>"""

CSS_MOUVEMENT = """
    /* ---------- Mouvement : tokens ---------- */
    @property --i { syntax: "<integer>"; inherits: false; initial-value: 0; }
    @property --mo-base { syntax: "<time>"; inherits: false; initial-value: 0ms; }
    :root {
      --mo-dur-1: 120ms; --mo-dur-2: 220ms; --mo-dur-3: 420ms; --mo-dur-4: 700ms;
      --mo-ease-out: cubic-bezier(.16, 1, .3, 1);
      --mo-ease-inout: cubic-bezier(.65, 0, .35, 1);
      --mo-ease-spring: cubic-bezier(.34, 1.25, .64, 1);
      --mo-pas: 45ms;
    }
    @supports (transition-timing-function: linear(0, 1)) {
      :root { --mo-ease-spring: linear(0, 0.1472 6.4%, 0.4806 12.9%, 0.7951 19.3%, 0.9827 25.7%, 1.0292 30%, 1.0378 34.3%, 1.0236 38.6%, 1.0022 42.9%, 0.9857 47.2%, 0.9803 51.5%, 0.9846 55.8%, 0.9929 60.1%, 1); }
    }

    /* ---------- Mouvement : apparition à l'entrée dans le viewport ---------- */
    @keyframes mo-entree { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } }
    html.mo-actif .mo-reveal:not(.mo-in), html.mo-actif .mo-stagger:not(.mo-in) > * { opacity: 0; }
    .mo-reveal.mo-in { animation: mo-entree var(--mo-dur-3) var(--mo-ease-out) backwards; animation-delay: calc(min(var(--i), 8) * var(--mo-pas)); }
    .mo-stagger.mo-in:not(.mo-fini) > *, .mo-casc { animation: mo-entree var(--mo-dur-3) var(--mo-ease-out) backwards; animation-delay: calc(var(--mo-base) + min(var(--i), 8) * var(--mo-pas)); }

    /* ---------- Mouvement : retour au clic et survol relevé ---------- */
    .mo-press, .btn, aside button.nav-btn, .raccourci, .onglet, .puce-cmd, .bouton-theme { -webkit-tap-highlight-color: transparent; }
    .mo-press { transition: transform var(--mo-dur-2) var(--mo-ease-spring); }
    .mo-press:active:not(:disabled), .btn:active:not(:disabled):not(.btn-lien), aside button.nav-btn:active, .raccourci:active, .bouton-theme:active { transform: scale(.97); transition-duration: var(--mo-dur-1); }
    @media (hover: hover) and (pointer: fine) {
      .mo-lift, .carte-cliquable, .raccourci { transition: transform var(--mo-dur-2) var(--mo-ease-out), box-shadow var(--mo-dur-2) var(--mo-ease-out), border-color var(--mo-dur-2) var(--mo-ease-out); }
      .mo-lift:hover, .carte-cliquable:hover, .raccourci:hover { transform: translateY(-2px); box-shadow: var(--ombre-2); border-color: var(--accent-moyen); }
      .mo-lift:active, .carte-cliquable:active, .raccourci:active { transform: translateY(0) scale(.99); }
    }

    /* ---------- Mouvement : squelette (miroitement par translation) et pouls ---------- */
    @keyframes mo-miroite { from { transform: translateX(-100%); } to { transform: translateX(100%); } }
    @keyframes mo-pouls-opacite { 0%, 100% { opacity: 1; } 50% { opacity: .45; } }
    .mo-skel, .squelette { position: relative; overflow: hidden; background-color: var(--surface-3); background-image: none; animation: none; }
    .mo-skel::after, .squelette::after { content: ""; position: absolute; inset: 0; background: linear-gradient(90deg, transparent 0, var(--miroitement) 50%, transparent 100%); transform: translateX(-100%); animation: mo-miroite 1.4s var(--mo-ease-inout) infinite; }
    .mo-pulse { animation: mo-pouls-opacite 2s var(--mo-ease-inout) infinite; }

    /* ---------- Coque : barre latérale (survol, pastille active qui glisse) ---------- */
    aside#navigation-principale nav { position: relative; }
    aside button.nav-btn .ico { transition: color var(--mo-dur-1) var(--mo-ease-out), transform var(--mo-dur-2) var(--mo-ease-out); }
    @media (hover: hover) and (pointer: fine) { aside button.nav-btn:hover .ico { transform: translateX(2px); } }
    .nav-pastille { position: absolute; left: 0; top: 0; width: 100%; height: var(--h-ctrl); border-radius: var(--r-m); background: var(--accent-doux); pointer-events: none; opacity: 0; transform: translateY(0); }
    .nav-pastille.mo-pret { opacity: 1; }
    .nav-pastille.mo-anim { transition: transform var(--mo-dur-3) var(--mo-ease-out); }
    html.mo-pastille aside button.nav-btn.actif { background: transparent; }
    html.mo-pastille aside button.nav-btn { z-index: 1; }

    /* ---------- Coque : tiroir mobile, modale, toasts ---------- */
    @media (max-width: 900px) {
      aside#navigation-principale { transition: transform var(--mo-dur-3) var(--mo-ease-out), visibility 0s linear var(--mo-dur-3); }
      body.nav-ouverte aside#navigation-principale { transition: transform var(--mo-dur-3) var(--mo-ease-out), visibility 0s; }
      body.nav-ouverte .scrim { animation: fondu var(--mo-dur-2) var(--mo-ease-out) both; }
    }
    dialog.modale[open]::backdrop { animation: fondu var(--mo-dur-2) var(--mo-ease-out) both; }
    @keyframes mo-toast-entree { from { opacity: 0; transform: translateX(18px) scale(.98); } to { opacity: 1; transform: none; } }
    @keyframes mo-toast-entree-bas { from { opacity: 0; transform: translateY(18px) scale(.98); } to { opacity: 1; transform: none; } }
    .toast { animation: mo-toast-entree var(--mo-dur-3) var(--mo-ease-spring) backwards; }
    @media (max-width: 900px) { .toast { animation-name: mo-toast-entree-bas; } }
    .toast.mo-sortie { animation: none !important; }

    /* ---------- Coque : bascule de thème (transition douce, classe temporaire) ---------- */
    html.mo-theme *, html.mo-theme *::before, html.mo-theme *::after {
      transition: background-color var(--mo-dur-3) var(--mo-ease-inout), color var(--mo-dur-3) var(--mo-ease-inout), border-color var(--mo-dur-3) var(--mo-ease-inout), fill var(--mo-dur-3) var(--mo-ease-inout), stroke var(--mo-dur-3) var(--mo-ease-inout), box-shadow var(--mo-dur-3) var(--mo-ease-inout);
    }

    /* ---------- Coque : entrée des écrans (pilotée par Mouvement.transitionVue) et connexion ---------- */
    .vue-ecran:not(.cache) { animation: none; }

    /* ---------- Sans mouvement : tout est affiché immédiatement ---------- */
    @media (prefers-reduced-motion: reduce) {
      .mo-reveal, .mo-stagger > *, .mo-casc, .toast { opacity: 1 !important; transform: none !important; animation: none !important; }
      .mo-skel::after, .squelette::after, .mo-pulse, body.nav-ouverte .scrim, dialog.modale[open]::backdrop { animation: none !important; }
      .mo-skel::after, .squelette::after { display: none; }
      .nav-pastille, .nav-pastille.mo-anim, html.mo-theme *, html.mo-theme *::before, html.mo-theme *::after { transition: none !important; }
      .mo-press:active:not(:disabled), .btn:active:not(:disabled), aside button.nav-btn:active, .raccourci:active, .bouton-theme:active, .mo-lift:hover, .mo-lift:active, .carte-cliquable:hover, .raccourci:hover, aside button.nav-btn:hover .ico { transform: none !important; }
    }
    @media print { .mo-reveal, .mo-stagger > * { opacity: 1 !important; animation: none !important; } }
"""

JS_MOUVEMENT = """
    // ===== Mouvement : API d'animation sobre (CSS + WAAPI), no-op en mouvement réduit =====
    // Contrat : window.Mouvement = { reduit, reveler, cascade, compteur, transitionVue, pret } (+ sortie, basculerTheme).
    // Transform et opacité seulement ; durées <= 700 ms ; jamais d'attente bloquante sur la saisie.
    (function () {
      const DUREES = { d1: 120, d2: 220, d3: 420, d4: 700 };
      const COURBE_SORTIE = "cubic-bezier(0.16, 1, 0.3, 1)";
      const COURBE_FUITE = "cubic-bezier(0.7, 0, 0.84, 0)";
      const PAS_MS = 45;
      const CASCADE_MAX = 8;
      const FIN_CASCADE_MS = 1600;
      const SELECTEUR_REVEL = ".mo-reveal, .mo-stagger";
      const racine = document.documentElement;
      const mqReduit = window.matchMedia("(prefers-reduced-motion: reduce)");
      const vus = new WeakSet();
      const suiviCompteur = new WeakMap();
      let observateur = null;
      let animationVue = null;
      let minuteurTheme = null;

      function reduit() { return !!mqReduit.matches; }

      function numeroter(liste) {
        Array.from(liste).forEach((el, i) => {
          if (el.style && el.style.getPropertyValue("--i") === "") el.style.setProperty("--i", String(i));
        });
      }

      function marquer(el) {
        if (el.classList.contains("mo-in")) return;
        const cascade = el.classList.contains("mo-stagger");
        if (cascade) numeroter(el.children);
        el.classList.add("mo-in");
        if (cascade) setTimeout(() => el.classList.add("mo-fini"), FIN_CASCADE_MS);
      }

      function creerObservateur() {
        if (typeof IntersectionObserver !== "function") return null;
        return new IntersectionObserver((entrees) => {
          entrees.forEach((entree) => {
            if (!entree.isIntersecting) return;
            observateur.unobserve(entree.target);
            marquer(entree.target);
          });
        }, { rootMargin: "0px 0px -6% 0px", threshold: 0 });
      }

      function reveler(zone) {
        const base = zone || document;
        if (!base.querySelectorAll) return;
        const liste = Array.from(base.querySelectorAll(SELECTEUR_REVEL));
        if (base.matches && base.matches(SELECTEUR_REVEL)) liste.unshift(base);
        liste.forEach((el) => {
          if (el.classList.contains("mo-in") || vus.has(el)) return;
          if (reduit() || !observateur) { marquer(el); return; }
          vus.add(el);
          observateur.observe(el);
        });
      }

      function cascade(liste) {
        if (!liste || reduit()) return;
        Array.from(liste).forEach((el, i) => {
          if (!el || !el.classList) return;
          el.style.setProperty("--i", String(i));
          el.classList.add("mo-casc");
          const retirer = () => { el.classList.remove("mo-casc"); el.style.removeProperty("--i"); };
          el.addEventListener("animationend", (e) => { if (e.target === el) retirer(); }, { once: true });
          setTimeout(retirer, FIN_CASCADE_MS);
        });
      }

      function compteur(el, valeur, ms) {
        if (!el) return;
        const precedent = suiviCompteur.get(el);
        if (precedent) { cancelAnimationFrame(precedent.raf); clearTimeout(precedent.garde); suiviCompteur.delete(el); }
        const cible = Number(valeur);
        if (!Number.isFinite(cible)) { el.textContent = String(valeur); return; }
        const duree = Math.min(Math.max(Number(ms) || DUREES.d4, 0), DUREES.d4);
        if (reduit() || duree === 0) { el.textContent = String(cible); return; }
        const lu = parseFloat(el.textContent);
        const depart = Number.isFinite(lu) ? lu : 0;
        const entier = Number.isInteger(cible);
        const ecrire = (v) => { el.textContent = String(entier ? Math.round(v) : Math.round(v * 10) / 10); };
        const t0 = performance.now();
        const suivi = { raf: 0, garde: 0 };
        const image = (maintenant) => {
          const t = Math.min(1, (maintenant - t0) / duree);
          ecrire(depart + (cible - depart) * (1 - Math.pow(1 - t, 3)));
          if (t < 1) suivi.raf = requestAnimationFrame(image);
          else suiviCompteur.delete(el);
        };
        suivi.garde = setTimeout(() => { cancelAnimationFrame(suivi.raf); el.textContent = String(cible); suiviCompteur.delete(el); }, duree + 120);
        suivi.raf = requestAnimationFrame(image);
        suiviCompteur.set(el, suivi);
      }

      // Entrée d'un écran : fondu + glissement court. L'ancien écran est déjà masqué (pas de sortie).
      // Le focus et le titre sont gérés par l'appelant, de façon synchrone : rien n'attend l'animation.
      function transitionVue(avant, apres) {
        if (animationVue) { animationVue.cancel(); animationVue = null; }
        if (reduit() || !apres || typeof apres.animate !== "function") return Promise.resolve();
        const anim = apres.animate(
          [{ opacity: 0, transform: "translateY(10px)" }, { opacity: 1, transform: "none" }],
          { duration: DUREES.d2, easing: COURBE_SORTIE, fill: "backwards" });
        animationVue = anim;
        return anim.finished.then(() => { if (animationVue === anim) animationVue = null; }, () => {});
      }

      // Sortie d'un élément (toast) : le nœud réel est retiré tout de suite (état du DOM immédiat) ;
      // un fantôme inerte, caché des lecteurs d'écran, joue la sortie puis disparaît.
      function sortie(el) {
        if (!el || !el.parentNode) return;
        if (reduit() || typeof el.animate !== "function") { el.remove(); return; }
        const r = el.getBoundingClientRect();
        const fantome = el.cloneNode(true);
        fantome.removeAttribute("id");
        fantome.setAttribute("aria-hidden", "true");
        fantome.inert = true;
        fantome.classList.add("mo-sortie");
        Object.assign(fantome.style, {
          position: "fixed", left: r.left + "px", top: r.top + "px", width: r.width + "px",
          right: "auto", bottom: "auto", margin: "0", pointerEvents: "none", zIndex: "35"
        });
        el.remove();
        document.body.appendChild(fantome);
        const fin = () => fantome.remove();
        const anim = fantome.animate(
          [{ opacity: 1, transform: "none" }, { opacity: 0, transform: "translateY(-6px) scale(0.98)" }],
          { duration: DUREES.d2, easing: COURBE_FUITE, fill: "forwards" });
        anim.finished.then(fin, fin);
      }

      // Bascule de thème : `appliquer` s'exécute tout de suite ; une classe temporaire adoucit les couleurs.
      function basculerTheme(appliquer) {
        if (reduit()) { appliquer(); return; }
        racine.classList.add("mo-theme");
        appliquer();
        clearTimeout(minuteurTheme);
        minuteurTheme = setTimeout(() => racine.classList.remove("mo-theme"), DUREES.d3 + 80);
      }

      // Barre latérale : une pastille unique glisse jusqu'au bouton actif (translation seulement).
      function initPastilleNav() {
        const nav = document.querySelector("aside#navigation-principale nav");
        if (!nav) return;
        const pastille = document.createElement("span");
        pastille.className = "nav-pastille";
        pastille.setAttribute("aria-hidden", "true");
        nav.insertBefore(pastille, nav.firstChild);
        function placer(animer) {
          const actif = nav.querySelector("button.nav-btn.actif");
          const rn = nav.getBoundingClientRect();
          const ra = actif ? actif.getBoundingClientRect() : null;
          if (!ra || ra.height === 0 || rn.width === 0) { pastille.classList.remove("mo-pret"); racine.classList.remove("mo-pastille"); return; }
          pastille.classList.toggle("mo-anim", !!animer && !reduit() && pastille.classList.contains("mo-pret"));
          pastille.style.height = ra.height + "px";
          pastille.style.transform = "translateY(" + (ra.top - rn.top) + "px)";
          pastille.classList.add("mo-pret");
          racine.classList.add("mo-pastille");
        }
        new MutationObserver((mutations) => {
          if (mutations.some((m) => m.target !== pastille)) placer(true);
        }).observe(nav, { attributes: true, attributeFilter: ["class"], subtree: true });
        if (typeof ResizeObserver === "function") new ResizeObserver(() => placer(false)).observe(nav);
        window.addEventListener("load", () => placer(false));
        placer(false);
      }

      // Éléments .mo-reveal / .mo-stagger ajoutés plus tard par les écrans : pris en charge automatiquement.
      function surveillerAjouts() {
        new MutationObserver((mutations) => {
          mutations.forEach((m) => {
            m.addedNodes.forEach((n) => {
              if (n.nodeType !== 1) return;
              if (n.matches(SELECTEUR_REVEL) || n.querySelector(SELECTEUR_REVEL)) reveler(n);
            });
          });
        }).observe(document.body, { childList: true, subtree: true });
      }

      function majActif() { racine.classList.toggle("mo-actif", !reduit()); }

      const pret = new Promise((resoudre) => {
        function demarrer() {
          majActif();
          observateur = creerObservateur();
          reveler(document);
          surveillerAjouts();
          initPastilleNav();
          const polices = document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve();
          Promise.race([polices, new Promise((r) => setTimeout(r, 800))]).then(() => resoudre(true), () => resoudre(true));
        }
        if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", demarrer, { once: true });
        else demarrer();
      });

      mqReduit.addEventListener("change", () => { majActif(); reveler(document); });

      window.Mouvement = Object.freeze({ reduit, reveler, cascade, compteur, transitionVue, sortie, basculerTheme, pret });
    })();

"""
