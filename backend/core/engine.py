"""Inference Engine abstraction — sjednocuje LLM volání.

Inspirováno OpenJarvis InferenceEngine ABC, zjednodušeno pro ADOBE-AUTOMAT.
Nahrazuje 3× copy-paste `anthropic.Anthropic().messages.create()` jednou abstrakcí.

Použití:
    engine = get_engine()  # default AnthropicEngine
    result = engine.generate(
        messages=[{"role": "user", "content": "Hello"}],
        model="claude-sonnet-4-6",
        system="You are a helpful assistant.",
    )
    print(result.content)
    print(f"Tokens: {result.input_tokens} in, {result.output_tokens} out")
"""

import os
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, Sequence

from core.registry import EngineRegistry

logger = logging.getLogger(__name__)


# === Model konstanty ===

MODEL_OPUS = "claude-opus-4-6"
MODEL_SONNET = "claude-sonnet-4-6"
MODEL_HAIKU = "claude-haiku-4-5-20251001"

# Aliasy pro snadné použití
MODELS = {
    "opus": MODEL_OPUS,
    "sonnet": MODEL_SONNET,
    "haiku": MODEL_HAIKU,
}


def resolve_model(model: str) -> str:
    """Resolve alias ('sonnet') na plný model ID."""
    return MODELS.get(model, model)


# === Datové typy ===

@dataclass(slots=True)
class EngineResult:
    """Výsledek jednoho LLM volání."""
    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    latency_seconds: float = 0.0
    stop_reason: Optional[str] = None
    raw_response: Optional[Any] = None
    thinking: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def cost_usd(self) -> float:
        """Odhad ceny volání v USD (Anthropic pricing 2026-03)."""
        return _estimate_cost(
            self.model, self.input_tokens, self.output_tokens,
            self.cache_read_tokens, self.cache_creation_tokens
        )


