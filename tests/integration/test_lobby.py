from bot import texts
from bot.keyboards import parse_callback
from game.models import Phase
from tests.integration.fakes import FakeTransport, make_orchestrator

CHAT = -1001


async def started(orch, *users):
    for uid, name in users:
        await orch.repo.set_user(str(uid), name, True)


def buttons(markup):
    return [b for row in markup.inline_keyboard for b in row]


def callbacks_of(markup):
    return {b.callback_data.split(":")[0] for b in buttons(markup) if b.callback_data}


async def test_new_creates_lobby_with_buttons():
    orch = make_orchestrator()
    await started(orch, (1, "Alice"))
    await orch.create_lobby(CHAT, 1, "Alice")
    msg = orch.transport.last_group()
    assert "Alice" in msg.text and "✅" in msg.text
    assert callbacks_of(msg.markup) == {"join", "leave", "launch", "cancel", "mode"}
    assert orch.games[CHAT].timer.kind == "lobby"


async def test_second_lobby_in_same_group_refused():
    orch = make_orchestrator()
    await orch.create_lobby(CHAT, 1, "Alice")
    await orch.create_lobby(CHAT, 2, "Bob")
    assert orch.transport.last_group().text == texts.GAME_EXISTS


async def test_join_updates_lobby_live_with_dm_marks():
    orch = make_orchestrator()
    await started(orch, (1, "Alice"))
    await orch.create_lobby(CHAT, 1, "Alice")
    gid = orch.games[CHAT].state.game_id
    await orch.join(CHAT, 2, "Bob", gid)
    edit = orch.transport.edits[-1]
    assert "✅ Alice" in edit.text
    assert "⚠️ Bob" in edit.text
    # lien profond vers le bot pour les joueurs ⚠️
    urls = [b.url for b in buttons(edit.markup) if b.url]
    assert urls == [f"https://t.me/undercover_test_bot?start={gid}"]


async def test_leave_updates_lobby():
    orch = make_orchestrator()
    await started(orch, (1, "Alice"), (2, "Bob"))
    await orch.create_lobby(CHAT, 1, "Alice")
    gid = orch.games[CHAT].state.game_id
    await orch.join(CHAT, 2, "Bob", gid)
    await orch.leave(CHAT, 2, gid)
    assert "Bob" not in orch.transport.edits[-1].text


async def test_launch_blocked_until_everyone_started_the_bot():
    orch = make_orchestrator()
    await started(orch, (1, "Alice"))
    await orch.create_lobby(CHAT, 1, "Alice")
    gid = orch.games[CHAT].state.game_id
    await orch.join(CHAT, 2, "Bob", gid)
    await orch.launch(CHAT, 1, gid)
    assert orch.games[CHAT].state.phase is Phase.LOBBY
    assert "Bob" in orch.transport.last_group().text
    assert "⛔" in orch.transport.last_group().text
    await orch.on_start(2, "Bob", gid)
    assert "✅ Bob" in orch.transport.edits[-1].text
    await orch.launch(CHAT, 1, gid)
    assert orch.games[CHAT].state.phase is Phase.DESCRIPTION


async def test_ninth_player_refused_with_full_message():
    orch = make_orchestrator()
    await started(orch, *[(i, f"J{i}") for i in range(1, 10)])
    await orch.create_lobby(CHAT, 1, "J1")
    gid = orch.games[CHAT].state.game_id
    for i in range(2, 9):
        await orch.join(CHAT, i, f"J{i}", gid)
    await orch.join(CHAT, 9, "J9", gid, callback_id="cb9")
    assert ("cb9", "Partie complète (8 joueurs maximum).", False) in orch.transport.callbacks
    assert len(orch.games[CHAT].state.humans) == 8


async def test_user_cannot_be_in_two_games_across_groups():
    orch = make_orchestrator()
    await orch.create_lobby(CHAT, 1, "Alice")
    await orch.create_lobby(-2002, 2, "Bob")
    gid2 = orch.games[-2002].state.game_id
    await orch.join(-2002, 1, "Alice", gid2, callback_id="cbx")
    assert any(t == texts.ALREADY_IN_GAME for _, t, _ in orch.transport.callbacks)
    assert not orch.games[-2002].state.has_player("h:1")
    # même refus pour un nouveau lobby
    await orch.create_lobby(-3003, 1, "Alice")
    assert orch.transport.last_group().text == texts.ALREADY_IN_GAME


async def test_lobby_expires_after_inactivity():
    orch = make_orchestrator()
    await orch.create_lobby(CHAT, 1, "Alice")
    await orch.fire_timeout(CHAT, "lobby")
    assert CHAT not in orch.games
    assert "expiré" in orch.transport.last_group().text
    assert await orch.repo.user_game("1") is None


async def test_creator_leaving_transfers_role():
    orch = make_orchestrator()
    await orch.create_lobby(CHAT, 1, "Alice")
    gid = orch.games[CHAT].state.game_id
    await orch.join(CHAT, 2, "Bob", gid)
    await orch.leave(CHAT, 1, gid)
    assert orch.games[CHAT].state.creator_id == "h:2"
    assert any("Bob" in t and "créateur" in t for t in orch.transport.group_texts())


async def test_only_creator_can_launch_or_cancel():
    orch = make_orchestrator()
    await started(orch, (1, "Alice"), (2, "Bob"))
    await orch.create_lobby(CHAT, 1, "Alice")
    gid = orch.games[CHAT].state.game_id
    await orch.join(CHAT, 2, "Bob", gid)
    await orch.launch(CHAT, 2, gid, "cb1")
    await orch.cancel(CHAT, 2, gid, "cb2")
    assert [t for _, t, _ in orch.transport.callbacks].count(texts.NOT_CREATOR) == 2
    assert orch.games[CHAT].state.phase is Phase.LOBBY


async def test_cancel_by_creator_ends_lobby():
    orch = make_orchestrator()
    await orch.create_lobby(CHAT, 1, "Alice")
    gid = orch.games[CHAT].state.game_id
    await orch.cancel(CHAT, 1, gid)
    assert CHAT not in orch.games


async def test_stale_lobby_button_gets_discreet_answer():
    orch = make_orchestrator()
    await orch.join(CHAT, 5, "Zoé", "deadbeef", callback_id="cbz")
    assert ("cbz", texts.LOBBY_STALE, False) in orch.transport.callbacks


def test_callback_data_roundtrip_and_limit():
    assert parse_callback("vote:abcd1234:h:123456789") == ("vote", "abcd1234", "h:123456789")
    assert parse_callback("join:abcd1234") == ("join", "abcd1234", None)
    assert parse_callback("bogus:x") is None
    assert len(FakeTransport.__name__) > 0
