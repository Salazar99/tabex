#!/usr/bin/env python3

import argparse
import os
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path

def summarize_benchmarks(df: pd.DataFrame) -> pd.DataFrame:
    df["temporal_sum"] = df[["f_nodes","g_nodes","u_nodes","r_nodes"]].sum(axis=1)
    grouped = df.groupby("benchmark")

    summary = grouped.agg(
        depth_median=("depth", "median"),
        depth_p95=("depth", lambda x: np.percentile(x, 95)),
        temp_depth_median=("temporal_depth", "median"),
        temp_depth_p95=("temporal_depth", lambda x: np.percentile(x, 95)),
        branch_mean=("branching_factor", "median"),
        horizon_median=("horizon", "median"),
        horizon_p95=("horizon", lambda x: np.percentile(x, 95)),
        f_sum=("f_nodes", "sum"),
        g_sum=("g_nodes", "sum"),
        u_sum=("u_nodes", "sum"),
        r_sum=("r_nodes", "sum"),
        temporal_total=("temporal_sum", "sum"),
    )

    # Normalize temporal operator mix
    for op in ["f_sum", "g_sum", "u_sum", "r_sum"]:
        summary[op] = (summary[op] / summary["temporal_total"] * 100).fillna(0)
    summary = summary.drop(columns=["temporal_total"])

    # Conditional formatting for horizons
    def format_val(v):
        if v >= 1e4:
            return f"{v:.1e}".replace("e+0", "e").replace("e+", "e")
        return f"{v:.0f}"

    def compact(a, b):
        return summary.apply(lambda x: f"{x[a]:.1f} ({x[b]:.1f})", axis=1)

    summary["Depth"] = compact("depth_median", "depth_p95")
    summary["TempDepth"] = compact("temp_depth_median", "temp_depth_p95")
    summary["Horizon"] = compact("horizon_median", "horizon_p95")
    summary["Branch"] = summary["branch_mean"].round(3)
    summary["Operators"] = summary.apply(
        lambda x: f"F {x['f_sum']:.1f}\\% / G {x['g_sum']:.1f}\\% / U {x['u_sum']:.1f}\\% / R {x['r_sum']:.1f}\\%",
        axis=1
    )

    return summary.reset_index()[["benchmark","Depth","TempDepth","Horizon","Branch","Operators"]]


def save_summary_table_latex_custom(summary: pd.DataFrame, output_dir: str):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    latex_path = out / "benchmark_summary_custom.tex"

    lines = []
    lines.append("\\begin{tabular}{lccccc}")
    lines.append("    \\toprule")
    lines.append("    \\emph{Benchmark} & Depth & Temporal Depth & Horizon & Branching Factor & Temporal Operator Dist. \\\\")
    lines.append("    \\midrule")

    for _, row in summary.iterrows():
        line = (
            f"    \\textbf{{{row['benchmark']}}} & "
            f"{row['Depth']} & {row['TempDepth']} & "
            f"{row['Horizon']} & {row['Branch']:.2f} & {row['Operators']} \\\\"
        )
        lines.append(line)

    lines.append("    \\bottomrule")
    lines.append("\\end{tabular}")

    tex = "\n".join(lines)
    with open(latex_path, "w") as f:
        f.write(tex)
    print(tex)
    print(f"\nSaved LaTeX table to {latex_path}")

# -----------------------------------------------------------------------------
# Plot functions
# -----------------------------------------------------------------------------

def plot_box(df, column, ylabel, output):
    plt.figure(figsize=(6, 4))
    sns.boxplot(x="benchmark", y=column, data=df, palette="gray")
    plt.ylabel(ylabel)
    plt.xlabel("")
    plt.tight_layout()
    plt.savefig(output)
    plt.close()

def plot_hist(df, column, bins, output):
    plt.figure(figsize=(6, 4))
    sns.histplot(data=df, x=column, hue="benchmark", bins=bins,
                 element="step", stat="density")
    plt.xlabel(column)
    plt.ylabel("Density")
    plt.tight_layout()
    plt.savefig(output)
    plt.close()

def plot_temporal_composition(df, output):
    tmp = df.copy()
    tmp["temporal_sum"] = tmp[["f_nodes", "g_nodes", "u_nodes", "r_nodes"]].sum(axis=1)
    for op in ["f_nodes", "g_nodes", "u_nodes", "r_nodes"]:
        tmp[op] = tmp[op] / tmp["temporal_sum"].replace(0, 1)
    agg = tmp.groupby("benchmark")[["f_nodes","g_nodes","u_nodes","r_nodes"]].mean()
    agg.plot(kind="bar", stacked=True, figsize=(6, 4),
             color=["#999999","#666666","#333333","#000000"])
    plt.ylabel("Fraction of temporal nodes")
    plt.xlabel("")
    plt.tight_layout()
    plt.savefig(output)
    plt.close()

def plot_depth_vs_branching(df, output):
    plt.figure(figsize=(6, 4))
    sns.scatterplot(data=df, x="depth", y="branching_factor",
                    hue="benchmark", alpha=0.6)
    plt.tight_layout()
    plt.savefig(output)
    plt.close()

# -----------------------------------------------------------------------------
# Batch plotting
# -----------------------------------------------------------------------------

def generate_all_plots(df, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    plot_box(df, "depth", "Formula depth", out / "box_depth.png")
    plot_box(df, "nodes", "Total nodes", out / "box_nodes.png")
    plot_hist(df, "horizon", 40, out / "hist_horizon.png")
    plot_temporal_composition(df, out / "temporal_composition.png")
    plot_depth_vs_branching(df, out / "scatter_depth_branching.png")

# -----------------------------------------------------------------------------
# Main entry point
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Read multiple benchmark CSV files and generate comparative plots."
    )
    parser.add_argument("csv_files", nargs="+",
                        help="List of CSV files, each representing one benchmark.")
    parser.add_argument("--output-dir", default="plots",
                        help="Directory to save plot outputs (default: plots).")
    args = parser.parse_args()

    try:
        frames = []
        for csv_path in args.csv_files:
            name = Path(csv_path).stem
            df = pd.read_csv(csv_path)
            df["benchmark"] = name
            frames.append(df)
            print(f"Loaded {len(df)} rows from {csv_path}")

        combined = pd.concat(frames, ignore_index=True)
        print(f"Total combined rows: {len(combined)}")
        os.makedirs(args.output_dir, exist_ok=True)
        print(f"Saving plots to: {args.output_dir}")

        generate_all_plots(combined, args.output_dir)
        save_summary_table_latex_custom(summarize_benchmarks(combined), args.output_dir)
        print("Plots generated successfully.")

    except FileNotFoundError as e:
        print(f"Error: {e}")
    except pd.errors.EmptyDataError:
        print("Error: One or more files are empty or invalid.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
