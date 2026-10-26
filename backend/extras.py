"""Deterministic features (no LLM, no cost): compare, state wages, schools, verticals, discovery scoring."""

from __future__ import annotations

import json
import math
from functools import lru_cache

from backend import data
from backend.config import DATA_FILE

DATA_DIR = DATA_FILE.parent
LEVEL = {"very low": 1, "low": 2, "moderate": 3, "high": 4, "very high": 5}
RIASEC = ["Realistic", "Investigative", "Artistic", "Social", "Enterprising", "Conventional"]


@lru_cache(maxsize=1)
def states() -> dict:
    return json.loads((DATA_DIR / "states.json").read_text())


@lru_cache(maxsize=1)
def schools() -> dict:
    return json.loads((DATA_DIR / "schools.json").read_text())


@lru_cache(maxsize=1)
def verticals() -> dict:
    return json.loads((DATA_DIR / "verticals.json").read_text())


def state_wages(career: dict, state: str | None) -> dict:
    rows = states()["wages"].get(career["soc"], {})
    table = [{"state": s, "name": states()["names"].get(s, s), "p10": v[0], "median": v[1], "p90": v[2],
              "employment": v[3], "concentration": v[4]} for s, v in rows.items()]
    table.sort(key=lambda r: (r["median"] or 0), reverse=True)
    mine = next((r for r in table if r["state"] == state), None)
    return {"by_state": table, "selected": mine}


def stage_pay(career: dict, state: str | None = None) -> dict:
    """Starting / ~5 years / senior pay. BLS percentiles (national or state) + College Scorecard major earnings."""
    w = career.get("wages_2024") or {}
    sw = state_wages(career, state)["selected"] if state else None
    majors = [m for m in career.get("majors", []) if m.get("earn_1yr")]
    best = majors[0] if majors else None
    return {
        "bls_start": (sw or {}).get("p10") if sw else w.get("p10"),
        "bls_median": (sw or {}).get("median") if sw else w.get("median"),
        "bls_senior": (sw or {}).get("p90") if sw else w.get("p90"),
        "scope": (sw or {}).get("name") if sw else "U.S.",
        "major": best["title"] if best else None,
        "major_1yr": best["earn_1yr"] if best else None,
        "major_5yr": best["earn_5yr"] if best else None,
        "major_is_pre_professional": career.get("majors_are_pre_professional", False),
    }


def profile(career_id: str, state: str | None = None) -> dict | None:
    c = data.get(career_id)
    if not c:
        return None
    card = data.summary_card(c)
    return {
        **card,
        "soc": c["soc"],
        "vertical": c["vertical"],
        "capability": c["capability"],
        "skills": c["skills"],
        "knowledge": c["knowledge"],
        "hs_subjects": c["hs_subjects"],
        "majors": c["majors"],
        "majors_are_pre_professional": c["majors_are_pre_professional"],
        "edu_years": c["edu_years"],
        "self_employed_pct": (c.get("outlook") or {}).get("self_employed_pct"),
        "job_zone": c.get("job_zone"),
        "alt_titles": c["alt_titles"][:12],
        "pay": stage_pay(c, state),
        "state_wages": state_wages(c, state),
        "related": c["related"],
    }


def compare(ids: list[str], state: str | None) -> list[dict]:
    out = []
    for i in ids[:4]:
        p = profile(i, state)
        if p:
            p.pop("state_wages")
            out.append(p)
    return out


def top_schools(career_id: str, state: str | None = None, levels: tuple[int, ...] = (2, 3),
                control: int | None = None, sort: str = "earnings", limit: int = 15) -> dict:
    c = data.get(career_id)
    s = schools()
    rows, seen = [], set()
    for m in c.get("majors", []):
        for unitid, lvl, grads, e1, e5 in s["programs"].get(m["cip"], []):
            inst = s["inst"].get(unitid)
            if not inst or lvl not in levels or (state and inst[2] != state):
                continue
            if (control in (1, 2, 3) and inst[4] != control) or (control is None and inst[4] == 3):  # default: no for-profits
                continue
            key = (unitid, m["cip"], lvl)
            if key in seen:
                continue
            seen.add(key)
            rows.append({"school": inst[0], "city": inst[1], "state": inst[2], "url": inst[3],
                         "type": {1: "Public", 2: "Private nonprofit", 3: "For-profit"}.get(inst[4], ""),
                         "admit_rate": inst[5], "grad_rate": inst[6], "net_price": inst[7], "undergrads": inst[8],
                         "program": m["title"], "credential": {1: "Certificate", 2: "Associate", 3: "Bachelor's"}[lvl],
                         "grads_per_year": grads, "earn_1yr": e1, "earn_5yr": e5})
    if sort == "size":
        rows.sort(key=lambda r: r["grads_per_year"] or 0, reverse=True)
    elif sort == "price":
        rows.sort(key=lambda r: (r["net_price"] is None, r["net_price"] or 0))
    else:  # graduates' earnings, then graduation rate, then size
        rows.sort(key=lambda r: (r["earn_5yr"] or r["earn_1yr"] or 0, r["grad_rate"] or 0, r["grads_per_year"] or 0), reverse=True)
    return {"total": len(rows), "rows": rows[:limit], "majors": c.get("majors", []),
            "pre_professional": c.get("majors_are_pre_professional", False)}


