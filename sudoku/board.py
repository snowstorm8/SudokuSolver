"""Sudoku board representation and validation.

A board is a 9x9 grid of ints, 0 meaning "empty". This module is deliberately
free of any solving logic or instrumentation (node counts, timers, etc.) --
those belong to solvers. Board only answers questions about a single static
grid: is this placement legal, is this grid complete, is this grid valid.
"""

from __future__ import annotations

SIZE = 9
BOX_SIZE = 3

Grid = list[list[int]]


def _compute_peers(row: int, col: int) -> frozenset[tuple[int, int]]:
    cells = set()
    for c in range(SIZE):
        if c != col:
            cells.add((row, c))
    for r in range(SIZE):
        if r != row:
            cells.add((r, col))
    box_row, box_col = (row // BOX_SIZE) * BOX_SIZE, (col // BOX_SIZE) * BOX_SIZE
    for r in range(box_row, box_row + BOX_SIZE):
        for c in range(box_col, box_col + BOX_SIZE):
            if (r, c) != (row, col):
                cells.add((r, c))
    return frozenset(cells)


_PEERS = {
    (row, col): _compute_peers(row, col) for row in range(SIZE) for col in range(SIZE)
}


def peers(row: int, col: int) -> frozenset[tuple[int, int]]:
    """The up to 20 other cells sharing (row, col)'s row, column, or box.

    A pure structural fact about the 9x9 grid, independent of any board's
    contents -- computed once at import time, not per call. Lives here
    rather than in a solver because more than one solver needs the same
    notion of "peers" (constraint propagation depends on it directly).
    """
    return _PEERS[(row, col)]


def _compute_units() -> tuple[frozenset[tuple[int, int]], ...]:
    units = []
    for r in range(SIZE):
        units.append(frozenset((r, c) for c in range(SIZE)))
    for c in range(SIZE):
        units.append(frozenset((r, c) for r in range(SIZE)))
    for box_row in range(0, SIZE, BOX_SIZE):
        for box_col in range(0, SIZE, BOX_SIZE):
            units.append(
                frozenset(
                    (r, c)
                    for r in range(box_row, box_row + BOX_SIZE)
                    for c in range(box_col, box_col + BOX_SIZE)
                )
            )
    return tuple(units)


UNITS = _compute_units()
"""Every row, column, and box as a frozenset of its 9 cells (27 total).

Distinct from peers(): peers are the cells around *one* cell, useful for
"does this value conflict with anything nearby." Units are needed for
techniques that reason about an entire row/column/box at once -- e.g.
"which cells in this row could still hold a 7" can't be answered from any
single cell's peer set.
"""


class Board:
    def __init__(self, grid: Grid) -> None:
        _validate_shape(grid)
        # Defensive copy: callers must not be able to mutate our internal
        # state by continuing to hold a reference to the list they passed in.
        self.grid: Grid = [row[:] for row in grid]

    @classmethod
    def from_string(cls, text: str) -> "Board":
        """Parse an 81-character puzzle string.

        Digits '1'-'9' are givens, '0' or '.' are empty cells. All whitespace
        (spaces, newlines) is ignored, so both a single 81-char line and a
        9-line-by-9-char block are accepted.
        """
        compact = "".join(text.split())
        if len(compact) != SIZE * SIZE:
            raise ValueError(
                f"expected {SIZE * SIZE} puzzle characters, got {len(compact)}"
            )
        grid: Grid = []
        for r in range(SIZE):
            row = []
            for c in range(SIZE):
                ch = compact[r * SIZE + c]
                if ch == ".":
                    row.append(0)
                elif ch.isdigit():
                    row.append(int(ch))
                else:
                    raise ValueError(f"invalid puzzle character: {ch!r}")
            grid.append(row)
        return cls(grid)

    def copy(self) -> "Board":
        return Board(self.grid)

    def __getitem__(self, pos: tuple[int, int]) -> int:
        r, c = pos
        return self.grid[r][c]

    def __setitem__(self, pos: tuple[int, int], value: int) -> None:
        r, c = pos
        if not (0 <= value <= SIZE):
            raise ValueError(f"value must be 0-9, got {value}")
        self.grid[r][c] = value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Board):
            return NotImplemented
        return self.grid == other.grid

    def __str__(self) -> str:
        return "\n".join(
            " ".join(str(v) if v else "." for v in row) for row in self.grid
        )

    def is_empty(self, row: int, col: int) -> bool:
        return self.grid[row][col] == 0

    def empty_cells(self) -> list[tuple[int, int]]:
        return [
            (r, c)
            for r in range(SIZE)
            for c in range(SIZE)
            if self.grid[r][c] == 0
        ]

    def is_complete(self) -> bool:
        return all(self.grid[r][c] != 0 for r in range(SIZE) for c in range(SIZE))

    def is_valid_placement(self, row: int, col: int, value: int) -> bool:
        """Would `value` at (row, col) conflict with any peer already on the
        board? Ignores whatever is currently at (row, col) itself, so this
        can be used both to test an empty cell and to re-check a filled one.
        """
        for c in range(SIZE):
            if c != col and self.grid[row][c] == value:
                return False
        for r in range(SIZE):
            if r != row and self.grid[r][col] == value:
                return False
        box_row, box_col = (row // BOX_SIZE) * BOX_SIZE, (col // BOX_SIZE) * BOX_SIZE
        for r in range(box_row, box_row + BOX_SIZE):
            for c in range(box_col, box_col + BOX_SIZE):
                if (r, c) != (row, col) and self.grid[r][c] == value:
                    return False
        return True

    def is_valid(self) -> bool:
        """Whole-board validity: every filled cell is consistent with its
        peers. Used to reject a malformed/contradictory puzzle up front,
        before a solver ever starts searching.
        """
        for r in range(SIZE):
            for c in range(SIZE):
                value = self.grid[r][c]
                if value != 0 and not self.is_valid_placement(r, c, value):
                    return False
        return True


def _validate_shape(grid: Grid) -> None:
    if len(grid) != SIZE:
        raise ValueError(f"expected {SIZE} rows, got {len(grid)}")
    for row in grid:
        if len(row) != SIZE:
            raise ValueError(f"expected {SIZE} columns, got {len(row)}")
        for value in row:
            if not (0 <= value <= SIZE):
                raise ValueError(f"cell values must be 0-9, got {value}")
