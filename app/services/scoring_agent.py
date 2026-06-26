import json

from collections.abc import Callable

from pydantic import BaseModel, Field

from app.config import MAX_RESUME_CHARS, SUSPICION_THRESHOLD, TOP_K_JDS
from app.db.models import (
    AnalysisResult,
    Candidate,
    HRQuestion,
    JobDescription,
    ProcessingJob,
    commit_with_retry,
)
from app.services.candidate_verification import (
    VerificationReport,
    questions_from_report,
    report_summary_for_prompt,
    verify_resume,
)
from app.services.jd_format import jd_prompt_block
from app.services.jd_service import list_active_jds
from app.services.llm_client import llm_client
from app.services.scoring_prompts import SCORING_SYSTEM
from app.services.resume_parser import (
    extract_contact_info,
    normalize_unstructured_resume,
    parse_resume,
)
from app.services.suspicion_detector import detect_suspicion
from app.services.vector_store import vector_store
from app.services.viz_snapshots import resume_parse_viz, resume_search_viz


class ScoreResult(BaseModel):
    technical_score: float = Field(ge=0, le=100)
    hr_score: float = Field(ge=0, le=100)
    overall_score: float = Field(ge=0, le=100)
    fit_summary: str = ""
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    recommended_role: str = ""


SCORING_SYSTEM_PROMPT = SCORING_SYSTEM


def _save_merged_hr_questions(
    session,
    candidate_id: int,
    analysis_id: int,
    verification_report: VerificationReport,
    suspicion_questions: list[str],
    suspicion_score: float,
) -> None:
    seen: set[str] = set()
    for item in questions_from_report(verification_report):
        q_norm = item["question"].strip().lower()
        if not q_norm or q_norm in seen:
            continue
        seen.add(q_norm)
        session.add(
            HRQuestion(
                candidate_id=candidate_id,
                analysis_id=analysis_id,
                question=item["question"],
                category=item.get("category", "general"),
                source_flag=item.get("source_flag", ""),
                resume_excerpt=item.get("resume_excerpt", ""),
                status="pending",
            )
        )
    if suspicion_score >= SUSPICION_THRESHOLD:
        for question in suspicion_questions:
            q_norm = question.strip().lower()
            if q_norm and q_norm not in seen:
                seen.add(q_norm)
                session.add(
                    HRQuestion(
                        candidate_id=candidate_id,
                        analysis_id=analysis_id,
                        question=question,
                        category="credential",
                        source_flag="suspicion_llm",
                        status="pending",
                    )
                )


