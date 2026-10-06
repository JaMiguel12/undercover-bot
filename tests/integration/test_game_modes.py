"""Choix du mode au lobby, un seul mot, 3 tours, et relance automatique du mode sans élimination."""

import asyncio

from bot import texts
from game.models import GameMode, Outcome, Phase, Role
from tests.integration.fakes import FakeLLM, make_orchestrator, settle, setup_game

CHAT = -7701


def mode_buttons(msg):
    return {
        b.callback_data.split(":")[2]: b.text
        for row in msg.markup.inline_keyboard
        for b in row
        if b.callback_data and b.callback_data.startswith("mode:")
    }


async def wait_until(condition, timeout=3.0):
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while not condition() and loop.time() < end:
        await asyncio.sleep(0.01)


# ------------------------------------------------------------ choix du mode au lobby


async def test_lobby_offers_both_modes_with_elimination_selected_by_default():
    orch = make_orchestrator()
    await orch.repo.set_user("1", "J1", True)
    await orch.create_lobby(CHAT, 1, "J1")
    msg = orch.transport.last_group()
    buttons = mode_buttons(msg)
    assert set(buttons) == {"elimination", "no_elimination"}
    assert buttons["elimination"].startswith("✔")
    assert "Avec élimination" in msg.text


async def test_creator_switches_mode_and_lobby_updates():
    orch = make_orchestrator()
    gid, state = await setup_game(orch, CHAT, 2)
    await orch.set_mode(CHAT, 1, gid, "no_elimination", "cb")
    assert state.mode is GameMode.NO_ELIMINATION
    edit = orch.transport.edits[-1]
    assert "Sans élimination" in edit.text
    assert mode_buttons(edit)["no_elimination"].startswith("✔")


async def test_only_the_creator_can_choose_the_mode():
    orch = make_orchestrator()
    gid, state = await setup_game(orch, CHAT, 2)
    await orch.set_mode(CHAT, 2, gid, "no_elimination", "cb2")
    assert state.mode is GameMode.ELIMINATION
    assert any(t == texts.NOT_CREATOR for _, t, _ in orch.transport.callbacks)


async def test_unknown_mode_value_is_ignored():
    orch = make_orchestrator()
    gid, state = await setup_game(orch, CHAT, 2)
    await orch.set_mode(CHAT, 1, gid, "n_importe_quoi", "cb3")
    assert state.mode is GameMode.ELIMINATION


async def test_the_mode_is_announced_when_the_game_starts():
    orch = make_orchestrator()
    gid, state = await setup_game(orch, CHAT, 3, mode="no_elimination")
    await orch.launch(CHAT, 1, gid)
    assert any("Sans élimination" in t for t in orch.transport.group_texts(CHAT))


# ------------------------------------------------------------ un mot, trois tours


async def test_a_two_word_description_is_refused_in_the_group():
    orch = make_orchestrator(seed=2)
    gid, state = await setup_game(orch, CHAT, 3)
    await orch.launch(CHAT, 1, gid)
    while state.current_speaker.is_ai:
        await orch.fire_timeout(CHAT, "description")
    speaker = state.current_speaker
    await orch.on_group_text(CHAT, int(speaker.id.split(":")[1]), "deux mots", 5)
    assert "un seul mot" in orch.transport.last_group().text
    assert not [d for d in state.descriptions if d.player_id == speaker.id and not d.skipped]


async def test_three_rounds_are_announced_before_the_vote():
    orch = make_orchestrator(seed=2)
    gid, state = await setup_game(orch, CHAT, 3)
    await orch.launch(CHAT, 1, gid)
    rnd = state.round
    while state.phase is Phase.DESCRIPTION and state.round == rnd:
        sp = state.current_speaker
        if sp.is_ai:
            await orch.fire_timeout(CHAT, "description")
        else:
            await orch.on_group_text(
                CHAT, int(sp.id.split(":")[1]), f"mot{len(state.descriptions)}", 9
            )
    texts_ = orch.transport.group_texts(CHAT)
    for k in (1, 2, 3):
        assert any(f"tour {k}/3" in t for t in texts_)
    recap = next(t for t in texts_ if "Récapitulatif" in t)
    assert recap.count("→") >= 2 * len(state.players)  # trois mots par joueur
    assert state.phase is Phase.VOTE


