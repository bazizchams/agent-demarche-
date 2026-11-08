"""Service de gestion et d'authentification des Agents Locaux (postes Windows du bureau).

Principes de sécurité :
- Chaque agent local est rattaché à un bureau (`tenant_id`).
- Le jeton secret d'API n'est affiché qu'une seule fois à l'enrôlement ; seule son
  empreinte SHA-256 est stockée en base (`empreinte_jeton`).
- La vérification du jeton fixe automatiquement le `tenant_id` sur la session SQLAlchemy,
  garantissant qu'un agent local ne peut accéder qu'aux tâches de son propre bureau.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.erreurs import AccesRefuse, NonAuthentifie, NonTrouve
from app.core.securite import empreinte_jeton, generer_jeton
from app.db.base import maintenant_utc
from app.db.tenant import definir_tenant, sans_filtre_tenant, tenant_courant
from app.modeles.agent_local import AgentLocal
from app.modeles.bureau import Bureau
from app.modeles.journal_audit import ResultatAudit
from app.schemas.tache import AgentLocalCreation, AgentLocalEnroleSortie, AgentLocalSortie
from app.services import audit


def enroler_agent_local(
    db: Session,
    *,
    donnees: AgentLocalCreation,
    acteur_id: uuid.UUID,
) -> AgentLocalEnroleSortie:
    tid = tenant_courant(db)
    if tid is None:
        raise RuntimeError("Contexte bureau (tenant) manquant sur la session.")

    jeton_clair = f"be_agent_{generer_jeton()}"
    empreinte = empreinte_jeton(jeton_clair)

    agent = AgentLocal(
        id=uuid.uuid4(),
        tenant_id=tid,
        nom_machine=donnees.nom_machine.strip(),
        empreinte_jeton=empreinte,
        actif=True,
        cree_par_id=acteur_id,
    )
    db.add(agent)
    db.flush()

    audit.journaliser(
        db,
        "agent_local.enrolement",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="agent_local",
        ressource_id=agent.id,
    )
    db.commit()
    return AgentLocalEnroleSortie(
        agent=AgentLocalSortie.model_validate(agent),
        jeton_secret=jeton_clair,
    )


def lister_agents_locaux(db: Session) -> list[AgentLocalSortie]:
    agents = db.scalars(
        select(AgentLocal).order_by(AgentLocal.cree_le.desc(), AgentLocal.id)
    ).all()
    return [AgentLocalSortie.model_validate(a) for a in agents]


def changer_statut_agent_local(
    db: Session,
    *,
    agent_id: uuid.UUID,
    actif: bool,
    acteur_id: uuid.UUID,
) -> AgentLocalSortie:
    agent = db.scalar(select(AgentLocal).where(AgentLocal.id == agent_id))
    if agent is None:
        raise NonTrouve("Agent local introuvable.")

    agent.actif = actif
    audit.journaliser(
        db,
        "agent_local.activation" if actif else "agent_local.revocation",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="agent_local",
        ressource_id=agent.id,
    )
    db.commit()
    return AgentLocalSortie.model_validate(agent)


def verifier_jeton_agent_local(
    db: Session,
    *,
    jeton_clair: str,
) -> AgentLocal:
    if not jeton_clair or not jeton_clair.strip():
        raise NonAuthentifie("Jeton d'agent local manquant.")

    empreinte = empreinte_jeton(jeton_clair.strip())
    with sans_filtre_tenant(db):
        agent = db.scalar(
            select(AgentLocal).where(AgentLocal.empreinte_jeton == empreinte)
        )
        if agent is None:
            raise NonAuthentifie("Jeton d'agent local invalide.")
        if not agent.actif:
            raise AccesRefuse("Cet agent local a été révoqué.")
        bureau = db.get(Bureau, agent.tenant_id)
        if bureau is None or not bureau.actif:
            raise AccesRefuse("L'abonnement du bureau rattaché à cet agent est suspendu.")

    definir_tenant(db, agent.tenant_id)
    agent.derniere_activite_le = maintenant_utc()
    db.commit()
    return agent
