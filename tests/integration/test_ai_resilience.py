import asyncio
import re

import pytest

from game.models import Phase
from tests.integration.fakes import FakeLLM, make_orchestrator, play_out, settle, setup_game

CHAT = -8101
AI_PREFIX = "🤖"


@pytest.mark.parametrize("seed", range(10))
async def test_game_completes_when_the_llm_is_down(seed):
    orch = make_orchestrator(ai_driver=FakeLLM(fail=True), seed=seed)
    gid, state = await setup_game(orch, CHAT, 1 + seed % 4)
    await orch.launch(CHAT, 1, gid)
    if state.solo_waiting:
        await orch.fire_timeout(CHAT, "solo_wait")
    await play_out(orch, CHAT, gid, seed=seed)
    assert state.phase in (Phase.ENDED, Phase.CANCELLED)
    assert CHAT not in orch.games


async def test_ai_passes_and_votes_randomly_without_llm_even_alone():
    orch = make_orchestrator(ai_driver=FakeLLM(fail=True), seed=5)
    gid, state = await setup_game(orch, CHAT, 1)
    await orch.launch(CHAT, 1, gid)
    await orch.fire_timeout(CHAT, "solo_wait")
    await play_out(orch, CHAT, gid, seed=5)
    texts = orch.transport.group_texts(CHAT)
    assert any("Je passe mon tour 🤐" in t for t in texts)
    assert state.is_final


async def test_every_ai_message_has_the_robot_prefix():
    orch = make_orchestrator(ai_driver=FakeLLM(), seed=3)
    gid, state = await setup_game(orch, CHAT, 2)
    await orch.launch(CHAT, 1, gid)
    await play_out(orch, CHAT, gid, seed=3)
    pattern = re.compile(r"^(\S+ )?(Zendaya IA|Kendall IA|BFF Diva IA) : ")
    spoken = [t for t in orch.transport.group_texts(CHAT) if pattern.match(t)]
    assert spoken
    for t in spoken:
        assert t.startswith(AI_PREFIX + " "), t


async def test_typing_indicator_before_each_ai_description():
    llm = FakeLLM()
    orch = make_orchestrator(ai_driver=llm, seed=4)
    gid, state = await setup_game(orch, CHAT, 2)
    await orch.launch(CHAT, 1, gid)
    await play_out(orch, CHAT, gid, seed=4)
    ai_descriptions = [t for t in orch.transport.group_texts(CHAT) if t.startswith(AI_PREFIX)]
    assert ai_descriptions
    assert len(orch.transport.typing) >= len([t for t in ai_descriptions if "Je passe" not in t])


async def test_typing_delay_is_between_two_and_five_seconds_by_default():
    from bot.orchestrator import Orchestrator

    orch = make_orchestrator()
    assert Orchestrator(
        orch.transport, orch.repo, orch.config, orch.trios, orch.timeouts
    ).typing_delay == (2.0, 5.0)


async def test_ai_votes_are_silent_ballots_only():
    orch = make_orchestrator(ai_driver=FakeLLM(), seed=6)
    gid, state = await setup_game(orch, CHAT, 2)
    await orch.launch(CHAT, 1, gid)
    await play_out(orch, CHAT, gid, seed=6)
    for t in orch.transport.group_texts(CHAT):
        assert not (t.startswith(AI_PREFIX) and "vote" in t.lower().split(":")[0])


async def test_ai_can_play_in_several_groups_in_parallel():
    llm = FakeLLM()
    orch = make_orchestrator(ai_driver=llm, seed=7)
    chats = [-8201, -8202]
    gids = {}
    for i, chat in enumerate(chats):
        base = 10 * (i + 1)
        for uid in (base + 1, base + 2):
            await orch.repo.set_user(str(uid), f"J{uid}", True)
        await orch.create_lobby(chat, base + 1, f"J{base + 1}")
        gids[chat] = orch.games[chat].state.game_id
        await orch.join(chat, base + 2, f"J{base + 2}", gids[chat])
        await orch.launch(chat, base + 1, gids[chat])
    both = [orch.games[c].state for c in chats]
    assert all(s.phase is Phase.DESCRIPTION for s in both)
    assert [p.name for p in both[0].players if p.is_ai] == [
        p.name for p in both[1].players if p.is_ai
    ]
    await asyncio.gather(
        play_out(orch, chats[0], gids[chats[0]], seed=1),
        play_out(orch, chats[1], gids[chats[1]], seed=2),
    )
    assert all(s.is_final for s in both)


async def test_ai_hanging_forever_does_not_block_the_game():
    class HangingLLM(FakeLLM):
        async def describe(self, view):
            await asyncio.sleep(3600)

    orch = make_orchestrator(ai_driver=HangingLLM(), seed=8)
    orch.ai_timeout = 0.05
    gid, state = await setup_game(orch, CHAT, 2)
    await orch.launch(CHAT, 1, gid)
    await play_out(orch, CHAT, gid, seed=8)
    assert state.is_final


async def test_stale_ai_result_is_ignored_after_timeout():
    """Si le délai de description expire pendant l'appel, la réponse tardive ne fait rien."""
    gate = asyncio.Event()

    class SlowLLM(FakeLLM):
        async def describe(self, view):
            await gate.wait()
            return "trop tard"

    orch = make_orchestrator(ai_driver=SlowLLM(), seed=9)
    gid, state = await setup_game(orch, CHAT, 2)
    await orch.launch(CHAT, 1, gid)
    while state.current_speaker.is_ai is False:
        await orch.on_group_text(CHAT, int(state.current_speaker.id.split(":")[1]), "indice", 1)
    await asyncio.sleep(0)
    speaker = state.current_speaker
    await orch.fire_timeout(CHAT, "description")  # l'IA passe son tour par expiration
    gate.set()
    await settle(orch)
    assert not any(d.text == "trop tard" and d.player_id == speaker.id for d in state.descriptions)


class WordLLM:
    """Client LLM scripté pour l'agent réel : un mot différent à chaque appel, vote au hasard."""

    def __init__(self):
        self.n = 0
        self.prompts = []

    async def complete_json(self, system, user, temperature=0.7):
        self.prompts.append(user)
        if "À TOI DE VOTER" in user:
            return '{"vote": "J1"}'
        self.n += 1
        return f'{{"description": "mot{self.n}"}}'


async def test_real_agent_describes_in_all_three_rounds_with_a_growing_history():
    """Régression : l'agent réel (pas un faux pilote) doit jouer ses 3 tours sans repli."""
    from ai.agent import Agent

    llm = WordLLM()
    orch = make_orchestrator(ai_driver=Agent(llm), seed=12)
    gid, state = await setup_game(orch, CHAT, 2)
    await orch.launch(CHAT, 1, gid)
    await play_out(orch, CHAT, gid, seed=12, wrong_words=False)
    ai_ids = {p.id for p in state.players if p.is_ai}
    ai_words = [d for d in state.descriptions if d.player_id in ai_ids]
    assert ai_words and not any(d.skipped for d in ai_words)  # aucun « passe son tour »
    assert {d.sub_round for d in ai_words} == {1, 2, 3}
    describe_prompts = [p for p in llm.prompts if "dis UN SEUL MOT" in p]
    assert any("Mots dits jusqu'ici" in p for p in describe_prompts)  # historique transmis
