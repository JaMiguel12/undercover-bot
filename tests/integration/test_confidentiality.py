"""Confidentialité (principe III, FR-043) : aucun mot secret dans le groupe avant l'écran de fin."""

import pytest

from game.normalize import normalize
from tests.integration.fakes import FakeLLM, make_orchestrator, play_out, setup_game

CHAT = -5001


def leaks(text: str, words: set[str]) -> list[str]:
    """Mots secrets présents (mots entiers, comparaison normalisée) dans un texte."""
    padded = f" {normalize(text)} "
    return [w for w in words if f" {normalize(w)} " in padded]


@pytest.mark.parametrize("humans", [2, 5, 8])
@pytest.mark.parametrize("seed", range(12))
async def test_no_secret_word_in_group_before_end_screen(humans, seed):
    orch = make_orchestrator(seed=seed)
    gid, state = await setup_game(orch, CHAT, humans)
    await orch.launch(CHAT, 1, gid)
    words = {state.civilian_word, state.undercover_word}
    assert len(words) == 2
    await play_out(orch, CHAT, gid, seed=seed)
    group = orch.transport.group_texts(CHAT)
    end_index = next((i for i, t in enumerate(group) if "🔓" in t), None)
    before_end = group if end_index is None else group[:end_index]
    for text in before_end:
        assert leaks(text, words) == [], text
    # les éditions du lobby ne contiennent pas non plus de mot secret
    for edit in orch.transport.edits:
        assert leaks(edit.text, words) == []


@pytest.mark.parametrize("seed", range(5))
async def test_no_secret_word_with_ai_players(seed):
    orch = make_orchestrator(ai_driver=FakeLLM(), seed=seed)
    gid, state = await setup_game(orch, CHAT, 3)
    await orch.launch(CHAT, 1, gid)
    words = {state.civilian_word, state.undercover_word}
    await play_out(orch, CHAT, gid, seed=seed)
    group = orch.transport.group_texts(CHAT)
    end_index = next((i for i, t in enumerate(group) if "🔓" in t), None)
    for text in group if end_index is None else group[:end_index]:
        assert leaks(text, words) == [], text


async def test_words_are_revealed_on_the_end_screen_only():
    orch = make_orchestrator(seed=3)
    gid, state = await setup_game(orch, CHAT, 5)
    await orch.launch(CHAT, 1, gid)
    words = {state.civilian_word, state.undercover_word}
    await play_out(orch, CHAT, gid, seed=3, wrong_words=False)
    end = [t for t in orch.transport.group_texts(CHAT) if "🔓" in t]
    if end:  # partie terminée normalement (et non annulée)
        assert all(leaks(end[0], {w}) for w in words)
