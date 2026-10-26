"""Input screening that runs before any agent sees the student's text.

Layer 1 (free, instant): length cap + regex for well-known injection phrasing.
Layer 2 (cheap LLM call): the Gatekeeper agent in agents.py classifies anything subtler.
"""

from __future__ import annotations

import re

from backend.config import MAX_INPUT_CHARS

INJECTION_PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above|earlier) (instructions|prompts|rules)",
    r"disregard (all |the )?(previous|prior|above) ",
    r"(reveal|show|print|repeat|leak) (me )?(your|the) (system )?(prompt|instructions|api key|key|secret)",
    r"\bsystem prompt\b",
    r"you are now (a|an|in) ",
    r"\b(developer|dan|jailbreak|god) mode\b",
    r"portkey|openai_api_key|\.env\b",
    r"<\s*/?\s*(script|system|instructions?)\b",
    r"act as (if you (are|were) )?(an? )?(unfiltered|unrestricted)",
]
_RX = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)


def prescreen(*texts: str) -> tuple[bool, str]:
    """Return (ok, reason). Blocks obvious attacks without spending a token."""
    joined = "\n".join(t or "" for t in texts)
    if not joined.strip():
        return False, "Tell me a career you're curious about first."
    if len(joined) > MAX_INPUT_CHARS:
        return False, f"That's a lot of text! Keep it under {MAX_INPUT_CHARS} characters so the agents stay focused."
    m = _RX.search(joined)
    if m:
        return False, f"blocked_injection:{m.group(0)}"
    return True, ""
