"""MRV cell selection with a degree-heuristic tiebreak, instead of
row-major position, when candidate counts are equal.

Deliberately built as a minimal diff against mrv.py, not a standalone
heuristic, so the comparison isolates exactly one variable: everything
here is identical to MRVSolver -- same checking timing, same primary
selection rule (fewest legal candidates first) -- except how ties in that
count get broken.

Why not just ignore domain size and sort by degree alone? Because MRV's
"fewest candidates" signal is the stronger one: a cell with one legal
value should always be filled before a cell with five, regardless of how
connected either is. Throwing that away in favor of pure connectivity
would very likely be a worse heuristic, not an interesting comparison.
The narrower, genuinely testable question is: when MRV *can't* distinguish
two cells by candidate count, does breaking that tie by connectivity
instead of by position actually reduce search effort?

The "degree" of a cell is how many of its peers (sudoku.board.peers,
added in stage 9 for forward checking) are still unassigned. The
intuition: among equally-constrained cells, resolving the more connected
one first has a larger ripple effect on every other cell's candidates.
Ties are broken lazily -- degree is only computed for a cell when it's
actually needed to break a candidate-count tie, not for every cell
scanned, keeping the added cost proportional to how often ties actually
occur rather than a fixed per-node tax.

Degree itself is a plain peer-count -- no board legality check, no
domain mutation -- so it isn't counted toward constraint_checks or
candidate_eliminations; it's a different, much cheaper kind of operation
than either, and forcing it into one of those buckets would misrepresent
what it costs.

Whether this tiebreak actually helps, hurts, or does nothing relative to
plain MRV is exactly the kind of question to measure, not assume -- see
this project's tests and, eventually, the benchmark.
"""

from __future__ import annotations

from sudoku.board import SIZE, Board, peers
from sudoku.solvers.base import Solver


class MRVDegreeSolver(Solver):
    name = "mrv_degree"

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
        best_cell = empty[0]
        best_candidates = self._legal_values(board, *best_cell)
        best_degree = self._degree(board, best_cell) if best_candidates else None

        for cell in empty[1:]:
            if not best_candidates:
                break  # zero is already the minimum possible -- stop early

            candidates = self._legal_values(board, *cell)
            if not candidates:
                best_cell, best_candidates = cell, candidates
                break

            if len(candidates) < len(best_candidates):
                best_cell, best_candidates = cell, candidates
                best_degree = self._degree(board, cell)
            elif len(candidates) == len(best_candidates):
                degree = self._degree(board, cell)
                if degree > best_degree:
                    best_cell, best_candidates, best_degree = cell, candidates, degree

        return best_cell, best_candidates

    def _legal_values(self, board: Board, row: int, col: int) -> list[int]:
        legal = []
        for value in range(1, SIZE + 1):
            self._record_constraint_check()
            if board.is_valid_placement(row, col, value):
                legal.append(value)
        return legal

    def _degree(self, board: Board, cell: tuple[int, int]) -> int:
        row, col = cell
        return sum(1 for r, c in peers(row, col) if board.is_empty(r, c))
