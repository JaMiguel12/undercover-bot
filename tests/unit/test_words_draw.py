import random

from game.models import WordTrio
from game.words import draw


def make_trios(n):
    return [WordTrio(i, "C", (f"a{i}", f"b{i}", f"c{i}")) for i in range(1, n + 1)]


def test_draw_excludes_played():
    trios = make_trios(10)
    played = set(range(1, 10))
    for seed in range(20):
        d = draw(trios, played, random.Random(seed))
        assert d.trio.id == 10


def test_draw_restarts_when_all_played():
    trios = make_trios(5)
    d = draw(trios, {1, 2, 3, 4, 5}, random.Random(1))
    assert d.trio.id in {1, 2, 3, 4, 5}
    assert d.cycle_restarted is True


def test_draw_no_replay_until_all_played():
    trios = make_trios(30)
    played: set[int] = set()
    rng = random.Random(3)
    for _ in range(30):
        d = draw(trios, played, rng)
        assert d.trio.id not in played
        played.add(d.trio.id)
    assert played == {t.id for t in trios}


def test_draw_deterministic_for_seed():
    trios = make_trios(20)
    a = draw(trios, set(), random.Random(42))
    b = draw(trios, set(), random.Random(42))
    assert a == b


def test_words_shuffled_over_seeds():
    trios = make_trios(1)
    seen = {draw(trios, set(), random.Random(s)).civilian for s in range(60)}
    assert seen == set(trios[0].words)


def test_civilians_and_undercovers_get_two_distinct_words_of_the_trio():
    for seed in range(20):
        d = draw(make_trios(1), set(), random.Random(seed))
        assert d.civilian != d.undercover
        assert {d.civilian, d.undercover} <= set(d.trio.words)
