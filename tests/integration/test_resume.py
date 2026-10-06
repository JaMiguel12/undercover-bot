"""Reprise après redémarrage (FR-060, critère 11 du brief) avec une vraie base SQLite."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from db.repository import SqlRepository
from game.models import Phase
from tests.integration.fakes import (
    FakeLLM,
    FakeTransport,
    make_orchestrator,
    settle,
    setup_game,
)

CHAT = -4242
T0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)


class Clock:
    def __init__(self, now: datetime = T0):
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class Sleeps:
    """Enregistre les durées demandées par les minuteries, puis attend indéfiniment."""

    def __init__(self):
        self.durations: list[float] = []

    async def __call__(self, seconds: float) -> None:
        if seconds == 0:
            await asyncio.sleep(0)
            return
        self.durations.append(seconds)
        await asyncio.Event().wait()


@pytest.fixture
async def db_url(tmp_path):
    return f"sqlite+aiosqlite:///{tmp_path / 'resume.db'}"


async def boot(db_url, clock, sleeps=None, ai_driver=None, seed=1):
    repo = SqlRepository(db_url)
    await repo.init()
    transport = FakeTransport()
    orch = make_orchestrator(
        transport=transport,
        repo=repo,
        clock=clock,
        sleep=sleeps or Sleeps(),
        ai_driver=ai_driver,
        seed=seed,
    )
    return orch, repo, transport


async def crash(orch, repo):
    """Simule l'arrêt brutal du processus : tâches annulées, connexions fermées."""
    for rt in orch.games.values():
        if rt.timer and rt.timer.task:
            rt.timer.task.cancel()
        for t in rt.ai_tasks:
            t.cancel()
    await asyncio.sleep(0)
    await repo.close()


async def wait_for(condition, timeout: float = 3.0) -> None:
    """Attend une condition (la base SQLite fait de vraies entrées/sorties)."""
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while not condition() and loop.time() < end:
        await asyncio.sleep(0.01)


async def describe_all(orch, state):
    rnd = state.round
    while state.phase is Phase.DESCRIPTION and state.round == rnd:
        sp = state.current_speaker
        if sp.is_ai:
            await settle(orch)
            continue
        await orch.on_group_text(CHAT, int(sp.id.split(":")[1]), "indice", 1)


async def test_restart_during_vote_resumes_same_vote_with_remaining_time(db_url):
    clock = Clock()
    orch, repo, transport = await boot(db_url, clock)
    gid, state = await setup_game(orch, CHAT, 8)
    await orch.launch(CHAT, 1, gid)
    await describe_all(orch, state)
    assert state.phase is Phase.VOTE
    await orch.vote(CHAT, 1, gid, "h:3", "c1")
    await orch.vote(CHAT, 2, gid, "h:3", "c2")
    ballots = dict(state.current_vote.ballots)
    await crash(orch, repo)

    clock.now = T0 + timedelta(seconds=30)  # 30 s écoulées sur 90
    sleeps = Sleeps()
    orch2, repo2, transport2 = await boot(db_url, clock, sleeps)
    assert await orch2.resume() == 1
    await asyncio.sleep(0)
    rt = orch2.games[CHAT]
    assert rt.state.phase is Phase.VOTE
    assert rt.state.current_vote.ballots == ballots  # même vote, bulletins conservés
    assert sleeps.durations == [pytest.approx(60.0, abs=0.01)]  # délai restant cohérent
    assert rt.timer.kind == "vote"
    assert transport2.group == []  # aucun message dupliqué au redémarrage

    # le vote reprend : les autres joueurs peuvent voter et la partie continue
    for uid in range(3, 9):
        await orch2.vote(CHAT, uid, gid, "h:1" if uid != 1 else "h:2", f"c{uid}")
    assert rt.state.phase is not Phase.VOTE or rt.state.current_vote.kind.value == "revote"
    await repo2.close()


