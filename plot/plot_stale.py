import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import argparse
from style import latexify, grid

p = argparse.ArgumentParser(
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
)
p.add_argument("--input", required=True)
p.add_argument("--output")

args = p.parse_args()

data = pd.read_csv(args.input)
data = data[
    (data["algorithm"] == "sp") &
    (data["load"] == data["load"].max())
]

data["accepted"] = data["status"] == "accepted"
data = data.groupby(by=["path_len", "seed"]).agg(prop=("accepted", "mean"), count=("accepted", "count")).reset_index()

# Take only path lengths with enough samples
data = data[data["count"] > 10]

if args.output:
    latexify(columns=1, fig_height=1)

ax = sns.lineplot(data, x="path_len", y="prop")

ax.set_xlabel("Path length (hops)")
ax.set_ylabel("Proportion of\naccepted paths")
grid(ax, "both")

if args.output:
    plt.savefig(args.output, bbox_inches="tight")
else:
    plt.show()