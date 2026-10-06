import pytest

from game.models import GameState, Outcome, Player, Role
from game.rules import ai_completion, check_victory, compute_points, role_distribution
from tests.unit.helpers import CONFIG


@pytest.mark.parametrize(
    "humans,expected_ai,total",
    [(1, 3, 4), (2, 3, 5), (3, 3, 6), (4, 3, 7), (5, 3, 8), (6, 2, 8), (7, 1, 8), (8, 0, 8)],
)
def test_ai_completion_table(humans, expected_ai, total):
    ai = ai_completion(humans)
    assert len(ai) == expected_ai
    assert humans + len(ai) == total


def test_ai_priority_order():
    assert [n for _, n in ai_completion(1)] == ["Zendaya IA", "Kendall IA", "BFF Diva IA"]
    assert [n for _, n in ai_completion(6)] == ["Zendaya IA", "Kendall IA"]
    assert [n for _, n in ai_completion(7)] == ["Zendaya IA"]


@pytest.mark.parametrize("humans", [0, 9, -1])
def test_ai_completion_refuses_out_of_range(humans):
    with pytest.raises(ValueError):
        ai_completion(humans)


@pytest.mark.parametrize(
    "total,expected",
    [(4, (3, 1)), (5, (4, 1)), (6, (5, 1)), (7, (6, 1)), (8, (6, 2))],
)
def test_role_distribution_without_mr_white(total, expected):
    assert role_distribution(total, CONFIG) == expected


def test_role_distribution_unknown_total():
    with pytest.raises(ValueError):
        role_distribution(3, CONFIG)


def test_config_has_three_description_rounds():
    assert CONFIG.description_rounds == 3


def state_with(roles, alive=None):
    players = [Player(f"p{i}", f"P{i}", role=r) for i, r in enumerate(roles)]
    for i, p in enumerate(players):
        p.alive = True if alive is None else alive[i]
    return GameState("g", 1, "p0", players=players)


def test_victory_civilians_when_no_undercover_alive():
    roles = [Role.CIVILIAN] * 4 + [Role.UNDERCOVER]
    s = state_with(roles, [True, True, True, True, False])
    assert check_victory(s) is Outcome.CIVILIANS


def test_victory_infiltrators_when_one_civilian_left():
    roles = [Role.CIVILIAN] * 4 + [Role.UNDERCOVER]
    s = state_with(roles, [True, False, False, False, True])
    assert check_victory(s) is Outcome.INFILTRATORS


def test_victory_infiltrators_when_no_civilian_left():
    roles = [Role.CIVILIAN] * 3 + [Role.UNDERCOVER]
    s = state_with(roles, [False, False, False, True])
    assert check_victory(s) is Outcome.INFILTRATORS


def test_no_victory_while_two_civilians_and_an_undercover():
    roles = [Role.CIVILIAN] * 3 + [Role.UNDERCOVER]
    s = state_with(roles, [True, True, False, True])
    assert check_victory(s) is None


def test_two_undercovers_need_both_eliminated():
    roles = [Role.CIVILIAN] * 6 + [Role.UNDERCOVER] * 2
    alive = [True] * 7 + [False]
    assert check_victory(state_with(roles, alive)) is None


def test_points_civilians_all_civilians_alive_or_not():
    roles = [Role.CIVILIAN] * 3 + [Role.UNDERCOVER]
    s = state_with(roles, [True, False, True, False])
    s.outcome = Outcome.CIVILIANS
    assert compute_points(s, CONFIG) == {"p0": 2, "p1": 2, "p2": 2}


def test_points_undercovers():
    roles = [Role.CIVILIAN] * 6 + [Role.UNDERCOVER] * 2
    s = state_with(roles)
    s.outcome = Outcome.INFILTRATORS
    assert compute_points(s, CONFIG) == {"p6": 10, "p7": 10}


def test_points_none_when_cancelled():
    s = state_with([Role.CIVILIAN] * 4)
    s.outcome = Outcome.CANCELLED
    assert compute_points(s, CONFIG) == {}
