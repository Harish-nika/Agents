import streamlit as st

from app.db.models import AnalysisResult, Candidate, HRQuestion, JobDescription, get_session


def render_hr_questions() -> None:
    st.subheader("HR Questions Queue")
    st.write("Clarifying questions for candidates with suspicious resumes.")

    session = get_session()
    try:
        questions = (
            session.query(HRQuestion)
            .order_by(HRQuestion.created_at.desc())
            .all()
        )
        if not questions:
            st.info("No HR questions pending.")
            return

        for q in questions:
            candidate = session.query(Candidate).get(q.candidate_id)
            analysis = session.query(AnalysisResult).get(q.analysis_id)
            jd = session.query(JobDescription).get(analysis.jd_id) if analysis else None

            status_color = {"pending": "🟡", "answered": "🟢", "dismissed": "⚪"}.get(q.status, "⚪")
            with st.container():
                st.markdown(
                    f"""
                    <div class="result-card">
                        <strong>{status_color} {candidate.name if candidate else 'Unknown'}</strong>
                        — {jd.title if jd else 'N/A'}
                        <br><em>Suspicion: {analysis.suspicion_score:.0f}/100</em>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.write(q.question)

                col1, col2, col3 = st.columns(3)
                if col1.button("Mark Answered", key=f"ans_{q.id}"):
                    q.status = "answered"
                    session.commit()
                    st.rerun()
                if col2.button("Dismiss", key=f"dismiss_{q.id}"):
                    q.status = "dismissed"
                    session.commit()
                    st.rerun()
                if col3.button("Reopen", key=f"reopen_{q.id}"):
                    q.status = "pending"
                    session.commit()
                    st.rerun()
    finally:
        session.close()
