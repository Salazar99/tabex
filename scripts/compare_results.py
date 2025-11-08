#!/usr/bin/env python3

import os.path, sys, argparse
import pandas as pd

def valid_result(r):
    return r in {'sat', 'unsat'}

def read_csv_files(tools, csv_files):
    """
    Reads the CSV files and returns a dictionary with the tools as keys
    and their corresponding data as values.
    """
    data = []
    for tool, csv_file in zip(tools, csv_files):
        if not os.path.exists(csv_file):
            print(f"Warning: {csv_file} does not exist. Skipping {tool}.")
            continue
        data.append((tool, pd.read_csv(csv_file)))
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('tools',
                        default='_error_',
                        help='Comma-separated tool names.')
    parser.add_argument('tool_csvs',
                        default='_error_',
                        help='List of comma-separated CSV files containing tool data.')
    parser.add_argument('--csv-output',
                        default=None,
                        help='If specified, save differing benchmarks to the given CSV file.')
    args = parser.parse_args()
    
    if args.tools == '_error_':
        sys.exit('Please specify the tool names.')
    if args.tool_csvs == '_error_':
        sys.exit('Please specify paths to the CSV files.')

    tools = args.tools.strip().split(",")
    tool_csvs = args.tool_csvs.strip().split(",")
    if len(tools) != len(tool_csvs):
        sys.exit("Error: different numbers of tools and CSV file were entered.")

    data = read_csv_files(tools, tool_csvs)

    t1, joined = data[0]
    col_renamer = lambda t: lambda c: c + '_' + t if c != 'Name' else c
    joined = joined.rename(columns=col_renamer(t1))
    joined['Collective result'] = joined[f'Result_{t1}']
    joined['Different results'] = False
    for t, df in data[1:]:
        df = df.rename(columns=col_renamer(t))
        joined = pd.merge(joined, df, on='Name', suffixes=('', '_' + t), validate='one_to_one')

        if joined.shape[0] != df.shape[0]:
            print(f"Warning: some benchmarks are missing in one of the CSV files.\n{t} has {df.shape[0]} benchmarks, but only {joined.shape[0]} benchmarks are common.")

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
    print("Benchmarks with differing sat/unsat results:")
    print(joined[diff_sat_unsat])

    if args.csv_output:
        joined[diff_sat_unsat].to_csv(args.csv_output, index=False)
