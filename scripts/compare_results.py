#!/usr/bin/env python3

import os.path, sys, argparse
import pandas as pd

def valid_result(r):
    return r in {'sat', 'unsat'}

def read_csv_files(tools, csv_files):
    """
    Reads the CSV files and returns a list of tuples containing tool names and their corresponding dataframes.
    """
    data = []
    for tool, csv_file in zip(tools, csv_files):
        if not os.path.exists(csv_file):
            print(f"WARNING: {csv_file} does not exist. Skipping {tool}.")
            continue
        data.append((tool, pd.read_csv(csv_file)))
    return data


def find_file_in_dirs(filename, dirs):
    """
    Searches for the given filename in the list of directories and returns the full path if found.
    """
    for d in dirs:
        potential_path = os.path.join(d, filename)
        if os.path.exists(potential_path):
            return potential_path
    return None


def compute_diff_for_bench(data, csv_output):
    t1, joined = data[0]
    col_renamer = lambda t: lambda c: c + '_' + t if c != 'Name' else c
    joined = joined.rename(columns=col_renamer(t1))
    joined['Collective result'] = joined[f'Result_{t1}']
    joined['Different results'] = False
    for t, df in data[1:]:
        df = df.rename(columns=col_renamer(t))
        joined = pd.merge(joined, df, on='Name', suffixes=('', '_' + t), validate='one_to_one')

        if joined.shape[0] != df.shape[0]:
            print(f"WARNING: some benchmarks are missing in one of the CSV files.\n{t} has {df.shape[0]} benchmarks, but only {joined.shape[0]} benchmarks are common.")

        def update_collective_result(row):
            cr = row['Collective result']
            tr = row[f'Result_{t}']
            if valid_result(tr):
                if valid_result(cr):
                    if cr != tr:
                        row['Different results'] = True
                else:
                    row['Collective result'] = tr
            return row
        joined = joined.apply(update_collective_result, axis=1)

    diff_sat_unsat = joined['Different results'] == True
    differing_benchmarks = joined[diff_sat_unsat]
    if differing_benchmarks.shape[0] == 0:
        print("✔️ All benchmarks agree on sat/unsat results.")
    else:
        print("❌ Benchmarks with differing sat/unsat results:")
        print(differing_benchmarks)

    if csv_output:
        differing_benchmarks.to_csv(csv_output, index=False)

    return differing_benchmarks


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('tools',
                        default=None,
                        help='Comma-separated tool names.')
    parser.add_argument('--tool-csvs',
                        default=None,
                        help='List of comma-separated CSV files containing tool data.')
    parser.add_argument('--csv-dirs',
                        default=None,
                        help='List of comma-separated directories where to look for CSVs.')
    parser.add_argument('--bench-names',
                        default=None,
                        help='If --csv-dirs is used, a comma-separated list of benchmark names to look for in each directory.')
    parser.add_argument('--csv-output',
                        default=None,
                        help='If specified, save differing benchmarks to the given CSV file.')
    args = parser.parse_args()
    
    if args.tools is None:
        sys.exit('Please specify the tool names.')

    tools = args.tools.strip().split(",")

    if args.tool_csvs:
        tool_csvs = args.tool_csvs.strip().split(",")
        if len(tools) != len(tool_csvs):
            sys.exit("Error: different numbers of tools and CSV file were entered.")

        data = read_csv_files(tools, tool_csvs)
        compute_diff_for_bench(data, args.csv_output)

    elif args.csv_dirs:
        csv_dirs = args.csv_dirs.strip().split(",")
        
        if args.bench_names is None:
            sys.exit("Error: when using --csv-dirs, please also specify --bench-names.")
        bench_names = args.bench_names.strip().split(",")
        for bench in bench_names:
            tool_csvs = []
            for tool in tools:
                filename = f"{tool}_{bench}.csv"
                csv_path = find_file_in_dirs(filename, csv_dirs)
                if csv_path is None:
                    sys.exit(f"Error: could not find {filename} in any of the specified directories.")
                tool_csvs.append(csv_path)
            data = read_csv_files(tools, tool_csvs)
            print(f"\nComparing results for benchmark: {bench}")
            compute_diff_for_bench(data, f"{args.csv_output}_{bench}.csv" if args.csv_output else None)

    else:
        sys.exit("Error: please specify either --tool-csvs or --csv-dirs.")
