"""Principe VIII et III : ni secret ni mot secret dans les journaux."""

import logging

from tests.integration.fakes import FakeTransport, make_orchestrator, setup_game

CHAT = -3301


class FailingTransport(FakeTransport):
    async def send_private(self, user_id, text):
        raise RuntimeError("Telegram est tombé")

    async def send_group(self, chat_id, text, reply_markup=None):
        if "commence" in text:
            raise RuntimeError("Telegram est tombé")
        return await super().send_group(chat_id, text, reply_markup)


async def test_effect_failures_are_logged_without_secret_words(caplog):
    caplog.set_level(logging.DEBUG)
    orch = make_orchestrator(transport=FailingTransport(), seed=4)
    gid, state = await setup_game(orch, CHAT, 3)
    await orch.launch(CHAT, 1, gid)
    words = {state.civilian_word, state.undercover_word}
    assert state.phase.value == "description"  # une panne Telegram ne fige pas la partie
    assert "Échec de l'effet" in caplog.text
    for word in words:
        assert word not in caplog.text
