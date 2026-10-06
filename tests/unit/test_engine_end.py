import pytest

from game.engine import apply
from game.models import (
    Cancel,
    GameMode,
    Outcome,
    Phase,
    RecordScores,
    Role,
    SendGroup,
    Timeout,
)
from tests.unit.helpers import describe_round, everyone_votes, hid, make_ctx, make_lobby, start_game


def kill(state, ctx, player_id):
    """Fait éliminer player_id par un vote unanime après les 3 tours de description."""
    effects = []
    describe_round(state, ctx)
    effects += everyone_votes(state, ctx, player_id)
    return effects


def test_civilians_win_when_the_undercover_is_eliminated():
    state, ctx, _ = start_game(5, seed=3)
    undercovers = [p.id for p in state.players if p.role is Role.UNDERCOVER]
    effects = []
    for pid in undercovers:
        effects += kill(state, ctx, pid)
    assert state.phase is Phase.ENDED and state.outcome is Outcome.CIVILIANS
    civilians = [p.id for p in state.players if p.role is Role.CIVILIAN]
    assert state.points == dict.fromkeys(civilians, 2)
    assert any(isinstance(e, RecordScores) for e in effects)


def test_infiltrators_win_when_one_civilian_left_in_four_player_game():
    state, ctx, _ = start_game(1, seed=2)
    assert len(state.players) == 4
    civilians = [p.id for p in state.players if p.role is Role.CIVILIAN]
    kill(state, ctx, civilians[0])
    assert state.phase is Phase.DESCRIPTION  # 2 civils + 1 undercover : on continue
    kill(state, ctx, civilians[1])
    assert state.phase is Phase.ENDED and state.outcome is Outcome.INFILTRATORS
    undercover = next(p.id for p in state.players if p.role is Role.UNDERCOVER)
    assert state.points == {undercover: 10}


def test_eight_players_need_both_undercovers_eliminated():
    state, ctx, _ = start_game(8, seed=4)
    undercovers = [p.id for p in state.players if p.role is Role.UNDERCOVER]
    assert len(undercovers) == 2
    kill(state, ctx, undercovers[0])
    assert state.phase is Phase.DESCRIPTION  # le deuxième undercover est toujours là
    kill(state, ctx, undercovers[1])
    assert state.outcome is Outcome.CIVILIANS


def test_end_screen_reveals_roles_and_both_words():
    state, ctx, _ = start_game(1, seed=2)
    civilians = [p.id for p in state.players if p.role is Role.CIVILIAN]
    kill(state, ctx, civilians[0])
    effects = kill(state, ctx, civilians[1])
    end = next(e for e in effects if isinstance(e, SendGroup) and e.key == "game_end")
    assert set(end.params["words"].values()) == {state.civilian_word, state.undercover_word}
    assert len(end.params["players"]) == 4


def test_no_secret_in_any_group_effect_before_end():
    secrets_checked = 0
    for seed in range(10):
        state, ctx, effects = start_game(3, seed)
        secrets = {state.civilian_word, state.undercover_word}
        all_effects = list(effects)
        while not state.is_final:
            if state.phase is Phase.DESCRIPTION:
                all_effects += describe_round(state, ctx)
            if state.phase in (Phase.VOTE, Phase.REVOTE):
                all_effects += everyone_votes(state, ctx)
        for e in all_effects:
            if isinstance(e, SendGroup) and e.key != "game_end":
                assert not any(s in str(e.params) for s in secrets)
                secrets_checked += 1
    assert secrets_checked > 0


@pytest.mark.parametrize("phase_setup", ["lobby", "description", "vote"])
def test_cancel_from_any_phase(phase_setup):
    if phase_setup == "lobby":
        ctx = make_ctx()
        state = make_lobby(3, ctx)
    else:
        state, ctx, _ = start_game(5, seed=1)
        if phase_setup == "vote":
            describe_round(state, ctx)
            assert state.phase is Phase.VOTE
    apply(state, Cancel(hid(1)), ctx)
    assert state.phase is Phase.CANCELLED and state.points == {}


