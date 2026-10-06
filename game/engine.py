"""Machine à états du jeu : fonctions pures, déterministes à graine égale.

Le moteur ne lit jamais l'horloge et n'effectue aucune entrée/sortie : il applique un
événement à l'état (modifié sur place) et renvoie la liste des effets à exécuter.

Une manche = `description_rounds` tours de description (un mot par joueur et par tour), puis un
vote. Deux modes : avec élimination (un éliminé par manche, jusqu'à une victoire) ou sans
élimination (un seul vote, puis révélation des rôles, des mots et des points).
"""

import random
from collections import Counter
from dataclasses import dataclass

from game.models import (
    MAX_DESCRIPTION_WORDS,
    MAX_PLAYERS,
    Cancel,
    CancelTimer,
    CastVote,
    DeleteMessage,
    Describe,
    Description,
    Effect,
    Elimination,
    Event,
    GameMode,
    GameState,
    Join,
    Launch,
    Leave,
    Notify,
    Outcome,
    PassTurn,
    Phase,
    Player,
    PublicView,
    RecordScores,
    RequestAIAction,
    Role,
    SendGroup,
    SendPrivate,
    SetCanDm,
    SetMode,
    StartTimer,
    Timeout,
    TrioPlayed,
    UpdateLobby,
    VoteKind,
    VoteRound,
    WordTrio,
)
from game.normalize import contains_secret_or_root
from game.rules import GameConfig, ai_completion, check_victory, compute_points, role_distribution
from game.words import draw

# Fin de partie : toutes les minuteries à couper
_ALL_TIMERS = ("description", "vote", "lobby", "solo_wait")
# Nombre de manches consécutives sans aucun vote avant l'annulation (FR-032)
MAX_NO_VOTE_STREAK = 3


@dataclass
class Timeouts:
    """Durées (secondes) demandées par le moteur via les effets StartTimer."""

    description: int = 60
    vote: int = 90
    lobby: int = 600
    solo_wait: int = 30


@dataclass
class EngineContext:
    """Dépendances injectées : hasard, configuration, base de mots, historique des trios."""

    rng: random.Random
    config: GameConfig
    trios: list[WordTrio]
    played_ids: set[int]
    timeouts: Timeouts


def create_lobby(
    game_id: str,
    chat_id: int,
    creator_id: str,
    creator_name: str,
    can_dm: bool = False,
    rng_seed: int = 0,
    mode: GameMode = GameMode.ELIMINATION,
) -> GameState:
    """Crée un lobby dont le créateur est le premier inscrit."""
    state = GameState(
        game_id=game_id, chat_id=chat_id, creator_id=creator_id, rng_seed=rng_seed, mode=mode
    )
    state.players.append(Player(id=creator_id, name=creator_name, can_dm=can_dm))
    return state


def apply(state: GameState, event: Event, ctx: EngineContext) -> list[Effect]:
    """Applique un événement à l'état et renvoie les effets à exécuter."""
    if state.is_final:
        return []
    if isinstance(event, Join):
        return _join(state, event, ctx)
    if isinstance(event, Leave):
        return _leave(state, event)
    if isinstance(event, SetCanDm):
        return _set_can_dm(state, event)
    if isinstance(event, SetMode):
        return _set_mode(state, event)
    if isinstance(event, Launch):
        return _launch(state, event, ctx)
    if isinstance(event, Cancel):
        return _cancel(state, event)
    if isinstance(event, Describe):
        return _describe(state, event, ctx)
    if isinstance(event, PassTurn):
        return _pass_turn(state, event.player_id, ctx)
    if isinstance(event, CastVote):
        return _cast_vote(state, event, ctx)
    if isinstance(event, Timeout):
        return _timeout(state, event, ctx)
    return []


# ---------------------------------------------------------------- lobby


def _join(state: GameState, ev: Join, ctx: EngineContext) -> list[Effect]:
    if state.phase is not Phase.LOBBY:
        return [Notify(ev.player_id, "not_lobby")]
    if state.has_player(ev.player_id):
        return [Notify(ev.player_id, "already_joined")]
    if len(state.humans) >= MAX_PLAYERS:
        return [Notify(ev.player_id, "full")]
    state.players.append(Player(id=ev.player_id, name=ev.name, can_dm=ev.can_dm))
    effects: list[Effect] = [UpdateLobby()]
    if not state.solo_waiting:
        effects.append(StartTimer("lobby", ctx.timeouts.lobby))
    return effects


