"""Descriptions, votes et commandes d'information dans le groupe."""

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot import texts
from bot.keyboards import parse_callback
from bot.orchestrator import Orchestrator

router = Router(name="game")
GROUP = F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP})


@router.message(Command("regles"))
async def cmd_rules(message: Message) -> None:
    await message.answer(texts.RULES)


@router.message(Command("etat"), GROUP)
async def cmd_state(message: Message, orch: Orchestrator) -> None:
    await message.answer(orch.state_text(message.chat.id))


@router.message(Command("classement"), GROUP)
async def cmd_leaderboard(message: Message, orch: Orchestrator) -> None:
    await message.answer(await orch.leaderboard_text(message.chat.id))


@router.callback_query(F.data.startswith("vote:"))
async def on_vote(cb: CallbackQuery, orch: Orchestrator) -> None:
    parsed = parse_callback(cb.data or "")
    if parsed is None or parsed[2] is None or cb.message is None:
        await cb.answer()
        return
    _, game_id, target = parsed
    await orch.vote(cb.message.chat.id, cb.from_user.id, game_id, target, cb.id)
    try:
        await cb.answer()
    except TelegramAPIError:
        pass


@router.message(GROUP, F.text, ~F.text.startswith("/"))
async def on_group_text(message: Message, orch: Orchestrator) -> None:
    if message.from_user and message.text:
        await orch.on_group_text(
            message.chat.id, message.from_user.id, message.text, message.message_id
        )
