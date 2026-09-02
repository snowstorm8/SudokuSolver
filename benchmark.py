"""Runs every registered solver against every puzzle in puzzles/manifest.csv
under identical conditions, and writes one row per (solver, puzzle) pair to
results/. This is the project's one source of benchmark data -- everything
in visualize.py (stage 6) reads its output rather than embedding numbers
directly.

Methodology notes:

- nodes_explored, assignments_tried, and constraint_checks are
  deterministic for a given (solver, puzzle) pair -- same fixed cell/value
  order, same board, same outcome every time -- so one run is enough to
  record them.
- runtime_seconds is not deterministic (system load, scheduling, thermal
  throttling all affect it), so it's measured across several repeated
  runs and reported as a median, which resists an occasional slow outlier
  better than a mean would.
- Repeating a run that timed out would tell us nothing new: with a fixed
  timeout on a fixed puzzle, it will hit the same wall every time. Runs
  are only repeated for timing purposes when the first attempt actually
  finished (solved or genuinely exhausted the search) within the
  timeout; a timed-out result is recorded from a single run.
- The default timeout (5s) was picked after actually measuring: every
  brute-force variant times out on nearly the whole puzzle set (as
  predicted back in stage 2), while backtracking and MRV solved even the
  hardest puzzle in the set, AI Escargot, in well under a second. 5s
  gives real solvers enormous headroom without letting a handful of
  guaranteed-timeout pairs make a full benchmark run take too long.
- Puzzles are loaded once per run and the same Board object is reused
  across every solver and every repeated run against it -- safe only
  because every solver's non-mutation contract is already covered by
  tests/test_*_family.py and friends.
"""

from __future__ import annotations

import csv
import dataclasses
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

from sudoku.board import Board
from sudoku.solvers import ALL_SOLVERS
from sudoku.solvers.base import SolveMetrics

PROJECT_ROOT = Path(__file__).resolve().parent
PUZZLES_DIR = PROJECT_ROOT / "puzzles"
MANIFEST_PATH = PUZZLES_DIR / "manifest.csv"
RESULTS_DIR = PROJECT_ROOT / "results"

DEFAULT_TIMEOUT_SECONDS = 5.0
RUNS_FOR_TIMING = 5

SOLVER_CLASSES = ALL_SOLVERS

# Every SolveMetrics field except runtime_seconds (replaced below by the
# median/all/count trio, since runtime alone needs repeated-run handling
# every other field doesn't). Derived rather than hand-listed: a fixed
# list here already fell behind SolveMetrics once (candidate_eliminations
# was the only field added at the time), and every stage since has added
# at least one more counter -- the same lesson cli.py's metrics printout
# already learned.
METRIC_FIELDNAMES = [
    f.name for f in dataclasses.fields(SolveMetrics) if f.name != "runtime_seconds"
]

FIELDNAMES = (
    ["solver", "puzzle_id", "category", "givens", "solved"]
    + METRIC_FIELDNAMES
    + ["runtime_median_s", "runtime_all_s", "num_runs"]
)


@dataclass
class PuzzleRecord:
    id: str
    filename: str
    category: str
    givens: int
    board: Board


def load_manifest() -> list[PuzzleRecord]:
    records = []
    with MANIFEST_PATH.open(newline="") as f:
        for row in csv.DictReader(f):
            path = PUZZLES_DIR / row["filename"]
            board = Board.from_string(path.read_text())
            records.append(
                PuzzleRecord(row["id"], row["filename"], row["category"], int(row["givens"]), board)
            )
    return records


def benchmark_one(solver_cls: type, puzzle: PuzzleRecord, timeout: float) -> dict:
    first = solver_cls(timeout_seconds=timeout).solve(puzzle.board)

    runtimes = [first.metrics.runtime_seconds]
    if not first.metrics.timed_out:
        for _ in range(RUNS_FOR_TIMING - 1):
            repeat = solver_cls(timeout_seconds=timeout).solve(puzzle.board)
            runtimes.append(repeat.metrics.runtime_seconds)

    row = {
        "solver": solver_cls.name,
        "puzzle_id": puzzle.id,
        "category": puzzle.category,
        "givens": puzzle.givens,
        "solved": first.solved,
    }
    for name in METRIC_FIELDNAMES:
        row[name] = getattr(first.metrics, name)
    row["runtime_median_s"] = statistics.median(runtimes)
    row["runtime_all_s"] = ";".join(f"{t:.6f}" for t in runtimes)
    row["num_runs"] = len(runtimes)
    return row


def run_benchmark(timeout: float = DEFAULT_TIMEOUT_SECONDS) -> list[dict]:
    rows = []
    for puzzle in load_manifest():
        for solver_cls in SOLVER_CLASSES:
            print(f"  {solver_cls.name:28s} {puzzle.id:14s}", end=" ", flush=True)
            row = benchmark_one(solver_cls, puzzle, timeout)
            if row["timed_out"]:
                status = "TIMEOUT"
            else:
                status = "solved" if row["solved"] else "no solution"
            median_ms = row["runtime_median_s"] * 1000
            print(f"{status:10s} nodes={row['nodes_explored']:<10d} median={median_ms:8.2f}ms")
            rows.append(row)
    return rows


def write_results(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    rows = run_benchmark()

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    timestamped_path = RESULTS_DIR / f"benchmark_{timestamp}.csv"
    latest_path = RESULTS_DIR / "latest.csv"
    write_results(rows, timestamped_path)
    write_results(rows, latest_path)
    print(f"\nWrote {len(rows)} rows to {timestamped_path} and {latest_path}")


if __name__ == "__main__":
    main()
