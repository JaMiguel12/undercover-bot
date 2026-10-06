"""Commandes et boutons du lobby (groupe)."""

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot import texts
from bot.keyboards import parse_callback
from bot.orchestrator import Orchestrator

router = Router(name="lobby")
GROUP = F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP})


@router.message(Command("nouvelle"))
async def cmd_new(message: Message, orch: Orchestrator) -> None:
    if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP) or message.from_user is None:
        await message.answer(texts.GROUP_ONLY)
        return
    await orch.create_lobby(message.chat.id, message.from_user.id, message.from_user.full_name)


@router.message(Command("lancer"), GROUP)
async def cmd_launch(message: Message, orch: Orchestrator) -> None:
    if message.from_user:
        await orch.launch(message.chat.id, message.from_user.id, None)


@router.message(Command("annuler"), GROUP)
async def cmd_cancel(message: Message, orch: Orchestrator) -> None:
    if message.from_user:
        await orch.cancel(message.chat.id, message.from_user.id, None)


@router.callback_query(F.data.startswith(("join:", "leave:", "launch:", "cancel:", "mode:")))
async def on_lobby_button(cb: CallbackQuery, orch: Orchestrator) -> None:
    parsed = parse_callback(cb.data or "")
    if parsed is None or cb.message is None:
        await cb.answer()
        return
    action, game_id, argument = parsed
    chat_id, user = cb.message.chat.id, cb.from_user
    if action == "join":
        await orch.join(chat_id, user.id, user.full_name, game_id, cb.id)
    elif action == "leave":
        await orch.leave(chat_id, user.id, game_id, cb.id)
    elif action == "launch":
        await orch.launch(chat_id, user.id, game_id, cb.id)
    elif action == "cancel":
        await orch.cancel(chat_id, user.id, game_id, cb.id)
    elif action == "mode" and argument:
        await orch.set_mode(chat_id, user.id, game_id, argument, cb.id)
    try:
        await cb.answer()  # sans effet si l'orchestrateur a déjà répondu
    except TelegramAPIError:
        pass
