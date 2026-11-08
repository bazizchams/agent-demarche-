"""Vérification de l'état du serveur et de la base de données."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependances import obtenir_db

routeur = APIRouter(tags=["santé"])


@routeur.get("/sante")
def etat_sante(db: Session = Depends(obtenir_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"statut": "ok"}
