"""Full constraint propagation (AC-3, specialized for Sudoku's
all-different constraints), maintained throughout search -- sometimes
called MAC (Maintaining Arc Consistency) to distinguish it from running
AC-3 once as a preprocessing pass.

Arc consistency, generally: an arc (X, Y) is consistent if every value
still in X's domain has some supporting value in Y's domain. AC-3
maintains this across every constrained pair by repeatedly revising arcs
and re-queuing any arc whose endpoint just changed, until nothing more
can be removed or some domain empties out.

The simplification specific to this project: every constraint here is the
same "not equal to my peer" relation. For a not-equal constraint, the
generic revise rule collapses to something much simpler: a value only
needs to be removed from a domain when a *peer's* domain has narrowed to
exactly that one value -- i.e., whenever a peer becomes a singleton,
propagate its forced value outward. That's precisely the Sudoku technique
"naked single" propagation. This solver implements that specialized,
Sudoku-specific form of AC-3's fixed point -- not the fully generic
arc-queue algorithm with a general constraint predicate -- since the two
reach an identical fixed point here and the specialized form is simpler
and faster.

The real difference from forward_checking.py: that solver propagates one
hop, from the cell just assigned to its direct peers, and stops. This
solver cascades -- if propagating causes some peer to become a singleton,
that singleton is immediately committed to the board and propagated
further in turn, transitively, until nothing more can be deduced or a
wipeout is found. This means part of a puzzle can get resolved by pure
propagation, with zero branching by the search loop -- something
forward checking's one-hop version structurally cannot do. Whether any
benchmark puzzle gets fully solved this way, with no branching at all, is
a real question this project's tests check directly rather than assume.

This is also run once, upfront, on the domains built purely from the
puzzle's givens -- before the search loop starts at all -- since any
cell already forced to a single candidate by the givens alone (a "naked
single" baked into the puzzle) should be resolved for free, not
discovered one node at a time by the search loop later.

Instrumentation: a cell resolved by propagation was never tried by the
search loop, it was derived -- counting it as assignments_tried would
misrepresent what happened. Counted separately as
propagated_assignments. Domain removals during propagation are still
candidate_eliminations, the same unit forward checking and LCV use.
"""

from __future__ import annotations

from sudoku.board import SIZE, Board, peers
from sudoku.solvers.base import Solver

Domains = dict[tuple[int, int], set[int]]
Assignment = tuple[int, int, int]  # (row, col, value)


class AC3Solver(Solver):
    name = "ac3"

    def _solve(self, board: Board) -> bool:
        domains = self._init_domains(board)
        if self._resolve_initial_singletons(board, domains):
            return False  # wiped out by propagation among the givens alone
        return self._search(board, domains)

    def _resolve_initial_singletons(self, board: Board, domains: Domains) -> bool:
        """Resolve any cell already forced to one candidate by the givens
        alone, before search starts. Done one at a time -- find a
        singleton, write and propagate it fully, then look again -- NOT
        by finding every such cell up front and writing them all before
        propagating any of them. Two peer cells can each independently
        look like "the only legal value is 5" purely against the
        (unchanged) givens, without yet accounting for each other; writing
        both directly would silently create a conflict propagation was
        supposed to catch. Processing one at a time through the same
        propagate-immediately path as every other assignment is what
        makes that conflict visible as a wipeout instead.
        Returns True on a wipeout.
        """
        while True:
            singleton = next(
                ((r, c) for r, c in board.empty_cells() if len(domains[(r, c)]) == 1),
                None,
            )
            if singleton is None:
                return False

            row, col = singleton
            value = next(iter(domains[(row, col)]))
            board[(row, col)] = value
            self._record_propagated_assignment()

            _, _, wiped_out = self._propagate(board, domains, [(row, col, value)])
            if wiped_out:
                return True

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

            removed, forced, wiped_out = self._propagate(board, domains, [(row, col, value)])
            if not wiped_out and self._search(board, domains):
                return True

            self._undo(board, domains, removed, forced)
            board[(row, col)] = 0

        return False

    def _propagate(
        self, board: Board, domains: Domains, queue: list[Assignment]
    ) -> tuple[list[Assignment], list[Assignment], bool]:
        """Propagate a worklist of forced (row, col, value) assignments to
        a full fixed point. Every item in `queue` must already be written
        to the board and counted by the caller -- this method only
        handles the ripple effects: removing each value from its peers'
        domains, committing (and counting) any new singleton it creates,
        and queuing that new singleton for further propagation. Stops the
        instant a wipeout is found, since the branch is already dead.

        Returns every domain removal made (for precise undo), every cell
        this call newly forced onto the board (to un-write on backtrack),
        and whether a wipeout occurred.
        """
        removed: list[Assignment] = []
        forced: list[Assignment] = []
        queue = list(queue)

        while queue:
            row, col, value = queue.pop()
            for peer_row, peer_col in peers(row, col):
                if not board.is_empty(peer_row, peer_col):
                    continue
                peer_domain = domains[(peer_row, peer_col)]
                if value not in peer_domain:
                    continue

                peer_domain.discard(value)
                self._record_candidate_elimination()
                removed.append((peer_row, peer_col, value))

                if not peer_domain:
                    return removed, forced, True

                if len(peer_domain) == 1:
                    forced_value = next(iter(peer_domain))
                    # A forced cell isn't propagated to ITS peers until
                    # it's popped from this queue (below) -- in that gap,
                    # an unrelated elimination chain can independently
                    # narrow a different peer to this same value and
                    # commit it first, since a peer that's already been
                    # written is skipped (via is_empty) by everyone else's
                    # propagation. That's a real contradiction, just
                    # discovered late -- verifying against the actual
                    # board before committing catches it as a wipeout
                    # instead of silently writing a conflicting value.
                    if not board.is_valid_placement(peer_row, peer_col, forced_value):
                        return removed, forced, True
                    board[(peer_row, peer_col)] = forced_value
                    self._record_propagated_assignment()
                    forced.append((peer_row, peer_col, forced_value))
                    queue.append((peer_row, peer_col, forced_value))

        return removed, forced, False

    def _undo(
        self, board: Board, domains: Domains, removed: list[Assignment], forced: list[Assignment]
    ) -> None:
        for row, col, _value in forced:
            board[(row, col)] = 0
        for row, col, value in removed:
            domains[(row, col)].add(value)
