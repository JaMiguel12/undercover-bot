import asyncio

import pytest

from game.models import Phase, Role
from tests.integration.fakes import FakeLLM, make_orchestrator, setup_game

CHAT = -8001
AI_NAMES = ["Zendaya IA", "Kendall IA", "BFF Diva IA"]
TABLE = {2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 1, 8: 0}
ROLES = {5: (4, 1), 6: (5, 1), 7: (6, 1), 8: (6, 2)}


@pytest.mark.parametrize("humans", range(2, 9))
async def test_ai_fill_the_table_when_launching(humans):
    orch = make_orchestrator(ai_driver=FakeLLM(), seed=humans)
    gid, state = await setup_game(orch, CHAT, humans)
    await orch.launch(CHAT, 1, gid)
    assert state.phase is Phase.DESCRIPTION
    ais = [p.name for p in state.players if p.is_ai]
    assert ais == AI_NAMES[: TABLE[humans]]
    assert len(state.players) == min(8, humans + TABLE[humans])
    total = len(state.players)
    counts = tuple(sum(p.role is r for p in state.players) for r in Role)
    assert counts == ROLES[total]


async def test_ai_roles_are_random_like_humans():
    roles = set()
    for seed in range(30):
        orch = make_orchestrator(ai_driver=FakeLLM(), seed=seed)
        gid, state = await setup_game(orch, -9000 - seed, 3)
        await orch.launch(-9000 - seed, 1, gid)
        roles |= {p.role for p in state.players if p.is_ai}
    assert roles == set(Role)


async def test_solo_launch_shows_last_call_and_live_countdown():
    orch = make_orchestrator(ai_driver=FakeLLM())
    gid, state = await setup_game(orch, CHAT, 1)
    await orch.launch(CHAT, 1, gid)
    await asyncio.sleep(0)
    assert state.phase is Phase.LOBBY and state.solo_waiting
    assert any("Dernier appel" in t for t in orch.transport.group_texts(CHAT))
    assert any("30 s" in e.text for e in orch.transport.edits)
    assert orch.games[CHAT].timer.kind == "solo_wait"


async def test_solo_without_arrival_starts_with_three_ai_at_four_players():
    orch = make_orchestrator(ai_driver=FakeLLM())
    gid, state = await setup_game(orch, CHAT, 1)
    await orch.launch(CHAT, 1, gid)
    await orch.fire_timeout(CHAT, "solo_wait")
    assert state.phase is Phase.DESCRIPTION
    assert [p.name for p in state.players if p.is_ai] == AI_NAMES
    assert tuple(sum(p.role is r for p in state.players) for r in Role) == (3, 1)


async def test_second_human_during_countdown_gives_two_humans_plus_three_ai():
    orch = make_orchestrator(ai_driver=FakeLLM())
    gid, state = await setup_game(orch, CHAT, 1)
    await orch.launch(CHAT, 1, gid)
    await orch.repo.set_user("2", "J2", True)
    await orch.join(CHAT, 2, "J2", gid)
    assert state.phase is Phase.LOBBY  # la partie démarre à la fin du délai
    await orch.launch(CHAT, 1, gid)  # ou dès que le créateur rappuie sur Lancer
    assert state.phase is Phase.DESCRIPTION
    assert len(state.players) == 5


async def test_second_human_then_timer_expiry_starts_normally():
    orch = make_orchestrator(ai_driver=FakeLLM())
    gid, state = await setup_game(orch, CHAT, 1)
    await orch.launch(CHAT, 1, gid)
    await orch.repo.set_user("2", "J2", True)
    await orch.join(CHAT, 2, "J2", gid)
    await orch.fire_timeout(CHAT, "solo_wait")
    assert len(state.players) == 5


async def test_creator_can_cancel_during_countdown():
    orch = make_orchestrator(ai_driver=FakeLLM())
    gid, state = await setup_game(orch, CHAT, 1)
    await orch.launch(CHAT, 1, gid)
    await orch.cancel(CHAT, 1, gid)
    assert CHAT not in orch.games
    assert state.phase is Phase.CANCELLED


async def test_ninth_human_still_refused_with_ai_rules():
    orch = make_orchestrator(ai_driver=FakeLLM())
    gid, state = await setup_game(orch, CHAT, 8)
    await orch.repo.set_user("9", "J9", True)
    await orch.join(CHAT, 9, "J9", gid, "cb9")
    assert len(state.humans) == 8
