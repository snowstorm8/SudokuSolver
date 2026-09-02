"""Tests for the Solver ABC's shared machinery (metrics, timeout, the
non-mutation contract) using minimal dummy subclasses -- not real solving
algorithms. Real algorithm behavior is tested per-solver once one exists.
"""

from sudoku.board import Board
from sudoku.solvers.base import Solver

SOLVABLE = Board.from_string(
    "530070000"
    "600195000"
    "098000060"
    "800060003"
    "400803001"
    "700020006"
    "060000280"
    "000419005"
    "000080079"
)


class ImmediateFailSolver(Solver):
    name = "immediate_fail"

    def _solve(self, board: Board) -> bool:
        self._enter_node()
        return False


class MutatesButFailsSolver(Solver):
    """Deliberately corrupts its working copy, to prove the caller's board
    is never touched -- solve() must be handing subclasses a private copy.
    """

    name = "mutates_but_fails"

    def _solve(self, board: Board) -> bool:
        self._enter_node()
        board[(0, 0)] = 9
        self._record_assignment()
        return False


class NeverEndingSolver(Solver):
    """Loops forever and relies solely on the base class's timeout to stop
    it, to prove the timeout is enforced even if a subclass never checks
    for completion on its own.
    """

    name = "never_ending"

    def _solve(self, board: Board) -> bool:
        while self._enter_node():
            self._record_assignment()
        return False


def test_immediate_fail_reports_no_solution_and_one_node():
    result = ImmediateFailSolver().solve(SOLVABLE)
    assert result.solved is False
    assert result.board is None
    assert result.metrics.nodes_explored == 1


def test_solver_never_mutates_the_caller_supplied_board():
    original = SOLVABLE.copy()
    MutatesButFailsSolver().solve(SOLVABLE)
    assert SOLVABLE == original


def test_invalid_board_is_rejected_before_solving_starts():
    invalid = SOLVABLE.copy()
    invalid[(0, 1)] = invalid[(0, 0)]  # now duplicates within row 0
    result = ImmediateFailSolver().solve(invalid)
    assert result.solved is False
    assert result.board is None
    assert result.metrics.nodes_explored == 0  # _solve never ran


def test_timeout_stops_a_solver_that_never_terminates_on_its_own():
    solver = NeverEndingSolver(timeout_seconds=0.05)
    result = solver.solve(SOLVABLE)
    assert result.solved is False
    assert result.metrics.timed_out is True
    # at least one full timeout-check interval must have elapsed
    assert result.metrics.nodes_explored >= 1000


def test_metrics_reset_between_calls():
    solver = ImmediateFailSolver()
    solver.solve(SOLVABLE)
    result = solver.solve(SOLVABLE)
    assert result.metrics.nodes_explored == 1  # not accumulated from the first call
