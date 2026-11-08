"""Outil en ligne de commande d'administration de la plateforme.

Usage (depuis le dossier `serveur/`) :
    python -m app.cli creer-bureau --nom "Bureau Alger Centre" --slug bureau-alger --email-admin admin@exemple.dz --nom-admin "Responsable"
    python -m app.cli lister-bureaux
"""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import select

from app.core.chiffrement import (
    charger_ou_creer_cle_maitresse,
    exporter_cle_secours,
)
from app.core.config import obtenir_parametres
from app.core.erreurs import ErreurMetier
from app.db.session import creer_fabrique_sessions, creer_moteur
from app.db.tenant import sans_filtre_tenant
from app.modeles.bureau import Bureau
from app.services.bureaux import provisionner_bureau_et_admin


def _demander_mot_de_passe() -> str:
    mdp1 = getpass.getpass("Mot de passe administrateur (min. 12 caractères) : ")
    mdp2 = getpass.getpass("Confirmez le mot de passe : ")
    if mdp1 != mdp2:
        print("Erreur : les deux mots de passe ne correspondent pas.", file=sys.stderr)
        sys.exit(2)
    return mdp1


def _cmd_creer_bureau(args: argparse.Namespace) -> int:
    parametres = obtenir_parametres()
    mot_de_passe = args.mot_de_passe or _demander_mot_de_passe()
    moteur = creer_moteur(parametres.url_base_donnees)
    Fabrique = creer_fabrique_sessions(moteur)
    try:
        with Fabrique() as db:
            bureau, admin = provisionner_bureau_et_admin(
                db,
                nom_bureau=args.nom,
                slug=args.slug,
                email_admin=args.email_admin,
                nom_admin=args.nom_admin,
                mot_de_passe_admin=mot_de_passe,
                parametres=parametres,
                doit_changer_mot_de_passe=args.temporaire,
            )
            print(f"Bureau créé : id={bureau.id} slug={bureau.slug}")
            print(f"Administrateur créé : id={admin.id} role={admin.role.value}")
        return 0
    except ErreurMetier as exc:
        print(f"Erreur ({exc.code}) : {exc.message}", file=sys.stderr)
        return 1
    finally:
        moteur.dispose()


def _cmd_lister_bureaux(_args: argparse.Namespace) -> int:
    parametres = obtenir_parametres()
    moteur = creer_moteur(parametres.url_base_donnees)
    Fabrique = creer_fabrique_sessions(moteur)
    try:
        with Fabrique() as db, sans_filtre_tenant(db):
            bureaux = db.scalars(select(Bureau).order_by(Bureau.cree_le.asc())).all()
            for b in bureaux:
                etat = "actif" if b.actif else "suspendu"
                print(f"{b.id}  {b.slug:<28}  {etat:<10}  {b.nom}")
        return 0
    finally:
        moteur.dispose()


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(prog="python -m app.cli")
    sous = analyseur.add_subparsers(dest="commande", required=True)

    p_creer = sous.add_parser("creer-bureau", help="Crée un bureau et son premier administrateur.")
    p_creer.add_argument("--nom", required=True, help="Nom complet du bureau")
    p_creer.add_argument("--slug", required=True, help="Identifiant court (ex. bureau-alger)")
    p_creer.add_argument("--email-admin", required=True, help="E-mail du premier administrateur")
    p_creer.add_argument("--nom-admin", required=True, help="Nom affiché de l'administrateur")
    p_creer.add_argument("--mot-de-passe", default=None, help="À éviter en interactif (sera demandé sans écho)")
    p_creer.add_argument("--temporaire", action="store_true", help="Impose le changement du mot de passe à la première connexion")
    p_creer.set_defaults(func=_cmd_creer_bureau)

    p_lister = sous.add_parser("lister-bureaux", help="Liste les bureaux enregistrés.")
    p_lister.set_defaults(func=_cmd_lister_bureaux)

    p_secours = sous.add_parser(
        "exporter-cle-secours",
        help="Génère (si besoin) la clé maîtresse DPAPI et affiche la clé de secours à imprimer.",
    )
    p_secours.set_defaults(func=_cmd_exporter_cle_secours)

    args = analyseur.parse_args(argv)
    return args.func(args)


def _cmd_exporter_cle_secours(_args: argparse.Namespace) -> int:
    parametres = obtenir_parametres()
    cle = charger_ou_creer_cle_maitresse(parametres)
    code = exporter_cle_secours(cle)
    print("CLÉ DE SECOURS À IMPRIMER ET CONSERVER EN LIEU SÛR :")
    print(code)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
