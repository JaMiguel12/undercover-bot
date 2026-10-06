# Feature Specification: Bot Telegram « Undercover »

**Feature Branch**: `001-undercover-bot`

**Created**: 2026-10-01

**Status**: Draft

**Input**: User description: "Lis docs/UNDERCOVER_BRIEF.md sections 1 à 5 et 9. Rédige la spécification fonctionnelle complète du bot Undercover, sans aucun choix technique. Chaque règle de jeu doit devenir une exigence testable."

> **Révision 2 (2026-10-01)** : les règles de jeu ont changé (un mot par description, 3 tours avant
> chaque vote, Mr. White supprimé, deux types de partie, solo à 60 s). Voir
> [revision-2.md](revision-2.md) : en cas de contradiction avec ce document, elle l'emporte.

## Clarifications

### Session 2026-10-01

- Q: Que doit-il se passer quand un joueur humain reste inactif tour après tour ? → A: Rien, la partie continue ; il passe son tour à chaque fois, sans sanction ni élimination.
- Q: Si personne ne vote tour après tour, comment éviter que la partie tourne indéfiniment ? → A: Après 3 tours consécutifs sans aucun vote exprimé, la partie est annulée, le bot l'annonce et aucun point n'est attribué.
- Q: Que se passe-t-il quand le créateur du lobby appuie sur « Quitter » alors que d'autres joueurs sont inscrits ? → A: Le rôle de créateur passe au premier inscrit suivant et le bot l'annonce ; les autres gardent leur inscription. Si le créateur est seul, le lobby est supprimé.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Jouer une partie complète entre amis dans un groupe (Priority: P1)

Un groupe d'amis francophones veut jouer à Undercover par écrit dans un groupe Telegram. Un joueur crée la partie, les autres la rejoignent, le créateur la lance. Chacun reçoit son mot en privé, puis la partie enchaîne des tours de description et de vote jusqu'à une victoire. À la fin, tous les rôles et les trois mots sont révélés, les points sont attribués et le classement de la partie est affiché.

**Why this priority**: c'est le cœur du produit. Sans une partie complète jouable entre humains, rien d'autre n'a de valeur.

**Independent Test**: avec 8 joueurs humains (aucune IA), jouer une partie de bout en bout, de la création du lobby à l'écran de fin, et vérifier que les rôles, mots, tours, votes, éliminations et points respectent les règles.

**Acceptance Scenarios**:

1. **Given** un groupe sans partie active, **When** un joueur envoie la commande de création, **Then** un lobby est créé avec les boutons Rejoindre et Quitter, plus Lancer et Annuler pour le créateur.
2. **Given** un lobby avec des joueurs prêts à recevoir des messages privés, **When** le créateur lance la partie, **Then** chaque humain reçoit en privé son mot, et les civils ont tous le même mot, l'undercover et Mr. White chacun un mot différent.
3. **Given** une phase de description, **When** le joueur dont c'est le tour envoie une description valide dans le groupe, **Then** elle est enregistrée et le tour passe au joueur suivant.
4. **Given** tous les joueurs vivants ont décrit, **When** le bot ouvre le vote, **Then** un bouton par joueur vivant est proposé et le récapitulatif des descriptions du tour est publié.
5. **Given** un vote terminé, **When** un joueur est éliminé, **Then** son rôle (pas son mot) est révélé et le bot affiche qui a voté pour qui.
6. **Given** une condition de victoire remplie, **When** la partie se termine, **Then** le bot révèle tous les rôles et les trois mots, attribue les points et affiche le classement de la partie.

---

### User Story 2 - Compléter la partie avec les IA, y compris en mode solo (Priority: P2)

Quand il manque des joueurs, Zendaya IA, Kendall IA et BFF Diva IA rejoignent automatiquement la partie, dans cet ordre de priorité, et jouent comme des humains : elles décrivent, votent et devinent. Un joueur seul peut lancer une partie contre les trois IA après un dernier appel de 2 minutes.

**Why this priority**: c'est ce qui rend le jeu jouable avec un petit nombre d'amis, et c'est la différenciation du produit, mais il dépend d'une partie humaine fonctionnelle (P1).

**Independent Test**: lancer des parties avec 1 à 8 humains et vérifier le nombre d'IA ajoutées, le total et la répartition des rôles ; couper l'accès au service d'IA et vérifier que la partie va quand même jusqu'au bout.

**Acceptance Scenarios**:

