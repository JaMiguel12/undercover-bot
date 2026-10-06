"""Client Groq : appel asynchrone avec délai maximal et backoff exponentiel (section 4.5)."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import groq

log = logging.getLogger(__name__)

# Erreurs temporaires : on réessaie avec un délai croissant (429, réseau, panne côté serveur)
_RETRIABLE = (
    groq.RateLimitError,
    groq.APIConnectionError,
    groq.APITimeoutError,
    groq.InternalServerError,
    asyncio.TimeoutError,
)


# Attente maximale entre deux essais, même si Groq demande plus (la partie doit avancer)
MAX_RETRY_WAIT = 10.0


def _is_transient_bad_request(exc: groq.APIError) -> bool:
    """400 « json_validate_failed » : le modèle n'a rien produit de valide, un essai suffit."""
    return isinstance(exc, groq.BadRequestError) and "json_validate_failed" in str(exc)


def _retry_after(exc: Exception) -> float | None:
    """Délai demandé par Groq (en-tête retry-after) pour une limite de débit, s'il existe."""
    response = getattr(exc, "response", None)
    value = response.headers.get("retry-after") if response is not None else None
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


class LLMUnavailable(Exception):
    """Le LLM n'a pas pu répondre (après les essais) : l'agent bascule sur son repli."""


class GroqClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float = 10.0,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        client: Any = None,
        reasoning_effort: str | None = None,
        concurrency: int = 2,
    ) -> None:
        # Les réessais du SDK sont désactivés : le backoff est géré ici (3 essais maximum)
        self._client = client or groq.AsyncGroq(api_key=api_key, timeout=timeout, max_retries=0)
        self.model = model  # lu depuis GROQ_MODEL, jamais codé en dur
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self._sleep = sleep
        self.reasoning_effort = reasoning_effort or None  # « low » réduit les jetons consommés
        # Peu d'appels simultanés : les trois IA ne doivent pas épuiser la limite par minute
        self._slots = asyncio.Semaphore(concurrency)

    async def complete_json(self, system: str, user: str, temperature: float = 0.7) -> str:
        """Renvoie le texte JSON brut du modèle, ou lève LLMUnavailable."""
        async with self._slots:
            return await self._complete(system, user, temperature)

    async def _complete(self, system: str, user: str, temperature: float) -> str:
        extra: dict[str, Any] = {}
        if self.reasoning_effort:
            extra["reasoning_effort"] = self.reasoning_effort
        last: Exception | None = None
        for attempt in range(self.max_attempts):
            try:
                response = await asyncio.wait_for(
                    self._client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        response_format={"type": "json_object"},
                        temperature=temperature,
                        max_tokens=400,
                        **extra,
                    ),
                    self.timeout,
                )
                return response.choices[0].message.content or ""
            except groq.APIError as exc:
                transient = isinstance(exc, _RETRIABLE) or _is_transient_bad_request(exc)
                if not transient:  # erreur définitive (clé invalide, modèle inconnu...)
                    log.error("LLM : erreur définitive, les IA passeront leur tour (%s)", exc)
                    raise LLMUnavailable(str(exc)) from exc
                last = exc
                await self._wait_before_retry(attempt, exc)
            except _RETRIABLE as exc:  # délai dépassé côté application
                last = exc
                await self._wait_before_retry(attempt, exc)
        raise LLMUnavailable(f"échec après {self.max_attempts} essais : {last}")

    async def _wait_before_retry(self, attempt: int, exc: Exception) -> None:
        log.warning("LLM : essai %d/%d échoué (%s)", attempt + 1, self.max_attempts, exc)
        if attempt + 1 >= self.max_attempts:
            return
        wanted = _retry_after(exc)
        delay = wanted + 0.2 if wanted is not None else self.base_delay * 2**attempt
        await self._sleep(min(delay, MAX_RETRY_WAIT))

    async def check_model(self) -> bool:
        """Vérifie au démarrage que GROQ_MODEL est accessible avec cette clé ; ne lève jamais."""
        try:
            models = await asyncio.wait_for(self._client.models.list(), self.timeout)
        except Exception as exc:
            log.warning("LLM : impossible de vérifier le modèle %s (%s)", self.model, exc)
            return False
        available = sorted(m.id for m in models.data)
        if self.model in available:
            log.info("LLM : modèle %s disponible", self.model)
            return True
        log.error(
            "LLM : le modèle %s n'est pas accessible avec cette clé. Modifiez GROQ_MODEL. "
            "Modèles disponibles : %s",
            self.model,
            ", ".join(available),
        )
        return False
