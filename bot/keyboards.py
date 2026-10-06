"""Claviers en ligne et données de rappel (contrat : contracts/callback-data.md).

Format des données : `<action>:<game_id>[:<argument>]`, 64 octets maximum.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.texts import MODE_LABELS
from game.models import GameMode, GameState

ACTIONS = ("join", "leave", "launch", "cancel", "vote", "mode")


def callback_data(action: str, game_id: str, argument: str | None = None) -> str:
    data = f"{action}:{game_id}" + (f":{argument}" if argument else "")
    assert len(data.encode()) <= 64, "données de rappel trop longues"
    return data


def parse_callback(data: str) -> tuple[str, str, str | None] | None:
    """Renvoie (action, game_id, argument) ou None si le format est inconnu."""
    parts = data.split(":", 2)
    if len(parts) < 2 or parts[0] not in ACTIONS or not parts[1]:
        return None
    return parts[0], parts[1], parts[2] if len(parts) == 3 else None


def deep_link(bot_username: str, game_id: str) -> str:
    return f"https://t.me/{bot_username}?start={game_id}"


def lobby_keyboard(state: GameState, bot_username: str) -> InlineKeyboardMarkup:
    gid = state.game_id
    # choix du type de partie par le créateur : la sélection courante est cochée
    mode_row = [
        InlineKeyboardButton(
            text=("✔ " if state.mode is mode else "") + MODE_LABELS[mode.value],
            callback_data=callback_data("mode", gid, mode.value),
        )
        for mode in GameMode
    ]
    rows = [
        mode_row,
        [
            InlineKeyboardButton(text="✅ Rejoindre", callback_data=callback_data("join", gid)),
            InlineKeyboardButton(text="🚪 Quitter", callback_data=callback_data("leave", gid)),
        ],
        [
            InlineKeyboardButton(text="🚀 Lancer", callback_data=callback_data("launch", gid)),
            InlineKeyboardButton(text="❌ Annuler", callback_data=callback_data("cancel", gid)),
        ],
    ]
    if any(not p.can_dm for p in state.humans):
        rows.append(
            [InlineKeyboardButton(text="🤖 Démarrer le bot", url=deep_link(bot_username, gid))]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def vote_keyboard(game_id: str, candidates: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """Un bouton par joueur vivant (FR-027)."""
    rows = [
        [InlineKeyboardButton(text=name, callback_data=callback_data("vote", game_id, pid))]
        for pid, name in candidates
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
