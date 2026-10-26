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
