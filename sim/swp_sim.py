#!/usr/bin/env python3
"""
swp_sim.py — Multicast SWP path-selection simulator.

Tests the Shortest Widest Path (SWP) heuristic against two baselines:
  sp      — plain shortest path (ignores capacity, fails silently)
  pruned  — prune a(v)=0 nodes, then shortest path
  swp     — Shortest Widest Path (proposed algorithm)

Topology sources
----------------
  --topo ba:<n>         Barabási–Albert random graph, n nodes (default)
  --topo <Name>         ISP Zoo topology name (e.g. Abilene, Geant2009)
  --topo <file.graphml> Local GraphML file
  --topo <URL>          Any URL returning a GraphML file

ISP Zoo base: http://www.topology-zoo.org/files/
GraphML files: https://github.com/mroughan/InternetTopologyZoo

Reference for ISP Zoo topologies:
  S. Knight, H. X. Nguyen, N. Falkner, R. Bowden, M. Roughan,
  "The Internet Topology Zoo", IEEE JSAC, Vol. 29, No. 9, Oct. 2011.

Threshold-triggered advertisement model (with hysteresis)
----------------------------------------------------------
Routers only re-advertise their available forwarding entries when
utilisation crosses a band boundary.  Each band has separate up and
down thresholds to prevent oscillation:

  HYSTERESIS_BANDS = [
      (down, up), ...
  ]

A node moves UP into the next band when utilisation >= up threshold.
A node moves DOWN out of the current band when utilisation < down threshold.
Re-advertisement fires on any band change.

Between band changes, neighbours see the last advertised value
(advertised_avail).  Path-selection algorithms use advertised_avail;
actual state installation uses the true value.  A "stale rejection" is
counted when the algorithm selects a path it believes is feasible but
actual installation fails because a node's true capacity is exhausted.
"""

import argparse
import csv
import heapq
import math
import sys
import urllib.request
from pathlib import Path
from dataclasses import dataclass

import networkx as nx
import numpy as np


# ---------------------------------------------------------------------------
# Threshold-triggered advertisement model (hysteresis)
# ---------------------------------------------------------------------------

# Each entry is (down_threshold, up_threshold) as a fraction of max_states.
# A node moves into the next band when utilisation >= up threshold.
# A node drops to the previous band when utilisation < down threshold.
# The gap (down < up) prevents re-advertisement oscillation.
HYSTERESIS_BANDS = [
    (0.22, 0.25),  # band 0
    (0.45, 0.50),  # band 1
    (0.70, 0.75),  # band 2
    (0.76, 0.80),  # band 3
    (0.81, 0.85),  # band 4
    (0.86, 0.90),  # band 5
    (0.91, 0.92),  # band 6
    (0.93, 0.94),  # band 7
    (0.94, 0.95),  # band 8
    (0.95, 0.96),  # band 9
    (0.96, 0.97),  # band 10
    (0.97, 0.98),  # band 11
    (0.98, 0.99),  # band 12
    (0.99, 1.00),  # band 13
]

# Sentinel advertised when a node has not yet crossed any threshold.
# Treated as "ample capacity" — SWP sees all such nodes as equal and
# falls back to plain shortest-path behaviour until a real constraint
# is reported (i.e. until utilisation crosses 25 %).
ADV_AMPLE = 10 ** 9

@dataclass
class Lsa:
    originator: int
    seq: int
    capacity: int
    
class Lsdb:
    def __init__(self, graph: nx.Graph, node: int):
        self.seq = 1
        self.node = node
        self.lsas = { v: Lsa(v, 0, ADV_AMPLE) for v in graph.nodes() }
        
    def capacity(self, node: int):
        return self.lsas[node].capacity
    
    def generate_lsa(self, capacity: int) -> Lsa:
        lsa = Lsa(self.node, self.seq, capacity)
        self.seq += 1
        return lsa
    
