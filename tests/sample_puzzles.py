"""Small, hand-verified puzzles shared across solver test files.

Not a test module itself (no test_ prefix) -- pytest won't collect it.
Kept in one place so every solver's tests exercise the exact same known
cases, and so the somewhat fiddly unsolvable construction below only has
to be gotten right once.
"""

from sudoku.board import Board

# A complete, valid, well-known Sudoku solution -- used as a base for
# constructing smaller test puzzles below.
SOLUTION_GRID = [
    [5, 3, 4, 6, 7, 8, 9, 1, 2],
    [6, 7, 2, 1, 9, 5, 3, 4, 8],
    [1, 9, 8, 3, 4, 2, 5, 6, 7],
    [8, 5, 9, 7, 6, 1, 4, 2, 3],
    [4, 2, 6, 8, 5, 3, 7, 9, 1],
    [7, 1, 3, 9, 2, 4, 8, 5, 6],
    [9, 6, 1, 5, 3, 7, 2, 8, 4],
    [2, 8, 7, 4, 1, 9, 6, 3, 5],
    [3, 4, 5, 2, 8, 6, 1, 7, 9],
]

# The classic "easy" newspaper-style example (51 givens... actually 30
# givens / 51 blanks) -- realistic enough that leaf-only brute force is
# expected to time out on it. Useful for confirming that expectation, not
# for correctness tests (which need something that finishes quickly).
CLASSIC_EASY_STRING = (
    "530070000"
    "600195000"
    "098000060"
    "800060003"
    "400803001"
    "700020006"
    "060000280"
    "000419005"
    "000080079"
)

# Three blanks, one per row -- each is uniquely forced by its own row
# alone (the row already contains the other 8 digits), so this has a
# guaranteed unique solution while keeping the search tiny enough for
# even leaf-only brute force to finish in well under a second.
_SOLVABLE_BLANKS = [(0, 8), (1, 0), (2, 4)]


def solvable_few_blanks() -> Board:
    grid = [row[:] for row in SOLUTION_GRID]
    for r, c in _SOLVABLE_BLANKS:
        grid[r][c] = 0
    return Board(grid)


def expected_solution() -> Board:
    return Board(SOLUTION_GRID)


def unsolvable_few_blanks() -> Board:
    """A 2-blank puzzle with no solution.

    Built from SOLUTION_GRID by blanking (0, 8) (whose row already
    contains every digit except its true value, 2) and then blocking
    that one remaining candidate: (3, 8) is changed from 3 to 2 (and
    (3, 7), which held the row's original 2, is blanked to keep the
    givens internally consistent). That puts a 2 in column 8, so (0, 8)
    can be neither 2 (column conflict) nor anything else (every other
    digit already sits elsewhere in its row) -- zero valid candidates,
    verified via Board.is_valid_placement in tests/test_board.py-style
    reasoning and confirmed programmatically while this was built.
    """
    grid = [row[:] for row in SOLUTION_GRID]
    grid[0][8] = 0
    grid[3][7] = 0
    grid[3][8] = 2
    return Board(grid)
