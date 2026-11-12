"""Vue opérateur du Co-Pilote navigateur en ligne : capture, contrôle humain, fermeture, état.

Réservé aux HUMAINS ADMINISTRATEUR / EMPLOYE du bureau courant (cookie de session + CSRF + blocage
d'abonnement, comme les autres routes) : les jetons d'agent local et le rôle LECTURE_SEULE sont refusés.

Quand le garde-fou Règle 2 (CAPTCHA / 2FA) a suspendu une tâche, ces routes sont le moyen pour l'HUMAIN
de résoudre le contrôle dans le navigateur du serveur. L'agent ne les utilise jamais.

Règle 5 : l'audit « navigateur.controle_humain » ne contient que le compte et le type d'action, JAMAIS le
texte saisi (code 2FA, mot de passe...) ni l'URL.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import ConfigDict, Field, model_validator

from app.agent_local.sessions_navigateur import (
    VIEWPORT_HAUTEUR,
    VIEWPORT_LARGEUR,
    RegistreSessionsNavigateur,
    etat_session_absente,
)
from app.api.dependances import ContexteAuth, exiger_roles, obtenir_registre_navigateur
from app.core.config import Parametres, obtenir_parametres
from app.core.erreurs import NonTrouve
from app.modeles.journal_audit import ResultatAudit
from app.modeles.utilisateur import Role
from app.schemas.commun import SchemaEntree
from app.services import audit

routeur = APIRouter(prefix="/navigateur", tags=["navigateur co-pilote (vue operateur)"])

ExigerOperateurHumain = Depends(exiger_roles(Role.ADMINISTRATEUR, Role.EMPLOYE))

TOUCHES_AUTORISEES: frozenset[str] = frozenset(
    {
        "Enter",
        "Tab",
        "Escape",
        "Backspace",
        "Delete",
        "ArrowUp",
        "ArrowDown",
        "ArrowLeft",
        "ArrowRight",
        "Home",
        "End",
        "PageUp",
        "PageDown",
    }
)
TEXTE_MAX_CARACTERES = 500
DEFILEMENT_MAX_PIXELS = 2000

TypeControle = Literal["clic", "texte", "touche", "defilement"]


class ControleHumainEntree(SchemaEntree):
    # Le texte saisi est transmis tel quel : pas de suppression d'espaces (mot de passe, code).
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    type: TypeControle
    x: int | None = Field(default=None, ge=0, lt=VIEWPORT_LARGEUR)
    y: int | None = Field(default=None, ge=0, lt=VIEWPORT_HAUTEUR)
    texte: str | None = Field(default=None, min_length=1, max_length=TEXTE_MAX_CARACTERES)
    touche: str | None = Field(default=None, max_length=20)
    delta_y: int | None = Field(default=None, ge=-DEFILEMENT_MAX_PIXELS, le=DEFILEMENT_MAX_PIXELS)

    @model_validator(mode="after")
    def _verifier_champs_selon_le_type(self) -> "ControleHumainEntree":
        if self.type == "clic":
            if self.x is None or self.y is None:
                raise ValueError("clic : x et y obligatoires")
        elif self.type == "texte":
            if not self.texte:
                raise ValueError("texte : texte obligatoire")
            if any(ord(c) < 32 or ord(c) == 127 for c in self.texte):
                raise ValueError("texte : caractères de contrôle interdits (utilisez le type touche)")
        elif self.type == "touche":
            if self.touche not in TOUCHES_AUTORISEES:
                raise ValueError("touche : hors liste blanche")
        elif self.type == "defilement":
            if self.delta_y is None:
                raise ValueError("defilement : delta_y obligatoire")
        return self


@routeur.get("/etat")
def obtenir_etat_navigateur(
    ctx: ContexteAuth = ExigerOperateurHumain,
    registre: RegistreSessionsNavigateur = Depends(obtenir_registre_navigateur),
) -> dict[str, Any]:
    """État de la session du bureau (URL sans paramètres, titre, contrôle CAPTCHA/2FA détecté,
    délai avant fermeture pour inactivité). Ne crée jamais de session et ne prolonge pas l'inactivité."""
    session = registre.existante(ctx.utilisateur.tenant_id)
    if session is None:
        return etat_session_absente()
    etat = session.gestionnaire.etat_operateur()
    return {
        "session_active": True,
        **etat,
        "mode_serveur": session.mode_serveur,
        "expire_dans_secondes": registre.secondes_avant_expiration(session),
        "viewport": {"largeur": VIEWPORT_LARGEUR, "hauteur": VIEWPORT_HAUTEUR},
    }


