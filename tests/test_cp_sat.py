import csv

import pytest

from sudoku.board import Board
from sudoku.solvers.backtracking import BacktrackingSolver
from sudoku.solvers.cp_sat import CPSATSolver
from sudoku.solvers.cp_sat import cp_model as _cp_model
from tests.sample_puzzles import expected_solution, solvable_few_blanks, unsolvable_few_blanks

pytestmark = pytest.mark.skipif(
    _cp_model is None,
    reason="ortools not installed -- see requirements-optional.txt",
)


def _load_manifest_boards():
    with open("puzzles/manifest.csv", newline="") as f:
        manifest_rows = list(csv.DictReader(f))
    return [
        (row["id"], Board.from_string(open(f"puzzles/{row['filename']}").read()))
        for row in manifest_rows
    ]


def test_solves_a_valid_puzzle_correctly():
    result = CPSATSolver().solve(solvable_few_blanks())
    assert result.solved is True
    assert result.board == expected_solution()


def test_returned_solution_is_complete_and_valid():
    result = CPSATSolver().solve(solvable_few_blanks())
    assert result.board.is_complete()
    assert result.board.is_valid()


def test_does_not_mutate_the_input_board():
    puzzle = solvable_few_blanks()
    original = puzzle.copy()
    CPSATSolver().solve(puzzle)
    assert puzzle == original


def test_reports_failure_for_an_unsolvable_puzzle():
    result = CPSATSolver(timeout_seconds=5).solve(unsolvable_few_blanks())
    assert result.solved is False
    assert result.board is None
    assert result.metrics.timed_out is False


def test_rejects_an_already_invalid_board():
    invalid = solvable_few_blanks()
    invalid[(0, 0)] = invalid[(0, 1)]
    result = CPSATSolver().solve(invalid)
    assert result.solved is False


def test_repeated_solves_are_deterministic():
    """Forced single-threaded, seeded search (see cp_sat.py) -- CP-SAT
    defaults to parallel search, which would make this non-deterministic.
    """
    puzzle = Board.from_string(open("puzzles/extreme/extreme_01.txt").read())
    results = [CPSATSolver().solve(puzzle) for _ in range(3)]
    node_counts = {r.metrics.nodes_explored for r in results}
    assert len(node_counts) == 1
    assert all(r.board == results[0].board for r in results)


def test_solver_specific_metrics_are_legitimately_zero():
    """Not a gap: this solver never runs its own search loop, so none of
    the operations every _record_* method names are ever performed here.
    """
    result = CPSATSolver().solve(solvable_few_blanks())
    m = result.metrics
    assert m.assignments_tried == 0
    assert m.constraint_checks == 0
    assert m.candidate_eliminations == 0
    assert m.domain_lookups == 0
    assert m.propagated_assignments == 0
    assert m.hidden_singles_found == 0
    assert m.naked_pairs_found == 0
    assert m.columns_covered == 0


def test_produces_a_genuinely_valid_solution_on_every_benchmark_puzzle():
    for puzzle_id, original in _load_manifest_boards():
        result = CPSATSolver(timeout_seconds=20).solve(original.copy())
        assert result.solved is True, puzzle_id
        assert result.board.is_valid(), puzzle_id
        assert result.board.is_complete(), puzzle_id
        for r in range(9):
            for c in range(9):
                if original[(r, c)] != 0:
                    assert result.board[(r, c)] == original[(r, c)], puzzle_id


def test_matches_an_independently_verified_solver_on_uniquely_solvable_puzzles():
    trusted_unique = {"easy_01", "extreme_01"}
    for puzzle_id, board in _load_manifest_boards():
        if puzzle_id not in trusted_unique:
            continue
        cp_result = CPSATSolver(timeout_seconds=20).solve(board.copy())
        bt_result = BacktrackingSolver(timeout_seconds=20).solve(board.copy())
        assert cp_result.board == bt_result.board, puzzle_id
