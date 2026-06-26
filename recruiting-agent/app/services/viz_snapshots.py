"""Build live vector-space snapshots for the Agent Activity panel."""

from __future__ import annotations

import hashlib
import re
from typing import Any

TECH_TERMS = {
    "python", "java", "javascript", "typescript", "react", "fastapi", "django",
    "flask", "sql", "postgresql", "mysql", "mongodb", "docker", "kubernetes",
    "aws", "azure", "gcp", "ml", "ai", "machine", "learning", "deep", "nlp",
    "tensorflow", "pytorch", "pandas", "numpy", "scikit", "api", "rest", "git",
    "linux", "node", "angular", "vue", "spring", "scala", "go", "rust", "c++",
    "html", "css", "etl", "spark", "hadoop", "kafka", "redis", "elasticsearch",
    "llm", "rag", "embeddings", "vector", "chromadb", "ollama", "groq",
}


def _hash_pos(seed: str, scale: float = 1.0) -> tuple[float, float, float]:
    digest = hashlib.md5(seed.encode()).digest()
    return (
        (digest[0] / 127.5 - 1.0) * scale,
        (digest[1] / 127.5 - 1.0) * scale,
        (digest[2] / 127.5 - 1.0) * scale,
    )


def _node(text: str, seed: str, scale: float = 0.75, kind: str = "token") -> dict[str, Any]:
    x, y, z = _hash_pos(seed, scale)
    return {"text": text, "x": x, "y": y, "z": z, "kind": kind}


def extract_resume_tokens(text: str, limit: int = 14) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for term in sorted(TECH_TERMS, key=len, reverse=True):
        if term in lowered and term not in found:
            found.append(term.title() if term.islower() else term.upper())
        if len(found) >= limit:
            return found

    words = re.findall(r"\b[A-Z][a-zA-Z+#]{2,}\b", text)
    for word in words:
        if word not in found:
            found.append(word)
        if len(found) >= limit:
            break

    if len(found) < 6:
        for word in re.findall(r"\b[a-zA-Z]{4,}\b", text.lower()):
            if word in TECH_TERMS and word.title() not in found:
                found.append(word.title())
            if len(found) >= limit:
                break
    return found[:limit]


def resume_parse_viz(text: str, phase: str = "normalize") -> dict[str, Any]:
    tokens = extract_resume_tokens(text)
    return {
        "mode": "resume",
        "phase": phase,
        "query": {"text": "resume", "x": 0.0, "y": 0.0, "z": 0.0, "kind": "query"},
        "tokens": [_node(t, f"tok-{t}-{i}", 0.55, "token") for i, t in enumerate(tokens)],
        "jd_nodes": [],
        "edges": [],
    }


def resume_search_viz(
    text: str,
    matches: list[dict[str, Any]],
    phase: str = "search",
    active_jd_id: int | None = None,
) -> dict[str, Any]:
    tokens = extract_resume_tokens(text)
    jd_nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    for match in matches:
        jd_id = int(match["jd_id"])
        sim = float(match.get("similarity", 0.0))
        bx, by, bz = _hash_pos(f"jd-{jd_id}", 0.85)
        pull = max(0.15, 1.0 - sim * 0.72)
        node = {
            "id": jd_id,
            "text": str(match.get("role") or match.get("title") or f"JD {jd_id}"),
            "x": bx * pull,
            "y": by * pull,
            "z": bz * pull,
            "kind": "jd",
            "similarity": round(sim, 3),
        }
        jd_nodes.append(node)
        edges.append(
            {
                "from": "query",
                "to": jd_id,
                "weight": sim,
                "active": active_jd_id == jd_id or (active_jd_id is None and sim == max(m.get("similarity", 0) for m in matches)),
            }
        )

    return {
        "mode": "resume",
        "phase": phase,
        "query": {"text": "resume", "x": 0.0, "y": 0.0, "z": 0.0, "kind": "query"},
        "tokens": [_node(t, f"tok-{t}-{i}", 0.4, "token") for i, t in enumerate(tokens)],
        "jd_nodes": jd_nodes,
        "edges": edges,
    }


def jd_parse_viz(skills: list[str], phase: str = "llm", title: str = "") -> dict[str, Any]:
    tokens = skills[:16] if skills else ["role", "skills", "requirements", "seniority"]
    center = title or "JD"
    return {
        "mode": "jd_parse",
        "phase": phase,
        "query": {"text": center[:24], "x": 0.0, "y": 0.0, "z": 0.0, "kind": "jd_root"},
        "tokens": [_node(t, f"skill-{t}-{i}", 0.5, "skill") for i, t in enumerate(tokens)],
        "chunks": [],
        "jd_nodes": [],
        "edges": [{"from": "query", "to": i, "weight": 0.6} for i in range(len(tokens))],
    }


def jd_index_viz(
    title: str,
    role: str,
    skills: list[str],
    chunks: list[str],
    phase: str = "embed",
) -> dict[str, Any]:
    tokens = [_node(s, f"skill-{s}-{i}", 0.45, "skill") for i, s in enumerate(skills[:12])]
    chunk_nodes = [
        {
            "text": f"chunk {i + 1}",
            "snippet": chunk[:80] + ("…" if len(chunk) > 80 else ""),
            "x": _hash_pos(f"chunk-{i}", 0.65)[0],
            "y": _hash_pos(f"chunk-{i}", 0.65)[1],
            "z": _hash_pos(f"chunk-{i}", 0.65)[2],
            "kind": "chunk",
        }
        for i, chunk in enumerate(chunks[:6])
    ]
    edges = [{"from": "query", "to": i, "weight": 0.5} for i in range(len(chunk_nodes))]
    return {
        "mode": "jd_index",
        "phase": phase,
        "query": {"text": role or title, "x": 0.0, "y": 0.0, "z": 0.0, "kind": "jd_root"},
        "tokens": tokens,
        "chunks": chunk_nodes,
        "jd_nodes": [],
        "edges": edges,
    }
