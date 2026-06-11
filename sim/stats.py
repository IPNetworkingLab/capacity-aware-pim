import pandas as pd

RHO = 1000
FILES = [
    "results/random-capacity/cogentco.csv",
    "results/random-capacity/tatanld.csv",
    "results/random-capacity/geant2012.csv",
    "results/fat-tree-12.csv"
]

for file in FILES:
    df = pd.read_csv(file)
    df = df[df["load"] == RHO]
    
    print("==========================")
    print(F"File = {file}")
    print("==========================")
    
    for algorithm in df["algorithm"].unique():
        print("-------------------------")
        filtered = df[df["algorithm"] == algorithm]
        
        acc = filtered['acceptance_rate']
        paths = filtered['mean_path_len']
        
        print(F"Algorithm {algorithm}")
        print(F"Acceptance rate: {acc.mean():.3f} +- {acc.std():.3f}")
        print(F"Path length: {paths.mean():.3f} +- {paths.std():.3f}")
        print("-------------------------")