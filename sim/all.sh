loads="10,20,50,100,200,500,1000,2000,5000,10000"
topos="Cogentco TataNld Geant2012"
seeds=10
min_states=50
max_states=5000

for topo in $topos; do
  python3 sim/run_sweep.py \
      --topo data/zoo/$topo.graphml \
      --min-states $min_states --max-states $max_states \
      --loads $loads \
      --summarise \
      --seeds $seeds \
      --out results/${topo,,}.csv
done

python3 sim/run_sweep.py \
    --topo ft:12  \
    --min-states 100 --max-states 100 \
    --loads $loads \
    --summarise \
    --seeds $seeds \
    --out results/fat-tree-12.csv

python3 sim/run_sweep.py \
    --topo data/zoo/Cogentco.graphml \
    --min-states 50 --max-states 5000 \
    --loads 5000 \
    --seeds 5 \
    --out results/cogentco-trace.csv