class ScoringAgent:
    def process_resume(
        self,
        session,
        file_bytes: bytes,
        filename: str,
        upload_dir,
        target_jd_id: int | None = None,
        on_step: Callable[[str], None] | None = None,
        cancel_check: Callable[[], None] | None = None,
        job_id: int | None = None,
    ) -> Candidate:
        def step(sid: str) -> None:
            if cancel_check:
                cancel_check()
            if on_step:
                on_step(sid)

        step("receive")
        parse_result = parse_resume(file_bytes, filename)
        step("parse")
        if job_id is not None:
            from app.services.job_service import job_service

            job_service.update_viz(
                job_id,
                resume_parse_viz(parse_result.text[:2000], "parse"),
            )
        raw_text = normalize_unstructured_resume(
            parse_result.text, parse_result, cancel_check=cancel_check
        )
        step("normalize")
        if job_id is not None:
            from app.services.job_service import job_service

            job_service.update_viz(job_id, resume_parse_viz(raw_text, "normalize"))
        parse_note = f"{parse_result.method} — {parse_result.structure_note}"
        contact = extract_contact_info(raw_text)

        email_key = contact["email"].strip().lower()
        existing: Candidate | None = None
        if email_key:
            existing = (
                session.query(Candidate)
                .filter(Candidate.email.ilike(email_key))
                .order_by(Candidate.created_at.desc())
                .first()
            )

        if existing:
            candidate = existing
            candidate.name = contact["name"] or existing.name
            candidate.phone = contact["phone"] or existing.phone
            candidate.raw_text = raw_text
            candidate.parse_method = parse_result.method
            candidate.status = "processing"
            for old in session.query(AnalysisResult).filter(AnalysisResult.candidate_id == existing.id).all():
                session.query(HRQuestion).filter(HRQuestion.analysis_id == old.id).delete()
                session.delete(old)
            session.flush()
        else:
            candidate = Candidate(
                name=contact["name"],
                email=contact["email"],
                phone=contact["phone"],
                file_path="",
                raw_text=raw_text,
                parse_method=parse_result.method,
                status="processing",
            )
            session.add(candidate)
            session.flush()

        if job_id is not None:
            job = session.get(ProcessingJob, job_id)
            if job:
                job.candidate_id = candidate.id

        candidate_dir = upload_dir / str(candidate.id)
        candidate_dir.mkdir(parents=True, exist_ok=True)
        file_path = candidate_dir / filename
        file_path.write_bytes(file_bytes)
        candidate.file_path = str(file_path)

        commit_with_retry(session)

        step("verify")
        verification_report = verify_resume(raw_text)
        candidate.structured_json = json.dumps(verification_report.structured)
        candidate.verification_json = json.dumps(verification_report.to_dict())
        commit_with_retry(session)

        active_jds = list_active_jds(session)
        if not active_jds:
            candidate.status = "failed"
            session.commit()
            raise ValueError("No active job descriptions found. Create a JD first.")

        step("embed")
        if job_id is not None:
            from app.services.job_service import job_service

            job_service.update_viz(job_id, resume_parse_viz(raw_text, "embed"))
        matches = vector_store.search_jds(raw_text, top_k=TOP_K_JDS)
        if target_jd_id:
            target_jd = session.query(JobDescription).filter(JobDescription.id == target_jd_id).first()
            if target_jd:
                matches = [{"jd_id": target_jd.id, "title": target_jd.title, "role": target_jd.role, "similarity": 1.0}]
        else:
            by_id: dict[int, dict] = {int(m["jd_id"]): m for m in matches}
            for jd in active_jds:
                if jd.id not in by_id:
                    by_id[jd.id] = {
                        "jd_id": jd.id,
                        "title": jd.title,
                        "role": jd.role,
                        "similarity": 0.0,
                    }
            matches = sorted(by_id.values(), key=lambda m: float(m.get("similarity", 0)), reverse=True)

        step("search")
        if job_id is not None:
            from app.services.job_service import job_service

            job_service.update_viz(job_id, resume_search_viz(raw_text, matches, "search"))

        primary_jd = session.query(JobDescription).filter(JobDescription.id == matches[0]["jd_id"]).first()
        jd_role = primary_jd.role if primary_jd else ""
        verify_context = report_summary_for_prompt(verification_report)
        step("suspicion")
        suspicion = detect_suspicion(raw_text, jd_role=jd_role, verification_context=verify_context)
        step("score")
        best_overall = 0.0
        recommended_role = ""
        best_analysis_id: int | None = None
        best_jd_id: int | None = None

        for match in matches:
            jd = session.query(JobDescription).filter(JobDescription.id == match["jd_id"]).first()
            if not jd:
                continue

            score = self._score_candidate(raw_text, jd, parse_note, verify_context)

            analysis = AnalysisResult(
                candidate_id=candidate.id,
                jd_id=jd.id,
                technical_score=score.technical_score,
                hr_score=score.hr_score,
                overall_score=score.overall_score,
                fit_summary=score.fit_summary,
                strengths_json="[]",
                gaps_json="[]",
                suspicion_score=suspicion.suspicion_score,
                suspicion_flags_json="[]",
                suspicion_reasoning=suspicion.reasoning,
                recommended_role=score.recommended_role or jd.role,
                similarity_score=float(match.get("similarity", 0.0)),
            )
            analysis.strengths_json = json.dumps(score.strengths)
            analysis.gaps_json = json.dumps(score.gaps)
            analysis.suspicion_flags_json = json.dumps(suspicion.flags)
            session.add(analysis)
            session.flush()
            if score.overall_score >= best_overall:
                best_overall = score.overall_score
                recommended_role = score.recommended_role or jd.role
                best_jd_id = jd.id
                best_analysis_id = analysis.id

        if best_analysis_id and (verification_report.anomalies or suspicion.hr_questions):
            _save_merged_hr_questions(
                session,
                candidate.id,
                best_analysis_id,
                verification_report,
                suspicion.hr_questions,
                suspicion.suspicion_score,
            )

        if job_id is not None and best_jd_id is not None:
            from app.services.job_service import job_service

            job_service.update_viz(
                job_id,
                resume_search_viz(raw_text, matches, "score", active_jd_id=best_jd_id),
            )

        candidate.status = "analyzed"
        step("save")
        commit_with_retry(session)
        session.refresh(candidate)
        return candidate

    def _score_candidate(
        self,
        resume_text: str,
        jd: JobDescription,
        parse_note: str = "",
        verification_context: str = "",
    ) -> ScoreResult:
        truncated_resume = resume_text[:MAX_RESUME_CHARS]
        source_note = f"\nResume source note: {parse_note}\n" if parse_note else ""
        verify_note = f"\nVerification findings:\n{verification_context}\n" if verification_context else ""
        user_prompt = f"""Job Description:
{jd_prompt_block(jd)}
{source_note}{verify_note}
Candidate Resume:
{truncated_resume}

Score this candidate for the role above. Cite specific resume evidence. Return JSON only."""
        data = llm_client.chat_json(
            SCORING_SYSTEM_PROMPT, user_prompt, use_gpu=True, fast=llm_client.using_groq()
        )
        return ScoreResult(
            technical_score=float(data.get("technical_score", 0)),
            hr_score=float(data.get("hr_score", 0)),
            overall_score=float(data.get("overall_score", 0)),
            fit_summary=str(data.get("fit_summary", "")),
            strengths=[str(s) for s in data.get("strengths", [])],
            gaps=[str(g) for g in data.get("gaps", [])],
            recommended_role=str(data.get("recommended_role", jd.role)),
        )


scoring_agent = ScoringAgent()
