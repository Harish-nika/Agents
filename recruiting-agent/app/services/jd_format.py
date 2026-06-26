"""Normalize JD content for LLM prompts (handles legacy dict-string storage)."""

from __future__ import annotations

import ast
import json
from typing import Any


def _lines_from_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    return [text] if text else []


def dict_to_jd_text(data: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, title in (
        ("RESPONSIBILITIES", "RESPONSIBILITIES"),
        ("responsibilities", "RESPONSIBILITIES"),
        ("REQUIREMENTS", "REQUIREMENTS"),
        ("requirements", "REQUIREMENTS"),
        ("must_haves", "REQUIREMENTS"),
        ("PREFERRED", "PREFERRED"),
        ("preferred", "PREFERRED"),
        ("nice_to_haves", "PREFERRED"),
    ):
        lines = _lines_from_value(data.get(key))
        if not lines:
            continue
        if parts:
            parts.append("")
        parts.append(title)
        parts.extend(f"- {line}" if not line.startswith("-") else line for line in lines)
    if parts:
        return "\n".join(parts)
    return json.dumps(data, indent=2)


def normalize_jd_content(content: str) -> str:
    text = (content or "").strip()
    if not text:
        return text
    if text.startswith("{") or text.startswith("{'"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return dict_to_jd_text(parsed)
        except json.JSONDecodeError:
            pass
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, dict):
                return dict_to_jd_text(parsed)
        except (SyntaxError, ValueError):
            pass
    return text


def jd_prompt_block(jd) -> str:
    """Build a clean JD block for scoring/suspicion prompts."""
    content = normalize_jd_content(jd.content)
    skills = ", ".join(jd.skills) if jd.skills else ""
    lines = [
        f"Title: {jd.title}",
        f"Role: {jd.role}",
        f"Department: {jd.department or 'N/A'}",
        f"Seniority: {jd.seniority or 'N/A'}",
    ]
    if skills:
        lines.append(f"Key skills: {skills}")
    lines.append("")
    lines.append(content)
    return "\n".join(lines)