# ------------------------------------------------------------ mode sans élimination et relance


async def play_single_vote(orch, chat, gid, state, accuse_role: Role | None = None):
    """Joue les 3 tours puis le vote unique, contre un joueur du rôle voulu si possible."""
    rnd = state.round
    while state.phase is Phase.DESCRIPTION and state.round == rnd:
        sp = state.current_speaker
        if sp.is_ai:
            await orch.fire_timeout(chat, "description")
        else:
            await orch.on_group_text(
                chat, int(sp.id.split(":")[1]), f"m{len(state.descriptions)}", 3
            )
    target = next(
        (p for p in state.players if accuse_role and p.role is accuse_role), state.players[0]
    )
    for _ in range(4):  # vote, puis éventuel revote
        cv = state.current_vote
        if cv is None or chat not in orch.games:
            break
        for p in state.humans:
            if p.id in cv.ballots or state.current_vote is not cv:
                continue
            pick = (
                target.id
                if target.id in cv.candidates and target.id != p.id
                else next(c for c in cv.candidates if c != p.id)
            )
            await orch.vote(chat, int(p.id.split(":")[1]), gid, pick, "cb")
        await settle(orch)
        if state.current_vote is cv and chat in orch.games:
            await orch.fire_timeout(chat, "vote")


async def test_no_elimination_game_reveals_everything_after_the_single_vote():
    orch = make_orchestrator(ai_driver=FakeLLM(), seed=4, restart_delay=3600.0)
    gid, state = await setup_game(orch, CHAT, 3, mode="no_elimination")
    await orch.launch(CHAT, 1, gid)
    await play_single_vote(orch, CHAT, gid, state, Role.UNDERCOVER)
    assert state.phase is Phase.ENDED
    assert all(p.alive for p in state.players)  # personne n'est éliminé
    end = next(t for t in orch.transport.group_texts(CHAT) if "🔓" in t)
    assert "Les rôles" in end and "Points de la partie" in end
    assert state.civilian_word in end and state.undercover_word in end
    assert not any("est éliminé" in t for t in orch.transport.group_texts(CHAT))
    orch._stop_restart(CHAT)


async def test_a_new_game_starts_automatically_with_the_same_members():
    orch = make_orchestrator(ai_driver=FakeLLM(), seed=6, restart_delay=0.0)
    gid, state = await setup_game(orch, CHAT, 3, mode="no_elimination")
    await orch.launch(CHAT, 1, gid)
    first_game = state
    await play_single_vote(orch, CHAT, gid, state)
    assert first_game.phase is Phase.ENDED
    await wait_until(lambda: CHAT in orch.games)
    nxt = orch.games[CHAT].state
    assert nxt is not first_game and nxt.game_id != first_game.game_id
    assert nxt.mode is GameMode.NO_ELIMINATION
    assert [p.id for p in nxt.humans] == [p.id for p in first_game.humans]
    assert nxt.phase is Phase.DESCRIPTION
    assert any("Nouvelle partie dans" in t for t in orch.transport.group_texts(CHAT))
    for p in nxt.humans:  # chacun reçoit son nouveau mot en privé
        assert len(orch.transport.private[p.id.split(":")[1]]) >= 2
    orch._stop_restart(CHAT)


async def test_the_series_keeps_going_for_several_games():
    orch = make_orchestrator(ai_driver=FakeLLM(), seed=8, restart_delay=0.0)
    gid, state = await setup_game(orch, CHAT, 3, mode="no_elimination")
    await orch.launch(CHAT, 1, gid)
    game_ids = [state.game_id]
    for _ in range(3):
        cur = orch.games[CHAT].state
        await play_single_vote(orch, CHAT, cur.game_id, cur)
        await wait_until(
            lambda ids=tuple(game_ids): (
                CHAT in orch.games and orch.games[CHAT].state.game_id not in ids
            )
        )
        game_ids.append(orch.games[CHAT].state.game_id)
    assert len(set(game_ids)) == 4
    board = await orch.repo.leaderboard(CHAT)
    assert all(r.games_played >= 3 for r in board if not r.player_id.startswith("ai:"))


