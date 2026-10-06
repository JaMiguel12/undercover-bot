import json

import pytest
from pydantic import ValidationError

from bot.config import ConfigError, Settings, load_game_config

REQUIRED = {"BOT_TOKEN": "t", "GROQ_API_KEY": "k", "GROQ_MODEL": "m"}


def make(monkeypatch, **extra):
    for key in (
        "BOT_TOKEN",
        "GROQ_API_KEY",
        "GROQ_MODEL",
        "DESCRIPTION_TIMEOUT",
        "VOTE_TIMEOUT",
        "LOBBY_TIMEOUT",
        "SOLO_WAIT_TIMEOUT",
        "RESTART_DELAY",
        "DATABASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in {**REQUIRED, **extra}.items():
        if value is not None:
            monkeypatch.setenv(key, str(value))
    return Settings(_env_file=None)


def test_defaults(monkeypatch):
    s = make(monkeypatch)
    assert s.description_timeout == 60
    assert s.vote_timeout == 90
    assert s.lobby_timeout == 600
    assert s.solo_wait_timeout == 30
    assert s.restart_delay == 60
    assert s.database_url.startswith("sqlite+aiosqlite")


@pytest.mark.parametrize("missing", ["BOT_TOKEN", "GROQ_API_KEY", "GROQ_MODEL"])
def test_required_variables(monkeypatch, missing):
    with pytest.raises(ValidationError):
        make(monkeypatch, **{missing: None})


@pytest.mark.parametrize("value", ["0", "-5", "abc"])
def test_invalid_timeout_refused(monkeypatch, value):
    with pytest.raises(ValidationError):
        make(monkeypatch, DESCRIPTION_TIMEOUT=value)


def test_game_config_loads_default_file():
    cfg = load_game_config("data/game_config.json")
    assert cfg.roles[8] == (6, 2)
    assert cfg.roles[4] == (3, 1)
    assert cfg.description_rounds == 3
    assert cfg.points.civilian_win_per_civilian == 2


def test_game_config_missing_file(tmp_path):
    with pytest.raises(ConfigError):
        load_game_config(tmp_path / "absent.json")


def test_game_config_invalid_content(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"roles": {}}), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_game_config(p)


def test_game_config_role_total_must_match(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(
        json.dumps(
            {
                "roles": {"4": {"civilians": 3, "undercovers": 2, "mr_white": 0}},
                "points": {
                    "civilian_win_per_civilian": 2,
                    "infiltrator_win_per_undercover": 10,
                },
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_game_config(p)


def test_description_rounds_must_be_positive(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(
        json.dumps(
            {
                "description_rounds": 0,
                "roles": {"4": {"civilians": 3, "undercovers": 1}},
                "points": {"civilian_win_per_civilian": 2, "infiltrator_win_per_undercover": 10},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_game_config(p)
