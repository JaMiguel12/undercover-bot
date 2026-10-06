"""Faux Telegram et faux LLM pour les tests d'intégration (aucun réseau)."""

import asyncio
import random
from dataclasses import dataclass, field
from typing import Any

from bot.config import load_game_config
from bot.orchestrator import Orchestrator
from db.repository import MemoryRepository
from game.engine import Timeouts
from game.models import PublicView
from game.words import load_words


@dataclass
class Sent:
    chat_id: int
    message_id: int
    text: str
    markup: Any = None


@dataclass
class FakeTransport:
    """Enregistre tout ce que le bot envoie, en séparant groupe et privé."""

    group: list[Sent] = field(default_factory=list)
    private: dict[str, list[str]] = field(default_factory=dict)
    edits: list[Sent] = field(default_factory=list)
    deleted: list[tuple[int, int]] = field(default_factory=list)
    typing: list[int] = field(default_factory=list)
    callbacks: list[tuple[str, str, bool]] = field(default_factory=list)
    unreachable: set[str] = field(default_factory=set)  # utilisateurs sans /start
    next_id: int = 100

    async def send_group(self, chat_id: int, text: str, reply_markup: Any = None) -> int:
        self.next_id += 1
        self.group.append(Sent(chat_id, self.next_id, text, reply_markup))
        return self.next_id

    async def edit_group(self, chat_id, message_id, text, reply_markup=None) -> None:
        self.edits.append(Sent(chat_id, message_id, text, reply_markup))

    async def send_private(self, user_id: str, text: str) -> bool:
        if user_id in self.unreachable:
            return False
        self.private.setdefault(user_id, []).append(text)
        return True

    async def delete_message(self, chat_id: int, message_id: int) -> None:
        self.deleted.append((chat_id, message_id))

    async def send_typing(self, chat_id: int) -> None:
        self.typing.append(chat_id)

    async def answer_callback(self, callback_id: str, text: str, alert: bool = False) -> None:
        self.callbacks.append((callback_id, text, alert))

    # --- aides de lecture ---
    def group_texts(self, chat_id: int | None = None) -> list[str]:
        return [m.text for m in self.group if chat_id is None or m.chat_id == chat_id]

    def last_group(self) -> Sent:
        return self.group[-1]


class FakeLLM:
    """Faux pilote d'IA : répond avec des indices fixes, ou lève des erreurs sur demande."""

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.views: list[PublicView] = []
        self.counter = 0

    async def describe(self, view: PublicView) -> str:
        self.views.append(view)
        if self.fail:
            raise RuntimeError("LLM indisponible")
        self.counter += 1
        return f"mot{self.counter}"

    async def vote(self, view: PublicView, rng: random.Random) -> str:
        self.views.append(view)
        if self.fail:
            raise RuntimeError("LLM indisponible")
        return rng.choice([pid for pid, _ in view.alive_players if pid != view.viewer_id])


async def instant_or_hang(seconds: float) -> None:
    """Les attentes nulles (frappe) passent ; les minuteries de partie ne se déclenchent jamais."""
    if seconds == 0:
        await asyncio.sleep(0)
        return
    await asyncio.Event().wait()


def make_orchestrator(
    transport: FakeTransport | None = None,
    repo=None,
    ai_driver=None,
    seed: int = 1,
    **kwargs,
) -> Orchestrator:
    kwargs.setdefault("sleep", instant_or_hang)
    kwargs.setdefault("typing_delay", (0.0, 0.0))
    kwargs.setdefault("ai_timeout", 5.0)
    return Orchestrator(
        transport=transport or FakeTransport(),
        repo=repo or MemoryRepository(),
        config=load_game_config("data/game_config.json"),
        trios=load_words("data/words.json"),
        timeouts=Timeouts(),
        bot_username="undercover_test_bot",
        ai_driver=ai_driver,
        rng=random.Random(seed),
        **kwargs,
    )


async def settle(orch: Orchestrator) -> None:
    """Attend la fin des actions d'IA en cours (elles peuvent en déclencher d'autres)."""
    for _ in range(500):
        tasks = [t for rt in list(orch.games.values()) for t in rt.ai_tasks if not t.done()]
        if not tasks:
            await asyncio.sleep(0)
            tasks = [t for rt in list(orch.games.values()) for t in rt.ai_tasks if not t.done()]
            if not tasks:
                return
        await asyncio.gather(*tasks, return_exceptions=True)


# ---------------------------------------------------------------- parties simulées


async def setup_game(orch: Orchestrator, chat_id: int, n_humans: int, mode: str | None = None):
    """Lobby de n humains qui ont tous démarré le bot ; renvoie (game_id, state)."""
    for uid in range(1, n_humans + 1):
        await orch.repo.set_user(str(uid), f"J{uid}", True)
    await orch.create_lobby(chat_id, 1, "J1")
    gid = orch.games[chat_id].state.game_id
    for uid in range(2, n_humans + 1):
        await orch.join(chat_id, uid, f"J{uid}", gid)
    if mode:
        await orch.set_mode(chat_id, 1, gid, mode)
    return gid, orch.games[chat_id].state


async def play_out(
    orch: Orchestrator,
    chat_id: int,
    gid: str,
    seed: int = 0,
    wrong_words: bool = True,
    max_steps: int = 400,
) -> None:
    """Joue la partie jusqu'au bout avec des humains au comportement aléatoire."""
    rng = random.Random(seed)
    rt = orch.games[chat_id]
    state = rt.state
    msg_id = 5000
    steps = 0
    while chat_id in orch.games and not state.is_final:
        steps += 1
        assert steps < max_steps, "partie sans fin"
        phase = state.phase.value
        if phase == "description":
            speaker = state.current_speaker
            if speaker.is_ai:
                await settle(orch)
                continue
            r = rng.random()
            uid = int(speaker.id.split(":")[1])
            msg_id += 1
            if r < 0.15:
                await orch.fire_timeout(chat_id, "description")
            elif r < 0.30 and wrong_words:
                await orch.on_group_text(chat_id, uid, speaker.word, msg_id)
                await orch.fire_timeout(chat_id, "description")
            else:
                await orch.on_group_text(chat_id, uid, f"indice{steps}", msg_id)
        elif phase in ("vote", "revote"):
            cv = state.current_vote
            for p in list(state.alive):
                if p.is_ai or state.current_vote is not cv:
                    continue
                if rng.random() < 0.1:
                    continue
                options = [c for c in cv.candidates if c != p.id]
                await orch.vote(chat_id, int(p.id.split(":")[1]), gid, rng.choice(options), "cb")
            await settle(orch)
            if state.current_vote is cv and chat_id in orch.games:
                await orch.fire_timeout(chat_id, "vote")
        else:
            await asyncio.sleep(0)
    await settle(orch)