1. **Given** 2 à 5 humains inscrits, **When** le créateur lance, **Then** les 3 IA entrent immédiatement et le total est respectivement 5, 6, 7 ou 8.
2. **Given** 6 humains, **When** le créateur lance, **Then** Zendaya IA et Kendall IA entrent (total 8) ; avec 7 humains, Zendaya IA seule ; avec 8 humains, aucune IA.
3. **Given** un seul humain inscrit, **When** le créateur appuie sur Lancer, **Then** un dernier appel est publié dans le groupe et un compte à rebours de 2 minutes est affiché et mis à jour dans le message du lobby.
4. **Given** le compte à rebours solo en cours et personne d'autre n'a rejoint, **When** le délai expire, **Then** les 3 IA entrent et la partie démarre à 4 joueurs (3 civils, 1 undercover, pas de Mr. White).
5. **Given** le compte à rebours solo en cours, **When** un autre humain rejoint, **Then** la partie démarre à la fin du délai (ou dès que le créateur rappuie sur Lancer) avec la complétion normale.
6. **Given** une IA dont c'est le tour, **When** le service d'IA est indisponible, **Then** l'IA passe son tour (description), vote aléatoirement (vote) ou rate sa devinette, et la partie continue.

---

### User Story 3 - Gérer le lobby et les inscriptions (Priority: P3)

Les joueurs s'inscrivent, quittent, voient en direct la liste des inscrits et l'état de leur accès aux messages privés. Le lancement est bloqué tant qu'un inscrit ne peut pas recevoir de message privé.

**Why this priority**: indispensable pour lancer une partie, mais ses règles sont un sous-ensemble du parcours P1 et peuvent être vérifiées séparément.

**Independent Test**: créer un lobby, inscrire des joueurs avec et sans accès privé, tenter de lancer, vérifier le blocage, le message nommant les joueurs concernés et le lien de démarrage.

**Acceptance Scenarios**:

