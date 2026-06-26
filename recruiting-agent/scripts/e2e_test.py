#!/usr/bin/env python3
"""End-to-end test: JD create -> resume upload -> scores + suspicion + HR questions."""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import UPLOADS_DIR, ensure_dirs
from app.db.models import AnalysisResult, HRQuestion, get_session, init_db
from app.services.jd_service import create_jd, list_active_jds
from app.services.ollama_client import ollama_client
from app.services.scoring_agent import scoring_agent

SAMPLE_RESUME = """
John Smith
john.smith@email.com | +1-555-0123

SUMMARY
Results-driven software engineer with extensive experience leveraging cutting-edge
technologies to deliver scalable solutions in fast-paced environments. Passionate about
synergizing cross-functional teams to drive innovation and operational excellence.

EXPERIENCE
Senior Software Engineer | TechCorp | 2020 - Present
- Spearheaded development of microservices architecture using Python and FastAPI
- Implemented CI/CD pipelines reducing deployment time by 40%
- Led team of 5 engineers on cloud migration project

Software Developer | StartupXYZ | 2018 - 2020
- Built REST APIs with Django and PostgreSQL
- Developed React frontend components

SKILLS
Python, FastAPI, Django, React, PostgreSQL, Docker, Kubernetes, AWS, Machine Learning

EDUCATION
B.S. Computer Science | State University | 2018
"""

SAMPLE_JD = {
    "title": "Backend Python Developer",
    "role": "Python Developer",
    "department": "Engineering",
    "seniority": "Mid",
    "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
    "content": """
We are looking for a Backend Python Developer to build and maintain our API services.

Responsibilities:
- Design and implement REST APIs using FastAPI
- Work with PostgreSQL databases
- Deploy services using Docker
- Collaborate with frontend team

Requirements:
- 3+ years Python experience
- Experience with FastAPI or Django
- Knowledge of SQL databases
- Docker experience preferred
""",
}


def main() -> int:
    print("=== E2E Test: Recruiting Agent ===\n")

    if not ollama_client.health_check():
        print("FAIL: Ollama is not reachable")
        return 1
    print("OK: Ollama is online")

    ensure_dirs()
    init_db()
    session = get_session()

    try:
        existing = list_active_jds(session)
        if not existing:
            jd = create_jd(session, **SAMPLE_JD)
            print(f"OK: Created JD '{jd.title}' (id={jd.id})")
        else:
            jd = existing[0]
            print(f"OK: Using existing JD '{jd.title}' (id={jd.id})")

        resume_bytes = SAMPLE_RESUME.encode("utf-8")
        candidate = scoring_agent.process_resume(
            session, resume_bytes, "test_resume.txt", UPLOADS_DIR
        )
        print(f"OK: Processed candidate '{candidate.name}' (id={candidate.id}, status={candidate.status})")

        analyses = (
            session.query(AnalysisResult)
            .filter(AnalysisResult.candidate_id == candidate.id)
            .all()
        )
        if not analyses:
            print("FAIL: No analysis results generated")
            return 1

        best = max(analyses, key=lambda a: a.overall_score)
        print(f"OK: Analysis scores — technical={best.technical_score:.0f}, hr={best.hr_score:.0f}, overall={best.overall_score:.0f}")
        print(f"    Fit summary: {best.fit_summary[:100]}...")
        print(f"    Suspicion score: {best.suspicion_score:.0f}")
        if best.suspicion_flags:
            print(f"    Flags: {best.suspicion_flags}")

        questions = (
            session.query(HRQuestion)
            .filter(HRQuestion.candidate_id == candidate.id)
            .all()
        )
        print(f"OK: HR questions generated: {len(questions)}")
        for q in questions[:3]:
            print(f"    - {q.question[:80]}...")

        print("\n=== E2E Test PASSED ===")
        return 0
    except Exception as exc:
        print(f"\nFAIL: {exc}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
