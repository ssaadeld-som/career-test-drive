"""The five agents of Career Test Drive.

Gatekeeper  -> screens the student's text (safety)
Scout       -> finds the official occupation with the search_careers tool, splits beliefs into claims
Fact-Checker-> judges each claim against the numbered fact sheet (grounded numbers only)
Test-Drive  -> writes three decision scenarios built on real O*NET tasks
Pathway     -> draws HS -> degree -> license -> entry/mid/senior, picks neighbors via lookup_related

Each agent has a typed output, a hard UsageLimits cap, and (where it writes facts) an output
validator that rejects invented numbers and sends the agent back for one retry.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.messages import RetryPromptPart, ToolCallPart, ToolReturnPart
from pydantic_ai.usage import UsageLimits

from backend import data
from backend.config import MODEL_NAME, PROMPTS, build_model, model_settings
from backend.grounding import allowed_numbers, unsupported
from backend.models import (Advice, FieldGuide, GateDecision, Pathway, ProfileRead, RealityCheck, ScoutResult,
                            Story, TestDrive)
from backend.pricing import cost_usd

LIMITS = {
    "Gatekeeper": UsageLimits(request_limit=2, total_tokens_limit=4_000),
    "Scout": UsageLimits(request_limit=6, tool_calls_limit=3, total_tokens_limit=20_000),
    "Fact-Checker": UsageLimits(request_limit=3, total_tokens_limit=20_000),
    "Test-Drive": UsageLimits(request_limit=3, total_tokens_limit=24_000),
    "Pathway": UsageLimits(request_limit=4, tool_calls_limit=2, total_tokens_limit=24_000),
    "Storyteller": UsageLimits(request_limit=3, total_tokens_limit=24_000),
    "Field Guide": UsageLimits(request_limit=3, total_tokens_limit=40_000),
    "Profiler": UsageLimits(request_limit=2, total_tokens_limit=6_000),
    "Advisor": UsageLimits(request_limit=3, total_tokens_limit=24_000),
}


def prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def wrap_student(*parts: tuple[str, str]) -> str:
    """Student text goes inside <student> tags so agents treat it as data."""
    body = "\n".join(f"{k}: {v.strip()}" for k, v in parts if v and v.strip())
    return f"<student>\n{body}\n</student>"


@dataclass
class CareerDeps:
    career: dict | None = None
    facts: list[dict] = field(default_factory=list)
    seen_ids: set[str] = field(default_factory=set)
    rejections: list[str] = field(default_factory=list)

    @property
    def fact_ids(self) -> set[str]:
        return {f["id"] for f in self.facts}

    @property
    def allowed(self) -> set[float]:
        return allowed_numbers([f["text"] for f in self.facts])


# ---------------------------------------------------------------- Gatekeeper
gatekeeper = Agent(output_type=GateDecision, instructions=prompt("gatekeeper"), name="Gatekeeper")

# ---------------------------------------------------------------- Scout
scout = Agent(deps_type=CareerDeps, output_type=ScoutResult, instructions=prompt("scout"), name="Scout", retries=1)


@scout.tool
def search_careers(ctx: RunContext[CareerDeps], words: str) -> list[dict]:
    """Search 774 official occupations (O*NET) by job title or nickname. Returns the 8 best matches."""
    hits = data.search(words, k=8)
    ctx.deps.seen_ids.update(h["id"] for h in hits)
    return [{"id": h["id"], "title": h["title"], "matched_on": h["matched_on"],
             "about": data.get(h["id"])["description"][:120]} for h in hits]


@scout.output_validator
def _scout_ok(ctx: RunContext[CareerDeps], out: ScoutResult) -> ScoutResult:
    if out.career_id not in ctx.deps.seen_ids or data.get(out.career_id) is None:
        ctx.deps.rejections.append(f"Scout picked unknown id {out.career_id}")
        raise ModelRetry("career_id must be one of the ids returned by search_careers. Search again if needed.")
    return out


# ---------------------------------------------------------------- Fact-Checker
fact_checker = Agent(deps_type=CareerDeps, output_type=RealityCheck, name="Fact-Checker", retries=1)


@fact_checker.instructions
def _fc_instructions(ctx: RunContext[CareerDeps]) -> str:
    return prompt("fact_checker").replace("{title}", ctx.deps.career["title"]).replace("{facts}", data.render(ctx.deps.facts))


@fact_checker.output_validator
def _fc_ok(ctx: RunContext[CareerDeps], out: RealityCheck) -> RealityCheck:
    allowed, ids = ctx.deps.allowed, ctx.deps.fact_ids
    problems = []
    for v in out.verdicts + out.surprises:
        bad = unsupported(v.explanation + " " + v.headline, allowed)
        unknown = [i for i in v.fact_ids if i not in ids]
        if bad:
            problems.append(f"'{v.claim[:40]}': numbers not in FACTS: {bad}")
        if unknown:
            problems.append(f"'{v.claim[:40]}': unknown fact ids {unknown}")
        if v.verdict != "no_data" and not v.fact_ids:
            problems.append(f"'{v.claim[:40]}': verdict needs fact_ids")
    if not problems:
        return out
    ctx.deps.rejections.extend(problems)
    if ctx.retry < 1:
        raise ModelRetry("Fix these and answer again. Use only numbers from FACTS:\n" + "\n".join(problems))
    # Second strike: never show an unverified number — downgrade the offending cards instead.
    for v in out.verdicts + out.surprises:
        if unsupported(v.explanation + " " + v.headline, allowed) or any(i not in ids for i in v.fact_ids):
            v.verdict, v.fact_ids = "no_data", []
            v.headline = "We couldn't verify this one"
            v.explanation = "Our checker could not back this up with official data, so we are not showing a number."
    out.surprises = [s for s in out.surprises if s.verdict != "no_data"]
    return out


# ---------------------------------------------------------------- Test-Drive
test_driver = Agent(deps_type=CareerDeps, output_type=TestDrive, name="Test-Drive", retries=1)


@test_driver.instructions
def _td_instructions(ctx: RunContext[CareerDeps]) -> str:
    return prompt("test_drive").replace("{title}", ctx.deps.career["title"]).replace("{facts}", data.render(ctx.deps.facts))


@test_driver.output_validator
def _td_ok(ctx: RunContext[CareerDeps], out: TestDrive) -> TestDrive:
    problems = []
    for s in out.scenarios:
        if s.task_id not in ctx.deps.fact_ids or not s.task_id.startswith("T"):
            problems.append(f"scenario '{s.title}' must use a real T-id, got {s.task_id}")
        bad = unsupported(s.situation + " " + s.pro_insight, ctx.deps.allowed | set(map(float, range(0, 13))))
        if bad:
            problems.append(f"scenario '{s.title}' has numbers not in FACTS: {bad}")
        if not any(c.aligned for c in s.choices):
            problems.append(f"scenario '{s.title}' needs at least one aligned choice")
    if problems and ctx.retry < 1:
        ctx.deps.rejections.extend(problems)
        raise ModelRetry("Fix these:\n" + "\n".join(problems))
    return out


# ---------------------------------------------------------------- Pathway
pathway = Agent(deps_type=CareerDeps, output_type=Pathway, name="Pathway", retries=1)


@pathway.instructions
def _pw_instructions(ctx: RunContext[CareerDeps]) -> str:
    return prompt("pathway").replace("{title}", ctx.deps.career["title"]).replace("{facts}", data.render(ctx.deps.facts))


@pathway.tool
def lookup_related(ctx: RunContext[CareerDeps]) -> list[dict]:
    """List related occupations with their median wage, growth and entry education (official data)."""
    out = []
    for r in ctx.deps.career["related"]:
        c = data.get(r["id"])
        if not c:
            continue
        card = data.summary_card(c)
        ctx.deps.seen_ids.add(r["id"])
        out.append({k: card[k] for k in ("id", "title", "median", "growth_pct", "education")})
    return out


@pathway.output_validator
def _pw_ok(ctx: RunContext[CareerDeps], out: Pathway) -> Pathway:
    related = {r["id"] for r in ctx.deps.career["related"]}
    bad = [n.career_id for n in out.neighbors if n.career_id not in related]
    if bad and ctx.retry < 1:
        ctx.deps.rejections.append(f"Pathway neighbors not in related list: {bad}")
        raise ModelRetry(f"Neighbors must come from lookup_related. Not allowed: {bad}")
    out.neighbors = [n for n in out.neighbors if n.career_id in related]
    return out


# ---------------------------------------------------------------- Storyteller (plain words + day-in-the-life)
storyteller = Agent(deps_type=CareerDeps, output_type=Story, name="Storyteller", retries=1)


@storyteller.instructions
def _st_instructions(ctx: RunContext[CareerDeps]) -> str:
    c = ctx.deps.career
    return (prompt("storyteller").replace("{title}", c["title"]).replace("{facts}", data.render(ctx.deps.facts))
            .replace("{alt_titles}", "; ".join(c["alt_titles"])))


@storyteller.output_validator
def _st_ok(ctx: RunContext[CareerDeps], out: Story) -> Story:
    alts = {a.lower() for a in ctx.deps.career["alt_titles"]}
    problems = [f"specialization '{s.name}' is not in ALT_TITLES" for s in out.specializations if s.name.lower() not in alts]
    small = set(map(float, range(0, 13)))
    for sc in out.scenes:
        if sc.task_id not in ctx.deps.fact_ids:
            problems.append(f"scene '{sc.title}' uses unknown fact id {sc.task_id}")
        bad = unsupported(sc.narration, ctx.deps.allowed | small)
        if bad:
            problems.append(f"scene '{sc.title}' has numbers not in FACTS: {bad}")
    bad = unsupported(out.eli12 + " " + out.not_to_confuse, ctx.deps.allowed | small)
    if bad:
        problems.append(f"explanation has numbers not in FACTS: {bad}")
    if problems and ctx.retry < 1:
        ctx.deps.rejections.extend(problems)
        raise ModelRetry("Fix these:\n" + "\n".join(problems))
    out.specializations = [s for s in out.specializations if s.name.lower() in alts]
    return out


# ---------------------------------------------------------------- Field Guide (plain words for a whole field)
field_guide = Agent(output_type=FieldGuide, name="Field Guide", retries=1)

# ---------------------------------------------------------------- Profiler + Advisor (discovery mode)
profiler = Agent(output_type=ProfileRead, instructions=prompt("profiler"), name="Profiler")


@dataclass
class AdviceDeps:
    ids: set[str]
    allowed: set[float]
    rejections: list[str] = field(default_factory=list)


advisor = Agent(deps_type=AdviceDeps, output_type=Advice, name="Advisor", retries=1)


@advisor.output_validator
def _adv_ok(ctx: RunContext[AdviceDeps], out: Advice) -> Advice:
    problems = [f"unknown id {p.id}" for p in out.picks if p.id not in ctx.deps.ids]
    for p in out.picks:
        bad = unsupported(p.why, ctx.deps.allowed)
        if bad:
            problems.append(f"'{p.id}' numbers not in FACTS: {bad}")
    if problems and ctx.retry < 1:
        ctx.deps.rejections.extend(problems)
        raise ModelRetry("Fix these:\n" + "\n".join(problems))
    out.picks = [p for p in out.picks if p.id in ctx.deps.ids and not unsupported(p.why, ctx.deps.allowed)]
    return out


# ---------------------------------------------------------------- runner
def trace_of(messages) -> list[dict]:
    """Readable step list (tool calls, tool results, retries) for the UI's 'under the hood' panel."""
    steps = []
    for m in messages:
        for p in getattr(m, "parts", []):
            if isinstance(p, ToolCallPart) and p.tool_name != "final_result":
                steps.append({"kind": "tool_call", "tool": p.tool_name, "args": p.args_as_dict()})
            elif isinstance(p, ToolReturnPart) and p.tool_name != "final_result":
                content = p.content
                n = len(content) if isinstance(content, list) else None
                steps.append({"kind": "tool_result", "tool": p.tool_name, "items": n,
                              "preview": [c.get("title") for c in content][:8] if isinstance(content, list) else str(content)[:120]})
            elif isinstance(p, RetryPromptPart):
                steps.append({"kind": "retry", "reason": str(p.content)[:300]})
    return steps


async def run_agent(agent: Agent, name: str, user_prompt: str, deps=None, effort: str | None = None,
                    cache_key: str | None = None, instructions: str | None = None) -> tuple[object, dict]:
    started = time.perf_counter()
    settings = model_settings(effort, cache_key) if effort else model_settings(cache_key=cache_key)
    result = await agent.run(user_prompt, deps=deps, model=build_model(MODEL_NAME), model_settings=settings,
                             usage_limits=LIMITS[name], instructions=instructions)
    u = result.usage() if callable(result.usage) else result.usage
    usage = {
        "agent": name,
        "requests": u.requests,
        "input_tokens": u.input_tokens or 0,
        "cached_tokens": u.cache_read_tokens or 0,
        "output_tokens": u.output_tokens or 0,
        "reasoning_tokens": getattr(u, "output_reasoning_tokens", 0) or (getattr(u, "details", None) or {}).get("reasoning_tokens", 0),
        "tool_calls": u.tool_calls or 0,
        "seconds": round(time.perf_counter() - started, 2),
    }
    usage["cost_usd"] = cost_usd(MODEL_NAME, usage["input_tokens"], usage["output_tokens"], usage["cached_tokens"])
    usage["trace"] = trace_of(result.all_messages())
    return result.output, usage
