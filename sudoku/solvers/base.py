"""Common interface every solver implements, and the instrumentation that
makes their metrics comparable to each other.

Design note: metrics are collected centrally (`_enter_node`,
`_record_assignment`, `_record_constraint_check`) rather than left to each
subclass to tally independently. If every solver counted "a node" or "a
constraint check" in its own way, the numbers would look comparable in a
results table without actually being comparable. Routing every increment
through the same three methods means a node, an assignment, and a constraint
check mean the same thing regardless of which solver produced them.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from sudoku.board import Board

DEFAULT_TIMEOUT_SECONDS = 30.0

# How many nodes to explore between wall-clock checks. Checking every single
# node would call time.perf_counter() far more often than necessary; checking
# too rarely lets the solver run well past the timeout before it notices.
_TIMEOUT_CHECK_INTERVAL = 1000


@dataclass
class SolveMetrics:
    nodes_explored: int = 0
    assignments_tried: int = 0
    constraint_checks: int = 0
    # Specific to propagation-based solvers (forward checking onward): one
    # per value actually removed from a peer's candidate set. This is a
    # cheaper, different operation than constraint_checks (a set removal,
    # not a full row/column/box legality scan) -- the two are not the same
    # unit and a raw magnitude comparison between them is not meaningful.
    # Always 0 for solvers that don't do propagation.
    candidate_eliminations: int = 0
    # Specific to value-ordering heuristics (least-constraining-value
    # onward): one per peer-domain membership check performed while
    # scoring a candidate value, before any assignment is made. Distinct
    # from candidate_eliminations (a value actually removed) and from
    # constraint_checks (a full row/column/box legality scan) -- a
    # membership test against an already-known domain is cheaper than
    # either. Always 0 for solvers that don't reorder values.
    domain_lookups: int = 0
    # Specific to full constraint propagation (AC-3 / MAC onward): one per
    # cell whose value was *derived* by propagation reaching a fixed
    # point (a peer narrowed to a single remaining candidate), rather
    # than chosen and tried by the search loop. Counting these as
    # assignments_tried would misrepresent them -- they were never a
    # branching decision. Always 0 for solvers that don't propagate to a
    # fixed point.
    propagated_assignments: int = 0
    # Specific to human-technique elimination (stage 13 onward): how many
    # times each named technique actually fired. Distinct from
    # propagated_assignments (which counts *cells resolved*, regardless
    # of which technique resolved them) -- these count *technique
    # applications*, the basis for a difficulty rating by which
    # techniques a puzzle actually required rather than by clue count.
    # Always 0 for solvers that don't implement the technique.
    hidden_singles_found: int = 0
    naked_pairs_found: int = 0
    # Specific to Dancing Links (stage 14 onward): one per column covered
    # during search. DLX's exact-cover encoding makes legality structural
    # -- there is no is_valid_placement-equivalent call anywhere in it --
    # so constraint_checks and every propagation-specific counter above
    # legitimately stay 0 for this solver; that absence is a real fact
    # about how it works, not a gap. columns_covered is its own atomic
    # unit of work, the same way each prior solver's genuinely new
    # operation got its own counter.
    columns_covered: int = 0
    # Specific to local search / min-conflicts (stage 17 onward): one per
    # restart from a fresh random assignment after getting stuck. This is
    # the one genuinely new event that kind of algorithm introduces --
    # nothing else here ever discards its own progress and starts over.
    # Always 0 for every complete-search solver.
    restarts: int = 0
    # Specific to the SAT/DPLL encoding (stage 15 onward): one per direct
    # contradiction unit propagation derives (an empty clause), forcing
    # an immediate backtrack. Standard SAT-solving vocabulary with no
    # equivalent among the counters above -- a forced positive literal
    # reuses propagated_assignments and a forced negative literal reuses
    # candidate_eliminations, since those are the same underlying
    # concepts, but a conflict is genuinely new. Always 0 for solvers
    # that aren't CNF-based.
    conflicts: int = 0
    runtime_seconds: float = 0.0
    timed_out: bool = False


@dataclass
class SolveResult:
    solved: bool
    board: Board | None
    metrics: SolveMetrics


class Solver(ABC):
    """Base class for all solving algorithms.

    Subclasses implement `_solve`, which mutates the board it is given
    in-place and returns True if a solution was found. Subclasses are
    responsible for calling `_enter_node()` once per recursive call (and
    bailing out if it returns False, meaning the timeout fired) and for
    calling `_record_assignment()` / `_record_constraint_check()` at the
    appropriate points in their search.
    """

    name: str = "solver"

    def __init__(self, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self.timeout_seconds = timeout_seconds
        self._metrics = SolveMetrics()
        self._deadline = 0.0

    def solve(self, board: Board) -> SolveResult:
        """Solve `board` without mutating it. Returns the solution (if any)
        plus the metrics collected along the way.
        """
        if not board.is_valid():
            return SolveResult(solved=False, board=None, metrics=SolveMetrics())

        working = board.copy()
        self._metrics = SolveMetrics()
        self._deadline = time.perf_counter() + self.timeout_seconds

        start = time.perf_counter()
        solved = self._solve(working)
        self._metrics.runtime_seconds = time.perf_counter() - start

        solved = solved and not self._metrics.timed_out
        return SolveResult(
            solved=solved,
            board=working if solved else None,
            metrics=self._metrics,
        )

    @abstractmethod
    def _solve(self, board: Board) -> bool:
        """Mutate `board` in place toward a solution. Return True if solved."""
        raise NotImplementedError

    def _enter_node(self) -> bool:
        """Call once at the top of every recursive call. Returns False once
        the timeout has fired, at which point the caller should unwind
        immediately (`return False`) without doing further work.
        """
        self._metrics.nodes_explored += 1
        if (
            not self._metrics.timed_out
            and self._metrics.nodes_explored % _TIMEOUT_CHECK_INTERVAL == 0
            and time.perf_counter() > self._deadline
        ):
            self._metrics.timed_out = True
        return not self._metrics.timed_out

    def _record_assignment(self) -> None:
        self._metrics.assignments_tried += 1

    def _record_constraint_check(self) -> None:
        self._metrics.constraint_checks += 1

    def _record_candidate_elimination(self) -> None:
        self._metrics.candidate_eliminations += 1

    def _record_domain_lookup(self) -> None:
        self._metrics.domain_lookups += 1

    def _record_propagated_assignment(self) -> None:
        self._metrics.propagated_assignments += 1

    def _record_hidden_single(self) -> None:
        self._metrics.hidden_singles_found += 1

    def _record_naked_pair(self) -> None:
        self._metrics.naked_pairs_found += 1

    def _record_column_covered(self) -> None:
        self._metrics.columns_covered += 1

    def _record_restart(self) -> None:
        self._metrics.restarts += 1

    def _record_conflict(self) -> None:
        self._metrics.conflicts += 1
