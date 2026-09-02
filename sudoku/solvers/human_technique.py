"""Human-technique elimination: naked singles, hidden singles, and naked
pairs, falling back to MRV-guided search only once genuinely stuck.

Every prior propagation-based solver (forward_checking.py, lcv.py,
ac3.py) reasons purely about a single cell's own domain size. That
misses two things a human solver routinely uses:

- A **hidden single**: a candidate value that can legally go in only one
  cell within some row, column, or box -- even if that cell still has
  OTHER candidates too, so it never shows up as a "naked" (obviously
  size-1) domain. Finding one requires looking at an entire unit at
  once ("which cells in this row could still be a 7"), which is exactly
  what Board.UNITS exists for -- peers() alone can't answer it.
- A **naked pair**: two cells in the same unit whose domains are
  identically {a, b}. Between just those two cells, a and b are fully
  "used up" -- neither value can legally appear anywhere else in that
  unit, so both can be eliminated from every other cell there, even
  though neither of the pair cells is itself resolved.

Deliberately not implemented, to keep this solver's scope bounded: hidden
pairs, pointing pairs / box-line reduction, and anything past that
(X-Wing, Swordfish, ...). Naked singles + hidden singles + naked pairs is
enough to go meaningfully beyond AC-3 and support a real technique-based
difficulty signal without building a full human-solving-technique
library.

Architecture: this is ac3.py's fixed-point propagation with two more
techniques layered into the SAME loop, tried in order of cost -- naked
singles first (cheapest, and AC-3 already proves it alone can solve some
puzzles outright), then hidden singles, then naked pairs -- falling
through to the next technique only when the cheaper ones have nothing
left to do, and looping back to naked singles whenever a stronger
technique makes any change (since it might have just created a new one).
Search is the final fallback, identical in shape to ac3.py's, once a full
pass finds no technique that makes any progress at all.

The natural payoff this project cares about: a puzzle's actual required
technique tier is now directly measurable, not guessed from clue count.
hidden_singles_found == 0 and naked_pairs_found == 0 and
nodes_explored == 1 means the puzzle was naked-singles-only, exactly like
AC3Solver would show. naked_pairs_found > 0 with nodes_explored still 1
means it needed the strongest technique here but no guessing at all.
nodes_explored > 1 means none of these three techniques, even combined,
were enough -- real search was required. That's a difficulty signal
grounded in what was actually necessary to solve the puzzle, not in how
many clues it started with.

Instrumentation: a cell resolved by any of these techniques is counted
as propagated_assignments (never assignments_tried -- it was derived,
not guessed), consistent with ac3.py. Domain narrowing from any
technique is candidate_eliminations, the same unit every propagation
based solver uses. Scanning units to look for a hidden single or naked
pair costs domain membership checks -- the same kind of cheap operation
LCV's domain_lookups already counts, reused here rather than inventing
yet another near-identical counter. hidden_singles_found and
naked_pairs_found count technique *applications*, not the eliminations
they cause -- the basis for the difficulty tier described above.
"""

from __future__ import annotations

from sudoku.board import SIZE, UNITS, Board, peers
from sudoku.solvers.base import Solver

Domains = dict[tuple[int, int], set[int]]
Assignment = tuple[int, int, int]  # (row, col, value)


