from fastapi import APIRouter, Depends, Query

from app.api.auth import get_current_user
from app.api.schemas import JobCreated, ProcessingJobPublic
from app.services.job_service import JD_PARSE_STEPS, RESUME_STEPS, job_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[ProcessingJobPublic])
def list_jobs(
    ids: str | None = Query(None, description="Comma-separated job IDs"),
    active_only: bool = False,
    _user: str = Depends(get_current_user),
):
    job_ids = [int(x) for x in ids.split(",") if x.strip().isdigit()] if ids else None
    return job_service.list_jobs(job_ids=job_ids, active_only=active_only)


@router.post("/{job_id}/cancel", response_model=ProcessingJobPublic)
def cancel_job(job_id: int, _user: str = Depends(get_current_user)):
    from fastapi import HTTPException

    if not job_service.cancel_job(job_id):
        job = job_service.get_job(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        raise HTTPException(400, "Job is not running")
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.get("/{job_id}", response_model=ProcessingJobPublic)
def get_job(job_id: int, _user: str = Depends(get_current_user)):
    from fastapi import HTTPException

    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job