1. **Given** un lobby ouvert, **When** un joueur rejoint ou quitte, **Then** le message du lobby est mis à jour en direct avec la liste des inscrits.
2. **Given** un inscrit qui n'a jamais démarré le bot, **When** le créateur tente de lancer, **Then** le lancement est bloqué et le bot nomme les joueurs concernés, avec un lien pour démarrer le bot.
3. **Given** un lobby à 8 humains, **When** un 9e joueur tente de rejoindre, **Then** l'inscription est refusée (« partie complète »).
4. **Given** un joueur déjà inscrit dans une partie (dans n'importe quel groupe), **When** il tente de rejoindre une autre partie, **Then** l'inscription est refusée.
5. **Given** un lobby sans activité, **When** 10 minutes s'écoulent, **Then** le lobby expire.

---

### User Story 4 - Confidentialité et équité (Priority: P4)

Aucun mot secret n'apparaît dans le groupe avant la fin de la partie, et les IA ne savent rien de plus qu'un humain.

**Why this priority**: c'est l'exigence la plus importante du projet, mais elle se vérifie comme une propriété transversale des parcours précédents.

**Independent Test**: lancer des parties simulées et inspecter tous les textes émis vers le groupe avant l'écran de fin ; inspecter les informations fournies à chaque IA.

**Acceptance Scenarios**:

1. **Given** une partie en cours, **When** on examine chaque message envoyé dans le groupe avant l'écran de fin, **Then** aucun ne contient un mot secret.
2. **Given** une IA qui doit agir, **When** on examine les informations qui lui sont transmises, **Then** elles se limitent à son mot, à l'historique public et à la liste des vivants, sans son rôle ni les mots ou rôles des autres.

---

### User Story 5 - Classement, état et aide (Priority: P5)

Le groupe consulte le classement cumulé (IA comprises), l'état de la partie en cours et le résumé des règles ; chaque joueur peut redemander son mot en privé.

**Why this priority**: confort et rétention, sans bloquer le jeu.

**Independent Test**: jouer plusieurs parties dans un groupe, puis consulter le classement ; interroger l'état en cours de partie.

**Acceptance Scenarios**:

1. **Given** plusieurs parties terminées dans un groupe, **When** un joueur demande le classement, **Then** les scores cumulés du groupe sont affichés, IA comprises.
2. **Given** une partie en cours, **When** un joueur demande l'état, **Then** le bot affiche la phase, les joueurs vivants et à qui c'est le tour.
3. **Given** un joueur en partie, **When** il demande son mot en privé, **Then** le bot lui renvoie son mot.

---

### User Story 6 - Reprise après interruption (Priority: P6)

Si le bot est interrompu et redémarré en pleine partie, la partie reprend là où elle en était, avec des délais restants cohérents.

**Why this priority**: robustesse, valable une fois le jeu fonctionnel.

**Independent Test**: interrompre le bot pendant un vote, le redémarrer, et vérifier que le même vote reprend avec le délai restant.

**Acceptance Scenarios**:

1. **Given** un vote en cours, **When** le bot redémarre, **Then** la partie reprend au même vote avec un délai restant cohérent.

---

### Edge Cases

- Un joueur dont c'est le tour ne répond pas dans les 60 secondes : son tour est passé et le bot le signale.
- Une description contient le mot secret du joueur : elle est refusée (supprimée si le bot est administrateur du groupe) et une autre description est demandée dans le délai restant.
- Une description dépasse 6 mots : elle est refusée.
- Un humain reste inactif tour après tour : il passe son tour à chaque délai, sans sanction ni élimination automatique, et la partie continue.
- Un message est envoyé par un joueur dont ce n'est pas le tour : il est ignoré, les joueurs peuvent discuter librement.
- Égalité au vote : revote limité aux joueurs à égalité ; nouvelle égalité : tirage au sort parmi eux.
- Aucun vote exprimé : personne n'est éliminé et un nouveau tour de description commence ; après 3 tours consécutifs sans aucun vote, la partie est annulée, le bot l'annonce et aucun point n'est attribué.
- Mr. White est éliminé : une seule tentative de devinette, 60 secondes (humain, en privé) ; s'il ne répond pas, la tentative est ratée.
- Le créateur annule pendant le compte à rebours solo ou la partie en cours : la partie est annulée.
- Une IA reçoit une réponse invalide ou ne répond pas : 3 tentatives pour décrire, puis « Je passe mon tour 🤐 ».
- Un joueur tente de voter pour lui-même : refusé ; il peut changer son vote tant que le vote est ouvert.
- Le créateur quitte le lobby alors que d'autres sont inscrits : le rôle de créateur passe au premier inscrit suivant, le bot l'annonce, les autres gardent leur inscription ; s'il est seul, le lobby est supprimé.
- Une seconde partie est demandée dans un groupe où une partie est déjà active : refusée.
- Une IA joue dans plusieurs groupes en parallèle : autorisé.
- La base de mots est invalide au démarrage : le bot refuse de démarrer avec une erreur explicite.
- Tous les trios ont été joués dans un groupe : le cycle recommence.

## Requirements *(mandatory)*

### Functional Requirements

**Lobby et inscriptions**

- **FR-001**: Le système MUST permettre à un joueur de créer un lobby dans un groupe Telegram, une seule partie active par groupe.
- **FR-002**: Le lobby MUST afficher les boutons « Rejoindre » et « Quitter », ainsi que « Lancer » et « Annuler » pour le créateur, et MUST être mis à jour en direct avec la liste des inscrits.
- **FR-003**: Le système MUST accepter de 1 à 8 humains et MUST refuser toute inscription au-delà avec le message « partie complète ».
- **FR-004**: Le système MUST marquer chaque inscrit ✅ s'il peut recevoir des messages privés, ⚠️ sinon, et MUST afficher un lien de démarrage du bot pour les inscrits ⚠️.
- **FR-005**: Le système MUST bloquer le lancement tant qu'un inscrit ne peut pas recevoir de message privé, et MUST nommer les joueurs concernés.
- **FR-006**: Le système MUST faire expirer un lobby après 10 minutes d'inactivité.
- **FR-007**: Un utilisateur MUST pouvoir être inscrit dans une seule partie à la fois, tous groupes confondus ; les IA MUST pouvoir jouer dans plusieurs groupes en parallèle.
- **FR-008**: Seul le créateur MUST pouvoir lancer ou annuler le lobby ou la partie en cours.
- **FR-008a**: Quand le créateur quitte un lobby où d'autres joueurs sont inscrits, le rôle de créateur MUST passer au premier inscrit suivant et le bot MUST l'annoncer ; si le créateur est seul, le lobby MUST être supprimé.

**Complétion par les IA et mode solo**

- **FR-009**: Le système MUST ajouter les IA au lancement, toujours dans l'ordre Zendaya IA, Kendall IA, BFF Diva IA, selon le tableau : 1 humain → 3 IA (total 4) ; 2 → 3 IA (5) ; 3 → 3 IA (6) ; 4 → 3 IA (7) ; 5 → 3 IA (8) ; 6 → 2 IA (8) ; 7 → 1 IA (8) ; 8 → aucune.
- **FR-010**: Avec un seul humain, « Lancer » MUST publier un dernier appel dans le groupe et démarrer un compte à rebours de 2 minutes (durée configurable), affiché et mis à jour dans le message du lobby.
- **FR-011**: Si personne ne rejoint pendant le compte à rebours, les 3 IA MUST entrer et la partie démarrer à 4 joueurs ; si d'autres humains rejoignent, la partie MUST démarrer à la fin du délai (ou dès que le créateur rappuie sur « Lancer ») avec la complétion normale.
- **FR-012**: Le créateur MUST pouvoir annuler pendant le compte à rebours solo.
- **FR-013**: À partir de 2 humains, « Lancer » MUST démarrer la partie immédiatement.

**Rôles, mots et distribution**

- **FR-014**: Chaque partie MUST utiliser un trio de mots tiré de la base, dont les trois mots sont mélangés aléatoirement puis attribués : Mot A aux civils (commun à tous), Mot B à l'undercover, Mot C à Mr. White.
- **FR-015**: La répartition des rôles MUST suivre le total de joueurs : 4 → 3 civils, 1 undercover, 0 Mr. White ; 5 → 3/1/1 ; 6 → 4/1/1 ; 7 → 5/1/1 ; 8 → 5/2/1.
- **FR-016**: La répartition des rôles MUST être configurable sans modifier la logique du jeu.
- **FR-017**: Les IA MUST pouvoir tirer n'importe quel rôle, comme les humains.
- **FR-018**: Chaque joueur MUST recevoir uniquement son mot ; personne ne connaît son rôle au début ; le rôle n'est révélé qu'à l'élimination ou en fin de partie.
- **FR-019**: Chaque humain MUST recevoir son mot en message privé au lancement.

**Phase de description**

- **FR-020**: Chaque joueur vivant MUST parler une seule fois par tour, dans l'ordre annoncé par le bot.
- **FR-021**: Au premier tour l'ordre MUST être aléatoire et Mr. White MUST ne jamais parler en premier ; aux tours suivants, le premier orateur MUST être le joueur vivant suivant dans l'ordre initial, avec la même contrainte.
- **FR-022**: Une description MUST être un mot ou une courte expression de 6 mots maximum, envoyée dans le groupe quand c'est son tour.
- **FR-023**: Le système MUST ne prendre en compte que le message du joueur dont c'est le tour et MUST ignorer les autres messages du groupe.
- **FR-024**: Le délai de description MUST être de 60 secondes (configurable) ; passé ce délai, le joueur passe son tour et le bot le signale ; aucune sanction n'est appliquée en cas d'inactivité répétée.
- **FR-025**: Une description contenant le mot secret du joueur (comparaison normalisée) MUST être refusée ; le bot MUST supprimer le message s'il est administrateur du groupe et, dans tous les cas, demander une autre description dans le délai restant.
- **FR-026**: Le bot MUST récapituler les descriptions du tour avant d'ouvrir le vote.

**Phase de vote**

- **FR-027**: Le bot MUST publier un message avec un bouton par joueur vivant.
- **FR-028**: Chaque joueur vivant MUST voter une seule fois, ne MUST PAS pouvoir voter pour lui-même, et MUST pouvoir changer son vote tant que le vote est ouvert.
- **FR-029**: Le vote MUST se clore quand tous les vivants ont voté ou après 90 secondes (configurable) ; les non-votants comptent comme abstention.
- **FR-030**: Le joueur ayant le plus de voix MUST être éliminé, et le bot MUST afficher qui a voté pour qui.
- **FR-031**: En cas d'égalité, le système MUST organiser un revote limité aux joueurs à égalité (qui votent aussi) ; en cas de nouvelle égalité, il MUST tirer au sort parmi eux.
- **FR-032**: Si aucun vote n'est exprimé, personne ne MUST être éliminé et un nouveau tour de description MUST commencer ; après 3 tours consécutifs sans aucun vote exprimé, le système MUST annuler la partie, l'annoncer dans le groupe et n'attribuer aucun point.

**Élimination, devinette et victoire**

- **FR-033**: À l'élimination, le bot MUST révéler le rôle du joueur mais pas son mot.
- **FR-034**: Si Mr. White est éliminé, il MUST avoir une seule tentative pour deviner le mot des civils : en privé avec un délai de 60 secondes pour un humain, à partir des descriptions publiques pour une IA.
- **FR-035**: La comparaison des mots MUST être normalisée : minuscules, accents supprimés, espaces et tirets unifiés, articles initiaux retirés (le, la, les, l', un, une, des).
- **FR-036**: Si la devinette est correcte, Mr. White MUST gagner seul et la partie MUST s'arrêter immédiatement.
- **FR-037**: Après chaque élimination, le système MUST vérifier la victoire : civils gagnants si tous les undercovers et Mr. White sont éliminés ; infiltrés gagnants s'il ne reste qu'un civil vivant ou aucun.
- **FR-038**: À la fin, le bot MUST révéler tous les rôles et les trois mots, attribuer les points et afficher le classement de la partie.

**Points et classement**

- **FR-039**: Les points MUST être : victoire des civils +2 par civil (vivant ou éliminé) ; victoire des infiltrés +10 par undercover et +6 pour Mr. White ; victoire de Mr. White par devinette +10 pour lui seul. Ces valeurs MUST être configurables.
- **FR-040**: Les points MUST être cumulés par groupe Telegram, et les IA MUST avoir un score et apparaître au classement.

**Commandes et confidentialité**

- **FR-041**: Dans le groupe, le système MUST proposer les commandes : créer un lobby, lancer, annuler, état (phase, vivants, joueur courant), règles, classement.
- **FR-042**: En privé, le système MUST proposer : démarrer le bot (prérequis pour recevoir son mot), redemander son mot pour la partie en cours, aide.
- **FR-043**: Aucun message envoyé dans le groupe ne MUST contenir un mot secret avant l'écran de fin, ce que des tests automatisés sur tous les textes émis MUST vérifier.
- **FR-044**: Les IA MUST être affichées dans le groupe avec le préfixe « 🤖 » (par exemple « 🤖 Zendaya IA : … »).
- **FR-045**: Toute l'interface utilisateur MUST être en français, avec un ton fun et direct et des emojis modérés.
- **FR-046**: Le système MUST documenter les prérequis côté Telegram : désactiver le mode privé du bot pour qu'il lise le groupe ; optionnel, le rendre administrateur pour supprimer les descriptions interdites.

**Agents IA**

- **FR-047**: Les trois IA MUST avoir des personnalités distinctes appliquées au style des indices uniquement : Zendaya IA posée et analytique, Kendall IA joueuse et imagée, BFF Diva IA expressive et issue de la vie quotidienne.
- **FR-048**: Les IA MUST ne parler que lorsque c'est leur tour (description) et agir silencieusement pour le vote, sans discussion libre.
- **FR-049**: Une IA MUST recevoir uniquement son mot, l'historique public (descriptions, votes, éliminations, rôles révélés) et la liste des vivants ; elle MUST ne jamais recevoir son rôle, ni les mots ou rôles des autres, ni l'état complet de la partie.
- **FR-050**: Une description d'IA MUST faire 6 mots maximum, ne pas contenir son mot ni sa racine évidente, et ne pas répéter une description déjà donnée dans la partie ; après 3 tentatives invalides, elle dit « Je passe mon tour 🤐 ».
- **FR-051**: Le vote d'une IA MUST désigner un joueur vivant autre qu'elle-même, sinon un vote aléatoire parmi les joueurs valides est utilisé.
- **FR-052**: Une IA éliminée en tant que Mr. White MUST proposer un mot (un mot ou une expression) ; en cas d'échec, la devinette est ratée.
- **FR-053**: Les IA MUST suivre la stratégie suivante : comparer leur mot aux descriptions des autres et rester vagues si elles se pensent infiltrées ; donner des indices précis sans rendre le mot devinable par Mr. White si elles se pensent civiles ; voter contre le joueur dont les descriptions collent le moins au mot estimé de la majorité ; déduire le mot des civils à partir des indices de la majorité si éliminées comme Mr. White.
- **FR-054**: Avant chaque message, une IA MUST afficher l'indicateur « en train d'écrire » pendant 2 à 5 secondes (délai aléatoire).
- **FR-055**: Les appels au service d'IA MUST avoir un délai maximal et gérer les limites de requêtes avec 3 essais espacés de façon croissante, puis basculer sur la solution de repli. Une IA MUST ne jamais bloquer une partie.

**Base de mots**

- **FR-056**: La base de mots MUST contenir 201 trios répartis en 15 catégories, chaque trio étant composé de 3 mots distincts et chaque trio ayant un identifiant unique.
- **FR-057**: Le système MUST valider la base au démarrage et MUST refuser de démarrer avec une erreur explicite si un trio n'a pas exactement 3 mots distincts ou si un identifiant est en double.
- **FR-058**: Un trio MUST ne pas être rejoué dans un même groupe tant que tous les autres trios n'ont pas été joués ; l'historique MUST être conservé par groupe.
- **FR-059**: La base MUST pouvoir être enrichie en éditant son fichier de données, sans modifier le code.

**Reprise**

- **FR-060**: L'état de la partie MUST être conservé après chaque transition, et le bot MUST reprendre une partie en cours après un redémarrage, au même point (par exemple le même vote) avec un délai restant cohérent.

### Key Entities

- **Groupe** : le groupe Telegram où se joue la partie ; porte l'historique des trios joués et les scores cumulés.
- **Partie** : une session de jeu dans un groupe, avec une phase, un créateur, un trio de mots, des joueurs, des tours et une issue.
- **Joueur** : humain ou IA ; a un nom, un rôle, un mot, un statut (vivant ou éliminé) et un score.
- **Rôle** : Civil, Undercover ou Mr. White, avec l'équipe correspondante (Civils ou Infiltrés).
- **Trio de mots** : identifiant, catégorie et trois mots proches mais différents (A, B, C).
- **Description** : texte court d'un joueur pour un tour donné.
- **Vote** : choix d'un joueur vivant pour un autre, modifiable tant que le vote est ouvert.
- **Vue publique** : ce qu'un joueur peut légitimement savoir (son mot, l'historique public, les vivants), seule information transmise aux IA.
- **Score** : points cumulés par joueur et par groupe, IA comprises.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Une partie complète de 8 joueurs peut être jouée du lobby à l'écran de fin sans intervention technique.
- **SC-002**: Sur 100 % des parties testées, aucun mot secret n'apparaît dans les messages du groupe avant l'écran de fin.
- **SC-003**: Pour chaque nombre d'humains de 1 à 8, le nombre d'IA ajoutées, le total de joueurs et la répartition des rôles correspondent exactement aux tableaux de la spécification.
- **SC-004**: Avec le service d'IA indisponible, 100 % des parties simulées vont jusqu'à leur terme, sans blocage.
- **SC-005**: Dans 100 % des parties, Mr. White n'est jamais le premier orateur d'un tour.
- **SC-006**: Un joueur seul peut obtenir une partie contre les trois IA en moins de 3 minutes après avoir appuyé sur « Lancer ».
- **SC-007**: Après un redémarrage en plein vote, la partie reprend au même vote dans 100 % des cas testés.
- **SC-008**: Sur un nombre de parties égal au nombre de trios, aucun trio n'est rejoué dans un même groupe avant que tous aient été joués.
- **SC-009**: Les informations fournies à une IA ne contiennent, dans 100 % des cas testés, ni son rôle ni les mots ou rôles des autres joueurs.
- **SC-010**: Les scores cumulés affichés par le classement du groupe correspondent, pour 100 % des cas testés, à la somme des points des parties jouées, IA comprises.

## Assumptions

- Les joueurs sont des amis francophones qui jouent dans un groupe Telegram, avec une connexion stable.
- Le bot a été créé côté Telegram avec le mode privé désactivé ; le statut d'administrateur est optionnel.
- Une partie nécessite au moins 1 humain : le créateur.
- Une partie à 4 joueurs n'a pas de Mr. White (règle du brief, mode solo).
- Quand un humain éliminé en tant que Mr. White ne répond pas dans le délai de 60 secondes, sa tentative est considérée comme ratée.
- Les valeurs par défaut des délais (60 s, 90 s, 60 s, 10 min, 2 min) et des points sont celles du brief et restent configurables.
- Le nom des joueurs affichés est leur nom Telegram.
- Hors périmètre v1 : mode présentiel ou oral, webhook et hébergement serverless, interface web d'administration, discussion libre des IA, parties en privé sans groupe, langues autres que le français.
- La pile technique et la structure du projet seront définies à l'étape de planification.
