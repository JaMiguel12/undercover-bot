"""Dépôt de persistance : interface et implémentation en mémoire (tests, première étape)."""

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from sqlalchemy import delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from db.models import Base, GameRow, ParticipantRow, PlayedTrioRow, ScoreEntry, UserRow
from game.models import FINAL_PHASES, GameState

log = logging.getLogger(__name__)


@dataclass
class StoredGame:
    """Une partie telle que conservée : état, échéance en cours, message de lobby."""

    state: GameState
    deadline_kind: str | None = None
    deadline_at: datetime | None = None
    lobby_message_id: int | None = None


@dataclass(frozen=True)
class ScoreRow:
    player_id: str
    name: str
    points: int
    games_played: int


class Repository(Protocol):
    async def save_game(self, game: StoredGame) -> None: ...

    async def load_active_games(self) -> list[StoredGame]: ...

    async def user_game(self, user_id: str) -> str | None:
        """Identifiant de la partie active (non terminée) qui inscrit cet utilisateur."""
        ...

    async def get_can_dm(self, user_id: str) -> bool: ...

    async def set_user(self, user_id: str, name: str, can_dm: bool = True) -> None: ...

    async def played_trios(self, chat_id: int) -> set[int]: ...

    async def add_played_trio(self, chat_id: int, trio_id: int, reset: bool = False) -> None: ...

    async def add_scores(
        self, chat_id: int, points: dict[str, int], players: list[tuple[str, str]]
    ) -> None: ...

    async def leaderboard(self, chat_id: int) -> list[ScoreRow]: ...


@dataclass
class MemoryRepository:
    """Implémentation en mémoire du dépôt (sans disque)."""

    games: dict[str, StoredGame] = field(default_factory=dict)
    users: dict[str, tuple[str, bool]] = field(default_factory=dict)
    played: dict[int, set[int]] = field(default_factory=dict)
    scores: dict[tuple[int, str], list] = field(default_factory=dict)  # [nom, points, parties]

    async def save_game(self, game: StoredGame) -> None:
        # Copie via sérialisation : le dépôt ne partage pas l'objet mutable du moteur
        stored = StoredGame(
            GameState.from_dict(game.state.to_dict()),
            game.deadline_kind,
            game.deadline_at,
            game.lobby_message_id,
        )
        self.games[game.state.game_id] = stored

    async def load_active_games(self) -> list[StoredGame]:
        return [
            StoredGame(
                GameState.from_dict(g.state.to_dict()),
                g.deadline_kind,
                g.deadline_at,
                g.lobby_message_id,
            )
            for g in self.games.values()
            if not g.state.is_final
        ]

    async def user_game(self, user_id: str) -> str | None:
        for g in self.games.values():
            if not g.state.is_final and g.state.has_player(f"h:{user_id}"):
                return g.state.game_id
        return None

    async def get_can_dm(self, user_id: str) -> bool:
        return self.users.get(user_id, ("", False))[1]

    async def set_user(self, user_id: str, name: str, can_dm: bool = True) -> None:
        self.users[user_id] = (name, can_dm)

    async def played_trios(self, chat_id: int) -> set[int]:
        return set(self.played.get(chat_id, set()))

    async def add_played_trio(self, chat_id: int, trio_id: int, reset: bool = False) -> None:
        if reset:
            self.played[chat_id] = set()
        self.played.setdefault(chat_id, set()).add(trio_id)

    async def add_scores(
        self, chat_id: int, points: dict[str, int], players: list[tuple[str, str]]
    ) -> None:
        for pid, name in players:
            row = self.scores.setdefault((chat_id, pid), [name, 0, 0])
            row[0] = name
            row[1] += points.get(pid, 0)
            row[2] += 1

    async def leaderboard(self, chat_id: int) -> list[ScoreRow]:
        rows = [
            ScoreRow(pid, v[0], v[1], v[2])
            for (cid, pid), v in self.scores.items()
            if cid == chat_id
        ]
        return sorted(rows, key=lambda r: (-r.points, r.name))


# ---------------------------------------------------------------- SQLite (SQLAlchemy async)


