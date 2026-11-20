"""Un nom lu dans la MRZ (sans chiffre de contrôle) n'est fiable que s'il figure dans la zone visuelle.

Cas réel du corpus OCR : MRZ « BENAII », zone visuelle « Nom / Surname : BENALI » -> jamais validé en lot.
"""

from types import SimpleNamespace

from app.services.extraction_champs import NOM, NUMERO_PASSEPORT, PRENOM
from app.services.validation_lot import _Ligne, _nom_confirme_par_zone_visuelle


def _ligne(champ: str, valeur: str, extrait: str) -> _Ligne:
    return _Ligne(SimpleNamespace(champ=champ), valeur, extrait)


def test_nom_mal_lu_dans_la_mrz_n_est_pas_confirme() -> None:
    assert not _nom_confirme_par_zone_visuelle(_ligne(NOM, "BENAII", "Nom / Surname : BENALI"))


def test_nom_identique_a_la_zone_visuelle_est_confirme() -> None:
    assert _nom_confirme_par_zone_visuelle(_ligne(NOM, "BENALI", "Nom / Surname : BENALI"))


def test_prenom_compose_et_accents() -> None:
    assert _nom_confirme_par_zone_visuelle(_ligne(PRENOM, "AMINA SARAH", "Prénoms / Given names : Amina Sarah"))
    assert _nom_confirme_par_zone_visuelle(_ligne(PRENOM, "HELENE", "Prénoms : Hélène"))
    assert not _nom_confirme_par_zone_visuelle(_ligne(PRENOM, "AMINA SARAH", "Prénoms : Amina"))


def test_nom_vide_ou_extrait_absent_n_est_pas_confirme() -> None:
    assert not _nom_confirme_par_zone_visuelle(_ligne(NOM, "", "Nom : BENALI"))
    assert not _nom_confirme_par_zone_visuelle(_ligne(NOM, "BENALI", ""))


def test_la_ligne_mrz_ne_confirme_pas_le_nom() -> None:
    assert not _nom_confirme_par_zone_visuelle(_ligne(PRENOM, "ANNA MARIA", "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<"))
    assert _nom_confirme_par_zone_visuelle(
        _ligne(NOM, "BENALI", "Nom / Surname : BENALI\nP<DZABENALI<<AMINA<<<<<<<<<<<<<<<")
    )


def test_autres_champs_non_concernes() -> None:
    assert _nom_confirme_par_zone_visuelle(_ligne(NUMERO_PASSEPORT, "123456789", ""))
