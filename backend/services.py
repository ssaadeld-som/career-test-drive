"""v2 agent services: Storyteller (per career), Field Guide (per field), Discover (Profiler + matcher + Advisor).

Story and Field Guide depend only on the career/field, so they are cached on disk and paid for once.
Discover is per student; it is budget-checked and logged like an exploration.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime

from backend import agents, data, extras
from backend.config import MODEL_NAME
from backend.grounding import allowed_numbers
from backend.guard import prescreen
from backend.pipeline import BUDGET, _cache_get, _cache_put, log_run

_locks: dict[str, asyncio.Lock] = {}


def _lock(key: str) -> asyncio.Lock:
    return _locks.setdefault(key, asyncio.Lock())


async def story(career_id: str) -> dict | None:
    c = data.get(career_id)
    if not c:
        return None
    async with _lock("story" + career_id):
        if hit := _cache_get("story", career_id):
            return {**hit, "cache_hit": True}
        deps = agents.CareerDeps(career=c, facts=data.fact_sheet(c, lean=False))
        out, u = await agents.run_agent(agents.storyteller, "Storyteller", f"Write the story for {c['title']}.",
                                        deps=deps, cache_key=f"story-{career_id}")
        res = out.model_dump()
        res["usage"] = {k: v for k, v in u.items() if k != "trace"}
        res["rejections"] = deps.rejections
        res["facts"] = {f["id"]: f["text"] for f in deps.facts if f["id"].startswith(("T", "C"))}
        _cache_put("story", career_id, res)
        log_run({"run_id": uuid.uuid4().hex[:10], "ts": datetime.now().isoformat(timespec="seconds"), "kind": "story",
                 "model": MODEL_NAME, "career_id": career_id, "status": "ok", "agents": [res["usage"]],
                 "totals": {k: u[k] for k in ("input_tokens", "cached_tokens", "output_tokens", "cost_usd")},
                 "rejections": deps.rejections})
        return {**res, "cache_hit": False}


async def field_guide(code: str) -> dict | None:
    eco = extras.ecosystem(code)
    if not eco:
        return None
    async with _lock("field" + code):
        if hit := _cache_get("field", code):
            return {**eco, **hit, "cache_hit": True}
        lines = []
        for r in eco["careers"]:
            desc = data.get(r["id"])["description"][:160]
            lines.append(f"{r['id']} | {r['title']} | {desc}")
        instr = agents.prompt("field_guide").replace("{field}", eco["name"]).replace("{roles}", "\n".join(lines))
        out, u = await agents.run_agent(agents.field_guide, "Field Guide", f"Explain every role in {eco['name']}.",
                                        instructions=instr, cache_key=f"field-{code}")
        res = {"intro": out.intro, "plain": {r.id: r.plain for r in out.roles},
               "usage": {k: v for k, v in u.items() if k != "trace"}}
        _cache_put("field", code, res)
        log_run({"run_id": uuid.uuid4().hex[:10], "ts": datetime.now().isoformat(timespec="seconds"), "kind": "field_guide",
                 "model": MODEL_NAME, "status": "ok", "agents": [res["usage"]],
                 "totals": {k: u[k] for k in ("input_tokens", "cached_tokens", "output_tokens", "cost_usd")}})
        return {**eco, **res, "cache_hit": False}


def _student_text(p: dict) -> str:
    parts = []
    for k, label in (("interests", "Hobbies/interests"), ("strengths", "Good at / enjoys"), ("subjects_like", "Likes subjects"),
                     ("subjects_dislike", "Dislikes subjects"), ("work_with", "Likes working with"), ("values", "Cares about")):
        if p.get(k):
            parts.append(f"{label}: {', '.join(p[k])}")
    for k, label in (("setting", "Prefers working"), ("activity", "Prefers a day that is"), ("max_school_years", "Years of school after HS willing"),
                     ("state", "Home state"), ("free_text", "In their words")):
        if p.get(k) not in (None, ""):
            parts.append(f"{label}: {p[k]}")
    return "\n".join(parts)


async def discover(p: dict, session: str) -> dict:
    run_id = uuid.uuid4().hex[:10]
    n = extras.signals(p)
    t = extras.tier(n)
    base = {"run_id": run_id, "signals": n, "tier": t}
    if t["name"] == "locked":
        return {**base, "status": "need_more"}
    if (msg := BUDGET.check(session)):
        return {**base, "status": "blocked", "message": msg}
    free = " ".join([p.get("free_text") or "", *p.get("interests", [])])
    ok, reason = prescreen(free or "ok")
    if not ok and reason.startswith("blocked_injection"):
        return {**base, "status": "blocked", "message": "That looks like an attempt to change how the app works. Tell us about yourself instead!"}
    BUDGET.start(session)
    usages = []
    student = _student_text(p)

    riasec, know, summary = None, None, ""
    if free.strip():
        gate, u = await agents.run_agent(agents.gatekeeper, "Gatekeeper", f"<student>\n{student}\n</student>", effort="low")
        usages.append(u)
        if gate.verdict == "block":
            return {**base, "status": "blocked", "message": gate.message_to_student, "usage": usages}
        read, u = await agents.run_agent(agents.profiler, "Profiler", f"<student>\n{student}\n</student>", effort="low")
        usages.append(u)
        riasec, know, summary = read.riasec.model_dump(), list(read.knowledge_areas), read.summary

    scored = extras.score_careers(p, riasec, know)
    picks = scored[: t["careers"]]
    fields = extras.top_fields(scored)

    facts_txt, allowed_src = [], []
    for r in picks:
        line = (f"[{r['id']}] {r['title']} | field: {r['vertical']} | median pay ${r['median']:,} | growth 2025-35 "
                f"{r['growth_pct']}% | entry education: {r['education']} | matched on: {'; '.join(r['reasons']) or 'overall profile'}")
        facts_txt.append(line)
        allowed_src.append(line)
    deps = agents.AdviceDeps(ids={r["id"] for r in picks}, allowed=allowed_numbers(allowed_src))
    instr = agents.prompt("advisor").replace("{student}", student).replace("{facts}", "\n".join(facts_txt))
    advice, u = await agents.run_agent(agents.advisor, "Advisor", "Explain these matches to the student.",
                                       deps=deps, instructions=instr, effort="low")
    usages.append(u)
    why = {pk.id: pk.why for pk in advice.picks}
    for r in picks:
        r["why"] = why.get(r["id"], "")
        c = data.get(r["id"])
        r["majors"] = [m["title"] for m in c.get("majors", [])[:3]]
        r["hs_subjects"] = c["hs_subjects"][:4]
    totals = {k: sum(x.get(k, 0) for x in usages) for k in ("input_tokens", "cached_tokens", "output_tokens", "requests")}
    totals["cost_usd"] = round(sum(x["cost_usd"] for x in usages), 6)
    BUDGET.charge(session, totals["cost_usd"])
    log_run({"run_id": run_id, "ts": datetime.now().isoformat(timespec="seconds"), "kind": "discover", "model": MODEL_NAME,
             "status": "ok", "signals": n, "tier": t["name"], "totals": totals,
             "agents": [{k: v for k, v in x.items() if k != "trace"} for x in usages], "rejections": deps.rejections})
    return {**base, "status": "ok", "summary": summary, "fields": fields, "careers": picks, "next_step": advice.next_step,
            "usage": [{k: v for k, v in x.items() if k != "trace"} for x in usages], "totals": totals,
            "rejections": deps.rejections}
