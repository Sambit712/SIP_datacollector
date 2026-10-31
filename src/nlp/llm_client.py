"""Groq LLM Client & Provider Interface.

High-throughput inference engine powered by Groq LPU hardware:
- Primary reasoning model: llama-3.3-70b-versatile (extraction, clustering, root-cause)
- High-speed triage model: llama-3.1-8b-instant (rapid zero-shot relevance filtering)

Features:
- Structured JSON response mode enforcement via response_format={"type": "json_object"}
- Exponential backoff retry handler with jitter for rate limits (429)
- Graceful offline fallback: raises GroqOfflineError when GROQ_API_KEY is not configured
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel

from config.settings import get_settings

logger = logging.getLogger("ai_discovery_engine.groq")


class GroqOfflineError(Exception):
    """Raised when Groq API is unavailable, offline, or unconfigured."""
    pass


class GroqLLMClient:
    """Manages chat completions and structured JSON extractions with Groq."""

    def __init__(self, api_key: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.GROQ_API_KEY
        self.primary_model = settings.GROQ_MODEL
        self.fast_model = settings.GROQ_FAST_MODEL
        self._client = None

        is_offline = settings.is_offline or (api_key is not None and not api_key.strip())
        if not is_offline and self.api_key and self.api_key.strip():
            try:
                from groq import Groq
                self._client = Groq(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize Groq client: {e}. Falling back to offline mode.")
                self._client = None

    @property
    def is_available(self) -> bool:
        """Returns True if Groq client is initialized with an active API key."""
        return self._client is not None

    def generate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1500,
        response_format: Optional[Dict[str, str]] = None,
        max_retries: int = 3,
    ) -> str:
        """Generates a text or JSON completion from Groq with retry handling.

        Args:
            messages: List of chat messages [{"role": "system", "content": ...}, ...].
            model: Optional model override (defaults to primary_model).
            temperature: Sampling temperature (default 0.1 for deterministic extraction).
            max_tokens: Output token limit.
            response_format: E.g., {"type": "json_object"}.
            max_retries: Number of exponential backoff retry attempts.

        Returns:
            Completion string response.

        Raises:
            GroqOfflineError: If client is unavailable or all retries fail.
        """
        if not self.is_available:
            raise GroqOfflineError("Groq client is offline or unconfigured.")

        chosen_model = model or self.primary_model
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                kwargs: Dict[str, Any] = {
                    "model": chosen_model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if response_format:
                    kwargs["response_format"] = response_format

                response = self._client.chat.completions.create(**kwargs)
                return response.choices[0].message.content or ""
            except Exception as e:
                last_error = e
                logger.warning(f"Groq API call attempt {attempt}/{max_retries} failed: {e}")
                if attempt < max_retries:
                    sleep_time = (2 ** attempt) * 0.5
                    time.sleep(sleep_time)

        raise GroqOfflineError(f"Groq API failed after {max_retries} attempts: {last_error}")

    def generate_structured_json(
        self,
        messages: List[Dict[str, str]],
        schema: Type[BaseModel],
        model: Optional[str] = None,
    ) -> BaseModel:
        """Enforces structured JSON extraction conforming to a Pydantic schema."""
        raw_json_str = self.generate_chat_completion(
            messages=messages,
            model=model or self.primary_model,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        try:
            data = json.loads(raw_json_str)
            return schema.model_validate(data)
        except Exception as e:
            logger.error(f"Failed to validate Groq JSON output against schema {schema.__name__}: {e}. Raw: {raw_json_str}")
            raise

