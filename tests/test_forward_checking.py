from sudoku.board import Board
from sudoku.solvers.forward_checking import ForwardCheckingSolver
from sudoku.solvers.mrv import MRVSolver
from tests.sample_puzzles import (
    CLASSIC_EASY_STRING,
    expected_solution,
    solvable_few_blanks,
    unsolvable_few_blanks,
)


def test_solves_a_valid_puzzle_correctly():
    result = ForwardCheckingSolver().solve(solvable_few_blanks())
    assert result.solved is True
    assert result.board == expected_solution()


def test_returned_solution_is_complete_and_valid():
    result = ForwardCheckingSolver().solve(solvable_few_blanks())
    assert result.board.is_complete()
    assert result.board.is_valid()


def test_does_not_mutate_the_input_board():
    puzzle = solvable_few_blanks()
    original = puzzle.copy()
    ForwardCheckingSolver().solve(puzzle)
    assert puzzle == original


def test_reports_failure_for_an_unsolvable_puzzle():
    result = ForwardCheckingSolver(timeout_seconds=5).solve(unsolvable_few_blanks())
    assert result.solved is False
    assert result.board is None
    assert result.metrics.timed_out is False


def test_rejects_an_already_invalid_board():
    invalid = solvable_few_blanks()
    invalid[(0, 0)] = invalid[(0, 1)]
    result = ForwardCheckingSolver().solve(invalid)
    assert result.solved is False
    assert result.metrics.nodes_explored == 0


def test_metrics_are_positive_on_a_real_search():
    result = ForwardCheckingSolver().solve(solvable_few_blanks())
    assert result.metrics.nodes_explored > 0
    assert result.metrics.assignments_tried > 0
    assert result.metrics.constraint_checks > 0  # the one-time initial domain build


def test_constraint_checks_reflect_only_the_initial_domain_build():
    """constraint_checks should equal exactly (empty cells) * 9 -- the
    one-time cost of Board.is_valid_placement calls building the initial
    domains -- since nothing during the search itself calls
    is_valid_placement at all (propagation uses set operations instead).
    """
    puzzle = solvable_few_blanks()
    result = ForwardCheckingSolver().solve(puzzle)
    assert result.metrics.constraint_checks == len(puzzle.empty_cells()) * 9


def test_solves_a_realistic_puzzle():
    puzzle = Board.from_string(CLASSIC_EASY_STRING)
    result = ForwardCheckingSolver(timeout_seconds=5).solve(puzzle)
    assert result.solved is True
    assert result.board.is_valid()
    assert result.board.is_complete()


def test_never_needs_more_nodes_than_mrv_and_agrees_on_the_answer():
    """The verified relationship (see forward_checking.py's docstring for
    how this was pinned down): identical assignments_tried, nodes_explored
    never higher than MRV's and sometimes strictly lower, same solution.
    """
    puzzle = Board.from_string(CLASSIC_EASY_STRING)
    mrv_result = MRVSolver().solve(puzzle)
    fc_result = ForwardCheckingSolver().solve(puzzle)

    assert fc_result.board == mrv_result.board
    assert fc_result.metrics.assignments_tried == mrv_result.metrics.assignments_tried
    assert fc_result.metrics.nodes_explored <= mrv_result.metrics.nodes_explored
