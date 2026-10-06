"""Transport Telegram réel (aiogram) : implémente l'interface attendue par l'orchestrateur."""

import asyncio
import logging
from typing import Any

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)

log = logging.getLogger(__name__)


class AiogramTransport:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def _retry(self, make_call):
        """Un nouvel essai après une limite de débit de Telegram."""
        try:
            return await make_call()
        except TelegramRetryAfter as exc:
            await asyncio.sleep(min(exc.retry_after, 30))
            return await make_call()

    async def send_group(self, chat_id: int, text: str, reply_markup: Any = None) -> int:
        msg = await self._retry(
            lambda: self.bot.send_message(chat_id, text, reply_markup=reply_markup)
        )
        return msg.message_id

    async def edit_group(
        self, chat_id: int, message_id: int, text: str, reply_markup: Any = None
    ) -> None:
        try:
            await self._retry(
                lambda: self.bot.edit_message_text(
                    text, chat_id=chat_id, message_id=message_id, reply_markup=reply_markup
                )
            )
        except TelegramBadRequest as exc:
            if "not modified" not in str(exc):
                raise

    async def send_private(self, user_id: str, text: str) -> bool:
        try:
            await self._retry(lambda: self.bot.send_message(int(user_id), text))
            return True
        except (TelegramForbiddenError, TelegramBadRequest):
            return False  # le joueur n'a jamais démarré le bot, ou l'a bloqué

    async def delete_message(self, chat_id: int, message_id: int) -> None:
        try:
            await self.bot.delete_message(chat_id, message_id)
        except TelegramAPIError:
            log.info("Suppression impossible (le bot n'est probablement pas administrateur)")

    async def send_typing(self, chat_id: int) -> None:
        await self.bot.send_chat_action(chat_id, "typing")

    async def answer_callback(self, callback_id: str, text: str, alert: bool = False) -> None:
        await self.bot.answer_callback_query(callback_id, text=text, show_alert=alert)
