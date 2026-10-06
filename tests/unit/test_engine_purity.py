import ast
from pathlib import Path

import pytest

from game.models import GameState
from tests.unit.helpers import describe_round, everyone_votes, make_ctx, make_lobby, start_game

GAME_DIR = Path(__file__).resolve().parents[2] / "game"
FORBIDDEN = {
    "aiogram",
    "sqlalchemy",
    "groq",
    "asyncio",
    "pydantic",
    "pydantic_settings",
    "bot",
    "ai",
    "db",
}


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    return found


@pytest.mark.parametrize("path", sorted(GAME_DIR.glob("*.py")), ids=lambda p: p.name)
def test_game_package_has_no_forbidden_import(path):
    assert not imported_modules(path) & FORBIDDEN


def test_roundtrip_lobby():
    state = make_lobby(3, make_ctx())
    assert GameState.from_dict(state.to_dict()).to_dict() == state.to_dict()


def test_roundtrip_in_every_phase():
    import json

    state, ctx, _ = start_game(5, seed=6)
    snapshots = [state.to_dict()]
    describe_round(state, ctx)
    snapshots.append(state.to_dict())  # vote ouvert
    everyone_votes(state, ctx)
    snapshots.append(state.to_dict())
    for snap in snapshots:
        restored = GameState.from_dict(json.loads(json.dumps(snap)))
        assert restored.to_dict() == snap
