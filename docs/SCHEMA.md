# Data schema

All data is public and pre-built into `data/`. Raw downloads go in `data/raw/` (not committed), then
`python scripts/build_data.py && python scripts/build_extras.py` rebuild everything.

## `data/careers.json`: one record per occupation (774)

| Field | Type | Source |
|---|---|---|
| `id`, `soc` | O*NET-SOC code (`23-1011.00`), BLS SOC (`23-1011`) | O*NET |
| `title`, `description`, `alt_titles[]` | strings (up to 150 alternate titles, used for search and "kinds of this job") | O*NET |
| `tasks[]` | top 14 tasks by importance | O*NET Task Ratings |
| `work_context{label: level}` | 18 items such as sitting, outdoors, deadline pressure, upset people (very low → very high) | O*NET Work Context |
| `pct_over_40_hours` | % of workers whose typical week is over 40 hours | O*NET |
| `work_styles[]`, `skills[]`, `knowledge[]` | top 6 each | O*NET |
| `knowledge_scores{area: 1–5}` | all 33 knowledge areas (used for discovery matching) | O*NET |
| `interests{RIASEC: 1–7}` | Holland interest profile | O*NET |
| `job_zone` | 1–5 preparation level | O*NET |
| `education_mix{level: %}` | education of current workers | O*NET |
| `related[]` | `{id, title}` related occupations | O*NET |
| `wages_2024` | `p10, p25, median, p75, p90, mean, employment` (national, annual) | BLS OEWS May 2024 |
| `outlook` | `employment_2025/2035, change_pct_2025_35, openings_per_year, median_wage_2025, typical_entry_education, work_experience, on_the_job_training, self_employed_pct` | BLS Projections |
| `vertical` | `{code, name, sub}`: industry/field = SOC major group, sub = minor group | BLS SOC |
| `capability` | `{primary, secondary}`: Building & fixing / Investigating & analyzing / Creating & designing / Helping & teaching / Leading & persuading / Organizing & detail work | derived from O*NET interests |
| `hs_subjects[]` | high-school classes mapped from top knowledge areas | derived |
| `edu_years` | years of school after HS for the typical entry education (0–8) | derived from BLS |
| `majors[]` | `{cip, title, credential, earn_1yr, earn_5yr, earn_5yr_p25, earn_5yr_p75, programs}`: national median earnings of graduates 1 and 5 years after completion | College Scorecard + NCES CIP–SOC crosswalk |
| `majors_are_pre_professional` | true when the job needs grad/professional school, so majors show the undergrad route | derived |

## `data/states.json`
`{"names": {ST: name}, "wages": {soc: {ST: [p10, median, p90, employment, location_quotient]}}}` from BLS OEWS state file (May 2024).

## `data/schools.json`
`{"inst": {unitid: [name, city, state, url, control, admit_rate, grad_rate, avg_net_price, undergrads]},
  "programs": {cip4: [[unitid, credential_level, grads_per_year, earn_1yr, earn_5yr], ...]}, "cip_titles": {...}}`
Only undergraduate credentials (1 = certificate, 2 = associate, 3 = bachelor's) at currently operating, not online-only schools.

## `data/verticals.json`
`{"capabilities": [6 labels], "verticals": [{code, name, careers: [{id, title, sub, capability, job_zone, median}]}]}`

## Student profile (Discover), posted to `/api/discover`
```json
{
  "strengths": ["Caring for people or animals", "Science & experiments"],
  "interests": ["volunteering at the animal shelter"],
  "subjects_like": ["Biology"], "subjects_dislike": ["Economics and Accounting"],
  "work_with": ["People"], "values": ["Helping others", "Job security & growth"],
  "setting": "Indoors | Outdoors | null", "activity": "Desk | Active | null",
  "max_school_years": 0, "state": "CT", "free_text": "..."
}
```
Each chip, each interest, each set preference and each ~6 words of free text count as one **signal**.
Below 5 signals nothing is suggested; 5–8 gives fields to explore plus 5 careers; 9–13 gives 8 careers
with reasons; 14+ gives 10 careers with majors and schools in the student's state.

## Saved careers (browser only)
`localStorage["ctd_garage"] = [{id, title, saved}]`. Nothing leaves the device. Compare uses `/api/compare?ids=a,b,c&state=CT`.

## Agent caches (`cache/`, not committed)
`story_<id>.json` (Storyteller), `field_<code>.json` (Field Guide), `test_drive_<id>.json`, `pathway_<id>.json`.
