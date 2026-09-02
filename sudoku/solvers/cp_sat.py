"""Google OR-Tools CP-SAT applied to Sudoku -- a deliberately different
kind of entry in this project. Every other solver here is an algorithm
built and understood from scratch; this one is a *model* handed to a
mature, professional constraint solver. The question this stage answers
isn't "how does this algorithm work" but "how does everything built by
hand in this project compare to just reaching for an industrial-strength
tool."

Optional dependency: this file is importable, and CPSATSolver is always
defined, but calling .solve() raises a clear RuntimeError if `ortools`
isn't installed (see requirements-optional.txt). sudoku/solvers/__init__.py
only adds this solver to ALL_SOLVERS when the import actually succeeds,
so benchmark.py and cli.py --list-solvers simply don't mention it rather
than crashing when the optional dependency is missing.

The model itself is almost the whole file, which is the point: CP-SAT
gets 81 integer variables, each with domain [1, 9] directly (no boolean
flattening needed -- contrast this with sat.py's 729-boolean-variable
encoding, which needed explicit "at least one value" clauses precisely
because plain CNF has no notion of a multi-valued domain; a CP solver's
native finite-domain variables make that constraint free), plus one
AllDifferent global constraint per row, column, and box, plus a fixed
value per given. No search code, no propagation code -- CP-SAT supplies
all of that internally, as a black box by design.

A genuine, deliberate design choice: CP-SAT defaults to multi-threaded
parallel search using several strategies at once, which would be neither
reproducible (different runs could finish via different threads at
different times) nor comparable to this project's single-threaded
solvers in any node-count sense. This solver forces single-threaded,
seeded search instead, trading away some of CP-SAT's real-world
performance advantage for a fair, reproducible comparison -- an honest
tradeoff, not a hidden one.

Metrics: this solver never calls _enter_node() or any _record_* method,
since there is no search loop here to instrument -- instead, after
Solve() returns, its own reported statistics are read directly and
written once: nodes_explored from NumBranches() (CP-SAT's own notion of
a search decision point) and conflicts from NumConflicts(), reusing the
same counter sat.py introduced, since CP-SAT's search core is itself
SAT-based and "conflict" means the same thing there. assignments_tried
and everything else stay at 0: CP-SAT doesn't expose a comparable
per-node "candidates tried" figure, and every other counter in this
project names an operation (a domain check, a propagation technique, an
exact-cover column) that simply isn't visible from outside this solver.
timed_out is set directly rather than discovered via the timeout-polling
_enter_node() mechanism every other solver uses, since CP-SAT enforces
its own internal time limit and reports whether it was hit via its
solve status.
"""

from __future__ import annotations

from sudoku.board import BOX_SIZE, SIZE, Board
from sudoku.solvers.base import Solver

try:
    from ortools.sat.python import cp_model
except ImportError:
    cp_model = None


class CPSATSolver(Solver):
    name = "cp_sat"

    def _solve(self, board: Board) -> bool:
        if cp_model is None:
            raise RuntimeError(
                "ortools is not installed. Install it with "
                "`pip install -r requirements-optional.txt` (or `pip install ortools`) "
                "to use CPSATSolver."
            )

        model = cp_model.CpModel()
        cells = {
            (row, col): model.NewIntVar(1, SIZE, f"cell_{row}_{col}")
            for row in range(SIZE)
            for col in range(SIZE)
        }

        for row in range(SIZE):
            model.AddAllDifferent(cells[(row, col)] for col in range(SIZE))
        for col in range(SIZE):
            model.AddAllDifferent(cells[(row, col)] for row in range(SIZE))
        for box_row in range(0, SIZE, BOX_SIZE):
            for box_col in range(0, SIZE, BOX_SIZE):
                model.AddAllDifferent(
                    cells[(r, c)]
                    for r in range(box_row, box_row + BOX_SIZE)
                    for c in range(box_col, box_col + BOX_SIZE)
                )
        for row in range(SIZE):
            for col in range(SIZE):
                value = board[(row, col)]
                if value != 0:
                    model.Add(cells[(row, col)] == value)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.timeout_seconds
        solver.parameters.num_search_workers = 1  # deterministic, comparable to our solvers
        solver.parameters.random_seed = 0

        status = solver.Solve(model)

        self._metrics.nodes_explored = solver.NumBranches()
        self._metrics.conflicts = solver.NumConflicts()

        if status == cp_model.UNKNOWN:
            self._metrics.timed_out = True
            return False
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return False

        for row in range(SIZE):
            for col in range(SIZE):
                board[(row, col)] = solver.Value(cells[(row, col)])
        return True
