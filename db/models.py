"""Tables SQLite (SQLAlchemy 2, asynchrone) : parties, participants, utilisateurs, scores, trios."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String, Text, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class GameRow(Base):
    """Une partie : l'état complet en JSON, mis à jour à chaque transition."""

    __tablename__ = "games"

    game_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    phase: Mapped[str] = mapped_column(String(32))  # copie de state.phase pour filtrer
    state_json: Mapped[str] = mapped_column(Text)
    deadline_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # UTC
    lobby_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime)

    __table_args__ = (
        # Au plus une partie non terminée par groupe
        Index(
            "uq_games_one_active_per_chat",
            "chat_id",
            unique=True,
            sqlite_where=text("phase NOT IN ('ended', 'cancelled')"),
        ),
    )


class ParticipantRow(Base):
    """Humain inscrit dans une partie non terminée (une seule partie à la fois, FR-007)."""

    __tablename__ = "participants"

    game_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), primary_key=True)

    __table_args__ = (Index("ix_participants_user", "user_id"),)


class UserRow(Base):
    """Utilisateur ayant démarré le bot : peut recevoir des messages privés."""

    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128))
    can_dm: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime)


class ScoreEntry(Base):
    """Points cumulés par groupe et par joueur (IA comprises)."""

    __tablename__ = "scores"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    player_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128))
    points: Mapped[int] = mapped_column(Integer, default=0)
    games_played: Mapped[int] = mapped_column(Integer, default=0)


class PlayedTrioRow(Base):
    """Historique des trios joués par groupe (pas de rejeu avant le tour complet)."""

    __tablename__ = "played_trios"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    trio_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    played_at: Mapped[datetime] = mapped_column(DateTime)
