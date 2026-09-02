"""Brute force with row-level pruning -- the second rung of the pruning
ladder (see brute_force.py for the full family and rationale).

Same fixed cell order and value order as brute_force.py, but instead of
waiting for the whole board to fill before checking anything, this
solver checks a row for internal duplicates the moment that row's last
blank cell gets filled. An invalid row prunes the entire subtree below it
right away, instead of only being discovered 1-80 cells later at the
leaf.

Column and box conflicts are still only caught at the final leaf check --
this solver adds exactly one thing on top of brute_force.py: early
rejection of rows that duplicate a digit within themselves.
"""

from __future__ import annotations

from sudoku.board import SIZE, Board
from sudoku.solvers.base import Solver


class RowPrunedBruteForceSolver(Solver):
    name = "brute_force_row_pruned"

    def _solve(self, board: Board) -> bool:
        if not self._enter_node():
            return False

        empty = board.empty_cells()
        if not empty:
            return self._is_valid_completion(board)

        row, col = empty[0]
        # Since `empty` is in row-major order, any other blank in this
        # same row -- given or not -- would be the very next entry.
        row_just_completed = len(empty) == 1 or empty[1][0] != row

        for value in range(1, SIZE + 1):
            self._record_assignment()
            board[(row, col)] = value
            if row_just_completed and not self._row_is_valid(board, row):
                board[(row, col)] = 0
                continue
            if self._solve(board):
                return True
            board[(row, col)] = 0
        return False

    def _row_is_valid(self, board: Board, row: int) -> bool:
        for c in range(SIZE):
            self._record_constraint_check()
            if not board.is_valid_placement(row, c, board[(row, c)]):
                return False
        return True

    def _is_valid_completion(self, board: Board) -> bool:
        for r in range(SIZE):
            for c in range(SIZE):
                self._record_constraint_check()
                if not board.is_valid_placement(r, c, board[(r, c)]):
                    return False
        return True
