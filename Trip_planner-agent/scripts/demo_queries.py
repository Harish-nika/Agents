#!/usr/bin/env python3
"""Smoke-run the Lesson 2 ultimate-router demo queries."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trip_planner.main import run_routed_query

DEMO_QUERIES = [
    "Find me the best sushi in Palo Alto and then tell me how to get there from the Caltrain station.",
    "Plan me a day in San Francisco with a museum and a nice dinner, but make sure the travel time between them is very short.",
    "Help me plan a trip to SF. I need one museum, one concert, and one great restaurant.",
]


async def run_demos(queries: list[str], verbose: bool = False) -> None:
    for query in queries:
        await run_routed_query(query, verbose=verbose)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run trip planner demo queries.")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print intermediate ADK events",
    )
    parser.add_argument(
        "--one",
        type=int,
        choices=range(1, len(DEMO_QUERIES) + 1),
        help="Run only demo query N (1-based)",
    )
    args = parser.parse_args()

    queries = DEMO_QUERIES
    if args.one:
        queries = [DEMO_QUERIES[args.one - 1]]

    try:
        asyncio.run(run_demos(queries, verbose=args.verbose))
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
