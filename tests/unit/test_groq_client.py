import asyncio
from types import SimpleNamespace

import groq
import httpx
import pytest

from ai.groq_client import GroqClient, LLMUnavailable

REQUEST = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


def status_error(cls, code, headers=None, message="erreur"):
    response = httpx.Response(code, request=REQUEST, headers=headers or {})
    return cls(message, response=response, body=None)


class FakeSDK:
    """Faux SDK : enchaîne des résultats (valeur ou exception) pour chaque appel."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.outcomes.pop(0)
        if isinstance(item, Exception):
            raise item
        if item == "hang":
            await asyncio.sleep(10)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=item))])


def make(*outcomes, **kwargs):
    delays: list[float] = []

    async def fake_sleep(d):
        delays.append(d)

    sdk = FakeSDK(*outcomes)
    client = GroqClient("cle", "modele-test", sleep=fake_sleep, client=sdk, **kwargs)
    return client, sdk, delays


async def test_success_uses_configured_model_and_json_mode():
    client, sdk, delays = make('{"vote": "x"}')
    assert await client.complete_json("sys", "usr") == '{"vote": "x"}'
    call = sdk.calls[0]
    assert call["model"] == "modele-test"
    assert call["response_format"] == {"type": "json_object"}
    assert call["messages"][0] == {"role": "system", "content": "sys"}
    assert delays == []


async def test_rate_limit_is_retried_with_exponential_backoff_then_succeeds():
    client, sdk, delays = make(status_error(groq.RateLimitError, 429), '{"ok": 1}')
    assert await client.complete_json("s", "u") == '{"ok": 1}'
    assert delays == [1.0]


async def test_three_failed_attempts_raise_llm_unavailable_with_backoff():
    errors = [status_error(groq.RateLimitError, 429) for _ in range(3)]
    client, sdk, delays = make(*errors)
    with pytest.raises(LLMUnavailable):
        await client.complete_json("s", "u")
    assert len(sdk.calls) == 3  # jamais plus de 3 essais
    assert delays == [1.0, 2.0]


async def test_network_error_is_retried():
    client, sdk, delays = make(groq.APIConnectionError(request=REQUEST), "{}")
    assert await client.complete_json("s", "u") == "{}"
    assert len(sdk.calls) == 2


async def test_timeout_is_retried_then_gives_up():
    client, sdk, delays = make("hang", "hang", "hang", timeout=0.01)
    with pytest.raises(LLMUnavailable):
        await client.complete_json("s", "u")
    assert len(sdk.calls) == 3


async def test_definitive_error_is_not_retried():
    client, sdk, delays = make(status_error(groq.AuthenticationError, 401))
    with pytest.raises(LLMUnavailable):
        await client.complete_json("s", "u")
    assert len(sdk.calls) == 1


async def test_model_is_never_hard_coded():
    import inspect

    import ai.groq_client as module

    assert "llama" not in inspect.getsource(module).lower()
    assert GroqClient("k", "autre-modele", client=FakeSDK()).model == "autre-modele"


class FakeModelsSDK(FakeSDK):
    def __init__(self, ids=None, error=None):
        super().__init__()
        self.ids, self.error = ids or [], error

        async def list_models():
            if self.error:
                raise self.error
            return SimpleNamespace(data=[SimpleNamespace(id=i) for i in self.ids])

        self.models = SimpleNamespace(list=list_models)


async def test_check_model_available(caplog):
    caplog.set_level("INFO")
    client = GroqClient("k", "m1", client=FakeModelsSDK(["m1", "m2"]))
    assert await client.check_model() is True
    assert "disponible" in caplog.text


async def test_check_model_unavailable_lists_the_available_ones(caplog):
    client = GroqClient("k", "absent", client=FakeModelsSDK(["m1", "m2"]))
    assert await client.check_model() is False
    assert "n'est pas accessible" in caplog.text and "m1, m2" in caplog.text


async def test_check_model_never_raises(caplog):
    client = GroqClient("k", "m", client=FakeModelsSDK(error=RuntimeError("réseau")))
    assert await client.check_model() is False
    assert "impossible de vérifier" in caplog.text


async def test_definitive_error_is_logged_not_silent(caplog):
    client, sdk, delays = make(status_error(groq.NotFoundError, 404))
    with pytest.raises(LLMUnavailable):
        await client.complete_json("s", "u")
    assert "erreur définitive" in caplog.text


async def test_retry_after_header_is_honored():
    err = status_error(groq.RateLimitError, 429, {"retry-after": "3"})
    client, sdk, delays = make(err, "{}")
    await client.complete_json("s", "u")
    assert delays == [pytest.approx(3.2)]


async def test_retry_wait_is_capped_so_the_game_keeps_moving():
    err = status_error(groq.RateLimitError, 429, {"retry-after": "120"})
    client, sdk, delays = make(err, "{}")
    await client.complete_json("s", "u")
    assert delays == [10.0]


async def test_json_validate_failed_is_retried_as_transient():
    err = status_error(groq.BadRequestError, 400, message="Error code: 400 - json_validate_failed")
    client, sdk, delays = make(err, '{"description": "ok"}')
    assert await client.complete_json("s", "u") == '{"description": "ok"}'
    assert len(sdk.calls) == 2


async def test_other_bad_requests_stay_definitive():
    err = status_error(groq.BadRequestError, 400, message="Error code: 400 - autre chose")
    client, sdk, delays = make(err)
    with pytest.raises(LLMUnavailable):
        await client.complete_json("s", "u")
    assert len(sdk.calls) == 1


async def test_reasoning_effort_is_sent_only_when_configured():
    client, sdk, _ = make("{}", reasoning_effort="low")
    await client.complete_json("s", "u")
    assert sdk.calls[0]["reasoning_effort"] == "low"
    client2, sdk2, _ = make("{}")
    await client2.complete_json("s", "u")
    assert "reasoning_effort" not in sdk2.calls[0]


async def test_concurrent_calls_are_limited():
    active = 0
    peak = 0

    async def slow_create(**kwargs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])

    sdk = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=slow_create)))
    client = GroqClient("k", "m", client=sdk, concurrency=2)
    await asyncio.gather(*[client.complete_json("s", "u") for _ in range(8)])
    assert peak == 2
