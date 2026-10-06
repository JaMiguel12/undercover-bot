"""Orchestrateur : relie le moteur pur, Telegram, les agents IA, la persistance et les minuteries.

Un verrou asyncio par partie sérialise tous les événements d'une même partie (clic, message,
expiration de délai, réponse d'IA). Les appels aux IA se font hors du verrou.
"""

import asyncio
import logging
import random
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from bot import texts
from bot.keyboards import lobby_keyboard, vote_keyboard
from db.repository import Repository, StoredGame
from game import engine
from game.engine import EngineContext, Timeouts
from game.models import (
    Cancel,
    CancelTimer,
    CastVote,
    DeleteMessage,
    Describe,
    Effect,
    Event,
    GameMode,
    GameState,
    Join,
    Launch,
    Leave,
    Notify,
    Outcome,
    PassTurn,
    Phase,
    Player,
    PublicView,
    RecordScores,
    RequestAIAction,
    SendGroup,
    SendPrivate,
    SetCanDm,
    SetMode,
    StartTimer,
    TrioPlayed,
    UpdateLobby,
    WordTrio,
)
from game.rules import GameConfig

log = logging.getLogger(__name__)

SOLO_TICK = 10.0  # secondes entre deux mises à jour du compte à rebours solo


class Transport(Protocol):
    """Ce que l'orchestrateur attend de Telegram (remplaçable par un faux dans les tests)."""

    async def send_group(self, chat_id: int, text: str, reply_markup: Any = None) -> int: ...

    async def edit_group(
        self, chat_id: int, message_id: int, text: str, reply_markup: Any = None
    ) -> None: ...

    async def send_private(self, user_id: str, text: str) -> bool: ...

    async def delete_message(self, chat_id: int, message_id: int) -> None: ...

    async def send_typing(self, chat_id: int) -> None: ...

    async def answer_callback(self, callback_id: str, text: str, alert: bool = False) -> None: ...


class AIDriver(Protocol):
    """Les trois actions d'une IA ; aucune ne lève d'exception (FR-055)."""

    async def describe(self, view: PublicView) -> str: ...

    async def vote(self, view: PublicView, rng: random.Random) -> str: ...


class FallbackAIDriver:
    """Pilote IA sans LLM : passe son tour et vote au hasard."""

    async def describe(self, view: PublicView) -> str:
        return texts.AI_PASS_TEXT

    async def vote(self, view: PublicView, rng: random.Random) -> str:
        options = [pid for pid, _ in view.alive_players if pid != view.viewer_id]
        return rng.choice(options)


@dataclass
class RestartInfo:
    """Nouvelle partie automatique en attente (mode sans élimination)."""

    creator_id: str
    task: asyncio.Task | None = None


@dataclass
class TimerInfo:
    kind: str
    deadline: datetime
    task: asyncio.Task | None = None


@dataclass
class Runtime:
    state: GameState
    lobby_message_id: int | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    timer: TimerInfo | None = None
    ai_tasks: set[asyncio.Task] = field(default_factory=set)
    ai_pending: set[tuple[str, str]] = field(default_factory=set)  # (joueur, action) en cours


def _now() -> datetime:
    return datetime.now(UTC)


def _user_of(player_id: str) -> str:
    return player_id.split(":", 1)[1]


