"""Forward checking with Least Constraining Value (LCV) ordering: the
first solver in this project to change *value* order rather than cell
order.

Every solver up to this one tries candidate values in a fixed ascending
order. LCV is MRV's natural complement: where MRV picks the most
constrained *cell* to fail fast, LCV picks the least constraining *value*
for whichever cell was picked, on the theory that leaving other cells'
options open as long as possible reduces the chance of talking yourself
into a dead end. Concretely: for the selected cell, each candidate value
is scored by how many still-unassigned peers currently have that value as
an option -- i.e., how many peer domains would shrink if it were chosen
here -- and values are tried smallest-score (least constraining) first.

Built on top of ForwardCheckingSolver, not MRVSolver, for a concrete
reason: scoring "how constraining is this value" means asking "how many
peer domains still contain it," and forward checking already maintains
those domains as live search state. MRV recomputes everything from
scratch and keeps no persistent domain structure to ask that question of
-- bolting LCV onto it would mean re-deriving the same information from
nothing. Building on forward checking instead isolates value ordering as
the one new variable against the baseline that already has what it needs.

_init_domains, _assign_and_propagate, and _undo_propagation below are
identical to forward_checking.py, duplicated rather than shared -- the
same choice made for the brute-force pruning ladder: each solver stays
readable start to finish without chasing a shared base across files, at
the cost of a few duplicated methods. The only new method is
_order_by_least_constraining; everything else is forward checking as-is.

Instrumentation: scoring candidates costs a domain membership check per
(peer, candidate value) pair -- a real, different operation from either
constraint_checks (a full legality scan) or candidate_eliminations (a
value actually removed). Counted separately as domain_lookups.

What this is expected to help with, and what it structurally can't: LCV
only matters when there's an actual solution to find and a real choice of
values to order -- it can help find that solution with less wasted
branching. It has no reason to help prove a puzzle is *unsolvable*: to
establish that, the search has to rule out every value for every cell
somewhere, regardless of what order they're tried in, so reordering
values doesn't change how much of the space needs to be ruled out. That's
a hypothesis to check against this project's benchmark, not an assumption
built into the design.
"""

from __future__ import annotations

from sudoku.board import SIZE, Board, peers
from sudoku.solvers.base import Solver

Domains = dict[tuple[int, int], set[int]]


class LCVSolver(Solver):
    name = "lcv"

    def _solve(self, board: Board) -> bool:
        domains = self._init_domains(board)
        return self._search(board, domains)

    def _init_domains(self, board: Board) -> Domains:
        domains: Domains = {}
        for row, col in board.empty_cells():
            legal = set()
            for value in range(1, SIZE + 1):
                self._record_constraint_check()
                if board.is_valid_placement(row, col, value):
                    legal.add(value)
            domains[(row, col)] = legal
        return domains

    def _search(self, board: Board, domains: Domains) -> bool:
        if not self._enter_node():
            return False

        empty = board.empty_cells()
        if not empty:
            return True

        row, col = min(empty, key=lambda cell: (len(domains[cell]), cell))
        candidates = self._order_by_least_constraining(board, domains, row, col)

        for value in candidates:
            self._record_assignment()
            board[(row, col)] = value

            removed, wiped_out = self._assign_and_propagate(board, domains, row, col, value)
            if not wiped_out and self._search(board, domains):
                return True

            self._undo_propagation(domains, removed, value)
            board[(row, col)] = 0

        return False

    def _order_by_least_constraining(
        self, board: Board, domains: Domains, row: int, col: int
    ) -> list[int]:
        cell_peers = peers(row, col)

        def constraining_count(value: int) -> int:
            count = 0
            for peer_row, peer_col in cell_peers:
                if board.is_empty(peer_row, peer_col):
                    self._record_domain_lookup()
                    if value in domains[(peer_row, peer_col)]:
                        count += 1
            return count

        return sorted(domains[(row, col)], key=lambda v: (constraining_count(v), v))

    def _assign_and_propagate(
        self, board: Board, domains: Domains, row: int, col: int, value: int
    ) -> tuple[list[tuple[int, int]], bool]:
        removed = []
        wiped_out = False
        for peer_row, peer_col in peers(row, col):
            if board.is_empty(peer_row, peer_col) and value in domains[(peer_row, peer_col)]:
                domains[(peer_row, peer_col)].discard(value)
                self._record_candidate_elimination()
                removed.append((peer_row, peer_col))
                if not domains[(peer_row, peer_col)]:
                    wiped_out = True
                    break
        return removed, wiped_out

    def _undo_propagation(
        self, domains: Domains, removed: list[tuple[int, int]], value: int
    ) -> None:
        for peer in removed:
            domains[peer].add(value)
