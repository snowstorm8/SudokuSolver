from sudoku.board import Board
from sudoku.solvers.min_conflicts import MinConflictsSolver
from tests.sample_puzzles import expected_solution, solvable_few_blanks, unsolvable_few_blanks


def test_solves_a_valid_puzzle_correctly():
    result = MinConflictsSolver().solve(solvable_few_blanks())
    assert result.solved is True
    assert result.board == expected_solution()


def test_returned_solution_is_complete_and_valid():
    result = MinConflictsSolver().solve(solvable_few_blanks())
    assert result.board.is_complete()
    assert result.board.is_valid()


def test_does_not_mutate_the_input_board():
    puzzle = solvable_few_blanks()
    original = puzzle.copy()
    MinConflictsSolver().solve(puzzle)
    assert puzzle == original


def test_failure_is_always_reported_as_timed_out_never_as_proven_unsolvable():
    """The central honesty invariant for this solver: unlike every other
    solver in this project, it can never prove a puzzle unsolvable --
    failure to converge just means it didn't find one. A short timeout
    keeps this test fast while still genuinely exercising the give-up
    path (see the fixture's docstring: the dead cell here has zero legal
    candidates, so this solver can never converge on it, no matter the
    budget).
    """
    result = MinConflictsSolver(timeout_seconds=1, seed=0).solve(unsolvable_few_blanks())
    assert result.solved is False
    assert result.metrics.timed_out is True
    assert result.metrics.restarts > 0  # genuinely tried, not an immediate bail


def test_metrics_are_positive_on_a_real_search():
    result = MinConflictsSolver().solve(solvable_few_blanks())
    assert result.metrics.nodes_explored > 0
    assert result.metrics.constraint_checks > 0


def test_handles_a_row_with_fewer_than_two_non_given_cells_without_crashing():
    """Regression test for a real bug found while building this solver:
    a row-local swap has no partner to swap with when fewer than 2 cells
    in that row are non-given, and rng.choice on the resulting empty
    candidate list raised IndexError rather than being treated as a
    legitimate no-op move.
    """
    grid = [
        [5, 3, 4, 6, 7, 8, 9, 1, 0],  # only (0, 8) is blank in this row
        [6, 7, 2, 1, 9, 5, 3, 4, 8],
        [1, 9, 8, 3, 4, 2, 5, 6, 7],
        [8, 5, 9, 7, 6, 1, 4, 2, 3],
        [4, 2, 6, 8, 5, 3, 7, 9, 1],
        [7, 1, 3, 9, 2, 4, 8, 5, 6],
        [9, 6, 1, 5, 3, 7, 2, 8, 4],
        [2, 8, 7, 4, 1, 9, 6, 3, 5],
        [3, 4, 5, 2, 8, 6, 1, 7, 9],
    ]
    result = MinConflictsSolver(timeout_seconds=2, seed=0).solve(Board(grid))
    assert result.solved is True


def test_repeated_solves_with_the_same_seed_are_deterministic():
    puzzle = Board.from_string(open("puzzles/extreme/extreme_02.txt").read())
    results = [MinConflictsSolver(seed=0).solve(puzzle) for _ in range(3)]
    node_counts = {r.metrics.nodes_explored for r in results}
    assert len(node_counts) == 1
    assert all(r.board == results[0].board for r in results)


def test_solves_a_realistic_puzzle():
    puzzle = Board.from_string(open("puzzles/extreme/extreme_02.txt").read())
    result = MinConflictsSolver(timeout_seconds=5, seed=0).solve(puzzle)
    assert result.solved is True
    assert result.board.is_valid()
    assert result.board.is_complete()


def test_genuine_convergence_failure_on_the_hardest_puzzle():
    """A real, measured result, not a bug to quietly tune away: this
    solver fails to converge on extreme_01 (AI Escargot) even with a
    generous budget (90,000 iterations / 17 restarts / 15s took this in
    manual testing; this test uses a shorter timeout to stay fast while
    still genuinely reproducing the failure). Every complete-search
    solver in this project solves this puzzle; this one does not, within
    this budget -- consistent with AI Escargot also being where the
    degree heuristic (stage 10) and LCV (stage 11) both regressed
    sharply, reinforcing that this specific puzzle seems adversarial to
    greedy, local heuristics generally, not just this one.
    """
    puzzle = Board.from_string(open("puzzles/extreme/extreme_01.txt").read())
    result = MinConflictsSolver(timeout_seconds=1.5, seed=0).solve(puzzle)
    assert result.solved is False
    assert result.metrics.timed_out is True