def _leave(state: GameState, ev: Leave) -> list[Effect]:
    if state.phase is not Phase.LOBBY or not state.has_player(ev.player_id):
        return []
    leaver = state.player(ev.player_id)
    state.players = [p for p in state.players if p.id != ev.player_id]
    if not state.humans:
        return [SendGroup("lobby_deleted")] + _terminate(state, "lobby_empty", announce=False)
    effects: list[Effect] = []
    if ev.player_id == state.creator_id:
        state.creator_id = state.humans[0].id
        effects.append(SendGroup("creator_transferred", {"name": state.humans[0].name}))
    effects.append(SendGroup("player_left", {"name": leaver.name}))
    effects.append(UpdateLobby())
    return effects


def _set_can_dm(state: GameState, ev: SetCanDm) -> list[Effect]:
    if state.has_player(ev.player_id):
        state.player(ev.player_id).can_dm = ev.can_dm
        if state.phase is Phase.LOBBY:
            return [UpdateLobby()]
    return []


def _set_mode(state: GameState, ev: SetMode) -> list[Effect]:
    """Le créateur choisit le type de partie tant que la partie n'a pas commencé."""
    if state.phase is not Phase.LOBBY:
        return [Notify(ev.by, "not_lobby")]
    if ev.by != state.creator_id:
        return [Notify(ev.by, "not_creator")]
    if state.mode is ev.mode:
        return []
    state.mode = ev.mode
    return [UpdateLobby()]


def _launch(state: GameState, ev: Launch, ctx: EngineContext) -> list[Effect]:
    if state.phase is not Phase.LOBBY:
        return []
    if ev.by != state.creator_id:
        return [Notify(ev.by, "not_creator")]
    blocked = [p.name for p in state.humans if not p.can_dm]
    if blocked:
        state.solo_waiting = False
        return [CancelTimer("solo_wait"), SendGroup("launch_blocked", {"names": blocked})]
    if len(state.humans) == 1 and not state.solo_waiting and not ev.immediate:
        state.solo_waiting = True
        return [
            CancelTimer("lobby"),
            StartTimer("solo_wait", ctx.timeouts.solo_wait),
            SendGroup("solo_last_call", {"seconds": ctx.timeouts.solo_wait}),
            UpdateLobby(),
        ]
    return _start(state, ctx)


def _cancel(state: GameState, ev: Cancel) -> list[Effect]:
    if ev.by != state.creator_id:
        return [Notify(ev.by, "not_creator")]
    return _terminate(state, "creator")


def _terminate(state: GameState, reason: str, announce: bool = True) -> list[Effect]:
    state.phase = Phase.CANCELLED
    state.outcome = Outcome.CANCELLED
    state.points = {}
    state.solo_waiting = False
    effects: list[Effect] = [CancelTimer(k) for k in _ALL_TIMERS]
    if announce:
        effects.append(SendGroup("cancelled", {"reason": reason}))
    return effects


# ---------------------------------------------------------------- distribution


def _start(state: GameState, ctx: EngineContext) -> list[Effect]:
    rng = ctx.rng
    for ai_id, ai_name in ai_completion(len(state.humans)):
        state.players.append(Player(id=ai_id, name=ai_name, is_ai=True, can_dm=True))
    total = len(state.players)
    civilians, undercovers = role_distribution(total, ctx.config)
    roles = [Role.CIVILIAN] * civilians + [Role.UNDERCOVER] * undercovers
    rng.shuffle(roles)
    drawn = draw(ctx.trios, ctx.played_ids, rng)
    state.trio = drawn.trio
    state.civilian_word = drawn.civilian
    state.undercover_word = drawn.undercover
    words = {Role.CIVILIAN: drawn.civilian, Role.UNDERCOVER: drawn.undercover}
    for player, role in zip(state.players, roles, strict=True):
        player.role = role
        player.word = words[role]
    order = [p.id for p in state.players]
    rng.shuffle(order)
    state.initial_order = order
    state.first_pos = 0
    state.round = 1
    state.solo_waiting = False
    state.phase = Phase.DESCRIPTION

    effects: list[Effect] = [
        CancelTimer("lobby"),
        CancelTimer("solo_wait"),
        TrioPlayed(drawn.trio.id, drawn.cycle_restarted),
        SendGroup(
            "game_started",
            {
                "players": [p.name for p in state.players],
                "total": total,
                "ai_count": total - len(state.humans),
                "mode": state.mode.value,
            },
        ),
    ]
    for p in state.humans:
        effects.append(SendPrivate(p.id, "your_word", {"word": p.word}))
    effects += _begin_round(state, ctx)
    return effects


