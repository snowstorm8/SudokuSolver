"""Registry of every solver in this project.

The single source of truth for "which solvers exist" -- both benchmark.py
and cli.py import ALL_SOLVERS / SOLVERS_BY_NAME from here rather than each
keeping their own list, so adding a new solver later means registering it
in exactly one place.
"""

from __future__ import annotations

from sudoku.solvers.ac3 import AC3Solver
from sudoku.solvers.backtracking import BacktrackingSolver
from sudoku.solvers.base import Solver
from sudoku.solvers.brute_force import BruteForceSolver
from sudoku.solvers.brute_force_row_box_pruned import RowBoxPrunedBruteForceSolver
from sudoku.solvers.brute_force_row_pruned import RowPrunedBruteForceSolver
from sudoku.solvers.cp_sat import CPSATSolver
from sudoku.solvers.cp_sat import cp_model as _cp_model
from sudoku.solvers.dlx import DLXSolver
from sudoku.solvers.forward_checking import ForwardCheckingSolver
from sudoku.solvers.human_technique import HumanTechniqueSolver
from sudoku.solvers.lcv import LCVSolver
from sudoku.solvers.min_conflicts import MinConflictsSolver
from sudoku.solvers.mrv import MRVSolver
from sudoku.solvers.mrv_degree import MRVDegreeSolver
from sudoku.solvers.sat import SATSolver

ALL_SOLVERS: list[type[Solver]] = [
    BruteForceSolver,
    RowPrunedBruteForceSolver,
    RowBoxPrunedBruteForceSolver,
    BacktrackingSolver,
    MRVSolver,
    ForwardCheckingSolver,
    MRVDegreeSolver,
    LCVSolver,
    AC3Solver,
    HumanTechniqueSolver,
    DLXSolver,
    SATSolver,
    MinConflictsSolver,
]

# CPSATSolver needs the optional `ortools` dependency (see
# requirements-optional.txt). Only register it when that import actually
# succeeded, so benchmark.py and `cli.py --list-solvers` simply don't
# mention it rather than crashing when it's missing.
if _cp_model is not None:
    ALL_SOLVERS.append(CPSATSolver)

SOLVERS_BY_NAME: dict[str, type[Solver]] = {cls.name: cls for cls in ALL_SOLVERS}
