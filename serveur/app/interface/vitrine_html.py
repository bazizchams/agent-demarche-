"""Sections HTML de la vitrine publique `/bienvenue`.

Tout le contenu est du HTML statique lisible sans JavaScript. Les démonstrations (flux du hero,
illustrations des étapes, aperçu du tableau de bord) sont décoratives : `aria-hidden`, avec un
libellé textuel pour les lecteurs d'écran. Aucun antislash dans ces chaînes. Les données des
démonstrations sont des exemples fictifs, annoncés comme tels.
"""

from __future__ import annotations

from html import escape

from app.interface.design.shell import icone
from app.schemas.abonnement_conformite import ForfaitCatalogueSortie
from app.services.abonnements import lister_catalogue_forfaits

LIBELLE_DEMO = (
    "Démonstration animée avec des données d'exemple : vous déposez les pièces d'un candidat, "
    "la plateforme les lit et prépare le dossier, puis vous validez le récapitulatif."
)


def _doc(rang: int, nom: str) -> str:
    return (
        f'<div class="fx-doc" style="--i:{rang}">{icone("pieces")}<span>{nom}</span>'
        f'<i class="fx-ok">{icone("coche")}</i></div>'
    )


def hero() -> str:
    return f"""
<section class="v-hero" aria-labelledby="titre-accroche">
<div class="v-hero-fond" data-scene aria-hidden="true"></div>
<div class="v-cadre v-hero-grille">
<div class="v-hero-texte">
<span class="surtitre">Bureaux d'études et d'accompagnement</span>
<h1 id="titre-accroche">Vos dossiers Campus France et IRCC, préparés. Rien ne part sans votre validation.</h1>
<p class="v-lead">Déposez les pièces du candidat. La plateforme lit les documents, prépare le
dossier et propose des vœux de formation. Votre équipe relit, corrige et valide : l'agent s'arrête avant le
bouton final.</p>
<div class="v-actions"><a class="btn btn-primaire btn-lg" href="/inscription">Créer mon bureau</a>
<a class="btn btn-contour btn-lg" href="#comment">Voir comment ça marche</a></div>
<ul class="v-garanties"><li>{icone("coche")}30 jours d'essai</li>
<li>{icone("coche")}Validation humaine obligatoire</li><li>{icone("coche")}CAPTCHA et double authentification : à vous</li></ul>
</div>
<div class="flux" data-flux role="group" aria-label="{escape(LIBELLE_DEMO)}">
<div class="flux-tete" aria-hidden="true">
<ol class="flux-legende"><li class="fl-1"><b>1</b>Vous déposez</li><li class="fl-2"><b>2</b>La plateforme prépare</li><li class="fl-3"><b>3</b>Vous validez</li></ol>
</div>
<div class="flux-scene" aria-hidden="true">
<div class="fx-col"><span class="fx-titre">Pièces du candidat</span>
{_doc(0, "Passeport.pdf")}{_doc(1, "Relevé bac.pdf")}{_doc(2, "Attestation.pdf")}</div>
<div class="fx-col"><span class="fx-titre">Fiche préparée</span>
<div class="fx-champ" style="--i:0"><small>Nom</small><strong>Candidat Exemple</strong></div>
<div class="fx-champ" style="--i:1"><small>Diplôme</small><strong>Baccalauréat</strong></div>
<div class="fx-champ" style="--i:2"><small>Formation visée</small><strong>Licence 3 Informatique</strong></div>
<span class="fx-verifier">{icone("alerte")}Moyenne à vérifier</span></div>
<div class="fx-col"><span class="fx-titre">Récapitulatif</span>
<div class="fx-ligne" style="--i:0"><span>Pièces reçues</span><b>3 sur 3</b></div>
<div class="fx-ligne" style="--i:1"><span>Champs à vérifier</span><b>1</b></div>
<div class="fx-ligne" style="--i:2"><span>Envoi officiel</span><b>En attente</b></div>
<div class="fx-bouton"><span class="fx-b-attente">Valider le récapitulatif</span>
<span class="fx-b-ok">{icone("coche")}Validé par votre équipe</span></div>
<svg class="fx-curseur" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3l14 8-6 2-3 6z"/></svg></div>
</div>
<div class="flux-controle"><p class="flux-note">Exemple fictif, à titre d'illustration.</p>
<button class="btn btn-fantome btn-sm" type="button" data-pause-anim aria-pressed="false">Mettre l'animation en pause</button></div>
</div>
</div>
</section>
"""


