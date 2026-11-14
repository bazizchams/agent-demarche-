"""Schémas de la discussion de l'agent (événements, consignes, commandes)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TypeEvenement = Literal["agent", "action", "alerte", "demande_humaine", "utilisateur", "commande"]
EtatAgent = Literal["en_cours", "pause", "arret"]


class EvenementEntree(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: TypeEvenement
    texte: str = Field(min_length=1, max_length=2000)
    code: str | None = Field(default=None, max_length=20)


class EvenementSortie(BaseModel):
    id: uuid.UUID
    tache_id: uuid.UUID
    seq: int
    type: TypeEvenement
    auteur: Literal["agent", "humain"]
    code: str | None = None
    texte: str
    cree_le: datetime
    traite: bool = False


class ListeEvenementsSortie(BaseModel):
    elements: list[EvenementSortie]
    dernier: int
    etat: EtatAgent


class MessageEntree(BaseModel):
    model_config = ConfigDict(extra="forbid")
    texte: str = Field(min_length=1, max_length=1000)


class MessageSortie(BaseModel):
    message: EvenementSortie
    refuse: bool
    reponse: EvenementSortie | None = None


class CommandeSortie(BaseModel):
    etat: EtatAgent
    evenement: EvenementSortie


class MessagesEnAttenteSortie(BaseModel):
    messages: list[EvenementSortie]
    commandes: list[str]
    etat: EtatAgent
