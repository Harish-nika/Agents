#!/usr/bin/env python3
"""Re-score resumes in ./resumes against the active JD (for testing)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import UPLOADS_DIR
from app.db.models import AnalysisResult, Candidate, HRQuestion, JobDescription, get_session
from app.services.candidate_verification import VerificationReport, category_counts
from app.services.jd_format import normalize_jd_content
from app.services.scoring_agent import scoring_agent
from app.services.user_settings_service import user_settings_service
from app.services.llm_context import reset_groq_api_key, set_groq_api_key

RESUMES_DIR = ROOT / "resumes"


def fix_jd_content(session) -> None:
    jd = session.query(JobDescription).filter(JobDescription.is_active.is_(True)).first()
    if not jd:
        print("No active JD — create one first.")
        return
    normalized = normalize_jd_content(jd.content)
    if normalized != jd.content:
        jd.content = normalized
        session.commit()
        print(f"Fixed JD #{jd.id} content formatting ({len(normalized)} chars)")


def print_verification(candidate: Candidate) -> None:
    report = VerificationReport.from_dict(
        json.loads(candidate.verification_json) if candidate.verification_json else None
    )
    print(f"  Completeness: {report.completeness_score:.0f}/100")
    if report.missing_sections:
        print(f"  Missing sections: {', '.join(report.missing_sections)}")
    counts = category_counts(report)
    if counts:
        print(f"  Anomalies by category: {counts}")
    for a in report.anomalies[:8]:
        print(f"    [{a.category}] {a.flag}: {a.excerpt or a.suggestion_question[:60]}")


def print_hr_questions(session, candidate_id: int) -> None:
    questions = (
        session.query(HRQuestion)
        .filter(HRQuestion.candidate_id == candidate_id)
        .order_by(HRQuestion.category, HRQuestion.created_at)
        .all()
    )
    if not questions:
        print("  HR questions: none")
        return
    by_cat: dict[str, list] = {}
    for q in questions:
        by_cat.setdefault(q.category or "general", []).append(q)
    print("  HR questions by category:")
    for cat, qs in sorted(by_cat.items()):
        print(f"    {cat} ({len(qs)}):")
        for q in qs[:3]:
            excerpt = f' — "{q.resume_excerpt[:50]}"' if q.resume_excerpt else ""
            print(f"      - {q.question[:80]}{excerpt}")


def run() -> None:
    token = set_groq_api_key(user_settings_service.get_groq_key("hr"))
    try:
        session = get_session()
        fix_jd_content(session)
        jd = session.query(JobDescription).filter(JobDescription.is_active.is_(True)).first()
        if not jd:
            return
        print(f"Scoring against: {jd.role}\n")

        files = sorted(RESUMES_DIR.glob("*"))
        results = []
        for path in files:
            if path.suffix.lower() not in {".pdf", ".docx", ".txt"}:
                continue
            print(f"--- {path.name} ---")
            if results:
                time.sleep(8)
            t0 = time.time()
            try:
                candidate = scoring_agent.process_resume(
                    session,
                    path.read_bytes(),
                    path.name,
                    UPLOADS_DIR,
                    target_jd_id=jd.id,
                )
                session.refresh(candidate)
                print_verification(candidate)
                print_hr_questions(session, candidate.id)
                analysis = (
                    session.query(AnalysisResult)
                    .filter_by(candidate_id=candidate.id, jd_id=jd.id)
                    .order_by(AnalysisResult.created_at.desc())
                    .first()
                )
                elapsed = round(time.time() - t0, 1)
                if analysis:
                    results.append((path.name, analysis, elapsed))
                    print(
                        f"  Overall: {analysis.overall_score:.0f} | Tech: {analysis.technical_score:.0f} | "
                        f"HR: {analysis.hr_score:.0f} | Suspicion: {analysis.suspicion_score:.0f} | {elapsed}s"
                    )
                    print(f"  {analysis.fit_summary[:200]}...")
                else:
                    print("  No analysis produced")
            except Exception as exc:
                print(f"  ERROR: {exc}")
            print()

        if results:
            print("=== RANKING (by overall score) ===")
            for name, a, elapsed in sorted(results, key=lambda x: -x[1].overall_score):
                print(f"{a.overall_score:5.1f}  {name}  (suspicion {a.suspicion_score:.0f})")
        session.close()
    finally:
        reset_groq_api_key(token)


if __name__ == "__main__":
    run()
