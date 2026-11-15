"""Messages explicites du contrôle `controler_texte` (projet professionnel).

Chaque élément dit ce qui est cité, ce qui manque et quoi faire. Le mot-clé cité reste entre « »
pour que la détection reste testable.
"""

from app.services.projet_professionnel import controler_texte


def test_chiffre_cite_et_absent_des_faits_message_explicite():
    elements = controler_texte("J'ai 17 ans d'expérience.", "Licence en droit")

    assert elements == [
        "Le projet cite le chiffre « 17 » mais il ne figure dans aucun fait confirmé : vérifiez-le ou retirez-le."
    ]


def test_certificat_cite_sans_attestation_message_explicite():
    elements = controler_texte("Je possède le TCF.", "Licence en droit")

    assert elements == [
        "Le projet cite le certificat « TCF » mais aucune attestation TCF n'est confirmée : "
        "confirmez l'attestation ou retirez la mention."
    ]


def test_niveau_de_langue_cite_sans_attestation_message_explicite():
    elements = controler_texte("Je parle le français au niveau C2.", "Licence en droit")

    assert elements == [
        "Le projet cite le niveau de langue « C2 » mais aucune attestation de ce niveau n'est confirmée : "
        "confirmez-le ou retirez la mention."
    ]


def test_baccalaureat_cite_sans_pièce_message_explicite():
    elements = controler_texte("Titulaire du baccalauréat.", "Licence en droit")

    assert elements == [
        "Le projet cite le baccalauréat mais aucune pièce de baccalauréat n'est confirmée : "
        "confirmez le relevé du bac ou retirez la mention."
    ]


def test_licence_citee_sans_pièce_message_explicite():
    elements = controler_texte("Je possède une licence en droit.", "Bac série S")

    assert elements == [
        "Le projet cite la licence mais aucune pièce de licence n'est confirmée : "
        "confirmez le relevé ou retirez la mention."
    ]


def test_master_cite_sans_pièce_message_explicite():
    elements = controler_texte("Je vise un master en droit.", "Licence en droit")

    assert elements == [
        "Le projet cite le master mais aucune pièce de master n'est confirmée : "
        "confirmez le relevé ou retirez la mention."
    ]


def test_intitule_cite_absent_des_faits_message_explicite():
    elements = controler_texte("Je vise un master en droit.", "Master en informatique")

    assert elements == [
        "Le projet cite l'intitulé « master droit » mais il ne figure dans aucun fait confirmé : "
        "vérifiez-le ou retirez-le."
    ]


def test_aucun_message_ne_reprend_l_ancienne_formulation():
    texte = "J'ai 17 ans, le TCF, le niveau C1, un master en droit et une licence en économie."

    elements = controler_texte(texte, "Bac série S")

    assert elements
    assert not any("absent des faits fournis" in element for element in elements)
