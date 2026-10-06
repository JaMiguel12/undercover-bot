"""Règles du jeu pures : configuration, complétion IA, répartition des rôles, victoire, points."""

from dataclasses import dataclass

from game.models import MAX_PLAYERS, GameState, Outcome, Role


@dataclass(frozen=True)
class Points:
    """Barème de points (FR-039)."""

    civilian_win_per_civilian: int
    infiltrator_win_per_undercover: int


@dataclass(frozen=True)
class GameConfig:
    """Valeurs de jeu configurables : rôles par total de joueurs, barème, tours de description."""

    # total de joueurs -> (civils, undercovers)
    roles: dict[int, tuple[int, int]]
    points: Points
    description_rounds: int = 3  # tours de description avant chaque vote


# Ordre de priorité des IA (FR-009)
AI_ROSTER: tuple[tuple[str, str], ...] = (
    ("ai:zendaya", "Zendaya IA"),
    ("ai:kendall", "Kendall IA"),
    ("ai:diva", "BFF Diva IA"),
)


def ai_completion(n_humans: int) -> list[tuple[str, str]]:
    """IA à ajouter pour n humains : jusqu'à 3 IA pour atteindre 8 joueurs (FR-009)."""
    if n_humans < 1 or n_humans > MAX_PLAYERS:
        raise ValueError(f"Nombre d'humains invalide : {n_humans}")
    count = min(len(AI_ROSTER), MAX_PLAYERS - n_humans)
    return list(AI_ROSTER[:count])


def role_distribution(total: int, config: GameConfig) -> tuple[int, int]:
    """(civils, undercovers) pour un total de joueurs (FR-015)."""
    try:
        return config.roles[total]
    except KeyError:
        raise ValueError(f"Aucune répartition de rôles pour {total} joueurs") from None


def check_victory(state: GameState) -> Outcome | None:
    """Condition de victoire après une élimination (FR-037)."""
    alive = state.alive
    undercovers = [p for p in alive if p.role is Role.UNDERCOVER]
    civilians = [p for p in alive if p.role is Role.CIVILIAN]
    if not undercovers:
        return Outcome.CIVILIANS
    if len(civilians) <= 1:
        return Outcome.INFILTRATORS
    return None


def compute_points(state: GameState, config: GameConfig) -> dict[str, int]:
    """Points attribués selon l'issue (FR-039) ; vide si la partie est annulée."""
    pts = config.points
    result: dict[str, int] = {}
    if state.outcome is Outcome.CIVILIANS:
        for p in state.players:
            if p.role is Role.CIVILIAN:
                result[p.id] = pts.civilian_win_per_civilian
    elif state.outcome is Outcome.INFILTRATORS:
        for p in state.players:
            if p.role is Role.UNDERCOVER:
                result[p.id] = pts.infiltrator_win_per_undercover
    return result
