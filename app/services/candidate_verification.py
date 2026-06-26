"""Structured resume verification: extract education/experience/projects + anomaly rules."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.config import MAX_RESUME_CHARS
from app.services.llm_client import llm_client

Category = Literal["education", "experience", "project", "timeline", "credential", "general"]

EXTRACT_SYSTEM = """You extract structured resume data from raw text (may be OCR).
Return JSON only with keys:
- education: list of {institution, degree, field, start_date, end_date} (empty strings if unknown)
- experience: list of {company, title, start_date, end_date, description}
- projects: list of {name, tech, start_date, end_date, employer_link, description}
- missing_sections: list of strings from: no_education, no_experience, no_projects, no_employment_dates, no_education_dates, no_degree_name, no_project_detail

Use YYYY or YYYY-MM for dates when possible. Do not invent employers or degrees not in the text."""


class Anomaly(BaseModel):
    category: Category
    severity: str = "medium"
    flag: str
    excerpt: str = ""
    suggestion_question: str


class VerificationReport(BaseModel):
    structured: dict[str, Any] = Field(default_factory=dict)
    anomalies: list[Anomaly] = Field(default_factory=list)
    missing_sections: list[str] = Field(default_factory=list)
    completeness_score: float = 100.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "structured": self.structured,
            "anomalies": [a.model_dump() for a in self.anomalies],
            "missing_sections": self.missing_sections,
            "completeness_score": self.completeness_score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> VerificationReport:
        if not data:
            return cls()
        anomalies = [Anomaly(**a) for a in data.get("anomalies", [])]
        return cls(
            structured=data.get("structured", {}),
            anomalies=anomalies,
            missing_sections=data.get("missing_sections", []),
            completeness_score=float(data.get("completeness_score", 100)),
        )


def _parse_year_month(text: str) -> tuple[int, int] | None:
    if not text or not str(text).strip():
        return None
    text = str(text).strip().lower()
    if text in ("present", "current", "now", "ongoing"):
        now = datetime.utcnow()
        return (now.year, now.month)
    m = re.search(r"(20\d{2}|19\d{2})", text)
    if m:
        year = int(m.group(1))
        month_m = re.search(r"(0[1-9]|1[0-2])", text)
        month = int(month_m.group(1)) if month_m else 6
        return (year, month)
    return None


def _months_between(start: tuple[int, int], end: tuple[int, int]) -> int:
    return (end[0] - start[0]) * 12 + (end[1] - start[1])


def _extract_structured(resume_text: str) -> dict[str, Any]:
    truncated = resume_text[:MAX_RESUME_CHARS]
    user = f"Extract structured fields from this resume:\n\n{truncated}\n\nReturn JSON only."
    try:
        data = llm_client.chat_json(EXTRACT_SYSTEM, user, fast=True)
    except Exception:
        return {"education": [], "experience": [], "projects": [], "missing_sections": []}
    return {
        "education": data.get("education", []) or [],
        "experience": data.get("experience", []) or [],
        "projects": data.get("projects", []) or [],
        "missing_sections": data.get("missing_sections", []) or [],
    }


def _check_timeline(experience: list[dict]) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    now = datetime.utcnow()
    parsed: list[tuple[dict, tuple[int, int], tuple[int, int]]] = []

    for exp in experience:
        start = _parse_year_month(exp.get("start_date", ""))
        end = _parse_year_month(exp.get("end_date", ""))
        if not start:
            continue
        if not end:
            end = (now.year, now.month)
        if end[0] > now.year + 1 or (end[0] == now.year + 1 and end[1] > 6):
            anomalies.append(
                Anomaly(
                    category="timeline",
                    severity="high",
                    flag="future_employment_date",
                    excerpt=f"{exp.get('company', '')} — {exp.get('end_date', '')}",
                    suggestion_question=f"Your resume shows employment at {exp.get('company', 'a company')} ending {exp.get('end_date', '')} — please confirm the correct dates.",
                )
            )
        parsed.append((exp, start, end))

    for i, (exp_a, start_a, end_a) in enumerate(parsed):
        for exp_b, start_b, end_b in parsed[i + 1 :]:
            overlap_start = max(start_a, start_b)
            overlap_end = min(end_a, end_b)
            if _months_between(overlap_start, overlap_end) > 2:
                anomalies.append(
                    Anomaly(
                        category="timeline",
                        severity="medium",
                        flag="overlapping_employment",
                        excerpt=f"{exp_a.get('company', '')} overlaps {exp_b.get('company', '')}",
                        suggestion_question=f"Can you clarify overlapping dates between {exp_a.get('company', '')} ({exp_a.get('start_date', '')}–{exp_a.get('end_date', '')}) and {exp_b.get('company', '')}?",
                    )
                )

    sorted_exp = sorted(parsed, key=lambda x: x[1])
    for i in range(len(sorted_exp) - 1):
        gap_months = _months_between(sorted_exp[i][2], sorted_exp[i + 1][1])
        if gap_months > 6:
            anomalies.append(
                Anomaly(
                    category="timeline",
                    severity="medium",
                    flag="employment_gap",
                    excerpt=f"Gap of ~{gap_months} months between roles",
                    suggestion_question=f"There is a gap of about {gap_months} months between {sorted_exp[i][0].get('company', '')} and {sorted_exp[i + 1][0].get('company', '')} — what were you doing during this period?",
                )
            )
    return anomalies


def _check_education(education: list[dict], experience: list[dict]) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    if not education:
        return [
            Anomaly(
                category="education",
                severity="medium",
                flag="no_education",
                excerpt="",
                suggestion_question="No education section found — please provide degree, institution, and graduation year.",
            )
        ]

    first_job = None
    for exp in experience:
        start = _parse_year_month(exp.get("start_date", ""))
        if start:
            first_job = start if first_job is None else min(first_job, start)

    for edu in education:
        inst = str(edu.get("institution", "")).strip()
        degree = str(edu.get("degree", "")).strip()
        if not inst:
            anomalies.append(
                Anomaly(
                    category="education",
                    severity="medium",
                    flag="unnamed_institution",
                    excerpt=degree or "Education entry",
                    suggestion_question="Which institution awarded your degree? The resume does not name the university/college.",
                )
            )
        if not degree:
            anomalies.append(
                Anomaly(
                    category="education",
                    severity="medium",
                    flag="missing_degree",
                    excerpt=inst or "Education entry",
                    suggestion_question=f"What degree did you complete at {inst or 'your institution'}?",
                )
            )
        grad = _parse_year_month(edu.get("end_date", ""))
        if first_job and grad and grad > first_job:
            anomalies.append(
                Anomaly(
                    category="education",
                    severity="high",
                    flag="graduation_after_employment",
                    excerpt=f"{degree} at {inst}, grad {edu.get('end_date', '')}",
                    suggestion_question=f"You list employment before graduation ({edu.get('end_date', '')}) — please clarify whether this was part-time study or correct the dates.",
                )
            )
    return anomalies


def _check_experience(experience: list[dict]) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    if not experience:
        return [
            Anomaly(
                category="experience",
                severity="high",
                flag="no_experience",
                excerpt="",
                suggestion_question="No work experience found — please list employers, titles, and dates.",
            )
        ]

    total_months = 0
    senior_titles = ("lead", "senior", "principal", "manager", "head", "director")
    for exp in experience:
        start = _parse_year_month(exp.get("start_date", ""))
        end = _parse_year_month(exp.get("end_date", ""))
        if start and end:
            total_months += max(0, _months_between(start, end))
        title = str(exp.get("title", "")).lower()
        company = str(exp.get("company", "")).strip()
        if not company:
            anomalies.append(
                Anomaly(
                    category="experience",
                    severity="medium",
                    flag="unnamed_employer",
                    excerpt=exp.get("title", ""),
                    suggestion_question=f"Please name the employer for your role as {exp.get('title', 'listed position')}.",
                )
            )
        if any(s in title for s in senior_titles) and total_months < 24:
            anomalies.append(
                Anomaly(
                    category="experience",
                    severity="medium",
                    flag="title_inflation",
                    excerpt=f"{exp.get('title', '')} at {company}",
                    suggestion_question=f"You list '{exp.get('title', '')}' with relatively limited total experience — describe your scope and team size in that role.",
                )
            )
    return anomalies


def _check_projects(projects: list[dict], experience: list[dict]) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    companies = {str(e.get("company", "")).lower() for e in experience if e.get("company")}

    for proj in projects:
        name = str(proj.get("name", "")).strip()
        desc = str(proj.get("description", "")).strip()
        link = str(proj.get("employer_link", "")).strip()
        if not desc and not proj.get("tech"):
            anomalies.append(
                Anomaly(
                    category="project",
                    severity="medium",
                    flag="thin_project_detail",
                    excerpt=name or "Unnamed project",
                    suggestion_question=f"Project '{name or 'listed'}' has little detail — describe your role, tech stack, and measurable outcome.",
                )
            )
        if not link and name:
            if not any(c and c in desc.lower() for c in companies if c):
                anomalies.append(
                    Anomaly(
                        category="project",
                        severity="low",
                        flag="orphan_project",
                        excerpt=name,
                        suggestion_question=f"Was project '{name}' done at an employer, freelance, or personal? Please link it to a company or client.",
                    )
                )
        if re.search(r"\d+%|\d+x|improved by \d+", desc, re.I) and not re.search(
            r"from|to|baseline|before|after|reduced .+ from", desc, re.I
        ):
            anomalies.append(
                Anomaly(
                    category="project",
                    severity="medium",
                    flag="metric_without_baseline",
                    excerpt=desc[:120],
                    suggestion_question=f"For project '{name}': what was the baseline before the improvement you claim? Please provide before/after context.",
                )
            )
    return anomalies


def _missing_section_anomalies(missing: list[str]) -> list[Anomaly]:
    prompts = {
        "no_education": (
            "education",
            "no_education",
            "No education section found — list degree, institution, and graduation year.",
        ),
        "no_experience": (
            "experience",
            "no_experience",
            "No employment history found — list companies, titles, and dates.",
        ),
        "no_projects": (
            "project",
            "no_projects",
            "No projects section — list 1–2 relevant projects with tech stack and outcomes.",
        ),
        "no_employment_dates": (
            "timeline",
            "no_employment_dates",
            "Employment entries lack dates — provide start and end month/year for each role.",
        ),
        "no_education_dates": (
            "education",
            "no_education_dates",
            "Education entries lack graduation dates — provide month/year for each degree.",
        ),
        "no_degree_name": (
            "education",
            "no_degree_name",
            "Degree name is missing — what qualification did you earn?",
        ),
        "no_project_detail": (
            "project",
            "no_project_detail",
            "Projects are listed without detail — describe your contribution and results.",
        ),
    }
    out: list[Anomaly] = []
    for key in missing:
        if key in prompts:
            cat, flag, question = prompts[key]
            out.append(
                Anomaly(category=cat, severity="medium", flag=flag, excerpt="", suggestion_question=question)
            )
    return out


def _completeness_score(structured: dict[str, Any], anomalies: list[Anomaly]) -> float:
    score = 100.0
    score -= len(structured.get("missing_sections", [])) * 8
    score -= len(anomalies) * 5
    if not structured.get("education"):
        score -= 15
    if not structured.get("experience"):
        score -= 20
    return max(0.0, min(100.0, score))


def verify_resume(resume_text: str) -> VerificationReport:
    structured = _extract_structured(resume_text)
    education = structured.get("education", [])
    experience = structured.get("experience", [])
    projects = structured.get("projects", [])
    missing = structured.get("missing_sections", [])

    anomalies: list[Anomaly] = []
    anomalies.extend(_missing_section_anomalies(missing))
    anomalies.extend(_check_education(education, experience))
    anomalies.extend(_check_experience(experience))
    anomalies.extend(_check_projects(projects, experience))
    anomalies.extend(_check_timeline(experience))

    seen_flags: set[str] = set()
    unique: list[Anomaly] = []
    for a in anomalies:
        if a.flag in seen_flags:
            continue
        seen_flags.add(a.flag)
        unique.append(a)

    return VerificationReport(
        structured=structured,
        anomalies=unique,
        missing_sections=missing,
        completeness_score=_completeness_score(structured, unique),
    )


def report_summary_for_prompt(report: VerificationReport) -> str:
    lines = [f"Completeness: {report.completeness_score:.0f}/100"]
    if report.missing_sections:
        lines.append(f"Missing sections: {', '.join(report.missing_sections)}")
    for a in report.anomalies[:12]:
        lines.append(f"- [{a.category}] {a.flag}: {a.excerpt or a.suggestion_question[:80]}")
    return "\n".join(lines)


def followup_questions_after_reassessment(
    report: VerificationReport,
    answered_source_flags: set[str],
    new_suspicion_flags: list[str],
) -> list[dict[str, str]]:
    """Create follow-up HR questions for anomalies HR did not address."""
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    flag_set = {f.lower() for f in new_suspicion_flags}
    for a in report.anomalies:
        if a.flag in answered_source_flags:
            continue
        if a.flag in seen:
            continue
        if a.severity in ("high", "medium") or a.flag.lower() in flag_set:
            seen.add(a.flag)
            out.append(
                {
                    "question": a.suggestion_question,
                    "category": a.category,
                    "source_flag": a.flag,
                    "resume_excerpt": a.excerpt[:500],
                }
            )
    return out


def questions_from_report(report: VerificationReport) -> list[dict[str, str]]:
    """Convert anomalies to HR question dicts with category metadata."""
    out: list[dict[str, str]] = []
    for a in report.anomalies:
        if a.suggestion_question.strip():
            out.append(
                {
                    "question": a.suggestion_question.strip(),
                    "category": a.category,
                    "source_flag": a.flag,
                    "resume_excerpt": a.excerpt[:500],
                }
            )
    return out


def category_counts(report: VerificationReport) -> dict[str, int]:
    counts: dict[str, int] = {}
    for a in report.anomalies:
        counts[a.category] = counts.get(a.category, 0) + 1
    return counts


def verification_summary_text(report: VerificationReport) -> str:
    counts = category_counts(report)
    if not counts:
        return ""
    parts = [f"{k}: {v}" for k, v in sorted(counts.items())]
    return f"Verification gaps — {', '.join(parts)}"
