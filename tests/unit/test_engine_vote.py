from game.engine import apply
from game.models import CastVote, Notify, Outcome, Phase, SendGroup, Timeout, VoteKind
from tests.unit.helpers import describe_round, everyone_votes, keys, start_game


def to_vote(n_humans=8, seed=0):
    state, ctx, _ = start_game(n_humans, seed)
    describe_round(state, ctx)
    assert state.phase is Phase.VOTE
    return state, ctx


def cast(state, ctx, ballots):
    out = []
    for voter, target in ballots.items():
        out += apply(state, CastVote(voter, target), ctx)
    return out


def tie_ballots(state):
    """Égalité parfaite : les deux premiers vivants se votent, les autres alternent."""
    ids = [p.id for p in state.alive]
    a, b = ids[0], ids[1]
    ballots = {a: b, b: a}
    for i, pid in enumerate(ids[2:]):
        ballots[pid] = a if i % 2 == 0 else b
    return a, b, ballots


def test_one_button_per_alive_player():
    state, ctx = to_vote(5)
    vote_round = state.current_vote
    assert vote_round.kind is VoteKind.VOTE
    assert set(vote_round.candidates) == {p.id for p in state.alive}


def test_cannot_vote_for_self():
    state, ctx = to_vote()
    me = state.alive[0].id
    effects = apply(state, CastVote(me, me), ctx)
    assert any(isinstance(e, Notify) and e.key == "self_vote" for e in effects)
    assert me not in state.current_vote.ballots


def test_dead_or_unknown_target_refused():
    state, ctx = to_vote()
    effects = apply(state, CastVote(state.alive[0].id, "h:999"), ctx)
    assert any(isinstance(e, Notify) and e.key == "invalid_target" for e in effects)


def test_vote_can_be_changed_while_open():
    state, ctx = to_vote()
    a, b, c = (p.id for p in state.alive[:3])
    apply(state, CastVote(a, b), ctx)
    apply(state, CastVote(a, c), ctx)
    assert state.current_vote.ballots[a] == c


def test_vote_closes_when_everybody_voted_and_most_voted_is_eliminated():
    state, ctx = to_vote()
    target = state.alive[2].id
    effects = everyone_votes(state, ctx, target)
    assert not state.player(target).alive
    assert "vote_result" in keys(effects) and "eliminated" in keys(effects)
    result = next(e for e in effects if isinstance(e, SendGroup) and e.key == "vote_result")
    assert len(result.params["ballots"]) == 8  # qui a voté pour qui


def test_vote_closes_on_timeout_with_abstentions():
    state, ctx = to_vote()
    ids = [p.id for p in state.alive]
    cast(state, ctx, {ids[0]: ids[2], ids[1]: ids[2]})
    apply(state, Timeout("vote"), ctx)
    assert not state.player(ids[2]).alive


def test_tie_triggers_revote_among_tied_players_only():
    state, ctx = to_vote()
    a, b, ballots = tie_ballots(state)
    effects = cast(state, ctx, ballots)
    assert "tie_revote" in keys(effects)
    assert state.phase is Phase.REVOTE
    assert set(state.current_vote.candidates) == {a, b}
    assert all(p.alive for p in state.players)


def test_new_tie_in_revote_draws_a_name():
    state, ctx = to_vote()
    a, b, ballots = tie_ballots(state)
    cast(state, ctx, ballots)
    effects = cast(state, ctx, ballots)  # mêmes bulletins : A->B, B->A, autres alternent
    assert "tie_draw" in keys(effects)
    dead = [p.id for p in state.players if not p.alive]
    assert len(dead) == 1 and dead[0] in (a, b)
    assert state.vote_rounds[-1].tie_break_drawn


def test_revote_tied_players_vote_too_but_not_for_themselves():
    state, ctx = to_vote()
    a, b, ballots = tie_ballots(state)
    cast(state, ctx, ballots)
    effects = apply(state, CastVote(a, a), ctx)
    assert any(isinstance(e, Notify) and e.key == "self_vote" for e in effects)
    effects = apply(state, CastVote(state.alive[2].id, state.alive[3].id), ctx)
    assert any(isinstance(e, Notify) and e.key == "invalid_target" for e in effects)


def test_no_vote_means_no_elimination_and_new_round():
    state, ctx = to_vote()
    effects = apply(state, Timeout("vote"), ctx)
    assert "no_votes" in keys(effects)
    assert state.no_vote_streak == 1
    assert state.phase is Phase.DESCRIPTION and state.round == 2
    assert all(p.alive for p in state.players)


def test_three_consecutive_rounds_without_votes_cancel_without_points():
    state, ctx = to_vote()
    for _ in range(3):
        apply(state, Timeout("vote"), ctx)
        if state.phase is Phase.DESCRIPTION:
            describe_round(state, ctx)
    assert state.phase is Phase.CANCELLED
    assert state.outcome is Outcome.CANCELLED
    assert state.points == {}


def test_a_vote_resets_the_streak():
    state, ctx = to_vote()
    apply(state, Timeout("vote"), ctx)
    describe_round(state, ctx)
    everyone_votes(state, ctx)
    assert state.no_vote_streak == 0


def test_vote_after_close_is_refused():
    state, ctx = to_vote()
    everyone_votes(state, ctx)
    if state.phase is Phase.DESCRIPTION:
        effects = apply(state, CastVote(state.alive[0].id, state.alive[1].id), ctx)
        assert any(isinstance(e, Notify) and e.key == "vote_closed" for e in effects)