async def test_creator_stops_the_series_with_annuler_during_the_pause():
    orch = make_orchestrator(ai_driver=FakeLLM(), seed=6, restart_delay=3600.0)
    gid, state = await setup_game(orch, CHAT, 3, mode="no_elimination")
    await orch.launch(CHAT, 1, gid)
    await play_single_vote(orch, CHAT, gid, state)
    await wait_until(lambda: CHAT in orch.restarts)
    await orch.cancel(CHAT, 2, None, "cbx")  # pas le créateur
    assert CHAT in orch.restarts
    await orch.cancel(CHAT, 1, None)
    assert CHAT not in orch.restarts and CHAT not in orch.games
    assert orch.transport.last_group().text == texts.SERIES_STOPPED


async def test_cancelling_a_running_game_ends_the_series():
    orch = make_orchestrator(ai_driver=FakeLLM(), seed=6, restart_delay=0.0)
    gid, state = await setup_game(orch, CHAT, 3, mode="no_elimination")
    await orch.launch(CHAT, 1, gid)
    await orch.cancel(CHAT, 1, gid)
    await asyncio.sleep(0.05)
    assert CHAT not in orch.games and CHAT not in orch.restarts
    assert state.outcome is Outcome.CANCELLED


async def test_elimination_mode_does_not_restart_automatically():
    orch = make_orchestrator(ai_driver=FakeLLM(), seed=7, restart_delay=0.0)
    gid, state = await setup_game(orch, CHAT, 3)
    await orch.launch(CHAT, 1, gid)
    assert state.mode is GameMode.ELIMINATION
    from tests.integration.fakes import play_out

    await play_out(orch, CHAT, gid, seed=7)
    await asyncio.sleep(0.05)
    assert CHAT not in orch.restarts and CHAT not in orch.games


async def test_new_lobby_is_refused_while_a_restart_is_pending():
    orch = make_orchestrator(ai_driver=FakeLLM(), seed=6, restart_delay=3600.0)
    gid, state = await setup_game(orch, CHAT, 3, mode="no_elimination")
    await orch.launch(CHAT, 1, gid)
    await play_single_vote(orch, CHAT, gid, state)
    await wait_until(lambda: CHAT in orch.restarts)
    await orch.create_lobby(CHAT, 2, "J2")
    assert orch.transport.last_group().text == texts.RESTART_PENDING
    orch._stop_restart(CHAT)


async def test_a_member_who_joined_another_game_is_left_out_of_the_new_one():
    gate = asyncio.Event()

    async def gated_sleep(seconds: float) -> None:
        if seconds == 0:
            await asyncio.sleep(0)
        elif seconds == 1.0:
            await gate.wait()  # la pause avant la relance dure tant qu'on n'ouvre pas la porte
        else:
            await asyncio.Event().wait()  # les autres minuteries ne se déclenchent pas

    orch = make_orchestrator(ai_driver=FakeLLM(), seed=6, restart_delay=1.0, sleep=gated_sleep)
    gid, state = await setup_game(orch, CHAT, 3, mode="no_elimination")
    await orch.launch(CHAT, 1, gid)
    await play_single_vote(orch, CHAT, gid, state)
    await wait_until(lambda: CHAT in orch.restarts)
    await orch.create_lobby(-7702, 3, "J3")  # J3 rejoint un autre groupe pendant la pause
    gate.set()
    await wait_until(lambda: CHAT in orch.games)
    nxt = orch.games[CHAT].state
    assert not nxt.has_player("h:3")
    assert [p.id for p in nxt.humans] == ["h:1", "h:2"]
    orch._stop_restart(CHAT)


async def test_default_pause_before_the_new_game_is_sixty_seconds():
    from bot.orchestrator import Orchestrator

    base = make_orchestrator()
    orch = Orchestrator(base.transport, base.repo, base.config, base.trios, base.timeouts)
    assert orch.restart_delay == 60.0
    assert orch.timeouts.solo_wait == 30