class Orchestrator:
    def __init__(
        self,
        transport: Transport,
        repo: Repository,
        config: GameConfig,
        trios: list[WordTrio],
        timeouts: Timeouts,
        bot_username: str = "undercover_bot",
        ai_driver: AIDriver | None = None,
        rng: random.Random | None = None,
        clock: Callable[[], datetime] = _now,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        typing_delay: tuple[float, float] = (2.0, 5.0),
        ai_timeout: float = 45.0,
        restart_delay: float = 60.0,
    ) -> None:
        self.transport = transport
        self.repo = repo
        self.config = config
        self.trios = trios
        self.timeouts = timeouts
        self.bot_username = bot_username
        self.ai_driver: AIDriver = ai_driver or FallbackAIDriver()
        self.rng = rng or random.Random()
        self.clock = clock
        self.sleep = sleep
        self.typing_delay = typing_delay
        self.ai_timeout = ai_timeout
        self.games: dict[int, Runtime] = {}
        self.restart_delay = restart_delay
        self.restarts: dict[int, RestartInfo] = {}  # série automatique en attente par groupe

    # ------------------------------------------------------------ lobby et commandes

    async def create_lobby(self, chat_id: int, user_id: int, name: str) -> None:
        if chat_id in self.games:
            await self.transport.send_group(chat_id, texts.GAME_EXISTS)
            return
        if chat_id in self.restarts:
            await self.transport.send_group(chat_id, texts.RESTART_PENDING)
            return
        if await self.repo.user_game(str(user_id)):
            await self.transport.send_group(chat_id, texts.ALREADY_IN_GAME)
            return
        can_dm = await self.repo.get_can_dm(str(user_id))
        game_id = uuid.UUID(int=self.rng.getrandbits(128)).hex[:8]
        state = engine.create_lobby(
            game_id, chat_id, f"h:{user_id}", name, can_dm, self.rng.getrandbits(31)
        )
        rt = Runtime(state)
        self.games[chat_id] = rt
        async with rt.lock:
            rt.lobby_message_id = await self.transport.send_group(
                chat_id, texts.render_lobby(state), lobby_keyboard(state, self.bot_username)
            )
            self._start_timer(rt, "lobby", self.timeouts.lobby)
            await self._persist(rt)

    async def join(
        self, chat_id: int, user_id: int, name: str, game_id: str, callback_id: str | None = None
    ) -> None:
        rt = self.games.get(chat_id)
        if rt is None or rt.state.game_id != game_id:
            await self._answer(callback_id, texts.LOBBY_STALE)
            return
        other = await self.repo.user_game(str(user_id))
        if other is not None and other != rt.state.game_id:
            await self._answer(callback_id, texts.ALREADY_IN_GAME, alert=True)
            return
        can_dm = await self.repo.get_can_dm(str(user_id))
        await self.dispatch(chat_id, Join(f"h:{user_id}", name, can_dm), game_id, callback_id)

    async def leave(self, chat_id: int, user_id: int, game_id: str, callback_id: str | None = None):
        await self.dispatch(chat_id, Leave(f"h:{user_id}"), game_id, callback_id)

    async def launch(self, chat_id: int, user_id: int, game_id: str | None, cb: str | None = None):
        await self.dispatch(chat_id, Launch(f"h:{user_id}"), game_id, cb)

    async def cancel(self, chat_id: int, user_id: int, game_id: str | None, cb: str | None = None):
        pending = self.restarts.get(chat_id)
        if pending is not None and chat_id not in self.games:
            if pending.creator_id != f"h:{user_id}":
                await self._answer(cb, texts.NOT_CREATOR)
                return
            self._stop_restart(chat_id)
            await self.transport.send_group(chat_id, texts.SERIES_STOPPED)
            return
        await self.dispatch(chat_id, Cancel(f"h:{user_id}"), game_id, cb)

    async def set_mode(
        self, chat_id: int, user_id: int, game_id: str, mode: str, cb: str | None = None
    ) -> None:
        try:
            chosen = GameMode(mode)
        except ValueError:
            await self._answer(cb, texts.LOBBY_STALE)
            return
        await self.dispatch(chat_id, SetMode(f"h:{user_id}", chosen), game_id, cb)

    async def vote(self, chat_id: int, user_id: int, game_id: str, target_id: str, cb: str | None):
        await self.dispatch(chat_id, CastVote(f"h:{user_id}", target_id), game_id, cb)

    async def on_group_text(self, chat_id: int, user_id: int, text: str, message_id: int) -> None:
        rt = self.games.get(chat_id)
        if rt is None or rt.state.phase is not Phase.DESCRIPTION:
            return
        speaker = rt.state.current_speaker
        if speaker is None or speaker.id != f"h:{user_id}":
            return  # les autres messages sont ignorés : on peut discuter librement
        await self.dispatch(chat_id, Describe(speaker.id, text), source_message_id=message_id)

    async def on_start(self, user_id: int, name: str, payload: str | None = None) -> str:
        """/start en privé : le joueur peut désormais recevoir ses mots."""
        await self.repo.set_user(str(user_id), name, True)
        for chat_id, rt in list(self.games.items()):
            if rt.state.has_player(f"h:{user_id}"):
                await self.dispatch(chat_id, SetCanDm(f"h:{user_id}", True))
        return texts.START_DEEP_LINK if payload else texts.START_OK

    def my_word(self, user_id: int) -> str:
        for rt in self.games.values():
            pid = f"h:{user_id}"
            if rt.state.has_player(pid) and rt.state.phase is not Phase.LOBBY:
                word = rt.state.player(pid).word
                if word:
                    return texts.my_word_text(word)
        return texts.NO_ACTIVE_GAME_PRIVATE

    async def leaderboard_text(self, chat_id: int) -> str:
        rows = await self.repo.leaderboard(chat_id)
        return texts.render_leaderboard(rows) if rows else texts.NO_SCORES

    def state_text(self, chat_id: int) -> str:
        rt = self.games.get(chat_id)
        return texts.state_text(rt.state) if rt else texts.NO_GAME

    # ------------------------------------------------------------ cœur : événements

    async def dispatch(
        self,
        chat_id: int,
        event: Event,
        game_id: str | None = None,
        callback_id: str | None = None,
        source_message_id: int | None = None,
    ) -> None:
        rt = self.games.get(chat_id)
        if rt is None or (game_id is not None and rt.state.game_id != game_id):
            await self._answer(callback_id, texts.LOBBY_STALE)
            return
        async with rt.lock:
            if rt.state.is_final or self.games.get(chat_id) is not rt:
                await self._answer(callback_id, texts.VOTE_ENDED)
                return
            await self._apply(rt, event, callback_id, source_message_id)

    async def fire_timeout(self, chat_id: int, kind: str) -> None:
        from game.models import Timeout

        await self.dispatch(chat_id, Timeout(kind))

    async def _apply(
        self, rt: Runtime, event: Event, callback_id: str | None, source_message_id: int | None
    ) -> None:
        state = rt.state
        ctx = EngineContext(
            rng=self.rng,
            config=self.config,
            trios=self.trios,
            played_ids=await self.repo.played_trios(state.chat_id),
            timeouts=self.timeouts,
        )
        effects = engine.apply(state, event, ctx)
        await self._run_effects(rt, effects, callback_id, source_message_id)
        await self._persist(rt)
        if state.is_final:
            self._finish(rt)
            self._schedule_restart(state)

    # ------------------------------------------------------------ effets

    async def _run_effects(
        self, rt: Runtime, effects: list[Effect], callback_id: str | None, source_id: int | None
    ) -> None:
        for effect in effects:
            try:
                await self._run_effect(rt, effect, callback_id, source_id)
            except Exception:  # une panne Telegram ne doit pas figer la partie
                log.exception("Échec de l'effet %s", type(effect).__name__)  # sans les mots secrets

    async def _run_effect(
        self, rt: Runtime, effect: Effect, callback_id: str | None, source_id: int | None
    ) -> None:
        state = rt.state
        chat_id = state.chat_id
        if isinstance(effect, SendGroup):
            markup = None
            if effect.key == "vote_open":
                markup = vote_keyboard(state.game_id, effect.params["candidates"])
            await self.transport.send_group(
                chat_id, texts.group_text(effect.key, effect.params), markup
            )
        elif isinstance(effect, SendPrivate):
            ok = await self.transport.send_private(
                _user_of(effect.player_id), texts.private_text(effect.key, effect.params)
            )
            if not ok and effect.key == "your_word":
                name = state.player(effect.player_id).name
                await self.transport.send_group(chat_id, texts.word_dm_failed(name))
        elif isinstance(effect, Notify):
            await self._answer(callback_id, texts.notify_text(effect.key, effect.params))
        elif isinstance(effect, DeleteMessage):
            if source_id is not None:
                await self.transport.delete_message(chat_id, source_id)
        elif isinstance(effect, RequestAIAction):
            self._spawn_ai(rt, effect.player_id, effect.kind)
        elif isinstance(effect, StartTimer):
            self._start_timer(rt, effect.kind, effect.seconds)
        elif isinstance(effect, CancelTimer):
            self._cancel_timer(rt, effect.kind)
        elif isinstance(effect, UpdateLobby):
            await self._refresh_lobby(rt)
        elif isinstance(effect, TrioPlayed):
            await self.repo.add_played_trio(chat_id, effect.trio_id, effect.cycle_restarted)
        elif isinstance(effect, RecordScores):
            await self.repo.add_scores(chat_id, effect.points, effect.players)

    async def _refresh_lobby(self, rt: Runtime, solo_remaining: int | None = None) -> None:
        if rt.lobby_message_id is None or rt.state.phase is not Phase.LOBBY:
            return
        await self.transport.edit_group(
            rt.state.chat_id,
            rt.lobby_message_id,
            texts.render_lobby(rt.state, solo_remaining),
            lobby_keyboard(rt.state, self.bot_username),
        )

    async def _answer(self, callback_id: str | None, text: str, alert: bool = False) -> None:
        if callback_id and text:
            try:
                await self.transport.answer_callback(callback_id, text, alert)
            except Exception:
                log.exception("Échec de la réponse au bouton")

    async def _persist(self, rt: Runtime) -> None:
        timer = rt.timer
        await self.repo.save_game(
            StoredGame(
                rt.state,
                timer.kind if timer else None,
                timer.deadline if timer else None,
                rt.lobby_message_id,
            )
        )

    def _finish(self, rt: Runtime) -> None:
        self._cancel_timer(rt)
        for task in list(rt.ai_tasks):
            if task is not asyncio.current_task():
                task.cancel()
        if self.games.get(rt.state.chat_id) is rt:
            del self.games[rt.state.chat_id]

    # ------------------------------------------------------------ minuteries

    def _start_timer(
        self, rt: Runtime, kind: str, seconds: float, deadline: datetime | None = None
    ):
        self._cancel_timer(rt)
        deadline = deadline or self.clock() + timedelta(seconds=seconds)
        info = TimerInfo(kind, deadline)
        rt.timer = info
        info.task = asyncio.create_task(self._timer_task(rt, info, seconds))

    def _cancel_timer(self, rt: Runtime, kind: str | None = None) -> None:
        info = rt.timer
        if info is None or (kind is not None and info.kind != kind):
            return
        rt.timer = None
        if info.task is not None and info.task is not asyncio.current_task():
            info.task.cancel()

    async def _timer_task(self, rt: Runtime, info: TimerInfo, seconds: float) -> None:
        try:
            if info.kind == "solo_wait":
                await self._solo_countdown(rt, seconds)
            else:
                await self.sleep(max(0.0, seconds))
        except asyncio.CancelledError:
            return
        if rt.timer is info:
            rt.timer = None  # évite que l'événement ne s'annule lui-même
        try:
            await self.fire_timeout(rt.state.chat_id, info.kind)
        except Exception:
            log.exception("Échec du traitement de l'échéance %s", info.kind)

    async def _solo_countdown(self, rt: Runtime, seconds: float) -> None:
        """Compte à rebours du mode solo, affiché et mis à jour dans le message du lobby."""
        remaining = seconds
        while remaining > 0:
            try:
                await self._refresh_lobby(rt, int(remaining))
            except Exception:
                log.exception("Échec de la mise à jour du compte à rebours")
            step = min(SOLO_TICK, remaining)
            await self.sleep(step)
            remaining -= step

    # ------------------------------------------------------------ agents IA

    def _spawn_ai(self, rt: Runtime, player_id: str, kind: str) -> None:
        key = (player_id, kind)
        if key in rt.ai_pending:
            return
        rt.ai_pending.add(key)
        task = asyncio.create_task(self._ai_action(rt, player_id, kind))
        rt.ai_tasks.add(task)
        task.add_done_callback(lambda t: rt.ai_tasks.discard(t))

    def _ai_still_relevant(self, rt: Runtime, player_id: str, kind: str) -> bool:
        s = rt.state
        if s.is_final:
            return False
        if kind == "describe":
            sp = s.current_speaker
            return sp is not None and sp.id == player_id
        if kind == "vote":
            cv = s.current_vote
            return cv is not None and s.player(player_id).alive and player_id not in cv.ballots
        return False

    async def _ai_action(self, rt: Runtime, player_id: str, kind: str) -> None:
        chat_id = rt.state.chat_id
        try:
            async with rt.lock:
                if not self._ai_still_relevant(rt, player_id, kind):
                    return
                view = engine.public_view(rt.state, player_id)
            result = await self._ask_ai(chat_id, kind, view)
            async with rt.lock:
                rt.ai_pending.discard((player_id, kind))
                if self.games.get(chat_id) is not rt or not self._ai_still_relevant(
                    rt, player_id, kind
                ):
                    return
                await self._submit_ai(rt, player_id, kind, result)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Échec de l'action d'IA %s %s", player_id, kind)
        finally:
            rt.ai_pending.discard((player_id, kind))

    async def _ask_ai(self, chat_id: int, kind: str, view: PublicView) -> str:
        driver = self.ai_driver
        try:
            if kind == "describe":
                call = driver.describe(view)
                # indicateur « en train d'écrire » de 2 à 5 secondes (FR-054)
                result, _ = await asyncio.wait_for(
                    asyncio.gather(call, self._typing(chat_id)), self.ai_timeout
                )
                return result
            return await asyncio.wait_for(driver.vote(view, self.rng), self.ai_timeout)
        except Exception:
            log.warning("Repli pour l'action d'IA %s", kind)
            fallback = FallbackAIDriver()
            if kind == "describe":
                return await fallback.describe(view)
            return await fallback.vote(view, self.rng)

    async def _typing(self, chat_id: int) -> None:
        try:
            await self.transport.send_typing(chat_id)
        except Exception:
            log.exception("Échec de l'indicateur de frappe")
        await self.sleep(self.rng.uniform(*self.typing_delay))

    async def _submit_ai(self, rt: Runtime, player_id: str, kind: str, result: str) -> None:
        state = rt.state
        if kind == "describe":
            before = len(state.descriptions)
            event: Event = (
                PassTurn(player_id) if result == texts.AI_PASS_TEXT else Describe(player_id, result)
            )
            await self._apply(rt, event, None, None)
            if (
                not state.is_final
                and len(state.descriptions) == before
                and state.current_speaker is not None
                and state.current_speaker.id == player_id
            ):
                await self._apply(rt, PassTurn(player_id), None, None)  # description refusée
        else:  # vote
            cv = state.current_vote
            valid = cv is not None and result in cv.candidates and result != player_id
            if not valid and cv is not None:
                result = self.rng.choice([c for c in cv.candidates if c != player_id])
            await self._apply(rt, CastVote(player_id, result), None, None)

    # ------------------------------------------------------------ reprise

    async def resume(self) -> int:
        """Relit les parties non terminées et reprogramme minuteries et actions d'IA."""
        count = 0
        for stored in await self.repo.load_active_games():
            state = stored.state
            rt = Runtime(state, stored.lobby_message_id)
            self.games[state.chat_id] = rt
            if stored.deadline_kind and stored.deadline_at:
                remaining = max(0.0, (stored.deadline_at - self.clock()).total_seconds())
                self._start_timer(rt, stored.deadline_kind, remaining, stored.deadline_at)
            self._resume_ai(rt)
            count += 1
        return count

    def _resume_ai(self, rt: Runtime) -> None:
        s = rt.state
        sp = s.current_speaker
        if s.phase is Phase.DESCRIPTION and sp is not None and sp.is_ai:
            self._spawn_ai(rt, sp.id, "describe")
        cv = s.current_vote
        if cv is not None:
            for p in s.alive:
                if p.is_ai and p.id not in cv.ballots:
                    self._spawn_ai(rt, p.id, "vote")

    # ------------------------------------------------------------ série automatique

    def _schedule_restart(self, state: GameState) -> None:
        """Mode sans élimination : nouvelle partie avec les mêmes membres après une courte pause."""
        if state.mode is not GameMode.NO_ELIMINATION or state.outcome is Outcome.CANCELLED:
            return
        if state.chat_id in self.restarts:
            return
        info = RestartInfo(creator_id=state.creator_id)
        self.restarts[state.chat_id] = info
        members = [(p.id, p.name) for p in state.humans]
        info.task = asyncio.create_task(self._restart_series(state.chat_id, members, info))

    def _stop_restart(self, chat_id: int) -> None:
        info = self.restarts.pop(chat_id, None)
        if info and info.task and info.task is not asyncio.current_task():
            info.task.cancel()

    async def _restart_series(
        self, chat_id: int, members: list[tuple[str, str]], info: RestartInfo
    ) -> None:
        try:
            try:
                await self.transport.send_group(
                    chat_id, texts.restart_countdown(int(self.restart_delay))
                )
            except Exception:
                log.exception("Échec de l'annonce de la nouvelle partie")
            await self.sleep(self.restart_delay)
            if self.restarts.get(chat_id) is not info or chat_id in self.games:
                return
            self.restarts.pop(chat_id, None)
            free = [
                (pid, name)
                for pid, name in members
                if await self.repo.user_game(pid.split(":", 1)[1]) is None
            ]
            if not free:
                return
            creator = (
                info.creator_id if any(pid == info.creator_id for pid, _ in free) else free[0][0]
            )
            state = engine.create_lobby(
                uuid.UUID(int=self.rng.getrandbits(128)).hex[:8],
                chat_id,
                creator,
                next(name for pid, name in free if pid == creator),
                True,
                self.rng.getrandbits(31),
                GameMode.NO_ELIMINATION,
            )
            for pid, name in free:
                if pid != creator:
                    state.players.append(Player(id=pid, name=name, can_dm=True))
            rt = Runtime(state)
            self.games[chat_id] = rt
            async with rt.lock:
                await self._apply(rt, Launch(creator, immediate=True), None, None)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Échec de la relance automatique")
            self.restarts.pop(chat_id, None)