def faits() -> str:
    return """
<div class="v-cadre"><ul class="v-faits" data-reveal>
<li><strong>Validation humaine</strong>L'agent s'arrête avant le bouton final de soumission.</li>
<li><strong>Deux démarches</strong>Études en France (Campus France) et permis d'études IRCC.</li>
<li><strong>30 jours d'essai</strong>Chaque nouveau bureau démarre par une période d'essai.</li>
</ul></div>
"""


def _etape(num: int, ident: str, titre: str, texte: str, illustration: str) -> str:
    return f"""<article class="v-etape" id="{ident}" data-etape data-reveal>
<div class="v-etape-texte"><span class="v-etape-num">Étape {num}</span><h3>{titre}</h3><p>{texte}</p></div>
<div class="il" aria-hidden="true">{illustration}</div>
</article>"""


def _illustrations() -> tuple[str, str, str, str]:
    depot = (
        '<div class="il-zone">'
        f'<div class="il-puce il-anim" style="--i:0">{icone("pieces")}Passeport.pdf<em>2 pages</em></div>'
        f'<div class="il-puce il-anim" style="--i:1">{icone("pieces")}Relevés de notes.pdf<em>4 pages</em></div>'
        f'<div class="il-puce il-anim" style="--i:2">{icone("pieces")}Diplôme.pdf<em>1 page</em></div>'
        "</div>"
    )
    lecture = (
        '<div class="il-page"><span class="il-trait l1"></span><span class="il-trait l2"></span>'
        '<span class="il-trait l3"></span><span class="il-trait l4"></span><span class="il-scan"></span></div>'
        '<div class="il-lus">'
        f'<span class="il-lu il-anim" style="--i:1">{icone("coche")}Nom lu</span>'
        f'<span class="il-lu il-anim" style="--i:2">{icone("coche")}Date de naissance lue</span>'
        f'<span class="il-lu verif il-anim" style="--i:3">{icone("alerte")}Moyenne à vérifier</span></div>'
    )
    proposition = (
        '<ul class="il-liste">'
        '<li class="il-anim" style="--i:0">Récapitulatif du dossier<span class="badge badge-brouillon">Brouillon</span></li>'
        '<li class="il-anim" style="--i:1">Lettre de vœu<span class="badge badge-brouillon">Brouillon</span></li>'
        '<li class="il-anim" style="--i:2">Formations suggérées<span class="badge badge-info">Lecture seule</span></li>'
        '<li class="il-anim" style="--i:3">Relevé de notes<span class="badge badge-completer">Pièce manquante</span></li></ul>'
    )
    validation = (
        '<ul class="il-liste"><li>Récapitulatif figé<span class="badge badge-ok">Prêt</span></li></ul>'
        '<div class="il-valid"><small>Toute modification invalide la validation. La validation est tracée.</small>'
        f'<div class="il-bouton"><span class="il-b-a">Valider le récapitulatif</span>'
        f'<span class="il-b-b">{icone("coche")}Validé par votre équipe</span></div></div>'
    )
    return depot, lecture, proposition, validation


