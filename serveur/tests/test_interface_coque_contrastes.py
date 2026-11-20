"""Coque : contrastes recalculés (clair et sombre), tailles minimales, toasts, bandeaux, tiroir, typographie."""

from __future__ import annotations

import re

import pytest

from app.interface.design import styles
from app.interface.routeur_interface import HTML_INTERFACE_FR

THEMES = {"clair": styles.TOKENS_CLAIR, "sombre": styles.TOKENS_SOMBRE}


def _couleur(css: str, nom: str) -> tuple[float, float, float, float]:
    m = re.search(r"%s:\s*(#[0-9a-fA-F]{6}|rgba\([^)]*\))" % re.escape(nom), css)
    assert m is not None, nom
    v = m.group(1)
    if v.startswith("#"):
        return (*(int(v[i:i + 2], 16) for i in (1, 3, 5)), 1.0)  # type: ignore[return-value]
    r, g, b, a = (float(x) for x in v[5:-1].split(","))
    return r, g, b, a


def _sur(fg: tuple[float, ...], fond: tuple[float, ...]) -> tuple[float, float, float]:
    a = fg[3]
    return tuple(fg[i] * a + fond[i] * (1 - a) for i in range(3))  # type: ignore[return-value]


def _lum(c: tuple[float, ...]) -> float:
    lin = [x / 255 / 12.92 if x / 255 <= 0.03928 else ((x / 255 + 0.055) / 1.055) ** 2.4 for x in c[:3]]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contraste(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("fond", ["--fond", "--fond-creux", "--surface", "--surface-2", "--surface-3", "--accent-doux"])
def test_texte_secondaire_au_moins_4_5(theme: str, fond: str) -> None:
    css = THEMES[theme]
    ref = _couleur(css, "--surface")
    for jeton in ("--texte-faible", "--texte-doux", "--texte"):
        assert _contraste(_couleur(css, jeton), _sur(_couleur(css, fond), ref)) >= 4.5, (jeton, fond)


@pytest.mark.parametrize("theme", THEMES)
def test_bouton_primaire_texte_blanc_au_moins_4_5(theme: str) -> None:
    css = THEMES[theme]
    blanc = _couleur(css, "--sur-accent")
    for jeton in ("--accent-plein", "--accent-plein-survol"):
        assert _contraste(blanc, _couleur(css, jeton)) >= 4.5, jeton


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("famille", ["bon", "alerte", "critique"])
@pytest.mark.parametrize("fond", ["--surface", "--surface-2", "--fond"])
def test_badges_semantiques_lisibles(theme: str, famille: str, fond: str) -> None:
    css = THEMES[theme]
    base = _couleur(css, fond)
    pastille = _sur(_couleur(css, f"--{famille}-doux"), _sur(base, _couleur(css, "--surface")))
    assert _contraste(_couleur(css, f"--{famille}-texte"), pastille) >= 4.5


def test_sombre_fonds_de_badge_a_12_pour_cent_et_verts_desatures() -> None:
    for famille in ("bon", "alerte", "critique"):
        assert _couleur(styles.TOKENS_SOMBRE, f"--{famille}-doux")[3] == pytest.approx(0.12)
    r, g, b, _ = _couleur(styles.TOKENS_SOMBRE, "--bon")
    assert (max(r, g, b) - min(r, g, b)) / max(r, g, b) < 0.5  # saturation HSV < 0,5


def test_texte_secondaire_au_moins_13_px() -> None:
    for jeton in ("--t-xs", "--t-sm"):
        m = re.search(r"%s: ([0-9.]+)rem" % jeton, styles.CSS_DESIGN)
        assert m is not None and float(m.group(1)) * 16 >= 13, jeton


def test_toasts_en_bas_sous_l_entete_collant() -> None:
    css = styles.CSS_DESIGN
    regle = re.search(r"#zone-notification \{([^}]*)\}", css)
    assert regle is not None
    assert "bottom:" in regle.group(1)
    z = int(re.search(r"z-index: (\d+)", regle.group(1)).group(1))  # type: ignore[union-attr]
    z_entete = int(re.search(r"\.barre-haute \{[^}]*z-index: (\d+)", css).group(1))  # type: ignore[union-attr]
    assert z < z_entete
    assert "safe-area-inset-bottom" in regle.group(1)


def test_bandeau_dossier_une_ligne_sur_mobile() -> None:
    mobile = styles.CSS_ADAPTATIF.split("@media (max-width: 900px) {")[1]
    assert "#banniere-etat { margin-bottom: var(--e4); flex-wrap: nowrap;" in mobile
    assert "text-overflow: ellipsis" in mobile and "white-space: nowrap" in mobile


def test_bandeau_email_fin_ferme_et_memorise() -> None:
    assert 'id="btn-renvoyer-verification" class="btn btn-lien"' in HTML_INTERFACE_FR
    assert re.search(r'id="btn-masquer-bandeau-email"[^>]*aria-label="Masquer ce rappel"', HTML_INTERFACE_FR)
    js = HTML_INTERFACE_FR.split("function bandeauEmailMasque")[1][:1200]
    assert "try {" in js and "localStorage.setItem" in js and "catch" in js


def test_tiroir_fermer_44_et_pied_collant() -> None:
    css = styles.CSS_DESIGN
    assert re.search(r"\.nav-fermer \{[^}]*min-width: 44px; min-height: 44px", css)
    assert re.search(r"\.nav-pied \{[^}]*position: sticky; bottom: 0", css)


def test_connexion_allegee_et_barre_laterale_attenuee() -> None:
    assert len(re.findall(r'class="argument-icone"', HTML_INTERFACE_FR)) == 3
    assert "connexion-exemple" not in HTML_INTERFACE_FR
    assert "body.hors-session aside#navigation-principale nav { opacity:" in styles.CSS_DESIGN
    assert "pointer-events: none" not in styles.CSS_DESIGN.split("body.hors-session aside#navigation-principale nav")[1][:120]


def test_majuscules_reservees_aux_titres_de_la_barre_laterale() -> None:
    css = styles.CSS_DESIGN
    assert not re.search(r"\.surtitre \{[^}]*uppercase", css)
    assert not re.search(r"\bth \{[^}]*uppercase", css)
    assert re.search(r"\.nav-titre \{[^}]*uppercase", css)
