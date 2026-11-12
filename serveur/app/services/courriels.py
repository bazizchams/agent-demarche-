"""Envoi de courriels (SMTP) et gabarits en français.

Principes de sécurité (règle 5) :
- le journal ne reçoit JAMAIS d'adresse, de lien ni de jeton : seulement le type de courriel,
  le transport et le nom de la classe d'erreur éventuelle ;
- le transport « memoire » (hors production ou sans configuration SMTP complète) n'envoie rien
  sur le réseau : il range le courriel dans une boîte d'envoi en mémoire, lue par les tests ;
- les liens placent le jeton dans le fragment (`#jeton=...`) : il n'est jamais transmis au
  serveur dans l'URL (donc absent des journaux d'accès) et un robot qui ouvre le lien sans
  exécuter de JavaScript ne le consomme pas.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from html import escape
from threading import Lock

from app.core.config import Environnement, Parametres

journal = logging.getLogger("app.courriels")

TAILLE_MAX_BOITE_MEMOIRE = 200
CHEMIN_VERIFICATION_ADRESSE = "/verification-adresse"
CHEMIN_NOUVEAU_MOT_DE_PASSE = "/nouveau-mot-de-passe"


@dataclass(frozen=True)
class Courriel:
    type: str
    destinataire: str
    sujet: str
    texte: str
    html: str


class BoiteEnvoiMemoire:
    """Courriels « envoyés » par le transport mémoire (bornée, sans écriture sur disque)."""

    def __init__(self) -> None:
        self._elements: list[Courriel] = []
        self._verrou = Lock()

    def deposer(self, courriel: Courriel) -> None:
        with self._verrou:
            self._elements.append(courriel)
            del self._elements[:-TAILLE_MAX_BOITE_MEMOIRE]

    def lister(self) -> list[Courriel]:
        with self._verrou:
            return list(self._elements)

    def vider(self) -> None:
        with self._verrou:
            self._elements.clear()


boite_memoire = BoiteEnvoiMemoire()


def url_base(parametres: Parametres) -> str:
    """Base publique des liens. Vide en production tant que `url_publique_plateforme` manque."""
    if parametres.url_publique_plateforme and parametres.url_publique_plateforme.strip():
        return parametres.url_publique_plateforme.strip().rstrip("/")
    if parametres.environnement is Environnement.PRODUCTION:
        return ""
    return parametres.url_serveur_local.strip().rstrip("/")


def construire_lien(parametres: Parametres, chemin: str, jeton: str) -> str | None:
    base = url_base(parametres)
    if not base:
        return None
    return f"{base}{chemin}#jeton={jeton}"


# --- Gabarits ---------------------------------------------------------------------------

def _gabarit(
    type_courriel: str, destinataire: str, sujet: str, paragraphes: list[str], lien: str | None,
    libelle_lien: str,
) -> Courriel:
    texte = "Bonjour,\n\n" + "\n\n".join(paragraphes)
    corps_html = "".join(f"<p>{escape(p)}</p>" for p in paragraphes)
    if lien:
        texte += f"\n\n{libelle_lien} :\n{lien}"
        corps_html += f'<p><a href="{escape(lien)}">{escape(libelle_lien)}</a></p>'
    texte += "\n\nAgent Bureau d'Études"
    html = (
        '<!doctype html><html lang="fr"><body style="font-family:system-ui,sans-serif">'
        f"<p>Bonjour,</p>{corps_html}<p>Agent Bureau d'Études</p></body></html>"
    )
    return Courriel(type_courriel, destinataire, sujet, texte, html)


def gabarit_verification_adresse(destinataire: str, lien: str | None, heures: int) -> Courriel:
    return _gabarit(
        "verification_adresse", destinataire,
        "Confirmez votre adresse e-mail",
        [
            "Pour confirmer votre adresse e-mail sur la plateforme, ouvrez le lien ci-dessous.",
            f"Ce lien est valable {heures} heures et ne peut être utilisé qu'une seule fois. "
            "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.",
        ],
        lien, "Confirmer mon adresse",
    )


def gabarit_mot_de_passe_oublie(destinataire: str, lien: str | None, minutes: int) -> Courriel:
    return _gabarit(
        "mot_de_passe_oublie", destinataire,
        "Réinitialisation de votre mot de passe",
        [
            "Une réinitialisation de mot de passe a été demandée pour votre compte.",
            f"Ce lien est valable {minutes} minutes et ne peut être utilisé qu'une seule fois. "
            "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message : "
            "votre mot de passe actuel reste inchangé.",
        ],
        lien, "Choisir un nouveau mot de passe",
    )


def gabarit_rappel_echeance(
    destinataire: str, libelle_echeance: str, date_echeance: str, jours_restants: int,
    lien: str | None = None,
) -> Courriel:
    """Rappel d'échéance. Reçoit uniquement un libellé de démarche et une date : jamais le
    nom d'un candidat dans le courriel."""
    quand = "aujourd'hui" if jours_restants == 0 else f"dans {jours_restants} jour(s)"
    return _gabarit(
        "rappel_echeance", destinataire,
        f"Rappel d'échéance : {libelle_echeance}",
        [f"L'échéance « {libelle_echeance} » est fixée au {date_echeance} ({quand})."],
        lien, "Ouvrir la plateforme",
    )


# --- Transports -------------------------------------------------------------------------

def _envoyer_smtp(courriel: Courriel, parametres: Parametres) -> None:
    message = EmailMessage()
    message["From"] = parametres.smtp_expediteur or ""
    message["To"] = courriel.destinataire
    message["Subject"] = courriel.sujet
    message.set_content(courriel.texte)
    message.add_alternative(courriel.html, subtype="html")

    securite = parametres.smtp_securite.strip().lower()
    contexte = ssl.create_default_context()
    hote = parametres.smtp_hote or ""
    if securite == "ssl":
        serveur: smtplib.SMTP = smtplib.SMTP_SSL(
            hote, parametres.smtp_port, timeout=parametres.smtp_delai_secondes, context=contexte
        )
    else:
        serveur = smtplib.SMTP(hote, parametres.smtp_port, timeout=parametres.smtp_delai_secondes)
    with serveur:
        if securite == "starttls":
            serveur.starttls(context=contexte)
        if parametres.smtp_utilisateur and parametres.smtp_mot_de_passe:
            serveur.login(parametres.smtp_utilisateur, parametres.smtp_mot_de_passe)
        serveur.send_message(message)


def envoyer_courriel(courriel: Courriel, parametres: Parametres) -> bool:
    """Envoie le courriel ; ne lève jamais (un échec d'envoi ne doit pas casser le parcours
    ni révéler l'existence d'un compte). Retourne True si le transport l'a accepté."""
    transport = parametres.transport_courriel_effectif
    try:
        if transport == "smtp":
            _envoyer_smtp(courriel, parametres)
        else:
            if parametres.environnement is Environnement.PRODUCTION:
                journal.warning("Courriel non envoyé : SMTP non configuré (transport mémoire).")
            boite_memoire.deposer(courriel)
    except Exception as exc:  # noqa: BLE001 - jamais le message d'erreur : il peut citer l'adresse
        journal.error(
            "Échec d'envoi de courriel (type=%s, transport=%s, erreur=%s).",
            courriel.type, transport, type(exc).__name__,
        )
        return False
    journal.info("Courriel traité (type=%s, transport=%s).", courriel.type, transport)
    return True
