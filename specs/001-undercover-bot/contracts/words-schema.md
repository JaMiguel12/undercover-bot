# Contrat : base de mots (`data/words.json`)

## Format

Un tableau JSON d'objets :

```json
[
  {"id": 1, "categorie": "Nourriture et boissons", "mots": ["café", "thé", "chocolat chaud"]}
]
```

| Champ | Type | Règle |
|---|---|---|
| `id` | entier | Unique dans tout le fichier |
| `categorie` | chaîne non vide | Libellé libre (15 catégories à la livraison) |
| `mots` | tableau de 3 chaînes | Exactement 3 mots, non vides, distincts entre eux |

L'ordre des mots dans un trio n'a pas d'importance : il est mélangé à chaque partie (FR-014).

## Validation au démarrage (FR-057)

Le chargeur (`game/words.py`) refuse la base, avec une erreur explicite qui nomme l'id fautif, si :

- le fichier n'est pas un tableau, ou un objet n'a pas les trois champs ;
- un `id` est en double ;
- un trio n'a pas exactement 3 mots, ou contient un mot vide ;
- deux mots d'un trio sont identiques **après normalisation** (majuscules, accents, tirets).

Une base invalide empêche le bot de démarrer (l'erreur s'affiche dans la console, le processus
s'arrête avec un code non nul).

## Tirage (FR-058)

`draw(trios, played_ids, rng)` renvoie un trio non présent dans `played_ids` (l'historique du
groupe). Quand `played_ids` couvre tous les trios, le cycle recommence avec un historique vide.

## Livraison

Le contenu initial (201 trios, 15 catégories) est extrait tel quel de l'annexe A de
`docs/UNDERCOVER_BRIEF.md`. La base se complète en éditant le fichier, sans toucher au code (FR-059).
