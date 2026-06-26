import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
CHROMA_DIR = DATA_DIR / "chroma"
DB_PATH = DATA_DIR / "ats.db"

load_dotenv(ROOT_DIR / ".env")

APP_USERNAME = os.getenv("APP_USERNAME", "hr")
APP_PASSWORD = os.getenv("APP_PASSWORD", "change-me")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_GPU_BASE_URL = os.getenv("OLLAMA_GPU_BASE_URL", "") or OLLAMA_BASE_URL
OLLAMA_LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "llama3.1:8b")
OLLAMA_FAST_MODEL = os.getenv("OLLAMA_FAST_MODEL", "qwen2.5:0.5b")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
SUSPICION_THRESHOLD = int(os.getenv("SUSPICION_THRESHOLD", "60"))
PORT_RANGE_START = int(os.getenv("PORT_RANGE_START", "8510"))
PORT_RANGE_END = int(os.getenv("PORT_RANGE_END", "8520"))
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "300"))
GROQ_LLM_MODEL = os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile")
GROQ_FAST_MODEL = os.getenv("GROQ_FAST_MODEL", "llama-3.1-8b-instant")
GROQ_TIMEOUT = int(os.getenv("GROQ_TIMEOUT", "120"))
TOP_K_JDS = 3
MAX_RESUME_CHARS = 12000


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
