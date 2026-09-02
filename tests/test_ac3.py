import csv

from sudoku.board import Board
from sudoku.solvers.ac3 import AC3Solver
from sudoku.solvers.forward_checking import ForwardCheckingSolver
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
    result = AC3Solver().solve(solvable_few_blanks())
    assert result.solved is True
    assert result.board == expected_solution()


def test_returned_solution_is_complete_and_valid():
    result = AC3Solver().solve(solvable_few_blanks())
    assert result.board.is_complete()
    assert result.board.is_valid()


def test_does_not_mutate_the_input_board():
    puzzle = solvable_few_blanks()
    original = puzzle.copy()
    AC3Solver().solve(puzzle)
    assert puzzle == original


def test_reports_failure_for_an_unsolvable_puzzle():
    result = AC3Solver(timeout_seconds=5).solve(unsolvable_few_blanks())
    assert result.solved is False
    assert result.board is None
    assert result.metrics.timed_out is False


def test_rejects_an_already_invalid_board():
    invalid = solvable_few_blanks()
    invalid[(0, 0)] = invalid[(0, 1)]
    result = AC3Solver().solve(invalid)
    assert result.solved is False
    assert result.metrics.nodes_explored == 0


def test_metrics_are_positive_on_a_real_search():
    result = AC3Solver().solve(solvable_few_blanks())
    assert result.metrics.nodes_explored > 0
    assert result.metrics.constraint_checks > 0
    assert result.metrics.propagated_assignments > 0


def test_small_puzzle_is_fully_resolved_by_propagation_alone():
    """Every blank in this puzzle is forced by its own row -- true of
    the givens from the start, so AC-3-style propagation should resolve
    the whole thing before the search loop ever needs to branch.
    """
    result = AC3Solver().solve(solvable_few_blanks())
    assert result.metrics.nodes_explored == 1
    assert result.metrics.assignments_tried == 0
    assert result.metrics.propagated_assignments == 3


def test_classic_easy_puzzle_is_also_fully_resolved_by_propagation_alone():
    """A genuinely striking real result, not a designed-in guarantee:
    this 51-blank puzzle -- the one every brute-force variant times out
    on -- needs zero branching once propagated to a fixed point.
    """
    puzzle = Board.from_string(CLASSIC_EASY_STRING)
    result = AC3Solver().solve(puzzle)
    assert result.solved is True
    assert result.metrics.nodes_explored == 1
    assert result.metrics.assignments_tried == 0


def test_never_needs_more_nodes_than_forward_checking():
    """AC-3 does strictly more deduction per assignment than forward
    checking's one-hop propagation, so its search space should never
    need to branch on anything forward checking's weaker propagation
    could not have derived for free. Verified across the whole benchmark
    puzzle set, not assumed.
    """
    for puzzle_id, puzzle in _load_manifest_boards():
        fc_nodes = ForwardCheckingSolver().solve(puzzle).metrics.nodes_explored
        ac3_nodes = AC3Solver().solve(puzzle).metrics.nodes_explored
        assert ac3_nodes <= fc_nodes, puzzle_id


def test_produces_a_genuinely_valid_solution_on_every_benchmark_puzzle():
    """Regression test for a real bug found while building this solver:
    a worklist-propagation race where two peer cells could each
    independently narrow to the same value and both get committed to the
    board, since a peer already written is skipped by everyone else's
    propagation (see ac3.py's _propagate comments). medium_01, hard_02,
    and extreme_01 originally exposed it; all 8 puzzles are checked here
    so the fix can't silently regress on any of them, including ones
    that happened not to trigger it on that particular run.
    """
    for puzzle_id, original in _load_manifest_boards():
        result = AC3Solver(timeout_seconds=10).solve(original.copy())
        assert result.solved is True, puzzle_id
        assert result.board.is_valid(), puzzle_id
        assert result.board.is_complete(), puzzle_id
        for r in range(9):
            for c in range(9):
                if original[(r, c)] != 0:
                    assert result.board[(r, c)] == original[(r, c)], puzzle_id
