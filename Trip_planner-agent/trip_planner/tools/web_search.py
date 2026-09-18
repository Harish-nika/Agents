"""Free web search: DuckDuckGo/ddgs when available, Wikipedia fallback."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

import requests

# Junk titles that mean the search backend misfired (dictionary / spam).
_JUNK_TITLE = re.compile(
    r"^(best|definition|meaning|dictionary|merriam|cambridge|thesaurus|"
    r"online payment|undertaking)\b",
    re.I,
)


def _normalize_rows(raw_rows: list[dict]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in raw_rows:
        title = (item.get("title") or "").strip()
        url = (item.get("href") or item.get("link") or item.get("url") or "").strip()
        snippet = (
            item.get("body") or item.get("snippet") or item.get("description") or ""
        ).strip()
        if not title and not url:
            continue
        if _JUNK_TITLE.match(title):
            continue
        if url and "cambridge.org" in url:
            continue
        if url and "merriam-webster.com" in url:
            continue
        rows.append({"title": title, "url": url, "snippet": snippet})
    return rows


def _search_ddgs(query: str, max_results: int) -> list[dict[str, str]]:
    try:
        from ddgs import DDGS  # type: ignore
    except ImportError:
        from duckduckgo_search import DDGS  # type: ignore

    with DDGS() as ddgs:
        raw = list(ddgs.text(query, max_results=max(1, min(max_results, 10))))
    return _normalize_rows(raw)


def _search_wikipedia(query: str, max_results: int) -> list[dict[str, str]]:
    """MediaWiki opensearch + REST summaries — free, no API key."""
    try:
        resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "opensearch",
                "search": query,
                "limit": max(1, min(max_results, 8)),
                "namespace": 0,
                "format": "json",
            },
            headers={"User-Agent": "TripGuide/1.0 (local travel agent)"},
            timeout=25,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    # opensearch: [query, [titles], [descriptions], [urls]]
    if not isinstance(data, list) or len(data) < 4:
        return []
    titles, descs, urls = data[1], data[2], data[3]
    rows: list[dict[str, str]] = []
    for title, desc, url in zip(titles, descs, urls):
        snippet = desc or ""
        if not snippet and title:
            try:
                sresp = requests.get(
                    f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title)}",
                    headers={"User-Agent": "TripGuide/1.0 (local travel agent)"},
                    timeout=15,
                )
                if sresp.ok:
                    snippet = (sresp.json().get("extract") or "")[:280]
            except Exception:
                pass
        rows.append(
            {
                "title": title,
                "url": url,
                "snippet": snippet,
            }
        )
    return rows


# Lightweight curated fallbacks when live search is blocked (common India coast trip).
_CURATED: dict[str, list[dict[str, str]]] = {
    "gokarna": [
        {
            "title": "Om Beach, Gokarna",
            "url": "https://en.wikipedia.org/wiki/Gokarna,_Karnataka",
            "snippet": "Famous OM-shaped beach; cafes, surfing, and sunset views.",
        },
        {
            "title": "Kudle Beach",
            "url": "https://en.wikipedia.org/wiki/Gokarna,_Karnataka",
            "snippet": "Quieter beach near town — good for chill budget stays.",
        },
        {
            "title": "Mahabaleshwar Temple, Gokarna",
            "url": "https://en.wikipedia.org/wiki/Mahabaleshwar_Temple,_Gokarna",
            "snippet": "Ancient Shiva temple and town pilgrimage center.",
        },
    ],
    "jog": [
        {
            "title": "Jog Falls (Gersoppa)",
            "url": "https://en.wikipedia.org/wiki/Jog_Falls",
            "snippet": "One of India’s highest plunge waterfalls in Sharavathi valley.",
        },
        {
            "title": "Sharavathi Valley viewpoint",
            "url": "https://en.wikipedia.org/wiki/Jog_Falls",
            "snippet": "Viewpoints and short walks around the falls complex.",
        },
    ],
    "murudeshwar": [
        {
            "title": "Murdeshwar Temple & Shiva statue",
            "url": "https://en.wikipedia.org/wiki/Murdeshwar",
            "snippet": "Coastal temple town with a towering Shiva statue and beach.",
        },
        {
            "title": "Murdeshwar Beach",
            "url": "https://en.wikipedia.org/wiki/Murdeshwar",
            "snippet": "Beach next to the temple complex — easy half-day stop.",
        },
    ],
    "murdeshwar": [
        {
            "title": "Murdeshwar Temple & Shiva statue",
            "url": "https://en.wikipedia.org/wiki/Murdeshwar",
            "snippet": "Coastal temple town with a towering Shiva statue and beach.",
        },
    ],
}


def _curated_for_query(query: str) -> list[dict[str, str]]:
    q = query.lower()
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for key, items in _CURATED.items():
        if key in q:
            for item in items:
                t = item["title"]
                if t not in seen:
                    seen.add(t)
                    out.append(item)
    return out


def web_search(query: str, max_results: int = 6) -> dict[str, Any]:
    """Search the public web for places, travel tips, food, or lodging info.

    Args:
        query: Search query, e.g. "Gokarna Karnataka tourist attractions".
        max_results: Max number of results (default 6).

    Returns:
        A dict with status and a list of title/url/snippet results.
    """
    print(f"TOOL CALLED: web_search(query='{query[:100]}...')")
    rows: list[dict[str, str]] = []

    # 1) DuckDuckGo / ddgs (often blocked or noisy from datacenter IPs)
    try:
        rows = _search_ddgs(query, max_results)
    except Exception as e:
        print(f"web_search ddgs error: {e}")

    # 2) Wikipedia opensearch (reliable free fallback)
    if len(rows) < 2:
        wiki_q = re.sub(
            r"\b(best rated|best|places to visit|tourist attractions|budget|chill)\b",
            " ",
            query,
            flags=re.I,
        )
        wiki_q = re.sub(r"\s+", " ", wiki_q).strip() or query
        wiki_rows = _search_wikipedia(wiki_q, max_results)
        # Prefer India-related hits when possible
        india = [r for r in wiki_rows if "India" in (r.get("snippet") or "") or "Karnataka" in (r.get("title") or "")]
        rows = (india or wiki_rows)[:max_results]

    # 3) Curated coastal Karnataka seeds if still empty
    if not rows:
        rows = _curated_for_query(query)[:max_results]

    if not rows:
        return {"status": "error", "message": "No search results.", "results": []}
    return {"status": "success", "query": query, "results": rows[:max_results]}


def format_search_results(data: dict[str, Any]) -> str:
    if data.get("status") != "success":
        return data.get("message") or "Search failed."
    lines = []
    for i, row in enumerate(data.get("results") or [], 1):
        lines.append(
            f"{i}. {row.get('title', '').strip()}\n"
            f"   {row.get('snippet', '').strip()}\n"
            f"   {row.get('url', '').strip()}"
        )
    return "\n".join(lines) if lines else "No results."
