"""Sélection de vœux sur FICHES FIGÉES : filtres durs, « à vérifier » pour toute exigence inconnue,
cas réel B2 vs C1, classement et justification factuelle. Aucune base, aucun réseau, données fictives."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
import yaml

from app.core.config import RACINE_PLATEFORME
from app.schemas.selection_voeux import (
    CertificatLangue,
    MoyennesProfil,
    NiveauLangueProfil,
    ProfilEtudiant,
)
from app.services.fiche_formation import FicheEntree, exigences_inconnues, fiches_depuis_yaml
from app.services.selection_voeux import selectionner

AUJOURD_HUI = date(2026, 11, 13)
RENTREE = date(2027, 9, 1)
LIMITE_FUTURE = AUJOURD_HUI + timedelta(days=60)


def fiche(**surcharges) -> FicheEntree:
    """Fiche COMPLÈTE (toutes les exigences connues) : chaque test n'altère que ce qu'il vérifie."""
    base = dict(
        etablissement="Université Fictive A",
        intitule="Master Fictif",
        niveau_entree_bac_plus=4,
        niveau_entree_libelle="Bac +4",
        francais_min="B2",
        moyenne_min=12.0,
        moyenne_reference="derniere_annee",
        date_limite=LIMITE_FUTURE,
        ferme=False,
        domaines=["informatique"],
        url_officielle="https://exemple.invalid/fiche",
        date_releve=AUJOURD_HUI,
        source="manuel",
    )
    base.update(surcharges)
    return FicheEntree(**base)


def profil(**surcharges) -> ProfilEtudiant:
    base = dict(
        niveau_diplome_bac_plus=3,
        moyennes=MoyennesProfil(derniere_annee=14.0),
        francais=NiveauLangueProfil(
            niveau="B2", certificat=CertificatLangue(type="DELF", date_obtention=date(2025, 6, 1))
        ),
        date_rentree=RENTREE,
    )
    base.update(surcharges)
    return ProfilEtudiant(**base)


def lancer(fiches: list[FicheEntree], p: ProfilEtudiant | None = None, **kw):
    couples = [(uuid.uuid4(), f) for f in fiches]
    return selectionner(couples, p or profil(), aujourd_hui=AUJOURD_HUI, **kw)


# ----------------------------------------------------------------------------- langue : B2 vs C1


def test_etudiante_b2_ne_se_voit_jamais_proposer_une_exigence_c1_comme_realiste_ou_sure() -> None:
    f = fiche(francais_min="C1", priorite_c1=True)
    rep = lancer([f])
    assert [p.categorie for p in rep.propositions] == ["ambitieux"]
    assert all(p.categorie not in ("realiste", "sur") for p in rep.propositions)
    ecart = " ".join(rep.propositions[0].ecarts)
    assert "C1" in ecart and "B2" in ecart
    assert rep.propositions[0].exigences.francais_min == "C1"


def test_priorite_c1_sans_exigence_chiffree_superieure_reste_ambitieux_pour_un_b2() -> None:
    rep = lancer([fiche(francais_min="B2", priorite_c1=True)])
    assert rep.propositions[0].categorie == "ambitieux"
    assert any("Priorité aux candidats C1" in e for e in rep.propositions[0].ecarts)


def test_deux_niveaux_d_ecart_de_langue_excluent_le_voeu() -> None:
    rep = lancer([fiche(francais_min="C2")])
    assert rep.propositions == []
    assert "2 niveaux d'écart" in rep.exclus[0].raisons[0]


def test_niveau_de_langue_suffisant_et_certifie_donne_realiste_puis_sur_avec_marge() -> None:
    realiste = lancer([fiche(francais_min="B2", moyenne_min=None, moyenne_reference=None,
                             aucune_exigence_confirmee=["moyenne"])])
    assert realiste.propositions[0].categorie == "realiste"
    c1 = profil(francais=NiveauLangueProfil(
        niveau="C1", certificat=CertificatLangue(type="DALF", date_obtention=date(2025, 6, 1))))
    sur = lancer([fiche(francais_min="B2", moyenne_min=10.0)], c1)
    assert sur.propositions[0].categorie == "sur"


# ----------------------------------------------------------------------------- inconnu => à vérifier


def test_exigence_de_langue_inconnue_ne_vaut_jamais_ok() -> None:
    f = fiche(francais_min=None)  # langue non lue, non confirmée « sans exigence »
    assert "langue" in exigences_inconnues(f)
    p = lancer([f]).propositions[0]
    assert p.a_verifier and p.categorie == "a_verifier"
    assert any(c.critere == "langue" and c.resultat == "inconnu" for c in p.criteres)
    assert not any(c.resultat == "ok" and c.critere == "langue" for c in p.criteres)
    assert any("langue" in r.lower() for r in p.raisons_a_verifier)


def test_langue_confirmee_sans_exigence_n_est_plus_a_verifier() -> None:
    f = fiche(francais_min=None, aucune_exigence_confirmee=["langue"])
    assert "langue" not in exigences_inconnues(f)
    assert not any(c.critere.startswith("langue") for c in lancer([f]).propositions[0].criteres)


def test_langue_ambigue_donne_a_verifier_avec_le_texte_releve() -> None:
    f = fiche(francais_min=None, langue_ambigue=True,
              langue_texte="Parcours français : B2 ; parcours anglais : IELTS 6")
    p = lancer([f]).propositions[0]
    assert p.a_verifier
    detail = next(c.detail for c in p.criteres if c.critere == "langue")
    assert "alternatives" in detail and "Parcours français" in detail


@pytest.mark.parametrize("champ", ["niveau_entree_bac_plus", "date_limite", "moyenne_min"])
def test_toute_exigence_inconnue_met_le_voeu_a_verifier(champ: str) -> None:
    surcharge = {champ: None}
    if champ == "moyenne_min":
        surcharge["moyenne_reference"] = None
    p = lancer([fiche(**surcharge)]).propositions[0]
    assert p.a_verifier
    assert p.categorie == "a_verifier"
    assert p.raisons_a_verifier


def test_moyenne_connue_sans_reference_est_a_verifier() -> None:
    p = lancer([fiche(moyenne_reference=None)]).propositions[0]
    assert p.a_verifier and "référence" in " ".join(p.raisons_a_verifier)


def test_donnee_de_profil_absente_est_a_verifier_jamais_ok() -> None:
    p = lancer([fiche()], profil(moyennes=MoyennesProfil(), niveau_diplome_bac_plus=None)).propositions[0]
    assert p.a_verifier
    resultats = {c.critere: c.resultat for c in p.criteres}
    assert resultats["moyenne"] == "inconnu" and resultats["niveau_diplome"] == "inconnu"


def test_niveau_de_francais_absent_du_profil_est_a_verifier() -> None:
    p = lancer([fiche()], profil(francais=NiveauLangueProfil())).propositions[0]
    assert next(c for c in p.criteres if c.critere == "français").resultat == "inconnu"
    assert p.a_verifier


# ----------------------------------------------------------------------------- certificat de langue


def test_tcf_expire_avant_la_rentree_est_a_verifier() -> None:
    p_tcf = profil(francais=NiveauLangueProfil(
        niveau="B2", certificat=CertificatLangue(type="TCF", date_obtention=date(2025, 3, 1))))
    # 2025-03-01 + 24 mois = 2027-03-01 < rentrée 2027-09-01
    p = lancer([fiche()], p_tcf).propositions[0]
    francais = next(c for c in p.criteres if c.critere == "français")
    assert francais.resultat == "inconnu" and "expiré" in francais.detail and p.a_verifier


def test_tcf_valide_a_la_rentree_est_accepte() -> None:
    p_tcf = profil(francais=NiveauLangueProfil(
        niveau="B2", certificat=CertificatLangue(type="TCF", date_obtention=date(2026, 3, 1))))
    p = lancer([fiche()], p_tcf).propositions[0]
    assert next(c for c in p.criteres if c.critere == "français").resultat == "ok"
    assert not p.a_verifier


def test_niveau_declare_sans_certificat_ou_sans_date_est_a_verifier() -> None:
    sans = profil(francais=NiveauLangueProfil(niveau="B2"))
    sans_date = profil(francais=NiveauLangueProfil(niveau="B2", certificat=CertificatLangue(type="DELF")))
    for p_ in (sans, sans_date):
        p = lancer([fiche()], p_).propositions[0]
        assert next(c for c in p.criteres if c.critere == "français").resultat == "inconnu"


def test_certificat_insuffisant_reste_un_ecart_meme_si_expire() -> None:
    p_b1 = profil(francais=NiveauLangueProfil(niveau="B1"))
    p = lancer([fiche(francais_min="B2")], p_b1).propositions[0]
    assert p.categorie == "ambitieux"


# ----------------------------------------------------------------------------- autres filtres durs


def test_date_limite_depassee_exclut_le_voeu() -> None:
    rep = lancer([fiche(date_limite=AUJOURD_HUI - timedelta(days=3))])
    assert rep.propositions == [] and "dépassée" in rep.exclus[0].raisons[0]


def test_candidatures_fermees_excluent_le_voeu() -> None:
    assert lancer([fiche(ferme=True)]).propositions == []


def test_niveau_de_diplome_insuffisant_exclut_et_suffisant_passe() -> None:
    assert lancer([fiche(niveau_entree_bac_plus=5)], profil(niveau_diplome_bac_plus=3)).propositions == []
    ok = lancer([fiche(niveau_entree_bac_plus=4)], profil(niveau_diplome_bac_plus=3))
    assert next(c for c in ok.propositions[0].criteres if c.critere == "niveau_diplome").resultat == "ok"


def test_moyenne_insuffisante_exclut() -> None:
    rep = lancer([fiche(moyenne_min=15.0)], profil(moyennes=MoyennesProfil(derniere_annee=14.0)))
    assert rep.propositions == [] and "Moyenne insuffisante" in rep.exclus[0].raisons[0]


def test_moyenne_comparee_a_la_bonne_reference() -> None:
    f = fiche(moyenne_min=13.0, moyenne_reference="bac")
    p = profil(moyennes=MoyennesProfil(bac=11.0, derniere_annee=16.0))
    assert lancer([f], p).propositions == []


def test_domaine_hors_choix_exclut_et_domaine_inconnu_est_a_verifier() -> None:
    p = profil(domaines_souhaites=["design"])
    assert lancer([fiche(domaines=["informatique"])], p).propositions == []
    inconnu = lancer([fiche(domaines=[])], p).propositions[0]
    assert inconnu.a_verifier


def test_echeance_de_demarche_depassee_met_a_verifier() -> None:
    echeances = [{"code": "x", "libelle": "Dépôt Campus France", "statut": "depassee", "date": None}]
    rep = lancer([fiche()], echeances=echeances)
    assert rep.propositions[0].a_verifier
    assert any("Dépôt Campus France" in a for a in rep.avertissements)


# ----------------------------------------------------------------------------- classement, limite, justification


def test_maximum_sept_voeux_et_ordre_sur_realiste_ambitieux_a_verifier() -> None:
    c1 = profil(francais=NiveauLangueProfil(
        niveau="C1", certificat=CertificatLangue(type="DALF", date_obtention=date(2025, 6, 1))))
    fiches = (
        [fiche(etablissement=f"Sure {i}", francais_min="B1", moyenne_min=9.0) for i in range(2)]
        + [fiche(etablissement=f"Realiste {i}", francais_min="C1") for i in range(2)]
        + [fiche(etablissement=f"Ambitieuse {i}", francais_min="C2") for i in range(1)]
        + [fiche(etablissement=f"Inconnue {i}", francais_min=None) for i in range(3)]
    )
    rep = lancer(fiches, c1)
    assert len(rep.propositions) == 7
    assert rep.nb_non_retenues_faute_de_place == rep.nb_fiches_examinees - len(rep.exclus) - 7
    ordre = [p.categorie for p in rep.propositions]
    assert ordre == sorted(ordre, key=lambda c: {"sur": 0, "realiste": 1, "ambitieux": 2, "a_verifier": 3}[c])
    assert [p.rang for p in rep.propositions] == list(range(1, 8))
    assert ordre[0] == "sur" and ordre[-1] == "a_verifier"
    assert rep.nb_non_retenues_faute_de_place == 1


def test_max_voeux_personnalise_est_respecte() -> None:
    rep = lancer([fiche(etablissement=f"E{i}") for i in range(5)], max_voeux=2)
    assert len(rep.propositions) == 2 and rep.nb_non_retenues_faute_de_place == 3


def test_justification_relie_chaque_critere_a_la_donnee_du_profil() -> None:
    p = lancer([fiche()]).propositions[0]
    assert {c.critere for c in p.criteres} >= {"français", "moyenne", "niveau_diplome", "date_limite"}
    for c in p.criteres:
        assert c.donnee_profil in p.justification and c.exigence_officielle in p.justification
    assert "B2 (DELF du 2025-06-01)" in p.justification
    assert "14/20" in p.justification


def test_sortie_porte_les_exigences_officielles_et_la_date_de_releve() -> None:
    e = lancer([fiche()]).propositions[0].exigences
    assert (e.francais_min, e.moyenne_min, e.date_limite, e.date_releve) == ("B2", 12.0, LIMITE_FUTURE, AUJOURD_HUI)
    assert e.url_officielle == "https://exemple.invalid/fiche"


def test_catalogue_vide_donne_un_avertissement_sans_proposition() -> None:
    rep = lancer([])
    assert rep.propositions == [] and rep.avertissements


# ----------------------------------------------------------------------------- import YAML


def _fiches_yaml() -> list[FicheEntree]:
    chemin = RACINE_PLATEFORME / "config" / "catalogues" / "ecoles_privees_france.yaml"
    return fiches_depuis_yaml(yaml.safe_load(chemin.read_text(encoding="utf-8")))


def test_import_yaml_couvre_les_15_ecoles_toutes_a_verifier() -> None:
    fiches = _fiches_yaml()
    assert len({f.etablissement for f in fiches}) == 15
    assert all(f.source == "yaml" and f.date_releve == date(2026, 11, 13) for f in fiches)
    assert all(exigences_inconnues(f) for f in fiches)  # niveau d'entrée, moyenne, date limite : jamais lus


def test_import_yaml_langue_reprise_seulement_si_non_ambigue_et_dans_la_portee() -> None:
    par_ecole: dict[str, list[FicheEntree]] = {}
    for f in _fiches_yaml():
        par_ecole.setdefault(f.etablissement, []).append(f)
    esiea = {f.intitule: f for f in par_ecole["ESIEA"]}
    assert esiea["Diplôme d'ingénieur (5 ans)"].francais_min == "B2"
    assert esiea["Bachelor Cybersécurité"].francais_min is None  # « (programme ingénieur) » seulement
    assert par_ecole["EPF École d'ingénieurs"][0].francais_min == "B1"
    assert all(f.langue_ambigue and f.francais_min is None for f in par_ecole["Paris School of Business (PSB)"])
    assert all(f.langue_ambigue for f in par_ecole["NEOMA Business School"])
    assert all(f.francais_min is None and not f.langue_ambigue for f in par_ecole["Efrei"])


def test_fiche_refuse_niveau_hors_cecrl_et_url_non_https() -> None:
    with pytest.raises(ValueError):
        fiche(francais_min="C3")
    with pytest.raises(ValueError):
        fiche(url_officielle="http://exemple.invalid")
    with pytest.raises(ValueError):
        fiche(francais_min="B2", langue_ambigue=True)
