import csv

from sudoku.board import Board
from sudoku.solvers.backtracking import BacktrackingSolver
from sudoku.solvers.dlx import DLXSolver
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
    result = DLXSolver().solve(solvable_few_blanks())
    assert result.solved is True
    assert result.board == expected_solution()


def test_returned_solution_is_complete_and_valid():
    result = DLXSolver().solve(solvable_few_blanks())
    assert result.board.is_complete()
    assert result.board.is_valid()


def test_does_not_mutate_the_input_board():
    puzzle = solvable_few_blanks()
    original = puzzle.copy()
    DLXSolver().solve(puzzle)
    assert puzzle == original


def test_reports_failure_for_an_unsolvable_puzzle():
    result = DLXSolver(timeout_seconds=5).solve(unsolvable_few_blanks())
    assert result.solved is False
    assert result.board is None
    assert result.metrics.timed_out is False


def test_rejects_an_already_invalid_board():
    invalid = solvable_few_blanks()
    invalid[(0, 0)] = invalid[(0, 1)]
    result = DLXSolver().solve(invalid)
    assert result.solved is False
    assert result.metrics.nodes_explored == 0


def test_metrics_are_positive_on_a_real_search():
    result = DLXSolver().solve(solvable_few_blanks())
    assert result.metrics.nodes_explored > 0
    assert result.metrics.assignments_tried > 0
    assert result.metrics.columns_covered > 0


def test_propagation_specific_metrics_are_legitimately_zero():
    """Not a gap: DLX's exact-cover encoding makes legality structural,
    so it never performs a constraint check or domain operation of any
    kind -- these fields should stay exactly 0, always, for this solver.
    """
    result = DLXSolver().solve(solvable_few_blanks())
    m = result.metrics
    assert m.constraint_checks == 0
    assert m.candidate_eliminations == 0
    assert m.domain_lookups == 0
    assert m.propagated_assignments == 0
    assert m.hidden_singles_found == 0
    assert m.naked_pairs_found == 0


def test_repeated_solves_are_deterministic():
    """benchmark.py re-runs the same solver multiple times on the same
    puzzle for timing -- this solver rebuilds its matrix from scratch
    every call, so there must be no cross-call state leakage."""
    puzzle = Board.from_string(CLASSIC_EASY_STRING)
    results = [DLXSolver().solve(puzzle) for _ in range(3)]
    node_counts = {r.metrics.nodes_explored for r in results}
    assert len(node_counts) == 1
    assert all(r.board == results[0].board for r in results)


def test_matches_an_independently_verified_solver_on_uniquely_solvable_puzzles():
    """A correctness check specific to how different this algorithm is
    from everything else in the project: cross-checking against
    BacktrackingSolver (built and tested independently, stage 3) on
    puzzles trusted to have a single solution. Only easy_01 (widely
    circulated, presumed unique) and extreme_01 (AI Escargot, a
    documented unique puzzle) qualify -- every self-constructed puzzle
    carries a "not verified unique" caveat in the manifest, and two of
    them (hard_01, stage 10; medium_01, found while writing this test --
    see the manifest for the confirmation) are now confirmed to actually
    have multiple solutions, so comparing exact boards on those would be
    asserting something false, not a legitimate correctness check.
    """
    trusted_unique = {"easy_01", "extreme_01"}
    for puzzle_id, board in _load_manifest_boards():
        if puzzle_id not in trusted_unique:
            continue
        dlx_result = DLXSolver(timeout_seconds=10).solve(board.copy())
        bt_result = BacktrackingSolver(timeout_seconds=10).solve(board.copy())
        assert dlx_result.board == bt_result.board, puzzle_id


def test_produces_a_genuinely_valid_solution_on_every_benchmark_puzzle():
    for puzzle_id, original in _load_manifest_boards():
        result = DLXSolver(timeout_seconds=10).solve(original.copy())
        assert result.solved is True, puzzle_id
        assert result.board.is_valid(), puzzle_id
        assert result.board.is_complete(), puzzle_id
        for r in range(9):
            for c in range(9):
                if original[(r, c)] != 0:
                    assert result.board[(r, c)] == original[(r, c)], puzzle_id
