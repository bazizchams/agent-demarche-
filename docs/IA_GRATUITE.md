# IA gratuite ou locale (sans clé Anthropic payante)

> **Avertissement d'honnêteté (2026-11-12).** La recherche web automatique n'a pas pu être
> exécutée lors de la rédaction (outils de recherche indisponibles). Ce document repose sur
> les connaissances du rédacteur, **sans chiffre garanti** : les quotas des offres gratuites
> changent souvent. **Vérifiez chaque point sur la page officielle citée avant de décider.**
> Aucun quota précis n'est donc écrit ici, volontairement.

## Principe retenu

La plateforme traite des dossiers d'étudiants (loi algérienne 18-07, RGPD pour les candidats
ou partenaires dans l'UE). Choix par défaut :

1. **Texte sensible : modèle local** (Ollama ou llama.cpp) sur le serveur du bureau. Les
   données ne quittent pas la machine ; aucune clé ; aucun quota ; coût = matériel.
2. **Offre gratuite hébergée : uniquement sur données anonymisées** (texte officiel de
   procédure, questions sans identité). Les niveaux gratuits des fournisseurs autorisent
   souvent l'utilisation des échanges pour améliorer leurs produits : ne jamais y envoyer de
   données de candidats.

## Comparatif (à vérifier sur les sources)

| Option | Gratuit ? | Données | Remarques | Source officielle |
|---|---|---|---|---|
| **Ollama** (local) | Oui, illimité | Restent sur le serveur | API compatible OpenAI (`/v1/chat/completions`, `http://127.0.0.1:11434/v1`). Français correct avec un modèle 7-14B récent (Qwen, Mistral, Llama, Gemma) mais inférieur aux grands modèles ; appels d'outils inégaux selon le modèle. Vérifier la licence du modèle choisi pour l'usage commercial. | https://docs.ollama.com/api/openai-compatibility |
| **llama.cpp `llama-server`** (local) | Oui | Restent sur le serveur | API compatible OpenAI. Même remarque sur les licences de modèles. | https://github.com/ggml-org/llama.cpp |
| **Google AI Studio / API Gemini** | Niveau gratuit à débit limité | Offre gratuite : les conditions prévoient en général l'usage des données pour améliorer les produits ; l'offre payante les exclut. Disponibilité gratuite variable selon les pays. | Point d'accès compatible OpenAI existant. Bon français. | https://ai.google.dev/gemini-api/terms ; https://ai.google.dev/gemini-api/docs/rate-limits |
| **Groq** | Niveau gratuit à débit limité | Hébergé aux États-Unis | Très rapide, modèles ouverts ; compatible OpenAI. | https://console.groq.com/docs/rate-limits |
| **OpenRouter** (modèles `:free`) | Modèles gratuits à quotas bas | Chaque modèle gratuit a son fournisseur final et sa politique : certains journalisent/entraînent | Passerelle compatible OpenAI ; qualité et disponibilité variables. | https://openrouter.ai/docs/api-reference/limits |
| **Mistral (La Plateforme)** | Niveau gratuit d'expérimentation | Entreprise française, hébergement UE ; vérifier si l'usage des données du palier gratuit pour l'entraînement est activé | Meilleur candidat « hébergé UE » ; très bon français ; compatible OpenAI. | https://docs.mistral.ai/deployment/laplateforme/tier/ |
| **Cerebras** | Niveau gratuit à débit limité | Hébergé aux États-Unis | Compatible OpenAI. | https://inference-docs.cerebras.ai/support/rate-limits |

Usage commercial : les niveaux gratuits sont souvent prévus pour le prototypage ; relisez
les conditions d'utilisation de chaque fournisseur avant un usage payant par vos clients.

## Risque juridique, dit franchement

- Envoyer un texte à un fournisseur hébergé à l'étranger est un **transfert de données** à un
  sous-traitant. La loi 18-07 soumet les transferts hors d'Algérie à des conditions (niveau de
  protection adéquat, autorisation/déclaration auprès de l'autorité de protection des
  données) : **à faire valider par un juriste algérien**. Le RGPD impose clauses contractuelles
  et information des personnes pour les résidents UE.
- Un niveau gratuit n'offre en général **pas d'accord de traitement (DPA)** : raison de plus
  de n'y envoyer que du texte anonymisé.
- L'anonymisation fournie (`app/services/anonymisation_ia.py`) est un **filet au mieux** :
  e-mails, téléphones, numéros de passeport, valeurs « nom : … » et termes connus. Elle ne
  détecte pas un nom cité au milieu d'une phrase. Les contextes IA de la plateforme restent
  construits sans donnée personnelle (règle 5).
- Un modèle local supprime ce risque de transfert (mais pas l'obligation de sécuriser le serveur).

## Configuration

Variables (`serveur/.env`) :

```
# Local (recommandé pour le texte sensible)
BE_IA_FOURNISSEUR=openai_compatible
BE_IA_URL_BASE=http://127.0.0.1:11434/v1
BE_IA_MODELE=<modèle installé, ex. celui listé par « ollama list »>

# Hébergé gratuit (données anonymisées uniquement)
BE_IA_FOURNISSEUR=openai_compatible
BE_IA_URL_BASE=https://api.mistral.ai/v1
BE_IA_MODELE=<modèle>
BE_IA_CLE=<clé gratuite du fournisseur>

# Anthropic (inchangé)
BE_IA_FOURNISSEUR=anthropic   # défaut
BE_CLE_API_ANTHROPIC=<clé>
```

`BE_IA_TENTATIVES` (défaut 2) règle les essais sur erreur réseau/429/5xx ; le délai est
`BE_DELAI_LLM_SECONDES`. Une URL locale (localhost, 127.x, réseau privé, `host.docker.internal`)
est traitée comme locale : pas d'anonymisation, `donnees_quittent_serveur = false`. Toute autre
URL est considérée hébergée : texte anonymisé avant envoi. `GET /api/v1/ia/statut` indique le
fournisseur, le modèle et si les données quittent le serveur. Le quota d'essai/mensuel est conservé.

Limite connue : la génération de procédure exige un JSON structuré ; un petit modèle local peut
échouer (réponse 422 « n'a pas pu structurer »). Le client retombe sur une réponse JSON dans le
texte si le modèle ne gère pas les appels d'outils, mais la qualité dépend du modèle.
