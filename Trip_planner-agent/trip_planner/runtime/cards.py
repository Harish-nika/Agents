"""Turn-scoped UI cards collected from tool calls."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

_cards: ContextVar[list[dict[str, Any]] | None] = ContextVar("trip_cards", default=None)


def begin_turn() -> None:
    """Start collecting cards for the current chat turn."""
    _cards.set([])


def add_card(card: dict[str, Any]) -> None:
    """Append a structured card for the UI (weather, map, places, etc.)."""
    cards = _cards.get()
    if cards is None:
        cards = []
        _cards.set(cards)
    cards.append(card)


def get_cards() -> list[dict[str, Any]]:
    """Return cards collected during this turn."""
    return list(_cards.get() or [])


def peek_new_cards(seen: int) -> tuple[list[dict[str, Any]], int]:
    """Return cards appended since ``seen`` without clearing the turn."""
    cards = get_cards()
    return cards[seen:], len(cards)


def end_turn() -> list[dict[str, Any]]:
    """Return and clear cards for this turn."""
    cards = get_cards()
    _cards.set(None)
    return cards
