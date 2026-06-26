#!/usr/bin/env python3
"""Clear all candidates and re-analyze every resume in ./resumes/."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import UPLOADS_DIR
from app.db.models import AnalysisResult, Candidate, HRQuestion, JobDescription, get_session
from app.services.candidate_service import delete_all_candidates
from app.services.candidate_verification import VerificationReport, category_counts
from app.services.jd_format import normalize_jd_content
from app.services.llm_client import llm_client
from app.services.llm_context import reset_groq_api_key, set_groq_api_key
from app.services.scoring_agent import scoring_agent
from app.services.user_settings_service import user_settings_service

RESUMES_DIR = ROOT / "resumes"


def main() -> None:
    groq_key = user_settings_service.get_groq_key("hr")
    if not groq_key and (ROOT / "groq_key.txt").is_file():
        groq_key = (ROOT / "groq_key.txt").read_text().strip()
    token = set_groq_api_key(groq_key)
    try:
        session = get_session()
        health = llm_client.health_status()
        print(f"LLM: groq={health.get('groq')} using_groq={llm_client.using_groq()} ollama={health.get('ollama')}")

        jd = session.query(JobDescription).filter(JobDescription.is_active.is_(True)).first()
        if not jd:
            print("ERROR: No active JD")
            return
        normalized = normalize_jd_content(jd.content)
        if normalized != jd.content:
            jd.content = normalized
            session.commit()
        print(f"JD: {jd.role} (id={jd.id})")

        n = delete_all_candidates(session)
        print(f"Cleared {n} old candidate(s)\n")

        files = sorted(p for p in RESUMES_DIR.glob("*") if p.suffix.lower() in {".pdf", ".docx", ".txt"})
        if not files:
            print(f"No resumes in {RESUMES_DIR}")
            return

        results = []
        for i, path in enumerate(files):
            print(f"=== {path.name} ===")
            if i > 0:
                time.sleep(10)
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
                elapsed = round(time.time() - t0, 1)

                report = VerificationReport.from_dict(json.loads(candidate.verification_json or "{}"))
                analysis = (
                    session.query(AnalysisResult)
                    .filter_by(candidate_id=candidate.id, jd_id=jd.id)
                    .first()
                )
                hr_count = session.query(HRQuestion).filter_by(candidate_id=candidate.id).count()

                print(f"  Saved candidate id={candidate.id} status={candidate.status}")
                print(f"  Completeness: {report.completeness_score:.0f}/100 anomalies={category_counts(report)}")
                if analysis:
                    print(
                        f"  Score: {analysis.overall_score:.0f} tech={analysis.technical_score:.0f} "
                        f"suspicion={analysis.suspicion_score:.0f} HR Qs={hr_count} ({elapsed}s)"
                    )
                    print(f"  Fit: {analysis.fit_summary[:180]}...")
                    results.append((path.name, analysis))
                else:
                    print("  ERROR: no analysis row saved")
            except Exception as exc:
                print(f"  ERROR: {exc}")
            print()

        print("=== FINAL DB STATE ===")
        for c in session.query(Candidate).order_by(Candidate.id).all():
            a = session.query(AnalysisResult).filter_by(candidate_id=c.id).first()
            q = session.query(HRQuestion).filter_by(candidate_id=c.id).count()
            score = f"{a.overall_score:.0f}" if a else "—"
            print(f"  id={c.id} {c.name} score={score} hr_q={q} verify={'yes' if c.verification_json else 'no'}")

        if results:
            print("\n=== RANKING ===")
            for name, a in sorted(results, key=lambda x: -x[1].overall_score):
                print(f"  {a.overall_score:5.1f}  {name}")
        session.close()
    finally:
        reset_groq_api_key(token)


if __name__ == "__main__":
    main()
