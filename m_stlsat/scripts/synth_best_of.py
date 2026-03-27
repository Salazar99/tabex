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

def replace_invalid_times(data, timeout):
    """
    Replaces -1 times and invalid results with the timeout value.
    """
    for _, df in data:
        df.loc[(df["Time (s)"] == -1) | (~ df["Result"].map(valid_result)), "Time (s)"] = timeout
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('tools',
                        help='Comma-separated tool names.')
    parser.add_argument('tool_csvs',
                        help='List of comma-separated CSV files containing tool data.')
    parser.add_argument('output_csv',
                        help='Output CSV file.')
    parser.add_argument('--timeout',
                        type=int,
                        default=120,
                        help='Timeout value to replace -1 times and invalid results.')
    args = parser.parse_args()

    tools = args.tools.strip().split(",")
    tool_csvs = args.tool_csvs.strip().split(",")
    if len(tools) != len(tool_csvs):
        sys.exit("Error: different numbers of tools and CSV file were entered.")

    data = read_csv_files(tools, tool_csvs)
    data = replace_invalid_times(data, args.timeout)

    t1, joined = data[0]
    col_renamer = lambda t: lambda c: c + '_' + t if c != 'Name' else c
    joined = joined.rename(columns=col_renamer(t1))
    for t, df in data[1:]:
        df = df.rename(columns=col_renamer(t))
        joined = pd.merge(joined, df, on='Name', suffixes=('', '_' + t), validate='one_to_one')

    time_index = [f'Time (s)_{t}' for t, _ in data]
    def make_best_of(row):
        best_tool = time_index[row[time_index].argmin()][len('Time (s)_'):]
        return {'Time (s)': row[f'Time (s)_{best_tool}'], 'Result': row[f'Result_{best_tool}']}

    best_of = joined.apply(make_best_of, axis=1, result_type='expand')
    joined = pd.concat([joined, best_of], axis=1)

    print(joined)

    joined[["Name", "Time (s)", "Result"]].to_csv(args.output_csv, index=False)
