"""A from-scratch DPLL SAT solver applied to a CNF encoding of Sudoku.

Not a wrapper around an external SAT library (MiniSat, python-sat, ...):
using a black-box solver would mean the actual solving isn't something
built or understood here, breaking with how every other solver in this
project works. DPLL (Davis-Putnam-Logemann-Loveland) is implemented
directly: unit propagation to a fixed point, then branch on an
unassigned variable and recurse, backtracking on conflict.

The encoding: one boolean variable x[r,c,v] per (cell, value) pair -- 729
variables (SIZE^3) -- meaning "cell (r, c) contains value v." Clauses:

  - each cell has at least one value (81 clauses, one 9-literal OR each)
  - each cell has at most one value (81 x C(9,2) = 2,916 two-literal
    clauses, one per pair of values a cell can't hold simultaneously)
  - each row/column/box has each value at least once and at most once
    (the same "at least" / "at most" pattern, applied per unit per value)
  - the puzzle's givens become unit clauses (a single literal, forcing
    that variable true before search even starts)

A genuine design choice worth being explicit about: the "at least one"
clauses for rows/columns/boxes are technically *redundant* -- given
every cell has exactly one value and no unit repeats a value, pigeonhole
already forces every value to appear. They're included anyway because
adding logically-implied clauses that give the unit-propagation engine
more to work with is a standard, well-known SAT-encoding technique, and
the goal here is a faithful textbook encoding, not a minimal one.

Metrics: DPLL's structure maps onto the existing vocabulary more richly
than DLX's did, because unit propagation here is doing almost exactly
what naked-single propagation does in ac3.py -- just over a CNF
representation instead of a domain dict. A forced *positive* literal
(unit propagation proves a cell IS some value) is exactly "a cell's
value derived, not chosen," so it reuses propagated_assignments. A
forced *negative* literal (proves a cell is NOT some value) is exactly
one candidate ruled out, so it reuses candidate_eliminations. What's
genuinely new is a *conflict* -- unit propagation deriving a direct
contradiction (an empty clause), forcing an immediate backtrack -- there
is no existing counter for that, so it gets its own: conflicts.
constraint_checks, domain_lookups, hidden_singles_found,
naked_pairs_found, and columns_covered stay at 0: none of those
operations exist in a CNF solver.

One structural difference worth naming, not hiding: every other solver
in this project makes a single 9-ary decision per branch point ("assign
this cell one of its 9 possible values"). DPLL only ever makes *binary*
decisions (this variable is True, or it's False) -- a 9-ary Sudoku choice
becomes a sequence of up to 9 binary ones, most of which unit propagation
is expected to collapse before they're ever reached as a real decision.
"""

from __future__ import annotations

from sudoku.board import BOX_SIZE, SIZE, Board
from sudoku.solvers.base import Solver

NUM_VARS = SIZE * SIZE * SIZE  # 729


def _var(row: int, col: int, value: int) -> int:
    """1-indexed variable id for "(row, col) holds value" -- value is 1-9."""
    return row * SIZE * SIZE + col * SIZE + value


class _Clause:
    __slots__ = ("literals", "true_count", "unassigned_count")

    def __init__(self, literals: list[int]) -> None:
        self.literals = literals
        self.true_count = 0
        self.unassigned_count = len(literals)


