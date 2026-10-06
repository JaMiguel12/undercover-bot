import pytest

from game.engine import apply
from game.models import (
    Cancel,
    GameMode,
    Join,
    Launch,
    Leave,
    Notify,
    Phase,
    Role,
    SendPrivate,
    SetCanDm,
    SetMode,
    Timeout,
)
from tests.unit.helpers import hid, keys, make_ctx, make_lobby, start_game

EXPECTED_ROLES = {4: (3, 1), 5: (4, 1), 6: (5, 1), 7: (6, 1), 8: (6, 2)}


@pytest.mark.parametrize(
    "humans,total", [(1, 4), (2, 5), (3, 6), (4, 7), (5, 8), (6, 8), (7, 8), (8, 8)]
)
def test_total_players_and_roles(humans, total):
    state, _, _ = start_game(humans, seed=humans)
    assert len(state.players) == total
    counts = (
        sum(p.role is Role.CIVILIAN for p in state.players),
        sum(p.role is Role.UNDERCOVER for p in state.players),
    )
    assert counts == EXPECTED_ROLES[total]
    assert sum(p.is_ai for p in state.players) == total - humans


def test_there_is_no_mr_white_role_anymore():
    assert {r.value for r in Role} == {"civilian", "undercover"}


@pytest.mark.parametrize("seed", range(10))
def test_words_follow_roles_and_come_from_the_trio(seed):
    state, _, _ = start_game(5, seed)
    for p in state.players:
        expected = state.civilian_word if p.role is Role.CIVILIAN else state.undercover_word
        assert p.word == expected
    assert state.civilian_word != state.undercover_word
    assert {state.civilian_word, state.undercover_word} <= set(state.trio.words)


def test_each_human_receives_only_their_word_privately():
    state, _, effects = start_game(3)
    private = [e for e in effects if isinstance(e, SendPrivate)]
    assert {e.player_id for e in private} == {p.id for p in state.humans}
    for e in private:
        assert e.params["word"] == state.player(e.player_id).word


def test_group_effects_never_carry_words_at_start():
    state, _, effects = start_game(4)
    secrets = {state.civilian_word, state.undercover_word}
    for e in effects:
        if e.__class__.__name__ == "SendGroup":
            assert not (set(map(str, e.params.values())) & secrets)


def test_deterministic_for_same_seed():
    a, _, _ = start_game(4, seed=7)
    b, _, _ = start_game(4, seed=7)
    assert a.to_dict() == b.to_dict()


def test_trio_recorded_as_played():
    _, ctx, effects = start_game(2)
    assert any(e.__class__.__name__ == "TrioPlayed" for e in effects)


def test_solo_launch_starts_countdown_then_game():
    ctx = make_ctx()
    state = make_lobby(1, ctx)
    effects = apply(state, Launch(hid(1)), ctx)
    assert state.solo_waiting and state.phase is Phase.LOBBY
    assert "solo_last_call" in keys(effects)
    last_call = next(e for e in effects if getattr(e, "key", "") == "solo_last_call")
    assert last_call.params["seconds"] == 30  # 30 secondes pour rejoindre
    apply(state, Timeout("solo_wait"), ctx)
    assert state.phase is Phase.DESCRIPTION
    assert len(state.players) == 4
    assert sum(p.role is Role.UNDERCOVER for p in state.players) == 1


def test_immediate_launch_skips_the_solo_countdown():
    ctx = make_ctx()
    state = make_lobby(1, ctx)
    apply(state, Launch(hid(1), immediate=True), ctx)
    assert state.phase is Phase.DESCRIPTION and len(state.players) == 4


def test_solo_second_human_joining_gives_five_players():
    ctx = make_ctx()
    state = make_lobby(1, ctx)
    apply(state, Launch(hid(1)), ctx)
    apply(state, Join(hid(2), "Joueur 2", True), ctx)
    assert state.solo_waiting
    apply(state, Launch(hid(1)), ctx)
    assert state.phase is Phase.DESCRIPTION
    assert len(state.players) == 5


