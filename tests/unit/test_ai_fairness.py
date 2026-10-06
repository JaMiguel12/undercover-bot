"""Équité (principe IV, FR-049) : l'IA ne reçoit que la vue publique."""

import ast
import inspect
from pathlib import Path

import pytest

from ai import prompts
from ai.agent import Agent
from game.engine import apply, public_view
from game.models import Describe, Phase
from tests.unit.helpers import describe_round, everyone_votes, start_game

AI_DIR = Path(__file__).resolve().parents[2] / "ai"


def imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
    return names


@pytest.mark.parametrize("path", sorted(AI_DIR.glob("*.py")), ids=lambda p: p.name)
def test_ai_package_never_imports_the_full_game_state(path):
    assert "GameState" not in imported_names(path)
    assert "engine" not in {n.split(".")[-1] for n in imported_names(path)}


def test_agent_methods_only_take_a_public_view():
    for method in (Agent.describe, Agent.vote):
        params = list(inspect.signature(method).parameters.values())
        assert params[1].name == "view"
        assert params[1].annotation.__name__ == "PublicView"


@pytest.mark.parametrize("seed", range(8))
def test_prompts_contain_no_foreign_word_or_own_role(seed):
    state, ctx, _ = start_game(3, seed)
    describe_round(state, ctx)
    ai = next(p for p in state.players if p.is_ai)
    view = public_view(state, ai.id)
    built = [
        prompts.system_prompt(ai.id, ai.name),
        prompts.describe_prompt(view),
        prompts.vote_prompt(view),
    ]
    text = "\n".join(built)
    assert ai.word in text  # son propre mot est bien fourni
    for other in state.players:
        if other.word != ai.word:
            assert other.word not in text
    # aucun rôle n'est attribué à l'IA ni à un joueur encore en jeu
    for p in state.players:
        assert f"{p.name} (Civil)" not in text and f"{p.name} (Undercover)" not in text


def test_eliminated_role_is_visible_but_still_no_word():
    state, ctx, _ = start_game(3, seed=4)
    describe_round(state, ctx)
    victim = next(p for p in state.players if not p.is_ai)
    everyone_votes(state, ctx, victim.id)
    ai = next(p for p in state.alive if p.is_ai)
    text = prompts.vote_prompt(public_view(state, ai.id))
    assert f"{victim.name} (" in text  # rôle révélé : information publique
    assert victim.word not in text or victim.word == ai.word


def test_view_changes_only_with_public_events():
    state, ctx, _ = start_game(3, seed=2)
    ai = next(p for p in state.players if p.is_ai)
    before = public_view(state, ai.id)
    assert state.phase is Phase.DESCRIPTION
    speaker = state.current_speaker
    apply(state, Describe(speaker.id, "indice"), ctx)
    after = public_view(state, ai.id)
    assert len(after.descriptions) == len(before.descriptions) + 1
