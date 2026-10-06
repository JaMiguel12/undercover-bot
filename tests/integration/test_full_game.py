from bot.keyboards import parse_callback
from game.models import Phase
from tests.integration.fakes import make_orchestrator, play_out, setup_game

CHAT = -6001


async def start(n=5, seed=1):
    orch = make_orchestrator(seed=seed)
    gid, state = await setup_game(orch, CHAT, n)
    await orch.launch(CHAT, 1, gid)
    return orch, gid, state


async def describe_round(orch, state):
    rnd = state.round
    while state.phase is Phase.DESCRIPTION and state.round == rnd:
        sp = state.current_speaker
        if sp.is_ai:
            await orch.fire_timeout(CHAT, "description")
            continue
        await orch.on_group_text(CHAT, int(sp.id.split(":")[1]), f"indice{state.speaker_index}", 7)


async def test_each_human_receives_their_own_word_in_private():
    orch, gid, state = await start(5)
    for p in state.humans:
        msgs = orch.transport.private[p.id.split(":")[1]]
        assert len(msgs) == 1 and p.word in msgs[0]
    civ = {p.word for p in state.players if p.role.value == "civilian"}
    assert len(civ) == 1


async def test_game_start_announcement_and_timer():
    orch, gid, state = await start(5)
    first = orch.transport.group_texts(CHAT)
    assert any("La partie commence" in t for t in first)
    assert any("Manche 1" in t and "tour 1/3" in t and "Ordre de passage" in t for t in first)
    assert orch.games[CHAT].timer.kind == "description"


async def test_messages_from_other_players_are_ignored():
    orch, gid, state = await start(5)
    speaker = state.current_speaker
    other = next(p for p in state.humans if p.id != speaker.id)
    await orch.on_group_text(CHAT, int(other.id.split(":")[1]), "bonjour tout le monde", 9)
    assert state.descriptions == []


async def test_forbidden_description_is_deleted_and_not_recorded():
    orch, gid, state = await start(5)
    while state.current_speaker.is_ai:
        await orch.fire_timeout(CHAT, "description")
    speaker = state.current_speaker
    await orch.on_group_text(CHAT, int(speaker.id.split(":")[1]), speaker.word, 42)
    assert (CHAT, 42) in orch.transport.deleted
    assert "ne peux pas utiliser ton mot" in orch.transport.last_group().text
    assert speaker.word not in orch.transport.last_group().text
    assert state.current_speaker.id == speaker.id


async def test_recap_then_vote_keyboard_with_one_button_per_alive_player():
    orch, gid, state = await start(5)
    await describe_round(orch, state)
    texts = orch.transport.group_texts(CHAT)
    recap = next(i for i, t in enumerate(texts) if "Récapitulatif" in t)
    vote = next(i for i, t in enumerate(texts) if "Vote !" in t)
    assert recap < vote
    markup = next(m.markup for m in orch.transport.group if "Vote !" in m.text)
    buttons = [b for row in markup.inline_keyboard for b in row]
    assert len(buttons) == len(state.alive) == 8
    for b in buttons:
        action, game_id, target = parse_callback(b.callback_data)
        assert (action, game_id) == ("vote", gid) and state.has_player(target)
    assert len(b.callback_data.encode()) <= 64


async def test_vote_confirmation_is_private_and_result_shows_who_voted_for_whom():
    orch, gid, state = await start(5)
    await describe_round(orch, state)
    humans = [p for p in state.humans]
    target = humans[2].id
    for p in humans:
        if p.id != target:
            await orch.vote(CHAT, int(p.id.split(":")[1]), gid, target, "cbv")
    assert any(t.startswith("Vote enregistré") for _, t, _ in orch.transport.callbacks)
    # les IA (pilote de repli) votent ensuite au hasard
    from tests.integration.fakes import settle

    await settle(orch)
    if state.phase is Phase.VOTE or state.phase is Phase.REVOTE:
        await orch.fire_timeout(CHAT, "vote")
    texts = orch.transport.group_texts(CHAT)
    result = next(t for t in texts if "Résultat du vote" in t)
    assert "→" in result


async def test_elimination_reveals_role_but_not_word():
    orch, gid, state = await start(5)
    await describe_round(orch, state)
    victim = state.humans[0]
    for p in state.humans:
        if p.id != victim.id:
            await orch.vote(CHAT, int(p.id.split(":")[1]), gid, victim.id, "cb")
    from tests.integration.fakes import settle

    await settle(orch)
    if state.alive and victim.alive:
        await orch.fire_timeout(CHAT, "vote")
    elim = [t for t in orch.transport.group_texts(CHAT) if "est éliminé" in t]
    assert elim and "Son rôle" in elim[0]
    assert victim.word not in elim[0]


async def test_complete_game_ends_with_roles_words_and_points():
    for seed in range(8):
        orch = make_orchestrator(seed=seed)
        gid, state = await setup_game(orch, CHAT, 8)
        await orch.launch(CHAT, 1, gid)
        await play_out(orch, CHAT, gid, seed=seed)
        assert state.is_final and CHAT not in orch.games
        if state.phase is Phase.ENDED:
            end = next(t for t in orch.transport.group_texts(CHAT) if "🔓" in t)
            assert "Les rôles" in end and "Points de la partie" in end
            for w in (state.civilian_word, state.undercover_word):
                assert w in end
            return
    raise AssertionError("aucune partie terminée normalement")


async def test_mon_mot_and_state_commands():
    orch, gid, state = await start(5)
    me = state.player("h:1")
    assert me.word in orch.my_word(1)
    assert "manche 1" in orch.state_text(CHAT)
    assert "Aucune partie" in orch.state_text(-1)
    assert "pas de partie" in orch.my_word(999)


async def test_description_turn_timeout_signals_pass():
    orch, gid, state = await start(5)
    while state.current_speaker.is_ai:
        await orch.fire_timeout(CHAT, "description")
    name = state.current_speaker.name
    await orch.fire_timeout(CHAT, "description")
    assert any(f"{name} passe son tour" in t for t in orch.transport.group_texts(CHAT))


async def test_word_dm_failure_is_reported_without_revealing_the_word():
    orch = make_orchestrator(seed=2)
    gid, state = await setup_game(orch, CHAT, 3)
    orch.transport.unreachable.add("2")
    await orch.launch(CHAT, 1, gid)
    warn = [t for t in orch.transport.group_texts(CHAT) if "pas pu écrire" in t]
    assert warn and state.player("h:2").word not in warn[0]
