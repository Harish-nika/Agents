from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
import json

from app.api.auth import get_current_user
from app.api.groq_key import effective_groq_key, get_groq_key_header
from app.api.schemas import AnalysisPublic, CandidatePublic, JobCreated
from app.config import UPLOADS_DIR
from app.db.models import AnalysisResult, Candidate, HRQuestion, JobDescription, get_session
from app.services.candidate_verification import VerificationReport, category_counts, verification_summary_text
from app.services.candidate_service import delete_all_candidates, delete_candidate
from app.services.job_service import HR_REASSESS_STEPS, RESUME_STEPS, job_service
from app.services.resume_parser import validate_resume_file
from app.services.scoring_agent import scoring_agent

router = APIRouter(prefix="/candidates", tags=["candidates"])


def _analysis_public(analysis: AnalysisResult, jd: JobDescription | None) -> AnalysisPublic:
    return AnalysisPublic(
        id=analysis.id,
        candidate_id=analysis.candidate_id,
        jd_id=analysis.jd_id,
        jd_title=jd.title if jd else "",
        jd_role=jd.role if jd else "",
        technical_score=analysis.technical_score,
        hr_score=analysis.hr_score,
        overall_score=analysis.overall_score,
        fit_summary=analysis.fit_summary,
        strengths=analysis.strengths,
        gaps=analysis.gaps,
        suspicion_score=analysis.suspicion_score,
        suspicion_flags=analysis.suspicion_flags,
        suspicion_reasoning=analysis.suspicion_reasoning or "",
        hr_verification_summary=analysis.hr_verification_summary or "",
        recommended_role=analysis.recommended_role,
        similarity_score=analysis.similarity_score,
        created_at=analysis.created_at,
    )


def _candidate_public(candidate: Candidate, session) -> CandidatePublic:
    analyses = (
        session.query(AnalysisResult)
        .filter(AnalysisResult.candidate_id == candidate.id)
        .order_by(AnalysisResult.overall_score.desc())
        .all()
    )
    analysis_list = []
    for a in analyses:
        jd = session.get(JobDescription, a.jd_id)
        analysis_list.append(_analysis_public(a, jd))
    pending_hr = (
        session.query(HRQuestion)
        .filter(HRQuestion.candidate_id == candidate.id, HRQuestion.status == "pending")
        .count()
    )
    report = VerificationReport.from_dict(
        json.loads(candidate.verification_json) if candidate.verification_json else None
    )
    return CandidatePublic(
        id=candidate.id,
        name=candidate.name,
        email=candidate.email,
        phone=candidate.phone,
        status=candidate.status,
        parse_method=candidate.parse_method or "",
        created_at=candidate.created_at,
        analyses=analysis_list,
        pending_hr_questions=pending_hr,
        verification_summary=verification_summary_text(report),
        verification_category_counts=category_counts(report),
        verification_completeness=report.completeness_score if report.anomalies or report.missing_sections else None,
    )


@router.get("", response_model=list[CandidatePublic])
def list_candidates(status: str | None = None, _user: str = Depends(get_current_user)):
    session = get_session()
    try:
        q = session.query(Candidate).order_by(Candidate.created_at.desc())
        if status:
            q = q.filter(Candidate.status == status)
        return [_candidate_public(c, session) for c in q.all()]
    finally:
        session.close()


@router.post("/upload-async", response_model=JobCreated)
async def upload_resume_async(
    request: Request,
    file: UploadFile = File(...),
    target_jd_id: int | None = Form(None),
    user: str = Depends(get_current_user),
    groq_api_key: str | None = Depends(get_groq_key_header),
):
    if not file.filename:
        raise HTTPException(400, "No file provided")
    try:
        validate_resume_file(file.filename)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    content = await file.read()
    job_id = job_service.create_job("resume_analysis", file.filename, RESUME_STEPS)
    job_service.start_resume_job(
        job_id, content, file.filename, target_jd_id,
        groq_api_key=effective_groq_key(request, groq_api_key, user),
    )
    return JobCreated(job_id=job_id)


@router.post("/upload", response_model=CandidatePublic)
async def upload_resume(
    file: UploadFile = File(...),
    target_jd_id: int | None = Form(None),
    _user: str = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(400, "No file provided")
    try:
        validate_resume_file(file.filename)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    content = await file.read()
    session = get_session()
    try:
        candidate = scoring_agent.process_resume(
            session, content, file.filename, UPLOADS_DIR, target_jd_id=target_jd_id
        )
        return _candidate_public(candidate, session)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        session.close()


@router.delete("/{candidate_id}", status_code=204)
def delete_candidate_route(candidate_id: int, _user: str = Depends(get_current_user)):
    session = get_session()
    try:
        delete_candidate(session, candidate_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    finally:
        session.close()


@router.delete("", status_code=204)
def delete_all_candidates_route(_user: str = Depends(get_current_user)):
    session = get_session()
    try:
        delete_all_candidates(session)
    finally:
        session.close()


@router.post("/{candidate_id}/reassess-suspicion", response_model=JobCreated)
def reassess_suspicion_async(
    request: Request,
    candidate_id: int,
    user: str = Depends(get_current_user),
    groq_api_key: str | None = Depends(get_groq_key_header),
):
    session = get_session()
    try:
        candidate = session.get(Candidate, candidate_id)
        if not candidate:
            raise HTTPException(404, "Candidate not found")
        answered = (
            session.query(HRQuestion)
            .filter(HRQuestion.candidate_id == candidate_id, HRQuestion.hr_answer != "")
            .count()
        )
        if answered == 0:
            raise HTTPException(400, "Enter HR answers before reassessing")
        label = f"HR reassess: {candidate.name}"
        job_id = job_service.create_job("hr_reassess", label, HR_REASSESS_STEPS)
        job_service.start_hr_reassess_job(
            job_id, candidate_id,
            groq_api_key=effective_groq_key(request, groq_api_key, user),
        )
        return JobCreated(job_id=job_id)
    finally:
        session.close()
