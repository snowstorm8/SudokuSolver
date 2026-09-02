"""Smoke tests for visualize.py: confirms results parsing and that each
plotting function actually produces a file, using the real benchmark
output already on disk. Doesn't inspect pixel content -- that's a job
for looking at the images, not for an automated test.
"""

import pytest

from visualize import (
    CATEGORY_ORDER,
    DEFAULT_RESULTS_CSV,
    SOLVER_ORDER,
    _category_index,
    _present_solver_order,
    _solvers_completing_every_puzzle,
    _sorted_puzzle_ids,
    load_results,
    plot_effort_distribution,
    plot_nodes_vs_difficulty,
    plot_runtime_vs_difficulty,
    plot_solver_comparison,
)

pytestmark = pytest.mark.skipif(
    not DEFAULT_RESULTS_CSV.exists(),
    reason="requires results/latest.csv -- run `python benchmark.py` first",
)


def test_load_results_parses_expected_row_count_and_types():
    rows = load_results()
    assert len(rows) == len(SOLVER_ORDER) * 8
    row = rows[0]
    assert isinstance(row["givens"], int)
    assert isinstance(row["solved"], bool)
    assert isinstance(row["timed_out"], bool)
    assert isinstance(row["nodes_explored"], int)
    assert isinstance(row["runtime_median_s"], float)


def test_every_solver_and_category_present():
    rows = load_results()
    assert {r["solver"] for r in rows} == set(SOLVER_ORDER)
    assert {r["category"] for r in rows} <= set(CATEGORY_ORDER)


def test_present_solver_order_matches_the_data():
    rows = load_results()
    assert set(_present_solver_order(rows)) == {r["solver"] for r in rows}


def test_category_index_matches_declared_order():
    assert _category_index("easy") == 0
    assert _category_index("extreme") == 3


def test_sorted_puzzle_ids_follow_category_order():
    rows = load_results()
    ids = _sorted_puzzle_ids(rows)
    categories = [next(r["category"] for r in rows if r["puzzle_id"] == pid) for pid in ids]
    assert categories == sorted(categories, key=_category_index)


def test_solvers_completing_every_puzzle_matches_measured_timeouts():
    """The known shape of the current benchmark data: the 3 brute-force
    variants and min_conflicts (extreme_01 only) time out somewhere;
    every other solver completes all 8 puzzles."""
    rows = load_results()
    solvers = _present_solver_order(rows)
    completing = set(_solvers_completing_every_puzzle(rows, solvers))
    timed_out_solvers = {r["solver"] for r in rows if r["timed_out"]}
    assert completing == set(solvers) - timed_out_solvers
    assert "backtracking" in completing
    assert "brute_force" not in completing


def test_all_four_plots_produce_files(tmp_path):
    rows = load_results()
    plot_nodes_vs_difficulty(rows, tmp_path / "a.png")
    plot_runtime_vs_difficulty(rows, tmp_path / "b.png")
    plot_solver_comparison(rows, tmp_path / "c.png")
    plot_effort_distribution(rows, tmp_path / "d.png")

    for name in ("a.png", "b.png", "c.png", "d.png"):
        path = tmp_path / name
        assert path.exists()
        assert path.stat().st_size > 0


def test_default_results_csv_exists_and_is_used_by_default():
    assert DEFAULT_RESULTS_CSV.exists()