# ---------------------------------------------------------------- description


def _begin_round(state: GameState, ctx: EngineContext) -> list[Effect]:
    """Début d'une manche : premier tour de description."""
    n = len(state.initial_order)
    order: list[str] = []
    for step in range(n):
        pid = state.initial_order[(state.first_pos + step) % n]
        if state.player(pid).alive:
            order.append(pid)
    state.speaking_order = order
    state.speaker_index = 0
    state.sub_round = 1
    state.phase = Phase.DESCRIPTION
    return _announce_sub_round(state, ctx)


def _announce_sub_round(state: GameState, ctx: EngineContext) -> list[Effect]:
    names = [state.player(pid).name for pid in state.speaking_order]
    announce = SendGroup(
        "round_start",
        {
            "round": state.round,
            "sub_round": state.sub_round,
            "sub_total": ctx.config.description_rounds,
            "order": names,
        },
    )
    return [announce] + _turn_effects(state, ctx)


def _turn_effects(state: GameState, ctx: EngineContext) -> list[Effect]:
    speaker = state.current_speaker
    assert speaker is not None
    effects: list[Effect] = [
        SendGroup("turn", {"player_id": speaker.id, "name": speaker.name}),
        StartTimer("description", ctx.timeouts.description),
    ]
    if speaker.is_ai:
        effects.append(RequestAIAction(speaker.id, "describe"))
    return effects


def _describe(state: GameState, ev: Describe, ctx: EngineContext) -> list[Effect]:
    speaker = state.current_speaker
    if speaker is None or speaker.id != ev.player_id:
        return []
    text = " ".join(ev.text.split())
    count = len(text.split())
    if count == 0:
        return []
    if count > MAX_DESCRIPTION_WORDS:
        return [
            SendGroup("description_too_long", {"name": speaker.name, "max": MAX_DESCRIPTION_WORDS})
        ]
    if speaker.word and contains_secret_or_root(text, speaker.word):
        return [DeleteMessage(), SendGroup("description_forbidden", {"name": speaker.name})]
    state.descriptions.append(Description(state.round, state.sub_round, speaker.id, text))
    effects: list[Effect] = [CancelTimer("description")]
    if speaker.is_ai:
        effects.append(
            SendGroup(
                "ai_description", {"player_id": speaker.id, "name": speaker.name, "text": text}
            )
        )
    return effects + _advance(state, ctx)


def _pass_turn(state: GameState, player_id: str, ctx: EngineContext) -> list[Effect]:
    speaker = state.current_speaker
    if speaker is None or speaker.id != player_id:
        return []
    state.descriptions.append(Description(state.round, state.sub_round, speaker.id, "", True))
    effects: list[Effect] = [
        CancelTimer("description"),
        SendGroup("turn_passed", {"name": speaker.name, "is_ai": speaker.is_ai}),
    ]
    return effects + _advance(state, ctx)


def _advance(state: GameState, ctx: EngineContext) -> list[Effect]:
    state.speaker_index += 1
    if state.speaker_index < len(state.speaking_order):
        return _turn_effects(state, ctx)
    if state.sub_round < ctx.config.description_rounds:
        # tour suivant : chacun redit un mot, dans le même ordre
        state.sub_round += 1
        state.speaker_index = 0
        return _announce_sub_round(state, ctx)
    effects: list[Effect] = [SendGroup("recap", {"round": state.round, "items": _recap(state)})]
    return effects + _open_vote(state, ctx, VoteKind.VOTE, [p.id for p in state.alive])


