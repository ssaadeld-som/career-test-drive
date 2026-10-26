"""Settings, API key loading and the model factory.

The .env file is looked up in this repo first, then in the folder above it
(where the teaching staff keep theirs). Nothing here ever prints the key.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

REPO = Path(__file__).resolve().parents[1]
for folder in (REPO, REPO.parent):  # repo first, then one level up
    if (folder / ".env").exists():
        load_dotenv(folder / ".env", override=False)

DATA_FILE = REPO / "data" / "careers.json"
LOG_FILE = REPO / "logs" / "runs.jsonl"
CACHE_DIR = REPO / "cache"
PROMPTS = Path(__file__).resolve().parent / "prompts"

MODEL_NAME = os.getenv("MODEL_NAME", "gpt-6-luna")  # course key allows gpt-6-luna only
REASONING_EFFORT = os.getenv("REASONING_EFFORT", "low")

# Spending guard rails (USD). A run costs well under a cent, so these are generous.
SESSION_BUDGET_USD = float(os.getenv("SESSION_BUDGET_USD", "0.05"))
DAILY_BUDGET_USD = float(os.getenv("DAILY_BUDGET_USD", "2.00"))
RUNS_PER_HOUR = int(os.getenv("RUNS_PER_HOUR", "12"))
MAX_INPUT_CHARS = 1200


def api_settings() -> tuple[str, str, dict]:
    """Return (api_key, base_url, headers): Portkey if available, else plain OpenAI."""
    portkey = os.getenv("PORTKEY_API_KEY", "").strip()
    if portkey:
        return portkey, "https://api.portkey.ai/v1", {"x-portkey-provider": "openai"}
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_key:
        return openai_key, "https://api.openai.com/v1", {}
    raise RuntimeError(
        "No API key found. Put PORTKEY_API_KEY (or OPENAI_API_KEY) in a .env file in this "
        "folder or the folder above it. See .env.example."
    )


@lru_cache(maxsize=2)
def build_model(model_name: str = MODEL_NAME) -> OpenAIResponsesModel:
    key, base_url, headers = api_settings()
    client = AsyncOpenAI(api_key=key, base_url=base_url, default_headers=headers)
    return OpenAIResponsesModel(model_name, provider=OpenAIProvider(openai_client=client))


def model_settings(effort: str = REASONING_EFFORT, cache_key: str | None = None) -> OpenAIResponsesModelSettings:
    s: OpenAIResponsesModelSettings = {"openai_reasoning_effort": effort}  # type: ignore[typeddict-item]
    if cache_key:
        s["openai_prompt_cache_key"] = cache_key  # routes same-prefix calls to the same cache
    return s
