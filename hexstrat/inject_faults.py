"""Make a damaged copy of a run's raw Parquet files, plus a log of every fault injected.

    python -m hexstrat.inject_faults --run-id <run_id> [--seed 42] [--out data/raw_faulty]

Reads data/raw/ (never modified) and writes:
    <out>/moves_<run_id>.parquet        damaged copy
    <out>/fault_log_<run_id>.parquet    one row per fault: fault_type, table, game_id,
                                        move_index, column, original_value, new_value, seed

Fault types: duplicate rows, missing values. One seeded rng drives every random choice,
so a seed reproduces the damage.
"""
import pandas as pd
import numpy as np
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("data/raw_faulty"))
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()      
    rng = np.random.default_rng(args.seed)
    df = pd.read_parquet(Path("data/raw") / f"moves_{args.run_id}.parquet")
    df=df.copy()
    duplicated, log_df_Dup = duplicate(df, rng)
    removed, log_df_removed = remove(duplicated, rng)
    log_df = pd.concat([log_df_Dup, log_df_removed], ignore_index=True)
    log_df['seed'] = args.seed
    args.out.mkdir(parents=True, exist_ok=True)

    removed.to_parquet(args.out / f"moves_{args.run_id}.parquet", index=False)
    log_df.to_parquet(args.out / f"fault_log_{args.run_id}.parquet", index=False)

def duplicate(df, rng):
    errorPicks = rng.choice(len(df), size = int(len(df) * 0.005), replace = False) 
    errors = df.iloc[errorPicks]
    errored = pd.concat([df, errors])
    errorRecords = {'fault_type': [],  'table': [], 'game_id': [], 'move_index': [], 'column': [], 'original_value': [], 'new_value': []}
    for i in range(len(errors)):
        errorRecords['fault_type'].append('duplicate')
        errorRecords['game_id'].append(errors.iloc[i]['game_id'])
        errorRecords['move_index'].append(errors.iloc[i]['move_index'])
        errorRecords['column'].append(None)
        errorRecords['original_value'].append(None)
        errorRecords['new_value'].append(None)
        errorRecords['table'].append('moves')
    erroredDF = pd.DataFrame(errorRecords)
    return errored, erroredDF

def remove(df, rng):
    k = int(len(df) * 0.005)
    picks = rng.choice(len(df), size = k, replace = False)
    cols = ['points', 'player', 'action_type', 'move_index', 'game_id', 'res_wood', 'res_brick', 'res_wheat', 'res_ore', 'res_sheep']
    int_cols = ['points', 'move_index', 'res_wood', 'res_brick', 'res_wheat', 'res_ore', 'res_sheep']
    df[int_cols] = df[int_cols].astype("Int64")
    colsDisturb = rng.choice(cols, size = k, replace = True)
    errorRecords = {'fault_type': [],  'table': [], 'game_id': [], 'move_index': [], 'column': [], 'original_value': [], 'new_value': []}
    for i in range(len(picks)):
        ogVal = df.iloc[picks[i]][colsDisturb[i]]
        ogGame_id = df.iloc[picks[i]]['game_id']
        og_move_index = df.iloc[picks[i]]['move_index']
        df.iat[picks[i], df.columns.get_loc(colsDisturb[i])] = None
        errorRecords['fault_type'].append('missing')
        errorRecords['table'].append('moves')
        errorRecords['game_id'].append(ogGame_id)
        errorRecords['move_index'].append(og_move_index)
        errorRecords['column'].append(colsDisturb[i])
        errorRecords['original_value'].append(str(ogVal))
        errorRecords['new_value'].append(None) 
    erroredDf = pd.DataFrame(errorRecords)
    return df, erroredDf

if __name__ == "__main__":
    main()
