"""Cost vs. quality experiment for the Fact-Checker (the per-student agent).

16 student-style beliefs with known answers (labels checked against the bundled BLS/O*NET data).
Each configuration judges all of them; we compare accuracy, grounding failures, tokens, cost, time.

    python scripts/eval_cost_quality.py            # writes logs/eval_results.json
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import agents, data  # noqa: E402

BENCH = [  # (O*NET id, claim, expected verdict)
    ("23-1011.00", "Most lawyers start out making over $200,000.", "myth"),
    ("23-1011.00", "You need more school than just college to be a lawyer.", "true"),
    ("15-1252.00", "Software developer jobs are growing faster than most jobs.", "true"),
    ("15-1252.00", "Coders work super long weeks, way over 40 hours.", "myth"),
    ("47-2111.00", "Electricians need a 4-year college degree.", "myth"),
    ("47-2111.00", "Electricians make less than $30,000 a year.", "myth"),
    ("29-1141.00", "Nurses have to deal with upset people a lot.", "true"),
    ("29-1131.00", "Vets only need a bachelor's degree.", "myth"),
    ("35-1011.00", "Chefs usually work long weeks, more than 40 hours.", "true"),
    ("53-2011.00", "Half of airline pilots make over $200,000.", "true"),
    ("25-2021.00", "Teachers have an easy schedule, under 40 hours a week.", "myth"),
    ("27-1024.00", "Graphic design jobs are booming.", "myth"),
    ("27-2021.00", "Pro athletes are all rich.", "myth"),
    ("29-1292.00", "Dental hygienists need a 4-year degree.", "myth"),
    ("33-3051.00", "Police officers spend a lot of time outdoors.", "true"),
    ("13-2011.00", "Accountants sit at a desk most of the day.", "true"),
]

CONFIGS = {
    "A: production (lean facts, effort=low)": {"lean": True, "effort": "low"},
    "B: no reasoning (lean, effort=none)": {"lean": True, "effort": "none"},
    "C: more reasoning (lean, effort=medium)": {"lean": True, "effort": "medium"},
    "D: full fact sheet (effort=low)": {"lean": False, "effort": "low"},
}
TRIALS = 2


async def judge(career_id: str, items: list[tuple[str, str]], lean: bool, effort: str, sem: asyncio.Semaphore):
    career = data.get(career_id)
    deps = agents.CareerDeps(career=career, facts=data.fact_sheet(career, lean=lean))
    claims = "\n".join(f"- {c}" for c, _ in items)
    async with sem:
        try:
            out, u = await agents.run_agent(
                agents.fact_checker, "Fact-Checker",
                f"Matched as: {career['title']}\n<student>\nClaims:\n{claims}\n</student>",
                deps=deps, effort=effort, cache_key=f"eval-{career_id}-{lean}")
        except Exception as exc:  # count a crash as all-wrong
            return [{"claim": c, "expected": e, "got": "error", "error": str(exc)[:120]} for c, e in items], None, []
    got = {v.claim.strip().lower().rstrip("."): v.verdict for v in out.verdicts}
    rows = []
    for (c, e), v in zip(items, out.verdicts + [None] * len(items)):
        verdict = got.get(c.strip().lower().rstrip("."), v.verdict if v else "missing")
        rows.append({"claim": c, "expected": e, "got": verdict})
    return rows, u, deps.rejections


async def run_config(name: str, cfg: dict) -> dict:
    sem = asyncio.Semaphore(8)
    by_career: dict[str, list] = {}
    for cid, claim, exp in BENCH:
        by_career.setdefault(cid, []).append((claim, exp))
    trials = []
    for t in range(TRIALS):
        started = time.perf_counter()
        results = await asyncio.gather(*[judge(cid, items, cfg["lean"], cfg["effort"], sem) for cid, items in by_career.items()])
        rows = [r for rs, _, _ in results for r in rs]
        usages = [u for _, u, _ in results if u]
        rejections = [x for _, _, rej in results for x in rej]
        exact = sum(r["got"] == r["expected"] for r in rows) / len(rows)
        lenient = sum((r["got"] == r["expected"]) or (r["got"] == "partly") for r in rows) / len(rows)
        trials.append({
            "trial": t + 1,
            "exact_accuracy": round(exact, 3),
            "lenient_accuracy": round(lenient, 3),
            "grounding_rejections": len(rejections),
            "input_tokens": sum(u["input_tokens"] for u in usages),
            "cached_tokens": sum(u["cached_tokens"] for u in usages),
            "output_tokens": sum(u["output_tokens"] for u in usages),
            "cost_usd": round(sum(u["cost_usd"] for u in usages), 6),
            "avg_seconds_per_call": round(statistics.mean(u["seconds"] for u in usages), 2) if usages else None,
            "wall_seconds": round(time.perf_counter() - started, 1),
            "calls": len(usages),
            "rows": rows,
            "rejections": rejections,
        })
        print(f"{name} trial {t+1}: exact {exact:.0%} lenient {lenient:.0%} cost ${trials[-1]['cost_usd']:.4f} "
              f"in {trials[-1]['input_tokens']} cached {trials[-1]['cached_tokens']} out {trials[-1]['output_tokens']}")
    return {"config": name, **cfg, "trials": trials}


async def main() -> None:
    out = []
    for name, cfg in CONFIGS.items():
        out.append(await run_config(name, cfg))
    path = Path(__file__).resolve().parents[1] / "logs" / "eval_results.json"
    path.write_text(json.dumps(out, indent=1))
    print("saved", path)


if __name__ == "__main__":
    asyncio.run(main())
