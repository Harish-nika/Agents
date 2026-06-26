"""Persistent JD Manager panel in the sidebar — roles and editable job descriptions."""

import streamlit as st

from app.db.models import get_session
from app.services import jd_service


def render_sidebar_jd_manager() -> int | None:
    """Render JD Manager in sidebar. Returns selected jd_id or None."""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### JD Manager")
    st.sidebar.caption("Manage roles and update job descriptions anytime.")

    session = get_session()
    try:
        active_jds = jd_service.list_active_jds(session)
        if not active_jds:
            st.sidebar.info("No roles yet. Create one below.")
        else:
            role_options = {f"{jd.role} — {jd.title}": jd.id for jd in active_jds}
            labels = list(role_options.keys())
            current_id = st.session_state.get("selected_jd_id")
            default_idx = 0
            if current_id:
                for i, label in enumerate(labels):
                    if role_options[label] == current_id:
                        default_idx = i
                        break

            selected_label = st.sidebar.selectbox(
                "Active roles",
                labels,
                index=default_idx if labels else 0,
                key="sidebar_jd_select",
            )
            selected_id = role_options[selected_label]
            st.session_state.selected_jd_id = selected_id

            jd = jd_service.get_jd(session, selected_id)
            if jd:
                updated = jd.updated_at.strftime("%d %b %Y") if jd.updated_at else "—"
                st.sidebar.markdown(
                    f"**{jd.role}**  \n"
                    f"<small>{jd.department or 'No dept'} · {jd.seniority} · updated {updated}</small>",
                    unsafe_allow_html=True,
                )
                if jd.skills:
                    st.sidebar.caption(f"Skills: {', '.join(jd.skills[:6])}{'…' if len(jd.skills) > 6 else ''}")

        col1, col2 = st.sidebar.columns(2)
        if col1.button("Edit JD", use_container_width=True, key="sidebar_edit_jd"):
            st.session_state.jd_panel = "edit"
            if st.session_state.get("selected_jd_id"):
                st.session_state.edit_jd_id = st.session_state.selected_jd_id
            st.rerun()
        if col2.button("New Role", use_container_width=True, key="sidebar_new_jd"):
            st.session_state.jd_panel = "new"
            st.session_state.pop("edit_jd_id", None)
            st.session_state.pop("parsed_jd", None)
            st.rerun()

        return st.session_state.get("selected_jd_id")
    finally:
        session.close()


def should_show_jd_editor() -> bool:
    return st.session_state.get("jd_panel") in ("edit", "new")
