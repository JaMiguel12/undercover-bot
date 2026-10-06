import pytest

from game.models import Outcome, Phase
from tests.unit.helpers import simulate


@pytest.mark.parametrize("humans", range(1, 9))
@pytest.mark.parametrize("seed", range(40))
def test_random_games_always_terminate(humans, seed):
    state, _ = simulate(humans, seed)
    assert state.phase in (Phase.ENDED, Phase.CANCELLED)
    assert state.outcome is not None
    if state.phase is Phase.ENDED:
        assert state.points  # un vainqueur au moins
        assert state.outcome is not Outcome.CANCELLED


def test_same_seed_same_result():
    a, _ = simulate(5, 17)
    b, _ = simulate(5, 17)
    assert a.to_dict() == b.to_dict()


def test_different_seeds_differ():
    results = {simulate(5, s)[0].outcome for s in range(30)}
    assert len(results) >= 2
