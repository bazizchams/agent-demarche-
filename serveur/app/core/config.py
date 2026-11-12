"""Paramètres de l'application, lus depuis les variables d'environnement (préfixe BE_)
et le fichier serveur/.env. Aucun secret ne doit être écrit en dur dans le code."""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RACINE_SERVEUR = Path(__file__).resolve().parents[2]
RACINE_PLATEFORME = RACINE_SERVEUR.parent


class Environnement(str, Enum):
    LOCAL = "local"
    TEST = "test"
    PRODUCTION = "production"


class Parametres(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BE_",
        env_file=RACINE_SERVEUR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environnement: Environnement = Environnement.LOCAL
    url_base_donnees: str = "sqlite:///./donnees/bureau.db"

    # Sessions
    nom_cookie_session: str = "be_session"
    cookie_securise: bool = True
    duree_session_minutes: int = Field(default=480, ge=5, le=7 * 24 * 60)
    inactivite_session_minutes: int = Field(default=120, ge=5, le=24 * 60)

    # Mots de passe et protection contre les essais
    longueur_min_mot_de_passe: int = Field(default=12, ge=10)
    max_echecs_connexion: int = Field(default=5, ge=3, le=20)
    duree_verrouillage_minutes: int = Field(default=15, ge=1)

    # Chiffrement au repos et stockage des documents (Phase 2)
    cle_maitresse_base64: str | None = None
    fichier_cle_dpapi: Path = RACINE_SERVEUR / "donnees" / "cle_maitresse.dpapi"
    dossier_stockage: Path = RACINE_SERVEUR / "donnees" / "stockage"
    dossier_demarches: Path = RACINE_PLATEFORME / "config" / "demarches"
    dossier_portails: Path = RACINE_PLATEFORME / "config" / "portails"
    taille_max_document_octets: int = Field(default=15 * 1024 * 1024, ge=1024)

    # Tâches longues et verrous exclusifs par dossier (Phase 3)
    duree_verrou_dossier_secondes: int = Field(default=300, ge=30, le=3600)

    # Sauvegardes chiffrées, facturation Stripe et conformité (Phase 6)
    dossier_sauvegardes: Path = RACINE_SERVEUR / "donnees" / "sauvegardes"
    stripe_cle_secrete: str | None = None
    stripe_secret_webhook: str = "whsec_dev_local_secret_change_me"
    # Identifiants de prix Stripe (price_...) de chaque forfait et base des URL de retour
    # (ex. https://app.exemple.com). Sans clé secrète Stripe, le paiement est simulé hors production.
    stripe_prix_starter: str | None = None
    stripe_prix_professionnel: str | None = None
    stripe_prix_entreprise: str | None = None
    url_publique_plateforme: str | None = None
    version_cgu_courante: str = "CGU-2026.10"
    version_consentement_loi_18_07: str = "L18-07-2026.1"

    # Assistant IA (Claude). Clé unique de la plateforme, jamais écrite dans le code :
    # variable d'environnement BE_CLE_API_ANTHROPIC ou fichier serveur/.env.
    # Sans clé, les fonctions IA sont désactivées (réponse 503), le reste fonctionne.
    cle_api_anthropic: str | None = None
    modele_llm: str = "claude-sonnet-5-5"
    url_api_anthropic: str = "https://api.anthropic.com/v1/messages"
    delai_llm_secondes: int = Field(default=90, ge=5, le=300)

    # Inscription en libre-service des agences
    inscriptions_ouvertes: bool = True
    inscription_max_par_heure_par_ip: int = Field(default=5, ge=1, le=1000)
    inscription_limite_active_en_test: bool = False

    # Contrôle de l'abonnement : un bureau dont l'essai est terminé ou l'abonnement suspendu
    # passe en LECTURE SEULE (consultation, export et droits des candidats restent possibles).
    # None => contrôle actif uniquement en production (même principe que docs_api_actives).
    blocage_abonnement_expire: bool | None = None
    duree_essai_jours: int = Field(default=30, ge=1, le=365)
    jours_grace_impaye: int = Field(default=7, ge=0, le=60)

    # Co-Pilote navigateur côté serveur (multi-bureaux). None => mode serveur actif en production :
    # navigateur headless forcé, jamais de rattachement CDP 9222 ni de canal chrome/msedge local.
    # Variables d'environnement : BE_NAVIGATEUR_SERVEUR (ou BE_NAVIGATEUR_SERVEUR_ACTIF du docker-compose),
    # BE_NAVIGATEUR_MAX_SESSIONS (ou ..._SERVEUR_SESSIONS_MAX), BE_NAVIGATEUR_INACTIVITE_MINUTES (ou ..._SERVEUR_...).
    navigateur_serveur: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("navigateur_serveur", "BE_NAVIGATEUR_SERVEUR", "BE_NAVIGATEUR_SERVEUR_ACTIF"),
    )
    navigateur_max_sessions: int = Field(
        default=3,
        ge=1,
        le=50,
        validation_alias=AliasChoices(
            "navigateur_max_sessions", "BE_NAVIGATEUR_MAX_SESSIONS", "BE_NAVIGATEUR_SERVEUR_SESSIONS_MAX"
        ),
    )
    navigateur_inactivite_minutes: int = Field(
        default=15,
        ge=1,
        le=240,
        validation_alias=AliasChoices(
            "navigateur_inactivite_minutes",
            "BE_NAVIGATEUR_INACTIVITE_MINUTES",
            "BE_NAVIGATEUR_SERVEUR_INACTIVITE_MINUTES",
        ),
    )
    # Racine des profils Chromium (un sous-dossier par bureau). Défaut : <dossier_stockage>/profil_navigateur_agent.
    dossier_profils_navigateur: Path | None = None
    # URL du serveur utilisée par le pont du Co-Pilote hors production quand `url_publique_plateforme` est vide.
    url_serveur_local: str = "http://127.0.0.1:8000"

    # Divers
    niveau_journal: str = "INFO"
    docs_api_actives: bool | None = None  # None => actives sauf en production

    @model_validator(mode="after")
    def _verifier_coherence(self) -> "Parametres":
        if self.environnement is Environnement.PRODUCTION and not self.cookie_securise:
            raise ValueError("En production, BE_COOKIE_SECURISE doit valoir true (HTTPS obligatoire).")
        self.url_base_donnees = _resoudre_chemin_sqlite(self.url_base_donnees)
        return self

    @property
    def docs_actives(self) -> bool:
        if self.docs_api_actives is not None:
            return self.docs_api_actives
        return self.environnement is not Environnement.PRODUCTION

    @property
    def blocage_abonnement_actif(self) -> bool:
        if self.blocage_abonnement_expire is not None:
            return self.blocage_abonnement_expire
        return self.environnement is Environnement.PRODUCTION

    @property
    def navigateur_serveur_actif(self) -> bool:
        if self.navigateur_serveur is not None:
            return self.navigateur_serveur
        return self.environnement is Environnement.PRODUCTION

    @property
    def url_serveur_copilote(self) -> str:
        """URL injectée dans la page du Co-Pilote pour joindre le pont. Vide (pont désactivé)
        en production tant que `url_publique_plateforme` n'est pas renseignée."""
        if self.url_publique_plateforme:
            return self.url_publique_plateforme.strip().rstrip("/")
        if self.environnement is Environnement.PRODUCTION:
            return ""
        return self.url_serveur_local.strip().rstrip("/")

    @property
    def est_sqlite(self) -> bool:
        return self.url_base_donnees.startswith("sqlite")


def _resoudre_chemin_sqlite(url: str) -> str:
    """Rend absolu un chemin SQLite relatif (par rapport au dossier serveur/),
    pour que la base soit toujours au même endroit quel que soit le dossier de lancement."""
    prefixe = "sqlite:///"
    if not url.startswith(prefixe) or url == "sqlite://" or ":memory:" in url:
        return url
    chemin = url[len(prefixe):]
    p = Path(chemin)
    if not p.is_absolute():
        p = (RACINE_SERVEUR / p).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    return prefixe + p.as_posix()


@lru_cache
def obtenir_parametres() -> Parametres:
    return Parametres()