def etapes() -> str:
    depot, lecture, proposition, validation = _illustrations()
    corps = "".join(
        (
            _etape(
                1, "etape-1", "Vous déposez les pièces",
                "Passeport, relevés de notes, diplômes, attestations : vous ajoutez les documents "
                "du candidat dans sa fiche, au même endroit que le reste du dossier.",
                depot,
            ),
            _etape(
                2, "etape-2", "La plateforme lit",
                "Le texte des PDF est lu, les scans passent par une lecture optique (OCR). Chaque "
                "champ repéré est proposé à votre relecture : rien n'est tenu pour exact sans vous.",
                lecture,
            ),
            _etape(
                3, "etape-3", "Elle prépare et propose",
                "Fiche du candidat, récapitulatif, brouillons de lettres de vœux, formations "
                "suggérées depuis le catalogue : ce sont des propositions, pas des décisions. Une "
                "pièce manquante est signalée, jamais inventée.",
                proposition,
            ),
            _etape(
                4, "etape-4", "Vous validez",
                "Un conseiller relit le récapitulatif, le corrige ou le valide. Une fois validé, "
                "il est figé : s'il change, la validation tombe. L'agent s'arrête avant le bouton "
                "final et la validation est inscrite au journal.",
                validation,
            ),
        )
    )
    return f"""
<section class="v-section" id="comment" aria-labelledby="titre-comment">
<div class="v-cadre v-etapes-zone" data-etapes-zone>
<div class="v-etapes-gauche">
<div class="v-entete"><span class="surtitre">Comment ça marche</span>
<h2 id="titre-comment">Du dépôt des pièces à la validation, en quatre temps</h2>
<p>Chaque étape produit quelque chose que votre équipe peut relire avant la suivante.</p></div>
<div class="v-rail" data-rail><span class="v-rail-prog" aria-hidden="true"></span>
<ol class="v-rail-liste" aria-label="Étapes">
<li><a href="#etape-1" class="actif">Déposer les pièces</a></li><li><a href="#etape-2">Lecture des documents</a></li>
<li><a href="#etape-3">Préparation et propositions</a></li><li><a href="#etape-4">Validation humaine</a></li></ol></div>
</div>
<div class="v-etapes">{corps}</div>
</div>
</section>
"""


def suivi() -> str:
    return f"""
<section class="v-section v-section-creuse" aria-labelledby="titre-suivi">
<div class="v-cadre v-suivi">
<div class="v-entete" data-reveal><span class="surtitre">Pour votre équipe</span>
<h2 id="titre-suivi">Chaque dossier, son état, sa prochaine action</h2>
<p>Pièces reçues, démarche en cours, récapitulatif à valider, agent en pause : vous voyez où en est
chaque candidat et ce qu'il reste à faire.</p></div>
<div data-reveal>
<div class="apercu" role="img" aria-label="Aperçu du tableau de bord avec des dossiers d'exemple">
<div class="apercu-fenetre" aria-hidden="true">
<div class="apercu-barre"><span class="apercu-point"></span><span class="apercu-point"></span><span class="apercu-point"></span><span>Tableau de bord · Bureau d'exemple</span></div>
<div class="apercu-corps">
<div class="apercu-nav"><span class="actif">{icone("accueil")}Accueil</span><span>{icone("etudiants")}Étudiants</span>
<span>{icone("globe")}Campus France</span><span>{icone("envoi")}IRCC</span><span>{icone("validation")}Validation</span></div>
<div class="apercu-contenu">
<span class="apercu-titre">Dossiers de la semaine</span>
<div class="apercu-kpis"><div class="apercu-kpi"><span>Dossiers actifs</span><b>24</b></div>
<div class="apercu-kpi"><span>À valider</span><b>3</b></div>
<div class="apercu-kpi alerte"><span>En pause</span><b>2</b></div></div>
<ul class="apercu-dossiers">
<li><div><strong>Études en France · Licence 3 Informatique</strong><small>Pièces 11 sur 11 · récapitulatif prêt</small></div>
<span class="badge badge-valide">Prêt à valider</span>
<div class="barre-progression ok"><div class="barre-progression-remplie" style="width:100%"></div></div></li>
<li><div><strong>IRCC · Permis d'études, Montréal</strong><small>Pièces 7 sur 11</small></div>
<span class="badge badge-completer">À compléter</span>
<div class="barre-progression"><div class="barre-progression-remplie" style="width:64%"></div></div></li>
<li><div><strong>Études en France · Master 1 Gestion</strong><small>CAPTCHA sur le portail : à vous</small></div>
<span class="badge badge-attente">En pause</span>
<div class="barre-progression alerte"><div class="barre-progression-remplie" style="width:82%"></div></div></li>
</ul></div></div></div></div>
<p class="apercu-note">Aperçu avec des dossiers d'exemple.</p>
</div>
</div>
</section>
"""


