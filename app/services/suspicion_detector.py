from pydantic import BaseModel, Field

from app.config import MAX_RESUME_CHARS
from app.services.llm_client import llm_client
from app.services.scoring_prompts import SUSPICION_SYSTEM


class SuspicionResult(BaseModel):
    suspicion_score: float = Field(ge=0, le=100)
    flags: list[str] = Field(default_factory=list)
    hr_questions: list[str] = Field(default_factory=list)
    reasoning: str = ""


SYSTEM_PROMPT = SUSPICION_SYSTEM


def detect_suspicion(
    resume_text: str, jd_role: str = "", verification_context: str = ""
) -> SuspicionResult:
    truncated = resume_text[:MAX_RESUME_CHARS]
    role_note = f"\nTarget role: {jd_role}\n" if jd_role else ""
    verify_note = f"\nVerification report:\n{verification_context}\n" if verification_context else ""
    user_prompt = f"""Analyze this resume for authenticity concerns:{role_note}{verify_note}

{truncated}

Return JSON only."""
    data = llm_client.chat_json(SYSTEM_PROMPT, user_prompt, use_gpu=True, fast=llm_client.using_groq())
    return SuspicionResult(
        suspicion_score=float(data.get("suspicion_score", 0)),
        flags=[str(f) for f in data.get("flags", [])],
        hr_questions=[str(q) for q in data.get("hr_questions", [])],
        reasoning=str(data.get("reasoning", "")),
    )
