"""Chargement et validation Pydantic des fichiers YAML de configuration des portails
(`config/portails/*.yaml` — Règle 7 : aucun sélecteur ni URL en dur dans le code)."""

from __future__ import annotations

import enum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class ModePortail(str, enum.Enum):
    DEMO = "demo"
    REEL = "reel"


class StatutTestFonctionnalite(str, enum.Enum):
    """Statuts réglementaires exigés par la Règle 6."""

    NON_TESTE = "non testé"
    TESTE_EN_LOCAL = "testé en local"
    TESTE_SUR_PAGE_DE_DEMO = "testé sur page de démo"
    VALIDE_SUR_PORTAIL_REEL = "validé sur portail réel"


class TypeChampPortail(str, enum.Enum):
    TEXTE = "texte"
    LISTE = "liste"
    DATE_ISO = "date_iso"
    ENTIER = "entier"


class TypeActionEtapePortail(str, enum.Enum):
    VERIFIER_SESSION_ET_SECURITE = "verifier_session_et_securite"
    REMPLIR_CHAMPS = "remplir_champs"
    REMPLIR_ET_TELEVERSER = "remplir_et_televerser"
    CAPTURE_ET_ARRET_AVANT_ENVOI = "capture_et_arret_avant_envoi"


class ConfigChampSelecteur(BaseModel):
    model_config = ConfigDict(extra="forbid")

    champ_candidat: str = Field(min_length=1, max_length=80)
    selecteur: str = Field(min_length=1, max_length=200)
    type_champ: TypeChampPortail = TypeChampPortail.TEXTE
    obligatoire: bool = True


class ConfigFichierSelecteur(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type_piece: str = Field(min_length=1, max_length=80)
    selecteur: str = Field(min_length=1, max_length=200)
    obligatoire: bool = True


class ConfigEtapeAutomatisation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code_etape: str = Field(min_length=1, max_length=80)
    type_action: TypeActionEtapePortail
    selecteur_navigation_onglet: str | None = Field(default=None, max_length=200)
    champs: list[ConfigChampSelecteur] = Field(default_factory=list)
    fichiers: list[ConfigFichierSelecteur] = Field(default_factory=list)
    cliquer_brouillon_apres: bool = False
    prendre_capture_etape: bool = False
    selecteur_temoin_pret: str | None = None


class ConfigPortailYAML(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code_portail: str | None = Field(default=None, min_length=1, max_length=80)
    code_demarche: str = Field(min_length=1, max_length=60)
    nom_portail: str = Field(min_length=1, max_length=200)
    mode_portail: ModePortail = ModePortail.DEMO
    statut_test_initial: StatutTestFonctionnalite = (
        StatutTestFonctionnalite.TESTE_SUR_PAGE_DE_DEMO
    )
    url_officielle: str | None = Field(default=None, max_length=500)
    domaines_autorises: list[str] = Field(default_factory=list)
    chemin_url: str = Field(min_length=1, max_length=300)
    temoin_session_ouverte: str = Field(min_length=1, max_length=200)
    detecteur_session_fermee: str | None = None
    detecteurs_blocage_securite: list[str] = Field(default_factory=list)
    selecteurs_soumission_interdits: list[str] = Field(default_factory=list)
    selecteur_enregistrer_brouillon: str | None = None
    etapes_automatisation: list[ConfigEtapeAutomatisation] = Field(default_factory=list)


def charger_config_portail(fichier_yaml: Path) -> ConfigPortailYAML:
    if not fichier_yaml.exists():
        raise FileNotFoundError(f"Fichier de configuration portail introuvable : {fichier_yaml}")
    brut = yaml.safe_load(fichier_yaml.read_text(encoding="utf-8"))
    cfg = ConfigPortailYAML.model_validate(brut)
    if cfg.code_portail is None:
        cfg.code_portail = fichier_yaml.stem
    return cfg


def lister_configs_portails(dossier_portails: Path) -> dict[str, ConfigPortailYAML]:
    resultat: dict[str, ConfigPortailYAML] = {}
    if not dossier_portails.exists():
        return resultat
    for fichier in sorted(dossier_portails.glob("*.yaml")):
        cfg = charger_config_portail(fichier)
        code = cfg.code_portail or fichier.stem
        resultat[code] = cfg
    return resultat
