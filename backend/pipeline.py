"""Orchestrator: runs the agents in order, streams progress, enforces budgets, logs every run.

    prescreen (regex, free) -> Gatekeeper -> Scout -> [Fact-Checker || Test-Drive* || Pathway*]

* Test-Drive and Pathway depend only on the career, not the student, so their results are cached
  per career on disk. A second student asking about the same job pays only for the Gatekeeper,
  Scout and Fact-Checker.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections import defaultdict, deque
from datetime import date, datetime
from typing import Awaitable, Callable

from backend import agents, data
from backend.config import (CACHE_DIR, DAILY_BUDGET_USD, LOG_FILE, MODEL_NAME, RUNS_PER_HOUR,
                            SESSION_BUDGET_USD)
from backend.guard import prescreen

Emit = Callable[[str, dict], Awaitable[None]]


class Budget:
    """Per-session and daily spending caps plus a per-session rate limit (in memory)."""

    def __init__(self) -> None:
        self.session_spend: dict[str, float] = defaultdict(float)
        self.session_runs: dict[str, deque] = defaultdict(deque)
        self.day = date.today()
        self.day_spend = 0.0

    def check(self, session: str) -> str | None:
        if date.today() != self.day:
            self.day, self.day_spend = date.today(), 0.0
        runs = self.session_runs[session]
        while runs and time.time() - runs[0] > 3600:
            runs.popleft()
        if len(runs) >= RUNS_PER_HOUR:
            return f"You've explored {RUNS_PER_HOUR} careers this hour. Take a break and come back soon!"
        if self.session_spend[session] >= SESSION_BUDGET_USD:
            return "This session reached its spending limit. Refresh later to keep exploring."
        if self.day_spend >= DAILY_BUDGET_USD:
            return "The app reached today's budget. Please try again tomorrow."
        return None

    def charge(self, session: str, usd: float) -> None:
        self.session_spend[session] += usd
        self.day_spend += usd

    def start(self, session: str) -> None:
        self.session_runs[session].append(time.time())


BUDGET = Budget()


def _cache_path(kind: str, career_id: str):
    return CACHE_DIR / f"{kind}_{career_id}.json"


def _cache_get(kind: str, career_id: str) -> dict | None:
    p = _cache_path(kind, career_id)
    return json.loads(p.read_text()) if p.exists() else None


def _cache_put(kind: str, career_id: str, value: dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    _cache_path(kind, career_id).write_text(json.dumps(value))


def log_run(record: dict) -> None:
    LOG_FILE.parent.mkdir(exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def stage_wages(card: dict) -> dict:
    """Official wage band per stage. Percentiles stand in for seniority (stated in the UI)."""
    return {
        "entry": {"low": card["p10"], "high": card["p25"], "label": "10th–25th percentile"},
        "mid": {"low": card["p25"], "high": card["p75"], "label": "25th–75th percentile", "median": card["median"]},
        "senior": {"low": card["p75"], "high": card["p90"], "label": "75th–90th percentile"},
    }


async def explore(career_text: str, beliefs: str, likes: str, session: str, emit: Emit,
                  use_cache: bool = True, effort: str | None = None) -> dict:
    run_id = uuid.uuid4().hex[:10]
    usages: list[dict] = []
    record = {"run_id": run_id, "ts": datetime.now().isoformat(timespec="seconds"), "model": MODEL_NAME,
              "input": {"career": career_text, "beliefs": beliefs, "likes": likes}}

    async def finish(status: str, **extra) -> dict:
        totals = {k: sum(u.get(k, 0) for u in usages) for k in
                  ("input_tokens", "cached_tokens", "output_tokens", "reasoning_tokens", "requests", "tool_calls")}
        totals["cost_usd"] = round(sum(u["cost_usd"] for u in usages), 6)
        BUDGET.charge(session, totals["cost_usd"])
        out = {"run_id": run_id, "status": status, "usage": usages, "totals": totals, **extra}
        log_run({**record, "status": status, "totals": totals,
                 "agents": [{k: v for k, v in u.items() if k != "trace"} for u in usages],
                 "rejections": extra.get("rejections", []), "career_id": extra.get("career", {}).get("id")})
        await emit("done", out)
        return out

    # 0. Budget + free regex screen -------------------------------------------------
    if (msg := BUDGET.check(session)):
        await emit("blocked", {"layer": "budget", "message": msg})
        return await finish("blocked_budget", message=msg)
    ok, reason = prescreen(career_text, beliefs, likes)
    if not ok:
        injection = reason.startswith("blocked_injection")
        message = ("That looks like an attempt to change how the app works, so the agents never saw it. "
                   "Try telling us about a career instead!") if injection else reason
        await emit("blocked", {"layer": "regex", "message": message, "matched": reason})
        return await finish("blocked_regex", message=message, matched=reason)
    BUDGET.start(session)
    student = agents.wrap_student(("career", career_text), ("beliefs", beliefs), ("likes", likes))

    # 1. Gatekeeper ------------------------------------------------------------------
    await emit("agent", {"agent": "Gatekeeper", "state": "working", "note": "Screening your message"})
    gate, u = await agents.run_agent(agents.gatekeeper, "Gatekeeper", student, effort="low")
    usages.append(u)
    await emit("agent", {"agent": "Gatekeeper", "state": "done", "usage": u, "note": f"{gate.verdict} ({gate.category})"})
    if gate.verdict == "block":
        await emit("blocked", {"layer": "gatekeeper", "category": gate.category, "message": gate.message_to_student})
        return await finish("blocked_gatekeeper", message=gate.message_to_student, category=gate.category)

    # 2. Scout -----------------------------------------------------------------------
    await emit("agent", {"agent": "Scout", "state": "working", "note": "Searching 774 official occupations"})
    deps = agents.CareerDeps()
    scout, u = await agents.run_agent(agents.scout, "Scout", student, deps=deps, effort=effort)
    usages.append(u)
    career = data.get(scout.career_id)
    deps.career, deps.facts = career, data.fact_sheet(career)
    card = data.summary_card(career)
    await emit("agent", {"agent": "Scout", "state": "done", "usage": u, "note": f"Matched: {career['title']}"})
    await emit("career", {"career": card, "match_note": scout.match_note, "claims": scout.claims,
                          "wages": stage_wages(card), "facts": deps.facts})

    # 3. Three specialists in parallel ------------------------------------------------
    claims = "\n".join(f"- {c}" for c in scout.claims)
    likes_txt = ", ".join(scout.likes) or "not given"

    async def run_fact_checker():
        await emit("agent", {"agent": "Fact-Checker", "state": "working", "note": f"Checking {len(scout.claims)} beliefs"})
        fdeps = agents.CareerDeps(career=career, facts=deps.facts)
        out, u = await agents.run_agent(agents.fact_checker, "Fact-Checker",
                                        f"Matched as: {career['title']} ({scout.match_note})\n<student>\nClaims:\n{claims}\nLikes: {likes_txt}\n</student>",
                                        deps=fdeps, effort=effort, cache_key=f"fc-{career['id']}")
        u["rejections"] = fdeps.rejections
        usages.append(u)
        res = out.model_dump()
        await emit("agent", {"agent": "Fact-Checker", "state": "done", "usage": u,
                             "note": f"{len(fdeps.rejections)} grounding fixes" if fdeps.rejections else "All numbers verified"})
        await emit("reality", res)
        return res, fdeps.rejections

    async def run_cached(kind: str, agent, name: str, note: str):
        if use_cache and (hit := _cache_get(kind, career["id"])):
            u = {"agent": name, "requests": 0, "input_tokens": 0, "cached_tokens": 0, "output_tokens": 0,
                 "reasoning_tokens": 0, "tool_calls": 0, "seconds": 0, "cost_usd": 0.0, "cache_hit": True, "trace": []}
            usages.append(u)
            await emit("agent", {"agent": name, "state": "done", "usage": u, "note": "Reused (cached for this career)"})
            await emit(kind, hit)
            return hit, []
        await emit("agent", {"agent": name, "state": "working", "note": note})
        d = agents.CareerDeps(career=career, facts=deps.facts)
        out, u = await agents.run_agent(agent, name, f"Build this for {career['title']}.", deps=d,
                                        effort=effort, cache_key=f"{kind}-{career['id']}")
        u["rejections"] = d.rejections
        usages.append(u)
        res = out.model_dump()
        if kind == "pathway":
            res["neighbors"] = [{**n, "card": data.summary_card(data.get(n["career_id"]))} for n in res["neighbors"]]
        _cache_put(kind, career["id"], res)
        await emit("agent", {"agent": name, "state": "done", "usage": u, "note": "Done"})
        await emit(kind, res)
        return res, d.rejections

    results = await asyncio.gather(
        run_fact_checker(),
        run_cached("test_drive", agents.test_driver, "Test-Drive", "Writing 3 job moments from real tasks"),
        run_cached("pathway", agents.pathway, "Pathway", "Drawing your road map"),
        return_exceptions=True,
    )
    payload, rejections = {}, []
    for key, r in zip(("reality", "test_drive", "pathway"), results):
        if isinstance(r, Exception):
            await emit("agent", {"agent": key, "state": "error", "note": type(r).__name__})
            payload[key] = None
            rejections.append(f"{key} failed: {type(r).__name__}: {str(r)[:160]}")
        else:
            payload[key], rej = r
            rejections.extend(rej)
    return await finish("ok", career=card, match_note=scout.match_note, claims=scout.claims,
                        rejections=rejections, wages=stage_wages(card), **payload)
