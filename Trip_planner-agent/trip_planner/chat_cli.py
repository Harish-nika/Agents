"""Interactive CLI chat with Trip Guide (same session)."""

from __future__ import annotations

import argparse
import asyncio
import sys

from trip_planner.config import require_api_key
from trip_planner.runtime.chat_service import ChatService


async def _repl(verbose_cards: bool = False) -> int:
    require_api_key()
    service = ChatService()
    session_id = None
    print("Trip Guide CLI — type 'quit' to exit, 'new' for a new trip.\n")
    while True:
        try:
            message = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not message:
            continue
        if message.lower() in {"quit", "exit", "q"}:
            return 0
        if message.lower() == "new":
            session_id = None
            print("(started a new trip session)\n")
            continue

        result = await service.chat(message, session_id=session_id)
        session_id = result.session_id
        print(f"\nTrip Guide: {result.reply}\n")
        if verbose_cards and result.cards:
            print(f"[cards] {result.cards}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chat with Trip Guide.")
    parser.add_argument(
        "--cards",
        action="store_true",
        help="Print structured UI cards after each reply",
    )
    args = parser.parse_args(argv)
    try:
        return asyncio.run(_repl(verbose_cards=args.cards))
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
