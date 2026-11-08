"""Conseiller Dossier & Espace Discussion :
- Calcul transparent et explicable du pourcentage estimé d'acceptation / solidité (0 à 100 %).
- Veille sur les prérequis et règles officielles issus des fichiers YAML (`config/demarches/*.yaml`).
- Sélection de la meilleure action prioritaire à entreprendre sur le dossier.
- Espace de discussion persisté et chiffré au repos (AES-256-GCM) par bureau et par candidat.
- Respect absolu de la règle 5 : aucune donnée personnelle n'apparaît dans les journaux.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.chiffrement import chiffrer_champ, dechiffrer_champ
from app.core.config import Parametres
from app.db.tenant import tenant_courant
from app.modeles.discussion_dossier import (
    AuteurMessageDossier,
    MessageDiscussionDossier,
)
from app.modeles.document import DocumentCandidat
from app.modeles.journal_audit import ResultatAudit
from app.schemas.candidat import CandidatSortie
from app.schemas.document import (
    CritereEvaluationSortie,
    EchangeDiscussionSortie,
    EvaluationDossierSortie,
    MessageDiscussionSortie,
    PointVeilleReglementaireSortie,
    StatutPieceRequise,
)
from app.services import audit
from app.services.candidats import obtenir_candidat
from app.services.documents import lister_documents_orm
from app.services.pieces_requises import (
    ConfigDemarche,
    obtenir_demarche,
    verifier_completude_dossier,
)

AVERTISSEMENT_EVALUATION = (
    "Indice estimatif de solidité du dossier calculé selon les prérequis réglementaires "
    "et la complétude des justificatifs. La décision finale d'admission ou de délivrance "
    "du permis/visa relève exclusivement des autorités et établissements compétents."
)


LIBELLES_CHAMPS_CANDIDAT_FR: dict[str, str] = {
    "nom": "Nom de famille",
    "prenom": "Prénom",
    "sexe": "Sexe",
    "date_naissance": "Date de naissance",
    "lieu_naissance": "Lieu de naissance",
    "nationalite": "Nationalité",
    "pays_residence": "Pays de résidence",
    "email": "Adresse e-mail",
    "telephone": "Numéro de téléphone",
    "adresse": "Adresse postale",
    "numero_passeport": "Numéro de passeport",
    "date_expiration_passeport": "Date d'expiration du passeport",
    "niveau_actuel": "Niveau d'études actuel",
    "programme_vise": "Formation / Programme visé",
    "etablissement_vise": "Établissement visé",
    "fonds_disponibles_eur": "Ressources financières disponibles (EUR)",
}

LIBELLES_NIVEAU_SOLIDITE_FR: dict[str, str] = {
    "tres_solide": "Très solide",
    "favorable": "Favorable",
    "fragile": "Fragile (à consolider)",
    "risque_eleve": "Risque élevé de refus",
    "incomplet_ou_bloquant": "Dossier incomplet (pièces ou informations obligatoires manquantes)",
}


def evaluer_dossier(
    *,
    candidat: CandidatSortie,
    documents: list[DocumentCandidat],
    demarche: ConfigDemarche,
    date_reference: date | None = None,
) -> EvaluationDossierSortie:
    """Calcule le score de solidité / chances d'acceptation sur 100 points répartis en 4 critères :
    1. Complétude des informations obligatoires (20 pts)
    2. Pièces justificatives obligatoires et validité des dates (40 pts)
    3. Capacité financière par rapport au seuil réglementaire de la démarche (25 pts)
    4. Cohérence du projet académique et pièces de renforcement (15 pts)
    """
    completude = verifier_completude_dossier(
        candidat=candidat,
        documents=documents,
        demarche=demarche,
        date_reference=date_reference,
    )

    points_forts: list[str] = []
    risques: list[str] = []
    actions: list[str] = []
    criteres: list[CritereEvaluationSortie] = []

    # 1. Complétude des champs obligatoires (sur 20 points)
    nb_champs_total = max(len(demarche.champs_candidat_requis), 1)
    nb_champs_manquants = len(completude.champs_candidat_manquants)
    nb_champs_ok = nb_champs_total - nb_champs_manquants
    pts_champs = round(20 * (nb_champs_ok / nb_champs_total))
    if nb_champs_manquants == 0:
        comm_champs = "Toutes les données obligatoires de la fiche candidat sont renseignées."
        points_forts.append("Fiche d'identité et de parcours complète.")
    else:
        libelles_ch = [
            LIBELLES_CHAMPS_CANDIDAT_FR.get(ch, ch)
            for ch in completude.champs_candidat_manquants
        ]
        liste_ch = ", ".join(libelles_ch)
        comm_champs = f"Informations obligatoires à renseigner : {liste_ch}."
        risques.append(f"Informations manquantes dans la fiche candidat : {liste_ch}.")
        actions.append(
            f"Compléter dans la fiche candidat : {liste_ch} "
            "(aucune valeur par défaut n'est inventée par la plateforme)."
        )
    criteres.append(
        CritereEvaluationSortie(
            code="completude_fiche",
            libelle="Complétude de la fiche candidat",
            points_obtenus=pts_champs,
            points_max=20,
            commentaire=comm_champs,
        )
    )

    # 2. Pièces justificatives obligatoires et validité (sur 40 points)
    pieces_obligatoires = [p for p in completude.pieces if p.obligatoire]
    nb_obl_total = max(len(pieces_obligatoires), 1)
    pieces_obl_valides = [
        p for p in pieces_obligatoires if p.statut == StatutPieceRequise.VALIDE
    ]
    pts_pieces = round(40 * (len(pieces_obl_valides) / nb_obl_total))

    for p in pieces_obligatoires:
        if p.statut == StatutPieceRequise.MANQUANTE:
            risques.append(f"Pièce obligatoire manquante : {p.libelle}.")
            actions.append(f"Ajouter la pièce obligatoire « {p.libelle} ».")
        elif p.statut == StatutPieceRequise.EXPIREE:
            risques.append(f"Pièce obligatoire expirée : {p.libelle}.")
            actions.append(
                f"Renouveler et remplacer immédiatement la pièce expirée « {p.libelle} »."
            )
        elif p.statut == StatutPieceRequise.VALIDITE_INSUFFISANTE:
            risques.append(
                f"Validité restante insuffisante pour « {p.libelle} » ({p.detail})."
            )
            actions.append(
                f"Fournir un document « {p.libelle} » couvrant la durée minimale réglementaire."
            )
        elif p.statut == StatutPieceRequise.EXPIRATION_NON_RENSEIGNEE:
            risques.append(f"Date d'expiration non renseignée pour « {p.libelle} ».")
            actions.append(f"Renseigner la date d'expiration de la pièce « {p.libelle} ».")

    if len(pieces_obl_valides) == len(pieces_obligatoires):
        comm_pieces = "Toutes les pièces justificatives obligatoires sont présentes et valides."
        points_forts.append("Dossier documentaire obligatoire complet et en cours de validité.")
    else:
        comm_pieces = (
            f"{len(pieces_obl_valides)} sur {len(pieces_obligatoires)} pièces obligatoires déposées et valides."
        )
    criteres.append(
        CritereEvaluationSortie(
            code="pieces_obligatoires",
            libelle="Pièces justificatives obligatoires et validité",
            points_obtenus=pts_pieces,
            points_max=40,
            commentaire=comm_pieces,
        )
    )

    # 3. Capacité financière par rapport au seuil réglementaire (sur 25 points)
    seuil = demarche.seuil_fonds_recommande_eur or 7380
    fonds = candidat.fonds_disponibles_eur
    if fonds is None:
        pts_fin = 0
        comm_fin = f"Fonds disponibles non renseignés (seuil réglementaire de référence : {seuil} EUR)."
        risques.append(
            f"Capacité financière non renseignée (minimum réglementaire de référence : {seuil} EUR)."
        )
        actions.append(
            f"Renseigner les fonds disponibles et vérifier qu'ils atteignent au moins {seuil} EUR."
        )
    elif fonds < int(seuil * 0.8):
        pts_fin = 5
        comm_fin = (
            f"Fonds déclarés ({fonds} EUR) nettement inférieurs au seuil réglementaire ({seuil} EUR)."
        )
        risques.append(
            f"Risque élevé de refus pour motif financier : {fonds} EUR déclarés pour {seuil} EUR requis."
        )
        actions.append(
            f"Renforcer impérativement les preuves financières d'au moins {seuil - fonds} EUR "
            "(garant supplémentaire, attestation bancaire consolidée ou CPG/GIC)."
        )
    elif fonds < seuil:
        pts_fin = 13
        comm_fin = (
            f"Fonds déclarés ({fonds} EUR) légèrement sous le seuil réglementaire ({seuil} EUR)."
        )
        risques.append(
            f"Marge financière insuffisante ({fonds} EUR pour {seuil} EUR recommandés)."
        )
        actions.append(
            f"Compléter le justificatif financier d'au moins {seuil - fonds} EUR pour atteindre le seuil."
        )
    elif fonds < int(seuil * 1.2):
        pts_fin = 21
        comm_fin = f"Fonds déclarés ({fonds} EUR) conformes au seuil minimal ({seuil} EUR)."
        points_forts.append(f"Seuil financier réglementaire atteint ({fonds} EUR pour {seuil} EUR requis).")
    else:
        pts_fin = 25
        comm_fin = (
            f"Fonds déclarés ({fonds} EUR) supérieurs de plus de 20 % au seuil ({seuil} EUR)."
        )
        points_forts.append(
            f"Capacité financière solide avec marge de sécurité ({fonds} EUR pour {seuil} EUR requis)."
        )

    criteres.append(
        CritereEvaluationSortie(
            code="capacite_financiere",
            libelle="Capacité financière et seuils réglementaires",
            points_obtenus=pts_fin,
            points_max=25,
            commentaire=comm_fin,
        )
    )

    # 4. Cohérence académique et pièces facultatives de renforcement (sur 15 points)
    pts_acad = 0
    if candidat.niveau_actuel:
        pts_acad += 3
    if candidat.programme_vise:
        pts_acad += 4
    if candidat.etablissement_vise:
        pts_acad += 4

    pieces_facultatives_valides = [
        p
        for p in completude.pieces
        if not p.obligatoire and p.statut == StatutPieceRequise.VALIDE
    ]
    if pieces_facultatives_valides:
        pts_acad += 4
        noms_fac = ", ".join(p.libelle for p in pieces_facultatives_valides)
        points_forts.append(f"Pièce(s) de renforcement fournie(s) : {noms_fac}.")
    else:
        pieces_fac_manquantes = [p for p in completude.pieces if not p.obligatoire]
        if pieces_fac_manquantes:
            lib_fac = pieces_fac_manquantes[0].libelle
            actions.append(
                f"Ajouter la pièce recommandée « {lib_fac} » pour gagner jusqu'à 4 % d'acceptation supplémentaires."
            )

    pts_acad = min(pts_acad, 15)
    comm_acad = (
        "Projet d'études complet et appuyé par les pièces de renforcement."
        if pts_acad == 15
        else "Préciser le parcours et joindre les pièces recommandées (lettre explicative ou attestation de langue) renforce la crédibilité du projet."
    )
    criteres.append(
        CritereEvaluationSortie(
            code="coherence_projet",
            libelle="Cohérence académique et pièces de renforcement",
            points_obtenus=pts_acad,
            points_max=15,
            commentaire=comm_acad,
        )
    )

    score_total = pts_champs + pts_pieces + pts_fin + pts_acad

    if not completude.pret_pour_prerequis:
        niveau = "incomplet_ou_bloquant"
    elif score_total >= 85:
        niveau = "tres_solide"
    elif score_total >= 70:
        niveau = "favorable"
    elif score_total >= 50:
        niveau = "fragile"
    else:
        niveau = "risque_eleve"

    meilleure_action = (
        actions[0]
        if actions
        else "Le dossier respecte tous les prérequis : vous pouvez lancer le pré-remplissage supervisé."
    )

    veille = [
        PointVeilleReglementaireSortie(
            titre=v.titre, resume=v.resume, reference=v.reference
        )
        for v in demarche.veille_reglementaire
    ]

    return EvaluationDossierSortie(
        candidat_id=candidat.id,
        code_demarche=demarche.code,
        libelle_demarche=demarche.libelle,
        pourcentage_acceptation_estime=score_total,
        niveau_solidite=niveau,
        pret_pour_soumission_humaine=completude.pret_pour_prerequis,
        meilleure_action_recommandee=meilleure_action,
        points_forts=points_forts,
        risques_et_blocages=risques,
        actions_prioritaires=actions,
        criteres=criteres,
        veille_reglementaire=veille,
        avertissement=AVERTISSEMENT_EVALUATION,
    )


def _rediger_reponse_conseiller(
    question: str, evaluation: EvaluationDossierSortie
) -> str:
    """Construit une réponse structurée en français clair (sans balises de code technique)
    à partir de l'évaluation réelle du dossier, du Guide officiel Études en France Septembre 2026
    et des règles de veille réglementaire de la démarche."""
    from app.agent_local.guide_campus_france_2026 import (
        repondre_question_guide_campus_france,
    )

    q_norm = question.lower()
    libelle_niveau = LIBELLES_NIVEAU_SOLIDITE_FR.get(
        evaluation.niveau_solidite, evaluation.niveau_solidite
    )

    lignes: list[str] = [
        f"Avis du Conseiller sur le dossier — {evaluation.libelle_demarche}",
        f"• Score d'acceptation estimé : {evaluation.pourcentage_acceptation_estime} % ({libelle_niveau})",
        f"• Priorité immédiate : {evaluation.meilleure_action_recommandee}",
    ]

    if evaluation.code_demarche == "campus_france":
        reponses_guide = repondre_question_guide_campus_france(question)
        if reponses_guide:
            lignes.append("\nRéponse selon le Guide officiel Études en France (Septembre 2026 — Algérie) :")
            for bloc in reponses_guide:
                lignes.append(bloc)

    if any(
        m in q_norm
        for m in (
            "loi",
            "règle",
            "regle",
            "prérequis",
            "prerequis",
            "nouve",
            "seuil",
            "finan",
            "ircc",
            "canada",
            "caq",
            "pal",
            "lap",
            "dli",
        )
    ):
        lignes.append("\nPrérequis et règles officielles à jour :")
        for pt in evaluation.veille_reglementaire:
            lignes.append(f"• {pt.titre} ({pt.reference}) : {pt.resume}")

    if evaluation.risques_et_blocages:
        lignes.append("\nPoints bloquants ou pièces manquantes à corriger :")
        for r in evaluation.risques_et_blocages:
            lignes.append(f"• {r}")

    if evaluation.points_forts:
        lignes.append("\nPoints forts actuels du dossier :")
        for pf in evaluation.points_forts:
            lignes.append(f"• {pf}")

    if evaluation.actions_prioritaires:
        lignes.append("\nPlan d'action par ordre de priorité :")
        for idx, act in enumerate(evaluation.actions_prioritaires, start=1):
            lignes.append(f"{idx}. {act}")

    lignes.append("\nDétail du score sur 100 points :")
    for c in evaluation.criteres:
        lignes.append(
            f"• {c.libelle} : {c.points_obtenus} / {c.points_max} points — {c.commentaire}"
        )

    lignes.append(f"\nNote : {evaluation.avertissement}")
    return "\n".join(lignes)


def _dechiffrer_message(
    msg: MessageDiscussionDossier, cle_maitresse: bytes
) -> MessageDiscussionSortie:
    texte = (
        dechiffrer_champ(
            cle_maitresse, msg.tenant_id, "message_discussion", msg.contenu_chiffre
        )
        or ""
    )
    return MessageDiscussionSortie(
        id=msg.id,
        candidat_id=msg.candidat_id,
        code_demarche=msg.code_demarche,
        auteur=msg.auteur.value,
        utilisateur_id=msg.utilisateur_id,
        contenu=texte,
        score_solidite_pourcent=msg.score_solidite_pourcent,
        cree_le=msg.cree_le,
    )


def poser_question_dossier(
    db: Session,
    *,
    candidat_id: uuid.UUID,
    code_demarche: str,
    message_utilisateur: str,
    acteur_id: uuid.UUID,
    parametres: Parametres,
    cle_maitresse: bytes,
) -> EchangeDiscussionSortie:
    tid = tenant_courant(db)
    if tid is None:
        raise RuntimeError("Contexte bureau (tenant) manquant sur la session.")

    candidat = obtenir_candidat(db, candidat_id=candidat_id, cle_maitresse=cle_maitresse)
    docs_orm = lister_documents_orm(db, candidat_id=candidat_id)
    demarche = obtenir_demarche(parametres.dossier_demarches, code_demarche)

    evaluation = evaluer_dossier(
        candidat=candidat,
        documents=docs_orm,
        demarche=demarche,
    )

    msg_user = MessageDiscussionDossier(
        id=uuid.uuid4(),
        tenant_id=tid,
        candidat_id=candidat.id,
        code_demarche=demarche.code,
        auteur=AuteurMessageDossier.UTILISATEUR,
        utilisateur_id=acteur_id,
        contenu_chiffre=chiffrer_champ(
            cle_maitresse, tid, "message_discussion", message_utilisateur.strip()
        )
        or "",
        score_solidite_pourcent=evaluation.pourcentage_acceptation_estime,
    )
    db.add(msg_user)
    db.flush()

    texte_reponse = _rediger_reponse_conseiller(message_utilisateur, evaluation)
    msg_assistant = MessageDiscussionDossier(
        id=uuid.uuid4(),
        tenant_id=tid,
        candidat_id=candidat.id,
        code_demarche=demarche.code,
        auteur=AuteurMessageDossier.ASSISTANT,
        utilisateur_id=None,
        contenu_chiffre=chiffrer_champ(
            cle_maitresse, tid, "message_discussion", texte_reponse
        )
        or "",
        score_solidite_pourcent=evaluation.pourcentage_acceptation_estime,
    )
    db.add(msg_assistant)

    audit.journaliser(
        db,
        "dossier.discussion_avis",
        ResultatAudit.SUCCES,
        acteur_id=acteur_id,
        ressource_type="candidat",
        ressource_id=candidat.id,
        details={
            "code_demarche": demarche.code,
            "score_solidite_pourcent": evaluation.pourcentage_acceptation_estime,
        },
    )
    db.commit()

    return EchangeDiscussionSortie(
        question=_dechiffrer_message(msg_user, cle_maitresse),
        reponse=_dechiffrer_message(msg_assistant, cle_maitresse),
        evaluation=evaluation,
    )


def lister_messages_dossier(
    db: Session,
    *,
    candidat_id: uuid.UUID,
    code_demarche: str | None,
    cle_maitresse: bytes,
) -> list[MessageDiscussionSortie]:
    # Vérifie que le candidat appartient bien au bureau courant.
    obtenir_candidat(db, candidat_id=candidat_id, cle_maitresse=cle_maitresse)
    conditions = [MessageDiscussionDossier.candidat_id == candidat_id]
    if code_demarche:
        conditions.append(MessageDiscussionDossier.code_demarche == code_demarche)

    lignes = db.scalars(
        select(MessageDiscussionDossier)
        .where(*conditions)
        .order_by(
            MessageDiscussionDossier.cree_le.asc(),
            MessageDiscussionDossier.id,
        )
    ).all()
    return [_dechiffrer_message(m, cle_maitresse) for m in lignes]
