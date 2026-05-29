"""
LLM Service — wraps Groq API (OpenAI-compatible).
Provides standard call, structured JSON call, and streaming.
"""

import asyncio
import json
import logging
from typing import AsyncGenerator

from openai import AsyncOpenAI, RateLimitError, APIStatusError

from core.config import settings

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM = (
    "You are DevBrain, an expert developer mentor and senior software engineer."
)


class LLMService:
    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            api_key=settings.XAI_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        )
        self.model = settings.GROK_MODEL

    # ------------------------------------------------------------------
    # Core call with exponential-backoff retry
    # ------------------------------------------------------------------

    async def call(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
    ) -> str:
        """
        Single-turn chat completion.
        Retries up to 3 times (2^attempt seconds back-off) on rate-limit
        or 429/529 status errors.
        """
        system_msg = system or _DEFAULT_SYSTEM
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ]

        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content or ""

            except RateLimitError as exc:
                last_exc = exc
                wait = 2 ** attempt
                logger.warning("Rate-limited by Groq API; retrying in %ds (attempt %d/3)", wait, attempt + 1)
                await asyncio.sleep(wait)

            except APIStatusError as exc:
                if exc.status_code in (429, 529):
                    last_exc = exc
                    wait = 2 ** attempt
                    logger.warning(
                        "API status %d; retrying in %ds (attempt %d/3)",
                        exc.status_code, wait, attempt + 1,
                    )
                    await asyncio.sleep(wait)
                else:
                    raise

        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Structured (JSON) call
    # ------------------------------------------------------------------

    async def structured_call(
        self,
        prompt: str,
        system: str = "",
    ) -> dict:
        """
        Returns a parsed JSON dict.
        Appends a strict JSON instruction to the prompt, strips fences,
        and retries once with a corrective prompt on parse failure.
        Raises ValueError with raw response if parsing fails twice.
        """
        json_prompt = (
            prompt
            + "\nIMPORTANT: Respond with ONLY valid JSON. "
            "No markdown, no explanation, just the JSON object."
        )

        raw = await self.call(json_prompt, system=system)
        parsed, error = self._try_parse(raw)
        if parsed is not None:
            return parsed

        logger.warning("First JSON parse failed (%s); retrying with corrective prompt.", error)
        corrective = (
            f"Your previous response could not be parsed as JSON.\n"
            f"Error: {error}\n"
            f"Raw response:\n{raw}\n\n"
            "Please return ONLY the corrected, valid JSON object — no explanation, no markdown."
        )
        raw2 = await self.call(corrective, system=system)
        parsed2, error2 = self._try_parse(raw2)
        if parsed2 is not None:
            return parsed2

        raise ValueError(
            f"LLM returned invalid JSON after two attempts.\nRaw response:\n{raw2}"
        )

    @staticmethod
    def _try_parse(text: str) -> tuple[dict | None, str]:
        """Strip optional ```json fences then parse. Returns (dict, '') or (None, err_msg)."""
        cleaned = text.strip()
        # Strip ```json ... ``` or ``` ... ```
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            # Drop first line (```json or ```) and last line (```)
            inner_lines = lines[1:] if lines[-1].strip() == "```" else lines[1:]
            if inner_lines and inner_lines[-1].strip() == "```":
                inner_lines = inner_lines[:-1]
            cleaned = "\n".join(inner_lines).strip()
        try:
            return json.loads(cleaned), ""
        except json.JSONDecodeError as exc:
            return None, str(exc)

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    async def stream(
        self,
        prompt: str,
        system: str = "",
    ) -> AsyncGenerator[str, None]:
        """
        Streams tokens from the API.
        Yields each non-empty text delta as a string.
        """
        system_msg = system or _DEFAULT_SYSTEM
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ]

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

llm = LLMService()