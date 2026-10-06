import dataclasses

from game.engine import public_view
from game.models import PublicView
from tests.unit.helpers import describe_round, everyone_votes, start_game


def flatten(obj) -> str:
    return repr(obj)


def test_public_view_has_no_role_or_foreign_word_field():
    names = {f.name for f in dataclasses.fields(PublicView)}
    assert (
        not {"role", "roles", "words", "civilian_word", "undercover_word", "mr_white_word"} & names
    )


def test_public_view_contents_and_secrecy():
    state, ctx, _ = start_game(4, seed=9)
    describe_round(state, ctx)
    ai = next(p for p in state.players if p.is_ai)
    view = public_view(state, ai.id)
    assert view.own_word == ai.word
    assert len(view.alive_players) == 7
    assert len(view.descriptions) == 7 * 3  # 3 tours de description
    text = flatten(view)
    others = {p.word for p in state.players if p.word != ai.word}
    assert not any(w in text for w in others)
    for role in ("civilian", "undercover"):
        assert role not in text  # aucun rôle révélé tant que personne n'est éliminé


def test_eliminated_role_is_public_but_not_their_word():
    state, ctx, _ = start_game(4, seed=9)
    describe_round(state, ctx)
    victim = next(p for p in state.players if not p.is_ai)
    everyone_votes(state, ctx, victim.id)
    viewer = next(p for p in state.alive if p.is_ai)
    view = public_view(state, viewer.id)
    assert any(
        name == victim.name and role == victim.role.value for _, name, role in view.eliminations
    )
    assert victim.name not in [n for _, n in view.alive_players]
    assert not any(
        w in flatten(view) for w in {p.word for p in state.players if p.word != viewer.word}
    )


def test_open_vote_ballots_are_not_in_the_view():
    state, ctx, _ = start_game(4, seed=9)
    describe_round(state, ctx)
    from game.models import CastVote

    a, b = state.alive[0], state.alive[1]
    from game.engine import apply

    apply(state, CastVote(a.id, b.id), ctx)
    assert public_view(state, a.id).votes == ()
