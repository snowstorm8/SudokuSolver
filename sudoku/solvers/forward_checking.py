"""Backtracking with forward checking: MRV cell selection, but with each
cell's candidate set maintained incrementally instead of recomputed from
scratch at every node.

A genuinely interesting fact falls out of comparing this to mrv.py: the
textbook selling point of forward checking is that it catches a peer
being reduced to zero candidates the moment that happens, rather than
only when the search reaches that cell. But MRVSolver already gets this
for free, as a side effect of recomputing every empty cell's candidates
from scratch at every single node -- if some peer was just wiped out, the
very next MRV scan sees it immediately, one level down. So the new
pruning power some textbooks credit to forward checking isn't new here.

What actually changes: HOW each cell's candidate set gets computed. MRV
re-derives it every node via SIZE calls to Board.is_valid_placement per
empty cell. This solver instead maintains a running `domains` dict
(cell -> set of remaining legal values) as search state: when a value is
assigned, it's removed from that cell's peers' domains directly (a set
operation, not a row/column/box rescan); when the search backtracks,
those exact removals are undone.

Given identical cell/value ordering rules to MRV, the first draft of this
docstring predicted the two would explore an *identical* search tree.
Measuring it against all 8 benchmark puzzles showed that's almost, but
not quite, right -- worth recording precisely rather than quietly fixing
the claim: assignments_tried came out exactly equal to MRV's on every
single puzzle (both try the same candidates in the same order), but
nodes_explored was never higher for this solver and strictly lower on 3
of 8. The reason is a genuine one-node asymmetry: when an assignment
would wipe out a peer's last candidate, this solver detects that via
propagation *before* recursing into the dead cell, so no node is spent
getting there. MRV can only discover the identical dead end one level
deeper, via its own next-node rescan -- which still costs one node to
find out. Same ultimate conclusion (this value fails), one solver
reaches it slightly earlier than the other.

Instrumentation: constraint_checks here counts only the one-time initial
domain build (SIZE calls to is_valid_placement per empty cell, done once
per solve() call, not per node) -- the same atomic operation the rest of
the family uses, so that startup cost stays comparable. Every domain
update *during* search is a different, cheaper operation (a single set
removal) and is counted separately as candidate_eliminations -- seeing
that a solver in this family did "8 checks" and another did "800
eliminations" is not a claim that one did 100x more work; they're
different units.
"""

from __future__ import annotations

from sudoku.board import SIZE, Board, peers
from sudoku.solvers.base import Solver

Domains = dict[tuple[int, int], set[int]]


class ForwardCheckingSolver(Solver):
    name = "forward_checking"

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
        candidates = sorted(domains[(row, col)])

        for value in candidates:
            self._record_assignment()
            board[(row, col)] = value

            removed, wiped_out = self._assign_and_propagate(board, domains, row, col, value)
            if not wiped_out and self._search(board, domains):
                return True

            self._undo_propagation(domains, removed, value)
            board[(row, col)] = 0

        return False

    def _assign_and_propagate(
        self, board: Board, domains: Domains, row: int, col: int, value: int
    ) -> tuple[list[tuple[int, int]], bool]:
        """Remove `value` from every still-unassigned peer's domain.
        Returns exactly which peers were changed (so the caller can undo
        precisely) and whether any peer was left with zero candidates.
        Stops propagating as soon as a wipeout is found -- once a branch
        is known dead there's no value in checking the remaining peers.
        """
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
