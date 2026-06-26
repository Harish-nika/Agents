from datetime import datetime
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func

from app.api.auth import get_current_user
from app.api.schemas import (
    DashboardStats,
    HRCandidateGroup,
    HRQuestionPublic,
    HRQuestionUpdate,
)
from app.db.models import AnalysisResult, Candidate, HRQuestion, JobDescription, get_session
from app.services.candidate_verification import VerificationReport, category_counts, verification_summary_text
from app.services.llm_client import llm_client

router = APIRouter(tags=["misc"])

VALID_STATUSES = ("pending", "answered", "dismissed", "resolved")


def _question_public(q: HRQuestion, session) -> HRQuestionPublic:
    candidate = session.get(Candidate, q.candidate_id)
    analysis = session.get(AnalysisResult, q.analysis_id)
    jd = session.get(JobDescription, analysis.jd_id) if analysis else None
    return HRQuestionPublic(
        id=q.id,
        candidate_id=q.candidate_id,
        candidate_name=candidate.name if candidate else "",
        analysis_id=q.analysis_id,
        question=q.question,
        category=q.category or "general",
        source_flag=q.source_flag or "",
        resume_excerpt=q.resume_excerpt or "",
        hr_answer=q.hr_answer or "",
        status=q.status,
        suspicion_score=analysis.suspicion_score if analysis else 0,
        suspicion_flags=analysis.suspicion_flags if analysis else [],
        suspicion_reasoning=analysis.suspicion_reasoning if analysis else "",
        jd_title=jd.title if jd else "",
        created_at=q.created_at,
        answered_at=q.answered_at,
    )


@router.get("/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(_user: str = Depends(get_current_user)):
    session = get_session()
    try:
        health = llm_client.health_status()
        return DashboardStats(
            active_jds=session.query(JobDescription).filter(JobDescription.is_active.is_(True)).count(),
            candidates=session.query(Candidate).count(),
            analyzed=session.query(Candidate).filter(Candidate.status == "analyzed").count(),
            failed=session.query(Candidate).filter(Candidate.status == "failed").count(),
            avg_score=float(session.query(func.avg(AnalysisResult.overall_score)).scalar() or 0),
            pending_questions=session.query(HRQuestion).filter(HRQuestion.status == "pending").count(),
            ollama_ok=health["ollama"],
            ollama_cpu=health["ollama_cpu"],
            ollama_gpu=health["ollama_gpu"],
            groq_ok=health.get("groq", False),
            using_groq=llm_client.using_groq(),
        )
    finally:
        session.close()


@router.get("/hr-questions", response_model=list[HRQuestionPublic])
def list_hr_questions(_user: str = Depends(get_current_user)):
    session = get_session()
    try:
        questions = session.query(HRQuestion).order_by(HRQuestion.created_at.desc()).all()
        return [_question_public(q, session) for q in questions]
    finally:
        session.close()


@router.get("/hr-questions/by-candidate/{candidate_id}", response_model=HRCandidateGroup)
def get_hr_questions_by_candidate(candidate_id: int, _user: str = Depends(get_current_user)):
    session = get_session()
    try:
        candidate = session.get(Candidate, candidate_id)
        if not candidate:
            raise HTTPException(404, "Candidate not found")
        questions = (
            session.query(HRQuestion)
            .filter(HRQuestion.candidate_id == candidate_id)
            .order_by(HRQuestion.created_at.asc())
            .all()
        )
        analysis = None
        if questions:
            analysis = session.get(AnalysisResult, questions[0].analysis_id)
        elif candidate.analyses:
            analysis = candidate.analyses[0]
        else:
            analysis = (
                session.query(AnalysisResult)
                .filter(AnalysisResult.candidate_id == candidate_id)
                .order_by(AnalysisResult.overall_score.desc())
                .first()
            )
        jd = session.get(JobDescription, analysis.jd_id) if analysis else None
        report = VerificationReport.from_dict(
            json.loads(candidate.verification_json) if candidate.verification_json else None
        )
        return HRCandidateGroup(
            candidate_id=candidate_id,
            candidate_name=candidate.name,
            suspicion_score=analysis.suspicion_score if analysis else 0,
            suspicion_flags=analysis.suspicion_flags if analysis else [],
            suspicion_reasoning=analysis.suspicion_reasoning if analysis else "",
            jd_title=jd.title if jd else "",
            verification_summary=verification_summary_text(report),
            verification_category_counts=category_counts(report),
            questions=[_question_public(q, session) for q in questions],
        )
    finally:
        session.close()


@router.get("/hr-questions/grouped", response_model=list[HRCandidateGroup])
def list_hr_questions_grouped(_user: str = Depends(get_current_user)):
    session = get_session()
    try:
        candidate_ids = [
            row[0]
            for row in session.query(HRQuestion.candidate_id)
            .distinct()
            .order_by(HRQuestion.candidate_id.desc())
            .all()
        ]
        groups = []
        for cid in candidate_ids:
            candidate = session.get(Candidate, cid)
            if not candidate:
                continue
            questions = (
                session.query(HRQuestion)
                .filter(HRQuestion.candidate_id == cid)
                .order_by(HRQuestion.created_at.asc())
                .all()
            )
            analysis = None
            if questions:
                analysis = session.get(AnalysisResult, questions[0].analysis_id)
            else:
                analysis = (
                    session.query(AnalysisResult)
                    .filter(AnalysisResult.candidate_id == cid)
                    .order_by(AnalysisResult.overall_score.desc())
                    .first()
                )
            jd = session.get(JobDescription, analysis.jd_id) if analysis else None
            report = VerificationReport.from_dict(
                json.loads(candidate.verification_json) if candidate.verification_json else None
            )
            groups.append(
                HRCandidateGroup(
                    candidate_id=cid,
                    candidate_name=candidate.name,
                    suspicion_score=analysis.suspicion_score if analysis else 0,
                    suspicion_flags=analysis.suspicion_flags if analysis else [],
                    suspicion_reasoning=analysis.suspicion_reasoning if analysis else "",
                    jd_title=jd.title if jd else "",
                    verification_summary=verification_summary_text(report),
                    verification_category_counts=category_counts(report),
                    questions=[_question_public(q, session) for q in questions],
                )
            )
        return groups
    finally:
        session.close()


@router.patch("/hr-questions/{question_id}", response_model=HRQuestionPublic)
def update_hr_question(
    question_id: int, body: HRQuestionUpdate, _user: str = Depends(get_current_user)
):
    session = get_session()
    try:
        q = session.get(HRQuestion, question_id)
        if not q:
            raise HTTPException(404, "Question not found")
        if body.status is not None:
            if body.status not in VALID_STATUSES:
                raise HTTPException(400, "Invalid status")
            q.status = body.status
        if body.hr_answer is not None:
            q.hr_answer = body.hr_answer.strip()
            if q.hr_answer and q.status == "pending":
                q.status = "answered"
                q.answered_at = datetime.utcnow()
        session.commit()
        session.refresh(q)
        return _question_public(q, session)
    finally:
        session.close()


@router.get("/health")
def health():
    status = llm_client.health_status()
    status["using_groq"] = llm_client.using_groq()
    return {"status": "ok", **status}
