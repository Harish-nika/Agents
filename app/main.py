import streamlit as st

from app.auth import logout_button, require_auth
from app.db.models import init_db
from app.ui.pages import dashboard, hr_questions, jds, results, settings, upload
from app.ui.sidebar_jd_manager import render_sidebar_jd_manager, should_show_jd_editor
from app.ui.theme import apply_theme, render_header

PAGES = {
    "Dashboard": dashboard.render_dashboard,
    "Upload Resumes": upload.render_upload,
    "Analysis Results": results.render_results,
    "HR Questions": hr_questions.render_hr_questions,
    "Settings": settings.render_settings,
}


def main() -> None:
    apply_theme()
    init_db()

    if not require_auth():
        return

    render_header()

    st.sidebar.title("Navigation")
    logout_button()
    render_sidebar_jd_manager()

    page = st.sidebar.radio("Go to", list(PAGES.keys()))

    if should_show_jd_editor():
        jds.render_jd_editor()
    else:
        PAGES[page]()


if __name__ == "__main__":
    main()
