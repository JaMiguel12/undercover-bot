# Contrat : actions des agents IA

Interface entre `ai/agent.py` et le LLM, et entre l'agent et l'orchestrateur. L'agent ne reçoit
que la vue publique (FR-049).

## Entrée commune (PublicView sérialisée)

```json
{
  "viewer": "Kendall IA",
  "own_word": "thé",
  "alive": ["Zendaya IA", "Marie", "Paul"],
  "descriptions": [{"round": 1, "player": "Marie", "text": "chaud le matin"}],
  "votes": [{"round": 1, "voter": "Paul", "target": "Marie"}],
  "eliminations": [{"round": 1, "player": "Luc", "role": "Civil"}],
  "persona": "joueuse, un peu taquine, indices imagés"
}
```

Aucun champ pour le rôle du joueur qui agit ni pour les mots ou rôles des autres joueurs encore en
jeu. Un test vérifie que cette structure ne peut pas les contenir.

## Sorties attendues (JSON strict)

| Action | Sortie | Validation applicative | Repli |
|---|---|---|---|
| Décrire | `{"description": "..."}` | ≤ 6 mots ; ne contient ni le mot de l'IA ni sa racine évidente ; différente de toute description déjà donnée dans la partie | 3 tentatives, puis « Je passe mon tour 🤐 » |
| Voter | `{"vote": "<nom exact>"}` | Nom d'un joueur vivant, différent de l'IA | Vote aléatoire parmi les joueurs valides |
| Deviner | `{"guess": "..."}` | Une chaîne non vide : un mot ou une expression | « Je ne sais pas » (devinette ratée) |

## Interface Python exposée à l'orchestrateur

```text
async describe(view: PublicView) -> str        # texte à publier, ou « Je passe mon tour 🤐 »
async vote(view: PublicView, rng) -> str       # id du joueur ciblé ; ne lève jamais
async guess(view: PublicView) -> str           # mot proposé, ou « Je ne sais pas » ; ne lève jamais
```

Garanties : aucune de ces méthodes ne lève d'exception vers l'orchestrateur ni ne dépasse le délai
global d'action ; une défaillance du LLM produit toujours le repli correspondant (FR-055).

## Client LLM (`ai/groq_client.py`)

- Modèle lu dans `GROQ_MODEL` ; clé dans `GROQ_API_KEY`.
- Un timeout par appel ; jusqu'à 3 essais avec backoff exponentiel sur 429 et erreurs réseau.
- Retourne le texte JSON brut ou lève une erreur typée unique (`LLMUnavailable`) capturée par
  l'agent.

## Comportement visible

- Avant chaque publication d'une IA, l'indicateur « en train d'écrire » est affiché pendant 2 à 5 s
  (délai aléatoire, FR-054).
- Le vote d'une IA est silencieux : aucun message, seulement un bulletin (FR-048).
- Les prompts, en français, sont centralisés dans `ai/prompts.py` et encodent la stratégie de la
  section 4.4 du brief.