def vertical_matrix() -> dict:
    v = verticals()
    caps = v["capabilities"]
    rows = []
    for vert in v["verticals"]:
        counts = {cap: [] for cap in caps}
        for c in vert["careers"]:
            counts[c["capability"]].append({"id": c["id"], "title": c["title"]})
        rows.append({"code": vert["code"], "name": vert["name"], "cells": counts, "total": len(vert["careers"])})
    return {"capabilities": caps, "rows": rows}


def ecosystem(vertical_code: str) -> dict | None:
    vert = next((v for v in verticals()["verticals"] if v["code"] == vertical_code), None)
    if not vert:
        return None
    return {"code": vert["code"], "name": vert["name"], "capabilities": verticals()["capabilities"],
            "careers": vert["careers"], "subs": sorted({c["sub"] for c in vert["careers"]})}


# ------------------------------------------------------------------ discovery (student profile -> careers)
# Deterministic maps from the chips a student can click to O*NET dimensions.
STRENGTH_RIASEC = {
    "Fixing or building things": {"Realistic": 1}, "Working with my hands": {"Realistic": 1},
    "Sports & being active": {"Realistic": 0.6, "Enterprising": 0.2}, "Math & puzzles": {"Investigative": 1, "Conventional": 0.3},
    "Science & experiments": {"Investigative": 1}, "Computers & coding": {"Investigative": 0.7, "Conventional": 0.4, "Realistic": 0.2},
    "Drawing & design": {"Artistic": 1}, "Writing & storytelling": {"Artistic": 0.8, "Social": 0.2},
    "Music, theater or video": {"Artistic": 1}, "Explaining things to others": {"Social": 1},
    "Caring for people or animals": {"Social": 1, "Realistic": 0.2}, "Listening & giving advice": {"Social": 1},
    "Leading a group": {"Enterprising": 1}, "Debating & persuading": {"Enterprising": 1},
    "Selling or starting things": {"Enterprising": 1}, "Organizing & planning": {"Conventional": 1},
    "Keeping track of details": {"Conventional": 1}, "Working with numbers & money": {"Conventional": 0.8, "Enterprising": 0.3},
}
WORK_WITH = {"People": {"Social": 1, "Enterprising": 0.5}, "Things & tools": {"Realistic": 1},
             "Ideas & problems": {"Investigative": 1, "Artistic": 0.5}, "Data & details": {"Conventional": 1}}
VALUE_KEYS = ["High pay", "Job security & growth", "Helping others", "Being creative", "Being my own boss", "Short training"]


