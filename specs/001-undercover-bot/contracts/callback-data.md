# Contrat : boutons et données de rappel

Les boutons en ligne de Telegram renvoient une chaîne de 64 octets maximum. Format :
`<action>:<game_id>[:<argument>]`. `game_id` est court (8 caractères alphanumériques) pour rester
sous la limite.

| Action | Données | Émetteur autorisé | Effet |
|---|---|---|---|
| `join` | `join:<game_id>` | tout utilisateur | Inscription au lobby (refus si complet, déjà dans une partie) |
| `leave` | `leave:<game_id>` | un inscrit | Désinscription ; transfert du rôle de créateur si besoin (FR-008a) |
| `launch` | `launch:<game_id>` | créateur | Lancement ; en mode solo, démarre ou abrège le compte à rebours |
| `cancel` | `cancel:<game_id>` | créateur | Annule le lobby, le compte à rebours ou la partie |
| `vote` | `vote:<game_id>:<player_id>` | joueur vivant, pas pour soi | Enregistre ou remplace le vote (FR-028) |

## Règles

- Le moteur revalide chaque événement (autorité de l'émetteur, phase, cible vivante) ; le format
  des données n'est qu'un transport. Un bouton périmé (phase terminée) reçoit un retour discret
  « Ce vote est terminé », sans modifier la partie.
- `player_id` suit le format `h:<user_id>` ou `ai:<nom>`, ce qui tient dans la limite de 64 octets.
- Un clic de `vote` est confirmé à l'utilisateur de façon privée (alerte légère) sans dévoiler le
  choix dans le groupe ; le détail « qui a voté pour qui » n'est publié qu'à la clôture (FR-030).
- Lien profond de démarrage : `https://t.me/<bot>?start=<game_id>`, affiché aux inscrits ⚠️ (FR-004).
