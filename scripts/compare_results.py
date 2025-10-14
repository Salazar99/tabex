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
    data = {}
    for tool, csv_file in zip(tools, csv_files):
        if not os.path.exists(csv_file):
            print(f"Warning: {csv_file} does not exist. Skipping {tool}.")
            continue
        data[tool] = pd.read_csv(csv_file)
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
    if len(tools) != 2:
        sys.exit("Error: exactly two tools must be compared.")
    if len(tools) != len(tool_csvs):
        sys.exit("Error: different numbers of tools and CSV file were entered.")

    data = read_csv_files(tools, tool_csvs)

    (t1, d1), (t2, d2) = data.items()

    joined = pd.merge(d1, d2, on='Name', suffixes=('_' + t1, '_' + t2), validate='one_to_one')

    diff = (joined[f'Result_{t1}'] != 'TO') & (joined[f'Result_{t2}'] != 'TO') & (joined[f'Result_{t1}'] != joined[f'Result_{t2}'])
    print(joined[diff])

    diff_sat_unsat = ((joined[f'Result_{t1}'] == 'sat') & (joined[f'Result_{t2}'] == 'unsat')) | ((joined[f'Result_{t1}'] == 'unsat') & (joined[f'Result_{t2}'] == 'sat'))
    print(joined[diff_sat_unsat])

    if args.csv_output:
        joined[diff_sat_unsat].to_csv(args.csv_output, index=False)
