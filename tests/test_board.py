import pytest

from sudoku.board import Board, peers

# The classic "easy" example puzzle (widely used in Sudoku write-ups) and its
# unique solution -- handy for tests here and for solver tests later, since
# we already know what a correct answer looks like.
GRID = [
    [5, 3, 0, 0, 7, 0, 0, 0, 0],
    [6, 0, 0, 1, 9, 5, 0, 0, 0],
    [0, 9, 8, 0, 0, 0, 0, 6, 0],
    [8, 0, 0, 0, 6, 0, 0, 0, 3],
    [4, 0, 0, 8, 0, 3, 0, 0, 1],
    [7, 0, 0, 0, 2, 0, 0, 0, 6],
    [0, 6, 0, 0, 0, 0, 2, 8, 0],
    [0, 0, 0, 4, 1, 9, 0, 0, 5],
    [0, 0, 0, 0, 8, 0, 0, 7, 9],
]

STRING = (
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

# A small hand-built grid for constraint tests, laid out so a row conflict,
# a column conflict, and a box conflict can each be triggered in isolation
# (no two constraint types overlap on the same test cell).
CONSTRAINT_GRID = [
    [1, 2, 3, 0, 0, 0, 0, 0, 0],
    [4, 5, 6, 0, 0, 0, 0, 0, 0],
    [7, 8, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
]


def test_from_string_matches_from_grid():
    assert Board.from_string(STRING) == Board(GRID)


def test_from_string_accepts_dots_and_multiline_layout():
    dotted = STRING.replace("0", ".")
    multiline = "\n".join(dotted[i : i + 9] for i in range(0, 81, 9))
    assert Board.from_string(multiline) == Board(GRID)


def test_from_string_rejects_wrong_length():
    with pytest.raises(ValueError):
        Board.from_string("123")


def test_from_string_rejects_invalid_characters():
    with pytest.raises(ValueError):
        Board.from_string("x" * 81)


def test_constructor_rejects_wrong_row_count():
    with pytest.raises(ValueError):
        Board([[0] * 9] * 8)


def test_constructor_rejects_wrong_column_count():
    bad = [row[:] for row in GRID]
    bad[0] = bad[0][:8]
    with pytest.raises(ValueError):
        Board(bad)


def test_constructor_rejects_out_of_range_values():
    bad = [row[:] for row in GRID]
    bad[0][0] = 10
    with pytest.raises(ValueError):
        Board(bad)


def test_constructor_does_not_alias_input_list():
    grid = [row[:] for row in GRID]
    board = Board(grid)
    grid[0][0] = 9
    assert board[(0, 0)] == 5


def test_copy_is_independent_of_original():
    board = Board(GRID)
    clone = board.copy()
    clone[(0, 0)] = 9
    assert board[(0, 0)] == 5
    assert clone[(0, 0)] == 9


def test_setitem_rejects_out_of_range_value():
    board = Board(GRID)
    with pytest.raises(ValueError):
        board[(0, 0)] = 10


def test_is_empty_and_empty_cells():
    board = Board(GRID)
    assert board.is_empty(0, 2) is True
    assert board.is_empty(0, 0) is False
    assert (0, 2) in board.empty_cells()
    assert len(board.empty_cells()) == sum(row.count(0) for row in GRID)


def test_is_complete_false_for_partial_board():
    assert Board(GRID).is_complete() is False


def test_is_complete_true_for_full_board():
    assert Board(SOLUTION_GRID).is_complete() is True


def test_row_conflict_detected_in_isolation():
    board = Board(CONSTRAINT_GRID)
    assert board.is_valid_placement(0, 3, 1) is False  # 1 already in row 0
    assert board.is_valid_placement(0, 3, 9) is True


def test_column_conflict_detected_in_isolation():
    board = Board(CONSTRAINT_GRID)
    assert board.is_valid_placement(3, 0, 1) is False  # 1 already in column 0
    assert board.is_valid_placement(3, 0, 9) is True


def test_box_conflict_detected_in_isolation():
    board = Board(CONSTRAINT_GRID)
    # 1 sits at (0, 0) in the same box as (2, 2); neither row 2 nor column 2
    # otherwise contains a 1, so this can only be a box conflict.
    assert board.is_valid_placement(2, 2, 1) is False
    assert board.is_valid_placement(2, 2, 9) is True


def test_is_valid_true_for_consistent_board():
    assert Board(CONSTRAINT_GRID).is_valid() is True


def test_is_valid_true_for_full_solution():
    assert Board(SOLUTION_GRID).is_valid() is True


def test_is_valid_false_when_a_duplicate_exists():
    bad = [row[:] for row in CONSTRAINT_GRID]
    bad[1][0] = 1  # duplicates the 1 already at (0, 0), same column
    assert Board(bad).is_valid() is False


def test_equality_compares_by_contents_not_identity():
    assert Board(GRID) == Board(GRID)
    assert Board(GRID) != Board(SOLUTION_GRID)


def test_peers_excludes_the_cell_itself():
    assert (4, 4) not in peers(4, 4)


def test_peers_count_is_the_standard_twenty():
    # 8 in the row + 8 in the column + 4 remaining in the box = 20
    assert len(peers(0, 0)) == 20
    assert len(peers(4, 4)) == 20


def test_peers_includes_full_row_column_and_box():
    p = peers(4, 4)
    assert all((4, c) in p for c in range(9) if c != 4)
    assert all((r, 4) in p for r in range(9) if r != 4)
    assert all((r, c) in p for r in range(3, 6) for c in range(3, 6) if (r, c) != (4, 4))


def test_peers_is_symmetric():
    # if B is a peer of A, A must be a peer of B
    for a in [(0, 0), (4, 4), (8, 8), (2, 7)]:
        for b in peers(*a):
            assert a in peers(*b)