def _estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read: int = 0,
    cache_creation: int = 0,
) -> float:
    """Odhad ceny v USD podle Anthropic pricing."""
    # Ceny za 1M tokenů (2026-03)
    pricing = {
        MODEL_OPUS: {"input": 15.0, "output": 75.0, "cache_read": 1.5, "cache_write": 18.75},
        MODEL_SONNET: {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_write": 3.75},
        MODEL_HAIKU: {"input": 0.80, "output": 4.0, "cache_read": 0.08, "cache_write": 1.0},
    }
    # Fallback — pokud model není v tabulce, odhadni jako Sonnet
    p = pricing.get(model, pricing[MODEL_SONNET])

    cost = (
        (input_tokens - cache_read - cache_creation) * p["input"]
        + output_tokens * p["output"]
        + cache_read * p["cache_read"]
        + cache_creation * p["cache_write"]
    ) / 1_000_000
    return max(0.0, cost)


# === ABC ===

class InferenceEngine(ABC):
    """Abstraktní rozhraní pro LLM inference."""

    engine_id: str = "base"

    @abstractmethod
    def generate(
        self,
        messages: Sequence[Dict[str, Any]],
        *,
        model: str = MODEL_SONNET,
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        thinking: Optional[Dict[str, Any]] = None,
        tools: Optional[list] = None,
        json_schema: Optional[Dict] = None,
        **kwargs,
    ) -> EngineResult:
        """Synchronní generování odpovědi."""
        ...

    def health(self) -> bool:
        """Kontrola dostupnosti engine."""
        return True

    def close(self) -> None:
        """Cleanup resources."""
        pass


# === Anthropic Engine ===

@EngineRegistry.register("anthropic")
class AnthropicEngine(InferenceEngine):
    """Anthropic Claude API engine."""

    engine_id = "anthropic"

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = 300.0,
        default_model: str = MODEL_SONNET,
    ):
        self.api_key = api_key or _get_api_key()
        self.timeout = timeout
        self.default_model = default_model
        self._client = None

    @property
    def client(self):
        """Lazy init klienta."""
        if self._client is None:
            import anthropic
            if not self.api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY není nastaven. "
                    "Nastavte env proměnnou nebo vytvořte .env soubor."
                )
            self._client = anthropic.Anthropic(
                api_key=self.api_key,
                timeout=self.timeout,
            )
        return self._client

    def generate(
        self,
        messages: Sequence[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        thinking: Optional[Dict[str, Any]] = None,
        tools: Optional[list] = None,
        json_schema: Optional[Dict] = None,
        cache_system: bool = False,
        **kwargs,
    ) -> EngineResult:
        """Zavolá Claude API a vrátí EngineResult."""
        model = resolve_model(model or self.default_model)

        call_kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": list(messages),
        }

        # System prompt (s volitelným cache_control)
        if system:
            if cache_system:
                call_kwargs["system"] = [{
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }]
            else:
                call_kwargs["system"] = system

        # Temperature (nenastavuj pokud thinking je zapnuté)
        if thinking:
            call_kwargs["thinking"] = thinking
        else:
            call_kwargs["temperature"] = temperature

        # Tools
        if tools:
            call_kwargs["tools"] = tools

        # Structured output
        if json_schema:
            # Anthropic nepoužívá json_schema přímo — řeší se přes tool_use
            # Pro teď přidáme instrukci do system promptu
            pass

        # Extra kwargs
        call_kwargs.update(kwargs)

        start = time.perf_counter()
        try:
            response = self.client.messages.create(**call_kwargs)
        except Exception as e:
            logger.error("Engine '%s' selhalo: %s", self.engine_id, e)
            raise

        elapsed = time.perf_counter() - start

        # Extrahovat obsah
        content = ""
        thinking_text = None
        for block in response.content:
            if block.type == "text":
                content = block.text
            elif block.type == "thinking":
                thinking_text = block.thinking

        # Usage
        usage = response.usage
        input_tokens = getattr(usage, "input_tokens", 0)
        output_tokens = getattr(usage, "output_tokens", 0)
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0

        result = EngineResult(
            content=content,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_creation_tokens=cache_creation,
            latency_seconds=elapsed,
            stop_reason=response.stop_reason,
            raw_response=response,
            thinking=thinking_text,
        )

        logger.debug(
            "Engine '%s' model=%s tokens=%d+%d cost=$%.4f latency=%.1fs",
            self.engine_id, model, input_tokens, output_tokens,
            result.cost_usd, elapsed,
        )
        return result

    def generate_stream(
        self,
        messages: Sequence[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        system: Optional[str] = None,
        max_tokens: int = 16000,
        thinking: Optional[Dict[str, Any]] = None,
        cache_system: bool = True,
        **kwargs,
    ) -> EngineResult:
        """Streaming varianta — sbírá tokeny a vrátí kompletní EngineResult.

        Pro use cases kde potřebujeme streaming (long responses, prompt caching).
        """
        model = resolve_model(model or self.default_model)

        call_kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": list(messages),
        }

        if system:
            if cache_system:
                call_kwargs["system"] = [{
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }]
            else:
                call_kwargs["system"] = system

        if thinking:
            call_kwargs["thinking"] = thinking

        call_kwargs.update(kwargs)

        start = time.perf_counter()
        content = ""
        thinking_text = None
        input_tokens = 0
        output_tokens = 0
        cache_read = 0
        cache_creation = 0
        stop_reason = None

        try:
            with self.client.messages.stream(**call_kwargs) as stream:
                for event in stream:
                    if hasattr(event, "type"):
                        if event.type == "content_block_delta":
                            delta = event.delta
                            if hasattr(delta, "text"):
                                content += delta.text
                            elif hasattr(delta, "thinking"):
                                thinking_text = (thinking_text or "") + delta.thinking

                # Finální message
                msg = stream.get_final_message()
                if msg:
                    usage = msg.usage
                    input_tokens = getattr(usage, "input_tokens", 0)
                    output_tokens = getattr(usage, "output_tokens", 0)
                    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
                    cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
                    stop_reason = msg.stop_reason

        except Exception as e:
            logger.error("Stream engine '%s' selhalo: %s", self.engine_id, e)
            raise

        elapsed = time.perf_counter() - start

        result = EngineResult(
            content=content,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_creation_tokens=cache_creation,
            latency_seconds=elapsed,
            stop_reason=stop_reason,
            thinking=thinking_text,
        )

        logger.debug(
            "Stream engine '%s' model=%s tokens=%d+%d cost=$%.4f latency=%.1fs",
            self.engine_id, model, input_tokens, output_tokens,
            result.cost_usd, elapsed,
        )
        return result

    def health(self) -> bool:
        try:
            return bool(self.api_key)
        except Exception:
            return False

    def close(self) -> None:
        self._client = None


# === Helpers ===

def _get_api_key() -> Optional[str]:
    """Získá API klíč z env nebo .env souboru."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key

    # Zkus .env v rootu projektu
    for candidate in [
        Path(__file__).resolve().parent.parent.parent / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]:
        if candidate.exists():
            for line in candidate.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


# === Singleton engine ===

_default_engine: Optional[AnthropicEngine] = None


def get_engine(
    engine_key: str = "anthropic",
    **kwargs,
) -> InferenceEngine:
    """Vrátí (cached) engine instanci.

    Pro jednoduché použití — většina kódu volá jen get_engine().generate(...).
    """
    global _default_engine

    if engine_key == "anthropic":
        if _default_engine is None:
            _default_engine = AnthropicEngine(**kwargs)
        return _default_engine

    return EngineRegistry.create(engine_key, **kwargs)
