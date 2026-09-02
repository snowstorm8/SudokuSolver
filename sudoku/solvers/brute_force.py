"""Naive brute-force solver -- the "no pruning" baseline.

Core idea: search the same tree standard backtracking will (fixed
row-major cell order, ascending 1-9 value order, DFS with undo), but
never check whether a placement is legal until the entire board is
filled. Only at a "leaf" of the search tree -- a complete assignment --
do we verify the result, and backtrack if it's wrong.

This is the first rung of a small ladder of brute-force variants that
differ only in *when* constraints get checked:

    brute_force.py                -- check only at the leaf (this file)
    brute_force_row_pruned.py     -- also check each row once it fills
    brute_force_row_box_pruned.py -- also check each row and box once
                                      they fill
    backtracking.py (stage 3)     -- check every single placement,
                                      immediately -- the limit of this
                                      ladder, not a separate idea

Expected complexity: since nothing is pruned before a leaf, the number of
leaves explored is up to 9^k, where k is the number of empty cells --
that isn't an implementation inefficiency, it's what "no pruning" means.
For any puzzle with more than a handful of empty cells this is
computationally infeasible; this solver is expected to time out on
essentially every puzzle in the eventual benchmark set except
near-complete ones. That's the point of including it: it's the baseline
every other rung gets measured against, not a solver meant to actually
finish real puzzles.
"""

from __future__ import annotations

from sudoku.board import SIZE, Board
from sudoku.solvers.base import Solver


class BruteForceSolver(Solver):
    name = "brute_force"

    def _solve(self, board: Board) -> bool:
        if not self._enter_node():
            return False

        empty = board.empty_cells()
        if not empty:
            return self._is_valid_completion(board)

        row, col = empty[0]
        for value in range(1, SIZE + 1):
            self._record_assignment()
            board[(row, col)] = value
            if self._solve(board):
                return True
            board[(row, col)] = 0
        return False

    def _is_valid_completion(self, board: Board) -> bool:
        """Called once per leaf. Checks the fully-assigned board one cell
        at a time -- rather than delegating to Board.is_valid() -- so
        every cell examined counts as one constraint check. That's the
        same atomic unit the row/box-pruned variants use for their early
        checks, which is what keeps constraint_checks comparable across
        the whole family.
        """
        for r in range(SIZE):
            for c in range(SIZE):
                self._record_constraint_check()
                if not board.is_valid_placement(r, c, board[(r, c)]):
                    return False
        return True
