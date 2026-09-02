"""Run a single solver against a single puzzle from the command line.

    python cli.py --solver mrv --puzzle puzzles/hard/hard_01.txt
    python cli.py --solver backtracking --puzzle-string 530070000600195000...
    python cli.py --list-solvers
"""

from __future__ import annotations

import argparse
import dataclasses
import sys

from sudoku.board import Board
from sudoku.solvers import SOLVERS_BY_NAME


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--solver",
        choices=sorted(SOLVERS_BY_NAME),
        help="which solver to run",
    )
    puzzle_source = parser.add_mutually_exclusive_group()
    puzzle_source.add_argument("--puzzle", type=str, help="path to a puzzle file")
    puzzle_source.add_argument(
        "--puzzle-string", type=str, help="an 81-character puzzle string (0 or . for blanks)"
    )
    parser.add_argument(
        "--timeout", type=float, default=30.0, help="timeout in seconds (default: 30)"
    )
    parser.add_argument(
        "--list-solvers", action="store_true", help="print available solver names and exit"
    )
    return parser


def load_puzzle(args: argparse.Namespace) -> Board:
    if args.puzzle_string:
        return Board.from_string(args.puzzle_string)
    if args.puzzle:
        with open(args.puzzle) as f:
            return Board.from_string(f.read())
    raise SystemExit("error: one of --puzzle or --puzzle-string is required")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_solvers:
        for name in sorted(SOLVERS_BY_NAME):
            print(name)
        return 0

    if not args.solver:
        parser.error("--solver is required (use --list-solvers to see options)")

    puzzle = load_puzzle(args)
    solver_cls = SOLVERS_BY_NAME[args.solver]
    result = solver_cls(timeout_seconds=args.timeout).solve(puzzle)

    if result.solved:
        print(result.board)
    elif result.metrics.timed_out:
        print(f"Timed out after {args.timeout}s without finding a solution.")
    else:
        print("No solution exists for this puzzle.")

    # Iterated rather than hand-listed: SolveMetrics has grown a field at
    # nearly every stage (candidate_eliminations, domain_lookups,
    # propagated_assignments, hidden_singles_found, ...), and a fixed
    # f-string here would silently fall behind each time.
    metric_fields = ", ".join(
        f"{field.name}={getattr(result.metrics, field.name)}"
        for field in dataclasses.fields(result.metrics)
    )
    print(f"\nsolver={solver_cls.name} solved={result.solved} {metric_fields}")
    return 0 if result.solved else 1


if __name__ == "__main__":
    sys.exit(main())
