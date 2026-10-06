"""Contrat du dépôt : mêmes tests pour l'implémentation mémoire et pour SQLite."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from db.repository import MemoryRepository, SqlRepository, StoredGame
from game.engine import apply, create_lobby
from game.models import Describe, Join, Launch
from tests.unit.helpers import make_ctx


@pytest.fixture(params=["memory", "sql"])
async def repo(request, tmp_path):
    if request.param == "memory":
        yield MemoryRepository()
        return
    r = SqlRepository(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await r.init()
    yield r
    await r.close()


def started_game(game_id="g1", chat_id=-1, humans=3):
    ctx = make_ctx(seed=3)
    state = create_lobby(game_id, chat_id, "h:1", "Alice", True)
    for i in range(2, humans + 1):
        apply(state, Join(f"h:{i}", f"J{i}", True), ctx)
    apply(state, Launch("h:1"), ctx)
    return state, ctx


async def test_state_roundtrip_is_identical(repo):
    state, ctx = started_game()
    apply(state, Describe(state.current_speaker.id, "indice"), ctx)
    deadline = datetime.now(UTC) + timedelta(seconds=60)
    await repo.save_game(StoredGame(state, "description", deadline, 77))
    [loaded] = await repo.load_active_games()
    assert loaded.state.to_dict() == state.to_dict()
    assert loaded.deadline_kind == "description"
    assert abs((loaded.deadline_at - deadline).total_seconds()) < 1
    assert loaded.deadline_at.tzinfo is not None
    assert loaded.lobby_message_id == 77


async def test_save_replaces_previous_version(repo):
    state, ctx = started_game()
    await repo.save_game(StoredGame(state))
    apply(state, Describe(state.current_speaker.id, "premier"), ctx)
    await repo.save_game(StoredGame(state))
    games = await repo.load_active_games()
    assert len(games) == 1 and len(games[0].state.descriptions) == 1


async def test_finished_games_are_not_active_and_free_their_players(repo):
    state, ctx = started_game()
    await repo.save_game(StoredGame(state))
    assert await repo.user_game("2") == "g1"
    from game.models import Cancel

    apply(state, Cancel("h:1"), ctx)
    await repo.save_game(StoredGame(state))
    assert await repo.load_active_games() == []
    assert await repo.user_game("2") is None


async def test_user_belongs_to_one_game_only(repo):
    state, _ = started_game("g1", -1)
    other, _ = started_game("g2", -2, humans=2)
    other.players[0].id = "h:10"
    other.players[1].id = "h:11"
    other.creator_id = "h:10"
    await repo.save_game(StoredGame(state))
    await repo.save_game(StoredGame(other))
    assert await repo.user_game("1") == "g1"
    assert await repo.user_game("11") == "g2"
    assert await repo.user_game("999") is None


async def test_users_can_dm_flag_is_stored(repo):
    assert await repo.get_can_dm("42") is False
    await repo.set_user("42", "Zoé", True)
    assert await repo.get_can_dm("42") is True


async def test_played_trios_per_group_with_reset(repo):
    await repo.add_played_trio(-1, 5)
    await repo.add_played_trio(-1, 6)
    await repo.add_played_trio(-2, 5)
    assert await repo.played_trios(-1) == {5, 6}
    assert await repo.played_trios(-2) == {5}
    await repo.add_played_trio(-1, 9, reset=True)
    assert await repo.played_trios(-1) == {9}
    assert await repo.played_trios(-2) == {5}


async def test_scores_accumulate_and_are_sorted_per_group(repo):
    players = [("h:1", "Alice"), ("ai:zendaya", "Zendaya IA"), ("h:2", "Bob")]
    await repo.add_scores(-1, {"h:1": 2, "ai:zendaya": 10}, players)
    await repo.add_scores(-1, {"h:1": 2, "h:2": 6}, players)
    await repo.add_scores(-2, {"h:1": 99}, players)
    board = await repo.leaderboard(-1)
    assert [(r.name, r.points, r.games_played) for r in board] == [
        ("Zendaya IA", 10, 2),
        ("Bob", 6, 2),
        ("Alice", 4, 2),
    ]
    assert (await repo.leaderboard(-2))[0].points == 99
    assert await repo.leaderboard(-3) == []


async def test_sql_allows_only_one_active_game_per_group(tmp_path):
    r = SqlRepository(f"sqlite+aiosqlite:///{tmp_path / 'one.db'}")
    await r.init()
    a, _ = started_game("g1", -1)
    b, _ = started_game("g2", -1)
    await r.save_game(StoredGame(a))
    with pytest.raises(IntegrityError):
        await r.save_game(StoredGame(b))
    await r.close()


async def test_sql_data_survives_reopening_the_file(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'persist.db'}"
    r1 = SqlRepository(url)
    await r1.init()
    state, _ = started_game()
    await r1.save_game(StoredGame(state, "vote", datetime.now(UTC), 5))
    await r1.set_user("7", "Max", True)
    await r1.add_scores(-1, {"h:1": 2}, [("h:1", "Alice")])
    await r1.close()
    r2 = SqlRepository(url)
    await r2.init()
    assert len(await r2.load_active_games()) == 1
    assert await r2.get_can_dm("7") is True
    assert (await r2.leaderboard(-1))[0].points == 2
    await r2.close()


async def test_init_creates_missing_directory(tmp_path):
    r = SqlRepository(f"sqlite+aiosqlite:///{tmp_path / 'nouveau' / 'dossier' / 'x.db'}")
    await r.init()
    assert (tmp_path / "nouveau" / "dossier" / "x.db").exists()
    await r.close()


async def test_games_saved_with_the_old_rules_are_cancelled_at_load(tmp_path, caplog):
    import json as _json
    from datetime import datetime

    from sqlalchemy import text

    r = SqlRepository(f"sqlite+aiosqlite:///{tmp_path / 'old.db'}")
    await r.init()
    old_state = {"game_id": "old1", "chat_id": -5, "phase": "mr_white_guess", "players": []}
    async with r.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO games (game_id, chat_id, phase, state_json, updated_at) "
                "VALUES (:g, :c, :p, :s, :u)"
            ),
            {
                "g": "old1",
                "c": -5,
                "p": "mr_white_guess",
                "s": _json.dumps(old_state),
                "u": datetime(2026, 1, 1),
            },
        )
    assert await r.load_active_games() == []
    assert "anciennes règles" in caplog.text
    assert await r.load_active_games() == []  # la partie est bien clôturée, pas relue
    async with r.engine.begin() as conn:
        phase = (await conn.execute(text("SELECT phase FROM games WHERE game_id='old1'"))).scalar()
    assert phase == "cancelled"
    await r.close()