async def test_overdue_deadline_is_handled_immediately_after_restart(db_url):
    clock = Clock()
    orch, repo, _ = await boot(db_url, clock)
    gid, state = await setup_game(orch, CHAT, 8)
    await orch.launch(CHAT, 1, gid)
    first = state.current_speaker.id
    await crash(orch, repo)

    clock.now = T0 + timedelta(minutes=10)  # largement après l'échéance de 60 s
    sleeps = Sleeps()
    orch2, repo2, transport2 = await boot(db_url, clock, sleeps)
    await orch2.resume()
    rt = orch2.games[CHAT]
    await wait_for(lambda: any("passe son tour" in t for t in transport2.group_texts(CHAT)))
    assert any("passe son tour" in t for t in transport2.group_texts(CHAT))
    assert rt.state.descriptions[0].player_id == first and rt.state.descriptions[0].skipped
    await repo2.close()


async def test_restart_while_an_ai_must_describe_makes_it_play(db_url):
    clock = Clock()
    llm = FakeLLM()
    orch, repo, _ = await boot(db_url, clock, ai_driver=llm)
    gid, state = await setup_game(orch, CHAT, 2)
    await orch.launch(CHAT, 1, gid)
    while not state.current_speaker.is_ai:
        await orch.on_group_text(CHAT, int(state.current_speaker.id.split(":")[1]), "indice", 1)
    # l'IA vient d'être sollicitée, mais le processus s'arrête avant sa réponse
    await crash(orch, repo)
    ai_id = state.current_speaker.id

    orch2, repo2, transport2 = await boot(db_url, clock, ai_driver=FakeLLM())
    await orch2.resume()
    await settle(orch2)
    resumed = orch2.games[CHAT].state
    assert any(d.player_id == ai_id for d in resumed.descriptions)
    await repo2.close()


async def test_restart_during_solo_countdown_continues_it(db_url):
    clock = Clock()
    orch, repo, _ = await boot(db_url, clock)
    gid, state = await setup_game(orch, CHAT, 1)
    await orch.launch(CHAT, 1, gid)
    await asyncio.sleep(0)
    await crash(orch, repo)

    clock.now = T0 + timedelta(seconds=20)
    sleeps = Sleeps()
    orch2, repo2, transport2 = await boot(db_url, clock, sleeps)
    await orch2.resume()
    await asyncio.sleep(0)
    rt = orch2.games[CHAT]
    assert rt.state.solo_waiting and rt.timer.kind == "solo_wait"
    assert any("10 s" in e.text for e in transport2.edits)  # 30 - 20 s, même message
    assert transport2.edits[0].message_id == rt.lobby_message_id
    await orch2.fire_timeout(CHAT, "solo_wait")
    assert rt.state.phase is Phase.DESCRIPTION and len(rt.state.players) == 4
    await repo2.close()


async def test_restart_in_lobby_keeps_players_and_user_rule(db_url):
    clock = Clock()
    orch, repo, _ = await boot(db_url, clock)
    gid, state = await setup_game(orch, CHAT, 3)
    await crash(orch, repo)

    orch2, repo2, transport2 = await boot(db_url, clock)
    await orch2.resume()
    rt = orch2.games[CHAT]
    assert [p.name for p in rt.state.humans] == ["J1", "J2", "J3"]
    assert await repo2.user_game("2") == gid
    assert await repo2.get_can_dm("2") is True  # statut des messages privés conservé
    await orch2.create_lobby(-999, 2, "J2")  # J2 est déjà dans une partie
    assert "déjà inscrit" in transport2.last_group().text
    await orch2.launch(CHAT, 1, gid)
    assert rt.state.phase is Phase.DESCRIPTION
    await repo2.close()


async def test_finished_game_is_not_resumed(db_url):
    clock = Clock()
    orch, repo, _ = await boot(db_url, clock)
    gid, state = await setup_game(orch, CHAT, 2)
    await orch.cancel(CHAT, 1, gid)
    await repo.close()
    orch2, repo2, _ = await boot(db_url, clock)
    assert await orch2.resume() == 0
    assert orch2.games == {}
    await repo2.close()
