import streamlit as st

from app.db.models import JDVersion, get_session
from app.services import jd_service
from app.services.jd_parser import SENIORITY_LEVELS, parse_jd_text


def _form_defaults(existing) -> dict:
    parsed = st.session_state.get("parsed_jd")
    if parsed and not existing:
        return {
            "role": parsed.role,
            "title": parsed.title,
            "department": parsed.department,
            "seniority": parsed.seniority if parsed.seniority in SENIORITY_LEVELS else "Mid",
            "skills_text": ", ".join(parsed.skills),
            "content": parsed.content,
            "must_haves": parsed.must_haves,
            "nice_to_haves": parsed.nice_to_haves,
        }
    return {
        "role": existing.role if existing else "",
        "title": existing.title if existing else "",
        "department": existing.department if existing else "",
        "seniority": existing.seniority
        if existing and existing.seniority in SENIORITY_LEVELS
        else "Mid",
        "skills_text": ", ".join(existing.skills) if existing else "",
        "content": existing.content if existing else "",
        "must_haves": [],
        "nice_to_haves": [],
    }


def render_jd_editor() -> None:
    """Full-page JD create/edit with AI paste parsing."""
    panel = st.session_state.get("jd_panel", "edit")
    session = get_session()

    try:
        if panel == "new":
            st.subheader("Create New Role & Job Description")
            existing = None
        else:
            edit_id = st.session_state.get("edit_jd_id") or st.session_state.get("selected_jd_id")
            existing = jd_service.get_jd(session, edit_id) if edit_id else None
            if existing:
                st.subheader(f"Edit JD — {existing.role}")
                updated = existing.updated_at.strftime("%d %b %Y %H:%M") if existing.updated_at else "—"
                st.caption(f"Last updated: {updated} · Changes are re-indexed automatically.")
            else:
                st.subheader("Edit Job Description")
                st.warning("Select a role from the sidebar JD Manager.")

        tab_paste, tab_form, tab_history = st.tabs(
            ["Paste & AI Parse", "Review & Save", "Version History"]
        )

        with tab_paste:
            st.markdown(
                "Paste a job description from email, Word, LinkedIn, or any source. "
                "AI will extract **role**, **title**, **skills**, **requirements**, and more."
            )
            raw_jd = st.text_area(
                "Paste full JD text here",
                height=280,
                placeholder="Paste the complete job description…",
                key="jd_raw_paste",
            )
            if st.button("Parse with AI", type="primary", key="parse_jd_btn"):
                if not raw_jd.strip():
                    st.error("Paste a job description first.")
                else:
                    with st.spinner("Analyzing job description…"):
                        try:
                            parsed = parse_jd_text(raw_jd)
                            st.session_state.parsed_jd = parsed
                            st.success("Parsed successfully! Review fields in the **Review & Save** tab.")
                        except Exception as exc:
                            st.error(f"Parse failed: {exc}")

            if st.session_state.get("parsed_jd"):
                p = st.session_state.parsed_jd
                st.markdown("**Preview**")
                c1, c2 = st.columns(2)
                c1.write(f"**Role:** {p.role}")
                c1.write(f"**Title:** {p.title}")
                c2.write(f"**Department:** {p.department or '—'}")
                c2.write(f"**Seniority:** {p.seniority}")
                if p.skills:
                    st.write(f"**Skills:** {', '.join(p.skills)}")
                if p.must_haves:
                    st.write(f"**Must have:** {', '.join(p.must_haves)}")
                if p.nice_to_haves:
                    st.write(f"**Nice to have:** {', '.join(p.nice_to_haves)}")

        with tab_form:
            defaults = _form_defaults(existing)

            with st.form("jd_form", clear_on_submit=False):
                role = st.text_input("Role *", value=defaults["role"])
                title = st.text_input("Job Title *", value=defaults["title"])
                c1, c2 = st.columns(2)
                department = c1.text_input("Department", value=defaults["department"])
                seniority = c2.selectbox(
                    "Seniority",
                    SENIORITY_LEVELS,
                    index=SENIORITY_LEVELS.index(defaults["seniority"]),
                )
                skills_text = st.text_input(
                    "Required Skills (comma-separated)",
                    value=defaults["skills_text"],
                )
                content = st.text_area("Job Description *", value=defaults["content"], height=320)
                submitted = st.form_submit_button("Save & Re-index", type="primary", use_container_width=True)

            if submitted:
                if not title or not role or not content:
                    st.error("Role, job title, and description are required.")
                else:
                    skills = [s.strip() for s in skills_text.split(",") if s.strip()]
                    if existing:
                        jd_service.update_jd(
                            session, existing.id, title, role, department, seniority, content, skills
                        )
                        st.session_state.selected_jd_id = existing.id
                        st.success(f"Updated **{role}** — vector index refreshed.")
                    else:
                        jd = jd_service.create_jd(
                            session, title, role, department, seniority, content, skills
                        )
                        st.session_state.selected_jd_id = jd.id
                        st.success(f"Created **{role}** — ready for resume matching.")
                    st.session_state.jd_panel = None
                    st.session_state.pop("parsed_jd", None)
                    st.session_state.pop("edit_jd_id", None)
                    st.rerun()

        with tab_history:
            if existing:
                versions = (
                    session.query(JDVersion)
                    .filter(JDVersion.jd_id == existing.id)
                    .order_by(JDVersion.version.desc())
                    .all()
                )
                if not versions:
                    st.info("No version history yet.")
                for v in versions:
                    with st.expander(f"Version {v.version} — {v.created_at.strftime('%d %b %Y %H:%M')}"):
                        st.text(v.content_snapshot[:2000])
            else:
                st.info("Save a JD first to see version history.")

        if st.button("← Back to app", key="jd_back"):
            st.session_state.jd_panel = None
            st.session_state.pop("edit_jd_id", None)
            st.session_state.pop("parsed_jd", None)
            st.rerun()

        with st.expander("All roles (including archived)"):
            for jd in jd_service.list_all_jds(session):
                status = "Active" if jd.is_active else "Archived"
                cols = st.columns([4, 1, 1])
                cols[0].write(f"**{jd.role}** — {jd.title} ({status})")
                if jd.is_active and cols[1].button("Open", key=f"open_jd_{jd.id}"):
                    st.session_state.selected_jd_id = jd.id
                    st.session_state.edit_jd_id = jd.id
                    st.session_state.jd_panel = "edit"
                    st.rerun()
                if jd.is_active and cols[2].button("Archive", key=f"arch_jd_{jd.id}"):
                    jd_service.archive_jd(session, jd.id)
                    st.rerun()
                elif not jd.is_active and cols[2].button("Restore", key=f"rest_jd_{jd.id}"):
                    jd_service.restore_jd(session, jd.id)
                    st.rerun()

        if st.button("Re-index all active JDs"):
            count = jd_service.reindex_all_jds(session)
            st.success(f"Re-indexed {count} job descriptions.")
    finally:
        session.close()
