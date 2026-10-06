"""Aides de test du moteur : contexte, lobby, simulation de parties."""

import random

from bot.config import load_game_config
from game.engine import EngineContext, Timeouts, apply, create_lobby
from game.models import (
    CastVote,
    Describe,
    Effect,
    GameMode,
    GameState,
    Join,
    Launch,
    Phase,
    SendGroup,
    Timeout,
    WordTrio,
)

CONFIG = load_game_config("data/game_config.json")


def make_trios(n: int = 10) -> list[WordTrio]:
    return [WordTrio(i, "Cat", (f"alpha{i}", f"bravo{i}", f"charlie{i}")) for i in range(1, n + 1)]


def make_ctx(seed: int = 0, n_trios: int = 10, played: set[int] | None = None) -> EngineContext:
    return EngineContext(
        rng=random.Random(seed),
        config=CONFIG,
        trios=make_trios(n_trios),
        played_ids=played if played is not None else set(),
        timeouts=Timeouts(),
    )


def hid(i: int) -> str:
    return f"h:{i}"


def make_lobby(
    n_humans: int,
    ctx: EngineContext,
    can_dm: bool = True,
    mode: GameMode = GameMode.ELIMINATION,
) -> GameState:
    state = create_lobby("g1", -100, hid(1), "Joueur 1", can_dm=can_dm, mode=mode)
    for i in range(2, n_humans + 1):
        apply(state, Join(hid(i), f"Joueur {i}", can_dm), ctx)
    return state


def start_game(
    n_humans: int, seed: int = 0, n_trios: int = 10, mode: GameMode = GameMode.ELIMINATION
):
    """Lobby de n humains puis lancement ; en solo, double « Lancer » pour démarrer."""
    ctx = make_ctx(seed, n_trios)
    state = make_lobby(n_humans, ctx, mode=mode)
    effects = apply(state, Launch(hid(1)), ctx)
    if state.solo_waiting:
        effects = apply(state, Launch(hid(1)), ctx)
    assert state.phase is Phase.DESCRIPTION
    return state, ctx, effects


def keys(effects: list[Effect]) -> list[str]:
    return [e.key for e in effects if isinstance(e, SendGroup)]


def describe_round(state: GameState, ctx: EngineContext) -> list[Effect]:
    """Fait décrire tous les orateurs du tour courant avec des indices neutres."""
    out: list[Effect] = []
    rnd = state.round
    while state.phase is Phase.DESCRIPTION and state.round == rnd:
        speaker = state.current_speaker
        word = f"indice{rnd}x{state.sub_round}x{state.speaker_index}"
        out += apply(state, Describe(speaker.id, word), ctx)
    return out


def everyone_votes(state: GameState, ctx: EngineContext, target_id: str | None = None):
    """Chaque vivant vote pour target_id (ou, à défaut, pour le premier candidat autre que lui)."""
    out: list[Effect] = []
    current = state.current_vote
    for p in list(state.alive):
        if state.current_vote is not current:
            break
        t = target_id if target_id and target_id != p.id else None
        if t is None:
            t = next(c for c in current.candidates if c != p.id)
        out += apply(state, CastVote(p.id, t), ctx)
    return out


def simulate(
    n_humans: int, seed: int, mode: GameMode = GameMode.ELIMINATION
) -> tuple[GameState, EngineContext]:
    """Joue une partie complète avec des joueurs au comportement aléatoire."""
    state, ctx, _ = start_game(n_humans, seed, mode=mode)
    rng = random.Random(seed + 1000)
    guard = 0
    while not state.is_final:
        guard += 1
        assert guard < 500, "partie sans fin"
        if state.phase is Phase.DESCRIPTION:
            speaker = state.current_speaker
            if rng.random() < 0.15:
                apply(state, Timeout("description"), ctx)
            else:
                apply(state, Describe(speaker.id, f"idee{guard}"), ctx)
        elif state.phase in (Phase.VOTE, Phase.REVOTE):
            current = state.current_vote
            for p in list(state.alive):
                if state.current_vote is not current:
                    break
                if rng.random() < 0.1:
                    continue
                options = [c for c in current.candidates if c != p.id]
                apply(state, CastVote(p.id, rng.choice(options)), ctx)
            if state.current_vote is current:
                apply(state, Timeout("vote"), ctx)
    return state, ctx
