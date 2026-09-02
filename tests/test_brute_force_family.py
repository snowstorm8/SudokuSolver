"""Behavioral tests shared across the whole brute-force pruning ladder.

Each solver in this family (leaf-only, row-pruned, row+box-pruned) must
agree on *what* the answer is -- they only differ in how much work it
takes to get there, which is covered separately below.
"""

import pytest

from sudoku.board import Board
from sudoku.solvers.brute_force import BruteForceSolver
from sudoku.solvers.brute_force_row_box_pruned import RowBoxPrunedBruteForceSolver
from sudoku.solvers.brute_force_row_pruned import RowPrunedBruteForceSolver
from tests.sample_puzzles import (
    expected_solution,
    solvable_few_blanks,
    unsolvable_few_blanks,
)

SOLVER_CLASSES = [BruteForceSolver, RowPrunedBruteForceSolver, RowBoxPrunedBruteForceSolver]


@pytest.mark.parametrize("solver_cls", SOLVER_CLASSES)
def test_solves_a_valid_puzzle_correctly(solver_cls):
    puzzle = solvable_few_blanks()
    result = solver_cls().solve(puzzle)
    assert result.solved is True
    assert result.board == expected_solution()


@pytest.mark.parametrize("solver_cls", SOLVER_CLASSES)
def test_returned_solution_is_complete_and_valid(solver_cls):
    result = solver_cls().solve(solvable_few_blanks())
    assert result.board.is_complete()
    assert result.board.is_valid()


@pytest.mark.parametrize("solver_cls", SOLVER_CLASSES)
def test_does_not_mutate_the_input_board(solver_cls):
    puzzle = solvable_few_blanks()
    original = puzzle.copy()
    solver_cls().solve(puzzle)
    assert puzzle == original


@pytest.mark.parametrize("solver_cls", SOLVER_CLASSES)
def test_reports_failure_for_an_unsolvable_puzzle(solver_cls):
    result = solver_cls(timeout_seconds=5).solve(unsolvable_few_blanks())
    assert result.solved is False
    assert result.board is None
    assert result.metrics.timed_out is False  # genuinely exhausted, not just out of time


@pytest.mark.parametrize("solver_cls", SOLVER_CLASSES)
def test_rejects_an_already_invalid_board(solver_cls):
    invalid = solvable_few_blanks()
    invalid[(0, 0)] = invalid[(0, 1)]  # introduce a same-row duplicate
    result = solver_cls().solve(invalid)
    assert result.solved is False
    assert result.metrics.nodes_explored == 0


@pytest.mark.parametrize("solver_cls", SOLVER_CLASSES)
def test_metrics_are_positive_on_a_real_search(solver_cls):
    result = solver_cls().solve(solvable_few_blanks())
    assert result.metrics.nodes_explored > 0
    assert result.metrics.assignments_tried > 0
    assert result.metrics.constraint_checks > 0
    assert result.metrics.runtime_seconds >= 0


def test_pruning_reduces_search_effort_on_the_same_puzzle():
    """The whole point of the ladder: each rung should need no more nodes
    than the one before it, on the same puzzle -- ending with backtracking
    (check every cell immediately), the finest-grained rung of all."""
    from sudoku.solvers.backtracking import BacktrackingSolver

    puzzle = solvable_few_blanks()
    leaf_only = BruteForceSolver().solve(puzzle).metrics
    row_pruned = RowPrunedBruteForceSolver().solve(puzzle).metrics
    row_box_pruned = RowBoxPrunedBruteForceSolver().solve(puzzle).metrics
    backtracking = BacktrackingSolver().solve(puzzle).metrics

    assert row_pruned.nodes_explored <= leaf_only.nodes_explored
    assert row_box_pruned.nodes_explored <= row_pruned.nodes_explored
    assert backtracking.nodes_explored <= row_box_pruned.nodes_explored


def test_leaf_only_brute_force_times_out_on_a_realistic_puzzle():
    """Confirms the predicted (not assumed) behavior: with zero pruning,
    even a puzzle usually described as 'easy' is intractable."""
    from tests.sample_puzzles import CLASSIC_EASY_STRING

    puzzle = Board.from_string(CLASSIC_EASY_STRING)
    result = BruteForceSolver(timeout_seconds=1).solve(puzzle)
    assert result.solved is False
    assert result.metrics.timed_out is True
