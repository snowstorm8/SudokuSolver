"""Local search / min-conflicts -- the largest character shift in this
project. Every other solver constructs a partial assignment and
backtracks when it fails. This one starts from a *complete* assignment
(every cell filled, likely with many constraint violations) and
repeatedly repairs the worst-conflicting cell, never undoing anything --
there is no search tree, no recursion, no undo, just a sequence of moves
on one mutable board.

That difference breaks assumptions the rest of this project relies on,
worth stating plainly rather than glossing over:

- This algorithm is *incomplete*. It can fail to find a solution that
  exists, by getting stuck in a local optimum no single swap escapes.
  Every other solver here is complete: given enough time, it either
  finds a solution or correctly proves none exists.
- It can **never prove a puzzle unsolvable**. A failure to converge means
  "didn't find one," not "none exists" -- there is no equivalent of a
  wipeout or an empty domain here, just running out of budget. Because
  of that, this solver reports every failure to converge as
  timed_out = True, whether the wall-clock limit or the internal
  iteration/restart budget was what actually stopped it -- never as a
  bare "no solution," which every other solver in this project can
  correctly claim but this one structurally cannot.
- It needs randomness -- restarts and tie-breaking -- which is seeded
  (default seed 0) for the same reproducibility every other solver gets
  from being fully deterministic.

Algorithm: fill each row with a random permutation of its still-missing
digits. This is a deliberate initialization choice, not the naive "every
blank cell fully random": it makes every row conflict-free *by
construction*, so only column and box conflicts ever need fixing, which
roughly halves the constraint surface search has to repair from the
start. Moves are row-local swaps between two non-given cells, not free
reassignment -- reassigning a single cell to any value would break the
"every row is a permutation" invariant every subsequent move depends on.
Each iteration: pick a conflicted cell at random, evaluate swapping it
with every other non-given cell in its row, and take whichever swap
minimizes total conflicts afterward (ties broken randomly) -- the "min
conflicts" the algorithm is named for. If a restart's iteration budget
runs out without reaching zero conflicts, discard progress and refill
from scratch with a new random assignment.

Instrumentation: nodes_explored is repurposed as an iteration count (one
per conflicted cell examined and repaired) -- the closest analog this
paradigm has to "a step of search," and reusing _enter_node() for it
gets the existing timeout-polling mechanism for free. assignments_tried
counts every candidate swap partner evaluated, not just the winning one,
consistent with how every other solver counts candidates considered.
constraint_checks counts peer comparisons made while counting conflicts,
the same atomic unit used everywhere else. restarts is a genuinely new
event this solver introduces: nothing else here ever discards its own
progress and starts over.
"""

from __future__ import annotations

import random

from sudoku.board import BOX_SIZE, SIZE, Board
from sudoku.solvers.base import DEFAULT_TIMEOUT_SECONDS, Solver

MAX_ITERATIONS_PER_RESTART = 5000
MAX_RESTARTS = 50


class MinConflictsSolver(Solver):
    name = "min_conflicts"

    def __init__(
        self, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS, seed: int = 0
    ) -> None:
        super().__init__(timeout_seconds)
        self._seed = seed

    def _solve(self, board: Board) -> bool:
        rng = random.Random(self._seed)
        is_given = [[board[(r, c)] != 0 for c in range(SIZE)] for r in range(SIZE)]

        for _restart in range(MAX_RESTARTS):
            self._fill_rows_randomly(board, is_given, rng)

            for _iteration in range(MAX_ITERATIONS_PER_RESTART):
                if not self._enter_node():
                    self._metrics.timed_out = True
                    return False

                conflicted = self._find_conflicted_cells(board, is_given)
                if not conflicted:
                    return True

                row, col = rng.choice(conflicted)
                self._repair(board, is_given, row, col, rng)

            self._record_restart()

        self._metrics.timed_out = True  # exhausted every restart -- inconclusive, not proof
        return False

    def _fill_rows_randomly(
        self, board: Board, is_given: list[list[bool]], rng: random.Random
    ) -> None:
        """Overwrites every non-given cell in every row with a fresh
        random permutation of that row's still-missing digits --
        "missing" relative to the fixed givens only, so this is safe to
        call on a restart too, not just the first fill."""
        for row in range(SIZE):
            present = {board[(row, c)] for c in range(SIZE) if is_given[row][c]}
            missing = [v for v in range(1, SIZE + 1) if v not in present]
            rng.shuffle(missing)
            non_given_cols = [c for c in range(SIZE) if not is_given[row][c]]
            for col, value in zip(non_given_cols, missing):
                board[(row, col)] = value

    def _conflicts_at(
        self,
        board: Board,
        row: int,
        col: int,
        value: int,
        ignore: frozenset[tuple[int, int]],
    ) -> int:
        """How many peers (column + box only -- rows are always conflict
        free by construction) currently hold `value`, excluding cells in
        `ignore` (the cells involved in a hypothetical swap, so they
        don't get compared against their own about-to-change value)."""
        count = 0
        for r in range(SIZE):
            if r != row and (r, col) not in ignore:
                self._record_constraint_check()
                if board[(r, col)] == value:
                    count += 1
        box_row, box_col = (row // BOX_SIZE) * BOX_SIZE, (col // BOX_SIZE) * BOX_SIZE
        for r in range(box_row, box_row + BOX_SIZE):
            for c in range(box_col, box_col + BOX_SIZE):
                if (r, c) != (row, col) and (r, c) not in ignore:
                    self._record_constraint_check()
                    if board[(r, c)] == value:
                        count += 1
        return count

    def _find_conflicted_cells(
        self, board: Board, is_given: list[list[bool]]
    ) -> list[tuple[int, int]]:
        conflicted = []
        for row in range(SIZE):
            for col in range(SIZE):
                if not is_given[row][col]:
                    value = board[(row, col)]
                    if self._conflicts_at(board, row, col, value, frozenset()) > 0:
                        conflicted.append((row, col))
        return conflicted

    def _repair(
        self,
        board: Board,
        is_given: list[list[bool]],
        row: int,
        col1: int,
        rng: random.Random,
    ) -> None:
        """Swap (row, col1) with whichever other non-given cell in the
        same row minimizes total conflicts afterward, ties broken
        randomly. A structural blind spot of row-swap moves, worth being
        upfront about: a row with fewer than 2 non-given cells has no
        swap partner at all, so a conflicted cell there can never be
        repaired by this solver -- there's nothing to do but leave it
        (the iteration becomes a no-op), and if that's the actual
        obstruction, every restart will hit the same wall and this
        solver will honestly exhaust its budget rather than converge.
        """
        value1 = board[(row, col1)]
        candidates = [c for c in range(SIZE) if c != col1 and not is_given[row][c]]
        if not candidates:
            return

        best_score = None
        best_partners: list[int] = []
        for col2 in candidates:
            self._record_assignment()
            value2 = board[(row, col2)]
            ignore = frozenset({(row, col1), (row, col2)})
            score = self._conflicts_at(board, row, col1, value2, ignore) + self._conflicts_at(
                board, row, col2, value1, ignore
            )
            if best_score is None or score < best_score:
                best_score = score
                best_partners = [col2]
            elif score == best_score:
                best_partners.append(col2)

        col2 = rng.choice(best_partners)
        board[(row, col1)], board[(row, col2)] = board[(row, col2)], board[(row, col1)]
