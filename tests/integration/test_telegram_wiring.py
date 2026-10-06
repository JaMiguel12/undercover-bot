"""Câblage aiogram : routeurs, filtres et transport réels, sans réseau (session factice)."""

from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.enums import ParseMode
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage
from aiogram.types import CallbackQuery, Chat, Message, MessageEntity, Update, User

from bot.handlers import game, lobby, private
from bot.transport import AiogramTransport
from tests.integration.fakes import make_orchestrator

CHAT = -100777


class RecordingSession(BaseSession):
    """Session aiogram qui n'appelle pas Telegram : enregistre les méthodes demandées."""

    def __init__(self):
        super().__init__()
        self.requests: list = []
        self.next_id = 500

    async def close(self) -> None:
        pass

    async def make_request(self, bot, method, timeout=None):
        self.requests.append(method)
        if isinstance(method, SendMessage):
            self.next_id += 1
            return Message(
                message_id=self.next_id,
                date=datetime.now(),
                chat=Chat(id=method.chat_id, type="supergroup"),
                text=method.text,
            )
        return True

    async def stream_content(self, *args, **kwargs):
        yield b""


_DISPATCHER: Dispatcher | None = None


def get_dispatcher() -> Dispatcher:
    """Les routeurs du bot ne peuvent être rattachés qu'une fois : un seul dispatcher partagé."""
    global _DISPATCHER
    if _DISPATCHER is None:
        _DISPATCHER = Dispatcher()
        _DISPATCHER.include_routers(lobby.router, private.router, game.router)
    return _DISPATCHER


def setup():
    session = RecordingSession()
    bot = Bot(
        "123456:ABCDEF", session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    orch = make_orchestrator()
    orch.transport = AiogramTransport(bot)
    return bot, orch, get_dispatcher(), session


def command_update(text, chat_id=CHAT, chat_type="supergroup", user_id=1, name="Alice", uid=1):
    entity = MessageEntity(type="bot_command", offset=0, length=len(text.split()[0]))
    return Update(
        update_id=uid,
        message=Message(
            message_id=uid,
            date=datetime.now(),
            chat=Chat(id=chat_id, type=chat_type),
            from_user=User(id=user_id, is_bot=False, first_name=name),
            text=text,
            entities=[entity] if text.startswith("/") else None,
        ),
    )


def button_update(data, user_id=2, name="Bob", uid=100, message_id=501):
    return Update(
        update_id=uid,
        callback_query=CallbackQuery(
            id=f"cb{uid}",
            from_user=User(id=user_id, is_bot=False, first_name=name),
            chat_instance="x",
            data=data,
            message=Message(
                message_id=message_id,
                date=datetime.now(),
                chat=Chat(id=CHAT, type="supergroup"),
            ),
        ),
    )


async def test_nouvelle_creates_a_lobby_with_buttons():
    bot, orch, dp, session = setup()
    await dp.feed_update(bot, command_update("/nouvelle"), orch=orch)
    sent = [m for m in session.requests if isinstance(m, SendMessage)]
    assert sent and "nouvelle partie" in sent[0].text
    labels = [b.text for row in sent[0].reply_markup.inline_keyboard for b in row]
    assert {"✅ Rejoindre", "🚪 Quitter", "🚀 Lancer", "❌ Annuler"} <= set(labels)


async def test_join_button_updates_the_lobby_message():
    bot, orch, dp, session = setup()
    await dp.feed_update(bot, command_update("/nouvelle"), orch=orch)
    gid = orch.games[CHAT].state.game_id
    await dp.feed_update(bot, button_update(f"join:{gid}"), orch=orch)
    edits = [m for m in session.requests if isinstance(m, EditMessageText)]
    assert edits and "Bob" in edits[-1].text
    assert any(isinstance(m, AnswerCallbackQuery) for m in session.requests)


async def test_regles_and_aide_commands_answer():
    bot, orch, dp, session = setup()
    await dp.feed_update(bot, command_update("/regles"), orch=orch)
    await dp.feed_update(
        bot, command_update("/aide", chat_id=5, chat_type="private", uid=2), orch=orch
    )
    texts = [m.text for m in session.requests if isinstance(m, SendMessage)]
    assert any("Règles d'Undercover" in t for t in texts)
    assert any("/monmot" in t for t in texts)


async def test_start_in_private_marks_the_user_as_reachable():
    bot, orch, dp, session = setup()
    await dp.feed_update(
        bot, command_update("/start", chat_id=2, chat_type="private", user_id=2, uid=3), orch=orch
    )
    assert await orch.repo.get_can_dm("2") is True


async def test_classement_and_etat_without_game():
    bot, orch, dp, session = setup()
    await dp.feed_update(bot, command_update("/classement"), orch=orch)
    await dp.feed_update(bot, command_update("/etat", uid=2), orch=orch)
    texts = [m.text for m in session.requests if isinstance(m, SendMessage)]
    assert any("Aucun score" in t for t in texts)
    assert any("Aucune partie" in t for t in texts)


async def test_group_text_from_a_non_speaker_is_ignored_and_private_free_text_too():
    bot, orch, dp, session = setup()
    await dp.feed_update(bot, command_update("bonjour tout le monde", uid=4), orch=orch)
    await dp.feed_update(
        bot, command_update("coucou", chat_id=2, chat_type="private", user_id=2, uid=5), orch=orch
    )
    assert [m for m in session.requests if isinstance(m, SendMessage)] == []
