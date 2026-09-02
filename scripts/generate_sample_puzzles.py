"""One-off script that generated the self-constructed puzzles under
puzzles/{easy,medium,hard,extreme}/ (the ones NOT sourced from a named
external puzzle -- see puzzles/manifest.csv for which is which).

Kept in the repo for transparency and reproducibility rather than run
routinely: anyone can see exactly how these puzzles were made, verify
them, or generate a larger set the same way later.

Method: start from one valid, complete 81-cell Sudoku solution. Derive a
few more complete solutions from it using transformations that provably
preserve validity (relabeling every digit through a fixed permutation;
transposing the grid), so the sample set isn't just one solution with
different cells blanked out. Then remove a target number of cells,
chosen with a fixed random seed for reproducibility.

Removing cells from an already-valid, complete grid can only ever ADD
solutions relative to that one, never remove it -- so every puzzle this
produces is guaranteed solvable. It is NOT guaranteed to have a UNIQUE
solution. An earlier version of this docstring claimed that risk only
mattered "at low clue counts" and left the manifest's uniqueness caveat
off puzzles with more givens (easy_02, medium_01, medium_02, hard_01).
That assumption was wrong: stage 10 found, by direct construction, that
hard_01 (26 givens) has at least two distinct valid solutions -- both
MRVSolver and MRVDegreeSolver solve it, to two different, independently
verified completions. The manifest now flags all six self-constructed
puzzles equally, since none of them were ever actually checked for
uniqueness -- only for solvability. Difficulty is being used here purely
as a clue-count proxy, not an independently validated rating -- whether
that proxy actually predicts computational effort is exactly the kind
of question this project's benchmark is meant to investigate, not
something to assume up front.
"""

from __future__ import annotations

import random
from pathlib import Path

from sudoku.board import SIZE, Board
from sudoku.solvers.backtracking import BacktrackingSolver

PUZZLES_DIR = Path(__file__).resolve().parent.parent / "puzzles"

BASE_SOLUTION = [
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


def relabel(grid: list[list[int]], shift: int) -> list[list[int]]:
    mapping = {v: ((v - 1 + shift) % SIZE) + 1 for v in range(1, SIZE + 1)}
    return [[mapping[v] for v in row] for row in grid]


def transpose(grid: list[list[int]]) -> list[list[int]]:
    return [list(col) for col in zip(*grid)]


def remove_cells(grid: list[list[int]], count: int, rng: random.Random) -> list[list[int]]:
    grid = [row[:] for row in grid]
    cells = [(r, c) for r in range(SIZE) for c in range(SIZE)]
    rng.shuffle(cells)
    for r, c in cells[:count]:
        grid[r][c] = 0
    return grid


def grid_to_string(grid: list[list[int]]) -> str:
    return "".join(str(v) for row in grid for v in row)


def build_and_verify(name: str, grid: list[list[int]], givens: int, seed: int) -> str:
    rng = random.Random(seed)
    blanks = SIZE * SIZE - givens
    puzzle_grid = remove_cells(grid, blanks, rng)
    board = Board(puzzle_grid)
    assert board.is_valid(), f"{name}: constructed puzzle is not internally valid"

    result = BacktrackingSolver(timeout_seconds=30).solve(board)
    assert result.solved, f"{name}: constructed puzzle turned out unsolvable"

    puzzle_string = grid_to_string(puzzle_grid)
    actual_givens = sum(1 for ch in puzzle_string if ch != "0")
    print(f"{name}: {actual_givens} givens, verified solvable")
    return puzzle_string


def main() -> None:
    grid_a = BASE_SOLUTION
    grid_b = relabel(BASE_SOLUTION, shift=3)
    grid_c = transpose(relabel(BASE_SOLUTION, shift=6))

    targets = [
        ("easy/easy_02.txt", grid_a, 36, 1),
        ("medium/medium_01.txt", grid_b, 30, 2),
        ("medium/medium_02.txt", grid_c, 28, 3),
        ("hard/hard_01.txt", grid_a, 26, 4),
        ("hard/hard_02.txt", grid_b, 24, 5),
        ("extreme/extreme_02.txt", grid_c, 22, 6),
    ]

    for filename, grid, givens, seed in targets:
        puzzle_string = build_and_verify(filename, grid, givens, seed)
        path = PUZZLES_DIR / filename
        path.write_text(puzzle_string + "\n")


if __name__ == "__main__":
    main()
