"""Exceptions métier typées. Les messages sont destinés à l'utilisateur et ne doivent
JAMAIS contenir de donnée personnelle (ils peuvent finir dans les journaux)."""

from __future__ import annotations


class ErreurMetier(Exception):
    statut_http: int = 400
    code: str = "erreur_metier"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NonTrouve(ErreurMetier):
    statut_http = 404
    code = "non_trouve"


class Conflit(ErreurMetier):
    statut_http = 409
    code = "conflit"


class DonneesInvalides(ErreurMetier):
    statut_http = 422
    code = "donnees_invalides"


class NonAuthentifie(ErreurMetier):
    statut_http = 401
    code = "non_authentifie"


NonAutorise = NonAuthentifie


class AccesRefuse(ErreurMetier):
    statut_http = 403
    code = "acces_refuse"


class PaiementRequis(ErreurMetier):
    """Abonnement expiré ou suspendu : le bureau est en lecture seule."""

    statut_http = 402
    code = "abonnement_requis"


class LimiteAtteinte(ErreurMetier):
    statut_http = 429
    code = "limite_atteinte"


class ServiceIndisponible(ErreurMetier):
    statut_http = 503
    code = "service_indisponible"
