#!/usr/bin/env python3
"""
run_sweep.py — Parameter sweep over network load ρ = λ/μ.

For each load level, each algorithm, and each random seed, runs swp_sim
and accumulates results into a single CSV.  Designed to produce the data
for the paper figures.

Usage
-----
  python3 run_sweep.py [--topo <name>] [--out results.csv]

The output CSV has one row per (topology, algorithm, load, seed) tuple
with the same columns as swp_sim.py summary output, plus a 'seed' column.
"""

import argparse
import csv
import subprocess
import sys
from pathlib import Path
import pandas as pd
from itertools import product
from tqdm import tqdm

# Default sweep parameters
LOADS = [0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0]   # ρ = λ/μ
MU = 0.1                                             # fixed leave rate
SEEDS = list(range(5))                               # 5 replications
ALGOS = "swp,pruned,sp"

SIM = Path(__file__).parent / "swp_sim.py"


def parse_args():
    p = argparse.ArgumentParser(
        description="Sweep ρ = λ/μ for all algorithms",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--topo", default="ba:30",
                   help="Topology (passed through to swp_sim.py)")
    p.add_argument("--min-states", type=int, default=1000)
    p.add_argument("--max-states", type=int, default=128000)
    p.add_argument("--capacity", choices=["random", "centrality", "roles"],
                help="Capacity assignment technique", default="random")
    p.add_argument("--condition", choices=["default", "cdn", "outdated"],
                help="Extra conditions on the network", default="default")
    p.add_argument("--loads", default=",".join(str(x) for x in LOADS),
                   help="Comma-separated load values ρ")
    p.add_argument("--seeds", type=int, default=len(SEEDS),
                   help="Number of random seeds per (algo, load) pair")
    p.add_argument("--out", default="results.csv",
                   help="Output CSV file")
    p.add_argument("--summarise", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    loads = [float(x) for x in args.loads.split(",")]
    seeds = list(range(args.seeds))

    if args.summarise:
        fieldnames = [
            "seed", "algorithm", "load",
            "total_joins", "accepted", "acceptance_rate",
            "stale_rejections", "stale_rejection_rate",
            "first_rejection", "mean_path_len", "mean_bottleneck", "flooded"
        ]
    else:
        fieldnames = [
            "seed", "algorithm", "load", "total_joins", "seq",
            "src", "dst", "time",
            "status", "path_len", "bottleneck", "flooded"
        ]

    with open(args.out, "w", newline="") as fout:
        writer = csv.DictWriter(fout, fieldnames=fieldnames)
        writer.writeheader()
        
        parameters = list(product(loads, seeds))

        for rho, seed in tqdm(parameters):
            lam = rho * MU
            # 5 rounds of join/leave
            total_duration = 5 / MU
            cmd = [
                sys.executable, str(SIM),
                "--topo", args.topo,
                "--algos", ALGOS,
                "--total-duration", str(total_duration),
                "--lam", str(lam),
                "--mu", str(MU),
                "--min-states", str(args.min_states),
                "--max-states", str(args.max_states),
                "--capacity", str(args.capacity),
                "--condition", str(args.condition),
                "--seed", str(seed),
            ]
                
            if args.summarise:
                cmd.append("--summarise") 
                
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"  ERROR: {result.stderr}", file=sys.stderr)
                continue

            import io
            import csv as _csv
            reader = _csv.DictReader(io.StringIO(result.stdout))
            for row in reader:
                row["seed"] = seed
                writer.writerow({k: row.get(k, "") for k in fieldnames})
            fout.flush()

    print(f"Results written to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
