#!/bin/bash

function make_tools_csvs() {
    set +x
    local basedir="$1"
    shift
    local dataset="$1"
    shift
    local tool_names=("$@")
    local tool_csvs=""

    for tool in "${tool_names[@]}"; do
        tool_csvs+="${basedir}/${tool}_${dataset}.csv,"
    done

    echo "${tool_csvs%,}"
    set -x
}

logic="$1"
shift
if [ "$logic" != "MLTL" ] && [ "$logic" != "STL" ]; then
    echo "Error: first argument must be either MLTL or STL"
    echo "Usage: $0 {MLTL|STL} [--timeout N] [--bench-sets \"SET1 SET2 ...\"] [--base-dir DIR]"
    exit 1
fi


basedir=""
timeout=120
datasets=()

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --timeout)
            timeout="$2"
            shift 2
            ;;
        --bench-sets)
            datasets=($2)
            shift 2
            ;;
        --base-dir)
            basedir="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

# Set defaults based on logic
if [ "$logic" = "MLTL" ]; then
    if [ -z "$basedir" ]; then
        basedir="../resources/results/MLTL"
    fi
    if [ ${#datasets[@]} -eq 0 ]; then
        datasets=("nasa-boeing" "random" "random0")
    fi
    tools="STLSat (par),STLSat (tableau),STLSat (FOL),STLTree (tableau),MLTLSAT (Z3 4.15.3)"
    tool_names=("stlcc_parallel" "stlcc" "stlcc_fol" "stltree" "mltlsat")
    prefix="mltl"
elif [ "$logic" = "STL" ]; then
    if [ -z "$basedir" ]; then
        basedir="../resources/results/STL"
    fi
    if [ ${#datasets[@]} -eq 0 ]; then
        datasets=("random" "random0")
    fi
    tools="STLSat (par),STLSat (tableau),STLSat (FOL),STLTree (tableau)"
    tool_names=("stlcc_parallel" "stlcc" "stlcc_fol" "stltree")
    prefix="stl"
fi

set -x

# Generate main plots
for dataset in "${datasets[@]}"; do
    python3 plot.py "${tools}" "$(make_tools_csvs "${basedir}" "${dataset}" "${tool_names[@]}")" ${timeout} --markers-survival -o "${prefix}_${dataset}"
done


# Generate scatter plots
tools_scatter="STLSat (tableau),STLSat (FOL)"
tool_names_scatter=("stlcc" "stlcc_fol")

for dataset in "${datasets[@]}"; do
    python3 plot.py "${tools_scatter}" "$(make_tools_csvs "${basedir}" "${dataset}" "${tool_names_scatter[@]}")" ${timeout} --scatter -o "${prefix}_${dataset}"
done
