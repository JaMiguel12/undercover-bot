from db.repository import SqlRepository
from game.models import Outcome
from tests.integration.fakes import FakeLLM, make_orchestrator, play_out, setup_game

CHAT = -9901


async def play_games(orch, chat_id, n, humans=3, base_seed=0, require_end=True):
    """Joue n parties dans un groupe ; renvoie les états finaux."""
    finals = []
    seed = base_seed
    while len(finals) < n:
        seed += 1
        gid, state = await setup_game(orch, chat_id, humans)
        await orch.launch(chat_id, 1, gid)
        await play_out(orch, chat_id, gid, seed=seed)
        if state.outcome is not Outcome.CANCELLED or not require_end:
            finals.append(state)
    return finals


async def test_points_accumulate_over_games_and_include_ai():
    orch = make_orchestrator(ai_driver=FakeLLM(), seed=11)
    finals = await play_games(orch, CHAT, 4)
    expected: dict[str, int] = {}
    names: dict[str, str] = {}
    for st in finals:
        for p in st.players:
            names[p.id] = p.name
        for pid, pts in st.points.items():
            expected[pid] = expected.get(pid, 0) + pts
    board = await orch.repo.leaderboard(CHAT)
    got = {r.player_id: r.points for r in board}
    for pid, pts in expected.items():
        assert got[pid] == pts
    assert any(r.player_id.startswith("ai:") for r in board)  # les IA au classement
    assert [r.points for r in board] == sorted((r.points for r in board), reverse=True)
    text = await orch.leaderboard_text(CHAT)
    assert "Classement du groupe" in text and "🤖" in text and "🥇" in text


async def test_both_outcomes_are_scored():
    seen: set[Outcome] = set()
    orch = make_orchestrator(ai_driver=FakeLLM(), seed=5)
    for chat in range(-9950, -9930):
        for st in await play_games(orch, chat, 3, humans=4, base_seed=chat):
            seen.add(st.outcome)
            if st.outcome is Outcome.CIVILIANS:
                assert set(st.points.values()) == {2}
            elif st.outcome is Outcome.INFILTRATORS:
                assert set(st.points.values()) == {10}
        if len(seen) == 2:
            break
    assert seen == {Outcome.CIVILIANS, Outcome.INFILTRATORS}


async def test_groups_have_independent_scores():
    orch = make_orchestrator(ai_driver=FakeLLM(), seed=3)
    [a] = await play_games(orch, -9961, 1)
    [b] = await play_games(orch, -9962, 1, base_seed=50)
    board_a = {r.player_id: r.points for r in await orch.repo.leaderboard(-9961)}
    board_b = {r.player_id: r.points for r in await orch.repo.leaderboard(-9962)}
    for pid, pts in a.points.items():
        assert board_a[pid] == pts
    for pid, pts in b.points.items():
        assert board_b[pid] == pts
    assert await orch.repo.leaderboard(-9963) == []


async def test_cancelled_game_gives_no_points_and_no_games_played():
    orch = make_orchestrator(seed=2)
    gid, state = await setup_game(orch, CHAT, 3)
    await orch.launch(CHAT, 1, gid)
    await orch.cancel(CHAT, 1, gid)
    assert await orch.repo.leaderboard(CHAT) == []


async def test_empty_leaderboard_message():
    orch = make_orchestrator()
    assert "Aucun score" in await orch.leaderboard_text(CHAT)


async def test_scores_survive_restart_with_sql(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'scores.db'}"
    repo = SqlRepository(url)
    await repo.init()
    orch = make_orchestrator(repo=repo, ai_driver=FakeLLM(), seed=8)
    [st] = await play_games(orch, CHAT, 1)
    await repo.close()
    repo2 = SqlRepository(url)
    await repo2.init()
    orch2 = make_orchestrator(repo=repo2)
    board = await repo2.leaderboard(CHAT)
    assert {r.player_id: r.points for r in board if r.points} == st.points
    assert "pts" in await orch2.leaderboard_text(CHAT)
    await repo2.close()
