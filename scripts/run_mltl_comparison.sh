#!/bin/bash

if [ $# -lt 1 ]; then
    echo "Usage: $0 mltlsatdir [--timeout SECONDS] [--jobs N] [--max-mem MB] [--iters N] [--z3bin PATH] [--bench-sets \"SET1 SET2 ...\"]"
    exit 1
fi

mltlsatdir="$1"
shift

timeout=120
jobs=4
max_mem=30720
iters=5
z3bin=z3
bench_sets=("nasa-boeing" "random" "random0")
outdir=./output_mltl

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
        --z3bin)
            z3bin="$2"
            shift 2
            ;;
        --bench-sets)
            bench_sets=("$2")
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

set -x

if [[ " ${bench_sets[@]} " =~ " nasa-boeing " ]]; then
    ./run_bench.py --timeout ${timeout} --max-mem ${max_mem} --jobs ${jobs} --iters ${iters} -vv --csv "${outdir}/tableau_nasa-boeing.csv" -b "${mltlsatdir}/" "${mltlsatdir}/benchmark_list/nasa-boeing.list" tableau &> "${outdir}/tableau_nasa-boeing.log"
    #./run_bench.py --timeout ${timeout} --max-mem ${max_mem} --jobs ${jobs} --iters ${iters} -vv --csv "${outdir}/smt-quant_z3_nasa-boeing.csv" -b "${mltlsatdir}/" "${mltlsatdir}/benchmark_list/nasa-boeing.list" smt-quant "${mltlsatdir}/translator/src/MLTLConvertor" "${z3bin}" &> "${outdir}/smt-quant_z3_nasa-boeing.log"
fi

if [[ " ${bench_sets[@]} " =~ " random " ]]; then
    ./run_bench.py --timeout ${timeout} --max-mem ${max_mem} --jobs ${jobs} --iters ${iters} -vv --csv "${outdir}/tableau_random.csv" -b "${mltlsatdir}/" "${mltlsatdir}/benchmark_list/random.list" tableau &> "${outdir}/tableau_random.log"
    #./run_bench.py --timeout ${timeout} --max-mem ${max_mem} --jobs ${jobs} --iters ${iters} -vv --csv "${outdir}/smt-quant_z3_random.csv" -b "${mltlsatdir}/" "${mltlsatdir}/benchmark_list/random.list" smt-quant "${mltlsatdir}/translator/src/MLTLConvertor" "${z3bin}" &> "${outdir}/smt-quant_z3_random.log"
fi

if [[ " ${bench_sets[@]} " =~ " random0 " ]]; then
    ./run_bench.py --timeout ${timeout} --max-mem ${max_mem} --jobs ${jobs} --iters ${iters} -vv --csv "${outdir}/tableau_random0.csv" -b "${mltlsatdir}/" "${mltlsatdir}/benchmark_list/random0.list" tableau &> "${outdir}/tableau_random0.log"
    #./run_bench.py --timeout ${timeout} --max-mem ${max_mem} --jobs ${jobs} --iters ${iters} -vv --csv "${outdir}/smt-quant_z3_random0.csv" -b "${mltlsatdir}/" "${mltlsatdir}/benchmark_list/random0.list" smt-quant "${mltlsatdir}/translator/src/MLTLConvertor" "${z3bin}" &> "${outdir}/smt-quant_z3_random0.log"
fi