class MulticastFIB:
    def __init__(self, size: int):
        self.entries = {}
        self.size = size
        self.current_band = -1
        self.advertised = ADV_AMPLE
        
    def contains(self, channel: tuple[int, int]) -> bool:
        return channel in self.entries
    
    def utilisation(self) -> float:
        return len(self.entries) / self.size
    
    def available(self) -> int:
        return max(0, self.size - len(self.entries))
    
    def should_advertise(self) -> bool:
        new_band = self.__get_new_band()
        if new_band != self.current_band:
            self.current_band = new_band
            return True
            
    def __get_new_band(self):
        new_band = -1
        util = self.utilisation()
        for i, (down, up) in enumerate(HYSTERESIS_BANDS):
            if i > self.current_band:
                if util >= up:
                    new_band = i
            else:
                if util >= down:
                    new_band = i
        return new_band
    
    def can_install(self, channel: tuple[int, int]) -> bool:
        return self.contains(channel) or self.available() > 0
        
    def install(self, channel: tuple[int, int], iif: int, oif: int, node: int):
        if not channel in self.entries:
            self.entries[channel] = (iif, set())
        (_, oifs) = self.entries[channel]
        oifs.add(oif)
        # print(F"Node {node} for channel ({channel[0]},{channel[1]}) add {oif}, available = {self.available()}")
        
    def remove(self, channel: tuple[int, int], oif: int, node: int):
        # print(F"Node {node} for channel ({channel[0]},{channel[1]}) remove {oif}, available = {self.available()}")
        (iif, oifs) = self.entries[channel]
        oifs.remove(oif)
        if len(oifs) == 0:
            del self.entries[channel]
            return iif
        return None

# ---------------------------------------------------------------------------
# Topology loading
# ---------------------------------------------------------------------------

ISP_ZOO_BASE = "http://www.topology-zoo.org/files/"

