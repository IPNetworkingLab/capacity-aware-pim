#!/usr/bin/env python3
"""
plot_paper.py — Generate publication-quality figures for anrw26.tex.

Outputs (in --outdir):
  fig_sim_acceptance.pdf  — 3-panel acceptance rate, one panel per topology
  fig_sim_pathlen.pdf     — single-panel mean path length for Cogentco

Usage
-----
  python3 plot_paper.py [--outdir ../]
"""

import argparse
import pandas as pd
import seaborn as sns
import numpy as np
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from style import latexify

# --------------------------------------------------------------------------
# Style
# --------------------------------------------------------------------------

ALGO_STYLE = {
    "swp":    dict(label="SWP", marker="o", ls="-",  zorder=3),
    "pruned": dict(label="Pruned SP", marker="s", ls="--", zorder=2),
    "sp":     dict(label="SP", marker="^", ls=":",  zorder=1),
}
ALGO_ORDER = ["sp", "pruned", "swp"]

TOPOS = [
    ("results/cogentco.csv",  "Cogentco (197 nodes)"),
    ("results/tatanld.csv",   "Tata NLD (145 nodes)"),
    ("results/geant2012.csv", "GÉANT 2012 (40 nodes)"),
    ("results/fat-tree-12.csv", "Fat-tree (180 nodes)")
]

TOPOS_FLOODING = [
    ("results/cogentco.csv",  "Cogentco (197 nodes)"),
    ("results/fat-tree-12.csv", "Fat-tree (180 nodes)")
]

# --------------------------------------------------------------------------
# Data helpers
# --------------------------------------------------------------------------

def load_results(path: str):
    df = pd.read_csv(path)
    df["topo"] = path
    return df

# --------------------------------------------------------------------------
# Figure 1 — acceptance rate, three topologies side by side
# --------------------------------------------------------------------------

def fig_acceptance(outfile: Path):
    latexify(columns=2, fig_height=1.7)
    fig, axes = plt.subplots(1, 4, sharey=True)

    for ax, (csv_path, title) in zip(axes, TOPOS):
        data = load_results(csv_path)
        # Lower values are not interesting for the plot
        data = data[data["load"] >= 100]

        sns.lineplot(data,
            x="load", y="acceptance_rate", hue="algorithm",
            err_style="bars", hue_order=ALGO_ORDER,
            style="algorithm", markers=True, dashes=False,
            ax=ax
        )

        data = data.groupby(["algorithm", "load"])["acceptance_rate"].mean().reset_index()

        sp  = data[data["algorithm"] == "sp"].reset_index()
        swp = data[data["algorithm"] == "swp"].reset_index()
        swp["diff"] = swp["acceptance_rate"] - sp["acceptance_rate"]

        start = swp[swp["diff"] > 0.1]["load"].min()
        end   = swp[(swp["diff"] < 0.05) & (swp["acceptance_rate"] < 1.0)]["load"].min()

        if np.isnan(end):
            end = swp["load"].max()

        ax.vlines([start, end], ymin=-0.1, ymax=1.1, color='grey', linestyle="dotted")

        ax.set_xscale("log")
        ax.set_ylim(-0.1, 1.1)
        ax.set_xlabel(r"Network load $\rho = \lambda/\mu$")
        ax.set_title(title, fontsize=9)
        ax.grid(True, which="both", alpha=0.3)
        ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.1f"))

    axes[0].set_ylabel("Join\nacceptance rate")
    for ax in axes:
        ax.get_legend().remove()

    handles, _ = axes[0].get_legend_handles_labels()
    fig.legend(
        handles, [ALGO_STYLE[a]["label"] for a in ALGO_ORDER],
        loc="lower center", ncol=3, fontsize=9,
        bbox_to_anchor=(0.5, -0.02),
    )
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    fig.savefig(outfile, bbox_inches="tight")
    print(f"Saved {outfile}")
    plt.close(fig)

