"""Modèles du moteur de jeu (objets purs, sans dépendance externe)."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

MAX_PLAYERS = 8
MAX_DESCRIPTION_WORDS = 1  # un seul mot par description


@dataclass(frozen=True)
class WordTrio:
    """Trio de mots proches : identifiant, catégorie et trois mots distincts."""

    id: int
    category: str
    words: tuple[str, str, str]


class Role(StrEnum):
    CIVILIAN = "civilian"
    UNDERCOVER = "undercover"


class Phase(StrEnum):
    LOBBY = "lobby"
    DISTRIBUTION = "distribution"
    DESCRIPTION = "description"
    VOTE = "vote"
    REVOTE = "revote"
    CHECK_VICTORY = "check_victory"
    ENDED = "ended"
    CANCELLED = "cancelled"


class Outcome(StrEnum):
    CIVILIANS = "civilians"
    INFILTRATORS = "infiltrators"
    CANCELLED = "cancelled"


class GameMode(StrEnum):
    """Type de partie choisi par le créateur au lobby."""

    ELIMINATION = "elimination"  # un éliminé par vote, jusqu'à une victoire
    NO_ELIMINATION = "no_elimination"  # un seul vote, puis révélation et nouvelle partie


class VoteKind(StrEnum):
    VOTE = "vote"
    REVOTE = "revote"


FINAL_PHASES = (Phase.ENDED, Phase.CANCELLED)


@dataclass
class Player:
    id: str  # "h:<user_id>" pour un humain, "ai:<nom>" pour une IA
    name: str
    is_ai: bool = False
    role: Role | None = None
    word: str | None = None
    alive: bool = True
    can_dm: bool = False


@dataclass
class Description:
    round: int  # manche (un vote par manche)
    sub_round: int  # tour de description dans la manche (1 à 3)
    player_id: str
    text: str  # un seul mot
    skipped: bool = False


@dataclass
class VoteRound:
    round: int
    kind: VoteKind
    candidates: list[str]
    ballots: dict[str, str] = field(default_factory=dict)  # votant -> cible
    tie_break_drawn: bool = False


@dataclass
class Elimination:
    round: int
    player_id: str
    role_revealed: Role
    by: str  # "vote" ou "draw"


@dataclass
class GameState:
    game_id: str
    chat_id: int
    creator_id: str
    phase: Phase = Phase.LOBBY
    mode: GameMode = GameMode.ELIMINATION
    players: list[Player] = field(default_factory=list)
    trio: WordTrio | None = None
    civilian_word: str | None = None
    undercover_word: str | None = None
    round: int = 0
    sub_round: int = 1
    initial_order: list[str] = field(default_factory=list)
    first_pos: int = 0  # position du premier orateur de la manche dans initial_order
    speaking_order: list[str] = field(default_factory=list)
    speaker_index: int = 0
    descriptions: list[Description] = field(default_factory=list)
    vote_rounds: list[VoteRound] = field(default_factory=list)
    eliminations: list[Elimination] = field(default_factory=list)
    no_vote_streak: int = 0
    solo_waiting: bool = False
    accused_id: str | None = None  # mode sans élimination : joueur le plus voté
    outcome: Outcome | None = None
    points: dict[str, int] = field(default_factory=dict)
    rng_seed: int = 0

    # --- accès pratiques ---
    def player(self, player_id: str) -> Player:
        for p in self.players:
            if p.id == player_id:
                return p
        raise KeyError(player_id)

    def has_player(self, player_id: str) -> bool:
        return any(p.id == player_id for p in self.players)

    @property
    def humans(self) -> list[Player]:
        return [p for p in self.players if not p.is_ai]

    @property
    def alive(self) -> list[Player]:
        return [p for p in self.players if p.alive]

    @property
    def current_speaker(self) -> Player | None:
        if self.phase is Phase.DESCRIPTION and self.speaker_index < len(self.speaking_order):
            return self.player(self.speaking_order[self.speaker_index])
        return None

    @property
    def current_vote(self) -> VoteRound | None:
        if self.phase in (Phase.VOTE, Phase.REVOTE) and self.vote_rounds:
            return self.vote_rounds[-1]
        return None

    @property
    def is_final(self) -> bool:
        return self.phase in FINAL_PHASES

    # --- sérialisation JSON ---
    def to_dict(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "chat_id": self.chat_id,
            "creator_id": self.creator_id,
            "phase": self.phase.value,
            "mode": self.mode.value,
            "players": [
                {
                    "id": p.id,
                    "name": p.name,
                    "is_ai": p.is_ai,
                    "role": p.role.value if p.role else None,
                    "word": p.word,
                    "alive": p.alive,
                    "can_dm": p.can_dm,
                }
                for p in self.players
            ],
            "trio": (
                {"id": self.trio.id, "category": self.trio.category, "words": list(self.trio.words)}
                if self.trio
                else None
            ),
            "civilian_word": self.civilian_word,
            "undercover_word": self.undercover_word,
            "round": self.round,
            "sub_round": self.sub_round,
            "initial_order": list(self.initial_order),
            "first_pos": self.first_pos,
            "speaking_order": list(self.speaking_order),
            "speaker_index": self.speaker_index,
            "descriptions": [
                {
                    "round": d.round,
                    "sub_round": d.sub_round,
                    "player_id": d.player_id,
                    "text": d.text,
                    "skipped": d.skipped,
                }
                for d in self.descriptions
            ],
            "vote_rounds": [
                {
                    "round": v.round,
                    "kind": v.kind.value,
                    "candidates": list(v.candidates),
                    "ballots": dict(v.ballots),
                    "tie_break_drawn": v.tie_break_drawn,
                }
                for v in self.vote_rounds
            ],
            "eliminations": [
                {
                    "round": e.round,
                    "player_id": e.player_id,
                    "role_revealed": e.role_revealed.value,
                    "by": e.by,
                }
                for e in self.eliminations
            ],
            "no_vote_streak": self.no_vote_streak,
            "solo_waiting": self.solo_waiting,
            "accused_id": self.accused_id,
            "outcome": self.outcome.value if self.outcome else None,
            "points": dict(self.points),
            "rng_seed": self.rng_seed,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "GameState":
        trio = d["trio"]
        return cls(
            game_id=d["game_id"],
            chat_id=d["chat_id"],
            creator_id=d["creator_id"],
            phase=Phase(d["phase"]),
            mode=GameMode(d["mode"]),
            players=[
                Player(
                    id=p["id"],
                    name=p["name"],
                    is_ai=p["is_ai"],
                    role=Role(p["role"]) if p["role"] else None,
                    word=p["word"],
                    alive=p["alive"],
                    can_dm=p["can_dm"],
                )
                for p in d["players"]
            ],
            trio=WordTrio(trio["id"], trio["category"], tuple(trio["words"])) if trio else None,
            civilian_word=d["civilian_word"],
            undercover_word=d["undercover_word"],
            round=d["round"],
            sub_round=d["sub_round"],
            initial_order=list(d["initial_order"]),
            first_pos=d["first_pos"],
            speaking_order=list(d["speaking_order"]),
            speaker_index=d["speaker_index"],
            descriptions=[Description(**x) for x in d["descriptions"]],
            vote_rounds=[
                VoteRound(
                    round=v["round"],
                    kind=VoteKind(v["kind"]),
                    candidates=list(v["candidates"]),
                    ballots=dict(v["ballots"]),
                    tie_break_drawn=v["tie_break_drawn"],
                )
                for v in d["vote_rounds"]
            ],
            eliminations=[
                Elimination(
                    round=e["round"],
                    player_id=e["player_id"],
                    role_revealed=Role(e["role_revealed"]),
                    by=e["by"],
                )
                for e in d["eliminations"]
            ],
            no_vote_streak=d["no_vote_streak"],
            solo_waiting=d["solo_waiting"],
            accused_id=d["accused_id"],
            outcome=Outcome(d["outcome"]) if d["outcome"] else None,
            points=dict(d["points"]),
            rng_seed=d["rng_seed"],
        )


# --- événements d'entrée du moteur ---


@dataclass(frozen=True)
class Join:
    player_id: str
    name: str
    can_dm: bool = False


@dataclass(frozen=True)
class Leave:
    player_id: str


@dataclass(frozen=True)
class SetCanDm:
    player_id: str
    can_dm: bool


@dataclass(frozen=True)
class SetMode:
    by: str
    mode: GameMode


@dataclass(frozen=True)
class Launch:
    by: str
    immediate: bool = False  # nouvelle partie automatique : pas de compte à rebours solo


@dataclass(frozen=True)
class Cancel:
    by: str


@dataclass(frozen=True)
class Describe:
    player_id: str
    text: str


@dataclass(frozen=True)
class PassTurn:
    player_id: str


@dataclass(frozen=True)
class CastVote:
    voter_id: str
    target_id: str


@dataclass(frozen=True)
class Timeout:
    kind: str  # "description", "vote", "lobby", "solo_wait"


Event = (
    Join | Leave | SetCanDm | SetMode | Launch | Cancel | Describe | PassTurn | CastVote | Timeout
)


# --- effets de sortie du moteur ---


@dataclass(frozen=True)
class SendGroup:
    key: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SendPrivate:
    player_id: str
    key: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Notify:
    """Retour discret à l'auteur d'une action (alerte de bouton, refus)."""

    player_id: str
    key: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeleteMessage:
    """Supprimer le message qui vient d'être traité (description interdite)."""