def generate_fat_tree(k: int) -> nx.DiGraph:
    graph = nx.DiGraph()
    
    for core in range((k//2)*(k//2)):
        graph.add_node(core)
    
    aggregate_off = (k//2)*(k//2)
    edge_off = aggregate_off + (k // 2) * k
        
    for pod in range(k):
        for aggregate in range(k // 2):
            agg_true = aggregate_off + pod * (k // 2) + aggregate
            graph.add_node(agg_true)
            
            # connect to core
            for i in range(k // 2):
                core = aggregate * (k // 2) + i
                graph.add_edge(agg_true, core, label=1000)
                graph.add_edge(core, agg_true, label=2000)
            
        for edge in range(k // 2):
            edge_true = edge_off + pod * (k // 2) + edge
            graph.add_node(edge_true)
            
            # connect to aggregate
            for aggregate in range(k // 2):
                agg_true = aggregate_off + pod * (k // 2) + aggregate
                graph.add_edge(edge_true, agg_true, label=1000)
                graph.add_edge(agg_true, edge_true, label=2000)
                
    return graph


def load_topology(source: str, rng: np.random.Generator) -> nx.Graph:
    """Return an undirected, integer-labelled, connected graph."""
    if source.startswith("ba:"):
        n = int(source.split(":")[1])
        # m=2 gives a sparse scale-free graph similar to ISP topologies
        G = nx.barabasi_albert_graph(n, m=2, seed=int(rng.integers(1 << 31)))
        for u, v in G.edges():
            G[u][v]["cost"] = 1
        return G
    
    if source.startswith("ft:"):
        k = int(source.split(":")[1])
        G = generate_fat_tree(k)
        for u, v in G.edges():
            G[u][v]["cost"] = 1
        return G.to_undirected()

    # Load GraphML from file, URL, or ISP Zoo name
    if source.endswith(".graphml") and Path(source).exists():
        raw = nx.read_graphml(source)
    elif source.endswith(".ntf") and Path(source).exists():
        raw = nx.read_edgelist(source, data=[("weight", int), ("delay", float)])
    elif source.startswith("http://") or source.startswith("https://"):
        data = urllib.request.urlopen(source, timeout=15).read()
        raw = nx.parse_graphml(data.decode())
    else:
        url = ISP_ZOO_BASE + source + ".graphml"
        try:
            data = urllib.request.urlopen(url, timeout=15).read()
            raw = nx.parse_graphml(data.decode())
        except Exception as exc:
            raise SystemExit(f"Cannot load ISP Zoo topology '{source}': {exc}")

    G = raw.to_undirected()
    G.remove_edges_from(nx.selfloop_edges(G))

    # Keep only internal routers when the attribute is present
    internal = [v for v, d in G.nodes(data=True) if d.get("Internal", 1) == 1]
    if len(internal) >= 3:
        G = G.subgraph(internal).copy()

    # Largest connected component — copy so the graph is mutable
    G = nx.Graph(G.subgraph(max(nx.connected_components(G), key=len)))
    G = nx.convert_node_labels_to_integers(G, label_attribute="name")

    # Derive IGP cost from LinkSpeed if present, else unit cost
    for u, v, d in G.edges(data=True):
        speed = d.get("LinkSpeed", None)
        try:
            # ISP Zoo stores speed in bps; invert so faster = lower cost
            G[u][v]["cost"] = max(1, int(1e9 / float(speed))) if speed else 1
        except (ValueError, ZeroDivisionError):
            G[u][v]["cost"] = 1

    return G


def assign_states(
    G: nx.Graph,
    min_states: int,
    max_states: int,
    rng: np.random.Generator,
    method: str,
    condition: str
) -> None:
    """
    Assign max_states to each node from a log-uniform distribution over
    [min_states, max_states], reflecting the 1 K–128 K range in Table 1
    of the paper.  All nodes start with used_states = 0.

    advertised_avail is initialised to max_states (routers advertise
    full capacity at startup; first advertisement is at threshold 0.0).
    """
        
    cores = []
    if method == "random":
        log_lo = math.log10(min_states)
        log_hi = math.log10(max_states)
        
        for v in G.nodes():
            G.nodes[v]["max_states"] = int(10 ** rng.uniform(log_lo, log_hi))
        
        return
    elif method == "centrality":
        centralities = nx.load_centrality(G)
        max_centrality = max(centralities.values())
        centralities = {k: v/max_centrality for (k, v) in centralities.items() }
        
        for v in G.nodes():
            bound = (max_states - min_states) * centralities[v]
            G.nodes[v]["max_states"] = min_states + rng.uniform(bound / 2, bound)
            
        cores = sorted(centralities.items(), key=lambda x: -x[1]) 
        # Top 10% routers are core routers
        cores = cores[:len(cores)//10] 
    elif method == "roles":
        capacity_factor = {
            "core": 1.0,
            "access": 0.7,
            "edge": 0.4
        }
        
        for v, data in G.nodes(data=True):
            prefix = data["name"].split(".")[0]
            if prefix.startswith("cr"):
                data["role"] = "core"
            elif prefix.startswith("ar"):
                data["role"] = "access"
            else:
                data["role"] = "edge"
                
        for v, data in G.nodes(data=True):
            bound = (max_states - min_states) * capacity_factor[data["role"]]
            G.nodes[v]["max_states"] = min_states + rng.uniform(bound / 2, bound)
            
        cores = [(v, d) for v, d in G.nodes(data=True) if d["role"] == "core"]
    else:
        exit(1)
     
    if condition == "outdated":   
        # 10% of core routers are outdated
        # i.e. same capacity as the edge
        outdated = rng.choice(cores, size=len(cores)//10)
        
        for (v, _) in outdated:
            G.nodes[v]["max_states"] = min_states

# ---------------------------------------------------------------------------
# Path-selection algorithms
# ---------------------------------------------------------------------------

def algo_swp(G: nx.Graph, source: int, dest: int, lsdb: Lsdb):
    """
    Shortest Widest Path from source to dest, using advertised capacity.

    Preference relation (Section 5.2 of the paper):
      p1 ≻ p2  iff  A(p1) > A(p2),
                 or (A(p1) == A(p2) and C(p1) < C(p2)),
                 or (A(p1) == A(p2) and C(p1) == C(p2) and first_hop(p1) < first_hop(p2))

    where A(p) = min_{v in p} a_adv(v)  and  C(p) = sum of edge costs.

    Returns list of node IDs on the chosen path (source…dest), or None if
    no feasible path exists (all paths pass through a_adv(v)=0 nodes).
    """
    INF = float("inf")
    # best[v] = (bottleneck, cost) of the best known path to v
    best = {}
    best[source] = (ADV_AMPLE, 0)
    prev = {source: None}

    # heap key: (-bottleneck, cost, node_id_tiebreak, node)
    heap = [(-ADV_AMPLE, 0, source, source)]

    while heap:
        neg_btn, cost, _, node = heapq.heappop(heap)
        bottleneck = -neg_btn

        # Stale check
        b_best, c_best = best.get(node, (-1, INF))
        if bottleneck < b_best or (bottleneck == b_best and cost > c_best):
            continue

        if node == dest:
            path = []
            cur = dest
            while cur is not None:
                path.append(cur)
                cur = prev[cur]
            return list(reversed(path))

        for nbr in G.neighbors(node):
            nbr_adv = lsdb.capacity(nbr)
            new_btn = min(bottleneck, nbr_adv)
            new_cost = cost + G[node][nbr].get("cost", 1)

            b_old, c_old = best.get(nbr, (-1, INF))
            # SWP: prefer higher bottleneck, then lower cost, then lower node-ID
            if new_btn > b_old or (new_btn == b_old and new_cost < c_old):
                best[nbr] = (new_btn, new_cost)
                prev[nbr] = node
                # node-ID as final tiebreaker for determinism across all routers
                heapq.heappush(heap, (-new_btn, new_cost, nbr, nbr))

    # No path found, try default optimistically if entries already present
    return algo_sp(G, source, dest, lsdb) 


def algo_sp(G: nx.Graph, source: int, dest: int, _lsdb: Lsdb):
    """
    Plain shortest path (ignores capacity).  A join is silently rejected
    only if a router on the chosen path has no advertised room.
    """
    try:
        return nx.shortest_path(G, source, dest, weight="cost")
    except nx.NetworkXNoPath:
        return None

def algo_pruned(G: nx.Graph, source: int, dest: int, lsdb: Lsdb):
    """
    Prune nodes with a_adv(v)=0 then shortest path.
    Better than plain SP but treats a_adv(v)=1 and a_adv(v)=1000 identically.
    """
    view = nx.subgraph_view(G, filter_node=lambda v: lsdb.capacity(v) > 0)
    try:
        path = nx.shortest_path(view, source, dest, weight="cost")
        return path
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        # No path found, try default optimistically if entries already present
        return algo_sp(G, source, dest, lsdb)


ALGORITHMS = {"swp": algo_swp, "pruned": algo_pruned, "sp": algo_sp}


# ---------------------------------------------------------------------------
# Discrete-event simulation
# ---------------------------------------------------------------------------

def channels(G: nx.Graph, limit: int, rng: np.random.Generator) -> list[tuple[int, int]]:
    chans = []
    channel_count = {}
    
    for _ in range(limit):
        source = int(rng.choice(G.nodes(), size=1)[0])
        group = channel_count.get(source, 0)
        channel_count[source] = group + 1
        chans.append((source, group))
    
    return chans

def run(
    G: nx.Graph,
    algorithm: str,
    total_duration: float,
    lam: float,
    mu: float,
    rng: np.random.Generator,
) -> list[dict]:
    """
    Simulate n_joins join attempts with Poisson arrivals (rate lam) and
    exponential lifetimes (mean 1/mu).

    Each join models a new (S,G) multicast channel: source and receiver are
    chosen independently and uniformly at random from all nodes, representing
    the real-world scenario where many different applications each have their
    own multicast source.  This distributes TCAM load across all routers
    rather than saturating a single fixed source node.

    Path selection uses advertised_avail (possibly stale due to threshold-
    triggered advertisements).  Actual state installation uses true avail().
    A "stale rejection" is counted when the algorithm selects a path it
    believes feasible but true capacity is exhausted at one or more nodes.

    Returns one dict per join attempt with keys:
      seq, time, accepted, stale_rejected, path_len, bottleneck
    """
    algo_fn = ALGORITHMS[algorithm]

    # Reset state and advertisement model
    for v in G.nodes():
        G.nodes[v]["used_states"] = 0
        # Until the first band crossing (25 % up), advertise ADV_AMPLE so
        # all unconstrained nodes look identical to path-selection algorithms
        # and SWP falls back to plain shortest-path behaviour.
        G.nodes[v]["advertised_avail"] = ADV_AMPLE
        G.nodes[v]["last_band"] = -1
        
    lsdbs = { v: Lsdb(G, v) for v in G.nodes() }
    mfibs = { v: MulticastFIB(G.nodes[v]["max_states"]) for v in G.nodes() }
    chans = channels(G, limit=int(lam/mu), rng=rng)
    active = set()

    # heap of (time, event_type, path)
    # event_type: 0=join, 1=leave
    ev_heap = []
    t = 0.0
    heapq.heappush(ev_heap, (rng.exponential(1 / lam), rng.random(size=1)[0], 0, []))

    results = []
    joins_scheduled = 1
    joins_done = 0
    total_flooded = 0
    while ev_heap:
        event = heapq.heappop(ev_heap)
        t = event[0]
        kind = event[2]
        
        if t > total_duration:
            break
        
        if kind == 0:
            # join: pick a random receiver dans channel
            joins_done += 1
            channel = tuple(rng.choice(chans, size=1)[0])
            src = int(rng.choice(G.nodes(), size=1)[0])
            while (src, channel) in active:
                src = int(rng.choice(G.nodes(), size=1)[0])
            active.add((src, channel))
            dst = channel[0]

            path = algo_fn(G, src, dst, lsdbs[src])
            
            result = dict(
                seq=joins_done, src=src, dst=dst, time=round(t, 3)
            )

            # Check whether capacity allows installation
            reject = path is None or not all(mfibs[v].can_install(channel) for v in path)
            if reject:
                # Path cannot be installed
                result["status"]     = "reject"
                result["path_len"]   = 0
                result["bottleneck"] = 0
                results.append(result)
            else:
                # print(F"Join ({channel[0]},{channel[1]}), path = {path}")
                # Install state on path
                for i in range(len(path)):
                    oif = path[max(i-1, 0)]
                    iif = path[min(i+1, len(path) - 1)]
                    v = path[i]
                    mfib = mfibs[v]
                    stop_join = mfib.contains(channel)
                    mfib.install(channel, iif, oif, v)
                    # Already entry, stop sending join upstream
                    if stop_join:
                        break
                    # Flooded new message
                    if mfib.should_advertise():
                        total_flooded += 1 
                        heapq.heappush(ev_heap, (t, rng.random(size=1)[0], 2, v, lsdbs[v].generate_lsa(mfib.available())))
                    
                leave_t = t + rng.exponential(1 / mu)
                heapq.heappush(ev_heap, (leave_t, rng.random(size=1)[0], 1, src, path, channel))
                path_len = len(path) - 1
                bottleneck = min(mfibs[v].available() for v in path)
                
                result["status"]     = "accepted"
                result["path_len"]   = path_len
                result["bottleneck"] = bottleneck
                results.append(result)


            heapq.heappush(
                ev_heap, (t + rng.exponential(1 / lam), rng.random(size=1)[0], 0, [])
            )
            joins_scheduled += 1
        elif kind == 1:  # leave
            src, path, channel = event[3:]
            active.remove((src, channel))
            prev = path[0]
            # print(F"Leave ({channel[0]},{channel[1]}), path = {path}")
            oif = path[0]
            curr = path[0]
            while True:
                mfib = mfibs[curr]
                iif = mfib.remove(channel, oif, curr)
                
                # Root or still oifs
                if iif is None or iif == curr:
                    break
                
                oif = curr
                curr = iif
                
                if mfib.should_advertise():
                    total_flooded += 1
                    heapq.heappush(ev_heap, (t, rng.random(size=1)[0], 2, v, lsdbs[v].generate_lsa(mfib.available())))

        elif kind == 2:
            (node, lsa) = event[3:]
            lsdb = lsdbs[node]
    
            prev = lsdb.lsas[lsa.originator]
            
            if prev.seq < lsa.seq:
                # New
                lsdb.lsas[lsa.originator] = lsa
                for peer in G.adj[node]:
                    heapq.heappush(ev_heap, (t + 0.01, rng.random(size=1)[0], 2, peer, lsa))

            
    if algorithm == "sp":
        total_flooded = 0

    return results, total_flooded


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def summarise(results: list[dict], algorithm: str, load: float, total_flooded: int) -> dict:
    total = len(results)
    acc = [r for r in results if r["status"] == "accepted"]
    stale = [r for r in results if r["status"] == "stale"]
    n_acc = len(acc)
    n_stale = len(stale)
    first_rej = next((r["seq"] for r in results if r["status"] != "accepted"), None)
    path_lens = [r["path_len"] for r in acc if r["path_len"] is not None]
    btns = [r["bottleneck"] for r in acc if r["bottleneck"] is not None]
    return {
        "algorithm": algorithm,
        "load": load,
        "total_joins": total,
        "accepted": n_acc,
        "acceptance_rate": round(n_acc / total, 4) if total else 0,
        "stale_rejections": n_stale,
        "stale_rejection_rate": round(n_stale / total, 4) if total else 0,
        "first_rejection": first_rej,
        "mean_path_len": round(float(np.mean(path_lens)), 3) if path_lens else None,
        "mean_bottleneck": round(float(np.mean(btns)), 1) if btns else None,
        "flooded": total_flooded
    }


def add_metadata(results: list[dict], algorithm: str, load: float) -> dict:
    total = len(results)

    for result in results:
        result["algorithm"] = algorithm
        result["load"] = load
        result["total_joins"] = total
        
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description="Multicast SWP simulator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--topo", default="ba:30",
                   help="Topology: ba:<n>, ISP Zoo name, .graphml file, or URL")
    p.add_argument("--algos", default="swp,pruned,sp",
                   help="Comma-separated list of algorithms to run")
    p.add_argument("--total-duration", type=float, default=1.0,
                   help="Total duration for the simulation")
    p.add_argument("--lam", type=float, default=5.0,
                   help="Join arrival rate λ")
    p.add_argument("--mu", type=float, default=0.1,
                   help="Leave rate μ (mean lifetime = 1/μ)")
    p.add_argument("--min-states", type=int, default=1000,
                   help="Minimum router TCAM capacity")
    p.add_argument("--max-states", type=int, default=128000,
                   help="Maximum router TCAM capacity")
    p.add_argument("--capacity", choices=["random", "centrality", "roles"],
                help="Capacity assignment technique", default="random"),
    p.add_argument("--condition", choices=["default", "cdn", "outdated"],
                help="Extra conditions on the network")
    p.add_argument("--summarise", action="store_true")
    p.add_argument("--seed", type=int, default=42,
                   help="Random seed")
    p.add_argument("--out", default=None,
                   help="CSV output file (default: stdout)")
    return p.parse_args()


def main():
    args = parse_args()
    rng = np.random.default_rng(args.seed)

    print(f"Loading topology: {args.topo}", file=sys.stderr)
    G = load_topology(args.topo, rng)
    print(f"  {G.number_of_nodes()} nodes, {G.number_of_edges()} edges",
          file=sys.stderr)

    assign_states(
        G, args.min_states, args.max_states, rng, 
        method=args.capacity, condition=args.condition
    )

    load = args.lam / args.mu
    algos = [a.strip() for a in args.algos.split(",")]

    all_results = []
    
    if args.summarise:
        fieldnames = [
            "algorithm", "load", "total_joins", "accepted",
            "acceptance_rate", "stale_rejections", "stale_rejection_rate",
            "first_rejection", "mean_path_len", "mean_bottleneck", "flooded"
        ]
    else:
        fieldnames = [
            "algorithm", "load", "total_joins", "seq",
            "src", "dst", "time",
            "status", "path_len", "bottleneck"
        ]

    for algo in algos:
        if algo not in ALGORITHMS:
            print(f"Unknown algorithm '{algo}', skipping.", file=sys.stderr)
            continue
        # Re-assign states with the same seed so all algorithms see same topology
        rng_run = np.random.default_rng(args.seed + 1)
        assign_states(
            G, args.min_states, args.max_states, rng_run, 
            method=args.capacity, condition=args.condition
        )

        print(f"  Running {algo} (λ={args.lam}, μ={args.mu}, ρ={load:.1f}) ...",
              file=sys.stderr)
        results, total_flooded = run(G, algo, args.total_duration, args.lam, args.mu,
                      np.random.default_rng(args.seed + 2))
        
        if args.summarise:
            all_results.append(summarise(results, algo, load, total_flooded))
        else:
            results = add_metadata(results, algo, load)
            all_results += results

    writer = csv.DictWriter(
        open(args.out, "w", newline="") if args.out else sys.stdout,
        fieldnames=fieldnames,
    )
    writer.writeheader()
    writer.writerows(all_results)


if __name__ == "__main__":
    main()