def _recap(state: GameState) -> list[tuple[str, list[str | None]]]:
    """Mots de la manche par joueur, dans l'ordre de passage (None = tour passé)."""
    items: list[tuple[str, list[str | None]]] = []
    for pid in state.speaking_order:
        words = [
            None if d.skipped else d.text
            for d in state.descriptions
            if d.round == state.round and d.player_id == pid
        ]
        items.append((state.player(pid).name, words))
    return items


# ---------------------------------------------------------------- vote


def _open_vote(
    state: GameState, ctx: EngineContext, kind: VoteKind, candidates: list[str]
) -> list[Effect]:
    state.phase = Phase.VOTE if kind is VoteKind.VOTE else Phase.REVOTE
    state.vote_rounds.append(VoteRound(state.round, kind, list(candidates)))
    effects: list[Effect] = [
        SendGroup(
            "vote_open",
            {
                "kind": kind.value,
                "mode": state.mode.value,
                "candidates": [(pid, state.player(pid).name) for pid in candidates],
            },
        ),
        StartTimer("vote", ctx.timeouts.vote),
    ]
    for p in state.alive:
        if p.is_ai:
            effects.append(RequestAIAction(p.id, "vote"))
    return effects


def _cast_vote(state: GameState, ev: CastVote, ctx: EngineContext) -> list[Effect]:
    current = state.current_vote
    if current is None:
        return [Notify(ev.voter_id, "vote_closed")]
    if not state.has_player(ev.voter_id) or not state.player(ev.voter_id).alive:
        return [Notify(ev.voter_id, "not_alive")]
    if ev.target_id == ev.voter_id:
        return [Notify(ev.voter_id, "self_vote")]
    if ev.target_id not in current.candidates:
        return [Notify(ev.voter_id, "invalid_target")]
    current.ballots[ev.voter_id] = ev.target_id
    effects: list[Effect] = [
        Notify(ev.voter_id, "vote_recorded", {"target": state.player(ev.target_id).name})
    ]
    if len(current.ballots) >= len(state.alive):
        effects += _resolve_vote(state, ctx)
    return effects


def _resolve_vote(state: GameState, ctx: EngineContext) -> list[Effect]:
    current = state.current_vote
    assert current is not None
    effects: list[Effect] = [CancelTimer("vote")]
    if not current.ballots:
        effects.append(SendGroup("no_votes"))
        state.no_vote_streak += 1
        if state.no_vote_streak >= MAX_NO_VOTE_STREAK:
            return effects + _terminate(state, "no_votes")
        return effects + _next_round(state, ctx)
    state.no_vote_streak = 0
    counts = Counter(current.ballots.values())
    top = max(counts.values())
    leaders = [pid for pid in current.candidates if counts[pid] == top]
    effects.append(
        SendGroup(
            "vote_result",
            {
                "kind": current.kind.value,
                "ballots": [
                    (state.player(v).name, state.player(t).name) for v, t in current.ballots.items()
                ],
                "counts": [(state.player(pid).name, counts[pid]) for pid in counts],
            },
        )
    )
    if len(leaders) == 1:
        return effects + _conclude_vote(state, ctx, leaders[0], "vote")
    names = [state.player(pid).name for pid in leaders]
    if current.kind is VoteKind.VOTE:
        effects.append(SendGroup("tie_revote", {"names": names}))
        return effects + _open_vote(state, ctx, VoteKind.REVOTE, leaders)
    chosen = ctx.rng.choice(leaders)
    current.tie_break_drawn = True
    effects.append(SendGroup("tie_draw", {"names": names, "name": state.player(chosen).name}))
    return effects + _conclude_vote(state, ctx, chosen, "draw")


def _conclude_vote(state: GameState, ctx: EngineContext, player_id: str, by: str) -> list[Effect]:
    if state.mode is GameMode.NO_ELIMINATION:
        return _accuse(state, ctx, player_id, by)
    return _eliminate(state, ctx, player_id, by)


# ---------------------------------------------------------------- élimination et fin


