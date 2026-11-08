"""Dépendances FastAPI : session de base de données, authentification, CSRF et rôles."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Parametres, obtenir_parametres
from app.core.erreurs import AccesRefuse, NonAuthentifie
from app.core.securite import comparer_constant
from app.modeles.agent_local import AgentLocal
from app.modeles.journal_audit import ResultatAudit
from app.modeles.session_utilisateur import SessionUtilisateur
from app.modeles.utilisateur import Role, Utilisateur
from app.services import agents_locaux as service_agents
from app.services import audit
from app.services.auth import verifier_et_rafraichir_session

EN_TETE_CSRF = "X-CSRF-Token"
EN_TETE_JETON_AGENT = "X-Agent-Token"
METHODES_MUTANTES = {"POST", "PUT", "PATCH", "DELETE"}


def obtenir_db(requete: Request) -> Iterator[Session]:
    fabrique = requete.app.state.fabrique_sessions
    session: Session = fabrique()
    try:
        yield session
    finally:
        session.close()


def obtenir_cle_maitresse(requete: Request) -> bytes:
    return requete.app.state.cle_maitresse


@dataclass(frozen=True)
class ContexteAuth:
    utilisateur: Utilisateur
    session: SessionUtilisateur
    db: Session


def obtenir_contexte_auth_brut(
    requete: Request,
    db: Session = Depends(obtenir_db),
    parametres: Parametres = Depends(obtenir_parametres),
) -> ContexteAuth:
    """Authentifie la requête par cookie de session, fixe le bureau (tenant) sur la
    session SQLAlchemy et vérifie le jeton CSRF pour toute méthode modifiant l'état."""
    jeton = requete.cookies.get(parametres.nom_cookie_session)
    if not jeton:
        raise NonAuthentifie("Authentification requise.")

    session_obj, utilisateur = verifier_et_rafraichir_session(
        db, jeton_clair=jeton, parametres=parametres
    )

    if requete.method.upper() in METHODES_MUTANTES:
        csrf_recu = requete.headers.get(EN_TETE_CSRF, "")
        if not csrf_recu or not comparer_constant(csrf_recu, session_obj.jeton_csrf):
            audit.journaliser(
                db,
                "securite.csrf_invalide",
                ResultatAudit.REFUS,
                acteur_id=utilisateur.id,
                ressource_type="session",
                ressource_id=session_obj.id,
            )
            db.commit()
            raise AccesRefuse("Jeton de protection CSRF manquant ou invalide.")

    return ContexteAuth(utilisateur=utilisateur, session=session_obj, db=db)


def obtenir_contexte_auth(
    ctx: ContexteAuth = Depends(obtenir_contexte_auth_brut),
) -> ContexteAuth:
    """Comme `obtenir_contexte_auth_brut`, mais bloque toute action tant que
    l'utilisateur n'a pas changé son mot de passe temporaire."""
    if ctx.utilisateur.doit_changer_mot_de_passe:
        raise AccesRefuse(
            "Changement du mot de passe temporaire obligatoire avant toute autre opération."
        )
    return ctx


def exiger_roles(*roles_autorises: Role) -> Callable[[ContexteAuth], ContexteAuth]:
    ensemble = set(roles_autorises)

    def _verifier(ctx: ContexteAuth = Depends(obtenir_contexte_auth)) -> ContexteAuth:
        if ctx.utilisateur.role not in ensemble:
            audit.journaliser(
                ctx.db,
                "securite.role_insuffisant",
                ResultatAudit.REFUS,
                acteur_id=ctx.utilisateur.id,
                details={"role_actuel": ctx.utilisateur.role.value},
            )
            ctx.db.commit()
            raise AccesRefuse("Votre rôle ne permet pas d'effectuer cette opération.")
        return ctx

    return _verifier


@dataclass(frozen=True)
class ContexteExecutionTache:
    """Contexte d'exécution d'une étape de tâche : peut être porté soit par un Agent Local
    enrôlé par le bureau (`X-Agent-Token`), soit par un employé/administrateur authentifié.
    Attention (Règle 1) : ce contexte ne donne JAMAIS le droit de valider humainement une tâche."""

    db: Session
    utilisateur: Utilisateur | None
    agent_local: AgentLocal | None

    @property
    def acteur_id(self) -> __import__("uuid").UUID | None:
        return self.utilisateur.id if self.utilisateur else None

    @property
    def agent_local_id(self) -> __import__("uuid").UUID | None:
        return self.agent_local.id if self.agent_local else None


def obtenir_contexte_execution_tache(
    requete: Request,
    db: Session = Depends(obtenir_db),
    parametres: Parametres = Depends(obtenir_parametres),
) -> ContexteExecutionTache:
    jeton_agent = requete.headers.get(EN_TETE_JETON_AGENT)
    if jeton_agent:
        agent = service_agents.verifier_jeton_agent_local(
            db, jeton_clair=jeton_agent
        )
        return ContexteExecutionTache(
            db=db, utilisateur=None, agent_local=agent
        )

    ctx_humain = obtenir_contexte_auth(
        obtenir_contexte_auth_brut(requete=requete, db=db, parametres=parametres)
    )
    if ctx_humain.utilisateur.role not in {Role.ADMINISTRATEUR, Role.EMPLOYE}:
        audit.journaliser(
            db,
            "securite.role_insuffisant",
            ResultatAudit.REFUS,
            acteur_id=ctx_humain.utilisateur.id,
            details={"role_actuel": ctx_humain.utilisateur.role.value},
        )
        db.commit()
        raise AccesRefuse("Votre rôle ne permet pas d'effectuer cette opération.")

    return ContexteExecutionTache(
        db=db, utilisateur=ctx_humain.utilisateur, agent_local=None
    )
