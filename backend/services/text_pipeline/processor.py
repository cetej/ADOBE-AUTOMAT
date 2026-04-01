"""ClaudeProcessor base class — adapted from NG-ROBOT claude_processor.py.

Provides streaming API calls with adaptive thinking, prompt caching,
structured outputs, and server-side tools (web_search, web_fetch, code_execution).

Refactored: používá core.engine Engine abstrakci pro LLM volání.
"""

import os
import re
import json
import logging
import uuid
import time
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from core.engine import MODEL_OPUS, MODEL_SONNET, MODEL_HAIKU, get_engine, _estimate_cost
from core.traces import Trace, TraceCollector, get_trace_store

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Výsledek zpracování jedné fáze."""
    success: bool
    content: str
    tokens_used: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    error: Optional[str] = None
    artifacts: Dict[str, str] = field(default_factory=dict)
    truncated: bool = False
    web_searches: list = field(default_factory=list)


class ClaudeProcessor:
    """Procesor pro volání Claude API s prompty z projektů.

    Používá core.engine Engine abstrakci — sjednocený přístup k LLM.
    Zachovává zpětnou kompatibilitu (self.client pro streaming).
    """

    DEFAULT_MODEL = MODEL_SONNET
    MAX_TOKENS = 16000
    EFFORT = "medium"
    DISABLE_THINKING = False

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        if api_key:
            self.api_key = api_key
        else:
            self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")

        self.model = model or self.DEFAULT_MODEL

        # Engine abstrakce — používáme client pro streaming, store pro trace
        self._engine = get_engine()
        self._trace_store = get_trace_store()
        self._trace_module = self.__class__.__name__

        # Přímý klient pro streaming (potřebujeme granulární kontrolu nad
        # stream events — text_stream, web_search blocks, thinking)
        self.client = self._engine.client

        self._prompt_cache: Dict[str, str] = {}

    def is_available(self) -> bool:
        return self._engine.health()

    def _record_trace(
        self, input_tokens: int, output_tokens: int,
        cache_read: int = 0, cache_write: int = 0,
        latency: float = 0.0, success: bool = True, error: str = None,
    ) -> None:
        """Zaznamená trace do TraceStore."""
        try:
            self._trace_store.record(Trace(
                trace_id=str(uuid.uuid4())[:12],
                timestamp=datetime.utcnow().isoformat() + "Z",
                module=self._trace_module,
                model=self.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read,
                cache_creation_tokens=cache_write,
                latency_seconds=latency,
                cost_usd=_estimate_cost(self.model, input_tokens, output_tokens, cache_read, cache_write),
                success=success,
                error=error,
            ))
        except Exception as e:
            logger.warning("Trace zápis selhal: %s", e)

    def load_project_prompt(self, project_dir: Path) -> str:
        """Načte prompt z projektové složky (MASTER > INSTRUCTION > README)."""
        cache_key = str(project_dir)
        if cache_key in self._prompt_cache:
            return self._prompt_cache[cache_key]

        if not project_dir.exists():
            return ""

        # 1. MASTER soubory — nejnovější verze
        master_files = list(project_dir.glob("*MASTER*.md"))
        if master_files:
            def extract_version(f):
                match = re.search(r'v?(\d+)\.(\d+)\.(\d+)', f.name)
                if match:
                    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
                return (0, 0, 0)

            master_files.sort(key=extract_version, reverse=True)
            selected_file = master_files[0]
            content = selected_file.read_text(encoding='utf-8')
            self._prompt_cache[cache_key] = content
            return content

        # 2. INSTRUCTION nebo MAIN
        for pattern in ["*INSTRUCTION*.md", "*MAIN*.md"]:
            files = list(project_dir.glob(pattern))
            if files:
                content = files[0].read_text(encoding='utf-8')
                self._prompt_cache[cache_key] = content
                return content

        # 3. README nebo první .md
        for pattern in ["README.md", "*.md"]:
            files = list(project_dir.glob(pattern))
            if files:
                content = files[0].read_text(encoding='utf-8')
                self._prompt_cache[cache_key] = content
                return content

        return ""

    def process(
        self,
        content: str,
        system_prompt: str,
        user_instruction: Optional[str] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[list] = None,
        json_schema: Optional[dict] = None,
        disable_thinking: bool = False
    ) -> ProcessingResult:
        """Zpracuje obsah pomocí Claude API se streaming."""
        if not self.is_available():
            return ProcessingResult(
                success=False, content="",
                error="Claude API není dostupné. Nastavte ANTHROPIC_API_KEY."
            )

        user_message = content
        if user_instruction:
            user_message = f"{user_instruction}\n\n---\n\n{content}"

        try:
            _t_start = time.perf_counter()

            result_content = ""
            input_tokens = 0
            output_tokens = 0
            cache_read = 0
            cache_write = 0
            stop_reason = None

            efficiency_hint = "\n\n[EFFICIENCY] Respond directly and concisely. Use extended thinking only when it meaningfully improves quality for multi-step reasoning."
            system_with_hint = system_prompt + efficiency_hint

            stream_kwargs = {
                "model": self.model,
                "max_tokens": max_tokens or self.MAX_TOKENS,
                "system": [
                    {
                        "type": "text",
                        "text": system_with_hint,
                        "cache_control": {"type": "ephemeral"}
                    }
                ],
                "messages": [{"role": "user", "content": user_message}],
            }

            # Thinking configuration
            should_think = (self.model in (MODEL_OPUS, MODEL_SONNET)
                           and not disable_thinking
                           and not self.DISABLE_THINKING)
            if should_think:
                stream_kwargs["thinking"] = {"type": "adaptive"}
                stream_kwargs["output_config"] = {"effort": self.EFFORT}
            elif self.model in (MODEL_OPUS, MODEL_SONNET):
                stream_kwargs["thinking"] = {"type": "disabled"}

            # Structured outputs
            if json_schema:
                output_config = stream_kwargs.get("output_config", {})
                output_config["format"] = {
                    "type": "json_schema",
                    "schema": json_schema
                }
                stream_kwargs["output_config"] = output_config

            if tools:
                stream_kwargs["tools"] = tools

            with self.client.messages.stream(**stream_kwargs) as stream:
                for text in stream.text_stream:
                    result_content += text

                final_message = stream.get_final_message()
                input_tokens = final_message.usage.input_tokens
                output_tokens = final_message.usage.output_tokens
                stop_reason = final_message.stop_reason

                # Web search protocol
                _web_searches = []
                try:
                    for block in final_message.content:
                        bt = getattr(block, 'type', 'unknown')
                        if bt == 'server_tool_use' and getattr(block, 'name', '') == 'web_search':
                            query = getattr(block, 'input', {}).get('query', '?')
                            _web_searches.append(query)
                except Exception:
                    pass

                # Cache stats
                try:
                    cache_read = getattr(final_message.usage, 'cache_read_input_tokens', 0)
                    cache_write = getattr(final_message.usage, 'cache_creation_input_tokens', 0)
                    if cache_read or cache_write:
                        logger.info(f"Cache: read={cache_read}, write={cache_write}")
                except Exception:
                    pass

            was_truncated = stop_reason == "max_tokens"
            if was_truncated:
                logger.warning(f"Odpověď dosáhla limitu {max_tokens or self.MAX_TOKENS} tokenů")

            # Strip leaked thinking artefacts (Sonnet 4.6 thinking:adaptive leaks CoT)
            if '<antml' in result_content or '<thinking>' in result_content:
                result_content = re.sub(r'<antml[^>]*>.*?</antml[^>]*>', '', result_content, flags=re.DOTALL)
                result_content = re.sub(r'<thinking>.*?</thinking>', '', result_content, flags=re.DOTALL)
                result_content = result_content.strip()

            # Strip tool call transcripts
            if '<tool_call>' in result_content or '<tool_response>' in result_content:
                result_content = re.sub(r'<tool_call>.*?</tool_call>', '', result_content, flags=re.DOTALL)
                result_content = re.sub(r'<tool_response>.*?</tool_response>', '', result_content, flags=re.DOTALL)
                result_content = result_content.strip()

            # Zaznamenat trace
            _elapsed = _time.perf_counter() - _t_start
            self._record_trace(
                input_tokens, output_tokens,
                cache_read or 0, cache_write or 0,
                _elapsed, success=True,
            )

            return ProcessingResult(
                success=True,
                content=result_content,
                tokens_used=input_tokens + output_tokens,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                truncated=was_truncated,
                web_searches=_web_searches
            )

        except anthropic.APIError as e:
            self._record_trace(0, 0, latency=time.perf_counter() - _t_start, success=False, error=str(e))
            return ProcessingResult(success=False, content="", error=f"API chyba: {e}")
        except Exception as e:
            self._record_trace(0, 0, latency=time.perf_counter() - _t_start, success=False, error=str(e))
            return ProcessingResult(success=False, content="", error=f"Neočekávaná chyba: {e}")

    def process_with_project(
        self,
        content: str,
        project_dir: Path,
        additional_instruction: Optional[str] = None,
        tools: Optional[list] = None,
        json_schema: Optional[dict] = None,
        disable_thinking: bool = False
    ) -> ProcessingResult:
        """Zpracuje obsah pomocí promptů z projektové složky."""
        system_prompt = self.load_project_prompt(project_dir)
        if not system_prompt:
            return ProcessingResult(
                success=False, content="",
                error=f"Nepodařilo se načíst prompty z {project_dir}"
            )

        return self.process(
            content=content,
            system_prompt=system_prompt,
            user_instruction=additional_instruction,
            tools=tools,
            json_schema=json_schema,
            disable_thinking=disable_thinking
        )
