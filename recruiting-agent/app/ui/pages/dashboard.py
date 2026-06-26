import streamlit as st
from sqlalchemy import func

from app.db.models import AnalysisResult, Candidate, HRQuestion, JobDescription, get_session
from app.services.ollama_client import ollama_client


def render_dashboard() -> None:
    session = get_session()
    try:
        jd_count = session.query(JobDescription).filter(JobDescription.is_active.is_(True)).count()
        candidate_count = session.query(Candidate).count()
        analyzed_count = session.query(Candidate).filter(Candidate.status == "analyzed").count()
        failed_count = session.query(Candidate).filter(Candidate.status == "failed").count()
        pending_questions = (
            session.query(HRQuestion).filter(HRQuestion.status == "pending").count()
        )
        avg_score = (
            session.query(func.avg(AnalysisResult.overall_score)).scalar() or 0.0
        )

        ollama_ok = ollama_client.health_check()

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Active JDs", jd_count)
        c2.metric("Candidates", candidate_count)
        c3.metric("Analyzed", analyzed_count)
        c4.metric("Failed", failed_count)
        c5.metric("Avg Score", f"{avg_score:.0f}")
        c6.metric("HR Questions", pending_questions)

        if ollama_ok:
            st.success("Ollama is online and ready.")
        else:
            st.error("Ollama is not reachable. Analysis will fail until it is running.")

        if jd_count == 0:
            st.warning("No job descriptions yet. Use **JD Manager** in the sidebar → **New Role** → paste a JD.")

        st.subheader("Recent Analyses")
        recent = (
            session.query(AnalysisResult)
            .order_by(AnalysisResult.created_at.desc())
            .limit(10)
            .all()
        )
        if not recent:
            st.info("No analyses yet. Upload resumes to get started.")
            return

        for analysis in recent:
            candidate = session.get(Candidate, analysis.candidate_id)
            jd = session.get(JobDescription, analysis.jd_id)
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                col1.write(f"**{candidate.name if candidate else 'Unknown'}** — {jd.title if jd else 'N/A'}")
                col2.write(analysis.fit_summary[:80] + "..." if len(analysis.fit_summary) > 80 else analysis.fit_summary)
                col3.write(f"Score: **{analysis.overall_score:.0f}**")
                col4.write(f"Suspicion: **{analysis.suspicion_score:.0f}**")
    finally:
        session.close()
