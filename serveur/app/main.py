"""Point d'entrée de l'application FastAPI."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.gzip import GZipMiddleware

import app.modeles  # noqa: F401  (enregistre les modèles ORM)
from app.api.v1 import routeur_v1
from app.core.chiffrement import charger_ou_creer_cle_maitresse
from app.core.config import Environnement, Parametres, obtenir_parametres
from app.core.erreurs import ErreurMetier
from app.core.journalisation import configurer_journalisation
from app.db.session import creer_fabrique_sessions, creer_moteur
from app.demo.routeur_demo import routeur_demo
from app.interface.routeur_interface import routeur_interface
from app.interface.routeur_public import routeur_public

journal = logging.getLogger("app.http")


def creer_application(parametres: Parametres | None = None) -> FastAPI:
    cfg = parametres or obtenir_parametres()
    configurer_journalisation(cfg.niveau_journal)

    @asynccontextmanager
    async def cycle_de_vie(application: FastAPI) -> AsyncIterator[None]:
        if not hasattr(application.state, "cle_maitresse"):
            application.state.cle_maitresse = charger_ou_creer_cle_maitresse(cfg)
        if not hasattr(application.state, "moteur"):
            moteur = creer_moteur(cfg.url_base_donnees)
            application.state.moteur = moteur
            application.state.fabrique_sessions = creer_fabrique_sessions(moteur)
            propre_moteur = True
        else:
            propre_moteur = False

        if cfg.environnement is Environnement.LOCAL:
            from datetime import date, timedelta
            from sqlalchemy import select
            from app.db.base import Base
            from app.db.tenant import definir_tenant, sans_filtre_tenant
            from app.modeles.utilisateur import Utilisateur
            from app.schemas.candidat import CandidatCreation
            from app.services.bureaux import provisionner_bureau_et_admin
            from app.services import candidats as service_candidats

            Base.metadata.create_all(application.state.moteur)
            comptes_locaux = [
                (
                    "Bureau d'Études Alger",
                    "bureau-alger-dz",
                    "admin@bureau-alger.dz",
                    "Administrateur Bureau Alger",
                    "BureauAlger!2026",
                ),
                (
                    "Bureau d'Études Démo Algérie",
                    "bureau-demo-dz",
                    "admin@bureau-demo.dz",
                    "Dirigeant Bureau Démo",
                    "MotDePasse!2026#Demo",
                ),
            ]
            with application.state.fabrique_sessions() as db_init:
                for nom_b, slug_b, email_b, nom_adm, mdp_adm in comptes_locaux:
                    # Graine locale : une session ne change pas de bureau, on repart de zéro à chaque bureau.
                    db_init.info.pop("tenant_id", None)
                    with sans_filtre_tenant(db_init):
                        admin_loc = db_init.scalar(
                            select(Utilisateur).where(Utilisateur.email == email_b)
                        )
                    if admin_loc is None:
                        bureau_loc, admin_loc = provisionner_bureau_et_admin(
                            db_init,
                            nom_bureau=nom_b,
                            slug=slug_b,
                            email_admin=email_b,
                            nom_admin=nom_adm,
                            mot_de_passe_admin=mdp_adm,
                            parametres=cfg,
                            doit_changer_mot_de_passe=False,
                        )
                        definir_tenant(db_init, bureau_loc.id)
                        service_candidats.creer_candidat(
                            db_init,
                            donnees=CandidatCreation(
                                nom="BENALI",
                                prenom="Yasmine",
                                sexe="F",
                                date_naissance=date(2003, 5, 14),
                                lieu_naissance="Alger",
                                nationalite="Algérienne",
                                pays_residence="Algérie",
                                email="yasmine.benali@exemple-fictif.dz",
                                telephone="+213550112233",
                                numero_passeport="DZ8844221",
                                date_expiration_passeport=date.today() + timedelta(days=900),
                                niveau_actuel="Licence 3 Informatique (USTHB)",
                                programme_vise="Master 1 Intelligence Artificielle",
                                etablissement_vise="Sorbonne Université",
                                fonds_disponibles_eur=9200,
                                consentement_signe=True,
                            ),
                            acteur_id=admin_loc.id,
                            cle_maitresse=application.state.cle_maitresse,
                        )
                        db_init.commit()

        from app.agent_local.sessions_navigateur import RegistreSessionsNavigateur

        if getattr(application.state, "registre_navigateur", None) is None:
            application.state.registre_navigateur = RegistreSessionsNavigateur()

        try:
            yield
        finally:
            # Arrêt propre : ferme tous les navigateurs Co-Pilote (un par bureau) et leurs threads.
            registre_nav = getattr(application.state, "registre_navigateur", None)
            if registre_nav is not None:
                registre_nav.fermer_tout()
            if propre_moteur:
                application.state.moteur.dispose()

    application = FastAPI(
        title="Plateforme Agent Bureau d'Études",
        version="0.1.0",
        docs_url="/docs" if cfg.docs_actives else None,
        redoc_url=None,
        openapi_url="/openapi.json" if cfg.docs_actives else None,
        lifespan=cycle_de_vie,
    )

    if parametres is not None:
        application.dependency_overrides[obtenir_parametres] = lambda: cfg

    # Compression des réponses texte (la page d'interface pèse ~600 Ko) ; le flux SSE est exclu par défaut.
    application.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=6)

    @application.middleware("http")
    async def en_tetes_securite(requete: Request, call_next):
        reponse = await call_next(requete)
        reponse.headers.setdefault("X-Content-Type-Options", "nosniff")
        reponse.headers.setdefault("X-Frame-Options", "DENY")
        reponse.headers.setdefault("Referrer-Policy", "no-referrer")
        if cfg.environnement is Environnement.PRODUCTION:
            reponse.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains; preload",
            )
        if requete.url.path.startswith("/api/"):
            reponse.headers.setdefault("Cache-Control", "no-store")
        return reponse

    @application.exception_handler(ErreurMetier)
    async def gerer_erreur_metier(_requete: Request, exc: ErreurMetier) -> JSONResponse:
        return JSONResponse(
            status_code=exc.statut_http,
            content={"code": exc.code, "detail": exc.message},
        )

    @application.exception_handler(RequestValidationError)
    async def gerer_erreur_validation(
        _requete: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # On ne renvoie NI ne journalise la valeur brute soumise (`input`), car elle
        # peut contenir un nom, une adresse e-mail ou un mot de passe (règle 5).
        champs = [
            {
                "champ": ".".join(str(p) for p in err.get("loc", ())),
                "type": err.get("type", "invalide"),
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "code": "donnees_invalides",
                "detail": "Les données envoyées ne respectent pas le format attendu.",
                "champs": champs,
            },
        )

    @application.exception_handler(Exception)
    async def gerer_erreur_inattendue(
        _requete: Request, exc: Exception
    ) -> JSONResponse:
        reference = str(uuid.uuid4())
        journal.error(
            "Erreur interne reference=%s type=%s",
            reference,
            type(exc).__name__,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "code": "erreur_interne",
                "detail": "Une erreur interne est survenue.",
                "reference": reference,
            },
        )

    application.include_router(routeur_v1)
    application.include_router(routeur_interface)
    application.include_router(routeur_public)
    if cfg.environnement is not Environnement.PRODUCTION:
        application.include_router(routeur_demo)
    return application


app = creer_application()