class HumanTechniqueSolver(Solver):
    name = "human_technique"

    def _solve(self, board: Board) -> bool:
        domains = self._init_domains(board)
        _, _, wiped_out = self._propagate(board, domains, [])
        if wiped_out:
            return False
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

            removed, forced, wiped_out = self._propagate(board, domains, [(row, col, value)])
            if not wiped_out and self._search(board, domains):
                return True

            self._undo(board, domains, removed, forced)
            board[(row, col)] = 0

        return False

    def _propagate(
        self, board: Board, domains: Domains, queue: list[Assignment]
    ) -> tuple[list[Assignment], list[Assignment], bool]:
        """Propagate to a full fixed point using every technique this
        solver knows, strongest fallback last. `queue` items must already
        be written to the board, exactly like ac3.py's _propagate.
        """
        removed: list[Assignment] = []
        forced: list[Assignment] = []
        queue = list(queue)

        while True:
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
                        if not board.is_valid_placement(peer_row, peer_col, forced_value):
                            return removed, forced, True
                        board[(peer_row, peer_col)] = forced_value
                        self._record_propagated_assignment()
                        forced.append((peer_row, peer_col, forced_value))
                        queue.append((peer_row, peer_col, forced_value))

            # A stronger technique can narrow a domain to size 1 without
            # explicitly queuing it -- catch that before trying anything
            # even stronger, same fix as ac3.py needed for its own bug.
            missed_single = next(
                ((r, c) for r, c in board.empty_cells() if len(domains[(r, c)]) == 1),
                None,
            )
            if missed_single is not None:
                row, col = missed_single
                value = next(iter(domains[(row, col)]))
                if not board.is_valid_placement(row, col, value):
                    return removed, forced, True
                board[(row, col)] = value
                self._record_propagated_assignment()
                forced.append((row, col, value))
                queue.append((row, col, value))
                continue

            hidden = self._find_hidden_single(board, domains)
            if hidden is not None:
                row, col, value = hidden
                for other_value in list(domains[(row, col)]):
                    if other_value != value:
                        domains[(row, col)].discard(other_value)
                        self._record_candidate_elimination()
                        removed.append((row, col, other_value))
                self._record_hidden_single()
                if not board.is_valid_placement(row, col, value):
                    return removed, forced, True
                board[(row, col)] = value
                self._record_propagated_assignment()
                forced.append((row, col, value))
                queue.append((row, col, value))
                continue

            pair = self._find_naked_pair(board, domains)
            if pair is not None:
                values, other_cells = pair
                wiped_out = False
                for r, c in other_cells:
                    for v in values:
                        if v in domains[(r, c)]:
                            domains[(r, c)].discard(v)
                            self._record_candidate_elimination()
                            removed.append((r, c, v))
                            if not domains[(r, c)]:
                                wiped_out = True
                self._record_naked_pair()
                if wiped_out:
                    return removed, forced, True
                continue

            return removed, forced, False

    def _find_hidden_single(
        self, board: Board, domains: Domains
    ) -> tuple[int, int, int] | None:
        """A candidate that can legally go in exactly one cell of some
        unit, even though that cell may have other candidates too."""
        for unit in UNITS:
            empty_in_unit = [cell for cell in unit if board.is_empty(*cell)]
            for value in range(1, SIZE + 1):
                holders = []
                for cell in empty_in_unit:
                    self._record_domain_lookup()
                    if value in domains[cell]:
                        holders.append(cell)
                if len(holders) == 1 and len(domains[holders[0]]) > 1:
                    row, col = holders[0]
                    return row, col, value
        return None

    def _find_naked_pair(
        self, board: Board, domains: Domains
    ) -> tuple[frozenset[int], list[tuple[int, int]]] | None:
        """Two cells in a unit sharing an identical 2-value domain, where
        at least one other cell in that unit still has one of those
        values as a candidate (otherwise there's nothing to eliminate)."""
        for unit in UNITS:
            empty_in_unit = [cell for cell in unit if board.is_empty(*cell)]
            pairs_by_domain: dict[frozenset[int], list[tuple[int, int]]] = {}
            for cell in empty_in_unit:
                self._record_domain_lookup()
                if len(domains[cell]) == 2:
                    pairs_by_domain.setdefault(frozenset(domains[cell]), []).append(cell)

            for values, cells in pairs_by_domain.items():
                if len(cells) != 2:
                    continue
                others = [c for c in empty_in_unit if c not in cells]
                affected = [c for c in others if domains[c] & values]
                if affected:
                    return values, affected
        return None

    def _undo(
        self, board: Board, domains: Domains, removed: list[Assignment], forced: list[Assignment]
    ) -> None:
        for row, col, _value in forced:
            board[(row, col)] = 0
        for row, col, value in removed:
            domains[(row, col)].add(value)