def _to_naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _to_aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class SqlRepository:
    """Persistance SQLite : un document JSON par partie, sauvegardé à chaque transition."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.engine: AsyncEngine = create_async_engine(database_url)
        self._sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init(self) -> None:
        """Crée le dossier du fichier SQLite et les tables."""
        db_path = make_url(self.database_url).database
        if db_path and db_path != ":memory:":
            Path(db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self.engine.dispose()

    async def save_game(self, game: StoredGame) -> None:
        state = game.state
        async with self._sessions() as session, session.begin():
            await session.merge(
                GameRow(
                    game_id=state.game_id,
                    chat_id=state.chat_id,
                    phase=state.phase.value,
                    state_json=json.dumps(state.to_dict(), ensure_ascii=False),
                    deadline_kind=game.deadline_kind,
                    deadline_at=_to_naive_utc(game.deadline_at),
                    lobby_message_id=game.lobby_message_id,
                    updated_at=_to_naive_utc(datetime.now(UTC)),
                )
            )
            await session.execute(
                delete(ParticipantRow).where(ParticipantRow.game_id == state.game_id)
            )
            if not state.is_final:
                for p in state.humans:
                    session.add(
                        ParticipantRow(game_id=state.game_id, user_id=p.id.split(":", 1)[1])
                    )

    async def load_active_games(self) -> list[StoredGame]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(GameRow).where(GameRow.phase.not_in([p.value for p in FINAL_PHASES]))
                )
            ).all()
        games: list[StoredGame] = []
        for r in rows:
            try:
                state = GameState.from_dict(json.loads(r.state_json))
            except (KeyError, ValueError, TypeError):
                # Partie enregistrée avec des règles qui n'existent plus : on la clôt proprement
                log.warning("Partie %s illisible (anciennes règles) : annulée", r.game_id)
                await self._discard_game(r.game_id)
                continue
            games.append(
                StoredGame(state, r.deadline_kind, _to_aware_utc(r.deadline_at), r.lobby_message_id)
            )
        return games

    async def _discard_game(self, game_id: str) -> None:
        async with self._sessions() as session, session.begin():
            row = await session.get(GameRow, game_id)
            if row is not None:
                row.phase = "cancelled"
            await session.execute(delete(ParticipantRow).where(ParticipantRow.game_id == game_id))

    async def user_game(self, user_id: str) -> str | None:
        async with self._sessions() as session:
            return await session.scalar(
                select(ParticipantRow.game_id).where(ParticipantRow.user_id == user_id).limit(1)
            )

    async def get_can_dm(self, user_id: str) -> bool:
        async with self._sessions() as session:
            row = await session.get(UserRow, user_id)
            return bool(row and row.can_dm)

    async def set_user(self, user_id: str, name: str, can_dm: bool = True) -> None:
        async with self._sessions() as session, session.begin():
            await session.merge(
                UserRow(
                    user_id=user_id,
                    display_name=name,
                    can_dm=can_dm,
                    started_at=_to_naive_utc(datetime.now(UTC)),
                )
            )

    async def played_trios(self, chat_id: int) -> set[int]:
        async with self._sessions() as session:
            rows = await session.scalars(
                select(PlayedTrioRow.trio_id).where(PlayedTrioRow.chat_id == chat_id)
            )
            return set(rows.all())

    async def add_played_trio(self, chat_id: int, trio_id: int, reset: bool = False) -> None:
        async with self._sessions() as session, session.begin():
            if reset:
                await session.execute(delete(PlayedTrioRow).where(PlayedTrioRow.chat_id == chat_id))
            await session.merge(
                PlayedTrioRow(
                    chat_id=chat_id, trio_id=trio_id, played_at=_to_naive_utc(datetime.now(UTC))
                )
            )

    async def add_scores(
        self, chat_id: int, points: dict[str, int], players: list[tuple[str, str]]
    ) -> None:
        async with self._sessions() as session, session.begin():
            for pid, name in players:
                row = await session.get(ScoreEntry, (chat_id, pid))
                if row is None:
                    row = ScoreEntry(
                        chat_id=chat_id, player_id=pid, display_name=name, points=0, games_played=0
                    )
                    session.add(row)
                row.display_name = name
                row.points += points.get(pid, 0)
                row.games_played += 1

    async def leaderboard(self, chat_id: int) -> list[ScoreRow]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(ScoreEntry)
                    .where(ScoreEntry.chat_id == chat_id)
                    .order_by(ScoreEntry.points.desc(), ScoreEntry.display_name)
                )
            ).all()
        return [ScoreRow(r.player_id, r.display_name, r.points, r.games_played) for r in rows]
