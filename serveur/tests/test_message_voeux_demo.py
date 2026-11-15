"""Message de l'agent local quand un vœu est absent du catalogue FICTIF de la page de démonstration."""

from __future__ import annotations

from app.agent_local.action_voeux_demo import message_voeux_non_ajoutes

PHRASE = "la page de démonstration ne connaît que son propre catalogue"


def test_voeu_introuvable_explique_le_catalogue_fictif() -> None:
    msg = message_voeux_non_ajoutes(["ajoute", "introuvable"])
    assert "1 vœu(x) sur 2" in msg
    assert PHRASE in msg
    assert "catalogue réel" in msg


def test_voeu_ambigu_ou_refuse_sans_explication_du_catalogue() -> None:
    msg = message_voeux_non_ajoutes(["ajoute", "ambigu"])
    assert PHRASE not in msg
    assert "contrôlez la fenêtre" in msg