# --------------------------------------------------------------------------
# Figure 2 — Flooding rate
# --------------------------------------------------------------------------
def fig_flooding(outfile: Path):
    latexify(fig_width=7.00560398505604*0.55, fig_height=1.7)
    fig, axes = plt.subplots(1, 2, sharey=True)

    for ax, (csv_path, title) in zip(axes, TOPOS_FLOODING):
        data = load_results(csv_path)
        # Lower values are not interesting for the plot
        data = data[data["load"] >= 100]

        sns.lineplot(data,
            x="load", y="flooded", hue="algorithm",
            err_style="bars", hue_order=ALGO_ORDER,
            style="algorithm", markers=True, dashes=False,
            ax=ax
        )

        ax.set_xscale("log")
        ax.set_xlabel(r"Network load $\rho = \lambda/\mu$")
        ax.set_title(title, fontsize=9)
        ax.grid(True, which="both", alpha=0.3)
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, pos: F"{v / 1e3:.0f}K" if v > 1000 else int(v)))

    axes[0].set_ylabel("\# of capacity\nadvertisement")
    for ax in axes:
        ax.get_legend().remove()

    handles, _ = axes[0].get_legend_handles_labels()
    fig.legend(
        handles, [ALGO_STYLE[a]["label"] for a in ALGO_ORDER],
        loc="lower center", ncol=3, fontsize=9,
        bbox_to_anchor=(0.5, -0.02),
    )
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    fig.savefig(outfile, bbox_inches="tight")
    print(f"Saved {outfile}")
    plt.close(fig)


# --------------------------------------------------------------------------
# Figure 3 — mean path length, Cogentco only
# --------------------------------------------------------------------------
def fig_pathlen(outfile: Path):
    data = load_results(TOPOS[0][0])  # Cogentco

    latexify(fig_width=7.00560398505604*0.43, fig_height=1.7)
    fig, ax = plt.subplots()

    sns.lineplot(data,
        x="load", y="mean_path_len", hue="algorithm",
        err_style="bars", hue_order=ALGO_ORDER,
        style="algorithm", markers=True, dashes=False,
        ax=ax
    )
    ax.get_legend().remove()

    ax.set_title(TOPOS[0][1], fontsize=9)

    ax.set_xscale("log")
    ax.set_xlabel(r"Network load $\rho = \lambda/\mu$")
    ax.set_ylabel("Mean path\nlength (hops)")
    ax.grid(True, which="both", alpha=0.3)

    handles, _ = ax.get_legend_handles_labels()
    fig.legend(
        handles, [ALGO_STYLE[a]["label"] for a in ALGO_ORDER],
        loc="lower center", ncol=3, fontsize=9,
        bbox_to_anchor=(0.5, -0.02),
    )
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    fig.savefig(outfile, bbox_inches="tight")
    print(f"Saved {outfile}")
    plt.close(fig)

# --------------------------------------------------------------------------
# Figure 4 — acceptance rate per length, cogentco only
# --------------------------------------------------------------------------
def fig_acceptance_pathlen(outfile: Path):
    data = load_results("results/cogentco-trace.csv")  # Cogentco
    data = data[
        (data["algorithm"] == "sp") &
        (data["load"] == data["load"].max())
    ]

    data["accepted"] = data["status"] == "accepted"
    data = data.groupby(by=["path_len", "seed"]).agg(acceptance_rate=("accepted", "mean"), count=("accepted", "count")).reset_index()

    # Take only path lengths with enough samples
    data = data[data["count"] > 10]

    latexify(columns=1, fig_height=1.1)
    fig, ax = plt.subplots()

    sns.lineplot(data,
        x="path_len", y="acceptance_rate",
        markers=True, dashes=False,
        ax=ax
    )

    ax.set_xlabel(r"Path length (hops)")
    ax.set_ylabel("Join\nacceptance rate")
    ax.grid(True, which="both", alpha=0.3)

    # fig.tight_layout(rect=[0, 0.08, 1, 1])
    fig.savefig(outfile, bbox_inches="tight")
    print(f"Saved {outfile}")
    plt.close(fig)

# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    p.add_argument("--outdir", default="figures")
    return p.parse_args()


def main():
    args = parse_args()
    outdir = Path(args.outdir)
    fig_acceptance(outdir / "sim_acceptance.pdf")
    fig_flooding(outdir / "sim_flooding.pdf")
    fig_pathlen(outdir / "sim_pathlen.pdf")
    fig_acceptance_pathlen(outdir / "sim_acceptance_pathlen.pdf")


if __name__ == "__main__":
    main()
