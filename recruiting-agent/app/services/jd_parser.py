from pydantic import BaseModel, Field

from app.config import MAX_RESUME_CHARS
from app.services.llm_client import llm_client

SENIORITY_LEVELS = ["Junior", "Mid", "Senior", "Lead", "Manager"]

SYSTEM_PROMPT = """You are an expert HR analyst. Parse a raw job description pasted by HR.
Extract structured fields from messy or unstructured text (bullet points, paragraphs, emails, etc.).
Do not invent requirements not present in the source text.
Return JSON with keys:
- role (string): primary role name e.g. "Senior Python Developer"
- title (string): full job title as it would appear in a listing
- department (string): department or team, empty string if unknown
- seniority (string): one of Junior, Mid, Senior, Lead, Manager — infer from text
- skills (list of strings): required technical/professional skills
- must_haves (list of strings): hard requirements
- nice_to_haves (list of strings): preferred but optional
- content (string): clean formatted JD with sections RESPONSIBILITIES, REQUIREMENTS, PREFERRED
"""


class ParsedJD(BaseModel):
    role: str = ""
    title: str = ""
    department: str = ""
    seniority: str = "Mid"
    skills: list[str] = Field(default_factory=list)
    must_haves: list[str] = Field(default_factory=list)
    nice_to_haves: list[str] = Field(default_factory=list)
    content: str = ""


def parse_jd_text(raw_text: str) -> ParsedJD:
    if not raw_text.strip():
        raise ValueError("Paste a job description first.")

    user_prompt = f"""Parse this job description:

{raw_text[:MAX_RESUME_CHARS]}

Return JSON only."""
    data = llm_client.chat_json(SYSTEM_PROMPT, user_prompt, fast=True)

    seniority = str(data.get("seniority", "Mid"))
    if seniority not in SENIORITY_LEVELS:
        seniority = _infer_seniority(seniority)

    skills = [str(s) for s in data.get("skills", [])]
    must_haves = [str(s) for s in data.get("must_haves", [])]
    nice_to_haves = [str(s) for s in data.get("nice_to_haves", [])]

    content = _normalize_parsed_content(data.get("content", ""))
    if not content:
        content = _build_content(raw_text, must_haves, nice_to_haves)

    return ParsedJD(
        role=str(data.get("role", "")).strip(),
        title=str(data.get("title", "")).strip(),
        department=str(data.get("department", "")).strip(),
        seniority=seniority,
        skills=skills,
        must_haves=must_haves,
        nice_to_haves=nice_to_haves,
        content=content,
    )


def _normalize_parsed_content(raw_content) -> str:
    from app.services.jd_format import dict_to_jd_text, normalize_jd_content

    if isinstance(raw_content, dict):
        return dict_to_jd_text(raw_content)
    text = str(raw_content or "").strip()
    if not text:
        return ""
    return normalize_jd_content(text)


def _infer_seniority(text: str) -> str:
    lower = text.lower()
    for level in ["Manager", "Lead", "Senior", "Junior", "Mid"]:
        if level.lower() in lower:
            return level
    return "Mid"


def _build_content(raw: str, must_haves: list[str], nice_to_haves: list[str]) -> str:
    parts = [raw.strip()]
    if must_haves:
        parts.append("\n\nMUST HAVE:\n" + "\n".join(f"- {m}" for m in must_haves))
    if nice_to_haves:
        parts.append("\n\nNICE TO HAVE:\n" + "\n".join(f"- {n}" for n in nice_to_haves))
    return "\n".join(parts)
