#!/usr/bin/env python3

import os, os.path, sys, argparse
import plotly.graph_objects as go
import pandas as pd
import plotly.io as pio
import math
pio.kaleido.scope.mathjax = None

def valid_result(r):
    return r in {'sat', 'unsat'}

def read_csv_files(tools, csv_files, timeout):
    """
    Reads the CSV files and returns a dictionary with the tools as keys
    and their corresponding data as values.
    """
    data = {}
    for tool, csv_file in zip(tools, csv_files):
        if not os.path.exists(csv_file):
            print(f"Warning: {csv_file} does not exist. Skipping {tool}.")
            continue
        df = pd.read_csv(csv_file)
        df.loc[(df["Time (s)"] == -1) | (~ df["Result"].map(valid_result)), "Time (s)"] = timeout
        data[tool] = df
    return data

def make_survival_line(tool, data, markers):
    """
    Creates a survival line for the given tool and its data.
    """
    # Sort the data by time
    data = data.sort_values(by="Time (s)", ascending=True, ignore_index=True)

    # Create the line
    return go.Scatter(
        x=data["Time (s)"],
        y=data.index,
        mode='lines+markers' if markers else 'lines',
        name=tool,
        marker=dict(size=4, symbol='x'),
        line=dict(shape='linear',width=2,simplify=True)
    ) 

def plot_identity_line(fig, end):
    idline = [0, end+.01]
    fig.add_trace(go.Scatter(
        x=idline,
        y=idline,
        mode='lines+markers',
        line=dict(
            color="black",
            width=1,
        )
    ))

def make_scatter_plot(data, output, timeout):
    """
    Creates a scatter plot for the given data.
    """
    (tool1, data1), (tool2, data2) = tuple(data.items())
    joint_data = data1.merge(data2, on="Name", suffixes=("_1", "_2"), validate="one_to_one")
    # print(joint_data)

    fig = go.Figure()
    plot_identity_line(fig, timeout)

    fig.add_trace(go.Scatter(
        x=joint_data["Time (s)_1"],
        y=joint_data["Time (s)_2"],
        mode='markers',
        marker=dict(size=5, symbol='x'),
        cliponaxis=False,
    ))

    # Set the layout
    fig.update_layout(
        #title="Scatter Plot of Benchmark Results",
        font_family="Linux Libertine Display O,serif",
        showlegend=False,
        xaxis_title=tool1 + " time (s)",
        yaxis_title=tool2 + " time (s)",
        margin=dict(l=0, r=5, t=5, b=0),
        plot_bgcolor='white',
        paper_bgcolor='white',
        xaxis=dict(
            type='log',
            range=(-2, math.log10(timeout)+.01),
            showgrid=True,
            gridcolor='lightgrey',
            layer='below traces',
            showline=True,
            linecolor='black',
            linewidth=1,
            mirror=True,
        ),
        yaxis=dict(
            type='log',
            range=(-2, math.log10(timeout)+.01),
            # scaleanchor = "x",
            # scaleratio = 1,
            showgrid=True,
            gridcolor='lightgrey',
            layer='below traces',
            showline=True,
            linecolor='black',
            linewidth=1,
            mirror=True
        ),
    )

    fig.write_image(output+".scatter.pdf", format='pdf', width=350, height=350)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('tools',
                        default='_error_',
                        help='Comma-separated tool names.')
    parser.add_argument('tool_csvs',
                        default='_error_',
                        help='List of comma-separated CSV files containing tool data.')
    parser.add_argument('timeout', type=int,
                        default=-1,
                        help='Time value for the timeout.')
    parser.add_argument('-o', '--output', dest='output', 
                        default='output',
                        help='Name of the output file')
    parser.add_argument('--no-legend', action='store_true',
                        help='Do not show the legend in the plot.')
    parser.add_argument('--scatter', action='store_true',
                        help='Also create a scatter plot.')
    parser.add_argument('--log-survival', action='store_true',
                        help='Use a log scale for the time axis in survival plots.')
    parser.add_argument('--markers-survival', action='store_true',
                        help='Use markers in the survival plot.')
    args = parser.parse_args()
    
    if args.tools == '_error_':
        sys.exit('Please specify the tool names.')
    if args.tool_csvs == '_error_':
        sys.exit('Please specify paths to the CSV files.')
    if args.timeout < 0:
        sys.exit('Please specify a positive timeout value.')

    tools = args.tools.strip().split(",")
    tool_csvs = args.tool_csvs.strip().split(",")
    if len(tools) != len(tool_csvs):
        sys.exit("Error: different numbers of tools and CSV file were entered.")

    data = read_csv_files(tools, tool_csvs, args.timeout)

    # Create the Plotly object for Figure
    fig = go.Figure()

    for tool in tools:
        line = make_survival_line(tool, data[tool], args.markers_survival)
        fig.add_trace(line)

    # set the labels
    fig.update_layout(
        font_family="Linux Libertine Display O,serif",
        #font_size=12,
        xaxis_title="Time (s)",
        yaxis_title="Number of benchmarks solved",
        margin=dict(l=0, r=0, t=0, b=0),
        plot_bgcolor='white',      # No background color
        paper_bgcolor='white',     # No outer background
        xaxis=dict(
            type='log' if args.log_survival else 'linear',
            showgrid=True,
            gridcolor='lightgrey',  # Grey grid lines
            # showline=True,             # Draw x=0 axis
            # linecolor='black',     # Axis color
            # linewidth=1
            # mirror=True
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='lightgrey',  # Grey grid lines
            showline=True,             # Draw x=0 axis
            linecolor='black',     # Axis color
            linewidth=1,
            mirror=True,
            zeroline=True,
            zerolinecolor='black',  # Color of the zero line
            zerolinewidth=1,         # Width of the zero line
        ),
        showlegend=not args.no_legend,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            # font=dict(size=8),
        )
    )

    fig.write_image(args.output+".survival.pdf", format='pdf', width=350, height=350)

    if args.scatter:
        if len(tools) == 2:
            make_scatter_plot(data, args.output, args.timeout)
        else:
            print("Scatter plot is only available for two tools.")
