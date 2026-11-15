"""Règle 4 : le formulaire « Nouvel étudiant » ne contient aucune valeur pré-remplie."""

from __future__ import annotations

import re

from app.interface.design.vues_dossiers import HTML_ETUDIANTS

CHAMPS = (
    "cand-nom", "cand-prenom", "cand-sexe", "cand-dn", "cand-lieu", "cand-nat", "cand-pays",
    "cand-email", "cand-tel", "cand-pass", "cand-exp-pass", "cand-niveau", "cand-prog",
    "cand-etab", "cand-fonds",
)


def _bloc() -> str:
    debut = HTML_ETUDIANTS.index('id="carte-nouvel-etudiant"')
    return HTML_ETUDIANTS[debut:]


def test_aucun_champ_n_est_prerempli() -> None:
    bloc = _bloc()
    for champ in CHAMPS:
        balise = re.search(rf'<(?:input|select)\b[^>]*id="{champ}"[^>]*>', bloc)
        assert balise is not None, champ
        assert not re.search(r'\bvalue="[^"]+"', balise.group(0)), f"{champ} est pré-rempli"


def test_aucune_option_de_liste_n_est_preselectionnee() -> None:
    bloc = _bloc()
    select = re.search(r'<select id="cand-sexe">.*?</select>', bloc, re.S)
    assert select is not None
    assert "selected" not in select.group(0)


def test_aucune_donnee_plausible_dans_le_bloc() -> None:
    bloc = _bloc()
    for interdit in ("BELAID", "Amine", "DZ9900112", "exemple.dz", "+213", "Paris-Saclay", "15000"):
        assert interdit not in bloc, interdit
