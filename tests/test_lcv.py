from sudoku.board import Board
from sudoku.solvers.forward_checking import ForwardCheckingSolver
from sudoku.solvers.lcv import LCVSolver
from tests.sample_puzzles import (
    CLASSIC_EASY_STRING,
    expected_solution,
    solvable_few_blanks,
    unsolvable_few_blanks,
)


def test_solves_a_valid_puzzle_correctly():
    result = LCVSolver().solve(solvable_few_blanks())
    assert result.solved is True
    assert result.board == expected_solution()


def test_returned_solution_is_complete_and_valid():
    result = LCVSolver().solve(solvable_few_blanks())
    assert result.board.is_complete()
    assert result.board.is_valid()


def test_does_not_mutate_the_input_board():
    puzzle = solvable_few_blanks()
    original = puzzle.copy()
    LCVSolver().solve(puzzle)
    assert puzzle == original


def test_reports_failure_for_an_unsolvable_puzzle():
    result = LCVSolver(timeout_seconds=5).solve(unsolvable_few_blanks())
    assert result.solved is False
    assert result.board is None
    assert result.metrics.timed_out is False


def test_rejects_an_already_invalid_board():
    invalid = solvable_few_blanks()
    invalid[(0, 0)] = invalid[(0, 1)]
    result = LCVSolver().solve(invalid)
    assert result.solved is False
    assert result.metrics.nodes_explored == 0


def test_metrics_are_positive_on_a_real_search():
    result = LCVSolver().solve(solvable_few_blanks())
    assert result.metrics.nodes_explored > 0
    assert result.metrics.assignments_tried > 0
    assert result.metrics.constraint_checks > 0


def test_domain_lookups_occur_when_a_cell_has_a_real_choice_of_values():
    """solvable_few_blanks has every cell forced to exactly one candidate
    (by construction), so sorted() never has more than one element to
    order and skips calling the key function entirely -- domain_lookups
    stays 0 there (see the unsolvable-puzzle test above for the same
    effect). A puzzle with real branching should actually exercise it.
    """
    puzzle = Board.from_string(CLASSIC_EASY_STRING)
    result = LCVSolver(timeout_seconds=5).solve(puzzle)
    assert result.metrics.domain_lookups > 0


def test_proving_unsolvable_needs_no_domain_lookups_when_no_real_ordering_choice():
    """The dead cell in this puzzle has zero candidates, so there's
    nothing to order between -- _order_by_least_constraining is never
    reached with more than one candidate to score."""
    result = LCVSolver().solve(unsolvable_few_blanks())
    assert result.metrics.domain_lookups == 0


def test_solves_a_realistic_puzzle():
    puzzle = Board.from_string(CLASSIC_EASY_STRING)
    result = LCVSolver(timeout_seconds=5).solve(puzzle)
    assert result.solved is True
    assert result.board.is_valid()
    assert result.board.is_complete()


def test_this_heuristic_is_not_a_strict_improvement_over_forward_checking():
    """A real, measured result, not an assumption: LCV helps on some
    puzzles and actively hurts on others -- hard_02 improves (64 -> 58
    nodes); extreme_01 (AI Escargot) regresses sharply (210 -> 1626
    nodes), the same puzzle the degree-heuristic tiebreak (stage 10) also
    regressed on. Both facts are guarded here so neither gets silently
    lost to a future change.
    """
    better_puzzle = Board.from_string(open("puzzles/hard/hard_02.txt").read())
    worse_puzzle = Board.from_string(open("puzzles/extreme/extreme_01.txt").read())

    fc_better = ForwardCheckingSolver().solve(better_puzzle).metrics.nodes_explored
    lcv_better = LCVSolver().solve(better_puzzle).metrics.nodes_explored
    assert lcv_better < fc_better

    fc_worse = ForwardCheckingSolver().solve(worse_puzzle).metrics.nodes_explored
    lcv_worse = LCVSolver().solve(worse_puzzle).metrics.nodes_explored
    assert lcv_worse > fc_worse
