"""Messages privés : /start, /aide et /monmot."""

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot import texts
from bot.orchestrator import Orchestrator

router = Router(name="private")
PRIVATE = F.chat.type == ChatType.PRIVATE


@router.message(Command("start"), PRIVATE)
async def cmd_start(message: Message, command: CommandObject, orch: Orchestrator) -> None:
    if message.from_user is None:
        return
    reply = await orch.on_start(message.from_user.id, message.from_user.full_name, command.args)
    await message.answer(reply)


@router.message(Command("aide"), PRIVATE)
async def cmd_help(message: Message) -> None:
    await message.answer(texts.HELP_PRIVATE)


@router.message(Command("aide"))
async def cmd_help_group(message: Message) -> None:
    await message.answer(texts.HELP_GROUP)


@router.message(Command("monmot"), PRIVATE)
async def cmd_my_word(message: Message, orch: Orchestrator) -> None:
    if message.from_user:
        await message.answer(orch.my_word(message.from_user.id))


@router.message(Command("monmot"))
async def cmd_my_word_group(message: Message) -> None:
    await message.answer(texts.PRIVATE_ONLY)
