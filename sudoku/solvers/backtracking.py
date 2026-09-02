"""Standard backtracking -- the fourth and final rung of the pruning
ladder started in brute_force.py.

Same fixed cell order (first empty cell, row-major) and same value order
(ascending 1-9) as every other solver in the family. The only change:
check the single new placement immediately, before recursing, instead of
waiting for a row or box to fill.

This makes the solver noticeably *simpler* than the row/box-pruned brute
force variants, not more complex: there's no bookkeeping about whether a
row or box "just completed," because there's nothing coarser than a
single cell to wait for. It also removes the need for the leaf-time
`_is_valid_completion` scan those solvers relied on -- once every cell
placed has already been individually validated on the way in, a complete
board is automatically a valid one. Validity becomes an invariant
maintained throughout the search, rather than something checked after
the fact.

Note on instrumentation: assignments_tried counts every candidate value
*considered* for a cell, whether or not the immediate constraint check
then accepts it -- not just the ones that get written to the board. That
keeps the metric measuring the same thing ("how many candidate values did
the search consider for a cell") as it does in the brute-force family,
where a candidate is always written before it's checked.

Expected behavior vs. the pruned brute-force variants: still exponential
in the worst case (this is still fixed-order DFS over the same tree), but
the effective branching factor at each cell is now however many
candidates are still legal at that point -- often far fewer than 9 -- so
in practice this should need dramatically fewer nodes than any brute-force
variant on the same puzzle. That's a prediction to confirm at the
benchmark stage, not an assumption to bake in here.

One thing this solver does *not* change: cell order is still naive fixed
row-major order, same as the rest of the family. Stage 4 (MRV) is about
changing *which* cell gets picked next, independent of when checking
happens -- this solver is the baseline that improvement gets measured
against.
"""

from __future__ import annotations

from sudoku.board import SIZE, Board
from sudoku.solvers.base import Solver


class BacktrackingSolver(Solver):
    name = "backtracking"

    def _solve(self, board: Board) -> bool:
        if not self._enter_node():
            return False

        empty = board.empty_cells()
        if not empty:
            return True

        row, col = empty[0]
        for value in range(1, SIZE + 1):
            self._record_assignment()
            self._record_constraint_check()
            if not board.is_valid_placement(row, col, value):
                continue
            board[(row, col)] = value
            if self._solve(board):
                return True
            board[(row, col)] = 0
        return False
