"""Validates benchmark.py's mechanics directly, without invoking main()
(which would run every solver -- including the ones designed to time out
-- against the full puzzle set, taking minutes).
"""

import csv

from sudoku.board import Board
from sudoku.solvers.backtracking import BacktrackingSolver
from sudoku.solvers.brute_force import BruteForceSolver
from tests.sample_puzzles import CLASSIC_EASY_STRING, solvable_few_blanks

from benchmark import (
    FIELDNAMES,
    RUNS_FOR_TIMING,
    PuzzleRecord,
    benchmark_one,
    load_manifest,
    write_results,
)


def test_load_manifest_reads_every_puzzle_file():
    puzzles = load_manifest()
    assert len(puzzles) == 8
    assert all(isinstance(p.board, Board) for p in puzzles)
    assert {p.category for p in puzzles} == {"easy", "medium", "hard", "extreme"}
    assert len({p.id for p in puzzles}) == 8  # ids are unique


def test_benchmark_one_has_the_documented_fields():
    puzzle = PuzzleRecord("t", "t.txt", "easy", 3, solvable_few_blanks())
    row = benchmark_one(BacktrackingSolver, puzzle, timeout=5)
    assert set(row) == set(FIELDNAMES)


def test_benchmark_one_repeats_a_finished_run_for_timing():
    puzzle = PuzzleRecord("t", "t.txt", "easy", 3, solvable_few_blanks())
    row = benchmark_one(BacktrackingSolver, puzzle, timeout=5)
    assert row["solved"] is True
    assert row["timed_out"] is False
    assert row["num_runs"] == RUNS_FOR_TIMING
    assert len(row["runtime_all_s"].split(";")) == RUNS_FOR_TIMING


def test_benchmark_one_does_not_repeat_a_timed_out_run():
    puzzle = PuzzleRecord("t", "t.txt", "easy", 30, Board.from_string(CLASSIC_EASY_STRING))
    row = benchmark_one(BruteForceSolver, puzzle, timeout=0.05)
    assert row["timed_out"] is True
    assert row["num_runs"] == 1


def test_write_results_round_trips_through_csv(tmp_path):
    puzzle = PuzzleRecord("t", "t.txt", "easy", 3, solvable_few_blanks())
    rows = [benchmark_one(BacktrackingSolver, puzzle, timeout=5)]

    path = tmp_path / "out.csv"
    write_results(rows, path)

    with path.open(newline="") as f:
        read_rows = list(csv.DictReader(f))

    assert len(read_rows) == 1
    assert read_rows[0]["solver"] == "backtracking"
    assert read_rows[0]["puzzle_id"] == "t"
    assert set(read_rows[0]) == set(FIELDNAMES)
