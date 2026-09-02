from sudoku.board import Board
from sudoku.solvers.mrv import MRVSolver
from sudoku.solvers.mrv_degree import MRVDegreeSolver
from tests.sample_puzzles import (
    CLASSIC_EASY_STRING,
    expected_solution,
    solvable_few_blanks,
    unsolvable_few_blanks,
)


def test_solves_a_valid_puzzle_correctly():
    result = MRVDegreeSolver().solve(solvable_few_blanks())
    assert result.solved is True
    assert result.board == expected_solution()


def test_returned_solution_is_complete_and_valid():
    result = MRVDegreeSolver().solve(solvable_few_blanks())
    assert result.board.is_complete()
    assert result.board.is_valid()


def test_does_not_mutate_the_input_board():
    puzzle = solvable_few_blanks()
    original = puzzle.copy()
    MRVDegreeSolver().solve(puzzle)
    assert puzzle == original


def test_reports_failure_for_an_unsolvable_puzzle():
    result = MRVDegreeSolver(timeout_seconds=5).solve(unsolvable_few_blanks())
    assert result.solved is False
    assert result.board is None
    assert result.metrics.timed_out is False


def test_rejects_an_already_invalid_board():
    invalid = solvable_few_blanks()
    invalid[(0, 0)] = invalid[(0, 1)]
    result = MRVDegreeSolver().solve(invalid)
    assert result.solved is False
    assert result.metrics.nodes_explored == 0


def test_metrics_are_positive_on_a_real_search():
    result = MRVDegreeSolver().solve(solvable_few_blanks())
    assert result.metrics.nodes_explored > 0
    assert result.metrics.assignments_tried > 0
    assert result.metrics.constraint_checks > 0


def test_degree_counts_only_still_unassigned_peers():
    solver = MRVDegreeSolver()
    board = Board.from_string(CLASSIC_EASY_STRING)
    # every peer of (0, 4) is unassigned in a fresh puzzle load only if
    # empty; check the count matches a direct recomputation.
    row, col = 0, 4
    from sudoku.board import peers

    expected = sum(1 for r, c in peers(row, col) if board.is_empty(r, c))
    assert solver._degree(board, (row, col)) == expected


def test_this_heuristic_is_not_a_strict_improvement_over_plain_mrv():
    """Locks in a real, measured result rather than an assumption: the
    degree tiebreak helps on some puzzles and actively hurts on others.
    medium_01 improves (117 -> 58 nodes); extreme_01 (AI Escargot)
    regresses sharply (218 -> 1071 nodes). Both facts are worth guarding
    against silent regression -- including the "it doesn't always help"
    one, so a future change doesn't quietly overwrite that finding.
    """
    better_puzzle = Board.from_string(open("puzzles/medium/medium_01.txt").read())
    worse_puzzle = Board.from_string(open("puzzles/extreme/extreme_01.txt").read())

    mrv_better = MRVSolver().solve(better_puzzle).metrics.nodes_explored
    deg_better = MRVDegreeSolver().solve(better_puzzle).metrics.nodes_explored
    assert deg_better < mrv_better

    mrv_worse = MRVSolver().solve(worse_puzzle).metrics.nodes_explored
    deg_worse = MRVDegreeSolver().solve(worse_puzzle).metrics.nodes_explored
    assert deg_worse > mrv_worse


def test_hard_01_has_multiple_solutions_found_by_different_tiebreaks():
    """Documents a real data-quality finding this stage surfaced: hard_01
    is not uniquely solvable. Both solvers must still produce a genuinely
    valid, complete solution that preserves every given digit -- they're
    just not required to agree on which one.
    """
    original = Board.from_string(open("puzzles/hard/hard_01.txt").read())

    mrv_result = MRVSolver().solve(original.copy())
    deg_result = MRVDegreeSolver().solve(original.copy())

    for result in (mrv_result, deg_result):
        assert result.solved is True
        assert result.board.is_valid()
        assert result.board.is_complete()
        for r in range(9):
            for c in range(9):
                if original[(r, c)] != 0:
                    assert result.board[(r, c)] == original[(r, c)]

    assert mrv_result.board != deg_result.board
