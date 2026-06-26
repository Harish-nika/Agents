import streamlit as st

from app.config import UPLOADS_DIR
from app.db.models import get_session
from app.services import jd_service
from app.services.scoring_agent import scoring_agent


def render_upload() -> None:
    st.subheader("Upload Resumes")
    st.write(
        "Upload one or multiple resumes. Supports **digital PDFs**, **scanned PDFs**, "
        "**photos/scans (JPG/PNG)**, Word documents, and plain text. "
        "Layout differences and OCR noise are handled automatically."
    )

    session = get_session()
    try:
        active_jds = jd_service.list_active_jds(session)
        if not active_jds:
            st.warning("Add at least one role in **JD Manager** (sidebar) before uploading resumes.")
            return

        role_options = ["Match all active roles"] + [f"{jd.role} — {jd.title}" for jd in active_jds]
        target_role = st.selectbox("Score against", role_options)
        target_jd_id = None
        if target_role != "Match all active roles":
            for jd in active_jds:
                if f"{jd.role} — {jd.title}" == target_role:
                    target_jd_id = jd.id
                    break
    finally:
        session.close()

    files = st.file_uploader(
        "Select resume files",
        type=["pdf", "docx", "txt", "jpg", "jpeg", "png", "tiff", "bmp", "webp"],
        accept_multiple_files=True,
    )

    if files and st.button("Analyze Resumes", type="primary"):
        session = get_session()
        progress = st.progress(0)
        status = st.empty()
        results_log: list[str] = []

        try:
            for i, uploaded in enumerate(files):
                status.info(f"Processing {uploaded.name} ({i + 1}/{len(files)})…")
                try:
                    file_bytes = uploaded.read()
                    candidate = scoring_agent.process_resume(
                        session, file_bytes, uploaded.name, UPLOADS_DIR,
                        target_jd_id=target_jd_id,
                    )
                    method = f" [{candidate.parse_method}]" if candidate.parse_method else ""
                    results_log.append(f"✅ {uploaded.name} → {candidate.name}{method}")
                except Exception as exc:
                    results_log.append(f"❌ {uploaded.name} → {exc}")
                progress.progress((i + 1) / len(files))

            status.success("Batch processing complete.")
            for line in results_log:
                st.write(line)
        finally:
            session.close()
