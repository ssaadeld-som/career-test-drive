"""Career data: loading, fuzzy search, and numbered fact sheets the agents must cite.

Every number a student sees comes from here (O*NET 31.0 + BLS), never from the model.
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from functools import lru_cache

from backend.config import DATA_FILE

SOURCES = {
    "W": "BLS Occupational Employment & Wage Statistics, May 2024",
    "O": "BLS Employment Projections 2025–35",
    "T": "O*NET 31.0 task list",
    "C": "O*NET 31.0 work context survey",
    "P": "O*NET 31.0 worker profile",
}


@lru_cache(maxsize=1)
def careers() -> dict[str, dict]:
    return {c["id"]: c for c in json.loads(DATA_FILE.read_text(encoding="utf-8"))}


def get(career_id: str) -> dict | None:
    return careers().get(career_id)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower()).strip()


@lru_cache(maxsize=1)
def _index() -> list[tuple[str, str, str]]:
    rows = []
    for c in careers().values():
        rows.append((c["id"], c["title"], _norm(c["title"])))
        for t in c["alt_titles"]:
            rows.append((c["id"], t, _norm(t)))
    return rows


def search(query: str, k: int = 8) -> list[dict]:
    """Rank careers by how well `query` matches their official or alternate job titles."""
    q = _norm(query)
    if not q:
        return []
    q_words = set(q.split())
    best: dict[str, tuple[float, str]] = {}
    for cid, label, norm in _index():
        words = set(norm.split())
        overlap = len(q_words & words) / max(len(q_words), 1)
        score = overlap + SequenceMatcher(None, q, norm).ratio()
        if q == norm:
            score += 2
        elif q in norm or norm in q:
            score += 0.6
        if score > best.get(cid, (0, ""))[0]:
            best[cid] = (score, label)
    ranked = sorted(best.items(), key=lambda kv: kv[1][0], reverse=True)[:k]
    return [
        {"id": cid, "title": careers()[cid]["title"], "matched_on": label, "score": round(s, 2)}
        for cid, (s, label) in ranked
    ]


def money(v: int | None) -> str:
    return "n/a" if v is None else f"${v:,}"


def fact_sheet(c: dict, lean: bool = True) -> list[dict]:
    """Numbered facts for one career. `lean` trims list lengths to cut input tokens."""
    facts: list[dict] = []

    def add(prefix: str, text: str) -> None:
        n = sum(f["id"].startswith(prefix) for f in facts) + 1
        facts.append({"id": f"{prefix}{n}", "text": text, "source": SOURCES[prefix]})

    w = c.get("wages_2024")
    if w:
        top = " (BLS top-codes wages at $239,200, so the real figure may be higher)" if w["p90"] == w["top_coded_at"] else ""
        add("W", f"Median annual wage: {money(w['median'])}")
        add("W", f"10th percentile (typical of early-career / lowest-paid): {money(w['p10'])}")
        add("W", f"25th percentile: {money(w['p25'])}")
        add("W", f"75th percentile: {money(w['p75'])}")
        add("W", f"90th percentile (top earners): {money(w['p90'])}{top}")
        add("W", f"People employed in this job (2024): {w['employment']:,}" if w.get("employment") else "Employment: n/a")
    o = c.get("outlook")
    if o:
        add("O", f"Projected job growth 2025–2035: {o['change_pct_2025_35']}% (all US jobs: 3.5%)")
        add("O", f"Average job openings per year 2025–2035: {o['openings_per_year']:,}")
        add("O", f"Typical education needed to enter: {o['typical_entry_education'] or 'n/a'}")
        add("O", f"Work experience needed in a related job: {o['work_experience'] or 'None'}")
        add("O", f"On-the-job training needed: {o['on_the_job_training'] or 'None'}")
        add("O", f"Share who are self-employed: {o['self_employed_pct']}%")
    for t in c["tasks"][: 8 if lean else 14]:
        add("T", f"Task: {t}")
    for k, v in c["work_context"].items():
        add("C", f"{k}: {v}")
    if "pct_over_40_hours" in c:
        add("C", f"Share of workers whose typical week is over 40 hours: {c['pct_over_40_hours']:.0f}%")
    if c.get("education_mix"):
        mix = ", ".join(f"{k} {v:.0f}%" for k, v in c["education_mix"].items())
        add("P", f"Education level of current workers (survey): {mix}")
    add("P", "Work styles that matter most: " + ", ".join(c["work_styles"]))
    add("P", "Most important skills: " + ", ".join(c["skills"]))
    add("P", "Most important knowledge areas: " + ", ".join(c["knowledge"]))
    top3 = sorted(c["interests"].items(), key=lambda kv: kv[1], reverse=True)[:3]
    add("P", "Strongest interest types (Holland code): " + ", ".join(k for k, _ in top3))
    if c.get("job_zone"):
        add("P", f"O*NET preparation level (Job Zone 1–5): {c['job_zone']}")
    return facts


def render(facts: list[dict]) -> str:
    return "\n".join(f"[{f['id']}] {f['text']}" for f in facts)


def summary_card(c: dict) -> dict:
    """Compact numbers the UI shows for a career (used for neighbors too)."""
    w, o = c.get("wages_2024") or {}, c.get("outlook") or {}
    return {
        "id": c["id"],
        "title": c["title"],
        "median": w.get("median"),
        "p10": w.get("p10"),
        "p25": w.get("p25"),
        "p75": w.get("p75"),
        "p90": w.get("p90"),
        "top_coded": w.get("p90") == w.get("top_coded_at"),
        "growth_pct": o.get("change_pct_2025_35"),
        "openings": o.get("openings_per_year"),
        "education": o.get("typical_entry_education"),
        "experience": o.get("work_experience"),
        "training": o.get("on_the_job_training"),
        "employment": w.get("employment"),
        "pct_over_40_hours": c.get("pct_over_40_hours"),
        "work_context": c["work_context"],
        "work_styles": c["work_styles"],
        "interests": c["interests"],
        "description": c["description"],
        "onet_url": f"https://www.onetonline.org/link/summary/{c['id']}",
    }
