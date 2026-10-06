"""Point d'entrée : charge la configuration, valide la base de mots, lance le long polling."""

import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from pydantic import ValidationError

from ai.agent import Agent
from ai.groq_client import GroqClient
from bot.config import ConfigError, Settings, load_game_config
from bot.handlers import game, lobby, private
from bot.orchestrator import Orchestrator
from bot.transport import AiogramTransport
from db.repository import SqlRepository
from game.engine import Timeouts
from game.words import WordsError, load_words

ROOT = Path(__file__).resolve().parent.parent
WORDS_FILE = ROOT / "data" / "words.json"
GAME_CONFIG_FILE = ROOT / "data" / "game_config.json"

log = logging.getLogger("undercover")


def fail(message: str) -> None:
    """Arrêt explicite avec un code non nul (FR-057)."""
    print(f"ERREUR : {message}", file=sys.stderr)
    sys.exit(1)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s : %(message)s"
    )
    # Aucune URL de requête ni contenu sensible dans les journaux (principe VIII)
    for noisy in ("httpx", "httpcore", "aiogram.event"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    try:
        settings = Settings()
    except ValidationError as exc:
        fail(f"configuration invalide dans l'environnement ou .env :\n{exc}")
    try:
        trios = load_words(WORDS_FILE)
        game_config = load_game_config(GAME_CONFIG_FILE)
    except (WordsError, ConfigError) as exc:
        fail(str(exc))

    repo = SqlRepository(settings.database_url)
    await repo.init()
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    me = await bot.get_me()
    groq_client = GroqClient(
        settings.groq_api_key,
        settings.groq_model,
        reasoning_effort=settings.groq_reasoning_effort or None,
    )
    await groq_client.check_model()  # signale tout de suite un modèle inaccessible
    orch = Orchestrator(
        transport=AiogramTransport(bot),
        repo=repo,
        config=game_config,
        trios=trios,
        timeouts=Timeouts(
            description=settings.description_timeout,
            vote=settings.vote_timeout,
            lobby=settings.lobby_timeout,
            solo_wait=settings.solo_wait_timeout,
        ),
        restart_delay=settings.restart_delay,
        bot_username=me.username or "undercover_bot",
        ai_driver=Agent(groq_client),
    )
    await orch.resume()

    dp = Dispatcher()
    dp.include_routers(lobby.router, private.router, game.router)
    log.info("Bot @%s démarré (%d trios de mots)", me.username, len(trios))
    try:
        await dp.start_polling(bot, orch=orch, allowed_updates=["message", "callback_query"])
    finally:
        await repo.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
