"""Démarrage : une base de mots ou une configuration invalide bloque le bot (FR-057)."""

import asyncio
import json

import pytest

import bot.main as main_module


def set_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # pas de .env du dépôt
    monkeypatch.setenv("BOT_TOKEN", "123:fake")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("GROQ_MODEL", "m")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'x.db'}")


def test_invalid_words_database_stops_the_bot_with_explicit_error(monkeypatch, tmp_path, capsys):
    set_env(monkeypatch, tmp_path)
    bad = tmp_path / "words.json"
    bad.write_text(
        json.dumps(
            [
                {"id": 7, "categorie": "A", "mots": ["a", "b", "c"]},
                {"id": 7, "categorie": "B", "mots": ["d", "e", "f"]},
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(main_module, "WORDS_FILE", bad)
    with pytest.raises(SystemExit) as exc:
        asyncio.run(main_module.main())
    assert exc.value.code == 1
    assert "7" in capsys.readouterr().err


def test_missing_secrets_stop_the_bot(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    for var in ("BOT_TOKEN", "GROQ_API_KEY", "GROQ_MODEL"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(SystemExit) as exc:
        asyncio.run(main_module.main())
    assert exc.value.code == 1
    assert "configuration invalide" in capsys.readouterr().err


def test_invalid_game_config_stops_the_bot(monkeypatch, tmp_path, capsys):
    set_env(monkeypatch, tmp_path)
    bad = tmp_path / "game_config.json"
    bad.write_text("{pas du json", encoding="utf-8")
    monkeypatch.setattr(main_module, "GAME_CONFIG_FILE", bad)
    with pytest.raises(SystemExit) as exc:
        asyncio.run(main_module.main())
    assert exc.value.code == 1
    assert "invalide" in capsys.readouterr().err
