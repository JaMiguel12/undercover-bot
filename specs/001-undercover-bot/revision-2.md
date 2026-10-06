# Révision 2 des règles du jeu (2026-10-01)

Demandée par le propriétaire du produit après les premiers essais sur un vrai groupe Telegram.
Ce document **remplace** les exigences correspondantes de [spec.md](spec.md) et de
`docs/UNDERCOVER_BRIEF.md` (sections 2.2, 2.3, 2.5, 2.6, 2.7, 2.8 et 2.9). En cas de contradiction,
la révision 2 l'emporte.

## Décisions

| # | Changement | Remplace |
|---|---|---|
| R2-1 | Le compte à rebours du mode solo (temps pour rejoindre) passe de 120 à **30 secondes** (`SOLO_WAIT_TIMEOUT=30`) | FR-010, FR-011 |
| R2-2 | Une description est **un seul mot** (au lieu de 6 mots maximum) | FR-022, FR-050 |
| R2-3 | Le rôle **Mr. White est supprimé** : plus de devinette, plus de variable `GUESS_TIMEOUT`. Seuls 2 mots du trio sont utilisés (civils, undercovers) | FR-014, FR-015, FR-021, FR-034 à FR-036, FR-052 |
| R2-4 | Répartition des rôles : 4 joueurs = 3 civils + 1 undercover ; 5 = 4+1 ; 6 = 5+1 ; 7 = 6+1 ; 8 = 6+2 (Mr. White devient civil) | FR-015 |
| R2-5 | **3 tours de description** (`description_rounds` dans `data/game_config.json`) avant chaque vote : chacun dit un mot par tour, dans le même ordre ; une **manche** = 3 tours + 1 vote | FR-020 à FR-026 |
| R2-6 | **Deux types de partie**, choisis par le créateur dans le lobby (boutons) : *avec élimination* (défaut, comme avant) ou *sans élimination* | nouveau |
| R2-7 | Victoire : les civils gagnent quand tous les undercovers sont éliminés ; les undercovers gagnent quand il ne reste qu'un civil | FR-037 |
| R2-8 | Points : civils +2 chacun si victoire des civils ; undercovers +10 chacun si victoire des undercovers. Plus de points pour Mr. White | FR-039 |

## Mode « sans élimination »

- Un seul vote après les 3 tours de description. Égalité : revote entre les ex æquo, puis tirage
  au sort. Aucun vote exprimé : on rejoue une manche ; après 3 manches sans vote, la partie est
  annulée.
- Le joueur le plus voté est l'**accusé** : s'il est un undercover, les **civils** gagnent (+2 par
  civil) ; sinon les **undercovers** gagnent (+10 par undercover).
- Personne n'est éliminé. L'écran de fin révèle les rôles, les mots et les points.
- **Nouvelle partie automatique** : 60 secondes après l'écran de fin (`RESTART_DELAY=60`), une nouvelle partie démarre
  avec les mêmes membres humains (nouveaux mots, nouveaux rôles, IA recomplétées), dans le même
  mode, **sans compte à rebours solo**. Un membre devenu inscrit dans une autre partie est écarté.
  Le créateur arrête la série avec `/annuler` (pendant la pause ou pendant une partie).
- La relance automatique n'existe **pas** en mode avec élimination, ni après une annulation.
  Elle n'est pas conservée si le bot redémarre pendant la pause.

## Hypothèses prises (à confirmer)

- En mode avec élimination, les 3 tours de description précèdent **chaque** vote, y compris après
  une élimination (le premier orateur tourne toujours parmi les joueurs vivants).
- L'ordre de passage est le même aux 3 tours d'une manche.
- Le créateur peut changer de type de partie tant que la partie n'est pas lancée.
- Les anciennes parties enregistrées avec les règles de la version 1 sont annulées au démarrage.

## Effets sur la configuration

- `.env` : `GUESS_TIMEOUT` supprimé ; `SOLO_WAIT_TIMEOUT` vaut 30 par défaut ; `RESTART_DELAY` (60 par défaut) règle la pause avant la relance automatique.
- `data/game_config.json` : `description_rounds`, rôles `{civilians, undercovers}`, points
  `{civilian_win_per_civilian, infiltrator_win_per_undercover}`.
- Les trios de `data/words.json` gardent 3 mots (la base reste valide) ; le troisième mot n'est
  plus attribué.
