#!/usr/bin/env python3
"""
plot_capacity.py — Bar chart of multicast forwarding-entry limits across
ISP routers, DC ASICs, and campus/access switches.

Only platforms with a precisely documented hardware limit are included.

Output: fig_capacity.pdf (written to the same directory as this script)
"""

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from matplotlib.patches import Patch
from style import latexify

# ---------------------------------------------------------------------------
# Data — (label, max_states, category)
# category: "ISP router" | "DC/enterprise ASIC" | "Enterprise router"
# ---------------------------------------------------------------------------

ENTRIES = [
    # --- ISP core routers (from table-tcam) --------------------------------
    ("Cisco NCS 5500",        100_000, "ISP router"),
    ("Cisco 8000",            128_000, "ISP router"),
    ("Nokia 7750 (per FP)", 16_000, "ISP router"),
#    ("Cisco NCS 5500\n(eTCAM scaled)",      100_000, "ISP router"),
#    ("Cisco 8000\n(SSM scaled)",            120_000, "ISP router"),
#    ("Cisco ASR 9000\n(RSP-2)",              64_000, "ISP router"),
#    ("Cisco ASR 9000\n(RSP-440/880)",       128_000, "ISP router"),
#    ("Nokia 7750 SR\n(pim-ssm-scaling)",    256_000, "ISP router"),

    # --- DC / enterprise ASICs (from table-dc) -----------------------------
#    ("Broadcom\nTomahawk",                    8_192, "DC/enterprise ASIC"),
#    ("NVIDIA\nSpectrum-2/3/4",               15_000, "DC/enterprise ASIC"),

    # --- Campus / access switches (from table-switch) ----------------------
    ("ALE OS6570M",                           1_000, "Enterprise router"),
    ("ALE OS6575",                            1_000, "Enterprise router"),
 #   ("Cisco Cat. 9200",                       1_024, "Enterprise router"),
 #   ("Cisco Cat. 9300\n(standard)",           8_192, "Enterprise router"),
    ("ALE OS6860",                           12_000, "Enterprise router"),
    ("ALE OS6865",                           12_000, "Enterprise router"),
    ("ALE OS6879",                           12_000, "Enterprise router"),
    ("ALE OS9900",                           16_000, "Enterprise router"),
 #   ("Cisco Cat. 9300\n(UB models)",         16_384, "Enterprise router"),
 #   ("Cisco Cat. 9400/9500",                 16_384, "Enterprise router"),
 #   ("NVIDIA Spectrum-1\n(campus)",          16_300, "Enterprise router"),
    ("ALE OS6900",                           20_000, "Enterprise router"),
 #   ("Cisco Cat. 9600",                      32_000, "Enterprise router"),
    ("ALE OS6860N",                          40_000, "Enterprise router"),
    ("ALE OS6900-X/T48c6",                   40_000, "Enterprise router"),
    ("ALE OS6920",                           40_000, "Enterprise router"),
]

# Sort ascending by max_states
ENTRIES.sort(key=lambda x: x[1])

# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------

CATEGORY_STYLE = {
    "ISP router":           ("#1b7837", "-\\"),
    # "DC/enterprise ASIC":   "#762a83",
    "Enterprise router": ("#d6604d", ".."),
}

labels = [e[0] for e in ENTRIES]
values = [e[1] for e in ENTRIES]
cats   = [e[2] for e in ENTRIES]
colors = [CATEGORY_STYLE[c][0] for c in cats]
hatches = [CATEGORY_STYLE[c][1] for c in cats]

latexify(columns=1, fig_height=4)
fig, ax = plt.subplots()

y    = np.arange(len(labels))
bars = ax.barh(y, values, color=colors, edgecolor="white", linewidth=0.4,
               height=0.7, hatch=hatches)

# Value annotations to the right of each bar
for bar, val in zip(bars, values):
    ax.text(val * 1.08, bar.get_y() + bar.get_height() / 2,
            f"{val / 1e3:.0f}K", va="center", ha="left", fontsize=9)

ax.set_yticks(y)
ax.set_yticklabels(labels, fontsize=9)
ax.set_xscale("log")
ax.set_xlabel("Max multicast forwarding entries\n(log scale)", fontsize=11)
ax.xaxis.set_major_formatter(ticker.FuncFormatter(
    lambda x, _: f"{int(x):,}" if x >= 1 else ""
))
ax.grid(True, which="both", axis="x", alpha=0.3, linestyle="--")
ax.set_axisbelow(True)

# Extra right margin for annotations
xmax = max(values)
ax.set_xlim(right=xmax * 3)

# Legend
handles = [Patch(facecolor=c[0], edgecolor="white", hatch=c[1]) for c in CATEGORY_STYLE.values()]
labels = [cat for cat in CATEGORY_STYLE]
ax.legend(handles=handles, labels=labels, fontsize=9, loc="lower right")

# ax.set_title("Multicast forwarding-entry limits by platform", fontsize=10)

out = "figures/capacity.pdf"
fig.savefig(out, bbox_inches="tight")
print(f"Saved {out}")
