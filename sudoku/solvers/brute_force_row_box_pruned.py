"""Brute force with row- and box-level pruning -- the third rung of the
pruning ladder (see brute_force.py for the full family and rationale).

Adds one more checkpoint on top of brute_force_row_pruned.py: as soon as
a 3x3 box's last blank cell gets filled, that box is checked for internal
duplicates too. Column conflicts are still only caught at the final leaf
check -- under fixed row-major traversal a column's cells are spread one
per row across the whole board, so a column only finishes near the very
end regardless of pruning strategy, which is why there's no equivalent
"column-pruned" rung (see brute_force.py's module docstring for the same
point about rows and boxes finishing early).
"""

from __future__ import annotations

from sudoku.board import BOX_SIZE, SIZE, Board
from sudoku.solvers.base import Solver


class RowBoxPrunedBruteForceSolver(Solver):
    name = "brute_force_row_box_pruned"

    def _solve(self, board: Board) -> bool:
        if not self._enter_node():
            return False

        empty = board.empty_cells()
        if not empty:
            return self._is_valid_completion(board)

        row, col = empty[0]
        box_row, box_col = row // BOX_SIZE, col // BOX_SIZE

        row_just_completed = len(empty) == 1 or empty[1][0] != row
        box_just_completed = not any(
            (r // BOX_SIZE, c // BOX_SIZE) == (box_row, box_col)
            for r, c in empty[1:]
        )

        for value in range(1, SIZE + 1):
            self._record_assignment()
            board[(row, col)] = value
            if row_just_completed and not self._row_is_valid(board, row):
                board[(row, col)] = 0
                continue
            if box_just_completed and not self._box_is_valid(board, box_row, box_col):
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

    def _box_is_valid(self, board: Board, box_row: int, box_col: int) -> bool:
        r0, c0 = box_row * BOX_SIZE, box_col * BOX_SIZE
        for r in range(r0, r0 + BOX_SIZE):
            for c in range(c0, c0 + BOX_SIZE):
                self._record_constraint_check()
                if not board.is_valid_placement(r, c, board[(r, c)]):
                    return False
        return True

    def _is_valid_completion(self, board: Board) -> bool:
        for r in range(SIZE):
            for c in range(SIZE):
                self._record_constraint_check()
                if not board.is_valid_placement(r, c, board[(r, c)]):
                    return False
        return True