def _carte_confiance(i: int, nom_icone: str, titre: str, texte: str) -> str:
    return (
        f'<li data-reveal style="--i:{i}"><span class="v-icone">{icone(nom_icone)}</span>'
        f"<h3>{titre}</h3><p>{texte}</p></li>"
    )


def securite() -> str:
    cartes = "".join(
        (
            _carte_confiance(
                0, "validation", "Validation humaine avant tout envoi",
                "L'agent prépare en brouillon et s'arrête avant le bouton final. Seul un employé ou "
                "un administrateur authentifié valide le récapitulatif, jamais l'agent lui-même.",
            ),
            _carte_confiance(
                1, "cadenas", "Un coffre chiffré pour les identifiants",
                "Les mots de passe des comptes des portails ne sont conservés que dans le coffre chiffré "
                "de votre bureau, avec le consentement écrit du candidat. Ils ne sont jamais "
                "renvoyés par l'API ni écrits dans les journaux.",
            ),
            _carte_confiance(
                2, "dossier", "Les données restent dans votre bureau",
                "Chaque bureau dispose d'un espace isolé et ne voit que ses dossiers. Le journal "
                "d'audit ne contient ni nom, ni e-mail, ni numéro de passeport.",
            ),
            _carte_confiance(
                3, "pause", "CAPTCHA et double authentification : à vous",
                "L'agent ne les contourne jamais. Il se met en pause, alerte votre équipe et "
                "attend. Vous suivez l'agent en direct et vous pouvez l'arrêter à tout moment.",
            ),
        )
    )
    return f"""
<section class="v-section" id="securite" aria-labelledby="titre-securite">
<div class="v-cadre">
<div class="v-entete" data-reveal><span class="surtitre">Sécurité et confiance</span>
<h2 id="titre-securite">Une plateforme qui sait où s'arrêter</h2>
<p>Les dossiers de candidats sont des données personnelles : la plateforme est conçue pour
accompagner le respect de la loi algérienne n° 18-07 et du RGPD.</p></div>
<ul class="v-confiance">{cartes}</ul>
<div class="v-limites" data-reveal><h3>Ce que la plateforme ne fait pas</h3>
<ul><li>Elle ne soumet jamais un dossier sans validation humaine.</li>
<li>Elle ne contourne ni CAPTCHA ni double authentification.</li>
<li>Elle ne garantit ni admission, ni visa, ni délai : les décisions appartiennent aux autorités.</li>
<li>Elle n'invente aucune donnée : un champ ou une pièce manquants sont signalés.</li></ul></div>
</div>
</section>
"""


def _carte_forfait(i: int, forfait: ForfaitCatalogueSortie) -> str:
    valeur = escape(forfait.forfait.value)
    classe = "fort" if i == 1 else ""
    bouton = "btn-primaire" if i == 1 else "btn-contour"
    return (
        f'<li class="{classe}" data-reveal style="--i:{i}">'
        f"<h3>{escape(forfait.libelle)}</h3>"
        f'<p class="v-prix"><b>{forfait.prix_mensuel_eur}&nbsp;&euro;</b><span>par mois</span></p>'
        f'<p class="v-quota">{icone("dossier")}'
        f"<span>Jusqu'à {forfait.quota_dossiers_mensuels} dossiers actifs par mois</span></p>"
        f'<a class="btn {bouton} btn-bloc" href="/inscription?forfait={valeur}">'
        "Commencer l'essai</a></li>"
    )


