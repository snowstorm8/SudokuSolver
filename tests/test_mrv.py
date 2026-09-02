from sudoku.board import Board
from sudoku.solvers.backtracking import BacktrackingSolver
from sudoku.solvers.mrv import MRVSolver
from tests.sample_puzzles import (
    CLASSIC_EASY_STRING,
    expected_solution,
    solvable_few_blanks,
    unsolvable_few_blanks,
)


def test_solves_a_valid_puzzle_correctly():
    result = MRVSolver().solve(solvable_few_blanks())
    assert result.solved is True
    assert result.board == expected_solution()


def test_returned_solution_is_complete_and_valid():
    result = MRVSolver().solve(solvable_few_blanks())
    assert result.board.is_complete()
    assert result.board.is_valid()


def test_does_not_mutate_the_input_board():
    puzzle = solvable_few_blanks()
    original = puzzle.copy()
    MRVSolver().solve(puzzle)
    assert puzzle == original


def test_reports_failure_for_an_unsolvable_puzzle():
    result = MRVSolver(timeout_seconds=5).solve(unsolvable_few_blanks())
    assert result.solved is False
    assert result.board is None
    assert result.metrics.timed_out is False


def test_detects_a_zero_candidate_cell_without_trying_any_assignment():
    """The dead cell in this puzzle is also the first cell MRV happens to
    scan, so it should be caught by the early-exit before any value is
    ever attempted."""
    result = MRVSolver().solve(unsolvable_few_blanks())
    assert result.metrics.nodes_explored == 1
    assert result.metrics.assignments_tried == 0


def test_rejects_an_already_invalid_board():
    invalid = solvable_few_blanks()
    invalid[(0, 0)] = invalid[(0, 1)]
    result = MRVSolver().solve(invalid)
    assert result.solved is False
    assert result.metrics.nodes_explored == 0


def test_metrics_are_positive_on_a_real_search():
    result = MRVSolver().solve(solvable_few_blanks())
    assert result.metrics.nodes_explored > 0
    assert result.metrics.assignments_tried > 0
    assert result.metrics.constraint_checks > 0
    assert result.metrics.runtime_seconds >= 0


def test_solves_a_realistic_puzzle():
    puzzle = Board.from_string(CLASSIC_EASY_STRING)
    result = MRVSolver(timeout_seconds=5).solve(puzzle)
    assert result.solved is True
    assert result.board.is_valid()
    assert result.board.is_complete()


def test_mrv_needs_no_more_nodes_than_backtracking_on_this_puzzle():
    """Not a universal guarantee -- MRV is a heuristic, not a proof of
    optimality for every conceivable puzzle -- just confirms the expected
    effect actually holds on this project's own test puzzle."""
    puzzle = Board.from_string(CLASSIC_EASY_STRING)
    backtracking_nodes = BacktrackingSolver().solve(puzzle).metrics.nodes_explored
    mrv_nodes = MRVSolver().solve(puzzle).metrics.nodes_explored
    assert mrv_nodes <= backtracking_nodes
