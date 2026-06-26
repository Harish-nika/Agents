import json
import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.exc import OperationalError

from app.config import SUSPICION_THRESHOLD, UPLOADS_DIR
from app.db.models import (
    AnalysisResult,
    Candidate,
    HRQuestion,
    JobDescription,
    ProcessingJob,
    commit_with_retry,
    get_session,
)
from app.services.job_errors import JobCancelled
from app.services.jd_parser import parse_jd_text
from app.services.llm_context import reset_groq_api_key, set_groq_api_key
from app.services.scoring_agent import scoring_agent
from app.services.suspicion_reassessment import reassess_candidate
from app.services.vector_store import vector_store
from app.services.viz_snapshots import jd_index_viz, jd_parse_viz

StepCallback = Callable[[str], None]

RESUME_STEPS = [
    ("receive", "Receive file"),
    ("parse", "Parse resume"),
    ("normalize", "Structure text"),
    ("verify", "Verify education & experience"),
    ("embed", "Embed vectors"),
    ("search", "Search matching roles"),
    ("score", "LLM role scoring"),
    ("suspicion", "Suspicion analysis"),
    ("save", "Save results"),
]

JD_PARSE_STEPS = [
    ("receive", "Receive JD text"),
    ("llm", "LLM extracting fields"),
    ("done", "Complete"),
]

JD_INDEX_STEPS = [
    ("chunk", "Chunk JD text"),
    ("embed", "Embed skill vectors"),
    ("index", "Write to vector store"),
    ("done", "Indexed"),
]

HR_REASSESS_STEPS = [
    ("collect", "Collect HR answers"),
    ("llm_reassess", "LLM re-evaluate suspicion"),
    ("update", "Update analysis"),
    ("done", "Complete"),
]


def _initial_steps(step_defs: list[tuple[str, str]]) -> list[dict[str, str]]:
    return [{"id": sid, "label": label, "status": "pending"} for sid, label in step_defs]


def _commit_with_retry(session, retries: int = 6) -> None:
    commit_with_retry(session, retries)


