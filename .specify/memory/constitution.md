# Constitution du projet Undercover (bot Telegram)

## Core Principles

### I. Simplicité d'abord
Le projet ne contient aucune sur-ingénierie. Chaque abstraction, couche ou dépendance ajoutée DOIT
être justifiée par un besoin réel et présent, pas par un besoin hypothétique. Entre deux solutions,
la plus simple qui satisfait la spécification l'emporte. Toute complexité ajoutée DOIT être
justifiée par écrit dans le plan de la fonctionnalité concernée.

### II. Moteur de jeu pur
Toute la logique de jeu (rôles, tours, votes, éliminations, victoire, points) vit dans un module
unique qui n'a AUCUNE dépendance à Telegram, à la base de données ou au LLM : aucun import de ces
couches, aucune entrée/sortie, aucune horloge ni source aléatoire implicite. Le moteur DOIT être
déterministe lorsqu'on lui fournit une graine aléatoire, et DOIT être testé unitairement sans
aucun mock de service externe. Les couches Telegram, persistance et IA dépendent du moteur, jamais
l'inverse.

### III. Confidentialité des mots (NON-NÉGOCIABLE)
Aucun mot secret (mot des civils, de l'undercover ou de Mr. White) ne DOIT apparaître dans un
message envoyé au groupe avant l'écran de fin de partie. C'est l'exigence la plus importante du
projet. Elle DOIT être couverte par des tests automatisés qui examinent l'ensemble des textes émis
vers le groupe. Toute modification qui ajoute ou change un message de groupe DOIT conserver ce
test au vert.

### IV. Équité des IA
Les agents IA n'accèdent qu'à la vue publique de la partie : leur propre mot, l'historique public
(descriptions, votes, éliminations, rôles révélés) et la liste des joueurs vivants. Ils ne DOIVENT
jamais recevoir leur rôle, ni les mots ou rôles des autres joueurs, ni l'état complet de la partie.
Le moteur construit cette vue publique, et un test DOIT vérifier qu'elle ne contient aucune
information cachée.

### V. Résilience
L'état de la partie est persisté après chaque transition, et le bot DOIT reprendre une partie en
cours après un redémarrage, avec des délais restants cohérents. Une panne, un timeout ou une
limite de requêtes du LLM ne DOIT jamais bloquer le jeu : une IA a toujours une solution de repli
et une partie ne reste jamais suspendue à une IA.

### VI. Tests avant fusion
Tout nouveau comportement du moteur DOIT arriver avec ses tests, dans la même modification. Aucune
modification n'est fusionnée si la suite de tests échoue. Les règles de jeu de la spécification
DOIVENT chacune être vérifiables par au moins un test.

### VII. Français et conventions de code
Tous les textes destinés aux utilisateurs (messages du bot, boutons, aide, règles) sont en
français, et centralisés dans un module dédié. Le code et les identifiants sont en anglais ; les
commentaires sont en français.

### VIII. Secrets hors du dépôt
Les secrets (jeton du bot, clés d'API) vivent uniquement dans un fichier `.env` qui n'est JAMAIS
commité. Un fichier `.env.example`, sans aucune valeur réelle, DOIT être fourni et tenu à jour.
Aucun secret ne DOIT apparaître dans le code, les tests, les journaux ou les messages du bot.

## Contraintes du projet

- **Source de vérité** : `docs/UNDERCOVER_BRIEF.md`. Aucune règle de jeu ne DOIT être inventée en
  dehors de ce document ; en cas d'ambiguïté, poser la question (clarification) plutôt que
  supposer.
- **Configurabilité** : les valeurs de jeu (délais, répartition des rôles, points) DOIVENT être
  configurables sans modifier la logique. La base de mots DOIT pouvoir être enrichie en éditant un
  fichier de données, sans toucher au code.
- **Périmètre v1** : les éléments listés en section 10 du brief (mode présentiel, webhook,
  interface d'administration, discussion libre des IA, parties en privé, langues autres que le
  français) sont hors périmètre et NE DOIVENT PAS être implémentés sans amendement de la
  spécification.
- **Choix techniques** : la pile technique et la structure du projet sont définies à l'étape de
  planification, pas dans cette constitution.

## Workflow de développement et portes qualité

- Le flux suit Spec Kit dans l'ordre : constitution, spécification, clarification, plan, tâches,
  analyse, implémentation.
- Les fonctionnalités sont livrées en user stories indépendantes, dans l'ordre défini par le
  brief, chacune testable séparément.
- Avant toute fusion : la suite de tests passe, le lint et le formatage passent, et les tests de
  confidentialité (principe III) et d'équité (principe IV) sont verts.
- Toute revue DOIT vérifier la conformité à cette constitution ; un écart DOIT être corrigé ou
  justifié explicitement dans le plan (principe I).

## Governance

Cette constitution prévaut sur les autres pratiques du projet. Un amendement DOIT être documenté
(motif et impact), accompagné d'une mise à jour des artefacts dépendants (spécification, plan,
tâches) si nécessaire, puis daté.

Versionnement sémantique de la constitution :
- MAJOR : suppression ou redéfinition incompatible d'un principe ou de la gouvernance ;
- MINOR : ajout d'un principe ou d'une section, ou extension substantielle des règles ;
- PATCH : clarification, reformulation, correction sans effet sur le fond.

Contrôle de conformité : chaque revue et chaque étape d'analyse (`/speckit-analyze`) DOIT vérifier
le respect des principes ; les principes III et IV sont des bloquants.

**Version**: 1.0.0 | **Ratified**: 2026-10-01 | **Last Amended**: 2026-10-01
