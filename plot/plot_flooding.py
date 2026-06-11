import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import argparse
from style import latexify, grid

ALGO_STYLE = {
    "swp":    dict(label="SWP", marker="o", ls="-",  zorder=3),
    "pruned": dict(label="Pruned SP", marker="s", ls="--", zorder=2),
    "sp":     dict(label="SP", marker="^", ls=":",  zorder=1),
}
ALGO_ORDER = ["sp", "pruned", "swp"]

p = argparse.ArgumentParser(
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
)
p.add_argument("--input", required=True)
p.add_argument("--output")

args = p.parse_args()

data = pd.read_csv(args.input)

if args.output:
    latexify(columns=1, fig_height=1)

fig, ax = plt.subplots()

sns.lineplot(
    data, x="load", y="flooded", hue="algorithm",
    err_style="bars", err_kws={"capsize": 3},
    hue_order=ALGO_ORDER,
    style="algorithm", markers=True, dashes=False,
    ax=ax
)

ax.set_xlabel(r"Network load $\rho = \lambda/\mu$")
ax.set_xscale("log")
ax.set_ylabel("\# of capacity\nadvertisement")
grid(ax, "both")

handles, _ = ax.get_legend_handles_labels()
ax.get_legend().remove()
fig.legend(
    handles, [ALGO_STYLE[a]["label"] for a in ALGO_ORDER],
    loc="lower center", ncol=3, fontsize=9,
    bbox_to_anchor=(0.5, 0.95),
)

if args.output:
    plt.savefig(args.output, bbox_inches="tight")
else:
    plt.show()