import streamlit as st

from app.config import SUSPICION_THRESHOLD
from app.db.models import AnalysisResult, Candidate, JobDescription, get_session
from app.services import jd_service
from app.ui.theme import score_badge


def render_results() -> None:
    st.subheader("Analysis Results")

    session = get_session()
    try:
        active_jds = jd_service.list_active_jds(session)
        role_filter = st.selectbox(
            "Filter by role",
            ["All roles"] + [f"{jd.role} — {jd.title}" for jd in active_jds],
        )
        min_score = st.slider("Minimum overall score", 0, 100, 0)

        candidates = (
            session.query(Candidate)
            .filter(Candidate.status == "analyzed")
            .order_by(Candidate.created_at.desc())
            .all()
        )
        if not candidates:
            st.info("No analyzed candidates yet.")
            return

        shown = 0
        for candidate in candidates:
            analyses = (
                session.query(AnalysisResult)
                .filter(AnalysisResult.candidate_id == candidate.id)
                .order_by(AnalysisResult.overall_score.desc())
                .all()
            )
            if not analyses:
                continue

            best = analyses[0]
            if best.overall_score < min_score:
                continue
            if role_filter != "All roles":
                jd = session.get(JobDescription, best.jd_id)
                label = f"{jd.role} — {jd.title}" if jd else ""
                if label != role_filter:
                    continue

            shown += 1
            with st.expander(
                f"{candidate.name} — Best fit: {best.recommended_role} ({best.overall_score:.0f}/100)",
                expanded=False,
            ):
                parse_info = f" · Parsed via {candidate.parse_method}" if candidate.parse_method else ""
                st.write(
                    f"**Email:** {candidate.email or 'N/A'} | **Phone:** {candidate.phone or 'N/A'}{parse_info}"
                )
                st.markdown(
                    f"Suspicion Score: {score_badge(best.suspicion_score)}",
                    unsafe_allow_html=True,
                )

                if best.suspicion_flags:
                    st.write("**Suspicion Flags:**")
                    for flag in best.suspicion_flags:
                        st.markdown(f'<div class="flag-item">{flag}</div>', unsafe_allow_html=True)

                for analysis in analyses:
                    jd = session.get(JobDescription, analysis.jd_id)
                    st.markdown("---")
                    st.write(f"### {jd.title if jd else 'Unknown JD'} ({jd.role if jd else ''})")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Technical", f"{analysis.technical_score:.0f}")
                    col2.metric("HR Fit", f"{analysis.hr_score:.0f}")
                    col3.metric("Overall", f"{analysis.overall_score:.0f}")
                    col4.metric("Similarity", f"{analysis.similarity_score:.0%}")

                    st.write(analysis.fit_summary)
                    if analysis.strengths:
                        st.write("**Strengths:** " + ", ".join(analysis.strengths))
                    if analysis.gaps:
                        st.write("**Gaps:** " + ", ".join(analysis.gaps))

        if shown == 0:
            st.warning("No candidates match the current filters.")
    finally:
        session.close()