class SATSolver(Solver):
    name = "sat"

    def _solve(self, board: Board) -> bool:
        clauses = self._build_clauses(board)
        occurs_pos: list[list[_Clause]] = [[] for _ in range(NUM_VARS + 1)]
        occurs_neg: list[list[_Clause]] = [[] for _ in range(NUM_VARS + 1)]
        for clause in clauses:
            for literal in clause.literals:
                (occurs_pos if literal > 0 else occurs_neg)[abs(literal)].append(clause)

        assignment: dict[int, bool] = {}
        trail, wiped_out = self._propagate(
            [], assignment, occurs_pos, occurs_neg, seed_literals=self._unit_literals(clauses)
        )
        if wiped_out:
            return False

        if not self._search(assignment, occurs_pos, occurs_neg):
            return False

        for row in range(SIZE):
            for col in range(SIZE):
                for value in range(1, SIZE + 1):
                    if assignment.get(_var(row, col, value)):
                        board[(row, col)] = value
        return True

    def _build_clauses(self, board: Board) -> list[_Clause]:
        clauses: list[list[int]] = []

        def at_least_one(vars_: list[int]) -> None:
            clauses.append(vars_)

        def at_most_one(vars_: list[int]) -> None:
            for i in range(len(vars_)):
                for j in range(i + 1, len(vars_)):
                    clauses.append([-vars_[i], -vars_[j]])

        for row in range(SIZE):
            for col in range(SIZE):
                cell_vars = [_var(row, col, v) for v in range(1, SIZE + 1)]
                at_least_one(cell_vars)
                at_most_one(cell_vars)

        for row in range(SIZE):
            for value in range(1, SIZE + 1):
                unit_vars = [_var(row, col, value) for col in range(SIZE)]
                at_least_one(unit_vars)
                at_most_one(unit_vars)

        for col in range(SIZE):
            for value in range(1, SIZE + 1):
                unit_vars = [_var(row, col, value) for row in range(SIZE)]
                at_least_one(unit_vars)
                at_most_one(unit_vars)

        for box_row in range(0, SIZE, BOX_SIZE):
            for box_col in range(0, SIZE, BOX_SIZE):
                for value in range(1, SIZE + 1):
                    unit_vars = [
                        _var(r, c, value)
                        for r in range(box_row, box_row + BOX_SIZE)
                        for c in range(box_col, box_col + BOX_SIZE)
                    ]
                    at_least_one(unit_vars)
                    at_most_one(unit_vars)

        for row in range(SIZE):
            for col in range(SIZE):
                value = board[(row, col)]
                if value != 0:
                    clauses.append([_var(row, col, value)])

        return [_Clause(literals) for literals in clauses]

    def _unit_literals(self, clauses: list[_Clause]) -> list[int]:
        return [clause.literals[0] for clause in clauses if len(clause.literals) == 1]

    def _search(
        self,
        assignment: dict[int, bool],
        occurs_pos: list[list[_Clause]],
        occurs_neg: list[list[_Clause]],
    ) -> bool:
        if not self._enter_node():
            return False

        if len(assignment) == NUM_VARS:
            return True

        var = next(v for v in range(1, NUM_VARS + 1) if v not in assignment)

        for value in (True, False):
            self._record_assignment()
            trail, wiped_out = self._propagate(
                [], assignment, occurs_pos, occurs_neg, seed_literals=[var if value else -var]
            )
            if not wiped_out and self._search(assignment, occurs_pos, occurs_neg):
                return True
            self._undo(trail, assignment, occurs_pos, occurs_neg)

        return False

    def _propagate(
        self,
        trail: list[int],
        assignment: dict[int, bool],
        occurs_pos: list[list[_Clause]],
        occurs_neg: list[list[_Clause]],
        seed_literals: list[int],
    ) -> tuple[list[int], bool]:
        """Assign every literal in the worklist and propagate to a fixed
        point. Returns the trail of variables this call assigned (for
        undo) and whether a conflict was found."""
        queue = list(seed_literals)
        while queue:
            literal = queue.pop()
            var = abs(literal)
            value = literal > 0
            if var in assignment:
                if assignment[var] != value:
                    self._record_conflict()
                    return trail, True
                continue

            assignment[var] = value
            trail.append(var)
            if value:
                self._record_propagated_assignment()
            else:
                self._record_candidate_elimination()

            satisfied, falsified = (occurs_pos[var], occurs_neg[var]) if value else (
                occurs_neg[var],
                occurs_pos[var],
            )
            for clause in satisfied:
                clause.true_count += 1
                clause.unassigned_count -= 1

            # Every clause referencing this variable must be updated
            # before checking for a conflict, not just the ones seen
            # before one is found -- _undo() reverses this variable's
            # *entire* occurrence list unconditionally, so bailing out
            # mid-loop here would leave later clauses never decremented
            # in the first place, and undo would still "revert" them,
            # drifting their counts. (This was a real bug: found by
            # tracking one specific clause's counters against a fresh
            # recount and seeing them diverge after an undo.)
            conflict = False
            newly_unit = []
            for clause in falsified:
                clause.unassigned_count -= 1
                if clause.true_count == 0:
                    if clause.unassigned_count == 0:
                        conflict = True
                    elif clause.unassigned_count == 1:
                        newly_unit.append(clause)

            if conflict:
                self._record_conflict()
                return trail, True
            for clause in newly_unit:
                queue.append(self._remaining_literal(clause, assignment))

        return trail, False

    def _remaining_literal(self, clause: _Clause, assignment: dict[int, bool]) -> int:
        for literal in clause.literals:
            if abs(literal) not in assignment:
                return literal
        raise AssertionError("unit clause has no unassigned literal")

    def _undo(
        self,
        trail: list[int],
        assignment: dict[int, bool],
        occurs_pos: list[list[_Clause]],
        occurs_neg: list[list[_Clause]],
    ) -> None:
        for var in reversed(trail):
            value = assignment.pop(var)
            same, other = (occurs_pos[var], occurs_neg[var]) if value else (
                occurs_neg[var],
                occurs_pos[var],
            )
            for clause in same:
                clause.true_count -= 1
                clause.unassigned_count += 1
            for clause in other:
                clause.unassigned_count += 1
        trail.clear()