@dataclass(frozen=True)
class RequestAIAction:
    player_id: str
    kind: str  # "describe" ou "vote"


@dataclass(frozen=True)
class StartTimer:
    kind: str
    seconds: int


@dataclass(frozen=True)
class CancelTimer:
    kind: str


@dataclass(frozen=True)
class UpdateLobby:
    pass


@dataclass(frozen=True)
class TrioPlayed:
    trio_id: int
    cycle_restarted: bool = False  # tous les trios étaient joués : l'historique repart de zéro


@dataclass(frozen=True)
class RecordScores:
    points: dict[str, int]
    players: list[tuple[str, str]]  # (id, nom) de tous les participants


Effect = (
    SendGroup
    | SendPrivate
    | Notify
    | DeleteMessage
    | RequestAIAction
    | StartTimer
    | CancelTimer
    | UpdateLobby
    | TrioPlayed
    | RecordScores
)


# --- vue publique pour les IA ---


@dataclass(frozen=True)
class PublicView:
    """Ce qu'un joueur peut légitimement savoir ; aucun rôle ni mot des autres (FR-049)."""

    viewer_id: str
    viewer_name: str
    own_word: str
    alive_players: tuple[tuple[str, str], ...]  # (id, nom)
    descriptions: tuple[tuple[int, int, str, str], ...]  # (manche, tour, nom, mot)
    votes: tuple[tuple[int, str, str], ...]  # (manche, votant, cible)
    eliminations: tuple[tuple[int, str, str], ...]  # (manche, nom, rôle révélé)
