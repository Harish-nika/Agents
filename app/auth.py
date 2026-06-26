import streamlit as st

from app.config import APP_PASSWORD, APP_USERNAME


def require_auth() -> bool:
    if st.session_state.get("authenticated"):
        return True

    st.markdown("### Sign in to Fact Entry Recruiting Agent")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", type="primary", use_container_width=True)

    if submitted:
        if username == APP_USERNAME and password == APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Invalid username or password.")
    return False


def logout_button() -> None:
    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()
