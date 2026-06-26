from pydantic import BaseModel, Field

import json
from datetime import datetime

from app.config import MAX_RESUME_CHARS, SUSPICION_THRESHOLD
from app.db.models import AnalysisResult, Candidate, HRQuestion, JobDescription, get_session
from app.services.candidate_verification import (
    VerificationReport,
    followup_questions_after_reassessment,
)
from app.services.llm_client import llm_client
from app.services.suspicion_detector import SuspicionResult


class ReassessResult(BaseModel):
    suspicion: SuspicionResult
    verification_summary: str = ""


REASSESS_SYSTEM = """You are an expert HR fraud-detection analyst re-evaluating a resume
after HR has gathered clarifying information from the candidate.

Given the original suspicion flags, HR's verification answers, and the resume:
- Lower suspicion_score if HR answers resolve concerns with credible evidence
- Keep or raise score if answers are vague, contradictory, or confirm red flags
- Update flags: remove resolved concerns, keep unresolved ones, add new ones if answers reveal issues
- Write hr_verification_summary: 2-3 sentences on what HR verified and the outcome

Return JSON with keys: suspicion_score (0-100), flags (list), reasoning (string),
hr_verification_summary (string for display to recruiters)."""


FIT_REFRESH_SYSTEM = """You are a senior technical recruiter updating a candidate fit summary
after HR completed verification of resume concerns.

Incorporate HR verification findings into an updated 2-3 sentence fit summary.
Be factual — note which concerns were resolved and which remain.
Return JSON with key: fit_summary (string)."""


def reassess_suspicion(
    resume_text: str,
    original_flags: list[str],
    original_score: float,
    original_reasoning: str,
    hr_qa: list[tuple[str, str]],
) -> ReassessResult:
    truncated = resume_text[:MAX_RESUME_CHARS]
    qa_block = "\n".join(
        f"Q: {q}\nHR verification: {a}" for q, a in hr_qa if a.strip()
    )
    user_prompt = f"""Original suspicion score: {original_score}
Original flags: {', '.join(original_flags) or 'none'}
Original reasoning: {original_reasoning}

HR verification Q&A:
{qa_block or 'No answers provided.'}

Resume:
{truncated}

Re-evaluate suspicion. Return JSON only."""
    data = llm_client.chat_json(REASSESS_SYSTEM, user_prompt, use_gpu=True)
    suspicion = SuspicionResult(
        suspicion_score=float(data.get("suspicion_score", original_score)),
        flags=[str(f) for f in data.get("flags", [])],
        hr_questions=[],
        reasoning=str(data.get("reasoning", "")),
    )
    return ReassessResult(
        suspicion=suspicion,
        verification_summary=str(data.get("hr_verification_summary", "")),
    )


def refresh_fit_summary(
    resume_text: str,
    jd_content: str,
    jd_title: str,
    jd_role: str,
    prior_summary: str,
    hr_qa: list[tuple[str, str]],
    verification_summary: str,
) -> str:
    truncated = resume_text[:MAX_RESUME_CHARS]
    qa_block = "\n".join(f"Q: {q}\nA: {a}" for q, a in hr_qa if a.strip())
    user_prompt = f"""Role: {jd_role} — {jd_title}

Prior fit summary: {prior_summary}

HR verification summary: {verification_summary}

HR Q&A:
{qa_block}

Job description excerpt:
{jd_content[:4000]}

Resume excerpt:
{truncated}

Return JSON only."""
    data = llm_client.chat_json(FIT_REFRESH_SYSTEM, user_prompt, use_gpu=True)
    return str(data.get("fit_summary", prior_summary))


def reassess_candidate(candidate_id: int, on_step=None) -> dict:
    def step(sid: str) -> None:
        if on_step:
            on_step(sid)

    session = get_session()
    try:
        candidate = session.get(Candidate, candidate_id)
        if not candidate:
            raise ValueError("Candidate not found")

        questions = (
            session.query(HRQuestion)
            .filter(HRQuestion.candidate_id == candidate_id)
            .filter(HRQuestion.hr_answer != "")
            .all()
        )
        if not questions:
            raise ValueError("No HR answers to reassess. Enter answers first.")

        hr_qa = [(q.question, q.hr_answer) for q in questions]

        analyses = (
            session.query(AnalysisResult)
            .filter(AnalysisResult.candidate_id == candidate_id)
            .order_by(AnalysisResult.overall_score.desc())
            .all()
        )
        if not analyses:
            raise ValueError("No analysis found for candidate")

        best = analyses[0]
        original_flags = best.suspicion_flags
        original_score = best.suspicion_score
        original_reasoning = best.suspicion_reasoning or ""

        step("llm_reassess")
        result = reassess_suspicion(
            candidate.raw_text,
            original_flags,
            original_score,
            original_reasoning,
            hr_qa,
        )

        step("update")
        verification_summary = result.verification_summary
        new_score = result.suspicion.suspicion_score
        new_flags = result.suspicion.flags

        jd = session.get(JobDescription, best.jd_id)
        new_fit_summary = best.fit_summary
        if jd:
            new_fit_summary = refresh_fit_summary(
                candidate.raw_text,
                jd.content,
                jd.title,
                jd.role,
                best.fit_summary,
                hr_qa,
                verification_summary,
            )
            best.fit_summary = new_fit_summary

        for analysis in analyses:
            analysis.suspicion_score = new_score
            analysis.suspicion_flags_json = json.dumps(new_flags)
            analysis.suspicion_reasoning = result.suspicion.reasoning
            analysis.hr_verification_summary = verification_summary

        for q in questions:
            q.status = "resolved"
            if not q.answered_at:
                q.answered_at = datetime.utcnow()

        answered_flags = {q.source_flag for q in questions if q.source_flag}
        report = VerificationReport.from_dict(
            json.loads(candidate.verification_json) if candidate.verification_json else None
        )
        followups = followup_questions_after_reassessment(report, answered_flags, new_flags)
        if followups and best:
            existing_pending = {
                q.question.strip().lower()
                for q in session.query(HRQuestion)
                .filter(HRQuestion.candidate_id == candidate_id, HRQuestion.status == "pending")
                .all()
            }
            for item in followups:
                q_norm = item["question"].strip().lower()
                if q_norm and q_norm not in existing_pending:
                    existing_pending.add(q_norm)
                    session.add(
                        HRQuestion(
                            candidate_id=candidate_id,
                            analysis_id=best.id,
                            question=item["question"],
                            category=item.get("category", "general"),
                            source_flag=item.get("source_flag", ""),
                            resume_excerpt=item.get("resume_excerpt", ""),
                            status="pending",
                        )
                    )

        if new_score < SUSPICION_THRESHOLD:
            pending = (
                session.query(HRQuestion)
                .filter(HRQuestion.candidate_id == candidate_id, HRQuestion.status == "pending")
                .all()
            )
            for q in pending:
                q.status = "dismissed"

        session.commit()
        return {
            "candidate_id": candidate_id,
            "suspicion_score": new_score,
            "flags": new_flags,
            "hr_verification_summary": verification_summary,
        }
    finally:
        session.close()