def tarifs() -> str:
    cartes = "".join(_carte_forfait(i, f) for i, f in enumerate(lister_catalogue_forfaits()))
    return f"""
<section class="v-section v-section-creuse" id="tarifs" aria-labelledby="titre-forfaits">
<div class="v-cadre">
<div class="v-entete" data-reveal><span class="surtitre">Tarifs</span>
<h2 id="titre-forfaits">Un prix mensuel selon le nombre de dossiers actifs</h2>
<p>Chaque nouveau bureau démarre par 30 jours d'essai. Prix en euros, par mois.</p></div>
<ul class="v-forfaits">{cartes}</ul>
<p class="v-tarif-note">Le paiement en ligne n'est pas disponible pour le moment. L'inscription ne demande aucun paiement.</p>
</div>
</section>
"""


_QUESTIONS = (
    (
        "L'agent peut-il envoyer un dossier sans moi ?",
        "Non. L'agent prépare le dossier en brouillon, produit un récapitulatif et s'arrête avant "
        "le bouton final. Seul un membre de votre équipe, authentifié, peut valider ce récapitulatif.",
    ),
    (
        "Quelles démarches la plateforme prépare-t-elle ?",
        "Les dossiers Études en France (Campus France) et les demandes de permis d'études IRCC "
        "(Canada). Les démarches sont décrites dans des fichiers de configuration que votre bureau "
        "peut adapter.",
    ),
    (
        "Que se passe-t-il quand un CAPTCHA apparaît ?",
        "L'agent ne le contourne jamais. Il met le dossier en pause et alerte votre équipe, qui "
        "reprend la main. Il en va de même pour une double authentification.",
    ),
    (
        "Où sont conservés les mots de passe des portails ?",
        "Uniquement dans le coffre chiffré de votre bureau, avec le consentement écrit du candidat. "
        "Ils ne sont jamais écrits en clair, jamais renvoyés par l'API, et supprimables à tout moment.",
    ),
    (
        "L'assistant IA voit-il les données des candidats ?",
        "L'assistant qui vous aide à rédiger ne reçoit ni nom, ni adresse e-mail, ni numéro de passeport.",
    ),
    (
        "Garantissez-vous une admission ou un visa ?",
        "Non. La plateforme prépare et organise les dossiers. Les décisions appartiennent aux "
        "établissements et aux autorités compétentes.",
    ),
    (
        "Puis-je payer en ligne ?",
        "Non : le paiement en ligne de l'abonnement n'est pas disponible pour le moment. "
        "L'inscription et l'essai de 30 jours ne demandent aucun paiement.",
    ),
)


def faq() -> str:
    items = "".join(
        f'<details class="v-faq"><summary>{q}</summary><p>{r}</p></details>' for q, r in _QUESTIONS
    )
    return f"""
<section class="v-section" id="faq" aria-labelledby="titre-faq">
<div class="v-cadre v-faq-zone">
<div class="v-entete"><span class="surtitre">Questions fréquentes</span>
<h2 id="titre-faq">Ce que les bureaux nous demandent</h2></div>
<div class="v-faq-liste" data-reveal>{items}</div>
</div>
</section>
"""


def appel() -> str:
    return """
<section class="v-section v-section-appel" aria-labelledby="titre-appel">
<div class="v-cadre"><div class="v-appel" data-reveal>
<div><h2 id="titre-appel">Créez votre bureau, essayez 30 jours</h2>
<p>Vous devenez administrateur de votre bureau. L'essai commence tout de suite.</p></div>
<a class="btn btn-lg" href="/inscription">Créer mon bureau</a>
</div></div>
</section>
"""


def corps_bienvenue() -> str:
    return hero() + faits() + etapes() + suivi() + securite() + tarifs() + faq() + appel()
