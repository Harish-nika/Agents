import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import func

from app.api.auth import get_current_user
from app.api.groq_key import effective_groq_key, get_groq_key_header
from app.api.groq_key import get_groq_key_header
from app.api.schemas import (
    AnalysisPublic,
    CandidatePublic,
    DashboardStats,
    HRQuestionPublic,
    HRQuestionUpdate,
    JDCreate,
    JDParseRequest,
    JDParsed,
    JDPublic,
    JDUpdate,
    JobCreated,
)
from app.config import UPLOADS_DIR
from app.db.models import AnalysisResult, Candidate, HRQuestion, JobDescription, get_session
from app.services import jd_service
from app.services.jd_parser import parse_jd_text
from app.services.job_service import JD_INDEX_STEPS, JD_PARSE_STEPS, job_service

router = APIRouter(prefix="/jds", tags=["jds"])


def _jd_to_public(jd: JobDescription) -> JDPublic:
    return JDPublic(
        id=jd.id,
        title=jd.title,
        role=jd.role,
        department=jd.department,
        seniority=jd.seniority,
        content=jd.content,
        skills=jd.skills,
        is_active=jd.is_active,
        created_at=jd.created_at,
        updated_at=jd.updated_at,
    )


@router.get("", response_model=list[JDPublic])
def list_jds(active_only: bool = False, _user: str = Depends(get_current_user)):
    session = get_session()
    try:
        jds = jd_service.list_active_jds(session) if active_only else jd_service.list_all_jds(session)
        return [_jd_to_public(jd) for jd in jds]
    finally:
        session.close()


@router.get("/{jd_id}", response_model=JDPublic)
def get_jd(jd_id: int, _user: str = Depends(get_current_user)):
    session = get_session()
    try:
        jd = jd_service.get_jd(session, jd_id)
        if not jd:
            raise HTTPException(404, "JD not found")
        return _jd_to_public(jd)
    finally:
        session.close()


@router.post("", response_model=JDPublic)
def create_jd(body: JDCreate, _user: str = Depends(get_current_user)):
    session = get_session()
    try:
        jd = jd_service.create_jd(
            session, body.title, body.role, body.department, body.seniority, body.content, body.skills
        )
        return _jd_to_public(jd)
    finally:
        session.close()


@router.put("/{jd_id}", response_model=JDPublic)
def update_jd(jd_id: int, body: JDUpdate, _user: str = Depends(get_current_user)):
    session = get_session()
    try:
        jd = jd_service.update_jd(
            session, jd_id, body.title, body.role, body.department, body.seniority, body.content, body.skills
        )
        return _jd_to_public(jd)
    finally:
        session.close()


@router.post("/{jd_id}/archive")
def archive_jd(jd_id: int, _user: str = Depends(get_current_user)):
    session = get_session()
    try:
        jd_service.archive_jd(session, jd_id)
        return {"ok": True}
    finally:
        session.close()


@router.post("/{jd_id}/restore", response_model=JDPublic)
def restore_jd(jd_id: int, _user: str = Depends(get_current_user)):
    session = get_session()
    try:
        jd = jd_service.restore_jd(session, jd_id)
        return _jd_to_public(jd)
    finally:
        session.close()


@router.delete("/{jd_id}", status_code=204)
def delete_jd(jd_id: int, _user: str = Depends(get_current_user)):
    session = get_session()
    try:
        jd_service.delete_jd(session, jd_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    finally:
        session.close()


@router.post("/{jd_id}/index-async", response_model=JobCreated)
def index_jd_async(jd_id: int, _user: str = Depends(get_current_user)):
    session = get_session()
    try:
        jd = jd_service.get_jd(session, jd_id)
        if not jd:
            raise HTTPException(404, "JD not found")
    finally:
        session.close()
    job_id = job_service.create_job("jd_index", f"Index: {jd.role}", JD_INDEX_STEPS)
    job_service.start_jd_index_job(job_id, jd_id)
    return JobCreated(job_id=job_id)


@router.post("/parse-async", response_model=JobCreated)
def parse_jd_async(
    request: Request,
    body: JDParseRequest,
    user: str = Depends(get_current_user),
    groq_api_key: str | None = Depends(get_groq_key_header),
):
    if not body.raw_text.strip():
        raise HTTPException(400, "Paste a job description first.")
    job_id = job_service.create_job("jd_parse", "JD paste parse", JD_PARSE_STEPS)
    job_service.start_jd_parse_job(
        job_id, body.raw_text,
        groq_api_key=effective_groq_key(request, groq_api_key, user),
    )
    return JobCreated(job_id=job_id)


@router.post("/parse", response_model=JDParsed)
def parse_jd(body: JDParseRequest, _user: str = Depends(get_current_user)):
    try:
        parsed = parse_jd_text(body.raw_text)
        return JDParsed(
            role=parsed.role,
            title=parsed.title,
            department=parsed.department,
            seniority=parsed.seniority,
            skills=parsed.skills,
            must_haves=parsed.must_haves,
            nice_to_haves=parsed.nice_to_haves,
            content=parsed.content,
        )
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/reindex")
def reindex_jds(_user: str = Depends(get_current_user)):
    session = get_session()
    try:
        count = jd_service.reindex_all_jds(session)
        return {"reindexed": count}
    finally:
        session.close()
