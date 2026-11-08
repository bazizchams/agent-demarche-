"""Journalisation technique sans données personnelles (règle 5).

Principe : le code ne journalise QUE des identifiants opaques (UUID), des codes d'action
et des types d'erreur — jamais de nom, e-mail, date de naissance ou numéro de passeport.

Le filtre ci-dessous est un FILET DE SÉCURITÉ supplémentaire : il masque les motifs
reconnaissables (e-mail, dates, téléphones, numéros longs). Il ne peut pas reconnaître
un nom ou un prénom : la règle « identifiants uniquement » reste donc obligatoire.
"""

from __future__ import annotations

import logging
import logging.config
import re

_MOTIFS_PII: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), "[email]"),
    (re.compile(r"(?<![\w-])\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}(?![\w-])"), "[date]"),
    (re.compile(r"(?<![\w-])\d{4}-\d{2}-\d{2}(?![\w-])"), "[date]"),
    (re.compile(r"(?<![\w-])(?:\+|00)\d[\d \-.]{7,}\d(?![\w-])"), "[telephone]"),
    (re.compile(r"(?<![\w-])0[5-7]\d(?:[ .\-]?\d{2}){3}(?![\w-])"), "[telephone]"),
    (re.compile(r"(?<![\w-])[A-Za-z]{0,2}\d{8,12}(?![\w-])"), "[numero]"),
]


def masquer_pii(texte: str) -> str:
    """Remplace les motifs de données personnelles reconnaissables par un marqueur."""
    for motif, remplacement in _MOTIFS_PII:
        texte = motif.sub(remplacement, texte)
    return texte


class FormateurSansPII(logging.Formatter):
    """Masque les données personnelles dans le message ET dans les traces d'exception,
    sans toucher à l'horodatage ajouté par le formateur."""

    def format(self, record: logging.LogRecord) -> str:
        copie = logging.makeLogRecord(record.__dict__)
        copie.msg = masquer_pii(copie.getMessage())
        copie.args = None
        if copie.exc_info:
            copie.exc_text = masquer_pii(self.formatException(copie.exc_info))
            copie.exc_info = None
        elif copie.exc_text:
            copie.exc_text = masquer_pii(copie.exc_text)
        if copie.stack_info:
            copie.stack_info = masquer_pii(copie.stack_info)
        return super().format(copie)


class FiltreSansParametresURL(logging.Filter):
    """Retire la partie « ?… » des URL dans le journal d'accès uvicorn :
    une recherche peut contenir un nom de candidat dans la query string."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            chemin = args[2].split("?", 1)[0]
            record.args = (*args[:2], chemin, *args[3:])
        return True


def configuration_journalisation(niveau: str = "INFO") -> dict:
    """Configuration commune à l'application et à uvicorn."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "sans_pii": {
                "()": "app.core.journalisation.FormateurSansPII",
                "fmt": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            },
        },
        "filters": {
            "sans_parametres_url": {"()": "app.core.journalisation.FiltreSansParametresURL"},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "sans_pii",
            },
            "acces": {
                "class": "logging.StreamHandler",
                "formatter": "sans_pii",
                "filters": ["sans_parametres_url"],
            },
        },
        "loggers": {
            "app": {"handlers": ["console"], "level": niveau, "propagate": False},
            "uvicorn": {"handlers": ["console"], "level": niveau, "propagate": False},
            "uvicorn.error": {"handlers": ["console"], "level": niveau, "propagate": False},
            "uvicorn.access": {"handlers": ["acces"], "level": niveau, "propagate": False},
            # Ne jamais activer l'écho SQL : il afficherait les valeurs des requêtes.
            "sqlalchemy.engine": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        },
        "root": {"handlers": ["console"], "level": "WARNING"},
    }


def configurer_journalisation(niveau: str = "INFO") -> None:
    logging.config.dictConfig(configuration_journalisation(niveau))
