"""Classification des pièces (proposition seulement) et fusion de la double lecture A/B."""

from __future__ import annotations

from datetime import date

from app.modeles.extraction_document import StatutExtraction
from app.services.classification_pieces import SEUIL_CONFIRMATION, deviner_type_piece
from app.services.extraction_champs import ChampLu, analyser_mrz
from app.services.fusion_extractions import (
    ValeurExtraite,
    controles_croises,
    fusionner_lectures,
    valeur_ancree,
)
from tests import corpus_synthetique as corpus

# ------------------------------------------------------------------ classification


def test_passeport_a_mrz_valide_classe_sans_confirmation() -> None:
    c = deviner_type_piece([(1, corpus.TEXTE_PASSEPORT_VALIDE)])
    assert c.type_piece_propose == "passeport" and c.famille == "passeport"
    assert c.confiance >= SEUIL_CONFIRMATION and not c.confirmation_humaine_requise


def test_passeport_a_mrz_invalide_exige_confirmation_humaine() -> None:
    c = deviner_type_piece([(1, corpus.TEXTE_PASSEPORT_INVALIDE)])
    assert c.famille == "passeport"
    assert c.confiance < SEUIL_CONFIRMATION and c.confirmation_humaine_requise


def test_releve_bac_et_certificat_de_langue() -> None:
    rel = deviner_type_piece([(1, corpus.TEXTE_RELEVE_BAC)])
    assert rel.type_piece_propose == "releve_notes_bac" and not rel.confirmation_humaine_requise
    cert = deviner_type_piece([(1, corpus.TEXTE_TCF)])
    assert cert.type_piece_propose == "resultats_test_langue" and not cert.confirmation_humaine_requise


def test_texte_vide_ou_sans_indice_ne_propose_aucun_type() -> None:
    for pages in ([], [(1, "")], [(1, "Lorem ipsum dolor sit amet")]):
        c = deviner_type_piece(pages)
        assert c.type_piece_propose is None and c.confiance == 0
        assert c.confirmation_humaine_requise


def test_mot_cle_isole_donne_une_confiance_basse() -> None:
    c = deviner_type_piece([(1, "Voyage : mon passeport est à renouveler.")])
    assert c.confiance < SEUIL_CONFIRMATION and c.confirmation_humaine_requise


# ------------------------------------------------------------------ fusion A/B


def _a(champ: str, valeur: str, extrait: str, **kw) -> ChampLu:
    return ChampLu(champ=champ, valeur=valeur, extrait=extrait, page=1, confiance=kw.pop("confiance", 0.9), **kw)


TEXTE = {1: "Moyenne générale : 14,52/20\nNom : DUPONT\n"}


def test_concordance_et_ancrage_donnent_auto() -> None:
    a = [_a("moyenne_generale", "14.52", "Moyenne générale : 14,52/20")]
    b = [_a("moyenne_generale", "14,52", "Moyenne générale : 14,52/20")]
    (f,) = fusionner_lectures(a, b, TEXTE)
    assert f.statut is StatutExtraction.AUTO and f.source == "A" and f.motif is None
    assert f.valeur == "14.52" and f.valeur_alternative is None


def test_discordance_ab_donne_a_verifier_avec_valeur_alternative() -> None:
    a = [_a("moyenne_generale", "14.52", "Moyenne générale : 14,52/20")]
    b = [_a("moyenne_generale", "14.62", "Moyenne générale : 14,52/20")]
    (f,) = fusionner_lectures(a, b, TEXTE)
    assert f.statut is StatutExtraction.A_VERIFIER and f.motif == "discordance_ab"
    assert f.valeur == "14.52" and f.valeur_alternative == "14.62"


def test_sans_lecteur_b_aucune_valeur_ordinaire_n_est_auto() -> None:
    a = [_a("moyenne_generale", "14.52", "Moyenne générale : 14,52/20")]
    (f,) = fusionner_lectures(a, None, TEXTE)
    assert f.statut is StatutExtraction.A_VERIFIER and f.motif == "double_lecture_absente"


def test_valeur_non_ancree_est_rejetee_meme_si_les_deux_lecteurs_concordent() -> None:
    a = [_a("nom", "MARTIN", "Nom : MARTIN")]
    b = [_a("nom", "MARTIN", "Nom : MARTIN")]
    (f,) = fusionner_lectures(a, b, TEXTE)
    assert f.statut is StatutExtraction.REJETE and f.motif == "non_ancree"


def test_valeur_seulement_vue_par_b_et_non_ancree_est_rejetee() -> None:
    b = [_a("nom", "INVENTE", "Nom : INVENTE")]
    (f,) = fusionner_lectures([], b, TEXTE)
    assert f.statut is StatutExtraction.REJETE and f.motif == "non_ancree" and f.source == "B"


def test_valeur_seulement_vue_par_b_mais_ancree_reste_a_verifier() -> None:
    b = [_a("nom", "DUPONT", "Nom : DUPONT")]
    (f,) = fusionner_lectures([], b, TEXTE)
    assert f.statut is StatutExtraction.A_VERIFIER and f.motif == "lecteur_a_absent" and f.source == "B"