def _eliminate(state: GameState, ctx: EngineContext, player_id: str, by: str) -> list[Effect]:
    player = state.player(player_id)
    assert player.role is not None
    player.alive = False
    state.eliminations.append(Elimination(state.round, player_id, player.role, by))
    effects: list[Effect] = [
        SendGroup(
            "eliminated",
            {"player_id": player_id, "name": player.name, "role": player.role.value, "by": by},
        )
    ]
    state.phase = Phase.CHECK_VICTORY
    outcome = check_victory(state)
    if outcome is not None:
        return effects + _end(state, ctx, outcome)
    return effects + _next_round(state, ctx)


def _accuse(state: GameState, ctx: EngineContext, player_id: str, by: str) -> list[Effect]:
    """Mode sans élimination : le plus voté est l'accusé ; civils gagnants si undercover."""
    accused = state.player(player_id)
    state.accused_id = player_id
    outcome = Outcome.CIVILIANS if accused.role is Role.UNDERCOVER else Outcome.INFILTRATORS
    effects: list[Effect] = [SendGroup("accused", {"name": accused.name, "by": by})]
    return effects + _end(state, ctx, outcome)


def _next_round(state: GameState, ctx: EngineContext) -> list[Effect]:
    state.round += 1
    n = len(state.initial_order)
    chosen = None
    for step in range(1, n + 1):
        idx = (state.first_pos + step) % n
        if state.player(state.initial_order[idx]).alive:
            chosen = idx
            break
    assert chosen is not None
    state.first_pos = chosen
    return _begin_round(state, ctx)


def _end(state: GameState, ctx: EngineContext, outcome: Outcome) -> list[Effect]:
    state.phase = Phase.ENDED
    state.outcome = outcome
    state.points = compute_points(state, ctx.config)
    accused = state.player(state.accused_id).name if state.accused_id else None
    effects: list[Effect] = [CancelTimer(k) for k in _ALL_TIMERS]
    effects.append(
        SendGroup(
            "game_end",
            {
                "outcome": outcome.value,
                "mode": state.mode.value,
                "accused": accused,
                "players": [
                    (p.name, p.role.value if p.role else "", p.word or "", p.is_ai)
                    for p in state.players
                ],
                "words": {
                    "civilian": state.civilian_word,
                    "undercover": state.undercover_word,
                },
                "points": [(state.player(pid).name, pts) for pid, pts in state.points.items()],
            },
        )
    )
    effects.append(RecordScores(dict(state.points), [(p.id, p.name) for p in state.players]))
    return effects


# ---------------------------------------------------------------- minuteries


def _timeout(state: GameState, ev: Timeout, ctx: EngineContext) -> list[Effect]:
    if ev.kind == "description" and state.phase is Phase.DESCRIPTION:
        speaker = state.current_speaker
        return _pass_turn(state, speaker.id, ctx) if speaker else []
    if ev.kind == "vote" and state.phase in (Phase.VOTE, Phase.REVOTE):
        return _resolve_vote(state, ctx)
    if ev.kind == "lobby" and state.phase is Phase.LOBBY:
        return _terminate(state, "lobby_expired")
    if ev.kind == "solo_wait" and state.phase is Phase.LOBBY and state.solo_waiting:
        return _launch(state, Launch(state.creator_id), ctx)
    return []


# ---------------------------------------------------------------- vue publique


def public_view(state: GameState, player_id: str) -> PublicView:
    """Vue publique pour un joueur : son mot et l'historique public uniquement (FR-049)."""
    me = state.player(player_id)
    open_vote = state.current_vote
    votes = tuple(
        (v.round, state.player(voter).name, state.player(target).name)
        for v in state.vote_rounds
        if v is not open_vote
        for voter, target in v.ballots.items()
    )
    return PublicView(
        viewer_id=me.id,
        viewer_name=me.name,
        own_word=me.word or "",
        alive_players=tuple((p.id, p.name) for p in state.alive),
        descriptions=tuple(
            (d.round, d.sub_round, state.player(d.player_id).name, d.text)
            for d in state.descriptions
            if not d.skipped
        ),
        votes=votes,
        eliminations=tuple(
            (e.round, state.player(e.player_id).name, e.role_revealed.value)
            for e in state.eliminations
        ),
    )