def test_final_state_ignores_events():
    state, ctx, _ = start_game(5, seed=1)
    apply(state, Cancel(hid(1)), ctx)
    assert apply(state, Timeout("vote"), ctx) == []


# ------------------------------------------------------------ mode sans élimination


def no_elim_game(n=5, seed=3):
    return start_game(n, seed, mode=GameMode.NO_ELIMINATION)


def test_no_elimination_mode_ends_after_the_single_vote_with_everybody_alive():
    state, ctx, _ = no_elim_game()
    undercover = next(p for p in state.players if p.role is Role.UNDERCOVER)
    describe_round(state, ctx)
    effects = everyone_votes(state, ctx, undercover.id)
    assert state.phase is Phase.ENDED
    assert state.eliminations == [] and all(p.alive for p in state.players)
    assert state.accused_id == undercover.id
    assert "accused" in [e.key for e in effects if isinstance(e, SendGroup)]


def test_no_elimination_civilians_win_when_the_accused_is_an_undercover():
    state, ctx, _ = no_elim_game(5, 3)
    undercover = next(p for p in state.players if p.role is Role.UNDERCOVER)
    describe_round(state, ctx)
    everyone_votes(state, ctx, undercover.id)
    assert state.outcome is Outcome.CIVILIANS
    civilians = [p.id for p in state.players if p.role is Role.CIVILIAN]
    assert state.points == dict.fromkeys(civilians, 2)


def test_no_elimination_undercovers_win_when_the_accused_is_a_civilian():
    state, ctx, _ = no_elim_game(5, 3)
    civilian = next(p for p in state.players if p.role is Role.CIVILIAN)
    describe_round(state, ctx)
    everyone_votes(state, ctx, civilian.id)
    assert state.outcome is Outcome.INFILTRATORS
    undercovers = [p.id for p in state.players if p.role is Role.UNDERCOVER]
    assert state.points == dict.fromkeys(undercovers, 10)


def test_no_elimination_end_screen_reveals_roles_words_and_points():
    state, ctx, _ = no_elim_game()
    civilian = next(p for p in state.players if p.role is Role.CIVILIAN)
    describe_round(state, ctx)
    effects = everyone_votes(state, ctx, civilian.id)
    end = next(e for e in effects if isinstance(e, SendGroup) and e.key == "game_end")
    assert end.params["mode"] == "no_elimination"
    assert end.params["accused"] == civilian.name
    assert set(end.params["words"].values()) == {state.civilian_word, state.undercover_word}
    assert end.params["points"]


def test_no_elimination_tie_goes_to_revote_then_draw_then_ends():
    state, ctx, _ = no_elim_game(8, 1)
    describe_round(state, ctx)
    ids = [p.id for p in state.alive]
    a, b = ids[0], ids[1]
    ballots = {a: b, b: a}
    for i, pid in enumerate(ids[2:]):
        ballots[pid] = a if i % 2 == 0 else b
    from game.models import CastVote

    for voter, target in ballots.items():
        apply(state, CastVote(voter, target), ctx)
    assert state.phase is Phase.REVOTE
    for voter, target in ballots.items():
        apply(state, CastVote(voter, target), ctx)
    assert state.phase is Phase.ENDED and state.accused_id in (a, b)


def test_no_elimination_without_votes_replays_the_rounds_then_cancels():
    state, ctx, _ = no_elim_game()
    for _ in range(3):
        describe_round(state, ctx)
        apply(state, Timeout("vote"), ctx)
    assert state.phase is Phase.CANCELLED


def test_no_elimination_secret_never_in_group_before_the_end():
    for seed in range(8):
        state, ctx, effects = no_elim_game(4, seed)
        secrets = {state.civilian_word, state.undercover_word}
        out = list(effects)
        out += describe_round(state, ctx)
        out += everyone_votes(state, ctx)
        for e in out:
            if isinstance(e, SendGroup) and e.key != "game_end":
                assert not any(s in str(e.params) for s in secrets)