def test_lecture_a_invalide_reste_a_verifier_meme_avec_concordance() -> None:
    texte = {1: "Moyenne générale : 25/20"}
    a = [_a("moyenne_generale", "25", "Moyenne générale : 25/20", valide=False, motif="moyenne_hors_bornes")]
    b = [_a("moyenne_generale", "25", "Moyenne générale : 25/20")]
    (f,) = fusionner_lectures(a, b, texte)
    assert f.statut is StatutExtraction.A_VERIFIER and f.motif == "moyenne_hors_bornes"


def test_controle_mrz_valide_autorise_auto_sans_lecteur_b() -> None:
    champs = analyser_mrz(corpus.TEXTE_PASSEPORT_VALIDE)
    texte = {1: corpus.TEXTE_PASSEPORT_VALIDE}
    par = {f.champ: f for f in fusionner_lectures(champs, None, texte)}
    assert par["numero_passeport"].statut is StatutExtraction.AUTO
    assert par["numero_passeport"].motif == "controle_icao"
    assert par["nom"].statut is StatutExtraction.A_VERIFIER  # pas de chiffre de contrôle sur le nom
    sans = {f.champ: f for f in fusionner_lectures(champs, None, texte, autoriser_controle_mrz=False)}
    assert sans["numero_passeport"].statut is StatutExtraction.A_VERIFIER


def test_b_contredit_un_mrz_valide_donne_a_verifier() -> None:
    champs = analyser_mrz(corpus.TEXTE_PASSEPORT_VALIDE)
    texte = {1: corpus.TEXTE_PASSEPORT_VALIDE}
    ligne = corpus.MRZ_L2_VALIDE
    b = [_a("numero_passeport", "L898902C8", ligne)]
    par = {f.champ: f for f in fusionner_lectures(champs, b, texte)}
    assert par["numero_passeport"].statut is StatutExtraction.A_VERIFIER
    assert par["numero_passeport"].motif == "discordance_ab"
    assert par["numero_passeport"].valeur_alternative == "L898902C8"


def test_valeur_ancree() -> None:
    page = "Moyenne  générale : 14,52/20"
    assert valeur_ancree(_a("moyenne_generale", "14.52", "Moyenne générale : 14,52/20"), page)
    assert not valeur_ancree(_a("moyenne_generale", "14.52", ""), page)
    assert not valeur_ancree(_a("moyenne_generale", "14.52", "Moyenne générale : 14,52/20"), "autre texte")
    assert not valeur_ancree(_a("moyenne_generale", "16.00", "Moyenne générale : 14,52/20"), page)
    assert not valeur_ancree(_a("moyenne_generale", "14.52", "Moyenne générale : 14,52/20"), None)


# ------------------------------------------------------------------ contrôles croisés


def _v(doc: str, piece: str, champ: str, valeur: str) -> ValeurExtraite:
    return ValeurExtraite(extraction_id=None, document_id=doc, type_piece=piece, champ=champ, valeur=valeur)


def test_controles_croises_coherents() -> None:
    vals = [
        _v("d1", "passeport", "nom", "ERIKSSON"),
        _v("d2", "releve_notes_bac", "nom", "Eriksson"),
        _v("d1", "passeport", "prenom", "ANNA MARIA"),
        _v("d2", "releve_notes_bac", "prenom", "Anna"),
        _v("d1", "passeport", "date_naissance", "1974-08-12"),
        _v("d2", "releve_notes_bac", "date_naissance", "1974-08-12"),
    ]
    assert controles_croises(vals, date_reference=date(2026, 1, 1)) == []


def test_controles_croises_detectent_discordances_sans_donnee_personnelle() -> None:
    vals = [
        _v("d1", "passeport", "nom", "ERIKSSON"),
        _v("d2", "releve_notes_bac", "nom", "ANDERSSON"),
        _v("d1", "passeport", "prenom", "ANNA"),
        _v("d2", "releve_notes_bac", "prenom", "PAUL"),
        _v("d1", "passeport", "date_naissance", "1974-08-12"),
        _v("d2", "releve_notes_bac", "date_naissance", "1975-08-12"),
    ]
    alertes = controles_croises(vals, date_reference=date(2026, 1, 1))
    assert {a.code for a in alertes} == {"nom_discordant", "prenom_discordant", "date_naissance_discordante"}
    for a in alertes:
        assert set(a.document_ids) == {"d1", "d2"}
        for secret in ("ERIKSSON", "ANDERSSON", "PAUL", "1974", "1975"):
            assert secret not in a.message


def test_controles_croises_expiration_du_passeport() -> None:
    ref = date(2026, 6, 1)
    expire = controles_croises([_v("d1", "passeport", "date_expiration_passeport", "2026-01-01")], date_reference=ref)
    assert [a.code for a in expire] == ["passeport_expire"]
    proche = controles_croises([_v("d1", "passeport", "date_expiration_passeport", "2026-09-01")], date_reference=ref)
    assert [a.code for a in proche] == ["passeport_expiration_proche"]
    assert controles_croises([_v("d1", "passeport", "date_expiration_passeport", "2030-01-01")], date_reference=ref) == []
