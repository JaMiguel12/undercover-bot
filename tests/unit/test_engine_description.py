from game.engine import apply
from game.models import DeleteMessage, Describe, PassTurn, Phase, SendGroup, Timeout
from tests.unit.helpers import describe_round, everyone_votes, keys, start_game


def test_only_one_word_is_accepted():
    state, ctx, _ = start_game(3)
    speaker = state.current_speaker
    effects = apply(state, Describe(speaker.id, "deux mots"), ctx)
    assert "description_too_long" in keys(effects)
    assert state.descriptions == []
    apply(state, Describe(speaker.id, "unmot"), ctx)
    assert len(state.descriptions) == 1


def test_surrounding_spaces_do_not_count_as_words():
    state, ctx, _ = start_game(3)
    apply(state, Describe(state.current_speaker.id, "   unmot  "), ctx)
    assert state.descriptions[0].text == "unmot"


def test_only_current_speaker_counts():
    state, ctx, _ = start_game(3)
    other = next(p for p in state.players if p.id != state.current_speaker.id)
    assert apply(state, Describe(other.id, "bonjour"), ctx) == []
    assert state.descriptions == []


def test_secret_word_refused_and_message_deleted():
    state, ctx, _ = start_game(3)
    speaker = state.current_speaker
    effects = apply(state, Describe(speaker.id, speaker.word.upper()), ctx)
    assert any(isinstance(e, DeleteMessage) for e in effects)
    assert "description_forbidden" in keys(effects)
    assert state.descriptions == []
    assert state.current_speaker.id == speaker.id  # même orateur, il peut réessayer
    for e in effects:
        if isinstance(e, SendGroup):
            assert speaker.word not in str(e.params)


def test_timeout_passes_the_turn_and_signals_it():
    state, ctx, _ = start_game(3)
    first = state.current_speaker
    effects = apply(state, Timeout("description"), ctx)
    assert "turn_passed" in keys(effects)
    assert state.descriptions[0].skipped and state.descriptions[0].player_id == first.id


def test_pass_turn_event_for_ai_fallback():
    state, ctx, _ = start_game(3)
    first = state.current_speaker
    effects = apply(state, PassTurn(first.id), ctx)
    assert "turn_passed" in keys(effects)


def test_ai_description_is_announced_with_player_id():
    state, ctx, _ = start_game(2)
    while not state.current_speaker.is_ai:
        apply(state, Describe(state.current_speaker.id, "indice"), ctx)
    ai = state.current_speaker
    effects = apply(state, Describe(ai.id, "discret"), ctx)
    announced = [e for e in effects if isinstance(e, SendGroup) and e.key == "ai_description"]
    assert announced and announced[0].params["player_id"] == ai.id


def test_three_description_rounds_before_the_vote():
    state, ctx, _ = start_game(4)
    n = len(state.players)
    seen_sub_rounds = [state.sub_round]
    announcements = []
    while state.phase is Phase.DESCRIPTION:
        speaker = state.current_speaker
        effects = apply(state, Describe(speaker.id, f"mot{len(state.descriptions)}"), ctx)
        announcements += [e for e in effects if getattr(e, "key", "") == "round_start"]
        seen_sub_rounds.append(state.sub_round)
    assert state.phase is Phase.VOTE
    assert len(state.descriptions) == 3 * n  # chacun dit 3 mots
    assert {d.sub_round for d in state.descriptions} == {1, 2, 3}
    assert sorted(set(seen_sub_rounds)) == [1, 2, 3]
    assert [a.params["sub_round"] for a in announcements] == [2, 3]
    assert all(a.params["sub_total"] == 3 for a in announcements)


def test_each_player_speaks_once_per_round_in_the_same_order():
    state, ctx, _ = start_game(4, seed=2)
    describe_round(state, ctx)
    order = [d.player_id for d in state.descriptions]
    n = len(state.players)
    assert order[:n] == order[n : 2 * n] == order[2 * n :]
    assert len(set(order[:n])) == n


def test_recap_lists_the_three_words_of_each_player_before_the_vote():
    state, ctx, _ = start_game(3, seed=1)
    effects = describe_round(state, ctx)
    ks = keys(effects)
    assert ks.index("recap") < ks.index("vote_open")
    recap = next(e for e in effects if isinstance(e, SendGroup) and e.key == "recap")
    assert all(len(words) == 3 for _, words in recap.params["items"])


def test_a_passed_turn_shows_in_the_recap_as_none():
    state, ctx, _ = start_game(3, seed=1)
    apply(state, Timeout("description"), ctx)
    effects = describe_round(state, ctx)
    recap = next(e for e in effects if isinstance(e, SendGroup) and e.key == "recap")
    assert any(None in words for _, words in recap.params["items"])


def test_first_speaker_rotates_in_initial_order_after_an_elimination():
    state, ctx, _ = start_game(6, seed=11)
    first_round_first = state.speaking_order[0]
    describe_round(state, ctx)
    everyone_votes(state, ctx)
    assert state.phase is Phase.DESCRIPTION and state.round == 2
    order = state.initial_order
    start = order.index(first_round_first)
    expected = next(
        order[(start + step) % len(order)]
        for step in range(1, len(order) + 1)
        if state.player(order[(start + step) % len(order)]).alive
    )
    assert state.speaking_order[0] == expected
    assert state.sub_round == 1  # on repart sur 3 nouveaux tours


def test_eliminated_player_does_not_speak_again():
    state, ctx, _ = start_game(6, seed=5)
    describe_round(state, ctx)
    everyone_votes(state, ctx)
    dead = {p.id for p in state.players if not p.alive}
    assert dead and not dead & set(state.speaking_order)
