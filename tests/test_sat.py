import csv

from sudoku.board import Board
from sudoku.solvers.backtracking import BacktrackingSolver
from sudoku.solvers.sat import SATSolver
from tests.sample_puzzles import (
    CLASSIC_EASY_STRING,
    expected_solution,
    solvable_few_blanks,
    unsolvable_few_blanks,
)


def _load_manifest_boards():
    with open("puzzles/manifest.csv", newline="") as f:
        manifest_rows = list(csv.DictReader(f))
    return [
        (row["id"], Board.from_string(open(f"puzzles/{row['filename']}").read()))
        for row in manifest_rows
    ]


def test_solves_a_valid_puzzle_correctly():
    result = SATSolver().solve(solvable_few_blanks())
    assert result.solved is True
    assert result.board == expected_solution()


def test_returned_solution_is_complete_and_valid():
    result = SATSolver().solve(solvable_few_blanks())
    assert result.board.is_complete()
    assert result.board.is_valid()


def test_does_not_mutate_the_input_board():
    puzzle = solvable_few_blanks()
    original = puzzle.copy()
    SATSolver().solve(puzzle)
    assert puzzle == original


def test_reports_failure_for_an_unsolvable_puzzle():
    result = SATSolver(timeout_seconds=5).solve(unsolvable_few_blanks())
    assert result.solved is False
    assert result.board is None
    assert result.metrics.timed_out is False
    assert result.metrics.conflicts > 0


def test_rejects_an_already_invalid_board():
    invalid = solvable_few_blanks()
    invalid[(0, 0)] = invalid[(0, 1)]
    result = SATSolver().solve(invalid)
    assert result.solved is False


def test_metrics_are_positive_on_a_real_search():
    puzzle = Board.from_string(CLASSIC_EASY_STRING)
    result = SATSolver(timeout_seconds=5).solve(puzzle)
    assert result.metrics.nodes_explored > 0
    assert result.metrics.propagated_assignments > 0
    assert result.metrics.candidate_eliminations > 0


def test_solver_specific_metrics_are_legitimately_zero():
    """Not a gap: this is a CNF solver, so none of the domain/technique/
    exact-cover operations from other solvers exist in it at all."""
    result = SATSolver().solve(solvable_few_blanks())
    m = result.metrics
    assert m.constraint_checks == 0
    assert m.domain_lookups == 0
    assert m.hidden_singles_found == 0
    assert m.naked_pairs_found == 0
    assert m.columns_covered == 0


def test_produces_a_genuinely_valid_solution_on_every_benchmark_puzzle():
    """The same lesson as every propagation-shaped solver in this project
    (ac3.py, human_technique.py) needed: verify actual validity, not just
    solved=True. This solver's own version of that bug (found while
    building it -- see sat.py's _propagate comments) happened to crash
    with an AssertionError rather than silently returning a wrong board,
    but the discipline of checking is the same regardless of how a bug
    happens to surface.
    """
    for puzzle_id, original in _load_manifest_boards():
        result = SATSolver(timeout_seconds=20).solve(original.copy())
        assert result.solved is True, puzzle_id
        assert result.board.is_valid(), puzzle_id
        assert result.board.is_complete(), puzzle_id
        for r in range(9):
            for c in range(9):
                if original[(r, c)] != 0:
                    assert result.board[(r, c)] == original[(r, c)], puzzle_id


def test_matches_an_independently_verified_solver_on_uniquely_solvable_puzzles():
    """Only easy_01 and extreme_01 are trusted unique in this puzzle set
    (see puzzles/manifest.csv) -- comparing exact boards on the others
    would assert something false, since several are now confirmed to
    have multiple solutions (stages 10 and 14).
    """
    trusted_unique = {"easy_01", "extreme_01"}
    for puzzle_id, board in _load_manifest_boards():
        if puzzle_id not in trusted_unique:
            continue
        sat_result = SATSolver(timeout_seconds=20).solve(board.copy())
        bt_result = BacktrackingSolver(timeout_seconds=20).solve(board.copy())
        assert sat_result.board == bt_result.board, puzzle_id
