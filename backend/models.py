"""Structured outputs for every agent (no free text to parse)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class GateDecision(BaseModel):
    verdict: Literal["allow", "block"]
    category: Literal["ok", "injection", "off_topic", "unsafe", "personal_info", "wellbeing"]
    message_to_student: str = Field(description="Short, kind message shown if blocked; empty if allowed.")


class ScoutResult(BaseModel):
    career_id: str = Field(description="O*NET id returned by search_careers, e.g. 23-1011.00")
    match_note: str = Field(description="One sentence: how the student's words map to this official job title.")
    claims: list[str] = Field(description="The student's beliefs split into 2-5 short, checkable claims, in their voice.")
    likes: list[str] = Field(default_factory=list, description="Things the student said they enjoy (may be empty).")


class Verdict(BaseModel):
    claim: str
    verdict: Literal["true", "partly", "myth", "no_data"]
    headline: str = Field(description="At most 8 words, punchy, teen-friendly.")
    explanation: str = Field(description="At most 45 words. Cite only numbers from the facts.")
    fact_ids: list[str] = Field(description="IDs of the facts that prove it, e.g. ['W1','C3']. Empty only for no_data.")


class RealityCheck(BaseModel):
    verdicts: list[Verdict]
    surprises: list[Verdict] = Field(description="2 facts the student did NOT ask about but would be surprised by (verdict 'true').")


class Choice(BaseModel):
    text: str = Field(description="What you'd do, first person, at most 18 words.")
    aligned: bool = Field(description="True if this is how people who thrive in the job usually act.")
    trait: str = Field(description="The work style or interest this choice reveals, e.g. 'Attention to Detail'.")


class Scenario(BaseModel):
    title: str
    moment: str = Field(description="Illustrative time stamp, e.g. 'Tuesday, 4:45 PM'.")
    situation: str = Field(description="Second person, at most 60 words, built on a real task.")
    task_id: str = Field(description="The T-fact this scene is built on.")
    choices: list[Choice] = Field(min_length=3, max_length=3)
    pro_insight: str = Field(description="At most 35 words: what experienced people in this job say matters here.")


class TestDrive(BaseModel):
    scenarios: list[Scenario] = Field(min_length=3, max_length=3)


class Course(BaseModel):
    subject: str
    why: str = Field(description="At most 15 words.")


class Credential(BaseModel):
    name: str
    note: str = Field(description="At most 20 words. Requirements vary by state; say so if relevant.")


class Stage(BaseModel):
    level: Literal["entry", "mid", "senior"]
    title: str = Field(description="Typical job title at this stage.")
    years: str = Field(description="Rough years of experience, e.g. '0-3 years'.")
    what_changes: str = Field(description="At most 25 words.")


class Neighbor(BaseModel):
    career_id: str
    why_consider: str = Field(description="At most 20 words, tied to the student's likes or claims.")


class Pathway(BaseModel):
    hs_courses: list[Course] = Field(min_length=2, max_length=5)
    education_steps: list[str] = Field(min_length=1, max_length=4, description="Ordered steps after high school.")
    credentials: list[Credential] = Field(max_length=3, description="Licenses or certifications, if any are usual.")
    stages: list[Stage] = Field(min_length=3, max_length=3)
    neighbors: list[Neighbor] = Field(min_length=2, max_length=3)


# ---------------------------------------------------------------- v2 agents
Icon = Literal["desk", "computer", "meeting", "phone", "email", "court", "classroom", "patient", "lab", "tools",
               "outdoors", "vehicle", "kitchen", "studio", "warehouse", "store", "travel", "home", "reading", "presentation"]


class Scene(BaseModel):
    time: str = Field(description="Clock time like '8:15 AM'.")
    place: str = Field(description="Where you are, 2-5 words.")
    title: str = Field(description="At most 6 words.")
    narration: str = Field(description="Second person, present tense, at most 35 words, plain words a 13-year-old knows.")
    icon: Icon
    task_id: str = Field(description="T-fact this scene is based on, or a C-fact for breaks/commute.")


class Specialization(BaseModel):
    name: str = Field(description="Exactly as written in ALT_TITLES.")
    plain: str = Field(description="What this kind does, at most 14 words.")


class Story(BaseModel):
    plain_title: str = Field(description="The job in 2-5 everyday words, e.g. 'judge's research assistant'.")
    eli12: str = Field(description="What the job is, explained to a 12-year-old, at most 45 words, with one everyday comparison.")
    not_to_confuse: str = Field(description="One sentence: a job people mix it up with and the difference. Empty if none.")
    specializations: list[Specialization] = Field(max_length=6)
    scenes: list[Scene] = Field(min_length=6, max_length=8)


class RolePlain(BaseModel):
    id: str
    plain: str = Field(description="At most 16 words, everyday language, what this person does.")


class FieldGuide(BaseModel):
    intro: str = Field(description="At most 40 words: what this field is about and how its jobs fit together.")
    roles: list[RolePlain]


KnowledgeArea = Literal[
    "Administration and Management", "Administrative", "Biology", "Building and Construction", "Chemistry",
    "Communications and Media", "Computers and Electronics", "Customer and Personal Service", "Design",
    "Economics and Accounting", "Education and Training", "Engineering and Technology", "English Language",
    "Fine Arts", "Food Production", "Foreign Language", "Geography", "History and Archeology", "Law and Government",
    "Mathematics", "Mechanical", "Medicine and Dentistry", "Personnel and Human Resources", "Philosophy and Theology",
    "Physics", "Production and Processing", "Psychology", "Public Safety and Security", "Sales and Marketing",
    "Sociology and Anthropology", "Telecommunications", "Therapy and Counseling", "Transportation"]


class RiasecWeights(BaseModel):
    Realistic: float = Field(ge=0, le=1)
    Investigative: float = Field(ge=0, le=1)
    Artistic: float = Field(ge=0, le=1)
    Social: float = Field(ge=0, le=1)
    Enterprising: float = Field(ge=0, le=1)
    Conventional: float = Field(ge=0, le=1)


class ProfileRead(BaseModel):
    riasec: RiasecWeights = Field(description="How strongly the student's hobbies/interests point to each interest type.")
    knowledge_areas: list[KnowledgeArea] = Field(max_length=5, description="Knowledge areas their interests suggest they'd enjoy.")
    summary: str = Field(description="One warm sentence reflecting the student back to themselves, at most 30 words.")


class Pick(BaseModel):
    id: str
    why: str = Field(description="At most 30 words, tied to the student's own inputs. Numbers only from FACTS.")


class Advice(BaseModel):
    picks: list[Pick]
    next_step: str = Field(description="One concrete thing to do this week, at most 25 words.")
