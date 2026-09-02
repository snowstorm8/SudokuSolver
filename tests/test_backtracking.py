from sudoku.board import Board
from sudoku.solvers.backtracking import BacktrackingSolver
from tests.sample_puzzles import (
    CLASSIC_EASY_STRING,
    expected_solution,
    solvable_few_blanks,
    unsolvable_few_blanks,
)


def test_solves_a_valid_puzzle_correctly():
    result = BacktrackingSolver().solve(solvable_few_blanks())
    assert result.solved is True
    assert result.board == expected_solution()


def test_returned_solution_is_complete_and_valid():
    result = BacktrackingSolver().solve(solvable_few_blanks())
    assert result.board.is_complete()
    assert result.board.is_valid()


def test_does_not_mutate_the_input_board():
    puzzle = solvable_few_blanks()
    original = puzzle.copy()
    BacktrackingSolver().solve(puzzle)
    assert puzzle == original


def test_reports_failure_for_an_unsolvable_puzzle():
    result = BacktrackingSolver(timeout_seconds=5).solve(unsolvable_few_blanks())
    assert result.solved is False
    assert result.board is None
    assert result.metrics.timed_out is False


def test_rejects_an_already_invalid_board():
    invalid = solvable_few_blanks()
    invalid[(0, 0)] = invalid[(0, 1)]
    result = BacktrackingSolver().solve(invalid)
    assert result.solved is False
    assert result.metrics.nodes_explored == 0


def test_metrics_are_positive_on_a_real_search():
    result = BacktrackingSolver().solve(solvable_few_blanks())
    assert result.metrics.nodes_explored > 0
    assert result.metrics.assignments_tried > 0
    assert result.metrics.constraint_checks > 0
    assert result.metrics.runtime_seconds >= 0


def test_solves_a_realistic_puzzle_that_brute_force_cannot():
    """The payoff of incremental checking: brute_force's equivalent test
    (test_leaf_only_brute_force_times_out_on_a_realistic_puzzle) proves
    the leaf-only variant can't finish this within a 1s timeout. Backtracking
    should solve it well within that budget.
    """
    puzzle = Board.from_string(CLASSIC_EASY_STRING)
    result = BacktrackingSolver(timeout_seconds=5).solve(puzzle)
    assert result.solved is True
    assert result.metrics.timed_out is False
    assert result.board.is_valid()
    assert result.board.is_complete()
