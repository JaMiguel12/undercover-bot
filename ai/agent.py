"""Agent IA : décrire et voter. Aucune méthode ne lève d'exception (FR-055).

L'agent ne reçoit qu'une `PublicView` (jamais l'état complet de la partie).
"""

import json
import logging
import random
import re
from typing import Any, Protocol

from ai import prompts
from ai.groq_client import LLMUnavailable
from game.models import PublicView
from game.normalize import contains_secret_or_root, normalize

log = logging.getLogger(__name__)

PASS_TEXT = "Je passe mon tour 🤐"
DESCRIBE_ATTEMPTS = 3


class LLMClient(Protocol):
    async def complete_json(self, system: str, user: str, temperature: float = 0.7) -> str: ...


def _parse_json(raw: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        match = re.search(r"\{.*\}", raw or "", re.S)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _clean(text: str) -> str:
    return " ".join(text.replace("\n", " ").split()).strip(' "«»')


class Agent:
    """Pilote d'IA branché sur un client LLM."""

    def __init__(self, client: LLMClient) -> None:
        self.client = client

    async def _ask(self, view: PublicView, user: str, temperature: float) -> dict[str, Any] | None:
        system = prompts.system_prompt(view.viewer_id, view.viewer_name)
        raw = await self.client.complete_json(system, user, temperature)
        return _parse_json(raw)

    # ------------------------------------------------------------ décrire

    def _check_description(self, view: PublicView, text: str) -> str | None:
        """Renvoie le motif de refus, ou None si la description est valide (section 4.3)."""
        if not text:
            return "description vide"
        if len(text.split()) > prompts.MAX_WORDS:
            return "un seul mot est attendu"
        if contains_secret_or_root(text, view.own_word):
            return "elle contient ton mot ou sa racine"
        previous = {normalize(t) for _, _, _, t in view.descriptions}
        if normalize(text) in previous:
            return "elle répète une description déjà donnée"
        return None

    async def describe(self, view: PublicView) -> str:
        try:
            hint: str | None = None
            for _ in range(DESCRIBE_ATTEMPTS):
                data = await self._ask(view, prompts.describe_prompt(view, hint), 0.9)
                text = _clean(str(data.get("description", ""))) if data else ""
                hint = self._check_description(view, text)
                if hint is None:
                    return text
                log.warning("IA %s : description refusée (%s)", view.viewer_name, hint)
            return PASS_TEXT
        except LLMUnavailable:
            log.warning("IA %s : LLM indisponible, elle passe son tour", view.viewer_name)
            return PASS_TEXT
        except Exception:
            log.exception("Erreur inattendue pendant la description de %s", view.viewer_name)
            return PASS_TEXT

    # ------------------------------------------------------------ voter

    @staticmethod
    def _random_vote(view: PublicView, rng: random.Random) -> str:
        return rng.choice([pid for pid, _ in view.alive_players if pid != view.viewer_id])

    async def vote(self, view: PublicView, rng: random.Random) -> str:
        """Identifiant du joueur ciblé ; vote aléatoire valide en cas de repli."""
        try:
            data = await self._ask(view, prompts.vote_prompt(view), 0.3)
            name = _clean(str(data.get("vote", ""))) if data else ""
            wanted = normalize(name)
            for pid, pname in view.alive_players:
                if pid != view.viewer_id and normalize(pname) == wanted and wanted:
                    return pid
        except LLMUnavailable:
            pass
        except Exception:
            log.exception("Erreur inattendue pendant le vote de %s", view.viewer_name)
        return self._random_vote(view, rng)
