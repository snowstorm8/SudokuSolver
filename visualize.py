"""Reads benchmark.py's CSV output and produces comparison plots. Every
plot below is generated from an actual results file on disk (default:
results/latest.csv) -- nothing here embeds a number directly.

A methodological note that shapes every plot in this file: some solvers
time out on some puzzles (all 3 brute-force variants on every puzzle in
the set; min_conflicts on exactly one, extreme_01 -- see its stage-17
writeup in the README). A timed-out row's nodes_explored is "how far the
search got before giving up," not "how many nodes the puzzle needs" --
not the same kind of measurement as a completed run, and plotting the
two on equal footing would misrepresent what was measured. Because of
this:

- The two "vs. difficulty" trend plots use only solvers that completed
  every single puzzle in the set (computed from the data, not a
  hardcoded list -- see _solvers_completing_every_puzzle), since those
  are the only ones with a real "cost to solve" number everywhere.
- The two comparison plots that include every solver mark every
  timed-out cell/box distinctly and say so in the title, rather than
  presenting a lower bound as if it were a completion.

This logic is generic across whichever solvers happen to time out on
whichever puzzles -- it doesn't hardcode "brute force" as the only
family capable of failing, since stage 17 proved that assumption wrong.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # must precede the pyplot import: no display in CI/headless runs
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import colormaps  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "results"
DEFAULT_RESULTS_CSV = RESULTS_DIR / "latest.csv"
PLOTS_DIR = RESULTS_DIR / "plots"

CATEGORY_ORDER = ["easy", "medium", "hard", "extreme"]

# Roughly the order each solver was introduced (stages 2-17), grouped by
# family, so related solvers land near each other in every plot.
SOLVER_ORDER = [
    "brute_force",
    "brute_force_row_pruned",
    "brute_force_row_box_pruned",
    "backtracking",
    "mrv",
    "mrv_degree",
    "lcv",
    "forward_checking",
    "ac3",
    "human_technique",
    "dlx",
    "sat",
    "cp_sat",
    "min_conflicts",
]


def _present_solver_order(rows: list[dict]) -> list[str]:
    """A results file from before a given solver existed won't list it --
    plot against whichever solvers actually appear in this run rather
    than the full roster above, so an older or narrower CSV doesn't
    crash plotting."""
    present = {r["solver"] for r in rows}
    ordered = [s for s in SOLVER_ORDER if s in present]
    return ordered + sorted(present - set(ordered))  # any unrecognized name, still shown


# Distinct color per solver, generated rather than hand-picked: a fixed
# dict of hex codes already needed revisiting every time a solver was
# added, the same lesson benchmark.py's FIELDNAMES and cli.py's metrics
# printout already learned from hardcoded lists falling behind.
def _solver_colors(solvers: list[str]) -> dict[str, tuple]:
    palette = colormaps["tab20"].resampled(max(len(solvers), 1))
    return {solver: palette(i) for i, solver in enumerate(solvers)}


def _solvers_completing_every_puzzle(rows: list[dict], solvers: list[str]) -> list[str]:
    timed_out_solvers = {r["solver"] for r in rows if r["timed_out"]}
    return [s for s in solvers if s not in timed_out_solvers]


def load_results(path: Path = DEFAULT_RESULTS_CSV) -> list[dict]:
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    # Every SolveMetrics field that's an int in practice; parsed
    # generically so a results file doesn't need a matching hand-edit to
    # this function every time a new counter is added elsewhere.
    int_fields = {
        "givens",
        "nodes_explored",
        "assignments_tried",
        "constraint_checks",
        "candidate_eliminations",
        "domain_lookups",
        "propagated_assignments",
        "hidden_singles_found",
        "naked_pairs_found",
        "columns_covered",
        "restarts",
        "conflicts",
        "num_runs",
    }
    for row in rows:
        for field in int_fields:
            if field in row:
                row[field] = int(row[field])
        row["solved"] = row["solved"] == "True"
        row["timed_out"] = row["timed_out"] == "True"
        row["runtime_median_s"] = float(row["runtime_median_s"])
    return rows


def _category_index(category: str) -> int:
    return CATEGORY_ORDER.index(category)


def _sorted_puzzle_ids(rows: list[dict]) -> list[str]:
    category_by_id = {r["puzzle_id"]: r["category"] for r in rows}
    return sorted(
        category_by_id,
        key=lambda pid: (_category_index(category_by_id[pid]), pid),
    )


def plot_nodes_vs_difficulty(rows: list[dict], out_path: Path) -> None:
    solvers = _present_solver_order(rows)
    completing = _solvers_completing_every_puzzle(rows, solvers)
    colors = _solver_colors(solvers)

    fig, ax = plt.subplots(figsize=(9, 5.5))
    for solver in completing:
        solver_rows = [r for r in rows if r["solver"] == solver]
        xs = [_category_index(r["category"]) for r in solver_rows]
        ys = [r["nodes_explored"] for r in solver_rows]
        ax.scatter(xs, ys, label=solver, color=colors[solver], s=60, alpha=0.85, zorder=3)
    ax.set_yscale("log")
    ax.set_xticks(range(len(CATEGORY_ORDER)))
    ax.set_xticklabels(CATEGORY_ORDER)
    ax.set_xlim(-0.5, len(CATEGORY_ORDER) - 0.5)
    ax.set_xlabel("puzzle category (clue-count proxy -- see puzzles/manifest.csv)")
    ax.set_ylabel("nodes explored (log scale)")
    ax.set_title(
        "Search nodes vs. puzzle category\n"
        "(only solvers that completed every puzzle; see solver_comparison.png for all of them)"
    )
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_runtime_vs_difficulty(rows: list[dict], out_path: Path) -> None:
    solvers = _present_solver_order(rows)
    completing = _solvers_completing_every_puzzle(rows, solvers)
    colors = _solver_colors(solvers)

    fig, ax = plt.subplots(figsize=(9, 5.5))
    for solver in completing:
        solver_rows = [r for r in rows if r["solver"] == solver]
        xs = [_category_index(r["category"]) for r in solver_rows]
        ys = [r["runtime_median_s"] * 1000 for r in solver_rows]
        ax.scatter(xs, ys, label=solver, color=colors[solver], s=60, alpha=0.85, zorder=3)
    ax.set_yscale("log")
    ax.set_xticks(range(len(CATEGORY_ORDER)))
    ax.set_xticklabels(CATEGORY_ORDER)
    ax.set_xlim(-0.5, len(CATEGORY_ORDER) - 0.5)
    ax.set_xlabel("puzzle category (clue-count proxy -- see puzzles/manifest.csv)")
    ax.set_ylabel("median runtime, ms (log scale)")
    ax.set_title(
        "Runtime vs. puzzle category\n"
        "(only solvers that completed every puzzle; see solver_comparison.png for all of them)"
    )
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_solver_comparison(rows: list[dict], out_path: Path) -> None:
    """A heatmap, not a grouped bar chart: with 14 solvers x 8 puzzles,
    112 side-by-side bars stopped being legible. Cell color encodes
    log10(nodes), the number itself is annotated in each cell, and a *
    marks a timed-out cell -- a lower bound, not a completion.
    """
    solvers = _present_solver_order(rows)
    puzzle_ids = _sorted_puzzle_ids(rows)
    by_key = {(r["solver"], r["puzzle_id"]): r for r in rows}

    data = [[by_key[(s, pid)]["nodes_explored"] for pid in puzzle_ids] for s in solvers]
    timed_out = [[by_key[(s, pid)]["timed_out"] for pid in puzzle_ids] for s in solvers]
    log_data = [[math.log10(v + 1) for v in row] for row in data]
    vmax = max(v for row in log_data for v in row) or 1.0

    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(log_data, aspect="auto", cmap="YlOrRd", vmin=0, vmax=vmax)

    ax.set_xticks(range(len(puzzle_ids)))
    ax.set_xticklabels(puzzle_ids, rotation=30, ha="right")
    ax.set_yticks(range(len(solvers)))
    ax.set_yticklabels(solvers)

    for i, row in enumerate(data):
        for j, nodes in enumerate(row):
            label = f"{nodes:,}" + ("*" if timed_out[i][j] else "")
            text_color = "white" if log_data[i][j] > vmax * 0.6 else "black"
            ax.text(j, i, label, ha="center", va="center", fontsize=7, color=text_color)

    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("log10(nodes explored + 1)")
    ax.set_title(
        "Nodes explored: solver x puzzle\n(* = timed out -- a lower bound, not a completion)"
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_effort_distribution(rows: list[dict], out_path: Path) -> None:
    """One box per solver, across all 8 puzzles. A solver with any
    timed-out puzzle has that puzzle excluded from its box (mixing a
    real completion with a timed-out lower bound in the same box would
    misrepresent both) -- the label says how many puzzles are shown.
    """
    solvers = _present_solver_order(rows)
    colors = _solver_colors(solvers)

    fig, ax = plt.subplots(figsize=(14, 6))
    data, labels, box_colors = [], [], []
    for solver in solvers:
        solver_rows = [r for r in rows if r["solver"] == solver]
        completed = [r["nodes_explored"] for r in solver_rows if not r["timed_out"]]
        n_total = len(solver_rows)
        n_timed_out = n_total - len(completed)
        if completed:
            data.append(completed)
            if n_timed_out:
                suffix = f"\n({len(completed)}/{n_total}, {n_timed_out} timed out)"
            else:
                suffix = ""
        else:
            data.append([r["nodes_explored"] for r in solver_rows])  # all timed out: show anyway
            suffix = f"\n(all {n_total} timed out)"
        labels.append(solver + suffix)
        box_colors.append(colors[solver])

    bp = ax.boxplot(data, tick_labels=labels, patch_artist=True)
    for patch, color in zip(bp["boxes"], box_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.8)

    ax.tick_params(axis="x", labelrotation=45)
    for label in ax.get_xticklabels():
        label.set_ha("right")
    ax.set_yscale("log")
    ax.set_ylabel("nodes explored (log scale)")
    ax.set_title(
        "Distribution of search effort by solver\n"
        "(boxes use only completed puzzles for that solver; see label for how many)"
    )
    ax.grid(True, which="both", axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main(results_path: Path = DEFAULT_RESULTS_CSV) -> None:
    rows = load_results(results_path)
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    plot_nodes_vs_difficulty(rows, PLOTS_DIR / "nodes_vs_difficulty.png")
    plot_runtime_vs_difficulty(rows, PLOTS_DIR / "runtime_vs_difficulty.png")
    plot_solver_comparison(rows, PLOTS_DIR / "solver_comparison.png")
    plot_effort_distribution(rows, PLOTS_DIR / "effort_distribution.png")

    print(f"Wrote 4 plots to {PLOTS_DIR}")


if __name__ == "__main__":
    main()