def test_solo_cancel_during_countdown():
    ctx = make_ctx()
    state = make_lobby(1, ctx)
    apply(state, Launch(hid(1)), ctx)
    apply(state, Cancel(hid(1)), ctx)
    assert state.phase is Phase.CANCELLED


def test_launch_blocked_when_a_human_cannot_receive_dm():
    ctx = make_ctx()
    state = make_lobby(2, ctx)
    state.player(hid(2)).can_dm = False
    effects = apply(state, Launch(hid(1)), ctx)
    assert state.phase is Phase.LOBBY
    blocked = [e for e in effects if getattr(e, "key", "") == "launch_blocked"]
    assert blocked and blocked[0].params["names"] == ["Joueur 2"]
    apply(state, SetCanDm(hid(2), True), ctx)
    apply(state, Launch(hid(1)), ctx)
    assert state.phase is Phase.DESCRIPTION


def test_only_creator_can_launch_and_cancel():
    ctx = make_ctx()
    state = make_lobby(2, ctx)
    for ev in (Launch(hid(2)), Cancel(hid(2))):
        effects = apply(state, ev, ctx)
        assert any(isinstance(e, Notify) and e.key == "not_creator" for e in effects)
    assert state.phase is Phase.LOBBY


def test_ninth_human_refused():
    ctx = make_ctx()
    state = make_lobby(8, ctx)
    effects = apply(state, Join(hid(9), "Joueur 9", True), ctx)
    assert any(isinstance(e, Notify) and e.key == "full" for e in effects)
    assert len(state.humans) == 8


def test_duplicate_join_refused():
    ctx = make_ctx()
    state = make_lobby(2, ctx)
    effects = apply(state, Join(hid(2), "Joueur 2", True), ctx)
    assert any(isinstance(e, Notify) and e.key == "already_joined" for e in effects)


def test_creator_transfer_and_empty_lobby():
    ctx = make_ctx()
    state = make_lobby(3, ctx)
    apply(state, Leave(hid(1)), ctx)
    assert state.creator_id == hid(2)
    apply(state, Leave(hid(2)), ctx)
    apply(state, Leave(hid(3)), ctx)
    assert state.phase is Phase.CANCELLED


def test_lobby_timeout_cancels():
    ctx = make_ctx()
    state = make_lobby(2, ctx)
    apply(state, Timeout("lobby"), ctx)
    assert state.phase is Phase.CANCELLED


def test_default_mode_is_elimination_and_creator_can_change_it():
    ctx = make_ctx()
    state = make_lobby(3, ctx)
    assert state.mode is GameMode.ELIMINATION
    apply(state, SetMode(hid(1), GameMode.NO_ELIMINATION), ctx)
    assert state.mode is GameMode.NO_ELIMINATION
    apply(state, SetMode(hid(1), GameMode.ELIMINATION), ctx)
    assert state.mode is GameMode.ELIMINATION


def test_only_the_creator_chooses_the_mode():
    ctx = make_ctx()
    state = make_lobby(3, ctx)
    effects = apply(state, SetMode(hid(2), GameMode.NO_ELIMINATION), ctx)
    assert any(isinstance(e, Notify) and e.key == "not_creator" for e in effects)
    assert state.mode is GameMode.ELIMINATION


def test_mode_cannot_change_after_the_start():
    state, ctx, _ = start_game(3)
    effects = apply(state, SetMode(hid(1), GameMode.NO_ELIMINATION), ctx)
    assert any(isinstance(e, Notify) and e.key == "not_lobby" for e in effects)
    assert state.mode is GameMode.ELIMINATION


def test_chosen_mode_is_announced_at_the_start():
    state, ctx, effects = start_game(3, mode=GameMode.NO_ELIMINATION)
    started = next(e for e in effects if getattr(e, "key", "") == "game_started")
    assert started.params["mode"] == "no_elimination"
