"""Second data build: states, college majors + schools, verticals/capabilities, HS subjects.

Run after build_data.py:   python scripts/build_extras.py
Inputs (data/raw/): O*NET Knowledge.txt, BLS OEWS state file (oesm24st), BLS national file (group names),
College Scorecard Field-of-Study + Institution files, NCES CIP2020-SOC2018 crosswalk.
Outputs: data/careers.json (augmented), data/states.json, data/schools.json, data/verticals.json
See docs/SCHEMA.md for the shape of every file.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DATA = ROOT / "data"

# Horizontals: O*NET's six interest types, renamed as capabilities a student recognizes.
CAPABILITIES = {
    "Realistic": "Building & fixing",
    "Investigative": "Investigating & analyzing",
    "Artistic": "Creating & designing",
    "Social": "Helping & teaching",
    "Enterprising": "Leading & persuading",
    "Conventional": "Organizing & detail work",
}

# O*NET knowledge area -> high-school subject(s) a student can actually sign up for.
HS_SUBJECTS = {
    "Mathematics": "Math (algebra → calculus/statistics)",
    "English Language": "English & writing",
    "Biology": "Biology",
    "Chemistry": "Chemistry",
    "Physics": "Physics",
    "Psychology": "Psychology",
    "Sociology and Anthropology": "Social studies / sociology",
    "History and Archeology": "History",
    "Geography": "Geography / earth science",
    "Law and Government": "Government & civics",
    "Economics and Accounting": "Economics / accounting",
    "Computers and Electronics": "Computer science",
    "Engineering and Technology": "Engineering / tech ed",
    "Design": "Art & design / technical drawing",
    "Fine Arts": "Art, music or theater",
    "Communications and Media": "Journalism / media",
    "Foreign Language": "A world language",
    "Medicine and Dentistry": "Health science / anatomy",
    "Therapy and Counseling": "Health science / psychology",
    "Mechanical": "Shop / automotive tech (CTE)",
    "Building and Construction": "Construction trades (CTE)",
    "Food Production": "Agriculture / culinary (CTE)",
    "Philosophy and Theology": "Philosophy / ethics",
    "Sales and Marketing": "Business & marketing",
    "Administration and Management": "Business",
    "Public Safety and Security": "Public safety / first aid (CTE)",
    "Telecommunications": "Computer networking (CTE)",
    "Education and Training": "Peer tutoring / education (CTE)",
}

EDU_YEARS = {  # years of school after high school, from BLS "typical entry education"
    "No formal educational credential": 0, "High school diploma or equivalent": 0,
    "Some college, no degree": 1, "Postsecondary nondegree award": 1, "Associate's degree": 2,
    "Bachelor's degree": 4, "Master's degree": 6, "Doctoral or professional degree": 8,
}

# Careers that need a graduate/professional degree: typical UNDERGRAD majors (CIP4) to show instead.
PRE_PROFESSIONAL = {  # keyed by SOC major group
    "23": ["2200", "4510", "2301", "4201"],  # legal -> legal studies, political science, English, psychology
    "29": ["5111", "2601", "4005", "3001"],  # doctors/dentists/vets/pharmacists -> pre-med, biology, chemistry
}
CRED = {"1": "Certificate", "2": "Associate", "3": "Bachelor's"}


def money(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else int(f)  # NaN -> None (JSON has no NaN)


def frac(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else round(f, 3)


def main() -> None:
    careers = json.loads((DATA / "careers.json").read_text())

    # ---------------- verticals (SOC major + minor groups) from the OEWS national file
    nat = pd.read_excel(RAW / "oesm24nat" / "national_M2024_dl.xlsx", dtype=str)
    major_name = {r.OCC_CODE[:2]: r.OCC_TITLE.replace(" Occupations", "") for r in nat[nat.O_GROUP == "major"].itertuples()}
    minor_name = {r.OCC_CODE[:4]: r.OCC_TITLE for r in nat[nat.O_GROUP == "minor"].itertuples()}

    # ---------------- knowledge scores (for HS subjects + profile matching)
    know = pd.read_csv(RAW / "db_31_0_text" / "Knowledge.txt", sep="\t", dtype=str)
    know = know[know["Scale ID"] == "IM"]
    kscores = defaultdict(dict)
    for r in know.itertuples(index=False):
        kscores[r[0]][r[2]] = round(float(r[4]), 2)

    # ---------------- CIP <-> SOC crosswalk
    xw = pd.read_excel(RAW / "cip_soc.xlsx", sheet_name="SOC-CIP", dtype=str)
    xw["cip4"] = xw["CIP2020Code"].str.replace(".", "", regex=False).str.zfill(6).str[:4]
    # CIP codes come in as e.g. "22.0101" -> "220101"; handle short floats like "1.0" too
    def cip4(code: str) -> str:
        a, _, b = code.partition(".")
        return a.zfill(2) + (b + "00")[:2]
    xw["cip4"] = xw["CIP2020Code"].map(cip4)
    soc_cips = xw[xw["SOC2018Code"] != "99-9999"].groupby("SOC2018Code")["cip4"].apply(lambda s: list(dict.fromkeys(s))).to_dict()

    # ---------------- College Scorecard
    fos = pd.read_csv(RAW / "fos" / "Most-Recent-Cohorts-Field-of-Study.csv", dtype=str,
                      usecols=["UNITID", "CIPCODE", "CIPDESC", "CREDLEV", "IPEDSCOUNT2", "EARN_MDN_1YR", "EARN_MDN_5YR",
                               "EARN_MDN_1YR_NAT", "EARN_MDN_5YR_NAT", "EARN_P25_5YR_NAT", "EARN_P75_5YR_NAT", "DISTANCE"])
    fos = fos[fos.CREDLEV.isin(["1", "2", "3"]) & (fos.DISTANCE != "2")]  # undergrad/college, not online-only
    cip_title = fos.drop_duplicates("CIPCODE").set_index("CIPCODE")["CIPDESC"].str.rstrip(".").to_dict()
    nat_earn = {}
    for (cip, cred), g in fos.groupby(["CIPCODE", "CREDLEV"]):
        r = g.iloc[0]
        nat_earn[(cip, cred)] = {"earn_1yr": money(r.EARN_MDN_1YR_NAT), "earn_5yr": money(r.EARN_MDN_5YR_NAT),
                                 "earn_5yr_p25": money(r.EARN_P25_5YR_NAT), "earn_5yr_p75": money(r.EARN_P75_5YR_NAT),
                                 "programs": len(g)}

    inst = pd.read_csv(RAW / "inst" / "Most-Recent-Cohorts-Institution.csv", dtype=str, low_memory=False,
                       usecols=["UNITID", "INSTNM", "CITY", "STABBR", "INSTURL", "CONTROL", "ADM_RATE", "C150_4", "C150_L4",
                                "NPT4_PUB", "NPT4_PRIV", "UGDS", "CURROPER", "PREDDEG"])
    inst = inst[inst.CURROPER == "1"]

    # ---------------- per-career majors
    used_cips: set[str] = set()
    for c in careers:
        soc = c["soc"]
        cips = [x for x in soc_cips.get(soc, []) if any((x, k) in nat_earn for k in "321")]
        pre = False
        entry = (c.get("outlook") or {}).get("typical_entry_education")
        if entry == "Doctoral or professional degree" and soc[:2] in PRE_PROFESSIONAL:
            # the job's own field (JD, MD, DVM) is graduate school; show the usual undergrad route instead
            cips = PRE_PROFESSIONAL[soc[:2]]
            pre = True
        elif entry in ("Doctoral or professional degree", "Master's degree"):
            pre = True
        majors = []
        for x in dict.fromkeys(cips):
            for k in ("3", "2", "1"):
                if (x, k) in nat_earn:
                    e = nat_earn[(x, k)]
                    majors.append({"cip": x, "title": cip_title.get(x, x), "credential": CRED[k], **e})
                    used_cips.add(x)
                    break
        majors.sort(key=lambda m: m["programs"], reverse=True)
        c["majors"] = majors[:6]
        c["majors_are_pre_professional"] = pre

        # verticals / capabilities / subjects / education years
        c["vertical"] = {"code": soc[:2], "name": major_name.get(soc[:2], soc[:2]),
                         "sub": minor_name.get(soc[:4], "")}
        ranked = sorted(c["interests"].items(), key=lambda kv: kv[1], reverse=True)
        c["capability"] = {"primary": CAPABILITIES[ranked[0][0]], "secondary": CAPABILITIES[ranked[1][0]]}
        ks = kscores.get(c["id"], {})
        c["knowledge_scores"] = ks
        subjects = []
        for area, v in sorted(ks.items(), key=lambda kv: kv[1], reverse=True):
            s = HS_SUBJECTS.get(area)
            if v >= 3.0 and s and s not in subjects:
                subjects.append(s)
        c["hs_subjects"] = subjects[:6]
        c["edu_years"] = EDU_YEARS.get((c.get("outlook") or {}).get("typical_entry_education"), None)
    (DATA / "careers.json").write_text(json.dumps(careers, ensure_ascii=False, separators=(",", ":"), allow_nan=False))

    # ---------------- states
    st = pd.read_excel(RAW / "oesm24st" / "state_M2024_dl.xlsx", dtype=str)
    st = st[st.O_GROUP == "detailed"]
    socs = {c["soc"] for c in careers}
    states: dict = defaultdict(dict)
    for r in st.itertuples(index=False):
        if r.OCC_CODE in socs and r.PRIM_STATE not in ("PR", "VI", "GU"):
            med = 239200 if r.A_MEDIAN == "#" else money(r.A_MEDIAN)
            p10 = money(r.A_PCT10)
            p90 = 239200 if r.A_PCT90 == "#" else money(r.A_PCT90)
            states[r.OCC_CODE][r.PRIM_STATE] = [p10, med, p90, money(r.TOT_EMP), frac(r.LOC_QUOTIENT)]
    names = st.drop_duplicates("PRIM_STATE").set_index("PRIM_STATE")["AREA_TITLE"].to_dict()
    (DATA / "states.json").write_text(json.dumps({"names": {k: v for k, v in names.items() if k not in ("PR", "VI", "GU")},
                                                   "wages": states}, separators=(",", ":"), allow_nan=False))

    # ---------------- schools (only programs for majors we reference)
    prog = fos[fos.CIPCODE.isin(used_cips) & fos.UNITID.isin(inst.UNITID)]
    programs: dict = defaultdict(list)
    for r in prog.itertuples(index=False):
        programs[r.CIPCODE].append([r.UNITID, int(r.CREDLEV), money(r.IPEDSCOUNT2), money(r.EARN_MDN_1YR), money(r.EARN_MDN_5YR)])
    keep = {p[0] for v in programs.values() for p in v}
    insts = {}
    for r in inst[inst.UNITID.isin(keep)].itertuples(index=False):
        grad = frac(r.C150_4) if frac(r.C150_4) is not None else frac(r.C150_L4)
        net = money(r.NPT4_PUB) or money(r.NPT4_PRIV)
        insts[r.UNITID] = [r.INSTNM, r.CITY, r.STABBR, (r.INSTURL or "").split("/")[0], int(r.CONTROL), frac(r.ADM_RATE),
                           grad, net, money(r.UGDS)]
    (DATA / "schools.json").write_text(json.dumps({"columns": {
        "inst": ["name", "city", "state", "url", "control(1=public,2=private nonprofit,3=for-profit)", "admit_rate",
                 "grad_rate", "avg_net_price", "undergrads"],
        "program": ["unitid", "credential_level(1=cert,2=assoc,3=bach)", "grads_per_year", "earn_1yr", "earn_5yr"]},
        "cip_titles": {k: cip_title.get(k, k) for k in used_cips}, "inst": insts, "programs": programs}, separators=(",", ":"), allow_nan=False))

    # ---------------- verticals index
    verts: dict = {}
    for c in careers:
        v = verts.setdefault(c["vertical"]["code"], {"code": c["vertical"]["code"], "name": c["vertical"]["name"], "careers": []})
        v["careers"].append({"id": c["id"], "title": c["title"], "sub": c["vertical"]["sub"],
                             "capability": c["capability"]["primary"], "job_zone": c.get("job_zone"),
                             "median": (c.get("wages_2024") or {}).get("median")})
    (DATA / "verticals.json").write_text(json.dumps({"capabilities": list(CAPABILITIES.values()),
                                                     "verticals": sorted(verts.values(), key=lambda v: v["code"])},
                                                    separators=(",", ":")))
    for f in ("careers.json", "states.json", "schools.json", "verticals.json"):
        print(f, f"{(DATA / f).stat().st_size / 1e6:.1f} MB")
    print("careers with majors:", sum(bool(c["majors"]) for c in careers), "/", len(careers),
          "| programs:", sum(len(v) for v in programs.values()), "| schools:", len(insts), "| states occ:", len(states))


if __name__ == "__main__":
    main()