def _job_to_dict(job: ProcessingJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "job_type": job.job_type,
        "label": job.label,
        "status": job.status,
        "current_step": job.current_step,
        "steps": json.loads(job.steps_json or "[]"),
        "viz": json.loads(job.viz_json) if job.viz_json else None,
        "result": json.loads(job.result_json) if job.result_json else None,
        "error": job.error or "",
        "candidate_id": job.candidate_id,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


class JobService:
    def __init__(self) -> None:
        self._cancelled: set[int] = set()
        self._lock = threading.Lock()
        self._resume_slot = threading.Semaphore(1)

    def recover_stale_jobs(self) -> int:
        """Mark orphaned running jobs failed after a server restart."""
        session = get_session()
        count = 0
        try:
            stale = (
                session.query(ProcessingJob)
                .filter(ProcessingJob.status.in_(["pending", "running"]))
                .all()
            )
            for job in stale:
                steps = json.loads(job.steps_json or "[]")
                for step in steps:
                    if step["status"] in ("pending", "running"):
                        step["status"] = "failed"
                job.steps_json = json.dumps(steps)
                job.status = "failed"
                job.error = "Interrupted — please upload again"
                job.updated_at = datetime.utcnow()
                count += 1
            if count:
                _commit_with_retry(session)
            return count
        finally:
            session.close()

    def is_cancelled(self, job_id: int) -> bool:
        with self._lock:
            return job_id in self._cancelled

    def _raise_if_cancelled(self, job_id: int) -> None:
        if self.is_cancelled(job_id):
            raise JobCancelled(job_id)

    def cancel_job(self, job_id: int) -> bool:
        session = get_session()
        try:
            job = session.get(ProcessingJob, job_id)
            if not job:
                return False
            if job.status not in ("pending", "running"):
                return False
            with self._lock:
                self._cancelled.add(job_id)
            steps = json.loads(job.steps_json or "[]")
            for step in steps:
                if step["status"] in ("pending", "running"):
                    step["status"] = "failed"
            job.steps_json = json.dumps(steps)
            job.status = "cancelled"
            job.error = "Cancelled by user"
            job.updated_at = datetime.utcnow()
            if job.candidate_id:
                candidate = session.get(Candidate, job.candidate_id)
                if candidate and candidate.status == "processing":
                    candidate.status = "failed"
            _commit_with_retry(session)
            return True
        finally:
            session.close()

    def set_candidate_id(self, job_id: int, candidate_id: int) -> None:
        session = get_session()
        try:
            job = session.get(ProcessingJob, job_id)
            if job:
                job.candidate_id = candidate_id
                job.updated_at = datetime.utcnow()
                _commit_with_retry(session)
        finally:
            session.close()

    def create_job(self, job_type: str, label: str, step_defs: list[tuple[str, str]]) -> int:
        session = get_session()
        try:
            job = ProcessingJob(
                job_type=job_type,
                label=label,
                status="pending",
                current_step=step_defs[0][0] if step_defs else "",
                steps_json=json.dumps(_initial_steps(step_defs)),
            )
            session.add(job)
            _commit_with_retry(session)
            session.refresh(job)
            return job.id
        finally:
            session.close()

    def update_viz(self, job_id: int, viz: dict[str, Any]) -> None:
        session = get_session()
        try:
            job = session.get(ProcessingJob, job_id)
            if job:
                job.viz_json = json.dumps(viz)
                job.updated_at = datetime.utcnow()
                _commit_with_retry(session)
        except OperationalError:
            pass
        finally:
            session.close()

    def get_job(self, job_id: int) -> dict[str, Any] | None:
        session = get_session()
        try:
            job = session.get(ProcessingJob, job_id)
            return _job_to_dict(job) if job else None
        finally:
            session.close()

    def list_jobs(self, job_ids: list[int] | None = None, active_only: bool = False) -> list[dict[str, Any]]:
        session = get_session()
        try:
            q = session.query(ProcessingJob).order_by(ProcessingJob.created_at.desc())
            if job_ids:
                q = q.filter(ProcessingJob.id.in_(job_ids))
            elif active_only:
                q = q.filter(ProcessingJob.status.in_(["pending", "running"]))
            return [_job_to_dict(j) for j in q.limit(50).all()]
        finally:
            session.close()

    def _update_step(self, job_id: int, step_id: str, step_status: str = "running") -> None:
        session = get_session()
        try:
            job = session.get(ProcessingJob, job_id)
            if not job:
                return
            steps = json.loads(job.steps_json or "[]")
            for step in steps:
                if step["id"] == step_id:
                    step["status"] = step_status
                elif step_status == "running":
                    prev_ids = [s["id"] for s in steps]
                    if prev_ids.index(step["id"]) < prev_ids.index(step_id):
                        if step["status"] == "running":
                            step["status"] = "done"
            job.steps_json = json.dumps(steps)
            job.current_step = step_id
            job.status = "running"
            job.updated_at = datetime.utcnow()
            _commit_with_retry(session)
        finally:
            session.close()

    def _complete_job(
        self,
        job_id: int,
        result: dict[str, Any] | None = None,
        candidate_id: int | None = None,
        error: str | None = None,
    ) -> None:
        session = get_session()
        try:
            job = session.get(ProcessingJob, job_id)
            if not job:
                return
            steps = json.loads(job.steps_json or "[]")
            for step in steps:
                if step["status"] in ("pending", "running"):
                    step["status"] = "done" if not error else "failed"
            job.steps_json = json.dumps(steps)
            job.status = "failed" if error else "completed"
            job.result_json = json.dumps(result) if result else ""
            job.error = error or ""
            job.candidate_id = candidate_id
            job.updated_at = datetime.utcnow()
            _commit_with_retry(session)
        finally:
            session.close()

    def _make_callback(self, job_id: int) -> StepCallback:
        def on_step(step_id: str) -> None:
            self._raise_if_cancelled(job_id)
            self._update_step(job_id, step_id, "running")

        return on_step

    def make_cancel_check(self, job_id: int) -> Callable[[], None]:
        def check() -> None:
            self._raise_if_cancelled(job_id)

        return check

    def _run_thread(self, groq_api_key: str | None, target) -> None:
        def run() -> None:
            token = set_groq_api_key(groq_api_key)
            try:
                target()
            finally:
                reset_groq_api_key(token)

        threading.Thread(target=run, daemon=True).start()

    def start_resume_job(
        self,
        job_id: int,
        file_bytes: bytes,
        filename: str,
        target_jd_id: int | None = None,
        groq_api_key: str | None = None,
    ) -> None:
        def work() -> None:
            with self._resume_slot:
                session = get_session()
                try:
                    callback = self._make_callback(job_id)
                    cancel_check = self.make_cancel_check(job_id)
                    candidate = scoring_agent.process_resume(
                        session,
                        file_bytes,
                        filename,
                        UPLOADS_DIR,
                        target_jd_id=target_jd_id,
                        on_step=callback,
                        cancel_check=cancel_check,
                        job_id=job_id,
                    )
                    self._raise_if_cancelled(job_id)
                    self._complete_job(
                        job_id,
                        result={"candidate_id": candidate.id, "name": candidate.name, "status": candidate.status},
                        candidate_id=candidate.id,
                    )
                except JobCancelled:
                    self._mark_candidate_failed(session, job_id)
                except Exception as exc:
                    self._complete_job(job_id, error=str(exc))
                finally:
                    with self._lock:
                        self._cancelled.discard(job_id)
                    session.close()

        self._run_thread(groq_api_key, work)

    def _mark_candidate_failed(self, session, job_id: int) -> None:
        job = session.get(ProcessingJob, job_id)
        if job and job.candidate_id:
            candidate = session.get(Candidate, job.candidate_id)
            if candidate and candidate.status == "processing":
                candidate.status = "failed"
        commit_with_retry(session)

    def start_jd_parse_job(self, job_id: int, raw_text: str, groq_api_key: str | None = None) -> None:
        def work() -> None:
            try:
                callback = self._make_callback(job_id)
                self._raise_if_cancelled(job_id)
                callback("receive")
                self.update_viz(job_id, jd_parse_viz([], "receive", "JD text"))
                callback("llm")
                self.update_viz(job_id, jd_parse_viz([], "llm", "Extracting…"))
                parsed = parse_jd_text(raw_text)
                self._raise_if_cancelled(job_id)
                self.update_viz(
                    job_id,
                    jd_parse_viz(parsed.skills, "llm", parsed.role or parsed.title),
                )
                callback("done")
                self._complete_job(
                    job_id,
                    result={
                        "role": parsed.role,
                        "title": parsed.title,
                        "department": parsed.department,
                        "seniority": parsed.seniority,
                        "skills": parsed.skills,
                        "must_haves": parsed.must_haves,
                        "nice_to_haves": parsed.nice_to_haves,
                        "content": parsed.content,
                    },
                )
            except JobCancelled:
                pass
            except Exception as exc:
                self._complete_job(job_id, error=str(exc))
            finally:
                with self._lock:
                    self._cancelled.discard(job_id)

        self._run_thread(groq_api_key, work)

    def start_jd_index_job(self, job_id: int, jd_id: int) -> None:
        def work() -> None:
            import time

            session = get_session()
            try:
                callback = self._make_callback(job_id)
                jd = session.get(JobDescription, jd_id)
                if not jd:
                    raise ValueError(f"JD {jd_id} not found")

                callback("chunk")
                chunks = vector_store._chunk_jd(jd.title, jd.role, jd.content, jd.skills)
                self.update_viz(
                    job_id,
                    jd_index_viz(jd.title, jd.role, jd.skills, chunks, "chunk"),
                )
                time.sleep(0.6)

                callback("embed")
                self.update_viz(
                    job_id,
                    jd_index_viz(jd.title, jd.role, jd.skills, chunks, "embed"),
                )
                time.sleep(0.8)

                callback("index")
                self.update_viz(
                    job_id,
                    jd_index_viz(jd.title, jd.role, jd.skills, chunks, "index"),
                )
                time.sleep(0.5)

                callback("done")
                self.update_viz(
                    job_id,
                    jd_index_viz(jd.title, jd.role, jd.skills, chunks, "done"),
                )
                self._complete_job(job_id, result={"jd_id": jd_id, "role": jd.role})
            except Exception as exc:
                self._complete_job(job_id, error=str(exc))
            finally:
                session.close()

        threading.Thread(target=work, daemon=True).start()

    def start_hr_reassess_job(
        self, job_id: int, candidate_id: int, groq_api_key: str | None = None
    ) -> None:
        def work() -> None:
            callback = self._make_callback(job_id)
            try:
                callback("collect")
                result = reassess_candidate(candidate_id, on_step=callback)
                self._raise_if_cancelled(job_id)
                callback("done")
                self._complete_job(
                    job_id,
                    result=result,
                    candidate_id=candidate_id,
                )
            except JobCancelled:
                pass
            except Exception as exc:
                self._complete_job(job_id, candidate_id=candidate_id, error=str(exc))
            finally:
                with self._lock:
                    self._cancelled.discard(job_id)

        self._run_thread(groq_api_key, work)


job_service = JobService()
