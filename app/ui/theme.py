import streamlit as st


def apply_theme() -> None:
    st.set_page_config(
        page_title="Fact Entry Recruiting Agent",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }

        .main-header {
            background: linear-gradient(135deg, #0f2744 0%, #1a4d6e 50%, #1e7a8c 100%);
            padding: 1.5rem 2rem;
            border-radius: 12px;
            margin-bottom: 1.5rem;
            color: white;
        }
        .main-header h1 {
            margin: 0;
            font-size: 1.8rem;
            font-weight: 700;
        }
        .main-header p {
            margin: 0.3rem 0 0 0;
            opacity: 0.85;
            font-size: 0.95rem;
        }

        .metric-card {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 1rem 1.2rem;
            text-align: center;
        }
        .metric-card .value {
            font-size: 2rem;
            font-weight: 700;
            color: #0f2744;
        }
        .metric-card .label {
            font-size: 0.85rem;
            color: #64748b;
            margin-top: 0.2rem;
        }

        .score-badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.9rem;
        }
        .score-high { background: #dcfce7; color: #166534; }
        .score-mid { background: #fef9c3; color: #854d0e; }
        .score-low { background: #fee2e2; color: #991b1b; }

        .result-card {
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 1.2rem;
            margin-bottom: 1rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }

        .flag-item {
            background: #fff7ed;
            border-left: 3px solid #f97316;
            padding: 0.5rem 0.8rem;
            margin: 0.3rem 0;
            border-radius: 0 6px 6px 0;
            font-size: 0.9rem;
        }

        div[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0f2744 0%, #1a3a5c 100%);
        }
        div[data-testid="stSidebar"] * {
            color: #e2e8f0 !important;
        }
        div[data-testid="stSidebar"] .stRadio label {
            font-size: 0.95rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.markdown(
        """
        <div class="main-header">
            <h1>Fact Entry Recruiting Agent</h1>
            <p>AI-powered resume screening with local LLM intelligence</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def score_badge(score: float) -> str:
    css = "score-high" if score >= 70 else "score-mid" if score >= 50 else "score-low"
    return f'<span class="score-badge {css}">{score:.0f}</span>'
