"""Build data/careers.json from the raw public datasets.

Sources (all public, see README):
  * O*NET 31.0 database (text)           data/raw/db_31_0_text/
  * BLS Employment Projections 2025-35    data/raw/occupation.xlsx  (Table 1.2)
  * BLS OEWS national wages, May 2024     data/raw/oesm24nat/national_M2024_dl.xlsx

Run once:  python scripts/build_data.py
The output (data/careers.json) is committed, so the app never needs the raw files.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
ONET = RAW / "db_31_0_text"
OUT = ROOT / "data" / "careers.json"

TOP_CODED = 239200  # OEWS shows "#" for wages at or above $239,200/yr


def onet(name: str) -> pd.DataFrame:
    return pd.read_csv(ONET / f"{name}.txt", sep="\t", dtype=str, keep_default_na=False)


def num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def txt(v):
    return None if pd.isna(v) or str(v).strip() in ("", "—", "-") else str(v)


def soc6(code: str) -> str:
    return code[:7]


# Work-context items worth showing to a teenager, with a plain-English label.
CONTEXT_ITEMS = {
    "Spend Time Sitting": "Time spent sitting",
    "Spend Time Standing": "Time spent standing",
    "Face-to-Face Discussions with Individuals and Within Teams": "Face-to-face talking",
    "Time Pressure": "Deadline pressure",
    "Public Speaking": "Public speaking",
    "Dealing With Unpleasant, Angry, or Discourteous People": "Dealing with upset people",
    "Conflict Situations": "Conflict situations",
    "Importance of Repeating Same Tasks": "Repetitive tasks",
    "Outdoors, Exposed to All Weather Conditions": "Working outdoors",
    "Indoors, Environmentally Controlled": "Working indoors (office-like)",
    "Freedom to Make Decisions": "Freedom to make decisions",
    "Work With or Contribute to a Work Group or Team": "Teamwork",
    "Exposed to Disease or Infections": "Exposure to disease",
    "Exposed to Hazardous Equipment": "Hazardous equipment",
    "E-Mail": "Email",
    "Level of Competition": "Competition with others",
    "Consequence of Error": "Cost of a mistake",
    "Spend Time Using Your Hands to Handle, Control, or Feel Objects, Tools, or Controls": "Hands-on work with tools",
}
LEVELS = ["very low", "low", "moderate", "high", "very high"]

EDU_LABELS = {
    "1": "Less than high school", "2": "High school diploma", "3": "Post-secondary certificate",
    "4": "Some college", "5": "Associate's degree", "6": "Bachelor's degree",
    "7": "Post-bacc certificate", "8": "Master's degree", "9": "Post-master's certificate",
    "10": "Professional degree (e.g. JD, MD)", "11": "Doctoral degree", "12": "Post-doctoral training",
}


def main() -> None:
    occ = onet("Occupation Data")
    occ = occ[occ["O*NET-SOC Code"].str.endswith(".00")]  # one record per SOC detail code

    # --- tasks, ranked by importance (IM) ---
    tasks = onet("Task Statements")
    ratings = onet("Task Ratings")
    imp = ratings[ratings["Scale ID"] == "IM"][["O*NET-SOC Code", "Task ID", "Data Value"]]
    tasks = tasks.merge(imp, on=["O*NET-SOC Code", "Task ID"], how="left")
    tasks["imp"] = num(tasks["Data Value"]).fillna(0)
    tasks = tasks.sort_values(["O*NET-SOC Code", "Task Type", "imp"], ascending=[True, True, False])

    titles = onet("Job Titles")
    styles = onet("Work Styles")
    styles = styles[styles["Scale ID"] == "WI"].assign(v=lambda d: num(d["Data Value"]))
    interests = onet("Career Interest Types")
    interests = interests[interests["Scale ID"] == "OI"].assign(v=lambda d: num(d["Data Value"]))
    know = onet("Knowledge")
    know = know[know["Scale ID"] == "IM"].assign(v=lambda d: num(d["Data Value"]))
    skills = pd.concat([onet("Essential Skills"), onet("Transferable Skills")])
    skills = skills[skills["Scale ID"] == "IM"].assign(v=lambda d: num(d["Data Value"]))
    zones = onet("Job Zones").set_index("O*NET-SOC Code")["Job Zone"].to_dict()
    related = onet("Related Occupations")
    ctx = onet("Work Context")
    ctx_cx = ctx[(ctx["Scale ID"] == "CX") & ctx["Element Name"].isin(CONTEXT_ITEMS)].assign(
        v=lambda d: num(d["Data Value"])
    )
    week = ctx[(ctx["Scale ID"] == "CTP") & (ctx["Element Name"] == "Duration of Typical Work Week")]
    edu = onet("Education")
    edu = edu[edu["Scale ID"] == "RL"].assign(v=lambda d: num(d["Data Value"]))

    # --- BLS projections ---
    proj = pd.read_excel(RAW / "occupation.xlsx", sheet_name="Table 1.2", header=1)
    proj.columns = [
        "title", "soc", "type", "emp_2025", "emp_2035", "dist25", "dist35", "change_num",
        "change_pct", "self_emp_pct", "openings", "median_wage_2025", "education",
        "experience", "ojt", "ooh1", "ooh2",
    ][: len(proj.columns)]
    proj = proj[proj["type"] == "Line item"].set_index("soc")

    # --- BLS OEWS wages ---
    oes = pd.read_excel(RAW / "oesm24nat" / "national_M2024_dl.xlsx", dtype=str)
    oes = oes[oes["O_GROUP"] == "detailed"].set_index("OCC_CODE")

    def wage(v: str):
        if v in ("#",):
            return TOP_CODED
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return None

    title_of = occ.set_index("O*NET-SOC Code")["Title"].to_dict()
    careers = []
    for _, row in occ.iterrows():
        code = row["O*NET-SOC Code"]
        soc = soc6(code)
        t = tasks[tasks["O*NET-SOC Code"] == code]
        if t.empty:
            continue
        rec = {
            "id": code,
            "soc": soc,
            "title": row["Title"],
            "description": row["Description"],
            "alt_titles": titles[titles["O*NET-SOC Code"] == code]["Job Title"].head(25).tolist(),
            "tasks": t["Task"].head(14).tolist(),
            "work_styles": styles[styles["O*NET-SOC Code"] == code].nlargest(6, "v")["Element Name"].tolist(),
            "skills": skills[skills["O*NET-SOC Code"] == code].nlargest(6, "v")["Element Name"].tolist(),
            "knowledge": know[know["O*NET-SOC Code"] == code].nlargest(6, "v")["Element Name"].tolist(),
            "interests": {
                r["Element Name"]: round(r["v"], 2)
                for _, r in interests[interests["O*NET-SOC Code"] == code].iterrows()
            },
            "job_zone": int(zones[code]) if code in zones else None,
            "work_context": {
                CONTEXT_ITEMS[r["Element Name"]]: LEVELS[min(4, max(0, round(r["v"]) - 1))]
                for _, r in ctx_cx[ctx_cx["O*NET-SOC Code"] == code].iterrows()
            },
            "related": [
                {"id": r, "title": title_of[r]}
                for r in related[related["O*NET-SOC Code"] == code]["Related O*NET-SOC Code"].head(8)
                if r in title_of
            ],
        }
        w = week[week["O*NET-SOC Code"] == code]
        if not w.empty:
            share = dict(zip(w["Category"], num(w["Data Value"])))
            rec["pct_over_40_hours"] = round(float(share.get("3", 0)), 0)
        e = edu[edu["O*NET-SOC Code"] == code]
        if not e.empty:
            rec["education_mix"] = {
                EDU_LABELS[c]: round(float(v), 0)
                for c, v in zip(e["Category"], e["v"]) if v >= 5
            }
        if soc in proj.index:
            p = proj.loc[soc]
            p = p.iloc[0] if isinstance(p, pd.DataFrame) else p
            rec["outlook"] = {
                "employment_2025": round((fnum(p["emp_2025"]) or 0) * 1000),
                "employment_2035": round((fnum(p["emp_2035"]) or 0) * 1000),
                "change_pct_2025_35": fnum(p["change_pct"]),
                "openings_per_year": round((fnum(p["openings"]) or 0) * 1000),
                "median_wage_2025": int(p["median_wage_2025"]) if str(p["median_wage_2025"]).isdigit() else None,
                "typical_entry_education": txt(p["education"]),
                "work_experience": txt(p["experience"]),
                "on_the_job_training": txt(p["ojt"]),
                "self_employed_pct": fnum(p["self_emp_pct"]),
            }
        if soc in oes.index:
            o = oes.loc[soc]
            o = o.iloc[0] if isinstance(o, pd.DataFrame) else o
            rec["wages_2024"] = {
                "p10": wage(o["A_PCT10"]), "p25": wage(o["A_PCT25"]), "median": wage(o["A_MEDIAN"]),
                "p75": wage(o["A_PCT75"]), "p90": wage(o["A_PCT90"]), "mean": wage(o["A_MEAN"]),
                "employment": wage(o["TOT_EMP"]),
                "top_coded_at": TOP_CODED,
            }
        careers.append(rec)

    OUT.write_text(json.dumps(careers, ensure_ascii=False, allow_nan=False, separators=(",", ":")))
    with_wages = sum("wages_2024" in c for c in careers)
    with_outlook = sum("outlook" in c for c in careers)
    print(f"{len(careers)} careers -> {OUT} ({OUT.stat().st_size/1e6:.1f} MB); "
          f"wages {with_wages}, outlook {with_outlook}")


if __name__ == "__main__":
    main()
