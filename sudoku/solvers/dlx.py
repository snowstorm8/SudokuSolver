"""Dancing Links (Knuth's Algorithm X) -- the first solver in this
project that isn't Sudoku-specific backtracking at all, but a general
exact-cover solver applied to a Sudoku-shaped matrix.

The reformulation: every (row, col, value) placement must satisfy
exactly 4 constraints --

  - this cell is filled (81 constraints: one per cell)
  - this row has this value exactly once (81: one per row/value pair)
  - this column has this value exactly once (81: one per column/value pair)
  - this box has this value exactly once (81: one per box/value pair)

-- giving a 729-row (9x9 cells x 9 values) by 324-column (4 x 81
constraints) binary matrix. Solving the puzzle is finding a set of rows
that covers every column exactly once: an *exact cover*. Algorithm X
solves that by repeatedly picking the column with the fewest remaining
candidate rows (this is DLX's own built-in MRV -- Knuth's paper calls it
the S heuristic), trying each row that satisfies it, and recursively
removing ("covering") every column and row that choice conflicts with.
"Dancing Links" is the specific trick that makes covering -- and,
critically, *uncovering* on backtrack -- O(1): a circular doubly-linked
list node can be spliced out with two pointer writes, and spliced back
in exactly where it was with two more, no copying or restoring an array.

Where this fits the existing metrics, and where it deliberately doesn't:
nodes_explored and assignments_tried transfer cleanly, because Algorithm
X's recursion has the exact same shape as every other solver here --
pick the most constrained thing, try each option, recurse, backtrack.
constraint_checks and every propagation-specific counter (
candidate_eliminations, domain_lookups, propagated_assignments,
hidden_singles_found, naked_pairs_found) legitimately stay at 0 for this
solver: DLX's exact-cover encoding makes legality structural -- a row
literally cannot be chosen once its column is gone -- so there is no
is_valid_placement-equivalent call anywhere in this file. That's a real
fact about how the algorithm achieves correctness, not a gap in
instrumentation. columns_covered is this solver's own new atomic unit,
one per covered column, the same pattern every prior stage's genuinely
new operation followed.

Given clues are handled by covering their row before search starts, the
same way a value would be covered during search -- from the matrix's
perspective a given digit and a search-chosen digit are the same kind of
fact, just decided before vs. during the recursion.
"""

from __future__ import annotations

from sudoku.board import BOX_SIZE, SIZE, Board
from sudoku.solvers.base import Solver

NUM_CONSTRAINTS = 4 * SIZE * SIZE  # cell, row-value, col-value, box-value


class _Node:
    __slots__ = ("left", "right", "up", "down", "column", "row_id")

    def __init__(self) -> None:
        self.left = self.right = self.up = self.down = self
        self.column: _Column | None = None
        self.row_id: tuple[int, int, int] | None = None  # (row, col, value)


class _Column(_Node):
    __slots__ = ("size",)

    def __init__(self) -> None:
        super().__init__()
        self.column = self
        self.size = 0


def _constraint_columns(row: int, col: int, value: int) -> tuple[int, int, int, int]:
    """The 4 constraint-column indices a (row, col, value) placement
    satisfies. value is 1-9."""
    v = value - 1
    cell = row * SIZE + col
    row_value = SIZE * SIZE + row * SIZE + v
    col_value = 2 * SIZE * SIZE + col * SIZE + v
    box = (row // BOX_SIZE) * BOX_SIZE + (col // BOX_SIZE)
    box_value = 3 * SIZE * SIZE + box * SIZE + v
    return cell, row_value, col_value, box_value


class DLXSolver(Solver):
    name = "dlx"

    def _solve(self, board: Board) -> bool:
        header, row_nodes = self._build_matrix()

        # A given digit is a constraint choice already made -- cover its
        # row's columns before search starts, exactly as search would if
        # it chose this row itself.
        for row, col in [(r, c) for r in range(SIZE) for c in range(SIZE)]:
            value = board[(row, col)]
            if value != 0:
                self._select_row(row_nodes[(row, col, value)])

        solution: list[_Node] = []
        if not self._search(header, solution):
            return False

        for node in solution:
            row, col, value = node.row_id
            board[(row, col)] = value
        return True

    def _build_matrix(self) -> tuple[_Column, dict[tuple[int, int, int], _Node]]:
        header = _Column()
        columns = [_Column() for _ in range(NUM_CONSTRAINTS)]
        for col in columns:
            col.right = header
            col.left = header.left
            header.left.right = col
            header.left = col

        row_nodes: dict[tuple[int, int, int], _Node] = {}
        for row in range(SIZE):
            for col in range(SIZE):
                for value in range(1, SIZE + 1):
                    nodes = [_Node() for _ in range(4)]
                    for node, col_index in zip(nodes, _constraint_columns(row, col, value)):
                        node.row_id = (row, col, value)
                        column = columns[col_index]
                        node.column = column
                        node.up = column.up
                        node.down = column
                        column.up.down = node
                        column.up = node
                        column.size += 1
                    for i in range(4):
                        nodes[i].right = nodes[(i + 1) % 4]
                        nodes[i].left = nodes[(i - 1) % 4]
                    row_nodes[(row, col, value)] = nodes[0]
        return header, row_nodes

    def _search(self, header: _Column, solution: list[_Node]) -> bool:
        if not self._enter_node():
            return False

        if header.right is header:
            return True  # every constraint covered -- solved

        column = self._choose_column(header)
        if column.size == 0:
            return False  # some constraint has no way left to satisfy it

        self._cover(column)
        node = column.down
        while node is not column:
            self._record_assignment()
            solution.append(node)
            right = node.right
            while right is not node:
                self._cover(right.column)
                right = right.right

            if self._search(header, solution):
                return True

            solution.pop()
            left = node.left
            while left is not node:
                self._uncover(left.column)
                left = left.left
            node = node.down

        self._uncover(column)
        return False

    def _choose_column(self, header: _Column) -> _Column:
        best = header.right
        column = best.right
        while column is not header:
            if column.size < best.size:
                best = column
            column = column.right
        return best

    def _select_row(self, node: _Node) -> None:
        """Commit a row (used for the puzzle's givens, before search
        starts) by covering its own column and every column its other
        3 nodes touch -- the same effect search has when it picks a row,
        just never undone since givens aren't backtracked over."""
        self._cover(node.column)
        right = node.right
        while right is not node:
            self._cover(right.column)
            right = right.right

    def _cover(self, column: _Column) -> None:
        self._record_column_covered()
        column.right.left = column.left
        column.left.right = column.right
        node = column.down
        while node is not column:
            right = node.right
            while right is not node:
                right.down.up = right.up
                right.up.down = right.down
                right.column.size -= 1
                right = right.right
            node = node.down

    def _uncover(self, column: _Column) -> None:
        node = column.up
        while node is not column:
            left = node.left
            while left is not node:
                left.column.size += 1
                left.down.up = left
                left.up.down = left
                left = left.left
            node = node.up
        column.right.left = column
        column.left.right = column
