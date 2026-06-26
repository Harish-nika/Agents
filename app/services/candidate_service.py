import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import UPLOADS_DIR
from app.db.models import AnalysisResult, Candidate, HRQuestion, ProcessingJob


def delete_candidate(session: Session, candidate_id: int) -> None:
    candidate = session.get(Candidate, candidate_id)
    if not candidate:
        raise ValueError(f"Candidate {candidate_id} not found")

    session.query(HRQuestion).filter(HRQuestion.candidate_id == candidate_id).delete(
        synchronize_session=False
    )
    session.query(AnalysisResult).filter(AnalysisResult.candidate_id == candidate_id).delete(
        synchronize_session=False
    )
    for job in session.query(ProcessingJob).filter(ProcessingJob.candidate_id == candidate_id).all():
        job.candidate_id = None

    if candidate.file_path:
        file_path = Path(candidate.file_path)
        if file_path.is_file():
            file_path.unlink(missing_ok=True)
    upload_dir = UPLOADS_DIR / str(candidate_id)
    if upload_dir.is_dir():
        shutil.rmtree(upload_dir, ignore_errors=True)

    session.delete(candidate)
    session.commit()


def delete_all_candidates(session: Session) -> int:
    ids = [row[0] for row in session.query(Candidate.id).all()]
    for cid in ids:
        delete_candidate(session, cid)
    return len(ids)
