import streamlit as st

from app.config import (
    OLLAMA_BASE_URL,
    OLLAMA_EMBED_MODEL,
    OLLAMA_LLM_MODEL,
    SUSPICION_THRESHOLD,
)
from app.services.ollama_client import ollama_client


def render_settings() -> None:
    st.subheader("Settings")
    st.write("Current configuration (read from environment):")

    st.code(
        f"""OLLAMA_BASE_URL={OLLAMA_BASE_URL}
OLLAMA_LLM_MODEL={OLLAMA_LLM_MODEL}
OLLAMA_EMBED_MODEL={OLLAMA_EMBED_MODEL}
SUSPICION_THRESHOLD={SUSPICION_THRESHOLD}"""
    )

    if ollama_client.health_check():
        st.success("Ollama connection: OK")
    else:
        st.error("Ollama connection: FAILED")

    st.info("To change settings, edit the `.env` file and restart the service.")