@routeur.get("/capture")
def capturer_page_navigateur(
    ctx: ContexteAuth = ExigerOperateurHumain,
    registre: RegistreSessionsNavigateur = Depends(obtenir_registre_navigateur),
) -> Response:
    """Capture JPEG (viewport 1280x900) de la page du bureau. 204 si aucune session ou page ouverte.
    Jamais mise en cache ni enregistrée."""
    entetes = {"Cache-Control": "no-store", "Pragma": "no-cache"}
    session = registre.existante(ctx.utilisateur.tenant_id)
    if session is None:
        return Response(status_code=204, headers=entetes)
    octets = session.gestionnaire.capturer_jpeg()
    if not octets:
        return Response(status_code=204, headers=entetes)
    return Response(content=octets, media_type="image/jpeg", headers=entetes)


@routeur.post("/controle")
def controler_navigateur_humain(
    donnees: ControleHumainEntree,
    ctx: ContexteAuth = ExigerOperateurHumain,
    registre: RegistreSessionsNavigateur = Depends(obtenir_registre_navigateur),
) -> dict[str, Any]:
    """Action d'un humain (clic, saisie, touche, défilement) dans le navigateur du bureau."""
    session = registre.existante(ctx.utilisateur.tenant_id)
    if session is None:
        raise NonTrouve("Aucun navigateur ouvert pour votre bureau.")
    registre.toucher(ctx.utilisateur.tenant_id)
    execute = session.gestionnaire.executer_controle_humain(
        type_action=donnees.type,
        x=donnees.x,
        y=donnees.y,
        texte=donnees.texte,
        touche=donnees.touche,
        delta_y=donnees.delta_y,
    )
    if not execute:
        raise NonTrouve("Aucune page ouverte dans le navigateur de votre bureau.")
    audit.journaliser(
        ctx.db,
        "navigateur.controle_humain",
        ResultatAudit.SUCCES,
        acteur_id=ctx.utilisateur.id,
        ressource_type="navigateur",
        details={"type_action": donnees.type},
    )
    ctx.db.commit()
    return {"succes": True, "type": donnees.type}


@routeur.post("/fermer")
def fermer_navigateur(
    effacer_profil: bool = False,
    ctx: ContexteAuth = ExigerOperateurHumain,
    registre: RegistreSessionsNavigateur = Depends(obtenir_registre_navigateur),
    parametres: Parametres = Depends(obtenir_parametres),
) -> dict[str, Any]:
    """Ferme le navigateur du bureau (idempotent). `effacer_profil=true` supprime aussi le profil
    (cookies de session des portails)."""
    tenant_id = ctx.utilisateur.tenant_id
    ferme = registre.existante(tenant_id) is not None
    if effacer_profil:
        registre.revoquer(tenant_id, parametres)
    else:
        registre.fermer(tenant_id)
    audit.journaliser(
        ctx.db,
        "navigateur.fermeture",
        ResultatAudit.SUCCES,
        acteur_id=ctx.utilisateur.id,
        ressource_type="navigateur",
        details={"session_fermee": ferme, "profil_efface": bool(effacer_profil)},
    )
    ctx.db.commit()
    return {"ferme": ferme}

