"""gpt-6-luna prices, USD per 1M tokens (OpenAI standard tier, as used in MGT 409 Lecture 11)."""

from __future__ import annotations

PRICES = {
    "gpt-6-luna": {"input": 0.10, "cached_input": 0.01, "output": 0.50},
}


def cost_usd(model: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> float:
    """Cached tokens are a subset of input tokens; reasoning tokens are inside output tokens."""
    p = PRICES.get(model, PRICES["gpt-6-luna"])
    cached = min(cached_tokens, input_tokens)
    return ((input_tokens - cached) * p["input"] + cached * p["cached_input"] + output_tokens * p["output"]) / 1e6
