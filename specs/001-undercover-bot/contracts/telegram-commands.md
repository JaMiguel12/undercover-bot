# Contrat : commandes Telegram

Interface exposée aux joueurs. Tous les textes sont en français et vivent dans `bot/texts.py`.

## Groupe

| Commande | Qui | Effet | Erreurs |
|---|---|---|---|
| `/nouvelle` | tout membre | Crée un lobby et publie le message du lobby (FR-001) | Partie déjà active dans le groupe ; l'utilisateur est déjà inscrit ailleurs (FR-007) |
| `/lancer` | créateur | Équivaut au bouton « Lancer » | Non créateur ; inscrit sans accès privé (liste nommée, FR-005) |
| `/annuler` | créateur | Annule le lobby ou la partie (FR-008) | Non créateur ; aucune partie |
| `/etat` | tout membre | Phase, joueurs vivants, joueur courant (FR-041) | Aucune partie |
| `/regles` | tout membre | Résumé des règles | — |
| `/classement` | tout membre | Scores cumulés du groupe, IA comprises (FR-040) | Aucun score |

## Privé

| Commande | Effet | Erreurs |
|---|---|---|
| `/start` | Active le bot pour l'utilisateur (`users.can_dm = true`) ; accepte un paramètre de lien profond `?start=<game_id>` qui ramène au lobby (FR-004) | — |
| `/monmot` | Renvoie le mot du joueur pour sa partie en cours (FR-042) | Aucune partie en cours |
| `/aide` | Aide | — |

En privé, un message texte libre n'est interprété que pour la **devinette de Mr. White** : quand une
devinette est attendue de cet utilisateur, son prochain message est sa tentative unique (FR-034).

## Messages du groupe (non commandes)

- Un message texte d'un joueur **dont c'est le tour de décrire** est traité comme sa description
  (FR-023). Tout autre message est ignoré par le moteur.
- Les messages du bot et des IA (préfixe « 🤖 », FR-044) sont les seuls textes émis par le bot.

## Prérequis côté Telegram (FR-046, à documenter dans le README)

- Désactiver le mode privé du bot (`/setprivacy` → Disable) pour lire les descriptions.
- Optionnel : rendre le bot administrateur du groupe pour supprimer une description interdite.
