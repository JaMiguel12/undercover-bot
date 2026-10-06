"""Configuration : variables d'environnement (.env) et fichier de configuration du jeu."""

import json
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from game.rules import GameConfig, Points


class ConfigError(Exception):
    """Configuration absente ou invalide."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    bot_token: str = Field(min_length=1)
    groq_api_key: str = Field(min_length=1)
    groq_model: str = Field(min_length=1)
    groq_reasoning_effort: str = ""  # facultatif : « low » pour les modèles qui raisonnent
    database_url: str = "sqlite+aiosqlite:///./data/undercover.db"
    description_timeout: int = Field(default=60, gt=0)
    vote_timeout: int = Field(default=90, gt=0)
    lobby_timeout: int = Field(default=600, gt=0)
    solo_wait_timeout: int = Field(default=30, gt=0)
    restart_delay: int = Field(default=60, gt=0)  # pause avant la nouvelle partie automatique


def load_game_config(path: str | Path) -> GameConfig:
    """Charge répartition des rôles, barème et tours de description ; erreur explicite sinon."""
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Fichier de configuration du jeu introuvable : {p}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Fichier de configuration du jeu invalide ({p}) : {exc}") from exc
    try:
        roles: dict[int, tuple[int, int]] = {}
        for total, r in data["roles"].items():
            c, u = int(r["civilians"]), int(r["undercovers"])
            if c + u != int(total) or min(c, u) < 0:
                raise ConfigError(f"Répartition incohérente pour {total} joueurs dans {p}")
            roles[int(total)] = (c, u)
        pts = data["points"]
        points = Points(
            civilian_win_per_civilian=int(pts["civilian_win_per_civilian"]),
            infiltrator_win_per_undercover=int(pts["infiltrator_win_per_undercover"]),
        )
        description_rounds = int(data.get("description_rounds", 3))
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ConfigError(f"Fichier de configuration du jeu invalide ({p}) : {exc!r}") from exc
    if not roles:
        raise ConfigError(f"Aucune répartition de rôles dans {p}")
    if description_rounds < 1:
        raise ConfigError(f"description_rounds doit être au moins 1 dans {p}")
    return GameConfig(roles=roles, points=points, description_rounds=description_rounds)
