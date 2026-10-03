"""Client-side pacing for Gemini free-tier rate limits (requests per minute)."""

import asyncio
import time
from os import environ
from typing import Any

from google.genai import types

DEFAULT_MIN_INTERVAL_SECONDS = 13.0

_last_call = 0.0


async def pace_model_calls(callback_context: Any, llm_request: Any) -> None:
    """ADK ``before_model_callback`` that spaces model requests apart.

    Set ``MODEL_MIN_INTERVAL_SECONDS=0`` to disable on a paid tier.
    """
    global _last_call
    interval = float(environ.get("MODEL_MIN_INTERVAL_SECONDS", DEFAULT_MIN_INTERVAL_SECONDS))
    wait = _last_call + interval - time.monotonic()
    _last_call = max(time.monotonic(), _last_call + interval) if wait > 0 else time.monotonic()
    if wait > 0:
        await asyncio.sleep(wait)
    return None


def retry_config() -> types.GenerateContentConfig:
    """Retry transient 429/503 responses with backoff instead of failing the run."""
    return types.GenerateContentConfig(
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(
                attempts=6,
                initial_delay=15.0,
                max_delay=65.0,
                http_status_codes=[429, 503],
            )
        )
    )
