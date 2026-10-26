"""Anti-hallucination check: every number an agent writes must exist in the fact sheet.

Used as a pydantic-ai output validator. If an agent invents a statistic (say
"lawyers make $300k"), the validator rejects the answer and sends it back with
the list of unsupported numbers (one retry). The run log records each rejection.
"""

from __future__ import annotations

import re

NUM = re.compile(r"\$?\d[\d,]*(?:\.\d+)?\s*(?:k|K|%|percent)?")
ALWAYS_OK = {2024.0, 2025.0, 2034.0, 2035.0, 40.0, 1.0, 2.0, 3.0, 4.0, 5.0}  # years, "40-hour week", Job Zone scale


def _values(text: str) -> list[float]:
    out = []
    for m in NUM.finditer(text):
        raw = m.group(0).strip()
        mult = 1000 if raw.lower().endswith("k") else 1
        digits = re.sub(r"[^\d.]", "", raw)
        if digits and digits != ".":
            try:
                out.append(float(digits) * mult)
            except ValueError:
                pass
    return out


def allowed_numbers(fact_texts: list[str]) -> set[float]:
    vals = set(ALWAYS_OK)
    for t in fact_texts:
        vals.update(_values(t))
    return vals


def _grounded(v: float, allowed: set[float]) -> bool:
    for a in allowed:
        if a == 0:
            continue
        if abs(v - a) / a <= 0.02:  # rounding ("$151K" vs $151,160)
            return True
        if a >= 1000 and abs(v * 1000 - a) / a <= 0.02:  # "151" meaning thousands
            return True
    return v in allowed


def unsupported(text: str, allowed: set[float]) -> list[str]:
    """Return the numbers in `text` that are not backed by any fact."""
    bad = []
    for m in NUM.finditer(text):
        vals = _values(m.group(0))
        if vals and not _grounded(vals[0], allowed):
            bad.append(m.group(0).strip())
    return bad
