#!/bin/bash

if [ $# -lt 1 ]; then
    echo "Usage: $0 benchdir [--timeout SECONDS] [--jobs N] [--max-mem MB] [--iters N] [--tools \"TOOL1 TOOL2 ...\"] [--stltree-path PATH]"
    exit 1
fi

benchdir="$1"
shift

timeout=120
jobs=4
max_mem=30720
iters=5
tools=("stlcc" "stlcc_fol" "stltree")
bench_set=random_stl
outdir=./output_stl

while [[ $# -gt 0 ]]; do
    case "$1" in
        --timeout)
            timeout="$2"
            shift 2
            ;;
        --jobs)
            jobs="$2"
            shift 2
            ;;
        --max-mem)
            max_mem="$2"
            shift 2
            ;;
        --iters)
            iters="$2"
            shift 2
            ;;
        --tools)
            tools=("$2")
            shift 2
            ;;
        --stltree-path)
            stltree_path="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

if [ ! -d "${outdir}" ]; then
    mkdir -p "${outdir}"
fi

ulimit -s unlimited

set -x

if [[ " ${tools[@]} " =~ " stlcc " ]]; then
    ./run_bench.py --timeout ${timeout} --max-mem ${max_mem} --jobs ${jobs} --iters ${iters} -vv --csv "${outdir}/stlcc_${bench_set}.csv" -b "${benchdir}/" "${benchdir}/${bench_set}.list" stlcc &> "${outdir}/stlcc_${bench_set}.log"
fi

if [[ " ${tools[@]} " =~ " stlcc_fol " ]]; then
    ./run_bench.py --timeout ${timeout} --max-mem ${max_mem} --jobs ${jobs} --iters ${iters} -vv --csv "${outdir}/stlcc_fol_${bench_set}.csv" -b "${benchdir}/" "${benchdir}/${bench_set}.list" stlcc --fol &> "${outdir}/stlcc_fol_${bench_set}.log"
fi

if [[ " ${tools[@]} " =~ " stltree " ]]; then
    if [ -z "${stltree_path}" ]; then
        echo "Error: --stltree-path must be provided when using stltree tool."
        exit 1
    fi
    ./run_bench.py --timeout ${timeout} --max-mem ${max_mem} --jobs ${jobs} --iters ${iters} -vv --csv "${outdir}/stltree_${bench_set}.csv" -b "${benchdir}/" "${benchdir}/${bench_set}.list" stltree "${stltree_path}" &> "${outdir}/stltree_${bench_set}.log"
fi