def signals(p: dict) -> int:
    n = len(p.get("interests", [])) + len(p.get("strengths", [])) + len(p.get("subjects_like", [])) \
        + len(p.get("subjects_dislike", [])) + len(p.get("work_with", [])) + len(p.get("values", []))
    n += bool(p.get("setting")) + bool(p.get("activity")) + (p.get("max_school_years") is not None)
    n += min(3, len((p.get("free_text") or "").split()) // 6)
    return n


def tier(n: int) -> dict:
    if n < 5:
        return {"name": "locked", "careers": 0, "need": 5 - n}
    if n < 9:
        return {"name": "explorer", "careers": 5, "need": 9 - n}
    if n < 14:
        return {"name": "focused", "careers": 8, "need": 14 - n}
    return {"name": "curated", "careers": 10, "need": 0}


def _pct_rank(values: list[float], v: float) -> float:
    return sum(x <= v for x in values) / len(values) if values else 0.5


@lru_cache(maxsize=1)
def _dists():
    cs = [c for c in data.careers().values() if c.get("wages_2024") and c.get("outlook")]
    return sorted(c["wages_2024"]["median"] or 0 for c in cs), sorted(c["outlook"]["change_pct_2025_35"] or 0 for c in cs)


def score_careers(p: dict, riasec_extra: dict | None = None, knowledge_extra: list[str] | None = None) -> list[dict]:
    target = {k: 0.0 for k in RIASEC}
    for s in p.get("strengths", []):
        for k, w in STRENGTH_RIASEC.get(s, {}).items():
            target[k] += w
    for s in p.get("work_with", []):
        for k, w in WORK_WITH.get(s, {}).items():
            target[k] += w
    for k, w in (riasec_extra or {}).items():
        if k in target:
            target[k] += float(w) * 1.5
    liked = set(p.get("subjects_like", [])) | set(knowledge_extra or [])
    disliked = set(p.get("subjects_dislike", []))
    values = set(p.get("values", []))
    max_years = p.get("max_school_years")
    wages, growths = _dists()
    tnorm = math.sqrt(sum(v * v for v in target.values())) or 1

    out = []
    for c in data.careers().values():
        w, o = c.get("wages_2024"), c.get("outlook")
        if not w or not o or w.get("median") is None:
            continue
        if max_years is not None and c.get("edu_years") is not None and c["edu_years"] > max_years:
            continue
        reasons = []
        vec = {k: max(0.0, c["interests"].get(k, 1) - 1) for k in RIASEC}
        cnorm = math.sqrt(sum(v * v for v in vec.values())) or 1
        r_fit = sum(target[k] * vec[k] for k in RIASEC) / (tnorm * cnorm) if any(target.values()) else 0.5
        if r_fit > 0.8:
            reasons.append(f"Matches how you like to work ({c['capability']['primary'].lower()})")
        ks = c.get("knowledge_scores", {})
        k_fit = 0.5
        if liked or disliked:
            pos = [ks.get(a, 1) for a in liked]
            neg = [ks.get(a, 1) for a in disliked]
            k_fit = ((sum(pos) / len(pos) - 1) / 4 if pos else 0.5) - ((sum(neg) / len(neg) - 1) / 4 * 0.6 if neg else 0)
            hits = [a for a in liked if ks.get(a, 0) >= 3.5]
            if hits:
                reasons.append("Uses subjects you like: " + ", ".join(sorted(hits)[:3]))
        ctx = {k: LEVEL.get(v, 3) for k, v in c["work_context"].items()}
        c_fit, n_ctx = 0.0, 0
        if p.get("setting") == "Outdoors":
            c_fit += (ctx.get("Working outdoors", 1) - 1) / 4; n_ctx += 1
        elif p.get("setting") == "Indoors":
            c_fit += (ctx.get("Working indoors (office-like)", 3) - 1) / 4; n_ctx += 1
        if p.get("activity") == "Active":
            c_fit += (5 - ctx.get("Time spent sitting", 3)) / 4; n_ctx += 1
        elif p.get("activity") == "Desk":
            c_fit += (ctx.get("Time spent sitting", 3) - 1) / 4; n_ctx += 1
        c_fit = c_fit / n_ctx if n_ctx else 0.5
        v_fit, n_val = 0.0, 0
        if "High pay" in values:
            v_fit += _pct_rank(wages, w["median"]); n_val += 1
        if "Job security & growth" in values:
            v_fit += _pct_rank(growths, o["change_pct_2025_35"] or 0); n_val += 1
        if "Helping others" in values:
            v_fit += (c["interests"].get("Social", 1) - 1) / 6; n_val += 1
        if "Being creative" in values:
            v_fit += (c["interests"].get("Artistic", 1) - 1) / 6; n_val += 1
        if "Being my own boss" in values:
            v_fit += min(1, (o.get("self_employed_pct") or 0) / 30); n_val += 1
        if "Short training" in values:
            v_fit += 1 - min(1, (c.get("edu_years") or 0) / 8); n_val += 1
        v_fit = v_fit / n_val if n_val else 0.5
        score = 0.42 * r_fit + 0.25 * k_fit + 0.13 * c_fit + 0.20 * v_fit
        if "High pay" in values and _pct_rank(wages, w["median"]) > 0.75:
            reasons.append("Pays in the top quarter of all jobs")
        if "Job security & growth" in values and (o["change_pct_2025_35"] or 0) > 3.5:
            reasons.append("Growing faster than the average job")
        out.append({"id": c["id"], "title": c["title"], "score": round(score, 4), "reasons": reasons,
                    "vertical": c["vertical"]["name"], "sub": c["vertical"]["sub"],
                    "capability": c["capability"]["primary"], "median": w["median"],
                    "growth_pct": o["change_pct_2025_35"], "education": o["typical_entry_education"]})
    out.sort(key=lambda r: r["score"], reverse=True)
    # diversity: at most 2 careers from the same sub-field in the list
    picked, per_sub = [], {}
    for r in out:
        if per_sub.get(r["sub"], 0) < 2:
            picked.append(r)
            per_sub[r["sub"]] = per_sub.get(r["sub"], 0) + 1
        if len(picked) >= 30:
            break
    return picked


def top_fields(scored: list[dict], n: int = 3) -> list[dict]:
    agg: dict = {}
    for r in scored[:20]:
        a = agg.setdefault(r["vertical"], {"vertical": r["vertical"], "score": 0.0, "examples": []})
        a["score"] += r["score"]
        if len(a["examples"]) < 3:
            a["examples"].append(r["title"])
    return sorted(agg.values(), key=lambda a: a["score"], reverse=True)[:n]
