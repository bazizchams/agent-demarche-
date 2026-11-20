"""Assemblage de la page de base : coquille, écrans, puis JavaScript dans l'ordre historique.

Les modules `ecrans_coffre_validation` et `ecran_navigateur_serveur` complètent ensuite cette page
aux marqueurs `<!-- nav:... -->`, `<!-- zone:... -->`, `  </main>\\n\\n  <script>` (fin de zone
principale) et `// Connexion automatique` (fin du script).
"""

from __future__ import annotations

from app.interface.design.js_demarches import JS_DEMARCHES
from app.interface.design.js_dossiers import JS_DOSSIERS
from app.interface.design.js_ouverture_pc import JS_OUVERTURE_PC
from app.interface.design.js_procedures import JS_PROCEDURES
from app.interface.design.js_voeux import JS_VOEUX
from app.interface.design.motion import JS_MOUVEMENT
from app.interface.design.shell import JS_COQUILLE, html_debut, rendre_icones
from app.interface.design.tableau_bord import HTML_ACCUEIL, JS_ACCUEIL
from app.interface.design.vues_demarches import (
    HTML_AUDIT,
    HTML_CAMPUS_FRANCE,
    HTML_IRCC,
    HTML_PARAMETRES,
    HTML_PROCEDURES,
    HTML_VALIDATION,
)
from app.interface.design.vues_dossiers import HTML_CONSEILLER, HTML_DOCUMENTS, HTML_ETUDIANTS

JS_DEMARRAGE = """    // Connexion automatique dès l'ouverture de l'interface pour une prise en main immédiate
    // Un rechargement de la page garde la session : on la reprend (cookie valide) au lieu de redemander la connexion.
    async function reprendreSessionOuverte() {
      let data = null;
      try {
        const rep = await appelApi("/api/v1/auth/moi");
        data = rep.ok ? await rep.json() : null;
      } catch (e) { data = null; }
      if (!data || !data.utilisateur || !data.jeton_csrf) return false;
      jetonCsrf = data.jeton_csrf;
      roleActif = data.utilisateur.role;
      const roleFr = data.utilisateur.role === "administrateur" ? "Administrateur du bureau" : "Employé";
      document.getElementById("etat-utilisateur").textContent = data.utilisateur.nom_affiche + " (" + roleFr + ")";
      document.getElementById("btn-se-deconnecter").classList.remove("cache");
      majBandeauVerification(data.utilisateur);
      await chargerCandidats();
      await rafraichirTableauDeBord();
      return true;
    }

    window.addEventListener("DOMContentLoaded", async () => {
      if (!(await reprendreSessionOuverte())) connecterOperateur(true);
    });
"""

_ECRANS = (
    HTML_ACCUEIL,
    HTML_ETUDIANTS,
    HTML_DOCUMENTS,
    HTML_CONSEILLER,
    HTML_CAMPUS_FRANCE,
    HTML_IRCC,
    HTML_VALIDATION,
    HTML_AUDIT,
    HTML_PARAMETRES,
    HTML_PROCEDURES,
)


def construire_page_base() -> str:
    corps = rendre_icones(html_debut() + "".join(_ECRANS))
    js = (
        JS_MOUVEMENT
        + JS_DOSSIERS
        + JS_OUVERTURE_PC
        + JS_DEMARCHES
        + JS_PROCEDURES
        + JS_VOEUX
        + JS_ACCUEIL
        + JS_COQUILLE
        + JS_DEMARRAGE
    )
    return corps + "  </main>\n\n  <script>\n" + js + "  </script>\n</body>\n</html>"
