"""Tokenomics measurement: 10 cold runs (new careers), then 5 warm runs (same careers, new students).

    python scripts/measure_runs.py      # appends to logs/runs.jsonl, prints a summary
"""
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.pipeline import explore

COLD = [
    ("lawyer", "Lawyers argue in court every day and make $300k right out of school.", "debating"),
    ("nurse", "Nurses just do what doctors say. The pay is low.", "helping people"),
    ("electrician", "Electricians don't make much money and you don't need any school.", "fixing things"),
    ("video game designer", "Game designers play games all day and it's chill.", "drawing, games"),
    ("veterinarian", "Vets play with puppies all day. It's easier than medical school.", "animals"),
    ("teacher", "Teachers get summers off and work short days.", "kids, explaining things"),
    ("pilot", "Pilots are rich and the job is mostly sitting.", "travel"),
    ("chef", "Chefs get to be creative all day and work normal hours.", "cooking"),
    ("police officer", "Police officers are in car chases all the time.", "sports, helping"),
    ("accountant", "Accounting is boring and robots will replace it soon.", "math"),
]
WARM = [
    ("lawyer", "Lawyers are all rich and work at big firms.", "reading"),
    ("nurse", "Nurses only work in hospitals and need a 2-year degree.", "science"),
    ("electrician", "Electricians work outside in all weather.", ""),
    ("teacher", "Teachers make under $40,000.", ""),
    ("chef", "Chefs need culinary school.", "food"),
]

async def go(batch, label):
    async def emit(*_): pass
    rows = []
    for i, (c, b, l) in enumerate(batch):
        out = await explore(c, b, l, session=f"measure-{label}-{i}", emit=emit)
        t = out["totals"]
        rows.append(t)
        print(f"{label:5} {c:20} in={t['input_tokens']:6} cached={t['cached_tokens']:5} out={t['output_tokens']:5} req={t['requests']:2} ${t['cost_usd']:.5f}")
    n = len(rows)
    avg = {k: round(sum(r[k] for r in rows) / n, 6) for k in rows[0]}
    print(label, "AVERAGE", avg)
    return avg

async def main():
    res = {"cold": await go(COLD, "cold"), "warm": await go(WARM, "warm")}
    Path("logs/measure_summary.json").write_text(json.dumps(res, indent=1))
asyncio.run(main())
