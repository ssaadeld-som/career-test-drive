"""Baseline: the same model WITHOUT our data (what a student gets from a plain chatbot).

Judges the same 16 beliefs with no fact sheet, then counts how many numbers it states that do not
match the official BLS/O*NET data.      python scripts/baseline_raw_llm.py
"""
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pydantic_ai import Agent
from backend import data
from backend.config import build_model, model_settings
from backend.grounding import allowed_numbers, unsupported
from backend.models import RealityCheck
from scripts.eval_cost_quality import BENCH

raw = Agent(output_type=RealityCheck, instructions=(
    "A student aged 12-18 shares beliefs about a career. For each claim give verdict true/partly/myth/no_data, "
    "a short headline and an explanation of at most 45 words with concrete numbers (salary, growth, hours) "
    "so the student learns the facts. fact_ids can be empty. surprises can be empty."))

async def one(cid, items):
    c = data.get(cid)
    claims = "\n".join(f"- {x}" for x, _ in items)
    r = await raw.run(f"Career: {c['title']}\nClaims:\n{claims}", model=build_model(), model_settings=model_settings("low"))
    allowed = allowed_numbers([f["text"] for f in data.fact_sheet(c, lean=False)])
    rows = []
    for (claim, exp), v in zip(items, r.output.verdicts):
        bad = unsupported(v.explanation, allowed)
        rows.append({"claim": claim, "expected": exp, "got": v.verdict, "explanation": v.explanation, "numbers_not_in_official_data": bad})
    return rows

async def main():
    by = {}
    for cid, cl, e in BENCH:
        by.setdefault(cid, []).append((cl, e))
    rows = [r for rs in await asyncio.gather(*[one(c, i) for c, i in by.items()]) for r in rs]
    acc = sum(r["got"] == r["expected"] for r in rows) / len(rows)
    with_bad = [r for r in rows if r["numbers_not_in_official_data"]]
    nums = sum(len(r["numbers_not_in_official_data"]) for r in rows)
    out = {"exact_accuracy": acc, "explanations_with_unverified_numbers": len(with_bad), "unverified_numbers": nums, "rows": rows}
    Path("logs/baseline_raw_llm.json").write_text(json.dumps(out, indent=1))
    print(f"accuracy {acc:.0%}; {len(with_bad)}/{len(rows)} explanations contain {nums} numbers not in official data")
    for r in with_bad[:6]:
        print(" -", r["claim"], "->", r["numbers_not_in_official_data"], "|", r["explanation"][:140])
asyncio.run(main())
