import pytest

from cli import main
from sudoku.solvers import SOLVERS_BY_NAME
from tests.sample_puzzles import CLASSIC_EASY_STRING, unsolvable_few_blanks


def test_list_solvers_prints_every_registered_solver(capsys):
    exit_code = main(["--list-solvers"])
    out = capsys.readouterr().out
    assert exit_code == 0
    for name in SOLVERS_BY_NAME:
        assert name in out


def test_solves_a_puzzle_given_as_a_string(capsys):
    exit_code = main(["--solver", "mrv", "--puzzle-string", CLASSIC_EASY_STRING])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "solved=True" in out


def test_solves_a_puzzle_given_as_a_file_path(capsys, tmp_path):
    puzzle_file = tmp_path / "puzzle.txt"
    puzzle_file.write_text(CLASSIC_EASY_STRING)
    exit_code = main(["--solver", "backtracking", "--puzzle", str(puzzle_file)])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "solved=True" in out


def test_reports_failure_for_an_unsolvable_puzzle(capsys):
    grid_string = "".join(str(v) for row in unsolvable_few_blanks().grid for v in row)
    exit_code = main(["--solver", "backtracking", "--puzzle-string", grid_string])
    out = capsys.readouterr().out
    assert exit_code == 1
    assert "No solution exists" in out


def test_missing_solver_exits_with_error():
    with pytest.raises(SystemExit):
        main(["--puzzle-string", CLASSIC_EASY_STRING])


def test_missing_puzzle_source_exits_with_error():
    with pytest.raises(SystemExit):
        main(["--solver", "mrv"])


def test_unknown_solver_name_rejected_by_argparse():
    with pytest.raises(SystemExit):
        main(["--solver", "not_a_real_solver", "--puzzle-string", CLASSIC_EASY_STRING])
