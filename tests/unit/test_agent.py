import json
import random

from ai.agent import PASS_TEXT, Agent
from ai.groq_client import LLMUnavailable
from game.models import PublicView


class ScriptedLLM:
    """Faux client LLM : renvoie les réponses dans l'ordre, ou lève une erreur."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.prompts: list[str] = []

    async def complete_json(self, system, user, temperature=0.7):
        self.prompts.append(user)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item if isinstance(item, str) else json.dumps(item)


def view(descriptions=(), alive=None, own_word="thé"):
    alive = alive or (("ai:kendall", "Kendall IA"), ("h:1", "Marie"), ("h:2", "Paul"))
    return PublicView(
        viewer_id="ai:kendall",
        viewer_name="Kendall IA",
        own_word=own_word,
        alive_players=tuple(alive),
        descriptions=tuple(descriptions),
        votes=(),
        eliminations=(),
    )


async def test_valid_description_is_returned():
    agent = Agent(ScriptedLLM({"description": "matin"}))
    assert await agent.describe(view()) == "matin"


async def test_json_wrapped_in_text_is_still_parsed():
    agent = Agent(ScriptedLLM('Voici : {"description": "doux"} merci'))
    assert await agent.describe(view()) == "doux"


async def test_too_many_words_secret_word_root_and_repeat_are_retried():
    previous = [(1, 1, "Marie", "chaude")]
    llm = ScriptedLLM(
        {"description": "deux mots"},  # plus d'un mot
        {"description": "thé"},  # mot secret
        {"description": "Chaude"},  # répétition (normalisée)
        {"description": "infusion"},  # inutilisé : 3 essais seulement
    )
    agent = Agent(llm)
    assert await agent.describe(view(previous)) == PASS_TEXT
    assert len(llm.prompts) == 3
    assert "refusée" in llm.prompts[1]  # le motif du refus est renvoyé au modèle


async def test_valid_after_a_refused_attempt():
    llm = ScriptedLLM({"description": "thé"}, {"description": "détente"})
    assert await Agent(llm).describe(view()) == "détente"


async def test_root_of_secret_word_refused():
    llm = ScriptedLLM({"description": "cuisinière"}, {"description": "recette"})
    assert await Agent(llm).describe(view(own_word="cuisinier")) == "recette"


async def test_llm_unavailable_means_pass():
    assert await Agent(ScriptedLLM(LLMUnavailable("down"))).describe(view()) == PASS_TEXT


async def test_garbage_response_means_pass_after_three_tries():
    assert await Agent(ScriptedLLM("n'importe quoi", "[]", "")).describe(view()) == PASS_TEXT


async def test_unexpected_exception_never_escapes():
    assert await Agent(ScriptedLLM(RuntimeError("boom"))).describe(view()) == PASS_TEXT


async def test_vote_by_exact_name():
    agent = Agent(ScriptedLLM({"vote": "Paul"}))
    assert await agent.vote(view(), random.Random(0)) == "h:2"


async def test_vote_normalized_name():
    agent = Agent(ScriptedLLM({"vote": "  PAUL "}))
    assert await agent.vote(view(), random.Random(0)) == "h:2"


async def test_vote_for_self_or_unknown_falls_back_to_random_valid():
    for answer in ({"vote": "Kendall IA"}, {"vote": "Inconnu"}, "pas du json"):
        got = await Agent(ScriptedLLM(answer)).vote(view(), random.Random(1))
        assert got in {"h:1", "h:2"}


async def test_vote_llm_down_is_random_valid():
    got = await Agent(ScriptedLLM(LLMUnavailable("x"))).vote(view(), random.Random(2))
    assert got in {"h:1", "h:2"}


async def test_llm_failure_is_logged_by_the_agent(caplog):
    await Agent(ScriptedLLM(LLMUnavailable("down"))).describe(view())
    assert "LLM indisponible" in caplog.text
    assert "thé" not in caplog.text  # jamais le mot secret dans les journaux


async def test_description_works_with_a_non_empty_history():
    """Régression : l'historique public (4 éléments par mot) est bien lu par l'agent."""
    history = [(1, 1, "Marie", "chaude"), (1, 2, "Paul", "matin"), (1, 3, "Marie", "sucre")]
    agent = Agent(ScriptedLLM({"description": "feuille"}))
    assert await agent.describe(view(history)) == "feuille"


async def test_repeating_a_word_from_any_round_is_refused():
    history = [(1, 1, "Marie", "chaude"), (2, 3, "Paul", "matin")]
    llm = ScriptedLLM({"description": "Matin"}, {"description": "feuille"})
    assert await Agent(llm).describe(view(history)) == "feuille"
