"""Backtracking with Minimum Remaining Values (MRV) cell selection.

Everything about *when* a placement gets checked is identical to
backtracking.py: every single assignment is validated immediately via
Board.is_valid_placement before recursing. The one thing this solver
changes is *which* empty cell gets filled next.

Standard backtracking always picks the first empty cell in row-major
order, regardless of how constrained it is. MRV instead picks whichever
empty cell currently has the fewest legal remaining values -- the "most
constrained variable" / "fail-first" heuristic:

  - A cell with zero legal candidates means this branch is already dead.
    Finding that cell as early as possible avoids wasting work deeper in
    a doomed subtree that a fixed order might not reach for many more
    assignments.
  - A cell with exactly one legal candidate isn't a real choice -- it's a
    forced consequence. Filling it immediately, rather than gambling on
    some wide-open cell first, avoids creating branches that never needed
    to exist.
  - A cell with many candidates is deferred, since it's the largest
    source of branching -- filling other cells first often narrows its
    options for free via shared row/column/box constraints.

Note this reuses the exact same constraint check as backtracking; it adds
no new pruning rule, only a different node order.

Design choices worth being explicit about:

- Candidates are recomputed from scratch for every empty cell at every
  node, rather than tracked incrementally as a running per-cell domain.
  That's a deliberate simplification to isolate cell *ordering* as the
  one variable this solver changes -- incremental domain tracking is
  what "forward checking" (a deferred future extension) would add.
- Finding the MRV cell is not free: it costs a constraint check for every
  candidate of every empty cell, not just the chosen one -- often
  hundreds of checks per node before a single value is even tried. The
  expectation is that this overhead is repaid by needing far fewer nodes
  overall, but whether total constraint_checks ends up lower or higher
  than plain backtracking is an empirical question, not an assumption
  baked in here.
- One optimization *does* fall directly out of the algorithm's own logic
  rather than being an arbitrary speedup: if a cell with zero candidates
  is found while scanning, the scan stops immediately, since zero is
  already the best (worst) possible score.
- Ties are broken by row-major order (the order Board.empty_cells()
  already returns), for determinism.
- assignments_tried counts values actually written to the board. Unlike
  backtracking, every candidate reaching that loop has already been
  filtered to be legal, so this solver never "tries and rejects" a value
  in the way backtracking's assignments_tried can -- the cost of ruling
  out illegal values instead shows up in constraint_checks, from the
  cell-selection scan.
"""

from __future__ import annotations

from sudoku.board import SIZE, Board
from sudoku.solvers.base import Solver


class MRVSolver(Solver):
    name = "mrv"

    def _solve(self, board: Board) -> bool:
        if not self._enter_node():
            return False

        empty = board.empty_cells()
        if not empty:
            return True

        (row, col), candidates = self._select_cell(board, empty)
        for value in candidates:
            self._record_assignment()
            board[(row, col)] = value
            if self._solve(board):
                return True
            board[(row, col)] = 0
        return False

    def _select_cell(
        self, board: Board, empty: list[tuple[int, int]]
    ) -> tuple[tuple[int, int], list[int]]:
        """Return the empty cell with the fewest legal candidates, and
        that candidate list (so callers don't need to recompute it)."""
        best_cell = empty[0]
        best_candidates = self._legal_values(board, *best_cell)
        for cell in empty[1:]:
            if not best_candidates:
                break  # zero is already the minimum possible -- stop early
            candidates = self._legal_values(board, *cell)
            if len(candidates) < len(best_candidates):
                best_cell, best_candidates = cell, candidates
        return best_cell, best_candidates

    def _legal_values(self, board: Board, row: int, col: int) -> list[int]:
        legal = []
        for value in range(1, SIZE + 1):
            self._record_constraint_check()
            if board.is_valid_placement(row, col, value):
                legal.append(value)
        return legal
