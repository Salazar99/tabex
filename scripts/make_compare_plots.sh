#!/bin/bash

if [ -z "$1" ]; then
    basedir="data/latest"
else
    basedir="$1"
    shift
fi

timeout=120

tools="FOL (Z3 4.13.4),Tableau"
datasets=("nasa-boeing" "random" "random0")

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
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

set -x

for dataset in "${datasets[@]}"; do
    files="${basedir}/smt-quant_z3_${dataset}.csv,${basedir}/tableau_${dataset}.csv"
    python3 plot.py "${tools}" "${files}" ${timeout} --markers-survival --scatter -o "comp_${dataset}"
done
