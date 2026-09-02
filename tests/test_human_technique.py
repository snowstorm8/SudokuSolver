import csv

from sudoku.board import Board
from sudoku.solvers.ac3 import AC3Solver
from sudoku.solvers.human_technique import HumanTechniqueSolver
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
    result = HumanTechniqueSolver().solve(solvable_few_blanks())
    assert result.solved is True
    assert result.board == expected_solution()


def test_returned_solution_is_complete_and_valid():
    result = HumanTechniqueSolver().solve(solvable_few_blanks())
    assert result.board.is_complete()
    assert result.board.is_valid()


def test_does_not_mutate_the_input_board():
    puzzle = solvable_few_blanks()
    original = puzzle.copy()
    HumanTechniqueSolver().solve(puzzle)
    assert puzzle == original


def test_reports_failure_for_an_unsolvable_puzzle():
    result = HumanTechniqueSolver(timeout_seconds=5).solve(unsolvable_few_blanks())
    assert result.solved is False
    assert result.board is None
    assert result.metrics.timed_out is False


def test_rejects_an_already_invalid_board():
    invalid = solvable_few_blanks()
    invalid[(0, 0)] = invalid[(0, 1)]
    result = HumanTechniqueSolver().solve(invalid)
    assert result.solved is False
    assert result.metrics.nodes_explored == 0


def test_metrics_are_positive_on_a_real_search():
    result = HumanTechniqueSolver().solve(solvable_few_blanks())
    assert result.metrics.nodes_explored > 0
    assert result.metrics.constraint_checks > 0
    assert result.metrics.propagated_assignments > 0


def test_small_puzzle_needs_no_techniques_beyond_naked_singles():
    result = HumanTechniqueSolver().solve(solvable_few_blanks())
    assert result.metrics.hidden_singles_found == 0
    assert result.metrics.naked_pairs_found == 0


def test_easy_01_is_solved_by_naked_singles_alone_same_as_ac3():
    """Confirms this solver agrees with AC3Solver's own finding (stage
    12) that this puzzle needs zero guessing -- and that the two extra
    techniques here correctly stay unused when they're not needed."""
    puzzle = Board.from_string(CLASSIC_EASY_STRING)
    result = HumanTechniqueSolver().solve(puzzle)
    assert result.metrics.nodes_explored == 1
    assert result.metrics.hidden_singles_found == 0
    assert result.metrics.naked_pairs_found == 0


def test_hidden_singles_and_naked_pairs_actually_fire_on_harder_puzzles():
    """Not just plumbing that's never exercised: at least one benchmark
    puzzle should need each technique."""
    any_hidden = False
    any_pairs = False
    for _puzzle_id, board in _load_manifest_boards():
        metrics = HumanTechniqueSolver(timeout_seconds=10).solve(board).metrics
        any_hidden = any_hidden or metrics.hidden_singles_found > 0
        any_pairs = any_pairs or metrics.naked_pairs_found > 0
    assert any_hidden
    assert any_pairs


def test_produces_a_genuinely_valid_solution_on_every_benchmark_puzzle():
    """Same lesson as ac3.py's equivalent test: verify actual validity,
    not just solved=True, since worklist propagation bugs can silently
    produce a wrong-but-complete board."""
    for puzzle_id, original in _load_manifest_boards():
        result = HumanTechniqueSolver(timeout_seconds=10).solve(original.copy())
        assert result.solved is True, puzzle_id
        assert result.board.is_valid(), puzzle_id
        assert result.board.is_complete(), puzzle_id
        for r in range(9):
            for c in range(9):
                if original[(r, c)] != 0:
                    assert result.board[(r, c)] == original[(r, c)], puzzle_id


def test_more_powerful_propagation_is_not_a_strict_improvement_over_ac3():
    """A real, measured result, not an assumption: adding hidden singles
    and naked pairs on top of AC-3's naked-single-only propagation
    sometimes needs FEWER nodes (medium_01: 12 -> 6) and sometimes MORE
    (medium_02: 10 -> 12) -- because a different elimination order
    changes which cell the shared MRV rule sees as "most constrained" at
    each branch point, and that greedy choice isn't guaranteed globally
    optimal. Consistent with what the degree heuristic and LCV already
    showed (stages 10-11): more locally-reasonable information doesn't
    guarantee a smaller search tree.
    """
    better_puzzle = Board.from_string(open("puzzles/medium/medium_01.txt").read())
    worse_puzzle = Board.from_string(open("puzzles/medium/medium_02.txt").read())

    ac3_better = AC3Solver().solve(better_puzzle).metrics.nodes_explored
    ht_better = HumanTechniqueSolver().solve(better_puzzle).metrics.nodes_explored
    assert ht_better < ac3_better

    ac3_worse = AC3Solver().solve(worse_puzzle).metrics.nodes_explored
    ht_worse = HumanTechniqueSolver().solve(worse_puzzle).metrics.nodes_explored
    assert ht_worse > ac3_worse
